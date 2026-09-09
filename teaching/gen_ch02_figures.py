# -*- coding: utf-8 -*-
"""为第 2 章(Python/NumPy/Pillow 工具链)生成真实数据驱动的可视化图。

数据: data/campus_jpg/ 下的一张真实 JPEG。
内容:
  - py_image_array : 原图 | R | G | B 通道 | 转灰度, 并标注数组形状/类型
  - py_dtype_culprit: 展示 uint8 溢出回绕(200+100=44)与切片/转置视图 vs 连续数组

输出: teaching/web/{zh,en}/assets/*.png (双语标签)
用法: python teaching/gen_ch02_figures.py
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
CANDIDATES = [
    os.path.join(ROOT, "data", "campus_jpg", f) for f in
    sorted(os.listdir(os.path.join(ROOT, "data", "campus_jpg"))) if f.lower().endswith((".jpg", ".jpeg"))
]
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
        "panels": ["原图 (RGB)", "R 通道", "G 通道", "B 通道", "转灰度 (L)"],
        "ch_title": "图 2-1  一张图 = 一个数组: 彩色是 (H,W,3), 灰度是 (H,W), 类型都是 uint8\n(真实相机照片, 原尺寸 {}×{}×3)",
        "dtype_titles": [
            "① np.zeros((8,8),uint8) + 画方块\n元素类型 uint8 (0-255)",
            "② uint8 溢出回绕: 200+100={} (不是 300)\n所以改位用 ^1 而不是 ±1",
            "③ 转置/切片得『视图』, 内存不连续:\n   b = a.T          # 视图, shape=(8,8)\n   np.ascontiguousarray(b)  # 拷贝成连续\n很多底层库(如 PIL/PyTorch/ctypes)喜欢连续数组, 保存前要转一下。",
        ],
        "dtype_title": "图 2-2  dtype 与内存布局: 两条最容易被绕进去的坑",
    },
    "en": {
        "panels": ["original (RGB)", "R channel", "G channel", "B channel", "grayscale (L)"],
        "ch_title": "Fig. 2-1  an image is an array: color is (H,W,3), grayscale is (H,W), both uint8\n(real camera photo, original {}×{}×{})",
        "dtype_titles": [
            "(1) np.zeros((8,8),uint8) + a square\n element type uint8 (0-255)",
            "(2) uint8 overflow wraparound: 200+100={} (not 300)\n hence flipping bits uses ^1 not ±1",
            "(3) transpose/slice gives a 'view', non-contiguous memory:\n   b = a.T          # view, shape=(8,8)\n   np.ascontiguousarray(b)  # copy to contiguous\nmany low-level libs (PIL/PyTorch/ctypes) want contiguous arrays; convert before saving.",
        ],
        "dtype_title": "Fig. 2-2  dtype and memory layout: two easy pitfalls",
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


def fig_channels(img_rgb, lang):
    S = L[lang]
    h, w, _ = img_rgb.shape
    disp = Image.fromarray(img_rgb); disp.thumbnail((200, 200))
    d = np.asarray(disp, np.uint8)
    panels = [(S["panels"][0], d), (S["panels"][1], d[..., 0]), (S["panels"][2], d[..., 1]),
              (S["panels"][3], d[..., 2]), (S["panels"][4], np.asarray(Image.fromarray(d).convert("L"), np.uint8))]
    fig, axes = plt.subplots(1, 5, figsize=(15.5, 3.6))
    for ax, (t, im) in zip(axes, panels):
        if im.ndim == 3:
            ax.imshow(im)
        else:
            ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(t, fontsize=9)
        ax.axis("off")
    fig.suptitle(S["ch_title"].format(h, w, 3), fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.86])
    out("py_image_array.png", lang)


def fig_dtype(lang):
    S = L[lang]
    a = np.zeros((8, 8), dtype=np.uint8)
    a[2:6, 2:6] = 255
    val = np.uint8(200)
    wrap = val + np.uint8(100)
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8))
    axes[0].imshow(a, cmap="gray", vmin=0, vmax=255)
    axes[0].set_title(S["dtype_titles"][0], fontsize=9)
    axes[1].bar(["200", "+100", "=result"], [200, 100, int(wrap)], color=["#1f77b4", "#1f77b4", "#d62728"])
    axes[1].set_title(S["dtype_titles"][1].format(int(wrap)), fontsize=9)
    axes[1].set_ylim(0, 320)
    axes[2].axis("off")
    axes[2].text(0.05, 0.8, S["dtype_titles"][2], fontsize=9, va="top")
    fig.suptitle(S["dtype_title"], fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.86])
    out("py_dtype_culprit.png", lang)


def main():
    setstyle()
    if not CANDIDATES:
        print("未找到校园 JPEG, 用 cover.png 替代")
        img_rgb = np.asarray(Image.open(os.path.join(ROOT, "img", "cover.png")).convert("RGB"), np.uint8)
    else:
        img_rgb = np.asarray(Image.open(CANDIDATES[0]).convert("RGB"), np.uint8)
    print("源图", CANDIDATES[0] if CANDIDATES else "cover", img_rgb.shape)
    for lang in ("zh", "en"):
        fig_channels(img_rgb, lang)
        fig_dtype(lang)
    print("完成 → ", ZH)


if __name__ == "__main__":
    main()
