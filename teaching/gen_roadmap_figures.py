# -*- coding: utf-8 -*-
"""为附录 F(6-12 个月深入自学路线图)生成可视化甘特图。

横轴: 月份 1..12; 纵轴: 主题(章节组); 颜色: 所属领域。
输出: teaching/web/{zh,en}/assets/*.png
用法: python teaching/gen_roadmap_figures.py
"""
from __future__ import annotations
import os, shutil
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


def main():
    setstyle()
    # (主题, 领域, 开始月, 结束月, 第几章)
    rows = [
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
    field_color = {
        "数字图像处理": "#1f77b4", "工具": "#8c564b", "信息隐藏": "#2ca02c",
        "机器学习": "#ff7f0e", "工程": "#9467bd", "综合": "#d62728",
    }
    # 从下往上排(主题1在底部)
    rows = list(reversed(rows))
    fig, ax = plt.subplots(figsize=(12.5, 6.0))
    for yi, (topic, field, s, e, ch) in enumerate(rows):
        ax.barh(yi, e - s + 1, left=s - 1, height=0.6,
                color=field_color[field], alpha=0.85, edgecolor="white")
        ax.text(s - 1 + (e - s + 1) / 2.0 - 0.5, yi, f"{topic}\n{field}", ha="center", va="center",
                fontsize=8, color="white")
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlabel("月份 (第 1 ~ 12 个月)", fontsize=10)
    ax.set_xticks(range(12)); ax.set_xticklabels([f"{i+1}" for i in range(12)], fontsize=8)
    ax.set_xticks(np.arange(-0.5, 12, 1), minor=True); ax.grid(axis="x", which="minor", alpha=0.3)
    # 阶段分界
    for m in (3, 6, 9):
        ax.axvline(m - 0.5, color="k", ls="--", lw=1)
    for x, lab in [(1, "基础期\n1-3月"), (4, "提高期\n4-6月"), (7, "深化期\n7-9月"), (10, "实战期\n10-12月")]:
        ax.text(x + 0.5, len(rows) - 0.2, lab, ha="center", fontsize=8.5, color="k")
    # 图例
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in field_color.values()]
    ax.legend(handles, field_color.keys(), loc="lower right", fontsize=8, ncol=2)
    ax.set_title("图 F-1  6–12 个月深入自学路线图：四大领域递进, 最后留足时间做综合项目", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out("roadmap.png")


if __name__ == "__main__":
    main()
