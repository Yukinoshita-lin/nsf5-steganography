"""JPEG 压缩域桥接测试: 往返 / 口令与参数错 / 容量与截断 / 分析 / 预览。

yccstego 是 Python>=3.10 的可选依赖 (pytest 作业里显式安装): 缺失时整个
模块 skip —— 否则 3.9 环境永远红。但与 GUI 测试同一纪律: "跳过"必须在
别处被真正跑过, CI 的 pytest 作业 (3.11) 装了 yccstego, 不允许两边都跳。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

import jpegstego

pytestmark = pytest.mark.skipif(not jpegstego.available(),
                                reason="yccstego 未安装 (Python<3.10 或缺 JPEG 域依赖)")


def _cover(h=96, w=128, seed=7):
    """平滑渐变 + 轻噪声的 RGB 封面: AC 系数非零, 有真实载体。"""
    rng = np.random.default_rng(seed)
    yy = np.linspace(0, 200, w)[None, :]
    xx = np.linspace(0, 80, h)[:, None]
    base = np.clip(110 + yy + xx, 0, 255)
    noise = rng.integers(-8, 9, (h, w))
    gray = np.clip(base + noise, 0, 255).astype(np.uint8)
    return np.stack([gray, gray, gray], axis=-1)


MSG = "你好, JPEG 域 nsF5!"


def test_roundtrip():
    jpg, rep = jpegstego.embed_jpeg(_cover(), MSG, p=3)
    assert rep["carriers_changed"] >= 1
    assert rep["truncated"] is False
    assert len(rep["cover_hash"]) == 32          # 16 字节认证头的 hex
    msg, cover_hash, tampered, head_match = jpegstego.extract_jpeg(jpg, p=3)
    assert msg == MSG
    assert tampered is False and head_match is True
    assert cover_hash == rep["cover_hash"]


def test_wrong_password_fails():
    jpg, _ = jpegstego.embed_jpeg(_cover(), MSG, p=3, password="口令A")
    msg, _, tampered, head_match = jpegstego.extract_jpeg(jpg, p=3, password="口令B")
    assert msg is None
    # 头部池 seed0 只由口令派生: 口令错 → 头都读不回来
    assert head_match is False


def test_wrong_p_fails():
    jpg, _ = jpegstego.embed_jpeg(_cover(), MSG, p=3)
    msg, _, _, _ = jpegstego.extract_jpeg(jpg, p=4)
    assert msg is None


def test_capacity_error():
    from yccstego.nsf5 import CapacityError
    # 16x16 全同像素 → 分块后 AC 全 0, 没有载体系数
    flat = np.full((16, 16, 3), 128, dtype=np.uint8)
    with pytest.raises(CapacityError):
        jpegstego.embed_jpeg(flat, MSG)


def test_truncate():
    small = _cover(h=32, w=32)
    long_msg = "藏" * 120          # 360 字节, 远超小图正文容量
    jpg, rep = jpegstego.embed_jpeg(small, long_msg, p=3, truncate=True)
    assert rep["truncated"] is True
    assert 0 < rep["embedded_chars"] < len(long_msg)
    msg, _, _, _ = jpegstego.extract_jpeg(jpg, p=3)
    assert msg == long_msg[:rep["embedded_chars"]]


def test_analyze_fields():
    jpg, _ = jpegstego.embed_jpeg(_cover(), MSG, p=3)
    r = jpegstego.analyze_jpeg(jpg, sensitivity="均衡")
    assert r["ok"] is True and r["n_ac"] > 0
    assert isinstance(r["stego_probability_dct"], float)
    assert isinstance(r["verdict"], str) and r["verdict"]


def test_decode_preview():
    jpg, _ = jpegstego.embed_jpeg(_cover(), MSG, p=3)
    rgb = jpegstego.decode_preview(jpg)
    assert rgb.shape == (96, 128, 3) and rgb.dtype == np.uint8


def test_unavailable_reason_shape():
    """available()/unavailable_reason() 互为表里: 可用时 reason 为空。"""
    if jpegstego.available():
        assert jpegstego.unavailable_reason() == ""


def test_vendored_root_layout():
    """源码 checkout 布局下 _vendored_root 必须找到真包根 (自愈的前提)。"""
    if jpegstego._vendored_root() is None:
        pytest.skip("无嵌套 yccstego checkout (PyPI 安装 / CI), 自愈路径不适用")
    root = jpegstego._vendored_root()
    assert root is not None, "仓库布局变了? <root>/yccstego/yccstego/__init__.py 不在"
    assert os.path.isfile(os.path.join(root, "yccstego", "nsf5.py"))


def test_selfheal_after_namespace_shadow():
    """复现用户实测事故 (2026-10-03 弹窗): 在没装 yccstego editable 的解释器
    上从仓库根运行, 顶层同名目录把 yccstego 解析成命名空间包, `from yccstego
    import api` 报 cannot import name 'api' —— 桥接层必须逐出缓存、把源码
    checkout 的真包插到 sys.path 最前后自愈。

    必须**子进程**复现: 本测试进程自己装有 editable (其 _Finder 会替子模块
    打圆场, 掩盖故障), 摘不干净; 新进程里显式摘掉 editable finder 才与用户
    环境等价。另需仓库内有嵌套 yccstego checkout 供自愈定向 (CI 的 PyPI
    安装形态没有遮蔽问题, 此用例不适用)。"""
    import subprocess
    import textwrap
    code = textwrap.dedent("""
        import sys, types
        sys.path.insert(0, 'src')
        def _is_editable(m):
            # 注意: meta_path 里放的是 finder **类**本身, type(类) 是 type,
            # 必须直接看类自己的 __name__/__module__
            return ('editable' in getattr(m, '__name__', '').lower()
                    or 'editable' in getattr(m, '__module__', '').lower())
        sys.meta_path[:] = [m for m in sys.meta_path if not _is_editable(m)]
        import jpegstego
        jpegstego._cache.update({'tried': False, 'api': None, 'error': None})
        fake = types.ModuleType('yccstego'); fake.__path__ = []
        sys.modules['yccstego'] = fake
        assert jpegstego.available() is True, jpegstego.unavailable_reason()
        assert getattr(sys.modules['yccstego'], '__file__', None), '父包应为真包'
        print('HEAL-OK')
    """)
    if jpegstego._vendored_root() is None:
        pytest.skip("无嵌套 yccstego checkout (PyPI 安装 / CI), 自愈路径不适用")
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, encoding="utf-8", cwd=repo, timeout=120)
    assert "HEAL-OK" in r.stdout, "自愈失败:\n" + r.stdout + "\n" + r.stderr


def _ycc2():
    t = jpegstego.ycc_version_tuple()
    return t is not None and t >= (0, 2, 0)


@pytest.mark.skipif(not _ycc2(), reason="yccstego >= 0.2.0 才有逐字节确定嵌入与 trace")
def test_embed_byte_deterministic():
    """0.2.0 核心升级: 相同输入 -> 完全相同的输出字节 (实验可写进回归测试)。"""
    jpg1, rep1 = jpegstego.embed_jpeg(_cover(), "确定性 42", p=3, quality=85)
    jpg2, rep2 = jpegstego.embed_jpeg(_cover(), "确定性 42", p=3, quality=85)
    assert jpg1 == jpg2
    assert rep1["carriers_changed"] == rep2["carriers_changed"]
    assert rep1["wet_points"] >= 0
    # 全局随机状态扰动不得影响结果 (0.1.4 的病灶)
    np.random.seed(123)
    np.random.rand(4096)
    jpg3, _ = jpegstego.embed_jpeg(_cover(), "确定性 42", p=3, quality=85)
    assert jpg1 == jpg3


@pytest.mark.skipif(not _ycc2(), reason="yccstego >= 0.2.0 才有逐字节确定嵌入与 trace")
def test_trace_changes():
    """trace: 每个被修改系数的 from/to 轨迹 (可视化用), 且不改变嵌入结果。"""
    jpg, rep = jpegstego.embed_jpeg(_cover(), "trace me", p=3, quality=85,
                                    trace=True)
    ch = rep["changes"]
    assert ch and len(ch) == rep["carriers_changed"]
    need = {"cell", "block", "rc", "pool", "kind", "from", "to"}
    assert all(need <= set(c) for c in ch)
    assert {c["pool"] for c in ch} == {"head", "body"}
    for c in ch:
        assert c["kind"] in ("shrink", "wet", "boost"), c
        assert c["to"] == c["from"] - (1 if c["from"] > 0 else -1)             or c["kind"] == "boost", c
    jpg2, _ = jpegstego.embed_jpeg(_cover(), "trace me", p=3, quality=85)
    assert jpg == jpg2, "trace 开关不得改变嵌入结果"
