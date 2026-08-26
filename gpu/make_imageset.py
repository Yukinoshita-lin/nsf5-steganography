"""
生成 GPU-CNN 训练用的整图像数据集。

- 输入: F:\\DCIM\\Camera 校园照片 (*.jpg)
- 每张: 转 512x512 灰度; 得到 1 张干净图 + 4 档含密变体 (nsF5/matrix, 弱→强)。
- CNN 输入 = 完整 512x512 (不裁剪): 隐写统计只在整图尺度才稳定, 中心裁剪会损失信号。
- 输出: gpu/data/imageset.npz  {x:(N,512,512) u8, y:(N,), photo_id:(N,), method/p/density 元数据}

用法:  python gpu/make_imageset.py [照片目录] [N张]
"""
from __future__ import annotations

import os, sys, glob, time
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROJ, "src"))

from cppembed import embed_string

PHOTO_DIR = r"F:\DCIM\Camera"
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


def main(photo_dir: str = PHOTO_DIR, n_photos: int = 150):
    photos = sorted(glob.glob(os.path.join(photo_dir, "*.jpg")))[:n_photos]
    if not photos:
        print(f"未在 {photo_dir} 找到 jpg"); return
    print(f"{len(photos)} 张照片, 嵌入尺寸 {FULL}x{FULL}, 裁剪 {IMG}x{IMG}")

    xs, ys, ids, metas = [], [], [], []
    t0 = time.perf_counter()
    for pi, path in enumerate(photos):
        a = np.asarray(Image.open(path).convert("L").resize((FULL, FULL), Image.LANCZOS),
                       dtype=np.uint8)
        npix = a.size
        # 干净图
        xs.append(center_crop(a, IMG)); ys.append(0); ids.append(pi)
        metas.append(("clean", "", "", ""))
        # 含密变体
        for meth, p, dens in VARIANTS:
            nb = int(capacity_bytes(npix, p) * dens)
            try:
                stego, rep, _ = embed_string(a, "S" * nb, method=meth, p=p,
                                             check=False, fast_permute=True)
            except Exception as e:
                print(f"  [嵌入失败] {os.path.basename(path)} {meth} p={p}: {e}"); continue
            xs.append(center_crop(stego, IMG)); ys.append(1); ids.append(pi)
            metas.append((meth, str(p), f"{dens:.2f}", os.path.basename(path)))
        if (pi + 1) % 25 == 0:
            print(f"  进度 {pi+1}/{len(photos)}, {time.perf_counter()-t0:.0f}s")

    x = np.stack(xs).astype(np.uint8)
    y = np.array(ys, np.int64)
    photo_id = np.array(ids, np.int64)
    out_dir = os.path.join(HERE, "data")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "imageset.npz")
    np.savez_compressed(out, x=x, y=y, photo_id=photo_id,
                        meta=np.array(metas, dtype=object))
    print(f"完成: {x.shape[0]} 样本, clean={int((y==0).sum())} stego={int((y==1).sum())},"
          f" 耗时 {time.perf_counter()-t0:.0f}s")
    print(f"已写出 -> {out}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    d = args[0] if len(args) > 0 else PHOTO_DIR
    n = int(args[1]) if len(args) > 1 else 150
    main(d, n)