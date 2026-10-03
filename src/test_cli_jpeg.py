"""CLI 的 JPEG 压缩域与实验重跑 (repro) 自测: 真实子进程链路。

覆盖: embed/extract/analyze 的 --jpeg 往返 / 域不一致被拒绝 / 档案 JSON
不含明文 / repro 像素域逐字节复现与 JPEG 域往返契约 / 档案损坏的友好报错。
依赖 yccstego (Python>=3.10): 缺失时 JPEG 用例 skip, pixel 域的 repro 用例
照跑 —— 与 test_jpeg.py 同一纪律: 跳过必须在别处被真正跑过 (CI 3.11)。
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import jpegstego  # noqa: E402
import experiment as EXP  # noqa: E402

CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py")

JPEG_MARK = pytest.mark.skipif(not jpegstego.available(),
                               reason="yccstego 未安装 (Python<3.10 或缺依赖)")


def _run(*args, stdin=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, CLI, *args],
                          capture_output=True, text=True, encoding="utf-8",
                          input=stdin, env=env, timeout=180)


def _cover(path, size=96):
    rng = np.random.default_rng(7)
    y = np.linspace(0, 220, size)[None, :]
    x = np.linspace(0, 90, size)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (size, size)), 12, 255)
    from PIL import Image
    Image.fromarray(img.astype(np.uint8)).save(path)
    return path


def test_help_lists_repro():
    r = _run("--help")
    assert r.returncode == 0, r.stderr
    assert "repro" in r.stdout
    print("[OK] --help 列出 repro 子命令")


@JPEG_MARK
@pytest.mark.slow
def test_jpeg_embed_extract_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        r = _run("embed", cover, "--jpeg", "-m", "压缩域你好", stdin=None)
        assert r.returncode == 0, r.stderr
        stego = os.path.join(d, "c_stego.jpg")
        assert os.path.exists(stego), r.stdout
        assert "DCT 系数" in r.stdout
        r2 = _run("extract", stego, "--jpeg")
        assert r2.returncode == 0, r2.stderr
        assert "压缩域你好" in r2.stdout
        assert "JPEG 压缩域" in r2.stdout
        print("[OK] embed --jpeg → extract --jpeg 往返一致")


@JPEG_MARK
@pytest.mark.slow
def test_jpeg_embed_json_record_and_repro():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        rec_path = os.path.join(d, "exp.json")
        r = _run("embed", cover, "--jpeg", "-m", "档案消息", "--json")
        assert r.returncode == 0, r.stderr
        record = json.loads(r.stdout)
        assert record["schema"] == EXP.SCHEMA
        assert record["algorithm"]["domain"] == "jpeg"
        assert record["result"]["cell_unit"] == "coefficients"
        assert "档案消息" not in r.stdout, "档案绝不携带消息明文"
        with open(rec_path, "w", encoding="utf-8") as f:
            f.write(r.stdout)
        r2 = _run("repro", rec_path, "-m", "档案消息")
        assert r2.returncode == 0, r2.stderr + r2.stdout
        assert "重跑通过" in r2.stdout
        # JPEG 域契约按 yccstego 版本分档 (PyPI 尚无 0.2.0 时 CI 装的是 0.1.4)
        t = jpegstego.ycc_version_tuple() or (0,)
        assert ("byte-deterministic" if t >= (0, 2, 0)
                else "round-trip-verified") in r2.stdout
        # 换原文必须失败
        r3 = _run("repro", rec_path, "-m", "另一段话")
        assert r3.returncode == 1
        print("[OK] embed --jpeg --json → repro 往返契约通过, 换原文报错")


@JPEG_MARK
@pytest.mark.slow
def test_jpeg_domain_mismatch_rejected():
    """教学第一坑: 嵌入用了 --jpeg, 解码不带 --jpeg 必须失败且报错可读。"""
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        assert _run("embed", cover, "--jpeg", "-m", "x").returncode == 0
        stego = os.path.join(d, "c_stego.jpg")
        r = _run("extract", stego)          # 忘了 --jpeg
        assert r.returncode == 1
        assert "Traceback" not in r.stderr
        print("[OK] 域不一致 (JPEG 含密图按像素域解码): 拒绝并给出提示")


@JPEG_MARK
@pytest.mark.slow
def test_jpeg_wrong_password_fails():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        assert _run("embed", cover, "--jpeg", "-m", "x", "-p", "A").returncode == 0
        stego = os.path.join(d, "c_stego.jpg")
        r = _run("extract", stego, "--jpeg", "-p", "B")
        assert r.returncode == 1
        assert "认证头" in r.stderr or "口令" in r.stderr
        print("[OK] JPEG 域口令错误: 拒绝并指明原因")


@JPEG_MARK
@pytest.mark.slow
def test_jpeg_analyze_json():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        assert _run("embed", cover, "--jpeg", "-m", "x").returncode == 0
        r = _run("analyze", os.path.join(d, "c_stego.jpg"), "--jpeg", "--json")
        assert r.returncode == 0, r.stderr
        payload = json.loads(r.stdout)
        for key in ("n_ac", "unit_frac", "stego_probability_dct", "verdict"):
            assert key in payload, f"JPEG 分析 JSON 缺少 {key}"
        print("[OK] analyze --jpeg --json 键齐全")


@pytest.mark.slow
def test_repro_pixel_byte_deterministic():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        r = _run("embed", cover, "-m", "可复现", "--json")
        assert r.returncode == 0, r.stderr
        rec_path = os.path.join(d, "exp.json")
        with open(rec_path, "w", encoding="utf-8") as f:
            f.write(r.stdout)
        record = json.loads(r.stdout)
        assert record["determinism"] == EXP.DET_BYTE
        r2 = _run("repro", rec_path, "-m", "可复现")
        assert r2.returncode == 0, r2.stderr + r2.stdout
        assert "byte-deterministic" in r2.stdout
        assert "含密图哈希一致" in r2.stdout
        r3 = _run("repro", rec_path, "-m", "不同的消息")
        assert r3.returncode == 1
        print("[OK] 像素域 repro: 逐字节复现通过, 换消息报错")


@pytest.mark.slow
def test_repro_broken_record_friendly():
    with tempfile.TemporaryDirectory() as d:
        bad = os.path.join(d, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write('{"schema": "other/1"}')
        r = _run("repro", bad, "-m", "x")
        assert r.returncode == 1
        assert "不是本工具的实验档案" in r.stderr
        assert "Traceback" not in r.stderr
        print("[OK] 非法档案: 友好报错")
