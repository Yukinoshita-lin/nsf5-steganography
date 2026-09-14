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
