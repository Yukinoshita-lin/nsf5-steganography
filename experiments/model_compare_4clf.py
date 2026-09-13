"""
experiments/model_compare_4clf.py — 4 分类器 × 5 特征子集 = 20 组对比实验。

分类器:
  - LR (Logistic Regression with StandardScaler)
  - XGB (XGBoost tuned)
  - LGB (LightGBM tuned)
  - RF (Random Forest)

特征子集 (复用 ablation_5stage 的 5 阶段):
  - B11, B11+P20, B11+P20+LP20, B11+P20+LP20+T2 (53d), FULL143

每组用 5 折 GroupKFold + 3 seed, 报告 OOF AUC.
输出: experiments/data/model_compare_4clf.csv
"""
from __future__ import annotations
import os, sys, time
import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
sys.path.insert(0, SRC)

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
import lightgbm as lgb
from xgboost import XGBClassifier


BASE_11 = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
           "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
           "median_prefix_p", "chi2_stat"]
PREFIX20 = [f"prefix_p{i+1}" for i in range(20)]
L20 = [f"lsb_prefix_p{i+1}" for i in range(20)]
SRM_STAT = (
    [f"srm_mu_c{c}" for c in range(30)] +
    [f"srm_absmean_c{c}" for c in range(30)] +
    [f"srm_std_c{c}" for c in range(30)]
)
T2 = ["texture_noise", "est_rate"]

STAGES = {
    "B11": BASE_11,
    "B11+P20": BASE_11 + PREFIX20,
    "B11+P20+LP20": BASE_11 + PREFIX20 + L20,
    "53d_Interpretable": BASE_11 + PREFIX20 + L20 + T2,
    "143d_Full": BASE_11 + SRM_STAT + PREFIX20 + T2 + L20,
}

LGB_PARAMS = dict(
    objective="binary", metric="auc",
    learning_rate=0.03, num_leaves=31, n_estimators=800,
    min_child_samples=10, feature_fraction=0.9, bagging_fraction=0.9,
    bagging_freq=5, verbose=-1,
)
XGB_PARAMS = dict(
    n_estimators=500, learning_rate=0.05, max_depth=5,
    subsample=0.9, colsample_bytree=0.8, eval_metric="logloss",
    n_jobs=-1,
)


def make_lr(): return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
def make_xgb(seed=0): return XGBClassifier(**XGB_PARAMS, random_state=seed)
def make_lgb(seed=0):
    p = dict(LGB_PARAMS); p["random_state"] = seed
    return lgb.LGBMClassifier(**p)
def make_rf(seed=0): return RandomForestClassifier(n_estimators=500, max_depth=None, n_jobs=-1, random_state=seed)

MODELS = {"LR": make_lr, "XGB": make_xgb, "LGB": make_lgb, "RF": make_rf}


def main():
    csv_path = os.path.join(PROJ, "data", "dataset_campus_v2_jpeg.csv")
    df = pd.read_csv(csv_path)
    y = df["label"].values.astype(np.int64)
    groups = df["photo_id"].values
    print(f"加载 {len(df)} 样本, clean={(y==0).sum()}, stego={(y==1).sum()}")

    seeds = [0, 1, 2]
    n_splits = 5
    rows = []
    for stage_name, feats in STAGES.items():
        avail = [f for f in feats if f in df.columns]
        X = df[avail].values.astype(np.float64)
        for mdl_name, mdl_fn in MODELS.items():
            t0 = time.time()
            for seed in seeds:
                gkf = GroupKFold(n_splits=n_splits)
                oof = np.full(len(y), np.nan)
                for tr, va in gkf.split(X, y, groups):
                    clf = mdl_fn(seed) if mdl_name in ("XGB", "LGB", "RF") else mdl_fn()
                    clf.fit(X[tr], y[tr])
                    oof[va] = clf.predict_proba(X[va])[:, 1]
                mask = ~np.isnan(oof)
                a = float(roc_auc_score(y[mask], oof[mask]))
                rows.append({
                    "model": mdl_name, "stage": stage_name, "n_feat": len(avail),
                    "seed": seed, "oof_auc": round(a, 4),
                    "elapsed_s": round(time.time() - t0, 1),
                })
            print(f"  [{mdl_name:<3} {stage_name:<22}] {len(avail):3d}维 done")
    df_out = pd.DataFrame(rows)
    out_path = os.path.join(PROJ, "experiments", "data", "model_compare_4clf.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_out.to_csv(out_path, index=False)
    # 汇总
    summary = df_out.groupby(["model", "stage"]).agg(
        auc_mean=("oof_auc", "mean"),
        auc_std=("oof_auc", "std"),
    ).reset_index().round(4)
    summary_path = os.path.join(PROJ, "experiments", "data", "model_compare_4clf_summary.csv")
    summary.to_csv(summary_path, index=False)
    print(f"\n已写出: {out_path}")
    print(f"已写出: {summary_path}")
    print(f"\n=== 4 模型 × 5 特征汇总 (OOF AUC mean ± std) ===")
    pivot = summary.pivot(index="model", columns="stage", values="auc_mean")
    print(pivot.to_string())


if __name__ == "__main__":
    main()
