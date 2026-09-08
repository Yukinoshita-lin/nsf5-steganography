# -*- coding: utf-8 -*-
"""为教学手册(ch07/ch08 ML 部分)生成真实数据驱动的可视化图。

数据源: data/dataset.csv (v1, 11 维) / data/dataset_campus_v2_min.csv (v1.4, 143 维)
模型: 仅用于图 (LogisticRegression / RandomForest / GB / XGB), OOF 用 GroupKFold 按 photo_id 分组。
输出: teaching/web/{zh,en}/assets/*.png (英文/中文双语标签, 中文字体 fallback)

用法: python teaching/gen_ml_figures.py
"""
from __future__ import annotations
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "dataset.csv")
ZH_ASSETS = os.path.join(ROOT, "teaching", "web", "zh", "assets")
EN_ASSETS = os.path.join(ROOT, "teaching", "web", "en", "assets")
META = {"label", "photo_id", "variant", "method", "p", "density", "changed_frac"}

# 中文字体(双语标签), 找不到就退回默认
_avail = {f.name for f in font_manager.fontManager.ttflist}
for _cand in ["Microsoft YaHei", "SimHei", "DengXian", "SimSun"]:
    if _cand in _avail:
        plt.rcParams["font.family"] = [_cand, "DejaVu Sans"]
        break
plt.rcParams["font.sans-serif"] = [plt.rcParams["font.family"][0], "DejaVu Sans"] if isinstance(plt.rcParams["font.family"], list) else plt.rcParams["font.family"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["savefig.bbox"] = "tight"
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150

ACCENT = "#1f77b4"; WARM = "#d62728"; GREEN = "#2ca02c"; GREY = "#7f7f7f"


def setstyle():
    for s in ["seaborn-v0_8-whitegrid", "seaborn-whitegrid", "ggplot"]:
        try:
            plt.style.use(s); break
        except Exception:
            continue
    # 关键：主题会覆盖字体为 Arial(sans-serif)，必须把中文字体放优先位置
    _cjk = None
    for _cand in ["Microsoft YaHei", "SimHei", "DengXian", "SimSun"]:
        if _cand in _avail:
            _cjk = _cand; break
    if _cjk:
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [_cjk, "DejaVu Sans"]
        plt.rcParams["font.family"] = [_cjk, "DejaVu Sans"]


def out(name: str):
    path = os.path.join(ZH_ASSETS, name)
    plt.savefig(path)
    plt.close("all")
    # 同步到英文册
    import shutil
    shutil.copy(path, os.path.join(EN_ASSETS, name))
    print(f"  [ok] {name}  {os.path.getsize(path)//1024} KB")


def load(which="v1"):
    d = pd.read_csv(DATA)
    feats = [c for c in d.columns if c not in META]
    X = d[feats].values.astype(np.float64)
    y = d["label"].values.astype(np.int64)
    g = d["photo_id"].values
    return d, feats, X, y, g


def oof_probs(make_clf, X, y, g, n_splits=5, seed=0):
    from sklearn.model_selection import GroupKFold
    gkf = GroupKFold(n_splits=n_splits)
    oof = {}
    for tr, va in gkf.split(X, y, g):
        for name, mk in make_clf.items():
            if name not in oof:
                oof[name] = np.full(len(X), np.nan)
            clf = mk(seed)
            clf.fit(X[tr], y[tr])
            oof[name][va] = clf.predict_proba(X[va])[:, 1]
    return oof


def build_clf(make=True):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from xgboost import XGBClassifier
    return {
        "LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s)),
        "RF": lambda s=0: RandomForestClassifier(n_estimators=200, max_depth=None, n_jobs=-1, random_state=s),
        "GB": lambda s=0: GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=s),
        "XGB": lambda s=0: XGBClassifier(n_estimators=200, learning_rate=0.05, max_depth=4, subsample=0.9,
                                         colsample_bytree=0.8, eval_metric="logloss",
                                         random_state=s),
    }


# ----------------------------------------------------------------------
# 1) ROC + AUC (真实数据, GroupKFold OOF)
# ----------------------------------------------------------------------
def fig_roc_auc(d, feats, X, y, g):
    from sklearn.metrics import roc_curve, roc_auc_score
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    def _lr(s=0): return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))
    p = oof_probs({"LR": _lr}, X, y, g)["LR"]
    mask = ~np.isnan(p)
    fpr, tpr, th = roc_curve(y[mask], p[mask])
    auc = roc_auc_score(y[mask], p[mask])
    j = tpr - fpr
    bi = int(np.argmax(j))

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.plot(fpr, tpr, color=ACCENT, lw=2.2, label=f"OOF ROC (AUC = {auc:.3f})")
    ax.fill_between(fpr, tpr, alpha=0.15, color=ACCENT)
    ax.plot([0, 1], [0, 1], ls="--", color=GREY, lw=1.2, label="随机瞎猜 (AUC = 0.5)") 
    ax.plot(fpr[bi], tpr[bi], "o", ms=9, color=WARM, zorder=5,
            label=f"Youden 点 ({fpr[bi]:.2f}, {tpr[bi]:.2f})")
    ax.annotate(f"最佳操作点\n检出={tpr[bi]:.0%} 误报={fpr[bi]:.0%}",
                xy=(fpr[bi], tpr[bi]), xytext=(fpr[bi]+0.22, tpr[bi]-0.28),
                arrowprops=dict(arrowstyle="->", color=WARM), color=WARM, fontsize=9)
    ax.set_xlabel("误报率 False Positive Rate")
    ax.set_ylabel("检出率 True Positive Rate")
    ax.set_title("图 7-6  隐写检测 ROC 曲线 + AUC\n(真实数据 · 11 维特征 · 按 photo_id 分组留出外折)")
    ax.legend(loc="lower right", fontsize=9)
    out("ml_roc_auc.png")


# ----------------------------------------------------------------------
# 2) ROC 上的阈值操作点 + 副图: FPR/TPR 随阈值变化
# ----------------------------------------------------------------------
def fig_roc_operating_points(d, feats, X, y, g):
    from sklearn.metrics import roc_curve, roc_auc_score
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    mask = ~np.isnan(p)
    fpr, tpr, th = roc_curve(y[mask], p[mask])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    ax1.plot(fpr, tpr, color=ACCENT, lw=2)
    ax1.plot([0, 1], [0, 1], ls="--", color=GREY, lw=1)
    for tval, col in [(0.3, GREEN), (0.5, ACCENT), (0.7, WARM)]:
        idx = int(np.argmin(np.abs(th - tval)))
        ax1.plot(fpr[idx], tpr[idx], "o", ms=8, color=col, zorder=5)
        ax1.annotate(f"阈值={tval:.1f}\n误报={fpr[idx]:.0%} 检出={tpr[idx]:.0%}",
                     xy=(fpr[idx], tpr[idx]), xytext=(fpr[idx]+0.03, tpr[idx]-0.18),
                     color=col, fontsize=8)
        ax2.plot(tval, fpr[idx], "o", color=col, ms=6)
        ax2.plot(tval, tpr[idx], "s", color=col, ms=6)
    ax1.set_xlabel("误报率 FPR"); ax1.set_ylabel("检出率 TPR")
    ax1.set_title("图 7-7  ROC：阈值从 1→0 扫过，每个阈值对应曲线上一点")
    ax2.set_xlabel("判定阈值 Threshold"); ax2.set_ylabel("比率")
    ax2.set_title("同一阈值下的 FPR(●) 与 TPR(■)")
    ax2.grid(True, alpha=0.3)
    out("ml_roc_operating_points.png")


# ----------------------------------------------------------------------
# 3) sigmoid 曲线
# ----------------------------------------------------------------------
def fig_sigmoid():
    z = np.linspace(-6, 6, 400)
    p = 1 / (1 + np.exp(-z))
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot(z, p, color=ACCENT, lw=2.4)
    ax.axhline(0.5, ls=":", color=GREY, lw=1.2)
    ax.axvline(0, ls=":", color=GREY, lw=1.2)
    ax.plot([0], [0.5], "o", color=WARM, ms=8)
    ax.annotate("z=0 → 概率=0.5 (一半一半)", xy=(0, 0.5), xytext=(1.2, 0.66),
                arrowprops=dict(arrowstyle="->", color=WARM), fontsize=9)
    ax.fill_between(z, p, 0.5, where=(p >= 0.5), alpha=0.10, color=WARM)
    ax.fill_between(z, p, 0.5, where=(p < 0.5), alpha=0.10, color=ACCENT)
    ax.text(3, 0.05, "分数高 → 概率高\n更像含密", color=WARM, fontsize=9)
    ax.text(-5.8, 0.9, "分数低 → 概率低\n更像干净", color=ACCENT, fontsize=9)
    ax.set_xlabel("线性得分 z = w·x + b")
    ax.set_ylabel("含密概率 p̂ = σ(z)")
    ax.set_title("图 7-2  sigmoid：把无上界的得分压成 0~1 的概率")
    out("ml_sigmoid.png")


# ----------------------------------------------------------------------
# 4) 决策边界 (真实两特征)
# ----------------------------------------------------------------------
def fig_decision_boundary(d, feats, X, y, g):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    i = feats.index("RS_Gn"); j = feats.index("chi2_pvalue")
    X2 = X[:, [i, j]]
    sc = StandardScaler(); Xs = sc.fit_transform(X2)
    clf = LogisticRegression(max_iter=2000, C=1.0).fit(Xs, y)
    xx, yy = np.meshgrid(np.linspace(Xs[:, 0].min()-0.5, Xs[:, 0].max()+0.5, 200),
                         np.linspace(Xs[:, 1].min()-0.5, Xs[:, 1].max()+0.5, 200))
    Z = clf.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, 1].reshape(xx.shape)
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    cs = ax.contourf(xx, yy, Z, levels=np.linspace(0, 1, 21), cmap="RdYlBu", alpha=0.55)
    cf = ax.contour(xx, yy, Z, levels=[0.5], colors="k", linewidths=2)
    ax.clabel(cf, fmt={0.5: "决策边界 50%"}, fontsize=8)
    ax.scatter(Xs[y == 0, 0], Xs[y == 0, 1], s=8, alpha=0.55, color=ACCENT, label="干净 (label=0)")
    ax.scatter(Xs[y == 1, 0], Xs[y == 1, 1], s=8, alpha=0.55, color=WARM, label="含密 (label=1)")
    ax.set_xlabel(f"RS_Gn  (标准化)")
    ax.set_ylabel(f"chi2_pvalue  (标准化)")
    ax.set_title("图 7-1  决策边界：逻辑回归把特征空间分成两类\n(真实数据 · 取两个特征示意)")
    ax.legend(loc="best", fontsize=9)
    fig.colorbar(cs, ax=ax, fraction=0.046, pad=0.04).set_label("含密概率")
    out("ml_decision_boundary.png")


# ----------------------------------------------------------------------
# 5) 混淆矩阵 (真实 OOF + Youden 阈值)
# ----------------------------------------------------------------------
def fig_confusion_matrix(d, feats, X, y, g):
    from sklearn.metrics import roc_curve, confusion_matrix
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    mask = ~np.isnan(p)
    fpr, tpr, th = roc_curve(y[mask], p[mask]); j = tpr - fpr
    thr = float(th[np.argmax(j)])
    pred = (p[mask] >= thr).astype(int)
    cm = confusion_matrix(y[mask], pred)
    fig, ax = plt.subplots(figsize=(5.6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["判为干净", "判为含密"]); ax.set_yticklabels(["真是干净", "真是含密"])
    labels = [["TN\n正确拒绝", "FP\n误报"], ["FN\n漏报", "TP\n正确检出"]]
    for r in range(2):
        for c in range(2):
            ax.text(c, r, f"{labels[r][c]}\n{cm[r][c]}", ha="center", va="center",
                    color="white" if cm[r][c] > cm.max()/2 else "black", fontsize=10)
    ax.set_xlabel("模型预测"); ax.set_ylabel("真实标签")
    ax.set_title(f"图 7-5  混淆矩阵 (Youden 阈值={thr:.2f})\n真实数据 · 留出外折")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    out("ml_confusion_matrix.png")


# ----------------------------------------------------------------------
# 6) 损失 + 梯度下降 (概念性, 用凸损失示意)
# ----------------------------------------------------------------------
def fig_loss_descent():
    w = np.linspace(-3, 3, 300)
    loss = (w - 1) ** 2 + 0.5
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot(w, loss, color=ACCENT, lw=2.4, label="损失 L(w)")
    # gradient descent steps (learning rate 0.3)
    wcur, lr = -2.4, 0.28
    xs, ys = [], []
    for _ in range(16):
        xs.append(wcur); ys.append((wcur - 1) ** 2 + 0.5)
        wcur = wcur - lr * 2 * (wcur - 1)
    ax.plot(xs, ys, ".-", color=WARM, ms=7, lw=1.4, label="梯度下降走法")
    ax.axvline(1, ls=":", color=GREY)
    ax.annotate("最优 w* (损失最小)", xy=(1, 0.5), xytext=(1.35, 3.5),
                arrowprops=dict(arrowstyle="->", color=GREY), fontsize=9)
    ax.set_xlabel("参数 w"); ax.set_ylabel("损失 L(w)")
    ax.set_title("图 7-3  梯度下降：沿损失下降最快的方向一步步走到谷底")
    ax.legend(loc="upper center", fontsize=9)
    out("ml_loss_descent.png")


# ----------------------------------------------------------------------
# 7) 指标随阈值变化 (真实 OOF)
# ----------------------------------------------------------------------
def fig_metrics_vs_threshold(d, feats, X, y, g):
    from sklearn.metrics import roc_curve, precision_recall_curve
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    m = ~np.isnan(p); yy = y[m].astype(bool); pp = p[m]
    prec, rec, ths = precision_recall_curve(yy, pp)
    fpr, tpr, th = roc_curve(yy, pp)
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    ax.plot(ths, prec[:-1], color=GREEN, lw=2, label="精确率 Precision")
    ax.plot(ths, rec[:-1], color=ACCENT, lw=2, label="召回率 Recall")
    ax.plot(th, fpr, color=WARM, lw=2, label="误报率 FPR")
    ax.axvline(0.5, ls="--", color=GREY, lw=1.2)
    ax.annotate("阈值=0.5", xy=(0.5, 1.0), xytext=(0.52, 0.93), color=GREY, fontsize=9)
    ax.set_xlabel("判定阈值 Threshold"); ax.set_ylabel("比率")
    ax.set_title("图 7-8  阈值怎么选：一条指标随阈值的完整变化\n(真实数据 · 同一组 OOF 概率)")
    ax.legend(loc="lower left", fontsize=9)
    ax.set_ylim(-0.03, 1.05)
    out("ml_metrics_vs_threshold.png")


# ----------------------------------------------------------------------
# 8) LR 特征系数(重要度)
# ----------------------------------------------------------------------
def fig_feature_importance(d, feats, X, y, g):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=0)).fit(X, y)
    coef = clf.named_steps["logisticregression"].coef_[0]
    order = np.argsort(np.abs(coef))[::-1]
    names = [feats[i] for i in order]; vals = [coef[i] for i in order]
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    cols = [WARM if v > 0 else ACCENT for v in vals]
    ax.barh(names[::-1], vals[::-1], color=cols[::-1])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("逻辑回归系数 (标准化后, 越大越重要)")
    ax.set_title("图 8-3  11 个特征谁更重要：LR 系数\n(正值→含密侧, 负值→干净侧)")
    out("ml_feature_importance.png")


# ----------------------------------------------------------------------
# 9-11) 特征分布 clean vs stego
# ----------------------------------------------------------------------
def fig_feat_hist(d, feats):
    feats_cfg = [("RS_Gn", "Gn: 负掩码 RS 缺口 (核心信号)", WARM),
                 ("RS_Gr", "Gr: 正掩码 RS 缺口", GREEN)]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    for ax, (fname, title, col) in zip(axes, feats_cfg):
        v0 = d.loc[d["label"] == 0, fname].values
        v1 = d.loc[d["label"] == 1, fname].values
        ax.hist(v0, bins=40, alpha=0.6, color=ACCENT, label="干净", density=True)
        ax.hist(v1, bins=40, alpha=0.6, color=col, label="含密", density=True)
        ax.set_title(title); ax.set_xlabel(fname); ax.set_ylabel("密度")
        ax.legend(fontsize=9)
    axes[0].annotate("干净 Gn 偏高, 含密 Gn 塌缩", xy=(0.05, 0.85), xycoords="axes fraction", fontsize=9, color=WARM)
    fig.suptitle("图 8-1  RS 缺口特征分布：干净 vs 含密", y=1.02)
    out("feat_rs.png")

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    f1 = "chi2_pvalue"; v0 = d.loc[d["label"] == 0, f1].values; v1 = d.loc[d["label"] == 1, f1].values
    axes[0].hist(v0, bins=40, alpha=0.6, color=ACCENT, label="干净", density=True)
    axes[0].hist(v1, bins=40, alpha=0.6, color=WARM, label="含密", density=True)
    axes[0].set_title("chi2_pvalue: 卡方 p 值"); axes[0].legend(fontsize=9); axes[0].set_xlabel("p 值")
    f2 = "lsb_diff_entropy"; v0 = d.loc[d["label"] == 0, f2].values; v1 = d.loc[d["label"] == 1, f2].values
    axes[1].hist(v0, bins=40, alpha=0.6, color=ACCENT, label="干净", density=True)
    axes[1].hist(v1, bins=40, alpha=0.6, color=WARM, label="含密", density=True)
    axes[1].set_title("lsb_diff_entropy: LSB 差分熵"); axes[1].legend(fontsize=9); axes[1].set_xlabel("熵 (0~1)")
    fig.suptitle("图 8-2  卡方/熵特征分布：干净 vs 含密", y=1.02)
    out("feat_chi2_entropy.png")


# ----------------------------------------------------------------------
# 12) 四分类器 ROC / AUC 对比 (真实 OOF)
# ----------------------------------------------------------------------
def fig_clf_compare(d, feats, X, y, g):
    from sklearn.metrics import roc_curve, roc_auc_score
    oof = oof_probs(build_clf(), X, y, g, n_splits=5)
    fig, ax = plt.subplots(figsize=(7.4, 5.4))
    colors = {"LR": ACCENT, "RF": GREEN, "GB": WARM, "XGB": "#9467bd"}
    for name, arr in oof.items():
        m = ~np.isnan(arr)
        fpr, tpr, _ = roc_curve(y[m], arr[m])
        auc = roc_auc_score(y[m], arr[m])
        ax.plot(fpr, tpr, lw=2, color=colors[name], label=f"{name}  AUC={auc:.3f}")
    ax.plot([0, 1], [0, 1], ls="--", color=GREY, lw=1, label="随机 0.5")
    ax.set_xlabel("误报率 FPR"); ax.set_ylabel("检出率 TPR")
    ax.set_title("图 8-4  四种分类器横向比较 (5 折 GroupKFold OOF)\n真实数据 · 11 维特征")
    ax.legend(loc="lower right", fontsize=9)
    out("ml_clf_compare_roc.png")


# ----------------------------------------------------------------------
# 13) 按方法/密度检出率
# ----------------------------------------------------------------------
def fig_density_detection(d, feats, X, y, g):
    from sklearn.metrics import roc_curve
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    m = ~np.isnan(p); yy = y[m]; pp = p[m]
    fpr, tpr, th = roc_curve(yy, pp); j = tpr - fpr
    thr = float(th[np.argmax(j)])
    dd = d.iloc[np.where(m)[0]].assign(_pred=(pp >= thr).astype(int))
    fig, ax = plt.subplots(figsize=(10, 5.2))
    rows = []
    for (meth, pv, dens), grp in dd.groupby(["method", "p", "density"]):
        if pd.isna(meth):
            continue
        rows.append((f"{meth} p={int(pv)} d={float(dens):.2f}", grp["_pred"].mean()))
    rows.sort(key=lambda r: r[1])
    labels = [r[0] for r in rows]; vals = [r[1] for r in rows]
    cols = [WARM if v < 0.7 else GREEN for v in vals]
    ax.barh(labels, vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(v + 0.015, i, f"{v:.0%}", va="center", fontsize=8)
    ax.set_xlabel("检出率 (Youden 阈值)"); ax.set_ylabel("变体 (方法, p, 密度)")
    ax.set_xlim(0, 1.05)
    ax.set_title("图 8-5  按方法/密度的检出率：越弱越难检出\n(真实数据 · 11 维 LR · 留出外折)")
    out("ml_density_detection.png")


# ----------------------------------------------------------------------
# 14) GroupKFold 分组示意 (schematic)
# ----------------------------------------------------------------------
def fig_groupkfold():
    n_photos = 12
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 5.8), sharex=True)
    for ax, mode in zip(axes, ["random", "grouped"]):
        if mode == "random":
            # 随机切分：每一个"变体"(列) 独立随机进折 → 同一张照片的 7 个变体可能落进不同折
            fold = np.random.default_rng(7).integers(0, 5, (n_photos, 7))
            title = "随机切分：同一照片的 7 个变体可能被拆进不同折 → 数据泄漏"
        else:
            # GroupKFold：同一张照片的所有变体进同一折
            fold = np.tile((np.arange(n_photos) % 5)[:, None], (1, 7))
            title = "GroupKFold：同一照片的所有变体进同一折 → 阻止泄漏"
        im = ax.imshow(fold, cmap="tab20", aspect="auto")
        ax.set_ylabel("照片 (photo_id)", fontsize=9)
        ax.yaxis.set_ticks(np.arange(n_photos))
        ax.yaxis.set_ticklabels([f"P{i+1}" for i in range(n_photos)], fontsize=6.5)
        ax.set_title(f"图 7-4  {title}", fontsize=9.5)
        for x in range(1, 7):
            ax.axvline(x - 0.5, color="white", lw=1.2)
    axes[1].set_xlabel("同一照片的 7 个变体（列）；颜色 = 所属折 fold", fontsize=9)
    fig.tight_layout()
    path = os.path.join(ZH_ASSETS, "ml_groupkfold.png")
    plt.savefig(path)
    import shutil
    shutil.copy(path, os.path.join(EN_ASSETS, "ml_groupkfold.png"))
    plt.close("all")
    print("  [ok] ml_groupkfold.png")


def main():
    os.makedirs(ZH_ASSETS, exist_ok=True); os.makedirs(EN_ASSETS, exist_ok=True)
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    setstyle()
    d, feats, X, y, g = load()
    print("载入", DATA, "shape", X.shape, "feat", len(feats))
    print("生成中...")
    fig_roc_auc(d, feats, X, y, g)
    fig_roc_operating_points(d, feats, X, y, g)
    fig_sigmoid()
    fig_decision_boundary(d, feats, X, y, g)
    fig_confusion_matrix(d, feats, X, y, g)
    fig_loss_descent()
    fig_metrics_vs_threshold(d, feats, X, y, g)
    fig_feature_importance(d, feats, X, y, g)
    fig_feat_hist(d, feats)
    fig_clf_compare(d, feats, X, y, g)
    fig_density_detection(d, feats, X, y, g)
    fig_groupkfold()
    print("完成。查看", ZH_ASSETS)


if __name__ == "__main__":
    main()
