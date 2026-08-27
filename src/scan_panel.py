"""隐写分析参数扫描面板 —— 逻辑。

对当前载入图, 按一组 payload(density 0→max) 逐档生成对应密度的含密图,
实时重算三类可观测量:
  - 卡方检验 p 值 (越小越异常);
  - RS 分析估计嵌入率（%）;
  - ML 分类含密概率(%)。
并绘制 3 子图。说明: 单图无"真 AUC"(AUC 需正/负样本集合),
此处以 ML 概率曲线作为区分能力趋势示意。
"""
from __future__ import annotations
import os
import numpy as np
from ns5_core import embed_string
import steganalysis as SA
from ml_predict import get_predictor


def capacity_bytes(npix: int, p: int) -> int:
    cap_bits = npix * p // ((1 << p) - 1)
    return max(1, cap_bits // 8)


def embed_by_density(image, density: float, method="nsF5", p=3, password=""):
    """按"占容量比例"密度嵌入伪随机块, 返回 (含密图, 嵌入比特数)。"""
    a = np.asarray(image, dtype=np.uint8)
    if density <= 1e-9:
        return a.copy(), 0
    nbytes = int(capacity_bytes(a.size, p) * density)
    if nbytes <= 0:
        return a.copy(), 0
    stego, _rep, nb = embed_string(a, "S" * nbytes, method=method, p=p, password=password)
    return stego, nb


def scan_curves(image, method="nsF5", p=3, password="",
                densities=(0.0, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4)):
    """返回 dict: densities, chi2_pvalue, rs_rate, ml_proba(%)."""
    pred = get_predictor(sensitivity="均衡")
    D, chi, est, ml = [], [], [], []
    for dd in densities:
        st = image if dd <= 1e-9 else embed_by_density(image, dd, method, p, password)[0]
        r = SA.analyze(st)
        rep = pred.predict(st)
        D.append(float(dd))
        chi.append(float(r["chi2_pvalue"]))
        est.append(float(r["est_rate"]) * 100.0)
        ml.append(float(rep["probability"] * 100.0) if rep["probability"] is not None
                  else float("nan"))
    return dict(densities=np.asarray(D), chi2_pvalue=np.asarray(chi),
                rs_rate=np.asarray(est), ml_proba=np.asarray(ml))


def plot_scan(res, path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = res["densities"]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.1))
    axes[0].plot(x, res["chi2_pvalue"], "-o", color="#c62828", lw=1.6, ms=4)
    axes[0].axhline(0.05, color="#666", ls="--", lw=1)
    axes[0].set_title("卡方检验 p 值", fontsize=10)
    axes[0].set_xlabel("payload (density)")
    axes[0].set_ylabel("p 值")
    axes[1].plot(x, res["rs_rate"], "-o", color="#1565c0", lw=1.6, ms=4)
    axes[1].set_title("RS 估计嵌入率 (%)", fontsize=10)
    axes[1].set_xlabel("payload (density)")
    axes[1].set_ylabel("估计率 %")
    axes[2].plot(x, res["ml_proba"], "-o", color="#2e7d32", lw=1.6, ms=4)
    axes[2].set_title("ML 含密概率 (%)", fontsize=10)
    axes[2].set_xlabel("payload (density)")
    axes[2].set_ylabel("概率 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.suptitle("隐写分析随载荷的变化 (单图; ML 概率为区分趋势示意, 非真 AUC)", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path