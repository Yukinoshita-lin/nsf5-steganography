"""
experiments/ablation_5stage.py — 5 阶梯式消融实验。

5 个特征子集 (累积式消融):
  1. B11    (11d)   = BASE 11
  2. B11+P20 (31d)  = BASE 11 + PREFIX 20
  3. B11+P20+LP20 (51d) = BASE 11 + PREFIX 20 + LSB PREFIX 20
  4. B11+P20+LP20+T2 (53d) = BASE 11 + PREFIX 20 + LSB PREFIX 20 + TEXTURE 2
  5. +SRM90 (143d)  = 完整 143 维

每组用 5 折 GroupKFold + 8 独立 seed 取平均, 报告 OOF AUC.
输出: experiments/data/ablation_5stage.csv
      experiments/data/ablation_5stage_detailed.csv  (每折详细数据)
"""
from __future__ import annotations
import os, sys, time, json
import numpy as np
import pandas as pd
from joblib import dump, load

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, os.path.join(PROJ, "gpu"))

from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
import lightgbm as lgb


# 特征子集定义
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
    "1_B11": BASE_11,
    "2_B11+P20": BASE_11 + PREFIX20,
    "3_B11+P20+LP20": BASE_11 + PREFIX20 + L20,
    "4_B11+P20+LP20+T2": BASE_11 + PREFIX20 + L20 + T2,  # = 53d 精简版
    "5_FULL143": BASE_11 + SRM_STAT + PREFIX20 + T2 + L20,
}

# 默认配置: LightGBM tuned
LGB_PARAMS = dict(
    objective="binary",
    metric="auc",
    learning_rate=0.03,
    num_leaves=31,
    n_estimators=800,
    min_child_samples=10,
    feature_fraction=0.9,
    bagging_fraction=0.9,
    bagging_freq=5,
    verbose=-1,
)


def main():
    csv_path = os.path.join(PROJ, "data", "dataset_campus_v2_jpeg.csv")
    if not os.path.exists(csv_path):
        sys.exit(f"未找到 {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"加载 {len(df)} 样本, clean={(df['label']==0).sum()}, stego={(df['label']==1).sum()}")

    # 准备分组 (photo_id)
    if "photo_id" not in df.columns:
        sys.exit("数据集缺少 photo_id 列")
    y = df["label"].values.astype(np.int64)
    groups = df["photo_id"].values

    # 8 个不同 seed 做 5 折 GroupKFold
    seeds = [0, 1, 2, 3, 4, 5, 6, 7]
    n_splits = 5

    out_dir = os.path.join(PROJ, "experiments", "data")
    os.makedirs(out_dir, exist_ok=True)

    summary_rows = []
    detail_rows = []
    for stage_name, feats in STAGES.items():
        # 校验特征可用
        avail = [f for f in feats if f in df.columns]
        if len(avail) != len(feats):
            print(f"  [{stage_name}] 警告: 缺失特征 {set(feats) - set(avail)}, 实际 {len(avail)}/{len(feats)}")
        X = df[avail].values.astype(np.float64)
        aucs = []
        t0 = time.time()
        for seed in seeds:
            gkf = GroupKFold(n_splits=n_splits)
            oof = np.full(len(y), np.nan)
            for tr, va in gkf.split(X, y, groups):
                p = dict(LGB_PARAMS)
                p["random_state"] = seed
                model = lgb.LGBMClassifier(**p)
                model.fit(X[tr], y[tr])
                oof[va] = model.predict_proba(X[va])[:, 1]
            mask = ~np.isnan(oof)
            if mask.sum() > 0 and len(np.unique(y[mask])) == 2:
                a = float(roc_auc_score(y[mask], oof[mask]))
                aucs.append(a)
                detail_rows.append({
                    "stage": stage_name, "n_feat": len(avail),
                    "seed": seed, "n_splits": n_splits,
                    "oof_auc": a, "n_samples": int(mask.sum()),
                    "elapsed_s": round(time.time() - t0, 1),
                })
        if aucs:
            mean = float(np.mean(aucs))
            std = float(np.std(aucs))
            summary_rows.append({
                "stage": stage_name, "n_feat": len(avail),
                "auc_mean": round(mean, 4), "auc_std": round(std, 4),
                "auc_min": round(float(min(aucs)), 4),
                "auc_max": round(float(max(aucs)), 4),
                "n_seeds": len(aucs),
            })
            print(f"  [{stage_name:<25}] {len(avail):3d}维  AUC = {mean:.4f} ± {std:.4f}  (n={len(aucs)})")
        else:
            print(f"  [{stage_name}] 无有效数据")

    # 写出
    df_summary = pd.DataFrame(summary_rows)
    df_detail = pd.DataFrame(detail_rows)
    p1 = os.path.join(out_dir, "ablation_5stage.csv")
    p2 = os.path.join(out_dir, "ablation_5stage_detailed.csv")
    df_summary.to_csv(p1, index=False)
    df_detail.to_csv(p2, index=False)
    print(f"\n已写出: {p1}")
    print(f"已写出: {p2}")
    print(f"\n=== 消融 5 阶段汇总 ===")
    print(df_summary.to_string(index=False))


if __name__ == "__main__":
    main()
