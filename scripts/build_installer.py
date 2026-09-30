# -*- coding: utf-8 -*-
"""构建 Windows 安装器 (打包计划 M3, 见 docs/PACKAGING.md):

    python scripts/build_installer.py

定位 Inno Setup 编译器 (ISCC): NSF5_ISCC 环境变量 -> 本机 D 盘工具目录 ->
常见安装路径 -> PATH。前置: `python scripts/build_exe.py` 已产出冻结 exe
(iss 里 GetFileVersion 读版本资源, 缺资源会直接报错)。产物:
dist/nsf5stego-setup-<版本>.exe。控制台输出只用 GBK 可编码字符。
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISS = os.path.join(PROJ, "installer", "nsf5stego.iss")


def find_iscc() -> str:
    env = os.environ.get("NSF5_ISCC")
    if env and os.path.exists(env):
        return env
    candidates = [
        os.path.join(os.environ.get("USERPROFILE", ""), os.pardir, os.pardir,
                     ".zcode", "tools", "Inno Setup 6", "ISCC.exe"),
        r"D:\Users\32403\.zcode\tools\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    which = shutil.which("ISCC")
    if which:
        candidates.append(which)
    for c in candidates:
        c = os.path.normpath(c)
        if os.path.exists(c):
            return c
    raise FileNotFoundError(
        "找不到 ISCC.exe —— 安装 Inno Setup 6 后设 NSF5_ISCC 指向 ISCC.exe, "
        "或加入 PATH")


def main() -> int:
    iscc = find_iscc()
    print(f"[iscc] {iscc}")
    r = subprocess.run([iscc, ISS], cwd=PROJ)
    if r.returncode != 0:
        print("[error] ISCC 编译失败")
        return 1
    outs = sorted(glob.glob(os.path.join(PROJ, "dist",
                                         "nsf5stego-setup-*.exe")))
    if not outs:
        print("[error] 编译完成但 dist/ 下没有 setup 产物")
        return 1
    out = outs[-1]
    print(f"[done] 安装器: {out} ({os.path.getsize(out) / 1048576:.0f}MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
