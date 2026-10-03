"""进程内覆盖 CLI 的 JPEG 域与 repro 全分支 (2026-10-03 新增)。

为什么要另开一个文件
--------------------
`test_cli_jpeg.py` 走的是**真实子进程** (端到端契约, 保留); 但覆盖率看不到
子进程里的代码 —— CI 的 pytest 作业因此从 69.1% 掉到 63.85% (门槛 65%),
新增的 `_cmd_embed_jpeg` / `_cmd_extract_jpeg` / `_cmd_analyze_jpeg` /
`_cmd_repro` 一分覆盖都拿不到。契约测试与覆盖测试是两件事, 这里补后者:
直接调 `cli.main([...])`, 把每条分支 (缺依赖 / 容量不足 / 覆盖已存在 /
截断 / 提取失败 / 无匹配 glob / 档案损坏 / 版本不一致…) 都真的走一遍。

与 `test_cli.py` 的进程内用例同一纪律; yccstego 缺失时 JPEG 域用例 skip
(CI 3.11 装了 yccstego, 必须真跑)。
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import experiment as EXP  # noqa: E402
import jpegstego  # noqa: E402

JPEG_MARK = pytest.mark.skipif(not jpegstego.available(),
                               reason="yccstego 未安装 (Python<3.10 或缺依赖)")


def _stdout(argv, capsys=None):
    """跑一条 CLI 命令, 返回 (returncode, stdout, stderr)。"""
    buf, err = io.StringIO(), io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        with redirect_stderr(err):
            rc = cli.main(argv)
    finally:
        sys.stdout = old
    return rc, buf.getvalue(), err.getvalue()


def _cover(path, size=96, seed=7):
    """造一张有纹理的灰度封面 (纯色图 AC 系数太少, JPEG 域容量不足)。"""
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 220, size)[None, :]
    x = np.linspace(0, 90, size)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (size, size)), 12, 255)
    from PIL import Image
    Image.fromarray(img.astype(np.uint8)).save(path)
    return path


# --------------------------------------------------------------------------- #
#  JPEG 域: embed / extract / analyze
# --------------------------------------------------------------------------- #
@JPEG_MARK
def test_inproc_embed_jpeg_human_and_json():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        out = os.path.join(d, "s.jpg")
        rc, so, _ = _stdout(["embed", cover, "--jpeg", "-m", "压缩域", "-o", out])
        assert rc == 0, so
        assert "DCT 系数" in so and "JPEG 压缩域" in so
        assert os.path.exists(out)
        # 已存在 → 覆盖提示那条分支
        rc, so2, se2 = _stdout(["embed", cover, "--jpeg", "-m", "压缩域", "-o", out])
        assert rc == 0
        assert "已覆盖" in se2
        # --json: 档案走 stdout, 且不含明文
        rc, so3, _ = _stdout(["embed", cover, "--jpeg", "-m", "压缩域", "--json"])
        assert rc == 0
        rec = json.loads(so3)
        assert rec["schema"] == EXP.SCHEMA
        assert rec["algorithm"]["domain"] == "jpeg"
        assert rec["result"]["cell_unit"] == "coefficients"
        assert "压缩域" not in so3
        print("[OK] 进程内 embed --jpeg: 人读 / 覆盖提示 / JSON 档案")


@JPEG_MARK
def test_inproc_embed_jpeg_truncated_report_path(monkeypatch):
    """report["truncated"] 为真时: 档案按 UTF-8 前缀记账 + 打印截断提示。

    真链路里 truncate 只在桥接层默认关闭 (CLI 不暴露该开关, 硬截断会毁消息),
    所以这里用 monkeypatch 造出截断报告 —— 覆盖的是 CLI 对它的**记账口径**,
    而不是 yccstego 的截断实现 (那由 test_jpeg.py 管)。"""
    real = jpegstego.embed_jpeg

    def fake(source, text, p=3, password="", quality=85, truncate=False,
             trace=False):
        jpg, rep = real(source, text, p=p, password=password, quality=quality)
        rep = dict(rep)
        rep["truncated"] = True
        rep["embedded_chars"] = 4          # 只写入 "ABCD"
        return jpg, rep

    monkeypatch.setattr(jpegstego, "embed_jpeg", fake)
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        rc, so, _ = _stdout(["embed", cover, "--jpeg", "-m", "ABCDEFGH",
                             "--json"])
        assert rc == 0, so
        rec = json.loads(so)
        assert rec["result"]["truncated"] is True
        assert rec["payload"]["chars"] == 4
        # 16 bit 头 + 4 个 ASCII 字符 = 48 bit (按真正写入的前缀记账)
        assert rec["payload"]["bits"] == 16 + 8 * 4
        rc, so, _ = _stdout(["embed", cover, "--jpeg", "-m", "ABCDEFGH",
                             "-o", os.path.join(d, "t.jpg")])
        assert rc == 0 and "已按 UTF-8 安全截断到 4 字符" in so
        print("[OK] 进程内 embed --jpeg: 截断报告按 UTF-8 前缀记账 + 提示")


@JPEG_MARK
def test_inproc_embed_jpeg_capacity_error_and_missing_cover():
    with tempfile.TemporaryDirectory() as d:
        tiny = _cover(os.path.join(d, "tiny.png"), size=8)
        rc, _, se = _stdout(["embed", tiny, "--jpeg", "-m", "x" * 2000])
        assert rc == 1
        assert "容量不足" in se or "失败" in se
        rc2, _, se2 = _stdout(["embed", os.path.join(d, "nope.png"),
                               "--jpeg", "-m", "x"])
        assert rc2 == 1 and se2
        print("[OK] 进程内 embed --jpeg: 容量不足 / 封面缺失")


@JPEG_MARK
def test_inproc_extract_jpeg_paths():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        stego = os.path.join(d, "s.jpg")
        assert _stdout(["embed", cover, "--jpeg", "-m", "解码我",
                        "-p", "k", "-o", stego])[0] == 0
        rc, so, _ = _stdout(["extract", stego, "--jpeg", "-p", "k"])
        assert rc == 0 and "解码我" in so
        # 口令错 → 认证头失配分支
        rc, _, se = _stdout(["extract", stego, "--jpeg", "-p", "bad"])
        assert rc == 1 and ("认证头" in se or "口令" in se)
        # 文件不存在
        rc, _, se = _stdout(["extract", os.path.join(d, "nope.jpg"), "--jpeg"])
        assert rc == 1 and se
        print("[OK] 进程内 extract --jpeg: 成功 / 认证头失配 / 文件缺失")


@JPEG_MARK
def test_inproc_analyze_jpeg_paths():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        stego = os.path.join(d, "s.jpg")
        assert _stdout(["embed", cover, "--jpeg", "-m", "x", "-o", stego])[0] == 0
        rc, so, _ = _stdout(["analyze", stego, "--jpeg"])
        assert rc == 0 and "隐写概率" in so and "像素域参照" in so
        rc, so, _ = _stdout(["analyze", stego, "--jpeg", "--json"])
        assert rc == 0 and json.loads(so)["n_ac"] > 0
        # 多图: 目标批次里混入"glob 未命中"与"文件不存在"两种失败
        rc, so, _ = _stdout(["analyze", os.path.join(d, "*.jpg"), "--jpeg"])
        assert rc == 0 and "隐写概率" in so
        rc, so, _ = _stdout(["analyze", os.path.join(d, "*.bmp"),
                             os.path.join(d, "nope.png"), "--jpeg"])
        assert rc == 1 and "无匹配文件" in so and "无法读取图像" in so
        assert "[失败]" in so
        # 全同像素 PNG (解析层直接抛错): 单图也要给可读错误
        from PIL import Image
        flat = os.path.join(d, "flat.png")
        Image.fromarray(np.full((64, 64), 128, np.uint8)).save(flat)
        rc, so, se = _stdout(["analyze", flat, "--jpeg"])
        assert rc == 1 and "不是有效的 JPEG 位流" in so + se
        assert "Traceback" not in se
        print("[OK] 进程内 analyze --jpeg: 单图 / JSON / 批量两种失败 / 非位流")


@JPEG_MARK
def test_inproc_analyze_jpeg_rejects_non_jpeg_bitstream():
    """把 PNG 当 --jpeg 传进来: 解析层会抛 KeyError, 必须变成可读错误而非 traceback。"""
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        rc, so, se = _stdout(["analyze", cover, "--jpeg"])
        assert rc == 1
        assert "不是有效的 JPEG 位流" in se or "不是有效的 JPEG 位流" in so
        assert "Traceback" not in se
        print("[OK] 进程内 analyze --jpeg: 非 JPEG 位流给可读错误, 不甩 traceback")


@JPEG_MARK
def test_inproc_jpeg_without_dependency_reports_reason():
    """依赖缺失时四个入口都必须给出可行动的错误 (monkeypatch 掉 _api)。"""
    def _boom():
        raise jpegstego.JpegDomainUnavailable("伪造: 未安装 yccstego")

    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        jpegstego._cache.update({"tried": True, "api": None, "error": "伪造"})
        orig = jpegstego._api
        jpegstego._api = _boom          # available() 也随之变 False
        try:
            for argv in (["embed", cover, "--jpeg", "-m", "x"],
                         ["extract", cover, "--jpeg"],
                         ["analyze", cover, "--jpeg"]):
                rc, _, se = _stdout(argv)
                assert rc == 1 and "yccstego" in se, argv
        finally:
            jpegstego._api = orig
            jpegstego._cache.update({"tried": False, "api": None, "error": None})
        print("[OK] 进程内 JPEG 三入口: 依赖缺失 → 退出码 1 + 可行动提示")


# --------------------------------------------------------------------------- #
#  实验档案 repro
# --------------------------------------------------------------------------- #
def _build_record(d, domain="pixel", message="重跑我", password=""):
    """按 CLI 路径建一份真档案 (embed --json), 返回 (record_path, record, cover)。"""
    cover = _cover(os.path.join(d, "c.png"))
    argv = ["embed", cover, "-m", message, "--json"]
    if domain == "jpeg":
        argv = ["embed", cover, "--jpeg", "-m", message,
                "-o", os.path.join(d, "s.jpg"), "--json"]
    if password:
        argv += ["-p", password]
    rc, so, se = _stdout(argv)
    assert rc == 0, se
    read = os.path.join(d, "exp.json")
    with open(read, "w", encoding="utf-8") as f:
        f.write(so)
    return read, json.loads(so), cover


def test_inproc_repro_pixel_branches():
    with tempfile.TemporaryDirectory() as d:
        rec_path, rec, cover = _build_record(d, "pixel")
        assert rec["determinism"] == EXP.DET_BYTE
        # 通过 (含 -o 落盘分支)
        out = os.path.join(d, "again.png")
        rc, so, _ = _stdout(["repro", rec_path, "-m", "重跑我", "-c", cover,
                             "-o", out])
        assert rc == 0 and "重跑通过" in so and "重跑产物" in so
        assert os.path.exists(out)
        # 换原文 → 校验失败
        rc, so, se = _stdout(["repro", rec_path, "-m", "别的", "-c", cover])
        assert rc == 1 and "重跑未通过" in se and "[FAIL]" in so
        # 封面不存在 / 档案里没有封面路径
        rc, _, se = _stdout(["repro", rec_path, "-m", "重跑我",
                             "-c", os.path.join(d, "nope.png")])
        assert rc == 1 and "封面文件不存在" in se
        no_cover = dict(rec)
        no_cover["cover"] = {"sha256": rec["cover"]["sha256"], "path": None}
        p2 = os.path.join(d, "nocover.json")
        with open(p2, "w", encoding="utf-8") as f:
            json.dump(no_cover, f)
        rc, _, se = _stdout(["repro", p2, "-m", "重跑我"])
        assert rc == 1 and "没有封面路径" in se
        print("[OK] 进程内 repro (像素域): 通过 / 换原文 / 封面缺失两分支")


def test_inproc_repro_record_errors():
    with tempfile.TemporaryDirectory() as d:
        # 读不了 / JSON 坏
        bad = os.path.join(d, "bad.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{ 不是 json")
        rc, _, se = _stdout(["repro", bad, "-m", "x"])
        assert rc == 1 and "无法读取实验档案" in se
        rc, _, se = _stdout(["repro", os.path.join(d, "nope.json"), "-m", "x"])
        assert rc == 1 and "无法读取实验档案" in se
        # schema 不对
        other = os.path.join(d, "other.json")
        with open(other, "w", encoding="utf-8") as f:
            json.dump({"schema": "other/1"}, f)
        rc, _, se = _stdout(["repro", other, "-m", "x"])
        assert rc == 1 and "不是本工具的实验档案" in se
        print("[OK] 进程内 repro: 损坏 JSON / 文件缺失 / schema 不符")


def test_inproc_repro_needs_message_from_stdin(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        rec_path, _, cover = _build_record(d, "pixel")
        # 交互式 tty → 提示用 -m
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
        rc, _, se = _stdout(["repro", rec_path, "-c", cover])
        assert rc == 2 and "请用 -m 提供原文" in se
        # 管道传入空内容 → 退出码 2
        monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
        monkeypatch.setattr(cli, "_stdin_text", lambda: "")
        rc, _, se = _stdout(["repro", rec_path, "-c", cover])
        assert rc == 2 and "原文为空" in se
        # 管道传入正确原文 → 通过
        monkeypatch.setattr(cli, "_stdin_text", lambda: "重跑我")
        rc, so, _ = _stdout(["repro", rec_path, "-c", cover])
        assert rc == 0 and "重跑通过" in so
        print("[OK] 进程内 repro: tty 提示 / 空 stdin / 管道原文")


@JPEG_MARK
def test_inproc_repro_jpeg_locked_and_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        rec_path, rec, cover = _build_record(d, "jpeg", message="重跑JPEG")
        assert rec["determinism"] == EXP.DET_BYTE_SAMEVER
        # 版本一致 (>=0.2.0) → 字节级契约分支
        rc, so, se = _stdout(["repro", rec_path, "-m", "重跑JPEG", "-c", cover])
        assert rc == 0, se + so
        assert "重跑通过" in so and "byte-deterministic" in so
        # 版本不一致 → 退回往返契约分支 (改动系数作参考值)
        stale = json.loads(json.dumps(rec))
        stale["tool"]["yccstego"] = "0.0.1"
        stale_path = os.path.join(d, "stale.json")
        with open(stale_path, "w", encoding="utf-8") as f:
            json.dump(stale, f)
        rc, so, se = _stdout(["repro", stale_path, "-m", "重跑JPEG", "-c", cover,
                              "-o", os.path.join(d, "again.jpg")])
        assert rc == 0, se + so
        assert "round-trip-verified" in so and "改动系数" in so
        assert "退回往返契约" in so
        assert os.path.exists(os.path.join(d, "again.jpg"))
        print("[OK] 进程内 repro (JPEG 域): 同版本字节级 / 跨版本往返契约")
