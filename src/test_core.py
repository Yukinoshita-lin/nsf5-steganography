"""核心算法自测: 嵌入→解码往返一致性 + 汉明矩阵正确性。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from ns5_core import (build_hamming, syndrome, encode_string, decode_string,
                      embed_string, extract_string, MSG_HEADER_BITS,
                      MatrixEmbedding, nsF5Pixel)

def test_hamming():
    for p in range(1, 6):
        H = build_hamming(p)
        assert H.shape == (p, (1 << p) - 1)
        # 列向量互不相同
        cols = {tuple(H[:, j].tolist()) for j in range(H.shape[1])}
        assert len(cols) == H.shape[1]
    print("[OK] 汉明校验矩阵正确")

def test_roundtrip():
    rng = np.random.default_rng(0)
    for method in ("matrix", "nsF5"):
        for p in (2, 3, 4):
            img = rng.integers(0, 256, (64, 64), dtype=np.uint8)
            msg = "Hello nsF5! p=%d" % p
            stego, report, nb = embed_string(img, msg, method=method, p=p, password="pepper")
            got = extract_string(stego, method=method, p=p, password="pepper")
            assert got == msg, f"{method} p{p}: {got!r} != {msg!r}"
            diff = (stego != img).sum()
            assert diff <= (nb + p)  # 有损合理
    print("[OK] 嵌入/解码往返一致 (matrix 与 nsF5)")

def test_wet_paper_needed():
    # 构造块内含湿位置, 验证 nsF5 湿纸路径不破坏解码
    rng = np.random.default_rng(7)
    p, n = 3, 7
    H = build_hamming(p)
    # 令前若干块内位置为湿(像素 127/128/129), 强制局部湿纸求解
    img = rng.integers(0, 256, (1, 2048), dtype=np.uint8)
    for k in range(0, 240, n):
        img[0, k + 0] = 128
        img[0, k + 1] = 127
        img[0, k + 2] = 129
    msg = "wet-paper-test-0123"
    stego, _, nb = embed_string(img, msg, method="nsF5", p=p)
    got = extract_string(stego, method="nsF5", p=p)
    assert got == msg
    print("[OK] 湿纸路径解码一致")

def test_pwd_mismatch():
    rng = np.random.default_rng(3)
    img = rng.integers(0, 256, (32, 32), dtype=np.uint8)
    stego, _, _ = embed_string(img, "secret", method="nsF5", password="A")
    try:
        extract_string(stego, method="nsF5", password="B")
        raise AssertionError("错误口令竟能解码")
    except ValueError:
        pass
    print("[OK] 口令不匹配无法解码")

if __name__ == "__main__":
    test_hamming()
    test_roundtrip()
    test_wet_paper_needed()
    test_pwd_mismatch()
    print("\n全部通过")