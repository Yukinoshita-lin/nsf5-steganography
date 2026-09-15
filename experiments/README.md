# experiments — 实验复现手册

论文里的每一张图、每一个数字，都应该能追到"哪个脚本、读哪个 CSV、什么命令"。
这份手册就是那张对照表；`experiments/PROVENANCE.md` 则标注哪些产物已经
**无法再生**（生产者随另一个项目被删除）。

## 依赖

```bash
python -m pip install -e ".[experiments]"      # seaborn + lightgbm + torch + pandas + sklearn
```

`torch` 只在跑 CNN 部分时需要（本机 RTX 4060 8GB 足够，两个模型约 2 小时）。

## 一键复现

```bash
make exp-data    # 特征表 + LGB 基线 + CNN 训练(耗时长) + 汇总表
make exp-figs    # 按 experiments/data 里的 CSV 重建全部图
```

两个**部署模型**的复现与结果表的刷新是另一条独立的链（不需要 torch）：

```bash
python experiments/train_deploy_models.py    # 重训 + 覆盖 models/*.joblib（约 3 分钟）
python experiments/build_results_table.py    # 合并成 docs/RESULTS.md + results_canonical.csv
```

（等价的 make 目标：`make exp-models` / `make results` / `make results-check`。）

`docs/RESULTS.md` 是项目**唯一权威结果表**：每一行都带 corpus（语料）与
protocol_id（协议），README 的指标一律引用它；口径冲突时以它为准。

## 数据流

```
gpu/data/imageset_bossbase.npz           2000 源图 × 5 变体 (1 干净 + 4 含密)
        │
        ├── featurize_bossbase_npz.py ──► data/dataset_bossbase_npz_v2.csv   (10000×143)
        │                                          │
        │                                          └── sota_compare.py ──► experiments/data/sota_compare.csv
        │
        └── run_cnn_sota.py ──► gpu/train_cnn.py ──► models/cnn_{xunet,yenet}_bossbase.pt
                    │                                       │
                    ├── experiments/data/sota_cnn_results.csv     │
                    │                                       │
                    └── experiments/data/sota_cnn_split.json ────┘   同一份按源图划分
                                        │
                          eval_cnn_checkpoint.py ──► experiments/data/cnn_checkpoint_eval.csv
                                        │
                          merge_sota_table.py ──► experiments/data/sota_table.csv ◄── sota_compare.csv
                                        │
                                  gen_figs.py::fig_sota ──► experiments/figs/fig_sota.png
```

**`sota_cnn_split.json` 是这条链的关键**：CNN 与 LGB 基线必须复用同一份按源图
的划分，否则两侧的验证集不是同一批图，比出来的差值没有意义。它由
`run_cnn_sota.py` 首次运行时写出，后续调用只读不覆盖。

## 脚本对照

| 脚本 | 产出 | 输入 | 大致耗时 |
|---|---|---|---|
| `featurize_bossbase_npz.py` | `data/dataset_bossbase_npz_v2.csv` | npz | 5 min (GPU) |
| `run_cnn_sota.py` | `sota_cnn_results.csv`, `sota_cnn_split.json`, `models/cnn_*.pt` | npz | ~2 h (GPU) |
| `eval_cnn_checkpoint.py` | `cnn_checkpoint_eval.csv` | 检查点 + npz | 1 min |
| `sota_compare.py` | `sota_compare.csv` | npz_v2 CSV + split json | 5 min |
| `merge_sota_table.py` | `sota_table.csv` | 上面三者 + 检查点 | < 1 min |
| `gen_figs.py` | `experiments/figs/fig_*.png` | `experiments/data/*.csv` | 1 min |
| `ablation_5stage.py` | `ablation_5stage*.csv` | 校园 v2 CSV | 分钟级 |
| `model_compare_4clf.py` | `model_compare_4clf*.csv` | 校园 v2 CSV | 分钟级 |
| `density_grid.py` | `density_grid.csv` | 校园 v2 CSV | 分钟级 |
| `train_deploy_models.py` | `deploy_model_metrics.csv` + `models/*.joblib` | `data/dataset_campus_v2_jpeg.csv` | ~3 min（8-split）/ ~10 s（单 seed） |
| `build_results_table.py` | `results_canonical.csv` + `docs/RESULTS.md` | `experiments/data/*.csv` | < 5 s |
| `ood_eval.py` | `ood_eval.csv` + `ood_summary.csv` | `data/campus_jpg` + `data/external/{div2k,alaska2}` | **~1.7 min**（1514 张 × 2 模型 × 2 配置, 8 进程; 特征每图只算一次） |
| `gain_importance.py` | `gain_importance*.csv` + `gain_group_share.csv` | `data/dataset_campus_v2_jpeg.csv` | < 1 min |

## 评测纪律（三条，违反任何一条结论就不成立）

1. **按源图分组划分。** 同一张源图派生的干净图与含密变体必须落在同一侧。
   混到两侧的话，模型只要认出源图内容就能刷高 AUC —— 那是源图泄漏，不是
   隐写检测能力。所有脚本统一走 `gpu/train_cnn.py::split_by_photo`。
2. **置信区间按源图重采样。** 同源样本高度相关，按图 bootstrap 会把有效样本
   量当成 5 倍，从而低估区间宽度。见 `sota_compare.py::bootstrap_auc_ci`。
3. **不同语料的数字不进同一张表。** `dataset_bossbase.csv`（10000 源图 × 7 变体）
   与 `imageset_bossbase.npz`（2000 源图 × 5 变体）是两套东西。
   `sota_table.csv` 用 `comparable_group` 列把这件事写死，`fig_sota` 也只画 A 组。

   其中最容易犯的一处：**「8-split 平均 AUC」在项目里指两种不同的东西** ——
   README 的 0.9085/0.9227 是「按源图 holdout × 8 个 seed 取均值」
   (`holdout_by_photo_8seed`)，而 `_8split_compare.py` 的 0.9853/0.9914 是
   「GroupKFold(8) 的 OOF」(`groupkfold8_oof`)。两者都被叫过 8-split，不能混引。
    `docs/RESULTS.md` 第 8 节把可以/不可以比较的组合写死了。

4. **特征口径唯一。** 语料是用哪条特征管线建的，推理就必须走哪条。
   2026-09-14 审计发现两个反例，都已修并有护栏：
   - `gpu/featurize_v2_gpu.py` 的 SRM 曾把像素先 `/255`，与 CPU 参考差约 30 倍
     （语料用 GPU、单图判定用 CPU）→ `src/test_pipeline.py::test_v2_cpu_gpu_consistency`
     与 CI 的 `feature-consistency` job 守住；
   - `cpp/fsfeatures.cpp` 的卡方自由度曾用 `n` 而非 `n-1`、中位数取上中位，
     与 Python 参考不一致（Windows 与 Linux 给出不同特征）→ `src/fsfeatures.py`
     的自检容差已从被误诊而放宽的 0.2 收回 `1e-9`。

5. **分组不变量必须成立。** 每个 `photo_id` 的 variant 集合必须完全一致；
   出现"孤儿 id 块"（某些 id 只有单一 variant）就是源图泄漏的前兆，
   `experiments/train_deploy_models.py::check_corpus_grouping()` 会直接拒绝训练。
   这正是 2026-09-14 审计最严重缺陷（414 个 `clean_jpeg` 行各占一个 photo_id）
   的形态 —— 修正分组后 143d held-out AUC 0.8946 → 0.7555。

6. **生产者的口径要有测试兜底。** 头条数字的生产者不能只有"代码在那里"这一条保障：
   - `src/test_results_contract.py` —— 生产者算哪些列 / 权威表是否带语料与协议；
   - `src/test_model_cards.py` —— 随包模型的模型卡与二进制不脱钩；
   - `src/test_ood_smoke.py` —— OOD 评估（`ood_eval.py`）用**合成语料**在 CI 里跑通：
     判据必须是 payload 里的部署阈值、`--workers` 并行与单进程逐位一致、
     汇总的 fp_rate / Wilson CI / ALL 行自洽。
   合成语料不代替真实照片，所以这些测试**只断言口径与统计结构，不断言具体误报率**；
   真实数字仍然只能由 `ood_eval.py` + 外部语料产出。

## 语料的可复现性边界

| 语料 | 能否从零重建 | 说明 |
|---|---|---|
| BOSSbase npz / CSV | ✅ | `scripts/download_datasets.py` 公开可下载（`dde.binghamton.edu`，2026-09 实测可用）|
| 校园 v2 / v2_jpeg | ❌ | 414 张照片是作者本人的 `data/campus_jpg/`，不可分发；脚本链完整但需自备照片 |
| OOD 真实照片集 | ⚠ 部分 | DIV2K 100 张公开可下载；ALASKA#2 需 Kaggle 凭据；校园 414 张同上 |

`docs/RESULTS.md` 第 4 节（主表）走的是 BOSSbase，因此主表可从零复现；
第 6 节（附表）的校园数字只能在拿到那批照片后重跑；第 5 节（OOD 误报率）
额外需要 DIV2K（公开）与 ALASKA#2（Kaggle）语料，见 `experiments/ood_eval.py`。

外部语料放在 `data/external/`（不入库，见 `.gitignore`）：本地可以用 junction/软链
指向别处的副本，`ood_eval.py` 的默认路径就是按这个布局写的。

## 关于 CNN 结果的说明

`gpu/models/` 下的 Xu-Net / Ye-Net 是**依据论文描述自行复现**的实现（Xu et al.
2016 / Ye et al. 2017），不是原作者发布的官方代码，绝对数值不可与原文逐位对比。

截至 2026-09-13 的实测（BOSSbase npz，按源图 holdout）：

| 模型 | val AUC (5-crop TTA) | 训练集 AUC | 说明 |
|---|---|---|---|
| Ye-Net（SRM 固定高通层） | **0.9541** [0.9463, 0.9630] | 0.8884 | 收敛 |
| Xu-Net | 0.5007 [0.5004, 0.5012] | **0.5005** | **未收敛** |
| LGB-143d | 0.7529 [0.7333, 0.7719] | — | |
| LGB-53d | 0.7172 [0.6943, 0.7406] | — | |
| LGB-11d | 0.7128 [0.6913, 0.7360] | — | |

Xu-Net 的**训练集** AUC 也是 0.50，说明它连训练集都没拟合上 —— 这是"没收敛"，
不是"过拟合"，因此**不能**把它当作"CNN 不如手工特征"的证据。已排除的原因：
学习率（1e-3 / 3e-4 / 1e-4）、输入尺度（0-255 与 1/255）、激活函数（Tanh / ReLU）、
网络头（65536→128 巨型 FC 与 GAP）。详见 `eval_cnn_checkpoint.py` 的自述。
