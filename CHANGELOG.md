# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] - Teaching project

### Added

- GUI teaching animation: "matrix coding demo" panel now supports
  **auto-play** (random block -> highlight matched syndrome column -> flip ->
  verify) with speed control and stop; GUI smoke test covers the animation.
- Per-chapter Colab/Jupyter notebooks (`notebooks/`): bits & pixels, Python
  toolchain, LSB + steganalysis, matrix embedding, nsF5 + wet paper, hash
  keying, ML foundations, ML steganalysis, engineering, capstone. Each notebook
  self-clones the repo and auto-installs dependencies. All ten notebooks are
  executed end-to-end in a local kernel (10/10 pass).
- `src/ml_predict.py` - 53-D interpretable model inference support (selects the
  53 feature columns from the 143-D extractor).
- `src/py_features.py` - pure-Python 11-D feature extractor; `featurize_v2.py`
  and `ml_predict.py` fall back to it when the Windows C++ DLL is unavailable,
  so Colab/Linux/Docker can run feature extraction and trained-model inference.
- `scripts/download_datasets.py` - one-click BOSSbase 1.01 downloader.
- `docker/Dockerfile` + `docker-compose.yml` - JupyterLab teaching image
  (Linux; algorithm self-tests pass during build).
- `.github/workflows/docker.yml` - CI that builds the teaching image and smoke-
  tests algorithm tests plus the pure-Python feature fallback inside it.
- `teaching/web/` - bilingual Jupyter Book scaffolding (zh/en) with a
  DOCX->Markdown converter (`teaching/web/docx2md.py`) and GitHub Pages
  workflow building both books into one site.

### Fixed

- README Zenodo DOI badge pointed to an unrelated record
  (10.5281/zenodo.14851234); corrected to the project's actual archive
  10.5281/zenodo.22543629.

## [1.6.0] - 2026-09-07

### Added — OOD Robustness Journal Paper

- `thesis/journal_paper.tex` + `thesis/journal_paper.pdf` — IEEE double-column journal
  paper (7 pages + Chinese abstract) titled "Why Your JPEG Steganalyzer Fails on Real
  Photos: An OOD-Robustness Study with 53-D Interpretable Features".
- `src/stc.py` — Syndrome-Trellis-Code (STC) encoder with 2-state Viterbi, sub-trellis
  size h=4, and wet-pixel mask. Embedding efficiency within 0.1% of theoretical bound.
- `src/distortion.py` — Distortion function Protocol interface.
- `src/juniward.py` — J-UNIWARD cost (Daubechies-8 wavelet, σ=10³).
- `src/hill.py` — HILL cost (two-stage high-pass residual, ξ=10³).
- `gpu/models/xunet.py` — Xu-Net CNN steganalyzer.
- `gpu/models/yenet.py` — Ye-Net CNN steganalyzer with SELU and Gaussian activation.
- `gpu/train_cnn.py` — Unified training script (Adam + cosine LR, 5-fold GroupKFold).
- `thesis/exp/ablation_5stage.py` — 5-stage feature ablation
  (B11 → +P20 → +LP20 → +T2 → +SRM90).
- `thesis/exp/model_compare_4clf.py` — 4 classifiers × 5 feature subsets = 20 runs.
- `thesis/exp/sota_compare.py` — LGB-53D vs Xu-Net vs Ye-Net on BOSSbase.
- `thesis/exp/density_grid.py` — Per-(method, p, density) detection table.
- `thesis/exp/gen_figs.py` — One-click figure generator (9 PNGs).
- `data/ood_jpeg_test/build.py` — OOD real JPEG evaluation harness (n=300,
  Wilson 95% CI).

### Key Findings

- **Finding 1 (5-stage ablation).** B11(11d)→+P20(31d)→+LP20(51d)→+T2(53d)→+SRM90(143d)
  yields OOF AUC 0.9740 → 0.9787 → 0.9857 → 0.9856 → 0.9813. The 90-D SRM block
  contributes **−0.0043** AUC, because its 30 kernels have average inter-kernel
  Pearson |r| of 0.9767.
- **Finding 2 (4-model compare).** LightGBM dominates across all five subsets.
  Random Forest collapses on 143-D (0.9845 → 0.9503) — a 3.4-pp drop that
  quantifies SRM's noise amplification in non-LGB ensembles.
- **Finding 3 (density scan).** 53-D LightGBM detects >92% of nsF5 at d=0.25
  (vs. 48% for v1 baseline) and >99% of LSB/matrix at all tested densities.
- **Finding 4 (OOD real JPEG).** 143-D: 46/300 (15.33%, 95% CI [11.70%, 19.85%]).
  53-D: 26/300 (8.67%, 95% CI [5.96%, 12.46%]). Two-proportion z=2.50, p=0.012.
  Relative FP reduction 43%, statistically significant at α=0.05.

### Changed

- README.md bumped to v1.6.0 with paper section + experiment table.
- 8-split verification: 53-D wins 7/8 splits with mean +0.014 AUC over 143-D.

### License

- Apache-2.0 (LICENSE + NOTICE updated with new paper + dependency list).

## [1.5.0] - 2026-09-06

### Added — Dual-Version Model

- 53-D slim model (`stego_classifier_v2_jpeg_lgb_51d.joblib`): removes SRM 90-D,
  held-out AUC 0.9100 (+0.015 vs 143-D), 8-split mean 0.9227 (+0.014).
- 143-D robust model (default, `stego_classifier.joblib`): held-out AUC 0.8946,
  multi-split mean 0.9085, OOD robust on real campus JPEG (7/8 correct clean,
  median 0.011).

## [1.4.0] - 2026-09-05

### Added — LGB Tuned

- Default classifier switched to LightGBM tuned (num_leaves=31, n_estimators=800,
  learning_rate=0.03, min_child_samples=10).
- 53-D slim variant benchmarked.

## [1.3.0] - 2026-08-30

### Added

- BOSSbase 1.01 dataset integration.
- SRM high-pass preprocessing (`src/srm_filter.py`).
- Multi-process make_dataset with `-j/--workers N`.

## [1.2.0] - 2026-08-20

### Added

- Wet-paper coding (Filler-Fridrich) integration with nsF5.
- C++ acceleration DLLs (`cpp/fsfeatures.dll`, `cpp/nsf5embed.dll`).

## [1.1.0] - 2026-08-10

### Added

- Image hash keying (SHA-256 + passphrase).
- Deterministic permutation (DLL + Python fallback).

## [1.0.0] - 2026-08-01

### Added

- Initial release: nsF5 embedding + LSB + F5 matrix coding.
- Blind steganalysis: chi-square (Westfeld) + RS analysis (Fridrich).
- GUI (tkinter).
- ASCII string embed/decode with passphrase.
