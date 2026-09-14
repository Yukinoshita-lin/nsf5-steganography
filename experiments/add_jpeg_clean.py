"""
experiments/add_jpeg_clean.py — 给校园 v2 语料补上 "JPEG 干净" 行。

背景 (2026-09-14 审计)
----------------------
README 里一直写着 `py src/_add_jpeg_clean.py` 生成 `dataset_campus_v2_jpeg.csv`,
但**这个脚本在仓库里从未存在过**(git 全历史查无此文件)。当年那次运行留下的
产物埋了一个真实缺陷:

  414 个 `clean_jpeg` 行用了 **1413..1826** 这一块独立 photo_id, 而它们的特征
  与对应的 `clean` 行逐位相同 (max|Δ| = 7e-9) —— 也就是说:
    1. 这些行是 clean 行的**副本**, 不是 JPEG 重编码过的图;
    2. 它们被当成 414 张**独立源图**, 于是"按源图 holdout"可以被绕过:
       某张源图的含密变体在训练集、它的副本在验证集 —— 正是项目自己
       (experiments/README.md 评测纪律 1) 明令禁止的源图泄漏。
  实测影响: 143d 的 held-out AUC 从 0.8946 掉到 0.7555, 53d 从 0.9100 掉到
  0.7503, 弱档 (nsF5 p3 d=0.25) 检出从 85.3%/87.2% 掉到 44.2%/29.8%。

本脚本是那个缺失脚本的**正确版本**:

  - photo_id **继承源图**(不再另开一块 id), 因此按源图分组的划分天然成立;
  - `clean_jpeg` 是真实的 JPEG 往返 (重编码 → 解码 → 提特征), 而不是 clean 的副本,
    这样它才真的提供"带 JPEG 压缩痕迹的干净样本"这一域信息;
  - 写盘前做不变量校验: 每个 photo_id 的 variant 集合必须完全一致 (旧产物就是
    在这里破了 —— 414 个 id 只有单一 variant), 不满足直接报错退出。

用法
----
    python experiments/add_jpeg_clean.py                       # 默认路径
    python experiments/add_jpeg_clean.py --quality 90 --verify
    python experiments/add_jpeg_clean.py --csv-in <a> --csv-out <b>
"""
from __future__ import annotations

import argparse
import glob
import io
import os
import sys

import numpy as np
import pandas as pd
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))

from featurize_v2 import ALL_FEATURE_NAMES, featurize_v2  # noqa: E402
from pathutil import rel_from_proj  # noqa: E402

DEFAULT_IN = os.path.join(PROJ, "data", "dataset_campus_v2.csv")
DEFAULT_OUT = os.path.join(PROJ, "data", "dataset_campus_v2_jpeg.csv")
DEFAULT_PHOTOS = os.path.join(PROJ, "data", "campus_jpg")
WORK = (512, 512)
IM_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tif", "*.tiff", "*.pgm")
VARIANT = "clean_jpeg"


def list_photos(photo_dir: str) -> list:
    """与 src/make_dataset.py 完全一致的枚举方式 (normcase + sorted), 否则
    photo_id 与源图会对不上。"""
    return sorted({os.path.normcase(p) for ext in IM_EXTS
                   for p in glob.glob(os.path.join(photo_dir, ext))})


def jpeg_roundtrip(img: Image.Image, quality: int) -> Image.Image:
    """灰度 → JPEG 编码 → 解码。返回解码后的灰度图 (带 JPEG 压缩痕迹)。"""
    buf = io.BytesIO()
    img.convert("L").save(buf, "JPEG", quality=quality)
    buf.seek(0)
    with Image.open(buf) as im:
        return im.convert("L").copy()


def featurizer(device: str):
    """优先用 GPU 版 (与 make_dataset 建语料时同一实现), 不可用时退回 CPU 版。

    两者的一致性由 src/test_pipeline.py::test_v2_cpu_gpu_consistency 兜底
    (2026-09-14 修复后 max|d| ~3e-5)。
    """
    if device != "cpu":
        try:
            sys.path.insert(0, os.path.join(PROJ, "gpu"))
            from featurize_v2_gpu import extract_features_v2_gpu
            return lambda a: extract_features_v2_gpu(a[None], chunk=1,
                                                    device=device)[0]
        except Exception as exc:  # noqa: BLE001
            print(f"  [提示] GPU 特征不可用 ({type(exc).__name__}: {exc}), 退回 CPU 版")
    return lambda a: featurize_v2(a)


def check_grouping(df: pd.DataFrame) -> None:
    """不变量: 每个 photo_id 的 variant 集合必须一致 (禁止孤儿 id 块)。"""
    sets = df.groupby("photo_id")["variant"].apply(frozenset)
    uniq = sets.value_counts()
    if len(uniq) > 1:
        bad = [s for s in uniq.index if s != sets.iloc[0]]
        broken = sets[sets.isin(bad)]
        raise SystemExit(
            f"分组不变量被破坏: {len(broken)} 个 photo_id 的 variant 集合与其余不同 "
            f"(例: id={list(broken.index[:3])} -> {sorted(list(bad[0])) if bad else '?'})。\n"
            f"这正是 2026-09-14 审计发现的缺陷形态 —— 单独成块的 id 会被当成独立源图, "
            f"让按源图划分失效。拒绝写出这样的语料。")


def main() -> int:
    ap = argparse.ArgumentParser(description="给校园 v2 语料补 JPEG 干净行 (photo_id 继承源图)")
    ap.add_argument("--csv-in", default=DEFAULT_IN)
    ap.add_argument("--csv-out", default=DEFAULT_OUT)
    ap.add_argument("--photos", default=DEFAULT_PHOTOS)
    ap.add_argument("--quality", type=int, default=90, help="JPEG 重编码质量 (默认 90)")
    ap.add_argument("--device", default="auto", choices=("auto", "cuda", "cpu"))
    ap.add_argument("--verify", action="store_true", help="只校验已有产物的分组不变量")
    args = ap.parse_args()

    if args.verify:
        df = pd.read_csv(args.csv_out)
        check_grouping(df)
        n_id, n_row = df.photo_id.nunique(), len(df)
        print(f"ok {os.path.basename(args.csv_out)}: {n_row} 行 / {n_id} 源图, "
              f"每个源图的 variant 集合一致")
        return 0

    if not os.path.exists(args.csv_in):
        sys.exit(f"输入语料不存在: {args.csv_in}\n"
                 f"先跑 `python src/make_dataset.py data/campus_jpg 512x512 "
                 f"--out campus_v2 --feature-set v2 --variants all`。")
    df = pd.read_csv(args.csv_in)
    if VARIANT in set(df["variant"]):
        sys.exit(f"{args.csv_in} 已经含 {VARIANT} 行; 请从干净的 campus_v2 重新生成。")

    photos = list_photos(args.photos)
    ids = sorted(df.photo_id.unique())
    if len(photos) != len(ids):
        sys.exit(f"源图数({len(photos)}) 与 photo_id 数({len(ids)}) 不一致, "
                 f"无法把 id 映射回源图 —— 拒绝猜测。")
    offset = ids[0]
    if ids != list(range(offset, offset + len(ids))):
        sys.exit(f"photo_id 不是从 {offset} 开始的连续区间, 无法安全映射。")

    feats = [c for c in ALL_FEATURE_NAMES if c in df.columns]
    if len(feats) != len(ALL_FEATURE_NAMES):
        sys.exit(f"输入语料只有 {len(feats)}/{len(ALL_FEATURE_NAMES)} 个 v2 特征列, "
                 f"不是 143 维语料 (缺例: "
                 f"{[c for c in ALL_FEATURE_NAMES if c not in df.columns][:5]})")

    extract = featurizer(args.device)
    n_photos = len(ids)
    print(f"给 {n_photos} 张源图各生成 1 行 {VARIANT} "
          f"(JPEG q={args.quality}, 工作尺寸 {WORK[0]}x{WORK[1]}, photo_id 继承源图)")
    new_rows = []
    for i, pid in enumerate(ids):
        path = photos[i]
        try:
            im = Image.open(path).convert("L").resize(WORK, Image.LANCZOS)
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"读取 {os.path.basename(path)} 失败: {exc}")
        rt = jpeg_roundtrip(im, args.quality)
        # 关键: photo_id 用源图的 id, 不另开一块 id 空间
        row = {c: 0.0 for c in ALL_FEATURE_NAMES}
        row.update({c: float(v) for c, v in zip(ALL_FEATURE_NAMES, extract(np.asarray(rt, dtype=np.uint8)))})
        row.update({"label": 0, "photo_id": int(pid), "variant": VARIANT,
                    "method": "", "p": np.nan, "density": np.nan,
                    "changed_frac": ""})
        new_rows.append(row)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{n_photos}")

    out = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
    out = out[list(df.columns)]
    # clean_jpeg 与 clean 必须**不同** (旧产物是逐位相同的副本),
    # 否则它不提供任何新信息, 只是把干净类重复了一遍。
    a = (out[out.variant == "clean"].set_index("photo_id").sort_index()[feats].values)
    b = (out[out.variant == VARIANT].set_index("photo_id").sort_index()[feats].values)
    d = np.abs(a - b)
    print(f"  clean vs {VARIANT}: max|Δ|={d.max():.3e}, 不同的特征列 {int((d.max(0) > 0).sum())}/{len(feats)}")
    if d.max() == 0.0:
        sys.exit(f"生成的 {VARIANT} 与 clean 完全相同, 没有提供任何新信息 —— 中止。")

    check_grouping(out)
    df_out = out.sort_values(["photo_id", "variant"], kind="stable").reset_index(drop=True)
    df_out.to_csv(args.csv_out, index=False)
    print(f"已写出 -> {rel_from_proj(args.csv_out, PROJ)}  "
          f"({len(df_out)} 行 / {df_out.photo_id.nunique()} 源图, "
          f"{os.path.getsize(args.csv_out) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
