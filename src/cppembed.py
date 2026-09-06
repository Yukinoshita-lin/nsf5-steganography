"""
cppembed —— nsF5 / matrix 嵌入的 C++ 加速封装。

与 ns5_core.embed_string 逻辑完全一致(种子/置乱/头部·正文池相同),
仅把逐块伴随式编码循环交给 cpp/nsf5embed.dll。提供回环自校验:
嵌入后立即用原生 Python 解码, 若不一致则报错(防止跨语言行为漂移)。
"""
from __future__ import annotations
import os
import ctypes
import hashlib

import numpy as np

from ns5_core import (encode_string, COVER_HASH_BYTES, derive_seed, permute_index,
                      MatrixEmbedding, MSG_HEADER_BITS, build_hamming)

DLL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "cpp", "nsf5embed.dll")

_lib = None
def _get_lib():
    global _lib
    if _lib is None:
        _lib = ctypes.CDLL(DLL_PATH)
        fn = _lib.nsf5_embed
        fn.argtypes = [
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,   # c, npix
            ctypes.POINTER(ctypes.c_int), ctypes.c_int,     # order, num_blocks
            ctypes.c_int, ctypes.c_int,                     # n, p
            ctypes.POINTER(ctypes.c_uint8), ctypes.c_int,   # bits, nbits
            ctypes.c_int,                                   # method
        ]
        fn.restype = None
    return _lib


def _run(c_flat: np.ndarray, blocks, bits: np.ndarray, n: int, p: int, method_flag: int):
    if not blocks:
        return
    lib = _get_lib()
    order = np.concatenate(blocks).astype(np.int32)
    bits = np.ascontiguousarray(bits, dtype=np.uint8)
    src = c_flat.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
    oar = order.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
    bar = bits.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8))
    lib.nsf5_embed(src, int(c_flat.size), oar, int(len(blocks)),
                   int(n), int(p), bar, int(bits.size), int(method_flag))


def _is_matrix(method: str) -> bool:
    return isinstance(method, str) and method.lower().startswith("matrix")


def _is_lsb(method: str) -> bool:
    return isinstance(method, str) and method.lower() in ("lsb", "lsb_direct", "lsb-replace")


def _embed_lsb_direct(image: np.ndarray, bits: np.ndarray) -> tuple[np.ndarray, int]:
    """直接 LSB 替换: 把 image 的 LSB 写成 bits 序列 (uint8 0/1)。
    与 nsF5 共享"头部 + 正文 + 16位长度头" 的比特流结构, 但不需要 cover_hash 同步.
    返回 (stego, changed_px_count).
    """
    img0 = np.ascontiguousarray(image).astype(np.uint8)
    stego = img0.copy()
    if stego.ndim == 3:
        ch = stego[..., 0].reshape(-1)
    else:
        ch = stego.reshape(-1)
    n = min(bits.size, ch.size)
    # 旧 LSB
    old = ch[:n] & 1
    flip = bits[:n].astype(np.uint8) ^ old
    ch[:n] = (ch[:n] & 0xFE) | bits[:n].astype(np.uint8)
    return stego, int(flip.sum())


def _lsb_extract_bits(image: np.ndarray, offset: int, nbits: int) -> np.ndarray:
    """从 image[offset:offset+nbits] 的 LSB 位平面抽出 nbits 个 0/1 (MSB-first in output).
    注意: 我们存的是"每像素一个 bit"流, 不是字节流, 所以不能用 unpackbits 字节展开.
    """
    img0 = np.ascontiguousarray(image).astype(np.uint8)
    if img0.ndim == 3:
        ch = img0[..., 0].reshape(-1)
    else:
        ch = img0.reshape(-1)
    bits = (ch[offset:offset + nbits] & 1).astype(np.uint8)
    return bits


def _extract_lsb_direct(image: np.ndarray, _body_bytes_ignored: int = 0):
    """读出正文 (依赖 16 位长度头)."""
    if image.ndim == 3:
        ch = image[..., 0].reshape(-1)
    else:
        ch = image.reshape(-1)
    head_bits = _lsb_extract_bits(image, 0, 16)
    n_bytes = int(head_bits.dot(1 << np.arange(15, -1, -1)))
    body_bits = _lsb_extract_bits(image, 16, n_bytes * 8)
    out = bytearray()
    for i in range(0, n_bytes * 8, 8):
        out.append(int(body_bits[i:i + 8].dot(1 << np.arange(7, -1, -1))))
    return bytes(out)


def _fast_perm(total: int, seed: int) -> np.ndarray:
    """向量化置换 (numpy C 实现, ~87x 快于 Python Fisher-Yates)。
    仅用于数据集批量化: 置换顺序不同, 但嵌入仍自洽(无需解码), 生成真实 stego 图。"""
    return np.random.default_rng(seed).permutation(total)


def embed_string(image, text: str, method: str = "nsF5", p: int = 3,
                 password: str = "", check: bool = True, fast_permute: bool = False):
    """以 C++ 嵌入, 返回 (stego, report, nbits)。nbits=正文比特数(含16位头)。
    fast_permute=True 用向量化置换加速(见 _fast_perm), 仅供批量生成, 配合 check=False。"""
    if fast_permute:
        permute = _fast_perm
    else:
        from ns5_core import permute_index
        permute = permute_index
    img0 = np.ascontiguousarray(image).astype(np.uint8)
    stego = img0.copy()
    if img0.ndim == 3:
        channel = stego[..., 0].reshape(-1)
    else:
        channel = stego.reshape(-1)
    c = channel
    total = int(c.size)
    method_flag = 0 if _is_matrix(method) else 1
    n = (1 << p) - 1

    body_bits = encode_string(text)                      # 16 bit 长度头 + 正文
    img_bytes = img0.tobytes()
    cover_hash = hashlib.sha256(img_bytes).digest()[:COVER_HASH_BYTES]
    head_arr = np.unpackbits(np.frombuffer(cover_hash, np.uint8))

    if _is_lsb(method):
        # 直接 LSB 替换: 无块结构, 无 cover_hash 同步.
        # 16 位长度头 + 实际正文 (text 的 ASCII 字节, 8 bit/字节, 末尾 pad 到 8).
        N_h = 16
        if total <= N_h + 8:
            raise ValueError("图像太小, 无法容纳头部+正文")
        # 正文 = text.encode 的 unpackbits (不带 16 位长头)
        body_bits_raw = np.unpackbits(np.frombuffer(text.encode("ascii"), dtype=np.uint8))
        n_body_bytes = body_bits_raw.size // 8 if body_bits_raw.size % 8 == 0 else body_bits_raw.size // 8 + 1
        body_full = np.pad(body_bits_raw, (0, (-body_bits_raw.size) % 8))
        head_full = np.array([(n_body_bytes >> (15 - k)) & 1 for k in range(16)], dtype=np.uint8)
        full_bits = np.concatenate([head_full, body_full])
        stego, _changed = _embed_lsb_direct(stego, full_bits)
        changed = int(np.sum(stego != img0))
        if check:
            body_back = _extract_lsb_direct(stego, 0)
            if body_back.decode("ascii", errors="replace") != text:
                raise RuntimeError(f"LSB 嵌入回环校验失败: decode != text")
        report = dict(cover_hash=cover_hash.hex(), head_bits=N_h, cover_changed=changed)
        return stego, report, int(body_bits_raw.size)

    hdr_blocks = max(2, int(np.ceil((COVER_HASH_BYTES * 8) / p)))
    N_h = hdr_blocks * n
    if total <= N_h + n:
        raise ValueError("图像太小, 无法容纳头部+正文, 请放大图像或改用较小的 p")
    head_pad = (-head_arr.size) % p
    head_full = np.pad(head_arr, (0, head_pad))
    body_pad = (-body_bits.size) % p
    body_full = np.pad(body_bits, (0, body_pad))
    body_pool = total - N_h

    # 头部池 (seed0 = 仅口令)
    seed0 = derive_seed(b"", password)
    perm0 = permute(N_h, seed0)
    head_order = MatrixEmbedding._pool_positions(perm0, N_h, n, hdr_blocks, pool_start=0)
    _run(c, head_order, head_full, n, p, method_flag)

    # 正文池 (seed = cover_hash + 口令)
    seedB = derive_seed(cover_hash, password)
    permB = permute(body_pool, seedB)
    nbody = body_full.size // p
    body_order = MatrixEmbedding._pool_positions(permB, body_pool, n, nbody, pool_start=N_h)
    _run(c, body_order, body_full, n, p, method_flag)

    changed = int(np.sum(stego != img0))
    if check:
        from ns5_core import extract_string
        back = extract_string(stego, method=method, p=p, password=password)
        if back != text:
            raise RuntimeError(f"C++ 嵌入回环校验失败: decode != text")
    report = dict(cover_hash=cover_hash.hex(), head_bits=N_h * 8, cover_changed=changed)
    return stego, report, int(body_bits.size)


def selfcheck(verbose: bool = False):
    """多种参数回环自检: 嵌入→原生解码 必须还原原文。"""
    rng = np.random.default_rng(7)
    cases = 0
    skipped = 0
    # 容量: p=4 时 3000B 需 ~30060px 正文池, 故用大图保证全部不超容量
    for shape, sizes in [((256, 256), (0, 1, 50, 1000)),
                         ((321, 217), (0, 1, 200, 3000))]:
        img = rng.integers(24, 232, shape, dtype=np.uint8)
        for method in ("nsF5", "matrix"):
            for p in (2, 3, 4):
                for sz in sizes:
                    text = "A" * sz
                    try:
                        st, rep, nb = embed_string(img, text, method=method, p=p, check=True)
                    except ValueError as e:  # 容量超限 → 跳过
                        skipped += 1
                        if verbose:
                            print(f"  !! {method} p={p} {shape} msg={sz}B 跳过({str(e)[:30]})")
                        continue
                    cases += 1
                    if verbose:
                        print(f"  {method} p={p} {shape} msg={sz}B -> changed={rep['cover_changed']}")
    print(f"[OK] cppembed 回环自检通过 ({cases} 用例, 容量跳过 {skipped})")


if __name__ == "__main__":
    selfcheck(verbose=True)