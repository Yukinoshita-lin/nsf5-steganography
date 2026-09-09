# -*- coding: utf-8 -*-
"""为第 10 章(综合实战)生成「诚实评估流水线」流程图。

对应 src/train_model.py 的真实步骤, 串联 ch07/08 反复强调的"训练/校准/测试 + 分组"方法论。
输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_ch10_figures.py
"""
from __future__ import annotations
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

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

STEPS = [
    ("(1) data data/dataset_*.csv\n(features X, label y, group photo_id)", True),
    ("(2) reserve test set GroupShuffleSplit\nby photo_id, 25% never in training", False),
    ("(3) training pool 75%\n5-fold GroupKFold -> per-fold OOF probs", True),
    ("(4) model selection (once): compare LR/RF/GB/XGB\npick the highest CV-AUC", False),
    ("(5) calibration set (extra 20% of pool)\npick Youden threshold + low-FP threshold", False),
    ("(6) retrain on the whole pool", True),
    ("(7) held-out test set evaluated once\nreport AUC / accuracy / classification report / per-density", False),
    ("(8) save model and threshold\nmodels/stego_classifier.joblib", True),
]
L = {
    "zh": {
        "steps": STEPS,  # replaced below
        "title": "图 10-1  诚实评估流水线：train_model.py 的真实步骤（也是你做综合实验的骨架）",
        "principle": "关键原则\n「任何用来选模型/调阈值的分数，都\n必须来自没用来训练它的数据。」",
        "three": "三层划分\n训练(学) → 校准(挑阈值) → 测试(只用一次)\nOOF = 在没见过的折上打分, 不「自己考自己」",
        "redline": "红线\n校准集阈值选定后, 别再回头用测试集调(\n否则测试集就「脏」了, 分数不再可信)",
        "cand": "候选模型", "calib": "校准集",
        "steps": [
            ("① 数据 data/dataset_*.csv\n(特征 X, 标签 y, 分组 photo_id)", True),
            ("② 预留测试集 GroupShuffleSplit\n按 photo_id 分, 25% 不进训练", False),
            ("③ 训练池 75%\n做 5 折 GroupKFold → 每折 OOF 概率", True),
            ("④ 模型选择(只此一次): 比较 LR/RF/GB/XGB\n选出 CV-AUC 最高者", False),
            ("⑤ 校准集(训练池内再切 20%)\n挑 Youden 阈值 + 低误报阈值", False),
            ("⑥ 用全部训练池重训", True),
            ("⑦ held-out 测试集只评测一次\n报 AUC / 准确率 / 分类报告 / 按密度检出率", False),
            ("⑧ 保存模型与阈值\nmodels/stego_classifier.joblib", True),
        ],
    },
    "en": {
        "title": "Fig. 10-1  Honest evaluation pipeline: the real steps of train_model.py (also the skeleton of your capstone)",
        "principle": "Key principle\nany score used to choose a model / tune a threshold\nmust come from data not used to train it.",
        "three": "Three-way split\ntrain (learn) -> calibrate (pick threshold) -> test (once)\nOOF = score on folds never seen during fitting; no self-grading",
        "redline": "Red line\nonce you fix the threshold on the calibration set, do not go back and tune on the test set\n(otherwise the test set is 'dirty' and the score is no longer trustworthy)",
        "cand": "candidate models", "calib": "calibration set",
        "steps": STEPS,
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


def box(ax, x, y, w, h, text, fc, ec="k", fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.10",
                                fc=fc, ec=ec, lw=1.0, alpha=0.92))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def arrow(ax, x1, y1, x2, y2, text="", color=GREY):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.4))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.10, text, ha="center", fontsize=8, color=color)


def fig_pipeline(lang):
    S = L[lang]
    steps = S["steps"]
    # 颜色按 主列步骤 每步颜色(交替与原图一致)
    colors = ["#1f77b4", "#2ca02c", "#1f77b4", "#9467bd", "#9467bd", "#1f77b4", "#d62728", "#7f7f7f"]
    fig, ax = plt.subplots(figsize=(11.5, 7.8))
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    bw, bh, gap = 4.1, 0.78, 0.42
    x0, y0 = 0.6, 9.0
    ys = []
    for i, (txt, _) in enumerate(steps):
        y = y0 - i * (bh + gap)
        ys.append(y)
        box(ax, x0, y, bw, bh, txt, colors[i], fs=8.5)
    for i in range(len(ys) - 1):
        arrow(ax, x0 + bw / 2, ys[i], x0 + bw / 2, ys[i] - gap, "")
    box(ax, 6.4, 5.6, 3.3, 1.15, S["principle"], GREY, fs=8.5, ec=WARM)
    box(ax, 6.4, 3.9, 3.3, 1.3, S["three"], GREEN, fs=8.5, ec=GREEN)
    box(ax, 6.4, 2.2, 3.3, 1.3, S["redline"], WARM, fs=8.5, ec=WARM)
    arrow(ax, x0 + bw, ys[3] + bh / 2, 6.4, 6.2, S["cand"])
    arrow(ax, x0 + bw, ys[4] + bh / 2, 6.4, 4.55, S["calib"])
    ax.set_title(S["title"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out("capstone_pipeline.png", lang)


def main():
    setstyle()
    print("生成第 10 章流水线图...")
    for lang in ("zh", "en"):
        fig_pipeline(lang)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
