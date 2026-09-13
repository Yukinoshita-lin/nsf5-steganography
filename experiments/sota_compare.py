"""
experiments/sota_compare.py — 手工特征 LGB 基线, 与 CNN 同语料、同划分。

⚠ 历史教训 (本文件的第一版就是反例): 旧版本读 `data/dataset_bossbase.csv`,
那个 CSV 只有 11 维特征列, 而代码用 `[c for c in feats if c in df.columns]`
做过滤 —— 于是 53 维请求被静默降级成 11 维, 结果却仍然被标成 `LGB-53d` 写进
`sota_compare.csv`。那份产物 (0.7565, n_features=11) 被论文原样引用。
现在特征列缺失一律 `raise`, 绝不降级; `feat_set` 与 `dataset` 是两个独立列,
从结构上杜绝再次错标。

语料一致性: CNN 用的是 `gpu/data/imageset_bossbase.npz` (2000 源图 x 5 变体)。
`data/dataset_bossbase.csv` 是另一套语料 (10000 源图 x 7 变体), 两者不同源,
同表比大小没有意义。因此主表统一用 `data/dataset_bossbase_npz_v2.csv`
(由 `featurize_bossbase_npz.py` 从同一个 npz 现场提出 143 维), 并按
`experiments/data/sota_cnn_split.json` 的同一份按源图划分训练/验证。

用法: python experiments/sota_compare.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))
sys.path.insert(0, os.path.join(PROJ, "gpu"))

from featurize_v2 import ALL_FEATURE_NAMES, BASE_11, SRM_STAT_NAMES  # noqa: E402

NPZ_CSV = os.path.join(PROJ, "data", "dataset_bossbase_npz_v2.csv")
APPENDIX_CSV = os.path.join(PROJ, "data", "dataset_bossbase.csv")
# 划分文件由 gpu/train_cnn.py 产出, 现写在 gpu/data/ 下 (工具链自己的目录)。
# 兼容旧位置 experiments/data/, 免得此前跑出的实验产物失效。
_SPLIT_CANDIDATES = [
    os.path.join(PROJ, "gpu", "data", "sota_cnn_split.json"),
    os.path.join(PROJ, "experiments", "data", "sota_cnn_split.json"),
]
SPLIT_JSON = next((p for p in _SPLIT_CANDIDATES if os.path.exists(p)), _SPLIT_CANDIDATES[0])
OUT = os.path.join(PROJ, "experiments", "data", "sota_compare.csv")

# 三个特征集。53d = 143d 去掉 90 个 SRM 统计量, 与项目部署的
# stego_classifier_v2_jpeg_lgb_51d.joblib 的口径一致 (11+20+2+20 = 53)。
FEAT_SETS = {
    "11d": list(BASE_11),
    "53d": [n for n in ALL_FEATURE_NAMES if n not in set(SRM_STAT_NAMES)],
    "143d": list(ALL_FEATURE_NAMES),
}

# 与项目既有 143d/53d 部署模型一致的超参 (README v1.4.0)
LGB_PARAMS = dict(objective="binary", metric="auc", learning_rate=0.03,
                  num_leaves=31, n_estimators=800, min_child_samples=10,
                  feature_fraction=0.9, bagging_fraction=0.9, bagging_freq=5,
                  verbose=-1, random_state=0)


def need_cols(df: pd.DataFrame, cols, tag: str):
    """特征列必须齐全, 缺一列就报错。绝不静默降级 —— 旧版就是在这里出的事。"""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"{tag}: 缺少 {len(missing)} 个特征列 (例: {missing[:8]}); "
            f"不允许降级到可用子集, 请先核对数据集。")
    return list(cols)


def bootstrap_auc_ci(y, p, groups, n_boot: int = 1000, alpha: float = 0.05, seed: int = 0):
    """按**源图**重采样的 bootstrap AUC 置信区间。

    必须按组重采样: 同一源图的 5 张变体高度相关, 按图重采样会把有效样本量
    当成 5 倍, 从而低估置信区间宽度。
    """
    from sklearn.metrics import roc_auc_score

    y = np.asarray(y)
    p = np.asarray(p)
    groups = np.asarray(groups)
    uniq = np.unique(groups)
    idx_by_group = {g: np.flatnonzero(groups == g) for g in uniq}
    rng = np.random.default_rng(seed)
    aucs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([idx_by_group[uniq[k]] for k in pick])
        if len(np.unique(y[idx])) < 2:
            continue
        aucs.append(roc_auc_score(y[idx], p[idx]))
    if not aucs:
        return float("nan"), float("nan")
    lo, hi = np.percentile(aucs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def load_split():
    if not os.path.exists(SPLIT_JSON):
        raise FileNotFoundError(
            f"缺少 {SPLIT_JSON}; 先跑 python experiments/run_cnn_sota.py "
            f"(划分由 CNN 侧统一产出, LGB 基线必须复用同一份)")
    with open(SPLIT_JSON, "r", encoding="utf-8") as fh:
        splits = json.load(fh)
    if not splits:
        raise ValueError(f"{SPLIT_JSON} 是空的")
    key = "imageset_bossbase" if "imageset_bossbase" in splits else next(iter(splits))
    return key, splits[key]


def fit_and_eval(df, feats, tr_mask, va_mask, tag, dataset, protocol):
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score

    need_cols(df, feats, tag)
    X = df[feats].to_numpy(dtype=np.float64)
    y = df["label"].to_numpy(dtype=np.int64)
    g = df["photo_id"].to_numpy()

    m = lgb.LGBMClassifier(**LGB_PARAMS)
    m.fit(X[tr_mask], y[tr_mask])
    p = m.predict_proba(X[va_mask])[:, 1]

    y_va, g_va = y[va_mask], g[va_mask]
    auc = float(roc_auc_score(y_va, p))
    lo, hi = bootstrap_auc_ci(y_va, p, g_va, seed=0)
    return {
        "model": f"LGB-{tag}", "family": "handcrafted", "dataset": dataset,
        "protocol": protocol, "feat_set": tag, "n_features": len(feats),
        "n_train": int(tr_mask.sum()), "n_val": int(va_mask.sum()),
        "n_test_photos": int(len(np.unique(g_va))),
        "auc": round(auc, 4), "auc_lo": round(lo, 4), "auc_hi": round(hi, 4),
        "ci_method": "bootstrap1000 by source photo",
        "epochs": "", "source_file": os.path.basename((NPZ_CSV if "npz" in dataset
                                                       else APPENDIX_CSV)),
    }


def main():
    rows = []
    split_key, split = load_split()
    val_photos = set(split["val_photo_ids"])
    print(f"=== 主表: 同一 npz 语料 + 同一按源图划分 (split key={split_key}) ===")
    print(f"    验证源图 {len(val_photos)} 张, 训练图 {split['n_train_images']} 张")

    if not os.path.exists(NPZ_CSV):
        print(f"  跳过: {NPZ_CSV} 不存在, 先跑 "
              f"python experiments/featurize_bossbase_npz.py")
    else:
        df = pd.read_csv(NPZ_CSV)
        vm = df["photo_id"].isin(val_photos).to_numpy()
        tm = ~vm
        protocol = "holdout by source photo (shared with CNN)"
        for tag in ("11d", "53d", "143d"):
            r = fit_and_eval(df, FEAT_SETS[tag], tm, vm, tag, "bossbase_npz", protocol)
            rows.append(r)
            print(f"  {r['model']:12s} n_features={r['n_features']:3d}  "
                  f"AUC={r['auc']:.4f} [{r['auc_lo']:.4f}, {r['auc_hi']:.4f}]")

    # 附录: 另一套语料, 协议不同源, 仅作参考, 必须单独标注
    if os.path.exists(APPENDIX_CSV):
        print("\n=== 附录: dataset_bossbase.csv (10000 源图 x 7 变体, 另一套语料) ===")
        dfa = pd.read_csv(APPENDIX_CSV)
        try:
            need_cols(dfa, FEAT_SETS["11d"], "appendix-11d")
            from sklearn.model_selection import GroupKFold
            from sklearn.metrics import roc_auc_score
            import lightgbm as lgb

            X = dfa[FEAT_SETS["11d"]].to_numpy(dtype=np.float64)
            y = dfa["label"].to_numpy(dtype=np.int64)
            g = dfa["photo_id"].to_numpy()
            oof = np.full(len(y), np.nan)
            for tr, va in GroupKFold(n_splits=5).split(X, y, g):
                m = lgb.LGBMClassifier(**LGB_PARAMS)
                m.fit(X[tr], y[tr])
                oof[va] = m.predict_proba(X[va])[:, 1]
            auc = float(roc_auc_score(y, oof))
            lo, hi = bootstrap_auc_ci(y, oof, g, seed=0)
            rows.append({
                "model": "LGB-11d", "family": "handcrafted",
                "dataset": "bossbase_csv", "protocol": "5-fold GroupKFold OOF",
                "feat_set": "11d", "n_features": 11,
                "n_train": int(len(y)), "n_val": int(len(y)),
                "n_test_photos": int(len(np.unique(g))),
                "auc": round(auc, 4), "auc_lo": round(lo, 4), "auc_hi": round(hi, 4),
                "ci_method": "bootstrap1000 by source photo",
                "epochs": "", "source_file": os.path.basename(APPENDIX_CSV),
            })
            print(f"  LGB-11d (协议不同源, 仅供附录)  AUC={auc:.4f} "
                  f"[{lo:.4f}, {hi:.4f}]")
        except ValueError as exc:
            print(f"  跳过附录: {exc}")

    if not rows:
        print("无数据可比, 退出")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\n已写出: {OUT}")


if __name__ == "__main__":
    main()
