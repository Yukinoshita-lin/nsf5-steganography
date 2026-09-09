# -*- coding: utf-8 -*-
"""为教学手册(ch07/ch08 ML 部分)生成真实数据驱动的可视化图。

数据源: data/dataset.csv (v1, 11 维) / data/dataset_campus_v2_min.csv (v1.4, 143 维)
模型: 仅用于图 (LogisticRegression / RandomForest / GB / XGB), OOF 用 GroupKFold 按 photo_id 分组。
输出: teaching/web/{zh,en}/assets/*.png (英文/中文双语标签, 中文字体 fallback)

用法: python teaching/gen_ml_figures.py
"""
from __future__ import annotations
import os, sys, shutil
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

# ---------------- 双语标签 ----------------
L = {
    "zh": {
        "roc_auc": {
            "label": "OOF ROC (AUC = {:.3f})",
            "random": "随机瞎猜 (AUC = 0.5)",
            "youden": "Youden 点 ({:.2f}, {:.2f})",
            "annot": "最佳操作点\n检出={:.0%} 误报={:.0%}",
            "xlab": "误报率 False Positive Rate", "ylab": "检出率 True Positive Rate",
            "title": "图 7-6  隐写检测 ROC 曲线 + AUC\n(真实数据 · 11 维特征 · 按 photo_id 分组留出外折)",
        },
        "op_pts": {
            "thr": "阈值={:.1f}", "fpr": "误报={:.0%}", "tpr": "检出={:.0%}",
            "xlab": "误报率 FPR", "ylab": "检出率 TPR",
            "title": "图 7-7  ROC：阈值从 1→0 扫过，每个阈值对应曲线上一点",
            "xlab2": "判定阈值 Threshold", "ylab2": "比率",
            "title2": "同一阈值下的 FPR(●) 与 TPR(■)",
        },
        "sigmoid": {
            "z0": "z=0 → 概率=0.5 (一半一半)",
            "high": "分数高 → 概率高\n更像含密", "low": "分数低 → 概率低\n更像干净",
            "xlab": "线性得分 z = w·x + b", "ylab": "含密概率 p̂ = σ(z)",
            "title": "图 7-2  sigmoid：把无上界的得分压成 0~1 的概率",
        },
        "decision": {
            "border": "决策边界 50%", "clean": "干净 (label=0)", "stego": "含密 (label=1)",
            "xlab": "RS_Gn  (标准化)", "ylab": "chi2_pvalue  (标准化)",
            "title": "图 7-1  决策边界：逻辑回归把特征空间分成两类\n(真实数据 · 取两个特征示意)",
            "cbar": "含密概率",
        },
        "confusion": {
            "xlabels": ["判为干净", "判为含密"], "ylabels": ["真是干净", "真是含密"],
            "cell": [["TN\n正确拒绝", "FP\n误报"], ["FN\n漏报", "TP\n正确检出"]],
            "xlab": "模型预测", "ylab": "真实标签",
            "title": "图 7-5  混淆矩阵 (Youden 阈值={:.2f})\n真实数据 · 留出外折",
        },
        "loss": {
            "loss": "损失 L(w)", "gd": "梯度下降走法", "best": "最优 w* (损失最小)",
            "xlab": "参数 w", "ylab": "损失 L(w)",
            "title": "图 7-3  梯度下降：沿损失下降最快的方向一步步走到谷底",
        },
        "metrics": {
            "prec": "精确率 Precision", "rec": "召回率 Recall", "fpr": "误报率 FPR",
            "thr": "阈值=0.5", "xlab": "判定阈值 Threshold", "ylab": "比率",
            "title": "图 7-8  阈值怎么选：一条指标随阈值的完整变化\n(真实数据 · 同一组 OOF 概率)",
        },
        "importance": {
            "xlab": "逻辑回归系数 (标准化后, 越大越重要)",
            "title": "图 8-3  11 个特征谁更重要：LR 系数\n(正值→含密侧, 负值→干净侧)",
        },
        "feat_rs": {
            "gn": "Gn: 负掩码 RS 缺口 (核心信号)", "gr": "Gr: 正掩码 RS 缺口",
            "clean": "干净", "stego": "含密", "ylabel": "密度",
            "annot": "干净 Gn 偏高，含密 Gn 塌缩",
            "title": "图 8-1  RS 缺口特征分布：干净 vs 含密",
        },
        "feat_chi2": {
            "left": "chi2_stat: 卡方统计量", "right": "lsb_diff_entropy: LSB 差分熵",
            "clean": "干净", "stego": "含密", "ylab": "密度",
            "xlab_left": "卡方统计量 (对数)", "xlab_right": "熵 (0~1)",
            "title": "图 8-2  卡方/熵特征分布：干净 vs 含密",
        },
        "clf_compare": {
            "random": "随机 0.5", "xlab": "误报率 FPR", "ylab": "检出率 TPR",
            "title": "图 8-4  四种分类器横向比较 (5 折 GroupKFold OOF)\n真实数据 · 11 维特征",
        },
        "density": {
            "fmt": "{} p={} d={:.2f}", "xlab": "检出率 (Youden 阈值)", "ylab": "变体 (方法, p, 密度)",
            "title": "图 8-5  按方法/密度的检出率：越弱越难检出\n(真实数据 · 11 维 LR · 留出外折)",
        },
        "groupkfold": {
            "random": "随机切分：同一照片的 7 个变体可能被拆进不同折 → 数据泄漏",
            "grouped": "GroupKFold：同一照片的所有变体进同一折 → 阻止泄漏",
            "ylabel": "照片 (photo_id)", "title": "图 7-4  {}",
            "xlabel": "同一照片的 7 个变体（列）；颜色 = 所属折 fold",
        },
    },
    "en": {
        "roc_auc": {
            "label": "OOF ROC (AUC = {:.3f})",
            "random": "random guess (AUC = 0.5)",
            "youden": "Youden point ({:.2f}, {:.2f})",
            "annot": "Best operating point\ntpr={:.0%} fpr={:.0%}",
            "xlab": "False Positive Rate", "ylab": "True Positive Rate",
            "title": "Fig. 7-6  Steganalysis ROC curve + AUC\n(real data - 11 features - grouped held-out by photo_id)",
        },
        "op_pts": {
            "thr": "thr={:.1f}", "fpr": "FP={:.0%}", "tpr": "TP={:.0%}",
            "xlab": "false positive rate (FPR)", "ylab": "true positive rate (TPR)",
            "title": "Fig. 7-7  ROC: sweeping threshold from 1 to 0, each threshold is one point on the curve",
            "xlab2": "decision threshold", "ylab2": "rate",
            "title2": "FPR (dot) and TPR (square) at the same threshold",
        },
        "sigmoid": {
            "z0": "z=0 -> probability = 0.5 (half-half)",
            "high": "high score -> high prob\nmore stego", "low": "low score -> low prob\nmore clean",
            "xlab": "linear score z = w.x + b", "ylab": "stego prob p = sigmoid(z)",
            "title": "Fig. 7-2  sigmoid: squashing an unbounded score into a 0-1 probability",
        },
        "decision": {
            "border": "decision boundary 50%", "clean": "clean (label=0)", "stego": "stego (label=1)",
            "xlab": "RS_Gn  (standardized)", "ylab": "chi2_pvalue  (standardized)",
            "title": "Fig. 7-1  Decision boundary: logistic regression splits the feature space into two classes\n(real data - two illustrative features)",
            "cbar": "stego probability",
        },
        "confusion": {
            "xlabels": ["predicted clean", "predicted stego"], "ylabels": ["truly clean", "truly stego"],
            "cell": [["TN\ncorrect reject", "FP\nfalse positive"], ["FN\nmiss", "TP\ncorrect detect"]],
            "xlab": "model prediction", "ylab": "true label",
            "title": "Fig. 7-5  Confusion matrix (Youden threshold={:.2f})\nreal data - held-out OOF",
        },
        "loss": {
            "loss": "loss L(w)", "gd": "gradient descent steps", "best": "optimal w* (min loss)",
            "xlab": "parameter w", "ylab": "loss L(w)",
            "title": "Fig. 7-3  Gradient descent: walk step by step down the steepest direction of the loss",
        },
        "metrics": {
            "prec": "precision", "rec": "recall", "fpr": "false positive rate (FPR)",
            "thr": "threshold=0.5", "xlab": "decision threshold", "ylab": "rate",
            "title": "Fig. 7-8  Choosing a threshold: how each metric changes with the threshold\n(real data - same OOF probabilities)",
        },
        "importance": {
            "xlab": "logistic regression coefficient (standardized; larger = more important)",
            "title": "Fig. 8-3  Which of the 11 features matter most: LR coefficients\n(positive -> stego side, negative -> clean side)",
        },
        "feat_rs": {
            "gn": "Gn: Rs gap under the negative mask (core signal)", "gr": "Gr: Rs gap under the positive mask",
            "clean": "clean", "stego": "stego", "ylabel": "density",
            "annot": "clean Gn is high; stego Gn collapses",
            "title": "Fig. 8-1  RS gap feature distribution: clean vs stego",
        },
        "feat_chi2": {
            "left": "chi2_stat: chi-square statistic", "right": "lsb_diff_entropy: LSB difference entropy",
            "clean": "clean", "stego": "stego", "ylab": "density",
            "xlab_left": "chi-square statistic (log)", "xlab_right": "entropy (0-1)",
            "title": "Fig. 8-2  Chi-square / entropy feature distributions: clean vs stego",
        },
        "clf_compare": {
            "random": "random 0.5", "xlab": "false positive rate (FPR)", "ylab": "true positive rate (TPR)",
            "title": "Fig. 8-4  Four classifiers compared (5-fold GroupKFold OOF)\nreal data - 11 features",
        },
        "density": {
            "fmt": "{} p={} d={:.2f}", "xlab": "detection rate (Youden threshold)", "ylab": "variant (method, p, density)",
            "title": "Fig. 8-5  Detection rate by method/density: weaker is harder to catch\n(real data - 11-D LR - held-out OOF)",
        },
        "groupkfold": {
            "random": "random split: the 7 variants of the same photo can land in different folds -> data leakage",
            "grouped": "GroupKFold: all variants of a photo go into the same fold -> no leakage",
            "ylabel": "photo (photo_id)", "title": "Fig. 7-4  {}",
            "xlabel": "the 7 variants of the same photo (columns); color = fold",
        },
    },
}


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


def out(name: str, lang: str):
    path = os.path.join(ZH_ASSETS if lang == "zh" else EN_ASSETS, name)
    plt.savefig(path)
    plt.close("all")
    print(f"  [ok] {lang}/{name}  {os.path.getsize(path)//1024} KB")


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
def fig_roc_auc(d, feats, X, y, g, lang):
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
    S = L[lang]["roc_auc"]

    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    ax.plot(fpr, tpr, color=ACCENT, lw=2.2, label=S["label"].format(auc))
    ax.fill_between(fpr, tpr, alpha=0.15, color=ACCENT)
    ax.plot([0, 1], [0, 1], ls="--", color=GREY, lw=1.2, label=S["random"])
    ax.plot(fpr[bi], tpr[bi], "o", ms=9, color=WARM, zorder=5,
            label=S["youden"].format(fpr[bi], tpr[bi]))
    ax.annotate(S["annot"].format(tpr[bi], fpr[bi]),
                xy=(fpr[bi], tpr[bi]), xytext=(fpr[bi]+0.22, tpr[bi]-0.28),
                arrowprops=dict(arrowstyle="->", color=WARM), color=WARM, fontsize=9)
    ax.set_xlabel(S["xlab"])
    ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"])
    ax.legend(loc="lower right", fontsize=9)
    out("ml_roc_auc.png", lang)


# ----------------------------------------------------------------------
# 2) ROC 上的阈值操作点 + 副图: FPR/TPR 随阈值变化
# ----------------------------------------------------------------------
def fig_roc_operating_points(d, feats, X, y, g, lang):
    from sklearn.metrics import roc_curve, roc_auc_score
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    mask = ~np.isnan(p)
    fpr, tpr, th = roc_curve(y[mask], p[mask])
    S = L[lang]["op_pts"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    ax1.plot(fpr, tpr, color=ACCENT, lw=2)
    ax1.plot([0, 1], [0, 1], ls="--", color=GREY, lw=1)
    pts = [(0.3, GREEN), (0.5, ACCENT), (0.7, WARM)]
    # 注释从上到下间隔排列, 避免重叠(勘误: 图 7-7 "阈值/误报" 应从上到下间隔排列)
    for i, (tval, col) in enumerate(pts):
        idx = int(np.argmin(np.abs(th - tval)))
        ax1.plot(fpr[idx], tpr[idx], "o", ms=8, color=col, zorder=5)
        ax1.annotate(S["thr"].format(tval) + "  " + S["fpr"].format(fpr[idx]) + "  " + S["tpr"].format(tpr[idx]),
                     xy=(fpr[idx], tpr[idx]),
                     xytext=(min(0.32, fpr[idx]-0.28), 0.72 - 0.13*i),
                     color=col, fontsize=8,
                     arrowprops=dict(arrowstyle="->", color=col, lw=0.8))
        ax2.plot(tval, fpr[idx], "o", color=col, ms=6)
        ax2.plot(tval, tpr[idx], "s", color=col, ms=6)
    ax1.set_xlabel(S["xlab"]); ax1.set_ylabel(S["ylab"])
    ax1.set_title(S["title"])
    ax2.set_xlabel(S["xlab2"]); ax2.set_ylabel(S["ylab2"])
    ax2.set_title(S["title2"])
    ax2.grid(True, alpha=0.3)
    out("ml_roc_operating_points.png", lang)


# ----------------------------------------------------------------------
# 3) sigmoid 曲线
# ----------------------------------------------------------------------
def fig_sigmoid(lang):
    z = np.linspace(-6, 6, 400)
    p = 1 / (1 + np.exp(-z))
    S = L[lang]["sigmoid"]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot(z, p, color=ACCENT, lw=2.4)
    ax.axhline(0.5, ls=":", color=GREY, lw=1.2)
    ax.axvline(0, ls=":", color=GREY, lw=1.2)
    ax.plot([0], [0.5], "o", color=WARM, ms=8)
    ax.annotate(S["z0"], xy=(0, 0.5), xytext=(1.2, 0.66),
                arrowprops=dict(arrowstyle="->", color=WARM), fontsize=9)
    ax.fill_between(z, p, 0.5, where=(p >= 0.5), alpha=0.10, color=WARM)
    ax.fill_between(z, p, 0.5, where=(p < 0.5), alpha=0.10, color=ACCENT)
    ax.text(3, 0.05, S["high"], color=WARM, fontsize=9)
    ax.text(-5.8, 0.9, S["low"], color=ACCENT, fontsize=9)
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"])
    out("ml_sigmoid.png", lang)


# ----------------------------------------------------------------------
# 4) 决策边界 (真实两特征)
# ----------------------------------------------------------------------
def fig_decision_boundary(d, feats, X, y, g, lang):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    i = feats.index("RS_Gn"); j = feats.index("chi2_pvalue")
    X2 = X[:, [i, j]]
    sc = StandardScaler(); Xs = sc.fit_transform(X2)
    clf = LogisticRegression(max_iter=2000, C=1.0).fit(Xs, y)
    xx, yy = np.meshgrid(np.linspace(Xs[:, 0].min()-0.5, Xs[:, 0].max()+0.5, 200),
                         np.linspace(Xs[:, 1].min()-0.5, Xs[:, 1].max()+0.5, 200))
    Z = clf.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, 1].reshape(xx.shape)
    S = L[lang]["decision"]
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    cs = ax.contourf(xx, yy, Z, levels=np.linspace(0, 1, 21), cmap="RdYlBu", alpha=0.55)
    cf = ax.contour(xx, yy, Z, levels=[0.5], colors="k", linewidths=2)
    ax.clabel(cf, fmt={0.5: S["border"]}, fontsize=8)
    ax.scatter(Xs[y == 0, 0], Xs[y == 0, 1], s=8, alpha=0.55, color=ACCENT, label=S["clean"])
    ax.scatter(Xs[y == 1, 0], Xs[y == 1, 1], s=8, alpha=0.55, color=WARM, label=S["stego"])
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"])
    ax.legend(loc="best", fontsize=9)
    fig.colorbar(cs, ax=ax, fraction=0.046, pad=0.04).set_label(S["cbar"])
    out("ml_decision_boundary.png", lang)


# ----------------------------------------------------------------------
# 5) 混淆矩阵 (真实 OOF + Youden 阈值)
# ----------------------------------------------------------------------
def fig_confusion_matrix(d, feats, X, y, g, lang):
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
    S = L[lang]["confusion"]
    fig, ax = plt.subplots(figsize=(5.6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(S["xlabels"]); ax.set_yticklabels(S["ylabels"])
    for r in range(2):
        for c in range(2):
            ax.text(c, r, f"{S['cell'][r][c]}\n{cm[r][c]}", ha="center", va="center",
                    color="white" if cm[r][c] > cm.max()/2 else "black", fontsize=10)
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"].format(thr))
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    out("ml_confusion_matrix.png", lang)


# ----------------------------------------------------------------------
# 6) 损失 + 梯度下降 (概念性, 用凸损失示意)
# ----------------------------------------------------------------------
def fig_loss_descent(lang):
    w = np.linspace(-3, 3, 300)
    loss = (w - 1) ** 2 + 0.5
    S = L[lang]["loss"]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.plot(w, loss, color=ACCENT, lw=2.4, label=S["loss"])
    wcur, lr = -2.4, 0.28
    xs, ys = [], []
    for _ in range(16):
        xs.append(wcur); ys.append((wcur - 1) ** 2 + 0.5)
        wcur = wcur - lr * 2 * (wcur - 1)
    ax.plot(xs, ys, ".-", color=WARM, ms=7, lw=1.4, label=S["gd"])
    ax.axvline(1, ls=":", color=GREY)
    ax.annotate(S["best"], xy=(1, 0.5), xytext=(1.35, 3.5),
                arrowprops=dict(arrowstyle="->", color=GREY), fontsize=9)
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"])
    ax.legend(loc="upper center", fontsize=9)
    out("ml_loss_descent.png", lang)


# ----------------------------------------------------------------------
# 7) 指标随阈值变化 (真实 OOF)
# ----------------------------------------------------------------------
def fig_metrics_vs_threshold(d, feats, X, y, g, lang):
    from sklearn.metrics import roc_curve, precision_recall_curve
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    m = ~np.isnan(p); yy = y[m].astype(bool); pp = p[m]
    prec, rec, ths = precision_recall_curve(yy, pp)
    fpr, tpr, th = roc_curve(yy, pp)
    S = L[lang]["metrics"]
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    ax.plot(ths, prec[:-1], color=GREEN, lw=2, label=S["prec"])
    ax.plot(ths, rec[:-1], color=ACCENT, lw=2, label=S["rec"])
    ax.plot(th, fpr, color=WARM, lw=2, label=S["fpr"])
    ax.axvline(0.5, ls="--", color=GREY, lw=1.2)
    ax.annotate(S["thr"], xy=(0.5, 1.0), xytext=(0.52, 0.93), color=GREY, fontsize=9)
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"])
    ax.legend(loc="lower left", fontsize=9)
    ax.set_ylim(-0.03, 1.05)
    out("ml_metrics_vs_threshold.png", lang)


# ----------------------------------------------------------------------
# 8) LR 特征系数(重要度)
# ----------------------------------------------------------------------
def fig_feature_importance(d, feats, X, y, g, lang):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=0)).fit(X, y)
    coef = clf.named_steps["logisticregression"].coef_[0]
    order = np.argsort(np.abs(coef))[::-1]
    names = [feats[i] for i in order]; vals = [coef[i] for i in order]
    S = L[lang]["importance"]
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    cols = [WARM if v > 0 else ACCENT for v in vals]
    ax.barh(names[::-1], vals[::-1], color=cols[::-1])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel(S["xlab"])
    ax.set_title(S["title"])
    out("ml_feature_importance.png", lang)


# ----------------------------------------------------------------------
# 9-11) 特征分布 clean vs stego
# ----------------------------------------------------------------------
def fig_feat_hist(d, feats, lang):
    Srs = L[lang]["feat_rs"]; Schi = L[lang]["feat_chi2"]
    feats_cfg = [("RS_Gn", Srs["gn"], WARM), ("RS_Gr", Srs["gr"], GREEN)]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    for ax, (fname, title, col) in zip(axes, feats_cfg):
        v0 = d.loc[d["label"] == 0, fname].values
        v1 = d.loc[d["label"] == 1, fname].values
        ax.hist(v0, bins=40, alpha=0.6, color=ACCENT, label=Srs["clean"], density=True)
        ax.hist(v1, bins=40, alpha=0.6, color=col, label=Srs["stego"], density=True)
        ax.set_title(title); ax.set_xlabel(fname); ax.set_ylabel(Srs["ylabel"])
        ax.legend(fontsize=9, loc="upper right")
    # 注释移到第一个子图(Gn)图例下方, 避免与图例重叠(勘误: 图 8-1 "干净Gn" 应移动到图例下)
    axes[0].text(0.98, 0.74, Srs["annot"], transform=axes[0].transAxes, ha="right", va="top",
                 fontsize=9, color=WARM)
    fig.suptitle(Srs["title"], y=1.02)
    out("feat_rs.png", lang)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    # 左图用 chi2_stat(非退化, 真实可辨) 而非 chi2_pvalue(几乎全为 0, 导致"无图像")(勘误: 图 8-2 无图像)
    f1 = "chi2_stat"
    v0 = d.loc[d["label"] == 0, f1].values; v1 = d.loc[d["label"] == 1, f1].values
    logmin = -1.0
    lv0 = np.log10(np.maximum(v0, 1e-5)); lv1 = np.log10(np.maximum(v1, 1e-5))
    axes[0].hist(lv0, bins=40, alpha=0.6, color=ACCENT, label=Schi["clean"], density=True)
    axes[0].hist(lv1, bins=40, alpha=0.6, color=WARM, label=Schi["stego"], density=True)
    axes[0].set_title(Schi["left"]); axes[0].legend(fontsize=9); axes[0].set_xlabel(Schi["xlab_left"])
    f2 = "lsb_diff_entropy"; v0 = d.loc[d["label"] == 0, f2].values; v1 = d.loc[d["label"] == 1, f2].values
    axes[1].hist(v0, bins=40, alpha=0.6, color=ACCENT, label=Schi["clean"], density=True)
    axes[1].hist(v1, bins=40, alpha=0.6, color=WARM, label=Schi["stego"], density=True)
    axes[1].set_title(Schi["right"]); axes[1].legend(fontsize=9); axes[1].set_xlabel(Schi["xlab_right"])
    fig.suptitle(Schi["title"], y=1.02)
    out("feat_chi2_entropy.png", lang)


# ----------------------------------------------------------------------
# 12) 四分类器 ROC / AUC 对比 (真实 OOF)
# ----------------------------------------------------------------------
def fig_clf_compare(d, feats, X, y, g, lang):
    from sklearn.metrics import roc_curve, roc_auc_score
    oof = oof_probs(build_clf(), X, y, g, n_splits=5)
    S = L[lang]["clf_compare"]
    fig, ax = plt.subplots(figsize=(7.4, 5.4))
    colors = {"LR": ACCENT, "RF": GREEN, "GB": WARM, "XGB": "#9467bd"}
    for name, arr in oof.items():
        m = ~np.isnan(arr)
        fpr, tpr, _ = roc_curve(y[m], arr[m])
        auc = roc_auc_score(y[m], arr[m])
        ax.plot(fpr, tpr, lw=2, color=colors[name], label=f"{name}  AUC={auc:.3f}")
    ax.plot([0, 1], [0, 1], ls="--", color=GREY, lw=1, label=S["random"])
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_title(S["title"])
    ax.legend(loc="lower right", fontsize=9)
    out("ml_clf_compare_roc.png", lang)


# ----------------------------------------------------------------------
# 13) 按方法/密度检出率
# ----------------------------------------------------------------------
def fig_density_detection(d, feats, X, y, g, lang):
    from sklearn.metrics import roc_curve
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    p = oof_probs({"LR": lambda s=0: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=0.1, random_state=s))}, X, y, g)["LR"]
    m = ~np.isnan(p); yy = y[m]; pp = p[m]
    fpr, tpr, th = roc_curve(yy, pp); j = tpr - fpr
    thr = float(th[np.argmax(j)])
    dd = d.iloc[np.where(m)[0]].assign(_pred=(pp >= thr).astype(int))
    S = L[lang]["density"]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    rows = []
    for (meth, pv, dens), grp in dd.groupby(["method", "p", "density"]):
        if pd.isna(meth):
            continue
        rows.append((S["fmt"].format(meth, int(pv), float(dens)), grp["_pred"].mean()))
    rows.sort(key=lambda r: r[1])
    labels = [r[0] for r in rows]; vals = [r[1] for r in rows]
    cols = [WARM if v < 0.7 else GREEN for v in vals]
    ax.barh(labels, vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(v + 0.015, i, f"{v:.0%}", va="center", fontsize=8)
    ax.set_xlabel(S["xlab"]); ax.set_ylabel(S["ylab"])
    ax.set_xlim(0, 1.05)
    ax.set_title(S["title"])
    out("ml_density_detection.png", lang)


# ----------------------------------------------------------------------
# 14) GroupKFold 分组示意 (schematic)
# ----------------------------------------------------------------------
def fig_groupkfold(lang):
    n_photos = 12
    S = L[lang]["groupkfold"]
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 5.8), sharex=True)
    for ax, mode in zip(axes, ["random", "grouped"]):
        if mode == "random":
            fold = np.random.default_rng(7).integers(0, 5, (n_photos, 7))
            title_s = S["random"]
        else:
            fold = np.tile((np.arange(n_photos) % 5)[:, None], (1, 7))
            title_s = S["grouped"]
        im = ax.imshow(fold, cmap="tab20", aspect="auto")
        ax.set_ylabel(S["ylabel"], fontsize=9)
        ax.yaxis.set_ticks(np.arange(n_photos))
        ax.yaxis.set_ticklabels([f"P{i+1}" for i in range(n_photos)], fontsize=6.5)
        ax.set_title(S["title"].format(title_s), fontsize=9.5)
        for x in range(1, 7):
            ax.axvline(x - 0.5, color="white", lw=1.2)
    axes[1].set_xlabel(S["xlabel"], fontsize=9)
    fig.tight_layout()
    out("ml_groupkfold.png", lang)


def main():
    os.makedirs(ZH_ASSETS, exist_ok=True); os.makedirs(EN_ASSETS, exist_ok=True)
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    setstyle()
    d, feats, X, y, g = load()
    print("载入", DATA, "shape", X.shape, "feat", len(feats))
    print("生成中...")
    for lang in ("zh", "en"):
        fig_roc_auc(d, feats, X, y, g, lang)
        fig_roc_operating_points(d, feats, X, y, g, lang)
        fig_sigmoid(lang)
        fig_decision_boundary(d, feats, X, y, g, lang)
        fig_confusion_matrix(d, feats, X, y, g, lang)
        fig_loss_descent(lang)
        fig_metrics_vs_threshold(d, feats, X, y, g, lang)
        fig_feature_importance(d, feats, X, y, g, lang)
        fig_feat_hist(d, feats, lang)
        fig_clf_compare(d, feats, X, y, g, lang)
        fig_density_detection(d, feats, X, y, g, lang)
        fig_groupkfold(lang)
    print("完成。查看", ZH_ASSETS)


if __name__ == "__main__":
    main()
