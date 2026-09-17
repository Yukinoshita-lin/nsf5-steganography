# nsF5 Steganography - Teaching Project

## English Version

This folder turns the nsf5-steganography research repository into a
ready-to-use **teaching project**: animated GUI demos, one-click Colab/Jupyter
notebooks for every major chapter, a dataset downloader, a Docker/JupyterLab
image, and a bilingual web handbook (Jupyter Book + GitHub Pages).

### 0) Cross-Platform Quick Start (Linux / macOS / Windows)

The core algorithms, feature extraction, and both ML models fall back to pure
Python when the Windows DLLs are absent, so Linux/macOS/Colab work directly:

```bash
git clone https://github.com/Yukinoshita-lin/nsf5-steganography.git
cd nsf5-steganography
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
make test        # algorithm + steganalysis + false positives + pure-Python features
make e2e         # end-to-end demo
make notebooks   # regenerate the 10 chapter notebooks
```

On Windows use `.venv\Scripts\activate`; the GUI needs system tkinter
(Ubuntu/Debian: `sudo apt install python3-tk`). All three platforms are
verified continuously by `.github/workflows/cross-platform.yml`.

### 1) Per-Chapter Notebooks (One-Click Colab)

Every notebook starts with a bootstrap cell that clones the repository (when
needed) and installs missing packages, so it runs directly in Colab or in local
Jupyter/JupyterLab.

| Chapter | Notebook | Open in Colab |
|---|---|---|
| Ch. 1 Bits & pixels | `notebooks/01_bits_and_pixels.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/01_bits_and_pixels.ipynb) |
| Ch. 2 Python toolchain | `notebooks/02_python_toolchain.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/02_python_toolchain.ipynb) |
| Ch. 3 LSB & steganalysis | `notebooks/03_lsb_steganalysis.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/03_lsb_steganalysis.ipynb) |
| Ch. 4 Matrix embedding & F5 | `notebooks/04_matrix_embedding.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/04_matrix_embedding.ipynb) |
| Ch. 5 nsF5 & wet paper | `notebooks/05_nsf5_wet_paper.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/05_nsf5_wet_paper.ipynb) |
| Ch. 6 Hash keying | `notebooks/06_hash_keying.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/06_hash_keying.ipynb) |
| Ch. 7 ML foundations | `notebooks/07_ml_foundations.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/07_ml_foundations.ipynb) |
| Ch. 8 ML steganalysis | `notebooks/08_ml_steganalysis.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/08_ml_steganalysis.ipynb) |
| Ch. 9 Engineering | `notebooks/09_engineering.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/09_engineering.ipynb) |
| Ch. 10 Capstone | `notebooks/10_capstone.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/10_capstone.ipynb) |

Regenerate locally with:

```bash
python teaching/build_notebooks.py
```

### 2) Dataset Download

The standard BOSSbase 1.01 benchmark (~1.6 GB, 10,000 512x512 PGM images):

```bash
python scripts/download_datasets.py --out data/BOSSbase_1.01
```

Then follow the main README to build GPU/CPU datasets:

```bash
python gpu/make_imageset.py data/BOSSbase_1.01 2000
python src/make_dataset.py data/BOSSbase_1.01 --out bossbase
```

> Tip: Chapter 8's notebook includes a small synthetic demo, so the full
> features -> training -> prediction flow works without any external dataset.

### 3) Docker Teaching Image

Start JupyterLab inside a Linux container (no Windows DLLs needed; embedding
and decoding use the pure-Python fallback and pass the algorithm tests during
the image build):

```bash
docker compose up --build
# open http://localhost:8888  (token: nsf5)
```

Equivalent one-off commands:

```bash
docker build -f docker/Dockerfile -t nsf5stego-teaching .
docker run --rm -p 8888:8888 -v ${PWD}/notebooks:/workspace/notebooks nsf5stego-teaching
```

### 4) GUI Teaching Animation

The "matrix coding demo" panel in `src/gui.py` supports **auto-play / stop /
speed**: each round generates a random LSB block and target syndrome m,
highlights the matched H column, pauses for inspection, then automatically
applies the flip and verifies H*x == m - useful for classroom projection.

```bash
python src/gui.py      # requires a tkinter-enabled Python
python src/test_gui.py # GUI smoke test (includes the animation)
```

### 5) Web Handbook

`teaching/web/` builds a bilingual static site with Jupyter Book:

- `zh/` - Chinese handbook
- `en/` - English handbook
- Deployment workflow: `.github/workflows/pages.yml`
- Live URLs:
  - zh: <https://yukinoshita-lin.github.io/nsf5-steganography/zh/content/intro.html>
  - en: <https://yukinoshita-lin.github.io/nsf5-steganography/en/content/intro.html>

### 6) Teaching Videos (zh, narrated & animated — official v2)

`teaching/gen_videos_v2.py` renders one **narrated & animated** video per
handbook chapter (Ch. 1-11). Each beat of narration (edge-tts neural zh-CN
voice, default Yunxi) drives the visuals: bullets fade in on cue, original
PIL animations illustrate the core ideas (bit-plane stacking, uint8 overflow,
syndrome decoding, wet/dry marking, keyed permutations, gradient descent, ROC
operating points, ...), handbook figures get a Ken-Burns push-in, and
subtitles are burned in. Scenes/scripts live in `video_scenes_zh.py`, the
engine in `video_engine_v2.py` (NVENC GPU encoding when available, parallel
beat production, resumable narration cache).

```bash
python -m pip install pillow edge-tts
python teaching/gen_videos_v2.py                 # build missing chapters
python teaching/gen_videos_v2.py --ch 3,5        # rebuild selected chapters
python teaching/gen_videos_v2.py --ch all --voice zh-CN-XiaoxiaoNeural
python teaching/gen_videos_v2.py --ch 2,7 --sheets-only   # rebuild contact
                                                          # sheets only (offline)
```

- Outputs: `teaching/videos/zh/chNN.mp4` (official), `index.html`,
  `durations.json`; QA contact sheets in `teaching/videos/qa/v2_*.png`
- **Do not rename the mp4 files.** `index.html` and `durations.json` address
  them as `chNN.mp4`; renaming them to their chapter titles silently breaks
  local playback (the page 404s every video).
- `--sheets-only` re-samples a contact sheet from an already-rendered mp4 at
  even intervals, so it works without network or a re-encode. Use it to
  recover a missing/damaged sheet; use a full rebuild when you want the
  sheet's "one frame per narration beat" sampling.
- A chapter that fails is reported and skipped, not fatal: it does not write
  its metadata, so it stays *missing* and the next `--ch missing` run picks it
  up again. The run exits non-zero and prints the retry command.
- Narration needs network access to the edge-tts service; encoding uses the
  NVIDIA GPU when present and falls back to libx264 elsewhere.
- ffmpeg is resolved in this order: `NSF5_FFMPEG` env var →
  `%USERNAME%\.zcode\bin\ffmpeg.exe` (this machine: `D:\Users\32403\.zcode\bin`)
  → `PATH` → the `imageio-ffmpeg` package. No C:-drive artifacts required.

The earlier static-slides generator (`gen_videos.py`) is kept as a fallback
that works fully offline (Windows SAPI voice, no animations).

---

## 中文版

让 nsf5-steganography 从“研究工具”变成可开箱即用的**教学项目**：
GUI 教学面板带自动动画、按章节提供 Colab/Jupyter Notebook、数据集一键下载、
Docker 教学镜像，网页版双语手册（Jupyter Book + GitHub Pages）正在建设中。

## 0) 跨平台快速开始（Linux / macOS / Windows）

项目核心算法、特征提取与双版本 ML 模型均为纯 Python 回退实现，**不依赖 Windows
DLL**，Linux/macOS/Colab 可直接运行：

```bash
git clone https://github.com/Yukinoshita-lin/nsf5-steganography.git
cd nsf5-steganography
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
make test        # 核心 + 隐写分析 + 误报 + 纯 Python 特征
make e2e         # 端到端演示
make notebooks   # 重新生成 10 个章节 Notebook
```

Windows 使用 `.venv\Scripts\activate`；GUI 需要系统 tkinter（Ubuntu/Debian：
`sudo apt install python3-tk`）。三个平台的算法与特征回退由
`.github/workflows/cross-platform.yml` 持续验证。

## 1) 按章节 Notebook（Colab 一键运行）

每个 Notebook 都内置“自动拉取仓库 + 自动安装依赖”的引导单元，因此在
Colab 中直接打开即可运行，也可以在本机 Jupyter/JupyterLab 中打开。

| 章节 | Notebook | Colab 打开 |
|---|---|---|
| 第 1 章 像素与二进制 | `notebooks/01_bits_and_pixels.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/01_bits_and_pixels.ipynb) |
| 第 2 章 Python 工具链 | `notebooks/02_python_toolchain.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/02_python_toolchain.ipynb) |
| 第 3 章 LSB 与盲分析 | `notebooks/03_lsb_steganalysis.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/03_lsb_steganalysis.ipynb) |
| 第 4 章 矩阵嵌入与 F5 | `notebooks/04_matrix_embedding.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/04_matrix_embedding.ipynb) |
| 第 5 章 nsF5 与湿纸 | `notebooks/05_nsf5_wet_paper.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/05_nsf5_wet_paper.ipynb) |
| 第 6 章 哈希键控 | `notebooks/06_hash_keying.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/06_hash_keying.ipynb) |
| 第 7 章 ML 基础 | `notebooks/07_ml_foundations.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/07_ml_foundations.ipynb) |
| 第 8 章 ML 隐写检测 | `notebooks/08_ml_steganalysis.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/08_ml_steganalysis.ipynb) |
| 第 9 章 工程化 | `notebooks/09_engineering.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/09_engineering.ipynb) |
| 第 10 章 综合实战 | `notebooks/10_capstone.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/10_capstone.ipynb) |

本地重新生成：

```bash
python teaching/build_notebooks.py
```

## 2) 数据集自动下载

教学与实验所用的标准基准 BOSSbase 1.01（约 1.6 GB，10,000 张 512×512 PGM）：

```bash
python scripts/download_datasets.py --out data/BOSSbase_1.01
```

下载完成后即可按 README 生成 GPU/CPU 数据集：

```bash
python gpu/make_imageset.py data/BOSSbase_1.01 2000
python src/make_dataset.py data/BOSSbase_1.01 --out bossbase
```

> 小技巧：Notebook 第 8 章自带“合成小样本演示”，无需外部数据即可跑通
> 特征 → 训练 → 判定 的完整流程；真实实验再用上面的 BOSSbase。

## 3) Docker 教学镜像

Linux 容器内一键启动 JupyterLab（不包含 Windows DLL；嵌入/解码走同算法
Python fallback，算法测试均已在镜像构建时通过）：

```bash
docker compose up --build
# 浏览器打开 http://localhost:8888  (token: nsf5)
```

等价命令：

```bash
docker build -f docker/Dockerfile -t nsf5stego-teaching .
docker run --rm -p 8888:8888 -v ${PWD}/notebooks:/workspace/notebooks nsf5stego-teaching
```

## 4) GUI 教学动画

`src/gui.py` 的「矩阵编码演示」面板新增 **▶ 自动演示 / ■ 停止 / 速度** 控件：
每轮随机生成一个 LSB 块与目标伴随式 m，先高亮 syndrome 计算与命中的列，
停顿后自动执行修改并校验 H·x == m，便于课堂投屏与学生跟练。

```bash
python src/gui.py      # 需要带 tkinter 的 Python
python src/test_gui.py # GUI 冒烟测试（含教学动画）
```

## 5) 网页版手册（双语，Jupyter Book + GitHub Pages）

`teaching/web/` 用 Jupyter Book 构建双语静态手册：

- `zh/` — 中文手册
- `en/` — English handbook
- 构建/部署：`.github/workflows/pages.yml`（推送到 `teaching/web/**` 时自动构建并发布 GitHub Pages）

**内容来源与同步（2026-09-15 更正）**：此前这里写着"`teaching/web/*/content/*.md`
是唯一内容源，`build_handbook_pdf.py` 用它编译出 `docs/` 下的 PDF，所以改 Markdown
PDF 与网页会同步"。这与仓库里的实际文件不符 —— 入库的两份 PDF 是**从 DOCX 导出**的
（版式是 Word 的，中文 67 页 / 英文 76 页），而 Markdown 比 DOCX **内容丰富得多**
（用 `build_handbook_pdf.py` 编译同一份 Markdown 会得到 100 / 112 页）。三份材料
因此各有各的来源，改一处不会自动同步别处。现在的实际情况是：

| 交付物 | 源 | 生成方式 | 同步方式 |
|---|---|---|---|
| 网页版（Jupyter Book / GitHub Pages） | `teaching/web/{zh,en}/content/*.md` | `jupyter-book build` | 改 Markdown 即生效 |
| 入库 PDF `docs/*.pdf`（67 / 76 页） | `docs/src/*.docx` | `teaching/export_handbook_pdf_word.py`（Word COM） | 改 DOCX 后重新导出 |
| 备用 PDF（100 / 112 页，内容更全） | 同一份 Markdown | `teaching/build_handbook_pdf.py`（xelatex） | 改 Markdown 后重新编译 |

改**事实/数字**时不要手改某一份：三处都要走 `teaching/handbook_facts.py`
（`--check` 会同时校验 DOCX、网页与入库 PDF 的文本）：

```bash
python teaching/handbook_facts.py --fix --web   # 修 DOCX 与网页 markdown
python teaching/export_handbook_pdf_word.py     # 重新导出入库 PDF (需要 Word)
python teaching/handbook_facts.py --check       # 三份材料一起校验
```

两个 PDF 生成器的取舍：`export_handbook_pdf_word.py` 得到的是交付过的那一版版式
（Word 会做字体回退）；`build_handbook_pdf.py` 不依赖 Word，但没有字体回退，
正文里的 `①` `ᵖ` `₄` 这类符号要靠脚本里的 `\newunicodechar` 表逐个映射。

```bash
python teaching/build_handbook_pdf.py zh --out _pdf_build/out/zh   # 验证这条路径, 不动 docs/
```

2026-09-15 补齐了 22 个易缺字形（此前 xelatex 只往日志里写 `Missing character`、
退出码仍是 0，两份 PDF 各有 80 余处符号会变成空白）；现在脚本会统计日志里的缺字，
**缺一个就返回非零**，`handbook_facts.py --check` 也会校验映射表没被删。

- 本地构建网页：`pip install -r teaching/web/requirements.txt && jupyter-book build teaching/web/zh`（en 同理）
- 打开：`teaching/web/{zh,en}/_build/html/index.html`
- 在线：zh `.../zh/content/intro.html`、en `.../en/content/intro.html`

## 6) 章节教学视频（中文配音 + 动画，正式版 v2）

`teaching/gen_videos_v2.py` 为手册第 1–11 章各生成一支**配音 + 动画**讲解视频（1080p）：
逐段神经网络语音（edge-tts，默认云希）驱动画面——要点随旁白逐条浮现、
原创 PIL 动画演示核心思想（位平面叠加、uint8 溢出、伴随式解码、湿点标记、
键控置换、梯度下降、ROC 操作点等）、手册真实插图带缓推镜头、底部同步字幕。
场景脚本在 `video_scenes_zh.py`，引擎在 `video_engine_v2.py`
（有 NVIDIA 显卡时走 NVENC GPU 编码 + 多进程并行，语音逐段落盘可断点续跑）。

```bash
python -m pip install pillow edge-tts
python teaching/gen_videos_v2.py                 # 生成缺失章节
python teaching/gen_videos_v2.py --ch 3,5        # 只重生成指定章节
python teaching/gen_videos_v2.py --ch all --voice zh-CN-XiaoxiaoNeural
```

- 产物：`teaching/videos/zh/chNN.mp4`（正式版）、`index.html`（本地播放页）、`durations.json`
- 质检：每章抽帧拼图在 `teaching/videos/qa/v2_*.png`
- 说明：语音合成需联网（edge-tts 服务）；编码有 NVIDIA 显卡时走 GPU，否则回退 libx264
- ffmpeg 查找顺序：`NSF5_FFMPEG` 环境变量 → `%USERNAME%\.zcode\bin\ffmpeg.exe`
  （本机为 `D:\Users\32403\.zcode\bin`）→ `PATH` → `imageio-ffmpeg` 包；不在 C 盘留存项目产物

早期纯静态幻灯版生成器 `gen_videos.py`（Windows SAPI 离线语音、无动画）保留作为备用。
