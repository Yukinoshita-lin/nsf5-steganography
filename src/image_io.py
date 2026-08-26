"""8bit 图像读写 (Pillow) 与工具。"""
from __future__ import annotations
import os
import numpy as np
from PIL import Image

SUPPORTED = (".png", ".bmp", ".jpg", ".jpeg", ".tif", ".tiff")


def load_image(path: str) -> np.ndarray:
    """读取图像 → uint8 ndarray (灰度 2D 或 RGB 3D)。"""
    im = Image.open(path).convert("L")
    return np.asarray(im, dtype=np.uint8)


def load_as_gray(path: str) -> np.ndarray:
    """强制转 8bit 灰度 (隐写主轴灰平面)。"""
    im = Image.open(path).convert("L")
    return np.asarray(im, dtype=np.uint8)


def save_image(image: np.ndarray, path: str):
    im = Image.fromarray(np.ascontiguousarray(image))
    im.save(path)


def default_out_path(src: str, tag: str, out_dir: str) -> str:
    base = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(out_dir, f"{base}_{tag}.png")