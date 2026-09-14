"""Windows 控制台编码护栏: print/stderr 行不得出现 GBK 编码不了的字符。

背景 (2026-09-14 审计)
----------------------
`python src/run_e2e.py` 是 README 快速开始里的命令, 但它在中文 Windows 的默认
控制台 (cp936/GBK) 上直接崩:

    UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'

罪魁是进度行里的 `✓` (U+2713)。Python 到 3.15 才默认开启 UTF-8 mode, 在那之前
stdout 用系统 locale 编码, 而 GBK 里没有 ✓ ✗ → ≈ 这类符号 (中文本身没问题,
GBK 能编)。同一个坑也埋在 `experiments/gen_figs.py` 与
`yccstego/tools/plot_results.py` 里。

这条测试静态扫描仓库里的 .py, 把 print / sys.stderr 行上 GBK 编码不了的字符
找出来 —— 在提交前拦住, 而不是等用户在 Windows 上踩到。
"""
import io
import os

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".idea",
             "_build", "videos", "data", "models", "dist", "build", ".venv"}
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLE_FUNCS = ("print(", "sys.stderr", "sys.stdout")


def _scannable(path: str) -> bool:
    return path.endswith(".py")


def find_violations(root: str = PROJ) -> list:
    """返回 [(relpath, lineno, [chars])], 只统计控制台输出行。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            if not _scannable(p):
                continue
            try:
                txt = io.open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(txt.splitlines(), 1):
                if not any(f in line for f in CONSOLE_FUNCS):
                    continue
                bad = []
                for ch in line:
                    try:
                        ch.encode("cp936")
                    except UnicodeEncodeError:
                        bad.append(ch)
                if bad:
                    out.append((os.path.relpath(p, root).replace("\\", "/"), i,
                                sorted(set(bad))))
    return out


def test_console_output_is_gbk_safe():
    violations = find_violations()
    assert not violations, (
        "以下 print/stderr 行含 GBK 编码不了的字符, 会在中文 Windows 控制台上抛 "
        "UnicodeEncodeError (请改成 ASCII, 例如 ✓ -> [OK], → -> ->):\n" +
        "\n".join(f"  {p}:{i}  {[ascii(c) for c in chars]}"
                  for p, i, chars in violations))
    print("[OK] 控制台输出 GBK 安全 (无 print/stderr 行含非 GBK 字符)")


if __name__ == "__main__":
    test_console_output_is_gbk_safe()
    print("\n全部通过")
