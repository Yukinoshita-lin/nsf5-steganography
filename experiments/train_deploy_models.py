"""
experiments/train_deploy_models.py — 两个部署模型的**生产者**。

背景 (为什么需要这个文件)
------------------------
`models/stego_classifier.joblib` (143d 默认版) 与
`models/stego_classifier_v2_jpeg_lgb_51d.joblib` (53d 可解释版) 此前随仓库
分发, 但仓库里没有任何脚本能产出它们: `src/train_model.py` 训练的是
LR/RF/GBDT/XGB 家族, `experiments/` 下的 LGB 脚本只评估不落盘。结果是模型
可用但**不可复现** —— 这是项目"可验证性"声明里最后一个真实缺口。

本文件把这条链补全:

    data/dataset_campus_v2_jpeg.csv        (414 校园照片 x 12 档 + 414 JPEG 干净图)
        │  143d = featurize_v2.ALL_FEATURE_NAMES (143 列)
        │  53d  = 143d 去掉 90 个 SRM 统计量
        ▼
    按**源图**分组划分 GroupShuffleSplit(test_size=0.25, random_state=seed)
        ▼
    LightGBM (冻结超参, 见 LGB_PARAMS)
        ▼
    models/stego_classifier.joblib
    models/stego_classifier_v2_jpeg_lgb_51d.joblib

口径 (2026-09-14 审计后)
------------------------
`held_out_auc` = seed 0 的验证 AUC; "8-split 平均 AUC" = seed 0..7 的均值。
划分按**源图**分组, 语料必须满足分组不变量 (见 check_corpus_grouping)。

审计发现 (已修): 2026-09-13 之前那份 `dataset_campus_v2_jpeg.csv` 里, 414 个
`clean_jpeg` 行用了 1413..1826 这一块**独立 photo_id**, 而它们的特征与对应
`clean` 行逐位相同 (max|Δ| = 7e-9) —— 既是重复样本, 又让按源图划分失效
(同一张源图的含密变体在训练集、它的副本在验证集)。按项目自己的评测纪律
(experiments/README.md 第 1 条) 这属于源图泄漏, 数字不可用。

修正前后实测 (同超参、同 seed):

    模型  泄漏口径 AUC   修正口径 AUC    弱档 nsF5 p3 d=0.25 检出
    143d      0.8946        0.7555        85.3% -> 44.2%
    53d       0.9100        0.7503        87.2% -> 29.8%

修正口径与 BOSSbase 上的同族模型 (0.7529 / 0.7172) 处在同一水平 —— 也就是说
"校园语料更容易" 这个说法主要来自那次泄漏, 不是语料难度。
修复方式见 `experiments/add_jpeg_clean.py` (photo_id 继承源图 + 真实 JPEG 往返),
本脚本的 check_corpus_grouping() 是防它复发的护栏。

划分口径说明: 这里用 `numpy.random.RandomState(seed)` 对**唯一源图**做
permutation, 与 `sklearn.model_selection.GroupShuffleSplit(random_state=seed)`
等价 —— 这正是当年产出这两个模型的语义 (两者在本数据集上给出同一划分)。
注意它和 `gpu/train_cnn.py::split_by_photo` 用的 `np.random.default_rng` **不是**
同一套随机流, 后者是 BOSSbase 工具链的划分, 两者不可互换。

用法
----
    python experiments/train_deploy_models.py                # 两个模型 + 8-split 评估 + 落盘
    python experiments/train_deploy_models.py --models 53d
    python experiments/train_deploy_models.py --seed 3
    python experiments/train_deploy_models.py --out-dir /tmp/models --no-save
    python experiments/train_deploy_models.py --no-splits     # 只跑 seed 0, 约 10 秒
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "src"))

from featurize_v2 import ALL_FEATURE_NAMES, SRM_STAT_NAMES  # noqa: E402
from pathutil import rel_from_proj  # noqa: E402

# ---------------------------------------------------------------- 冻结口径
# 这三项 + LGB_PARAMS 就是两个部署模型的完整"配方", 改动任何一项都等于
# 发布一个新模型, 必须同步更新 README 的指标表。
DEFAULT_CSV = os.path.join(PROJ, "data", "dataset_campus_v2_jpeg.csv")
SPLIT_TEST_SIZE = 0.25          # 按源图留出 25% 做验证
DEFAULT_SEED = 0
SEED_SWEEP = tuple(range(8))    # README 的 "8-split 平均 AUC" = 这 8 个 seed 的均值
LOW_FP = 0.10                   # threshold_low_fp: 验证集误报率 ≤ 10% 下的最低阈值

# 与随仓库分发的两个 .joblib 的 payload['params'] 逐键一致。
LGB_PARAMS = dict(objective="binary", metric="binary_logloss", num_leaves=31,
                  n_estimators=800, learning_rate=0.03, min_child_samples=10,
                  subsample=0.9, colsample_bytree=0.8, random_state=0,
                  n_jobs=-1, verbose=-1)

META_COLS = {"label", "photo_id", "variant", "method", "p", "density",
             "changed_frac", "basename"}

# 产物文件名保持历史命名 (53d 版在 README 里叫 "LGB-51d", 因为 53 维里只有
# 51 维有明确统计语义)。改名会让已发布的 ml_predict/GUI 路径失效。
MODEL_FILES = {
    "143d": "stego_classifier.joblib",
    "53d": "stego_classifier_v2_jpeg_lgb_51d.joblib",
}
MODEL_NAMES = {"143d": "LGB", "53d": "LGB-51d"}
OUT_CSV = os.path.join(PROJ, "experiments", "data", "deploy_model_metrics.csv")


def feature_sets() -> dict:
    """143d = 全部 v2 特征; 53d = 去掉 90 个 SRM 统计量 (11+20+20+2)。"""
    srm = set(SRM_STAT_NAMES)
    return {
        "143d": list(ALL_FEATURE_NAMES),
        "53d": [n for n in ALL_FEATURE_NAMES if n not in srm],
    }


def load_dataset(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        sys.exit(f"数据集不存在: {csv_path}\n"
                 f"先按 README 的 '重新生成 v2 数据集' 一节产出 {os.path.basename(csv_path)}。")
    df = pd.read_csv(csv_path)
    need = {"label", "photo_id"}
    missing = need - set(df.columns)
    if missing:
        sys.exit(f"{csv_path} 缺少必要列: {sorted(missing)}")
    return df


def split_by_photo(pid: np.ndarray, seed: int = DEFAULT_SEED,
                   test_size: float = SPLIT_TEST_SIZE) -> np.ndarray:
    """按**源图**划分, 返回验证集布尔掩码。

    同一 photo_id 的全部变体必落同一侧 —— 否则模型只要认出源图内容就能刷高
    AUC, 那是源图泄漏, 不是隐写检测能力 (见 experiments/README.md 评测纪律 1)。

    用 RandomState + permutation 而不是 sklearn 的 GroupShuffleSplit, 是为了
    让划分跨 sklearn 版本可复现 (两者在本数据集上给出完全相同的划分)。
    """
    uniq = np.unique(pid)
    perm = np.random.RandomState(seed).permutation(len(uniq))
    n_val = int(round(len(uniq) * test_size))
    val_photos = set(uniq[perm[:n_val]].tolist())
    return np.fromiter((p in val_photos for p in pid), bool, len(pid))


def check_corpus_grouping(df: pd.DataFrame, csv_path: str) -> None:
    """分组不变量: 每个 photo_id 的 variant 集合必须完全一致。

    这是 2026-09-14 审计缺陷的护栏。当时的语料里 414 个 `clean_jpeg` 行各占一个
    独立 photo_id (只有单一 variant), 而同源图的其余 13 行挂在另一个 id 上 ——
    "按源图划分"于是形同虚设, AUC 被抬高约 0.15。孤儿 id 块是这种泄漏的通用
    形态, 因此这里直接拒绝, 而不是照常训练出一个好看但无效的数字。
    """
    if "variant" not in df.columns:
        return
    sets = df.groupby("photo_id")["variant"].apply(frozenset)
    counts = sets.value_counts()
    if len(counts) > 1:
        odd = counts.index[counts.index != counts.index[0]][0]
        ids = list(sets[sets == odd].index[:5])
        raise SystemExit(
            f"{os.path.basename(csv_path)} 破坏了按源图分组不变量: "
            f"{int(counts[odd])} 个 photo_id 只有 {sorted(odd)} 这一部分变体 "
            f"(例: {ids})。\n"
            f"这会让同一张源图的样本跨训练/验证两侧 —— 见 experiments/README.md "
            f"评测纪律第 1 条。\n"
            f"请用 `python experiments/add_jpeg_clean.py` 重建语料 "
            f"(它把 clean_jpeg 行的 photo_id 绑回源图)。")


def youden_threshold(y_true, p) -> float:
    """Youden J 最大点。与 src/train_model.py::youden_threshold 同定义。

    2026-09-17: 加了 np.isfinite 过滤。`sklearn.metrics.roc_curve` 的
    `thresholds[0]` 是 **inf**(表示"没有任何样本被判为正"), 而 `argmax(J)` 在
    小样本/弱可分数据上经常正落在这一点 —— 于是阈值被写成 inf, 模型此后对任何图
    都不会判含密 (`p >= inf` 恒假), 而且**没有任何报错**。实测触发: 4 张合成照片
    x 3 档的语料上, 生产者直接写出 `threshold_youden=inf` (随仓库分发的两个模型
    恰好没踩到, 它们的阈值是 0.9493 / 0.9595)。同文件的 `threshold_for_fp()` 一直
    有这个过滤, 只有这里漏了。
    """
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_true, p)
    j = tpr - fpr
    cand = [(ji, t) for ji, t in zip(j, th) if np.isfinite(t)]
    if not cand:
        return 0.5
    return float(max(cand)[1])          # J 最大的**有限**阈值


def threshold_for_fp(y_true, p, max_fp: float = LOW_FP) -> float:
    """误报率 ≤ max_fp 时的最低阈值。与 src/train_model.py::threshold_for_fp 同定义。"""
    from sklearn.metrics import roc_curve
    fpr, tpr, th = roc_curve(y_true, p)
    cand = [t for t, f, tp in zip(th, fpr, tpr)
            if np.isfinite(t) and f <= max_fp and tp > 0.0]
    return float(min(cand)) if cand else 0.5


def _git_rev() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              cwd=PROJ, capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - 溯源信息缺失不该阻断训练
        return "unknown"


def train_once(X, y, pid, feats, seed: int):
    """训练一个方向, 返回 (model, 验证集指标)。"""
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score

    val = split_by_photo(pid, seed)
    tr = ~val
    clf = lgb.LGBMClassifier(**LGB_PARAMS)
    clf.fit(X[tr], y[tr])
    p_val = clf.predict_proba(X[val])[:, 1]
    auc = float(roc_auc_score(y[val], p_val))
    thr = youden_threshold(y[val], p_val)
    thr_fp = threshold_for_fp(y[val], p_val)
    return clf, dict(auc=auc, threshold=thr, threshold_low_fp=thr_fp,
                     n_train=int(tr.sum()), n_val=int(val.sum()),
                     val_mask=val, p_val=p_val)


VARIANT_LABELS = {          # 来自 data/dataset_campus_v2_jpeg.csv 的 variant 定义
    "v0": "nsF5 p3 d=0.25", "v1": "nsF5 p3 d=0.40", "v2": "nsF5 p3 d=0.55",
    "v3": "nsF5 p2 d=0.35", "v4": "nsF5 p2 d=0.85", "v5": "matrix p3 d=0.50",
    "v6": "matrix p2 d=0.80", "v7": "lsb d=0.50", "v8": "matrix p3 d=0.40",
    "v9": "matrix p3 d=0.60", "v10": "lsb d=0.30", "v11": "lsb d=0.70",
}


def variant_detection(df: pd.DataFrame, mask: np.ndarray, p: np.ndarray,
                      thr: float) -> dict:
    """每档变体在 Youden 阈值下的检出率 / 干净图误报率。

    键是 CSV 的 variant 原值 (v0..v11 / clean / clean_jpeg); 语义对照见
    VARIANT_LABELS。`v0` 就是 README 反复引用的弱档 `nsF5 p3 d=0.25`。
    """
    # 只带两列构造小 DataFrame —— 在大表切片上 assign 会触发 pandas
    # "highly fragmented frame" 性能警告 (纯噪声, 但会污染 CI 日志)。
    sub = pd.DataFrame({"variant": df["variant"].values[mask], "p": np.asarray(p)})
    return {str(v): float((g["p"] >= thr).mean()) for v, g in sub.groupby("variant")}


def build_payload(clf, feats, name, metrics, seed, csv_path, feat_key):
    return {
        # —— ml_predict.py 依赖的键, 一个都不能少或改名 ——
        "model": clf,
        "features": list(feats),
        "threshold": metrics["threshold"],
        "threshold_low_fp": metrics["threshold_low_fp"],
        "held_out_auc": metrics["auc"],
        "name": name,
        "note": (f"train_deploy_models.py — {feat_key} LGB on "
                 f"{os.path.basename(csv_path)}; by-photo holdout "
                 f"(test_size={SPLIT_TEST_SIZE}, seed={seed}); "
                 f"held-out AUC={metrics['auc']:.4f}; "
                 f"thr_youden={metrics['threshold']:.3f}, "
                 f"thr_fp{int(LOW_FP * 100)}={metrics['threshold_low_fp']:.3f}"),
        "params": dict(LGB_PARAMS),
        # —— 溯源字段 (新增; 旧 payload 没有, 读方不做假设) ——
        "provenance": {
            "producer": "experiments/train_deploy_models.py",
            "dataset": rel_from_proj(csv_path, PROJ),
            "dataset_rows": int(metrics["dataset_rows"]),
            "n_photos": int(metrics["n_photos"]),
            "feature_set": feat_key,
            "n_features": len(feats),
            "split": {"by": "photo_id", "test_size": SPLIT_TEST_SIZE, "seed": seed,
                      "rng": "numpy.random.RandomState"},
            "splits_evaluated": metrics.get("splits"),
            "mean_auc_8split": metrics.get("mean_auc"),
            "std_auc_8split": metrics.get("std_auc"),
            "env": {"python": platform.python_version(),
                    "numpy": np.__version__,
                    "sklearn": _pkg_version("sklearn"),
                    "lightgbm": _pkg_version("lightgbm"),
                    "pandas": pd.__version__},
            "git_rev": _git_rev(),
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def _pkg_version(mod: str) -> str:
    try:
        return __import__(mod).__version__
    except Exception:  # noqa: BLE001
        return "unknown"


def run(feat_key: str, args) -> dict:
    import joblib

    csv_path = os.path.abspath(args.csv)
    df = load_dataset(csv_path)
    check_corpus_grouping(df, csv_path)
    feats = feature_sets()[feat_key]
    missing = [c for c in feats if c not in df.columns]
    if missing:
        # 绝不静默降级 —— sota_compare.py 的历史教训就是"请求 53 维、实得 11 维"
        sys.exit(f"{os.path.basename(csv_path)} 缺少 {len(missing)} 个 {feat_key} "
                 f"特征列 (例: {missing[:6]}); 不允许降级到可用子集。")

    df = df.dropna(subset=feats)
    X = df[feats].values.astype(np.float64)
    y = df["label"].values.astype(np.int64)
    pid = df["photo_id"].values

    print(f"\n=== {feat_key} ({len(feats)} 维) ===")
    print(f"  数据: {rel_from_proj(csv_path, PROJ)}  "
          f"样本 {len(df)}  源图 {len(np.unique(pid))}  "
          f"clean={(y == 0).sum()} stego={(y == 1).sum()}")

    clf, m = train_once(X, y, pid, feats, args.seed)
    print(f"  seed={args.seed}  held-out AUC={m['auc']:.4f}  "
          f"thr_youden={m['threshold']:.4f}  thr_fp10={m['threshold_low_fp']:.4f}")

    det = variant_detection(df, m["val_mask"], m["p_val"], m["threshold"])
    clean_fp = max(det.get("clean", 0.0), det.get("clean_jpeg", 0.0))
    order = sorted((v for v in det if v.startswith("v")), key=lambda v: int(v[1:]))
    print(f"  验证集干净误报={clean_fp:.3f}  逐档检出:")
    for v in order:
        print(f"    {v:>3s}  {VARIANT_LABELS.get(v, '?'):<16s} {det[v]:.3f}")

    m["dataset_rows"] = len(df)
    m["n_photos"] = int(len(np.unique(pid)))
    m["splits"] = {args.seed: round(m["auc"], 4)}
    if args.splits:
        aucs = []
        for s in SEED_SWEEP:
            if s == args.seed:
                aucs.append(m["auc"])
                continue
            _, ms = train_once(X, y, pid, feats, s)
            aucs.append(ms["auc"])
            m["splits"][s] = round(ms["auc"], 4)
            print(f"  seed={s}  held-out AUC={ms['auc']:.4f}")
        m["mean_auc"] = float(np.mean(aucs))
        m["std_auc"] = float(np.std(aucs))
        print(f"  {len(aucs)}-split 平均 AUC={m['mean_auc']:.4f} ± {m['std_auc']:.4f}")

    row = {
        "model": MODEL_NAMES[feat_key], "feature_set": feat_key,
        "n_features": len(feats), "dataset": os.path.basename(csv_path),
        "protocol": f"by-photo holdout test_size={SPLIT_TEST_SIZE} seed={args.seed}",
        "auc_held_out": round(m["auc"], 4),
        "auc_8split_mean": round(m["mean_auc"], 4) if m.get("mean_auc") else "",
        "auc_8split_std": round(m["std_auc"], 4) if m.get("std_auc") else "",
        "threshold_youden": round(m["threshold"], 4),
        "threshold_low_fp": round(m["threshold_low_fp"], 4),
        "clean_fp_val": round(clean_fp, 4),
        # 弱档 nsF5 p3 d=0.25 是 README 反复引用的关键指标, 单独成列
        "det_nsf5_p3_d025": round(det.get("v0", float("nan")), 4),
        "det_nsf5_p2_d035": round(det.get("v3", float("nan")), 4),
        "det_matrix_p3_d040": round(det.get("v8", float("nan")), 4),
        "n_train": m["n_train"], "n_val": m["n_val"],
        "n_photos": m["n_photos"], "dataset_rows": m["dataset_rows"],
        "model_file": MODEL_FILES[feat_key],
    }

    if not args.splits:
        # 提醒而不是静默: 这条 CSV 会被权威结果表读走, 少了 8-split 列意味着
        # README 引用的 "8-split 平均 AUC" 失去支撑 (build_results_table 也会报警)。
        print("  注意: --no-splits 未计算 8-split 均值, 指标 CSV 的对应列将留空; "
              "要恢复请完整跑一次 (约 3 分钟)")

    if args.save:
        out_dir = os.path.abspath(args.out_dir)
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, MODEL_FILES[feat_key])
        payload = build_payload(clf, feats, MODEL_NAMES[feat_key], m, args.seed,
                               csv_path, feat_key)
        joblib.dump(payload, path)
        print(f"  已保存 -> {rel_from_proj(path, PROJ)}  "
              f"({os.path.getsize(path) / 1e6:.1f} MB)")
    else:
        print("  --no-save: 未落盘")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="训练并保存两个部署模型 (可复现生产者)")
    ap.add_argument("--models", default="143d,53d",
                    help="要训练的模型, 逗号分隔: 143d,53d (默认两个都跑)")
    ap.add_argument("--csv", default=DEFAULT_CSV, help="训练集 CSV")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="划分 seed")
    ap.add_argument("--splits", dest="splits", action="store_true", default=True,
                    help="额外跑 seed=0..7 的 8-split 均值 (默认开)")
    ap.add_argument("--no-splits", dest="splits", action="store_false",
                    help="只跑单个 seed, 快 (~10 秒/模型)")
    ap.add_argument("--out-dir", default=os.path.join(PROJ, "models"),
                    help="模型输出目录 (默认 models/)")
    ap.add_argument("--no-save", dest="save", action="store_false", default=True,
                    help="只评估, 不写模型文件")
    ap.add_argument("--out-csv", default=OUT_CSV,
                    help="指标 CSV 落点 (默认 experiments/data/deploy_model_metrics.csv; "
                         "试跑/冒烟测试请改这里, 别覆盖权威表用的那一份)")
    args = ap.parse_args()

    keys = [k.strip() for k in args.models.split(",") if k.strip()]
    bad = [k for k in keys if k not in MODEL_FILES]
    if bad:
        sys.exit(f"未知模型 {bad}; 可选 {sorted(MODEL_FILES)}")

    print("部署模型生产者 — 冻结口径:")
    print(f"  csv={rel_from_proj(os.path.abspath(args.csv), PROJ)}  "
          f"test_size={SPLIT_TEST_SIZE}  seed={args.seed}")
    print(f"  params={json.dumps(LGB_PARAMS, sort_keys=True)}")

    rows = [run(k, args) for k in keys]

    out_csv = os.path.abspath(args.out_csv)
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    pd.DataFrame(rows).to_csv(out_csv, index=False, float_format="%.4f")
    print(f"\n指标已写入 -> {rel_from_proj(out_csv, PROJ)}")

    # 模型卡紧跟模型走: 卡里含 sha256, 所以"重训了模型但没更新卡"必须由生产者
    # 自己消灭, 而不是留给下一个人发现 (发现方式会是 CI 里 pytest 报红)。
    if args.save:
        import model_card as MC  # 同目录
        saved = [MODEL_FILES[k] for k in keys if k in MODEL_FILES]
        print("\n刷新模型卡:")
        MC.write_cards([f for f in saved if f in MC.SPECS])

    print("下一步: python experiments/build_results_table.py  (刷新唯一权威结果表)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
