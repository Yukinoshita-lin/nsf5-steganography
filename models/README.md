# 部署模型与模型卡

这个目录里只有**两个** `.joblib` 是随仓库分发的（其余是本地训练产物，见文末）。
两个模型都是 `lightgbm.LGBMClassifier` 的 pickle，由
`experiments/train_deploy_models.py` 现场训练得到，`src/ml_predict.py` 加载。

| 文件 | 模型卡 | 角色 |
|---|---|---|
| `stego_classifier.joblib` | [`stego_classifier.card.json`](stego_classifier.card.json) | **143d 默认版**：`MLPredictor()` 不指定路径时加载的就是它 |
| `stego_classifier_v2_jpeg_lgb_51d.joblib` | [`stego_classifier_v2_jpeg_lgb_51d.card.json`](stego_classifier_v2_jpeg_lgb_51d.card.json) | **53d 可解释版**：教学/答辩用，需显式 `model_path=...` |

每张模型卡是一份入库的 JSON，写着：语料与协议、held-out / 8-split 指标、
各个嵌入档的检出率、真实照片上的误报率、跨语料（BOSSbase）参考值、
**特征列表与顺序**、超参、训练环境、git 版本、适用边界与已知局限、以及
该 `.joblib` 的 `sha256`。

## 校验：模型卡不会和二进制脱钩

卡片与模型是**硬绑定**的（sha256）。任何一个 `.joblib` 被替换、或 payload 里的
阈值/特征/超参被改，校验就会失败：

```bash
python experiments/model_card.py --check   # 等价于 CI 里 pytest 跑的那一步
python -m pytest -q src/test_model_cards.py
```

重新生成（模型重训之后）：

```bash
python experiments/model_card.py           # 或 make model-cards
```

指标值来自 `experiments/data/deploy_model_metrics.csv` 与
`experiments/data/ood_summary.csv` —— 这两份 CSV 是产物、不入库。因此：
**本地有数据时**校验会逐项核对卡片里的指标；**CI 上没有数据时**这部分明确
打印 `[skip]` 跳过，但 sha256 与 payload 的核对照做（那部分只依赖入库文件）。
`--check` 从不把"没数据"当成"通过"。

## 复现

```bash
# 语料: 414 张校园照片 x 12 档嵌入 + 414 张 JPEG 干净图 = 5796 样本
python experiments/add_jpeg_clean.py             # 若语料不存在
python experiments/train_deploy_models.py        # 训练 + 8-split 评估 + 落盘 + 刷新模型卡
python experiments/ood_eval.py                   # 真实干净照片上的误报率（约 2 分钟）
python experiments/build_results_table.py        # 唯一权威结果表 docs/RESULTS.md
```

生产者在写盘后会自己调用 `model_card.py`，所以"训练完忘了更新卡"这件事不会发生。

## 引用这两个模型时请注意

- **头条数字要用 BOSSbase 的**：143d 0.8062 / 53d 0.7172（`docs/RESULTS.md` 第 4 节）。
  仓库 README 与模型卡里更高的 0.8939 / 0.8391 来自**自建校园语料**，更容易，
  两者不可并列。
- **这不是取证工具**：143d 在 1514 张公开真实干净照片上有 9.58% 的误报
  （53d 是 28.86%），DIV2K 那 100 张更是到了 51%。它适合做单图辅助判读与批量
  排序，不适合单独定案。
- **输入口径固定**：灰度（亮度）→ LANCZOS 512×512，与语料一致。彩色输入曾经
  取的是红通道而不是亮度，导致训练/推理偏差，2026-09-15 修正（见 CHANGELOG 1.6.9）。

## 目录里其余的模型文件

`models/` 下还有作者本地留下的历史训练产物（`stego_classifier_v2_jpeg_*.joblib`、
`cnn_*.pt` 等）。它们**不入库**（见 `.gitignore`），也不在任何发布路径上；
`stego_classifier_v2_jpeg_xgb_tuned.bak.joblib` 与 `_weak3_stack.joblib` 是
README 提到的场景切换备份。要清理它们不影响项目功能。
