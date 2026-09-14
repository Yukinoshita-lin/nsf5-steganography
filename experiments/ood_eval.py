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

    口径与部署完全一致: src/ml_predict.MLPredictor (灰度 → 512x512 LANCZOS →
    143 维 / 53 维 → 模型概率 → 与 payload 里的阈值比较)。

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

OUT_DIR = os.path.join(PROJ, "experiments", "data")
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
def evaluate(models: list, sources: dict, clips: tuple, n_sigma: float) -> pd.DataFrame:
    from ml_predict import MLPredictor

    rows = []
    for label, path in models:
        if not os.path.exists(path):
            print(f"  [跳过] 模型不存在: {path}")
            continue
        for clip in clips:
            pred = MLPredictor(model_path=path, clip_outliers=clip, n_sigma=n_sigma)
            if not pred.available:
                print(f"  [跳过] {label} clip={clip} 加载失败: {pred.load_error}")
                continue
            for src, paths in sources.items():
                t0 = time.time()
                n_fp = 0
                for i, p in enumerate(paths):
                    try:
                        a = np.asarray(Image.open(p).convert("L").resize(WORK, Image.LANCZOS),
                                       dtype=np.uint8)
                    except Exception as exc:  # noqa: BLE001
                        print(f"    [读取失败] {os.path.basename(p)}: {exc}")
                        continue
                    r = pred.predict(a)
                    prob, thr = r["probability"], r["threshold"]
                    if prob is None or thr is None:
                        continue
                    is_fp = int(prob >= thr)
                    n_fp += is_fp
                    rows.append({"model": label, "clip": bool(clip), "source": src,
                                 "photo_path": p, "photo_name": os.path.basename(p),
                                 "ml_prob": round(float(prob), 6),
                                 "threshold": round(float(thr), 6),
                                 "pred_stego": is_fp})
                    if (i + 1) % 100 == 0:
                        print(f"    [{label} clip={int(clip)} {src}] {i+1}/{len(paths)} "
                              f"({time.time()-t0:.0f}s, 累计误报 {n_fp})", flush=True)
                print(f"  {label:>5} clip={int(clip)} {src:>7}: "
                      f"{n_fp}/{len(paths)} 误报  ({time.time()-t0:.0f}s)", flush=True)
    return pd.DataFrame(rows)


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
                "protocol": f"clean real photos, {WORK[0]}x{WORK[1]} LANCZOS, "
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
    args = ap.parse_args()

    models = DEFAULT_MODELS
    if args.models:
        models = []
        for item in args.models.split(","):
            if "=" in item:
                label, path = item.split("=", 1)
                models.append((label.strip(), path.strip()))
    clips = tuple(bool(int(c)) for c in args.clips.split(",") if c.strip() != "")

    print("OOD 干净真实照片误报率评估")
    print(f"  模型: {[m[0] for m in models]}   clip_outliers={clips}")
    sources = gather_sources(args)
    if not sources:
        sys.exit("没有任何可用语料 —— 检查 --campus-dir / --div2k-dir / --alaska-dir。")
    print(f"  合计 {sum(len(v) for v in sources.values())} 张干净照片\n")

    df = evaluate(models, sources, clips, args.n_sigma)
    if df.empty:
        sys.exit("评估没有产出任何行。")
    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(OUT_RAW, index=False)
    summary = summarize(df)
    summary.to_csv(OUT_SUM, index=False)
    print(f"\n逐图 -> {os.path.relpath(OUT_RAW, PROJ)}  ({len(df)} 行)")
    print(f"汇总 -> {os.path.relpath(OUT_SUM, PROJ)}\n")
    print(summary.to_string(index=False))
    print("\n下一步: python experiments/build_results_table.py  (刷新权威结果表)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
