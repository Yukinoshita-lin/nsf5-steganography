# -*- coding: utf-8 -*-
"""一键打包 (打包计划 M1, 见 docs/PACKAGING.md):

    python scripts/build_exe.py

流程: 读 pyproject 版本号 -> 写 build/version.txt -> 尽力编译 C++ 加速库
(失败只告警, 运行时自动回退纯 Python) -> PyInstaller 按 nsf5stego.spec 出
build/exe/nsf5stego/ (nsf5stego.exe 控制台 + nsf5stego-gui.exe 图形界面,
共享一份 DLL/模型) -> 冒烟 (--version 必须带版本号) -> 打便携 zip 到
dist/。产物不落 C 盘 (全在仓库 build/ 与 dist/ 下)。

控制台输出只使用 GBK 可编码字符 (同 test_console_encoding 约定)。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(PROJ, "build", "exe")
WORK_DIR = os.path.join(PROJ, "build", "pyinstaller")
VERSION_FILE = os.path.join(PROJ, "build", "version.txt")
APP_DIR = os.path.join(DIST_DIR, "nsf5stego")
SIZE_BUDGET_MB = 500   # docs/PACKAGING.md 的体积预算 (M2 起由测试硬断言)


def read_version() -> str:
    """pyproject.toml 的 project.version; tomllib (3.11+) 优先, 兜底正则。"""
    pp = os.path.join(PROJ, "pyproject.toml")
    try:
        import tomllib
        with open(pp, "rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    except ImportError:
        m = re.search(r'^version\s*=\s*"([^"]+)"',
                      open(pp, encoding="utf-8").read(), re.M)
        if not m:
            raise RuntimeError("pyproject.toml 里找不到 version")
        return m.group(1)


def write_version_info(version: str) -> str:
    """生成 PyInstaller 的版本资源文件 -> 写进 exe。

    作用: Explorer 属性页显示版本; 杀软信誉; Inno Setup 的
    GetFileVersion 靠它把版本号注入安装器 (M3)。"""
    parts = [int(x) for x in re.findall(r"\d+", version)[:3]]
    parts += [0] * (4 - len(parts))
    quad = ", ".join(str(x) for x in parts)
    path = os.path.join(PROJ, "build", "version_info.txt")
    content = f"""# 由 scripts/build_exe.py 生成, 勿手改。080404b0 = 简体中文 + Unicode。
VSVersionInfo(
  ffi=FixedFileInfo(filevers=({quad}), prodvers=({quad}),
                    mask=0x3F, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
                    date=(0, 0)),
  kids=[
    StringFileInfo([StringTable("080404b0", [
      StringStruct("CompanyName", "nsf5stego"),
      StringStruct("FileDescription", "nsF5 隐写工具 - 伴随式矩阵编码 + 湿纸编码 + 盲隐写分析"),
      StringStruct("FileVersion", "{version}"),
      StringStruct("InternalName", "nsf5stego"),
      StringStruct("LegalCopyright", "Apache-2.0"),
      StringStruct("OriginalFilename", "nsf5stego.exe"),
      StringStruct("ProductName", "nsF5 隐写工具"),
      StringStruct("ProductVersion", "{version}")])]),
    VarFileInfo([VarStruct("Translation", [2052, 1200])]),
  ])
"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


def build_cpp() -> bool:
    """尽力编译 C++ 加速库; 没编译器/失败都只告警 (运行时回退纯 Python)。"""
    script = os.path.join(PROJ, "scripts", "build_cpp.py")
    if not os.path.exists(script):
        print("[warn] 找不到 scripts/build_cpp.py, 跳过 C++ 加速库")
        return False
    r = subprocess.run([sys.executable, script], cwd=PROJ,
                       capture_output=True, text=True)
    if r.returncode == 0:
        print("[ok] C++ 加速库已编译, 随包分发")
        return True
    print("[warn] C++ 加速库编译失败, 安装包不含加速 (纯 Python 回退):\n"
          + (r.stderr or r.stdout).strip()[-400:])
    return False


def main() -> int:
    os.chdir(PROJ)
    version = read_version()
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    with open(VERSION_FILE, "w", encoding="utf-8") as fh:
        fh.write(version + "\n")
    write_version_info(version)
    print(f"[1/4] 版本号 {version} -> version.txt + version_info.txt")

    build_cpp()
    print("[2/4] PyInstaller 构建 (console + windowed 双入口, 约 3 分钟)...")

    # 冒烟构建的教训: add-data 相对路径按 --specpath 解析, 必须绝对路径;
    # spec 里已写绝对安全的相对项, 这里只传 distpath/workpath。
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", DIST_DIR, "--workpath", WORK_DIR, "nsf5stego.spec"],
        cwd=PROJ)
    if r.returncode != 0:
        print("[error] PyInstaller 构建失败")
        return 1
    exe_cli = os.path.join(APP_DIR, "nsf5stego.exe")
    exe_gui = os.path.join(APP_DIR, "nsf5stego-gui.exe")
    for exe in (exe_cli, exe_gui):
        if not os.path.exists(exe):
            print(f"[error] 缺产物: {exe}")
            return 1

    print("[3/4] 冻结冒烟...")
    r = subprocess.run([exe_cli, "--version"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=120, cwd=os.environ.get("TEMP", PROJ))
    ver_out = (r.stdout or "").strip()
    if r.returncode != 0 or version not in ver_out:
        print(f"[error] 冻结 exe --version 异常: rc={r.returncode} "
              f"输出={ver_out!r} (应包含 {version})")
        return 1
    print(f"[ok] nsf5stego.exe --version: {ver_out}")

    mb = sum(os.path.getsize(os.path.join(dp, f))
             for dp, _, fs in os.walk(APP_DIR) for f in fs) / 1048576
    print(f"[info] onedir 体积 {mb:.0f}MB (预算 {SIZE_BUDGET_MB}MB)"
          + ("" if mb <= SIZE_BUDGET_MB else " —— 超预算, 检查 spec 的 excludes"))

    print("[4/4] 打便携 zip...")
    os.makedirs(os.path.join(PROJ, "dist"), exist_ok=True)
    zip_path = os.path.join(PROJ, "dist",
                            f"nsf5stego-portable-{version}-win64.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dp, _, fs in os.walk(APP_DIR):
            for f in fs:
                p = os.path.join(dp, f)
                zf.write(p, os.path.relpath(p, DIST_DIR))
    print(f"[done] 便携包: {zip_path} "
          f"({os.path.getsize(zip_path) / 1048576:.0f}MB)\n"
          f"       安装版 (Inno Setup) 在 M3 接入, GUI exe 可直接双击验证")
    return 0


if __name__ == "__main__":
    sys.exit(main())
