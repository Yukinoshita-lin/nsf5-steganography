"""
生成 GPU-CNN 训练用的整图像数据集。

- 输入: F:\\DCIM\\Camera 校园照片 (*.jpg)
- 每张: 转 512x512 灰度; 得到 1 张干净图 + 4 档含密变体 (nsF5/matrix, 弱→强)。
- CNN 输入 = 完整 512x512 (不裁剪): 隐写统计只在整图尺度才稳定, 中心裁剪会损失信号。
- 输出: gpu/data/imageset.npz  {x:(N,512,512) u8, y:(N,), photo_id:(N,), method/p/density 元数据}

用法:  python gpu/make_imageset.py [照片目录] [N张] [--out NAME] [--id-offset N]
  --out NAME    输出 gpu/data/imageset_<NAME>.npz (默认 imageset.npz)
  --id-offset N 每组源图 photo_id 加偏移, 保证多数据源合并时源分组互不冲突
"""
from __future__ import annotations

import os, sys, glob, time, argparse
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "src"))

from cppembed import embed_string

PHOTO_DIR = r"F:\Steganography\data\campus_jpg"  # 纯校园照片(已分离 DIP4E tif)
IMG = 512            # 输入边长 = 嵌入尺寸, 保留全部隐写统计 (裁剪会丢掉信号)
FULL = 512           # 嵌入工作尺寸
VARIANTS = [         # (method, p, density): 弱→强
    ("nsF5", 3, 0.30),
    ("nsF5", 2, 0.50),
    ("matrix", 3, 0.50),
    ("nsF5", 2, 0.95),
]


def capacity_bytes(npix: int, p: int, head_pixels: int = 0) -> int:
    cap_bits = (npix - head_pixels) * p // ((1 << p) - 1)
    return max(1, cap_bits // 8)


def center_crop(a: np.ndarray, size: int) -> np.ndarray:
    h, w = a.shape[-2:]
    y0, x0 = (h - size) // 2, (w - size) // 2
    return a[..., y0:y0 + size, x0:x0 + size]


def main(photo_dir: str = PHOTO_DIR, n_photos: int = 0, out_name: str = "",
         id_offset: int = 0):
    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tif", "*.tiff", "*.pgm")
    photos = sorted({os.path.normcase(p) for ext in exts
                     for p in glob.glob(os.path.join(photo_dir, ext))})
    if n_photos > 0:
        photos = photos[:n_photos]
    if not photos:
        print(f"未在 {photo_dir} 找到图像"); return
    print(f"{len(photos)} 张照片(含 jpg/tif 等), 嵌入尺寸 {FULL}x{FULL}, 裁剪 {IMG}x{IMG}")

    out_dir = os.path.join(HERE, "data")
    os.makedirs(out_dir, exist_ok=True)
    prefix = f"imageset_{out_name}" if out_name else "imageset"
    x_path = os.path.join(out_dir, prefix + "_x.npy")   # 大数组 memmap, 非压缩
    aux_path = os.path.join(out_dir, prefix + ".npz")   # y/photo_id/meta 元数据

    per_photo = 1 + len(VARIANTS)
    n = len(photos) * per_photo
    # memmap 逐张落盘: 全程内存仅单张水平, 避免大数组一次性堆叠 OOM
    xm = np.lib.format.open_memmap(x_path, mode="w+", dtype=np.uint8,
                                   shape=(n, IMG, IMG))
    ys, ids, metas = [], [], []
    t0 = time.perf_counter()
    row = 0
    for pi, path in enumerate(photos):
        a = np.asarray(Image.open(path).convert("L").resize((FULL, FULL), Image.LANCZOS),
                       dtype=np.uint8)
        npix = a.size
        base = id_offset + pi
        # 干净图
        xm[row] = center_crop(a, IMG); ys.append(0); ids.append(base)
        metas.append(("clean", "", "", "")); row += 1
        # 含密变体
        for meth, p, dens in VARIANTS:
            nb = int(capacity_bytes(npix, p) * dens)
            try:
                stego, rep, _ = embed_string(a, "S" * nb, method=meth, p=p,
                                             check=False, fast_permute=True)
            except Exception as e:
                print(f"  [嵌入失败] {os.path.basename(path)} {meth} p={p}: {e}"); continue
            xm[row] = center_crop(stego, IMG); ys.append(1); ids.append(base)
            metas.append((meth, str(p), f"{dens:.2f}", os.path.basename(path))); row += 1
        if (pi + 1) % 25 == 0:
            print(f"  进度 {pi+1}/{len(photos)}, {time.perf_counter()-t0:.0f}s")

    del xm  # flush memmap
    y = np.array(ys, np.int64)
    photo_id = np.array(ids, np.int64)
    np.savez_compressed(aux_path, y=y, photo_id=photo_id,
                        meta=np.array(metas, dtype=object))
    n_clean = int((y == 0).sum()); n_stego = int((y == 1).sum())
    print(f"完成: {n_clean+n_stego} 样本, clean={n_clean} stego={n_stego},"
          f" 耗时 {time.perf_counter()-t0:.0f}s")
    print(f"已写出 -> {x_path} (memmap) / {aux_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*", help="照片目录(可多个, 依次生成)")
    ap.add_argument("--out", default="", help="输出名 imageset_<NAME> (默认 imageset)")
    ap.add_argument("--id-offset", type=int, default=0)
    ap.add_argument("-n", type=int, default=0, help="每目录截取前 N 张(0=全部)")
    a = ap.parse_args()
    for i, d in enumerate(a.dirs or [PHOTO_DIR]):
        main(d, a.n, a.out, a.id_offset)