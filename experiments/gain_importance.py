"""
experiments/gain_importance.py — 特征重要性 (LightGBM gain) 的生产者。

背景 (2026-09-14 审计)
----------------------
`experiments/data/gain_importance.csv` 与 `gain_importance_53d.csv` 一直是
"只读不写"的产物: 全仓只有 `experiments/gen_figs.py` 读它们画 Top-20 图,
没有任何脚本能再生产 —— PROVENANCE.md 里把它标成不可再生。

更要命的是: 旧表是**错误特征尺度**的产物 (GPU 端 SRM 曾把像素先 /255),
当年据此得出的"SRM 90 维 gain 占比仅 26.6% / 是噪声特征"的结论已作废。
本脚本按当前口径重算, 于是这两个文件重新变成可溯源产物。

口径: 与 `train_deploy_models.py` 完全一致 —— 同一份语料、同一套超参、
同一个按源图划分、seed 0; 只是多导出一次 gain importance。

输出
----
    experiments/data/gain_importance.csv       143d 模型 (列: rank/feature/gain/gain_pct/group/model)
    experiments/data/gain_importance_53d.csv   53d  模型 (同上; gen_figs.py 按 feature/gain 读)
    experiments/data/gain_group_share.csv      按特征组汇总的 gain 占比

用法
----
    python experiments/gain_importance.py
    python experiments/gain_importance.py --seed 3 --csv data/dataset_campus_v2_jpeg.csv
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))
sys.path.insert(0, os.path.join(PROJ, "experiments"))

from featurize_v2 import ALL_FEATURE_NAMES, BASE_11, SRM_STAT_NAMES  # noqa: E402
from train_deploy_models import (DEFAULT_CSV, LGB_PARAMS,  # noqa: E402
                                 check_corpus_grouping, feature_sets, split_by_photo)

DATA = os.path.join(PROJ, "experiments", "data")
OUT_143 = os.path.join(DATA, "gain_importance.csv")
OUT_53 = os.path.join(DATA, "gain_importance_53d.csv")
OUT_GROUP = os.path.join(DATA, "gain_group_share.csv")


def group_of(name: str) -> str:
    if name in SRM_STAT_NAMES:
        return "SRM 90"
    if name in BASE_11:
        return "BASE 11"
    if name.startswith("lsb_prefix_p"):
        return "LSB PREFIX 20"
    if name.startswith("prefix_p"):
        return "PREFIX 20"
    return "TEXTURE/EST 2"


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJ,
                              capture_output=True, text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def importance_table(feats: list, gains: np.ndarray, model: str, meta: dict) -> pd.DataFrame:
    df = pd.DataFrame({"feature": feats, "gain": np.asarray(gains, dtype=float)})
    df = df.sort_values("gain", ascending=False, kind="stable").reset_index(drop=True)
    total = float(df["gain"].sum()) or 1.0
    df.insert(0, "rank", np.arange(1, len(df) + 1))
    df["gain_pct"] = (df["gain"] / total).round(6)
    df["group"] = df["feature"].map(group_of)
    df["model"] = model
    for k, v in meta.items():
        df[k] = v
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description="导出两个部署模型的 LGB gain importance")
    ap.add_argument("--csv", default=DEFAULT_CSV, help="训练语料 (默认校园 v2_jpeg)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import lightgbm as lgb

    csv_path = os.path.abspath(args.csv)
    if not os.path.exists(csv_path):
        sys.exit(f"语料不存在: {csv_path}")
    df = pd.read_csv(csv_path)
    check_corpus_grouping(df, csv_path)
    y = df["label"].values.astype(np.int64)
    pid = df["photo_id"].values
    val = split_by_photo(pid, seed=args.seed)
    tr = ~val
    print(f"语料 {os.path.basename(csv_path)}: {len(df)} 样本 / {len(np.unique(pid))} 源图  "
          f"(训练 {tr.sum()} / 验证 {val.sum()}, seed={args.seed})")

    meta = {"dataset": os.path.basename(csv_path), "split": "by-photo holdout seed=%d" % args.seed,
            "git_rev": _git_rev(), "python": platform.python_version(),
            "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    outs = {}
    for key, feats in feature_sets().items():
        missing = [c for c in feats if c not in df.columns]
        if missing:
            sys.exit(f"{key}: 缺 {len(missing)} 列 (例 {missing[:4]}); 拒绝降级。")
        X = df[feats].values.astype(np.float64)
        clf = lgb.LGBMClassifier(**LGB_PARAMS)
        clf.fit(X[tr], y[tr])
        gains = clf.booster_.feature_importance(importance_type="gain")
        table = importance_table(feats, gains, name := ("143d" if key == "143d" else "53d"), meta)
        outs[key] = table
        path = OUT_143 if key == "143d" else OUT_53
        table.to_csv(path, index=False, float_format="%.6g")
        print(f"  {name}: {len(feats)} 维, gain 合计 {table['gain'].sum():.0f} -> "
              f"{os.path.relpath(path, PROJ)}")
        print(f"      Top5: " + ", ".join(f"{r.feature}({r.gain_pct*100:.1f}%)"
                                          for r in table.head(5).itertuples()))

    rows = []
    for key, table in outs.items():
        g = table.groupby("group")["gain"].sum()
        for grp, val_ in g.items():
            rows.append({"model": table['model'].iloc[0], "group": grp,
                         "gain": float(val_),
                         "gain_pct": round(float(val_) / float(table['gain'].sum()), 6)})
    share = pd.DataFrame(rows).sort_values(["model", "gain_pct"], ascending=[True, False])
    share.to_csv(OUT_GROUP, index=False)
    print(f"\n按组汇总 -> {os.path.relpath(OUT_GROUP, PROJ)}")
    print(share.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
