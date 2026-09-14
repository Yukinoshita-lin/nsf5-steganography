"""部署模型生产者 / 权威结果表的契约自测。

守两件事, 它们都是 2026-09-13 才补上的可验证性缺口:

1. **两个部署模型必须能被 `experiments/train_deploy_models.py` 复现** ——
   生产者的特征集/划分口径一旦和随仓库分发的 `.joblib` 脱钩, 模型就又变成
   不可复现的黑盒。这里直接比对"生产者会训练哪 143/53 列"与"模型 payload 里
   声明的 features"。
2. **权威结果表必须带语料与协议** —— 同一指标名跨语料混用是评审最容易
   判定为数据不可信的地方 (项目真实发生过一次: 11 维结果被标成 53 维)。

本文件不训练模型, 因此毫秒级完成; `pytest` 与 `python src/test_results_contract.py`
均可运行。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJ, "experiments"))

import numpy as np

MODEL_FILES = ["models/stego_classifier.joblib",
               "models/stego_classifier_v2_jpeg_lgb_51d.joblib"]


def _load(path):
    from joblib import load
    return load(os.path.join(PROJ, path))


# --------------------------------------------------------------------------- #
#  1. 部署模型 payload
# --------------------------------------------------------------------------- #
def test_deploy_model_payload_keys():
    """ml_predict 依赖的键一个都不能少, 阈值必须是合法概率。"""
    required = ["model", "features", "threshold", "threshold_low_fp",
                "held_out_auc", "name"]
    for path in MODEL_FILES:
        pkg = _load(path)
        for k in required:
            assert k in pkg, f"{path} 缺少 ml_predict 依赖的键: {k}"
        n = len(pkg["features"])
        assert n in (143, 53), f"{path} 特征数 {n} 不在 {143, 53} 内"
        assert 0.0 < pkg["threshold"] < 1.0, f"{path} threshold 越界"
        assert 0.0 < pkg["threshold_low_fp"] < 1.0, f"{path} threshold_low_fp 越界"
        assert 0.5 < pkg["held_out_auc"] < 1.0, f"{path} held_out_auc 异常"
        print(f"[OK] {os.path.basename(path)}: {n} 维, thr={pkg['threshold']:.4f}, "
              f"AUC={pkg['held_out_auc']:.4f}")


def test_deploy_model_provenance_present():
    """两个模型都必须带溯源字段 —— 否则"可复现"只是一句声明。"""
    for path in MODEL_FILES:
        pkg = _load(path)
        prov = pkg.get("provenance")
        assert prov, f"{path} 没有 provenance 字段"
        assert prov["producer"] == "experiments/train_deploy_models.py", prov["producer"]
        assert prov["split"]["by"] == "photo_id", "划分必须按源图"
        assert prov["dataset"].endswith(".csv")
        print(f"[OK] {os.path.basename(path)}: producer={prov['producer']} "
              f"dataset={prov['dataset']} seed={prov['split']['seed']}")


# --------------------------------------------------------------------------- #
#  2. 生产者口径与随包模型一致
# --------------------------------------------------------------------------- #
def test_producer_feature_sets_match_shipped_models():
    """生产者算出的特征列必须与模型 payload 声明的 features 逐位一致。

    列序也算 —— LightGBM 的特征捆绑对列序敏感, 换序会让 AUC 漂移
    (实测同一份数据换序可以从 0.9100 掉到 0.9083)。
    """
    from train_deploy_models import feature_sets
    sets = feature_sets()
    assert len(sets["143d"]) == 143, f"143d 应 143 列, 实际 {len(sets['143d'])}"
    assert len(sets["53d"]) == 53, f"53d 应 53 列, 实际 {len(sets['53d'])}"
    for path, key in zip(MODEL_FILES, ["143d", "53d"]):
        pkg = _load(path)
        assert list(pkg["features"]) == sets[key], (
            f"{os.path.basename(path)} 的 features 与生产者 {key} 特征集不一致 "
            f"(列序也算)")
        print(f"[OK] 生产者 {key} 特征集与 {os.path.basename(path)} 逐位一致")


def test_producer_split_is_grouped():
    """按源图划分: 同一源图不跨侧; 同 seed 可复现; 比例接近 test_size。"""
    from train_deploy_models import split_by_photo
    pid = np.repeat(np.array([f"p{i:03d}" for i in range(100)]), 4)
    a = split_by_photo(pid, seed=0, test_size=0.25)
    b = split_by_photo(pid, seed=0, test_size=0.25)
    assert np.array_equal(a, b), "同 seed 两次划分不一致"
    leaks = [p for p in np.unique(pid) if 0 < a[pid == p].sum() < (pid == p).sum()]
    assert not leaks, f"有源图被拆到两侧: {leaks[:3]}"
    frac = a.mean()
    assert 0.20 <= frac <= 0.30, f"验证集比例 {frac:.3f} 偏离 test_size"
    print(f"[OK] 按源图划分: 无跨侧泄漏, 验证集比例 {frac:.3f}, 同 seed 可复现")


def test_corpus_grouping_guard_rejects_orphan_ids():
    """语料若出现"孤儿 id 块"（部分 photo_id 只有单一 variant），必须拒绝训练。

    这是 2026-09-14 审计最严重缺陷的回归护栏：当年 414 个 `clean_jpeg` 行各占一个
    独立 photo_id，于是"按源图划分"形同虚设、AUC 被抬高约 0.14。
    """
    import pandas as pd
    from train_deploy_models import check_corpus_grouping

    good = pd.DataFrame({
        "photo_id": [0, 0, 0, 1, 1, 1],
        "variant": ["clean", "clean_jpeg", "v0"] * 2,
    })
    check_corpus_grouping(good, "good.csv")      # 不抛

    broken = pd.DataFrame({
        "photo_id": [0, 0, 0, 1, 1, 1, 101, 102],
        "variant": ["clean", "clean_jpeg", "v0"] * 2 + ["clean_jpeg", "clean_jpeg"],
    })
    try:
        check_corpus_grouping(broken, "broken.csv")
    except SystemExit as exc:
        assert "分组不变量" in str(exc), f"错误信息没说清原因: {exc}"
        print("[OK] 孤儿 id 块被拒绝 (分组不变量护栏生效)")
        return
    raise AssertionError("破坏分组不变量的语料竟然通过了检查")


# --------------------------------------------------------------------------- #
#  3. 权威结果表
# --------------------------------------------------------------------------- #
def test_canonical_table_has_corpus_and_protocol():
    """每一行都必须能回答"什么语料、什么协议、可不可溯源"。"""
    import build_results_table as B
    df = B.build()
    assert len(df) > 0, "权威表为空"
    assert list(df.columns) == B.COLS, "列定义漂移"
    for col in ("corpus", "protocol_id", "model", "metric", "value", "traceable"):
        assert df[col].astype(str).str.len().gt(0).all(), f"{col} 有空值"
    assert set(df["corpus"]) <= set(B.CORPORA), "出现未登记的语料"
    assert set(df["protocol_id"]) <= set(B.PROTOCOLS), "出现未登记的协议"
    key = ["corpus", "protocol_id", "model", "metric", "subject"]
    dup = df[df.duplicated(key, keep=False)]
    assert dup.empty, f"权威表有重复行:\n{dup[key].to_string()}"
    tr = df[df["traceable"] == "yes"]
    assert (tr["source_file"].astype(str).str.len() > 0).all(), "可溯源行缺少来源文件"
    untr = df[df["traceable"] == "no"]
    assert (untr["note"].astype(str).str.len() > 0).all(), "不可溯源行必须写明原因"
    print(f"[OK] 权威表: {len(df)} 行 "
          f"(可溯源 {len(tr)} / 不可溯源 {len(untr)}), 语料与协议均已登记")


def test_canonical_doc_is_in_sync_when_present():
    """docs/RESULTS.md 若存在且输入齐备, 必须与生成器输出一致 (防止手改后漂移)。

    输入 CSV 不入库, CI / 新 clone 里拿不到, 此时只能跳过 —— 强行断言会因为
    文档里有 BOSSbase/校园两节而产物里没有, 把 CI 判成红。
    """
    import build_results_table as B
    if not os.path.exists(B.OUT_DOC):
        print("[SKIP] docs/RESULTS.md 不存在")
        return
    if not B.inputs_present():
        print("[SKIP] experiments/data 下的输入产物不全 (不入库), 跳过文档同步校验")
        return
    with open(B.OUT_DOC, "r", encoding="utf-8") as fh:
        on_disk = fh.read()
    assert on_disk.strip() == B.render_doc(B.build()).strip(), (
        "docs/RESULTS.md 与 build_results_table.py 的输出不同步; "
        "跑 `python experiments/build_results_table.py` 重新生成")
    print("[OK] docs/RESULTS.md 与生成器输出同步")


if __name__ == "__main__":
    test_deploy_model_payload_keys()
    test_deploy_model_provenance_present()
    test_producer_feature_sets_match_shipped_models()
    test_producer_split_is_grouped()
    test_corpus_grouping_guard_rejects_orphan_ids()
    test_canonical_table_has_corpus_and_protocol()
    test_canonical_doc_is_in_sync_when_present()
    print("\n全部通过")
