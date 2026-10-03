"""实验记录 (reproducibility) —— 单次实验的结构化档案 + 一键重跑校验。

为什么 (2026-10-03)
-------------------
GUI/CLI 此前只有"结果"没有"档案": 课堂演示完想复现, 只能靠手抄参数。
本模块把一次实验的关键字段收进一份 JSON 档案, 并配套
`nsf5stego repro <record.json>` 重跑校验。两个设计决定:

1. **消息明文不落盘**: 档案只记 message_sha256 (口令同理只记有无) ——
   档案会被分享/提交, 密钥不能跟着走; 重跑时消息由使用者重新提供。
2. **确定性契约**: 像素域与 JPEG 压缩域 (yccstego 0.2.0 起) 的湿纸求解
   种子都由输入派生, 相同输入逐字节复现。档案记录建档时的 yccstego 版本:
   重跑时版本一致 → 字节级校验 (提取 + 改动数 + 含密哈希); 版本不同
   (或档案来自 0.1.4 时代) → 自动退回"提取一致", 改动数作为参考值如实报告。

档案 schema (nsf5stego.experiment/1) 示例::

    {
      "schema": "nsf5stego.experiment/1",
      "created_utc": "2026-10-03T12:00:00+00:00",
      "tool": {"name": "nsf5stego", "version": "1.9.0",
            "yccstego": "0.2.0"},
      "algorithm": {"domain": "pixel", "method": "nsF5", "hamming_p": 3,
                    "password_used": false},
      "payload": {"bits": 208, "chars": 26,
                  "message_sha256": "<64hex>"},
      "cover": {"artifact": "pixels", "sha256": "<64hex>", "size": [256, 256],
                "path": null},
      "stego": {"sha256": "<64hex>", "path": "...", "format": "png"},
      "result": {"changed_cells": 183, "cell_unit": "pixels",
                 "changed_ratio": 0.0028, "capacity_bits": null,
                 "truncated": null},
      "determinism": "byte-deterministic",
      "detector": null
    }
"""
from __future__ import annotations

import datetime
import hashlib
import json

from pathutil import app_version

SCHEMA = "nsf5stego.experiment/1"
# determinism 字段的取值:
DET_BYTE = "byte-deterministic"       # 同输入 → 同字节 (pixel 恒定; jpeg 同版本)
DET_BYTE_SAMEVER = "byte-deterministic (same yccstego version)"
                                      # jpeg 档案的记录值: 重跑时须 yccstego
                                      # 版本一致才承诺字节级; 否则退回往返
DET_ROUNDTRIP = "round-trip-verified"  # jpeg 跨版本: 同输入 → 提取一致


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_array(img) -> str:
    """像素域的"封面指纹": 数组字节逐位哈希 (跨平台确定, 与文件编码无关)。"""
    import numpy as np
    return sha256_bytes(np.ascontiguousarray(img).tobytes())


def new_record(domain: str, method: str, p: int, password_used: bool,
               quality=None, ycc_version: str = None) -> dict:
    """按 schema 建档案骨架。domain: "pixel" | "jpeg"。

    ycc_version: JPEG 域建档时传入当前 yccstego 版本 (jpegstego.ycc_version()),
    重跑据此决定字节级校验还是退回往返一致。"""
    return {
        "schema": SCHEMA,
        "created_utc": datetime.datetime.now(datetime.timezone.utc)
                                 .isoformat(timespec="seconds"),
        "tool": {"name": "nsf5stego", "version": app_version() or "source",
                 **({"yccstego": ycc_version} if ycc_version else {})},
        "algorithm": {"domain": domain, "method": method, "hamming_p": int(p),
                      "password_used": bool(password_used),
                      **({"jpeg_quality": int(quality)} if domain == "jpeg" else {})},
        "payload": None,
        "cover": None,
        "stego": None,
        "result": None,
        # 像素域恒字节级; JPEG 域 0.2.0 起同为字节级, 但以"重跑端 yccstego
        # 版本与建档一致"为前提 —— verify() 据此选择校验强度。
        "determinism": DET_BYTE if domain == "pixel" else DET_BYTE_SAMEVER,
        "detector": None,
    }


def fill_embed(record: dict, *, payload_bits: int, payload_chars: int,
               message: str, cover_sha256: str, cover_size=None,
               cover_path=None, stego_sha256: str = None, stego_path=None,
               stego_format: str = None, changed_cells: int = 0,
               cell_unit: str = "pixels", changed_total: int = None,
               capacity_bits=None, truncated=None) -> dict:
    """嵌入完成后补全档案。changed_total: 载体单元总数 (算占比用)。"""
    record["payload"] = {
        "bits": int(payload_bits),
        "chars": int(payload_chars),
        # 明文不落盘: 档案会被分享/提交, 只留指纹供"是不是同一段话"对照
        "message_sha256": sha256_bytes(message.encode("utf-8")),
    }
    record["cover"] = {"sha256": cover_sha256, "path": cover_path,
                       **({"size": list(cover_size)} if cover_size else {})}
    record["stego"] = {"sha256": stego_sha256, "path": stego_path,
                       "format": stego_format}
    ratio = (changed_cells / changed_total) if changed_total else None
    record["result"] = {"changed_cells": int(changed_cells),
                        "cell_unit": cell_unit,
                        **({"changed_ratio": round(ratio, 6)} if ratio is not None else {}),
                        "capacity_bits": capacity_bits,
                        "truncated": truncated}
    return record


def merge_detector(record: dict, det: dict, sensitivity: str = None,
                   ml: dict = None) -> dict:
    """把一次盲分析的结果并入档案 (detector 字段; 没分析过则为 null)。"""
    if not det:
        return record
    block = {k: det[k] for k in
             ("chi2_stat", "chi2_pvalue", "RS_Gn", "RS_Gr", "est_rate",
              "stego_probability", "verdict") if k in det}
    if sensitivity:
        block["sensitivity"] = sensitivity
    if ml:
        if ml.get("probability") is not None:
            block["ml_probability"] = ml["probability"]
            block["ml_verdict"] = ml.get("verdict")
        else:
            block["ml_available"] = False
    record["detector"] = block
    return record


def dumps(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2, default=str)


# --------------------------------------------------------------------------- #
#  重跑校验
# --------------------------------------------------------------------------- #
def verify(record: dict, message: str, cover_path: str, password: str = "",
           out_path: str = None) -> dict:
    """按档案重跑一次嵌入并逐项校验。返回
    {"ok": bool, "checks": [{"name", "expected", "actual", "ok"}], "stego_path"}。

    - cover 契约: 重跑用的封面必须与档案是同一份 (像素域比像素数组哈希,
      JPEG 域比文件字节哈希) —— 否则参数再对也解不出, 先在这里就报清楚;
    - 确定性契约: pixel 比改动数 + 含密哈希; jpeg 只要求提取一致。
    """
    alg = record["algorithm"]
    domain, method, p = alg["domain"], alg["method"], int(alg["hamming_p"])
    checks = []

    def check(name, expected, actual, ok):
        checks.append({"name": name, "expected": expected,
                       "actual": actual, "ok": bool(ok)})

    if domain == "pixel":
        import image_io as IO
        from ns5_core import embed_string, extract_string
        img = IO.load_image(cover_path)
        check("封面像素哈希一致", record["cover"]["sha256"],
              sha256_array(img), sha256_array(img) == record["cover"]["sha256"])
        stego, rep, nbits = embed_string(img, message, method=method, p=p,
                                         password=password)
        back = extract_string(stego, method=method, p=p, password=password)
        check("提取一致", record["payload"]["message_sha256"],
              sha256_bytes((back or "").encode("utf-8")),
              sha256_bytes((back or "").encode("utf-8"))
              == record["payload"]["message_sha256"])
        exp_changed = record["result"]["changed_cells"]
        changed = int((stego != img).sum())
        check("改动数一致 (字节级确定)", exp_changed, changed, changed == exp_changed)
        stego_sha = sha256_array(stego)
        check("含密图哈希一致 (字节级确定)", record["stego"]["sha256"],
              stego_sha, stego_sha == record["stego"]["sha256"])
        if out_path:
            IO.save_image(stego, out_path)
    else:
        import jpegstego
        with open(cover_path, "rb") as f:
            cover_bytes = f.read()
        check("封面文件哈希一致", record["cover"]["sha256"],
              sha256_bytes(cover_bytes),
              sha256_bytes(cover_bytes) == record["cover"]["sha256"])
        quality = alg.get("jpeg_quality", 85)
        jpg, rep = jpegstego.embed_jpeg(cover_bytes, message, p=p,
                                        password=password, quality=quality)
        msg, _, tampered, _ = jpegstego.extract_jpeg(jpg, p=p, password=password)
        back_sha = sha256_bytes((msg or "").encode("utf-8"))
        check("提取一致", record["payload"]["message_sha256"],
              back_sha, back_sha == record["payload"]["message_sha256"])
        exp_changed = record["result"]["changed_cells"]
        # 校验强度按 yccstego 版本分档: 建档与重跑同版本 (>=0.2.0) → 字节级;
        # 版本不同 (或档案来自 0.1.4 时代) → 退回往返一致, 改动数作参考值
        rec_ycc = (record.get("tool") or {}).get("yccstego")
        cur_ycc = jpegstego.ycc_version()
        cur_tuple = jpegstego.ycc_version_tuple() or (0,)
        locked = bool(rec_ycc and cur_ycc and rec_ycc == cur_ycc
                      and cur_tuple >= (0, 2, 0))
        if locked:
            changed = rep["carriers_changed"]
            check("改动数一致 (字节级确定)", exp_changed, changed,
                  changed == exp_changed)
            stego_sha = sha256_bytes(jpg)
            check("含密字节一致 (同版本确定)", record["stego"]["sha256"],
                  stego_sha, stego_sha == record["stego"]["sha256"])
            det = DET_BYTE
        else:
            check("改动系数 (参考值: 档案 yccstego 版本 {} 与当前 {} 不同, "
                  "允许浮动)".format(rec_ycc, cur_ycc),
                  f"{exp_changed} (±)", rep["carriers_changed"], True)
            det = DET_ROUNDTRIP
        if out_path:
            with open(out_path, "wb") as f:
                f.write(jpg)
    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "checks": checks,
            "determinism": DET_BYTE if domain == "pixel" else det}
