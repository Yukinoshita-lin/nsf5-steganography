# -*- coding: utf-8 -*-
"""为第 4/5 章(矩阵编码 / F5 / nsF5)生成真实数据驱动的可视化图。

内容:
  - f5_syndrome_demo   : 矩阵编码伴随式原理示意(H 矩阵, 算伴随式, 换一列)
  - f5_efficiency      : 嵌入效率 p/n(每像素容量)、改动率、每改动携带比特数 随 p 变化
                       (对比朴素 LSB)。用真实公式计算, 非手绘。

输出: teaching/web/{zh,en}/assets/*.png  (双语标签)
用法: python teaching/gen_f5_figures.py
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
ACCENT, WARM, GREEN, GREY = "#1f77b4", "#d62728", "#2ca02c", "#7f7f7f"


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


def build_hamming(p):
    n = (1 << p) - 1
    return np.array([[ (j >> k) & 1 for j in range(1, n + 1)] for k in range(p)], np.uint8)


def syndrome(H, x):
    return (H @ x) % 2


# ----------------------------------------------------------------------
# 1) 矩阵编码伴随式示意
# ----------------------------------------------------------------------
def _strips(ax, arr, title, cmap="Blues", highlight=None, hi_color=None):
    arr = np.asarray(arr, np.uint8)
    ax.imshow(arr[None, :], cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(arr.size)); ax.set_xticklabels([f"{i+1}" for i in range(arr.size)], fontsize=7)
    ax.set_yticks([])
    ax.set_title(title, fontsize=8.5)
    if arr.size >= 3:
        ax.set_xlabel("位 1→" + str(arr.size), fontsize=7)
    for c in range(arr.size):
        ax.text(c, 0, str(arr[c]), ha="center", va="center",
                fontsize=8, color="white" if arr[c] else "black")
    if highlight is not None:
        ax.add_patch(plt.Rectangle((highlight - 0.5, -0.5), 1, 1, fill=False,
                                   edgecolor=WARM, lw=2.5))


def fig_syndrome_demo():
    p, n = 3, 7
    H = build_hamming(p)
    rng = np.random.default_rng(3)
    x = rng.integers(0, 2, n).astype(np.uint8)          # 当前块 LSB
    m = rng.integers(0, 2, p).astype(np.uint8)          # 想写的 p 位消息
    s = syndrome(H, x)
    d = (s ^ m).astype(np.uint8)
    col = int(np.where(np.all(H == d[:, None], axis=0))[0][0])
    x2 = x.copy(); x2[col] ^= 1

    fig = plt.figure(figsize=(12.5, 6.0))
    gs = fig.add_gridspec(2, 3, width_ratios=[1.15, 1.0, 1.0], hspace=0.55, wspace=0.35,
                          left=0.05, right=0.98, top=0.86, bottom=0.10)

    # --- 左上: H 矩阵 ---
    ax = fig.add_subplot(gs[0, 0])
    ax.set_title("① 伴随矩阵 H (p=3, n=7): 每一列是一个 3 位二进制", fontsize=8.5)
    ax.imshow(H.astype(float), cmap="Blues", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(n)); ax.set_xticklabels(range(1, n + 1), fontsize=7)
    ax.set_yticks(range(p)); ax.set_yticklabels(["b1", "b2", "b3"], fontsize=7)
    for r in range(p):
        for c in range(n):
            ax.text(c, r, str(H[r, c]), ha="center", va="center", fontsize=7,
                    color="white" if H[r, c] else "black")
    ax.add_patch(plt.Rectangle((col - 0.5, -0.5), 1, p, fill=False, edgecolor=WARM, lw=2.2))
    ax.set_xlabel("像素位 1~7 (列)", fontsize=8)

    # --- 左下: 当前 LSB 块 x + 伴随式 s ---
    ax = fig.add_subplot(gs[1, 0])
    _strips(ax, x, "② 这一块 7 个像素的 LSB : x", cmap="Blues", highlight=col)
    ax.text(x.size + 0.6, 0, "→ s=H·x", va="center", fontsize=9, color=GREY)

    # --- 右列: 流程 s / m / d / 结果 ---
    ax = fig.add_subplot(gs[0, 1]); _strips(ax, s, "③ 伴随式 s = H·x", cmap="Greys")
    ax = fig.add_subplot(gs[0, 2]); _strips(ax, m, "④ 想藏的 3 位消息 m", cmap="Greens")
    ax = fig.add_subplot(gs[1, 1]); _strips(ax, d, "⑤ 差分 d = s ⊕ m", cmap="Reds")
    ax = fig.add_subplot(gs[1, 2]); _strips(ax, x2, "⑥ 翻转第 %d 列后: H·x′ = m ✓" % (col + 1),
                                            cmap="Blues", highlight=col, hi_color=WARM)

    fig.suptitle("图 4-1  矩阵编码：7 个像素的 LSB 藏 3 位，通常只需翻 1 个像素"
                 f"\n本轮: x={''.join(map(str, x))}  m={''.join(map(str, m))}  翻转列={col+1}",
                 fontsize=10.5)
    out("f5_syndrome_demo.png")


# ----------------------------------------------------------------------
# 2) 嵌入效率 / 改动率 随 p
# ----------------------------------------------------------------------
def fig_efficiency():
    ps = np.arange(1, 9)
    n = 2**ps - 1
    payload = ps / n                                  # bits/pixel
    change = (1 - 2.0**(-ps)) / n                     # changes/pixel (期望)
    eff = ps / (1 - 2.0**(-ps))                       # bits/change (期望)

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.8))
    axes[0].plot(ps, payload, "o-", color=ACCENT, lw=2)
    axes[0].axhline(1.0, ls="--", color=GREY)
    axes[0].text(ps[-1]-0.1, 1.02, "朴素 LSB=1", color=GREY, fontsize=8, ha="right")
    axes[0].set_xlabel("参数 p"); axes[0].set_ylabel("容量 (bits/像素)")
    axes[0].set_title("① 每像素能藏多少位\n容量 = p/(2^p-1)")

    axes[1].plot(ps, change, "o-", color=WARM, lw=2)
    axes[1].axhline(0.5, ls="--", color=GREY)
    axes[1].text(ps[-1]-0.1, 0.52, "朴素 LSB=0.5", color=GREY, fontsize=8, ha="right")
    axes[1].set_xlabel("参数 p"); axes[1].set_ylabel("改动率 (改动像素/总像素)")
    axes[1].set_title("② 平均改动多少像素\n改动率 = (1-2^-p)/(2^p-1)")

    axes[2].plot(ps, eff, "o-", color=GREEN, lw=2)
    axes[2].axhline(1.0, ls="--", color=GREY)
    axes[2].text(ps[-1]-0.1, 1.08, "朴素 LSB=1", color=GREY, fontsize=8, ha="right")
    axes[2].set_xlabel("参数 p"); axes[2].set_ylabel("效率 (携带比特数/每次改动)")
    axes[2].set_title("③ 每次改动能携带多少位\n效率 = p/(1-2^-p)")
    fig.suptitle("图 4-2  矩阵编码为什么比朴素 LSB 高效：p 越大, 每次改动携带越多的秘密位", y=1.04)
    out("f5_efficiency.png")


# ----------------------------------------------------------------------
# 3) 容量-改动率 权衡(把三种画在一张, 便于对比"藏多少 vs 改多少")
# ----------------------------------------------------------------------
def fig_tradeoff():
    ps = np.arange(1, 9)
    n = 2**ps - 1
    payload = ps / n
    change = (1 - 2.0**(-ps)) / n
    fig, ax = plt.subplots(figsize=(7.4, 5.2))
    ax.plot(payload, change, "o-", color=ACCENT, lw=2)
    for p_, pl, ch in zip(ps, payload, change):
        ax.annotate(f"p={p_}", xy=(pl, ch), xytext=(pl+0.015, ch+0.008), fontsize=8)
    ax.plot([0.0, 1.0], [0.0, 0.5], "--", color=WARM, lw=1.8, label="朴素 LSB（1 bit/改动）")
    ax.scatter([1.0], [0.5], color=WARM, s=60, zorder=5)
    ax.set_xlabel("容量 (bits/像素)"); ax.set_ylabel("改动率 (改动像素/总像素)")
    ax.set_title("图 4-3  容量-改动率权衡：矩阵编码大幅改进\n(同等改动率下能藏更多, 或同等容量下改得更少=痕迹更小)")
    ax.legend(fontsize=9)
    out("f5_tradeoff.png")


def main():
    setstyle()
    print("生成矩阵编码相关图...")
    fig_syndrome_demo()
    fig_efficiency()
    fig_tradeoff()
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
