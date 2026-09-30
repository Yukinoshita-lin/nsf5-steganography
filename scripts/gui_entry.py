"""窗口化入口: PyInstaller windowed exe 的启动脚本, 双击即开 GUI。

与控制台入口 (src/cli.py) 分开的原因: windowed 模式没有 stdout/stderr,
CLI 的 print 会直接崩; GUI 也不该要求用户传子命令。源码运行时本脚本
等价于 `python src/gui.py`。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(os.path.dirname(HERE), "src")
if os.path.isdir(_src):
    sys.path.insert(0, _src)

import gui  # noqa: E402

if __name__ == "__main__":
    sys.exit(gui.main())
