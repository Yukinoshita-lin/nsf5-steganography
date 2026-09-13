"""
experiments/run_cnn_sota.py — 后台执行 Xu-Net + Ye-Net 训练并落盘 AUC.
"""
from __future__ import annotations
import os, sys, json, time, traceback
import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "gpu"))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

from train_cnn import train_one

OUT = os.path.join(PROJ, "experiments", "data", "sota_cnn_results.csv")
rows = []

for m in ("xunet", "yenet"):
    try:
        print(f"\n=== {m} on imageset_bossbase ===", flush=True)
        t0 = time.time()
        best, aucs = train_one(
            model_name=m, datas=["imageset_bossbase"],
            epochs=40, batch=32, crop=256, lr=1e-3, device="cuda", num_workers=0,
            out=os.path.join(PROJ, "models", f"cnn_{m}_bossbase.pt"),
        )
        rows.append({
            "model": m, "dataset": "imageset_bossbase",
            # best_val_auc = 最优权重的 5-crop TTA (对外报告口径)
            # final_auc    = 最后一个 epoch 的单中心裁剪 AUC (训练曲线口径)
            # 两者协议不同, 不可互相比较; 论文表只用 best_val_auc。
            "best_val_auc": round(float(best), 4),
            "final_auc": round(float(aucs[-1]), 4),
            "epochs": len(aucs),
            "elapsed_s": round(time.time() - t0, 1),
        })
    except Exception as e:
        print(f"{m} failed: {e}\n{traceback.format_exc()}", flush=True)
        rows.append({"model": m, "dataset": "imageset_bossbase", "error": str(e)[:200]})

if rows:
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"\n已写出: {OUT}", flush=True)
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
