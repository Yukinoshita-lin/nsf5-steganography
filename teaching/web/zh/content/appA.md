# 附录 A · 术语中英对照

<!-- lang-switch -->
> [🌐 English version](../../en/content/appA.md)


按出现顺序整理，方便随时查阅。掌握粗体项即可覆盖本手册绝大部分内容。

| **中文** | **英文** | **一句话解释** |
| --- | --- | --- |
| 隐写术 | Steganography | 把秘密信息藏进正常载体，隐藏“通信行为本身” |
| 隐写分析 | Steganalysis | 通过统计/学习判断载体是否藏有秘密 |
| 载体 / 含密图 | cover / stego | 嵌入前的原始图像 / 嵌入后的图像 |
| 最低有效位 | LSB | 像素二进制的最低位，翻转后视觉几乎不变 |
| 位平面 | bit plane | 按二进制位拆出的二值图层，共 8 层 |
| 冗余 | redundancy | 载体中可被修改而不易察觉的部分 |
| 嵌入容量 | capacity / payload | 一张图最多能承载的秘密比特数 |
| 相对载荷 | relative payload | 嵌入比特数与可嵌位置数之比 |
| 嵌入效率 | embedding efficiency | 平均每次修改所携带的比特数 α |
| 矩阵嵌入 | matrix embedding | 用分组编码在更少改动中嵌入更多位 |
| 二元汉明码 | binary Hamming code | 能纠正/定位 1 位错误的线性码 [n,k,3] |
| 校验矩阵 | parity-check matrix H | p×n 矩阵，列互异，用于算伴随式 |
| 伴随式 | syndrome | s=H·x (mod 2)，块的“现状摘要” |
| GF(2) | Galois field of 2 | 只含 0/1、按异或运算的有限域 |
| 收缩 | shrinkage | 减幅时系数变 0 导致块作废的现象 |
| 湿纸编码 | wet paper coding | 湿点不动、只在干点解方程完成嵌入 |
| 干点 / 湿点 | dry / wet positions | 可修改的位置 / 碰不得的位置 |
| F5 / nsF5 | F5 / nsF5 algorithm | JPEG 矩阵嵌入；nsF5 用湿纸消除收缩 |
| 减幅 | coefficient shrinking | 让系数绝对值减小 1 的修改方式 |
| SHA-256 | SHA-256 | 输出 256 位摘要的密码学哈希函数 |
| 键控 | keying | 由口令/内容密钥决定隐藏位置等行为 |
| 确定性置换 | deterministic permutation | 同种子必得同排列的洗牌算法 |
| splitmix64 | splitmix64 | 项目使用的 64 位伪随机数生成器 |
| Fisher–Yates | Fisher–Yates shuffle | 等概率洗牌的标准算法 |
| 自同步 | self-synchronization | 解码端无需外部参数即能找到正文 |
| 篡改感知 | tamper perception | 图像被改动后能够被察觉 |
| 盲隐写分析 | blind steganalysis | 无原始载体时的统计检测 |
| 卡方检验 | chi-square test | 检验相邻灰度对是否被拉平 |
| p 值 | p-value | 观测与假设吻合的概率（此处高 p 反而可疑） |
| RS 分析 | RS analysis | 通过正负掩码扰动统计规则/奇异组 |
| 常规/奇异组 | regular / singular | 扰动后判别值变大 / 变小的像素组 |
| 差分熵 | difference entropy | 相邻像素差分布的香农熵，衡量纹理随机度 |
| 香农熵 | Shannon entropy | 信息量/不确定度的度量，单位 bit |
| 监督学习 | supervised learning | 用带标签样本训练模型 |
| 特征向量 | feature vector | 描述样本的数值列表（本项目 11 维） |
| 标签 | label | 样本的正确答案（0=干净，1=含密） |
| 二分类 | binary classification | 输出属于两类之一的预测 |
| 逻辑回归 | logistic regression | 线性加权 + sigmoid 的可解释分类器 |
| sigmoid | sigmoid | 把任意实数压到 0～1 的 S 形函数 |
| 交叉熵损失 | cross-entropy loss | 分类常用的损失函数 |
| 梯度下降 | gradient descent | 沿损失下降方向迭代更新参数 |
| 过拟合 | overfitting | 背下训练样本而失去泛化能力 |
| 交叉验证 | cross-validation | 轮流用不同折验证模型的流程 |
| 数据泄漏 | data leakage | 验证信息混入训练导致指标虚高 |
| GroupKFold | GroupKFold | 按组切分的交叉验证（同照片样本同组） |
| 混淆矩阵 | confusion matrix | 真实 vs 预测的四格计数表 |
| 精确率/召回率 | precision / recall | 判对比例 / 抓全比例 |
| ROC / AUC | ROC curve / AUC | 全阈值下的检出-误报曲线及其面积 |
| Youden 准则 | Youden’s J | 在 tpr−fpr 最大处选阈值 |
| 误报 / 漏报 | false positive / negative | 把干净判成含密 / 把含密判成干净 |
| ctypes | ctypes | Python 调用 C/C++ 动态库的接口 |
| DLL | dynamic-link library | Windows 动态链接库 |
| CUDA / 批处理 | CUDA / batching | GPU 并行计算 / 多样本同时处理 |
| 一致性校验 | consistency check | C++/GPU 与 Python 结果逐位比对 |
| ASCII / UTF-8 | ASCII / UTF-8 | 英文字符编码 / 通用字符编码（含中文） |
| 空间富模型 | SRM / Spatial Rich Model | 一组高通滤波残差核，用于突出嵌入噪声 |
| 残差图 | residual map | 高通滤波后保留的“噪声残差” |
| LightGBM | LightGBM / LGB | 梯度提升树实现（v1.4 双版本模型使用的分类器） |
| 特征组 | feature group | 同一来源的一批特征（BASE/SRM/PREFIX/LSB-PREFIX 等） |
| 分布外 | out-of-distribution (OOD) | 与训练分布不同的输入（如真实 JPEG 干净图） |
| BOSSbase | BOSSbase 1.01 | 隐写分析标准基准库：1 万张 512² 灰度 PGM |
| PGM | PGM | 无损灰度图像格式（BOSSbase 载体格式） |
| Stacking | stacking / meta-learner | 用次级模型组合多个基模型预测的集成方法 |
| 内存映射 | memmap | 大数组分批落盘、按需读写，避免一次性 OOM |
| 校准集 | calibration set | 单独用于选择阈值的样本子集 |
| 网格调优 | grid tuning | 在超参数网格上搜索并比较模型 |
| 双版本模型 | dual-version model | 143d 稳健版 + 53d 可解释版并存部署策略 |
