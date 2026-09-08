"""Generate PNG assets used by the interactive teaching website.

Run with a Python that has numpy/matplotlib/Pillow plus project deps:
    python scripts/generate_web_assets.py

Assets are written to webapp/assets/ and are committed with the web app.
"""

from __future__ import annotations

import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "webapp", "assets")
os.makedirs(OUT, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, os.path.join(ROOT, "src"))


def demo_image(n=360, seed=7):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 200, n)[None, :]
    x = np.linspace(0, 130, n)[:, None]
    wave = 12 * np.sin(np.linspace(0, 24, n))[None, :]
    return np.clip(70 + x + y + wave + rng.integers(-8, 9, (n, n)), 0, 255).astype(np.uint8)


def hero_covers():
    cover = demo_image()
    from ns5_core import embed_string
    stego, rep, _ = embed_string(cover, "Hello nsF5! This is a hidden message.",
                                 method="nsF5", p=3)
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 5.4))
    for ax, img, title in ((axes[0], cover, "cover"), (axes[1], stego, "stego")):
        ax.imshow(img, cmap="gray", vmin=0, vmax=255)
        ax.set_title(title, fontsize=15, fontweight="bold")
        ax.axis("off")
    fig.suptitle("", fontsize=1)
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "hero-covers.png"), dpi=110, bbox_inches="tight")
    plt.close(fig)


def lsb_planes():
    img = demo_image(180)
    fig, axes = plt.subplots(1, 4, figsize=(10.5, 3.4))
    titles = ["original", "MSB plane 7", "plane 4", "LSB plane 0"]
    views = [img, ((img >> 7) & 1) * 255, ((img >> 4) & 1) * 255, ((img >> 0) & 1) * 255]
    for ax, im, ti in zip(axes, views, titles):
        ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(ti, fontsize=11)
        ax.axis("off")
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "lsb-planes.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def stego_detect():
    from ns5_core import embed_string
    import steganalysis as SA
    clean = demo_image(256)
    stego, _, _ = embed_string(clean, "S" * 4000, method="nsF5", p=3)
    rc = SA.analyze(clean)
    rs = SA.analyze(stego)
    labels = ["Gn (RS)", "chi2 p", "stego prob"]
    clean_v = [rc["RS_Gn"], rc["chi2_pvalue"], rc["stego_probability"]]
    stego_v = [rs["RS_Gn"], rs["chi2_pvalue"], rs["stego_probability"]]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    ax.bar(x - 0.2, clean_v, 0.4, label="clean", color="#4c9be8")
    ax.bar(x + 0.2, stego_v, 0.4, label="stego", color="#ef6f9f")
    ax.set_xticks(x, labels)
    ax.legend(frameon=False)
    ax.grid(alpha=0.2, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "stego-detect.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def diff_mask():
    from ns5_core import embed_string
    cover = demo_image(256, seed=11)
    stego, _, _ = embed_string(cover, "S" * 1200, method="nsF5", p=3)
    mask = (stego != cover).astype(np.uint8) * 255
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 3.9))
    for ax, im, title in ((axes[0], cover, "cover"), (axes[1], stego, "stego"),
                          (axes[2], mask, "changed pixels")):
        ax.imshow(im, cmap="gray", vmin=0, vmax=255)
        ax.set_title(title, fontsize=11)
        ax.axis("off")
    fig.tight_layout(pad=0.4)
    fig.savefig(os.path.join(OUT, "diff-mask.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def histogram_pairs(lang):
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    cover = demo_image(220, seed=3)
    stego = cover.copy()
    rng = np.random.default_rng(9)
    for i in range(0, cover.size, 2):
        if rng.random() < 0.45:
            stego.flat[i] = (stego.flat[i] & 0xfe) | (1 - (stego.flat[i] & 1))
    bins = np.arange(0, 258, 2)
    hc, _ = np.histogram(cover.ravel(), bins=bins)
    hs, _ = np.histogram(stego.ravel(), bins=bins)
    fig, ax = plt.subplots(figsize=(7.6, 3.5))
    x = np.arange(len(hc))
    w = 0.4
    ax.bar(x - w / 2, hc, w, label=("clean" if lang == "en" else "干净图"), color="#4c9be8")
    ax.bar(x + w / 2, hs, w, label=("embedded" if lang == "en" else "嵌入后"), color="#ef6f9f")
    ax.set_xlabel(("gray-level pair (2i, 2i+1)" if lang == "en" else "灰度相邻对 (2i, 2i+1)"))
    ax.set_ylabel(("count" if lang == "en" else "频数"))
    ax.set_title(("LSB replacement flattens pair counts"
                  if lang == "en" else "LSB 替换把相邻对频数拉平"), fontsize=11)
    ax.legend(frameon=False)
    ax.grid(alpha=0.2, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"histogram-pairs-{lang}.png"), dpi=120,
                bbox_inches="tight")
    plt.close(fig)


def wetpaper(lang):
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    values = [132, 129, 128, 127, 130, 126, 140]  # |xv|<=1 -> 127..129
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ax.axis("off")
    for i, v in enumerate(values):
        xv = v - 128
        wet = abs(xv) <= 1
        color = "#c62828" if wet else "#2e7d32"
        ax.text(i * 1.12, 0.35, str(v), ha="center", fontsize=15, fontweight="bold")
        ax.text(i * 1.12, 0.05, f"xv={xv:+d}", ha="center", fontsize=11, color=color)
        if wet:
            ax.text(i * 1.12, 0.62, "wet", ha="center", fontsize=9, color="#c62828")
        else:
            ax.text(i * 1.12, 0.62, "dry", ha="center", fontsize=9, color="#2e7d32")
    ax.text(-0.4, 1.55,
            ("wet (|xv|<=1) never used; solve on dry positions"
             if lang == "en" else "湿点 (|xv|≤1) 不承载消息，只在干点求解"),
            fontsize=12, ha="left")
    ax.set_xlim(-0.5, 7.8)
    ax.set_ylim(-0.15, 1.85)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, f"wetpaper-{lang}.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def hamming_illustration():
    p, n = 3, 7
    x = [0, 1, 0, 1, 1, 0, 1]
    H = np.array([[((j + 1) >> r) & 1 for j in range(n)] for r in range(p)])
    s = (H @ np.asarray(x)) & 1
    m = np.array([1, 1, 0])
    d = s ^ m
    hit = (d @ (1 << np.arange(p))) - 1
    fig, ax = plt.subplots(figsize=(8.8, 2.8))
    cell = 0.85
    for j in range(n):
        color = "#ffd54f" if j == hit else ("#2e7d32" if x[j] else "#e8edf3")
        edge = "#c62828" if j == hit else "#9aa7b5"
        rect = FancyBboxPatch((j * (cell + 0.2), 0.4), cell, cell,
                              boxstyle="round,pad=0.04",
                              facecolor=color, edgecolor=edge, lw=3 if j == hit else 1)
        ax.add_patch(rect)
        ax.text(j * (cell + 0.2) + cell / 2, 0.4 + cell / 2, str(x[j]),
                ha="center", va="center", fontsize=16, fontweight="bold")
        ax.text(j * (cell + 0.2) + cell / 2, 0.15, str(j + 1), ha="center", fontsize=9, color="#5b6b7a")
    ax.text(-0.5, 1.9, "s=" + "".join(map(str, s)) + "  m=" + "".join(map(str, m)) +
            "  d=" + "".join(map(str, d)) + "  -> flip #" + str(hit + 1),
            fontsize=12, family="monospace")
    ax.set_xlim(-0.9, n * (cell + 0.2) + 0.1)
    ax.set_ylim(0, 2.4)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "hamming-illustration.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def efficiency_curve():
    ps = np.arange(1, 7)
    theory = ps * (2.0 ** ps) / (2.0 ** ps - 1)
    measured = [2.015, 2.620, 3.392, 4.199, 5.119, 5.983]
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.plot(ps, theory, "-o", label="theory alpha(p)", color="#2e74b5")
    ax.plot(ps, measured, "-s", label="measured", color="#12b5a5")
    ax.set_xlabel("p")
    ax.set_ylabel("embedding efficiency (bits / change)")
    ax.set_xticks(ps)
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "efficiency-curve.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def roc_illustration():
    tpr = np.linspace(0, 1, 200)
    fpr = tpr ** 1.6
    fig, ax = plt.subplots(figsize=(6.4, 5.0))
    ax.plot([0, 1], [0, 1], "--", color="#aab4bf", lw=1.2)
    ax.plot(fpr, tpr, color="#2e74b5", lw=2.6, label="strong model")
    ax.fill_between(fpr, tpr, alpha=0.12, color="#2e74b5")
    ax.set_xlabel("false positive rate")
    ax.set_ylabel("true positive rate")
    ax.set_title("ROC illustration (AUC ~ 0.91)", fontsize=11)
    ax.legend(frameon=False, loc="lower right")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "roc-illustration.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def dual_models():
    groups = ["8-split AUC", "held-out AUC", "OOD clean FP / 8"]
    m143 = [0.9085, 0.8946, 1]
    m53 = [0.9227, 0.9100, 3]
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    ax.bar(x - 0.2, m143, 0.4, label="143-D robust", color="#2e74b5")
    ax.bar(x + 0.2, m53, 0.4, label="53-D interpretable", color="#ef9f6f")
    ax.set_xticks(x, groups, fontsize=9)
    ax.legend(frameon=False)
    ax.grid(alpha=0.2, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "dual-models.png"), dpi=120, bbox_inches="tight")
    plt.close(fig)


def pipeline(lang):
    labels = {
        "zh": ["载体", "消息", "嵌入", "含密图", "解码", "分析"],
        "en": ["cover", "msg", "embed", "stego", "decode", "analyze"],
    }[lang]
    fig, ax = plt.subplots(figsize=(11.4, 2.6))
    ax.axis("off")
    xs = [0, 1.3, 2.9, 4.5, 6.1, 7.7]
    palette = ["#90caf9", "#f5b042", "#4caf9b", "#ef6f9f", "#7aa5f0", "#b48ce6"]
    for x0, name, color in zip(xs, labels, palette):
        box = FancyBboxPatch((x0, 0.5), 1.1, 1.2, boxstyle="round,pad=0.06",
                             facecolor=color, edgecolor="none")
        ax.add_patch(box)
        ax.text(x0 + 0.55, 1.1, name, ha="center", va="center",
                fontsize=11, fontweight="bold", color="white")
    for a, b in zip(xs[:3], xs[1:4]):
        ax.add_patch(FancyArrowPatch((a + 1.12, 1.1), (b - 0.06, 1.1),
                                     arrowstyle="-|>", mutation_scale=14,
                                     color="#445566", lw=1.6))
    for a, b in [(4.62, 6.04), (4.62, 7.62)]:
        ax.add_patch(FancyArrowPatch((a, 1.1), (b, 1.1), arrowstyle="-|>",
                                     mutation_scale=14, color="#445566", lw=1.2))
    ax.text(4.0, 0.1, "", fontsize=1)
    ax.set_xlim(-0.3, 9.4)
    ax.set_ylim(0, 2.1)
    fig.tight_layout()
    path = os.path.join(OUT, f"pipeline-{lang}.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    for fn in (hero_covers, lsb_planes, stego_detect, diff_mask,
               hamming_illustration, efficiency_curve, roc_illustration,
               dual_models):
        fn()
    for lang in ("zh", "en"):
        pipeline(lang)
        histogram_pairs(lang)
        wetpaper(lang)
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
