# nsF5 图像隐写工具 (Steganography)

![CI](https://github.com/Yukinoshita-lin/nsf5-steganography/actions/workflows/ci.yml/badge.svg)
![version](https://img.shields.io/badge/version-1.5.0-blue)
![license](https://img.shields.io/badge/license-Apache_2.0-blue)
![python](https://img.shields.io/badge/python-3.9%2B-blue)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.14851234.svg)](https://doi.org/10.5281/zenodo.14851234)

针对 **8bit 灰度/彩色图像** 的隐写研究工具，实现了基于**伴随式矩阵编码（二元汉明码）** 的
nsF5 隐写算法，并附带**盲隐写分析**、**图像哈希键控**与**码族/嵌入效率可视化**。

项目位于 `F:\Steganography`，核心为纯 Python（依赖 `numpy`/`Pillow`，GUI 使用标准库 `tkinter`）；
另提供 **C++ 加速库**（`cpp/fsfeatures.dll` 特征提取、`cpp/nsf5embed.dll` 嵌入热路径 + 确定性置乱
`nsf5_permute`，MinGW 编译，跨语言校验与 Python 一致性一致；置乱在 DLL 缺失时自动回退到
Python 同算法，嵌入/解码两端序列恒定可逆）。

---

## 功能总览

| 模块 | 说明 |
|------|------|
| **嵌入 / 解码** | 将 ASCII 字符串嵌入图像 LSB，解码还原；支持口令键控 |
| **伴随式矩阵编码** | nsF5 + F5 / LSB 矩阵编码，二元汉明码 `[n=2^p-1, k, 3]`，块内至多改 1 系数 |
| **湿纸编码** | nsF5 核心：预标记"减幅归零=湿"位置，在干位解 GF(2) 线性方程，无收缩 |
| **图像哈希键控** | 载入时计算 SHA-256；隐藏路径由"内容哈希+口令"唯一决定，解码端自同步并感知篡改 |
| **盲隐写分析** | 卡方检验(Westfeld) + RS 分析(Fridrich)，输出 0–1 隐写倾向概率与判读 |
| **ML 隐写分类器(双版本)** | 143d 稳健版(默认) + 53d 可解释版,详见下文"双版本部署策略" |
| **绘图** | 绘制码族(嵌入率 α vs 载荷)理论曲线 与 实测嵌入效率对比 |
| **GUI** | 载入图 → 嵌入/解码 → 分析 → 绘图 一体化界面 |

## 学习手册

项目提供**中英文双语学习手册 (PDF)**，从零基础开始，12 周学完整个项目:

- 🇨🇳 [`docs/学习手册-从零读懂nsF5隐写项目.pdf`](docs/学习手册-从零读懂nsF5隐写项目.pdf) — 中文版, 94 页
- 🇬🇧 [`docs/Learning-Handbook-From-Zero-to-nsF5-Steganography.pdf`](docs/Learning-Handbook-From-Zero-to-nsF5-Steganography.pdf) — English, 80 pages

涵盖: 数字图像基础 → Python 入门 → LSB 隐写 → 卡方/RS 分析 → 汉明矩阵编码 → F5/nsF5 → 湿纸编码 → 哈希键控 → 机器学习基础 → v1/v2 特征工程 → SRM 滤波 → 143d/53d 双版本模型 → C++/GPU 加速 → 综合实验。每章配有"动手做"实验与"想一想"思考题, 适合本科毕设自学。

### 模型双版本(2026-09-06)

项目保留两套训练好的 LGB 模型,默认加载 **143d 稳健版**,可切换到 **53d 可解释版**:

```python
from src.ml_predict import MLPredictor

# 默认 143d (稳健, 部署推荐)
pred = MLPredictor()  # models/stego_classifier.joblib

# 切换 53d 可解释版 (AUC 更高, 论文/教学推荐)
pred = MLPredictor(model_path='models/stego_classifier_v2_jpeg_lgb_51d.joblib',
                   clip_outliers=False)

# 预测
r = pred.predict(image)
# r = {'probability': 0.83, 'verdict': '含密(stego)', 'threshold': 0.168}
```

| 版本 | 文件 | AUC (8-split mean) | OOD 鲁棒 | 推荐场景 |
|---|---|---|---|---|
| **143d 默认** | `stego_classifier.joblib` | 0.9085 | **1/8 fp** | 通用部署 / 真实图 |
| **53d 可解释** | `stego_classifier_v2_jpeg_lgb_51d.joblib` | **0.9227** | 3/8 fp | 论文 / 答辩 / 教学 |

详见下文的 **双版本部署策略** 一节。

---

## 安装与运行

### 方式 A：从源码运行

```bash
cd F:\Steganography
pip install numpy pillow
python src\gui.py
```

> 若系统默认 `python` 未带 tkinter，可用带 tkinter 的解释器（如 `C:\Python314\python.exe`）：
> `C:\Python314\python.exe src\gui.py`

### 方式 B：安装打包的模块（wheel）

每个版本会以源码包发布，可构建并安装：

```bash
# 构建 wheel + sdist（需已安装 build）
python -m build

# 安装 wheel（核心模块：ns5_core / steganalysis / gui 等）
pip install dist\nsf5stego-1.1.0-py3-none-any.whl
```

> 注意：wheel 仅含纯 Python 核心；`cpp/` 下的 Windows DLL（特征提取/嵌入加速）随仓库源码发布，
> 运行 GUI/离线使用仍需项目源码目录内的 `cpp/`。

### 运行测试

```bash
python src\test_core.py    # 核心算法自测（嵌入/解码 + 汉明矩阵 + 湿纸 + 口令）
python src\test_steg.py    # 盲隐写分析自测（区分 干净/含密 图）
python src\run_e2e.py      # 端到端验证（嵌入→保存→解码→分析→绘图）
python src\test_gui.py     # GUI 冒烟测试（构建窗口/载入/预览）
```

---

## GUI 使用流程

1. 点击 **载入原始图 / 含密图** 选择 8bit 图像。
2. 选择 **算法**（`nsF5` 或 `matrix`）、**参数 p**（块比特数，越大效率越高）、可选**口令**。
3. 在文本框中输入待嵌入的 **ASCII 字符串**。
4. 点击 **1 嵌入并保存** → 生成 `output/stego_*.png`，右侧预览含密图。
5. 点击 **2 解码提取** → 从含密图还原字符串（须与嵌入使用相同 算法/p/口令）。
6. 点击 **3 分析** → 显示 SHA256、卡方统计、RS 缺口、估计嵌入率与隐写概率。
7. 点击 **生成码族与效率图** → 弹出理论 vs 实测效率对比图。

> 解码与嵌入参数（方法/p/口令）必须一致；口令或图像内容不匹配将无法正确解码。

---

## 目录结构

```
F:\Steganography
├── README.md
├── cpp
│   ├── fsfeatures.cpp    # C++ 特征提取源
│   ├── fsfeatures.dll    # 编译产物 (MinGW)
│   ├── nsf5embed.cpp     # C++ nsF5/matrix 嵌入热路径源
│   └── nsf5embed.dll     # 编译产物 (MinGW)
├── data/dataset.csv      # 有监督训练数据集 (clean+stego 特征)
├── gpu
│   ├── make_imageset.py  # GPU版数据集生成 (完整512, 1干净+4含密变体/照片)
│   ├── featurize_gpu.py  # GPU批量向量化 11 维统计特征 (与 CPU 参考 bit 级一致)
│   ├── train_ml_gpu.py   # GPU特征提取 + 按照片分组训练分类器
│   └── predict_gpu.py    # 单图像 GPU 隐写检测
├── models                # 训练出的分类器 stego_classifier.joblib / steg_classifier_gpu.joblib
└── src
    ├── ns5_core.py       # nsF5 核心：汉明码、湿纸求解、哈希键控、嵌入/解码
    ├── cppembed.py       # C++ 嵌入封装 (自校验与 Python 像素级一致)
    ├── steganalysis.py   # 盲隐写分析：卡方 + RS 嵌入率估计
    ├── fsfeatures.py     # C++ 特征库的 ctypes 绑定（含与 Python 一致性校验）
    ├── ml_predict.py     # 有监督 ML 判定封装
    ├── make_dataset.py   # 批量生成特征数据集 (支持 --preprocess srm SRM 预处理)
    ├── srm_filter.py     # SRM 高通滤波预处理层 (numpy + torch 双实现, 30 核)
    ├── train_model.py    # 训练/评估/保存分类器
    ├── efficiency.py     # 码族与嵌入效率绘图
    ├── image_io.py       # 图像读写工具
    ├── gui.py            # tkinter GUI
    ├── run_e2e.py        # 端到端验证脚本
    ├── test_core.py      # 核心算法单测
    ├── test_steg.py      # 隐写分析单测
    ├── test_false_positive.py  # 误报回归测试
    └── test_gui.py       # GUI 冒烟测试
├── img                   # 示例封面图
└── output                # 生成结果（含密图、效率图）
```

---

## 技术细节

### 伴随式矩阵编码（nsF5）

二元汉明码 `[n,k,d]`，`n = 2^p - 1`，校验矩阵 **H** 的列向量取 GF(2)^p 全部非零向量。
载体系数 LSB 奇偶向量 `x` 的伴随式 `s = H·x (mod 2)`。

- 嵌入 `p` 比特消息 `m`：若 `s == m` 不改动；否则 `d = s ⊕ m`，
  找到唯一列 `j`（`H_j == d`）翻转该系数 → **每块至多改 1 个系数**。
- 需要改动的概率 `(2^p-1)/2^p`，嵌入效率 `α(p) = p·2^p / (2^p-1)`，随 p 增大而提高。

### F5 → nsF5

- **F5**：直流/减幅归零时"收缩"，该块整块重嵌、载荷下降。
- **nsF5**：用**湿纸编码**预标记"减幅会归零 = 湿"的位置，湿位不动，
  在**干位**解 GF(2) 线性方程完成嵌入 → **无收缩**，效率与安全性更高。

### 图像哈希键控

载入原图计算 SHA-256（`cover_hash`）：

- 头部区：用仅口令派生的种子预埋 `cover_hash`（认证头）；
- 正文区：用 `cover_hash + 口令` 派生的种子键控置乱路径。

解码端先用口令种子读回头部，重算正文种子解码 → 隐藏路径由图像内容唯一决定，
改动任意像素会破坏解码结构，可经头部校验感知篡改。

### 盲隐写分析

- **卡方检验（Westfeld）**：相邻灰度对 `(2i,2i+1)` 频率在嵌密后趋近均衡，
  p 值高表示该区已随机化/嵌入。
- **RS 分析（Fridrich-Goljan-Du）**：统计正/负掩码的常规-奇异缺口
  `Gr`、`Gn`；干净图 LSB 平面有结构（Gn 明显为正），隐写使其随机化而下降。
- 综合多个统计量给出 **0–1 隐写倾向概率** 与判读（不太可能 / 可能 / 高度可能）。

> 盲隐写分析本质为启发式：没有原始封面时无法给出精确绝对概率，
> 此处概率供评估与教学参考。

---

## 有监督 ML 隐写分析（C++ 特征提取 + 校园照片训练）

将**特征提取**从 Python 移植到 **C++**（`cpp/fsfeatures.dll`，MinGW 编译），
可显著降低逐图统计开销；嵌入热路径同样提供 **C++ 版**（`cpp/nsf5embed.dll`，
经跨语言回环校验与 Python **像素级一致**，`cppembed.py` 封装）。
并用真实校园照片做**有监督训练**，得到一个可部署的分类器。

### 训练管线

```bash
# 1) 用 F:\DCIM\Camera 下照片批量生成 干净/含密 特征数据集
#    (每张降采样 512x512 灰度, 1 干净 + 6 含密变体, C++ 提取 11 维特征 + C++ 嵌入)
python src\make_dataset.py

# 2) 训练/评估 (预留 held-out 测试集 + 5 折 GroupKFold 交叉验证选模)
python src\train_model.py
```

- **特征 (全由 C++ 计算)**：`RS_Gn, RS_Gr, Rm, Sm, Rn, Sn`、
  `chi2_pvalue, chi2_stat`、`diff_entropy、lsb_diff_entropy`、`median_prefix_p`。
- **6 档含密变体**：覆盖弱→强，`nsF5 p3`（弱密度）至 `matrix p2`（强）。
  414 张照片 → 2898 样本（414 干净 + 2484 含密）。
- **5 折 GroupKFold**：按照片分组交叉验证选模（杜绝同源泄漏），
  再在留出测试集上报综合指标与每密度层检出率。

### 在 GUI 中启用

GUI 新增 **判定灵敏度** 下拉框（严格 / 均衡 / 宽松），作用于 **3 分析**：

- **严格 (低误报)**：提高含密判定阈值 → 干净图更少被误判；
- **均衡**：默认。
- **宽松 (高检出)**：下调阈值 → 更易检出弱密度嵌入（代价是误报略升）。

它与下方 **ML 分类含密概率** 联动（同一张净图在三种灵敏度下阈值
0.95→0.77→0.57，ML 判决会由"干净"切换到"含密"），启发式概率也会围绕
0.5 上下牵引。GUI **3 分析**会在原有启发式结果下方追加一行 **ML 分类含密概率**，
输入图像会自动按训练一致的方式（转灰度→512 缩放→C++ 特征）送入模型。
模型未加载时会提示先运行 `train_model.py`。

```bash
# 单独用 ML 判定单张图
python -c "import sys; sys.path.insert(0,'src'); from ml_predict import get_predictor; \
import numpy as np,os; from PIL import Image; from ns5_core import embed_string; \
a=np.asarray(Image.open(r'img/cover.png').convert('L').resize((512,512)).convert('L')); \
print(get_predictor().predict(a))"
```

> **局限**：真实 JPEG 照片的 LSB 位平面天然近乎随机，弱密度 nsF5 嵌入的
> 统计足印很弱；ML 概率应与启发式判读**交叉印证**，不宜单独作为铁证。

### SRM 高通滤波预处理层（检测性能提升）

`src/srm_filter.py` 提供 **SRM (Spatial Rich Model) 高通滤波预处理层**，在提取
11 维统计特征**之前**对图像做高通滤波，突出嵌入噪声、抑制图像内容，从而增强
弱密度隐写的统计足印。

- **30 个标准 SRM 核**（Fridrich 体系，与 Ye-Net 所用一致）：一阶差分 8 + 二阶 4 +
  三阶 8 + 边缘 3×3 4 + 边缘 5×5 4 + 方形 3×3/5×5 各 1；按标准因子归一化并补齐到 5×5。
- **合成增强图**：逐像素取 30 个残差的最大绝对响应，clip 到 ±T（默认 4）后平移缩放到
  uint8 [0,255]，输出单通道增强图，直接喂给现有特征器，其余管线不变。
- **CPU (numpy) / GPU (torch conv)** 双实现，接口一致
  （`srm_residuals_np` / `srm_residuals_torch` / `preprocess_batch_torch`）。

接入方式（两条管线均已内置开关）：

```bash
# CPU数据集: --preprocess srm (默认 none=原图基线)
py src\make_dataset.py data\campus_jpg --out campus_srm --preprocess srm -j 16

# GPU特征: extract_features_gpu(x, use_srm=True) (默认开启)
#   自检: py gpu\featurize_gpu.py   (含 SRM 路径冒烟)
```

**实测效果（同一 414 张校园照片，LR，同协议 5 折 GroupKFold + 留出测试）**：

| 指标 | 原图基线 (dataset.csv) | SRM 增强 (dataset_campus_srm.csv) |
|------|:--:|:--:|
| 5 折 CV-AUC | 0.7594 | **0.7922** |
| held-out 测试 AUC | 0.7811 | **0.8085** |
| 低误报点含密检出率 | 41.2% | **50.3%** |
| 弱密度 `nsF5 p3 d0.25` 检出 | 51.9% | **62.5%** |
| `nsF5 p2 d0.35` 检出 | 76.0% | **90.4%** |
| 干净误报率（低误报阈值） | 9.6% | 9.6% |

SRM 在保持低误报不变的同时，将 CV-AUC 提升约 **3.3 个百分点**、测试 AUC 提升约
**2.7 个百分点**，弱密度档检测增益尤其显著，且 SRM 增强图约 0.35s/张、
16 核并行下生成全量数据集不受影响。

> **重要（跨源合并时结论相反）**：SRM 的收益只出现在**同源**内。接入
> BOSSbase 全量做**跨源合并训练**时，SRM 反而显著拉低性能，CPU 与 GPU 两管线
> 相互印证：
>
> | 跨源合并 | CPU (校园+全量BOSSbase, 测试AUC) | GPU (校园+BOSSbase2000源, 验证AUC) |
> |---|---|---|
> | 非 SRM（基线） | **0.741** | **0.651** |
> | SRM | 0.704（−3.7pp） | 0.572（−7.9pp） |
>
> 机理：SRM 高通滤波在抑制图像内容的同时，也把不同相机/JPEG 压缩源之间的可区分
> 信号一并压平——同源时被压掉的是嵌入噪声（收益），跨异构源时被压掉的是跨源可分
> 性（损失）。因此**默认模型采用未 SRM 的合并全量**（`stego_classifier.joblib`，
> 测试 AUC≈0.741），SRM 单源校园模型另存为
> `stego_classifier_campus_srm.joblib`（AUC≈0.8085，仅供校园同源场景）。

### v2 扩展特征（143 维）与多档变体 A/B（2026-09）

在原 11 维之上扩展为 **143 维 v2 特征集**：30 个 SRM 残差的均值 / 绝对均值 / 标准差
（90 维）+ 20 段前缀卡方 p（20 维）+ texture_noise + est_rate（2 维）+ 20 段 LSB 前缀
卡方 p（20 维）。同时把训练变体从 6 档扩展到 **12 档**（追加 `nsF5 p3 d=0.40`、
`matrix p3 d=0.40/0.60`、`lsb d=0.30/0.50/0.70`）。

```bash
# 重新生成 v2 数据集 (单进程 GPU, 414 张 ~7 min)
py src\make_dataset.py --out campus_v2 --feature-set v2 --variants all
py src\make_dataset.py --out campus_v2_min --feature-set v2 --variants minimal  # 6 档对照

# 训练 v2 143d + 4 模型 stacking (5 折 GroupKFold, 留出 25% 测)
$env:DS_FILES = "dataset_campus_v2.csv"
py src\train_model.py
```

**严格 A/B 对比**（同一测试集照片 ID 分组，5 折 GroupKFold OOF）：

| 数据集 | 特征 | OOF-AUC | 弱档 `nsF5 p3 d=0.25` 检出 | 模型 |
|---|---|---|---|---|
| `dataset.csv` (6 档) | v1 11 维 | 0.7678 | 49% | XGB |
| `dataset_campus_v2.csv` (12 档) | v1 11 维 | 0.7868 | — | LR |
| `dataset_campus_v2.csv` (12 档) | v2 143 维 | **0.8143** | 25% | LR |
| `dataset_campus_v2.csv` (12 档) | v2 143 维 (held-out) | **0.8278** | 25% | LR |

- v2 数据集 12 档 vs 6 档：+0.019（同 11 维）→ 真实信号（多档位学到档位差）。
- v2 143 维 vs v1 11 维：+0.027 → SRM 残差 / 20 段前缀 p 确实贡献判别力。
- 累计 +0.05 AUC（0.78 → 0.83）。

> **部署警告**：v2 模型在 5 折 OOF 与 held-out 上 AUC 显著提升，但**实际部署到真实
> JPEG 干净图时倾向过激**（SRM 残差对 JPEG 高频噪声过于敏感，干净 JPEG 几乎全被
> 判 1.0）。**默认 `stego_classifier.joblib` 仍为 v1 11 维 XGB 模型**（held-out
> AUC=0.7435，干净 JPEG 误判率低）；v2 模型另存为
> `stego_classifier_v2_campus_stack.joblib`（AUC=0.8278，**仅供训练分布内的
> PGM/BMP 灰度图使用**）。

#### 分布外（OOD）分析与缓解尝试

为修复 v2 在真实 JPEG 干净图上的过激（logit 263 vs 训练集 clean mean 1.68），
探索了两种部署抗偏移方案（均不替换默认模型，仅做参考）：

| 方案 | 思路 | 真实 JPEG 干净 prob | 局限 |
|---|---|---|---|
| 原始 v2 | 无防护 | 1.000 | — |
| ① clip-to-±5σ | 把每维特征裁到训练集 μ±5σ | 0.996 | JPEG 干净 logit=5.6 已超训练集 clean p99=3.73 |
| ② OOD-cap | logit 超 clean p99 时封顶概率到 clean p99 prob (0.977) | 0.977 | 仍 ≥ thr 0.912；stego p5=1.30 已与 clean p99=3.73 重叠，单阈值无解 |

**根本原因**：训练集 clean 与 stego 的 logits 严重重叠（clean p99=3.73 vs
stego p5=1.30）。v2 模型在训练分布内已"过激"，JPEG 干净图即使 clip 也回不到训练分布内
位置。

#### ✅ 根本修复：v2 训练集追加真实 JPEG 干净样本（2026-09）

把 `data/campus_jpg/` 414 张真实 JPEG 干净图（campus PGM-derived 来源之外）作为
额外 clean 样本加入 v2 训练集，photo_id 独立区间 `max_id+1000 ~ max_id+1413`，
**与原训练集完全 disjoint**（防 group 泄漏）。重新训练 v2 4 模型 OOF stacking：

```bash
# 自动生成 v2 + JPEG 数据集 (campus_v2.csv + 414 JPEG clean -> campus_v2_jpeg.csv)
py src\_add_jpeg_clean.py

# 训练 (与 v2 同样的 5 折 GroupKFold + 4 模型 stacking)
$env:DS_FILES = "dataset_campus_v2_jpeg.csv"
py src\train_model.py
```

**v2 特征可解释性**(2026-09-06):

- v2 143d 特征组:LGB gain 占比 → LSB PREFIX 42.2%, BASE 21.6%, SRM 90 维合计 26.6%, PREFIX 9.6%
- 单特征 AUC 排名:20 段 LSB 前缀 + 11 维 BASE 全部 > 0.60;SRM 90 维平均单特征 AUC 仅 0.50~0.52(近随机)
- 结论:**143d 中 ~73% 增益来自 31 个可解释特征**;SRM 90 维是"压舱石",边际贡献微弱但提供 OOD 鲁棒性

### 双版本部署策略(2026-09-06)

经过可解释性对照实验,项目保留 **143d 默认版** 与 **53d 可解释版** 两套模型,各自适用场景不同:

| 维度 | **143d 默认版**(`stego_classifier.joblib`) | **53d 可解释版**(`stego_classifier_v2_jpeg_lgb_51d.joblib`) |
|---|---|---|
| 特征构成 | BASE 11 + SRM 90 + PREFIX 20 + LSB PREFIX 20 + TEX/EST 2 | BASE 11 + PREFIX 20 + LSB PREFIX 20 + TEX/EST 2(去 SRM) |
| 8-split 平均 AUC | 0.9085 | **0.9227**(+0.014) |
| Held-out AUC (seed=0) | 0.8946 | **0.9100**(+0.015) |
| 弱档检出 nsF5 p3 d=0.25 | 85.3% | **87.2%** |
| OOD 鲁棒性 (真实 JPEG 干净 fp) | **1/8**(median 0.011) | 3/8(median 0.028) |
| 模型文件大小 | 2.7 MB | 2.7 MB |
| 可解释性 | 一般(143 维,LIME/SHAP 可对单图解释) | **强**(51 维有明确统计定义,可直接列 Top 贡献) |
| 推荐场景 | 通用部署 / 异构数据 / 真实图像 | 论文 / 答辩 / 教学 / 单图分析 |

**核心结论**:
- 53d 在 AUC 和弱档检出上**全面胜出**,因为 SRM 90 维是 LGB 中的"噪声特征"(平均单特征 AUC 仅 0.50~0.52)
- 但 143d 在 OOD 鲁棒性上**更稳**:SRM 高通残差对 JPEG 高频噪声有"过滤"作用,真实校园照片判错率更低
- **工程上保留双版本,默认加载 143d**(稳健),可通过 GUI 选项切换 53d(可解释)

#### 53d 精简实验明细

- 8 split 全部胜出(差异 +0.005 ~ +0.022):
  ```
  seed    143d     53d    diff
     0  0.8946  0.9100 +0.0155
     1  0.9228  0.9307 +0.0080
     2  0.9166  0.9216 +0.0051
     3  0.9083  0.9307 +0.0224
     4  0.9263  0.9375 +0.0112
     5  0.8933  0.9131 +0.0198
     6  0.9196  0.9385 +0.0189
     7  0.8866  0.8995 +0.0129
  ```
- **可解释优势**:53 维中 51 维有明确统计含义
  - `Rm/Sm/Rn/Sn/RS_Gr/RS_Gn`:RS 分析 6 个规则翻转率
  - `chi2_pvalue/chi2_stat`:LSB 卡方 p 值与统计量
  - `diff_entropy/lsb_diff_entropy`:全局/LSB 位平面熵差
  - `median_prefix_p`:20 段前缀卡方 p 中位数
  - `prefix_p1~p20`:全图像 20 段卡方 p
  - `lsb_prefix_p1~p20`:LSB 通道 20 段卡方 p
  - `texture_noise`:图像纹理方差归一化
  - `est_rate`:从 χ²p + 前缀 p 反推估计嵌入率

#### 切换 53d 模式(代码示例)

```python
import joblib
from ml_predict import MLPredictor

# 默认 143d
pred_143 = MLPredictor()  # model_path=stego_classifier.joblib

# 切换 53d
pred_53 = MLPredictor(model_path='models/stego_classifier_v2_jpeg_lgb_51d.joblib',
                      clip_outliers=False)  # 53d 不需要 clip(单特征 AUC 高,训练分布更稳)

# 同一张图
result_143 = pred_143.predict(img)  # AUC 高 + OOD 稳
result_53 = pred_53.predict(img)    # AUC 更高 + 可对每维特征解释
```

#### GUI 集成(规划)

`src/gui.py` 在 ML 模型加载处增加单选框:`[●] 143d 默认(稳健)` / `[ ] 53d 可解释(AUC+)`。
切换后:
- 143d 模式:与现状完全一致,部署推荐
- 53d 模式:增加"贡献特征"面板,显示 Top 5 特征 + 方向 + 强度,供研究/教学场景



| 模型 | 训练集 | Held-out AUC | 真实 JPEG 干净 prob | nsF5 p3 d=0.25 检出 |
|---|---|---|---|---|
| v1 XGB (旧默认) | dataset.csv (11维, 6档) | 0.7435 | 0.30 (正确) | 49% |
| v2 LR (未修复) | campus_v2 (143维, 12档) | 0.8278 | **1.00 (误判)** | 25% |
| v2 XGB (旧默认) | campus_v2_jpeg (143维, 12档 + 414 JPEG clean) | 0.8723 | 0.14 (正确) | 15.6% |
| v2 XGB tuned | campus_v2_jpeg + 网格调优 (depth=5, n_est=500) | 0.8889 | 0.14 (正确) | 67.9% |
| v2 XGB + WEAK_WEIGHT=3 | campus_v2_jpeg + 弱档加权×3 | 0.8534 | 0.14 (正确) | 20.2% |
| v2 XGB + WEAK_WEIGHT=5 | campus_v2_jpeg + 弱档加权×5 | 0.8377 | — | 25.7% |
| v2 STACK (WEAK_WEIGHT=3) | campus_v2_jpeg + 4 模型 LR meta | 0.8321 | **0.10 (正确)** | **32.1%** |
| **v2 LGB tuned (新默认)** | **campus_v2_jpeg + LGB 网格调优 (nl=31, ne=800, lr=0.03)** | **0.8946** | **0.14 (正确)** | **85.3%** |

- **新默认** `stego_classifier.joblib` = **v2 LGB tuned**
  (`num_leaves=31, n_estimators=800, learning_rate=0.03, min_child_samples=10`)。
- 测试集 AUC **0.8946**（vs XGB tuned 0.8889，**+0.006**）；多 split 平均 AUC **0.9085**（+0.007）。
- **弱档检出最强**：nsF5 p3 d=0.25: 67.9% → **85.3%**；nsF5 p2 d=0.35: 84.4% → **95.4%**；
  matrix p3 d=0.40: 89.0% → **94.5%**。LSB 三档全部 100% 检出。
- 真实校园 JPEG 干净照片 OOD 鲁棒性提升（8 张中 7 张 prob < 0.5；median 0.011 vs XGB tuned 0.18）。
- XGB tuned 已备份为 `stego_classifier_v2_jpeg_xgb_tuned.bak.joblib`。
- **STACK 版** (`_weak3_stack.joblib`) 仍保留供 OOD 严重场景切换（人工噪声 prob 0.24 vs LGB 0.99）。
- v1 11 维 XGB 保留为参考。

> **最终决策**：项目保留**双版本模型**供不同场景使用：
>
> | 版本 | 文件 | 适用 |
> |---|---|---|
> | **143d 默认版(稳健)** | `stego_classifier.joblib` | 通用部署 / 异构数据 / 真实图像(默认加载) |
> | **53d 可解释版(AUC+)** | `stego_classifier_v2_jpeg_lgb_51d.joblib` | 论文 / 答辩 / 教学 / 单图分析 |
>
> 143d 默认:LGB tuned(`num_leaves=31, n_estimators=800, learning_rate=0.03, min_child_samples=10`),
> held-out AUC **0.8946**、多 split 平均 AUC **0.9085**、OOD 1/8 fp。
> 53d 可解释:同样超参,53 维特征(去 SRM),held-out AUC **0.9100**、多 split 平均 AUC **0.9227**、
> OOD 3/8 fp(牺牲少量鲁棒性换 AUC+0.014 与完全可解释性)。
> STACK 与 XGB tuned 仍保留供场景切换;v1 11 维 XGB 保留为参考。

---

## GPU 版 (v1.2)：PyTorch 批量向量化的统计特征分析

`gpu/` 子目录提供一套 **GPU(CUDA) 加速**的隐写检测管线，复刻已验证的
**11 维统计特征**（RS、卡方、差分熵、LSB 熵、前缀中位 p，与 `src/fsfeatures.py`
参考实现 **bit 级一致**），把原来逐图 Python 循环（RS 逐组、20 段前缀卡方）
改写为 PyTorch 张量化算子，在 CUDA 上一批并行算完。

> **为什么是"特征法"而不是裸像素 CNN？** 实测表明：在 414 张校园照片上，
> 从头训练的整图深度卷积网络（多架构/输入/正则组合）均无法跨照片泛化
> （验证 AUC≤0.50）——有效独立样本只有照片数，弱 LSB 信号需数千张源图才能学稳。
> 统计特征法在相同数据上验证 AUC≈**0.79**，且特征提取可被 GPU 并行化，
> 因此 GPU 版选择**加速这条真正管用的路径**，而非裸 CNN。

### 管线

```bash
# 1) 生成数据集 (每张照片 1 干净 + 4 档含密变体, 完整 512x512, 不裁剪以保留统计)
python gpu\make_imageset.py  [照片目录] [张数]

# 2) GPU 批量提取特征 + 按照片分组训练 + 评估
python gpu\train_ml_gpu.py            # 输出 models\steg_classifier_gpu.joblib

# 3) 单张图像 GPU 检测
python gpu\predict_gpu.py <图像> [<图像>...]
```

### 实测 (RTX 4060 Laptop, 纯校园照片)

数据源已从 `F:\DCIM\Camera` 中**去除 DIP4E 教材灰度 tif**，改用纯校园照片目录
`data/campus_jpg`（仅 414 张 jpg）作为唯一数据源，CPU 与 GPU 两条管线均已全量重跑。

- **GPU 统计特征管线**：特征 2070 张 512² 灰度约 **5s（≈397 img/s）**，GPU 利用率
  峰值 **99% / 平均 74%**；验证 **AUC≈0.790**，acc≈0.802（Youden 阈值 0.713）；逐档——
  `matrix p3`≈99%、`nsF5 p2 d0.95`≈93%、`nsF5 p2 d0.50`≈89%、弱 `nsF5 p3`≈64%、干净误报≈43%。
- **CPU 特征管线**：2898 样本（414 干净 + 2484 含密，6 档），CV 最佳为
  **LogisticRegression CV-AUC≈0.759**；held-out **AUC≈0.781**、acc≈0.780；
  `matrix p2 d0.80`/`p3 d0.50` 检出≈100%/99%、`nsF5 p2 d0.85`≈95%、弱 `nsF5 p3 d0.25`≈52%。
- **一致性**：`python gpu\featurize_gpu.py` 自检，GPU 与 CPU 参考特征逐项一致
  （RS 到 bit 级、浮点 ~1e-7）。

### 参考基准数据集 (BOSSbase 1.01) 重跑

用隐写分析领域事实标准基准 **BOSSbase 1.01**（官方 `dde.binghamton.edu`，1.67GB zip，
10,000 张 **512×512 灰度 PGM**，与管线工作尺寸完全一致）重新生成数据并重训
（`make_imageset.py` 已增补 `*.pgm` 支持）。

```bash
# 1) 下载解压至 data\BOSSbase_1.01\*.pgm (官方 zip 1.67GB)
# 2) 生成图像集 (本实验取前 2000 张源图 -> 10000 样本, 512x512)
py gpu\make_imageset.py F:\Steganography\data\BOSSbase_1.01 2000
# 3) 训练 (默认读 imageset.npz, 覆盖 steg_classifier_gpu.joblib)
py gpu\train_ml_gpu.py
```

- **数据**：2000 源图 → **10000 样本**（2000 干净 + 8000 含密，1干净+4变体），npz ≈1.57GB。
- **实测 (验证 2000 样本, Youden 阈值 0.798)**：**AUC≈0.644**，acc≈0.655；逐档——
  `matrix p3 d0.50`≈80%、`nsF5 p2 d0.95`≈70%、`nsF5 p2 d0.50`≈68%、弱 `nsF5 p3 d0.30`≈57%、
  干净误报≈48%。
- **对比**：相比校园照片基线（AUC≈0.767/0.79）下降，验证了文献公认结论——BOSSbase
  经去马赛克加工、统计结构更强，弱密度 LSB 嵌入足印更弱，是**更难的隐写分析基准**；
  远优于 CIFAR 32×32 补充实验（AUC≈0.555，已回退清理）。
- 原基于校园照片的 `imageset.npz` / `steg_classifier_gpu.joblib` 已备份为
  `imageset_photobase.npz` / `steg_classifier_gpu_photobase.joblib`；BOSSbase 数据与
  去 DIP4E 前的旧数据/模型同时备份于 `backup_20260905/`。默认模型为纯校园照片版
  `steg_classifier_gpu.joblib` / `stego_classifier.joblib`。

### BOSSbase 全量合并训练（校园 + BOSSbase 10,000 源图）

为最大化训练作用，将 **BOSSbase 全量 10,000 张源图**与校园照片**合并训练**，让单一
模型同时看到"自然校园 + 去马赛克基准"两类域。

- **数据生成**：`make_imageset.py` 现以 **memmap 逐张落盘**（`<base>_x.npy`，避免大数组
  一次性堆叠造成 OOM），支持 `--out / --id-offset / -n` 多源分工。
  ```bash
  py gpu\make_imageset.py data\campus_jpg   --out campus            # 校园 414 源 -> 2070 样本
  py gpu\make_imageset.py data\BOSSbase_1.01 --out bossbase          # BOSSbase 10000 源 -> 50000 样本
  py gpu\train_ml_gpu.py                    # 合并两源训练(默认读取两源)
  ```
- **数据**：校园 2070 + BOSSbase 50000 = **52070 样本**（414+10000 源图，各 1干净+4变体）。
- **实测 (验证 10430 样本, Youden 阈值 0.795)**：**AUC≈0.712**，acc≈0.690；逐档——
  `matrix p3`≈87%、`nsF5 p2 d0.95`≈79%、`nsF5 p2 d0.50`≈70%、弱 `nsF5 p3`≈50%、干净误报≈41%。
- **对比**：合并 AUC(0.712) 介于纯校园(0.790) 与 BOSSbase 单跑(0.644) 之间，符合数据
  难度梯度——模型在更难基准与自然场景间取得平衡；GPU 特征提取 52k 张约 146s，GPU 满载。

### CPU 全量合并训练（校园 + BOSSbase 全量）

CPU 版同样接入 BOSSbase 全量，与校园照片合并训练，覆盖 10,000 张基准源图。

```bash
py src\make_dataset.py data\campus_jpg --out campus       # 校园 414 源 -> 2898 样本(1干净+6变体)
py src\make_dataset.py data\BOSSbase_1.01 --out bossbase  # BOSSbase 10000 源 -> 70000 样本
py src\train_model.py                                     # 合并两源训练(默认读取两源)
```

- **数据**：校园 2898 + BOSSbase 70000 = **72898 样本**（10414 clean + 62484 stego，11 维特征）。
- **5 折 GroupKFold CV**（照片分组防泄漏）：RandomForest **CV-AUC≈0.745**（最佳）、
  XGBoost 0.744、LogisticRegression 0.736、GradientBoosting 0.732。
- **held-out 测试（18228 样本）**：**AUC≈0.741**，acc≈0.685，bacc≈0.668，thr=0.834；
  逐档检出——`matrix p2 d0.80`≈99%、`matrix p3 d0.50`≈85%、`nsF5 p2 d0.85`≈73%、`nsF5 p2 d0.35`≈59%、
  弱 `nsF5 p3`≈44–55%；低误报点(thr=0.910) 干净误报≈11.6%、含密检出≈38.9%。
- **代价**：CPU 全量特征提取 70000 行约 **79 分钟**（单进程串行，见下文并行改造说明）。
- **对比**：CPU AUC(0.741) 略高于 GPU(0.712)，符合 CPU 逐张 6 档、更多 stego 变体覆盖更强的预期。

> **多进程并行（已实现）**：`make_dataset.py` 内置多进程并行（`-j / --workers N`，默认
> 用满 CPU 核数）。每张图内 6 档 C++ 嵌入/特征有强数据依赖无法图内并行，但**图与图
> 相互独立**，按图分片交多个子进程并行处理、主进程流式合并。实测 100 张（700 样本）：
> 单进程 53.5s → 16 核并行 9.5s，**加速约 5.6 倍**，多进程与单进程输出逐行一致。
> 注意每进程各自加载 `fsfeatures.dll`，内存按核数倍增（单进程约 54MB）。
> 命令：`python src\make_dataset.py <目录> --out x -j 15`

> 依赖：`torch`(CUDA)、`numpy`、`Pillow`、`scipy`、`scikit-learn`、`joblib`、
> `nvidia-ml-py`(可选，用于上报 GPU 利用率)。样本数据 `gpu/data/*` 较大(含 `_x.npy`
> 大数组)，不入库，可随时重新生成。

> 同 CPU 版一样，GPU 检测器输出的是**统计含密概率**，弱密度嵌入应结合启发式判读
> 交叉印证。GPU 特征提取亦可作为大批量图片的批量分析入口复用。

---

## 持续集成 & 发版

- **CI**（`.github/workflows/ci.yml`）：任何对 `main` 的推送 / PR 都会自动运行
  `test_core.py` 与 `test_steg.py`（Python 3.9 / 3.11），并构建 `wheel + sdist`。
- **自动发布**：推送形如 `v1.1.0` 的 tag 时，CI 会构建包并自动创建 **GitHub Release**，
  附带 `wheel` 与 `sdist` 作为资产，同时自动生成发布说明。
- **发布流程**：

```bash
# 提交改动并打 tag（本地）
git add -A && git commit -m "feat: v1.1"
git tag v1.1 && git push origin main --tags
```

## 版本历史

- **v1.5.0 (当前) — 学习手册发布 + Zenodo DOI**
  - 发布中英文学习手册(PDF)至 `docs/`:
    - `docs/学习手册-从零读懂nsF5隐写项目.pdf` (中文, 12 周学习路线, 94 页)
    - `docs/Learning-Handbook-From-Zero-to-nsF5-Steganography.pdf` (英文, 12 周 roadmap, 80 页)
  - 涵盖 v1.4.0 全部新特性: 143d/53d 双版本 ML 模型、SRM 高通滤波、特征可解释性分析
  - 零基础: 从"像素与二进制"到"LGB 分类器超参调优"的完整学习路径
  - 新增 Zenodo 存档 DOI 徽章

- **v1.4.0 — 双版本 ML 模型**
  - **143d 默认版**(`stego_classifier.joblib`) — LGB tuned
    (`num_leaves=31, n_estimators=800, learning_rate=0.03, min_child_samples=10`)
    - Held-out AUC **0.8946**,8 split 平均 **0.9085**
    - OOD 鲁棒:**1/8 fp**(median prob 0.011),真实校园 JPEG 干净
    - 训练数据:`data/dataset_campus_v2_jpeg.csv`(143d,12 档变体 + 414 张 JPEG 干净)
  - **53d 可解释版**(`stego_classifier_v2_jpeg_lgb_51d.joblib`) — 去 SRM 90 维
    - Held-out AUC **0.9100**(+0.015),8 split 平均 **0.9227**(+0.014)
    - 弱档检出全面优于 143d:nsF5 p3 d=0.25 87.2%、matrix p3 d=0.40 95.4%
    - OOD 鲁棒:3/8 fp(牺牲少量鲁棒性换 AUC 与可解释性)
    - 51 维有明确统计定义,可对单图输出 Top 贡献特征(论文/教学推荐)
  - 关键发现:v2 143d 中 ~73% 增益来自 31 个可解释特征,SRM 90 维平均单特征 AUC 仅 0.50~0.52
    (近随机),是 LGB 中的"噪声特征";但 SRM 残差对 JPEG 高频噪声有过滤作用,故 143d 在 OOD 上更稳
- **v1.3.1 (待发布)**
  - 补齐运行时依赖 `matplotlib`/`joblib`/`scikit-learn`/`pandas`(此前缺失导致 ML/绘图模块导入崩溃)
- **v1.3.0**
  - 新增**矩阵编码演示**面板(GUI):随机/可点击块 LSB,实时计算伴随式 `s`
    与目标 `m` 的差值 `d`,在汉明校验矩阵 `H` 中定位命中的列并**高亮被改系数**,
    执行修改后校验 `H·x==m`。核心逻辑独立于 `src/matrix_demo.py`。
  - 新增**隐写分析随载荷扫描**面板:`payload` 滑条 0→0.4,逐档重新嵌入并实时刷新
    卡方 p 值 / RS 估计嵌入率 / ML 含密概率三曲线
    （单图无真 AUC，以 ML 概率作区分趋势示意）。逻辑位于 `src/scan_panel.py`。

- **SRM 高通滤波预处理层**
  - 新增 `src/srm_filter.py`（30 个标准 SRM 核，numpy/torch 双实现，合成单通道增强图）；
    `make_dataset.py` 增 `--preprocess srm`、`featurize_gpu.extract_features_gpu` 增
    `use_srm` 开关（`train_ml_gpu` 增 `--srm on/off`）。
  - **同源校园**：CV-AUC 0.7594→0.7922、测试 AUC 0.7811→0.8085，弱密度检出明显提升。
  - **跨源合并（校园+BOSSbase 全量）**：CPU 测试 AUC 0.741→0.704、GPU 校园+BOSSbase2000源
    验证 AUC 0.651→0.572，SRM 均**下降**，两管线相互印证（详见上文 SRM 小节"重要"段）。
  - 结论与默认：默认模型=未 SRM 合并全量（≈0.741），SRM 单源校园（≈0.8085）另存为
    `stego_classifier_campus_srm.joblib` 备用。
- **数据重跑（移除 DIP4E）**
  - 从数据源**去除 DIP4E 教材灰度 tif**，建立纯校园照片目录 `data/campus_jpg`（仅 414 jpg），
    CPU 与 GPU 管线全量重跑：GPU 验证 AUC≈0.790、CPU held-out AUC≈0.781；
    旧数据/模型备份至 `backup_20260905/`。
- **v1.2.2**
  - GPU 数据集支持 **jpg/tif 等多格式混合**（`gpu/make_imageset.py`），去掉默认 150 张上限、默认全量；
    曾用加入 DIP4E tif 后的 **682 张 / 3410 样本** 重训（DIP4E 已于后续数据重跑中移除）。
  - README 检测指标**按数据集区分**（自然照片 A：AUC≈0.79 / 含 tif 混合 B：AUC≈0.767）；
    模型为二进制、不入库，与 PyPI 上 ver1.2.1 明确区分。
- **v1.2.1**
  - 修复仅 1 个有效灰度对的强二值图（`letterA/B/T.tif`）隐写分析 `lgamma(0)` 崩溃，返回中性 p 值。
  - 新增 C++ `nsf5_permute` 确定性置乱加速：4096² 置乱 524ms→210ms、整体嵌入约 540→281ms；
    DLL 缺失自动回退同算法 Python，编码/解码两端序列恒定可逆。
  - GUI 绘图预览崩溃修复，并按屏幕尺寸 1:1 高质量展示。
- **v1.2.0**
  - 新增 **GPU 版**（`gpu/`）：PyTorch 批量向量化复刻 11 维统计特征（RS/卡方/熵/前缀 p，
    与 CPU 参考实现 bit 级一致），GPU 提取 2070 张特征 ≈5s、利用率峰值 99%。
  - 新增 GPU 训练/推理管线 `train_ml_gpu.py`、`predict_gpu.py`；验证 **AUC≈0.79**。
  - 实测与文档说明了"裸像素深度 CNN 需海量独立源图、局部特征法更适合小样本隐写检测"。
- **v1.1.0**
  - 新增 **C++ 嵌入加速** `cpp/nsf5embed.dll`（修复汉明缓存越界；与 Python 像素级一致并经回环校验）。
  - 监督学习升级：数据集扩展为 **6 档密度变体**、构建提速约 8→**90 倍**，
    `train_model.py` 改为 **5 折 GroupKFold** 交叉验证选模。
  - 修复低误报阈值选择 bug（`threshold_for_fp` 取最低阈值而非最高，保障真实低误报检出率）。
  - GUI 新增 **判定灵敏度**（严格 / 均衡 / 宽松），联动启发式与 ML 判决阈值。
  - 新增 CI、Apache-2.0 License、构建与发版说明。
- **v1.0.0**
  - nsF5 伴随式矩阵编码 + 湿纸编码；图像哈希键控；盲隐写分析；GUI；码族与效率绘图。
  - C++ 特征提取 `cpp/fsfeatures.dll`；一版有监督分类器（LR，AUC≈0.78）。

## 许可

本项目基于 **Apache License 2.0** 发布，详见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。