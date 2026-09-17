"""
experiments/ood_eval.py — OOD 真实 JPEG 干净照片上的误报率评估（生产者）。

背景 (2026-09-14 审计)
----------------------
README 与文档里长期挂着两个数字："143d OOD 误报 1/8"、"53d 3/8"。它们的生产者
与 `data/ood_jpeg_test/` 一起随另一个项目消失了, 于是这两个数字只能待在
`docs/RESULTS.md` 的"不可溯源"一节 —— n=8 本身也毫无统计意义。

本脚本把这条链补回来, 并把样本量提到千张级:

    语料 (全部是**无嵌入的干净真实照片**):
      campus : data/campus_jpg/            414 张 (作者本人照片, 不入库)
      div2k  : DIV2K validation HR         100 张 (公开可下载)
      alaska : ALASKA#2 Cover 子集        --alaska-n 张 (Kaggle, 需凭据)

    口径与部署完全一致: src/ml_predict.MLPredictor.preprocess (转灰度 → 512x512
    LANCZOS) → 143 维特征 → 模型概率 → 与 payload 里的阈值比较。

    2026-09-15 两处改进:
      * **特征只算一次**: 53 维是 143 维的子集, 以前一张图要跑两遍 featurize_v2。
        现在算一次 143 维, 用 MLPredictor.predict_from_v2() 选列打分 —— 打分路径
        与 predict() 完全相同 (有测试逐位比对)。
      * **并行**: `--workers N` (默认 min(8, CPU))。1514 张 × 2 模型 × 2 配置的
        全量评估从约 20 分钟降到 **1.7 分钟**, 结果逐位不变。

    2026-09-17 并行实现的两个补丁 (都由真实事故驱动):
      * **显式用 spawn 起进程池**。原来用 `multiprocessing.Pool`, 在 Linux 上默认
        是 **fork**: 调用方进程如果已经加载过 LightGBM (OpenMP 线程池已初始化),
        fork 出来的子进程再碰 LightGBM 就会**死锁**。实测证据: 加了调用并行路径的
        冒烟测试之后, CI 的 pytest 作业从 1 分 44 秒变成**挂满 6 小时被取消**
        (残留 `xvfb-run` + 5 个 python 孤儿进程); Windows 本地是 spawn, 所以一直
        没暴露。现在显式 `mp.get_context("spawn")`, 与平台无关。
      * **每个分片都有超时** (`--chunk-timeout`, 默认 600 秒)。并行卡住必须是
        **报错**, 不能是"永远在跑" —— 6 小时的 CI 只是最贵的那种表现。

    同时评估两种配置:
      clip=False  部署默认 (GUI / CLI 走的 get_predictor() 默认值)
      clip=True   文档里的抗分布偏移缓解手段 (特征 clip 到训练集 mu±5σ)

统计口径: 误报率 = 被判成含密的干净图比例, 附 Wilson 95% 置信区间
(n=200 时 CI 宽度 <7%, n=1500 时 <5%)。

输出
----
    experiments/data/ood_eval.csv      逐图 (model, clip, source, path, prob, threshold, pred)
    experiments/data/ood_summary.csv   model x clip x source 的 n / 误报 / 率 / CI / 中位概率

用法
----
    python experiments/ood_eval.py                        # 默认 414+100+1000 张
    python experiments/ood_eval.py --alaska-n 3000
    python experiments/ood_eval.py --sources campus,div2k
    python experiments/ood_eval.py --div2k-dir D:/DIV2K_valid_HR --alaska-dir D:/alaska2/Cover

外部语料目录默认找 `<repo>/data/external/{div2k/DIV2K_valid_HR,alaska2}`;
缺失时跳过该源并打印原因 (绝不静默少行)。
"""
from __future__ import annotations

import argparse
import glob
import math
import os
import sys
import time

import numpy as np
import pandas as pd
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))

from pathutil import rel_from_proj  # noqa: E402  (src/ 里的跨盘符安全 relpath)

OUT_DIR = os.path.join(PROJ, "experiments", "data")
OUT_RAW = os.path.join(OUT_DIR, "ood_eval.csv")
OUT_SUM = os.path.join(OUT_DIR, "ood_summary.csv")


def configure_out(out_dir: str) -> None:
    """改输出目录 (产物默认落在 experiments/data/, 测试与试跑用 --out-dir 走别处,
    免得覆盖已经用于 docs/RESULTS.md 的那两份 CSV)。"""
    global OUT_DIR, OUT_RAW, OUT_SUM
    OUT_DIR = os.path.abspath(out_dir)
    OUT_RAW = os.path.join(OUT_DIR, "ood_eval.csv")
    OUT_SUM = os.path.join(OUT_DIR, "ood_summary.csv")

WORK = (512, 512)
DEFAULT_MODELS = [
    ("143d", os.path.join(PROJ, "models", "stego_classifier.joblib")),
    ("53d", os.path.join(PROJ, "models", "stego_classifier_v2_jpeg_lgb_51d.joblib")),
]
IMG_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tif", "*.tiff", "*.pgm")


# ---------------------------------------------------------------- 语料发现
def list_images(root: str, limit: int) -> list:
    if not root or not os.path.isdir(root):
        return []
    paths = []
    for ext in IMG_EXTS:
        paths.extend(glob.glob(os.path.join(root, ext)))
        paths.extend(glob.glob(os.path.join(root, "**", ext), recursive=True))
    return sorted(set(paths))[:limit] if limit > 0 else sorted(set(paths))


def gather_sources(args) -> dict:
    """返回 {source: [paths]}。缺数据源的**明确跳过并打印原因**。"""
    out = {}
    want = [s.strip() for s in args.sources.split(",") if s.strip()]
    if "campus" in want:
        p = list_images(args.campus_dir, args.campus_n)
        print(f"  campus : {len(p):>5} 张  <- {args.campus_dir}")
        if p:
            out["campus"] = p
    if "div2k" in want:
        p = list_images(args.div2k_dir, args.div2k_n)
        print(f"  div2k  : {len(p):>5} 张  <- {args.div2k_dir}")
        if p:
            out["div2k"] = p
        else:
            print("           [跳过] DIV2K 目录不存在; 公开下载: "
                  "http://data.vision.ee.ethz.ch/cvl/DIV2K/DIV2K_valid_HR.zip")
    if "alaska" in want:
        p = list_images(args.alaska_dir, args.alaska_n)
        print(f"  alaska : {len(p):>5} 张  <- {args.alaska_dir}")
        if p:
            out["alaska"] = p
        else:
            print("           [跳过] ALASKA#2 目录不存在; 需 Kaggle 凭据: "
                  "kaggle competitions download -c alaska2-image-steganalysis")
    return out


# ---------------------------------------------------------------- 统计
def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple:
    """误报率的 Wilson 95% 置信区间 (小样本比正态近似可靠)。"""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ---------------------------------------------------------------- 评估
_PREDS = []          # 每个 worker 进程里初始化一次


def _init_worker(specs: list, n_sigma: float) -> None:
    """在子进程里一次性加载全部模型 (每张图要用它们全部打分)。"""
    from ml_predict import MLPredictor
    global _PREDS
    _PREDS = []
    for label, path, clip in specs:
        pred = MLPredictor(model_path=path, clip_outliers=clip, n_sigma=n_sigma)
        _PREDS.append((label, clip, pred, pred.available, pred.load_error))


def _score_one(item: tuple) -> list:
    """(src, path) → 该图在所有模型/配置下的行。

    2026-09-15 性能与口径:
      * 特征只算一次: 53d 是 143d 的子集, 以前一张图要跑两遍 featurize_v2
        (143d 与 53d 各一遍)。现在算一次 143 维, 交给 predict_from_v2() 选列打分。
      * 预处理**必须**等于部署路径: 以前这里用 convert("L") 取亮度, 而
        MLPredictor.preprocess() 取的是第一个通道 —— 实测两者在真实照片上平均
        概率差 0.24、最大 0.97, 等于在评测一个跟线上不同的输入管线。
    """
    from ml_predict import MLPredictor
    from featurize_v2 import featurize_v2
    src, path = item
    try:
        raw = np.asarray(Image.open(path), dtype=np.uint8)
        a = MLPredictor.preprocess(raw)
    except Exception as exc:  # noqa: BLE001
        print(f"    [读取失败] {os.path.basename(path)}: {exc}", flush=True)
        return []
    x143 = featurize_v2(a).reshape(1, -1)
    out = []
    for label, clip, pred, available, err in _PREDS:
        if not available:
            continue
        r = pred.predict_from_v2(x143)
        prob, thr = r["probability"], r["threshold"]
        if prob is None or thr is None:
            continue
        out.append({"model": label, "clip": bool(clip), "source": src,
                    "photo_path": path, "photo_name": os.path.basename(path),
                    "ml_prob": round(float(prob), 6),
                    "threshold": round(float(thr), 6),
                    "pred_stego": int(prob >= thr)})
    return out


def _score_chunk(chunk: list) -> list:
    """一个分片: 逐图打分并拼平 (给 apply_async 用, 便于给每个分片设超时)。"""
    rows = []
    for item in chunk:
        rows.extend(_score_one(item))
    return rows


def evaluate(models: list, sources: dict, clips: tuple, n_sigma: float,
             workers: int = 1, chunk_timeout: float = 600.0) -> pd.DataFrame:
    specs = [(label, path, clip) for label, path in models for clip in clips]
    for label, path in models:
        if not os.path.exists(path):
            print(f"  [跳过] 模型不存在: {path}")
    _init_worker([s for s in specs if os.path.exists(s[1])], n_sigma)
    for label, clip, pred, ok, err in _PREDS:
        if not ok:
            print(f"  [跳过] {label} clip={int(clip)} 加载失败: {err}")

    items = [(src, p) for src, paths in sources.items() for p in paths]
    t0 = time.time()
    rows = []
    if workers > 1:
        import multiprocessing as mp
        from collections import deque
        used = [s for s in specs if os.path.exists(s[1])]
        # spawn, **不要** fork: 见文件头 2026-09-17 的说明 (fork + OpenMP 死锁,
        # 实测在 CI 上挂了 6 小时)。spawn 的额外开销是每个 worker 重新导入一次
        # 模块 + 加载模型 (约 1 s), 相对"一张图要算 143 维特征"可以忽略。
        ctx = mp.get_context("spawn")
        # 分片 + `apply_async(...).get(timeout=...)`: 比 `imap_unordered` 啰嗦, 但
        # 它是**跨版本可移植**的 —— Python 3.14 的 imap_unordered 返回的是普通
        # 生成器 (没有 `.next(timeout=...)`), 用那个 API 写超时会在新版本直接崩。
        chunks = [items[i:i + 8] for i in range(0, len(items), 8)] or [[]]
        with ctx.Pool(workers, initializer=_init_worker, initargs=(used, n_sigma)) as pool:
            inflight = deque()
            nxt, done = 0, 0
            while nxt < len(chunks) or inflight:
                while nxt < len(chunks) and len(inflight) < workers * 2:
                    inflight.append(pool.apply_async(_score_chunk, (chunks[nxt],)))
                    nxt += 1
                ar = inflight.popleft()
                try:
                    got = ar.get(timeout=chunk_timeout)
                except mp.TimeoutError:
                    pool.terminate()
                    raise RuntimeError(
                        f"并行评估在 {chunk_timeout:.0f} 秒内没有返回任何分片 "
                        f"(已完成 {done}/{len(items)} 张)。这通常是子进程卡死 —— "
                        f"用 `--workers 1` 复跑确认, 或调大 `--chunk-timeout`。")
                rows.extend(got)
                done += len(got) or 0
                if len(inflight) == 0 or done % 200 < 8:
                    if done:
                        print(f"    进度 {done}/{len(items)}  ({time.time()-t0:.0f}s)",
                              flush=True)
    else:
        for i, item in enumerate(items, 1):
            rows.extend(_score_one(item))
            if i % 200 == 0:
                print(f"    进度 {i}/{len(items)}  ({time.time()-t0:.0f}s)", flush=True)
    df = pd.DataFrame(rows)
    if len(df):
        # 排序后再落盘: 并行返回分片的顺序取决于进程调度, 不排序的话同一份语料
        # 每次跑出来的 CSV 行序都不同 (内容一样, 但 diff 全是噪声, 也没法用
        # 哈希断言"重跑一致")。按 (模型, 配置, 来源, 文件名) 排成确定顺序。
        df = df.sort_values(["model", "clip", "source", "photo_name"]).reset_index(drop=True)
        for (label, clip, src), g in df.groupby(["model", "clip", "source"]):
            print(f"  {label:>5} clip={int(clip)} {src:>7}: "
                  f"{int(g['pred_stego'].sum())}/{len(g)} 误报", flush=True)
    print(f"  {len(items)} 张图 × {len(_PREDS)} 个模型配置, 耗时 {time.time()-t0:.0f}s "
          f"({'并行 ' + str(workers) + ' 进程' if workers > 1 else '单进程'})")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    if df.empty:
        return pd.DataFrame(out)
    for (model, clip), sub in df.groupby(["model", "clip"]):
        for src, s in list(sub.groupby("source")) + [("ALL", sub)]:
            n = len(s)
            k = int(s["pred_stego"].sum())
            lo, hi = wilson_ci(k, n)
            out.append({
                "model": model, "clip_outliers": bool(clip), "source": src,
                "n_photos": n, "n_false_positive": k,
                "fp_rate": round(k / n, 4) if n else float("nan"),
                "fp_ci_lo": round(lo, 4) if n else float("nan"),
                "fp_ci_hi": round(hi, 4) if n else float("nan"),
                "median_prob": round(float(s["ml_prob"].median()), 6) if n else float("nan"),
                "protocol": f"clean real photos, grayscale -> {WORK[0]}x{WORK[1]} LANCZOS, "
                            f"verdict = prob >= payload threshold",
            })
    return pd.DataFrame(out).sort_values(["model", "clip_outliers", "source"])


def main() -> int:
    ap = argparse.ArgumentParser(description="OOD 真实干净照片误报率评估 (生产者)")
    ext = os.path.join(PROJ, "data", "external")
    ap.add_argument("--sources", default="campus,div2k,alaska")
    ap.add_argument("--campus-dir", default=os.path.join(PROJ, "data", "campus_jpg"))
    ap.add_argument("--div2k-dir", default=os.path.join(ext, "div2k", "DIV2K_valid_HR"))
    ap.add_argument("--alaska-dir", default=os.path.join(ext, "alaska2"))
    ap.add_argument("--campus-n", type=int, default=0, help="0 = 全部")
    ap.add_argument("--div2k-n", type=int, default=0)
    ap.add_argument("--alaska-n", type=int, default=1000)
    ap.add_argument("--models", default="",
                    help="覆盖模型列表: label=path,label=path")
    ap.add_argument("--clips", default="0,1", help="要评估的 clip_outliers 取值")
    ap.add_argument("--n-sigma", type=float, default=5.0)
    ap.add_argument("--workers", type=int, default=0,
                    help="并行进程数 (0 = min(8, CPU 核数); 1 = 单进程)")
    ap.add_argument("--chunk-timeout", type=float, default=600.0,
                    help="并行时每个分片的等待上限 (秒); 超时直接报错, 不无限等")
    ap.add_argument("--out-dir", default=OUT_DIR,
                    help="产物目录 (默认 experiments/data/; 试跑请改这里, "
                         "别覆盖权威表用的那两份 CSV)")
    args = ap.parse_args()

    models = DEFAULT_MODELS
    if args.models:
        models = []
        for item in args.models.split(","):
            if "=" in item:
                label, path = item.split("=", 1)
                models.append((label.strip(), path.strip()))
    clips = tuple(bool(int(c)) for c in args.clips.split(",") if c.strip() != "")
    configure_out(args.out_dir)

    print("OOD 干净真实照片误报率评估")
    print(f"  模型: {[m[0] for m in models]}   clip_outliers={clips}")
    sources = gather_sources(args)
    if not sources:
        sys.exit("没有任何可用语料 —— 检查 --campus-dir / --div2k-dir / --alaska-dir。")
    print(f"  合计 {sum(len(v) for v in sources.values())} 张干净照片\n")

    n_workers = args.workers if args.workers > 0 else min(8, os.cpu_count() or 1)
    df = evaluate(models, sources, clips, args.n_sigma, workers=n_workers,
                  chunk_timeout=args.chunk_timeout)
    if df.empty:
        sys.exit("评估没有产出任何行。")
    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(OUT_RAW, index=False)
    summary = summarize(df)
    summary.to_csv(OUT_SUM, index=False)
    # 用 rel_from_proj 而不是 os.path.relpath: `--out-dir` 完全可能指到别的盘符
    # (Windows 上 temp 在 C:、仓库在别的盘), 那时 relpath 会抛 ValueError ——
    # 而且是在**跑完全部评估之后**才抛, 白跑一遍。src/pathutil.py 的文件头就是
    # 为这个坑写的。2026-09-17 加 --out-dir 的冒烟测试第一次跑就撞上了。
    print(f"\n逐图 -> {rel_from_proj(OUT_RAW, PROJ)}  ({len(df)} 行)")
    print(f"汇总 -> {rel_from_proj(OUT_SUM, PROJ)}\n")
    print(summary.to_string(index=False))
    print("\n下一步: python experiments/build_results_table.py  (刷新权威结果表)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
