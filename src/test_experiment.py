"""实验档案 (experiment.py) 测试: schema 完整性 + 两种域的重跑校验契约。

像素域字节级确定 → verify 应全绿; JPEG 域 0.2.0 起同为字节级 (同版本
前提), 跨版本自动退回往返一致。yccstego 缺失时 JPEG 域的用例 skip
(与 test_jpeg.py 同纪律)。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pytest

import experiment as EX
import image_io as IO
from ns5_core import embed_string

MSG = "repro contract 42"


def _cover_path():
    rng = np.random.default_rng(42)
    y = np.linspace(0, 220, 256)[None, :]
    x = np.linspace(0, 90, 256)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (256, 256)), 12, 255).astype(np.uint8)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    IO.save_image(img, path)
    return path


def test_record_schema_complete():
    cover = _cover_path()
    img = IO.load_image(cover)
    stego, rep, nbits = embed_string(img, MSG, method="nsF5", p=3, password="")
    rec = EX.new_record("pixel", "nsF5", 3, False)
    EX.fill_embed(rec, payload_bits=nbits, payload_chars=len(MSG), message=MSG,
                  cover_sha256=EX.sha256_array(img), cover_size=img.shape,
                  cover_path=cover, stego_sha256=EX.sha256_array(stego),
                  changed_cells=rep["cover_changed"], cell_unit="pixels",
                  changed_total=img.size)
    EX.merge_detector(rec, {"stego_probability": 0.42, "verdict": "临界"},
                      sensitivity="均衡", ml={"probability": None})
    # 档案里绝不允许出现消息明文
    assert MSG not in EX.dumps(rec)
    assert rec["schema"] == EX.SCHEMA
    assert rec["determinism"] == EX.DET_BYTE
    assert rec["payload"]["bits"] == nbits
    assert rec["detector"]["ml_available"] is False
    os.unlink(cover)


def test_verify_pixel_byte_deterministic():
    cover = _cover_path()
    img = IO.load_image(cover)
    stego, rep, nbits = embed_string(img, MSG, method="nsF5", p=3)
    rec = EX.new_record("pixel", "nsF5", 3, False)
    EX.fill_embed(rec, payload_bits=nbits, payload_chars=len(MSG), message=MSG,
                  cover_sha256=EX.sha256_array(img), cover_size=img.shape,
                  stego_sha256=EX.sha256_array(stego),
                  changed_cells=rep["cover_changed"], cell_unit="pixels",
                  changed_total=img.size)
    out = os.path.join(tempfile.mkdtemp(), "repro.png")
    r = EX.verify(rec, MSG, cover, password="", out_path=out)
    assert r["ok"] is True, r["checks"]
    assert all(c["ok"] for c in r["checks"])
    assert os.path.exists(out)
    # 换一条消息必须红: 契约真的在查, 不是走过场
    r2 = EX.verify(rec, "另一段话", cover)
    assert r2["ok"] is False
    # 换一张封面必须红在"封面哈希"这一项
    other = os.path.join(tempfile.mkdtemp(), "other.png")
    IO.save_image(np.flipud(img), other)
    r3 = EX.verify(rec, MSG, other)
    assert r3["ok"] is False
    assert any(c["name"].startswith("封面") and not c["ok"] for c in r3["checks"])
    os.unlink(cover)


def test_verify_jpeg_roundtrip_contract():
    if not __import__("jpegstego").available():
        pytest.skip("yccstego 未安装")
    import jpegstego
    from PIL import Image
    fd, cover = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    rgb = np.stack([IO.load_image(_cover_path())] * 3, axis=-1)
    Image.fromarray(rgb).save(cover)
    with open(cover, "rb") as f:
        cover_bytes = f.read()
    jpg, rep = jpegstego.embed_jpeg(cover_bytes, MSG, p=3)
    import jpegstego
    rec = EX.new_record("jpeg", "nsF5", 3, False, quality=85,
                        ycc_version=jpegstego.ycc_version())
    EX.fill_embed(rec, payload_bits=len(MSG) * 8 + 16, payload_chars=len(MSG),
                  message=MSG, cover_sha256=EX.sha256_bytes(cover_bytes),
                  stego_sha256=EX.sha256_bytes(jpg),
                  changed_cells=rep["carriers_changed"], cell_unit="coefficients",
                  capacity_bits=rep["capacity_bits"])
    t = jpegstego.ycc_version_tuple() or (0,)
    r = EX.verify(rec, MSG, cover)
    assert r["ok"] is True, r["checks"]
    if t >= (0, 2, 0):
        # 建档与重跑同 yccstego 版本 -> 字节级校验
        assert r["determinism"] == EX.DET_BYTE, r["determinism"]
        assert any(c["name"].startswith("含密字节一致") and c["ok"]
                   for c in r["checks"])
        # 跨版本退回往返契约: 改动数降级为参考值, 不判失败
        rec["tool"]["yccstego"] = "0.1.4"
        r2 = EX.verify(rec, MSG, cover)
        assert r2["ok"] is True, r2["checks"]
        assert r2["determinism"] == EX.DET_ROUNDTRIP
        assert any("允许浮动" in c["name"] for c in r2["checks"])
    else:
        # yccstego 0.1.4 (PyPI 尚未发 0.2.0 时的 CI): 只有往返契约
        assert r["determinism"] == EX.DET_ROUNDTRIP, r["determinism"]
    os.unlink(cover)
