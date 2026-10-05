# 附录 H · 命令行工具与安装版（v1.9.0）

<!-- lang-switch -->
> [🌐 English version](https://yukinoshita-lin.github.io/nsf5-steganography/en/content/appH.html)



本手册正文以“从 Python 代码出发”讲解算法; v1.8 起, 项目同时提供不写一行代码就能完成完整流程的两种形态: 图形界面 (见第 2 章与第 10 章) 与命令行工具 nsf5stego。本章速查这两种形态的安装与用法, 命令在 Windows PowerShell 与 Linux/macOS 终端下均可运行。

## H.1 三种安装方式

PyPI (推荐 pip 用户): pip install nsf5stego —— 自带两个部署模型、命令行入口与图形界面; Windows 安装版: 到 GitHub Releases 下载 nsf5stego-setup-1.9.0.exe, 简体中文向导、每用户免管理员、开始菜单快捷方式、可选加入 PATH; 免安装便携包: 解压 nsf5stego-portable-1.9.0-win64.zip 即用。三者算法完全一致, 按使用场景任选。

## H.2 命令行三步 (与 GUI 一一对应)

嵌入 (把文本写进图片):

```bash
nsf5stego embed cover.png -m "要隐藏的文本" -p 口令 -o stego.png
```

解码 (从含密图还原文本, 方法/p/口令须与嵌入一致):

```bash
nsf5stego extract stego.png -p 口令
```

盲隐写分析 (卡方 + RS + 机器学习判定; 支持多图批量):

```bash
nsf5stego analyze stego.png --json
```

文本按 UTF-8 编码, 中文可直接嵌入; analyze 支持 --json 机器可读输出与通配符批量, 退出码 0/1/2 区分 成功/失败/参数错误, 便于脚本化考核。

## H.3 新手引导路径

首次打开图形界面会自动载入一张演示封面, 界面顶部的引导条会随操作推进, 始终提示“下一步点哪里”: 点「嵌入并保存」(观察改动像素数与保存路径) → 勾选「查看差异」放大看哪些像素变了 → 点「解码提取」验证完整还原。整个闭环一分钟内可完成, 完成后再回到正文对应章节理解背后的原理。

## H.4 与手册正文的对应

命令行的实现入口是 src/cli.py, 算法核心仍在 ns5_core.py: 嵌入/解码原理见第 1–4 章, 盲隐写分析见第 5 章, 机器学习检测见第 8–9 章。用 CLI 完成实验后回到对应章节阅读源码, 学习路径与纯 GUI 用户完全一致。
