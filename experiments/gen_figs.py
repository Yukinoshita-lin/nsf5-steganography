"""
experiments/gen_figs.py — 一键生成论文所有图.

读取:
  - experiments/data/ablation_5stage.csv
  - experiments/data/model_compare_4clf_summary.csv
  - experiments/data/density_grid.csv
  - experiments/data/sota_compare.csv (+ sota_cnn_results.csv)
  - experiments/data/ood_jpeg_eval.csv (从 data/ood_jpeg_test/eval.csv 复制)
  - experiments/data/single_feat_auc.csv
  - experiments/data/gain_importance_53d.csv
  - experiments/data/srm_corr.csv
  - experiments/data/8split_raw.csv

输出:
  experiments/figs/fig_ablation.png
  experiments/figs/fig_model_heatmap.png
  experiments/figs/fig_density.png  (重写)
  experiments/figs/fig_sota.png
  experiments/figs/fig_roc.png
  experiments/figs/fig_ood_jpeg.png
  experiments/figs/fig_top20_gain.png
  experiments/figs/fig_srm_heatmap.png
  experiments/figs/fig_8split.png
  experiments/figs/fig_single_auc.png
"""
from __future__ import annotations
import os, sys, shutil
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP_DATA = os.path.join(PROJ, "experiments", "data")
EXP_FIGS = os.path.join(PROJ, "experiments", "figs")
os.makedirs(EXP_FIGS, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def fig_ablation():
    p = os.path.join(EXP_DATA, "ablation_5stage.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    x = np.arange(len(df))
    ax.bar(x, df["auc_mean"], yerr=df["auc_std"], capsize=4, color="#4C78A8", edgecolor="black", linewidth=0.5)
    for i, (m, s) in enumerate(zip(df["auc_mean"], df["n_feat"])):
        ax.text(i, m + 0.001, f"{m:.4f}\n({s}d)", ha="center", va="bottom", fontsize=8.5)
    ax.set_xticks(x)
    ax.set_xticklabels(df["stage"], rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("5-fold OOF AUC (mean of 8 seeds)")
    ax.set_ylim(0.96, 1.00)
    ax.set_title("Ablation: feature groups on 53d vs 143d")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_ablation.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_ablation.png")


def fig_model_heatmap():
    p = os.path.join(EXP_DATA, "model_compare_4clf_summary.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p)
    pivot = df.pivot(index="model", columns="stage", values="auc_mean")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    sns.heatmap(pivot, annot=True, fmt=".4f", cmap="viridis", cbar_kws={"label": "OOF AUC"},
                linewidths=0.5, linecolor="white", vmin=0.78, vmax=1.00, ax=ax)
    ax.set_title("4 classifiers × 5 feature subsets (OOF AUC)")
    ax.set_xlabel("Feature subset")
    ax.set_ylabel("Classifier")
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_model_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_model_heatmap.png")


def fig_density():
    p = os.path.join(EXP_DATA, "density_grid.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p)
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    colors = {"lsb": "#E45756", "matrix": "#F58518", "nsF5": "#4C78A8"}
    for meth, sub in df.groupby("method"):
        for p_val, sub2 in sub.groupby("p"):
            sub2 = sub2.sort_values("density")
            ax.plot(sub2["density"], sub2["detection_rate"], "o-",
                    color=colors.get(meth, "gray"),
                    label=f"{meth} p={p_val}", linewidth=1.6, markersize=6)
    ax.set_xlabel("Embedding density (payload / capacity)")
    ax.set_ylabel("Detection rate (Youden threshold)")
    ax.set_title("Detection rate vs embedding density (53d LGB)")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_density.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_density.png")


def fig_sota():
    """SOTA 对比图。

    优先读 `sota_table.csv` (merge_sota_table.py 产出的统一长表), 它才是把
    CNN 与手工特征口径拉齐、并给 CNN 也算了置信区间的产物。旧的两文件拼接
    路径保留作回退, 但有三个已知缺陷, 仅在统一表缺失时使用:
      - CNN 行没有置信区间, 却和带 CI 的 LGB 行画在一起;
      - `set_xlim(0.5, 0.85)` 是写死的, 真实 AUC 落在 0.9 以上 (或 0.6 附近)
        时柱子会被裁到图外/看不见;
      - 不同语料的行混在一起没有标注。
    """
    p = os.path.join(EXP_DATA, "sota_table.csv")
    rows = []
    if os.path.exists(p):
        df = pd.read_csv(p)
        if "comparable_group" in df.columns:
            # 只画可比组: 另一组的语料/协议不同源, 画在一起就是误导
            dropped = int((df["comparable_group"] != "A_bossbase_npz_holdout").sum())
            df = df[df["comparable_group"] == "A_bossbase_npz_holdout"]
            if dropped:
                print(f"  [fig_sota] 略过 {dropped} 行非同源语料/协议的结果")
        for _, r in df.iterrows():
            rows.append({"model": str(r["model"]), "family": r.get("family", ""),
                         "auc": float(r["auc"]), "lo": float(r.get("auc_lo", r["auc"])),
                         "hi": float(r.get("auc_hi", r["auc"]))})
    else:
        print("  [fig_sota] 缺少 sota_table.csv, 回退到旧的两文件拼接 "
              "(无 CI、xlim 写死); 建议跑 experiments/merge_sota_table.py")
        p1 = os.path.join(EXP_DATA, "sota_compare.csv")
        p2 = os.path.join(EXP_DATA, "sota_cnn_results.csv")
        if os.path.exists(p1):
            for _, r in pd.read_csv(p1).iterrows():
                rows.append({"model": r["model"], "family": "handcrafted",
                             "auc": r["auc"], "lo": r.get("auc_lo", r["auc"]),
                             "hi": r.get("auc_hi", r["auc"])})
        if os.path.exists(p2):
            for _, r in pd.read_csv(p2).iterrows():
                if "error" in r and pd.notna(r.get("error")):
                    continue
                rows.append({"model": r["model"].upper(), "family": "cnn",
                             "auc": r["best_val_auc"], "lo": r["best_val_auc"],
                             "hi": r["best_val_auc"]})
    if not rows:
        return

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    names = [r["model"] for r in rows]
    aucs = np.array([r["auc"] for r in rows])
    los = np.array([r["lo"] for r in rows])
    his = np.array([r["hi"] for r in rows])
    errs = np.vstack([np.clip(aucs - los, 0, None), np.clip(his - aucs, 0, None)])
    palette = {"cnn": "#E45756", "handcrafted": "#4C78A8"}
    colors = [palette.get(r["family"], "#54A24B") for r in rows]

    y = np.arange(len(names))
    ax.barh(y, aucs, xerr=errs, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    # 动态 x 范围: 写死的 (0.5, 0.85) 会把 0.95 的柱子画到图外
    lo_edge = max(0.0, float(min(los.min(), aucs.min())) - 0.05)
    hi_edge = min(1.0, float(max(his.max(), aucs.max())) + 0.06)
    ax.set_xlim(lo_edge, hi_edge)
    ax.axvline(0.5, color="#888", linestyle=":", linewidth=1, zorder=0)
    ax.set_xlabel("AUC (BOSSbase 512², group-split by source photo)")
    ax.set_title("SOTA comparison: handcrafted-feature LGB vs CNN detectors")
    for i, a in enumerate(aucs):
        ax.text(a + (hi_edge - lo_edge) * 0.012, i, f"{a:.4f}", va="center", fontsize=9)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_sota.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_sota.png")


def fig_ood_jpeg():
    src = os.path.join(PROJ, "data", "ood_jpeg_test", "eval.csv")
    dst = os.path.join(EXP_DATA, "ood_jpeg_eval.csv")
    if not os.path.exists(src):
        # 这份数据的生产者随另一个项目被删除, experiments/data/ood_jpeg_eval.csv 是
        # 仅存的历史产物 —— 无法再生。这里显式说明, 免得图默默少一张没人知道。
        print("  [fig_ood_jpeg] 跳过: 源目录 data/ood_jpeg_test/ 不存在。"
              "experiments/data/ood_jpeg_eval.csv 是不可再生的历史产物, "
              "详见 experiments/PROVENANCE.md")
        return
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    df = pd.read_csv(dst).dropna(subset=["ml_prob", "threshold"])
    if df.empty: return
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6))
    ax = axes[0]
    ax.hist(df["ml_prob"], bins=30, color="#4C78A8", edgecolor="white")
    thr = float(df["threshold"].iloc[0])
    ax.axvline(thr, color="red", linestyle="--", label=f"threshold={thr:.2f}")
    ax.set_xlabel("ML probability (clean = 0)")
    ax.set_ylabel("Count")
    ax.set_title(f"OOD real JPEG clean (n={len(df)}, FP={int(df['pred_stego'].sum())})")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    fp_rate = df["pred_stego"].mean()
    n = len(df); p = fp_rate
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    halfw = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    lo, hi = max(0, center - halfw), min(1, center + halfw)
    ax.barh([0], [hi - lo], left=[lo], color="#E45756", edgecolor="black")
    ax.plot([center, center], [-0.3, 0.3], "k-", linewidth=1)
    ax.text(center, 0.45, f"{center:.4f}", ha="center", fontsize=9)
    ax.set_yticks([])
    ax.set_xlim(0, 1)
    ax.set_xlabel("False positive rate")
    ax.set_title(f"95% Wilson CI = [{lo:.4f}, {hi:.4f}]")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_ood_jpeg.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_ood_jpeg.png")


def fig_top20_gain():
    p = os.path.join(EXP_DATA, "gain_importance_53d.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p).head(20)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.barh(df["feature"][::-1], df["gain"][::-1], color="#54A24B", edgecolor="black", linewidth=0.4)
    ax.set_xlabel("LightGBM gain importance")
    ax.set_title("Top-20 features in 53d model")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_top20_gain.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_top20_gain.png")


def fig_srm_heatmap():
    p = os.path.join(EXP_DATA, "srm_corr.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p, index_col=0)
    # 只取 srm_absmean_* 子集
    cols = [c for c in df.columns if c.startswith("srm_absmean_c")]
    if not cols: return
    sub = df.loc[[c for c in df.index if c.startswith("srm_absmean_c")], cols]
    mat = sub.values.astype(float)
    fig, ax = plt.subplots(figsize=(5, 4.2))
    sns.heatmap(mat, cmap="rocket_r", center=0, vmin=-1, vmax=1, ax=ax,
                cbar_kws={"label": "Pearson r"},
                xticklabels=False, yticklabels=False, square=True)
    # 计算平均 |r|
    mask = ~np.eye(len(mat), dtype=bool)
    avg_abs = float(np.nanmean(np.abs(mat[mask])))
    ax.set_title(f"SRM absmean 30×30 corr (avg |r|={avg_abs:.3f})")
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_srm_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_srm_heatmap.png")


def fig_8split():
    p = os.path.join(EXP_DATA, "8split_raw.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    x = np.arange(len(df))
    ax.plot(x, df["auc_143d"], "o-", label="143d", color="#4C78A8", linewidth=1.5)
    ax.plot(x, df["auc_53d"], "s-", label="53d", color="#E45756", linewidth=1.5)
    ax.set_xticks(x)
    ax.set_xticklabels(df["split"], rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("AUC")
    ax.set_title("8-split AUC: 53d vs 143d")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_8split.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_8split.png")


def fig_single_auc():
    p = os.path.join(EXP_DATA, "single_feat_auc.csv")
    if not os.path.exists(p): return
    df = pd.read_csv(p)
    df = df.rename(columns={"single_auc_mean": "auc"}).sort_values("auc")
    if "auc" not in df.columns:
        return
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    df = df.sort_values("auc")
    ax.scatter(df["auc"], np.arange(len(df)), s=18, color="#4C78A8")
    ax.set_yticks(np.arange(len(df)))
    ax.set_yticklabels(df["feature"], fontsize=7)
    ax.axvline(0.5, color="gray", linestyle=":")
    ax.set_xlabel("Single-feature AUC")
    ax.set_title("Single-feature AUC ranking")
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(EXP_FIGS, "fig_single_auc.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("✓ fig_single_auc.png")


def main():
    fig_ablation(); fig_model_heatmap(); fig_density(); fig_sota()
    fig_ood_jpeg(); fig_top20_gain(); fig_srm_heatmap()
    fig_8split(); fig_single_auc()


if __name__ == "__main__":
    main()
