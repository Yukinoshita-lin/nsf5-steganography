# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased] - Teaching project

### Added

- README refresh: interactive teaching-website section, updated bilingual
  handbook links, current directory tree, and cross-platform command examples.
- Interactive bilingual learning website (`webapp/`): LSB bit-plane lab and
  Hamming syndrome-coding demo in the browser, project visuals, ML charts,
  12-week roadmap, and one-click language switching; served at the GitHub
  Pages root while the Jupyter Books remain at `/zh` and `/en`.
- Website additions: wet-paper / danger-pixel visual section, LSB histogram
  and changed-pixel-mask figures (bilingual variants), and `?lang=zh|en` URL
  switching for sharing and automated checks.
- Website labs: interactive wet-paper dry-position solver (toggle wet/dry cells
  and solve syndrome on dry columns) and an ML decision-threshold playground
  (drag threshold, live FP/FN rates).
- Website UX: wet-paper auto-play animation, mobile navigation menu, and
  scroll-spy highlighting of the active section.
- Website data-viz lab: payload scan (real project statistics on a campus
  photo) with chi-square p / RS estimate / ML probability curves synced to an
  embedding-density slider.
- Website tests: `webapp/tests/interactive.mjs` runs the full interactive lab
  (language toggle, LSB embed, Hamming, wet auto-play, threshold/payload
  sliders, mobile menu) in Chrome/Edge with console-error detection.
- Website accessibility: Hamming and wet-paper canvases are keyboard-operable
  (arrow keys + Space) with visible focus outlines; live result captions are
  announced via `aria-live`.
- Website layout/perf: lazy-loading below-the-fold images and a browser layout
  test (`webapp/tests/layout.mjs`) covering desktop/mobile overflow, broken
  images and missing alt text.
- README: full English overview section (features, cross-platform quick start,
  learning resources and license) alongside the Chinese documentation.
- teaching/README: bilingual version - full English teaching guide followed by
  the Chinese section.
- Cross-platform (Linux/macOS/Windows) support:
  - `fsfeatures.get_lib()` falls back to pure-Python 11-D features when the
    Windows DLL is missing;
  - `cppembed.embed_string()` falls back to the pure-Python embedder when
    `cpp/nsf5embed.dll` is unavailable;
  - root `Makefile` with `install/test/e2e/notebooks/dataset/web` targets;
  - `.github/workflows/cross-platform.yml` CI matrix (Ubuntu/macOS/Windows)
    runs algorithm tests and both feature/embedding fallbacks.
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
