"""
experiments/merge_sota_table.py — 把 CNN 与手工特征的结果合并成一张论文用长表。

输入:
  experiments/data/sota_cnn_results.csv     CNN 训练摘要 (run_cnn_sota.py)
  experiments/data/cnn_checkpoint_eval.csv  检查点复评 (eval_cnn_checkpoint.py)
  experiments/data/sota_compare.csv         手工特征基线 (sota_compare.py)
  models/cnn_*_bossbase.pt             逐样本验证概率, 用于重建 bootstrap CI

输出: experiments/data/sota_table.csv

为什么要有这一层: CNN 与 LGB 的结果原本分散在三个文件里, 各自的口径 (TTA/单
裁剪、bootstrap 还是无 CI、哪套语料) 都不一样, 直接拼在一起必然出现 "LGB-53d
其实是 11 维" 那类错标。这里把口径写进列, 一行一个 (模型, 特征集, 语料, 协议)。

同时它是唯一给出 CNN 置信区间的地方 —— 之前 CNN 行只有点估计, 而 LGB 有 CI,
这种不对称会让"CNN 更好/更差"看起来比实际更确定。CI 一律按**源图**重采样。

用法: python experiments/merge_sota_table.py
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "experiments"))
sys.path.insert(0, os.path.join(PROJ, "gpu"))

from sota_compare import bootstrap_auc_ci  # noqa: E402

DATA = os.path.join(PROJ, "experiments", "data")
OUT = os.path.join(DATA, "sota_table.csv")

COLUMNS = ["model", "family", "dataset", "protocol", "feat_set", "n_features",
           "n_train", "n_val", "n_test_photos", "auc", "auc_lo", "auc_hi",
           "ci_method", "train_auc", "epochs", "source_file"]


# 语料名归一: CNN 侧写的是 imageset_bossbase, LGB 侧写的是 bossbase_npz ——
# 它们其实是同一份 npz。不归一的话二者会被判成不同语料, 从而落进不同的可比组,
# 那就又回到了"看起来在同一张表里、实际不能比"的老问题。
DATASET_ALIAS = {"imageset_bossbase": "bossbase_npz"}

CNN_FEAT_SET = {"yenet": "30 SRM fixed + conv", "xunet": "8.4M params"}


def cnn_rows() -> list:
    """CNN 行。

    主数据源是 `cnn_checkpoint_eval.csv` —— 一个入库的小 CSV, 含训练/验证
    AUC、按源图 bootstrap 的置信区间与样本量。训练检查点 (models/cnn_*.pt)
    体积大且可由 run_cnn_sota.py 重训, 因此**不入库**; 它们只作为可选覆盖:
    在本地存在时用它重算一遍, 拿到的是同一套数字 (CI 口径一致)。

    这样新 clone 的仓库不需要 33MB 权重, 也能复现论文表里的每一个 CNN 数字。
    """
    ev = os.path.join(DATA, "cnn_checkpoint_eval.csv")
    if not os.path.exists(ev):
        print(f"  (缺少 {ev}; 先跑 python experiments/run_cnn_sota.py "
              f"+ eval_cnn_checkpoint.py)")
        return []
    df = pd.read_csv(ev)

    ck_paths = {os.path.basename(p).split("_")[1]: p
                for p in glob.glob(os.path.join(PROJ, "models", "cnn_*_bossbase.pt"))}

    rows = []
    for _, r in df.iterrows():
        name = str(r["model"])
        ds = DATASET_ALIAS.get(str(r["dataset"]), str(r["dataset"]))
        row = {
            "model": name, "family": "cnn", "dataset": ds,
            "protocol": "holdout by source photo (shared with LGB)",
            "feat_set": "raw pixels",
            "n_features": CNN_FEAT_SET.get(name, "conv"),
            "n_train": "", "n_val": int(r["n_val"]),
            "n_test_photos": int(r.get("n_test_photos", 0)) or "",
            "auc": round(float(r["val_auc_tta5"]), 4),
            "auc_lo": round(float(r["auc_lo"]), 4),
            "auc_hi": round(float(r["auc_hi"]), 4),
            "ci_method": str(r.get("ci_method", "bootstrap1000 by source photo")),
            "train_auc": round(float(r["train_auc_1crop"]), 4),
            "epochs": int(r.get("epochs_run", 0)) or "",
            "source_file": os.path.basename(ev),
        }
        # 本地有检查点就顺带校验一遍, 数字对不上说明 CSV 过期了
        ck = ck_paths.get(name)
        if ck:
            try:
                import torch
                from sklearn.metrics import roc_auc_score
                d = torch.load(ck, map_location="cpu", weights_only=False)
                live = float(roc_auc_score(np.asarray(d["val_y"]),
                                           np.asarray(d["val_prob"])))
                if abs(live - row["auc"]) > 5e-4:
                    print(f"  [warn] {name}: 检查点重算 AUC={live:.4f} 与 "
                          f"{os.path.basename(ev)} 记录的 {row['auc']:.4f} 不一致; "
                          f"请重跑 eval_cnn_checkpoint.py")
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] {name}: 检查点校验失败 ({exc!r})")
        rows.append(row)
    return rows


def main():
    rows = []

    for r in cnn_rows():
        rows.append(r)
        print(f"  {r['model']:8s} AUC={r['auc']:.4f} [{r['auc_lo']:.4f}, {r['auc_hi']:.4f}] "
              f"train={r['train_auc']:.4f} epochs={r['epochs']}")

    cmp_csv = os.path.join(DATA, "sota_compare.csv")
    if os.path.exists(cmp_csv):
        for _, r in pd.read_csv(cmp_csv).iterrows():
            rows.append({
                "model": r["model"], "family": r.get("family", "handcrafted"),
                "dataset": r["dataset"], "protocol": r["protocol"],
                "feat_set": r["feat_set"], "n_features": r["n_features"],
                "n_train": r["n_train"], "n_val": r["n_val"],
                "n_test_photos": r["n_test_photos"],
                "auc": r["auc"], "auc_lo": r["auc_lo"], "auc_hi": r["auc_hi"],
                "ci_method": r["ci_method"], "train_auc": "",
                "epochs": r.get("epochs", ""),
                "source_file": r.get("source_file", os.path.basename(cmp_csv)),
            })
    else:
        print(f"  (缺少 {cmp_csv}; 先跑 python experiments/sota_compare.py)")

    if not rows:
        print("无数据可合并")
        return
    df = pd.DataFrame(rows)[COLUMNS]

    # 同一语料/协议的行才可横向比较 —— 把可比较组显式标出来, 避免再犯
    # "不同源语料放同一张表里比大小" 的错。
    main_group = ((df["dataset"] == "bossbase_npz")
                  & (df["protocol"].str.contains("holdout by source photo")))
    df["comparable_group"] = np.where(main_group, "A_bossbase_npz_holdout", "B_other")

    df.to_csv(OUT, index=False)
    print(f"\n已写出: {OUT}\n")
    show = df[["model", "feat_set", "n_features", "auc", "auc_lo", "auc_hi",
               "train_auc", "comparable_group"]]
    print(show.to_string(index=False))
    print("\n注意: 只有 comparable_group=A 的行可以横向比较; B 组语料/协议不同源。")


if __name__ == "__main__":
    main()
