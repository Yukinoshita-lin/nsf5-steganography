"""
experiments/density_grid.py — 密度网格扫描: d ∈ {0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00}

目标: 在 7 档密度上, 用 53d LGB 模型训练并报告 OOF AUC, 绘制密度-AUC 曲线.

数据: 已有 dataset_campus_v2.csv (含 nsF5/matrix/lsb 的 12 档变体) + 7 个新增 density 档.
      若缺失, 先调用 src/make_dataset.py 在校园照片上以 7 档密度生成新数据集.

输出: experiments/data/density_grid.csv
      experiments/figs/density_grid.png
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
sys.path.insert(0, SRC)

DENSITIES = [0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00]
LGB_PARAMS = dict(
    objective="binary", metric="auc",
    learning_rate=0.03, num_leaves=31, n_estimators=800,
    min_child_samples=10, feature_fraction=0.9, bagging_fraction=0.9,
    bagging_freq=5, verbose=-1,
)


def load_features():
    """加载 53d 特征 (B11 + P20 + LP20 + T2)."""
    csv_path = os.path.join(PROJ, "data", "dataset_campus_v2_jpeg.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(PROJ, "data", "dataset_campus_v2.csv")
    df = pd.read_csv(csv_path)
    feats = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
             "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
             "median_prefix_p", "chi2_stat"] + \
            [f"prefix_p{i+1}" for i in range(20)] + \
            [f"lsb_prefix_p{i+1}" for i in range(20)] + \
            ["texture_noise", "est_rate"]
    feats = [c for c in feats if c in df.columns]
    return df, feats


def train_and_eval_one_density(target_density: float, df: pd.DataFrame, feats: list):
    """对目标密度, 训练 53d LGB, 报告 OOF AUC."""
    y = df["label"].values.astype(np.int64)
    groups = df["photo_id"].values
    X = df[feats].values.astype(np.float64)
    # 用全部样本, 不限制密度 (此 CSV 已按密度分档, 我们用全部做 "整体" AUC)
    gkf = GroupKFold(n_splits=5)
    oof = np.full(len(y), np.nan)
    for tr, va in gkf.split(X, y, groups):
        m = lgb.LGBMClassifier(**LGB_PARAMS, random_state=0)
        m.fit(X[tr], y[tr])
        oof[va] = m.predict_proba(X[va])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return None
    auc = float(roc_auc_score(y[mask], oof[mask]))
    return auc, oof, y, groups


def evaluate_density_curve():
    """对每个 (method, density) 变体, 报告检出率 vs 整体 AUC."""
    df, feats = load_features()
    print(f"加载 {len(df)} 样本, 特征 {len(feats)} 维")
    # 整体 OOF AUC
    res = train_and_eval_one_density(1.0, df, feats)
    if res is None:
        print("  训练失败")
        return
    auc, oof, y, groups = res
    print(f"  整体 OOF AUC = {auc:.4f}")

    # 按密度分档统计
    rows = []
    if "density" not in df.columns:
        print("  缺 density 列, 退出")
        return
    # 为每个 (method, p, density) 组合, 在 OOF 概率上取 Youden 阈值
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y, oof)
    j = tpr - fpr
    youden = float(th[j.argmax()]) if len(j) else 0.5

    for (meth, p, dens), g in df.groupby(["method", "p", "density"]):
        if pd.isna(meth):
            continue
        # 取属于该变体的 OOF 概率
        idx = g.index
        p_oof = oof[idx]
        lbl = y[idx]
        det = float((p_oof >= youden).mean())
        clean = (lbl == 0)
        if clean.any():
            fp = float((p_oof[clean] >= youden).mean())
        else:
            fp = 0.0
        rows.append({
            "method": meth, "p": int(p) if pd.notna(p) else 0,
            "density": float(dens), "n": int(len(idx)),
            "detection_rate": round(det, 4),
            "false_positive_rate": round(fp, 4),
        })
    out = pd.DataFrame(rows)
    out_path = os.path.join(PROJ, "experiments", "data", "density_grid.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"\n已写出: {out_path}")
    print(out.sort_values(["method", "density"]).to_string(index=False))

    # 绘图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for meth, sub in out.groupby("method"):
            sub = sub.sort_values("density")
            for p_val, sub2 in sub.groupby("p"):
                ax.plot(sub2["density"], sub2["detection_rate"], "o-",
                        label=f"{meth} p={p_val}", linewidth=1.5, markersize=5)
        ax.set_xlabel("Embedding density (payload / capacity)")
        ax.set_ylabel("Detection rate (Youden threshold)")
        ax.set_title("Detection rate vs embedding density (53d LGB)")
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=8, ncol=2)
        fig.tight_layout()
        fig_path = os.path.join(PROJ, "experiments", "figs", "density_grid.png")
        os.makedirs(os.path.dirname(fig_path), exist_ok=True)
        fig.savefig(fig_path, dpi=150, bbox_inches="tight")
        print(f"图: {fig_path}")
    except Exception as e:
        print(f"绘图失败: {e}")


if __name__ == "__main__":
    evaluate_density_curve()
