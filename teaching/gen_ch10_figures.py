# -*- coding: utf-8 -*-
"""为第 10 章(综合实战)生成「诚实评估流水线」流程图。

对应 src/train_model.py 的真实步骤, 串联 ch07/08 反复强调的"训练/校准/测试 + 分组"方法论。
输出: teaching/web/{zh,en}/assets/*.png
用法: python teaching/gen_ch10_figures.py
"""
from __future__ import annotations
import os, shutil
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


def out(name):
    p = os.path.join(ZH, name); plt.savefig(p); plt.close("all")
    shutil.copy(p, os.path.join(EN, name))
    print(f"  [ok] {name}  {os.path.getsize(p)//1024} KB")


def box(ax, x, y, w, h, text, fc, ec="k", fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.10",
                                fc=fc, ec=ec, lw=1.0, alpha=0.92))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def arrow(ax, x1, y1, x2, y2, text="", color=GREY):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=1.4))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.10, text, ha="center", fontsize=8, color=color)


def main():
    setstyle()
    fig, ax = plt.subplots(figsize=(11.5, 7.8))
    ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10)

    # 主列 (x 从 0.6 到 4.8)
    steps = [
        ("① 数据 data/dataset_*.csv\n(特征 X, 标签 y, 分组 photo_id)", ACCENT),
        ("② 预留测试集 GroupShuffleSplit\n按 photo_id 分, 25% 不进训练", GREEN),
        ("③ 训练池 75%\n做 5 折 GroupKFold → 每折 OOF 概率", ACCENT),
        ("④ 模型选择(只此一次): 比较 LR/RF/GB/XGB\n选出 CV-AUC 最高者", PURPLE),
        ("⑤ 校准集(训练池内再切 20%)\n挑 Youden 阈值 + 低误报阈值", PURPLE),
        ("⑥ 用全部训练池重训", ACCENT),
        ("⑦ held-out 测试集只评测一次\n报 AUC / 准确率 / 分类报告 / 按密度检出率", WARM),
        ("⑧ 保存模型与阈值\nmodels/stego_classifier.joblib", GREY),
    ]
    bw, bh, gap = 4.1, 0.78, 0.42
    x0, y0 = 0.6, 9.0
    ys = []
    for i, (txt, col) in enumerate(steps):
        y = y0 - i * (bh + gap)
        ys.append(y)
        box(ax, x0, y, bw, bh, txt, col, fs=8.5)
    for i in range(len(ys) - 1):
        arrow(ax, x0 + bw / 2, ys[i], x0 + bw / 2, ys[i] - gap, "")

    # 右侧: 关键原则
    box(ax, 6.4, 5.6, 3.3, 1.15,
        "关键原则\n「任何用来选模型/调阈值的分数，都\n必须来自没用来训练它的数据。」", GREY, fs=8.5, ec=WARM)
    box(ax, 6.4, 3.9, 3.3, 1.3,
        "三层划分\n训练(学) → 校准(挑阈值) → 测试(只用一次)\nOOF = 在没见过的折上打分, 不「自己考自己」", GREEN, fs=8.5, ec=GREEN)
    box(ax, 6.4, 2.2, 3.3, 1.3,
        "红线\n校准集阈值选定后, 别再回头用测试集调(\n否则测试集就「脏」了, 分数不再可信)", WARM, fs=8.5, ec=WARM)

    # 连接主列到右侧
    arrow(ax, x0 + bw, ys[3] + bh / 2, 6.4, 6.2, "候选模型")
    arrow(ax, x0 + bw, ys[4] + bh / 2, 6.4, 4.55, "校准集")

    ax.set_title("图 10-1  诚实评估流水线：train_model.py 的真实步骤（也是你做综合实验的骨架）", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out("capstone_pipeline.png")


if __name__ == "__main__":
    main()
