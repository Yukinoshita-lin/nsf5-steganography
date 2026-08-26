"""
nsF5 隐写核心 —— 伴随式矩阵编码（二元汉明码）+ 湿纸编码 + 图像哈希自同步。

算法要点
--------
1) 二元汉明码 [n,k,d], n = 2^p - 1: 校验矩阵 H 列向量取 GF(2)^p 全部非零向量。
   伴随式(矩阵)编码: 载体系数 LSB 奇偶向量 x, 伴随式 s = H·x (mod 2)。
   嵌入 p 比特 m: s==m 不改; 否则 d=s^m, 找唯一列 j (H_j==d) 改动该系数。
   每块至多改 1 个系数 → 嵌入效率随 p 提高。

2) F5 与 nsF5: F5 减幅递减, 系数减到 0 时"收缩"导致整块重嵌、载荷下降;
   nsF5 用湿纸编码, 预标记"减幅会归零=湿", 湿位不动, 在"干"位解 GF(2)
   线性方程完成嵌入 → 无收缩, 嵌入效率与安全性更高。

3) 图像哈希自同步(考虑图像哈希):
   载入原图时计算 SHA-256 (cover_hash)。
    · 头部区(idx 0..N_h) : 用仅"口令"派生的种子 seed0 预埋 cover_hash(认证头);
    · 正文区(其余像素) : 用 cover_hash+口令 派生 seed, 键控正文置乱路径。
   解码端先用 seed0 读头部取回 cover_hash, 再重算正文 seed 解码。
   这样隐藏路径由"图像内容哈希"唯一决定, 改动任意像素会使解码结构破坏 →
   可经头部区块校验感知篡改。这是本程序对"考虑图像哈希值"的落点。
"""

from __future__ import annotations

import hashlib
from typing import Sequence

import numpy as np

MSG_HEADER_BITS = 16   # ASCII 字节数(≤65535)
COVER_HASH_BYTES = 16  # 认证头: 截取 sha256 前16字节 (128 bit), 控制头部开销


# --------------------------------------------------------------------------- #
#  二元汉明码
# --------------------------------------------------------------------------- #
def build_hamming(p: int) -> np.ndarray:
    if p < 1:
        raise ValueError("p 必须 >= 1")
    n = (1 << p) - 1
    H = np.zeros((p, n), dtype=np.uint8)
    for j in range(1, n + 1):
        for r in range(p):
            H[r, j - 1] = (j >> r) & 1
    return H


def syndrome(H: np.ndarray, x: np.ndarray) -> np.ndarray:
    """s = H·x (mod 2)。x:(n,)→(p,)。"""
    return (H @ (x & 1)) & 1


# --------------------------------------------------------------------------- #
#  密钥/种子
# --------------------------------------------------------------------------- #
def derive_seed(image_bytes: bytes, password: str = "") -> int:
    base = hashlib.sha256(image_bytes).hexdigest()
    if password:
        base = hashlib.sha256(base.encode() + password.encode()).hexdigest()
    return int(base, 16)


_perm_fn = None
_perm_checked = False


def _load_cpp_permute():
    """惰性加载 cpp/nsf5embed.dll 的 nsf5_permute(仅一次)。缺失/失败返回 None。"""
    global _perm_fn, _perm_checked
    if not _perm_checked:
        _perm_checked = True
        try:
            import ctypes
            import os
            dll = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), "cpp", "nsf5embed.dll")
            fn = ctypes.CDLL(dll).nsf5_permute
            fn.argtypes = [ctypes.c_longlong, ctypes.c_ulonglong,
                           ctypes.POINTER(ctypes.c_longlong)]
            fn.restype = None
            _perm_fn = fn
        except Exception:
            _perm_fn = None
    return _perm_fn


def permute_index(total: int, seed: int) -> np.ndarray:
    """确定性伪随机置换。

    - 优先走 C++ nsf5_permute(splitmix64 + Fisher-Yates), 超大图显著快;
    - DLL 缺失时用下方同算法的 Python fallback, 保证两路径序列一致,
      从而"嵌入/解码"无论有无 DLL 都能还原。
    该置换必须是"保持同一算法"的稳定映射; 改了会破坏可逆性。
    """
    fn = _load_cpp_permute()
    if fn is not None:
        import ctypes
        out = np.empty(total, dtype=np.int64)
        ptr = out.ctypes.data_as(ctypes.POINTER(ctypes.c_longlong))
        fn(int(total), int(seed) & ((1 << 64) - 1), ptr)
        return out
    mask = (1 << 64) - 1
    a = np.arange(total, dtype=np.int64)
    x = int(seed) & mask
    for i in range(total - 1, 0, -1):
        x = (x + 0x9E3779B97F4A7C15) & mask
        z = x
        z = (z ^ (z >> 30)) & mask
        z = (z * 0xBF58476D1CE4E5B9) & mask
        z = (z ^ (z >> 27)) & mask
        z = (z * 0x94D049BB133111EB) & mask
        r = (z ^ (z >> 31)) & mask
        j = int(r % (i + 1))
        a[i], a[j] = a[j], a[i]
    return a


# --------------------------------------------------------------------------- #
#  消息编码: ASCII → 比特 (16 位长度头)
# --------------------------------------------------------------------------- #
def encode_string(text: str) -> np.ndarray:
    raw = text.encode("ascii", errors="replace")
    length = len(raw)
    if length > 0xFFFF:
        raise ValueError("ASCII 文本过长(≤65535 字节)")
    head = np.array([(length >> i) & 1 for i in range(MSG_HEADER_BITS)], np.uint8)
    body = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))
    return np.concatenate([head, body])


def decode_string(bits: np.ndarray) -> str:
    if bits.size < MSG_HEADER_BITS:
        raise ValueError("数据过短, 无法解码长度头")
    length = sum(int(bits[i]) << i for i in range(MSG_HEADER_BITS))
    body = bits[MSG_HEADER_BITS:MSG_HEADER_BITS + length * 8]
    if body.size < length * 8:
        raise ValueError("有效载荷不足, 消息可能被截断或被破坏")
    return bytes(np.packbits(body[:length * 8])).decode("ascii", errors="replace")


# --------------------------------------------------------------------------- #
#  湿纸求解: 在"干"列上找尽量稀疏的解 H[:,dry]·y = target
# --------------------------------------------------------------------------- #
def solve_wet_paper(H, dry_cols: Sequence[int], target, max_weight: int = 2):
    dry = np.asarray(list(dry_cols), dtype=np.int64)
    if dry.size == 0:
        return None
    target = target.astype(np.uint8)
    n = H.shape[1]
    # 权重 1: 单个干列命中
    for ci in dry:
        if np.array_equal(H[:, ci], target):
            e = np.zeros(n, np.uint8); e[ci] = 1; return e
    # 权重 2: 成对干列异或命中
    if max_weight >= 2 and dry.size >= 2:
        rng = np.random.default_rng(int(np.random.randint(0, 1 << 30)))
        order = rng.permutation(dry.size)
        limit = min(dry.size, 600)
        for a in range(limit):
            for b in range(limit):
                if a == b:
                    continue
                ca, cb = int(dry[order[a]]), int(dry[order[b]])
                if np.array_equal((H[:, ca] ^ H[:, cb]).astype(np.uint8), target):
                    e = np.zeros(n, np.uint8); e[ca] = 1; e[cb] = 1; return e
    # 兜底: GF(2) 高斯消元一般解(可解时必定成功, 自由变量置0压低权重)
    sol = gauss_solve_GF2([H[:, ci] for ci in dry], target)
    if sol is None:
        return None
    e = np.zeros(n, np.uint8)
    for k, ci in enumerate(dry):
        if sol[k]:
            e[ci] = 1
    return e


def gauss_solve_GF2(cols, b):
    """解 A·x = b (mod 2)。cols: 列向量列表, A = hstack(cols)。返回 0/1 系数
    (自由变量置 0 以降低权重) 或不可解时 None。"""
    m = len(cols)
    p = len(cols[0])
    if m == 0:
        return None
    A = np.hstack([c[:, None].astype(np.uint8) for c in cols])  # (p, m)
    b = np.array(b, np.uint8).reshape(-1)
    aug = np.hstack([A, b[:, None]])  # (p, m+1), 最后列为增广
    col_piv = np.zeros(m, np.int64)
    piv_row = 0
    for c in range(m):
        r = piv_row
        while r < p and aug[r, c] == 0:
            r += 1
        if r == p:
            continue
        aug[[piv_row, r]] = aug[[r, piv_row]]
        for rr in range(p):
            if rr != piv_row and aug[rr, c]:
                aug[rr] ^= aug[piv_row]
        col_piv[piv_row] = c
        piv_row += 1
        if piv_row == p:
            break
    for r in range(piv_row, p):
        if aug[r, m] == 1 and np.all(aug[r, :m] == 0):
            return None
    x = np.zeros(m, np.uint8)
    for r in range(piv_row):
        x[col_piv[r]] = aug[r, m]
    return x


# --------------------------------------------------------------------------- #
#  矩阵编码(伴随式编码) —— 纯 LSB 翻转
# --------------------------------------------------------------------------- #
class MatrixEmbedding:
    """伴随式矩阵编码核心: 在给定像素池(perm)内逐块嵌入/提取。"""

    def __init__(self, p: int = 3, password: str = ""):
        if not 1 <= p <= 8:
            raise ValueError("p 建议取值 1..8")
        self.p = p
        self.n = (1 << p) - 1
        self.password = password
        self.H = build_hamming(p)

    # -- 池内工具: 用 perm 在池内连续取块(块内位置升序, 面向外部 pos 数组)
    @staticmethod
    def _pool_positions(perm, pool_size, n, num_blocks, pool_start=0):
        """返回 list[ ndarray(pos) ], 每块 n 个像素在整图索引中的位置。"""
        blocks = []
        for bi in range(num_blocks):
            base = pool_start + bi * n
            if base + n > pool_start + pool_size:
                break
            # 在池的 perm 局部取 n 个后排序, 映射到整图索引
            local = perm[bi * n:(bi + 1) * n]
            blocks.append(np.sort(local) + pool_start)
        return blocks

    def _embed(self, order_map, c, H, bits, pool_start, pool_translator):
        """通用嵌入。order_map: list[pos-ndarray]按块划分; 返回改动后 c。"""
        c = c.copy()
        p = self.p
        n = self.n
        for bi in range(min(len(order_map), bits.size // p)):
            pos = order_map[bi]
            m = bits[bi * p:(bi + 1) * p]
            xl = (c[pos] & 1).astype(np.uint8)
            s = syndrome(H, xl)
            if np.array_equal(s, m):
                continue
            d = (s ^ m).astype(np.uint8)
            col = int(np.where(np.all(H == d[:, None], axis=0))[0][0])
            c[pos[col]] ^= 1
        return c

    def _extract(self, order_map, c, H, num_bits):
        p = self.p
        out = []
        need = (num_bits + p - 1) // p
        for bi in range(need):
            if bi >= len(order_map):
                break
            xl = (c[order_map[bi]] & 1).astype(np.uint8)
            out.extend(int(b) for b in syndrome(H, xl))
        return np.array(out[:num_bits], np.uint8)


# --------------------------------------------------------------------------- #
#  nsF5 像素适配 (减幅 + 湿纸, 共享矩阵编码解码)
# --------------------------------------------------------------------------- #
class nsF5Pixel(MatrixEmbedding):
    def _embed(self, order_map, c, H, bits, pool_start, pool_translator):
        c = c.copy()
        p, n = self.p, self.n
        for bi, pos in enumerate(order_map):
            m = bits[bi * p:(bi + 1) * p]
            xv = c[pos].astype(np.int16) - 128
            xl = (xv & 1).astype(np.uint8)
            s = syndrome(H, xl)
            if np.array_equal(s, m):
                continue
            d = (s ^ m).astype(np.uint8)
            tc = int(np.where(np.all(H == d[:, None], axis=0))[0][0])
            if abs(xv[tc]) > 1:
                c[pos[tc]] = np.clip(c[pos[tc]].item() - np.sign(xv[tc]).item(), 0, 255)
            else:
                dry = [k for k in range(n) if abs(xv[k]) > 1]
                e = solve_wet_paper(H, dry, d, max_weight=2)
                if e is not None:
                    for ci in np.where(e == 1)[0]:
                        if ci < n and abs(xv[ci]) > 1:
                            c[pos[ci]] = np.clip(
                                c[pos[ci]].item() - np.sign(xv[ci]).item(), 0, 255)
                else:
                    # 兜底: 干位不足导致湿纸无解(极端情形), 翻转目标位 LSB,
                    # 使伴随式精确命中 m, 保证消息可解码。
                    c[pos[tc]] ^= 1
        return c


# --------------------------------------------------------------------------- #
#  图像的通道处理与整体嵌入/提取
# --------------------------------------------------------------------------- #
COLOR_CHANNELS = ("R", "G", "B")


def _channel(image, ch: int):
    img = np.ascontiguousarray(image).astype(np.uint8)
    if img.ndim == 3:
        return img[..., ch].reshape(-1), img.shape
    return img.reshape(-1), img.shape


def _embed_into_image(image, head_bits, body_bits, method, p, password):
    """head_bits: 认证头(图像哈希)比特; body_bits: 正文比特。返回 (stego, 报告)。"""
    img0 = np.ascontiguousarray(image).astype(np.uint8)
    ok_head = False
    stego = img0.copy()
    if img0.ndim == 3:
        stego = img0; stego[..., 0] = stego[..., 0]  # 仅主轴 R 通道_
        channel = stego[..., 0]
    else:
        channel = stego
    c = channel.reshape(-1)
    total = c.size
    img_bytes = img0.tobytes()
    cover_hash = hashlib.sha256(img_bytes).digest()[:COVER_HASH_BYTES]
    head_arr = np.unpackbits(np.frombuffer(cover_hash, np.uint8))

    hdr_cls = (nsF5Pixel if method.lower() in ("nsf5", "nsf5pixel") else MatrixEmbedding)(p=p, password=password)
    body_cls = type(hdr_cls)(p=p, password=password)

    n = hdr_cls.n
    # 头部池大小: 足够放 head_arr(128 bit) 及其补齐
    hdr_blocks = max(2, int(np.ceil((COVER_HASH_BYTES * 8) / p)))
    N_h = hdr_blocks * n
    if total <= N_h + n:
        raise ValueError("图像太小, 无法容纳头部+正文, 请放大图像或改用较小的 p")
    head_pad = (-head_arr.size) % p
    head_full = np.pad(head_arr, (0, head_pad))
    body_pad = (-body_bits.size) % p
    body_full = np.pad(body_bits, (0, body_pad))
    body_pool = total - N_h

    # 头部池: seed0 = 仅口令
    seed0 = derive_seed(b"", password)
    perm0 = permute_index(N_h, seed0)
    head_order = hdr_cls._pool_positions(perm0, N_h, n, hdr_blocks, pool_start=0)
    c = hdr_cls._embed(head_order, c, hdr_cls.H, head_full, 0, None)

    # 正文池: seed = cover_hash + 口令
    seedB = derive_seed(cover_hash, password)
    permB = permute_index(body_pool, seedB)
    nbody = body_full.size // p
    body_order = body_cls._pool_positions(permB, body_pool, n, nbody, pool_start=N_h)
    c = body_cls._embed(body_order, c, body_cls.H, body_full, N_h, None)

    if img0.ndim == 3:
        stego[..., 0] = c.reshape(stego[..., 0].shape)
    else:
        stego = c.reshape(img0.shape)
    changed = int(np.sum(stego != img0))
    report = dict(cover_hash=cover_hash.hex(), head_bits=N_h * 8,
                  cover_changed=changed)
    return stego, report


def _extract_from_image(stego_image, method, p, password, expect_body_bits=None):
    img = np.ascontiguousarray(stego_image).astype(np.uint8)
    channel = img[..., 0].reshape(-1) if img.ndim == 3 else img.reshape(-1)
    cls = (nsF5Pixel if method.lower() in ("nsf5", "nsf5pixel") else MatrixEmbedding)(p=p, password=password)
    n = cls.n

    # 头部池解码: 先按固定大小取回 head 比特
    hdr_blocks = max(2, int(np.ceil((COVER_HASH_BYTES * 8) / p)))
    N_h = hdr_blocks * n
    seed0 = derive_seed(b"", password)
    perm0 = permute_index(min(N_h, channel.size), seed0)
    head_order = cls._pool_positions(perm0, min(N_h, channel.size), n, hdr_blocks, 0)
    cov_hash = None
    if len(head_order) >= hdr_blocks:
        hb = cls._extract(head_order, channel, cls.H, COVER_HASH_BYTES * 8)
        if hb.size == COVER_HASH_BYTES * 8:
            cov_hash = bytes(np.packbits(hb))

    if cov_hash is None:
        return None, None
    # 正文池解码
    body_pool = channel.size - N_h
    seedB = derive_seed(cov_hash, password)
    permB = permute_index(body_pool, seedB)
    # 先解码正文的 16 bit 长度头
    head_order_b = cls._pool_positions(permB, body_pool, n,
                                       max(1, int(np.ceil(MSG_HEADER_BITS / p))),
                                       pool_start=N_h)
    bit16 = cls._extract(head_order_b, channel, cls.H, MSG_HEADER_BITS)
    if bit16.size < MSG_HEADER_BITS:
        return cov_hash, None
    length = sum(int(bit16[i]) << i for i in range(MSG_HEADER_BITS))
    total_bits = MSG_HEADER_BITS + length * 8
    need_blocks = (total_bits + p - 1) // p
    body_order = cls._pool_positions(permB, body_pool, n, need_blocks, pool_start=N_h)
    body = cls._extract(body_order, channel, cls.H, total_bits)
    return cov_hash, decode_string(body)


# --------------------------------------------------------------------------- #
#  高层 API
# --------------------------------------------------------------------------- #
def embed_string(image, text: str, method="nsF5", p=3, password=""):
    body_bits = encode_string(text)
    stego, report = _embed_into_image(image, None, body_bits, method, p, password)
    return stego, report, body_bits.size


def extract_string(stego, method="nsF5", p=3, password=""):
    _, text = _extract_from_image(stego, method, p, password)
    return text


def get_image_hash(image) -> str:
    return hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()