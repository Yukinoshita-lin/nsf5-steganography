# nsF5 图像隐写工具 (Steganography)

![CI](https://github.com/Yushitayuri/nsf5-steganography/actions/workflows/ci.yml/badge.svg)
![version](https://img.shields.io/badge/version-1.2.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![python](https://img.shields.io/badge/python-3.9%2B-blue)

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
| **绘图** | 绘制码族(嵌入率 α vs 载荷)理论曲线 与 实测嵌入效率对比 |
| **GUI** | 载入图 → 嵌入/解码 → 分析 → 绘图 一体化界面 |

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
    ├── make_dataset.py   # 批量生成特征数据集
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

### 实测 (RTX 4060 Laptop / 2070 样本)

- **特征提取**：2070 张 512² 灰度 约 **5s（≈410 img/s）**，GPU 利用率峰值 **99% / 平均 75%**。
- **检测性能**：验证 **AUC≈0.79**；按档检出率（Youden 阈值）——
  `matrix p3`≈99%、`nsF5 p2`(强)≈89–93%、弱 `nsF5 p3`≈64%、干净误报可控。
- **一致性**：`python gpu\featurize_gpu.py` 自检，GPU 与 CPU 参考特征逐项一致
  （RS 到 bit 级、浮点 ~1e-7）。

> 依赖：`torch`(CUDA)、`numpy`、`Pillow`、`scipy`、`scikit-learn`、`joblib`、
> `nvidia-ml-py`(可选，用于上报 GPU 利用率)。样本数据 `gpu/data/*.npz` 较大，不入库，可重生成。

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
  - 新增 CI、MIT License、构建与发版说明。
- **v1.0.0**
  - nsF5 伴随式矩阵编码 + 湿纸编码；图像哈希键控；盲隐写分析；GUI；码族与效率绘图。
  - C++ 特征提取 `cpp/fsfeatures.dll`；一版有监督分类器（LR，AUC≈0.78）。

## 许可

本项目基于 **MIT License** 发布，详见 [LICENSE](LICENSE)。