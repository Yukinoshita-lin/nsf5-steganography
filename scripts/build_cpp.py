"""
scripts/build_cpp.py —— 编译 cpp/ 下的 C++ 加速库 (跨平台)。

产物不入库 (见 .gitignore): 二进制随平台而异, 提交进仓库既无用又会让仓库膨胀,
而且 Windows-only 的 .dll 会让 Linux/macOS 用户以为"没有加速可用"。这里按平台
现场编译, 编译失败了调用方也能靠纯 Python 回退继续工作。

后缀/编译器选择:
    Windows : g++ (MinGW)        -O2 -shared -static  -> nsf5embed.dll
    macOS   : g++/clang++        -O2 -shared -fPIC    -> nsf5embed.dylib
    Linux   : g++/clang++        -O2 -shared -fPIC    -> nsf5embed.so

用法:
    python scripts/build_cpp.py            # 编译两个库
    python scripts/build_cpp.py --check    # 只报告编译器与产物状态
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPP_DIR = os.path.join(PROJ, "cpp")
sys.path.insert(0, os.path.join(PROJ, "src"))

TARGETS = ("fsfeatures", "nsf5embed")


def compiler() -> str:
    for c in ("g++", "clang++", "c++"):
        p = shutil.which(c)
        if p:
            return p
    raise RuntimeError(
        "找不到 C++ 编译器 (g++ / clang++ / c++)。"
        "Windows 上装 MinGW-w64 或 MSYS2; Debian/Ubuntu 上 `apt-get install g++`; "
        "macOS 上 `xcode-select --install`。")


def flags() -> list:
    if sys.platform == "win32":
        return ["-O2", "-shared", "-static"]
    return ["-O2", "-shared", "-fPIC"]


def suffix() -> str:
    if sys.platform == "win32":
        return ".dll"
    if sys.platform == "darwin":
        return ".dylib"
    return ".so"


def build(verbose: bool = True) -> list:
    import cpplib  # 复用同一套后缀/命名规则, 避免两处不一致

    cxx = compiler()
    fl = flags()
    out_paths = []
    for stem in TARGETS:
        src = os.path.join(CPP_DIR, f"{stem}.cpp")
        if not os.path.exists(src):
            raise FileNotFoundError(src)
        out = os.path.join(CPP_DIR, f"{stem}{cpplib.SUFFIX}")
        cmd = [cxx, *fl, "-o", out, src]
        if verbose:
            print("  " + " ".join(os.path.basename(c) if i == 0 else c
                                  for i, c in enumerate(cmd)), flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"编译 {stem} 失败:\n{r.stderr[-1500:]}")
        out_paths.append(out)
    return out_paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="只报告编译器与产物状态, 不编译")
    args = ap.parse_args()

    import cpplib
    if args.check:
        try:
            print("编译器:", compiler())
        except RuntimeError as e:
            print("编译器: 无 —", e)
        for stem in TARGETS:
            p = cpplib.find(stem)
            print(f"  {stem}: {'存在' if os.path.exists(p) else '缺失'} — {p}")
        return

    print(f"平台 {sys.platform} → 后缀 {cpplib.SUFFIX}")
    outs = build()
    print("已构建:")
    for p in outs:
        print(f"  {p}  ({os.path.getsize(p) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
