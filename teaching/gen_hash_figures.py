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

# 双语标签
L = {
    "zh": {
        "title": "图 6-1  嵌入位置是「由密钥决定的伪随机顺序」：两张不同口令给出完全不同的路径",
        "seed_a": "seed = 0x1234ABCD (口令 A)",
        "seed_b": "seed = 0x9F00BEEF (口令 B)",
        "cbar": "访问次序 (1 = 最先, 最大 = 最后)",
        "scatter_title": "图 6-2  键控置换: 同样是置换(每点一次), 但不同口令顺序完全不同",
        "xlabel": "像素位置 index", "ylabel": "访问次序 rank",
        "order_note": "不置乱(顺序) = 可预测=危险",
        "pw_a": "口令 A", "pw_b": "口令 B",
        "legend": "位置→次序",
    },
    "en": {
        "title": "Fig. 6-1  Embedding positions follow a keyed pseudo-random order: two passwords give completely different paths",
        "seed_a": "seed = 0x1234ABCD (password A)",
        "seed_b": "seed = 0x9F00BEEF (password B)",
        "cbar": "visit order (1 = first, max = last)",
        "scatter_title": "Fig. 6-2  Keyed permutation: the same permutation (each point once), but a different password gives a completely different order",
        "xlabel": "pixel index", "ylabel": "visit rank",
        "order_note": "no shuffle (sequential) = predictable = dangerous",
        "pw_a": "password A", "pw_b": "password B",
        "legend": "pos -> order",
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


def fig_path(lang):
    side = 64
    n = side * side
    def rank_img(seed):
        perm = permute_index(n, seed)
        img = np.zeros((side, side), np.int64)
        img[np.unravel_index(np.arange(n), (side, side))] = perm + 1
        return img
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 5.0))
    imgs = [(rank_img(0x1234ABCD), L[lang]["seed_a"]),
            (rank_img(0x9F00BEEF), L[lang]["seed_b"])]
    im_ = None
    for ax, (im, t) in zip(axes, imgs):
        im_ = ax.imshow(im, cmap="viridis")
        ax.set_title(t, fontsize=9.5)
        ax.axis("off")
    # 色条只挂在第二个子图右侧, 避免遮挡右侧热图(勘误: 图例渐变色条应右移)
    cax = fig.colorbar(im_, ax=axes[1], fraction=0.046, pad=0.04)
    cax.set_label(L[lang]["cbar"], fontsize=9)
    fig.suptitle(L[lang]["title"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("hash_permute_path.png", lang)


def fig_scatter(lang):
    n = 400
    seeds = {L[lang]["pw_a"]: 0x1234ABCD, L[lang]["pw_b"]: 0x9F00BEEF}
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    colors = {L[lang]["pw_a"]: ACCENT, L[lang]["pw_b"]: WARM}
    for name, seed in seeds.items():
        perm = permute_index(n, seed)
        rank = np.argsort(perm) + 1
        ax.scatter(np.arange(n), rank, s=4, alpha=0.6, color=colors[name],
                   label=f"{name}  ({L[lang]['legend']})")
    ax.plot(np.arange(n), np.arange(n) + 1, ls="--", color=GREY, lw=1.2,
            label=L[lang]["order_note"])
    ax.set_xlabel(L[lang]["xlabel"]); ax.set_ylabel(L[lang]["ylabel"])
    ax.set_title(L[lang]["scatter_title"], fontsize=10.5)
    ax.legend(fontsize=8)
    out("hash_permute_scatter.png", lang)


def main():
    setstyle()
    print("生成哈希键控相关图...")
    for lang in ("zh", "en"):
        fig_path(lang)
        fig_scatter(lang)
    print("完成 → ", ZH, "和", EN)


if __name__ == "__main__":
    main()
