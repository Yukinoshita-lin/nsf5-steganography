# -*- coding: utf-8 -*-
"""论文实验1c: 特征吞吐 CPU vs GPU (稳健版: 预热 + 取中位)"""
from __future__ import annotations
import sys, os, time, csv, statistics
os.chdir(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.abspath("src"); GPU = os.path.abspath("gpu")
for p in (SRC, GPU):
    if p not in sys.path: sys.path.insert(0, p)
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fsfeatures import get_lib
from featurize_gpu import extract_features_gpu, pick_gpu

OUTD = os.path.join("experiments", "data"); FIGD = os.path.join("experiments", "figs")
os.makedirs(OUTD, exist_ok=True); os.makedirs(FIGD, exist_ok=True)
gpu_name = pick_gpu()
print("GPU:", gpu_name)

lib = get_lib()
# 预热 GPU(丢弃) 与 CPU
warm = np.random.default_rng(0).integers(0, 256, (64, 512, 512), dtype=np.uint8)
extract_features_gpu(warm, chunk=128)
for i in range(8): lib.features(warm[i])

def cpu_time(imgs):
    t0 = time.perf_counter()
    for i in range(len(imgs)): lib.features(imgs[i])
    return time.perf_counter() - t0

def gpu_time(imgs):
    t0 = time.perf_counter(); extract_features_gpu(imgs, chunk=256)
    return time.perf_counter() - t0

rows = []
for n in [200, 400, 800, 1600]:
    imgs = np.random.default_rng(n).integers(0, 256, (n, 512, 512), dtype=np.uint8)
    tc = statistics.median(cpu_time(imgs) for _ in range(2))
    tg = statistics.median(gpu_time(imgs) for _ in range(3))
    rows.append((n, tc, tg))
    print(f"N={n}: cpu={tc:.2f}s({n/tc:.0f}/s) gpu={tg:.2f}s({n/tg:.0f}/s) x={tc/tg:.2f}")

with open(os.path.join(OUTD, "bench_feat.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["N", "cpu_s", "gpu_s", "cpu_img_s", "gpu_img_s", "gpu"])
    for n, tc, tg in rows:
        w.writerow([n, round(tc, 3), round(tg, 3), round(n/tc, 1), round(n/tg, 1), gpu_name])

nn, cps, gps = zip(*[(n, tc, tg) for n, tc, tg in rows])
x = np.arange(len(nn)); wdt = 0.36
fig, ax = plt.subplots(figsize=(6, 3.6))
ax.bar(x - wdt/2, [n/c for n, c in zip(nn, cps)], wdt, label="CPU (fsfeatures.dll)", color="#8e24aa")
ax.bar(x + wdt/2, [n/g for n, g in zip(nn, gps)], wdt, label="GPU (torch 批量)", color="#00897b")
ax.set_xticks(x); ax.set_xticklabels([str(n) for n in nn])
ax.set_xlabel("样本数 N (512×512)"); ax.set_ylabel("吞吐 / img·s⁻¹")
ax.set_title("11维特征提取吞吐 (预热取中位)")
ax.legend(fontsize=9); ax.grid(True, axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIGD, "feat_throughput.png"), dpi=300)
fig.savefig(os.path.join(FIGD, "feat_throughput.svg")); plt.close(fig)
print("\nOK: experiments/figs/feat_throughput.*")