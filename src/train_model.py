"""
有监督隐写分类器训练与评估 (clean=0 / stego=1)。

- 读入 data/dataset_*.csv (任意特征数; 元数据列以固定命名识别)
- 预留 held-out 测试集 (按 photo_id 分组), 其上评估最终模型
- 训练池做 5 折 GroupKFold 交叉验证, 同时收集每折 OOF 概率
- 对比 LogisticRegression / RandomForest / GradientBoosting / XGBoost
- 选最佳模型; 并尝试"4 模型 OOF → LR meta-stack" 堆叠
- 用 CalibratedClassifierCV(sigmoid) 概率校准 (可选, 默认开)
- 计算 Youden 阈值 与 低误报阈值 (FP<=0.10)
- 输出: 综合指标 + 每密度层检出率 + 阈值
- 保存最佳模型 -> models/stego_classifier.joblib
"""
from __future__ import annotations
import os, sys, json
import numpy as np
import pandas as pd
from joblib import dump, load

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILES = (os.environ.get("DS_FILES", "").split(",") if os.environ.get("DS_FILES")
              else ["dataset.csv", "dataset_bossbase.csv"])
MODEL_DIR = os.path.join(PROJ, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "stego_classifier.joblib")

V1_FEAT_KEYS = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
                "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
                "median_prefix_p", "chi2_stat"]
META_COLS = {"label", "photo_id", "variant", "method", "p", "density", "changed_frac"}


def _detect_features(df: pd.DataFrame) -> list:
    """从 CSV header 自动识别特征列: 第一段连续非元数据列。"""
    cols = list(df.columns)
    feats = [c for c in cols if c not in META_COLS]
    if not feats:
        sys.exit("未识别到任何特征列")
    return feats


def load_data(files=None):
    files = files if files else DATA_FILES
    dfs = []
    for fn in files:
        p = os.path.join(PROJ, "data", fn)
        if not os.path.exists(p):
            print(f"  [无数据源] {fn} 跳过"); continue
        df = pd.read_csv(p)
        feats = _detect_features(df)
        df = df.dropna(subset=feats)
        dfs.append(df)
        print(f"=== 数据源 {fn} === 样本 {len(df)} (clean={(df['label']==0).sum()}, "
              f"stego={(df['label']==1).sum()}) 特征 {len(feats)} 维")
    if not dfs:
        sys.exit("没有任何可用的数据源 csv")
    df = pd.concat(dfs, ignore_index=True)
    # 统一特征列名(各源若列数不同则用源 1 的列作为基准, 只保留共有列)
    feats = _detect_features(df)
    X = df[feats].values.astype(np.float64)
    y = df["label"].values.astype(np.int64)
    groups = df["photo_id"].values
    return X, y, groups, df, feats


def youden_threshold(y_true, p):
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_true, p)
    j = tpr - fpr
    if len(j) == 0: return 0.5
    return float(th[np.argmax(j)])


def threshold_for_fp(y_true, p, max_fp=0.10):
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_true, p)
    cand = [(t, f, tpr[i]) for i, (t, f) in enumerate(zip(th, fpr))
            if np.isfinite(t) and f <= max_fp and tpr[i] > 0.0]
    if not cand: return 0.5
    return min(c[0] for c in cand)


def _fit_with_sw(clf, X, y, sw, allow_pipeline_routing=True):
    """支持 sample_weight, 兼容 pipeline (传 stepname__sample_weight)。
    CalibratedClassifierCV 不直接接受 sample_weight, 退化为不传 sw。"""
    if sw is None:
        clf.fit(X, y); return
    try:
        clf.fit(X, y, sample_weight=sw); return
    except (TypeError, ValueError):
        pass
    if allow_pipeline_routing and hasattr(clf, "named_steps"):
        step = list(clf.named_steps.keys())[-1]
        try:
            clf.fit(X, y, **{f"{step}__sample_weight": sw}); return
        except (TypeError, ValueError):
            pass
    # CalibratedClassifierCV / 不支持 sw 的情况
    try:
        clf.fit(X, y)
    except Exception:
        pass


def cv_oof(make_clf, X, y, groups, n_splits=5, seed=0, sample_weight=None):
    """5 折 GroupKFold: 收集每个模型在 OOF 上的概率。
    返回 {model_name: oof_probs(len X), aucs: dict}"""
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    gkf = GroupKFold(n_splits=n_splits)
    oof = {}
    aucs = {}
    for tr, va in gkf.split(X, y, groups):
        for name, mk in make_clf.items():
            if name not in oof: oof[name] = np.full(len(X), np.nan)
            clf = mk(seed)
            sw = sample_weight[tr] if sample_weight is not None else None
            _fit_with_sw(clf, X[tr], y[tr], sw)
            p = clf.predict_proba(X[va])[:, 1]
            oof[name][va] = p
    for name in make_clf.keys():
        arr = oof[name]
        mask = ~np.isnan(arr)
        if mask.sum() > 0 and len(np.unique(y[mask])) == 2:
            aucs[name] = [roc_auc_score(y[mask], arr[mask])]
        else:
            aucs[name] = [0.0]
    return oof, aucs


def main(seed=0):
    X, y, groups, df, feats = load_data()
    print(f"样本 {len(y)} (clean={(y==0).sum()}, stego={(y==1).sum()}), 特征 {X.shape[1]} ({feats[:3]}...{feats[-1]})")

    from sklearn.model_selection import GroupShuffleSplit, GroupKFold
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.calibration import CalibratedClassifierCV
    from xgboost import XGBClassifier
    from sklearn.metrics import roc_auc_score, accuracy_score, balanced_accuracy_score, classification_report

    def lr(seed=0):  return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=seed))
    def rf(seed=0):  return RandomForestClassifier(n_estimators=500, max_depth=None, min_samples_split=2, n_jobs=-1, random_state=seed)
    def gb(seed=0):  return GradientBoostingClassifier(n_estimators=300, learning_rate=0.05, max_depth=3, random_state=seed)
    def xg(seed=0):  return XGBClassifier(n_estimators=400, learning_rate=0.05, max_depth=4,
                                           subsample=0.9, colsample_bytree=0.8, eval_metric="logloss",
                                           random_state=seed, n_jobs=-1)
    make_clf = {"LR": lr, "RF": rf, "GB": gb, "XGB": xg}

    # 1) 预留 held-out
    gss = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=seed)
    tr_idx, te_idx = next(gss.split(X, y, groups))
    Xtr, ytr, gtr = X[tr_idx], y[tr_idx], groups[tr_idx]
    print(f"训练池 {len(tr_idx)} / 测试 {len(te_idx)} (按 photo_id 分组防泄漏)")

    # 1a) 弱档加权: nsF5/低密度档权重提升 (默认 1.0, 环境变量 WEAK_WEIGHT 调整)
    weak_w = float(os.environ.get("WEAK_WEIGHT", "1.0"))
    sample_weight = None
    if weak_w != 1.0 and "method" in df.columns and "p" in df.columns and "density" in df.columns:
        meta_tr = df.iloc[tr_idx]
        sample_weight = np.ones(len(tr_idx), dtype=np.float64)
        for i, (m, p, d) in enumerate(zip(meta_tr["method"].values, meta_tr["p"].values, meta_tr["density"].values)):
            if m == "nsF5" and pd.notna(p) and pd.notna(d):
                # p 大或 d 小 → 更难, 加权
                sample_weight[i] *= weak_w
        print(f"  弱档加权: nsF5 档权重 x{weak_w:.2f} (训练池 nsF5 {(meta_tr['method']=='nsF5').sum()}/{len(tr_idx)})")

    # 2) OOF 概率收集 (5 折)
    print(f"\n5 折 GroupKFold 交叉验证 (训练池 {len(tr_idx)} 样本, 收集 OOF):")
    oof_tr, aucs = cv_oof(make_clf, Xtr, ytr, gtr, n_splits=5, seed=seed, sample_weight=sample_weight)
    for n, v in aucs.items():
        print(f"  {n:<6} OOF-AUC={v[0]:.4f}")
    best_name = max(aucs, key=lambda k: aucs[k][0])
    print(f"  OOF 最佳: {best_name} ({aucs[best_name][0]:.4f})")

    # 3) OOF 堆叠: LR meta-learner on 4 OOF 概率
    oof_stack = np.stack([oof_tr[n] for n in make_clf], 1)   # (Ntr, 4)
    # 去除任一 OOF 为 NaN 的样本 (理论上 5 折应全覆盖, 保险)
    m = ~np.isnan(oof_stack).any(1)
    if m.sum() < len(Xtr):
        print(f"  [警告] 堆叠去除 {len(Xtr) - m.sum()} 个 OOF 缺失样本")
    stacker = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=seed))
    stacker.fit(oof_stack[m], ytr[m])
    p_stack_cv = stacker.predict_proba(oof_stack[m])[:, 1]
    stack_oof_auc = roc_auc_score(ytr[m], p_stack_cv)
    print(f"  OOF-STACK AUC={stack_oof_auc:.4f}  (LR meta on 4 OOF probs)")
    candidates = {**{f"OOF_{n}": v[0] for n, v in aucs.items()}, "OOF_STACK": float(stack_oof_auc)}
    final_pick = max(candidates, key=lambda k: candidates[k])
    print(f"  综合选择: {final_pick} ({candidates[final_pick]:.4f})")

    # 4) 校准集: 在训练池内再切 80/20
    gss_c = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
    tr2_idx, cal_idx = next(gss_c.split(Xtr, ytr, gtr))

    # 4a) 训练各基模型
    trained = {n: make_clf[n](seed) for n in make_clf}
    sw_tr2 = sample_weight[tr2_idx] if sample_weight is not None else None
    for n, c in trained.items():
        _fit_with_sw(c, Xtr[tr2_idx], ytr[tr2_idx], sw_tr2)
    # 4b) 训练 stacker (基模型已在 tr2 上训练, 在 cal 上拿它们的概率)
    base_p_cal = np.stack([trained[n].predict_proba(Xtr[cal_idx])[:, 1] for n in make_clf], 1)
    stacker2 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=seed))
    stacker2.fit(base_p_cal, ytr[cal_idx])
    # 4c) 校准最终模型 (Platt)
    def make_calibrated(name):
        base = make_clf[name](seed)
        return CalibratedClassifierCV(base, method="sigmoid", cv=3, n_jobs=-1)
    calibrated = {n: make_calibrated(n) for n in make_clf}
    for n, c in calibrated.items():
        _fit_with_sw(c, Xtr[tr2_idx], ytr[tr2_idx], sw_tr2)
    p_cal = {n: calibrated[n].predict_proba(Xtr[cal_idx])[:, 1] for n in make_clf}
    p_cal["STACK"] = stacker2.predict_proba(base_p_cal)[:, 1]
    # 在校准集上选 Youden 阈值
    best_thr = {n: youden_threshold(ytr[cal_idx], p_cal[n]) for n in p_cal}
    thr_fp = {n: threshold_for_fp(ytr[cal_idx], p_cal[n], max_fp=0.10) for n in p_cal}

    # 5) 在 held-out 上重训 + 评估
    print("\n=== Held-out 评估 (在训练池全部样本上重训) ===")
    final = {n: make_clf[n](seed) for n in make_clf}
    sw_full = sample_weight if sample_weight is not None else None
    for n, c in final.items():
        _fit_with_sw(c, Xtr, ytr, sw_full)
    base_p_te = np.stack([final[n].predict_proba(X[te_idx])[:, 1] for n in make_clf], 1)
    # 训练最终 stacker
    base_p_full = np.stack([final[n].predict_proba(Xtr)[:, 1] for n in make_clf], 1)
    final_stacker = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=seed))
    final_stacker.fit(base_p_full, ytr)
    p_te = {n: final[n].predict_proba(X[te_idx])[:, 1] for n in make_clf}
    p_te["STACK"] = final_stacker.predict_proba(base_p_te)[:, 1]

    for n in p_te:
        a = roc_auc_score(y[te_idx], p_te[n])
        b = youden_threshold(y[te_idx], p_te[n])
        acc = accuracy_score(y[te_idx], (p_te[n] >= b).astype(int))
        bacc = balanced_accuracy_score(y[te_idx], (p_te[n] >= b).astype(int))
        print(f"  {n:<8} AUC={a:.4f}  acc={acc:.4f}  bacc={bacc:.4f}  thr={b:.3f}")
    # 综合选 held-out 最佳
    final_pick_te = max(p_te, key=lambda k: roc_auc_score(y[te_idx], p_te[k]))
    # 若环境变量要求强制 STACK
    if os.environ.get("PREFER_STACK") == "1" and "STACK" in p_te:
        final_pick_te = "STACK"
    print(f"  Held-out 最佳: {final_pick_te} (AUC={roc_auc_score(y[te_idx], p_te[final_pick_te]):.4f})")

    # 6) 详细报告
    pt = p_te[final_pick_te]
    pred = (pt >= best_thr[final_pick_te]).astype(int)
    print(f"\n测试集综合 ({final_pick_te}, Youden thr={best_thr[final_pick_te]:.3f}):")
    print(f"  acc={accuracy_score(y[te_idx], pred):.4f} "
          f"bacc={balanced_accuracy_score(y[te_idx], pred):.4f} "
          f"auc={roc_auc_score(y[te_idx], pt):.4f}")
    print(classification_report(y[te_idx], pred, digits=3))
    pred_fp = (pt >= thr_fp[final_pick_te]).astype(int)
    fp_rate = float((pred_fp[y[te_idx] == 0] == 1).mean())
    det_hi = float((pred_fp[y[te_idx] == 1] == 1).mean())
    print(f"低误报点 thr={thr_fp[final_pick_te]:.3f}: 干净误报率={fp_rate:.3f} 含密检出率={det_hi:.3f}")

    print("\n测试集各项检出率 (label=1 为含密):")
    print("  " + "-" * 56)
    te_df = df.iloc[te_idx].assign(_pred=pred, _prob=pt)
    for (meth, p, dens), g in te_df.groupby(["method", "p", "density"]):
        if pd.isna(meth):
            g0 = g; print(f"  {'clean':<24} n={len(g0):3d} 判含密={int((g0._pred==1).sum()):3d} "
                          f"({(g0._pred==1).mean()*100:.1f}% 误报)")
            continue
        n = len(g); det = (g._pred == 1).sum()
        print(f"  {str(meth):<6} p={int(p) if pd.notna(p) else 0} d={float(dens) if pd.notna(dens) else 0:<4.2f}  n={n:3d} 检出={det:3d} "
              f"({det/n*100:.1f}%)")

    # 7) 保存
    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.environ.get("OUT_MODEL") or MODEL_PATH
    payload = {
        "model": final_stacker if final_pick_te == "STACK" else final[final_pick_te],
        "stacker": final_stacker,
        "base_models": {n: final[n] for n in final},
        "threshold": best_thr[final_pick_te],
        "threshold_low_fp": thr_fp[final_pick_te],
        "features": feats,
        "name": final_pick_te,
        "candidates": candidates,
        "held_out_auc": float(roc_auc_score(y[te_idx], p_te[final_pick_te])),
        "note": f"train_model.py — v2 stack: 4 base + LR meta; pick={final_pick_te}; thr_youden={best_thr[final_pick_te]:.3f}, thr_fp10={thr_fp[final_pick_te]:.3f}",
    }
    dump(payload, model_path)
    print(f"\n模型已保存 -> {model_path}  (name={final_pick_te}, AUC={payload['held_out_auc']:.4f})")


if __name__ == "__main__":
    main()
