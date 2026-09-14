"""
experiments/build_results_table.py — 项目唯一权威结果表的生成器。

为什么需要它
------------
同一个指标名在不同文档里出现过互相矛盾的数字: README 头部的
「8-split 平均 AUC = 0.9085」来自校园照片语料, 而当时的论文稿第 5 章里
「8 split 平均 AUC = 0.9853」来自同一批校园照片、但用的是 GroupKFold(8) 的
OOF 协议 (该论文稿已于 2026-09-14 随 thesis/ 一并删除, 这里保留数字作为
审计记录)。名字一样, 语料和协议不同 —— 这正是评审最容易判定为「数据不可信」
的地方, 而且这个错误在 2026-09 之前真实发生过一次 (11 维结果被标成 53 维
写进论文, 见 experiments/sota_compare.py 的文件头)。

修法不是改数字, 而是把**语料 (corpus)** 和**协议 (protocol)** 提升为每一行的
一等公民, 并让 README 只引用本表, 由本表规定哪个数字可以当头条。

产出
----
1. `experiments/data/results_canonical.csv` — 机器可读的合并表 (产物, 不入库)
2. `docs/RESULTS.md`                       — 人读的权威表 (入库, 无易变字段)

规则
----
- 只收录**能追到脚本 + CSV** 的数字; 追不到的一律标 traceable=no 并写明原因。
  这是项目自己的规矩: 「论文里的每一张图、每一个数字, 都应该能追到哪个脚本、
  读哪个 CSV」(experiments/README.md)。
- 不同语料的数字**不放进同一张表做比较**, 只并列陈述; 见 docs/RESULTS.md 第 8 节。
- README 头条只允许用 BOSSbase 1.01 (领域标准基准) 的数字; 校园语料是自建语料,
  数字更高但**更容易**, 只能进附表。

用法
----
    python experiments/build_results_table.py            # 生成 CSV + 文档
    python experiments/build_results_table.py --check     # 校验 docs/RESULTS.md 是否同步
    python experiments/build_results_table.py --csv-only
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(PROJ, "experiments", "data")
OUT_CSV = os.path.join(DATA, "results_canonical.csv")
OUT_DOC = os.path.join(PROJ, "docs", "RESULTS.md")

# ------------------------------------------------------------------ 语料登记
# README 只允许用 headline=True 的语料做头条。
CORPORA = {
    "bossbase_npz": dict(
        label="BOSSbase 1.01 (npz 子集) — 领域标准基准",
        file="gpu/data/imageset_bossbase.npz  ->  data/dataset_bossbase_npz_v2.csv",
        detail="2000 张源图 x 5 变体 (1 干净 + 4 含密) = 10000 样本; 验证 400 源图",
        headline=True),
    "bossbase_csv": dict(
        label="BOSSbase 1.01 (CSV 全量) — 与 npz 子集不同源, 仅附录",
        file="data/dataset_bossbase.csv",
        detail="10000 张源图 x 7 变体 = 70000 样本",
        headline=False),
    "campus_v2_jpeg": dict(
        label="校园照片 (自建语料) — 比 BOSSbase 容易, 只可进附表",
        file="data/dataset_campus_v2_jpeg.csv",
        detail="414 张校园照片 x 14 (12 档嵌入 + 2 干净) = 5796 样本",
        headline=False),
    "campus_v1": dict(
        label="校园照片 v1 (历史) — 6 档、11 维时代的语料",
        file="data/dataset.csv",
        detail="2898 样本 (414 干净 + 2484 含密, 6 档)",
        headline=False),
    "merged_campus_bossbase": dict(
        label="校园 + BOSSbase 合并 — 混合语料, 只用于 GPU 管线记录",
        file="gpu/data/imageset.npz 等 (无 CSV 产物)",
        detail="414 + 10000 源图 = 52070 样本",
        headline=False),
    "campus_imageset": dict(
        label="校园照片 GPU 特征集 — 414 源图 x 5 变体 (11 维管线用)",
        file="gpu/data/imageset_photobase.npz",
        detail="2070 样本 (1 干净 + 4 含密/源图), 512x512",
        headline=False),
    "ood_real_jpeg": dict(
        label="OOD 真实干净照片 (无嵌入) — 误报率评估集",
        file="data/campus_jpg + data/external/{div2k/DIV2K_valid_HR,alaska2}",
        detail="campus 414 + DIV2K 100 + ALASKA#2 子集; DIV2K 公开可下载, "
               "ALASKA#2 需 Kaggle 凭据, 详见 experiments/ood_eval.py",
        headline=False),
}

# ------------------------------------------------------------------ 协议登记
PROTOCOLS = {
    "holdout_by_photo": "按源图 holdout; 同一源图的全部变体落同一侧",
    "holdout_by_photo_seed0": "按源图 holdout, test_size=0.25, seed=0 (模型元数据里的 held_out_auc)",
    "holdout_by_photo_8seed": "同上的 8 个 seed (0..7) 取均值 ± 标准差 = README 的「8-split 平均 AUC」",
    "groupkfold8_oof": "按源图 GroupKFold(8) 的 out-of-fold AUC; 不是「8-split 随机划分」",
    "groupkfold5_oof_3seed": "按源图 GroupKFold(5) 的 OOF AUC, 3 个 seed 取均值",
    "groupkfold5_oof_8seed": "按源图 GroupKFold(5) 的 OOF AUC, 8 个 seed 取均值",
    "groupkfold5_oof": "按源图 5 折 GroupKFold 的 OOF AUC",
    "cnn_holdout_tta5": "CNN holdout, 5-crop TTA; 与 LGB 基线共用同一份按源图划分",
    "ood_clean_fp": "OOD 干净真实照片上的误报率 (判据 = 概率 >= 模型 payload 阈值), Wilson 95% CI",
    "gpu_pipeline_lr": "GPU 特征管线 + LR, 按源图 80/20 (gpu/train_ml_gpu.py)",
    "train_model_holdout": "src/train_model.py: 按源图 GroupShuffleSplit(test_size=0.25, seed=0) + 5 折 OOF stacking",
    "none": "无协议信息 (不可溯源)",
}

COLS = ["corpus", "corpus_label", "dataset_file", "protocol_id", "protocol",
        "model", "subject", "family", "feat_set", "n_features", "n_samples", "n_photos",
        "metric", "value", "ci_lo", "ci_hi", "ci_method",
        "source_file", "traceable", "producer", "note"]


def _row(corpus, model, metric, value, *, subject="overall", protocol_id="none",
         family="handcrafted",
         feat_set="", n_features="", n_samples="", n_photos="", ci_lo="", ci_hi="",
         ci_method="", source_file="", traceable="yes", producer="", note=""):
    c = CORPORA[corpus]
    return dict(corpus=corpus, corpus_label=c["label"], dataset_file=c["file"],
                protocol_id=protocol_id, protocol=PROTOCOLS[protocol_id],
                model=model, subject=subject, family=family, feat_set=feat_set,
                n_features=n_features,
                n_samples=n_samples, n_photos=n_photos, metric=metric, value=value,
                ci_lo=ci_lo, ci_hi=ci_hi, ci_method=ci_method,
                source_file=source_file, traceable=traceable,
                producer=producer, note=note)


def _read(name: str, required: bool = False):
    """读一个实验产物 CSV。缺失时返回 None 并打印原因 (绝不静默少行)。"""
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        msg = f"  [跳过] {name} 不存在"
        if required:
            msg += " — 先跑 experiments/train_deploy_models.py"
        print(msg)
        return None
    return pd.read_csv(p)


# 这些产物是文档主体的来源。它们都不入库 (.gitignore), 因此 CI / 新 clone 里
# 通常拿不到 —— 此时只能校验 "行级契约", 不能校验文档是否同步。
PRIMARY_SOURCES = ("sota_table.csv", "deploy_model_metrics.csv", "ablation_5stage.csv",
                   "model_compare_4clf_summary.csv", "8split_comparison.csv")


def inputs_present() -> bool:
    """主表的输入产物是否齐备 (决定能不能做文档同步校验)。"""
    return all(os.path.exists(os.path.join(DATA, n)) for n in PRIMARY_SOURCES)


def rows_bossbase() -> list:
    """主表: BOSSbase, CNN 与 LGB 共用同一份按源图划分 (sota_table.csv)。"""
    df = _read("sota_table.csv")
    if df is None:
        return []
    out = []
    for _, r in df.iterrows():
        proto = "cnn_holdout_tta5" if r["family"] == "cnn" else "holdout_by_photo"
        corpus = "bossbase_npz" if r["dataset"] == "bossbase_npz" else "bossbase_csv"
        note = ""
        if r["model"] == "xunet":
            # 训练集 AUC 也是 0.50 说明是「未收敛」而不是「过拟合」, 更不能当作
            # 「CNN 不如手工特征」的证据 —— 论文里已经这么写了, 表里也必须带上。
            note = ("未收敛: 训练集 AUC=0.5005 与随机猜测无异, "
                    "不可作为「CNN 弱于手工特征」的证据")
        out.append(_row(
            corpus, r["model"], "auc", round(float(r["auc"]), 4),
            protocol_id=proto, family=r["family"], feat_set=r["feat_set"],
            n_features=r["n_features"], n_samples=r.get("n_train", ""),
            n_photos=r.get("n_test_photos", ""),
            ci_lo=r.get("auc_lo", ""), ci_hi=r.get("auc_hi", ""),
            ci_method=r.get("ci_method", ""),
            source_file=r.get("source_file", "sota_table.csv"),
            producer="experiments/sota_compare.py + experiments/merge_sota_table.py",
            note=note))
        train_auc = r.get("train_auc", "")
        if pd.notna(train_auc) and str(train_auc) != "":
            out.append(_row(
                corpus, r["model"], "train_auc", round(float(train_auc), 4),
                protocol_id=proto, family=r["family"], feat_set=r["feat_set"],
                n_features=r["n_features"], n_photos=r.get("n_val", ""),
                source_file="sota_table.csv",
                producer="experiments/eval_cnn_checkpoint.py",
                note=note))
    return out


def rows_deploy() -> list:
    """附表: 校园语料上两个**部署模型**的指标 (由生产者脚本现场产出)。"""
    df = _read("deploy_model_metrics.csv", required=True)
    if df is None:
        return []
    out = []
    missing_splits = []
    for _, r in df.iterrows():
        name = f"LGB-{r['feature_set']}"
        base = dict(family="handcrafted (deployed)", feat_set=str(r["feature_set"]),
                    n_features=r["n_features"],
                    n_samples=int(r["n_train"]) + int(r["n_val"]),
                    n_photos=r["n_photos"], source_file="deploy_model_metrics.csv",
                    producer="experiments/train_deploy_models.py")
        out.append(_row("campus_v2_jpeg", name, "auc", round(float(r["auc_held_out"]), 4),
                        protocol_id="holdout_by_photo_seed0", **base,
                        note=f"部署模型 {r['model_file']} 的 held_out_auc"))
        if pd.notna(r.get("auc_8split_mean", "")) and str(r["auc_8split_mean"]) != "":
            out.append(_row("campus_v2_jpeg", name, "auc",
                            round(float(r["auc_8split_mean"]), 4),
                            protocol_id="holdout_by_photo_8seed", **base,
                            note=f"README 所称「8-split 平均 AUC」; std={r['auc_8split_std']}"))
        else:
            missing_splits.append(str(r["model"]))
        for col, label in (("det_nsf5_p3_d025", "nsF5 p3 d=0.25 (弱档)"),
                           ("det_nsf5_p2_d035", "nsF5 p2 d=0.35"),
                           ("det_matrix_p3_d040", "matrix p3 d=0.40")):
            v = r.get(col, "")
            if pd.notna(v) and str(v) != "":
                out.append(_row("campus_v2_jpeg", name, "detection_rate",
                                round(float(v), 4), subject=label,
                                protocol_id="holdout_by_photo_seed0", **base,
                                note=label))
        # 阈值本身也是被测对象: 部署时「严格」档用的就是 threshold_low_fp
        out.append(_row("campus_v2_jpeg", name, "threshold_youden",
                        round(float(r["threshold_youden"]), 4), subject="youden",
                        protocol_id="holdout_by_photo_seed0", **base,
                        note="验证集 Youden 点; 写入模型 payload 供 ml_predict 使用"))
        out.append(_row("campus_v2_jpeg", name, "threshold_low_fp",
                        round(float(r["threshold_low_fp"]), 4), subject="fp<=10%",
                        protocol_id="holdout_by_photo_seed0", **base,
                        note="验证集 FP<=10% 的最低阈值 (GUI「严格」档)"))
    if missing_splits:
        print(f"  [警告] {', '.join(missing_splits)} 的 8-split 均值缺失 —— "
              f"README 引用的 8-split 数字将失去支撑; "
              f"完整跑一次 experiments/train_deploy_models.py (不带 --no-splits)")
    return out


def rows_campus_appendix() -> list:
    """附表: 校园语料上的消融 / 分类器对比 / GroupKFold-8 OOF。"""
    out = []

    df = _read("ablation_5stage.csv")
    if df is not None:
        for _, r in df.iterrows():
            out.append(_row(
                "campus_v2_jpeg", f"LGB {r['stage']}", "auc",
                round(float(r["auc_mean"]), 4), protocol_id="groupkfold5_oof_8seed",
                feat_set=str(r["stage"]), n_features=int(r["n_feat"]),
                source_file="ablation_5stage.csv",
                producer="experiments/ablation_5stage.py",
                note=f"8 seed 均值; min={r['auc_min']} max={r['auc_max']}"))

    df = _read("model_compare_4clf_summary.csv")
    if df is not None:
        for _, r in df.iterrows():
            out.append(_row(
                "campus_v2_jpeg", f"{r['model']} {r['stage']}", "auc",
                round(float(r["auc_mean"]), 4), protocol_id="groupkfold5_oof_3seed",
                family=str(r["model"]), feat_set=str(r["stage"]),
                source_file="model_compare_4clf_summary.csv",
                producer="experiments/model_compare_4clf.py",
                note=f"3 seed 均值; std={r['auc_std']}"))

    df = _read("8split_comparison.csv")
    if df is not None:
        for _, r in df.iterrows():
            for tag, mean, std in (("143d", r["mean_143d"], r["std_143d"]),
                                   ("53d", r["mean_53d"], r["std_53d"])):
                out.append(_row(
                    "campus_v2_jpeg", f"LGB-{tag}", "auc", round(float(mean), 4),
                    protocol_id="groupkfold8_oof", feat_set=tag,
                    n_features=143 if tag == "143d" else 53,
                    source_file="8split_comparison.csv",
                    producer="experiments/_8split_compare.py",
                    note=f"8 折 OOF 均值, std={std}; 与 holdout_by_photo_8seed 不是一回事"))
    return out


def rows_untraceable() -> list:
    """历史上"只打印不落盘"的数字 —— 一旦对应生产者跑过, 就自动从这里消失。

    2026-09-14: 上列的每一项都补上了生产者并重跑 (gpu/train_ml_gpu.py 落盘、
    src/train_model.py 落盘、experiments/ood_eval.py 重建 OOD 评估)。
    这里保留动态判定而不是直接删列表: 若某次重跑没做, 老数字仍会以
    traceable=no 出现, 而不是凭空消失。
    """
    gpu_reason = "gpu/train_ml_gpu.py 只把指标打到 stdout, 不落 CSV, 无产物可核对"
    ood_reason = "生产者与 data/ood_jpeg_test/ 已丢失 (2026-09-14 由 experiments/ood_eval.py 重建)"
    tm_reason = "指标只出现在 README 正文, 当时的训练未落盘"
    traced = {
        "gpu": os.path.exists(os.path.join(DATA, "gpu_pipeline_metrics.csv")),
        "ood": os.path.exists(os.path.join(DATA, "ood_summary.csv")),
        "tm": os.path.exists(os.path.join(DATA, "train_model_metrics.csv")),
    }
    # (组, 语料, 条目, 数值, 指标, 为什么不可追溯)
    spec = [
        ("gpu", "campus_v2_jpeg", "GPU 统计特征管线", "0.790", "auc", gpu_reason),
        ("gpu", "bossbase_npz", "GPU 统计特征管线 (单跑)", "0.644", "auc", gpu_reason),
        ("gpu", "merged_campus_bossbase", "GPU 统计特征管线 (合并训练)", "0.712", "auc",
         gpu_reason + "; 52070 样本"),
        ("tm", "campus_v1", "v1 XGB (11d)", "0.7435", "auc",
         "data/dataset.csv 11 维 6 档; " + tm_reason),
        ("tm", "campus_v2_jpeg", "v2 XGB tuned", "0.8889", "auc",
         "网格调优; " + tm_reason),
        ("tm", "campus_v2_jpeg", "v2 XGB + WEAK_WEIGHT=3", "0.8534", "auc",
         "弱档加权实验; " + tm_reason),
        ("tm", "campus_v2_jpeg", "v2 STACK (WEAK_WEIGHT=3)", "0.8321", "auc",
         "4 模型 LR meta; " + tm_reason),
        ("ood", "campus_v2_jpeg", "143d OOD 干净 JPEG 误报 (部署模型)", "1/8",
         "false_positive_count", ood_reason),
        ("ood", "campus_v2_jpeg", "53d OOD 干净 JPEG 误报 (部署模型)", "3/8",
         "false_positive_count", ood_reason),
    ]
    return [_row(corpus, name, metric, val, source_file="README.md (正文)",
                 traceable="no", producer="—", note=note)
            for group, corpus, name, val, metric, note in spec if not traced[group]]


def rows_ood() -> list:
    """OOD 真实干净照片上的误报率 (experiments/ood_eval.py 现场产出)。"""
    df = _read("ood_summary.csv", required=True)
    if df is None:
        return []
    out = []
    for _, r in df.iterrows():
        label = f"LGB-{r['model']}"
        clip = bool(r["clip_outliers"])
        out.append(_row(
            "ood_real_jpeg", label, "false_positive_rate", round(float(r["fp_rate"]), 4),
            subject=f"{r['source']} / clip={clip}",
            protocol_id="ood_clean_fp",
            family="handcrafted (deployed)", feat_set=str(r["model"]),
            n_samples=int(r["n_photos"]), ci_lo=r["fp_ci_lo"], ci_hi=r["fp_ci_hi"],
            ci_method="Wilson 95% CI",
            source_file="ood_summary.csv",
            producer="experiments/ood_eval.py",
            note=("部署默认 (GUI/CLI 的 get_predictor 默认 clip_outliers=False)"
                  if not clip else "文档里的抗分布偏移缓解手段 (特征 clip 到训练集 mu±5σ)") +
                 f"; 误报 {int(r['n_false_positive'])}/{int(r['n_photos'])}; "
                 f"median prob={r['median_prob']}"))
    return out


def rows_gpu_pipeline() -> list:
    """GPU 特征管线 (11 维 + LR) 的三个语料配置 (gpu/train_ml_gpu.py 现场产出)。"""
    df = _read("gpu_pipeline_metrics.csv", required=True)
    if df is None:
        return []
    corpus_map = [("imageset_photobase", "campus_imageset"),
                  ("imageset_bossbase", "bossbase_npz")]
    out = []
    for _, r in df.iterrows():
        ds = str(r["dataset"])
        corpus = "merged_campus_bossbase" if "+" in ds else next(
            (c for key, c in corpus_map if key == ds), "campus_imageset")
        out.append(_row(
            corpus, f"GPU pipeline {r['model']} ({r['feature_set']})", "auc",
            round(float(r["auc"]), 4), protocol_id="gpu_pipeline_lr",
            subject=f"{ds} | srm={'on' if bool(r['srm_preprocess']) else 'off'}",
            feat_set=f"{r['feature_set']} ({r['n_features']}d)",
            n_features=int(r["n_features"]), n_samples=int(r["n_samples"]),
            n_photos=int(r["n_photos"]),
            source_file="gpu_pipeline_metrics.csv",
            producer="gpu/train_ml_gpu.py",
            note=f"srm_preprocess={bool(r['srm_preprocess'])}; acc={r['acc']}; "
                 f"thr={r['threshold_youden']}; device={r['device']}; "
                 f"模型 {r['model_path']}"))
    return out


def rows_train_model() -> list:
    """src/train_model.py 的 LR/RF/GBDT/XGB/STACK 家族与其阈值 (现场产出)。"""
    df = _read("train_model_metrics.csv", required=True)
    if df is None:
        return []
    out = []
    for _, r in df.iterrows():
        ds = str(r["dataset"])
        if "campus_v2_jpeg" in ds:
            corpus = "campus_v2_jpeg"
        elif ds == "dataset.csv":
            corpus = "campus_v1"
        elif "bossbase" in ds:
            corpus = "bossbase_csv"
        else:
            corpus = "campus_v2_jpeg"
        ww = str(r.get("weak_weight", "") or "")
        note = (f"held-out acc={r['acc']} bacc={r['bacc']}; "
                f"clean FP={r['clean_fp_rate']}; stego det={r['stego_detection_rate']}; "
                f"XGB(depth={r['xgb_depth']},n={r['xgb_n_est']},lr={r['xgb_lr']}); "
                f"逐候选 held-out AUC: {r['candidates_auc']}; 模型 {r['model_path']}")
        if ww:
            note = f"WEAK_WEIGHT={ww}; " + note
        out.append(_row(
            corpus, f"train_model {r['model']}", "auc",
            round(float(r["held_out_auc"]), 4), protocol_id="train_model_holdout",
            subject=f"weak={ww or '1'} | xgb={r['xgb_depth']}/{r['xgb_n_est']}/{r['xgb_lr']}",
            feat_set=f"{r['n_features']}d", n_features=int(r["n_features"]),
            n_samples=int(r["n_samples"]), n_photos=int(r["n_photos"]),
            source_file="train_model_metrics.csv",
            producer="src/train_model.py", note=note))
    return out


def build() -> pd.DataFrame:
    rows = (rows_bossbase() + rows_ood() + rows_gpu_pipeline() + rows_train_model()
            + rows_deploy() + rows_campus_appendix() + rows_untraceable())
    df = pd.DataFrame(rows, columns=COLS)
    order = {"bossbase_npz": 0, "bossbase_csv": 1, "merged_campus_bossbase": 2,
             "campus_v2_jpeg": 3, "campus_imageset": 4, "campus_v1": 5,
             "ood_real_jpeg": 6}
    df["_o"] = df["corpus"].map(order).fillna(9)
    df["_p"] = df["protocol_id"].map({k: i for i, k in enumerate(PROTOCOLS)})
    df = df.sort_values(["_o", "_p", "model", "metric"],
                        kind="stable").drop(columns=["_o", "_p"])
    return df.reset_index(drop=True)


def _fmt_tbl(rows: list, headers: list) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out)


def render_doc(df: pd.DataFrame) -> str:
    """人读版。刻意不含日期 / git rev 等易变字段, 免得每次生成都 churn。"""
    L = []
    L.append("# 权威结果表 (single source of truth)\n")
    L.append("> **本文件由 `experiments/build_results_table.py` 生成, 请勿手改。**\n"
             "> 每个数字都必须能追到「脚本 + CSV」; 追不到的一律进第 7 节并标注原因。\n"
             "> README 的指标一律引用本表 —— 口径冲突时以本表为准。\n")

    L.append("## 1. 为什么需要这张表 (2026-09-14 审计)\n")
    L.append("这张表存在的理由, 来自两次真实发生过的错误:\n")
    L.append(_fmt_tbl(
        [["同一指标名 `8-split` 指两种协议", "校园照片",
          "一个是「8 个 seed 各做一次按源图 holdout」, 一个是「GroupKFold(8) 的 OOF」",
          "README vs 论文稿第 5 章 (该稿 2026-09-14 已随 thesis/ 删除)"],
         ["11 维结果被标成 53 维", "BOSSbase",
          "`sota_compare.py` 静默降级到可用列, 产物却仍写 53d",
          "曾被论文原样引用"],
         ["`clean_jpeg` 行错用独立 photo_id", "校园照片",
          "414 行副本各占一个 photo_id, 让「按源图划分」失效; "
          "旧口径 143d AUC 0.8946 / 弱档检出 85.3%, 修正后 0.7555 / 44.2%",
          "2026-09-14 审计发现"]],
        ["错误", "语料", "病灶", "出处"]))
    L.append("\n前两条靠**语料**与**协议**成为必填字段来堵; 第三条(源图泄漏)靠"
             "「按源图分组的不变量校验」来堵 —— 生产者"
             "(`train_deploy_models.py`) 与语料生成器"
             "(`add_jpeg_clean.py`) 都会在训练前拒绝破坏分组不变量的语料。\n")

    L.append("## 2. 语料 (corpus)\n")
    L.append(_fmt_tbl([[k, v["label"], v["file"], v["detail"]]
                       for k, v in CORPORA.items()],
                      ["corpus", "说明", "数据文件", "规模"]))
    L.append("\n**不同语料的数字不可比较。** 同一个 143d 模型在 BOSSbase 上是 "
             "0.8062, 在自建校园语料上是 0.8939 —— 差值反映的是**语料**, "
             "不是模型变强了。两个语料的负样本构成也不同 (校园语料含 414 张真实 "
             "JPEG 干净图)。\n")

    L.append("## 3. 协议 (protocol)\n")
    L.append(_fmt_tbl([[k, v] for k, v in PROTOCOLS.items()],
                      ["protocol_id", "含义"]))
    L.append("\n划分与评估一律**按源图分组**: 同一张源图派生的干净图与含密变体必须"
             "落在同一侧, 否则模型只要认出源图内容就能刷高 AUC (源图泄漏)。"
             "置信区间按**源图**重采样, 不能按图 —— 同源样本高度相关, 按图重采样"
             "会把有效样本量当成 5 倍。\n")

    bb = df[(df["corpus"] == "bossbase_npz") & (df["traceable"] == "yes")]
    L.append("## 4. 主表: BOSSbase 1.01 — README 头条只允许引用本节\n")
    if len(bb):
        rows = []
        for _, r in bb[bb["metric"] == "auc"].iterrows():
            ci = (f"[{r['ci_lo']}, {r['ci_hi']}]"
                  if str(r["ci_lo"]) not in ("", "nan") else "—")
            rows.append([f"`{r['model']}`", r["feat_set"], r["n_features"],
                         f"**{r['value']:.4f}**", ci, r["protocol"]])
        L.append(_fmt_tbl(rows, ["模型", "特征集", "维数", "AUC", "95% CI", "协议"]))
        L.append("\n同一份按源图划分下 CNN 与 LGB 基线的对比 "
                 "(`sota_table.csv`, 置信区间按源图 bootstrap 1000 次):\n")
        seen = set()
        for _, r in bb[bb["note"].astype(str).str.len() > 0].iterrows():
            if r["model"] in seen:      # auc 与 train_auc 两行共用同一条注释
                continue
            seen.add(r["model"])
            L.append(f"- `{r['model']}`: {r['note']}")
    else:
        L.append("_(未生成: 缺 `experiments/data/sota_table.csv`)_")
    L.append("\n> LGB 在 BOSSbase 上的 0.71~0.81 不是「模型没调好」, 而是该基准上"
             "弱密度嵌入本来就极难检测 —— 这正是文献把它当基准的原因。"
             "其中 143d 从 0.7529 升到 0.8062 是 2026-09-14 修复 SRM 特征尺度"
             "(GPU 端曾把像素先 /255, 与推理端的 CPU 特征不一致) 带来的真实收益。\n")

    ood = df[(df["corpus"] == "ood_real_jpeg")]
    L.append("## 5. OOD 真实干净照片的误报率 (部署最关心的一栏)\n")
    if len(ood):
        rows = []
        for _, r in ood.iterrows():
            ci = (f"[{r['ci_lo']}, {r['ci_hi']}]"
                  if str(r["ci_lo"]) not in ("", "nan") else "—")
            src, _, clip = str(r["subject"]).partition(" / ")
            rows.append([f"`{r['model']}`", src,
                         "deploy" if "False" in clip else "clip 5σ",
                         r["n_samples"], f"**{r['value']*100:.2f}%**", ci])
        L.append(_fmt_tbl(rows, ["模型", "来源", "配置", "n", "误报率", "95% CI"]))
        L.append("\n语料是**无嵌入的干净真实照片** (校园 414 + DIV2K 100 + ALASKA#2 子集 1000),"
                 " 判据与部署一致 (概率 >= 模型 payload 阈值), 区间为 Wilson 95% CI。")
        L.append("- `deploy` = GUI/CLI 默认路径 (`get_predictor()` 的 `clip_outliers=False`);"
                 " `clip 5σ` = 文档里的抗分布偏移缓解手段。")
        L.append("- **实测两者误报数完全相同** (16 个格子逐一相同): 5σ 裁剪在训练集"
                 "方差较大时几乎不生效, 中位概率只有千分位变化。也就是说这个「缓解手段」"
                 "目前没有实际作用, 不应再当作 OOD 防护来宣传。")
        L.append("- DIV2K (2K 高清 PNG 缩到 512) 是主要失分来源 —— 两个模型在其上误报"
                 " 都在一半左右; 真实相机 JPEG (campus/ALASKA#2) 上 143d 仅 6.6~6.8%。\n")
    else:
        L.append("_(未生成: 缺 `experiments/data/ood_summary.csv`, 跑 "
                 "`python experiments/ood_eval.py`)_\n")

    L.append("## 6. 附表: 校园照片语料 (自建语料; 与 BOSSbase 不可并列)\n")
    L.append("### 6.1 部署模型 (`experiments/train_deploy_models.py` 现场产出)\n")
    dep = df[(df["corpus"] == "campus_v2_jpeg") & (df["metric"] == "auc")
             & (df["family"].astype(str).str.contains("deployed"))]
    if len(dep):
        L.append(_fmt_tbl(
            [[f"`{r['model']}`", r["n_features"], f"{r['value']:.4f}", r["protocol_id"]]
             for _, r in dep.iterrows()],
            ["模型", "维数", "AUC", "协议"]))
    det = df[df["metric"] == "detection_rate"]
    if len(det):
        L.append("\n弱档检出率 (Youden 阈值, 验证集):\n")
        L.append(_fmt_tbl(
            [[f"`{r['model']}`", r["note"], f"{r['value']:.4f}"] for _, r in det.iterrows()],
            ["模型", "档位", "检出率"]))
    thr = df[df["metric"].isin(["threshold_youden", "threshold_low_fp"])]
    if len(thr):
        L.append("\n部署阈值 (写入模型 payload):\n")
        L.append(_fmt_tbl(
            [[f"`{r['model']}`", r["metric"], f"{r['value']:.4f}", r["note"]]
             for _, r in thr.iterrows()],
            ["模型", "指标", "值", "说明"]))

    L.append("\n### 6.2 特征消融与分类器对比\n")
    abl = df[(df["corpus"] == "campus_v2_jpeg")
             & (df["protocol_id"] == "groupkfold5_oof_8seed")]
    if len(abl):
        L.append(_fmt_tbl(
            [[f"`{r['model']}`", r["n_features"], f"{r['value']:.4f}"]
             for _, r in abl.iterrows()],
            ["特征子集", "维数", "OOF AUC (8 seed 均值)"]))
    cmp_ = df[(df["corpus"] == "campus_v2_jpeg")
              & (df["protocol_id"] == "groupkfold5_oof_3seed")]
    if len(cmp_):
        piv = cmp_.pivot_table(index="feat_set", columns="family", values="value")
        L.append("\n分类器 x 特征子集 (5 折 GroupKFold OOF, 3 seed 均值):\n")
        L.append(_fmt_tbl([[i] + [f"{v:.4f}" if pd.notna(v) else "—" for v in piv.loc[i]]
                           for i in piv.index],
                          ["特征子集"] + [str(c) for c in piv.columns]))
    g8 = df[(df["corpus"] == "campus_v2_jpeg")
            & (df["protocol_id"] == "groupkfold8_oof")]
    if len(g8):
        L.append("\n按源图 GroupKFold(8) 的 OOF (注意: **不是**「8-split 随机划分」):\n")
        L.append(_fmt_tbl(
            [[f"`{r['model']}`", r["n_features"], f"{r['value']:.4f}", r["note"]]
             for _, r in g8.iterrows()],
            ["模型", "维数", "OOF AUC", "备注"]))

    gain = _read("gain_group_share.csv")
    if gain is not None and len(gain):
        L.append("\n### 6.3 特征重要性 (LightGBM gain, 当前口径)\n")
        rows = [[f"`{r['model']}`", r["group"], round(float(r["gain_pct"]) * 100, 2)]
                for _, r in gain.iterrows()]
        L.append(_fmt_tbl(rows, ["模型", "特征组", "gain 占比 %"]))
        L.append("\n由 `experiments/gain_importance.py` 现场训练并导出 "
                 "(`gain_importance.csv` / `gain_importance_53d.csv`)。"
                 "旧版按 gain 占比得出的「SRM 是噪声特征」结论产生于错误的 SRM 尺度,"
                 " 已在这套新数字下作废。\n")

    L.append("\n## 7. 不可溯源的行 (引用时必须注明)\n")
    un = df[df["traceable"] == "no"]
    if len(un):
        L.append(_fmt_tbl(
            [[r["corpus"], f"`{r['model']}`", r["value"], r["source_file"], r["note"]]
             for _, r in un.iterrows()],
            ["语料", "条目", "数值", "出处", "为什么不可追溯"]))
    if len(un):
        L.append("\n这些数字**不是错的**, 但它们不能像其他行一样被当作可复现结果引用。"
                 "要升级进可溯源区, 需要补上「脚本 + CSV」这一环 —— 例如给 "
                 "`gpu/train_ml_gpu.py` 加指标落盘。\n")
    else:
        L.append("**本节当前为空。** 2026-09-14 的审计把此前所有「只打印不落盘」的"
                 "数字都补上了生产者并重跑: GPU 管线 (`gpu_pipeline_metrics.csv`)、"
                 "train_model 家族 (`train_model_metrics.csv`)、OOD 误报"
                 " (`ood_summary.csv`)、特征重要性 (`gain_importance*.csv`)。"
                 "若某次重跑缺失, 对应行会自动以 `traceable=no` 出现在这里, "
                 "而不是凭空消失。\n")

    L.append("## 8. 可以 / 不可以比较\n")
    L.append("- ✅ 同一 corpus + 同一 protocol_id 的行之间可以比较 "
             "(如 BOSSbase 上 Ye-Net 0.9541 vs LGB-143d 0.8062)。\n"
             "- ✅ 同一 corpus 上, 用**同一种**协议比较不同特征集 / 分类器。\n"
             "- ❌ 校园语料 vs BOSSbase 的 AUC 不能并列 (语料难度不同)。\n"
             "- ❌ `groupkfold8_oof` 与 `holdout_by_photo_8seed` 不能互相引用 "
             "(两者都带 8, 但一个是 8 折 OOF、一个是 8 个随机划分)。\n"
             "- ❌ 任何 `traceable=no` 的行进入论文正文而不加说明。\n")

    L.append("## 9. 重新生成\n")
    L.append("```bash\n"
             "python experiments/train_deploy_models.py   # 产 deploy_model_metrics.csv\n"
             "python experiments/ood_eval.py              # 产 ood_summary.csv\n"
             "python experiments/gain_importance.py       # 产 gain_importance*.csv\n"
             "python experiments/build_results_table.py   # 合并成这张表\n"
             "python experiments/build_results_table.py --check   # 校验本文档是否同步\n"
             "```\n"
             "输入 CSV 大多不入库 (见 .gitignore): 脚本在缺产物时会跳过对应区块并"
             "打印原因, 不会静默少行。\n")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成唯一权威结果表")
    ap.add_argument("--check", action="store_true",
                    help="只校验 docs/RESULTS.md 是否与当前产物同步 (不写文件)")
    ap.add_argument("--csv-only", action="store_true", help="只写 CSV, 不写文档")
    args = ap.parse_args()

    df = build()
    if not len(df):
        sys.exit("没有任何可收录的行 —— 检查 experiments/data/ 下的产物是否都在。")
    print(f"\n收录 {len(df)} 行  "
          f"(BOSSbase {len(df[df['corpus'].str.startswith('bossbase')])}, "
          f"校园 {len(df[df['corpus'].str.startswith('campus')])}, "
          f"合并 {len(df[df['corpus'] == 'merged_campus_bossbase'])}, "
          f"不可溯源 {len(df[df['traceable'] == 'no'])})")

    doc = render_doc(df)
    if args.check:
        if not inputs_present():
            missing = [n for n in PRIMARY_SOURCES
                       if not os.path.exists(os.path.join(DATA, n))]
            print(f"跳过同步校验: 缺 {len(missing)} 个输入产物 "
                  f"({', '.join(missing[:3])}...); 它们不入库, 需先跑训练/评估脚本")
            return 0
        if not os.path.exists(OUT_DOC):
            print(f"x {os.path.relpath(OUT_DOC, PROJ)} 不存在"); return 1
        with open(OUT_DOC, "r", encoding="utf-8") as fh:
            on_disk = fh.read()
        if on_disk.strip() != doc.strip():
            print(f"x {os.path.relpath(OUT_DOC, PROJ)} 与产物不同步, "
                  f"跑一次不带 --check 的生成"); return 1
        print(f"ok {os.path.relpath(OUT_DOC, PROJ)} 与产物同步"); return 0

    os.makedirs(DATA, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"已写入 -> {os.path.relpath(OUT_CSV, PROJ)}")
    if not args.csv_only:
        os.makedirs(os.path.dirname(OUT_DOC), exist_ok=True)
        with open(OUT_DOC, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(doc + "\n")
        print(f"已写入 -> {os.path.relpath(OUT_DOC, PROJ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
