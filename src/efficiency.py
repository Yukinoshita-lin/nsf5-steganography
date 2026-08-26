"""
码族与嵌入效率绘图 (Code Family & Embedding Efficiency)。

理论
----
汉明码族 [n,k,d]: n = 2^p - 1, k = n - p, d = 3, 码率 R = k/n。
矩阵嵌入(伴随式编码): 每块 n=2^p-1 个系数嵌入 p 比特, 至多改 1 个系数。
   · 需要改动的概率 = (2^p - 1)/2^p (伴随式不中的情形)
   · 每块平均改动 = (2^p-1)/2^p
   · 嵌入效率 α(p) = p / E[改动] = p·2^p / (2^p - 1)
     — F5 因收缩重嵌实际低于该值; nsF5 无收缩, 实测接近该理论上限。
"""

from __future__ import annotations
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ns5_core import embed_string

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")


def theoretical_code_family(p_max=8):
    """返回 码族 与 理论嵌入效率 表。"""
    ps = list(range(1, p_max + 1))
    rows = []
    for p in ps:
        n = (1 << p) - 1
        k = n - p
        R = k / n
        alpha = (p * (1 << p)) / ((1 << p) - 1)   # 理论嵌入效率
        rows.append({"p": p, "n": n, "k": k, "code_rate": R, "alpha": alpha})
    return rows


def measured_efficiency(p, img_size=(256, 256), rng=None):
    """实测 nsF5 嵌入效率 = 嵌入比特 / 改动系数 (经高层哈希自同步流程)。"""
    if rng is None:
        rng = np.random.default_rng(p)
    img = rng.integers(0, 256, img_size, dtype=np.uint8)
    n = (1 << p) - 1
    capacity = (img.size // n) * p
    text = "A" * max(1, min(55000, (capacity // 8) - 8))  # 填充至接近容量(受ASCII长度限制)
    stego, report, nb = embed_string(img, text, method="nsF5", p=p)
    changed = report["cover_changed"]
    eff = nb / changed if changed else 0.0
    return nb, changed, eff


def compute_comparison(p_max=6, img_size=(256, 256)):
    """计算理论 vs 实测 嵌入效率。"""
    rows = theoretical_code_family(p_max)
    rng = np.random.default_rng(2026)
    for r in rows:
        _, changed, eff = measured_efficiency(r["p"], img_size, rng)
        r["measured_alpha"] = eff
        r["measured_changed"] = changed
    return rows


def plot_code_family_and_efficiency(p_max=6, save_path=None, dpi=120):
    """绘制 (a) 汉明码族 (b) 理论 vs 实测嵌入效率。
    save_path 为 None 时保存到 项目/output/efficiency.png。"""
    if save_path is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        save_path = os.path.join(OUTPUT_DIR, "efficiency.png")
    rows = compute_comparison(p_max)
    ps = np.array([r["p"] for r in rows])
    n_arr = np.array([r["n"] for r in rows])
    k_arr = np.array([r["k"] for r in rows])
    alpha_t = np.array([r["alpha"] for r in rows])
    alpha_m = np.array([r["measured_alpha"] for r in rows])

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    ax.plot(ps, n_arr, "o-", label="码字长 n=2$^p$-1")
    ax.plot(ps, k_arr, "s--", label="信息位 k=n-p")
    ax.plot(ps, k_arr / n_arr, "^-.", label="码率 R=k/n (右轴同刻度, 值/100)")
    ax.set_xlabel("参数 p (每块嵌入比特数)")
    ax.set_ylabel("码长度")
    ax.set_title("二元汉明码族 [n,k,3]")
    ax.grid(True, alpha=0.3)
    ax.legend()

    ax2 = axes[1]
    ax2.plot(ps, alpha_t, "o-", label="理论嵌入效率 F5(矩阵编码) α=p·2$^p$/(2$^p$-1)", markersize=7)
    ax2.plot(ps, alpha_m, "s--", label="实测 nsF5 (减幅+湿纸, 本实现)", markersize=7)
    ax2.axhline(2.0, color="gray", ls=":", lw=1)
    ax2.text(ps[0], 2.06, "LSB 朴素嵌入效率=2 (1bit/1可用bit)", color="gray", fontsize=8)
    ax2.set_xlabel("参数 p (每块嵌入比特数)")
    ax2.set_ylabel("嵌入效率 (embedded bits per change)")
    ax2.set_title("嵌入效率: 理论 vs 实测 nsF5")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    fig.suptitle("码族与嵌入效率 (nsF5 / 伴随式汉明矩阵编码)", fontsize=13, y=1.02)
    fig.tight_layout()
    fig.savefig(save_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return rows


if __name__ == "__main__":
    rows = plot_code_family_and_efficiency(p_max=6)
    for r in rows:
        print(f"p={r['p']} n={r['n']} k={r['k']} 码率={r['code_rate']:.3f} "
              f"α理论={r['alpha']:.3f} α实测={r['measured_alpha']:.3f} "
              f"(改动{r['measured_changed']})")
    print(f"\n绘图已保存: {os.path.join(OUTPUT_DIR, 'efficiency.png')}")