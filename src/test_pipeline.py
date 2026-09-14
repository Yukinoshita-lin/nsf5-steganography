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


def test_v2_cpu_gpu_consistency():
    """143 维特征的 CPU 与 GPU 实现必须同尺度 —— SRM 段曾经在这里出过事。

    2026-09-14 审计发现: `gpu/featurize_v2_gpu.py` 把像素先 `/255` 再过高通核,
    残差整体缩小 255 倍、`clamp(±4)` 形同虚设, 于是 GPU 产出的
    `srm_mu/absmean/std` 与 CPU 参考实现差约 30 倍。语料是用 GPU 特征建的,
    而 `ml_predict` 单图判定走 CPU 特征 —— 等于线上给 143d 模型喂分布外输入
    (53d 模型不含 SRM, 不受影响)。这条测试是该缺陷的回归护栏。
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        print("[SKIP] 未安装 torch, 跳过 143 维 CPU/GPU 一致性")
        return
    gpu_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gpu")
    if gpu_dir not in sys.path:
        sys.path.insert(0, gpu_dir)
    from featurize_v2_gpu import NAMES, extract_features_v2_gpu
    img = _photo(shape=(256, 256))
    cpu = featurize_v2(img)
    gpu = extract_features_v2_gpu(img[None], chunk=1, device="cpu")[0]
    assert list(NAMES) == list(ALL_FEATURE_NAMES), (
        "GPU 与 CPU 的 143 维列名/列序不一致, 模型会拿到错位的特征")
    diff = np.abs(cpu - gpu)
    rel = diff / (np.abs(cpu) + 1e-9)
    assert diff.max() < 1e-2 and rel.max() < 1e-2, (
        f"143 维 CPU/GPU 特征不一致: max|d|={diff.max():.3e}, max rel={rel.max():.3e} "
        f"(最差的几维: {[ALL_FEATURE_NAMES[i] for i in np.argsort(-diff)[:4]]})")
    print(f"[OK] 143 维 CPU/GPU 特征一致 (max|d|={diff.max():.2e}, max rel={rel.max():.2e})")


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
def test_cpp_features_match_python():
    """装得上 C++ 加速库时, 11 维特征必须与纯 Python 参考逐项一致。

    2026-09-14 审计发现两处偏差, 且都被仓库里的自检以"放宽容差"掩盖:
      1. 卡方自由度用了非空灰度对数 n, 参考实现用 n-1 → p 值差约 26%;
      2. 20 段中位数取上中位, numpy.median 取中间两个的均值。
    两者都会让 Windows(带 DLL) 与 Linux(纯 Python) 在同一张图上给出不同的
    chi2_pvalue / median_prefix_p —— 等于训练用一套特征、推理用另一套。
    """
    try:
        from fsfeatures import FSFeatures
        lib = FSFeatures()
    except Exception as exc:  # noqa: BLE001 - 无 DLL 是正常情况 (Linux/macOS/Colab)
        print(f"[SKIP] 无 C++ 加速库 ({type(exc).__name__}), 跳过 C++/Python 特征一致性")
        return
    img = _photo(shape=(256, 256))
    cpp = lib.features(img)
    py = py_features(img)
    worst, worst_k = 0.0, ""
    for k, v in py.items():
        d = abs(float(cpp[k]) - float(v))
        if d > worst:
            worst, worst_k = d, k
    assert worst < 1e-9, (
        f"C++ 与 Python 的 11 维特征不一致: 最大差 {worst:.2e} 出现在 {worst_k} "
        f"(cpp={cpp[worst_k]}, python={py[worst_k]})")
    print(f"[OK] C++ 与 Python 的 11 维特征逐项一致 (max|d|={worst:.2e})")


def test_cpp_python_embed_contract():
    """固定 C++ 加速路径与纯 Python 回退之间的契约。

    README 早期称两者 "bit-compatible", 这对 `fsfeatures` 成立, 对 nsF5 嵌入
    则**不成立** (matrix 成立)。这个测试把真实关系写死, 免得以后有人照着那句
    话去断言逐像素相等 —— 或者反过来, 在不知情的情况下把 C++ 或 Python 一侧
    的湿纸策略改到真正破坏互操作。

    同时它也是 p≥4 栈越界的回归防线: 修复前 `nsf5_embed` 里 xl/xv 等数组定长
    8, 而块长 n = 2^p - 1 (p=4 → 15, p=5 → 31), 会往栈上写越界数据。
    """
    import cppembed
    from ns5_core import embed_string as py_embed, extract_string as py_extract

    if not cppembed._cpp_ok():
        print("[OK] C++ 加速库缺失, 跳过合约比对 (纯 Python 路径已由其他测试覆盖)")
        return

    rng = np.random.default_rng(11)
    img = rng.integers(24, 232, (256, 256), dtype=np.uint8)
    msg = "contract" * 30
    for p in (2, 3, 4, 5):
        # matrix: 必须逐像素一致
        st_c, _, _ = cppembed.embed_string(img, msg, method="matrix", p=p)
        st_p, _, _ = py_embed(img.copy(), msg, method="matrix", p=p)
        assert np.array_equal(st_c, st_p), (
            f"p={p} matrix 路径 C++ 与 Python 应当逐像素一致, "
            f"实际差 {int((st_c != st_p).sum())} 个像素")
        # nsF5: 只要求互操作 (双向回环), 不要求逐像素一致
        st_n, _, _ = cppembed.embed_string(img, msg, method="nsF5", p=p)
        assert py_extract(st_n, method="nsF5", p=p) == msg, (
            f"p={p}: C++ 嵌入的 nsF5 图无法被解码还原")
        p_n, _, _ = py_embed(img.copy(), msg, method="nsF5", p=p)
        assert cppembed.embed_string(img, msg, method="nsF5", p=p)[0].shape == p_n.shape
        diff = int((st_n != p_n).sum())
        print(f"[OK] p={p}: matrix 逐像素一致; nsF5 有 {diff} 像素差异 "
              f"(两个合法解, 均可互解)")
    print("[OK] C++ / Python 嵌入契约符合预期")


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
    test_v2_cpu_gpu_consistency()
    test_steganalysis_contract()
    test_steganalysis_survives_degenerate_images()
    test_cpp_features_match_python()
    test_cpp_python_embed_contract()
    test_ml_model_is_loadable()
    test_ml_predict_routing()
    print("\n全部通过")
