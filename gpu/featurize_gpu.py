"""
featurize_gpu —— 用 GPU (torch) 批量向量化提取经典统计隐写特征。

复刻已验证的 11 维特征口径 (与 src/fsfeatures.py / src/steganalysis.py 一致):
    0 Rm  1 Sm  2 Rn  3 Sn               (RS 四类组计数)
    4 RS_Gr = (Rm-Sm)/G  5 RS_Gn = (Rn-Sn)/G
    6 chi2_pvalue         7 diff_entropy
    8 lsb_diff_entropy    9 median_prefix_p
    10 chi2_stat

把原本逐图 Python 循环 (RS 逐组、卡方逐图、前缀卡方 20 段) 全部写成张量化算子,
在 CUDA 上一批并行算完 → 既提速度又真正吃满 GPU。特征向量对训练/推理无区别。

用法(库):  from featurize_gpu import extract_features_gpu, FEAT_NAMES, check_vs_cpu
"""
from __future__ import annotations
import os, sys
import numpy as np

FEAT_NAMES = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
              "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
              "median_prefix_p", "chi2_stat"]

_PREFIX = np.array([0, 1, 1, 0], dtype=np.int64)


def pick_gpu():
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def _chi2_stat_p(counts_np):
    """counts_np: (B,256) -> (stat, p, df-free)  在 numpy/scipy 侧算 p。"""
    even = counts_np[:, 0::2]; odd = counts_np[:, 1::2]
    sums = even + odd
    msk = sums > 0
    stat = np.where(msk, (even - odd) ** 2 / np.maximum(sums, 1), 0.0).sum(1)
    df = msk.sum(1) - 1
    p = np.zeros_like(stat)
    good = df > 0
    if good.any():
        from scipy.stats import chi2 as _chi2
        p[good] = _chi2.sf(stat[good], df[good])
    return stat.astype(np.float64), p.astype(np.float64)


def _hist256(flat):
    """flat: (B,L) long 值 0..255 -> (B,256) float32 计数。"""
    import torch
    zeros = torch.zeros(flat.shape[0], 256, dtype=torch.float32, device=flat.device)
    ones = torch.ones(flat.shape[0], flat.shape[1], dtype=torch.float32, device=flat.device)
    return zeros.scatter_add_(1, flat, ones)


def _entropy_bits(hist):
    """hist: (B,C) 计数 -> (B,) 香农熵(比特)。"""
    import torch
    pm = hist / hist.sum(1, keepdim=True).clamp_min(1e-12)
    mask = pm > 0
    logp = torch.zeros_like(pm)
    logp[mask] = torch.log2(pm[mask])
    return -(pm * logp).sum(1)


def _features_batch(xt):
    """xt: (B,H,W) int64 @ CUDA -> 返回 11 列 numpy (各自 (B,))。"""
    import torch
    B, H, W = xt.shape
    flat = xt.reshape(B, -1)
    L = H * W

    # ---- RS (4像素组, 掩码 M=[0,1,1,0]) ----
    m = L - L % 4
    groups = flat[:, :m].reshape(B, -1, 4)          # (B,G,4)
    fg = groups.diff(dim=2).abs().sum(2)             # (B,G)
    mask = torch.from_numpy(_PREFIX).to(xt.device)
    pos = groups ^ mask
    neg = groups ^ (1 - mask)
    fM = pos.diff(dim=2).abs().sum(2)
    fN = neg.diff(dim=2).abs().sum(2)
    G = fg.shape[1]
    Rm = (fM > fg).sum(1).float(); Sm = (fM < fg).sum(1).float()
    Rn = (fN > fg).sum(1).float(); Sn = (fN < fg).sum(1).float()
    Gr = (Rm - Sm) / G
    Gn = (Rn - Sn) / G

    # ---- 全局灰度直方图 -> 卡方 ----
    cnt = _hist256(flat)
    ev = cnt[:, 0::2]; od = cnt[:, 1::2]; su = ev + od
    msk = su > 0
    stat = ((ev - od).pow(2) / su.clamp_min(1e-12) * msk).sum(1)
    dfv = msk.sum(1) - 1

    # ---- 差分熵 (水平+垂直相邻绝对差) ----
    d1 = xt.diff(dim=2).abs()                      # (B,H,W-1)
    d2 = xt.diff(dim=1).abs()                      # (B,H-1,W)
    dcat = torch.cat([d1.reshape(B, -1), d2.reshape(B, -1)], 1).clamp(0, 255)
    ent_diff = _entropy_bits(_hist256(dcat))

    # ---- LSB 位平面差分熵 ----
    lsb = xt & 1
    l1 = lsb.diff(dim=2).abs().reshape(B, -1)
    l2 = lsb.diff(dim=1).abs().reshape(B, -1)
    lcat = torch.cat([l1, l2], 1)
    ent_lsb = _entropy_bits(_hist256(lcat))       # 0..1

    # ---- 前缀中位卡方 p (20 段, 与 fsfeatures 一致) ----
    steps = 20
    st2 = []
    for i in range(1, steps + 1):
        end = max(64, int(L * i / steps))
        st2.append(_chi2_stat_p(_hist256(flat[:, :end]).cpu().numpy()))

    # 收集到 CPU numpy
    def _to_np(t):
        return t.detach().cpu().numpy()

    RmN, SmN, RnN, SnN = (_to_np(t) for t in (Rm, Sm, Rn, Sn))
    GrN, GnN = _to_np(Gr), _to_np(Gn)
    statN = _to_np(stat)
    # 全局卡方 p 也走 scipy (与 CPU 版一致)
    _, pN = _chi2_stat_p(cnt.cpu().numpy())
    entDiffN = _to_np(ent_diff)
    entLsbN = _to_np(ent_lsb)
    medp = np.median(np.stack([_p for _s, _p in st2], 1), 1)   # (B,)
    chi_statN = statN

    cols = [RmN, SmN, RnN, SnN, GrN, GnN, pN, entDiffN, entLsbN, medp, chi_statN]
    return cols


def extract_features_gpu(x_u8, chunk: int = 128, device: str = "auto"):
    """x_u8: (N,H,W) uint8 灰度。返回 (N,11) float64 特征。"""
    import torch
    dev = pick_gpu() if device == "auto" else device
    if x_u8.ndim == 3 and x_u8.shape[-1] in (3, 4):
        x_u8 = x_u8[..., 0]
    x_u8 = np.ascontiguousarray(x_u8, dtype=np.uint8)
    N = x_u8.shape[0]
    cols = [[] for _ in FEAT_NAMES]
    for s in range(0, N, chunk):
        xt = torch.from_numpy(x_u8[s:s + chunk].astype(np.int64)).to(dev)
        c = _features_batch(xt)
        for j in range(len(cols)):
            cols[j].append(np.asarray(c[j]))
    return np.stack([np.concatenate(cols[j]) for j in range(len(cols))], 1)


# ------------------- 与 CPU 实现一致性验证 -------------------
def check_vs_cpu(x_u8, tol: float = 1e-5):
    """抽取一张对照: GPU 特征 vs src/steganalysis 的 RS/熵, fsfeatures 接口同名。"""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
    import steganalysis as SA
    g = extract_features_gpu(x_u8[:1], chunk=1)[0]
    img = x_u8[0]
    rs = SA.rs_metrics(img)
    h = SA.diff_entropy(img)
    lg = SA.lsb_diff_entropy(img)
    flat = img.ravel()
    ps = []
    for i in range(1, 21):
        end = max(64, int(flat.size * i / 20))
        c = np.bincount(flat[:end], minlength=256).astype(np.float64)
        _, p, _ = SA.chi2_stats(c)
        ps.append(p if p is not None else 0.0)
    medp = float(np.median(np.asarray(ps))) if ps else 0.0
    pairs = {
        "Rm": (g[0], rs["Rm"]), "Sm": (g[1], rs["Sm"]),
        "Rn": (g[2], rs["Rn"]), "Sn": (g[3], rs["Sn"]),
        "RS_Gr": (g[4], rs["Gr"]), "RS_Gn": (g[5], rs["Gn"]),
        "diff_entropy": (g[7], h), "lsb_diff_entropy": (g[8], lg),
        "median_prefix_p": (g[9], medp),
    }
    ok = True
    for k, (a, b) in pairs.items():
        d = abs(a - b)
        flag = "OK" if d < tol else "MISMATCH"
        if d > tol: ok = False
        print(f"  {k:<18} gpu={a:.6f} cpu={b:.6f} diff={d:.2e}  {flag}")
    print("  [一致性]", "全部一致" if ok else "存在差异!")
    return ok


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    im = rng.integers(0, 256, (256, 256), dtype=np.uint8)
    ok = check_vs_cpu(im[None])
    sys.exit(0 if ok else 1)