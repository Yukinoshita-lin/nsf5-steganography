"""
第 5 章 — 特征可解释性分析图表生成
产出: experiments/figs/*.png (300dpi, 适合论文排版)
"""
import os, sys, numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP_DIR = os.path.join(PROJ, "experiments")
FIGS = os.path.join(EXP_DIR, "figs")
DATA = os.path.join(EXP_DIR, "data")
os.makedirs(FIGS, exist_ok=True)

# ---- 中文字体 ----
for fname in ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC"]:
    try:
        matplotlib.font_manager.findfont(fname, fallback_to_default=False)
        plt.rcParams["font.family"] = fname
        plt.rcParams["axes.unicode_minus"] = False
        break
    except Exception:
        continue
else:
    # fallback: use sans-serif with SimHei as first choice
    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

# ---- Load data ----
gain = pd.read_csv(os.path.join(DATA, "gain_importance.csv"))
sf = pd.read_csv(os.path.join(DATA, "single_feat_auc.csv"))
groups = pd.read_csv(os.path.join(DATA, "feature_groups.csv"))
srm_corr = pd.read_csv(os.path.join(DATA, "srm_corr.csv"), index_col=0)
split8 = pd.read_csv(os.path.join(DATA, "8split_raw.csv"))
det = pd.read_csv(os.path.join(DATA, "density_detection.csv"))

# Group colors
GRP_COLORS = {
    "BASE (v1 11d)": "#E74C3C",
    "SRM mu (30)": "#3498DB",
    "SRM absmean (30)": "#2980B9",
    "SRM std (30)": "#1ABC9C",
    "PREFIX 20": "#F39C12",
    "LSB PREFIX 20": "#9B59B6",
    "TEXTURE/EST": "#95A5A6",
}

# Feature group mapping
def get_group(feat):
    if feat in ["Rm","Sm","Rn","Sn","RS_Gr","RS_Gn","chi2_pvalue","diff_entropy",
                "lsb_diff_entropy","median_prefix_p","chi2_stat"]:
        return "BASE (v1 11d)"
    if feat.startswith("srm_mu_"): return "SRM mu (30)"
    if feat.startswith("srm_absmean_"): return "SRM absmean (30)"
    if feat.startswith("srm_std_"): return "SRM std (30)"
    if feat.startswith("prefix_p"): return "PREFIX 20"
    if feat.startswith("lsb_prefix_p"): return "LSB PREFIX 20"
    return "TEXTURE/EST"

# =====================================================================
# Fig 1: Top 20 Feature Gain (horizontal bar)
# =====================================================================
fig, ax = plt.subplots(figsize=(8, 5.5))
top20 = gain.head(20)
top20["group"] = top20["feature"].apply(get_group)
colors = [GRP_COLORS[g] for g in top20["group"]]
bars = ax.barh(range(len(top20)), top20["gain_pct"], color=colors, edgecolor="white", height=0.7)
ax.set_yticks(range(len(top20)))
ax.set_yticklabels(top20["feature"], fontsize=9)
ax.set_xlabel("Gain 占比 (%)", fontsize=10)
ax.set_title("Top 20 特征贡献度 (LGB Gain)", fontsize=12, fontweight="bold")
ax.invert_yaxis()
# Add value labels
for i, (v, g) in enumerate(zip(top20["gain_pct"], top20["gain_cum"])):
    ax.text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=8)
# Legend
from matplotlib.patches import Patch
legend_handles = [Patch(facecolor=c, label=g) for g, c in GRP_COLORS.items()
                  if g in top20["group"].values]
ax.legend(handles=legend_handles, fontsize=8, loc="lower right")
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_1_top20_gain.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_1_top20_gain.png")

# =====================================================================
# Fig 2: Feature group contribution (donut chart)
# =====================================================================
fig, ax = plt.subplots(figsize=(6, 6))
non_zero = groups[groups["gain_pct"] > 0.1]
labels = non_zero["group"].tolist()
vals = non_zero["gain_pct"].tolist()
colors_donut = [GRP_COLORS[g] for g in labels]
wedges, texts, autotexts = ax.pie(
    vals, labels=labels, autopct="%1.1f%%",
    colors=colors_donut, startangle=90, pctdistance=0.78,
    wedgeprops=dict(width=0.4, edgecolor="w", linewidth=2),
    textprops=dict(fontsize=9),
)
ax.set_title("特征组 Gain 贡献占比", fontsize=12, fontweight="bold")
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_2_group_donut.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_2_group_donut.png")

# =====================================================================
# Fig 3: Single-feature AUC scatter plot
# =====================================================================
fig, ax = plt.subplots(figsize=(10, 4.5))
sf["group"] = sf["feature"].apply(get_group)
x = np.arange(len(sf))
for g in sf["group"].unique():
    mask = sf["group"] == g
    ax.scatter(x[mask], sf.loc[mask, "single_auc_mean"], c=GRP_COLORS[g],
               label=g, s=15, alpha=0.8, edgecolors="none")
ax.axhline(y=0.5, color="gray", linestyle="--", linewidth=0.8, alpha=0.6)
ax.axhline(y=0.6, color="red", linestyle=":", linewidth=0.8, alpha=0.4)
ax.set_xlabel("特征索引 (按单特征 AUC 降序)", fontsize=10)
ax.set_ylabel("单特征 AUC", fontsize=10)
ax.set_title("143 维特征的单特征 AUC 分布", fontsize=12, fontweight="bold")
ax.legend(fontsize=8, loc="lower left", ncol=2)
ax.set_ylim(0.45, 0.70)
ax.text(0.98, 0.52, "随机基线 (AUC=0.5)", transform=ax.transAxes, fontsize=8, ha="right", color="gray")
ax.text(0.98, 0.62, "强信号 (AUC>0.6)", transform=ax.transAxes, fontsize=8, ha="right", color="red")
# Add count annotations
n_strong = (sf["single_auc_mean"] > 0.6).sum()
n_weak = (sf["single_auc_mean"] < 0.5).sum()
ax.text(0.02, 0.95, f"AUC>0.6: {n_strong} 个", transform=ax.transAxes, fontsize=9, color="red", va="top")
ax.text(0.02, 0.88, f"AUC<0.5: {n_weak} 个", transform=ax.transAxes, fontsize=9, color="gray", va="top")
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_3_single_auc_scatter.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_3_single_auc_scatter.png")

# =====================================================================
# Fig 4: SRM 30 kernel correlation heatmap
# =====================================================================
fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(srm_corr.values, cmap="RdYlBu_r", vmin=0.9, vmax=1.0, aspect="auto")
ax.set_xticks(range(30))
ax.set_yticks(range(30))
ax.set_xticklabels([f"c{i}" for i in range(30)], fontsize=6, rotation=90)
ax.set_yticklabels([f"c{i}" for i in range(30)], fontsize=6)
ax.set_title("SRM 30 核相关系数矩阵", fontsize=12, fontweight="bold")
ax.set_xlabel("SRM 核索引", fontsize=9)
ax.set_ylabel("SRM 核索引", fontsize=9)
cbar = fig.colorbar(im, ax=ax, shrink=0.8)
cbar.set_label("Pearson r", fontsize=9)
# Add annotation
corr_vals = srm_corr.values[np.triu_indices(30, k=1)]
ax.text(0.98, 0.02, f"平均 r = {corr_vals.mean():.4f}", transform=ax.transAxes,
        fontsize=10, ha="right", va="bottom", color="white",
        bbox=dict(facecolor="black", alpha=0.5, pad=3))
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_4_srm_heatmap.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_4_srm_heatmap.png")

# =====================================================================
# Fig 5: 8-split AUC comparison (143d vs 53d)
# =====================================================================
fig, ax = plt.subplots(figsize=(8, 4.5))
split_overall = split8[split8["metric"] == "overall_auc"].copy()
x = np.arange(8)
w = 0.35
ax.bar(x - w/2, split_overall["auc_143d"], w, label="143d 完整版", color="#E74C3C", alpha=0.85)
ax.bar(x + w/2, split_overall["auc_53d"], w, label="53d 精简版", color="#9B59B6", alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels([f"Split {i}" for i in range(8)])
ax.set_ylabel("AUC", fontsize=10)
ax.set_title("8-split 交叉验证 AUC 对比 (143d vs 53d)", fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
ax.set_ylim(0.94, 1.01)
# Add mean lines
mean_143 = split_overall["auc_143d"].mean()
mean_53 = split_overall["auc_53d"].mean()
ax.axhline(y=mean_143, color="#E74C3C", linestyle="--", linewidth=0.8, alpha=0.6)
ax.axhline(y=mean_53, color="#9B59B6", linestyle="--", linewidth=0.8, alpha=0.6)
ax.text(7.2, mean_143, f"143d μ={mean_143:.4f}", color="#E74C3C", fontsize=8, va="bottom")
ax.text(7.2, mean_53, f"53d μ={mean_53:.4f}", color="#9B59B6", fontsize=8, va="top")
# Mark winner
for i, (a, b) in enumerate(zip(split_overall["auc_143d"], split_overall["auc_53d"])):
    if b > a:
        ax.text(i + w/2, b + 0.003, "★", fontsize=10, color="#9B59B6", ha="center")
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_5_8split_compare.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_5_8split_compare.png")

# =====================================================================
# Fig 6: Density-wise detection rate comparison
# =====================================================================
fig, ax = plt.subplots(figsize=(10, 5.5))
# Variant labels
variant_labels = {
    "clean": "clean", "clean_jpeg": "clean(JPEG)",
    "v0": "nsF5 p3 d0.25", "v1": "nsF5 p3 d0.40", "v2": "nsF5 p3 d0.55",
    "v3": "nsF5 p2 d0.35", "v4": "nsF5 p2 d0.85",
    "v5": "matrix p3 d0.50", "v6": "matrix p2 d0.80",
    "v7": "lsb d0.50", "v8": "matrix p3 d0.40", "v9": "matrix p3 d0.60",
    "v10": "lsb d0.30", "v11": "lsb d0.70",
}
# Only stego variants
stego_det = det[~det["variant"].isin(["clean", "clean_jpeg"])].copy()
stego_det["label"] = stego_det["variant"].map(variant_labels)
stego_det = stego_det.sort_values("det_143d_youden")
x = np.arange(len(stego_det))
w = 0.35
ax.bar(x - w/2, stego_det["det_143d_youden"] * 100, w, label="143d 完整版", color="#E74C3C", alpha=0.85)
ax.bar(x + w/2, stego_det["det_53d_youden"] * 100, w, label="53d 精简版", color="#9B59B6", alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(stego_det["label"], fontsize=8, rotation=45, ha="right")
ax.set_ylabel("检出率 (%)", fontsize=10)
ax.set_title("各密度变体 Youden 阈值检出率对比", fontsize=12, fontweight="bold")
ax.legend(fontsize=9)
ax.set_ylim(70, 102)
ax.axhline(y=100, color="gray", linestyle=":", linewidth=0.5)
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_6_density_detection.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_6_density_detection.png")

# =====================================================================
# Fig 7: Cumulative gain curve
# =====================================================================
fig, ax1 = plt.subplots(figsize=(8, 4.5))
x = np.arange(1, len(gain) + 1)
ax1.plot(x, gain["gain_cum"], color="#2C3E50", linewidth=2)
ax1.axhline(y=50, color="red", linestyle="--", linewidth=0.8, alpha=0.5)
ax1.axhline(y=80, color="orange", linestyle="--", linewidth=0.8, alpha=0.5)
ax1.axhline(y=90, color="green", linestyle="--", linewidth=0.8, alpha=0.5)
# Find how many features for 50%, 80%, 90%
n50 = (gain["gain_cum"] <= 50).sum() + 1
n80 = (gain["gain_cum"] <= 80).sum() + 1
n90 = (gain["gain_cum"] <= 90).sum() + 1
ax1.scatter([n50, n80, n90], [50, 80, 90], color=["red", "orange", "green"], zorder=5, s=40)
ax1.annotate(f"{n50} 个特征 → 50%", xy=(n50, 50), xytext=(n50+20, 45),
             fontsize=9, color="red", arrowprops=dict(arrowstyle="->", color="red"))
ax1.annotate(f"{n80} 个特征 → 80%", xy=(n80, 80), xytext=(n80+20, 75),
             fontsize=9, color="orange", arrowprops=dict(arrowstyle="->", color="orange"))
ax1.annotate(f"{n90} 个特征 → 90%", xy=(n90, 90), xytext=(n90+20, 85),
             fontsize=9, color="green", arrowprops=dict(arrowstyle="->", color="green"))
ax1.set_xlabel("特征数 (按 Gain 降序)", fontsize=10)
ax1.set_ylabel("累计 Gain 占比 (%)", fontsize=10)
ax1.set_title("累计 Gain 占比曲线", fontsize=12, fontweight="bold")
ax1.set_xlim(0, 145)
ax1.set_ylim(0, 105)
# Highlight 53d and 143d
ax1.axvline(x=53, color="#9B59B6", linestyle=":", linewidth=1, alpha=0.7)
ax1.axvline(x=143, color="#E74C3C", linestyle=":", linewidth=1, alpha=0.7)
ax1.text(55, 5, "53d 精简版", fontsize=8, color="#9B59B6")
ax1.text(145, 5, "143d 完整版", fontsize=8, color="#E74C3C", ha="right")
plt.tight_layout()
fig.savefig(os.path.join(FIGS, "fig5_7_cumulative_gain.png"), dpi=300, bbox_inches="tight")
plt.close()
print("  [OK] fig5_7_cumulative_gain.png")

# =====================================================================
# Summary
# =====================================================================
print(f"\n=== 所有图表已生成至 {FIGS} ===")
for f in sorted(os.listdir(FIGS)):
    if f.endswith(".png"):
        sz = os.path.getsize(os.path.join(FIGS, f))
        print(f"  {f:30s}  {sz//1024:4d} KB")