"""
experiments/model_card.py — 两个部署模型的**模型卡 (model card)** 生成器与校验器。

为什么需要它 (2026-09-15 模型治理)
----------------------------------
`models/stego_classifier.joblib` (143d) 与
`models/stego_classifier_v2_jpeg_lgb_51d.joblib` (53d) 是随仓库分发的两个
**裸二进制**。payload 里虽然写了 provenance, 但要读到它得先装齐 lightgbm 与
scikit-learn 再反序列化一个 pickle —— 对使用者 (以及任何想引用这两个模型的人)
来说, 摆在面前的就是"2.8 MB 的不明文件", 看不到语料、协议、指标与适用边界。

本脚本把这些信息落成**入库的 JSON 模型卡** (models/<模型名>.card.json):

    payload (joblib)   ─┐
    权威指标 CSV       ─┼─►  models/<模型名>.card.json   (入库, 可 diff, 可评审)
    静态适用边界/局限  ─┘

并提供一个 `--check` 模式供 CI 使用, 保证卡片不会与二进制脱钩 —— **sha256 是
硬绑定**: 模型文件一改, 卡就必须重新生成, 否则 `pytest` 直接红。

与其它脚本的分工
----------------
- `experiments/train_deploy_models.py` — 生产者: 训练并落盘 .joblib + 指标 CSV。
  它在写完模型后会调用本脚本刷新模型卡, 正常流程不需要手工跑。
- `experiments/build_results_table.py` — 每个**数字**的登记处 (docs/RESULTS.md)。
  本脚本是每个**模型**的登记处, 指标值取自同一批 CSV, 两者由 tests 交叉校验,
  不会各说各话。

数据缺失时的行为 (CI 上没有 experiments/data/)
---------------------------------------------
指标来自 `experiments/data/*.csv` (产物, 不入库)。这些文件不存在时:
  - 生成模式: 保留卡片里已有的指标值, 不写空值 (绝不会把指标抹成 null);
  - 校验模式: 跳过指标交叉核对并**明确打印跳过**, 但 sha256 / payload 字段
    的核对照做 —— 那部分只依赖入库文件, CI 上是完整覆盖的。

用法
----
    python experiments/model_card.py             # 生成/刷新两张卡
    python experiments/model_card.py --check     # 校验 (CI / pytest 用同一套逻辑)
    python experiments/model_card.py --print     # 打印卡片摘要
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THIS = os.path.dirname(os.path.abspath(__file__))
for _p in (os.path.join(PROJ, "src"), THIS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DATA = os.path.join(PROJ, "experiments", "data")
MODEL_DIR = os.path.join(PROJ, "models")

SCHEMA = "nsf5-deploy-model-card/1"
DEPLOY_CSV = "deploy_model_metrics.csv"
OOD_CSV = "ood_summary.csv"

# 模型文件 -> 卡片文件名 + 静态元数据。
# 静态部分是**人写的**, 每条都要能对上某个实测数字或某段代码, 不能是套话:
# 相关证据在 docs/RESULTS.md (数字) 与 experiments/ood_eval.py (OOD 协议)。
SPECS = {
    "stego_classifier.joblib": dict(
        card="stego_classifier.card.json",
        display_name="143d 默认版 (LGB)",
        feature_set="143d",
        role="ml_predict.MLPredictor 的默认模型; GUI 与 CLI 未指定模型时加载的就是它",
        feature_groups=[
            ["BASE_11 (RS / chi2 / 熵 / 前缀 p)", 11],
            ["SRM_90 (30 个高通核的 mu / absmean / std)", 90],
            ["PREFIX_20 (全图 20 段卡方 p)", 20],
            ["TEX_EST_2 (texture_noise / est_rate)", 2],
            ["LSB_PREFIX_20 (LSB 位平面 20 段卡方 p)", 20],
        ],
        intended_use=[
            "单张图的辅助判读: 与启发式 (RS 卡方 / 前缀卡方) 交叉印证, 而不是单独定案",
            "批量的相对排序: 同一批图里哪几张更可疑 (AUC 高于 53d, 弱档检出 50.0% vs 41.4%)",
            "教学里演示'有监督隐写分析'这条路线 (SRM 统计占 LGB gain 的 52.6%)",
        ],
        not_intended_use=[
            "取证定案或法律用途: 该模型在公开真实照片上有两位数的误报率 (见 metrics.ood_clean_real_photos)",
            "嵌入率低于 d=0.25 的 nsF5: 语料里最弱的一档就是 d=0.25, 更弱的没测过",
            "经重采样/再压缩/裁剪过的图: 预处理固定 LANCZOS 到 512x512, 二次 JPEG 会改变 LSB 统计",
            "非 JPEG 来源或截图: 语料是相机 JPEG (含一次干净的 JPEG 往返), 屏幕截图/PNG 的分布不同",
        ],
        known_limitations=[
            "语料是自建的 414 张校园照片 (12 档嵌入 + 414 张 JPEG 干净图), 不是领域标准基准; "
            "同族模型在 BOSSbase 1.01 上只有 0.8062 (见 cross_corpus_reference)",
            "验证集干净误报 27.9% (Youden 阈值) —— 阈值是'均衡'口径, 不是低误报口径; "
            "低误报档 (threshold_low_fp) 会把弱档检出从 50.0% 压到更低",
            "DIV2K 干净照片误报 51.0%: 训练语料里没有任何 DIV2K 风格的图, 这条数字是分布外证据",
            "clip_outliers=True 只对本模型 (143d) 生效, 且依赖本地 data/dataset_campus_v2*.csv 的训练统计",
            "pickle 由 scikit-learn 1.7 / lightgbm 4.7 序列化; 依赖声明收紧在 scikit-learn>=1.5,<2",
        ],
        cross_corpus=dict(
            dataset="BOSSbase 1.01 (2000 张源图, npz 子集)",
            auc=0.8062,
            protocol="按源图 holdout, 同一源图全部变体落同一侧",
            source="docs/RESULTS.md 第 4 节 / sota_table.csv",
            note="对外引用请用这个数字: 它来自领域标准基准, 校园语料的 0.8939 更容易、不可与它并列",
        ),
    ),
    "stego_classifier_v2_jpeg_lgb_51d.joblib": dict(
        card="stego_classifier_v2_jpeg_lgb_51d.card.json",
        display_name="53d 可解释版 (LGB-51d)",
        feature_set="53d",
        role="教学 / 答辩 / 单图解释用的可解释版; 不会默认加载, 需显式指定 model_path",
        feature_groups=[
            ["BASE_11 (RS / chi2 / 熵 / 前缀 p)", 11],
            ["PREFIX_20 (全图 20 段卡方 p)", 20],
            ["TEX_EST_2 (texture_noise / est_rate)", 2],
            ["LSB_PREFIX_20 (LSB 位平面 20 段卡方 p)", 20],
        ],
        intended_use=[
            "把判定拆成可逐维解释的 51 个统计量 (53 维里只有 2 维是派生量), 教学与答辩场景",
            "需要向非技术读者说明'为什么这张图可疑'时, 列出 Top 贡献特征的方向与强度",
        ],
        not_intended_use=[
            "追求检出率的生产部署: 同语料下 AUC 比 143d 低约 0.05, 弱档检出 41.4% vs 50.0%",
            "与 143d 一样的所有边界 (取证定案 / 极弱嵌入 / 重采样图 / 截图)",
        ],
        known_limitations=[
            "去掉 90 个 SRM 统计量是有代价的: 消融实验里 143d 的 OOF AUC 0.9010 掉到 0.8513",
            "OOD 误报明显高于 143d: 1514 张真实干净照片上 28.86% (143d 是 9.58%), "
            "其中 ALASKA#2 子集 36.0% —— 域外图像上不可用",
            "验证集干净误报 28.9%, 与 143d 同量级; 这是阈值口径问题, 不是模型优势",
            "文件名里的 51d 是历史命名 (53 维里 51 维有明确统计语义), 不要按 51 去算列数",
        ],
        cross_corpus=dict(
            dataset="BOSSbase 1.01 (2000 张源图, npz 子集)",
            auc=0.7172,
            protocol="按源图 holdout, 同一源图全部变体落同一侧",
            source="docs/RESULTS.md 第 4 节 / sota_table.csv",
            note="对外引用请用这个数字; 可解释性换来的 AUC 损失在标准基准上同样存在",
        ),
    ),
}

# OOD 表里模型用 feature_set 标识 (143d / 53d), 只取 clip_outliers=False 的行
OOD_SOURCES = ["ALL", "campus", "alaska", "div2k"]


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_splits(d):
    """JSON 的键只能是字符串: 8-split 的 {0: .., 1: ..} 入库后键会变 "0"。
    两边都归一化, 免得每次比对都报一个格式差异。"""
    if not isinstance(d, dict):
        return d
    return {str(k): v for k, v in d.items()}


def load_payload(model_path: str) -> dict:
    from joblib import load
    return load(model_path)


def _read_csv(name: str):
    """读 experiments/data/<name>; 不存在返回 None (CI 上没有数据)。"""
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return None
    import pandas as pd
    return pd.read_csv(path)


def _deploy_metrics(model_file: str):
    df = _read_csv(DEPLOY_CSV)
    if df is None:
        return None
    rows = df[df["model_file"] == model_file]
    if rows.empty:
        return None
    r = rows.iloc[0]
    out = {
        "dataset": str(r["dataset"]),
        "protocol": str(r["protocol"]),
        "n_train": int(r["n_train"]),
        "n_val": int(r["n_val"]),
        "n_photos": int(r["n_photos"]),
        "dataset_rows": int(r["dataset_rows"]),
        "auc_held_out": float(r["auc_held_out"]),
        "auc_8split_mean": float(r["auc_8split_mean"]),
        "auc_8split_std": float(r["auc_8split_std"]),
        "threshold_youden": float(r["threshold_youden"]),
        "threshold_low_fp": float(r["threshold_low_fp"]),
        "clean_fp_val": float(r["clean_fp_val"]),
        "det_nsf5_p3_d025": float(r["det_nsf5_p3_d025"]),
        "det_nsf5_p2_d035": float(r["det_nsf5_p2_d035"]),
        "det_matrix_p3_d040": float(r["det_matrix_p3_d040"]),
        "source": f"experiments/data/{DEPLOY_CSV}",
    }
    return out


def _ood_metrics(feature_set: str):
    df = _read_csv(OOD_CSV)
    if df is None:
        return None
    df = df[(df["model"] == feature_set) & (df["clip_outliers"] == False)]  # noqa: E712
    if df.empty:
        return None
    per_source = {}
    for _, r in df.iterrows():
        if str(r["source"]) not in OOD_SOURCES:
            continue
        per_source[str(r["source"])] = {
            "n_photos": int(r["n_photos"]),
            "n_false_positive": int(r["n_false_positive"]),
            "fp_rate": float(r["fp_rate"]),
            "fp_ci95": [float(r["fp_ci_lo"]), float(r["fp_ci_hi"])],
            "median_prob": float(r["median_prob"]),
        }
    if not per_source:
        return None
    return {
        "protocol": str(df.iloc[0]["protocol"]),
        "per_source": per_source,
        "source": f"experiments/data/{OOD_CSV}",
        "producer": "experiments/ood_eval.py",
    }


def build_card(model_file: str, prev: dict | None = None) -> dict:
    """从 payload + 指标 CSV + 静态元数据组装一张模型卡。"""
    spec = SPECS[model_file]
    path = os.path.join(MODEL_DIR, model_file)
    pkg = load_payload(path)
    prov = dict(pkg.get("provenance", {}))

    deploy = _deploy_metrics(model_file)
    if deploy is None and prev is not None:
        deploy = prev.get("metrics", {}).get("campus_corpus")
    ood = _ood_metrics(spec["feature_set"])
    if ood is None and prev is not None:
        ood = prev.get("metrics", {}).get("ood_clean_real_photos")

    return {
        "schema": SCHEMA,
        "file": model_file,
        "sha256": sha256_of(path),
        "bytes": os.path.getsize(path),
        "display_name": spec["display_name"],
        "role": spec["role"],
        "payload": {
            "name": pkg.get("name", ""),
            "note": pkg.get("note", ""),
            "features": list(pkg["features"]),
            "n_features": len(pkg["features"]),
            "threshold": float(pkg["threshold"]),
            "threshold_low_fp": float(pkg["threshold_low_fp"]),
            "held_out_auc": float(pkg["held_out_auc"]),
            "params": dict(pkg.get("params", {})),
        },
        "training": {
            "producer": prov.get("producer", ""),
            "dataset": prov.get("dataset", ""),
            "dataset_rows": prov.get("dataset_rows"),
            "n_photos": prov.get("n_photos"),
            "feature_set": prov.get("feature_set", spec["feature_set"]),
            "split": prov.get("split"),
            "splits_evaluated": _norm_splits(prov.get("splits_evaluated")),
            "mean_auc_8split": prov.get("mean_auc_8split"),
            "std_auc_8split": prov.get("std_auc_8split"),
            "env": prov.get("env"),
            "git_rev": prov.get("git_rev"),
            "trained_at": prov.get("trained_at"),
        },
        "metrics": {
            "campus_corpus": deploy,
            "ood_clean_real_photos": ood,
            "cross_corpus_reference": spec["cross_corpus"],
        },
        "feature_groups": [{"group": g, "n": n} for g, n in spec["feature_groups"]],
        "intended_use": list(spec["intended_use"]),
        "not_intended_use": list(spec["not_intended_use"]),
        "known_limitations": list(spec["known_limitations"]),
    }


def card_path(model_file: str) -> str:
    return os.path.join(MODEL_DIR, SPECS[model_file]["card"])


def _load_card(model_file: str):
    path = card_path(model_file)
    if not os.path.exists(path):
        return None, path
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh), path


def write_cards(models=None, quiet: bool = False) -> list:
    """生成/刷新模型卡; 返回 [(模型文件, 卡片路径)]。"""
    out = []
    for model_file in (models or sorted(SPECS)):
        prev, _ = _load_card(model_file)
        card = build_card(model_file, prev)
        path = card_path(model_file)
        txt = json.dumps(card, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(txt)
        if not quiet:
            print(f"  已写入 {os.path.relpath(path, PROJ)}  "
                  f"sha256={card['sha256'][:12]}...  {card['bytes'] / 1e6:.1f} MB")
        out.append((model_file, path))
    return out


def _diff(prefix: str, a, b, problems: list):
    """把 a(卡片) 与 b(重算) 的差异收进 problems。"""
    if a != b:
        problems.append(f"{prefix}: 卡片={a!r} 重算={b!r}")


def check_cards(models=None) -> list:
    """校验模型卡与 .joblib / 指标 CSV 是否一致; 返回问题列表 (空 = 通过)。"""
    problems = []
    for model_file in (models or sorted(SPECS)):
        card, path = _load_card(model_file)
        if card is None:
            problems.append(f"缺少模型卡: {os.path.relpath(path, PROJ)} "
                            f"(跑 python experiments/model_card.py 生成)")
            continue
        if card.get("schema") != SCHEMA:
            problems.append(f"{os.path.relpath(path, PROJ)}: schema 应为 {SCHEMA}, "
                            f"实际 {card.get('schema')!r}")

        mp = os.path.join(MODEL_DIR, model_file)
        if not os.path.exists(mp):
            problems.append(f"卡片指向的模型不存在: {os.path.relpath(mp, PROJ)}")
            continue

        # 1) 硬绑定: 二进制指纹
        _diff(f"{model_file} sha256", card.get("sha256"), sha256_of(mp), problems)
        _diff(f"{model_file} bytes", card.get("bytes"), os.path.getsize(mp), problems)

        # 2) payload 字段逐项核对 (只依赖入库文件, CI 上是完整覆盖)
        pkg = load_payload(mp)
        pb = card.get("payload", {})
        _diff(f"{model_file} payload.name", pb.get("name"), pkg.get("name", ""), problems)
        _diff(f"{model_file} payload.features",
              pb.get("features"), list(pkg.get("features", [])), problems)
        _diff(f"{model_file} payload.n_features",
              pb.get("n_features"), len(pkg.get("features", [])), problems)
        _diff(f"{model_file} payload.threshold",
              pb.get("threshold"), float(pkg["threshold"]), problems)
        _diff(f"{model_file} payload.threshold_low_fp",
              pb.get("threshold_low_fp"), float(pkg["threshold_low_fp"]), problems)
        _diff(f"{model_file} payload.held_out_auc",
              pb.get("held_out_auc"), float(pkg["held_out_auc"]), problems)
        _diff(f"{model_file} payload.params",
              pb.get("params"), dict(pkg.get("params", {})), problems)

        prov = pkg.get("provenance", {})
        tr = card.get("training", {})
        for key in ("producer", "dataset", "dataset_rows", "n_photos", "feature_set",
                    "split", "splits_evaluated", "mean_auc_8split", "std_auc_8split",
                    "env", "git_rev", "trained_at"):
            want = _norm_splits(prov.get(key)) if key == "splits_evaluated" else prov.get(key)
            _diff(f"{model_file} training.{key}", tr.get(key), want, problems)

        # 3) 指标交叉核对 (需要 experiments/data/*.csv, 没有就明确跳过)
        rebuilt = build_card(model_file, prev=card)
        for block in ("campus_corpus", "ood_clean_real_photos"):
            a = card.get("metrics", {}).get(block)
            b = rebuilt["metrics"].get(block)
            if b is None:
                print(f"  [skip] {model_file} metrics.{block}: 指标 CSV 不在库 "
                      f"(本地跑 `make exp-models`/`make ood` 可完整核对)")
                continue
            _diff(f"{model_file} metrics.{block}", a, b, problems)

        # 4) 卡片的必填部分不能空
        for key in ("intended_use", "not_intended_use", "known_limitations",
                    "feature_groups", "display_name", "role"):
            if not card.get(key):
                problems.append(f"{os.path.relpath(path, PROJ)}: {key} 为空")
        n_declared = sum(g["n"] for g in card.get("feature_groups", []))
        if n_declared != card.get("payload", {}).get("n_features"):
            problems.append(f"{os.path.relpath(path, PROJ)}: feature_groups 合计 "
                            f"{n_declared} != n_features "
                            f"{card.get('payload', {}).get('n_features')}")
    return problems


def print_summary() -> int:
    for model_file in sorted(SPECS):
        card, _ = _load_card(model_file)
        if card is None:
            print(f"{model_file}: 无模型卡")
            continue
        pb = card["payload"]
        m = card.get("metrics", {})
        cc = m.get("campus_corpus") or {}
        ood = (m.get("ood_clean_real_photos") or {}).get("per_source", {})
        print(f"\n== {card['display_name']} ({model_file}) ==")
        print(f"   sha256 {card['sha256'][:16]}...  {card['bytes'] / 1e6:.2f} MB")
        print(f"   特征 {pb['n_features']} 维  thr_youden={pb['threshold']:.4f}  "
              f"thr_low_fp={pb['threshold_low_fp']:.4f}")
        if cc:
            print(f"   校园语料 held-out AUC={cc['auc_held_out']:.4f}  "
                  f"8-split={cc['auc_8split_mean']:.4f} +- {cc['auc_8split_std']:.4f}  "
                  f"弱档检出={cc['det_nsf5_p3_d025']:.2%}")
        for src in OOD_SOURCES:
            if src in ood:
                r = ood[src]
                print(f"   OOD {src:<7s} n={r['n_photos']:<5d} "
                      f"误报={r['fp_rate']:.2%} ({r['n_false_positive']})")
        print(f"   跨语料参考 (BOSSbase): AUC={card['metrics']['cross_corpus_reference']['auc']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="部署模型卡生成器 / 校验器")
    ap.add_argument("--check", action="store_true",
                    help="只校验 (CI 与 pytest 用同一套逻辑), 不写文件")
    ap.add_argument("--print", dest="print_only", action="store_true",
                    help="打印模型卡摘要")
    ap.add_argument("--models", default="", help="逗号分隔的模型文件名 (默认全部)")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()] or None
    if models:
        bad = [m for m in models if m not in SPECS]
        if bad:
            sys.exit(f"未知模型 {bad}; 可选 {sorted(SPECS)}")

    if args.print_only:
        return print_summary()

    if args.check:
        problems = check_cards(models)
        if problems:
            print("模型卡校验失败:")
            for p in problems:
                print(f"  - {p}")
            print("修法: python experiments/model_card.py  然后提交 models/*.card.json")
            return 1
        print(f"模型卡校验通过 ({len(models or SPECS)} 张)")
        return 0

    print("刷新模型卡:")
    write_cards(models)
    problems = check_cards(models)
    if problems:
        print("写回后仍不一致 (不该发生):")
        for p in problems:
            print(f"  - {p}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
