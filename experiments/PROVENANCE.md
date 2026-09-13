# experiments/data 产物溯源

每个 CSV 都要能回答两个问题：**谁生产的**、**还能不能再生产一次**。
标 ❌ 的是**不可再生的历史产物** —— 它们的数据源或生产者已经不在仓库里了，
引用这些数字时必须说明这一点，不能当作可复现结果呈现。

## ✅ 可从仓库代码复现

| CSV | 生产者 | 输入 |
|---|---|---|
| `sota_table.csv` | `exp/merge_sota_table.py` | 下面几项 + 检查点 |
| `sota_compare.csv` | `exp/sota_compare.py` | `data/dataset_bossbase_npz_v2.csv` + `sota_cnn_split.json` |
| `sota_cnn_results.csv` | `exp/run_cnn_sota.py` | `gpu/data/imageset_bossbase.npz` |
| `sota_cnn_split.json` | 同上（首次运行写出） | 同上 |
| `cnn_checkpoint_eval.csv` | `exp/eval_cnn_checkpoint.py` | `models/cnn_*.pt` + npz |
| `ablation_5stage.csv`, `ablation_5stage_detailed.csv` | `exp/ablation_5stage.py` | `data/dataset_campus_v2*.csv` |
| `model_compare_4clf.csv`, `model_compare_4clf_summary.csv` | `exp/model_compare_4clf.py` | 同上 |
| `density_grid.csv`, `density_detection.csv` | `exp/density_grid.py` | 同上 |
| `8split_raw.csv`, `8split_comparison.csv` | `experiments/_8split_compare.py` | 同上 |
| `code_family.csv`, `scan_curves.csv`, `tamper.csv` | `experiments/tools/gen_figs.py` | 现场计算 |
| `det_*.csv` | `experiments/tools/gen_eval.py` | 现场计算 |
| `bench_*.csv` | `experiments/tools/gen_bench.py` | 现场计算 |
| `feat_*.csv` | `experiments/tools/gen_feat.py` | 现场计算 |

## ❌ 不可再生（引用时须注明）

| CSV | 行数 | 为什么不可再生 |
|---|---|---|
| `ood_jpeg_eval.csv` | 300 | 生产者与源目录 `data/ood_jpeg_test/` 属于另一个项目，已随其删除。`exp/gen_figs.py::fig_ood_jpeg` 现在会显式打印跳过原因，不再静默少图。 |
| `gain_importance_53d.csv` | 53 | 全仓无写者，只有读者（`exp/gen_figs.py`）。数值本身与 53d 模型的 gain importance 一致，但产生它的那次运行没有留下脚本。 |

## ⚠ 口径提示

- `sota_compare.csv` 里的 `LGB-11d / dataset=bossbase_csv` 行来自
  `data/dataset_bossbase.csv`（10000 源图 × 7 变体），与其余各行**不同源**，
  只可作为附录参考。`sota_table.csv` 的 `comparable_group` 列把这一点显式标出。
- 2026-09 之前，这一行曾被写进论文正文并与 CNN 结果直接比较 —— 那是错的，
  两者语料不同源。
- `models/*.joblib` 里的两个部署模型（143d / 53d LGB）**目前没有仓库内的生产者**：
  `src/train_model.py` 训练的是 LR/RF/GB/XGB 家族，`experiments/` 下的 LGB 脚本
  都只训练+评估、不落盘。见 README 的"模型来源"一节。
