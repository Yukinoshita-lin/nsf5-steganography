"""
featurize_gpu_v2 —— GPU 端提取扩展特征 (143 维), 与 src/featurize_v2.py 口径一致:

  0..10   11 维基础 (与 featurize_gpu 一致)
 11..40   30 维 SRM 残差均值 (clip ±4)
 41..70   30 维 SRM 残差 |r| 均值
 71..100  30 维 SRM 残差 |r| 标准差
 101..120 20 段前缀卡方 p
 121      texture_noise (整体 std 归一)
 122      est_rate      (1 - 2*min(chi_p, median_p))
 123..142 20 段 LSB 前缀卡方 p

输入: (N,H,W) uint8
输出: (N, 143) float32
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
NAMES = BASE_11 + SRM_STAT_NAMES + PREFIX20_NAMES + EXTRA_NAMES + L20_NAMES
N_FEAT = len(NAMES)

_SRM = None  # (kernels (30,1,5,5) on cuda)


def _load_srm_kernels(device):
    global _SRM
    import torch
    if _SRM is None:
        from srm_filter import SRM_KERNELS
        _SRM = torch.from_numpy(SRM_KERNELS[:, None, :, :]).to(device)
    return _SRM


def _chi2_stat_p(counts_t):
    """counts_t: (B,256) torch -> (stat(B,), p(B,)) numpy."""
    even = counts_t[:, 0::2]; odd = counts_t[:, 1::2]; su = even + odd
    msk = su > 0
    stat = ((even - odd).pow(2) / su.clamp_min(1e-12) * msk).sum(1)
    dfv = msk.sum(1) - 1
    stat_np = stat.cpu().numpy()
    df_np = dfv.cpu().numpy()
    p = np.zeros_like(stat_np)
    good = df_np > 0
    if good.any():
        from scipy.stats import chi2 as _chi2
        p[good] = _chi2.sf(stat_np[good], df_np[good])
    return stat_np, p


def _hist256(flat):
    """flat: (B,L) long on device -> (B,256) float on device."""
    import torch
    z = torch.zeros(flat.shape[0], 256, dtype=torch.float32, device=flat.device)
    o = torch.ones_like(flat, dtype=torch.float32)
    return z.scatter_add_(1, flat, o)


def _entropy_bits(hist):
    """hist: (B,C) -> (B,) 香农熵(比特)。"""
    import torch
    pm = hist / hist.sum(1, keepdim=True).clamp_min(1e-12)
    mask = pm > 0
    logp = torch.zeros_like(pm)
    logp[mask] = torch.log2(pm[mask])
    return -(pm * logp).sum(1)


_PREFIX = np.array([0, 1, 1, 0], dtype=np.int64)


def _srm_residuals(xt):
    """xt: (B,1,H,W) float @ device → (B,30,H,W) float (clip ±4)。"""
    import torch
    k = _load_srm_kernels(xt.device)
    r = torch.nn.functional.conv2d(xt, k, padding=2)         # (B,30,H,W)
    return r.clamp(-4.0, 4.0)


def _features_v2(xt, sub_u8):
    """xt: (B,H,W) int64 @ device; sub_u8: (B,H,W) uint8 numpy.
    返回 (B, 143) float32, 列顺序与 NAMES 对齐。
    """
    import torch
    B, H, W = xt.shape
    L = H * W
    flat = xt.reshape(B, -1)

    # ----- 11 维基础 (同 featurize_gpu) -----
    m = L - L % 4
    groups = flat[:, :m].reshape(B, -1, 4)
    fg = groups.diff(dim=2).abs().sum(2)
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

    cnt = _hist256(flat)
    statN, pN = _chi2_stat_p(cnt)

    d1 = xt.diff(dim=2).abs(); d2 = xt.diff(dim=1).abs()
    dcat = torch.cat([d1.reshape(B, -1), d2.reshape(B, -1)], 1).clamp(0, 255)
    ent_diff = _entropy_bits(_hist256(dcat)).cpu().numpy()

    lsb = xt & 1
    l1 = lsb.diff(dim=2).abs().reshape(B, -1)
    l2 = lsb.diff(dim=1).abs().reshape(B, -1)
    lcat = torch.cat([l1, l2], 1)
    ent_lsb = _entropy_bits(_hist256(lcat)).cpu().numpy()

    steps = 20
    st2 = []
    for i in range(1, steps + 1):
        end = max(64, int(L * i / steps))
        st2.append(_chi2_stat_p(_hist256(flat[:, :end])))
    p20 = np.stack([_p for _s, _p in st2], 1).astype(np.float32)   # (B,20)
    medp = np.median(p20, 1).astype(np.float32)

    # ----- SRM 30 残差统计 -----
    xf = sub_u8.astype(np.float32) / 255.0  # (B,H,W) 0~1, 减少 conv 数值
    xf_t = torch.from_numpy(np.ascontiguousarray(xf)).to(xt.device).unsqueeze(1)  # (B,1,H,W)
    r = _srm_residuals(xf_t)                                                       # (B,30,H,W)
    # mean / absmean / abs.std  三个统计 -> 各 30 维
    mu = r.mean(dim=(-1, -2))                                                      # (B,30)
    am = r.abs().mean(dim=(-1, -2))                                                # (B,30)
    sd = r.abs().std(dim=(-1, -2))                                                 # (B,30)
    srm_v = torch.cat([mu, am, sd], 1).cpu().numpy().astype(np.float32)            # (B,90)

    # ----- texture_noise / est_rate (在 numpy 算) -----
    tex = sub_u8.astype(np.float32).reshape(B, -1).std(1)                          # (B,)
    tex = np.clip((tex - 1.2) / (7.0 - 1.2), 0.0, 1.0)
    rate = np.clip(1.0 - 2.0 * np.minimum(pN, medp.astype(np.float64)), 0.0, 1.0).astype(np.float32)

    # ----- 20 段 LSB 前缀 p -----
    flat_lsb = (sub_u8.reshape(B, -1) & 1).astype(np.int64)                        # numpy
    l20 = np.empty((B, 20), dtype=np.float32)
    for i in range(1, 21):
        end = max(64, int(L * i / 20))
        if end > L: end = L
        c0 = np.zeros((B, 2), dtype=np.int64)
        # 加速: 对 (B,L) bool 取累加
        bflat = flat_lsb[:, :end]
        c0[:, 0] = (bflat == 0).sum(1)
        c0[:, 1] = (bflat == 1).sum(1)
        s = c0.sum(1, keepdims=True).astype(np.float64)
        chi = ((c0 - s / 2.0).astype(np.float64) ** 2 / (s / 2.0)).sum(1)
        l20[:, i - 1] = np.exp(-chi / 2.0).astype(np.float32)   # 1 自由度生存函数

    cols = [
        Rm.cpu().numpy().astype(np.float32),
        Sm.cpu().numpy().astype(np.float32),
        Rn.cpu().numpy().astype(np.float32),
        Sn.cpu().numpy().astype(np.float32),
        Gr.cpu().numpy().astype(np.float32),
        Gn.cpu().numpy().astype(np.float32),
        pN.astype(np.float32),
        ent_diff.astype(np.float32),
        ent_lsb.astype(np.float32),
        medp,
        statN.astype(np.float32),
    ]
    base = np.stack(cols, 1)              # (B, 11)
    full = np.concatenate([base, srm_v, p20, tex[:, None], rate[:, None], l20], 1)  # (B, 143)
    return full


def extract_features_v2_gpu(x_u8, chunk: int = 64, device: str = "auto"):
    """x_u8: (N,H,W) uint8 灰度。返回 (N,143) float32。无 SRM 单通道预处理层。"""
    import torch
    import featurize_gpu as _FG
    dev = _FG.pick_gpu() if device == "auto" else device
    if x_u8.ndim == 3 and x_u8.shape[-1] in (3, 4):
        x_u8 = x_u8[..., 0]
    x_u8 = np.ascontiguousarray(x_u8, dtype=np.uint8)
    N = x_u8.shape[0]
    out = np.empty((N, N_FEAT), dtype=np.float32)
    for s in range(0, N, chunk):
        sub = x_u8[s:s + chunk]
        xt = torch.from_numpy(sub.astype(np.int64)).to(dev)
        out[s:s + chunk] = _features_v2(xt, sub)
    return out


if __name__ == "__main__":
    import time
    rng = np.random.default_rng(0)
    im = rng.integers(0, 256, (256, 256), dtype=np.uint8)
    F = extract_features_v2_gpu(im[None], chunk=1)
    print("v2 单图 shape", F.shape, "范围", F.min(), F.max())
    # 批量
    t = time.time(); Fb = extract_features_v2_gpu(np.stack([im] * 32), chunk=32)
    print(f"v2 32 张 256x256: {time.time()-t:.3f}s")
    # 512x512
    big = rng.integers(0, 256, (512, 512), dtype=np.uint8)
    t = time.time(); Fb = extract_features_v2_gpu(np.stack([big] * 16), chunk=8)
    print(f"v2 16 张 512x512: {time.time()-t:.3f}s")
