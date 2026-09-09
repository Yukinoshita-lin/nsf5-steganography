# -*- coding: utf-8 -*-
"""为稀疏章节(导读 intro / 结语 ch11)补充分阶段可视化图。

内容:
  - learning_path  : intro  12 周快速路线的四段流程图(基础/算法/检测/工程+综合)
  - project_overview: ch11  项目从算法到工程的分层全貌图

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_extra_teaching_figures.py
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

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

C = {"base": "#1f77b4", "algo": "#2ca02c", "ml": "#ff7f0e", "eng": "#9467bd", "cap": "#d62728"}

L = {
    "zh": {
        "lp_title": "图 · 12 周快速入门：四段递进（6–12 个月深入版见附录 F）",
        "lp_phases": [
            ("基础期\n第 1–2 周", ["数字图像与二进制", "Python / NumPy / Pillow"], "base"),
            ("算法期\n第 3–6 周", ["LSB 与统计指纹", "矩阵编码 / F5", "nsF5 与湿纸", "口令 / 哈希键控"], "algo"),
            ("检测期\n第 7–9 周", ["机器学习基础", "ML 隐写检测"], "ml"),
            ("工程 + 综合\n第 10–12 周", ["C++ / GPU / GUI", "综合项目与汇报"], "eng"),
        ],
        "po_title": "图 · 项目全貌：从载体到“看得懂”的干净/含密判定",
        "po_left": "载体图", "po_embed": "嵌入算法\nns5_core / 矩阵编码 / nsF5", "po_stego": "含密图",
        "po_feat": "统计指纹\n卡方 / RS / 差分熵 / SRM", "po_ml": "ML 模型\n11 维 → 143 维(稳健) / 53 维(可解释)",
        "po_out": "判读 / GUI\n分析概率 + 灵敏度",
    },
    "en": {
        "lp_title": "Fig. · 12-week quick start: four stages (deep 6-12 month version in Appendix F)",
        "lp_phases": [
            ("Foundation\nWeeks 1-2", ["Digital images & binary", "Python / NumPy / Pillow"], "base"),
            ("Algorithms\nWeeks 3-6", ["LSB & fingerprints", "Matrix embedding / F5", "nsF5 & wet paper", "Password / hash keying"], "algo"),
            ("Detection\nWeeks 7-9", ["ML foundations", "ML steganalysis"], "ml"),
            ("Engineering + Capstone\nWeeks 10-12", ["C++ / GPU / GUI", "Capstone project"], "eng"),
        ],
        "po_title": "Fig. · Project overview: from a cover to an interpretable clean/stego decision",
        "po_left": "cover", "po_embed": "embedding\nns5_core / matrix / nsF5", "po_stego": "stego",
        "po_feat": "statistical fingerprints\nchi-square / RS / diff-entropy / SRM", "po_ml": "ML model\n11-D -> 143-D (robust) / 53-D (interpretable)",
        "po_out": "decision / GUI\nprob + sensitivity",
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


def box(ax, x, y, w, h, text, fc, fs=8.5, ec="white", tc="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                                fc=fc, ec=ec, lw=1.0, alpha=0.92))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tc)


def arrow(ax, x1, y1, x2, y2, color="#445566"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=14, color=color, lw=1.6))


def fig_learning_path(lang):
    S = L[lang]
    phases = S["lp_phases"]
    fig, ax = plt.subplots(figsize=(11.6, 3.6))
    ax.axis("off"); ax.set_xlim(0, 12); ax.set_ylim(0, 3.6)
    bw, bh = 2.6, 0.6
    xs = [0.4, 3.1, 5.8, 8.5]
    for i, (ptitle, items, ck) in enumerate(phases):
        x = xs[i]; col = C[ck]
        box(ax, x, 2.1, bw, 0.85, ptitle, col, fs=9, tc="white")
        for j, it in enumerate(items):
            box(ax, x + 0.05, 1.15 - j * 0.5, bw - 0.1, 0.42, it, "#ffffff",
                fs=7.5, ec=col, tc="#1b1b1b")
        if i < len(phases) - 1:
            arrow(ax, x + bw, 2.5, xs[i + 1] - 0.06, 2.5)
    ax.set_title(S["lp_title"], fontsize=10.5, pad=8)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out("learning_path.png", lang)


def fig_project_overview(lang):
    S = L[lang]
    fig, ax = plt.subplots(figsize=(11.6, 3.4))
    ax.axis("off"); ax.set_xlim(0, 12); ax.set_ylim(0, 3.4)
    # top row: cover -> embed -> stego
    box(ax, 0.3, 2.4, 1.8, 0.7, S["po_left"], "#1f77b4", fs=9)
    arrow(ax, 2.2, 2.75, 2.9, 2.75)
    box(ax, 3.0, 2.3, 2.2, 0.9, S["po_embed"], "#2ca02c", fs=8)
    arrow(ax, 5.3, 2.75, 5.9, 2.75)
    box(ax, 6.0, 2.4, 1.8, 0.7, S["po_stego"], "#2ca02c", fs=9)
    # bottom row: fingerprint -> ML -> decision
    box(ax, 0.3, 0.6, 2.4, 0.7, S["po_feat"], "#ff7f0e", fs=8)
    arrow(ax, 2.8, 0.95, 3.6, 0.95)
    box(ax, 3.7, 0.55, 3.0, 0.8, S["po_ml"], "#9467bd", fs=8)
    arrow(ax, 6.8, 0.95, 7.6, 0.95)
    box(ax, 7.7, 0.6, 2.4, 0.7, S["po_out"], "#d62728", fs=8)
    # connect stego -> fingerprint (data feeds features)
    arrow(ax, 6.9, 2.4, 1.5, 1.35, color="#8a8a8a")
    ax.set_title(S["po_title"], fontsize=10.5, pad=8)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out("project_overview.png", lang)


def main():
    setstyle()
    print("生成导读/结语补充图...")
    for lang in ("zh", "en"):
        fig_learning_path(lang)
        fig_project_overview(lang)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
