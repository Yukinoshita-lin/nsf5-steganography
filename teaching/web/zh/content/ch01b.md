# 第 1½ 章 · JPEG 是什么，DCT 系数是什么？（压缩域隐写的战场）

<!-- lang-switch -->
> [🌐 English version](https://yukinoshita-lin.github.io/nsf5-steganography/en/content/ch01b.html)




> **新手提示｜** 这一章写于 v1.9.0（2026-10），是应"学习路径应该先讲清楚 JPEG 和 DCT，再进入 LSB/隐写"的反馈补进来的。它编号是"1½"而不是把后面各章整体重排：手册已有大量"见第 N 章"的交叉引用、10 个按章 Notebook 和事实校验脚本，重编号的收益远小于风险。你只需要在读完第 1 章之后、进入第 3 章之前，把这一章读完。

第 1 章把图像拆成了像素与位平面，接下来按理就该讲 LSB 隐写了。但本项目的主线算法 nsF5 有两个"家"：主仓库 `ns5_core.py` 里的像素域实现（改灰度像素），以及 v1.9.0 起接入主线的 JPEG 压缩域实现（改量化 DCT 系数，来自姊妹项目 yccstego）。教科书里的 F5/nsF5 讲的是后者。不先弄懂 JPEG 和 DCT 系数，第 4、5 章里的"+3→+2"就永远只是口号。

## 1.5.1 JPEG 是什么：一台"有损压缩机"

JPEG 不是一种文件格式那么简单，它是一条**有损压缩流水线**，对每个 8×8 像素块依次做三件事：

1. **DCT 变换**：把 8×8 的像素值改写成 64 个"花纹权重"（下一节细讲）；
2. **量化**：每个权重除以量化表里对应位置的一个步长，再四舍五入取整——**有损就发生在这一步**：右下角（高频）的步长大，除完取整后大量直接变成 0；
3. **熵编码**：把剩下的非零系数按之字顺序串起来做压缩编码，写成 .jpg 文件。

第 3 步是可逆的（能一字不差地解回来），第 2 步不可逆（取整丢掉的信息回不来）。**JPEG 压缩域隐写的全部艺术，就是让秘密住进第 2 步的产物——量化之后的系数——里。**

> **避坑提醒｜** 这也解释了第 3 章 FAQ 的那句话"JPEG 会破坏像素 LSB"：一张藏了像素 LSB 的 PNG 被另存为 JPEG 时，整条流水线重新跑一遍，量化取整会把 LSB 结构搅乱。反过来，JPEG 域隐写写的是量化系数本身，编码器会带着这些系数原样做完熵编码——所以它的含密图**必须是 JPEG 自己**，而且**不能再被任何工具重新另存**（重存等于重新量化，载荷即毁）。GUI 对 JPEG 域含密图按原始字节保存，就是这个原因。

## 1.5.2 DCT 系数是什么：8×8 块的"配方表"

把 8×8 块看成一幅微型画像。DCT（离散余弦变换）准备了 64 种固定的"花纹"：左上角的花纹是整块的均匀明暗（最低频），往右下走花纹越来越细密（高频）。DCT 变换做的事，就是回答一个问题：**这一块像素，按每种花纹各用多少比例调配出来？**得到的 64 个配比就是 DCT 系数。

- 左上角第一个系数叫 **DC**（直流），表示整块的平均亮度，不参与隐写；
- 其余 63 个叫 **AC**（交流）系数；
- 自然图像的能量集中在左上（低频），所以量化后右下角大批系数归 0——**归零的系数不是载体，活下来的非零 AC 系数才是**。

> **动手做｜** 下面的片段用项目压缩域实现里同一套 DCT 矩阵与量化表（`yccstego/dct.py`），对同一个 8×8 块分别按质量 60、85、95 量化，数一数非零 AC 载体和 |c|=1 的"湿点"各有多少。跑之前请确认已安装压缩域依赖：`pip install yccstego`。

```python
import numpy as np
from yccstego import dct as jdct

# 造一个 8x8 块: 平滑渐变(低频为主) + 轻噪声(高频细节)
rng = np.random.default_rng(3)
block = np.linspace(90, 200, 8)[None, :] + np.linspace(0, 60, 8)[:, None]
block = np.clip(block + rng.integers(-8, 9, (8, 8)), 0, 255).astype(float)

counts = {}
for q in (60, 85, 95):
    T = jdct.scale_qtable(jdct.LUM_QT, q)      # libjpeg 风格的质量缩放
    F = jdct.dct_blocks(block - 128)           # 中心化后做 DCT (JPEG 的做法)
    Q = np.round(F / T).astype(int)            # 量化: 有损就发生在这一步
    ac = Q.reshape(-1)[1:]                     # 去掉 DC, 剩 63 个 AC
    nz = int(np.sum(ac != 0))
    wet = int(np.sum(np.abs(ac) == 1))
    counts[q] = nz
    print(f"质量 {q}: 非零 AC 载体 {nz} 个, |c|=1 湿点 {wet} 个")
assert counts[95] > counts[60], "质量越高, 活下来的载体应越多"
print(f"质量 95 的非零 AC 载体多于质量 60: {counts[95]} > {counts[60]}")
```

<!-- expect: 质量 95 的非零 AC 载体多于质量 60 -->

> **观察｜** 你会看到两个规律：质量从 60 提到 95，非零 AC 载体明显变多（量化步长变小，更多系数"活了下来"）；同时 |c|=1 的系数不少——它们马上就要给你惹麻烦了。

## 1.5.3 在系数上做 nsF5：载体、湿点与减幅

JPEG 域 nsF5 的载体系数是**量化 Y 块（亮度）的非零 AC 系数**，每个系数贡献一个比特：`x = c & 1`（奇偶）。往一个比特里写 1，不是把系数翻转，而是 **F5 的"减幅"：幅值减 1、保符号**。

| 原系数 | 修改后 | 说明 |
| --- | --- | --- |
| +3 | +2 | 幅值减 1，奇偶从 1 变 0 |
| −5 | −4 | 保符号，同样翻 LSB |
| +1 | 湿点，不碰 | 再减就归 0（收缩），系数会从载体集合里消失 |
| −1 | 湿点，不碰 | 同上 |

为什么"收缩"是灾难：提取端要按同样的顺序收集载体系数，一个系数从 +1 缩成 0 就从集合里消失，后面所有比特错位。这正是 F5 的老毛病，也是 nsF5 用**湿纸编码**（把 |c|=1 的系数划为"湿点"、只在干点上解方程）修掉的问题——第 5 章展开。

> **动手做｜** 三行代码看懂"减幅"与"湿点"的边界：

```python
for c in (3, -5, 1, -1):
    action = c - (1 if c > 0 else -1) if abs(c) > 1 else "湿点, 不碰"
    print(c, "->", action)
```

<!-- expect: 3 -> 2 -->

> **想一想｜**
> 1. +3 和 +2 的二进制 LSB 都是 1，减幅之后 LSB 怎么会变？——提示：想想 +1、-1 与奇偶的关系，再想 |c|=1 时为什么不能减。
> 2. 与"翻转 LSB"（+3 与 +4 之间跳）相比，减幅让系数的幅值直方图在 |c|=1 处堆积。这种堆积是伪装的破绽还是伪装的代价？第 8 章的"magnitude-1 指纹"会反过来用它抓隐写。

> **避坑提醒｜** JPEG 域的口令键控与像素域同理：隐藏路径由"色度系数哈希 + 口令"派生，解码端 p / 口令 / 质量（若重嵌）任一不一致都提取不出来。重跑契约两域一致：yccstego 0.2.0 起湿纸求解种子由输入派生，相同输入逐字节复现；档案记录建档时的 yccstego 版本，重跑同版本走字节级校验，跨版本自动退回"提取一致"（旧档兼容），这写在了 `src/experiment.py` 的文档里。

## 1.5.4 在真 JPEG 上跑一遍

前面两段是在"单块"上看原理。真正的嵌入由 yccstego 完成：整图分块、逐块量化、在全部载体上做伴随式编码、再熵编码回标准 .jpg。下面用桥接层把它跑通（GUI 的"JPEG 域"和 CLI 的 `--jpeg` 走的就是这同一份代码）：

```python
import sys
sys.path.insert(0, "src")        # 源码运行时需要; pip 安装后可删掉这行
import numpy as np
import jpegstego

rng = np.random.default_rng(7)
y = np.linspace(0, 220, 128)[None, :]
x = np.linspace(0, 90, 128)[:, None]
gray = np.clip(110 + y + x + rng.integers(-6, 7, (128, 128)), 0, 255).astype(np.uint8)
rgb = np.stack([gray, gray, gray], axis=-1)      # JPEG 域吃 RGB

jpg, rep = jpegstego.embed_jpeg(rgb, "你好, DCT 域!", p=3, quality=85)
print("改动系数:", rep["carriers_changed"], "容量(bit):", rep["capacity_bits"])

msg, _, tampered, head_match = jpegstego.extract_jpeg(jpg, p=3)
assert msg == "你好, DCT 域!" and not tampered and head_match
print("往返一致:", msg)
```

<!-- expect: 往返一致: 你好, DCT 域! -->

命令行等价形式（安装后可用）：

```bash
nsf5stego embed cover.png --jpeg -m "秘密" --quality 85
nsf5stego extract cover_stego.jpg --jpeg
```

## 1.5.5 回到项目看代码

| 概念 | 文件 | 优先阅读内容 |
| --- | --- | --- |
| 桥接层（统一入口/降级提示） | src/jpegstego.py | embed_jpeg / extract_jpeg |
| 块级 nsF5（减幅 + 湿纸） | yccstego/yccstego/nsf5.py | _embed_block / solve_wet_paper |
| DCT 与量化表 | yccstego/yccstego/dct.py | _dct_matrix / scale_qtable / LUM_QT |
| JPEG 域分析（\|c\|=1 指纹） | yccstego/yccstego/steganalysis.py | analyze_y |
| 重跑契约（两域差异） | src/experiment.py | verify() 与模块文档 |
| GUI 域切换 | src/gui.py | _on_domain_change / _do_embed_jpeg |

> **想一想｜** 把同一张 128×128 的图分别用像素域（第 5 章的 nsF5Pixel）和本章的 JPEG 域嵌入，统计"可写位置"的数量：像素域约有 16000 个像素位，JPEG 域只有几千个系数——是什么决定了两者的差距？质量 60 时再算一次呢？这个容量直觉会在第 10 章的综合实验里派上用场。
