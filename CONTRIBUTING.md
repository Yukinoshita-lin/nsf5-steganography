# 贡献指南

这是一个**教学 + 研究**工具，项目对"可复现"和"数字可信"的要求比一般项目高。
下面是最短的路径。

## 1. 环境

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev,experiments]"
make hooks        # 启用 .githooks/commit-msg（提交时自动剔除 AI 署名尾注）
```

`make hooks` 只在本机生效一次，但它很重要：见下面第 4 条。

## 2. 跑测试

```bash
make test          # 核心/隐写分析/假阳性/管线自测
make pytest        # 完整 pytest 套件
make notebooks-run # 逐本执行教学 notebook（约 1 分钟）
```

CI 会在 Ubuntu / macOS / Windows 上跑同样的东西，外加 C++ 加速库的编译与
一致性自检（`cross-platform.yml`）、Docker 镜像、浏览器回归与
`attribution` / `handbook` / `feature-consistency` 三个专项作业。

## 3. 改动的"必带动作"

| 你改了什么 | 必须跑 |
|---|---|
| `src/` 里的算法或特征 | `make pytest`（含 CPU/GPU 特征一致性） |
| `experiments/` 的实验或数据 | `make exp-models` → `make results`（刷新 `docs/RESULTS.md`）|
| 教学手册（DOCX / 网页版 / PDF） | `make handbook-check`（口径必须一致） |
| 手册里的代码片段 | `make handbook-snippets`（可执行片段必须跑通，含期望输出断言） |
| `teaching/build_notebooks.py` | `make notebooks` 并提交生成的 `notebooks/`（CI 会比对） |
| 部署模型 | `make exp-models`（并核对 `experiments/data/deploy_model_metrics.csv`） |

**测不了就说明原因，别静默跳过。** 项目里所有检查都遵循这一条：缺数据源会打印
跳过原因，缺特征列会直接报错而不是降级。

## 4. 提交信息

- 用 `type(scope): 摘要` 的形式（`fix` / `feat` / `docs` / `ci` / `chore` …）。
- **不要带 AI 协作工具的署名尾注**（`Co-Authored-By: Claude Code …` 之类）。
  GitHub 会把它们当作共同作者显示在提交历史里，事后只能改写历史才能去掉。
  `.githooks/commit-msg` 会在提交时自动剔除，CI 的 `attribution` 作业兜底检查。

## 5. 写数字的三条纪律

1. **按源图分组**：同一张源图的干净图与全部变体必须落在同一侧，否则就是源图泄漏。
   训练脚本会校验"每个 `photo_id` 的 variant 集合一致"，语料不合规直接拒绝训练。
2. **口径唯一**：同一个模型在训练语料与推理路径上必须用同一套特征实现。
   `src/test_pipeline.py` 里的 CPU/GPU 与 C++/Python 一致性测试守这条。
3. **可溯源**：任何写进文档的数字，都要能追到"脚本 + CSV"。做不到的请写进
   `experiments/PROVENANCE.md` 并说明原因，不要让它悄悄变成结论。

## 6. 数据与产物的入库政策

| 入库 | 不入库（本地生成） |
|---|---|
| 源码、脚本、教学材料、生成的网页正文、`docs/RESULTS.md` | 数据集 CSV（`data/dataset_*.csv`）、`experiments/data/`、`experiments/figs/` |
| 两个可部署模型 `models/stego_classifier*.joblib`、手册 PDF | 手册 DOCX 源稿（`docs/src/`）、外部语料（`data/external/`）、教学视频 `teaching/videos/` |

校园照片语料是作者本人的照片，无法分发；因此**部署模型的训练语料不能从零重建**，
`docs/RESULTS.md` 的主表走公开的 BOSSbase，那条链可以。

## 7. 教学材料

- 手册事实由 `teaching/handbook_facts.py` 统一：`--check` 校验（CI 用），
  `--fix --web` 按表修正。改口径请改这张表，不要手改生成的正文。
- **不要用 `make web-convert` 覆盖 `teaching/web/*/content/`**：网页版比 DOCX
  内容丰富得多，重新生成会删掉增量（原因见 `teaching/web/README.md`）。
