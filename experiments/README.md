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

## 评测纪律（三条，违反任何一条结论就不成立）

1. **按源图分组划分。** 同一张源图派生的干净图与含密变体必须落在同一侧。
   混到两侧的话，模型只要认出源图内容就能刷高 AUC —— 那是源图泄漏，不是
   隐写检测能力。所有脚本统一走 `gpu/train_cnn.py::split_by_photo`。
2. **置信区间按源图重采样。** 同源样本高度相关，按图 bootstrap 会把有效样本
   量当成 5 倍，从而低估区间宽度。见 `sota_compare.py::bootstrap_auc_ci`。
3. **不同语料的数字不进同一张表。** `dataset_bossbase.csv`（10000 源图 × 7 变体）
   与 `imageset_bossbase.npz`（2000 源图 × 5 变体）是两套东西。
   `sota_table.csv` 用 `comparable_group` 列把这件事写死，`fig_sota` 也只画 A 组。

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
