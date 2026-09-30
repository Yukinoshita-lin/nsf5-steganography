"""pathutil 单测: output_dir 的两种布局判定 (2026-09-29)。

背景: `pip install nsf5stego` 后 gui.py / efficiency.py 位于 site-packages,
原来的 `dirname(dirname(__file__))/output` 会把嵌入结果与效率图写进解释器根
—— 系统 Python 直接 PermissionError, 用户级安装则悄悄污染 site-packages。
output_dir() 按 "project_dir 下是否同时存在 src/ 与 pyproject.toml" 区分
仓库布局 (沿用 仓库/output) 与安装布局 (改用 当前工作目录/output)。
`python src/test_pathutil.py` 与 `pytest` 均可运行。
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import pathutil as PU

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_output_dir_repo_layout():
    assert PU.output_dir(PROJ) == os.path.join(PROJ, "output"), \
        "仓库布局 (src/ + pyproject.toml) 应沿用 仓库/output"
    print("[OK] output_dir 仓库布局 -> 仓库/output")


def test_output_dir_installed_layout_uses_cwd():
    # 不真的 chdir: Windows 上临时目录一旦当过进程 cwd, rmtree 就可能
    # 撞上 WinError 32 (本测试首跑即复现)。改为补丁 os.getcwd。
    import shutil
    fake_cwd = tempfile.mkdtemp(prefix="nsf5_outdir_")
    real_getcwd = os.getcwd
    try:
        os.getcwd = lambda: fake_cwd
        fake_site = os.path.join(fake_cwd, "site-packages")  # 非仓库布局
        got = PU.output_dir(fake_site)
        assert got == os.path.join(fake_cwd, "output"), \
            f"安装布局应写当前工作目录, 实际 {got}"
    finally:
        os.getcwd = real_getcwd
        shutil.rmtree(fake_cwd, ignore_errors=True)
    print("[OK] output_dir 安装布局 -> 当前工作目录/output")


def test_rel_from_proj_normal_path():
    rel = PU.rel_from_proj(os.path.join(PROJ, "src", "x.py"), PROJ)
    assert rel.replace("\\", "/") == "src/x.py", f"普通相对路径不应变形: {rel}"
    print("[OK] rel_from_proj 常规相对路径")


# --------------------------------------------------------------------------- #
#  冻结环境 (PyInstaller 安装版) 分支: sys._MEIPASS 存在即视为 frozen
# --------------------------------------------------------------------------- #
def test_app_version_frozen_reads_version_txt():
    fake = tempfile.mkdtemp(prefix="nsf5_ver_")
    with open(os.path.join(fake, "version.txt"), "w", encoding="utf-8") as fh:
        fh.write("9.9.9-test\n")
    old = getattr(sys, "_MEIPASS", None)
    sys._MEIPASS = fake
    try:
        assert PU.app_version() == "9.9.9-test", \
            "冻结环境必须读 version.txt, 而不是查安装元数据"
    finally:
        if old is None:
            del sys._MEIPASS
        else:
            sys._MEIPASS = old
        shutil.rmtree(fake, ignore_errors=True)
    print("[OK] app_version 冻结分支: 读 _MEIPASS/version.txt")


def test_output_dir_frozen_uses_appdata():
    # 冻结 + 装进 Program Files 时 cwd 不可写: 产物必须落 %APPDATA%
    import shutil
    fake = tempfile.mkdtemp(prefix="nsf5_appdata_")
    old_meipass = getattr(sys, "_MEIPASS", None)
    old_appdata = os.environ.get("APPDATA")
    sys._MEIPASS = fake                      # 冻结标记
    os.environ["APPDATA"] = fake
    try:
        got = PU.output_dir(os.path.join(fake, "Program Files", "nsf5stego"))
        assert got == os.path.join(fake, "nsf5stego", "output"), \
            f"冻结环境应写 %APPDATA%/nsf5stego/output, 实际 {got}"
    finally:
        if old_meipass is None:
            del sys._MEIPASS
        else:
            sys._MEIPASS = old_meipass
        if old_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = old_appdata
        shutil.rmtree(fake, ignore_errors=True)
    print("[OK] output_dir 冻结分支: %APPDATA%/nsf5stego/output")


if __name__ == "__main__":
    test_output_dir_repo_layout()
    test_output_dir_installed_layout_uses_cwd()
    test_rel_from_proj_normal_path()
    test_app_version_frozen_reads_version_txt()
    test_output_dir_frozen_uses_appdata()
    print("\n全部通过")
