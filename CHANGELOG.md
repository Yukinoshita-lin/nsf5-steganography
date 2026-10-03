# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.9.0] - 2026-10-03

**yccstego 接入教学主线 + 可复现性与自证系统: 教科书里的 nsF5 (JPEG DCT 域) 从此是主线功能, 每次实验可存档重跑, 正确性一键当场可见。**

### Added

- **JPEG 压缩域接入 (姊妹项目 yccstego)**: 新增 `src/jpegstego.py` 桥接层
  (统一入口 / 统一报告口径 / 依赖缺失时降级提示, 与 ml_predict 同模式);
  `pyproject.toml` 按 `python_version >= '3.10'` 声明 `yccstego` 依赖,
  Python 3.9 只影响 JPEG 域, 像素域功能不受影响;
- **CLI `--jpeg`**: `embed --jpeg [--quality 1..100]` 在量化 DCT 系数上嵌入
  并输出标准 .jpg; `extract --jpeg` 从位流字节解码 (认证头失配时指明
  "p/口令不一致或文件被改动"); `analyze --jpeg` 用 |c|=1 系数指纹做
  DCT 域盲分析 (ML 判定在 JPEG 域如实标注不可用);
- **实验档案与一键重跑**: 新增 `src/experiment.py` (schema
  `nsf5stego.experiment/1`) —— 每次嵌入生成参数/哈希/改动统计档案,
  消息明文与口令不落盘; `nsf5stego embed --json` 直接输出,
  `nsf5stego repro <档案> -m 原文` 重跑并逐项校验: 档案记录建档时的
  yccstego 版本, 同版本下两域均承诺**逐字节复现** (yccstego 0.2.0 起湿纸
  求解种子由输入派生, 与像素域同一公式), 跨版本退回**往返一致**并降级
  改动数为参考值 (0.1.4 旧档兼容);
- **GUI**: 参数区新增"嵌入域"切换 (JPEG 域固定 nsF5 语义, 算法选框随之禁用,
  质量框随之启用); 含密 JPEG 按**原始字节**保存 (菜单与嵌入产物都不过 PIL
  重编码, 否则系数即毁); 「往返自检」按钮做 嵌入→提取→比对 内存闭环;
  「导出实验记录」把最近一次嵌入落盘为 JSON 档案;
- **手册**: 新增第 1½ 章 "JPEG 是什么, DCT 系数是什么" (zh/en), 代码片段
  走桥接层真跑; webapp 新增 8×8 DCT 量化系数实验室 (+3→+2 减幅高亮);
- **README**: 新增"同类工具与本项目定位"(Aletheia / CONSEAL / DDE Lab tools
  等, 写明本项目定位是 interactive learning / visualization / reproducible
  experiments, 不替代研究工具链) 与"正确性验证体系"成文。

### Changed

- 测试 96 → 115+ (新增 `test_jpeg.py` / `test_experiment.py` /
  `test_cli_jpeg.py`, GUI 冒烟覆盖域切换/JPEG 往返/档案 schema);
- CI: pytest 作业与手册作业补装 yccstego (JPEG 测试必须在 CI 真跑,
  不允许"本地装了所以一直绿");
- PyInstaller spec: 补 `jpegstego` / `experiment` / `yccstego.*` hiddenimports
  (函数内惰性导入静态分析看不见); 冻结冒烟新增第 6 项 —— 冻结环境
  `--jpeg` 往返 + 档案 repro 通过 (防打包丢依赖的静默降级, 同第 4 条教训)。

## [1.8.4] - 2026-10-01

**GUI 操作台升级与品牌图标: 不换框架、不加依赖, 只动信息架构与视觉层级。**

### Changed

- **操作台按工作流重排**: 输入(载入/演示图 + 待嵌入文本) → 参数(算法/p/口令/灵敏度
  2x2 紧凑排布) → 执行(嵌入/解码/分析主按钮 + 效率图/编码演示/载荷扫描辅助行),
  小节标题 10.5pt 加粗配通栏分隔线, 视线不再来回跳;
- **结果与日志分页**: 「分析结果」「运行日志」收进右栏 Notebook 页签——结果是主角,
  技术日志退居次要; 复制按钮随迁并右缘对齐;
- **进度条仅在忙时显示**, 不再常驻占行;
- **按钮层级与 tooltip**: 主流程三键深蓝加粗(padding 10,6), 辅助工具白底; 自写
  30 行 Tooltip(纯 tk, 无依赖)标注快捷键;
- **跨平台字型**: Win=Microsoft YaHei UI / macOS=PingFang SC / Linux=Noto Sans
  CJK SC, 9/10/13pt 字阶(Tk 对缺失字型自动回退);
- **空状态行动引导**: "(未载入 - 点「演示图」或 Ctrl+O)" 两行居中占位, 空态底色
  近白融入卡片(载入后恢复画布色);
- **待嵌入标签更正** ASCII → UTF-8(算法本就支持中文)。

### Added

- **品牌图标**: 照片卡 + 溢出比特流 + 放大镜检出三元素, 蓝白体系; 多尺寸 PNG/
  多帧 ico/SVG 源与色板卡(palette.png, 对比度按 WCAG 实算)沉淀为设计 token;
  exe/安装器/窗口标题栏全部接入;
- **关于对话框**附联系邮箱 eu-lin@foxmail.com。

## [1.8.3] - 2026-09-30

**两条都是"审计 1.8.2 的 tag 运行"时暴露出来的。**

v1.8.2 的 tag 上, `pytest (完整依赖)` 是**红的**, 而 `发布到 PyPI` 与
`发布 GitHub Release` 却都**成功**了 —— 一个失败的全量测试作业没能拦住发布。
红的原因是 `src/test_ood_smoke.py` 里那条"并行超时必须报错"的用例在我自己写的
1 秒上限上 flake 了（2 张 256² 的小图在快 runner 上 <1s 就跑完，断路器没被触发）。

### Fixed

- **超时用例不再依赖时序**: `--chunk-timeout` 从 `1`(秒) 压到 `0.001`(秒)。
  进程池光是 spawn 子进程 + 加载 LightGBM 就要几百毫秒, 不可能赢过 1 毫秒,
  所以"来不及返回"从"通常成立"变成"必然成立"。本机连跑三次全过。
  （教训与 2026-09-17 那次同源: **测试一旦依赖时序就一定会 flake**。）
- **发布不再绕过验证**: `build` 的 `needs` 从 `[test]` 改成
  `[test, pytest, gui, feature-consistency, notebooks, handbook, attribution]` ——
  任何一项红, `build` / `release` / `pypi` 都不会跑。这些作业本来就并行执行,
  所以只是加约束, 不增加墙钟时间。这正是 v1.8.2 缺的那道闸:
  红灯的 tag 不该往 PyPI 送包。

### Notes

- v1.8.2 已经发布（PyPI + Release + Zenodo）, 其代码与 v1.8.3 相同 —— 差别只在
  测试的时序写法与 CI 的发布闸门; 但按本项目"tag 应对应一次全绿"的规矩,
  v1.8.2 那次 tag 的 pytest 是红的, 所以在 1.8.3 里把这条记录在案, 而不是
  悄悄重打 tag。

## [1.8.2] - 2026-09-30

**一个 Release 里出现了两个不同的 wheel。**

审计 v1.8.1 的产物时发现: PyPI 上的 `nsf5stego-1.8.1-py3-none-any.whl`
(`sha256 5c84312c…`) 与 GitHub Release 资产里的同名文件
(`sha256 b30220c5…`) **不是同一份字节**。原因不是代码不同, 而是**同一个 wheel
被构建了两次**: `ci.yml` 在 Linux 上 `python -m build` → 上传 PyPI + 挂到
Release; `release.yml` 又在 Windows 上 `python -m build --wheel` → 以同名文件
追加到同一个 Release, 把前一份**覆盖**掉。两份的 30 个成员文件内容完全一致,
差异只在 `METADATA`/`RECORD` 与 zip 时间戳 —— 但"哪个哈希对应哪个产物"这件事
因此变得说不清, 而这个项目一直靠"一个版本一份字节"来做溯源
(`nsf5stego-1.8.0` 那次两者就是逐字节相同的)。

### Fixed

- **`release.yml` 不再往 Release 上传 wheel**: Release 里的 wheel/sdist 一律由
  `ci.yml` 的构建作业提供(与 PyPI 上的那两份同源同字节), Windows 作业只提供
  `nsf5stego-setup-*.exe` 与 `nsf5stego-portable-*.zip`。`python -m build --wheel`
  这一步保留(它验证打包元数据在 Windows/Python 3.12 上也编得出来), 只是结果
  不再发布, 并有注释说明原因。

### Verification

- 修复前的对照证据: 两份 1.8.1 wheel 的成员集合相同(30 个文件), 载荷文件
  逐字节相同, 只有 `METADATA`/`RECORD` 与 zip 时间戳不同 —— 据此确认了
  "同名覆盖"而非"代码不同"。
- 修复后的验证见 v1.8.2 的 tag 运行: Release 资产里只应出现 ci.yml 构建的
  wheel/sdist, 且与 PyPI 上的 `sha256` 一致。

## [1.8.1] - 2026-09-30

**审计 1.8.0：给发布链路补上"可验证"。**

审计发现的四件事, 都不是新功能, 而是"声称"与"可验证"之间的差:

1. **v1.8.0 的 tag CI 是红的**（`发布到 PyPI (trusted publishing)` 作业失败：
   pypi.org 端的 pending publisher 从未配置, 而 workflow 走的是 OIDC）。修复
   （改用 API token）落在 tag 之后的一个提交上, 所以**已发布的 tag 与绿色 CI 不
   对应**。缓解事实: PyPI 上的
   `nsf5stego-1.8.0-py3-none-any.whl` 与 GitHub Release 里的那个**字节相同**
   （sha256 `02d2177a…`）, 所以发布产物确实来自 tag 那次构建, 不是另一份代码。
2. **打包链只在 tag 上跑**, 于是它的前两次真实运行（v1.8.0 的 12:14 与 12:21）
   才暴露问题 —— 打包坏了要等"已经发布"才知道。
3. **安装器的行为只在文档里"已实测"**: `scripts/test_frozen.py` 验的是冻结目录
   里的 exe, 而"静默安装 → 快捷方式 → 加 PATH → 静默卸载 → PATH 还原"这套
   **安装器自身**的逻辑, CI 从没跑过。
4. `ci.yml` 用 workflow 级的 `contents: write`, 等于给每个作业（pytest / GUI /
   notebook…）都发了写仓库的令牌; pypi 作业还留着已不需要的 `id-token: write`。

### Changed

- **`ci.yml` 最小权限**: workflow 级改 `contents: read`, 只有 `release` 作业单独
  拿 `contents: write`; `pypi` 作业去掉 `id-token: write`（当前用 API token),
  并在注释里写明切回 trusted publishing 需要加回哪一行。
- **`release.yml` 支持 tag 前 dry-run**: 加 `workflow_dispatch`
  （`gh workflow run release.yml --ref main`), 并且**手动运行不会发布** ——
  "发布 GitHub Release"那一步加了 `if: startsWith(github.ref, 'refs/tags/v')`。
  实测: 手动 dry-run 里 `构建安装器: success` + `发布 GitHub Release: skipped`。
- **`docs/PACKAGING.md` 与事实对齐**: 体积改成以 CI 产物为准(setup exe
  90,032,664 B = **85.9 MiB**; 便携 zip 118,900,069 B = **113.4 MiB**;
  本机 Python 3.14 构建则是 125MB / 164MB, 差异来自构建环境),
  "首次真实 tag 运行待确认"改成已确认; "卸载后 PATH 逐字节还原"按
  `installer/nsf5stego.iss` 的真实行为收紧（只删自己加的那一项, 原值里的冗余
  分隔符会被规范化）; 风险表里"询问是否删除 `%APPDATA%/nsf5stego`"标注为
  "现状保留 + 后续计划", 因为卸载器目前**没有**这个询问。

### Added

- **安装器的静默安装/卸载冒烟**（`release.yml`, windows-latest）: 装到临时目录、
  `/TASKS=` 不选任何任务 → 断言**没有动用户 PATH** → 跑装好的
  `nsf5stego.exe --version` 与一次 embed→extract 往返（验证模型/DLL 随安装目录
  就位）→ 静默卸载 → 断言应用目录已清理。
- **发布入口在 CI 里被真的调用**（`ci.yml` 的 build 作业）: 干净 venv 里先验
  "模型随包可用", 再跑 `nsf5stego --version`、`embed`→`extract` 往返、
  `analyze --json` 的必需键 —— 1.8.0 的 headline 是正式 CLI, 而此前 CI 从没
  调用过安装后的 console script。
- `src/test_makefile_help.py`: `make help` 的完整性护栏。这条漂移**犯过两次**
  （09-17 漏 8 个 target 且列了一个不存在的 `handbook-check-`; 09-30 又漏了
  `readme-toc-check`), 现在两个方向都测: 漏列 + 列了不存在的。
- `.gitignore` 收 `.zcodeignore`（本地 IDE 的忽略规则文件, 审计时以未跟踪状态
  挂在仓库根）。

### Verification

- `python -m pytest -q`: **95 项通过 / 1 项平台相关跳过**, 覆盖率 71%（门槛 65%）。
- 两次 release dry-run: 第一次（不带安装器冒烟）成功且不发布; 第二次带安装器
  冒烟。链路的"能不能在 tag 之前验证"这件事, 现在有 CI 记录可查。
- 1.8.0 发布产物核验: PyPI wheel 与 GitHub Release wheel 字节一致
  （sha256 `02d2177a30a5…`）; Release 含 setup exe / 便携 zip / wheel / sdist;
  Zenodo 1.8.0 = `10.5281/zenodo.23062253`。
- 本机按 CHANGELOG 逐条复现 1.8.0 的 CLI 语义: 退出码 0/1/2、默认输出名
  `<原名>_stego.png`、`cat msg.txt | nsf5stego embed`（UTF-8 中文往返一致）、
  `analyze` 批量 `--json` 为数组且坏图记 `error` 后整体非零退出、通配符由 CLI
  自己展开。

## [1.8.0] - 2026-09-29

**补上项目一直缺的正式命令行入口：此前装完包只有 `nsf5stego` 弹窗一条路,
服务器、脚本与批量场景只能自己 `import ns5_core` 拼代码。**

### Added

- **`src/cli.py`：nsf5stego 命令行界面**, 四个子命令与 GUI 能力一一对应,
  参数语义（方法 / p / 口令）也一致, 课堂演示与脚本调用看到的是同一套行为：
  - `embed`：文本用 `-m/--message` 给出, 省略则从 stdin 读入（`cat msg.txt |
    nsf5stego embed cover.png`）; 默认输出 `<原名>_stego.png`, 目标已存在时在
    stderr 明示覆盖;
  - `extract`：解码成功打印文本; 口令/参数不匹配时解出的多半是替换字符或
    截断报错, 统一以非零码退出并提示"请确认 方法/p/口令 与嵌入时一致"——
    不把乱码当结果输出;
  - `analyze`：卡方 + RS + ML 判定, `--json` 输出完整机器可读负载（含
    `image_sha256` 与 ML 概率, `default=float` 兜底 numpy 标量）, 人读模式与
    GUI 结果面板字段对齐;
  - `gui`：即原先的入口行为; tkinter 缺失 / 无显示环境时给可行动提示
    （`sudo apt install python3-tk` 或改用 CLI）, `python src/gui.py` 同步受益。
- **可脚本化语义**：退出码 0 / 1 / 2 分别对应 成功 / 运行失败 / 参数错误;
  读图失败（文件不存在、格式无法识别——PIL 的 `UnidentifiedImageError` 继承
  `OSError`）转成一行提示而非栈回溯; 容量超限沿用 `ns5_core` 的容量校验文案
  （"消息过长: 需要 N 个汉明块..."）。
- **控制台安全**：输出只用 GBK 可编码字符（`test_console_encoding.py` 静态护栏
  覆盖新文件）, 启动时再对 stdout/stderr 做 `errors="replace"` 兜底——extract
  打印任意 UTF-8 解码结果时不会打崩 cp936 终端。
- **入口调整**：`[project.scripts]` 从 `gui:main` 改为 `cli:main`, `cli` 加入
  `py-modules`; 图形界面走 `nsf5stego gui` 或 `python src/gui.py`, 行为不变。
- **stdin 编码健壮**：`embed` 从管道读文本时按 UTF-8 优先、系统 locale 兜底
  （`_stdin_text`）—— Windows cp936 控制台下 `cat msg.txt | nsf5stego embed`
  里的 UTF-8 中文此前会被 locale 读成乱码并原样嵌入; 两侧都解不出时报错退出,
  宁可拒绝也不嵌乱码。
- **GUI 标题栏带版本号**：`pathutil.app_version()`（安装元数据缺失时静默省略,
  永不抛错）—— 用户截图报问题时自带版本; `cli --version` 复用同一实现。
- **`make webapp`**：一条命令本地起交互实验室（`python -m http.server 8080
  --directory webapp`）。直接双击 `index.html` 时 file:// 下 fetch 本地 JSON
  会被浏览器拦（载荷扫描拿不到数据）, README 的"互动教学网站"一节已写明。
- **安装布局的产物路径修复**：`pip install nsf5stego` 后 gui.py 位于
  site-packages, 原来的 `dirname(dirname(__file__))/output` 变成解释器根 ——
  GUI 嵌入结果、效率图、扫描曲线会写进安装目录（系统 Python 直接
  PermissionError）。新增 `pathutil.output_dir()`: 仓库布局沿用 `仓库/output`,
  安装布局自动改写**当前工作目录**的 `output/`; gui.py 四处与 efficiency.py
  的 `OUTPUT_DIR` 全部切换过去。
- **`analyze` 批量模式**：`nsf5stego analyze a.png b.png ...` 逐图一行汇总
  （隐写概率 + 判定 + ML）; `--json` 单图（唯一条目且分析成功）保持对象、
  其余一律数组（每项带 `image` 键, error 条目也是数组形态, 脚本端无需为
  错误结果单写分支）; 批量中单张坏图记 `error` 条目继续跑完, 整体非零退出
  —— 一张坏图不再拖垮整批。**通配符由 CLI 自己展开**（Windows 的 shell 不
  展开 `*.png`, README 示例因此跨平台成立; 已存在的字面路径优先, 含 `[ ]`
  的文件名不受影响）, 匹配不到报"无匹配文件"而非"无法读取图像"。
- **GUI 演示图一键生成**：`img/cover.png` 随仓库分发, 但 wheel 安装布局里
  没有 —— "载入演示图" 由死路警告改为询问后当场生成
  (`gui.generate_demo_cover()`, 与 run_e2e.py 相同的 seed=42 确定性配方,
  任何机器生成逐字节一致)。
- **Windows 打包 M1+M2+M3** (计划见 `docs/PACKAGING.md`): 新增 `nsf5stego.spec`
  (console + windowed 双 exe 共享一个 onedir) 与 `scripts/build_exe.py`
  一键构建; `pathutil.app_version/output_dir` 与 `cpplib` 增加
  PyInstaller 冻结分支 (版本号读 `version.txt`, 产物落
  `%APPDATA%/nsf5stego/output`, C++ 库找 `_MEIPASS/cpp`); CLI 嵌入前确保
  输出目录存在。实测 onedir 317MB / 便携 zip 164MB, 冻结 GUI 与 ML 推理
  与源码一致。`scripts/test_frozen.py` 对冻结产物做五项冒烟 (体积/版本/
  往返/ML 逐位一致/GUI 蓝白主题像素自检), 走 `make pkg-test`。
  **安装器**: `installer/nsf5stego.iss` (简体中文界面, 每用户免管理员安装,
  开始菜单/桌面快捷方式, 可选加入用户 PATH 且卸载时还原) 经 Inno Setup
  出 `dist/nsf5stego-setup-<版本>.exe` (125MB); exe 携带版本资源
  (Explorer 属性 + 杀软信誉), 安装→启动→卸载全流程实测, 卸载后 PATH
  逐字节还原。**CI 自动出包**: 新增 `.github/workflows/release.yml`,
  tag `v*` 推送时在 windows-latest (Python 3.12) 走 编译 C++ → 冻结打包 →
  冻结冒烟 → wheel → Inno Setup 安装器, 产物追加到同一个 GitHub Release
  (与 ci.yml 的 release 作业协同: 后者负责创建与发布说明);
  README 中英文新增"安装版 (Windows)"入口。
- **测试**：`src/test_cli.py` 十五个用例 —— 真实子进程（`--help` / 无参数 /
  `--version` / 读图错误 / `analyze --json` 单图 + 批量三态（人读行 / JSON
  数组 / 坏图容错）+ 通配符展开/无匹配四条快路径 + 嵌入解码往返 / stdin
  往返 / 口令错误 / 容量超限四条 `slow` 真实链路）+ 进程内 stdin 解码单测;
  新增 `src/test_pathutil.py`（output_dir 两种布局, 安装布局用例**补丁
  os.getcwd 而非 chdir** —— Windows 上临时目录当过进程 cwd 后 rmtree 会撞
  WinError 32, 本测试首跑即复现）; `test_gui.py` 补演示图生成的确定性断言;
  子进程固定 `PYTHONIOENCODING=utf-8`, 断言不被宿主控制台编码影响。

### Changed

- **GUI 蓝白"国企风"改版**（美观而朴素）：
  - 色板集中为模块级常量（`C_NAVY`/`C_BLUE`/`C_CARD`...）, ttk 主题与
    非 ttk 控件（横幅/画布/文本框）共用一份, 结束此前各处零散写灰;
  - 大面积白卡片 + 极浅蓝底 + 统一浅蓝边框; 深蓝只出现在"锚点"上：
    顶部深蓝横幅（应用名 + 副标题 + 版本号）、主操作按钮
    （载入 / 嵌入 / 解码 / 分析用 `Primary.TButton` 深蓝底白字）、
    标签框标题与状态栏;
  - 全局字体统一微软雅黑（此前 Tk 默认宋体与 Segoe UI 混排）, 文本框
    （待嵌内容 / 日志 / 结果输出）统一白底浅蓝边框 + 蓝色选区;
  - 矩阵编码演示与隐写分析扫描两个 Toplevel 同风格（白底 + Card.TFrame +
    浅蓝画布）; **教学语义配色不动**（绿=1、黄=命中、红框=目标列）;
  - 顺手修三处布局问题: 灵敏度提示由叠放在组合框上改为独立一行
    （雅黑字体度量下原布局必然相撞）; 窗口默认高 720 → 780（横幅 +
    高字体后左栏放不下）; 复选框禁用态在 clam 下露出非白底（补状态映射）;
  - 验证: test_gui 冒烟通过; 以 DPI 感知进程实截主窗与演示面板截图
    逐项目检（色板/横幅/按钮层级/无叠字）, 截图脚本存于会话不腐化仓库。

### Removed

- **旁白视频流水线整体下线** (应用户要求, 2026-09-30): 删除
  `teaching/gen_videos.py`、`gen_videos_v2.py`、`video_engine_v2.py`、
  `video_scenes_zh.py`、`video_decks_zh.py`、`video_optimization_report.html`
  六个脚本与 `teaching/videos/_tmp_v2/` 语音缓存 (约 255MB);
  `handbook_facts.py` 同步摘除视频讲稿扫描段 (事实口径仍由网页/DOCX/PDF
  承载, `--check` 通过); `teaching/README.md` 中英两节改为下线说明。
  已渲染的 11 章成片 (`teaching/videos/zh/`) 不入库, 本地保留可观看,
  但仓库不再能重新生成。

## [1.7.2] - 2026-09-17

**两条线：把"fork 死锁"做成一次全仓排查，以及一个由新冒烟测试当场抓到的静默 bug。**

1.7.1 查出 OOD 评估的并行路径在 Linux 上 fork 出子进程后与 LightGBM 的 OpenMP
线程池死锁（CI 的 pytest 作业因此挂满 6 小时）。这次先做**同类隐患的全仓扫描**：
`multiprocessing` / `Pool` / `DataLoader` / `joblib.Parallel` 一共只有三处进程池 ——
`experiments/ood_eval.py`（1.7.1 已修）、`src/make_dataset.py`（本次修）、
`teaching/video_engine_v2.py`（本来就是 spawn）；`gpu/train_cnn.py` 与
`experiments/run_cnn_sota.py` 的 DataLoader 默认 `num_workers=0`，不会 fork。

然后给**部署模型的生产者**补上第一条端到端冒烟测试（此前它只有"契约比对"），
而这条测试第一次跑就抓到了 `youden_threshold` 会返回 `inf` 的问题（见下）。

### Fixed

- **教学材料里的"置换加速 263 倍"没有出处，而且算错了**：中文网页版 / 英文网页版 /
  两本 DOCX / 两份入库 PDF / 旁白视频脚本（`video_scenes_zh.py` 的画面与旁白、
  `video_decks_zh.py` 的要点页）一共 7 处都写着"最高约 263 倍（4096²：12.3 s → 223 ms）"。
  两个问题：① 项目自己的 `experiments/data/bench_permute.csv` 里 4096² 是
  37.3 s → 0.56 s（66.7×），教学材料引的是另一个数；② 即便按它自己给的耗时算，
  12.3 / 0.223 ≈ **55×**，不是 263×（263 那个量级出现在小 N 处，是两种口径混算）。
  现在：
  - 用 `gen_bench.py --only permute` **重跑基准**（本次机器：4096² = 1600 万位置，
    Python 15.6 s → C++ 0.24 s ≈ 65×；同一份 CSV 小 N 处最高约 240×），CSV 随之刷新；
  - 七处文字统一改成"加速随规模变化"并**点名数据文件**（`bench_permute.csv`）与复现命令；
  - `handbook_facts.py` 把 `263` 列入 FORBIDDEN（中英 DOCX/网页/PDF + 视频脚本），
    把 `bench_permute.csv` 列入 REQUIRED —— 性能数字必须指向可复现的产物；
  - `gen_bench.py` 新增 `--only permute|embed|feat|all`（刷新那一个数字不必重跑 GPU 段）；
  - 入库 PDF 重新导出：英文 75 → **76 页**，中文仍 67 页。
- **`youden_threshold` 可能返回 `inf` —— 一个静默失效的阈值**（新增的生产者冒烟测试
  当场抓到）：`sklearn.metrics.roc_curve` 的 `thresholds[0]` 是 **inf**（表示"没有
  任何样本被判为正"），而 `argmax(J)` 在小样本/弱可分数据上经常正落在这一点 ——
  阈值于是被写成 `inf`，模型此后对任何图都不判含密（`p >= inf` 恒假），且**不报错**。
  两处实现（`experiments/train_deploy_models.py` 与 `src/train_model.py`）都加了
  `np.isfinite` 过滤；同文件的 `threshold_for_fp()` 一直有这个过滤，只有它漏了。
  - 触发证据：4 张合成照片 × 3 档的小语料上，生产者写出 `threshold_youden=inf`。
  - 影响范围：随仓库分发的两个模型没踩到（阈值 0.9493 / 0.9595 都是有限值）；
    用 `--no-save` 重跑真实校园语料，指标 CSV 与入库的那份**逐项一致**。
- **`src/make_dataset.py` 的多进程分支**（此前**从未被执行过**：CLI 冒烟只看 `--help`，
  功能测试传的是 `workers=1`）。现在显式 `mp.get_context("spawn")`，并加
  `--pool-timeout`（默认 1800 秒）—— 卡住就报错退出，不再"永远在跑"。
- `scripts/readme_toc.py` 打印路径时对跨盘符做兜底（`--file` 指向别的盘符时不再在
  最后一行 `os.path.relpath` 上崩）—— 与 1.7.1 修的 OOD `--out-dir` 同一类。

### Added

- **`src/test_deploy_producer_smoke.py`**（3 条，覆盖此前只有"契约比对"的生产者）：
  - **端到端跑通**：自造 143 维小语料（4 张合成照片 × 3 档 = 12 行，走
    `nsF5 嵌入 → featurize_v2 → CSV`）→ `train_deploy_models.py --models 143d
    --no-splits --no-save --out-csv <tmp>`，断言指标 CSV 的列、语料计数、
    `n_train+n_val`、AUC/阈值范围与 `model_file`；
  - **孤儿 photo_id 必须被拒**（源图泄漏护栏走 CLI，而不只是单元层）；
  - **`youden_threshold` 在退化输入下仍是有限值**（两处实现都测）。
  测试**不断言具体 AUC**（12 行合成数据没有意义），只断言结构与护栏。
- `train_deploy_models.py` 新增 `--out-csv`（试跑/冒烟测试不再覆盖权威表用的那一份）。
- `experiments/tools/gen_bench.py` 新增 `--only permute|embed|feat|all`（默认 all）。
- `src/test_experiment_smoke.py` 两条慢测试（`make_dataset` 的并行分支）：
  **`workers=2` 与 `workers=1` 逐行一致**（走 CLI 子进程，实测 35 样本逐行相同）、
  **超时断路器**（`--pool-timeout 0.001` 必须以非零码退出）。
- 真实语料抽查（一次性，不进 CI）：`DS_LIMIT=8 python src/make_dataset.py data/campus_jpg
  512x512 --out _parcheck --workers 4` → `photo=8 clean=8 stego=48 合计=56 耗时 2s (4 进程)`。

## [1.7.1] - 2026-09-17

**两件事：教学材料里一处悬空引用（`yccstego`），以及一次把 CI 挂满 6 小时的事故。**

先说事故：1.7.1 把新写的 OOD 冒烟测试并入 CI 之后，`pytest` 作业**挂了 6 小时**才被
GitHub 取消（前一版只要 1 分 44 秒）。根因是新测试在 pytest 进程里起
`multiprocessing.Pool`，Linux 默认 fork，而该进程已经初始化过 LightGBM 的 OpenMP
线程池 —— 子进程再进 LightGBM 就死锁。修法、断路器与 CI 超时见下面的 Fixed 一节；
这条事故本身也值得留在案上：**"测试跑得通"与"测试在 CI 上跑得通"是两件事**。

中英文手册的 ch03 / ch11 / 附录 F 都把 `yccstego` 说成"项目 `yccstego` 扩展"、"
the project's `yccstego` extension"，但 `yccstego` 是**独立仓库与 PyPI 包**
（`pip install yccstego`，当前 0.1.4，另有自己的 GitHub 仓库），本仓库里既没有它的
代码（`yccstego/` 被 `.gitignore` 排除），也没有任何链接。读者按手册去 clone，什么也
找不到 —— 与之前那条指向已删除 `thesis/` 的图注是同一类错误：教学材料把读者指向了
不存在的东西。

### Fixed

- 手册中英各 5 处（DOCX 4 + 网页 5，按文本出现次数；DOCX 与网页是两套源）改为
  "姊妹项目 yccstego"，并给出 <https://github.com/Yukinoshita-lin/yccstego>；表格里
  的"本项目即可扩展"改成"姊妹项目（独立仓库与 PyPI 包）"。
- README 的"学习手册"一节新增**姊妹项目**一行（含 `pip install yccstego` 与仓库地址），
  读者不必先翻到手册附录才知道它在哪里。
- 入库 PDF 按修正后的 DOCX 重新导出：英文 74 → **75 页**（新增的地址使正文多了一页），
  中文仍 67 页；`docs/README.md`、`README.md`、`teaching/README.md` 的页数声明同步更新。

### Added

- **README 的目录（生成 + 守卫）**：README 已有 14 个二级小节、60 KB 以上却没有目录，
  想找"目录结构"或"更正记录"只能一路滚；而**手写目录会立刻腐烂**（这几天已经因为
  "指向不存在的东西"修过 `thesis/`、`yccstego` 与手册图注三处）。现在目录由
  `scripts/readme_toc.py` 从二级标题生成（`make readme-toc`），`src/test_readme_toc.py`
  把"标题改了目录没改""锚点找不到标题""二级标题漏收录""把代码里的 `# 注释` 当标题"
  四类问题钉进 `pytest`。
- `teaching/handbook_facts.py` 的 `REQUIRED` 增加
  `github.com/Yukinoshita-lin/yccstego`：DOCX、网页、入库 PDF 三份材料都必须能给出
  这个地址，谁把正文改回"项目扩展"都会在 CI 红。
- **`src/test_ood_smoke.py`**（6 条）：OOD 误报率评估在 CI 里此前**从未被执行过**
  （它要 1514 张外部照片），而它产出的正是 README 的头条数字。现在用自造的合成照片
  在 CI 里跑通这条链，并钉住三类不变量：
  - **口径**：判据必须等于模型 payload 里的部署阈值，`pred_stego` 必须由
    `prob >= threshold` 得来，概率落在 [0,1]；
  - **并行不改数**：`--workers 2` 与 `--workers 1` 的逐图概率**逐位相同**
    （并行是 1.6.9 之后 20 分钟 → 1.7 分钟的默认路径，此前没有任何测试碰过它）；
  - **统计自洽**：`fp_rate = 误报数/张数`、Wilson CI 覆盖点估计且随 n 变窄、
    按来源分组的行加起来等于 `ALL` 行、缺语料时必须打印原因而不是静默少行。
  合成语料不代替真实照片，所以测试**不断言具体误报率**。
- `Makefile` 的 `help` 补上此前漏掉的 `core/steg/fp/pipeline/pyfeatures/cpp-clean/gui/
  exp-data/handbook-check`，并修掉一个笔误（`make handbook-check-` —— 那个 target
  并不存在，`make help` 却把它列了出来）。
- `experiments/ood_eval.py` 新增 `--out-dir`（试跑不再覆盖权威表用的那两份 CSV）
  与 `--chunk-timeout`（并行分片的等待上限）。
- **备用 PDF 路径（xelatex）不再缺字形**：`teaching/build_handbook_pdf.py` 用
  `Microsoft YaHei` 作 CJK 主字体，而正文里的 `① ᵖ ₄ ′ ↔ ■ ● ✔ ᵖ` 等 22 个符号在
  该字体里没有字形 —— xelatex 只在日志里写一行 `Missing character`，**退出码仍是 0**，
  于是两份 PDF 各有 80 余处会渲染成空白。现在逐个 `\newunicodechar` 映射到等价排版
  （上/下标、圈号、箭头、几何符号），实测两份 PDF 的日志里 `Missing character` 归零；
  脚本还会统计缺字并在缺字形时**返回非零**（交付物坏了不该只是一个警告）。
  同时新增 `--out` 参数：可以在 `_pdf_build/out/` 里验证这条路径而不覆盖入库 PDF
  （入库 PDF 仍走 Word 那条线）。`handbook_facts.py --check` 会校验这 22 个映射没被删。

### Verification

- `python teaching/handbook_facts.py --check` → 通过（中英 DOCX + 网页 + PDF 六处）。
- `python -m pytest -q` → **63 项通过**（新增 7 条 OOD 冒烟/断路器 + 6 条 README 目录守卫），
  覆盖率 69.3% ≥ 门槛 65%。
- `python teaching/run_notebooks.py` → 10/10 通过。
- 两份 PDF 的文本里各含 3 处 yccstego 仓库地址，页数 67 / 75。

## [1.7.0] - 2026-09-15

**模型治理：给两个部署模型补上模型卡。**

`models/stego_classifier.joblib`（143d）与 `models/stego_classifier_v2_jpeg_lgb_51d.joblib`
（53d）随仓库分发，但一直是**裸二进制**：语料/协议/指标只存在于 README 的散文里，
payload 虽写了 provenance 却要先装齐 lightgbm + scikit-learn 再反序列化才能读到，
而且没有任何机制阻止"模型换了、文档没换"。一个想引用这两个模型的人拿到手的，
就是两个 2.8 MB 的不明文件。

### Added

- **入库的 JSON 模型卡** `models/<模型名>.card.json`
  （`experiments/model_card.py` 生成）：
  - 语料与协议：414 张校园照片 x 14（12 档嵌入 + 2 干净）= 5796 样本，
    按**源图** holdout（test_size=0.25, seed=0）与 seed 0..7 的 8-split 均值；
  - 指标：held-out AUC、8-split 均值 ± 标准差、验证集干净误报、逐档检出率
    （弱档 nsF5 p3 d=0.25 单列）、OOD 真实干净照片误报率（ALL / campus /
    ALASKA#2 / DIV2K，含 Wilson 95% CI 与中位概率）；
  - **特征列表与顺序**（143 / 53 列，逐位列全）、超参、训练环境、git 版本、训练时间；
  - 适用场景、不适用场景、已知局限、跨语料（BOSSbase）参考值；
  - 该 `.joblib` 的 `sha256` 与字节数。
- **契约测试** `src/test_model_cards.py`（10 条）：sha256 硬绑定、payload 逐字段
  一致（含特征顺序）、provenance 一致、特征分组求和 = 维数、边界与局限非空、
  卡片 JSON 结构、`ml_predict` 的安装布局查找、wheel 必须打进这两个模型。
  有指标 CSV 时额外与 `experiments/data/*.csv` 交叉核对；
  CSV 不在库（CI）时明确打印 `[skip]`，不把"没数据"当成"通过"。
- `models/README.md`：模型卡入口，校验/重训/引用注意事项。
- Makefile：`make model-cards`、`make model-cards-check`。

### Changed

- `experiments/train_deploy_models.py` 在保存模型后**自动刷新模型卡** —— 卡片含
  sha256，所以"重训了模型但忘了更新卡"由生产者自己消灭，而不是留给 CI 报红。
- README 的"双版本部署策略"与 CI 小节补上模型卡入口与校验方式。

### Fixed

- **CI 的 pytest 作业挂满 6 小时**（这个 bug 是新加的 OOD 冒烟测试自己揭出来的）：
  1.7.1 把 `src/test_ood_smoke.py` 加进 CI 之后，pytest 作业从 **1 分 44 秒**
  （v1.7.0 tag 的实测）变成 **14:04 起跑、20:06 被取消**，日志里除了
  `##[error]The operation was canceled.` 和 5 个 `python` 孤儿进程之外什么都没有。
  根因：`experiments/ood_eval.py` 用 `multiprocessing.Pool`，在 Linux 上默认是
  **fork**；pytest 进程此前已经加载过 LightGBM（OpenMP 线程池已初始化），
  fork 出来的子进程再进 LightGBM 就死锁 —— Windows 本地是 spawn，所以一直没暴露。
  三处修复：
  - `ood_eval.py` 显式 `mp.get_context("spawn")`（与平台无关）；
  - 每个分片有 `--chunk-timeout`（默认 600 秒），卡住就 **报错退出**，不再无限等；
  - 冒烟测试改成**跑真的 CLI 子进程**（干净进程 + spawn），既避开 fork，
    又顺带覆盖了此前零测试的 CLI 参数解析与 CSV 落盘。
  另加两道防线：CI 的 `pytest`/`notebooks`/`handbook`/`build` 作业都设了
  `timeout-minutes` —— 任何"永远在跑"必须是 15–25 分钟内的失败，而不是 6 小时。
- **`--out-dir` 指到别的盘符会崩**：`ood_eval.py` 用 `os.path.relpath(OUT_RAW, PROJ)`
  打印产物路径，Windows 上输出目录与仓库不同盘符时会抛
  `ValueError: path is on mount 'C:', start on mount 'F:'` —— 而且是在**跑完全部评估
  之后**才抛（`src/pathutil.py` 的文件头正是为这个坑写的，只是这里没接上）。
  现在改用 `rel_from_proj()`（跨盘符时退回绝对路径，永不抛错）。
- **模型卡里的 OOD 协议串落后了一版**：卡片生成于 1.7.0，写的是
  `clean real photos, 512x512 LANCZOS, ...`，而 1.6.9 之后的产物 CSV 已经是
  `... grayscale -> 512x512 LANCZOS ...`（数字完全相同，只是口径描述）。这条漂移是被
  `src/test_model_cards.py` 在**有指标 CSV 的本地**抓到的（CI 上那部分明确 skip）——
  正是这个测试存在的意义。已重新生成两张卡。
- `ood_eval.py` 现在**排序后再落盘**（按 模型/配置/来源/文件名）：并行返回分片的顺序
  取决于进程调度，不排序的话同一份语料每次跑出来的 CSV 行序都不同，既无法用哈希断言
  "重跑一致"，diff 也全是噪声。实测 150 张真实照片上用 `--workers 1` 与 `--workers 4`
  跑出的逐图 CSV 与汇总 CSV **字节完全相同**。

- **手册里指向已删除论文稿的图注**：中文 ch09 图 9-2 写"（log–log 坐标，**论文图**）"、
  英文 ch09 写 "(log-log axes, **thesis figure**)" —— `thesis/` 与全部论文稿在
  2026-09-14 已删除。更糟的是这条**同时存在于入库的两份 PDF 里**，而 CI 的事实校验
  没抓到：`FORBIDDEN` 里写的是 `"（论文图"` / `"(thesis figure"`（左括号紧贴图字），
  而实际文本是 `"（log–log 坐标，论文图）"` / `"(log-log axes, thesis figure)"`，
  子串匹配被绕过。现在改成 `"论文图"` / `"thesis figure"` 匹配（并顺带禁掉英文的
  `"project thesis"`；不能用裸 `"thesis"`，那会命中 `"hypothesis"`），
  DOCX + 网页 + 入库 PDF 的 6 处全部修正并重新导出（中文 67 页 / 英文 74 页不变）。
- **入库 PDF 的导出步骤此前没有脚本**：两份 `docs/*.pdf` 是"用 Word 从 DOCX 另存为
  PDF"得到的，但这个步骤只存在于某次提交信息里。新增
  `teaching/export_handbook_pdf_word.py` 把它固定下来（`make handbook-pdf`），
  Word 不可用时明确跳过并返回 0。
- **`teaching/README.md` 描述与实际文件不符**：原文写"Markdown 是唯一内容源，
  `build_handbook_pdf.py` 编译出 `docs/` 下的 PDF，所以 PDF 与网页会同步"。
  实际入库的 PDF 来自 DOCX（67 / 74 页），而用同一份 Markdown 编译得到的是
  100 / 112 页（网页版内容更丰富）。现在用一张表写清三份交付物各自的源与同步方式。

- **wheel 里没有模型文件**：两个部署模型只存在于仓库的 `models/` 目录,
  `pyproject.toml` 没有把它们打进包, 而 `src/ml_predict.py` 又只按
  `<repo>/models/` 找路径。实测在安装布局下 (解包 wheel 到临时目录再导入
  `ml_predict`) 行到 `available=False` / `FileNotFoundError` ——
  `pip install nsf5stego` 之后, 依赖里装着 lightgbm、README 也写着有 ML 判定,
  但 ML 判定**恒不可用**, 且只提示"模型未加载"。修法:
  - `models/` 作为 `nsf5_models` 包打进 wheel (`package-dir` 映射, 不复制文件;
    `package-data` 逐个列出四个文件, 不用 `*.joblib` 通配, 免得把本地未入库的
    训练产物一起发出去);
  - `ml_predict` 按"仓库布局 -> 安装布局"查找, 并新增
    `_model_candidates()` / `_resolve_model()` 供测试断言。
- CI 的 `build` 作业增加一步**干净 venv + 安装布局**的验证 (模型在包里、路径解析
  走安装布局、模型能真的打出一个概率) —— 合约测试只能检查 `pyproject` 的声明,
  这一步才是"装了真的能用"。
- README 的 wheel 小节原写着"模型不打进 wheel, 请自行取 `models/` 目录", 现改为
  实际情况; "更正记录"新增第 13 条。

### Notes

- 模型卡如实写下边界，而不是只报喜：143d 在 1514 张公开真实干净照片上误报
  **9.58%**（53d **28.86%**；DIV2K 的 100 张是 51% / 47%），因此两者都只适合
  单图辅助判读与批量排序，不适合单独定案。对外引用用 BOSSbase 口径
  （0.8062 / 0.7172），不要用校园语料的 0.8939 / 0.8391。
- 校验命令：`python experiments/model_card.py --check`（CI 里由 `pytest` 执行）。

## [1.6.9] - 2026-09-15

**性能 + 一处训练/推理偏差。** 这版把最贵的一步实验从 20 分钟压到 1.7 分钟，
并修掉一个只在彩色输入下才暴露的口径问题。

### Performance

- **SRM 残差向量化**（`src/srm_filter.py`）：原来 30 个 5×5 核各自做 25 次切片累加
  （512² 约 72 ms），现在把图像一次变成滑动窗口视图、与 (30,5,5) 核张量做一次收缩
  （约 19 ms，**3.9×**）。两种写法都是"零填充 + 互相关"，与 `torch.nn.functional.conv2d`
  同口径，差别只是 float32 求和顺序（实测 max|Δ| = 5.5e-05）。慢速参考实现保留为
  `srm_residuals_np_reference()` 供测试逐位对照。
- `featurize_v2._srm_stats` 少算一遍 `abs(rc)`（同一份 26 MB 数组上的两次逐元素 pass
  合成一次，数值完全不变）。整条 `featurize_v2` 从 ~139 ms 降到 ~103 ms。
- **特征只算一次**（`MLPredictor.predict_from_v2`）：53 维是 143 维的子集，以前同一张图
  要为两个模型各跑一遍 `featurize_v2`。现在算一次 143 维、由 `predict_from_v2()` 选列
  打分，打分路径与 `predict()` 共用（新增逐位相等的契约测试）。
- **OOD 评估并行**（`experiments/ood_eval.py --workers N`，默认 min(8, CPU)）：
  1514 张 × 2 模型 × 2 配置从 **约 20 分钟 → 1.7 分钟**，误报数与中位概率逐位不变。

### Fixed

- **彩色图像的训练/推理偏差**：`MLPredictor.preprocess` 原来对 3 通道输入取
  `img[..., 0]`（RGB 时即红通道），而语料是 `make_dataset.py` 用 `.convert("L")`
  （亮度）建的。实测 30 张真实照片上平均概率差 **0.24**、最大 **0.97**；用部署口径
  重跑 OOD 会把 143d 误报率从 9.58% 抬到 **29.71%**、53d 从 28.86% 抬到 36.00%。
  现在 `preprocess` 统一走亮度转换 —— 灰度输入逐位不变（GUI 与既有用法不受影响），
  彩色输入与训练口径一致。修正后 OOD 评估**逐位复现**此前公布的数字
  （143d 9.58% / 53d 28.86%，中位概率 0.025021 / 0.527863 也一致）。
- OOD 评估的协议串补上"grayscale"，`docs/RESULTS.md` 里的口径描述随之更新。

### Verification

- `pytest` **40 项通过**（新增 2 条：预处理=训练口径、predict_from_v2=predict 逐位相等），
  覆盖率 **69.2%** ≥ 门槛 65%。
- OOD 评估重跑（亮度口径 + 8 进程）：误报数 145/1514 与 437/1514，与修正前公布值一致。

## [1.6.8] - 2026-09-14

**覆盖率门槛的第三个坑：测的是"有没有屏幕"。** v1.6.7 的 tag CI 仍然红在 pytest
作业上，日志给出的数字是 **51.3%**（本地模拟是 66%，Windows 是 69%）。

### Fixed

- **pytest 作业在无显示环境下跳过 GUI 冒烟测试**，而 `gui.py` 有 670 行，
  覆盖率因此从 ~69% 掉到 ~51% —— 65% 门槛实际在惩罚"这台机器没有屏幕"，而不是
  代码质量。现在该作业也安装 xvfb 并用 `xvfb-run -a` 跑，使覆盖率与有显示的环境
  可比。这也和第 1 条教训同源：**门槛必须有稳定的测量口径**，否则它会时红时绿。

### Verification

- 本地（Windows，38 项全跑）覆盖率 **68.8%**；模拟"无 C++ 库 + 无 torch + 无 xgboost"
  为 **66.1%**；本次修复后 CI 的 pytest 作业会以 `xvfb-run` 执行，测量口径与前者一致。

## [1.6.7] - 2026-09-14

**v1.6.6 上线后 CI 报红的两处修复**（tag 已归档到 Zenodo，因此按补丁版本向前修，
不回改已发布的 tag）。

### Fixed

- **`train_model.py` 硬依赖 xgboost**：CI 的 pytest 作业没有安装它（虽然
  `pyproject.toml` 里声明了），于是新增的"实验链冒烟"在 Linux 上直接
  `ModuleNotFoundError` 退出，覆盖率随之掉到 44%，撞破 65% 门槛。现在 xgboost
  缺失时**只跳过 XGB 候选并打印提示**（少一个候选，不该让整条训练崩掉），
  同时 CI 的"完整依赖"作业把 xgboost 装上。
- **手册里两段示例依赖 `output/` 目录**：ch02 的 `save_image(..., "output/my_copy.png")`
  与 ch03 的 `output/lab3_stego.png` 在**全新 clone** 上会 `FileNotFoundError`
  （该目录是 gitignore 的运行时产物，作者本机有、CI 没有）。两语言各加一行
  `os.makedirs("output", exist_ok=True)` —— 学员照抄也能跑。

### Verification

- 在"无 C++ 库 + 无 torch + 无 xgboost"的模拟 Linux 环境下：`pytest` 38 项通过，
  覆盖率 **66.1%** ≥ 门槛 65%；手册片段 46 个（21 执行 / 13 条期望输出断言）全过。
- 顺带确认：v1.6.6 的 `pypi` 作业按设计被跳过（仓库变量未设），发布步骤不会误触发。

## [1.6.6] - 2026-09-14

**发布链路 + 仓库治理 + 质量保障。** 这一版不加新功能，只补"项目能不能被正确
引用、能不能被可靠维护"这几件事。

### Added

- `.gitattributes`：仓库统一 LF（此前每次 diff 都刷 "LF will be replaced by
  CRLF" 警告）；PDF/DOCX/joblib/npz/png 等显式标为二进制；钩子与脚本强制 LF。
- `CITATION.cff` + `.zenodo.json`：GitHub 的 "Cite this repository" 与 Zenodo
  归档元数据（此前两者都没有，而姊妹项目有）。
- `CONTRIBUTING.md`、`SECURITY.md`、`.github/pull_request_template.md`：贡献入口、
  漏洞报告渠道（含"算法可检测性不是漏洞"这类边界说明）、PR 自检清单。
- `src/test_experiment_smoke.py`：**实验链冒烟** —— 造 12 张合成图 →
  `make_dataset` → `train_model` → `run_e2e`。覆盖率一测就发现这三条用户入口
  是 **0%**，也就是"按 README 跑一遍"从来没被 CI 验证过。
- `webapp/tests/a11y.mjs` + CI 步骤：用 axe-core 做无障碍审计（只对
  serious/critical 判失败，例外需写明理由）。
- `teaching/verify_handbook_experiments.py`：**执行手册里的 python 片段**并断言
  期望输出（此前只校验数字与结论，不校验"照着抄能不能跑"）。
- `src/pathutil.py`：跨盘符的路径显示工具（见下面的 Fixed）。
- CI：pytest 作业现在跑覆盖率并要求 ≥65%；新增 PyPI 发布作业
  （trusted publishing，默认由仓库变量 `PUBLISH_TO_PYPI` 控制，避免未配置时误红）。

### Fixed

- **手册里 3 段示例代码其实是坏的**（两语言各一份）：ch06 用错误口令去解码、
  以及从被篡改的图里解码，都会直接抛 `ValueError` —— 现在改成显式捕获并打印
  "解码失败"，既是能跑的示例，也更清楚地把"键控 + 篡改感知"讲明白。
- 手册里把**命令写进了 ```python 围栏**（`python src\make_dataset.py` 之类）：
  已改为 ```bash，并把 Windows 专用的反斜杠路径改成跨平台的 `src/xxx.py`。
- **跨盘符路径会让脚本崩**：`train_model.py` 等处于 `os.path.relpath(model_path,
  PROJ)` —— 当 `OUT_MODEL` 指向另一个盘符（CI 上的 `/tmp` 就是这种情况）时抛
  `ValueError: path is on mount ...`，训练都跑完了却在写指标时崩溃。统一改用
  `pathutil.rel_from_proj()`（这类写法共修了 4 个文件 9 处）。
- **网站无障碍缺陷 5 处**：4 个表单控件缺 `label for`（汉明 p/m、湿纸 m、阈值滑块）、
  1 个下拉框无可访问名称、3 处 `.range-note` 对比度只有 4.2:1（低于 WCAG AA 4.5:1）。
  修复后 axe 在两个视口上均为 **0 违规**。
- `NOTICE`：版权署名仍是旧的占位邮箱 `dev@example.com`；并且声明"`yccstego/` 随本
  仓库分发"—— 实际上它是独立发布在 PyPI 的姊妹项目、并不在本仓库里。两处都改对了。
- 覆盖率的两个连带问题：`train_model.py` 的指标路径现在可用 `METRICS_CSV` /
  `DETECTION_CSV` 覆盖（冒烟测试不再往权威表里写测试行）。

### Changed

- README 的 DOI 徽章从"某个版本 DOI"改为 **concept DOI**
  （10.5281/zenodo.22543628）—— 它始终解析到最新归档版本，不会再指向审计前的旧快照。

### 待你完成的一步

- PyPI 上的 `nsf5stego` 仍是 **1.4.0**（依赖里没有 `lightgbm`，主页还指向旧 owner）。
  发布作业已经写好，但需要你在 PyPI 配置一次 trusted publisher（见 `ci.yml` 里
  `pypi` 作业的注释），然后在仓库设 `PUBLISH_TO_PYPI=true` 才会真正上传。

## [1.6.5] - 2026-09-14

**把"教学面"补全：视频旁白脚本、教学图、以及散落各处的措辞。**

上一版修了手册的 DOCX / 网页 / PDF 三处，但教学材料还有第五处 —— **旁白视频**
（`teaching/video_scenes_zh.py` 与 `video_decks_zh.py`）。排查后确认它们同样带着
被推翻的结论，这一版一起修掉并把护栏扩到视频脚本。

### Fixed

- `video_scenes_zh.py` / `video_decks_zh.py`：
  - **"53d 可解释版 AUC 更高"** —— 错。现改为"143d 更准（8-split 0.898）做默认，
    53d 每一维都能解释（0.846），代价是 AUC 低约 0.05"；
  - **"143 维 + 12 档：AUC 推到 0.81 / OOF ≈ 0.814"** —— v1 时期数字，已删；
  - **"SRM 预处理：同源 +0.03、跨源反亏"** —— v1 口径，加上"未在当前版本复现"的限定；
  - "四个分类器 AUC 几乎重叠" 补上范围限定（**11 维**语料上成立：LR/RF/GB/XGB =
    0.701/0.702/0.714/0.720，极差 0.02；143 维上是 LR 0.924 / XGB 0.900 /
    LGB 0.901 / RF 0.866）。
- `teaching/web/{zh,en}/content/ch08.md`：8.8.1 节标题与代码注释里的
  "AUC 更高"、v1 时期 SRM 口径的表述；`appF.md` 的同一处。
- `README.md`：`MLPredictor` 示例注释 "53d 可解释版（AUC 更高）" → "AUC 略低，
  但每一维都能解释"。
- 教学图按修正后的 11 维语料重画（`teaching/gen_ml_figures.py`，含四分类器 ROC）。
- **本地视频重渲**：第 8 章 `ch08.mp4` 重新生成（4:06，14 段；变化的旁白重新
  TTS，未变的分段复用缓存），`durations.json` / `index.html` / 质检图同步更新。

### Added

- `teaching/handbook_facts.py` 的校验范围扩到**视频脚本文稿**：禁止
  "AUC 更高""推到 0.81""OOF ≈ 0.814" 等陈旧说法，要求出现"未在当前版本复现"
  与现口径数字。CI 的手册 job 一并覆盖（注入测试验证过它能抓到）。

## [1.6.4] - 2026-09-14

**对教学材料负责：手册改正 + 教学 notebook 进 CI。**

### Fixed

- **两本学习手册带着已被推翻的结论**（DOCX 源稿、网页版、PDF 三处都有）：
  `8-split 平均 AUC 0.9085 / 0.9227`、"53d AUC 更高"、"SRM 90 维接近随机、去掉
  反而更好"、"OOD 1/8 / 3/8"、以及大量指向已删除 `thesis/` 的引用。
  现全部改为修正后的口径：**0.8980 / 0.8461（143d 更准）**、**SRM 占 gain
  52.6%、去掉它 OOF AUC 掉 0.05**、**1514 张真实干净照片上 OOD 误报 9.58% /
  28.86%**，引用统一指向 `docs/RESULTS.md`。
- `notebooks/03_lsb_steganalysis.ipynb` 让学员嵌入 5000 字符，而 `img/cover.png`
  在 p=3 下的容量只有 3494 字节 —— 该 cell 一直抛 `ValueError`。这正是"教学
  notebook 从未被执行过"的直接后果。现在改为按容量计算（留 10% 余量），并顺手
  教学化：先算出容量、再演示"超容量会得到清晰的报错"。

### Added

- `teaching/handbook_facts.py` —— 手册事实的**单一来源 + 修正器/校验器**。
  `--check`（CI 用）要求"陈旧结论必须消失、现口径必须出现"；`--fix --web` 按表
  修正 DOCX 与网页 markdown。修正表覆盖中英两册共 60 余处。
- `teaching/run_notebooks.py` —— 用 nbclient 在仓库根逐本执行 10 本 notebook
  （`MPLBACKEND=Agg`、不写回文件），失败时打印出错 cell。
- CI 新增两个 job：`notebooks`（生成器一致性 + 逐本执行）与 `handbook`
  （事实校验）。Makefile 新增 `handbook-check` / `handbook-fix` / `notebooks-run`。

### Changed

- **手册 PDF 重新生成**：中文 66 → **67 页**，英文 72 → **74 页**（用 Word COM
  从修正后的 DOCX 导出；`docs/README.md` 与主 README 的页数声明同步更新）。
- **发现并记录一个维护陷阱**：入库的网页版 `teaching/web/*/content/*.md`
  比 `docs/src/*.docx` **内容丰富得多**（ch07 190 行 vs DOCX 可生成的 78 行），
  因此 `make web-convert` 会静默删掉网页版增量。已在 `teaching/web/README.md`
  写明：网页手册的事实修正走 `handbook_facts.py` 的 `WEB` 表，不要重新生成。

### Verification

- `python teaching/handbook_facts.py --check` → 通过（DOCX 中英 + 网页中英四处）。
- `python teaching/run_notebooks.py` → 10/10 通过（共约 45 秒）。
- 新 PDF 文本抽查：含 0.8980 / 0.8461 / 0.8939 / 0.8391 / 9.58 / 28.86 / 52.6 /
  `docs/RESULTS.md`，不含 0.9085、`thesis/thesis1.pdf`、"1/8"。
- CPU 合并训练（2898+70000=72898 样本）重跑 → RF **0.7417**，与手册里"≈0.741"一致
  （现可追到 `experiments/data/train_model_metrics.csv`）。

## [1.6.3] - 2026-09-14

**把"不可溯源"清零。** 1.6.2 的审计在 `docs/RESULTS.md` 第 7 节留下 9 行
`traceable=no` 的数字（GPU 管线、train_model 家族、OOD 误报）。这一版给每一行
补上生产者并重跑，结果：**74 行、0 行不可溯源**。

### Added

- `experiments/ood_eval.py` —— OOD 真实干净照片误报率的生产者（此前生产者与
  `data/ood_jpeg_test/` 一起丢失，只剩"1/8、3/8"这种 n=8 的数字）。
  语料扩到 **1514 张**：校园 414 + DIV2K 100 + ALASKA#2 1000，全部无嵌入，
  判据与部署一致，输出逐图 + 汇总（Wilson 95% CI）。
  实测：**143d 9.58%** [8.20, 11.16]、**53d 28.86%** [26.64, 31.20]；
  DIV2K（2K PNG）是主要失分来源（51% / 47%），真实相机 JPEG 上 143d 仅 6.6~6.8%。
- `experiments/gain_importance.py` —— 特征重要性的生产者（此前两个
  `gain_importance*.csv` 全仓无写者）。按当前口径重算：**SRM 90 维占 gain 52.6%**
  （旧错误尺度下是 26.6%），BASE 11 占 20.7%、LSB PREFIX 20 占 20.6%。
- `gpu/train_ml_gpu.py` 现在把每次运行的指标与逐档检出落盘
  （`gpu_pipeline_metrics.csv` / `gpu_pipeline_detection.csv`）。
- `src/train_model.py` 现在把指标、逐候选 held-out AUC、XGB 超参落盘
  （`train_model_metrics.csv` / `train_model_detection.csv`），并支持
  `XGB_DEPTH / XGB_N_EST / XGB_LR` 环境变量覆盖 —— README 里那行
  "v2 XGB tuned (depth=5, n_est=500)" 因此第一次可以从脚本复现。
- `Makefile`: `make ood`、`make gain-importance`。
- `.gitignore`: `data/external/`（DIV2K / ALASKA#2 等外部语料，本地挂载，不入库）。

### Changed

- **分支 `chore/hardening-2026-09` 已删除**（本地 + 远端）。删除前先把它的 17 个
  提交**快进合并进 main 并推送**（`origin/main`: 45c863f → 41eabfe），
  确保工作不丢：本地 `git branch -d`（已合并）＋远端 `git push --delete`。
- v1 语料 `data/dataset.csv` 按**修正后的 C++ 特征口径**重新生成
  （旧文件的 `chi2_pvalue` / `median_prefix_p` 是在自由度少减 1 的口径下算的，
  与修复后的推理路径不一致）。
- README 相应段落改为引用新产物：OOD 从"1/8 / 3/8"换成 1514 张的比率与 CI；
  GPU 管线两个数字标注"已复现"并写明口径（`--srm off`）；合并配置注明
  旧值基于 50000 样本的 BOSSbase 图像集（现仓库只有 10000 样本，故改跑 13410 样本）。

### Fixed

- `src/train_model.py`: 环境变量为**空字符串**时 `float("")` 直接崩溃
  （`WEAK_WEIGHT=` / `$env:WEAK_WEIGHT=''` 都会踩到）。
- `src/make_dataset.py`: 多进程分支的"跳过表头"判断永远匹配不上，
  导致打印的样本数恒比真实值多 1（实测 2899 vs 2898）。
- `gpu/train_ml_gpu.py --datas a,b` 被当成单个名字（`nargs="*"`），
  报错信息也误导；现在文档与用法都按空格分隔。

### Verification

- **逐位复现**：GPU 管线校园 **0.7903**（阈值 0.7130 / acc 0.8024，README 旧值
  0.790 / 0.713 / 0.802）、BOSSbase **0.6438**（0.7983 / 0.6550，旧值 0.644 / 0.798 /
  0.655）、v2 XGB tuned **0.8889**（旧值 0.8889）。
- 合并配置：3410 + 10000 = 13410 样本 → **0.6672**（旧 0.712 基于 50000 样本的
  BOSSbase，语料不同源，已注明）。
- v1（11 维 6 档）重跑 → XGB **0.7371**（旧 0.7435，差异来自修正后的 p 值列）。

### New finding (待查)

- 在修正后的语料上，**标准化 + 校准的 LR 往往是最强单模型**
  （campus v2_jpeg: LR 0.9055 > XGB 0.8889 > STACK 0.8672），
  与旧口径下"XGB/LGB 更强"的印象相反；下一轮实验应单独查清。
- `clip_outliers`（5σ）在 OOD 评估里**没有改变任何一条判定**（16 个格子误报数全同），
  不应再作为 OOD 防护宣传。

## [1.6.2] - 2026-09-14

审计发现**两个报告数字的缺陷**（算法实现本身没错，错的是"用什么数据、什么口径
得到这个数字"）。两者都影响此前对外公布的指标，因此全部重跑、重报。

### Fixed

- **源图泄漏（严重）**：`data/dataset_campus_v2_jpeg.csv` 的 414 个 `clean_jpeg`
  行被赋了独立 photo_id（1413..1826），而它们的特征与对应 `clean` 行逐位相同
  （max|Δ| = 7e-9，是副本而非 JPEG 重编码）。后果是按源图 holdout 被绕过 ——
  同一张源图的含密变体可进训练集、副本进验证集，正是
  `experiments/README.md` 评测纪律第 1 条禁止的情形。
  单独修正分组后的实测：143d held-out AUC 0.8946 → **0.7555**、
  53d 0.9100 → **0.7503**；弱档 nsF5 p3 d=0.25 检出 85.3% → **44.2%**、
  87.2% → **29.8%**。
- **SRM 特征尺度（严重）**：`gpu/featurize_v2_gpu.py` 在高通卷积前把像素 `/255`，
  残差整体缩小 255 倍、`clamp(±4)` 形同虚设，于是 GPU 产出的
  `srm_mu/absmean/std` 与 CPU 参考实现相差约 30 倍。语料是用 GPU 特征建的，
  而 `ml_predict` 单图判定走 CPU 特征 —— 143d 模型一直吃着分布外输入
  （53d 不含 SRM，不受影响）。该错误尺度还污染了"SRM 90 维近随机、去掉反而
  更好"的整个结论链。修复后 BOSSbase 上 LGB-143d 从 0.7529 升到 **0.8062**。
- **C++ 与 Python 的 11 维特征不一致（严重，且被自检掩盖）**：`cpp/fsfeatures.cpp`
  有两处与 Python 参考实现不同 —— 卡方自由度直接用了非空灰度对数 `n`（参考实现用
  `n-1`，同一张图 p 值差 26%）、20 段中位数取上中位（numpy 取中间两个的均值）。
  `src/fsfeatures.py` 的自检曾把该偏差解释成"MinGW 半整数 lgamma 精度偏移、单调
  等价"，把容差放宽到 **0.2** 就算通过 —— 误诊掩盖了真因。后果是
  `chi2_pvalue` / `median_prefix_p` 这两个 BASE 特征在 Windows（带 DLL）与
  Linux（纯 Python）上取值不同，训练与推理各用一套。修复后 11 维逐项一致
  （max|d| ≈ 6e-14），自检容差收回 1e-9。

### Added

- `experiments/add_jpeg_clean.py` —— 补上 README 一直引用、却在 git 全历史里
  **从未存在过**的 `src/_add_jpeg_clean.py`。新脚本把 JPEG 干净行的 photo_id
  **继承源图**，并做真实 JPEG 往返（不是 clean 的副本），写盘前校验分组不变量。
- `experiments/train_deploy_models.py::check_corpus_grouping()` —— 训练前的分组
  不变量护栏：任何 photo_id 的 variant 集合与其余不一致就直接拒绝训练。
- `src/test_pipeline.py::test_v2_cpu_gpu_consistency` —— CPU/GPU 143 维特征一致性
  回归护栏（修复后 max|Δ| ≈ 3e-5）。这正是当初缺失、让尺度缺陷溜过去的那道检查。
- `src/test_console_encoding.py` —— 静态护栏：`print`/`stderr` 行不得出现 GBK
  编码不了的字符。

### Changed

- 按修正后的语料与特征**重跑**：校园语料（414 源图 × 14 = 5796）、
  BOSSbase npz 143 维、`sota_compare`、5 阶消融、4 分类器对比、
  GroupKFold(8) OOF、两个部署模型。
- 新口径（全部可追到 `experiments/data/deploy_model_metrics.csv`）：

  | 模型 | held-out AUC (seed 0) | 8-split 平均 | 弱档 nsF5 p3 d=0.25 |
  |---|---|---|---|
  | **143d 默认** | **0.8939** | **0.8980 ± 0.0074** | **50.0%** |
  | 53d 可解释 | 0.8391 | 0.8461 ± 0.0106 | 41.4% |

- **结论翻转**：修好 SRM 尺度后是 **143d 优于 53d**（消融：去掉 SRM 90 维
  OOF AUC 0.9010 → 0.8513；按源图 GroupKFold(8) 上 143d 8/8 全胜）。
  53d 的定位因此改为"用约 0.05 AUC 换逐维可解释"，而不再是"AUC 更高"。
- 部署阈值随模型更新：143d `threshold` 0.1677 → **0.9493**，
  53d 0.2301 → **0.9595**（`threshold_low_fp` 0.9832 / 0.9845）。
- README、`docs/RESULTS.md`、`teaching/web/{zh,en}` 第 8 章与绪论、
  `webapp` 的 i18n 文案与 `dual-models.png` 资产生成器全部按新口径改写；
  旧数字在使用处逐条标注"审计前口径，已作废"。
- 1.6.1 条目里的"逐位复现 0.8946 / 0.9228 / …"只证明**脚本与产物一致**，
  不证明口径正确 —— 那份协议本身就含上面的源图泄漏，已在 1.6.2 更正。

### Fixed (其他)

- `python src/run_e2e.py`（README 快速开始里的命令）在中文 Windows 的默认控制台
  直接崩溃：`UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`。
  同类问题还有 `experiments/gen_figs.py`（9 处）与
  `yccstego/tools/plot_results.py`（1 处），一并改成 ASCII 的 `[OK]`。
- README 引用了不存在的 `src/_add_jpeg_clean.py`（见上）。
- `run_e2e` 未列入 `pyproject.toml` 的 `py-modules`，wheel 里会缺这个模块。
- `CHANGELOG` 1.6.1 误记"`pytest` 24 项通过"（当时实际 30 项；现为 34 项）。
- `.gitignore` 收编 `artifact-delivery-contract.json` 与 `.claude/`（一直以未跟踪
  状态挂在仓库根）。

### Known gaps

- `docs/*.pdf` 的两本学习手册仍印着旧数字，需要按新口径重新生成；
  源稿 `docs/src/*.docx` 已在手（见下"Removed"）。
- OOD"1/8 / 3/8 误报"与 GPU 管线的 0.790/0.644/0.712 仍不可溯源；
  `gain_importance*.csv` 产生于错误尺度，一并归入不可溯源。
- `src/make_dataset.py` 的 CLI 会把尺寸参数（`512x512`）当成第二个照片目录，
  打印一行"未找到图像"的无害告警。

### Removed

- **`thesis/` 与全部论文稿已从项目中删除**：学位论文、文献综述、项目综述
  （tex/pdf）、期刊稿（`journal_paper.*`、`paper/` 排版与 PDF）、JOSE 投稿草稿
  （`paper.md` / `paper.bib`）、论文构建脚本（`thesis/build_*.js`、
  `thesis/exp/`、`thesis/package*.json`）。共 10.5 MB。
- 学习手册的 DOCX 源稿**保留并迁移**到 `docs/src/`（它们是 `docs/*.pdf` 与
  `teaching/web/{zh,en}` 正文的唯一可编辑来源，不属于论文）。该目录按
  "产物入库、源稿本地"的约定写入 `.gitignore`。
- 随之清理：`Makefile` 的 `web-convert`、`teaching/web/{docx2md.py,README.md}`、
  `gpu/train_cnn.py`、`experiments/tools/gen_figs.py`、`docs/RESULTS.md` 生成器
  与教学网页正文里所有指向 `thesis/paper` 的路径与引用。

## [1.6.1] - 2026-09-13

关闭 1.6.0 遗留的最后两个可验证性缺口：**部署模型没有生产者**，以及
**同一个指标名在不同文档里对应不同语料/协议**。

### Added

- `experiments/train_deploy_models.py`：两个部署模型（143d / 53d LGB）的
  **生产者**。冻结口径 = `data/dataset_campus_v2_jpeg.csv` +
  按源图 `GroupShuffleSplit(test_size=0.25, random_state=seed)` +
  `num_leaves=31, n_estimators=800, learning_rate=0.03, min_child_samples=10,
  subsample=0.9, colsample_bytree=0.8`。产出模型、指标 CSV 与 `provenance`
  字段（数据集、划分、依赖版本、git rev）。
- `experiments/build_results_table.py` + `docs/RESULTS.md`：**唯一权威结果表**。
  每一行都带 `corpus`（语料）与 `protocol_id`（协议），并标 `traceable`
  是否可追到「脚本 + CSV」；追不到的（GPU 管线、OOD、旧 XGB/STACK）单独成节
  写明原因。`--check` 可校验文档与产物是否同步。

### Changed

- **README 头条口径改为 BOSSbase 1.01**：同一族模型在 BOSSbase 上是
  0.7529（143d）/ 0.7172（53d），而校园照片语料上是 0.8946 / 0.9100。
  前者是领域标准基准，后者是自建语料（统计结构更弱、更容易），
  两者不可并列。校园数字降为附表，并在使用处逐条标注语料。
- 随仓库分发的两个 `.joblib` 由新生产者**重新生成**：与旧文件在全部 5796 个
  样本上预测完全一致（max|Δp| = 0），阈值 0.1677 / 0.2301 不变；
  新 payload 额外带 `provenance`，并去掉了旧文件加载时的
  `InconsistentVersionWarning`（旧文件由 scikit-learn 1.7 序列化）。
- `experiments/README.md` / `experiments/PROVENANCE.md` 同步：模型有了生产者，
  并写明「8-split」在项目里指两种不同协议（8 seed 随机划分 vs GroupKFold(8) OOF）。

### Verification

- 143d 在 seed=0..7 上逐位复现 README 的 8-split 序列
  （0.8946 / 0.9228 / 0.9166 / 0.9083 / 0.9263 / 0.8933 / 0.9196 / 0.8866，
  均值 0.9085）；53d 逐位复现（均值 0.9227，per-seed 与 README 表一致）。
- 弱档检出率一并复现：nsF5 p3 d=0.25 为 85.3%（143d）/ 87.2%（53d）。
- 全量测试：`python -m pytest -q` 30 项通过；`src/test_core.py`、
  `src/test_steg.py` 通过。

### Known gaps

- 143d / 53d 的 **OOD 真实 JPEG 误报（1/8、3/8）仍不可溯源**：生产者与
  `data/ood_jpeg_test/` 已随另一项目删除，现列在 `docs/RESULTS.md` 第 7 节。
- `gpu/train_ml_gpu.py` 的指标（校园 0.790 / BOSSbase 0.644 / 合并 0.712）
  仍只打到 stdout，未落 CSV，因此同样只能待在不可溯源区。

## [1.6.0] - 2026-09-13

Verifiability hardening: every claim the project makes should now be checkable
by running something in the repo, and the claims that were not true have been
corrected rather than kept.

### Added

- `gpu/train_cnn.py` and `gpu/models/{xunet,yenet}.py`. The paper referenced
  these paths but they did not exist, so the "53-D features beat a CNN in the
  small-sample regime" claim had no supporting data anywhere. The models are
  reimplementations from the papers' descriptions (Xu et al. 2016, Ye et al.
  2017), not the authors' official code, and are labelled as such. Training
  splits strictly by source photo and reports train AUC beside val AUC, which is
  what distinguishes "did not converge" from "overfit". Measured on BOSSbase:
  Ye-Net 0.9541 [0.9463, 0.9630]; LGB-143d 0.7529; LGB-53d 0.7172; LGB-11d
  0.7128; Xu-Net 0.5007 with chance-level *training* AUC, i.e. not converged.
- `gpu/models/{xunet,yenet}.py` are joined by `gpu/train_cnn.py`, which lives in
  `gpu/` rather than under the (untracked) thesis directory because the CNN
  belongs to the toolkit, not to a paper.
- `scripts/build_cpp.py` plus `make cpp` / `make cpp-clean`.
- `src/cpplib.py`, resolving the accelerator filename per platform.
- `src/test_pipeline.py`: feature contracts, SRM kernels (numpy vs torch),
  the `analyze()` result contract, degenerate images, and ML model loading.
- CI jobs: `pytest`, and a headless GUI job under `xvfb-run`.
- `.github/workflows/webapp-tests.yml` (previously untracked, so the browser
  regression suite had never run).
- Two deployable models are now in the repository.

### Changed

- C++ accelerators are built from source on all three platforms instead of
  shipping a Windows-only `.dll`; no binaries are committed.
- `sota_compare.py` raises on missing feature columns instead of silently
  degrading, keeps `feat_set` and `dataset` as separate columns, and computes
  bootstrap CIs by resampling source photos rather than images.
- `fig_sota` reads the merged table and scales its x-axis to the data (it
  hardcoded `xlim(0.5, 0.85)`, which would draw a 0.95 bar off the canvas).
- `models/*.joblib` moved from "ignored" to "two whitelisted files";
  `lightgbm` added as a dependency (the shipped models are LightGBM pickles, so
  without it a clone still got `available=False`); `scikit-learn` pinned `<2`.
- `pyproject.toml` declares `xgboost`, the missing `py-modules` entries, a
  `thesis` extra, and pytest configuration. The `dev` extra promised pytest
  while the suite was bare asserts with `main()` guards.
- `teaching/videos/` is ignored: 134 MB of generated output, rebuildable from
  `teaching/README.md`.

### Fixed

- `qa_sheet()` wrote a 33-byte zero-height PNG when a chapter produced no beat
  timestamps, then aborted the run, so later chapters were silently never built
  and already-listed chapters were never retried. It now refuses to run with no
  timestamps, and a failing chapter is reported, skipped, and left retryable.
  Two unusable QA contact sheets (one 33-byte, one missing) were rebuilt.
- The eleven rendered videos on disk had been renamed to their Chinese titles
  while `index.html`/`durations.json` address them as `chNN.mp4`, so every link
  on the local playback page 404'd.
- `test_false_positive.py` contained `ok = ok` — a no-op assignment that
  discarded the loop's failure signal, leaving the whole test resting on one
  assertion.
- `solve_wet_paper()` drew its traversal order from the global NumPy RNG, so the
  same input produced different (equally valid) solutions run to run; the order
  now derives from a hash of the inputs.
- `encode_string()`/`decode_string()` used ASCII with `errors="replace"`, so any
  non-ASCII message silently decoded as `?`. Now UTF-8.
- `cross-platform.yml` used `python` in a job with no Python setup step.

### Known gaps

- The two shipped models have **no in-repo producer**: `src/train_model.py`
  trains an LR/RF/GB/XGB family, and the LightGBM runs that produced them were
  never scripted. They work, but they are not reproducible from this repository.
- The thesis and the JOSE paper are deliberately not in this repository
  (`thesis/` and `paper*` are ignored). What *is* tracked is the code they need
  to be reproducible: the toolkit in `gpu/` and the experiment orchestration in
  `experiments/`. Their outputs (`experiments/data/`, `experiments/figs/`) are
  generated artefacts and stay out.
- The experiment scripts were moved out of `thesis/exp/` and `thesis/tools/`
  because a tracked test or experiment that imports from an ignored directory is
  reproducible only on the author's machine. Fixing that also removed four
  scripts' hardcoded `F:\Steganography` paths.

## [Unreleased] - Teaching project

### Added

- Website nsF5 comparison lab (Lab 4, `#nsf5`): embeds the same message into the
  demo image with either naive LSB replacement or the project's real nsF5
  strategy ported to JS (per-block Hamming syndrome coding, magnitude-decrement
  modification, wet pixels 127/128/129 handed to the wet-paper solver, seeded
  permutation of the block path mirroring `permute_index`/`_pool_positions`).
  The lab shows changed-pixel count, embedding efficiency (bits per change),
  PSNR, a difference map and the same in-browser chi-square/RS detector, so
  learners can see that nsF5 both changes fewer pixels and leaves a weaker
  statistical fingerprint; includes a decode round-trip and `data-*` test hooks.
- Handbook ch05 (zh + en): a hand-worked GF(2) example for the wet-paper solver
  (single-column hit, two-column XOR, and when Gaussian elimination is actually
  needed), plus the solvability criterion (dry columns must span GF(2)^p) and
  why free variables are set to 0 to minimize changes.
- Handbook ch03 (zh + en): reused the webapp's chi-square pair-count and
  clean-vs-stego bar figures so the "visual statistics" chapter has concrete
  imagery matching the theory.
- Website payload-scan honesty: `scan-demo.json` now records the real
  changed-pixel footprint (`changed_pixels`) alongside the nominal capacity
  fraction, and the scan note shows "改动像素≈N%" so the density axis is no
  longer misleading.
- Website LSB live steganalysis: after embedding, the page runs real chi-square
  (Westfeld) and RS analysis in JavaScript on the current image and shows
  `chi2 p · RS Gn → verdict`, plus a **changed-pixel mask** canvas (white =
  modified LSB) - so learners can embed a sentence and immediately see the
  statistical fingerprint that detection catches.
- Website a11y/conventions: label `for`/id association for the Hamming / wet-paper
  / ML / payload controls, `aria-live` on result readouts, and a live decode
  note. (Details in the reference-removal note below.)
- Website LSB lab round-trip: a **Decode it back** button that reads the length
  header and payload straight out of the current canvas LSBs and shows the
  recovered message, so learners can embed a sentence and see it come back (the
  format matches `ns5_core.encode_string`); a live decode note replaces the
  change count.
- Website structure/hierarchy: an "on this page" contents map right after the
  hero groups the whole page into four themed parts (hands-on labs / how it
  works / learning path / FAQ), and every section carries a matching part badge,
  giving the single-page lab a clear learning progression.
- Website FAQ: a bilingual accordion section (8 common questions on PNG vs JPEG,
  why LSB is invisible, chi-square/RS detection, Hamming matrix coding, nsF5 vs
  F5, choosing a cover and raw-pixel CNNs), plus a "still stuck / try it /
  license" card row; added to the top nav and scroll-spy. The license FAQ entry
  states the correct **Apache-2.0** terms (matching LICENSE/NOTICE).
- Bit-plane layering teaching visual (`lsb-layering-{zh,en}.png` in `webapp/assets`
  and `img009.png` in both handbook assets): shows an 8-bit image as eight
  stacked bit planes and proves each must be weighted by `2**k` before they can
  be summed back into the original.
- Website LSB experiment extension: a bit-plane layering explorer that switches
  between **Extract plane** (pull out any single bit plane to inspect) and
  **Restack (weighted)** (toggle planes on/off and watch the weighted sum
  reconstruct the original), plus the new weighted-stacking figure; keyboard
  operable and covered by the interactive test.
- README refresh: interactive teaching-website section, updated bilingual
  handbook links, current directory tree, and cross-platform command examples.
- Interactive bilingual learning website (`webapp/`): LSB bit-plane lab and
  Hamming syndrome-coding demo in the browser, project visuals, ML charts,
  12-week roadmap, and one-click language switching; served at the GitHub
  Pages root while the Jupyter Books remain at `/zh` and `/en`.
- Website additions: wet-paper / danger-pixel visual section, LSB histogram
  and changed-pixel-mask figures (bilingual variants), and `?lang=zh|en` URL
  switching for sharing and automated checks.
- Website labs: interactive wet-paper dry-position solver (toggle wet/dry cells
  and solve syndrome on dry columns) and an ML decision-threshold playground
  (drag threshold, live FP/FN rates).
- Website UX: wet-paper auto-play animation, mobile navigation menu, and
  scroll-spy highlighting of the active section.
- Website data-viz lab: payload scan (real project statistics on a campus
  photo) with chi-square p / RS estimate / ML probability curves synced to an
  embedding-density slider.
- Website tests: `webapp/tests/interactive.mjs` runs the full interactive lab
  (language toggle, LSB embed, Hamming, wet auto-play, threshold/payload
  sliders, mobile menu) in Chrome/Edge with console-error detection.
- Website accessibility: Hamming and wet-paper canvases are keyboard-operable
  (arrow keys + Space) with visible focus outlines; live result captions are
  announced via `aria-live`.
- Website layout/perf: lazy-loading below-the-fold images and a browser layout
  test (`webapp/tests/layout.mjs`) covering desktop/mobile overflow, broken
  images and missing alt text.
- README: full English overview section (features, cross-platform quick start,
  learning resources and license) alongside the Chinese documentation.
- teaching/README: bilingual version - full English teaching guide followed by
  the Chinese section.
- Cross-platform (Linux/macOS/Windows) support:
  - `fsfeatures.get_lib()` falls back to pure-Python 11-D features when the
    Windows DLL is missing;
  - `cppembed.embed_string()` falls back to the pure-Python embedder when
    `cpp/nsf5embed.dll` is unavailable;
  - root `Makefile` with `install/test/e2e/notebooks/dataset/web` targets;
  - `.github/workflows/cross-platform.yml` CI matrix (Ubuntu/macOS/Windows)
    runs algorithm tests and both feature/embedding fallbacks.
- GUI teaching animation: "matrix coding demo" panel now supports
  **auto-play** (random block -> highlight matched syndrome column -> flip ->
  verify) with speed control and stop; GUI smoke test covers the animation.
- Per-chapter Colab/Jupyter notebooks (`notebooks/`): bits & pixels, Python
  toolchain, LSB + steganalysis, matrix embedding, nsF5 + wet paper, hash
  keying, ML foundations, ML steganalysis, engineering, capstone. Each notebook
  self-clones the repo and auto-installs dependencies. All ten notebooks are
  executed end-to-end in a local kernel (10/10 pass).
- `src/ml_predict.py` - 53-D interpretable model inference support (selects the
  53 feature columns from the 143-D extractor).
- `src/py_features.py` - pure-Python 11-D feature extractor; `featurize_v2.py`
  and `ml_predict.py` fall back to it when the Windows C++ DLL is unavailable,
  so Colab/Linux/Docker can run feature extraction and trained-model inference.
- `scripts/download_datasets.py` - one-click BOSSbase 1.01 downloader.
- `docker/Dockerfile` + `docker-compose.yml` - JupyterLab teaching image
  (Linux; algorithm self-tests pass during build).
- `.github/workflows/docker.yml` - CI that builds the teaching image and smoke-
  tests algorithm tests plus the pure-Python feature fallback inside it.
- `teaching/web/` - bilingual Jupyter Book scaffolding (zh/en) with a
  DOCX->Markdown converter (`teaching/web/docx2md.py`) and GitHub Pages
  workflow building both books into one site.

### Fixed

- Repo hygiene: `data/` generated datasets (`dataset_*.csv`), `campus_jpg/` and
  `data/_*.log` training logs, plus `webapp/tests/node_modules/.npm-cache` are
  now gitignored (kept locally; 7.8 GB historical backup moved out of the repo
  tree to external storage).
- Website i18n: the self-test section's part badge showed the raw key `part5`
  (the key was missing from both dictionaries); the "on this page" contents map
  now also lists the nsF5 lab and the self-test quiz, and the static fallback
  for the FAQ notebook count says 10 (matching the dictionaries and the repo).
- Website: removed a dead `preconnect` to fonts.googleapis.com (no webfont is
  loaded; the design system uses local font stacks).
- Core: `ns5_core._embed_into_image` no longer silently truncates an over-capacity
  message; it now validates the payload against the image's body-pool size and
  raises a clear `ValueError` with the number of Hamming blocks needed vs
  available.
- Core: RGB images no longer report `cover_changed = 0` - the `stego` buffer was
  re-bound to the source image so the clean/stego comparison was a self-comparison;
  the copy is kept independent now (also fixes the `efficiency.py` measured curve
  when fed RGB data).
- Core: message encoding switched from ASCII `errors="replace"` to UTF-8, so
  non-ASCII text (e.g. Chinese) is preserved instead of silently becoming `?`.
- Core: wet-paper pair-search seeding is deterministic (derived from the dry cols
  and target), no longer perturbs the global NumPy RNG, so identical inputs give
  identical stego images.
- Core: `efficiency.measured_efficiency` now sizes the test message within the
  real body-pool capacity (it previously filled to an over-estimated capacity and
  would overflow once embed validation was added).
- Assets: `stego_detect` and `scan_curves` demo messages clamped to fit the 256x256
  / 512x512 cover capacities (previously over-capacity and silently failing).
- GUI: "Decode" and "Analyze" now operate on the generated stego image instead of
  always the loaded cover, fixing the embed -> decode/analyze flow.
- Tests: added coverage for `get_image_hash`, `derive_seed`, `solve_wet_paper`,
  `gauss_solve_GF2` and `permute_index` (previously untested), plus regression
  tests for the UTF-8 round-trip, RGB `cover_changed`, capacity error and wet-paper
  determinism.
- Packaging: `pyproject.toml` `py-modules` now includes `featurize_v2`,
  `py_features` and `srm_filter` (they were missing from the wheel, which broke
  `import make_dataset` and the `ml_predict`/GUI feature path), and declares
  `xgboost` as a dependency.
- Docs: corrected stale handbook page counts (Chinese 94 -> 66, English 80 -> 72),
  fixed the webapp FAQ license statement to Apache-2.0, and corrected the
  notebook count (12 -> 10).
- CI: added `webapp-tests.yml` that serves the webapp and runs the Playwright
  interactive + layout tests (previously these were never wired into any workflow),
  and added a missing `workflow_dispatch` trigger to `ci.yml`.
- README Zenodo DOI badge pointed to an unrelated record
  (10.5281/zenodo.14851234); corrected to the project's actual archive
  10.5281/zenodo.22543629.

## [1.5.0] - 2026-09-06

### Added — Dual-Version Model

- 53-D slim model (`stego_classifier_v2_jpeg_lgb_51d.joblib`): removes SRM 90-D,
  held-out AUC 0.9100 (+0.015 vs 143-D), 8-split mean 0.9227 (+0.014).
- 143-D robust model (default, `stego_classifier.joblib`): held-out AUC 0.8946,
  multi-split mean 0.9085, OOD robust on real campus JPEG (7/8 correct clean,
  median 0.011).

## [1.4.0] - 2026-09-05

### Added — LGB Tuned

- Default classifier switched to LightGBM tuned (num_leaves=31, n_estimators=800,
  learning_rate=0.03, min_child_samples=10).
- 53-D slim variant benchmarked.

## [1.3.0] - 2026-08-30

### Added

- BOSSbase 1.01 dataset integration.
- SRM high-pass preprocessing (`src/srm_filter.py`).
- Multi-process make_dataset with `-j/--workers N`.

## [1.2.0] - 2026-08-20

### Added

- Wet-paper coding (Filler-Fridrich) integration with nsF5.
- C++ acceleration DLLs (`cpp/fsfeatures.dll`, `cpp/nsf5embed.dll`).

## [1.1.0] - 2026-08-10

### Added

- Image hash keying (SHA-256 + passphrase).
- Deterministic permutation (DLL + Python fallback).

## [1.0.0] - 2026-08-01

### Added

- Initial release: nsF5 embedding + LSB + F5 matrix coding.
- Blind steganalysis: chi-square (Westfeld) + RS analysis (Fridrich).
- GUI (tkinter).
- ASCII string embed/decode with passphrase.
