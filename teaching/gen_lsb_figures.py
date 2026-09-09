# -*- coding: utf-8 -*-
"""为第 3 章(LSB 隐写与统计指纹)生成真实数据驱动的可视化图。

数据: img/cover.png (项目演示载体)。用朴素 LSB 替换嵌入随机比特, 生成含密图。
内容:
  - lsb_cover_stego  : 载体 | 含密 | 放大差异(|cover-stego|*255) | LSB 平面
  - lsb_pixel_level  : 一小块真实像素值 嵌入前后 对比, 高亮被翻转的 LSB
  - img010           : 相邻灰度对 (2i,2i+1) 频数, 干净 vs 嵌入后(拉平)
  - img011           : Gn / 卡方统计量 / 隐写概率 三道证据, 干净 vs 含密

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_lsb_figures.py
"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZH = os.path.join(ROOT, "teaching", "web", "zh", "assets")
EN = os.path.join(ROOT, "teaching", "web", "en", "assets")
COVER = os.path.join(ROOT, "img", "cover.png")
os.makedirs(ZH, exist_ok=True); os.makedirs(EN, exist_ok=True)

_avail = {f.name for f in font_manager.fontManager.ttflist}
for _c in ["Microsoft YaHei", "SimHei", "DengXian", "SimSun"]:
    if _c in _avail:
        plt.rcParams["font.family"] = [_c, "DejaVu Sans"]; break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
ACCENT, WARM, GREEN, GREY = "#1f77b4", "#d62728", "#2ca02c", "#7f7f7f"

L = {
    "zh": {
        "cover_stego_title": "图 3-1  肉眼看几乎一模一样, 但差异放大与 LSB 位平面会露出端倪",
        "cs": ["① 载体 cover (原图)", "② 含密 stego (LSB 藏随机比特)",
               "③ 差异放大 ×255: 改了 {:.1%} 像素", "④ cover 的 LSB 位平面(本就近似噪声)"],
        "pixel_title": "图 3-2  像素级对比: 只是个别像素的 LSB 变了 0↔1, 灰度几乎不变",
        "px": ["① 原图这一小块", "② 藏了比特后", "③ 这一小块改动: {}/{} 像素"],
        "hist_title": "图 3-3  LSB 替换把相邻灰度对的奇偶频数拉平",
        "clean": "干净图", "embedded": "嵌入后",
        "hist_x": "灰度相邻对 (2i, 2i+1)", "hist_ylabel": "偶值占比 2i / (2i + 2i+1)",
        "hist_note": "干净图奇偶明显不齐(偏离 0.5) → 嵌入后被拉平(向 0.5 靠拢)",
        "bar_title": "图 3-4  三道证据对照：RS 缺口塌缩（基于真实数据）",
        "bar_cats": ["Gn (RS)", "卡方统计量", "隐写概率"],
        "bar_clean": "干净", "bar_stego": "含密",
        "bar_x": "统计量", "bar_y_left": "Gn / 隐写概率 (0~1)", "bar_y_right": "卡方统计量 (对数)",
        "bar_note": "含密图(粉)的 Gn 明显塌缩、卡方统计量下降、隐写概率升高——这就是三道判据的合力",
    },
    "en": {
        "cover_stego_title": "Fig. 3-1  Almost identical to the eye, but the amplified difference and LSB plane reveal the trace",
        "cs": ["(1) cover (original)", "(2) stego (random bits in LSB)",
               "(3) difference x255: {:.1%} pixels changed", "(4) cover's LSB plane (already noiselike)"],
        "pixel_title": "Fig. 3-2  Pixel-level comparison: only a few LSB bits flipped 0<->1, gray barely changes",
        "px": ["(1) original patch", "(2) after embedding", "(3) changes here: {}/{} pixels"],
        "hist_title": "Fig. 3-3  LSB replacement flattens the even/odd balance of adjacent gray pairs",
        "clean": "clean", "embedded": "embedded",
        "hist_x": "gray-level pair (2i, 2i+1)", "hist_ylabel": "share of the even value 2i",
        "hist_note": "clean pairs are uneven (away from 0.5) -> flattened after embedding (toward 0.5)",
        "bar_title": "Fig. 3-4  Three lines of evidence: the RS gap collapses (real data)",
        "bar_cats": ["Gn (RS)", "chi-square stat", "stego prob"],
        "bar_clean": "clean", "bar_stego": "stego",
        "bar_x": "statistic", "bar_y_left": "Gn / stego prob (0-1)", "bar_y_right": "chi-square stat (log)",
        "bar_note": "the stego (pink) has a collapsed Gn, lower chi-square statistic, higher stego probability - the combined pull of three clues",
    },
}


def setstyle():
    for s in ["seaborn-v0_8-whitegrid", "seaborn-whitegrid", "ggplot"]:
        try:
            plt.style.use(s); break
        except Exception:
            continue
    for _c in ["Microsoft YaHei", "SimHei", "DengXian", "SimSun"]:
        if _c in _avail:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [_c, "DejaVu Sans"]
            plt.rcParams["font.family"] = [_c, "DejaVu Sans"]; break


def out(name, lang):
    p = os.path.join(ZH if lang == "zh" else EN, name)
    plt.savefig(p)
    plt.close("all")
    print(f"  [ok] {lang}/{name}  {os.path.getsize(p)//1024} KB")


def load_cover():
    im = Image.open(COVER)
    if im.mode != "L":
        im = im.convert("L")
    a = np.asarray(im, np.uint8)
    if a.size == 0:
        raise RuntimeError("cover.png empty")
    return a


def lsb_replace(cover, rng, ratio=0.5):
    stego = cover.copy().astype(np.uint8)
    flat = stego.ravel()
    n = flat.size
    idx = rng.choice(n, size=int(n * ratio), replace=False)
    flat[idx] = (flat[idx] & 0xFE) | rng.integers(0, 2, idx.size)
    return stego.reshape(cover.shape)


def pair_counts(img):
    """统计相邻灰度对 (2i,2i+1) 的频数, 返回以 2i 为下标的数组(0..254)。"""
    cnt = np.bincount(img.ravel(), minlength=256).astype(np.float64)
    even = cnt[0::2]
    return even.copy()  # even[k] = 灰度对 (2k, 2k+1) 的总频数


def fig_cover_stego(cover, stego, lang):
    diff = np.abs(cover.astype(int) - stego.astype(int))
    lsb_clean = (cover & 1) * 255
    S = L[lang]
    fig, axes = plt.subplots(1, 4, figsize=(15.5, 4.4))
    plt.rcParams["image.interpolation"] = "nearest"
    axes[0].imshow(cover, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title(S["cs"][0], fontsize=9)
    axes[1].imshow(stego, cmap="gray", vmin=0, vmax=255)
    axes[1].set_title(S["cs"][1], fontsize=9)
    axes[2].imshow(diff * 255, cmap="hot", vmin=0, vmax=255)
    axes[2].set_title(S["cs"][2].format(int((diff > 0).sum()) / diff.size), fontsize=9)
    axes[3].imshow(lsb_clean, cmap="gray", vmin=0, vmax=255)
    axes[3].set_title(S["cs"][3], fontsize=9)
    for ax in axes:
        ax.axis("off")
    fig.suptitle(S["cover_stego_title"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("lsb_cover_stego.png", lang)


def fig_pixel_level(cover, stego, lang):
    r0, c0 = 12, 16
    h, w = 8, 10
    cov = cover[r0:r0+h, c0:c0+w].astype(int)
    ste = stego[r0:r0+h, c0:c0+w].astype(int)
    changed = cov != ste
    S = L[lang]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5))
    for ax, mat, title in [(axes[0], cov, S["px"][0]), (axes[1], ste, S["px"][1])]:
        im = ax.imshow(mat, cmap="magma", vmin=cov.min()-1, vmax=cov.max()+1)
        ax.set_xticks(range(w)); ax.set_yticks(range(h))
        ax.set_xticklabels(range(c0, c0+w), fontsize=6); ax.set_yticklabels(range(r0, r0+h), fontsize=6)
        for r in range(h):
            for c in range(w):
                ax.text(c, r, str(mat[r, c]), ha="center", va="center", fontsize=6,
                        color="white" if (mat[r, c] < (cov.min()+cov.max())/2) else "black")
        ax.set_title(title, fontsize=9)
    ax = axes[2]
    ax.imshow(changed, cmap="Reds", vmin=0, vmax=1)
    ax.set_xticks(range(w)); ax.set_yticks(range(h))
    ax.set_xticklabels(range(c0, c0+w), fontsize=6); ax.set_yticklabels(range(r0, r0+h), fontsize=6)
    ax.set_title(S["px"][2].format(int(changed.sum()), h*w), fontsize=9)
    fig.suptitle(S["pixel_title"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("lsb_pixel_level.png", lang)


def pair_balance(img, min_px=40):
    """返回 (pair_left, frac_even): 每个灰度对 (2k,2k+1) 中偶值所占比例, 只保留像素足够多的对。"""
    cnt = np.bincount(img.ravel(), minlength=256).astype(np.float64)
    even = cnt[0::2]; odd = cnt[1::2]
    tot = even + odd
    mask = tot >= min_px
    k = np.where(mask)[0]
    frac = even[mask] / tot[mask]
    return 2 * k, frac


def fig_hist_pairs(cover, stego, lang):
    """img010: 相邻灰度对 (2i, 2i+1) 的奇偶均衡度, 干净 vs 嵌入后(拉平)。

    卡方检验抓的正是"每个灰度对里奇偶是否被拉平": 干净图偏离 0.5, 嵌入后向 0.5 靠拢。
    用"偶值占比"而非原始频数, 避免个别超亮灰度(如 255)把纵轴压扁。
    """
    S = L[lang]
    x1, f1 = pair_balance(cover)
    x2, f2 = pair_balance(stego)
    fig, ax = plt.subplots(figsize=(10.0, 4.2))
    ax.axhline(0.5, ls="--", color=GREY, lw=1.1, label="0.5 (完全均衡)")
    ax.plot(x1, f1, "-o", ms=3, lw=1.4, color=ACCENT, label=S["clean"])
    ax.plot(x2, f2, "-s", ms=3, lw=1.4, color=WARM, label=S["embedded"])
    ax.set_xlabel(S["hist_x"]); ax.set_ylabel(S["hist_ylabel"])
    ax.set_title(S["hist_title"], fontsize=11)
    ax.set_ylim(0, 1); ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    n = len(x1)
    step = max(1, n // 14)
    ax.set_xticks(x1[::step]); ax.set_xticklabels([f"{v}" for v in x1[::step]], fontsize=8)
    ax.legend(frameon=False, loc="upper right")
    ax.grid(alpha=0.2, axis="y")
    ax.text(0.02, 0.03, S["hist_note"], transform=ax.transAxes, va="bottom", ha="left",
            fontsize=8.5, color="#333")
    fig.tight_layout()
    out("img010.png", lang)


def fig_stego_bars(cover, stego, lang):
    """img011: Gn / 卡方统计量 / 隐写概率 三道证据, 干净 vs 含密。"""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import steganalysis as SA
    S = L[lang]
    rc = SA.analyze(cover); rs = SA.analyze(stego)
    gn_c, gn_s = rc["RS_Gn"], rs["RS_Gn"]
    chi_c, chi_s = float(rc["chi2_stat"]), float(rs["chi2_stat"])
    pr_c, pr_s = rc["stego_probability"], rs["stego_probability"]
    cats = S["bar_cats"]
    x = np.arange(len(cats))
    w = 0.34

    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    ax2 = ax.twinx()
    # 左轴(线性 0~1): Gn 与 隐写概率
    ax.bar(0 - w/2, gn_c, w, label=S["bar_clean"], color=ACCENT, alpha=0.9)
    ax.bar(0 + w/2, gn_s, w, label=S["bar_stego"], color=WARM, alpha=0.9)
    ax.bar(2 - w/2, pr_c, w, color=ACCENT, alpha=0.9)
    ax.bar(2 + w/2, pr_s, w, color=WARM, alpha=0.9)
    ax.set_ylim(0, 0.72); ax.set_ylabel(S["bar_y_left"])
    # 右轴(对数): 卡方统计量
    ax2.bar(1 - w/2, chi_c, w, color=ACCENT, alpha=0.55)
    ax2.bar(1 + w/2, chi_s, w, color=WARM, alpha=0.55)
    ax2.set_yscale("log"); ax2.set_ylim(1e3, 1e5); ax2.set_ylabel(S["bar_y_right"])

    ax.set_xticks(x); ax.set_xticklabels(cats, fontsize=9)
    ax.set_xlabel(S["bar_x"])
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.grid(alpha=0.2, axis="y")
    ax2.grid(False)
    ax.set_title(S["bar_title"], fontsize=11, pad=14)
    fig.text(0.5, -0.02, S["bar_note"], ha="center", va="top", fontsize=8, color="#333")
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    out("img011.png", lang)


def main():
    setstyle()
    cover = load_cover()
    rng = np.random.default_rng(0)
    stego = lsb_replace(cover, rng, ratio=0.5)
    print("cover", cover.shape, "改成", int(np.sum(cover != stego)), "像素")
    for lang in ("zh", "en"):
        fig_cover_stego(cover, stego, lang)
        fig_pixel_level(cover, stego, lang)
        fig_hist_pairs(cover, stego, lang)
        fig_stego_bars(cover, stego, lang)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
