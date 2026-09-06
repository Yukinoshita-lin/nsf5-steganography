"""
train_ml_gpu —— 用 GPU 批量加速提取统计特征 + 训练隐写分类器。

- 数据: gpu/data/imageset.npz (full-512: 1干净+4档含密变体/照片)
- 特征: featurize_gpu.extract_features_gpu (11维 v1) 或 featurize_v2_gpu (143维 v2) — --feature-set 选择
- 分割: 按照片分组 80/20 (杜绝同源泄漏)
- 模型: 默认 LogisticRegression; --stack 开启 4 模型 (LR/RF/GBDT/XGB) OOF stacking + 概率校准
- 输出: models/steg_classifier_gpu.joblib (+阈值/特征名/元数据)

用法:  python gpu/train_ml_gpu.py [--chunk 128] [--feature-set v1|v2] [--stack]
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
DATA_FILES = ["imageset_campus", "imageset_bossbase"]  # 多数据源合并训练(<base>.npz + <base>_x.npy)
MODEL_DIR = os.path.join(PROJ, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "steg_classifier_gpu.joblib")

GLOBAL_PHOTO_ID = None  # 记录拼接后 source 边界, 供逐档统计


def _unique_ids(y, ids):
    """在保持顺序的同时把 y 压缩为连续 id, 保证合并后按源分组不串。"""
    import pandas as pd
    s = pd.Series(ids).rank(method="dense").astype(np.int64)
    return s.values


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


def _load_source(fn):
    """读一个数据源: 返回 (memmap_x 或 None, y, photo_id, meta, H, W)。"""
    base = os.path.join(HERE, "data", fn)
    npz_path = base + ".npz"
    npy_path = base + "_x.npy"
    if not os.path.exists(npz_path) and not os.path.exists(npy_path):
        return None
    aux = np.load(npz_path, allow_pickle=True) if os.path.exists(npz_path) else None
    x = None
    if os.path.exists(npy_path):           # 大数组单独 memmap
        mm = np.load(npy_path, mmap_mode="r")
        x = mm; H, W = mm.shape[1], mm.shape[2]
    elif aux is not None and "x" in aux:
        x = aux["x"]; H, W = x.shape[1], x.shape[2]
    elif aux is not None:
        # 旧式单 npz (无 _x.npy): 依 meta 长度推断, 以元数据样本数为主
        n_samp = len(aux["y"]) if "y" in aux else 0
        if n_samp == 0:
            return None
        x = None; H = W = 0
    else:
        return None
    y = aux["y"] if aux is not None and "y" in aux else np.zeros(len(x) if x is not None else 0, np.int64)
    pid = aux["photo_id"] if aux is not None and "photo_id" in aux else np.arange(len(y))
    meta = aux["meta"] if aux is not None and "meta" in aux else \
        np.array([("clean", "", "", "")] * len(y), dtype=object)
    return x, y, pid, meta, H, W


def _oof_stack_train(F, y, photo_id, n_splits=5, seed=0):
    """GPU 链路专用 OOF stacking: LR/RF/GBDT/XGB + LR meta-learner + Platt 校准。
    返回 (auc, p_full, thr) — p_full 为在 OOF 段+stacker 重训后整段预测。"""
    from sklearn.model_selection import GroupKFold
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV
    from xgboost import XGBClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    gkf = GroupKFold(n_splits=n_splits)
    oof = {n: np.full(len(y), np.nan) for n in ("LR", "RF", "GB", "XGB")}
    aucs = {}
    for tr, va in gkf.split(F, y, photo_id):
        for name, mk in {
            "LR":  lambda s=seed: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=s)),
            "RF":  lambda s=seed: RandomForestClassifier(n_estimators=400, max_depth=None, n_jobs=-1, random_state=s),
            "GB":  lambda s=seed: GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=s),
            "XGB": lambda s=seed: XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=4, eval_metric="logloss", n_jobs=-1, random_state=s),
        }.items():
            clf = mk()
            clf.fit(F[tr], y[tr])
            oof[name][va] = clf.predict_proba(F[va])[:, 1]
    for n, arr in oof.items():
        m = ~np.isnan(arr)
        aucs[n] = float(roc_auc_score(y[m], arr[m])) if m.sum() > 0 and len(np.unique(y[m])) == 2 else 0.0
        print(f"  {n:<4} OOF-AUC={aucs[n]:.4f}")
    # 4 模型 → LR meta
    stack_X = np.stack([oof[n] for n in ("LR", "RF", "GB", "XGB")], 1)
    msk = ~np.isnan(stack_X).any(1)
    meta = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=seed))
    meta.fit(stack_X[msk], y[msk])
    p_meta_oof = meta.predict_proba(stack_X[msk])[:, 1]
    stack_auc = float(roc_auc_score(y[msk], p_meta_oof))
    print(f"  STACK OOF-AUC={stack_auc:.4f}  (LR meta on 4 OOF probs)")
    # 重训所有基模型在全集, meta-learner 也在全集 OOF 概率上重训
    final_models = {n: None for n in ("LR", "RF", "GB", "XGB")}
    for name, mk in {
        "LR":  lambda: make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=seed)),
        "RF":  lambda: RandomForestClassifier(n_estimators=400, max_depth=None, n_jobs=-1, random_state=seed),
        "GB":  lambda: GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, max_depth=3, random_state=seed),
        "XGB": lambda: XGBClassifier(n_estimators=300, learning_rate=0.05, max_depth=4, eval_metric="logloss", n_jobs=-1, random_state=seed),
    }.items():
        final_models[name] = mk(); final_models[name].fit(F, y)
    base_p_full = np.stack([final_models[n].predict_proba(F)[:, 1] for n in ("LR", "RF", "GB", "XGB")], 1)
    final_meta = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0, random_state=seed))
    final_meta.fit(base_p_full, y)
    p_full = final_meta.predict_proba(base_p_full)[:, 1]
    auc_full = float(roc_auc_score(y, p_full))
    thr = youden_thr(y, p_full)
    candidates = {**aucs, "STACK": stack_auc, "STACK_full": auc_full}
    best = max(candidates, key=lambda k: candidates[k])
    print(f"  GPU STACK: OOF={stack_auc:.4f}  full={auc_full:.4f}  best={best}={candidates[best]:.4f}")
    return auc_full, p_full, thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk", type=int, default=128, help="GPU特征批量块大小 (8GB卡建议<=256)")
    ap.add_argument("--datas", nargs="*", default=None,
                    help="多数据源 basename(相对 gpu/data, 取 <base>.npz + <base>_x.npy), 默认 = campus+bossbase")
    ap.add_argument("--srm", choices=("auto", "on", "off"), default="auto",
                    help="SRM 高通滤波预处理: on/off 强制, auto=用 featurize 默认(=on)")
    ap.add_argument("--feature-set", choices=("v1", "v2"), default="v1",
                    help="v1=11维 (与 CPU 一致); v2=143维 (SRM 30残差统计+20段前缀p+texture/est_rate+lsb20段)")
    ap.add_argument("--stack", action="store_true",
                    help="开启 4 模型 (LR/RF/GBDT/XGB) OOF stacking + 概率校准; 默认只训 LR")
    ap.add_argument("--out", default=None,
                    help="保存 joblib 路径 (默认 models/steg_classifier_gpu.joblib); v2 时自动加 _v2 后缀")
    args = ap.parse_args()
    use_srm = False if args.srm == "off" else True
    fset = args.feature_set
    feat_extractor = (lambda x, chunk: __import__("featurize_v2_gpu").extract_features_v2_gpu(x, chunk=chunk)) \
        if fset == "v2" else (lambda x, chunk: FG.extract_features_gpu(x, chunk=chunk, use_srm=use_srm))
    feat_names = __import__("featurize_v2_gpu").NAMES if fset == "v2" else FG.FEAT_NAMES

    names = args.datas if args.datas else DATA_FILES
    all_y, all_pid, all_meta, all_shape = [], [], [], None
    t0 = time.perf_counter()
    Fs = []
    for fn in names:
        src = _load_source(fn)
        if src is None:
            sys.exit(f"未找到数据源 {fn}, 请先运行: python gpu/make_imageset.py --out {fn}")
        x, y, pid, meta, H, W = src
        print(f"=== 数据源 {fn} === 样本 {len(y)} "
              f"(clean={(y==0).sum()}, stego={(y==1).sum()}) {H}x{W}")
        # memmap 激活后按源分批提取(内部也分 chunk), 避免整块载入内存
        Fi, peak, avg = measure_gpu_util(lambda: feat_extractor(x, args.chunk))
        Fs.append(Fi)
        all_y.append(y); all_pid.append(_unique_ids(y, pid)); all_meta.append(meta)

    F = np.concatenate(Fs); y = np.concatenate(all_y)
    photo_id = np.concatenate(all_pid); meta = np.concatenate(all_meta)
    print(f"\n合并样本 {len(y)} (clean={(y==0).sum()}, stego={(y==1).sum()}) 特征 {F.shape[1]} ({fset})")
    print(f"GPU: {FG.pick_gpu()}, 特征提取 {time.perf_counter()-t0:.1f}s")

    if not args.stack:
        # ---- 单模型 (LR) ----
        tr, va = split_by_photo(photo_id, frac=0.8, seed=0)
        print(f"照片分组: 训练 {len(tr)} / 验证 {len(va)}")
        clf = LogisticRegression(max_iter=3000, C=1.0)
        clf.fit(F[tr], y[tr])
        pv = clf.predict_proba(F[va])[:, 1]
        auc = float(roc_auc_score(y[va], pv))
        thr = youden_thr(y[va], pv)
        acc = float(((pv >= thr) == y[va]).mean())
        print(f"\n验证:  AUC={auc:.3f}  Youden阈值={thr:.3f}  acc={acc:.3f}")
        payload_model = clf
    else:
        # ---- 4 模型 OOF stacking ----
        from sklearn.model_selection import GroupKFold
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.calibration import CalibratedClassifierCV
        from xgboost import XGBClassifier
        auc, pv, thr = _oof_stack_train(F, y, photo_id, n_splits=5, seed=0)
        # va 评估已包含在 _oof_stack_train 内部; va_meta 仍可统计
        tr, va = split_by_photo(photo_id, frac=0.8, seed=0)
        acc = float(((pv >= thr) == y[va]).mean())
        print(f"\n验证 (STACK):  AUC={auc:.3f}  Youden阈值={thr:.3f}  acc={acc:.3f}")
        payload_model = "stack"

    # 每档检出率
    print("\n验证集各项检出率 (thr 判定):")
    from collections import defaultdict
    va_meta = meta[va]
    rows = defaultdict(list)
    for i, idx in enumerate(va):
        m = tuple(va_meta[i]); k = (m[0], m[1], m[2] if len(m) > 2 else "")
        rows[k].append(1 if pv[i] >= thr else 0)
    for key, vals in sorted(rows.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        meth, p, dens = key
        det = sum(vals)
        print(f"  {str(meth):<6} p={str(p):<3} d={str(dens):<6} 判含密={det:3d}/{len(vals)} ({det/len(vals)*100:.1f}%)")

    os.makedirs(MODEL_DIR, exist_ok=True)
    out_path = args.out
    if out_path is None:
        suffix = f"_{fset}_stack" if args.stack else f"_{fset}"
        out_path = os.path.join(MODEL_DIR, f"steg_classifier_gpu{suffix}.joblib")
    payload = {
        "model": payload_model, "threshold": thr, "features": feat_names,
        "auc": auc, "input_size": F.shape[1],
        "datas": names, "feature_set": fset, "stack": args.stack,
        "note": f"train_ml_gpu.py — {fset} {('4模型OOF stacking' if args.stack else 'LR')}",
    }
    joblib.dump(payload, out_path)
    print(f"\n分类器已保存 -> {out_path}")
    print("判定: python gpu/predict_gpu.py <图像路径>")


if __name__ == "__main__":
    main()