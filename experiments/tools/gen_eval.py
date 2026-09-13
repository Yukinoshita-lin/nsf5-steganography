# -*- coding: utf-8 -*-
"""论文实验2: 盲隐写分析监督检测评估
基于 gpu/data/imageset.npz (682 照片×5: 1 干净+4 含密变体, 11维特征),
按 photo_id 做 GroupKFold 交叉验证 + Logistic Regression:
  - 整体 ROC 曲线 与 pooled AUC / 5折 CV-AUC
  - 混淆矩阵(Youden 阈值)
  - 按 (method,p,density) 的分档检出率 与 干净误报
输出: experiments/data/{det_roc,det_density,det_confusion,det_metrics}
       experiments/figs/{det_roc,det_density}.png|svg
"""
from __future__ import annotations
import sys, os, time, csv
os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.abspath("src"); GPU = os.path.abspath("gpu")
for p in (SRC, GPU):
    if p not in sys.path: sys.path.insert(0, p)
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_curve, roc_auc_score, confusion_matrix
from fsfeatures import get_lib
from ml_predict import FEAT_KEYS

OUTD = os.path.join("experiments", "data"); FIGD = os.path.join("experiments", "figs")
os.makedirs(OUTD, exist_ok=True); os.makedirs(FIGD, exist_ok=True)

d = np.load(os.path.join("gpu", "data", "imageset.npz"), allow_pickle=True)
x, y, pid, meta = d["x"], d["y"], d["photo_id"], d["meta"]
lib = get_lib()
print(f"样本 {len(y)}: clean={(y==0).sum()} stego={(y==1).sum()}, {x.shape[1]}x{x.shape[2]}; 提取特征(CPU dll)…")
t0 = time.perf_counter()
F = np.stack([np.array([lib.features(im)[k] for k in FEAT_KEYS], dtype=np.float64) for im in x])
print(f"特征提取 {len(y)} 张: {time.perf_counter()-t0:.1f}s ({len(y)/(time.perf_counter()-t0):.0f}/s)", F.shape)

# GroupKFold 5 折
gkf = GroupKFold(n_splits=5)
oof = np.zeros(len(y))          # out-of-fold 概率
prob, truth = [], []
for tr, va in gkf.split(F, y, groups=pid):
    clf = LogisticRegression(max_iter=3000, C=1.0).fit(F[tr], y[tr])
    oof[va] = clf.predict_proba(F[va])[:, 1]
    prob.append(oof[va]); truth.append(y[va])
pool_p = np.concatenate(prob); pool_y = np.concatenate(truth)
auc = roc_auc_score(pool_y, pool_p)
fpr, tpr, _ = roc_curve(pool_y, pool_p)
print(f"\npooled AUC = {auc:.3f}  (N={len(pool_y)})")

# Youden 阈值
ths = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
best = max(ths, key=lambda th: ((pool_p[pool_y == 1] >= th).mean()
                                - (pool_p[pool_y == 0] >= th).mean()))  # Youden
cm = confusion_matrix(pool_y, pool_p >= best)
tn, fp, fn, tp = cm.ravel()
print(f"Youden thr={best:.2f}: TPR={tp/(tp+fn)*100:.1f}%  FPR={fp/(fp+tn)*100:.1f}%  acc={(tp+tn)/len(pool_y)*100:.1f}%")

# 按方法/密度 检出率
rows = []
metas = [m for m in meta]
for (meth, p, dens) in sorted(set((m[0], m[1], m[2]) for m in metas if m[3])):
    idx = np.array([i for i, m in enumerate(metas) if m[0] == meth and m[1] == p and m[2] == dens])
    if len(idx) == 0: continue
    idx = idx[pool_y[idx] == 1]
    if len(idx) == 0: continue
    dr = (pool_p[idx] >= best).mean()
    rows.append((meth, p, float(dens), dr, len(idx)))
c0 = (pool_p[pool_y == 0] >= best).mean()   # 干净误报
print("--- 按方法/密度检出率 ---")
for r in rows:
    print(f"  {r[0]} p{r[1]} d={r[2]:.2f}: det={r[3]*100:.1f}%  (n={r[4]})")
print(f"  干净(误报)  = {c0*100:.1f}%")

with open(os.path.join(OUTD, "det_roc.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["fpr", "tpr"]); w.writerows(zip(fpr, tpr))
with open(os.path.join(OUTD, "det_density.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["method", "p", "density", "detect_rate", "n", "clean_fpr"])
    for r in rows: w.writerow([r[0], r[1], r[2], round(r[3], 4), r[4], round(c0, 4)])
with open(os.path.join(OUTD, "det_metrics.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metric", "value"])
    [w.writerow([k, v]) for k, v in [("pooled_auc", round(auc, 4)), ("youden_thr", best),
                                     ("TPR%", round(tp/(tp+fn)*100, 2)), ("FPR%", round(fp/(fp+tn)*100, 2)),
                                     ("acc%", round((tp+tn)/len(pool_y)*100, 2)),
                                     ("TNR%", round(tn/(tn+fp)*100, 2))]]
with open(os.path.join(OUTD, "det_confusion.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["label", "pred_clean", "pred_stego"])
    for i, lab in enumerate(["clean(0)", "stego(1)"]):
        w.writerow([lab, int(cm[i, 0]), int(cm[i, 1])])

# 图: ROC
fig, ax = plt.subplots(figsize=(5.2, 4.2))
ax.plot(fpr, tpr, "-", color="#1a73e8", lw=2, label=f"5-fold OOF CNN 拒空 (AUC={auc:.3f})")
ax.plot([0, 1], [0, 1], "--", color="#999", lw=1)
ax.set_xlabel("误报率 FPR"); ax.set_ylabel("检出率 TPR")
ax.set_title("nsF5/矩阵编码 隐写检测 ROC (在照分组 OOF)"); ax.legend(loc="lower right")
ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "det_roc.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "det_roc.svg")); plt.close(fig)

# 图: 按密度检出率 (块: 散点, 颜色按方法)
fig, ax = plt.subplots(figsize=(6.6, 4.0))
labels = {"nsF5": "#1a73e8", "matrix": "#c62828"}
for meth in labels:
    sub = [r for r in rows if r[0] == meth]
    if sub:
        ax.plot([r[2] for r in sub], [r[3]*100 for r in sub], "o-",
                color=labels[meth], label=meth)
ax.axhline(c0*100, color="#666", ls="--", lw=1)
ax.text(0.3, c0*100 + 2, f"干净误报 {c0*100:.0f}%", color="#666", fontsize=9)
ax.set_xlabel("含密密度 (density)"); ax.set_ylabel("检出率 %")
ax.set_title("按方法/密度的检出率 (Youden 阈值)")
ax.set_xlim(-0.02, 1.02); ax.grid(alpha=0.3); ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "det_density.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "det_density.svg")); plt.close(fig)
print("\nOK: det_roc/det_density 图与 CSV 已写出")