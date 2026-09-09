# -*- coding: utf-8 -*-
"""为附录 F(6-12 个月深入自学路线图)生成可视化甘特图。

横轴: 月份 1..12; 纵轴: 主题(章节组); 颜色: 所属领域。
输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_roadmap_figures.py
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

FIELD_COLOR = {
    "数字图像处理": "#1f77b4", "工具": "#8c564b", "信息隐藏": "#2ca02c",
    "机器学习": "#ff7f0e", "工程": "#9467bd", "综合": "#d62728",
}
FIELD_EN = {
    "数字图像处理": "Digital image processing", "工具": "Toolchain",
    "信息隐藏": "Information hiding", "机器学习": "Machine learning",
    "工程": "Engineering", "综合": "Capstone",
}
# (主题, 领域, 开始月, 结束月, 第几章)
ALL_ROWS = [
    ("数字图像与二进制", "数字图像处理", 1, 1, "ch01"),
    ("Python / NumPy / Pillow", "工具", 1, 1, "ch02"),
    ("LSB 隐写与盲分析", "信息隐藏", 1, 2, "ch03"),
    ("矩阵编码与 F5", "信息隐藏", 2, 2, "ch04"),
    ("nsF5 与湿纸编码", "信息隐藏", 2, 3, "ch05"),
    ("口令 / 哈希键控", "信息隐藏", 3, 3, "ch06"),
    ("机器学习基础", "机器学习", 3, 5, "ch07"),
    ("机器学习隐写检测", "机器学习", 5, 7, "ch08"),
    ("工程化: C++ / GPU / GUI", "工程", 6, 8, "ch09"),
    ("综合项目与汇报", "综合", 9, 12, "ch10-11"),
]
L = {
    "zh": {
        "title": "图 F-1  6–12 个月深入自学路线图：四大领域递进, 最后留足时间做综合项目",
        "xlabel": "月份 (第 1 ~ 12 个月)",
        "phases": [(1, "基础期\n1-3月"), (4, "提高期\n4-6月"), (7, "深化期\n7-9月"), (10, "实战期\n10-12月")],
        "field": FIELD_COLOR,
    },
    "en": {
        "title": "Fig. F-1  6-12 month in-depth self-study roadmap: four domains in sequence, with enough time left for the capstone",
        "xlabel": "Month (1 - 12)",
        "phases": [(1, "Foundation\nMon 1-3"), (4, "Advanced\nMon 4-6"), (7, "Deep dive\nMon 7-9"), (10, "Capstone\nMon 10-12")],
        "field": FIELD_COLOR,
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


def fig_roadmap(lang):
    rows = list(reversed(ALL_ROWS))
    n = len(rows)
    fig, ax = plt.subplots(figsize=(12.5, 6.2))
    for yi, (topic, field, s, e, ch) in enumerate(rows):
        color = L[lang]["field"][field]
        ax.barh(yi, e - s + 1, left=s - 1, height=0.6,
                color=color, alpha=0.85, edgecolor="white")
        # 领域名放在条的最右端外侧, 避免长文本被条宽截断(勘误: 文字显示不全)
        ax.text(e - 1 + 1 + 0.12, yi, (field if lang == "zh" else FIELD_EN[field]),
                ha="left", va="center", fontsize=7, color="#3a3a3a")
    ax.set_yticks(range(n)); ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlabel(L[lang]["xlabel"], fontsize=10)
    ax.set_xlim(0.4, 12.9)
    ax.set_xticks(range(1, 13)); ax.set_xticklabels([f"{i}" for i in range(1, 13)], fontsize=8)
    ax.set_xticks(np.arange(0.5, 12.5, 1), minor=True); ax.grid(axis="x", which="minor", alpha=0.3)
    # 阶段分界
    for m in (3, 6, 9):
        ax.axvline(m + 0.5, color="k", ls="--", lw=1)
    # 阶段标签放在数据区顶部一行(不与标题重叠)
    for x0, lab in L[lang]["phases"]:
        ax.text(x0 + 0.5, n - 0.12, lab, ha="center", va="bottom", fontsize=8.5, color="k")
    ax.set_ylim(-0.65, n + 0.62)
    # 图例
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in L[lang]["field"].values()]
    labels = list(L[lang]["field"].keys())
    if lang == "en":
        labels = [FIELD_EN[k] for k in labels]
    ax.legend(handles, labels, loc="lower left", fontsize=8, ncol=3, framealpha=0.95)
    ax.set_title(L[lang]["title"], fontsize=11, pad=20)
    fig.tight_layout()
    out("roadmap.png", lang)


def main():
    setstyle()
    print("生成附录 F 路线图...")
    for lang in ("zh", "en"):
        fig_roadmap(lang)
    print("完成 → ", ZH, "和", EN)


if __name__ == "__main__":
    main()
