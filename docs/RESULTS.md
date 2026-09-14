# 权威结果表 (single source of truth)

> **本文件由 `experiments/build_results_table.py` 生成, 请勿手改。**
> 每个数字都必须能追到「脚本 + CSV」; 追不到的一律进第 7 节并标注原因。
> README 的指标一律引用本表 —— 口径冲突时以本表为准。

## 1. 为什么需要这张表 (2026-09-14 审计)

这张表存在的理由, 来自两次真实发生过的错误:

| 错误 | 语料 | 病灶 | 出处 |
|---|---|---|---|
| 同一指标名 `8-split` 指两种协议 | 校园照片 | 一个是「8 个 seed 各做一次按源图 holdout」, 一个是「GroupKFold(8) 的 OOF」 | README vs 论文稿第 5 章 (该稿 2026-09-14 已随 thesis/ 删除) |
| 11 维结果被标成 53 维 | BOSSbase | `sota_compare.py` 静默降级到可用列, 产物却仍写 53d | 曾被论文原样引用 |
| `clean_jpeg` 行错用独立 photo_id | 校园照片 | 414 行副本各占一个 photo_id, 让「按源图划分」失效; 旧口径 143d AUC 0.8946 / 弱档检出 85.3%, 修正后 0.7555 / 44.2% | 2026-09-14 审计发现 |

前两条靠**语料**与**协议**成为必填字段来堵; 第三条(源图泄漏)靠「按源图分组的不变量校验」来堵 —— 生产者(`train_deploy_models.py`) 与语料生成器(`add_jpeg_clean.py`) 都会在训练前拒绝破坏分组不变量的语料。

## 2. 语料 (corpus)

| corpus | 说明 | 数据文件 | 规模 |
|---|---|---|---|
| bossbase_npz | BOSSbase 1.01 (npz 子集) — 领域标准基准 | gpu/data/imageset_bossbase.npz  ->  data/dataset_bossbase_npz_v2.csv | 2000 张源图 x 5 变体 (1 干净 + 4 含密) = 10000 样本; 验证 400 源图 |
| bossbase_csv | BOSSbase 1.01 (CSV 全量) — 与 npz 子集不同源, 仅附录 | data/dataset_bossbase.csv | 10000 张源图 x 7 变体 = 70000 样本 |
| campus_v2_jpeg | 校园照片 (自建语料) — 比 BOSSbase 容易, 只可进附表 | data/dataset_campus_v2_jpeg.csv | 414 张校园照片 x 14 (12 档嵌入 + 2 干净) = 5796 样本 |
| campus_v1 | 校园照片 v1 (历史) — 6 档、11 维时代的语料 | data/dataset.csv | 2898 样本 (414 干净 + 2484 含密, 6 档) |
| merged_campus_bossbase | 校园 + BOSSbase 合并 — 混合语料, 只用于 GPU 管线记录 | gpu/data/imageset.npz 等 (无 CSV 产物) | 414 + 10000 源图 = 52070 样本 |
| campus_imageset | 校园照片 GPU 特征集 — 414 源图 x 5 变体 (11 维管线用) | gpu/data/imageset_photobase.npz | 2070 样本 (1 干净 + 4 含密/源图), 512x512 |
| ood_real_jpeg | OOD 真实干净照片 (无嵌入) — 误报率评估集 | data/campus_jpg + data/external/{div2k/DIV2K_valid_HR,alaska2} | campus 414 + DIV2K 100 + ALASKA#2 子集; DIV2K 公开可下载, ALASKA#2 需 Kaggle 凭据, 详见 experiments/ood_eval.py |

**不同语料的数字不可比较。** 同一个 143d 模型在 BOSSbase 上是 0.8062, 在自建校园语料上是 0.8939 —— 差值反映的是**语料**, 不是模型变强了。两个语料的负样本构成也不同 (校园语料含 414 张真实 JPEG 干净图)。

## 3. 协议 (protocol)

| protocol_id | 含义 |
|---|---|
| holdout_by_photo | 按源图 holdout; 同一源图的全部变体落同一侧 |
| holdout_by_photo_seed0 | 按源图 holdout, test_size=0.25, seed=0 (模型元数据里的 held_out_auc) |
| holdout_by_photo_8seed | 同上的 8 个 seed (0..7) 取均值 ± 标准差 = README 的「8-split 平均 AUC」 |
| groupkfold8_oof | 按源图 GroupKFold(8) 的 out-of-fold AUC; 不是「8-split 随机划分」 |
| groupkfold5_oof_3seed | 按源图 GroupKFold(5) 的 OOF AUC, 3 个 seed 取均值 |
| groupkfold5_oof_8seed | 按源图 GroupKFold(5) 的 OOF AUC, 8 个 seed 取均值 |
| groupkfold5_oof | 按源图 5 折 GroupKFold 的 OOF AUC |
| cnn_holdout_tta5 | CNN holdout, 5-crop TTA; 与 LGB 基线共用同一份按源图划分 |
| ood_clean_fp | OOD 干净真实照片上的误报率 (判据 = 概率 >= 模型 payload 阈值), Wilson 95% CI |
| gpu_pipeline_lr | GPU 特征管线 + LR, 按源图 80/20 (gpu/train_ml_gpu.py) |
| train_model_holdout | src/train_model.py: 按源图 GroupShuffleSplit(test_size=0.25, seed=0) + 5 折 OOF stacking |
| none | 无协议信息 (不可溯源) |

划分与评估一律**按源图分组**: 同一张源图派生的干净图与含密变体必须落在同一侧, 否则模型只要认出源图内容就能刷高 AUC (源图泄漏)。置信区间按**源图**重采样, 不能按图 —— 同源样本高度相关, 按图重采样会把有效样本量当成 5 倍。

## 4. 主表: BOSSbase 1.01 — README 头条只允许引用本节

| 模型 | 特征集 | 维数 | AUC | 95% CI | 协议 |
|---|---|---|---|---|---|
| `LGB-11d` | 11d | 11 | **0.7128** | [0.6913, 0.736] | 按源图 holdout; 同一源图的全部变体落同一侧 |
| `LGB-143d` | 143d | 143 | **0.8062** | [0.7894, 0.8225] | 按源图 holdout; 同一源图的全部变体落同一侧 |
| `LGB-53d` | 53d | 53 | **0.7172** | [0.6943, 0.7406] | 按源图 holdout; 同一源图的全部变体落同一侧 |
| `xunet` | raw pixels | 8.4M params | **0.5007** | [0.5004, 0.5012] | CNN holdout, 5-crop TTA; 与 LGB 基线共用同一份按源图划分 |
| `yenet` | raw pixels | 30 SRM fixed + conv | **0.9541** | [0.9463, 0.963] | CNN holdout, 5-crop TTA; 与 LGB 基线共用同一份按源图划分 |
| `GPU pipeline LR (v1)` | v1 (11d) | 11 | **0.6438** | — | GPU 特征管线 + LR, 按源图 80/20 (gpu/train_ml_gpu.py) |

同一份按源图划分下 CNN 与 LGB 基线的对比 (`sota_table.csv`, 置信区间按源图 bootstrap 1000 次):

- `xunet`: 未收敛: 训练集 AUC=0.5005 与随机猜测无异, 不可作为「CNN 弱于手工特征」的证据
- `GPU pipeline LR (v1)`: srm_preprocess=False; acc=0.655; thr=0.798272; device=cuda; 模型 models/_audit_gpu_bossbase.joblib

> LGB 在 BOSSbase 上的 0.71~0.81 不是「模型没调好」, 而是该基准上弱密度嵌入本来就极难检测 —— 这正是文献把它当基准的原因。其中 143d 从 0.7529 升到 0.8062 是 2026-09-14 修复 SRM 特征尺度(GPU 端曾把像素先 /255, 与推理端的 CPU 特征不一致) 带来的真实收益。

## 5. OOD 真实干净照片的误报率 (部署最关心的一栏)

| 模型 | 来源 | 配置 | n | 误报率 | 95% CI |
|---|---|---|---|---|---|
| `LGB-143d` | ALL | deploy | 1514 | **9.58%** | [0.082, 0.1116] |
| `LGB-143d` | alaska | deploy | 1000 | **6.60%** | [0.0522, 0.0831] |
| `LGB-143d` | campus | deploy | 414 | **6.76%** | [0.0472, 0.096] |
| `LGB-143d` | div2k | deploy | 100 | **51.00%** | [0.4135, 0.6058] |
| `LGB-143d` | ALL | clip 5σ | 1514 | **9.58%** | [0.082, 0.1116] |
| `LGB-143d` | alaska | clip 5σ | 1000 | **6.60%** | [0.0522, 0.0831] |
| `LGB-143d` | campus | clip 5σ | 414 | **6.76%** | [0.0472, 0.096] |
| `LGB-143d` | div2k | clip 5σ | 100 | **51.00%** | [0.4135, 0.6058] |
| `LGB-53d` | ALL | deploy | 1514 | **28.86%** | [0.2664, 0.312] |
| `LGB-53d` | alaska | deploy | 1000 | **36.00%** | [0.3308, 0.3902] |
| `LGB-53d` | campus | deploy | 414 | **7.25%** | [0.0512, 0.1016] |
| `LGB-53d` | div2k | deploy | 100 | **47.00%** | [0.3751, 0.5671] |
| `LGB-53d` | ALL | clip 5σ | 1514 | **28.86%** | [0.2664, 0.312] |
| `LGB-53d` | alaska | clip 5σ | 1000 | **36.00%** | [0.3308, 0.3902] |
| `LGB-53d` | campus | clip 5σ | 414 | **7.25%** | [0.0512, 0.1016] |
| `LGB-53d` | div2k | clip 5σ | 100 | **47.00%** | [0.3751, 0.5671] |

语料是**无嵌入的干净真实照片** (校园 414 + DIV2K 100 + ALASKA#2 子集 1000), 判据与部署一致 (概率 >= 模型 payload 阈值), 区间为 Wilson 95% CI。
- `deploy` = GUI/CLI 默认路径 (`get_predictor()` 的 `clip_outliers=False`); `clip 5σ` = 文档里的抗分布偏移缓解手段。
- **实测两者误报数完全相同** (16 个格子逐一相同): 5σ 裁剪在训练集方差较大时几乎不生效, 中位概率只有千分位变化。也就是说这个「缓解手段」目前没有实际作用, 不应再当作 OOD 防护来宣传。
- DIV2K (2K 高清 PNG 缩到 512) 是主要失分来源 —— 两个模型在其上误报 都在一半左右; 真实相机 JPEG (campus/ALASKA#2) 上 143d 仅 6.6~6.8%。

## 6. 附表: 校园照片语料 (自建语料; 与 BOSSbase 不可并列)

### 6.1 部署模型 (`experiments/train_deploy_models.py` 现场产出)

| 模型 | 维数 | AUC | 协议 |
|---|---|---|---|
| `LGB-143d` | 143 | 0.8939 | holdout_by_photo_seed0 |
| `LGB-53d` | 53 | 0.8391 | holdout_by_photo_seed0 |
| `LGB-143d` | 143 | 0.8980 | holdout_by_photo_8seed |
| `LGB-53d` | 53 | 0.8461 | holdout_by_photo_8seed |

弱档检出率 (Youden 阈值, 验证集):

| 模型 | 档位 | 检出率 |
|---|---|---|
| `LGB-143d` | nsF5 p3 d=0.25 (弱档) | 0.5000 |
| `LGB-143d` | nsF5 p2 d=0.35 | 0.7115 |
| `LGB-143d` | matrix p3 d=0.40 | 0.7404 |
| `LGB-53d` | nsF5 p3 d=0.25 (弱档) | 0.4135 |
| `LGB-53d` | nsF5 p2 d=0.35 | 0.4615 |
| `LGB-53d` | matrix p3 d=0.40 | 0.6250 |

部署阈值 (写入模型 payload):

| 模型 | 指标 | 值 | 说明 |
|---|---|---|---|
| `LGB-143d` | threshold_low_fp | 0.9832 | 验证集 FP<=10% 的最低阈值 (GUI「严格」档) |
| `LGB-143d` | threshold_youden | 0.9493 | 验证集 Youden 点; 写入模型 payload 供 ml_predict 使用 |
| `LGB-53d` | threshold_low_fp | 0.9845 | 验证集 FP<=10% 的最低阈值 (GUI「严格」档) |
| `LGB-53d` | threshold_youden | 0.9595 | 验证集 Youden 点; 写入模型 payload 供 ml_predict 使用 |

### 6.2 特征消融与分类器对比

| 特征子集 | 维数 | OOF AUC (8 seed 均值) |
|---|---|---|
| `LGB 1_B11` | 11 | 0.8708 |
| `LGB 2_B11+P20` | 31 | 0.8665 |
| `LGB 3_B11+P20+LP20` | 51 | 0.8516 |
| `LGB 4_B11+P20+LP20+T2` | 53 | 0.8513 |
| `LGB 5_FULL143` | 143 | 0.9010 |

分类器 x 特征子集 (5 折 GroupKFold OOF, 3 seed 均值):

| 特征子集 | LGB | LR | RF | XGB |
|---|---|---|---|---|
| 143d_Full | 0.9014 | 0.9239 | 0.8663 | 0.9002 |
| 53d_Interpretable | 0.8520 | 0.8633 | 0.7961 | 0.8465 |
| B11 | 0.8717 | 0.8472 | 0.8549 | 0.8707 |
| B11+P20 | 0.8661 | 0.8661 | 0.8466 | 0.8652 |
| B11+P20+LP20 | 0.8520 | 0.8627 | 0.7978 | 0.8463 |

按源图 GroupKFold(8) 的 OOF (注意: **不是**「8-split 随机划分」):

| 模型 | 维数 | OOF AUC | 备注 |
|---|---|---|---|
| `LGB-143d` | 143 | 0.8966 | 8 折 OOF 均值, std=0.018; 与 holdout_by_photo_8seed 不是一回事 |
| `LGB-53d` | 53 | 0.8470 | 8 折 OOF 均值, std=0.0166; 与 holdout_by_photo_8seed 不是一回事 |

### 6.3 特征重要性 (LightGBM gain, 当前口径)

| 模型 | 特征组 | gain 占比 % |
|---|---|---|
| `143d` | SRM 90 | 52.57 |
| `143d` | BASE 11 | 20.67 |
| `143d` | LSB PREFIX 20 | 20.61 |
| `143d` | PREFIX 20 | 6.15 |
| `143d` | TEXTURE/EST 2 | 0.0 |
| `53d` | BASE 11 | 47.61 |
| `53d` | LSB PREFIX 20 | 41.78 |
| `53d` | PREFIX 20 | 10.6 |
| `53d` | TEXTURE/EST 2 | 0.01 |

由 `experiments/gain_importance.py` 现场训练并导出 (`gain_importance.csv` / `gain_importance_53d.csv`)。旧版按 gain 占比得出的「SRM 是噪声特征」结论产生于错误的 SRM 尺度, 已在这套新数字下作废。


## 7. 不可溯源的行 (引用时必须注明)

**本节当前为空。** 2026-09-14 的审计把此前所有「只打印不落盘」的数字都补上了生产者并重跑: GPU 管线 (`gpu_pipeline_metrics.csv`)、train_model 家族 (`train_model_metrics.csv`)、OOD 误报 (`ood_summary.csv`)、特征重要性 (`gain_importance*.csv`)。若某次重跑缺失, 对应行会自动以 `traceable=no` 出现在这里, 而不是凭空消失。

## 8. 可以 / 不可以比较

- ✅ 同一 corpus + 同一 protocol_id 的行之间可以比较 (如 BOSSbase 上 Ye-Net 0.9541 vs LGB-143d 0.8062)。
- ✅ 同一 corpus 上, 用**同一种**协议比较不同特征集 / 分类器。
- ❌ 校园语料 vs BOSSbase 的 AUC 不能并列 (语料难度不同)。
- ❌ `groupkfold8_oof` 与 `holdout_by_photo_8seed` 不能互相引用 (两者都带 8, 但一个是 8 折 OOF、一个是 8 个随机划分)。
- ❌ 任何 `traceable=no` 的行进入论文正文而不加说明。

## 9. 重新生成

```bash
python experiments/train_deploy_models.py   # 产 deploy_model_metrics.csv
python experiments/ood_eval.py              # 产 ood_summary.csv
python experiments/gain_importance.py       # 产 gain_importance*.csv
python experiments/build_results_table.py   # 合并成这张表
python experiments/build_results_table.py --check   # 校验本文档是否同步
```
输入 CSV 大多不入库 (见 .gitignore): 脚本在缺产物时会跳过对应区块并打印原因, 不会静默少行。

