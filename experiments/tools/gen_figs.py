# -*- coding: utf-8 -*-
"""论文实验3: 其余支撑图
  (a) 码族与嵌入效率 理论 vs 实测
  (b) 隐写分析随载荷扫描 (卡方p / RS率 / ML概率)
  (c) 篡改感知演示 (哈希键控 + 解码还原成功/失败)
  (d) 系统架构图  (代码绘制)
  (e) 伴随式矩阵编码查询示意 (高亮命中的被改系数)
CSV → experiments/data ; 图 → experiments/figs
"""
from __future__ import annotations
import sys, os, csv, glob
os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.abspath("src"); GPU = os.path.abspath("gpu")
for p in (SRC, GPU):
    if p not in sys.path: sys.path.insert(0, p)
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from PIL import Image as PILImage

OUTD = os.path.join("experiments", "data"); FIGD = os.path.join("experiments", "figs")
os.makedirs(OUTD, exist_ok=True); os.makedirs(FIGD, exist_ok=True)
C = dict(blue="#1a73e8", red="#c62828", green="#2e7d32", purple="#8e24aa",
         teal="#00897b", amber="#ffd54f", gray="#607d8b")


# ---------------- (a) 码族与嵌入效率 ----------------
import efficiency as EF
cm = EF.compute_comparison(p_max=6)
ps = [r["p"] for r in cm]; aT = [r["alpha"] for r in cm]; aM = [r["measured_alpha"] for r in cm]
R = [r["code_rate"] for r in cm]
with open(os.path.join(OUTD, "code_family.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["p", "n", "k", "code_rate", "alpha_theory", "alpha_measured"])
    for r in cm: w.writerow([r["p"], r.get("n", ""), r.get("k", ""), r["code_rate"], r["alpha"], r["measured_alpha"]])
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(8.6, 3.4))
ax1.plot(ps, aT, "o-", label="理论 α=p·2^p/(2^p−1)", color=C["blue"])
ax1.plot(ps, aM, "s--", label="实测 nsF5(减幅+湿纸)", color=C["red"])
ax1.set_xlabel("矩阵编码参数 p"); ax1.set_ylabel("嵌入效率 α (载荷/改动)")
ax1.set_title("码族/嵌入效率"); ax1.grid(alpha=0.3); ax1.legend(fontsize=8)
ax2.plot(ps, R, "^-", color=C["green"])
ax2.set_xlabel("p"); ax2.set_ylabel("码率 R = k/n")
ax2.set_title("汉明码 [2^p−1, 2^p−1−p, 3] 码率"); ax2.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "code_family.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "code_family.svg")); plt.close(fig)
print("(a) code_family 完成")

# ---------------- (b) 载荷扫描 ----------------
import scan_panel as SP


def _sample_photo():
    """取一张有内容的灰度测试图。

    原先硬编码 `F:\\DCIM\\Camera\\*.jpg` —— 那是作者本机路径, 别人跑必然
    IndexError。改为按优先级找: 环境变量 NSF5_SAMPLE_PHOTO → 仓库内
    data/campus_jpg/ → 合成图(保证任何环境都能出图)。
    """
    env = os.environ.get("NSF5_SAMPLE_PHOTO")
    if env and os.path.exists(env):
        return env
    # 本脚本开头已 chdir 到仓库根, 故用相对路径
    hits = sorted(glob.glob(os.path.join("data", "campus_jpg", "*.jpg")))
    if hits:
        return hits[0]
    print("  (未找到样本照片, 改用合成图; 可用 NSF5_SAMPLE_PHOTO=<path> 指定)")
    return None


_photo = _sample_photo()
if _photo:
    im = PILImage.open(_photo).convert("L").resize((512, 512), PILImage.LANCZOS)
else:
    yy, xx = np.mgrid[0:512, 0:512]
    im = PILImage.fromarray(np.clip(
        110 + 45 * np.sin(xx / 23.0) + 35 * np.cos(yy / 31.0), 0, 255).astype(np.uint8))
a = np.asarray(im, dtype=np.uint8)
res = SP.scan_curves(a, method="nsF5", p=3, password="", densities=(0, 0.05, 0.1, 0.2, 0.3, 0.4))
with open(os.path.join(OUTD, "scan_curves.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["density", "chi2_pvalue", "rs_rate_pct", "ml_proba_pct"])
    for i, dd in enumerate(res["densities"]):
        w.writerow([round(float(dd), 3), round(float(res["chi2_pvalue"][i]), 5),
                    round(float(res["rs_rate"][i]), 3), round(float(res["ml_proba"][i]), 3)])
fig, axes = plt.subplots(1, 3, figsize=(12.2, 3.0))
axes[0].plot(res["densities"], res["chi2_pvalue"], "-o", color=C["red"]); axes[0].axhline(0.05, ls="--", color="#888")
axes[0].set_title("卡方检验 p 值"); axes[0].set_xlabel("density"); axes[0].grid(alpha=0.3)
axes[1].plot(res["densities"], res["rs_rate"], "-o", color=C["blue"]); axes[1].set_ylabel("估计嵌入率 %")
axes[1].set_title("RS 估计嵌入率"); axes[1].set_xlabel("density"); axes[1].grid(alpha=0.3)
axes[2].plot(res["densities"], res["ml_proba"], "-o", color=C["green"]); axes[2].set_ylabel("含密概率 %")
axes[2].set_title("ML 含密概率"); axes[2].set_xlabel("density"); axes[2].grid(alpha=0.3)
fig.suptitle("隐写分析随载荷变化 (真实照片, nsF5 p=3)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "scan_curves.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "scan_curves.svg")); plt.close(fig)
print("(b) scan_curves 完成")

# ---------------- (c) 篡改感知演示 ----------------
import ns5_core as N
msg = "NSF5-STEGO KSM-kVUdh Security demo; hash-keyed payload 128-bit."
stego, _rep, _ = N.embed_string(a, msg, method="nsF5", p=3, password="demo")
try:
    ok1 = N.extract_string(stego, method="nsF5", p=3, password="demo") == msg
except Exception:
    ok1 = False
h_clean = N.get_image_hash(a)[:12]; h_stego = N.get_image_hash(stego)[:12]
tam = stego.copy()
tam[200:230, 240:300] ^= np.random.default_rng(1).integers(0, 2, (30, 60), dtype=np.uint8)
h_tam = N.get_image_hash(tam)[:12]
try:
    ok2 = (N.extract_string(tam, method="nsF5", p=3, password="demo") == msg)
except Exception:
    ok2 = False
with open(os.path.join(OUTD, "tamper.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["scenario", "hash_prefix", "restore_ok"])
    w.writerow(["clean", h_clean, ""]); w.writerow(["stego", h_stego, ok1]); w.writerow(["tampered", h_tam, ok2])
fig, axes = plt.subplots(1, 3, figsize=(11, 3.3))
for ax, (im_, title) in zip(axes, [
        (a, f"原始载体 h={h_clean}"), (stego, f"nsF5 含密 h={h_stego}\n还原={ok1}"),
        (tam, f"像素篡改 h={h_tam}\n还原={ok2}")]):
    ax.imshow(im_ & 1, cmap="gray", interpolation="nearest")
    ax.set_title(title, fontsize=9); ax.set_xticks([]); ax.set_yticks([])
axes[2].add_patch(plt.Rectangle((240, 200), 60, 30, fill=False, edgecolor=C["red"], lw=2))
fig.suptitle("篡改感知 (SHA-256 键控隐藏路径): 哈希变化 ⇒ 解码端无法自同步还原", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "tamper.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "tamper.svg")); plt.close(fig)
print(f"(c) tamper 完成  ok1={ok1} ok2={ok2}")

# ---------------- (d) 系统架构图 ----------------
fig, ax = plt.subplots(figsize=(8.6, 5.4))
ax.set_xlim(0, 10); ax.set_ylim(0, 7.2); ax.axis("off")
def box(x, y, w, h, text, fc="#eef3fb", ec=C["blue"], fs=9):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06", facecolor=fc, edgecolor=ec, lw=1.4)
    ax.add_patch(p); ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs)
def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.3, color=C["gray"]))
# 层1 GUI
box(1.2, 5.6, 7.6, 1.0, "GUI (Tkinter): 载入 / 嵌入 / 解码 / 盲分析 / 码族绘图 / 矩阵编码演示 / 载荷扫描", fc="#e8f0fe")
# 层2 功能
box(0.9, 4.35, 3.4, 1.0, "嵌入(ASCII→比特)\n哈希键控隐藏路径", fc="#fff8e1", ec=C["amber"])
box(5.7, 4.35, 3.4, 1.0, "解码提取\n自同步+篡改感知", fc="#fff8e1", ec=C["amber"])
box(0.9, 3.1, 3.4, 1.0, "盲隐写分析\n卡方+RS+11维特征", fc="#e8f5e9", ec=C["green"])
box(5.7, 3.1, 3.4, 1.0, "监督检测\nLR (GroupKFold)", fc="#e8f5e9", ec=C["green"])
# 层3 核心算法
box(0.4, 1.6, 4.5, 1.15, "nsF5 伴随式矩阵编码\n二元汉明码[2^p−1,k,3] · 湿纸去收缩", fc="#fce4ec", ec=C["red"])
box(5.1, 1.6, 4.5, 1.15, "SHA-256 图像哈希键控\n确定性 splitmix64 置换", fc="#f3e5f5", ec=C["purple"])
# 层4 加速
box(0.9, 0.25, 3.4, 1.05, "C++ 加速\nfsfeatures.dll · nsf5embed.dll", fc="#e0f7fa", ec=C["teal"])
box(5.7, 0.25, 3.4, 1.05, "GPU 并行特征\ntorch 批量 (RTX 4060)", fc="#e0f7fa", ec=C["teal"])
arrow(2.6, 5.55, 2.6, 5.4); arrow(7.4, 5.55, 7.4, 5.4)
arrow(2.6, 4.3, 2.6, 4.28); arrow(2.6, 4.1, 2.6, 4.1)
arrow(1.4, 3.05, 2.55, 2.78); arrow(7.4, 3.05, 7.4, 2.78)
arrow(2.6, 1.55, 2.6, 1.32); arrow(2.6, 0.95, 2.6, 1.28)
ax.set_title("系统总体架构（模块化分层）", fontsize=11)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "arch.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "arch.svg")); plt.close(fig)
print("(d) arch 完成")

# ---------------- (e) 伴随式查询示意 ----------------
import matrix_demo as MD
p = 3; x = np.array([1, 0, 1, 0, 0, 1, 0], dtype=np.uint8); m = "110"
r = MD.demo_step(p, x, m)
n = r["n"]; cell = 0.9
fig, ax = plt.subplots(figsize=(8.0, 3.4))
ax.set_xlim(-0.5, n*cell + 0.5); ax.set_ylim(-1.2, 2.4); ax.axis("off")
for i in range(n):
    cx = i*cell
    high = (i == r["col"])
    fc = C["amber"] if high else (C["green"] if r["x"][i] else "#dfdfdf")
    ax.add_patch(plt.Rectangle((cx, 0.6), cell, cell*0.9, facecolor=fc, edgecolor=(C["red"] if high else "#bbb"), lw=(3 if high else 1)))
    ax.text(cx + cell/2, 1.05, f"{r['x'][i]}", ha="center", va="center", fontsize=15)
    ax.text(cx + cell/2, 0.5, f"{i+1}", ha="center", fontsize=8, color=C["gray"])
ax.text(0, 2.2, f"块 LSB         syndrome s = {r['s_bin']} ({r['s_val']})", fontsize=11)
ax.text(0, 1.85, f"目标          m   = {r['m_bin']} ({r['m_val']})", fontsize=11, color=C["blue"])
ax.text(0, -0.35, f"差值 d = s⊕m = {r['d_bin']}  ⇒  校验矩阵 H 第 {r['flip_label']} 列\n⇒ 翻转该系数 {r['flip_from']}→{r['flip_to']} 后  H·x = m  ✓", fontsize=11, color=C["red"])
ax.set_title("nsF5 伴随式矩阵编码：一次只改 1 个系数 (p=3, 高亮格)", fontsize=11)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "hamming.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "hamming.svg")); plt.close(fig)
print(f"(e) hamming 完成  d={r['d_bin']} col={r['col']+1}")

print("\n全部图已写出至 experiments/figs/")
