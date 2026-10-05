# 附录 L · 配套工具 ImageMatrix 使用指南

本附录是第 1 章配套工具 ImageMatrix 的完整说明。它是同作者发布的独立开源项目（github.com/Yukinoshita-lin/ImageMatrix，Apache-2.0 许可），与本手册学习的 nsF5 项目**没有任何依赖关系，也不含隐写功能**；它唯一的用途，是把“图像 = 数字矩阵”这件事从抽象变成你屏幕上看得见、改得动的东西。

## L.1 它是什么，为什么配它

一句话：**图片 ↔ 数值矩阵（R/G/B/灰度）双向转换器**——纯 C/C++ 编写、不依赖任何第三方库，自带 Win32 图形界面，也提供命令行模式。

| **能力** | **说明** |
| --- | --- |
| 打开图片 | BMP / PNG / JPEG / GIF / TIFF，支持把文件直接拖进窗口 |
| 导出 TXT 矩阵 | 五种排布：CHANNELS / RGB / RGBA / GRAY / HEX |
| 导入 TXT 矩阵 | 把改过的矩阵文本还原成图片；缺宽高时弹窗询问宽度，自动纠错 |
| 另存为图片 | PNG / JPEG / BMP / GIF / TIFF |
| 像素取值 | 状态栏实时显示鼠标所指像素的 R/G/B/灰度 与 #RRGGBB |

把它放进第 1 章，是因为它精确地补上了这本手册开头唯一的“实物缺口”：原文让你“打开项目看代码”，而看代码需要先会 Python（第 2 章才教）；ImageMatrix 让你在**学任何代码之前**，就能亲手验证“图像就是一张整数表格”。它是 CSAPP“先摸实物”纪律在本手册里的第一件教具。

## L.2 获取与安装

| **方式** | **做法** | **适合谁** |
| --- | --- | --- |
| 一键安装包 | 在仓库 Releases 下载 ImageMatrix_Setup.exe，双击安装（无需管理员权限） | 只想动手做实验的同学 |
| 源码编译 | 用 MinGW-w64 运行 build.bat，得到 build\imagematrix.exe 与 imagematrix-cli.exe | 想顺手读一份纯 C++ 工程的同学 |
| 直接运行 | 编译产物是静态链接的单文件，拷到别的 Windows 机器也能直接双击运行 | 实验室机房、无网络环境 |

安装包会把程序释放到 %LOCALAPPDATA%\Programs\ImageMatrix，并自动创建开始菜单与桌面快捷方式；在「设置 → 应用」里可一键卸载。

## L.3 界面与核心操作

![fig-91](../assets/img091.png)

ImageMatrix 主界面。上方一排是“打开图片 / 导出为 TXT / 导入 TXT / 另存为图片”，以及“矩阵格式”下拉框与“写注释头”开关；中间画布支持滚轮缩放与拖动平移。第一次没有素材时，点“生成测试图案”即可得到一张彩条 + 灰阶 + 渐变的测试图。（截图来自 ImageMatrix 仓库）

1. 打开图片：点“打开图片…”，或把图片直接拖进窗口；

2. 查看矩阵：点“查看矩阵文本”，窗口内直接预览当前图片的数值矩阵，可复制到剪贴板；

3. 导出：在“矩阵格式”里选一种排布，点“导出为 TXT…”，选择保存位置；

4. 导入：点“导入 TXT…”，程序按矩阵把图片还原出来（没有 # width 头时会弹窗询问宽度）；

5. 保存：点“另存为图片…”，把还原结果存成 PNG / JPEG / BMP 等。

快捷键：Ctrl+O 打开、Ctrl+S 导出 TXT、Ctrl+T 导入 TXT、Ctrl+E 另存为图片；滚轮以光标为中心缩放，左键拖动平移，放大 8 倍以上显示像素网格。

## L.4 五种矩阵格式速查

| **format** | **每行内容** | **典型用途** |
| --- | --- | --- |
| GRAY | 一行 = 图像的一行（width 个灰度值） | 做第 1.2 / 1.4 节的 LSB 实验（只关心亮度） |
| CHANNELS | R 矩阵 → G 矩阵 → B 矩阵 → GRAY 矩阵 | 看清“彩色图 = 三张表叠起来” |
| RGB | 一行 = 一个像素：R, G, B | 逐像素看颜色 |
| RGBA | 一行 = 一个像素：R, G, B, A | 带透明度（A）的图 |
| HEX | 一行 = 一个像素：RRGGBB | 体会十六进制记法（1.2 节） |

导出的文件带 `#` 注释头，声明 width / height / format / max 与灰度公式，读回时靠它准确还原；灰度公式与手册一致：`Y = round(0.299*R + 0.587*G + 0.114*B)`（ITU-R BT.601）。

## L.5 命令行（批处理与自检）

```text
build\imagematrix-cli.exe to-txt   -i photo.png -o photo.txt -f GRAY
build\imagematrix-cli.exe to-image -i photo.txt -o back.png
build\imagematrix-cli.exe info     -i photo.png
build\imagematrix-cli.exe gen      -o pattern.png -w 320 -h 240
build\imagematrix-cli.exe selftest            :: 20 项自检
```

参数：`-f RGB|RGBA|GRAY|CHANNELS|HEX`、`--no-header`、`--width N`、`-q 92`（JPEG 质量）。命令行与 GUI 导出的 TXT 经仓库测试验证 **SHA256 完全一致**——这正是第 9 章“一致性优先”的工程纪律，只不过这里用在了一个更小的程序上。

## L.6 与手册各章的对应

| **手册位置** | **用 ImageMatrix 做什么** |
| --- | --- |
| 1.1 图像即矩阵 | 导出 GRAY / CHANNELS，亲眼看到“图 = 数字表格” |
| 1.2 二进制与 LSB | 在 TXT 里把 200 改成 201，零代码体验 LSB 翻转 |
| 1.4 位平面 | 把一列像素写成二进制，观察高位 / 低位的规律差异 |
| 1.5 cover / stego | 用记事本手工造出第一对载体与含密图 |
| 2.2 用 NumPy 思考图像 | 先用它看现象，再用 NumPy 复现同一个数组 |
| 3.2 最小 LSB 隐写 | 把手工动作换成代码，比较“手工 vs 代码”的差别 |
| 9.5 测试与 CI | 参考它的 selftest 与 GUI 冒烟测试（GUI 与 CLI 输出逐字节一致） |

## L.7 一个完整的动手流程

> **动手做｜** 从一张照片到一对 cover / stego（全程零代码）
> 
> ① 打开一张真实照片（或点“生成测试图案”）；
> 
> ② 格式选 GRAY，导出为 cover.txt，再另存一份 stego.txt；
> 
> ③ 用记事本打开 stego.txt，按约定位置把若干像素改成目标奇偶（藏 1 → 奇数，藏 0 → 偶数）；
> 
> ④ 导入 stego.txt，另存为 stego.png；
> 
> ⑤ 把原图与 stego.png 并排看：肉眼无差别。
> 
> 进阶：把第 3 章的 Python LSB 脚本跑一遍，导出它生成的 output/stego_*.png，再用 ImageMatrix 打开——你会看到代码与手工做的是同一件事。

最后提醒一句边界：ImageMatrix 帮你**看见**数字，不帮你**隐藏**数字。真正的 nsF5 隐写——汉明矩阵编码、减幅、湿纸编码、口令键控——仍然要在第 4、5、6 章里，跟着 F:\Steganography 的代码一步步学。它只是把你领到门口的那块垫脚石。
