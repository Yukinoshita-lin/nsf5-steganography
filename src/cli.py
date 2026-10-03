"""nsf5stego 命令行界面: embed / extract / analyze / repro / gui。

为什么需要 CLI (2026-09-29)
---------------------------
此前安装后的唯一入口 `nsf5stego` 直接弹 tkinter 窗口, 服务器 / 脚本 / 批量
场景只能自己 import ns5_core 拼代码。CLI 与 GUI 的参数语义 (方法 / p / 口令)
一一对应, 便于课堂演示与 CI 冒烟; GUI 继续走 `nsf5stego gui` 或
`python src/gui.py`。

JPEG 压缩域 (2026-10-03, v1.9.0)
--------------------------------
embed / extract / analyze 均支持 `--jpeg`: 走 jpegstego.py 桥接 (yccstego),
在量化 DCT 系数上嵌入 —— 教科书里 nsF5 的原始战场。嵌入输出是标准 .jpg,
解码必须同样 `--jpeg` 且 p / 口令一致; 域不一致是初学者第一常见错误。

控制台输出只使用 GBK 可编码字符 (中文 + ASCII), 原因见
test_console_encoding.py; 另在启动时把 stdout/stderr 的编码错误降级为替换,
否则 extract 打印任意 UTF-8 文本时可能在 cp936 控制台上崩掉。
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import locale
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import image_io as IO
from ns5_core import embed_string, extract_string, get_image_hash
import steganalysis as SA
import jpegstego
import experiment as EXP
from pathutil import app_version

SENS_CHOICES = {"严格": "严格 (低误报)", "均衡": "均衡", "宽松": "宽松 (高检出)"}


def _version() -> str:
    return app_version() or "unknown (源码运行, 未安装)"


def _err(msg: str) -> None:
    sys.stderr.write("[错误] " + msg + "\n")


def _short_sha(img) -> str:
    return hashlib.sha256(img.tobytes()).hexdigest()[:16]


def _load_image(path: str):
    """读图并把 OSError (文件不存在 / 格式无法识别) 转成友好提示。

    PIL 的 UnidentifiedImageError 继承自 OSError, 一并覆盖。"""
    try:
        return IO.load_image(path)
    except OSError as e:
        _err(f"无法读取图像 {path}: {e.strerror or e}")
        return None


def _read_cover_bytes(path: str):
    """JPEG 域吃的是原始文件字节 (量化系数在位流里, 解码再重编就没了)。"""
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        _err(f"无法读取图像 {path}: {e.strerror or e}")
        return None


# --------------------------------------------------------------------------- #
#  子命令
# --------------------------------------------------------------------------- #
def _stdin_text():
    """从 stdin 读文本, 编码按 UTF-8 优先、系统 locale 兜底。

    为什么: Windows 管道的默认解码是 locale (如 cp936), 但
    `cat msg.txt | nsf5stego embed cover.png` 里的 msg.txt 多半是 UTF-8 ——
    只信 locale 会把中文读成乱码并原样嵌进图片。两侧都解不出时返回 None,
    由调用方报错退出 (宁可拒绝, 不嵌乱码)。"""
    data = sys.stdin.buffer.read()
    for enc in ("utf-8", locale.getpreferredencoding(False)):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _cmd_embed(args) -> int:
    if args.message is None:
        if sys.stdin.isatty():
            _err("请用 -m/--message 提供文本, 或用管道传入: cat msg.txt | nsf5stego embed 封面.png")
            return 2
        args.message = _stdin_text()
        if not args.message:
            _err("待嵌入文本为空 (或 stdin 无法按 UTF-8 / 系统编码解码)")
            return 2

    if args.jpeg:
        return _cmd_embed_jpeg(args)

    img = _load_image(args.image)
    if img is None:
        return 1
    try:
        stego, report, nbits = embed_string(img, args.message,
                                            method=args.method, p=args.p,
                                            password=args.password)
    except ValueError as e:
        _err(str(e))
        return 1

    out = args.out or IO.default_out_path(
        args.image, "stego", os.path.dirname(os.path.abspath(args.image)))
    # 安装版默认输出在 %APPDATA%/nsf5stego/output, 首次嵌入时目录还不存在
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if os.path.exists(out):
        # 覆盖旧含密图是正常操作, 但旧图里藏的消息会随覆盖丢失, 应明说
        sys.stderr.write(f"[提示] 目标文件已存在, 已覆盖: {out}\n")
    IO.save_image(stego, out)
    record = EXP.new_record("pixel", args.method, args.p, bool(args.password))
    EXP.fill_embed(record, payload_bits=nbits, payload_chars=len(args.message),
                   message=args.message, cover_sha256=EXP.sha256_array(img),
                   cover_size=img.shape, cover_path=args.image,
                   stego_sha256=EXP.sha256_array(stego), stego_path=out,
                   stego_format="png", changed_cells=report["cover_changed"],
                   cell_unit="pixels", changed_total=img.size)
    if args.json:
        print(EXP.dumps(record))
        return 0
    print(f"封面: {args.image} {img.shape[1]}x{img.shape[0]}  SHA256: {_short_sha(img)}")
    print(f"嵌入 {nbits} 比特, 改动 {report['cover_changed']} 像素 [OK]")
    print(f"含密图: {out}")
    print(f"(口令: {'有' if args.password else '无'}, 方法: {args.method}, p: {args.p})")
    return 0


def _cmd_embed_jpeg(args) -> int:
    """JPEG 压缩域嵌入 (--jpeg): 在量化 DCT 系数上做 nsF5, 输出标准 .jpg。"""
    if not jpegstego.available():
        _err(jpegstego.unavailable_reason())
        return 1
    cover_bytes = _read_cover_bytes(args.image)
    if cover_bytes is None:
        return 1
    from yccstego.nsf5 import CapacityError
    try:
        jpg, rep = jpegstego.embed_jpeg(cover_bytes, args.message, p=args.p,
                                        password=args.password,
                                        quality=args.quality)
    except CapacityError as e:
        _err(f"容量不足: {e}")
        _err("可换更大的图 / 调高质量 --quality / 减小 p / 缩短消息")
        return 1

    base = os.path.splitext(os.path.basename(args.image))[0]
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.image)),
                                   f"{base}_stego.jpg")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if os.path.exists(out):
        sys.stderr.write(f"[提示] 目标文件已存在, 已覆盖: {out}\n")
    with open(out, "wb") as f:
        f.write(jpg)

    # 截断时真正写入的是 UTF-8 安全前缀, 档案里的 payload 必须按它记
    embedded_text = (args.message[:rep["embedded_chars"]]
                     if rep["truncated"] else args.message)
    nbits = 16 + 8 * len(embedded_text.encode("utf-8"))
    size = jpegstego.decode_preview(jpg).shape[:2]
    record = EXP.new_record("jpeg", "nsF5", args.p, bool(args.password),
                            quality=args.quality,
                            ycc_version=jpegstego.ycc_version())
    EXP.fill_embed(record, payload_bits=nbits,
                   payload_chars=rep["embedded_chars"], message=embedded_text,
                   cover_sha256=EXP.sha256_bytes(cover_bytes),
                   cover_size=size, cover_path=args.image,
                   stego_sha256=EXP.sha256_bytes(jpg), stego_path=out,
                   stego_format="jpg", changed_cells=rep["carriers_changed"],
                   cell_unit="coefficients", capacity_bits=rep["capacity_bits"],
                   truncated=rep["truncated"])
    if args.json:
        print(EXP.dumps(record))
        return 0
    print(f"封面: {args.image} {size[1]}x{size[0]}  SHA256: {hashlib.sha256(cover_bytes).hexdigest()[:16]}")
    print(f"嵌入 {nbits} 比特, 改动 {rep['carriers_changed']} 个 DCT 系数 "
          f"[OK] (JPEG 压缩域)")
    if rep["truncated"]:
        print(f"[提示] 消息超容量, 已按 UTF-8 安全截断到 {rep['embedded_chars']} 字符")
    print(f"含密图: {out}")
    print(f"(口令: {'有' if args.password else '无'}, p: {args.p}, 质量: {args.quality}, "
          f"容量: {rep['capacity_bits']} bit)")
    print("(解码需同样加 --jpeg, 且 p / 口令一致)")
    return 0


def _cmd_extract(args) -> int:
    if args.jpeg:
        return _cmd_extract_jpeg(args)
    img = _load_image(args.image)
    if img is None:
        return 1
    try:
        text = extract_string(img, method=args.method, p=args.p,
                              password=args.password)
    except ValueError as e:
        _err(f"解码失败: {e}")
        _err("请确认 方法 / p / 口令 与嵌入时一致 (口令或图像不匹配是最常见原因)")
        return 1
    # 口令/参数错误时置换序列错开, 解出的多半是替换字符 (U+FFFD) 或空串,
    # 与"嵌入了含 U+FFFD 的原文"在实务上不可区分, 统一按失败提示。
    if not text or "\ufffd" in text:
        _err("未提取到有效内容 (方法: {}, p: {})。".format(args.method, args.p))
        _err("请确认: 待解读图片 / 方法 / p / 口令 与嵌入时一致。")
        return 1
    print(f"解码成功 (方法: {args.method}, p: {args.p}):")
    print(text)
    return 0


def _cmd_extract_jpeg(args) -> int:
    """JPEG 压缩域提取 (--jpeg): 解析位流回到量化系数再解码。"""
    if not jpegstego.available():
        _err(jpegstego.unavailable_reason())
        return 1
    data = _read_cover_bytes(args.image)
    if data is None:
        return 1
    msg, _, tampered, head_match = jpegstego.extract_jpeg(
        data, p=args.p, password=args.password)
    if not msg:
        if head_match is False:
            _err("未提取到有效内容: 认证头读取失败 (色度哈希失配)。")
            _err("最常见原因: p / 口令 与嵌入时不一致, 或文件被改动 / 不是本工具生成。")
        else:
            _err("未提取到有效内容 (JPEG 域, p: {})。".format(args.p))
            _err("请确认: 待解读文件 / --jpeg / p / 口令 与嵌入时一致。")
        return 1
    print(f"解码成功 (JPEG 压缩域, p: {args.p}):")
    print(msg)
    return 0


def _ml_verdict(img, sens: str):
    """ML 判定; 模型/lightgbm 缺失不阻断盲分析, 返回说明性 dict。

    不可用时带上 load_error —— 打包 (PyInstaller) 环境里缺依赖/缺 DLL 的
    排障全靠这一行, JSON 消费者也能直接看到原因。"""
    try:
        from ml_predict import get_predictor
        pr = get_predictor(sensitivity=sens)
        r = pr.predict(img)
        if r is None or r.get("probability") is None:
            err = getattr(pr, "load_error", None) or r.get("verdict") or "模型未加载"
            return {"available": False, "error": str(err)}
        return r
    except Exception as e:
        return {"available": False, "error": str(e)}


def _cmd_analyze(args) -> int:
    if args.jpeg:
        return _cmd_analyze_jpeg(args)
    sens = SENS_CHOICES[args.sensitivity]
    entries = []   # 分析结果与 error 条目的最终序列
    failed = 0
    # Windows 的 shell 不展开通配符, README 示例 `analyze *.png` 要跨平台成立
    # 就得 CLI 自己补: 已存在的路径原样收 (含字面 [ ] 的文件名), 含通配符且
    # 匹配不到的记为 error 条目而不是误报"无法读取图像"。
    paths = []
    for raw in args.images:
        if os.path.exists(raw) or not glob.has_magic(raw):
            paths.append(raw)
            continue
        hits = sorted(glob.glob(raw))
        paths.extend(hits)
        if not hits:
            entries.append({"image": raw, "error": "无匹配文件"})
            failed += 1
    for path in paths:
        img = _load_image(path)
        if img is None:
            # 批量时一张坏图不拖垮整批: 记为 error 条目继续, 最后统一非零退出
            entries.append({"image": path, "error": "无法读取图像"})
            failed += 1
            continue
        r = SA.analyze(img, sensitivity=sens)
        payload = dict(r)
        payload["image"] = path
        payload["image_sha256"] = get_image_hash(img)
        payload["ml"] = _ml_verdict(img, sens)
        entries.append(payload)

    # "单图"按展开后的条目数判定: 一个 *.png 匹配两张图也算批量;
    # error 条目一律走数组/单行形态, 脚本端不用为错误结果再写一个分支
    single = len(entries) == 1 and "error" not in entries[0]
    if args.json:
        data = entries[0] if single else entries
        print(json.dumps(data, ensure_ascii=False, indent=2, default=float))
    elif single:
        _print_analyze_detail(entries[0])
    else:
        for p in entries:
            _print_analyze_line(p)
    return 1 if failed else 0


def _print_analyze_detail(p) -> None:
    print(f"图像: {p['image']}  SHA256: {p['image_sha256'][:16]}")
    print(f"判定灵敏度: {p['sensitivity']}")
    print(f"卡方: stat={p['chi2_stat']:.2f}  p={p['chi2_pvalue']}")
    print(f"RS: Gn={p['RS_Gn']:.3f}  Gr={p['RS_Gr']:.3f}")
    print(f"估计嵌入率: {p['est_rate'] * 100:.1f}%")
    print(f"隐写概率: {p['stego_probability'] * 100:.1f}%  ({p['verdict']})")
    ml = p.get("ml")
    if ml is None or ml.get("probability") is None:
        reason = ((ml.get("error") or ml.get("load_error") or "模型未加载")
                  if ml else "模型未加载")
        print(f"ML 判定: 不可用 ({reason})")
    else:
        print(f"ML 判定含密概率: {ml['probability'] * 100:.1f}%  "
              f"(阈值 {ml['threshold']:.3f}, {ml['verdict']})")


def _print_analyze_line(p) -> None:
    """批量模式的一行式汇总: 扫一眼就能比较多张图。"""
    if "error" in p:
        print(f"{p['image']}  [失败] {p['error']}")
        return
    line = (f"{p['image']}  隐写概率 {p['stego_probability'] * 100:.1f}%"
            f"  ({p['verdict']})")
    ml = p.get("ml")
    if ml is not None and ml.get("probability") is not None:
        line += f"  ML {ml['probability'] * 100:.1f}% ({ml['verdict']})"
    print(line)


def _cmd_analyze_jpeg(args) -> int:
    """JPEG 压缩域盲分析 (--jpeg): 主信号是 |c|=1 系数占比 (F5 减幅指纹)。

    ML 判定在此不可用 —— 部署模型吃的是像素域特征, DCT 域指纹属于
    yccstego 的启发式分析, 输出里如实说明而不是留空。"""
    if not jpegstego.available():
        _err(jpegstego.unavailable_reason())
        return 1
    sens = SENS_CHOICES[args.sensitivity]
    entries, failed = [], 0
    paths = []
    for raw in args.images:
        if os.path.exists(raw) or not glob.has_magic(raw):
            paths.append(raw)
            continue
        hits = sorted(glob.glob(raw))
        paths.extend(hits)
        if not hits:
            entries.append({"image": raw, "error": "无匹配文件"})
            failed += 1
    for path in paths:
        data = _read_cover_bytes(path)
        if data is None:
            entries.append({"image": path, "error": "无法读取图像"})
            failed += 1
            continue
        r = jpegstego.analyze_jpeg(data, sensitivity=sens)
        if not r.get("ok"):
            r["image"], r["error"] = path, "无可用 AC 系数 (图像过小或全同像素)"
            entries.append(r)
            failed += 1
            continue
        r["image"] = path
        r["image_sha256"] = hashlib.sha256(data).hexdigest()[:16]
        r["sensitivity"] = sens
        entries.append(r)
    single = len(entries) == 1 and "error" not in entries[0]
    if args.json:
        data = entries[0] if single else entries
        print(json.dumps(data, ensure_ascii=False, indent=2, default=float))
    elif single:
        _print_analyze_jpeg(entries[0])
    else:
        for p in entries:
            if "error" in p:
                print(f"{p['image']}  [失败] {p['error']}")
            else:
                print(f"{p['image']}  DCT隐写概率 {p['stego_probability_dct'] * 100:.1f}%"
                      f"  ({p['verdict']})")
    return 1 if failed else 0


def _print_analyze_jpeg(p) -> None:
    print(f"图像: {p['image']}  SHA256: {p['image_sha256']} (文件字节)")
    print(f"判定灵敏度: {p['sensitivity']}  (JPEG 压缩域, yccstego)")
    print(f"AC 载体系数: {p['n_ac']}  |c|=1 占比: {p['unit_frac'] * 100:.1f}%"
          f"  (基线 {p['unit_baseline'] * 100:.0f}%)")
    print(f"LSB 奇占比: {p['parity_odd'] * 100:.1f}%  DCT 卡方 p: {p['dct_chi2_pvalue']:.4f}")
    print(f"隐写概率: {p['stego_probability_dct'] * 100:.1f}%  ({p['verdict']})")
    if "pix_probability" in p:
        print(f"像素域参照: {p['pix_probability'] * 100:.1f}%  ({p['pix_verdict']})")
    print("(ML 判定不可用: 部署模型吃像素域特征, 与 DCT 域指纹不同轴)")


def _cmd_repro(args) -> int:
    """按实验档案重跑嵌入并逐项校验 (可复现性的一键入口)。"""
    try:
        with open(args.record, "r", encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        _err(f"无法读取实验档案 {args.record}: {e}")
        return 1
    if record.get("schema") != EXP.SCHEMA:
        _err(f"不是本工具的实验档案 (schema: {record.get('schema')}, "
             f"期望 {EXP.SCHEMA})")
        return 1
    message = args.message
    if message is None:
        if sys.stdin.isatty():
            _err("档案不含消息明文 (密钥不落盘), 请用 -m 提供原文或管道传入")
            return 2
        message = _stdin_text()
        if not message:
            _err("待重跑的原文为空")
            return 2
    cover = args.cover or record.get("cover", {}).get("path")
    if not cover:
        _err("档案里没有封面路径, 请用 -c/--cover 指定同一份封面文件")
        return 1
    if not os.path.exists(cover):
        _err(f"封面文件不存在: {cover} (档案记录的路径可能已移动, 用 -c 指定)")
        return 1
    alg = record["algorithm"]
    print(f"档案: {args.record}  ({record['tool']['version']}, "
          f"{alg['domain']}/{alg['method']} p={alg['hamming_p']})")
    print(f"重跑封面: {cover}")
    r = EXP.verify(record, message, cover, password=args.password,
                   out_path=args.out)
    for c in r["checks"]:
        mark = "[OK]  " if c["ok"] else "[FAIL]"
        extra = "" if c["name"].startswith("改动系数") else f": {c['actual']}"
        print(f"  {mark}{c['name']}{extra}")
    if not r["ok"]:
        _err("重跑未通过: 请核对封面文件 / 消息原文 / 口令是否与建档时完全一致")
        return 1
    if args.out:
        print(f"重跑产物: {args.out}")
    if r["determinism"] == EXP.DET_ROUNDTRIP:
        print("(JPEG 域退回往返契约: 档案与当前 yccstego 版本不同, "
              "只要求提取一致, 改动数作参考值)")
    elif alg["domain"] == "jpeg":
        print("(JPEG 域契约: 同一 yccstego 版本下逐字节复现)")
    print(f"重跑通过 (契约: {r['determinism']})")
    return 0


def _cmd_gui(args) -> int:
    try:
        import gui
    except ImportError as e:
        _err(f"无法导入图形界面 (多半缺 tkinter): {e}")
        _err("Ubuntu/Debian: sudo apt install python3-tk; "
             "或改用命令行: nsf5stego embed / extract / analyze")
        return 1
    try:
        gui.main()
    except Exception as e:
        _err(f"图形界面启动失败 (无显示环境?): {e}")
        _err("服务器上请改用命令行: nsf5stego embed / extract / analyze")
        return 1
    return 0


# --------------------------------------------------------------------------- #
#  参数表
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="nsf5stego",
        description="nsF5 隐写工具命令行: 嵌入 / 解码 / 盲隐写分析 / 实验重跑 / 图形界面。"
                    "解码与嵌入的 域 / 方法 / p / 口令 必须一致。",
        epilog="示例:\n"
               "  nsf5stego embed cover.png -m \"秘密\" -p 口令 -o stego.png\n"
               "  cat msg.txt | nsf5stego embed cover.png\n"
               "  nsf5stego embed cover.png --jpeg -m \"秘密\" --quality 85\n"
               "  nsf5stego extract stego.png -p 口令\n"
               "  nsf5stego extract stego.jpg --jpeg -p 口令\n"
               "  nsf5stego analyze stego.png --sensitivity 宽松 --json\n"
               "  nsf5stego analyze stego.jpg --jpeg\n"
               "  nsf5stego embed cover.png -m 秘密 --json > experiment.json\n"
               "  nsf5stego repro experiment.json -m 秘密\n"
               "  nsf5stego gui",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    ap.add_argument("--version", action="version", version="nsf5stego " + _version())

    def _common(sp):
        sp.add_argument("--method", choices=["nsF5", "matrix"], default="nsF5",
                        help="嵌入算法: nsF5 (默认) 或 matrix (纯伴随式矩阵编码); 仅像素域")
        sp.add_argument("--hamming-p", dest="p", type=int, choices=[1, 2, 3, 4, 5, 6],
                        default=3, help="汉明伴随式参数 p (每块比特数, 块长 2^p-1), 默认 3")
        sp.add_argument("-p", "--password", default="",
                        help="口令 (可选); 解码时必须与嵌入一致")

    sub = ap.add_subparsers(dest="command", metavar="命令")
    sub.required = True

    sp = sub.add_parser("embed", help="把文本嵌入图像 (像素域或 --jpeg 压缩域)",
                        description="把文本嵌入 8bit 图像 (彩图只改 R 通道); "
                                    "加 --jpeg 则在量化 DCT 系数上嵌入并输出 .jpg。")
    sp.add_argument("image", help="封面图路径")
    sp.add_argument("-m", "--message", help="待嵌入文本; 缺省时从 stdin 读入")
    sp.add_argument("-o", "--out", help="输出含密图路径 (默认 <原图名>_stego.png 或 .jpg)")
    sp.add_argument("--jpeg", action="store_true",
                    help="JPEG 压缩域嵌入 (yccstego): 改量化 DCT 系数, 输出 .jpg; "
                         "解码端同样需要 --jpeg")
    sp.add_argument("--quality", type=int, default=85,
                    help="JPEG 质量 1..100 (仅 --jpeg; 越高容量越大, 默认 85)")
    sp.add_argument("--json", action="store_true",
                    help="把实验档案 (参数/哈希/改动统计, 不含消息明文) 以 JSON 打到 stdout")
    _common(sp)
    sp.set_defaults(func=_cmd_embed)

    sp = sub.add_parser("extract", help="从含密图解码文本",
                        description="从含密图还原文本 (须与嵌入使用相同 域/方法/p/口令)。")
    sp.add_argument("image", help="含密图路径")
    sp.add_argument("--jpeg", action="store_true",
                    help="按 JPEG 压缩域解析 (嵌入用了 --jpeg 时必须加)")
    _common(sp)
    sp.set_defaults(func=_cmd_extract)

    sp = sub.add_parser("analyze", help="盲隐写分析 (卡方 + RS [+ ML]; --jpeg 走 DCT 指纹)",
                        description="对图像做盲隐写分析并给出判定与概率。"
                                    "可传多张图批量汇总; 单图与多图的 --json "
                                    "输出分别为对象/数组。--jpeg 用 |c|=1 系数指纹分析。")
    sp.add_argument("images", nargs="+",
                    help="待检图路径 (可多张; 支持 *.png 等通配符, Windows 的 "
                         "shell 不展开, 由本命令补齐)")
    sp.add_argument("--jpeg", action="store_true",
                    help="JPEG 压缩域分析 (yccstego): |c|=1 指纹为主信号; ML 判定不可用")
    sp.add_argument("-s", "--sensitivity", choices=list(SENS_CHOICES), default="均衡",
                    help="判定灵敏度: 严格=少误报干净图, 宽松=更易检出弱嵌入 (默认 均衡)")
    sp.add_argument("--json", action="store_true", help="输出机器可读 JSON (供脚本使用)")
    sp.set_defaults(func=_cmd_analyze)

    sp = sub.add_parser("repro", help="按实验档案重跑嵌入并逐项校验 (可复现性)",
                        description="读入 embed --json / GUI 导出的实验档案, 用同一封面与"
                                    "参数重新嵌入: 像素域要求逐字节复现, JPEG 域要求往返一致。"
                                    "档案不含消息明文, 原文需重新提供。")
    sp.add_argument("record", help="实验档案 JSON 路径")
    sp.add_argument("-m", "--message", help="建档时的原文; 缺省时从 stdin 读入")
    sp.add_argument("-c", "--cover", help="封面文件路径 (缺省用档案里记录的 path)")
    sp.add_argument("-p", "--password", default="",
                    help="建档时的口令 (档案只记有无, 不记内容)")
    sp.add_argument("-o", "--out", help="重跑产物保存路径 (缺省只校验不落盘)")
    sp.set_defaults(func=_cmd_repro)

    sp = sub.add_parser("gui", help="启动图形界面 (tkinter)")
    sp.set_defaults(func=_cmd_gui)
    return ap


def main(argv=None) -> int:
    # 打印任意 UTF-8 解码结果时, cp936 等窄编码控制台不应崩溃
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except Exception:
                pass
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
