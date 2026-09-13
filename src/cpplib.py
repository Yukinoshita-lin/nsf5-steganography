"""cpplib —— 定位 cpp/ 下的 C++ 加速库产物 (跨平台)。

历史问题: `cppembed.py` / `fsfeatures.py` / `ns5_core.py` 三处都把文件名
硬编码成 `.dll`, 于是 Linux/macOS 上即使编译出了 `.so` / `.dylib` 也永远
加载不到, C++ 路径形同 Windows 专属。这里把"平台 → 后缀"的规则收在一处,
三个调用点共用。

产物不入库 (见 .gitignore): 用 `make cpp` 或 CI 现场编译; 库缺失时各调用点
都有等价的纯 Python 回退, 功能不受影响, 只是慢一些。
"""
from __future__ import annotations

import os
import sys

CPP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cpp")

if sys.platform == "win32":
    SUFFIX = ".dll"
elif sys.platform == "darwin":
    SUFFIX = ".dylib"
else:
    SUFFIX = ".so"

# 各平台的候选文件名 (Linux 惯例会加 lib 前缀)
_CANDIDATES = {
    "nsf5embed": [f"nsf5embed{SUFFIX}"] + ([f"libnsf5embed{SUFFIX}"] if os.name != "nt" else []),
    "fsfeatures": [f"fsfeatures{SUFFIX}"] + ([f"libfsfeatures{SUFFIX}"] if os.name != "nt" else []),
}


def candidates(stem: str):
    names = _CANDIDATES.get(stem) or [f"{stem}{SUFFIX}"]
    return [os.path.join(CPP_DIR, n) for n in names]


def find(stem: str) -> str:
    """返回首个存在的库路径; 都不存在时返回第一个候选 (交给 CDLL 去报错,
    调用方本来就要 try/except 回退)。"""
    cands = candidates(stem)
    for p in cands:
        if os.path.exists(p):
            return p
    return cands[0]
