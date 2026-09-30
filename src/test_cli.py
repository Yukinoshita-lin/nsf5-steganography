"""nsf5stego CLI 冒烟自测 (2026-09-29, 随 1.8.0 的 cli.py 加入)。

此前唯一的入口脚本 `nsf5stego = "gui:main"` 只会弹窗, 服务器/脚本场景没有
命令行可用 —— 1.8.0 起入口改为 `cli:main` (embed/extract/analyze/gui)。
本文件用**真实子进程**验证: --help / 无参数 / 容量超限 / 口令错误 / 文件
缺失都以非零码 + 可读中文报错退出, 成功路径往返一致 (交互式布局见
webapp/tests/, GUI 见 test_gui.py)。

子进程用 PYTHONIOENCODING=utf-8 固定 stdio 编码, 避免宿主控制台 (如 cp936)
影响断言; Windows 控制台本身的输出安全由 test_console_encoding.py 静态护栏
另管。真实链路的用例标了 slow (每个子进程约 2 秒), 快速反馈可
`-m "not slow"` 跳过。`python src/test_cli.py` 与 `pytest` 均可运行。
"""
import io
import json
import locale
import os
import subprocess
import sys
import tempfile

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402  (进程内单测 _stdin_text 用; 其余走子进程)

CLI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py")


def _run(*args, stdin=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, CLI, *args],
                          capture_output=True, text=True, encoding="utf-8",
                          input=stdin, env=env, timeout=180)


def _cover(path, size=64):
    """平滑自然感封面 (与 run_e2e 同款), 纯噪声图会把分析判成'本底随机'。"""
    rng = np.random.default_rng(7)
    y = np.linspace(0, 220, size)[None, :]
    x = np.linspace(0, 90, size)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (size, size)), 12, 255)
    from PIL import Image
    Image.fromarray(img.astype(np.uint8)).save(path)
    return path


# --------------------------------------------------------------------------- #
#  快路径: 帮助 / 版本 / 参数错误 / 读图错误
# --------------------------------------------------------------------------- #
def test_help_lists_subcommands():
    r = _run("--help")
    assert r.returncode == 0, r.stderr
    for cmd in ("embed", "extract", "analyze", "gui"):
        assert cmd in r.stdout, f"--help 应列出 {cmd}"
    print("[OK] --help 列出全部子命令")


def test_no_args_shows_usage_exit_2():
    r = _run()
    assert r.returncode == 2, "无子命令应以 argparse 的 2 退出"
    assert "usage" in (r.stdout + r.stderr).lower()
    print("[OK] 无子命令: usage + 退出码 2")


def test_version_flag():
    r = _run("--version")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip(), "--version 应打印版本"
    print("[OK] --version:", r.stdout.strip())


def test_missing_image_is_friendly():
    with tempfile.TemporaryDirectory() as d:
        r = _run("extract", os.path.join(d, "nope.png"))
    assert r.returncode == 1
    assert "无法读取图像" in r.stderr and "Traceback" not in r.stderr
    print("[OK] 图像不存在: 友好报错, 无栈回溯")


def test_analyze_clean_image_json():
    with tempfile.TemporaryDirectory() as d:
        img = _cover(os.path.join(d, "c.png"))
        r = _run("analyze", img, "--json")
    assert r.returncode == 0, r.stderr
    payload = json.loads(r.stdout)
    for key in ("stego_probability", "verdict", "sensitivity", "image_sha256"):
        assert key in payload, f"JSON 输出缺少 {key}"
    assert 0.0 <= payload["stego_probability"] <= 1.0
    print("[OK] analyze --json 可解析且键齐全")


class _FakeStdin:
    """按给定字节伪造 sys.stdin (只暴露 _stdin_text 用到的 buffer / isatty)。"""

    def __init__(self, data: bytes = b"", tty: bool = False):
        self.buffer = io.BytesIO(data)
        self._tty = tty

    def isatty(self):
        return self._tty


def _with_stdin(data: bytes, fn):
    old = cli.sys.stdin
    cli.sys.stdin = _FakeStdin(data)
    try:
        return fn()
    finally:
        cli.sys.stdin = old


def test_stdin_decodes_utf8_before_locale():
    # 核心修复: Windows 管道默认按 locale (如 cp936) 解码, UTF-8 的 msg.txt
    # 若交给 locale 会变成乱码并被原样嵌进图片。UTF-8 必须优先。
    got = _with_stdin("中文消息".encode("utf-8"), cli._stdin_text)
    assert got == "中文消息", f"UTF-8 stdin 应原样解码, 实际 {got!r}"
    print("[OK] stdin 文本: UTF-8 优先解码")


@pytest.mark.skipif(
    locale.getpreferredencoding(False).lower().replace("-", "") != "utf8",
    reason="仅 UTF-8 locale 上能确定 GBK 字节两侧都解不出; 其余 locale 行为依赖环境")
def test_stdin_undecodable_returns_none():
    got = _with_stdin("中文消息".encode("gbk"), cli._stdin_text)
    assert got is None, f"解不出的输入应返回 None 以便报错退出, 实际 {got!r}"
    print("[OK] stdin 文本: 两侧都解不出时返回 None (由调用方报错)")


# --------------------------------------------------------------------------- #
#  慢路径: 真实 嵌入 -> 解码 / 分析 链
# --------------------------------------------------------------------------- #
def test_analyze_batch_human_lines():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        img = cli.IO.load_image(cover)
        stego, _, _ = cli.embed_string(img, "batch demo", method="nsF5", p=3)
        stego_path = os.path.join(d, "s.png")
        cli.IO.save_image(stego, stego_path)
        r = _run("analyze", cover, stego_path)
    assert r.returncode == 0, r.stderr
    lines = [l for l in r.stdout.splitlines() if "隐写概率" in l]
    assert len(lines) == 2, f"批量应逐图一行, 实际输出:\n{r.stdout}"
    assert "c.png" in lines[0] and "s.png" in lines[1]
    print("[OK] analyze 批量: 逐图一行汇总")


def test_analyze_batch_json_is_array():
    with tempfile.TemporaryDirectory() as d:
        a = _cover(os.path.join(d, "a.png"))
        b = _cover(os.path.join(d, "b.png"))
        r = _run("analyze", a, b, "--json")
    assert r.returncode == 0, r.stderr
    arr = json.loads(r.stdout)
    assert isinstance(arr, list) and len(arr) == 2, "多图 --json 应输出数组"
    assert [os.path.basename(p["image"]) for p in arr] == ["a.png", "b.png"]
    assert all("stego_probability" in p for p in arr)
    print("[OK] analyze 批量 --json: 对象数组且带 image 键")


def test_analyze_batch_survives_missing_image():
    with tempfile.TemporaryDirectory() as d:
        a = _cover(os.path.join(d, "a.png"))
        missing = os.path.join(d, "gone.png")
        r = _run("analyze", a, missing, "--json")
    assert r.returncode == 1, "批量中存在坏图应以非零码退出"
    arr = json.loads(r.stdout)
    assert len(arr) == 2, "坏图不应拖垮整批, 好图结果仍要输出"
    assert "stego_probability" in arr[0] and "error" in arr[1]
    print("[OK] analyze 批量: 单张坏图记 error 条目, 整批非零退出")


def test_analyze_batch_glob_pattern():
    # Windows shell 不展开 *.png: CLI 必须自己 glob, 否则 README 示例是坏的
    with tempfile.TemporaryDirectory() as d:
        _cover(os.path.join(d, "a.png"))
        _cover(os.path.join(d, "b.png"))
        r = _run("analyze", os.path.join(d, "*.png"), "--json")
        assert r.returncode == 0, r.stderr
        arr = json.loads(r.stdout)
        assert isinstance(arr, list) and len(arr) == 2, \
            f"通配符应展开成 2 张图, 实际 {arr if not isinstance(arr, list) else len(arr)} 项"

        r = _run("analyze", os.path.join(d, "*.jpg"), "--json")
    assert r.returncode == 1 and json.loads(r.stdout)[0]["error"] == "无匹配文件"
    print("[OK] analyze 批量通配符: 展开 + 无匹配报'无匹配文件'")


# --------------------------------------------------------------------------- #
#  进程内直调 cli.main: 子进程不计入 coverage (曾因此掉到 65% 门槛之下),
#  行为断言以子进程用例为准, 这里负责覆盖率与不启动子进程的快速反馈。
# --------------------------------------------------------------------------- #
def test_inproc_embed_extract_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        out = os.path.join(d, "s.png")
        assert cli.main(["embed", cover, "-m", "inproc", "-p", "k", "-o", out]) == 0
        assert os.path.exists(out), "默认/指定输出应落盘"
        assert cli.main(["extract", out, "-p", "k"]) == 0
    print("[OK] 进程内 embed -> extract 往返")


def test_inproc_embed_stdin_and_error_paths():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        # stdin 传文本
        rc = _with_stdin(b"inproc stdin",
                         lambda: cli.main(["embed", cover, "-o",
                                           os.path.join(d, "s1.png")]))
        assert rc == 0
        # tty 且无 -m -> 2; 空文本 -> 2
        cli.sys.stdin = _FakeStdin(b"", tty=True)
        try:
            assert cli.main(["embed", cover]) == 2
        finally:
            cli.sys.stdin = sys.__stdin__
        rc = _with_stdin(b"", lambda: cli.main(["embed", cover]))
        assert rc == 2
        # 容量超限 -> 1; 图像缺失 -> 1
        tiny = _cover(os.path.join(d, "tiny.png"), size=32)
        assert cli.main(["embed", tiny, "-m", "x" * 400]) == 1
        assert cli.main(["embed", os.path.join(d, "nope.png"), "-m", "x"]) == 1
    print("[OK] 进程内 embed 错误路径 (tty/空文本/容量/缺图)")


def test_inproc_extract_failures():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        stego = os.path.join(d, "c_stego.png")
        assert cli.main(["embed", cover, "-m", "hello", "-p", "k", "-o", stego]) == 0
        assert cli.main(["extract", stego, "-p", "wrong"]) == 1
        assert cli.main(["extract", os.path.join(d, "nope.png")]) == 1
    print("[OK] 进程内 extract 失败路径 (口令错误/缺图)")


def test_inproc_analyze_paths():
    with tempfile.TemporaryDirectory() as d:
        a = _cover(os.path.join(d, "a.png"))
        b = _cover(os.path.join(d, "b.png"))
        assert cli.main(["analyze", a]) == 0                       # 人读单图
        assert cli.main(["analyze", a, "--json"]) == 0             # JSON 对象
        assert cli.main(["analyze", a, b, "--json"]) == 0          # JSON 数组
        r = cli.main(["analyze", a, os.path.join(d, "gone.png"), "--json"])
        assert r == 1, "批量含坏图应非零退出"
        r = cli.main(["analyze", os.path.join(d, "*.nomatch"), "--json"])
        assert r == 1, "通配符无匹配应非零退出"
    print("[OK] 进程内 analyze 全形态 (人读/JSON/批量/无匹配)")


def test_inproc_gui_import_error():
    # tkinter 缺失等导致 import gui 失败时, _cmd_gui 必须友好返回 1
    old = sys.modules.get("gui")
    sys.modules["gui"] = None          # 使 import gui 抛 ImportError
    try:
        assert cli.main(["gui"]) == 1
    finally:
        if old is None:
            sys.modules.pop("gui", None)
        else:
            sys.modules["gui"] = old
    print("[OK] 进程内 gui 导入失败分支")


def test_inproc_version_and_no_args():
    with pytest.raises(SystemExit) as ei:
        cli.main(["--version"])
    assert ei.value.code == 0
    with pytest.raises(SystemExit) as ei:
        cli.main([])
    assert ei.value.code == 2
    print("[OK] 进程内 --version / 无参数退出码")


@pytest.mark.slow
def test_embed_extract_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        msg = "cli round-trip 123"
        r = _run("embed", cover, "-m", msg, "-p", "pw1")
        assert r.returncode == 0, r.stderr
        stego = os.path.join(d, "c_stego.png")
        assert os.path.exists(stego), "默认输出应为 <原名>_stego.png"
        assert "嵌入" in r.stdout and "[OK]" in r.stdout

        r = _run("extract", stego, "-p", "pw1")
        assert r.returncode == 0, r.stderr
        assert msg in r.stdout
    print("[OK] embed -> extract 往返一致")


@pytest.mark.slow
def test_stdin_message_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        msg = "piped message"
        r = _run("embed", cover, stdin=msg)
        assert r.returncode == 0, r.stderr
        r = _run("extract", os.path.join(d, "c_stego.png"))
        assert r.returncode == 0, r.stderr
        assert msg in r.stdout
    print("[OK] stdin 传文本往返一致")


@pytest.mark.slow
def test_wrong_password_fails_with_hint():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"))
        assert _run("embed", cover, "-m", "secret", "-p", "right").returncode == 0
        r = _run("extract", os.path.join(d, "c_stego.png"), "-p", "wrong")
    assert r.returncode == 1, "口令错误必须以非零码退出"
    assert "[错误]" in r.stderr and "口令" in r.stderr
    print("[OK] 口令错误: 非零码 + 指向 参数/口令 的提示")


@pytest.mark.slow
def test_embed_capacity_error_is_friendly():
    with tempfile.TemporaryDirectory() as d:
        cover = _cover(os.path.join(d, "c.png"), size=32)
        r = _run("embed", cover, "-m", "x" * 400)
    assert r.returncode == 1
    assert "消息过长" in r.stderr and "Traceback" not in r.stderr
    print("[OK] 容量超限: 明确指出 消息过长 与出路")


if __name__ == "__main__":
    test_help_lists_subcommands()
    test_no_args_shows_usage_exit_2()
    test_version_flag()
    test_missing_image_is_friendly()
    test_analyze_clean_image_json()
    test_analyze_batch_human_lines()
    test_analyze_batch_json_is_array()
    test_analyze_batch_survives_missing_image()
    test_analyze_batch_glob_pattern()
    test_stdin_decodes_utf8_before_locale()
    test_stdin_undecodable_returns_none()
    test_inproc_embed_extract_roundtrip()
    test_inproc_embed_stdin_and_error_paths()
    test_inproc_extract_failures()
    test_inproc_analyze_paths()
    test_inproc_gui_import_error()
    test_inproc_version_and_no_args()
    test_embed_extract_roundtrip()
    test_stdin_message_roundtrip()
    test_wrong_password_fails_with_hint()
    test_embed_capacity_error_is_friendly()
    print("\n全部通过")
