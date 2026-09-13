"""
8-split 对比: 143d vs 53d LGB, GroupKFold 8 splits
产出: experiments/data/8split_comparison.csv
"""
import os, sys, numpy as np, pandas as pd
from joblib import load
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
import lightgbm as lgb

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))
DATA_DIR = os.path.join(PROJ, "data")
EXP_DATA = os.path.join(PROJ, "experiments", "data")
os.makedirs(EXP_DATA, exist_ok=True)

CSV = os.path.join(DATA_DIR, "dataset_campus_v2_jpeg.csv")
df = pd.read_csv(CSV)
META_COLS = {"label", "photo_id", "variant", "method", "p", "density", "changed_frac"}
feats = [c for c in df.columns if c not in META_COLS]
X = df[feats].values.astype(np.float64)
y = df["label"].values.astype(np.int64)
groups = df["photo_id"].values
N = len(feats)

# 53d feature indices
BASE_11 = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
           "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
           "median_prefix_p", "chi2_stat"]
PREFIX20 = [f"prefix_p{i+1}" for i in range(20)]
L20 = [f"lsb_prefix_p{i+1}" for i in range(20)]
EXTRA = ["texture_noise", "est_rate"]
FEATS_53 = BASE_11 + PREFIX20 + L20 + EXTRA
idx53 = [feats.index(f) for f in FEATS_53]
X53 = X[:, idx53]

LGB_PARAMS = {
    "num_leaves": 31, "n_estimators": 800, "learning_rate": 0.03,
    "min_child_samples": 10, "random_state": 0, "n_jobs": -1,
    "verbose": -1,
}

gkf = GroupKFold(n_splits=8)
oof_143 = np.full(len(y), np.nan)
oof_53 = np.full(len(y), np.nan)
results = []

for split_i, (tr, va) in enumerate(gkf.split(X, y, groups)):
    m143 = lgb.LGBMClassifier(**LGB_PARAMS)
    m143.fit(X[tr], y[tr])
    p143 = m143.predict_proba(X[va])[:, 1]
    oof_143[va] = p143

    m53 = lgb.LGBMClassifier(**LGB_PARAMS)
    m53.fit(X53[tr], y[tr])
    p53 = m53.predict_proba(X53[va])[:, 1]
    oof_53[va] = p53

    auc143 = roc_auc_score(y[va], p143)
    auc53 = roc_auc_score(y[va], p53)
    results.append({
        "split": split_i, "metric": "overall_auc",
        "auc_143d": auc143, "auc_53d": auc53,
    })
    print(f"  Split {split_i}: 143d AUC={auc143:.4f}  53d AUC={auc53:.4f}")

# Aggregate
rf = pd.DataFrame(results)
agg = rf.groupby("metric").agg(
    mean_143d=("auc_143d", "mean"), std_143d=("auc_143d", "std"),
    mean_53d=("auc_53d", "mean"), std_53d=("auc_53d", "std"),
    n_wins_143d=("auc_143d", lambda x: (x > rf.loc[rf["metric"]==rf.loc[x.index,"metric"].iloc[0],"auc_53d"].values).sum()),
    n_wins_53d=("auc_53d", lambda x: (x > rf.loc[rf["metric"]==rf.loc[x.index,"metric"].iloc[0],"auc_143d"].values).sum()),
).reset_index()
agg.columns = ["metric", "mean_143d", "std_143d", "mean_53d", "std_53d", "wins_143d", "wins_53d"]

# Per-density detection using pooled OOF
variants = df["variant"].unique()
density_rows = []
for v in variants:
    mask = df["variant"] == v
    gmask = groups[mask]
    # Only compute if both classes present
    if len(np.unique(y[mask])) == 2:
        auc143 = roc_auc_score(y[mask], oof_143[mask])
        auc53 = roc_auc_score(y[mask], oof_53[mask])
    else:
        auc143 = auc53 = np.nan
    # Also compute detection rate at Youden threshold
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y, oof_143)
    youden = th[np.argmax(tpr - fpr)]
    det143 = (oof_143[mask] > youden).mean()
    fpr, tpr, th = roc_curve(y, oof_53)
    youden53 = th[np.argmax(tpr - fpr)]
    det53 = (oof_53[mask] > youden53).mean()
    density_rows.append({
        "variant": v, "n": mask.sum(),
        "auc_143d": auc143, "auc_53d": auc53,
        "det_143d_youden": det143, "det_53d_youden": det53,
    })

det_df = pd.DataFrame(density_rows)
det_df.to_csv(os.path.join(EXP_DATA, "density_detection.csv"), index=False, float_format="%.4f")

agg.to_csv(os.path.join(EXP_DATA, "8split_comparison.csv"), index=False, float_format="%.4f")
print(f"\n=== 8-split Aggregated ===")
print(agg.to_string(index=False))

# Raw split data
rf.to_csv(os.path.join(EXP_DATA, "8split_raw.csv"), index=False, float_format="%.4f")
print(f"\nSaved to {EXP_DATA}")