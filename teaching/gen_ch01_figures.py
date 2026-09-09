# -*- coding: utf-8 -*-
"""为第 1 章(数字图像与二进制)生成真实数据驱动的可视化图。

数据: img/cover.png (256x256 灰度)。做真实位平面分解与逐层累加重建。
内容:
  - bit_planes      : 原图 + 8 个位平面(bit7..bit0)
  - bit_reconstruct : 从最高位逐层累加(bit7 → ... → 全部8层=原图)

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_ch01_figures.py
"""
from __future__ import annotations
import os
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

L = {
    "zh": {
        "orig": "原图\n0-255",
        "planes_title": "图 1-1  一张 8bit 灰度图拆成 8 个位平面 (bit7=最高位, bit0=最低位/LSB)",
        "recon_layers": "已加 {}/8 层\n最高 {} 位",
        "recon_title": "图 1-2  从最高位逐层累加: 加得越多越清晰, 8 层全加 = 精确还原原图\n原图 = Σ (bit_k)×2^k, 每一层必须乘其权重再相加",
    },
    "en": {
        "orig": "original\n0-255",
        "planes_title": "Fig. 1-1  an 8-bit grayscale image split into 8 bit planes (bit7 = MSB, bit0 = LSB)",
        "recon_layers": "{}/8 layers\nhigh {} bits",
        "recon_title": "Fig. 1-2  accumulating from the MSB: more layers = clearer, all 8 = exact reconstruction\noriginal = sum (bit_k) x 2^k, each layer must be weighted before summing",
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


def load_cover():
    im = Image.open(COVER)
    if im.mode != "L":
        im = im.convert("L")
    return np.asarray(im, np.uint8)


def fig_planes(img, lang):
    S = L[lang]
    fig, axes = plt.subplots(1, 9, figsize=(16.5, 3.2))
    plt.rcParams["image.interpolation"] = "nearest"
    axes[0].imshow(img, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title(S["orig"], fontsize=9)
    for k in range(8):
        plane = ((img >> k) & 1) * 255
        axes[k + 1].imshow(plane, cmap="gray", vmin=0, vmax=255)
        axes[k + 1].set_title(f"bit {k}\n×{2**k}", fontsize=9)
    for ax in axes:
        ax.axis("off")
    fig.suptitle(S["planes_title"], fontsize=11.5)
    fig.tight_layout(rect=[0, 0, 1, 0.82])
    out("bit_planes.png", lang)


def fig_reconstruct(img, lang):
    S = L[lang]
    fig, axes = plt.subplots(1, 8, figsize=(16.5, 3.4))
    plt.rcParams["image.interpolation"] = "nearest"
    acc = np.zeros_like(img, dtype=np.int32)
    for k in range(8, 0, -1):
        b = k - 1
        acc = acc + (((img >> b) & 1) * (2**b))
        axes[8 - k].imshow(np.clip(acc, 0, 255), cmap="gray", vmin=0, vmax=255)
        n_layers = 8 - b
        axes[8 - k].set_title(S["recon_layers"].format(n_layers, n_layers), fontsize=8.5)
    for ax in axes:
        ax.axis("off")
    fig.suptitle(S["recon_title"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.84])
    out("bit_reconstruct.png", lang)


def main():
    setstyle()
    img = load_cover()
    print("cover", img.shape, img.dtype)
    for lang in ("zh", "en"):
        fig_planes(img, lang)
        fig_reconstruct(img, lang)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
