# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.6.0] - 2026-09-13

Verifiability hardening: every claim the project makes should now be checkable
by running something in the repo, and the claims that were not true have been
corrected rather than kept.

### Added

- `gpu/train_cnn.py` and `gpu/models/{xunet,yenet}.py`. The paper referenced
  these paths but they did not exist, so the "53-D features beat a CNN in the
  small-sample regime" claim had no supporting data anywhere. The models are
  reimplementations from the papers' descriptions (Xu et al. 2016, Ye et al.
  2017), not the authors' official code, and are labelled as such. Training
  splits strictly by source photo and reports train AUC beside val AUC, which is
  what distinguishes "did not converge" from "overfit". Measured on BOSSbase:
  Ye-Net 0.9541 [0.9463, 0.9630]; LGB-143d 0.7529; LGB-53d 0.7172; LGB-11d
  0.7128; Xu-Net 0.5007 with chance-level *training* AUC, i.e. not converged.
- `gpu/models/{xunet,yenet}.py` are joined by `gpu/train_cnn.py`, which lives in
  `gpu/` rather than under the (untracked) thesis directory because the CNN
  belongs to the toolkit, not to a paper.
- `scripts/build_cpp.py` plus `make cpp` / `make cpp-clean`.
- `src/cpplib.py`, resolving the accelerator filename per platform.
- `src/test_pipeline.py`: feature contracts, SRM kernels (numpy vs torch),
  the `analyze()` result contract, degenerate images, and ML model loading.
- CI jobs: `pytest`, and a headless GUI job under `xvfb-run`.
- `.github/workflows/webapp-tests.yml` (previously untracked, so the browser
  regression suite had never run).
- Two deployable models are now in the repository.

### Changed

- C++ accelerators are built from source on all three platforms instead of
  shipping a Windows-only `.dll`; no binaries are committed.
- `sota_compare.py` raises on missing feature columns instead of silently
  degrading, keeps `feat_set` and `dataset` as separate columns, and computes
  bootstrap CIs by resampling source photos rather than images.
- `fig_sota` reads the merged table and scales its x-axis to the data (it
  hardcoded `xlim(0.5, 0.85)`, which would draw a 0.95 bar off the canvas).
- `models/*.joblib` moved from "ignored" to "two whitelisted files";
  `lightgbm` added as a dependency (the shipped models are LightGBM pickles, so
  without it a clone still got `available=False`); `scikit-learn` pinned `<2`.
- `pyproject.toml` declares `xgboost`, the missing `py-modules` entries, a
  `thesis` extra, and pytest configuration. The `dev` extra promised pytest
  while the suite was bare asserts with `main()` guards.
- `teaching/videos/` is ignored: 134 MB of generated output, rebuildable from
  `teaching/README.md`.

### Fixed

- `qa_sheet()` wrote a 33-byte zero-height PNG when a chapter produced no beat
  timestamps, then aborted the run, so later chapters were silently never built
  and already-listed chapters were never retried. It now refuses to run with no
  timestamps, and a failing chapter is reported, skipped, and left retryable.
  Two unusable QA contact sheets (one 33-byte, one missing) were rebuilt.
- The eleven rendered videos on disk had been renamed to their Chinese titles
  while `index.html`/`durations.json` address them as `chNN.mp4`, so every link
  on the local playback page 404'd.
- `test_false_positive.py` contained `ok = ok` — a no-op assignment that
  discarded the loop's failure signal, leaving the whole test resting on one
  assertion.
- `solve_wet_paper()` drew its traversal order from the global NumPy RNG, so the
  same input produced different (equally valid) solutions run to run; the order
  now derives from a hash of the inputs.
- `encode_string()`/`decode_string()` used ASCII with `errors="replace"`, so any
  non-ASCII message silently decoded as `?`. Now UTF-8.
- `cross-platform.yml` used `python` in a job with no Python setup step.

### Known gaps

- The two shipped models have **no in-repo producer**: `src/train_model.py`
  trains an LR/RF/GB/XGB family, and the LightGBM runs that produced them were
  never scripted. They work, but they are not reproducible from this repository.
- The thesis and the JOSE paper are deliberately not in this repository
  (`thesis/` and `paper*` are ignored). What *is* tracked is the code they need
  to be reproducible: the toolkit in `gpu/` and the experiment orchestration in
  `experiments/`. Their outputs (`experiments/data/`, `experiments/figs/`) are
  generated artefacts and stay out.
- The experiment scripts were moved out of `thesis/exp/` and `thesis/tools/`
  because a tracked test or experiment that imports from an ignored directory is
  reproducible only on the author's machine. Fixing that also removed four
  scripts' hardcoded `F:\Steganography` paths.

## [Unreleased] - Teaching project

### Added

- Website nsF5 comparison lab (Lab 4, `#nsf5`): embeds the same message into the
  demo image with either naive LSB replacement or the project's real nsF5
  strategy ported to JS (per-block Hamming syndrome coding, magnitude-decrement
  modification, wet pixels 127/128/129 handed to the wet-paper solver, seeded
  permutation of the block path mirroring `permute_index`/`_pool_positions`).
  The lab shows changed-pixel count, embedding efficiency (bits per change),
  PSNR, a difference map and the same in-browser chi-square/RS detector, so
  learners can see that nsF5 both changes fewer pixels and leaves a weaker
  statistical fingerprint; includes a decode round-trip and `data-*` test hooks.
- Handbook ch05 (zh + en): a hand-worked GF(2) example for the wet-paper solver
  (single-column hit, two-column XOR, and when Gaussian elimination is actually
  needed), plus the solvability criterion (dry columns must span GF(2)^p) and
  why free variables are set to 0 to minimize changes.
- Handbook ch03 (zh + en): reused the webapp's chi-square pair-count and
  clean-vs-stego bar figures so the "visual statistics" chapter has concrete
  imagery matching the theory.
- Website payload-scan honesty: `scan-demo.json` now records the real
  changed-pixel footprint (`changed_pixels`) alongside the nominal capacity
  fraction, and the scan note shows "改动像素≈N%" so the density axis is no
  longer misleading.
- Website LSB live steganalysis: after embedding, the page runs real chi-square
  (Westfeld) and RS analysis in JavaScript on the current image and shows
  `chi2 p · RS Gn → verdict`, plus a **changed-pixel mask** canvas (white =
  modified LSB) - so learners can embed a sentence and immediately see the
  statistical fingerprint that detection catches.
- Website a11y/conventions: label `for`/id association for the Hamming / wet-paper
  / ML / payload controls, `aria-live` on result readouts, and a live decode
  note. (Details in the reference-removal note below.)
- Website LSB lab round-trip: a **Decode it back** button that reads the length
  header and payload straight out of the current canvas LSBs and shows the
  recovered message, so learners can embed a sentence and see it come back (the
  format matches `ns5_core.encode_string`); a live decode note replaces the
  change count.
- Website structure/hierarchy: an "on this page" contents map right after the
  hero groups the whole page into four themed parts (hands-on labs / how it
  works / learning path / FAQ), and every section carries a matching part badge,
  giving the single-page lab a clear learning progression.
- Website FAQ: a bilingual accordion section (8 common questions on PNG vs JPEG,
  why LSB is invisible, chi-square/RS detection, Hamming matrix coding, nsF5 vs
  F5, choosing a cover and raw-pixel CNNs), plus a "still stuck / try it /
  license" card row; added to the top nav and scroll-spy. The license FAQ entry
  states the correct **Apache-2.0** terms (matching LICENSE/NOTICE).
- Bit-plane layering teaching visual (`lsb-layering-{zh,en}.png` in `webapp/assets`
  and `img009.png` in both handbook assets): shows an 8-bit image as eight
  stacked bit planes and proves each must be weighted by `2**k` before they can
  be summed back into the original.
- Website LSB experiment extension: a bit-plane layering explorer that switches
  between **Extract plane** (pull out any single bit plane to inspect) and
  **Restack (weighted)** (toggle planes on/off and watch the weighted sum
  reconstruct the original), plus the new weighted-stacking figure; keyboard
  operable and covered by the interactive test.
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

- Repo hygiene: `data/` generated datasets (`dataset_*.csv`), `campus_jpg/` and
  `data/_*.log` training logs, plus `webapp/tests/node_modules/.npm-cache` are
  now gitignored (kept locally; 7.8 GB historical backup moved out of the repo
  tree to external storage).
- Website i18n: the self-test section's part badge showed the raw key `part5`
  (the key was missing from both dictionaries); the "on this page" contents map
  now also lists the nsF5 lab and the self-test quiz, and the static fallback
  for the FAQ notebook count says 10 (matching the dictionaries and the repo).
- Website: removed a dead `preconnect` to fonts.googleapis.com (no webfont is
  loaded; the design system uses local font stacks).
- Core: `ns5_core._embed_into_image` no longer silently truncates an over-capacity
  message; it now validates the payload against the image's body-pool size and
  raises a clear `ValueError` with the number of Hamming blocks needed vs
  available.
- Core: RGB images no longer report `cover_changed = 0` - the `stego` buffer was
  re-bound to the source image so the clean/stego comparison was a self-comparison;
  the copy is kept independent now (also fixes the `efficiency.py` measured curve
  when fed RGB data).
- Core: message encoding switched from ASCII `errors="replace"` to UTF-8, so
  non-ASCII text (e.g. Chinese) is preserved instead of silently becoming `?`.
- Core: wet-paper pair-search seeding is deterministic (derived from the dry cols
  and target), no longer perturbs the global NumPy RNG, so identical inputs give
  identical stego images.
- Core: `efficiency.measured_efficiency` now sizes the test message within the
  real body-pool capacity (it previously filled to an over-estimated capacity and
  would overflow once embed validation was added).
- Assets: `stego_detect` and `scan_curves` demo messages clamped to fit the 256x256
  / 512x512 cover capacities (previously over-capacity and silently failing).
- GUI: "Decode" and "Analyze" now operate on the generated stego image instead of
  always the loaded cover, fixing the embed -> decode/analyze flow.
- Tests: added coverage for `get_image_hash`, `derive_seed`, `solve_wet_paper`,
  `gauss_solve_GF2` and `permute_index` (previously untested), plus regression
  tests for the UTF-8 round-trip, RGB `cover_changed`, capacity error and wet-paper
  determinism.
- Packaging: `pyproject.toml` `py-modules` now includes `featurize_v2`,
  `py_features` and `srm_filter` (they were missing from the wheel, which broke
  `import make_dataset` and the `ml_predict`/GUI feature path), and declares
  `xgboost` as a dependency.
- Docs: corrected stale handbook page counts (Chinese 94 -> 66, English 80 -> 72),
  fixed the webapp FAQ license statement to Apache-2.0, and corrected the
  notebook count (12 -> 10).
- CI: added `webapp-tests.yml` that serves the webapp and runs the Playwright
  interactive + layout tests (previously these were never wired into any workflow),
  and added a missing `workflow_dispatch` trigger to `ci.yml`.
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
