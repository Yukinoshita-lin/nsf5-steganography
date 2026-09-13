"""
experiments/featurize_bossbase_npz.py — 对 CNN 用的那个 npz 语料提 143 维特征,
使手工特征基线与 CNN 处在**同一语料、同一划分**上。

为什么必须做这一步: `experiments/data/sota_compare.csv` 里那行 `LGB-53d, 0.7565`
读的是 `data/dataset_bossbase.csv` (10000 源图 x 7 变体, 且只有 11 维列),
而 CNN 用的是 `gpu/data/imageset_bossbase.npz` (2000 源图 x 5 变体)。两套
语料不同源, 放在同一张表里比大小没有意义。这里把 npz 的每一张图都提一次
143 维, 于是 11d / 53d / 143d 三个特征集都能在这份语料上重算, 并与 CNN
共用 `experiments/data/sota_cnn_split.json` 的按源图划分。

输出: data/dataset_bossbase_npz_v2.csv  (143 特征列 + label/photo_id/method/p/density)

用法: python experiments/featurize_bossbase_npz.py
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "gpu"))
sys.path.insert(0, os.path.join(PROJ, "src"))

from train_cnn import load_imageset  # noqa: E402
from featurize_v2 import ALL_FEATURE_NAMES, N_FEAT  # noqa: E402

OUT_CSV = os.path.join(PROJ, "data", "dataset_bossbase_npz_v2.csv")
NPZ_NAME = "imageset_bossbase"


def main():
    from featurize_v2_gpu import extract_features_v2_gpu

    x, y, pid, meta = load_imageset(NPZ_NAME)
    n = x.shape[0]
    print(f"[data] {NPZ_NAME}: {n} 张 {x.shape[1]}x{x.shape[2]}, "
          f"clean={(y == 0).sum()} stego={(y == 1).sum()}, "
          f"源图={len(np.unique(pid))}", flush=True)

    # x 可能是 memmap; 每次只取一块喂给 GPU, 避免把 2.6 GB 全读进内存
    chunk = 64
    feats = np.empty((n, N_FEAT), dtype=np.float32)
    t0 = time.time()
    for s in range(0, n, chunk):
        sub = np.asarray(x[s:s + chunk], dtype=np.uint8)
        feats[s:s + chunk] = extract_features_v2_gpu(sub, chunk=chunk)
        if s % (chunk * 20) == 0:
            done = min(s + chunk, n)
            print(f"  {done}/{n}  {time.time() - t0:.0f}s", flush=True)

    assert feats.shape[1] == N_FEAT == 143, f"特征维度异常: {feats.shape}"
    assert np.isfinite(feats).all(), "特征里出现 NaN/Inf"

    df = pd.DataFrame(feats, columns=ALL_FEATURE_NAMES)
    df.insert(0, "label", y.astype(int))
    df.insert(1, "photo_id", pid.astype(int))
    if meta is not None:
        m = np.asarray(meta)
        # meta 每行是 (method, p, density, basename); 干净行为空串
        df["method"] = m[:, 0]
        df["p"] = pd.to_numeric(m[:, 1], errors="coerce")
        df["density"] = pd.to_numeric(m[:, 2], errors="coerce")
        df["basename"] = m[:, 3]
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"已写出 {OUT_CSV}  ({len(df)} 行 x {df.shape[1]} 列, "
          f"{os.path.getsize(OUT_CSV) / 1e6:.1f} MB)", flush=True)
    print(df.groupby("method").size().to_string(), flush=True)


if __name__ == "__main__":
    main()
