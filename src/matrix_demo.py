"""伴随式矩阵编码 教学演示逻辑。

给定一个 LSB 块与目标伴随式 m，在二元汉明码 [n=2^p-1, k, 3] 下：
  1) 计算该块当前实际伴随式 s = syndrome(H, x)；
  2) 若 s != m，则差值 d = s ^ m；
  3) d 必对应校验矩阵 H 的某一列 → 翻转其所在系数即可使伴随式等于目标 m。

返回单步所需的全部可视化信息(被高亮的系数、翻转前后值、校验结果)。
仅用 numpy, 无 pygame/matplotlib 依赖, 便于单测。
"""
from __future__ import annotations
import numpy as np
from ns5_core import build_hamming, syndrome


def fmt_bin(v: int, p: int) -> str:
    return f"{int(v):0{p}b}"


def random_block(p: int, seed: int | None = None) -> np.ndarray:
    """随机生成一个 n=2^p-1 位的 LSB 块(演示输入)。"""
    n = (1 << p) - 1
    rng = np.random.default_rng(seed)
    return rng.integers(0, 2, size=n, dtype=np.uint8)


def demo_step(p: int, x, m_bin: str) -> dict:
    """计算伴随式查找的一步。

    x: 块内 n 位 LSB(广播/截取到 n)。m_bin: p 位二进制目标伴随式, 如 "110"。
    返回 dict 含: syndrome 十进制/二进制、差值、命中系数(0-based)、
    flip_from/flip_to、修改后二次校验结果(verified)。
    """
    if not 1 <= p <= 8:
        raise ValueError("p 应在 1..8")
    if len(m_bin) != p:
        raise ValueError(f"目标伴随式应为 {p} 位二进制, 当前为 {len(m_bin)} 位")
    m_val = int(m_bin, 2)
    n = (1 << p) - 1
    x1 = np.asarray(x, dtype=np.uint8).reshape(-1)[:n]

    H = build_hamming(p)
    s = syndrome(H, x1)
    s_val = int(np.dot(s, 1 << np.arange(p)))      # r=0 为 LSB
    d_val = s_val ^ m_val
    modified = (s_val != m_val)
    valid_col = (1 <= d_val <= n)                   # d==0 表示无需修改
    col = d_val - 1 if valid_col else 0             # 0-based
    flip_from = int(x1[col]) if valid_col else None
    x_after = x1.copy()
    if valid_col:
        x_after[col] ^= 1
    s2 = syndrome(H, x_after)
    s2_val = int(np.dot(s2, 1 << np.arange(p)))

    return dict(p=p, n=n, x=x1,
                s_val=s_val, s_bin=fmt_bin(s_val, p),
                m_val=m_val, m_bin=m_bin,
                d_val=d_val, d_bin=fmt_bin(d_val, p),
                modified=modified, valid_col=valid_col, col=col,
                flip_label=(f"第 {col + 1} 个系数" if valid_col else "已是目标, 无需修改"),
                flip_from=flip_from,
                flip_to=(None if flip_from is None else 1 - flip_from),
                s2_val=s2_val, s2_bin=fmt_bin(s2_val, p),
                verified=(s2_val == m_val))