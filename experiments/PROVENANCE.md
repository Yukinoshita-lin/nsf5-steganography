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
| `deploy_model_metrics.csv` | `experiments/train_deploy_models.py` | `data/dataset_campus_v2_jpeg.csv` |
| `results_canonical.csv` | `experiments/build_results_table.py` | 上面这些 CSV |
| `ood_eval.csv`, `ood_summary.csv` | `experiments/ood_eval.py` | `data/campus_jpg` + `data/external/{div2k,alaska2}` |
| `gain_importance.csv`, `gain_importance_53d.csv`, `gain_group_share.csv` | `experiments/gain_importance.py` | `data/dataset_campus_v2_jpeg.csv` |
| `gpu_pipeline_metrics.csv`, `gpu_pipeline_detection.csv` | `gpu/train_ml_gpu.py`（2026-09-14 起落盘） | `gpu/data/imageset*.npz` |
| `train_model_metrics.csv`, `train_model_detection.csv` | `src/train_model.py`（2026-09-14 起落盘） | `data/dataset*.csv` |
| `code_family.csv`, `scan_curves.csv`, `tamper.csv` | `experiments/tools/gen_figs.py` | 现场计算 |
| `det_*.csv` | `experiments/tools/gen_eval.py` | 现场计算 |
| `bench_*.csv` | `experiments/tools/gen_bench.py` | 现场计算 |
| `feat_*.csv` | `experiments/tools/gen_feat.py` | 现场计算 |

## ❌ 不可再生（引用时须注明）

| CSV | 行数 | 为什么不可再生 |
|---|---|---|
| `ood_jpeg_eval.csv` | 300 | 生产者与源目录 `data/ood_jpeg_test/` 属于另一个项目，已随其删除。`exp/gen_figs.py::fig_ood_jpeg` 现在会显式打印跳过原因，不再静默少图。 |
| ~~`gain_importance_53d.csv`~~ | 53 | **2026-09-14 已移出本表**：现有写者 `experiments/gain_importance.py`。 |
| ~~`gain_importance.csv`~~ | 143 | **2026-09-14 已移出本表**：现有写者 `experiments/gain_importance.py`。旧表产生于 SRM 尺度错误的语料（GPU 端先 /255），"SRM 90 维 gain 占比仅 26.6%"的结论已作废；重算后 SRM 占 52.6%。 |

## ⚠ 口径提示

- **2026-09-14：本文档对应的"不可溯源"清单已清空。** README 里另外三处只打印不落盘
  的历史数字（GPU 管线 0.790/0.644/0.712、train_model 家族 XGB/LGB/STACK、
  OOD 误报 1/8 与 3/8）也都补上了生产者并重跑，见上表新增的四行。
  其中 0.790 / 0.644 逐位复现；0.712 因现有 BOSSbase 图像集只有 10000 样本
  （旧数是 50000）而无法复现，改用 13410 样本重跑并注明口径差异。

- `sota_compare.csv` 里的 `LGB-11d / dataset=bossbase_csv` 行来自
  `data/dataset_bossbase.csv`（10000 源图 × 7 变体），与其余各行**不同源**，
  只可作为附录参考。`sota_table.csv` 的 `comparable_group` 列把这一点显式标出。
- 2026-09 之前，这一行曾被写进论文正文并与 CNN 结果直接比较 —— 那是错的，
  两者语料不同源。
- 两个部署模型（143d / 53d LGB）**已有仓库内生产者**：
  `experiments/train_deploy_models.py`（2026-09-13 补）。口径为
  `GroupShuffleSplit(test_size=0.25, random_state=seed)` 按源图划分 +
  冻结的 LightGBM 超参，在 `data/dataset_campus_v2_jpeg.csv` 上训练。
  它与随仓库分发的 `.joblib` 在全部 5796 个样本上预测完全一致
  （143d 的 8 个 seed AUC 逐位复现），产出的指标落在
  `experiments/data/deploy_model_metrics.csv`。见 README 的"模型从哪来"一节。
