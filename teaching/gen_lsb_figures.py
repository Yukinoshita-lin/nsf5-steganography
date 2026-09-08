# -*- coding: utf-8 -*-
"""为第 3 章(LSB 隐写与统计指纹)生成真实数据驱动的可视化图。

数据: img/cover.png (项目演示载体)。用朴素 LSB 替换嵌入随机比特, 生成含密图。
内容:
  - lsb_cover_stego  : 载体 | 含密 | 放大差异(|cover-stego|*255) | LSB 平面
  - lsb_pixel_level  : 一小块真实像素值 嵌入前后 对比, 高亮被翻转的 LSB

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_lsb_figures.py
"""
from __future__ import annotations
import os, shutil
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


def load_cover():
    im = Image.open(COVER)
    if im.mode != "L":
        im = im.convert("L")
    a = np.asarray(im, np.uint8)
    if a.size == 0:
        raise RuntimeError("cover.png empty")
    return a


def lsb_replace(cover, rng, ratio=0.5):
    """朴素 LSB 替换: 随机选 ratio 比例像素, 把其 LSB 随机重写(模拟藏随机消息)。"""
    stego = cover.copy().astype(np.uint8)
    flat = stego.ravel()
    n = flat.size
    idx = rng.choice(n, size=int(n * ratio), replace=False)
    flat[idx] = (flat[idx] & 0xFE) | rng.integers(0, 2, idx.size)
    return stego.reshape(cover.shape)


def fig_cover_stego(cover, stego):
    diff = np.abs(cover.astype(int) - stego.astype(int))
    lsb_clean = (cover & 1) * 255
    fig, axes = plt.subplots(1, 4, figsize=(15.5, 4.4))
    plt.rcParams["image.interpolation"] = "nearest"
    axes[0].imshow(cover, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title("① 载体 cover (原图)", fontsize=9)
    axes[1].imshow(stego, cmap="gray", vmin=0, vmax=255)
    axes[1].set_title("② 含密 stego (LSB 藏随机比特)", fontsize=9)
    axes[2].imshow(diff * 255, cmap="hot", vmin=0, vmax=255)
    axes[2].set_title(f"③ 差异放大 ×255: 改了 {int((diff>0).sum())/diff.size:.1%} 像素", fontsize=9)
    axes[3].imshow(lsb_clean, cmap="gray", vmin=0, vmax=255)
    axes[3].set_title("④ cover 的 LSB 位平面(本就近似噪声)", fontsize=9)
    for ax in axes:
        ax.axis("off")
    fig.suptitle("图 3-1  肉眼看几乎一模一样, 但差异放大与 LSB 位平面会露出端倪", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("lsb_cover_stego.png")


def fig_pixel_level(cover, stego):
    r0, c0 = 12, 16          # 取一小块区域
    h, w = 8, 10
    cov = cover[r0:r0+h, c0:c0+w].astype(int)
    ste = stego[r0:r0+h, c0:c0+w].astype(int)
    changed = cov != ste
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.5))
    for ax, mat, title in [(axes[0], cov, "① 原图这一小块"), (axes[1], ste, "② 藏了比特后")]:
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
    ax.set_title(f"③ 这一小块改动: {int(changed.sum())}/{h*w} 像素", fontsize=9)
    fig.suptitle("图 3-2  像素级对比: 只是个别像素的 LSB 变了 0↔1, 灰度几乎不变", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out("lsb_pixel_level.png")


def main():
    setstyle()
    cover = load_cover()
    rng = np.random.default_rng(0)
    stego = lsb_replace(cover, rng, ratio=0.5)
    print("cover", cover.shape, "改成", int(np.sum(cover != stego)), "像素")
    fig_cover_stego(cover, stego)
    fig_pixel_level(cover, stego)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
