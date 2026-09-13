"""端到端管线自测: 特征提取 / SRM / ML 判定 / 隐写分析契约。

覆盖此前零测试的公共面。`python src/test_pipeline.py` 与 `pytest` 均可运行。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np

import steganalysis as SA
from featurize_v2 import ALL_FEATURE_NAMES, BASE_11, N_FEAT, featurize_v2
from py_features import features as py_features


def _photo(seed=7, shape=(512, 512)):
    """一张有结构的灰度图 (纯噪声会让 SRM 残差退化成常数)。"""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    img = (110 + 45 * np.sin(xx / 23.0) + 35 * np.cos(yy / 31.0)
           + rng.integers(-4, 5, shape))
    return np.clip(img, 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------- #
#  特征提取
# --------------------------------------------------------------------------- #
def test_v1_features_contract():
    f = py_features(_photo(shape=(256, 256)))
    assert len(f) == 11, f"v1 特征应为 11 维, 实际 {len(f)}"
    for k in BASE_11:
        assert k in f, f"v1 特征缺少 {k}"
        assert np.isfinite(f[k]), f"{k} 不是有限值"
    print("[OK] v1 纯 Python 特征: 11 维且键名齐全")


def test_v2_features_shape_and_finiteness():
    assert N_FEAT == 143, f"N_FEAT 应为 143, 实际 {N_FEAT}"
    assert len(ALL_FEATURE_NAMES) == 143
    assert ALL_FEATURE_NAMES[:11] == BASE_11, "143 维前 11 列必须就是 v1 的 11 维"
    x = featurize_v2(_photo())
    assert x.shape == (143,), f"v2 特征形状应为 (143,), 实际 {x.shape}"
    assert np.isfinite(x).all(), "v2 特征里出现 NaN/Inf"
    print("[OK] v2 特征: 143 维、有限、前 11 列与 v1 对齐")


def test_v2_53d_subset_is_consistent():
    """部署的 53d 模型按列名从 143 维里取子集 —— 列名必须都能对上。

    这条断言的价值: `ml_predict` 拿模型里的 features 名去 ALL_FEATURE_NAMES
    里 index(), 一旦两边命名漂移, 53d 模型会静默失效 (退回"特征名不匹配")。
    """
    import ml_predict as MP
    names = MP.V1_FEAT_KEYS
    missing = [n for n in names if n not in ALL_FEATURE_NAMES]
    assert not missing, f"ml_predict 的 v1 列名在 v2 里找不到: {missing}"
    srm = [n for n in ALL_FEATURE_NAMES if n.startswith("srm_")]
    assert len(srm) == 90, f"SRM 统计量应为 90 列, 实际 {len(srm)}"
    d53 = [n for n in ALL_FEATURE_NAMES if n not in set(srm)]
    assert len(d53) == 53, f"53d 子集应为 53 列, 实际 {len(d53)}"
    print("[OK] 143d / 53d / 11d 三套列名自洽 (90 SRM + 53 可解释)")


def test_srm_kernels():
    from srm_filter import SRM_KERNELS, srm_residuals_np, srm_residuals_torch
    assert SRM_KERNELS.shape == (30, 5, 5), f"SRM 核形状 {SRM_KERNELS.shape}"
    img = _photo(shape=(128, 128))
    r = srm_residuals_np(img)
    assert r.shape == (30, 128, 128), f"残差形状 {r.shape}"
    assert np.isfinite(r).all()
    try:
        import torch  # noqa: F401
    except ImportError:
        print("[OK] SRM 30 核 (跳过 torch 一致性: 未安装 torch)")
        return
    rt = srm_residuals_torch(img)
    if hasattr(rt, "detach"):          # torch 张量 (可能还在 GPU 上)
        rt = rt.detach().cpu().numpy()
    diff = float(np.abs(r - rt).max())
    assert diff < 1e-3, f"numpy 与 torch 的 SRM 残差不一致, 最大差 {diff:.2e}"
    print(f"[OK] SRM 30 核, numpy/torch 双实现一致 (max diff {diff:.2e})")


# --------------------------------------------------------------------------- #
#  隐写分析契约
# --------------------------------------------------------------------------- #
def test_steganalysis_contract():
    r = SA.analyze(_photo(shape=(256, 256)))
    for k in ("stego_probability", "verdict", "RS_Gn", "RS_Gr", "chi2_pvalue",
              "est_rate", "lsb_diff_entropy"):
        assert k in r, f"analyze() 结果缺少 {k}"
    p = r["stego_probability"]
    assert 0.0 <= p <= 1.0, f"概率越界: {p}"
    assert isinstance(r["verdict"], str) and r["verdict"]
    print(f"[OK] analyze() 契约完整 (prob={p:.3f}, verdict={r['verdict']})")


def test_steganalysis_survives_degenerate_images():
    """强二值图曾触发 lgamma(0) 崩溃 (v1.2.1 修复), 不能回归。"""
    for name, img in (("全黑", np.zeros((64, 64), np.uint8)),
                      ("全白", np.full((64, 64), 255, np.uint8)),
                      ("二值", (np.indices((64, 64)).sum(0) % 2 * 255).astype(np.uint8))):
        r = SA.analyze(img)
        assert 0.0 <= r["stego_probability"] <= 1.0, f"{name} 概率越界"
    print("[OK] 退化图像 (全黑/全白/强二值) 不再崩溃")


# --------------------------------------------------------------------------- #
#  ML 判定
# --------------------------------------------------------------------------- #
def test_ml_model_is_loadable():
    """模型必须随仓库分发, 否则 clone 之后 ML 功能直接不可用。

    这里刻意用 assert 而不是 skip: 模型缺失是要立刻暴露的回归, 不是可以被
    环境差异掩盖的情况。`.gitignore` 用白名单把两个部署模型放了进来。
    """
    import ml_predict as MP
    pred = MP.MLPredictor()
    assert pred.available, (
        f"ML 模型未能加载: {pred.model_path}\n"
        f"  原因: {pred.load_error}\n"
        "  该文件应随仓库分发 (.gitignore 白名单 / Dockerfile 的 COPY models); "
        "若确实缺失, 需重新训练 (注意 src/train_model.py 训练的是 "
        "LR/RF/GB/XGB 家族, 不是仓库里这两个 LGB 模型)。")
    print(f"[OK] 部署模型可加载: {os.path.basename(MP.MODEL_PATH)}")


def test_ml_predict_routing():
    import ml_predict as MP
    pred = MP.MLPredictor()
    img = _photo(shape=(512, 512))
    r = pred.predict(img)
    if not pred.available:
        assert r["verdict"] == "ML 模型未加载"
        print("[OK] ML 模型缺失时返回明确的未加载判读")
        return
    p = r["probability"]
    assert p is not None and 0.0 <= p <= 1.0, (
        f"概率异常: {p} (verdict={r['verdict']}; 特征维度不支持时会是 None)")
    feats = pred._pkg.get("features", [])
    print(f"[OK] ML 判定路由正确 (特征维度 {len(feats)}, prob={p:.3f}, "
          f"verdict={r['verdict']})")


if __name__ == "__main__":
    test_v1_features_contract()
    test_v2_features_shape_and_finiteness()
    test_v2_53d_subset_is_consistent()
    test_srm_kernels()
    test_steganalysis_contract()
    test_steganalysis_survives_degenerate_images()
    test_ml_model_is_loadable()
    test_ml_predict_routing()
    print("\n全部通过")
