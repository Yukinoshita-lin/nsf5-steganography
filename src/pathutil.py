"""跨平台路径显示的小工具。

为什么需要它 (2026-09-14)
------------------------
脚本里到处写 `os.path.relpath(path, PROJ)` 来"显示相对仓库根的路径"。这在
**路径与仓库不在同一个盘符**时会直接抛 `ValueError: path is on mount 'C:',
start on mount 'F:'` —— `--out` / `OUT_MODEL` / `--csv-out` 之类参数完全可以
指向别处 (CI 上就是 `/tmp`), 于是"只是打印一行日志"就足以让整个脚本退出非零。
实测踩到过一次: 冒烟测试把模型写到系统临时目录, `train_model.py` 训练全都跑完、
报告也打印了, 最后在写指标 CSV 时崩掉。

`rel_from_proj()` 的行为: 能相对就相对, 不能就原样返回 (统一成正斜杠), 永不抛错。
"""
from __future__ import annotations

import os


def rel_from_proj(path: str, proj: str) -> str:
    """返回相对 `proj` 的路径; 跨盘符/无法相对时返回绝对路径。永不抛错。"""
    try:
        rel = os.path.relpath(path, proj)
    except ValueError:
        rel = os.path.abspath(path)
    return rel.replace("\\", "/")


def app_version(package: str = "nsf5stego") -> str:
    """安装元数据里的版本号; 源码运行且未安装时返回空串。

    冻结环境 (PyInstaller) 没有发行元数据, 读构建时随包打入的
    version.txt (见 scripts/build_exe.py)。

    永不抛错: GUI 标题栏 / CLI --version 只是想"报个版本", 不能因为元数据
    缺失而打断主流程 (从源码目录 `python src/gui.py` 而没有 `pip install -e .`
    时 importlib.metadata 查不到 nsf5stego 是常态)。"""
    try:
        import sys
        mp = getattr(sys, "_MEIPASS", None)
        if mp:
            vf = os.path.join(mp, "version.txt")
            if os.path.exists(vf):
                with open(vf, encoding="utf-8") as fh:
                    v = fh.read().strip()
                if v:
                    return v
        from importlib.metadata import version
        return version(package)
    except Exception:
        return ""


def output_dir(project_dir: str) -> str:
    """产物输出目录: 仓库布局用 <仓库>/output, 安装布局用 <当前目录>/output。

    冻结环境 (PyInstaller 安装版) 用户目录优先: 安装到 Program Files 时
    cwd/安装目录都不可写, 产物落 `%APPDATA%/nsf5stego/output`
    (非 Windows: XDG_DATA_HOME 或 ~/.local/share/nsf5stego/output)。

    为什么 (2026-09-29): gui.py / efficiency.py 原来一律拼
    dirname(dirname(module.__file__))/output。源码运行没问题, 但
    `pip install nsf5stego` 后 gui.py 位于 site-packages, PROJECT_DIR 变成
    解释器根 (如 C:/Python314), 嵌入结果与效率图会写进安装目录 —— 系统
    Python 下直接 PermissionError, 用户级安装则悄悄污染 site-packages。
    识别仓库布局的依据: project_dir 下同时存在 src/ 与 pyproject.toml。"""
    import sys
    if getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None):
        if os.name == "nt":
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
        else:
            base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
                os.path.join("~", ".local", "share"))
        return os.path.join(base, "nsf5stego", "output")
    repo_layout = (os.path.isdir(os.path.join(project_dir, "src"))
                   and os.path.isfile(os.path.join(project_dir, "pyproject.toml")))
    base = project_dir if repo_layout else os.getcwd()
    return os.path.join(base, "output")
