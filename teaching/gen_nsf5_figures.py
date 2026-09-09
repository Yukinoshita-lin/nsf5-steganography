# -*- coding: utf-8 -*-
"""为第 5 章(nsF5 / 湿纸编码)生成真实数据驱动的可视化图。

内容:
  - nsf5_wet_dry  : 像素块中 湿点(|xv|<=1) vs 干点(|xv|>1) 的划分, 及 xv=像素-128 映射
  - nsf5_solve    : 在 H 矩阵的干列上解伴随式 d, 标出要减幅的位置(单列→双列命中)

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_nsf5_figures.py
"""
from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZH = os.path.join(ROOT, "teaching", "web", "zh", "assets")
EN = os.path.join(ROOT, "teaching", "web", "en", "assets")
os.makedirs(ZH, exist_ok=True); os.makedirs(EN, exist_ok=True)

_avail = {f.name for f in font_manager.fontManager.ttflist}
for _c in ["Microsoft YaHei", "SimHei", "DengXian", "SimSun"]:
    if _c in _avail:
        plt.rcParams["font.family"] = [_c, "DejaVu Sans"]; break
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
ACCENT, WARM, GREEN, GREY, PURPLE = "#1f77b4", "#d62728", "#2ca02c", "#7f7f7f", "#9467bd"

L = {
    "zh": {
        "wet_dry": {
            "ylabel": "|xv| = |像素−128|",
            "wet_lab": "湿", "dry_lab": "干",
            "t1": "① 湿点 |xv|≤1 (红)=像素 127/128/129; 干点(绿)可安全减幅",
            "danger": "危险带 |xv|≤1",
            "xlab2": "xv (有符号系数 = 像素−128)", "ylabel2": "像素数",
            "t2": "② 越靠近 0 越危险: 减幅会撞向 127/128/129",
            "suptitle": "图 5-1  nsF5 的「湿点/干点」: 先把碰不得的位置划出来",
        },
        "solve": {
            "t1": "① H 矩阵: 湿列(淡红框)不参与, 干列(绿框)可解, 绿粗框=命中列",
            "xlab": "像素位 1~7 (列)",
            "t2": "② 期望伴随式差 d = s⊕m",
            "ylabel3": "是否改动",
            "t3": "③ 解: 改 {} 个干位置  列{}",
            "suptitle": "图 5-2  湿纸编码: 在干列上解 H·y = d  (本例: h{}⊕h{} = {}⊕{} = {} = d  ✔)",
        },
    },
    "en": {
        "wet_dry": {
            "ylabel": "|xv| = |pixel-128|",
            "wet_lab": "wet", "dry_lab": "dry",
            "t1": "(1) wet points |xv|<=1 (red) = pixels 127/128/129; dry points (green) can be safely decremented",
            "danger": "danger zone |xv|<=1",
            "xlab2": "xv (signed coefficient = pixel-128)", "ylabel2": "pixel count",
            "t2": "(2) closer to 0 is more dangerous: decrement would hit 127/128/129",
            "suptitle": "Fig. 5-1  nsF5 'wet/dry' points: mark the untouchable positions first",
        },
        "solve": {
            "t1": "(1) H matrix: wet columns (light red) are skipped, dry columns (green) solvable, thick green = chosen columns",
            "xlab": "pixel bits 1-7 (columns)",
            "t2": "(2) desired syndrome difference d = s xor m",
            "ylabel3": "change?",
            "t3": "(3) solution: change {} dry positions columns{}",
            "suptitle": "Fig. 5-2  Wet paper coding: solve H.y = d on dry columns  (here: h{} xor h{} = {} xor {} = {} = d  OK)",
        },
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
    plt.savefig(p); plt.close("all")
    print(f"  [ok] {lang}/{name}  {os.path.getsize(p)//1024} KB")


def build_hamming(p):
    n = (1 << p) - 1
    return np.array([[ (j >> k) & 1 for j in range(1, n + 1)] for k in range(p)], np.uint8)


def syndrome(H, x):
    return (H @ x) % 2


def solve_dry_two(H, dry1, d):
    for c in dry1:
        if np.array_equal(H[:, c - 1], d):
            return [c]
    for a in range(len(dry1)):
        for b in range(a + 1, len(dry1)):
            if np.array_equal((H[:, dry1[a]-1] ^ H[:, dry1[b]-1]).astype(np.uint8), d):
                return [dry1[a], dry1[b]]
    return None


def _draw_h(ax, H, wet, dry, sol=None):
    p, n = H.shape
    bg = np.zeros((p, n))
    for c in range(n):
        bg[:, c] = 0.55 if (c + 1) in wet else 0.0
    disp = np.clip(H.astype(float) * (1.0 - bg), 0, 1)
    ax.imshow(disp, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(n)); ax.set_xticklabels(range(1, n + 1), fontsize=7)
    ax.set_yticks(range(p)); ax.set_yticklabels(["b1", "b2", "b3"], fontsize=7)
    for r in range(p):
        for c in range(n):
            v = H[r, c]
            ax.text(c, r, str(v), ha="center", va="center", fontsize=7,
                    color="white" if v else "black")
    for c in range(n):
        col = c + 1
        if col in wet:
            ax.add_patch(plt.Rectangle((c - 0.5, -0.5), 1, p, fill=True, color=WARM, alpha=0.14))
        else:
            ax.add_patch(plt.Rectangle((c - 0.5, -0.5), 1, p, fill=False, edgecolor=GREEN, lw=0.8))
        if sol is not None and col in sol:
            ax.add_patch(plt.Rectangle((c - 0.5, -0.5), 1, p, fill=False, edgecolor=GREEN, lw=2.4))


def fig_wet_dry(lang):
    S = L[lang]["wet_dry"]
    vals = np.array([127, 128, 129, 100, 200, 55, 150], np.int16)
    xv = vals - 128
    wet = np.abs(xv) <= 1
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.8))
    ax = axes[0]
    cols = [WARM if w else GREEN for w in wet]
    ax.bar(range(7), np.abs(xv).astype(float), color=cols, alpha=0.85)
    ax.set_xticks(range(7)); ax.set_xticklabels([f"p{i+1}\n{v}" for i, v in enumerate(vals)], fontsize=7.5)
    ax.set_ylabel(S["ylabel"], fontsize=9)
    for i, w in enumerate(wet):
        ax.text(i, np.abs(xv)[i] + 0.6, S["wet_lab"] if w else S["dry_lab"], ha="center", fontsize=7.5,
                color=WARM if w else GREEN)
    ax.axhline(1.0, ls="--", color=GREY, lw=1)
    ax.set_ylim(0, max(np.abs(xv)) + 8)
    ax.set_title(S["t1"], fontsize=9.5)
    ax = axes[1]
    xv_range = np.arange(-6, 7)
    counts = np.bincount(np.clip(xv + 6, 0, xv_range.size - 1), minlength=xv_range.size)
    ax.bar(xv_range, counts, color=ACCENT, alpha=0.7)
    ax.axvspan(-1, 1, color=WARM, alpha=0.18)
    ax.text(0, max(counts) + 0.1, S["danger"], ha="center", color=WARM, fontsize=9)
    ax.set_xlabel(S["xlab2"]); ax.set_ylabel(S["ylabel2"]); ax.set_xticks(xv_range)
    ax.set_title(S["t2"], fontsize=9.5)
    fig.suptitle(S["suptitle"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("nsf5_wet_dry.png", lang)


def fig_solve(lang):
    S = L[lang]["solve"]
    p, n = 3, 7
    H = build_hamming(p)
    wet = [1, 2, 3]; dry = [4, 5, 6, 7]
    d = np.array([1, 1, 0], np.uint8)
    sol = solve_dry_two(H, dry, d)
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.6), gridspec_kw={"width_ratios": [1.15, 0.85, 1.0]})
    _draw_h(axes[0], H, wet, dry, sol=sol)
    axes[0].set_title(S["t1"], fontsize=8.5)
    axes[0].set_xlabel(S["xlab"], fontsize=8)
    ax = axes[1]
    ax.set_title(S["t2"], fontsize=8.5)
    ax.imshow(d[None, :], cmap="Greens", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(3)); ax.set_xticklabels(["d1", "d2", "d3"], fontsize=8); ax.set_yticks([])
    for c in range(3):
        ax.text(c, 0, str(d[c]), ha="center", va="center", fontsize=10, color="white" if d[c] else "black")
    ax = axes[2]
    bar = ax.bar(range(n), [1 if (i + 1) in sol else 0 for i in range(n)], color=ACCENT)
    for i in sol:
        bar[i - 1].set_color(GREEN)
    ax.set_xticks(range(n)); ax.set_xticklabels(range(1, n + 1), fontsize=7)
    ax.set_ylim(-0.15, 1.4); ax.set_yticks([0, 1]); ax.set_ylabel(S["ylabel3"], fontsize=9)
    ax.set_title(S["t3"].format(len(sol), sol), fontsize=9)
    fig.suptitle(S["suptitle"].format(sol[0], sol[1],
                                      list(map(int, H[:, sol[0]-1])), list(map(int, H[:, sol[1]-1])),
                                      list(map(int, d))), fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.88])
    out("nsf5_solve.png", lang)


def main():
    setstyle()
    print("生成 nsF5/湿纸 相关图...")
    for lang in ("zh", "en"):
        fig_wet_dry(lang)
        fig_solve(lang)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
