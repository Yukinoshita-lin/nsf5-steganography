"""
experiments/eval_cnn_checkpoint.py — 从已保存的 CNN 检查点重算评测指标。

存在意义: 区分"CNN 没收敛"与"CNN 过拟合"。训练集 AUC 也贴在 0.5 说明模型
压根没拟合上, 此时把它报成"CNN 输给手工特征"是错的结论 —— 必须能看见这个数。
检查点里已经存了验证集逐样本概率 (val_idx/val_prob/val_y), 所以验证侧不需要
重跑; 训练侧要再前向一次, 取样上限 800 张控制开销。

本脚本是"检查点不入库"的前提: 训练检查点体积大 (Xu-Net 33MB) 且可由
run_cnn_sota.py 重训, 所以 .gitignore 排除 models/*.pt; 而论文需要的全部指标
(训练/验证 AUC、按源图 bootstrap 的置信区间、样本量) 都汇总进这里产出的
`experiments/data/cnn_checkpoint_eval.csv` —— 一个几十行的小 CSV, 随仓库入库。
于是别人拿到仓库不需要 33MB 权重也能核对论文里的每一个 CNN 数字。

用法: python experiments/eval_cnn_checkpoint.py [--ckpt models/cnn_yenet_bossbase.pt ...]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "gpu"))
sys.path.insert(0, os.path.join(PROJ, "experiments"))

from train_cnn import evaluate, load_imageset, split_by_photo  # noqa: E402
from sota_compare import bootstrap_auc_ci  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", nargs="*", default=[],
                    help="检查点路径 (默认: models/cnn_*_bossbase.pt)")
    ap.add_argument("--train-sub", type=int, default=800)
    args = ap.parse_args()

    import torch
    from models import MODEL_ZOO
    from sklearn.metrics import roc_auc_score

    ckpts = args.ckpt or sorted(glob.glob(os.path.join(PROJ, "models", "cnn_*_bossbase.pt")))
    if not ckpts:
        print("没有找到检查点; 先跑 python experiments/run_cnn_sota.py")
        return

    rows = []
    x = y = pid = None
    for path in ckpts:
        ck = torch.load(path, map_location="cpu", weights_only=False)
        name, datas = ck["model_name"], ck["datas"]
        if x is None:
            x, y, pid, _meta = load_imageset(datas[0])
        device = "cuda" if torch.cuda.is_available() else "cpu"

        model = MODEL_ZOO[name]().to(device)
        model.load_state_dict(ck["state_dict"])

        train_idx, val_idx = split_by_photo(pid, seed=ck.get("seed", 0),
                                           val_frac=ck.get("val_frac", 0.2),
                                           write=None)
        val_idx_ck = np.asarray(ck["val_idx"])
        same_split = val_idx_ck.size == val_idx.size
        if not same_split:
            print(f"[warn] {path}: 检查点的验证划分与当前 split json 不一致, "
                  f"用检查点里存的 val_idx/val_prob 报验证 AUC")

        if "val_prob" in ck:
            y_va = np.asarray(ck["val_y"])
            p_va = np.asarray(ck["val_prob"])
            g_va = np.asarray(ck.get("val_photo_id", np.arange(y_va.size)))
            val_auc = float(roc_auc_score(y_va, p_va))
            val_n = int(y_va.size)
        else:
            p_va = evaluate(model, x, y, val_idx, ck["crop"], device, tta=True)
            y_va, g_va = y[val_idx], pid[val_idx]
            val_auc = float(roc_auc_score(y_va, p_va))
            val_n = int(val_idx.size)
        # 置信区间必须与 LGB 基线用同一套口径 (按源图重采样), 否则两侧的
        # 误差棒不可比。
        lo, hi = bootstrap_auc_ci(y_va, p_va, g_va, seed=0)

        tr_sub = train_idx[:min(args.train_sub, len(train_idx))]
        p_tr = evaluate(model, x, y, tr_sub, ck["crop"], device,
                        batch=16, tta=False)
        train_auc = float(roc_auc_score(y[tr_sub], p_tr))

        rows.append({
            "model": name, "dataset": datas[0],
            "train_auc_1crop": round(train_auc, 4),
            "val_auc_tta5": round(val_auc, 4),
            "auc_lo": round(lo, 4), "auc_hi": round(hi, 4),
            "ci_method": "bootstrap1000 by source photo",
            "val_auc_1crop": round(float(ck.get("best_val_auc_1crop", float("nan"))), 4),
            "epochs_run": len(ck.get("aucs", [])),
            "n_val": val_n, "n_test_photos": int(len(np.unique(g_va))),
            "ckpt": os.path.basename(path),
        })
        print(f"{name}: train_auc(中心裁剪, n={len(tr_sub)}) = {train_auc:.4f} | "
              f"val_auc(5-crop TTA, n={val_n}) = {val_auc:.4f} "
              f"[{lo:.4f}, {hi:.4f}]", flush=True)

    import pandas as pd
    out = os.path.join(PROJ, "experiments", "data", "cnn_checkpoint_eval.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\n已写出: {out}")


if __name__ == "__main__":
    main()
