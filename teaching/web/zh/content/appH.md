# 附录 H · 命令行工具与安装版（v1.9.0）

<!-- lang-switch -->
> [🌐 English version](https://yukinoshita-lin.github.io/nsf5-steganography/en/content/appH.html)

本手册正文以“从 Python 代码出发”讲解算法；v1.8 起，项目同时提供**不写一行代码就能完成完整流程**的两种形态：图形界面（见第 2 章与第 10 章）与命令行工具 `nsf5stego`。本附录速查这两种形态的安装与用法，命令在 Windows PowerShell 与 Linux/macOS 终端下均可运行。

> **版本说明｜** 本附录随项目 **v1.9.0**（2026-10）更新。命令行在 v1.8 的 `embed / extract / analyze / gui` 之上，v1.9.0 新增 **JPEG 压缩域（`--jpeg`）** 与 **实验档案一键重跑（`repro`）**；像素域的既有用法完全不受影响。

## H.1 三种安装形态

| 形态 | 适合谁 | 怎么装 | 产物落在哪 |
| --- | --- | --- | --- |
| **Windows 安装版**（推荐普通用户） | 不装 Python，只想直接开软件 | 到 [Releases](https://github.com/Yukinoshita-lin/nsf5-steganography/releases/latest) 下载 `nsf5stego-setup-<版本>.exe`，双击安装（简体中文向导，每用户免管理员） | `%APPDATA%\nsf5stego\output` |
| **免安装便携包** | 不想安装、随身带 | 同一 Release 里的 `nsf5stego-portable-<版本>-win64.zip`，解压即用 | 便携包所在目录 |
| **源码 / PyPI** | 要读代码、写脚本、接 CI | 源码 `pip install -e .`；PyPI `pip install nsf5stego`（已上架 1.9.0） | 当前工作目录 |

安装版要点：

- 开始菜单（可选桌面快捷方式）→ **nsF5 隐写工具**，双击即开图形界面，**不需要 Python**；
- 向导里勾选“加入用户 PATH”后，`nsf5stego` 命令行直接可用（重开终端生效），卸载时自动从 PATH 移除；
- 首次运行若遇 SmartScreen 提示，点“仍要运行”——项目未做代码签名。

> **避坑提醒｜** 本项目支持 Python 3.9，但 **JPEG 压缩域依赖姊妹项目 [`yccstego`](https://github.com/Yukinoshita-lin/yccstego)，它要求 Python ≥ 3.10**。该依赖按环境标记自动安装；缺失时 `jpegstego.available()` 为 `False`，`--jpeg` 会给出可读的安装提示，而**像素域功能完全不受影响**（这与缺 `lightgbm` 时 ML 判定的降级模式一致）。

## H.2 子命令速查

```bash
nsf5stego --help                    # 总览; --version 打印版本号
nsf5stego embed   cover.png -m "秘密文本" -p 口令 -o stego.png
nsf5stego extract stego.png -p 口令
nsf5stego analyze stego.png --sensitivity 宽松 --json
nsf5stego repro   experiment.json -m "秘密文本"
nsf5stego gui                       # 图形界面 (与 python src/gui.py 相同)
```

| 子命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `embed <封面图>` | 把文本嵌入图像 | `-m/--message`（缺省读 stdin）、`-o/--out`、`--jpeg`、`--quality`（1–100，默认 85，仅 `--jpeg`）、`--json`（导出实验档案）、`--method {nsF5,matrix}`、`--hamming-p {1..6}`（默认 3）、`-p/--password` |
| `extract <含密图>` | 从含密图解码文本 | `--jpeg`、`--method`、`--hamming-p`、`-p/--password` |
| `analyze <图...>` | 盲隐写分析（卡方 + RS [+ ML]） | `--jpeg`、`-s/--sensitivity {严格,均衡,宽松}`（默认 均衡）、`--json` |
| `repro <档案.json>` | 按实验档案重跑并逐项校验 | `-m/--message`、`-c/--cover`、`-p/--password`、`-o/--out` |
| `gui` | 启动图形界面（tkinter） | — |

三点容易踩的语义：

- **`--method` 与 `--hamming-p` 仅像素域有效**：JPEG 压缩域固定是 nsF5 语义，不接受这两个参数；
- **`analyze` 的通配符由 CLI 自己展开**（Windows 的 shell 不展开），所以 `nsf5stego analyze *.png` 在三大平台都能直接用；批量里某张图读不出来只记为 `error` 条目并继续跑完，整体仍以非零码退出；
- **`--json` 在 `analyze` 下的形状**：单图输出对象，多图输出对象数组（每项带 `image` 键），脚本可稳定解析。

## H.3 像素域与 JPEG 压缩域：域必须一致

```bash
# 像素域 (默认): 改灰度像素的 LSB, 输出 PNG
nsf5stego embed cover.png -m "秘密" -o stego.png
nsf5stego extract stego.png

# JPEG 压缩域 (v1.9.0): 在量化 DCT 系数上嵌入, 输出标准 .jpg
nsf5stego embed cover.png --jpeg -m "秘密" --quality 85
nsf5stego extract cover_stego.jpg --jpeg     # 嵌入用了 --jpeg, 解码也必须加

# 盲分析: --jpeg 时以 |c|=1 系数指纹为主信号 (该模式下 ML 判定不可用)
nsf5stego analyze stego.png
nsf5stego analyze cover_stego.jpg --jpeg
```

> **避坑提醒｜** 压缩域的载荷住在 **JPEG 位流的量化系数**里，所以含密 `.jpg` 必须原样保存与传输——**用任何工具重新编码一次就毁了**。像素域则相反：PNG/BMP 是无损的，位面不会变。

解码端必须与嵌入端**四处一致**：**域（是否 `--jpeg`）、方法（`--method`）、汉明参数 p、口令**。不一致时解出的不是原文，CLI 会以非零码退出并提示“请确认 方法/p/口令 与嵌入时一致”，而不是把替换字符打印出来。

## H.4 实验档案与一键重跑（v1.9.0）

每次嵌入都能顺手导出**实验档案**：`embed --json`（或 GUI 的“导出实验记录”）把参数、图像哈希与改动统计打成 JSON，schema 为 `nsf5stego.experiment/1`。档案**不含消息明文**，所以重跑时原文要重新提供。

```bash
nsf5stego embed cover.png -m "秘密" --json > experiment_20261003.json
nsf5stego repro experiment_20261003.json -m "秘密"   # 重跑并逐项校验, 逐条打印通过/失败
```

`repro` 的校验强度按域选择：

- **像素域**恒为**逐字节复现**；
- **JPEG 域**在 `yccstego` 版本一致时同样逐字节复现，档案里记录的版本不同则自动退回**往返校验**（提取一致即通过），旧档案仍然兼容。

口令在档案里**只记有无、不记内容**，因此 `repro` 也需要你把口令再传一次（`-p`）。

## H.5 退出码与常见错误

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 运行失败：容量超限 / 口令或参数不匹配 / 图像无法读取等 |
| `2` | 参数错误（参数解析层） |

脚本可直接按退出码判断成败。三个新手最常遇到的错误：

1. **解码加了 `--jpeg`、嵌入没加**（或反之）——域不一致，解不出原文；
2. **`p` 或口令对不上**——解出的是无效文本，CLI 统一以非零码退出并给出提示；
3. **在 Python 3.9 上用 `--jpeg`**——缺 `yccstego`，报错里带有安装提示；装好依赖或改用像素域即可。

## H.6 图形界面：一分钟走通闭环

首次打开图形界面会自动载入一张演示封面，界面顶部的引导条随操作推进，始终提示“下一步点哪里”：点**「嵌入并保存」**（观察改动像素数与保存路径）→ 勾选**「查看差异」**放大看哪些像素变了 → 点**「解码提取」**验证完整还原。整个闭环一分钟内可完成，完成后再回到正文对应章节理解背后的原理。

图形界面与命令行共用同一套参数语义（域 / 方法 / p / 口令）；CLI 的实现入口是 `src/cli.py`，算法核心仍在 `ns5_core.py`。

想继续往下走：命令行只能跑通流程，**参数背后的原理**仍在正文——域与位平面见第 1 章、JPEG 与 DCT 见第 1½ 章、矩阵编码与湿纸见第 4、5 章、实验档案的设计见第 9 章。
