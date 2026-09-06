"""
featurize_v2 —— 在原 11 维 fsfeatures 之上, 添加 SRM 30 残差统计 + 20 段前缀 p 全量
+ texture_noise + est_rate + lsb_diff_entropy 20 段前缀, 共计 11 + 30*3 + 20
+ 2 + 20 = 143 维(或子集, 默认 11+90+20+2+20=143)。

输入/输出约定:
  - 输入 uint8 灰度图 (H,W) 或 (N,H,W)
  - 返回 np.ndarray (N, N_FEAT), 列名 = ALL_FEATURE_NAMES
  - 旧 11 维兼容模式 EXTEND_LEVEL=0; 中等=1(只加残差统计+texture); 全量=2

依赖: srm_filter.py, src/steganalysis.py(texture_noise/est_rate)
"""
from __future__ import annotations
import os, sys
import numpy as np

THIS = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(THIS)
if PROJ not in sys.path:
    sys.path.insert(0, PROJ)
SRC = os.path.join(PROJ, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fsfeatures import get_lib  # 11 维 C++ 特征

BASE_11 = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
           "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
           "median_prefix_p", "chi2_stat"]

SRM_STAT_NAMES = (
    [f"srm_mu_c{c}" for c in range(30)] +
    [f"srm_absmean_c{c}" for c in range(30)] +
    [f"srm_std_c{c}" for c in range(30)]
)
PREFIX20_NAMES = [f"prefix_p{i+1}" for i in range(20)]
L20_NAMES = [f"lsb_prefix_p{i+1}" for i in range(20)]
EXTRA_NAMES = ["texture_noise", "est_rate"]

ALL_FEATURE_NAMES = BASE_11 + SRM_STAT_NAMES + PREFIX20_NAMES + EXTRA_NAMES + L20_NAMES  # 11+90+20+2+20=143
N_FEAT = len(ALL_FEATURE_NAMES)


# ---- texture_noise / est_rate (复用 steganalysis.analyze 中的语义) ----
def _texture_noise(img_u8: np.ndarray) -> float:
    h = float(np.std(img_u8.astype(np.float32)))
    return float(np.clip((h - 1.2) / (7.0 - 1.2), 0.0, 1.0))


def _est_rate(chi_p: float, median_p: float) -> float:
    """简单启发式: 卡方 p 越小、估计嵌入率越高。值域 0~1。"""
    p = min(chi_p, median_p)
    return float(np.clip(1.0 - 2.0 * p, 0.0, 1.0))


# ---- 20 段前缀 p (用 numpy 一次性算 20 个, 比 C++ 循环快且一次返回) ----
def _prefix20_p(img_u8: np.ndarray) -> np.ndarray:
    N = img_u8.size
    if N < 64:
        return np.full(20, 1.0, dtype=np.float32)
    flat = img_u8.reshape(-1)
    out = np.empty(20, dtype=np.float32)
    for k in range(1, 21):
        end = min(N, max(64, int(N * k / 20)))
        c = np.bincount(flat[:end], minlength=256).astype(np.float64)
        e = c[0::2]; o = c[1::2]; s = e + o
        msk = s > 0
        if not msk.any():
            out[k - 1] = 0.0
            continue
        stat = ((e[msk] - o[msk]) ** 2 / s[msk]).sum()
        df = int(msk.sum()) - 1
        if df <= 0:
            out[k - 1] = 0.0
            continue
        # 用同款不完全伽马
        from scipy.stats import chi2
        out[k - 1] = float(chi2.sf(stat, df))
    return out


def _lsb_prefix20_p(img_u8: np.ndarray) -> np.ndarray:
    N = img_u8.size
    if N < 64:
        return np.full(20, 1.0, dtype=np.float32)
    flat = (img_u8.reshape(-1) & 1).astype(np.int64)
    out = np.empty(20, dtype=np.float32)
    for k in range(1, 21):
        end = min(N, max(64, int(N * k / 20)))
        c = np.bincount(flat[:end], minlength=2).astype(np.float64)
        s = c.sum()
        if s <= 0:
            out[k - 1] = 0.0; continue
        chi = ((c - s / 2.0) ** 2 / (s / 2.0)).sum()
        out[k - 1] = float(np.exp(-chi / 2.0))  # 1 自由度生存函数近似
    return out


# ---- SRM 30 残差统计 (复用 srm_residuals_np) ----
def _srm_stats(x_u8: np.ndarray, T: float = 4.0) -> np.ndarray:
    from srm_filter import srm_residuals_np
    r = srm_residuals_np(x_u8)               # (30,H,W) float32
    rc = np.clip(r, -T, T)
    mu = rc.mean(axis=(-2, -1))               # (30,)
    am = np.abs(rc).mean(axis=(-2, -1))       # (30,)
    sd = np.abs(rc).std(axis=(-2, -1))        # (30,)
    return np.concatenate([mu, am, sd]).astype(np.float32)


# ---- 单图主入口 ----
def featurize_v2(img_u8: np.ndarray, T: float = 4.0) -> np.ndarray:
    """单张图 (H,W) uint8 -> (143,) 特征向量。"""
    lib = get_lib()
    base = lib.features(img_u8)
    base_v = np.array([base[k] for k in BASE_11], dtype=np.float64)
    srm_v = _srm_stats(img_u8, T).astype(np.float64)
    pf_v = _prefix20_p(img_u8).astype(np.float64)
    l20_v = _lsb_prefix20_p(img_u8).astype(np.float64)
    tex = _texture_noise(img_u8)
    rate = _est_rate(base["chi2_pvalue"], base["median_prefix_p"])
    extra = np.array([tex, rate], dtype=np.float64)
    return np.concatenate([base_v, srm_v, pf_v, extra, l20_v])


def featurize_batch_v2(x_u8: np.ndarray, T: float = 4.0) -> np.ndarray:
    """批量 (N,H,W) uint8 -> (N, 143) 特征矩阵。"""
    x = np.ascontiguousarray(x_u8, dtype=np.uint8)
    N = x.shape[0]
    out = np.empty((N, N_FEAT), dtype=np.float32)
    for i in range(N):
        out[i] = featurize_v2(x[i], T)
    return out


# ---- 一致性/性能自测 ----
if __name__ == "__main__":
    import time
    rng = np.random.default_rng(0)
    im = rng.integers(0, 256, (256, 256), dtype=np.uint8)
    t = time.time()
    v = featurize_v2(im)
    dt = time.time() - t
    print(f"v2 单图 143 维 耗时 {dt:.3f}s, 形状 {v.shape}, 范围 [{v.min():.3f}, {v.max():.3f}]")
    print("前 11 维(应与 fsfeatures 一致):", np.round(v[:11], 3))
    # 批量
    batch = np.stack([im, im])
    t = time.time(); F = featurize_batch_v2(batch); dt2 = time.time() - t
    print(f"v2 批量 2 张: {dt2:.3f}s")
    # 与 C++ 11 维一致性
    lib = get_lib()
    b = lib.features(im)
    for k, name in enumerate(BASE_11):
        if abs(v[k] - b[name]) > 1e-3:
            print(f"  ! 差异: {name} py={v[k]} cpp={b[name]}")
    print("OK")
