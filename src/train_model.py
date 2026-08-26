"""
有监督隐写分类器训练与评估 (clean=0 / stego=1)。

- 读入 data/dataset.csv (C++ 特征 + label + 照片分组)
- 预留 held-out 测试集 (按 photo_id 分组), 其上评估最终模型
- 训练集上做 5 折 GroupKFold 交叉验证选模 (杜绝同源泄漏)
- 对比 LogisticRegression / RandomForest / GradientBoosting / XGBoost
- 输出: 交叉验证指标 + 每密度层检出率 + 阈值调优结果
- 保存最佳模型 -> models/stego_classifier.joblib
"""
from __future__ import annotations
import os, sys, json
import numpy as np
import pandas as pd
from joblib import dump, load

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJ, "data", "dataset.csv")
MODEL_DIR = os.path.join(PROJ, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "stego_classifier.joblib")

FEAT_KEYS = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
             "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
             "median_prefix_p", "chi2_stat"]


def load_data(path=DATA):
    df = pd.read_csv(path)
    df = df.dropna(subset=FEAT_KEYS)
    X = df[FEAT_KEYS].values.astype(np.float64)
    y = df["label"].values.astype(np.int64)
    groups = df["photo_id"].values
    return X, y, groups, df


def youden_threshold(y_true, p):
    """Youden J 最大化选取阈值。"""
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_true, p)
    j = tpr - fpr
    if len(j) == 0:
        return 0.5
    return float(th[np.argmax(j)])


def threshold_for_fp(y_true, p, max_fp=0.10):
    """在校准集上取满足 FP<=max_fp 的最低阈值 (该约束下检测率最高)。"""
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_true, p)
    cand = [(t, f, tpr[i]) for i, (t, f) in enumerate(zip(th, fpr))
            if np.isfinite(t) and f <= max_fp and tpr[i] > 0.0]
    if not cand:
        return 0.5
    return min(c[0] for c in cand)


def cv_auc(clf, X, y, groups, seed=0):
    """5 折 GroupKFold 交叉验证, 返回各折 AUC 列表 (按照片分组防泄漏)。"""
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    gkf = GroupKFold(n_splits=5)
    aucs = []
    for tr, va in gkf.split(X, y, groups):
        clf.fit(X[tr], y[tr])
        p = clf.predict_proba(X[va])[:, 1]
        if len(np.unique(y[va])) == 2:
            aucs.append(roc_auc_score(y[va], p))
    return aucs


def main(seed=0):
    X, y, groups, df = load_data()
    print(f"样本 {len(y)} (clean={(y==0).sum()}, stego={(y==1).sum()}), 特征 {X.shape[1]}")

    # 1) 预留 held-out 测试集 (按照片分组), 其余为训练池
    from sklearn.model_selection import GroupShuffleSplit
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    tr_idx, te_idx = next(gss.split(X, y, groups))
    Xtr, ytr, gtr = X[tr_idx], y[tr_idx], groups[tr_idx]

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from xgboost import XGBClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    models = {
        "LogisticRegression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
        "RandomForest": RandomForestClassifier(n_estimators=500, n_jobs=-1, random_state=seed),
        "GradientBoosting": GradientBoostingClassifier(n_estimators=300, random_state=seed),
        "XGBoost": XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4,
                                 subsample=0.9, colsample_bytree=0.8, eval_metric="logloss",
                                 random_state=seed, n_jobs=-1),
    }

    # 2) 5 折 GroupKFold CV 选模
    print(f"\n5 折 GroupKFold 交叉验证 (训练池共 {len(tr_idx)} 样本):")
    cv = {}
    for name, clf in models.items():
        aucs = cv_auc(clf, Xtr, ytr, gtr, seed)
        cv[name] = aucs
        print(f"  {name:<22} CV-AUC={np.mean(aucs):.4f} ({', '.join(f'{a:.3f}' for a in aucs)})")
    best_name = max(cv, key=lambda k: np.mean(cv[k]))
    print(f"\nCV 最佳模型: {best_name}")

    # 3) 训练池内再切校准集选阈值 (按组分)
    gss_c = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
    tr2_idx, cal_idx = next(gss_c.split(Xtr, ytr, gtr))
    best_clf = models[best_name]
    best_clf.fit(Xtr[tr2_idx], ytr[tr2_idx])
    p_cal = best_clf.predict_proba(Xtr[cal_idx])[:, 1]
    best_thr = youden_threshold(ytr[cal_idx], p_cal)
    thr_fp = threshold_for_fp(ytr[cal_idx], p_cal, max_fp=0.10)

    # 4) 全量训练池重训, 在 held-out 测试集上评估
    best_clf.fit(Xtr, ytr)
    pt = best_clf.predict_proba(X[te_idx])[:, 1]
    pred = (pt >= best_thr).astype(int)
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score, classification_report
    print("\n测试集综合 (held-out, best_thr):")
    print(f"  acc={accuracy_score(y[te_idx], pred):.4f} "
          f"bacc={balanced_accuracy_score(y[te_idx], pred):.4f} "
          f"auc={roc_auc_score(y[te_idx], pt):.4f}  thr={best_thr:.3f}")
    print(classification_report(y[te_idx], pred, digits=3))

    pred_fp = (pt >= thr_fp).astype(int)
    fp_rate = float((pred_fp[y[te_idx] == 0] == 1).mean())
    det_hi = float((pred_fp[y[te_idx] == 1] == 1).mean())
    print(f"低误报点 thr={thr_fp:.3f}: 干净误报率={fp_rate:.3f} 含密检出率={det_hi:.3f}")

    # 每层检出率 (在 held-out 测试集上按 variant/密度)
    te_df = df.iloc[te_idx]
    te_df = te_df.assign(_pred=pred, _prob=pt)
    print("\n测试集各项检出率 (label=1 为含密):")
    print("  " + "-" * 56)
    for (meth, p, dens), g in te_df.groupby(["method", "p", "density"]):
        if pd.isna(meth):
            g0 = g; print(f"  {'clean':<24} n={len(g0):3d} 判含密={int((g0._pred==1).sum()):3d} "
                          f"({(g0._pred==1).mean()*100:.1f}% 误报)")
            continue
        n = len(g); det = (g._pred == 1).sum()
        print(f"  {str(meth):<6} p={int(p)} d={float(dens):<4.2f}  n={n:3d} 检出={det:3d} "
              f"({det/n*100:.1f}%)")

    os.makedirs(MODEL_DIR, exist_ok=True)
    dump({"model": best_clf, "threshold": best_thr, "threshold_low_fp": thr_fp,
          "features": FEAT_KEYS, "name": best_name,
          "cv_auc": {k: float(np.mean(v)) for k, v in cv.items()},
          "auc": float(roc_auc_score(y[te_idx], pt))},
         MODEL_PATH)
    print(f"\n模型已保存 -> {MODEL_PATH}")


if __name__ == "__main__":
    main()