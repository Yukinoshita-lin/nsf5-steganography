# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
- `python -m pytest -q` → **56 项通过**（新增 6 条 OOD 冒烟），覆盖率 69.3% ≥ 门槛 65%。
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
