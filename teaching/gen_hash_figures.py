# -*- coding: utf-8 -*-
"""为第 6 章(口令 / 哈希键控)生成真实数据驱动的可视化图。

复刻 src/ns5_core.py 的 permute_index (splitmix64 + Fisher-Yates) 算法本身,
内容:
  - hash_permute_path  : 同一图像二维格子上, 不同 seed 的"访问顺序" 热图
  - hash_permute_scatter: 一维 位置 vs 访问次序 散点(确定性 + 种子敏感)

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_hash_figures.py
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


def permute_index(total: int, seed: int) -> np.ndarray:
    """与 src/ns5_core.py 相同的 splitmix64 + Fisher-Yates 确定性置换。"""
    mask = (1 << 64) - 1
    a = np.arange(total, dtype=np.int64)
    x = int(seed) & mask
    for i in range(total - 1, 0, -1):
        x = (x + 0x9E3779B97F4A7C15) & mask
        z = x
        z = (z ^ (z >> 30)) & mask
        z = (z * 0xBF58476D1CE4E5B9) & mask
        z = (z ^ (z >> 27)) & mask
        z = (z * 0x94D049BB133111EB) & mask
        r = (z ^ (z >> 31)) & mask
        j = int(r % (i + 1))
        a[i], a[j] = a[j], a[i]
    return a


def fig_path():
    side = 64
    n = side * side
    # 用彩色热图显示"访问顺序": 位置(index) -> 次序(rank=perm+1)
    def rank_img(seed):
        perm = permute_index(n, seed)
        img = np.zeros((side, side), np.int64)
        img[np.unravel_index(np.arange(n), (side, side))] = perm + 1
        return img
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 5.0))
    imgs = [(rank_img(0x1234ABCD), "seed = 0x1234ABCD (口令 A)"),
            (rank_img(0x9F00BEEF), "seed = 0x9F00BEEF (口令 B)")]
    for ax, (im, t) in zip(axes, imgs):
        im_ = ax.imshow(im, cmap="viridis")
        ax.set_title(t, fontsize=9.5)
        ax.axis("off")
    fig.colorbar(im_, ax=axes, fraction=0.03, pad=0.02).set_label("访问次序 (1 = 最先, 最大 = 最后)")
    fig.suptitle("图 6-1  嵌入位置是「由密钥决定的伪随机顺序」：两张不同口令给出完全不同的路径", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("hash_permute_path.png")


def fig_scatter():
    n = 400
    seeds = {"口令 A": 0x1234ABCD, "口令 B": 0x9F00BEEF}
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    colors = {"口令 A": ACCENT, "口令 B": WARM}
    for name, seed in seeds.items():
        perm = permute_index(n, seed)
        rank = np.argsort(perm) + 1            # rank[p] = 位置 p 的访问次序
        ax.scatter(np.arange(n), rank, s=4, alpha=0.6, color=colors[name], label=f"{name}  (位置→次序)")
    ax.plot(np.arange(n), np.arange(n) + 1, ls="--", color=GREY, lw=1.2,
            label="不置乱(顺序) = 可预测=危险")
    ax.set_xlabel("像素位置 index"); ax.set_ylabel("访问次序 rank")
    ax.set_title("图 6-2  键控置换: 同样是置换(每点一次), 但不同口令顺序完全不同", fontsize=10.5)
    ax.legend(fontsize=8)
    out("hash_permute_scatter.png")


def main():
    setstyle()
    print("生成哈希键控相关图...")
    fig_path()
    fig_scatter()
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
