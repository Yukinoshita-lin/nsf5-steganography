# -*- coding: utf-8 -*-
"""论文实验1: 性能基准
  (a) splitmix64 置换: Python fallback vs C++ nsf5_permute (n~2^10..2^24)
  (b) nsF5 嵌入端到端耗时 vs 图像尺寸 256..4096
  (c) 11维特征提取吞吐: CPU(fsfeatures.dll) vs GPU(torch 批量)
输出 CSV → experiments/data/*.csv ; 图 → experiments/figs/*.png|svg

用法
----
    python experiments/tools/gen_bench.py                # 三段都跑 (需要 torch+CUDA)
    python experiments/tools/gen_bench.py --only permute # 只刷新 (a): 不需要 GPU

为什么有 `--only`: 教学材料引用的是 (a) 的置换加速比, 而重跑 (b)/(c) 需要 GPU 与
几十分钟 —— 想更新那一个数字不该被逼着重跑全部。**性能数字是机器相关的**,
引用它时必须带上"哪台机器/哪个版本的实现", 所以每次刷新都请在同一提交里
更新引用它的手册文字 (handbook_facts.py 里有护栏)。
"""
from __future__ import annotations
import sys, os, time, csv, statistics
os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.abspath("src"); GPU = os.path.abspath("gpu")
for p in (SRC, GPU):
    if p not in sys.path: sys.path.insert(0, p)
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTD = os.path.join("experiments", "data"); FIGD = os.path.join("experiments", "figs")
os.makedirs(OUTD, exist_ok=True); os.makedirs(FIGD, exist_ok=True)

import ns5_core as N
from fsfeatures import get_lib


def perm_py(total, seed):
    mask = (1 << 64) - 1
    a = np.arange(total, dtype=np.int64)
    x = int(seed) & mask
    for i in range(total - 1, 0, -1):
        x = (x + 0x9E3779B97F4A7C15) & mask
        z = x; z = (z ^ (z >> 30)) & mask; z = (z * 0xBF58476D1CE4E5B9) & mask
        z = (z ^ (z >> 27)) & mask; z = (z * 0x94D049BB133111EB) & mask
        r = (z ^ (z >> 31)) & mask
        j = int(r % (i + 1)); a[i], a[j] = a[j], a[i]
    return a


def best(fn, *a, k=3):
    ts = []
    for _ in range(k):
        t0 = time.perf_counter(); fn(*a); ts.append(time.perf_counter() - t0)
    return statistics.median(ts)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all", choices=["all", "permute", "embed", "feat"],
                    help="只跑其中一段 (默认全部)")
    args = ap.parse_args()
    want = lambda k: args.only in ("all", k)          # noqa: E731

    # ---------- (a) 置换 ----------
    if want("permute"):
        ns = [2 ** i for i in range(10, 25)]
        pr = []
        for n in ns:
            k = 1 if n >= 1 << 22 else 3
            tp = best(perm_py, n, 42, k=k)
            tc = best(N.permute_index, n, 42, k=k)
            pr.append((n, tp, tc))
            print(f"permute n={n}: py={tp*1e3:.2f}ms cpp={tc*1e3:.2f}ms x={tp/tc:.1f}")
        with open(os.path.join(OUTD, "bench_permute.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["n", "python_ms", "cpp_ms", "speedup"])
            for n, tp, tc in pr:
                w.writerow([n, round(tp*1e3, 3), round(tc*1e3, 3), round(tp/tc, 2)])

    # ---------- (b) 嵌入端到端 ----------
    if want("embed"):
        sizes = [256, 512, 1024, 2048, 4096]
        er = []
        for s in sizes:
            rng = np.random.default_rng(s)
            a = rng.integers(0, 256, (s, s), dtype=np.uint8)
            cap_b = (s * s * 2) // ((1 << 2) - 1) // 8
            nbytes = max(1, min(int(cap_b * 0.2), 60000))
            text = "S" * nbytes
            t = best(lambda: N.embed_string(a, text, method="nsF5", p=2), k=3)
            er.append((s, t))
            print(f"embed {s}x{s}: {t*1e3:.1f} ms")
        with open(os.path.join(OUTD, "bench_embed.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["size_px", "embed_ms"])
            for s, t in er:
                w.writerow([s, round(t*1e3, 1)])

    # ---------- (c) 特征吞吐 CPU vs GPU ----------
    if want("feat"):
        from featurize_gpu import extract_features_gpu, pick_gpu
        gpu_name = pick_gpu()
        Nlist = [50, 100, 200]
        fr = []
        lib = get_lib()
        for n in Nlist:
            rng = np.random.default_rng(n)
            imgs = rng.integers(0, 256, (n, 512, 512), dtype=np.uint8)
            t0 = time.perf_counter()
            for i in range(n):
                lib.features(imgs[i])
            tc = time.perf_counter() - t0
            t0 = time.perf_counter()
            extract_features_gpu(imgs, chunk=256)
            tg = time.perf_counter() - t0
            fr.append((n, tc, tg))
            print(f"feat N={n}: cpu={tc:.2f}s({n/tc:.0f}/s) gpu={tg:.2f}s({n/tg:.0f}/s) x={tc/tg:.1f}")
        with open(os.path.join(OUTD, "bench_feat.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["N", "cpu_s", "gpu_s", "cpu_img_s", "gpu_img_s", "gpu"])
            for n, tc, tg in fr:
                w.writerow([n, round(tc, 3), round(tg, 3), round(n/tc, 1), round(n/tg, 1), gpu_name])

    # ---------- 绘图 ----------
    if want("permute"):
        # 1) 置换 log-log
        ns_, py_, cp_ = zip(*pr)
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.loglog(ns_, [t*1e3 for t in py_], "o-", label="Python fallback (splitmix64)")
        ax.loglog(ns_, [t*1e3 for t in cp_], "s-", label="C++ nsf5_permute")
        ax.set_xlabel("N (置换元素数)"); ax.set_ylabel("耗时 / ms")
        ax.set_title("确定性置乱性能对比 (log-log)"); ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=9)
        fig.tight_layout(); fig.savefig(os.path.join(FIGD, "permute.png"), dpi=300)
        fig.savefig(os.path.join(FIGD, "permute.svg")); plt.close(fig)

    # 2) 嵌入端到端
    if want("embed"):
        ss, et = zip(*er)
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.semilogy([s*s/1e6 for s in ss], [t*1e3 for t in et], "o-", color="#1565c0")
        ax.set_xlabel("图像尺寸 / Mpixel"); ax.set_ylabel("嵌入耗时 / ms")
        ax.set_title("nsF5 嵌入端到端耗时 (4096² 约 281 ms)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(FIGD, "embed.png"), dpi=300)
        fig.savefig(os.path.join(FIGD, "embed.svg")); plt.close(fig)

    # 3) 特征吞吐
    if want("feat"):
        nn, cps, gps = zip(*[(n, tc, tg) for n, tc, tg in fr])
        x = np.arange(len(nn)); wdt = 0.36
        fig, ax = plt.subplots(figsize=(6, 3.6))
        ax.bar(x - wdt/2, [n/c for n, c in zip(nn, cps)], wdt, label="CPU (fsfeatures.dll)", color="#8e24aa")
        ax.bar(x + wdt/2, [n/g for n, g in zip(nn, gps)], wdt, label="GPU (torch 批量)", color="#00897b")
        ax.set_xticks(x); ax.set_xticklabels([str(n) for n in nn])
        ax.set_xlabel("样本数 N (512×512)"); ax.set_ylabel("吞吐 / img·s⁻¹")
        ax.set_title(f"11维特征提取吞吐 (GPU={gpu_name})"); ax.legend(fontsize=9)
        ax.grid(True, axis="y", alpha=0.3)
        fig.tight_layout(); fig.savefig(os.path.join(FIGD, "feat_throughput.png"), dpi=300)
        fig.savefig(os.path.join(FIGD, "feat_throughput.svg")); plt.close(fig)
    print(f"\n(--only {args.only}) 数据已写出 experiments/data/, 图在 experiments/figs/")


if __name__ == "__main__":
    main()
