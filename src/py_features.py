"""Pure-Python v1 11-D feature extractor (no C++ DLL required).

Implements the same statistical features as ``cpp/fsfeatures.dll`` so that the
teaching notebooks, Colab, and Linux/Docker environments can run feature
extraction, v2 features, and the trained models without a Windows DLL.

The output dict uses the exact same keys and order as ``FSFeatures.features``:
    Rm, Sm, Rn, Sn, RS_Gr, RS_Gn, chi2_pvalue, diff_entropy,
    lsb_diff_entropy, median_prefix_p, chi2_stat
"""

from __future__ import annotations

import numpy as np

import steganalysis as SA


def _channel(image: np.ndarray) -> np.ndarray:
    img = np.ascontiguousarray(image, dtype=np.uint8)
    return img[..., 0] if img.ndim == 3 else img


def _median_prefix_p(ch: np.ndarray) -> float:
    flat = ch.ravel()
    total = flat.size
    ps = []
    for i in range(1, 21):
        end = max(64, int(total * i / 20))
        counts = np.bincount(flat[:end], minlength=256).astype(np.float64)
        _stat, p, _df = SA.chi2_stats(counts)
        ps.append(p if p is not None else 0.0)
    return float(np.median(ps))


def features(image: np.ndarray) -> dict:
    ch = _channel(image)
    counts = np.bincount(ch.ravel(), minlength=256).astype(np.float64)
    chi_stat, chi_p, _df = SA.chi2_stats(counts)
    rs = SA.rs_metrics(ch)
    return {
        "Rm": int(rs["Rm"]), "Sm": int(rs["Sm"]),
        "Rn": int(rs["Rn"]), "Sn": int(rs["Sn"]),
        "RS_Gr": float(rs["Gr"]), "RS_Gn": float(rs["Gn"]),
        "chi2_pvalue": float(chi_p if chi_p is not None else 1.0),
        "diff_entropy": float(SA.diff_entropy(ch)),
        "lsb_diff_entropy": float(SA.lsb_diff_entropy(ch)),
        "median_prefix_p": float(_median_prefix_p(ch)),
        "chi2_stat": float(chi_stat),
    }


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    demo = rng.integers(0, 256, (256, 256), dtype=np.uint8)
    f = features(demo)
    print("py_features ok:", {k: round(float(v), 4) for k, v in f.items()})
