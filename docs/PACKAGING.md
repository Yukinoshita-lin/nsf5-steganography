# 打包计划:安装后像普通应用一样使用

> 状态:**M1–M5 全部完成**(2026-09-30)。一键链路:
> `python scripts/build_exe.py` → 双 exe onedir(解包约 317MB / 便携 zip 119MB);
> `python scripts/test_frozen.py`(`make pkg-test`)五项冻结冒烟全过;
> `python scripts/build_installer.py`(`make installer`)→
> `dist/nsf5stego-setup-1.8.0.exe`(90MB,简体中文界面),静默
> 安装 → 开始菜单快捷方式 + 装好的 GUI/CLI 启动 → 加 PATH 任务 →
> 静默卸载,全流程已实测,卸载后 PATH 逐字节还原。
> **M4**:`.github/workflows/release.yml` 在 tag `v*` 推送时于
> windows-latest (Python 3.12) 自动走 编译 C++ → 冻结打包 → 冻结冒烟 →
> wheel → choco 装 Inno Setup → 安装器 → 产物追加到 GitHub Release;
> 链路各步骤已在本机逐一实证;2026-09-30 的 v1.8.0 真实 tag 运行已确认
> (release.yml 成功,产物追加到 Release)。**M5**:README 中英文新增安装版入口
> ("方式 0:Windows 安装版")。
>
> Inno Setup 6.7.3 装在 `D:\Users\32403\.zcode\tools\Inno Setup 6`
> (choco 需管理员被拒,改官方包 /VERYSILENT 装 D 盘);`build_installer.py`
> 按 `NSF5_ISCC` 环境变量 → 该 D 盘路径 → 常见路径 → PATH 找 ISCC
> (CI 上 choco 装完自带 PATH)。中文界面文件 `installer/ChineseSimplified.isl`
> 已入库(Inno 6.3+ 官方翻译,经 GitHub API 获取)。两处与原计划的偏差:
> GUI exe 文件名用 ASCII `nsf5stego-gui.exe`(快捷方式显示名仍可为
> "nsF5 隐写工具");C++ 加速库在本机编译成功并已随包分发。

## 1. 目标与非目标

**目标** —— 用户从 GitHub Releases(或网盘)下载 `nsf5stego-setup-<版本>.exe`,
双击安装后:

1. 开始菜单出现"nsF5 隐写工具"(可选桌面快捷方式),双击即开 GUI,
   全程不需要终端、不需要装 Python;
2. 可选勾选"加入 PATH",装完 `nsf5stego embed / extract / analyze` 直接可用;
3. 控制面板"应用和功能"里可以正常卸载;
4. 产物(含密图/效率图)写到**用户可写目录**,绝不写进安装目录;
5. Windows 10/11 x64 开箱即用,离线可用(联网只是下载安装器本身)。

**非目标**:不做自动更新;不上架商店(MSIX 可作后续);PyPI wheel 流程
**保留不变**——`pip install nsf5stego` 服务 pip 用户/Colab/CI,与安装版互补。

## 2. 方案选型

**推荐:PyInstaller onedir(双 exe)+ Inno Setup 安装器 + 同一产物打便携 zip。**

| 方案 | 结论 | 理由 |
|------|------|------|
| PyInstaller **onedir** + Inno Setup | ✅ 采用 | 启动快(实测 0.3s)、杀软误报率低于 onefile、模型/DLL 以普通文件存在便于排障;Inno Setup 成熟、支持中文界面/快捷方式/卸载 |
| PyInstaller onefile | ❌ | 每次启动解压到临时目录(慢),单文件 exe 是杀软误报重灾区 |
| MSIX / 商店 | ⏸ 后续 | 打包与签名门槛高,先不做 |
| py2app + AppImage(mac/Linux) | ⏸ 后续 | 项目声称跨平台,但安装版先做主战场 Windows;mac/Linux 用户走 pip/Colab |
| 仅 wheel + 快捷方式脚本 | ❌ | 要求用户先装 Python,不满足"像其他应用一样" |

**双入口**:同一份代码出两个 exe——
`nsf5stego.exe`(控制台,CLI 全功能)+ `nsf5stego-gui.exe`(windowed,直接进 GUI)。
控制台/窗口ed 用同一 spec 构建两次,仅 `console` 标志不同。

## 3. 实证基础(2026-09-30 冒烟,PyInstaller 6.22.3 + Python 3.14,本机)

这些不是推测,是已经跑通的事实,实现时直接沿用:

- `python -m PyInstaller --name nsf5stego --hidden-import gui --hidden-import joblib
  --hidden-import pandas --hidden-import sklearn --collect-all lightgbm
  --add-data "models/*.joblib;nsf5_models" --add-data "models/*.card.json;nsf5_models"
  src/cli.py` 构建 onedir 约 **3 分钟**;
- 冻结 exe 实测:`embed` 冷启动 **0.3s**,`extract` 往返一致,
  `analyze --json` 温启动 2.0s,**ML 概率与源码运行逐位一致**
  (0.042463230474490035);
- `--hidden-import gui` 会连带收齐 tkinter/matplotlib(Agg)链。

**三条血泪教训**(冒烟中各踩一次,正式 spec 必须遵守):

1. **模型必须显式 `--add-data`**:对 `nsf5_models` 用 `--collect-data` 会把
   models/ 下的文件**平铺进 `_internal/` 根**(package-dir 映射丢子目录),
   `ml_predict` 按 `nsf5_models/<名字>` 找不到 → ML 静默不可用;
2. **延迟导入必须显式收集**:`joblib`、`pandas`、`lightgbm`、`sklearn` 在
   `ml_predict.py` 里全是函数内 import(或反序列化 pickle 时才需要),静态
   分析看不见——不带 hidden-import/collect-all 时包里连 lightgbm 都没有,
   ML 静默不可用;`--collect-all sklearn` 会过度收集(包体 **3.0GB**!),
   必须用 `--hidden-import sklearn` 让 hooks-contrib 的专用钩子精准收集
   (414MB);
3. **models/ 白名单**:`models/` 里有 10 个 joblib(含 `.bak` 训练残留),
   `--add-data models/*.joblib` 会全打进去——正式 spec 按白名单只收
   `stego_classifier.joblib`、`stego_classifier_v2_jpeg_lgb_51d.joblib`
   和对应两个 `.card.json`(与 pyproject `[tool.setuptools.package-data]` 一致)。

## 4. 需要的代码补丁(实现 M1 时一并做)

冻结环境里 `__file__` 指向 `_internal/`,`sys._MEIPASS` 才是资源根;现有三处
路径逻辑需要 frozen 分支:

1. **`pathutil.app_version()`**:冻结后读不到安装元数据(冒烟实测显示
   `unknown`)。构建时把版本号写成 `version.txt` 一并打入
   (`--add-data "build/version.txt;."`),`app_version()` 增加
   `sys._MEIPASS/version.txt` 候选;
2. **`pathutil.output_dir()`**:冻结 + 安装到 Program Files 时 `cwd/output`
   不可写。增加 frozen 分支:默认 `%APPDATA%/nsf5stego/output`
   (`os.environ["APPDATA"]`,非 Windows 用 `~/.local/share/nsf5stego`),
   仍遵循"永不抛错";
3. **`cpplib` 的 `CPP_DIR`**:补 `sys._MEIPASS/cpp` 候选,配合 spec 把
   `make cpp` 产物打进包;没有 DLL 时照旧回退纯 Python(现有逻辑不动);
4. (已完成,2026-09-30)**`cli._ml_verdict`**:ML 不可用时在 JSON 里带出
   `load_error`——打包排障全靠这一行。

## 5. 阶段计划与验收标准

### M1 打包规格入库 ✅
- 新增 `nsf5stego.spec`(两个 Analysis:console + windowed,**共享一个
  COLLECT**,DLL/模型只有一份)与 `scripts/build_exe.py`(封一层:生成
  version.txt + version_info 版本资源 → 尽力编译 C++ → 调 PyInstaller →
  冻结冒烟 → 打便携 zip),体积预算 **≤ 500MB**;
- 上面第 4 节的三个 frozen 补丁 + 单测
  (test_pathutil 增加 frozen 分支用例,补丁 `sys._MEIPASS`)。
- **验收**:本机 `python scripts/build_exe.py` 一键出
  `build/exe/nsf5stego/`(双 exe),`--version` 带版本号。实测 onedir
  **317MB** / 便携 zip **164MB**,C++ 加速库随包分发。

### M2 冻结冒烟测试 ✅
- 新增 `scripts/test_frozen.py`:对 dist 里的 CLI 跑 embed→extract 往返、
  analyze JSON 断言 盲分析概率与 `ml.probability` 与源码一致(容差 1e-9)、
  体积预算断言、GUI exe 启动后按标题/pid 找窗口并 DWM 截屏做**蓝白主题
  像素自检**,探针图留 `build/pkg-test/gui_probe.png` 供人工复核;
- **验收**:`make pkg-test` 本地一键通过,五项全绿。

### M3 Inno Setup 安装器 ✅
- 新增 `installer/nsf5stego.iss`:简体中文界面、每用户免管理员安装(默认
  `%LOCALAPPDATA%\Programs\nsf5stego`)、开始菜单 + 可选桌面快捷方式、
  可选"加入用户 PATH"(卸载时精确移除并广播 WM_SETTINGCHANGE)、版本号
  由 exe 版本资源注入;
- **验收**:本机 ISCC 出 `nsf5stego-setup-1.8.0.exe`(本机 125MB / **CI 产物
  90MB**,见下),静默安装 → 开始菜单快捷方式 → 装好的 GUI/CLI 启动 → 加 PATH
  任务 → 静默卸载,卸载后应用目录、开始菜单组清除,**用户 PATH 恢复原值**
  (只删掉我们追加的那一项;若原值末尾带多余的 `;` 等冗余分隔符,重建时会被
  规范化 —— 所以严格说不是"逐字节",见 `installer/nsf5stego.iss` 的
  `RemoveFromUserPath`)。
  > **尺寸以 CI 产物为准**(2026-09-30 v1.8.0 Release 实测):setup exe
  > 90,032,664 B(**85.9 MiB**),便携 zip 118,900,069 B(**113.4 MiB**);
  > 本机(Python 3.14 + 本地 PyInstaller)则分别是 125MB / 164MB。
  > 差异来自构建环境与 PyInstaller 版本,不是回归 —— 引用体积请注明环境。

### M4 CI 自动出包 ✅
- 新增 `.github/workflows/release.yml`:tag `v*` 推送 → windows-latest
  (Python 3.12) → 依赖 → `scripts/build_cpp.py` → `build_exe.py` →
  `test_frozen.py` → wheel → choco innosetup → `build_installer.py` →
  产物(setup exe / 便携 zip / wheel)追加到 GitHub Release,调试工件
  (含 GUI 探针截图)随时可下载;
- **与 ci.yml 协同**:ci.yml 的 release 作业同样在 `v*` tag 上创建 Release
  并生成发布说明;release.yml 只追加文件、不重复生成 notes;
- **验收**:链路各步骤本机逐一实证(YAML 校验通过);首次真实 tag 运行待
  推 tag 后在 Actions 页确认。

### M5 文档 ✅
- README 新增"方式 0:Windows 安装版(推荐普通用户)"小节与英文 Quick Start
  指引;CHANGELOG 记录整条打包链。

## 6. 风险与对策

| 风险 | 对策 |
|------|------|
| 杀软误报 | onedir(已定);有条件时上代码签名证书,没有则在 README 提示"SmartScreen 点仍要运行" |
| 首启慢(模型加载 ~1-2s) | 可接受;GUI 启动画面后续可加 |
| Python/PyInstaller 版本漂移 | CI 钉版本(Python 3.12 + PyInstaller 当时最新);spec 入库可复现 |
| 体积膨胀回归 | M2 冒烟断言 dist ≤ 500MB,超了直接红 |
| 卸载残留用户数据 | 卸载时询问是否删除 `%APPDATA%/nsf5stego`(默认保留) |

## 7. 工作量估计

M1+M2 约半天,M3 约半天(需装一次 Inno Setup),M4 约半天(调试 CI)。
合计 **1.5–2 个工作日**出首个安装版。
