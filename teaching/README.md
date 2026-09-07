# nsF5 Steganography - Teaching Project

让 F:\Steganography 从“研究工具”变成可开箱即用的**教学项目**：
GUI 教学面板带自动动画、按章节提供 Colab/Jupyter Notebook、数据集一键下载、
Docker 教学镜像，网页版双语手册（Jupyter Book + GitHub Pages）正在建设中。

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
| 第 8 章 ML 隐写检测 | `notebooks/08_ml_steganalysis.ipynb` | [Open in Colab](https://colab.research.google.com/github/Yukinoshita-lin/nsf5-steganography/blob/main/notebooks/08_ml_steganalysis.ipynb) |

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

## 5) 网页版手册（进行中）

`teaching/web/` 正在构建 Jupyter Book 双语静态站：

- `zh/` — 中文手册
- `en/` — English handbook
- 部署到 GitHub Pages 的 workflow 见 `.github/workflows/pages.yml`

状态：站点脚手架与 DOCX → Markdown 转换器已就位，章节内容将同步自
`docs/` 目录下的 PDF 源文档（以 DOCX 为母本）。
