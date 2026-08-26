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


# ---------------- 综合分析 ----------------
def analyze(image):
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

    # 嵌入率/倾向得分: 主信号 = RS 负掩码缺口 Gn 的塌缩(LSB 随机化压低 Gn)
    Gn = rs["Gn"]; Gr = rs["Gr"]
    est_rate = float(np.clip(0.55 * max(0.0, (0.62 - Gn) / 0.62) +
                             0.45 * max(0.0, (0.72 - Gr) / 0.72), 0.0, 1.0))
    # sigmoid: Gn 越低→分越高; 中心与陡度按典型均衡值标定
    def _sig(z):
        return 1.0 / (1.0 + math.exp(-z))
    s_rs = float(_sig((0.47 - Gn) / 0.07))
    s_chi = float(np.clip((median_p - 0.3) / 0.6, 0, 1))  # 卡方越强分越高
    prob = float(np.clip(0.05 + 0.95 * max(s_rs, s_chi), 0, 1))
    # 干净图镇定: 缺口很高且卡方无信号 → 强烈压低(此时 @gn>0.56 视为干净)
    if Gn > 0.56 and median_p < 0.05:
        prob = min(prob, 0.18)

    verdict = ("高度可能被隐写" if prob >= 0.7 else
               "可能被隐写" if prob >= 0.4 else
               "不太可能被隐写")

    return {
        "chi2_stat": chi_stat, "chi2_pvalue": chi_p,
        "median_prefix_p": median_p,
        "RS_Gr": Gr, "RS_Gn": Gn,
        "est_rate": est_rate,
        "stego_probability": prob,
        "verdict": verdict,
        "prefix_ps": [float(x) for x in ps],
    }