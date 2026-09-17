"""两个部署模型的**生产者**在 CI 里的冒烟测试 (2026-09-17)。

为什么需要它
------------
`experiments/train_deploy_models.py` 产出的是随仓库分发的两个 `.joblib` 与
README/权威表里的校园语料指标 (held-out 0.8939 / 0.8391, 8-split 0.8980 / 0.8461,
弱档检出 50.0% / 41.4%)。此前 CI 里只有**契约测试**碰它 ——
`test_results_contract.py` 比对"生产者会训练哪 143/53 列"与随包模型 payload 里的
features, 但从来没有真的把这条生产者跑一遍:

- 参数解析 / 指标 CSV 的列名变了, 要到有人手工跑 `make exp-models` 才会发现;
- 语料分组护栏 (`check_corpus_grouping`) 是否真的拦住"孤儿 photo_id"只在单元层面
  测过, 没走过 CLI;
- 模型卡刷新挂了 (1.7.0 起生产者会调 `model_card.write_cards`) 也不会有信号。

本测试用**自造的 143 维小语料**(4 张合成照片 × 3 档 = 12 行)把这条链跑通:

    合成照片 → nsF5 嵌入 → featurize_v2(143 维) → CSV
        → train_deploy_models.py --models 143d --no-split --no-save
        → 指标 CSV (列名/语料计数/AUC 范围)

它**不断言具体 AUC** —— 12 行合成数据的 AUC 没有意义; 真实数字只能由真实语料产出
(`make exp-models`)。这里断言的是**结构与护栏**。
"""
import csv
import io
import os
import subprocess
import sys

import numpy as np
import pytest
from PIL import Image

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
EXP = os.path.join(PROJ, "experiments")
for _p in (SRC, EXP):
    if _p not in sys.path:
        sys.path.insert(0, _p)

N_PHOTOS = 4
VARIANTS = [("nsF5", 3, 0.25), ("nsF5", 3, 0.55)]


def _photo(i: int, size: int = 256) -> np.ndarray:
    rng = np.random.default_rng(3000 + i)
    yy, xx = np.mgrid[0:size, 0:size]
    img = (85 + 45 * np.sin(xx / (10 + i)) + 35 * np.cos(yy / (14 + i))
           + rng.integers(-7, 8, (size, size)))
    return np.clip(img, 0, 255).astype(np.uint8)


def build_corpus(csv_path: str, leaky: bool = False) -> dict:
    """写一份 143 维小语料; leaky=True 时给一个 photo_id 制造"孤儿 id 块"。"""
    import make_dataset as MD          # capacity_bytes / 与生产一致的容量口径
    from cppembed import embed_string
    from featurize_v2 import ALL_FEATURE_NAMES, featurize_v2
    from ml_predict import MLPredictor

    meta = ["label", "photo_id", "variant", "method", "p", "density", "changed_frac"]
    rows = []
    for i in range(N_PHOTOS):
        # 与部署口径一致的预处理: 亮度 + LANCZOS 512x512
        a = MLPredictor.preprocess(_photo(i))
        rows.append(list(featurize_v2(a)) + [0, f"p{i}", "clean", "", "", "", ""])
        for vi, (method, p, dens) in enumerate(VARIANTS):
            nbytes = int(MD.capacity_bytes(a.size, p, head_pixels=0) * dens)
            stego, _, _ = embed_string(a, "S" * nbytes, method=method, p=p,
                                       check=False, fast_permute=True)
            changed = float(np.sum(stego != a)) / a.size
            rows.append(list(featurize_v2(stego))
                        + [1, f"p{i}", f"v{vi}", method, p, dens, f"{changed:.4f}"])
    if leaky:
        # 孤儿 id 块: 单独一个 photo_id 只有一档 variant —— 正是 2026-09-14 那次
        # 源图泄漏的形态, 生产者必须拒绝。
        # 注意行结构是 [143 个特征..., label, photo_id, variant, ...], 不是 label 打头。
        n_feat = len(ALL_FEATURE_NAMES)
        orphan = list(rows[-1])
        orphan[n_feat] = 1                    # label
        orphan[n_feat + 1] = "orphan_id"      # photo_id
        rows.append(orphan)

    with io.open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(ALL_FEATURE_NAMES + meta)
        w.writerows(rows)
    return {"rows": len(rows), "photos": N_PHOTOS, "path": csv_path}


def _run_producer(csv_path: str, out_csv: str, extra=()):
    cmd = [sys.executable, os.path.join(EXP, "train_deploy_models.py"),
           "--csv", csv_path, "--models", "143d", "--no-splits", "--no-save",
           "--out-csv", out_csv, *extra]
    return subprocess.run(cmd, cwd=PROJ, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)


@pytest.mark.slow
def test_deploy_producer_runs_end_to_end_on_synthetic_corpus(tmp_path):
    """生产者跑通: 指标 CSV 的列/计数/AUC 范围都对, 且不碰权威产物。"""
    import pandas as pd
    corpus = build_corpus(str(tmp_path / "corpus.csv"))
    out_csv = str(tmp_path / "metrics.csv")
    r = _run_producer(corpus["path"], out_csv)
    assert r.returncode == 0, f"生产者失败:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}"
    assert os.path.exists(out_csv), "没有写出指标 CSV"

    df = pd.read_csv(out_csv)
    expected = {"model", "feature_set", "n_features", "dataset", "protocol",
                "auc_held_out", "threshold_youden", "threshold_low_fp",
                "n_train", "n_val", "n_photos", "dataset_rows", "model_file"}
    missing = expected - set(df.columns)
    assert not missing, f"指标 CSV 少了列: {sorted(missing)}"
    assert len(df) == 1, f"只训了 143d, 应有 1 行, 实际 {len(df)}"
    row = df.iloc[0]
    assert row["feature_set"] == "143d"
    assert int(row["n_features"]) == 143
    assert int(row["dataset_rows"]) == corpus["rows"]
    assert int(row["n_photos"]) == corpus["photos"]
    assert int(row["n_train"]) + int(row["n_val"]) == corpus["rows"]
    assert 0.0 <= float(row["auc_held_out"]) <= 1.0
    assert 0.0 < float(row["threshold_youden"]) < 1.0
    assert row["model_file"] == "stego_classifier.joblib"
    assert "by-photo holdout" in str(row["protocol"]), row["protocol"]
    # 试跑绝不能覆盖权威表用的那一份
    canonical = os.path.join(PROJ, "experiments", "data", "deploy_model_metrics.csv")
    if os.path.exists(canonical):
        txt = io.open(canonical, encoding="utf-8").read()
        assert "ci_smoke" not in txt and "corpus.csv" not in txt, "冒烟测试污染了权威指标表"
    print(f"[OK] 生产者: 合成语料跑通 ({corpus['rows']} 行), AUC="
          f"{float(row['auc_held_out']):.3f}")


@pytest.mark.slow
def test_deploy_producer_refuses_orphan_photo_ids(tmp_path):
    """语料一旦出现"孤儿 id 块", 生产者必须**拒绝训练** (源图泄漏护栏走 CLI)。"""
    corpus = build_corpus(str(tmp_path / "leaky.csv"), leaky=True)
    out_csv = str(tmp_path / "metrics_leaky.csv")
    r = _run_producer(corpus["path"], out_csv)
    assert r.returncode != 0, "破坏分组不变量的语料竟然训下去了"
    out = r.stdout + r.stderr
    assert "分组不变量" in out, out[-800:]
    assert not os.path.exists(out_csv), "被拒绝的语料不该留下指标 CSV"
    print("[OK] 生产者: 孤儿 photo_id 被拒绝 (源图泄漏护栏生效)")


def test_youden_threshold_never_returns_inf():
    """阈值必须是有限值, 且落在 (0, 1] 内。

    2026-09-17 的真实触发: `sklearn.roc_curve` 的 `thresholds[0]` 是 inf,
    小样本/弱可分数据上 `argmax(J)` 经常落在这一点 —— 阈值于是变成 inf,
    `p >= inf` 恒假, 模型对任何图都判"干净"且不报错。这个测试用几组退化输入
    把两个实现 (生产者与 src/train_model.py) 都覆盖一遍。
    """
    import train_deploy_models as TD
    import train_model as TM
    cases = [
        ([0, 1], [0.5, 0.5]),                 # 完全无区分: argmax 会落在 inf 上
        ([0, 0, 1, 1], [0.2, 0.3, 0.25, 0.35]),   # 弱可分 + 交叉
        ([0, 1], [0.0, 1.0]),                 # 完全可分
        ([1, 0], [0.1, 0.9]),                 # 标签顺序反过来
    ]
    for y, p in cases:
        for name, fn in (("train_deploy_models", TD.youden_threshold),
                         ("train_model", TM.youden_threshold)):
            thr = fn(np.array(y), np.array(p, dtype=float))
            assert np.isfinite(thr), f"{name} 给出非有限阈值: {thr} (y={y}, p={p})"
            assert 0.0 < thr <= 1.0, f"{name} 阈值越界: {thr} (y={y}, p={p})"
    print("[OK] youden_threshold: 退化输入下仍是有限阈值")
