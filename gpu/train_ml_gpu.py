"""
train_ml_gpu —— 用 GPU 批量加速提取统计特征 + 训练隐写分类器。

- 数据: gpu/data/imageset.npz (full-512: 1干净+4档含密变体/照片)
- 特征: featurize_gpu.extract_features_gpu (11维, 与 CPU 参考实现 bit 级一致)
- 分割: 按照片分组 80/20 (杜绝同源泄漏)
- 模型: LogisticRegression; 报告验证 AUC + 每档检出率
- 输出: models/steg_classifier_gpu.joblib (+阈值/特征名/元数据)

用法:  python gpu/train_ml_gpu.py [--chunk 256]
"""
from __future__ import annotations
import os, sys, time, argparse, json
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import featurize_gpu as FG

PROJ = os.path.dirname(HERE)
DATA = os.path.join(HERE, "data", "imageset.npz")
MODEL_DIR = os.path.join(PROJ, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "steg_classifier_gpu.joblib")


def split_by_photo(photo_id, frac=0.8, seed=0):
    rng = np.random.default_rng(seed)
    photos = np.unique(photo_id)
    rng.shuffle(photos)
    n_tr = int(len(photos) * frac)
    tr_photos = set(photos[:n_tr].tolist())
    tr = np.array([i for i, pid in enumerate(photo_id) if int(pid) in tr_photos])
    va = np.array([i for i, pid in enumerate(photo_id) if int(pid) not in tr_photos])
    return tr, va


def youden_thr(y, p):
    order = np.argsort(p); y = y[order]; p = p[order]
    best = (0.5, -1.0)
    for thr in np.unique(p):
        tp = ((y == 1) & (p >= thr)).sum(); fp = ((y == 0) & (p >= thr)).sum()
        j = tp / max((y == 1).sum(), 1) - fp / max((y == 0).sum(), 1)
        if j > best[1]:
            best = (float(thr), float(j))
    return best[0]


def _util_sampler(stop, samples, interval=0.05):
    """后台采样 GPU 利用率, 直至 stop 事件置位。"""
    import threading
    try:
        import pynvml
        pynvml.nvmlInit()
        h = pynvml.nvmlDeviceGetHandleByIndex(0)
        while not stop.is_set():
            try:
                samples.append(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
            except Exception:
                pass
            stop.wait(interval)
    except Exception:
        pass


def measure_gpu_util(func, *args, **kwargs):
    """执行 func, 期间采样 GPU利用率, 返回 (结果, 峰值%, 平均%)。"""
    import threading
    stop = threading.Event(); samples: list = []
    th = threading.Thread(target=_util_sampler, args=(stop, samples), daemon=True)
    th.start()
    try:
        ret = func(*args, **kwargs)
    finally:
        stop.set(); th.join(timeout=1.0)
    avg = float(np.mean(samples)) if samples else -1.0
    peak = float(np.max(samples)) if samples else -1.0
    return ret, peak, avg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=128, help="GPU特征批量块大小 (8GB卡建议<=256)")
    args = ap.parse_args()

    if not os.path.exists(DATA):
        sys.exit(f"未找到 {DATA}, 请先运行: python gpu/make_imageset.py")
    d = np.load(DATA, allow_pickle=True)
    x, y, photo_id, meta = d["x"], d["y"], d["photo_id"], d["meta"]
    print(f"样本 {len(y)} (clean={(y==0).sum()}, stego={(y==1).sum()}), {x.shape[1]}x{x.shape[2]}")
    print(f"GPU: {FG.pick_gpu()}")

    t0 = time.perf_counter()
    F, util_peak, util_avg = measure_gpu_util(
        lambda: FG.extract_features_gpu(x, chunk=args.chunk))
    t_feat = time.perf_counter() - t0
    print(f"GPU提取 {len(y)} 张特征: {t_feat:.1f}s ({len(y)/max(t_feat,1e-9):.0f} img/s)")
    print(f"GPU利用率: 峰值 {util_peak:.0f}% / 平均 {util_avg:.0f}%")

    tr, va = split_by_photo(photo_id, frac=0.8, seed=0)
    print(f"照片分组: 训练 {len(tr)} / 验证 {len(va)}")

    clf = LogisticRegression(max_iter=3000, C=1.0)
    clf.fit(F[tr], y[tr])
    pv = clf.predict_proba(F[va])[:, 1]
    auc = float(roc_auc_score(y[va], pv))
    thr = youden_thr(y[va], pv)
    acc = float(((pv >= thr) == y[va]).mean())
    print(f"\n验证:  AUC={auc:.3f}  Youden阈值={thr:.3f}  acc={acc:.3f}")

    # 每档检出率
    print("\n验证集各项检出率 (thr 判定):")
    from collections import defaultdict
    rows = defaultdict(list)
    for idx in va:
        m = tuple(meta[idx]); k = (m[0], m[1], m[2] if len(m) > 2 else "")
        rows[k].append(1 if pv[list(va).index(idx)] >= thr else 0)
    for key, vals in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        meth, p, dens = key
        det = sum(vals)
        print(f"  {str(meth):<6} p={str(p):<3} d={str(dens):<6} 判含密={det:3d}/{len(vals)} ({det/len(vals)*100:.1f}%)")

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({
        "model": clf, "threshold": thr, "features": FG.FEAT_NAMES,
        "auc": auc, "input_size": int(x.shape[1]),
        "note": "train_ml_gpu.py — GPU批量统计特征 + LogisticRegression",
    }, MODEL_PATH)
    print(f"\n分类器已保存 -> {MODEL_PATH}")
    print("判定: python gpu/predict_gpu.py <图像路径>")


if __name__ == "__main__":
    main()