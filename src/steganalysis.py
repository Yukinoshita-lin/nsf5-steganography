"""
盲隐写分析 (Blind Steganalysis) —— 面向 8bit 图像 LSB/矩阵类隐写。

信号来源
--------
1) 卡方检验 (Westfeld): 相邻灰度对 (2i,2i+1) 频率在嵌密后趋近均衡。
   p 值高 → 该区已随机化/嵌入。
2) RS 分析 (Fridrich-Goljan-Du): 将灰度流分成 4 像素组, 用掩码 M=[0,1,1,0]
   及其补掩码 -M 施加 LSB 翻转, 统计"常规(R)/奇异(S)"组。
   定义负掩码常规-奇异缺口 Gn=(R_-M - S_-M)/N 与正掩码缺口 Gr=(R_M-S_M)/N。
   干净图 LSB 平面有结构 → Gn 明显为正 (常在 0.3~0.7);
   隐写使 LSB 平面随机化 → Gn 显著下降, 全随机时≈0。

说明
----
盲隐写分析本质是启发式: 没有 cover 原图时, 绝对概率无法精确给出。本程序
组合多个统计量给出 0..1 的"隐写倾向概率"作为判读参考, 供评估使用。
"""

from __future__ import annotations
import math
import numpy as np


# ---------------- 正则化不完全伽马(自实现) ----------------
def _gser(a, x, itmax=200, eps=3e-14):
    if x <= 0:
        return 0.0
    ap, s, del_ = a, 1.0 / a, 1.0 / a
    for _ in range(itmax):
        ap += 1.0
        del_ *= x / ap
        s += del_
        if abs(del_) < abs(s) * eps:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a, x, itmax=200, eps=3e-14, fpmin=1e-300):
    b = x + 1.0 - a
    c, d, h = 1.0 / fpmin, 1.0 / b, 1.0 / b
    for i in range(1, itmax + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1.0) < eps:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gamma_p(a, x):
    return _gser(a, x) if x < a + 1.0 else 1.0 - _gcf(a, x)


def gamma_q(a, x):
    return 1.0 - _gser(a, x) if x < a + 1.0 else _gcf(a, x)


def chi2_sf(x, df):
    """卡方生存函数 1-CDF。"""
    return gamma_q(df / 2.0, x / 2.0)


# ---------------- 通道抽取 ----------------
def _channel(image):
    img = np.ascontiguousarray(image)
    return img[..., 0] if img.ndim == 3 else img


def _gray_counts(image):
    return np.bincount(_channel(image).ravel(), minlength=256).astype(np.float64)


# ---------------- 卡方 ----------------
def chi2_stats(counts: np.ndarray):
    even = counts[0::2]; odd = counts[1::2]
    sums = even + odd
    mask = sums > 0
    n = int(mask.sum())
    if n == 0:
        return 0.0, 0.0, 0
    stat = float(np.sum((even[mask] - odd[mask]) ** 2 / sums[mask]))
    return stat, float(chi2_sf(stat, n - 1)), n - 1


# ---------------- 内容本底随机度(差分熵) ----------------
def diff_entropy(image, axis_bins=256):
    """相邻像素绝对差值的香农熵(比特/样本), 0~log2(256)=8。
    平滑/结构化图低(≈1~3), 高噪声/抖动图接近 8 → 估图像天然 LSB 随机基线。
    """
    ch = _channel(image).astype(np.int16)
    d = np.concatenate([
        np.abs(np.diff(ch, axis=1)).ravel(),
        np.abs(np.diff(ch, axis=0)).ravel(),
    ])
    hist = np.bincount(np.clip(d, 0, axis_bins - 1), minlength=axis_bins).astype(np.float64)
    hist = hist / hist.sum()
    nz = hist[hist > 0]
    return float(-np.sum(nz * np.log2(nz)))


# ---------------- RS 分析 ----------------
def rs_metrics(image, mask=np.array([0, 1, 1, 0])):
    ch = _channel(image)
    flat = ch.ravel()
    m = len(flat) - len(flat) % 4
    groups = flat[:m].reshape(-1, 4)
    n = groups.shape[0]
    if n == 0:
        return {"Rm": 0, "Sm": 0, "Rn": 0, "Sn": 0, "Gr": 0.0, "Gn": 0.0}
    gi = groups.astype(np.int16)
    fg = np.abs(np.diff(gi, axis=1)).sum(axis=1)
    pos = ((gi ^ mask) & 0xFF).astype(np.int16)
    neg = ((gi ^ (1 - mask)) & 0xFF).astype(np.int16)
    fM = np.abs(np.diff(pos, axis=1)).sum(axis=1)
    fN = np.abs(np.diff(neg, axis=1)).sum(axis=1)
    Rm = int(np.sum(fM > fg)); Sm = int(np.sum(fM < fg))
    Rn = int(np.sum(fN > fg)); Sn = int(np.sum(fN < fg))
    return {"Rm": Rm, "Sm": Sm, "Rn": Rn, "Sn": Sn,
            "Gr": (Rm - Sm) / n, "Gn": (Rn - Sn) / n}


def lsb_diff_entropy(image):
    """LSB 位平面的相邻差分熵 (0~1)。1 → LSB 已完全随机(天然噪声/抖动或已嵌入);
    <~0.7 → LSB 明显有结构(自然平滑图)。用于认定"LSB 随机是否本底固有"。
    """
    lsb = _channel(image).astype(np.int16) & 1
    d = np.concatenate([np.abs(np.diff(lsb, axis=1)).ravel(),
                        np.abs(np.diff(lsb, axis=0)).ravel()])
    hist = np.bincount(d, minlength=2).astype(np.float64)
    hist = hist / hist.sum()
    nz = hist[hist > 0]
    return float(-np.sum(nz * np.log2(nz)))


# ---------------- 综合分析 ----------------
# 灵敏度: 判定阈值 (可能阈值, 高度可能阈值) 与 概率牵引系数
#   严格: 需更高概率才判含密 → 降低干净误报
#   宽松: 阈值下调 + 概率外推 → 提高弱嵌入检出
_SENS = {
    "严格 (低误报)": ((0.50, 0.80), 0.85),
    "均衡":           ((0.40, 0.70), 1.00),
    "宽松 (高检出)": ((0.30, 0.60), 1.18),
}


def analyze(image, base_gn=0.62, sensitivity="均衡"):
    cnt = _gray_counts(image)
    chi_stat, chi_p, df = chi2_stats(cnt)
    rs = rs_metrics(image)

    full_img = _channel(image)
    flat = full_img.ravel()
    steps = 20
    ps = []
    for i in range(1, steps + 1):
        end = max(64, int(flat.size * i / steps))
        c = np.bincount(flat[:end], minlength=256).astype(np.float64)
        _, p, _ = chi2_stats(c)
        ps.append(p if p is not None else 0.0)
    ps = np.asarray(ps)
    median_p = float(np.median(ps)) if ps.size else 0.0

    # ---- 内容本底随机度(以灰度差分熵为准) ----
    h = diff_entropy(image)
    lg = lsb_diff_entropy(image)
    # 灰度差分熵: 平滑(≈1) → 0; 纯随机(≈7.7) → 1。高 -> 天然照片/噪声, 无法可靠判嵌入
    tex = float(np.clip((h - 1.2) / (7.0 - 1.2), 0.0, 1.0))

    Gn = rs["Gn"]; Gr = rs["Gr"]

    # 干净基线: 图像本底越"结构化"期待 Gn 越高; 本底越随机期待 Gn 越低。
    # 用同样的差分熵信息把"天然随机"的图从"疑似隐写"里区分出来。
    gn_floor = 0.06 * tex          # 随机本底图 Gn 天然压到很低
    baseline = base_gn * (1.0 - 0.8 * tex) + gn_floor

    # RS 塌缩信号: 干净基线 G_LSB = base_gn*(1-0.8*tex)。结构化封面(base_gn高)若
    # Gn 跌破基线 → 强嵌入证据; 天然噪声图(tex高)基线下调, 塌缩不再强判。
    drop = max(0.0, (baseline - Gn) / max(baseline, 1e-3))
    def _sig(z):
        return 1.0 / (1.0 + math.exp(-z))
    # 缺口头寸: drop 超过阈值才成信号; 阈值随 tex 微调, 但结构封面(tex低)对塌缩很敏感
    center = 0.34 + 0.20 * tex
    s_rs = _sig((drop - center) / 0.12)

    # 卡方: 仅对本底结构化图有意义(干净高结构图灰度对不应均衡);
    # 本底随机图 p 天然高, 不应当作嵌入证据。
    struct = 1.0 - tex
    s_chi = np.clip((median_p - 0.35) / 0.5, 0, 1) * pow(struct, 2)

    # 嵌入率估计(参考语义弱化)
    est_rate = float(np.clip((0.55 * max(0.0, (0.62 - Gn) / 0.62) +
                              0.45 * max(0.0, (0.72 - Gr) / 0.72)), 0.0, 1.0))

    raw = max(s_rs, s_chi)

    # ---- 可判性：仅当 LSB 位平面仍有结构(lg 低)时, Gn 塌缩/卡方才是可靠证据 ----
    # 若 lg 高(→0.9): 天然照片/噪声/抖动 与 嵌入 在 LSB 统计上不可分, 诚实 abstain。
    lsb_rand = float(np.clip((lg - 0.90) / 0.08, 0.0, 1.0))
    # 灵敏度: 取判定阈值与概率牵引系数
    (thr_poss, thr_high), pull = _SENS.get(sensitivity, _SENS["均衡"])

    if tex >= 0.55:
        prob = float(np.clip(0.5 + 0.10 * raw, 0.5, 0.62))
        _abstain = "图像本底噪声高"
    elif lsb_rand > 0.0:
        prob = float(np.clip(0.5 + 0.12 * lsb_rand * raw, 0.5, 0.62))
        _abstain = "LSB 位平面已随机化"
    else:
        prob = float(np.clip(0.04 + 0.96 * raw, 0.0, 1.0))
        _abstain = None
        # 干净镇定点: 强结构 + Gn 仍高 + 卡方无信号 -> 强烈压低
        if tex < 0.35 and (Gn / max(base_gn, 1e-3)) > 0.82 and median_p < 0.1:
            prob = min(prob, 0.15)

    # 概率牵引(围绕 0.5): 严格→更接近 0.5 不轻易判含密; 宽松→外推增强检出
    prob_pull = float(np.clip(0.5 + (prob - 0.5) * pull, 0.0, 1.0))
    if _abstain is not None:
        verdict = f"无法可靠判定({_abstain})"
    else:
        verdict = ("高度可能被隐写" if prob >= thr_high else
                   "可能被隐写" if prob >= thr_poss else
                   "不太可能被隐写")

    return {
        "chi2_stat": chi_stat, "chi2_pvalue": chi_p,
        "median_prefix_p": median_p,
        "diff_entropy": h, "lsb_diff_entropy": lg, "texture_noise": tex,
        "RS_Gr": Gr, "RS_Gn": Gn,
        "est_rate": est_rate,
        "stego_probability": prob_pull,
        "verdict": verdict,
        "sensitivity": sensitivity,
        "prefix_ps": [float(x) for x in ps],
    }