"""核心算法自测: 嵌入→解码往返一致性 + 汉明矩阵正确性。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from ns5_core import (build_hamming, syndrome, encode_string, decode_string,
                      embed_string, extract_string, MSG_HEADER_BITS,
                      MatrixEmbedding, nsF5Pixel, get_image_hash,
                      derive_seed, solve_wet_paper, gauss_solve_GF2, permute_index)

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

# ---- 之前零测试的公共函数 ----
def test_permute_index_deterministic():
    # permute_index 承载 C++/Python 双路径的可逆性命脉: 同种子必同排列, 且是合法置换
    for seed in (0, 99, 2026):
        p1 = permute_index(1000, seed)
        p2 = permute_index(1000, seed)
        assert np.array_equal(p1, p2), "同种子应产生相同排列"
        assert sorted(p1.tolist()) == list(range(1000)), "应为 0..999 的合法置换"
    print("[OK] permute_index 确定性 + 合法置换")

def test_derive_seed():
    # 同输入同种子, 不同输入不同种子, 空/非空口令区分
    assert derive_seed(b"imgA") == derive_seed(b"imgA")
    assert derive_seed(b"imgA") != derive_seed(b"imgB")
    assert derive_seed(b"imgA", "pw") != derive_seed(b"imgA", "")
    print("[OK] derive_seed 确定性且区分输入")

def test_get_image_hash():
    a = np.zeros((4, 4), dtype=np.uint8)
    b = a.copy()
    assert get_image_hash(a) == get_image_hash(b)
    b[0, 0] = 1
    assert get_image_hash(a) != get_image_hash(b)
    print("[OK] get_image_hash 对内容敏感")

def test_solve_wet_paper_solves_target():
    # 湿纸解必须满足 H·e = target, 且只改动干列
    p, n = 3, 7
    H = build_hamming(p)
    target = np.array([1, 1, 0], np.uint8)
    dry = [0, 2, 3, 5, 6]
    e = solve_wet_paper(H, dry, target)
    assert e is not None
    assert np.array_equal(syndrome(H, e), target), "湿纸解应满足伴随式=目标"
    assert all(e[j] == 0 for j in range(n) if j not in dry), "只应改动干列"
    # 确定性: 两次调用结果一致 (B4)
    e2 = solve_wet_paper(H, dry, target)
    assert np.array_equal(e, e2)
    print("[OK] solve_wet_paper 解正确 + 确定性")

def test_gauss_solve_GF2():
    # 用满秩列向量验证消元 (可解), 及不可解情形返回 None
    cols = [np.array([1, 0, 0], np.uint8), np.array([0, 1, 0], np.uint8),
            np.array([0, 0, 1], np.uint8)]
    x = gauss_solve_GF2(cols, np.array([1, 0, 1], np.uint8))
    assert np.array_equal(x, np.array([1, 0, 1], np.uint8))
    # 列不足 (秩 < 目标维数) -> 不可解
    short = [np.array([1, 0], np.uint8), np.array([1, 0], np.uint8)]
    assert gauss_solve_GF2(short, np.array([0, 1], np.uint8)) is None
    print("[OK] gauss_solve_GF2 可解/不可解判定正确")

def test_utf8_roundtrip():
    # B7: 中文等多字节字符不能被静默替换为 "?"
    img = np.random.default_rng(11).integers(0, 256, (64, 64), dtype=np.uint8)
    for msg in ("中文测试 hello ✅", "nsF5 隐写 demo"):
        stego, _, _ = embed_string(img, msg, method="nsF5", p=3)
        assert extract_string(stego, method="nsF5", p=3) == msg
    # 直接单元测试 encode/decode_string
    bits = encode_string("你好世界")
    assert decode_string(bits) == "你好世界"
    print("[OK] UTF-8 往返 (中文不被替换)")

def test_rgb_cover_changed():
    # B1: RGB 图 cover_changed 不得恒为 0 (之前把 stego 重绑成 img0 自比较)
    rgb = np.random.default_rng(5).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    stego, report, _ = embed_string(rgb, "rgb test", method="matrix", p=3)
    assert (stego != rgb).sum() == report["cover_changed"] > 0
    assert extract_string(stego, method="matrix", p=3) == "rgb test"
    print("[OK] RGB cover_changed 统计正确")

def test_capacity_error():
    # B2: 消息放不下时应明确报错, 而非静默截断
    img = np.random.default_rng(2).integers(0, 256, (64, 64), dtype=np.uint8)
    try:
        embed_string(img, "A" * 20000, method="nsF5", p=3)
        raise AssertionError("超载消息应报错")
    except ValueError as e:
        assert "消息过长" in str(e) or "图像太小" in str(e)
    print("[OK] 容量不足明确报错")

if __name__ == "__main__":
    test_hamming()
    test_roundtrip()
    test_wet_paper_needed()
    test_pwd_mismatch()
    test_permute_index_deterministic()
    test_derive_seed()
    test_get_image_hash()
    test_solve_wet_paper_solves_target()
    test_gauss_solve_GF2()
    test_utf8_roundtrip()
    test_rgb_cover_changed()
    test_capacity_error()
    print("\n全部通过")