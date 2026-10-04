# -*- coding: utf-8 -*-
"""冻结产物冒烟测试 (打包计划 M2, 见 docs/PACKAGING.md):

    make pkg          # 先构建 (build/exe/nsf5stego/)
    make pkg-test     # 本文件: 对冻结 exe 做全套冒烟

对 build/exe/nsf5stego/ 里的两个 exe 断言:
  1. 体积 <= 500MB (docs/PACKAGING.md 预算, 超了直接红 —— 防体积回归);
  2. CLI --version 带仓库版本号 (version.txt 冻结分支);
  3. embed -> extract 往返一致;
  4. analyze --json 的 盲分析概率 与 ML 概率 与源码运行逐位一致 (1e-9)
     —— 防止打包丢依赖导致 ML 静默降级 (曾实测踩过);
  5. GUI exe 启动后窗口标题带版本号, 截图含蓝白主题的深蓝横幅
     (像素级自检, 复用 GUI 冒烟的 DWM 截屏做法), 探针图留在
     build/pkg-test/gui_probe.png 供人工复核;
  6. JPEG 压缩域 (v1.9.0): --jpeg 嵌入 → --jpeg 提取往返 + 实验档案
     repro 重跑通过 —— yccstego 是 jpegstego 的函数内惰性导入, 静态分析
     看不见, 打包丢了它就会在这里红 (同第 4 条的教训)。

退出码 0/1; 控制台输出只用 GBK 可编码字符 (同 test_console_encoding 约定)。
"""
from __future__ import annotations

import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(PROJ, "build", "exe", "nsf5stego")
EXE_CLI = os.path.join(APP_DIR, "nsf5stego.exe")
EXE_GUI = os.path.join(APP_DIR, "nsf5stego-gui.exe")
OUT_DIR = os.path.join(PROJ, "build", "pkg-test")
SIZE_BUDGET_MB = 500
TOL = 1e-9

sys.path.insert(0, os.path.join(PROJ, "src"))
sys.path.insert(0, os.path.join(PROJ, "scripts"))

GUI_TITLE = ("nsF5 隐写工具 v{version} — "
             "伴随式矩阵编码 + 湿纸编码 + 盲隐写分析")
NAVY = (31, 78, 121)   # 与 src/gui.py C_NAVY 同源


def _version() -> str:
    from build_exe import read_version
    return read_version()


def _run(args, timeout=180, with_utf8_env=True):
    """跑冻结 exe; with_utf8_env=False 时完全不动 PYTHON* 变量 (用户视角)。

    2026-10-03 实测: 冻结 exe 在中文 Windows 上把中文按 **GBK** 写进管道,
    父进程传 PYTHONUTF8 / PYTHONIOENCODING 都无效 (C 层 UTF-8 模式在冻结引导
    阶段就定了)。所以 CLI 侧显式把 stdio 钉成 UTF-8 (cli._force_utf8_stdio),
    这里默认仍给 UTF-8 环境变量做双保险。
    """
    env = dict(os.environ)
    if with_utf8_env:
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          env=env)


def _raw(args, timeout=180):
    """按字节拿 stdio 的编码事实; 刻意**不加**任何 PYTHON* 环境变量 ——
    要塞就是塞"父进程说了不算"这条: 用户双击/管道运行时没有这些变量。"""
    return subprocess.run(args, capture_output=True, timeout=timeout,
                          env=dict(os.environ))


def _decode_host(raw: bytes) -> str:
    """按**宿主首选编码**解出"用户实际看到的东西"。

    这是证明"冻结 exe 真的写了 UTF-8"的唯一办法: 用 text=True 让 Python 自己
    解码时, 不管 exe 写的是 UTF-8 还是 GBK 都可能"解出来" (errors='replace'
    兜底), 中文断言会假绿。必须自己按宿主编码解: UTF-8 字节在 cp1252/GBK 下
    会露馅成 '?' 或乱码。"""
    import locale
    return raw.decode(locale.getpreferredencoding(False), errors="replace")


def _test_image(path, n=64):
    """平滑自然感封面 (与 run_e2e 同款配方), 供嵌入/分析。

    n=64 仅够像素域冒烟; JPEG 域 (yccstego 0.2.1 起载体语义正确) 下 64x64
    平滑渐变只有 ~57 个非零 AC 载体, 连 p=3 的头部 (~301) 都不够,
    --jpeg 用例必须用 n=256 (与 GUI 演示图同尺寸, 载体 ~5150)。"""
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(7)
    y = np.linspace(0, 220, n)[None, :]
    x = np.linspace(0, 90, n)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (n, n)), 12, 255)
    Image.fromarray(img.astype(np.uint8)).save(path)
    return path


def test_size_budget():
    total = sum(os.path.getsize(os.path.join(dp, f))
                for dp, _, fs in os.walk(APP_DIR) for f in fs) / 1048576
    assert total <= SIZE_BUDGET_MB, \
        f"冻结包体积 {total:.0f}MB 超预算 {SIZE_BUDGET_MB}MB —— 检查 spec excludes"
    print(f"[OK] 体积 {total:.0f}MB <= {SIZE_BUDGET_MB}MB")


def test_version():
    want = _version()
    r = _run([EXE_CLI, "--version"])
    assert r.returncode == 0 and want in (r.stdout or ""), \
        f"--version 应含 {want}, 实际 rc={r.returncode} {(r.stdout or r.stderr)[:80]!r}"
    print(f"[OK] --version: {(r.stdout or '').strip()}")


def test_roundtrip_and_analyze():
    import numpy as np
    from ns5_core import embed_string
    from ml_predict import get_predictor
    import steganalysis as SA
    import image_io as IO

    d = tempfile.mkdtemp(prefix="nsf5_frozen_")
    try:
        cover = _test_image(os.path.join(d, "cover.png"))
        msg = "frozen smoke 123"
        r = _run([EXE_CLI, "embed", cover, "-m", msg, "-p", "pw1",
                  "-o", os.path.join(d, "stego.png")])
        assert r.returncode == 0, f"冻结 embed 失败: {(r.stderr or r.stdout)[:200]}"
        stego_path = os.path.join(d, "stego.png")
        assert os.path.exists(stego_path), "冻结 embed 未产出含密图"

        r = _run([EXE_CLI, "extract", stego_path, "-p", "pw1"])
        assert r.returncode == 0 and msg in (r.stdout or ""), \
            f"冻结 extract 往返失败: {(r.stdout or r.stderr)[:200]}"
        print("[OK] 冻结 embed -> extract 往返一致")

        img = IO.load_image(stego_path)
        r = _run([EXE_CLI, "analyze", stego_path, "--json"], timeout=300)
        assert r.returncode == 0, f"冻结 analyze 失败: {(r.stderr or r.stdout)[:200]}"
        payload = json.loads(r.stdout)

        src = SA.analyze(img, sensitivity="均衡")
        assert abs(payload["stego_probability"] - src["stego_probability"]) <= TOL, \
            "冻结盲分析概率与源码不一致"
        src_ml = get_predictor(sensitivity="均衡").predict(img)
        frozen_ml = payload.get("ml") or {}
        assert frozen_ml.get("probability") is not None, \
            f"冻结环境 ML 静默不可用 (丢依赖的老毛病): {frozen_ml}"
        assert abs(frozen_ml["probability"] - src_ml["probability"]) <= TOL, \
            f"冻结 ML 概率与源码不一致: {frozen_ml['probability']} vs {src_ml['probability']}"
        print(f"[OK] 冻结 analyze 与源码逐位一致 "
              f"(prob={payload['stego_probability']:.4f}, "
              f"ml={frozen_ml['probability']:.4f})")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_jpeg_roundtrip_and_repro():
    """冻结环境的 JPEG 压缩域冒烟: --jpeg 往返 + 实验档案 repro。"""
    d = tempfile.mkdtemp(prefix="nsf5_frozen_jpeg_")
    try:
        cover = _test_image(os.path.join(d, "cover.png"), n=256)
        msg = "frozen jpeg 42"
        rec = os.path.join(d, "exp.json")
        r = _run([EXE_CLI, "embed", cover, "--jpeg", "-m", msg, "--json"])
        assert r.returncode == 0, f"冻结 --jpeg embed 失败: {(r.stderr or r.stdout)[:200]}"
        payload = json.loads(r.stdout)
        assert payload["algorithm"]["domain"] == "jpeg", "档案域应为 jpeg"
        assert msg not in r.stdout, "档案不得携带消息明文"
        stego = payload["stego"]["path"]
        assert os.path.exists(stego), "冻结 --jpeg embed 未产出 .jpg"
        with open(rec, "w", encoding="utf-8") as f:
            f.write(r.stdout)

        r = _run([EXE_CLI, "extract", stego, "--jpeg"])
        assert r.returncode == 0 and msg in (r.stdout or ""), \
            f"冻结 --jpeg extract 往返失败: {(r.stdout or r.stderr)[:200]}"
        print("[OK] 冻结 JPEG 域 embed -> extract 往返一致")

        r = _run([EXE_CLI, "repro", rec, "-m", msg])
        assert r.returncode == 0, ("冻结 repro 失败: "
                                   f"{(r.stderr or r.stdout)[:300]}")
        assert "重跑通过" in (r.stdout or ""), (
            "冻结 repro 未打印通过结论; repro 输出:\n"
            + (r.stdout or "")[:400] + "\nstderr: " + (r.stderr or "")[:300])
        print("[OK] 冻结实验档案 repro 通过 (往返契约)")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_frozen_stdout_is_really_utf8():
    """冻结 exe 的中文 stdout 必须是**字节级 UTF-8** (不能靠父进程喂环境变量)。

    为什么单列一条: v1.9.0 的 repro 断言在 tag 首跑失败的真实原因就是这个 ——
    冻结 exe 在中文 Windows 上按 GBK 写管道, 于是
    `"重跑通过" in stdout` 取决于断言侧怎么解码, 时绿时红。更严重的是用户把
    输出重定向/管道给别的程序 (本工具 --json 的契约就是 UTF-8) 时中文直接乱码。

    所以这里绕开 text=True 的自动解码, 直接看字节:
      * b"\\xe9\\x87\\x8d..." (UTF-8) 必须在;
      * 宿主首选编码 (cp1252 / GBK) 解出来的文本里 "重跑通过" 也必须在 ——
        这一条正是"用户看到的东西"是否可读的判据。
    """
    d = tempfile.mkdtemp(prefix="nsf5_frozen_utf8_")
    try:
        cover = _test_image(os.path.join(d, "cover.png"), n=256)
        msg = "冻结编码探针"
        rec = os.path.join(d, "exp.json")
        r = _run([EXE_CLI, "embed", cover, "--jpeg", "-m", msg, "--json"])
        assert r.returncode == 0, f"冻结 --jpeg embed 失败: {(r.stderr or r.stdout)[:200]}"
        with open(rec, "w", encoding="utf-8") as f:
            f.write(r.stdout)

        raw = _raw([EXE_CLI, "repro", rec, "-m", msg])
        assert raw.returncode == 0, f"冻结 repro 失败: {raw.stderr[:300]!r}"
        want = "重跑通过".encode("utf-8")
        assert want in raw.stdout, (
            "冻结 repro 的 stdout 不是 UTF-8 字节 (父进程 PYTHONUTF8 救不了它); "
            "stdout 尾部字节: " + repr(raw.stdout[-80:]))
        host_text = _decode_host(raw.stdout)
        assert "重跑通过" in host_text, (
            "宿主首选编码下读不出中文 (用户看到的会是乱码): "
            + repr(host_text[-120:]))
        print("[OK] 冻结 stdout 是字节级 UTF-8: " + repr(host_text.strip()[-40:]))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _find_window(u32, pid: int, title: str):
    """先按标题找窗口; 找不到再按进程 ID 兜底 (CI 上比标题匹配更稳)。"""
    hwnd = u32.FindWindowW(None, title)
    if hwnd:
        return hwnd
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _):
        p = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h):
            found.append(h)
        return True
    u32.EnumWindows(proc(cb), None)
    return found[0] if found else 0


def test_gui_launch_and_theme():
    from PIL import ImageGrab
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    u32 = ctypes.windll.user32
    want_title = GUI_TITLE.format(version=_version())
    p = subprocess.Popen([EXE_GUI])
    hwnd = 0
    try:
        for _ in range(60):                 # 最多 15s 等 Tk 起来
            time.sleep(0.25)
            hwnd = _find_window(u32, p.pid, want_title)
            if hwnd:
                break
        assert hwnd, f"15s 内没找到冻结 GUI 窗口 (标题 {want_title!r} / pid {p.pid})"

        class R(ctypes.Structure):
            _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long),
                        ("r", ctypes.c_long), ("b", ctypes.c_long)]
        rc = R()
        r = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rc), ctypes.sizeof(rc))
        assert r == 0 and rc.r > rc.l, "DWM 取窗口边界失败"
        u32.SetForegroundWindow(hwnd)
        os.makedirs(OUT_DIR, exist_ok=True)
        probe = os.path.join(OUT_DIR, "gui_probe.png")

        # 蓝白主题像素自检: 截图上部应有大片深蓝横幅 (C_NAVY 同源色)。
        # CI 上 Tk 首帧绘制可能滞后于窗口出现 —— 单次截图会偶发拿到未绘制
        # 的白窗 (v1.8.4 tag 首跑实测), 因此轮询重试, 任一帧达标即过。
        import numpy as np
        navy = 0
        shot = None
        for _attempt in range(10):
            time.sleep(1.0)
            u32.SetForegroundWindow(hwnd)
            shot = ImageGrab.grab((rc.l, rc.t, rc.r, rc.b))
            a = np.array(shot)
            top = a[: max(1, int(a.shape[0] * 0.45))]
            navy = int(((abs(top[:, :, 0].astype(int) - NAVY[0]) < 25)
                        & (abs(top[:, :, 1].astype(int) - NAVY[1]) < 25)
                        & (abs(top[:, :, 2].astype(int) - NAVY[2]) < 25)).sum())
            if navy > 5000:
                break
        shot.save(probe)
        assert navy > 5000, \
            (f"10 次截图中深蓝横幅像素最多 {navy}, 主题可能没生效或窗口未完成"
             f"首帧绘制; 探针图 {probe}")
        print(f"[OK] 冻结 GUI 启动 + 蓝白主题自检 (探针图 {os.path.relpath(probe, PROJ)})")
    finally:
        p.terminate()
        try:
            p.wait(timeout=10)
        except Exception:
            p.kill()


def main() -> int:
    for exe in (EXE_CLI, EXE_GUI):
        if not os.path.exists(exe):
            print(f"[error] 缺 {exe} —— 先跑 `make pkg` (scripts/build_exe.py)")
            return 1
    failures = 0
    for fn in (test_size_budget, test_version,
               test_roundtrip_and_analyze, test_jpeg_roundtrip_and_repro,
               test_frozen_stdout_is_really_utf8,
               test_gui_launch_and_theme):
        try:
            fn()
        except AssertionError as e:
            print(f"[FAIL] {fn.__name__}: {e}")
            failures += 1
        except Exception as e:
            print(f"[FAIL] {fn.__name__}: {type(e).__name__}: {e}")
            failures += 1
    if failures:
        print(f"\n冻结冒烟未通过: {failures} 项")
        return 1
    print("\n冻结冒烟全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
