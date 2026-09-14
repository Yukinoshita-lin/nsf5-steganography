# -*- coding: utf-8 -*-
"""Per-chapter scene scripts + animations for the v2 teaching videos.

Every chapter follows the approved ch03-demo pattern: hook -> concept ->
hands-on -> evidence -> takeaway -> question/next-episode. Narration is
conversational with analogies, not the handbook read aloud.
Animation functions are registered into video_engine_v2.ANIMS.
"""
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from video_engine_v2 import (ACCENT, ACCENT_DARK, LINE, MUTED, TEAL, TEXT, W,
                             ease, fonts, mono_fonts, register_anim)

COVER = str(Path(__file__).resolve().parent.parent / "img" / "cover.png")

F_NUM = lambda s: fonts(s)[0]
F_B = lambda s: fonts(s)[1]


def S(kind, title, beats, elements=None, anim=None):
    return dict(kind=kind, title=title, beats=beats,
                elements=elements or [], anim=anim)


def B(say, show=0, **kw):
    d = dict(say=say, show=show)
    d.update(kw)
    return d


def title_scene(num, main_title, tagline, keywords, say1, say2, size=68):
    return S("title", None, [B(say1, 3), B(say2, 5)], [
        "__center__nsF5 隐写教学系列|200|30|muted|r",
        f"__pillc__第 {num} 章|360|42",
        f"__center__{main_title}|470|{size}",
        f"__center__{tagline}|610|38|muted|r",
        f"__center__{keywords}|700|30|accentd|r"])


def close_scene(question, next_line, say1, say2, finished=False):
    els = ["__pillc__想一想|300|40|teal", f"__center__{question}|460|46"]
    if finished:
        els += [f"__center__{next_line}|670|34|teal"]
        beats = [B(say1, 2), B(say2, 3)]
    else:
        els += ["__center__下一章预告|640|28|teal|r",
                f"__center__{next_line}|700|38|muted|r"]
        beats = [B(say1, 2), B(say2, 4)]
    return S("close", None, beats, els)


# =================================================================
# animations
# =================================================================
@register_anim("bits200")
def anim_bits200(img, beat, t, d):
    f60, _ = fonts(64)
    f34, _ = fonts(34)
    f24, _ = fonts(24)
    bits = [int(b) for b in f"{200:08b}"]
    weights = [128, 64, 32, 16, 8, 4, 2, 1]
    cx0, cy, cw = 430, 430, 118
    n_lit = (int(t * 8 / 0.8) + 1) if beat == 0 else 8
    d.text((300, 250), "200 = ?", font=f60, fill=TEXT)
    total = 0
    for i in range(8):
        x = cx0 + i * cw
        lit = i < n_lit and bits[i] == 1
        col = (255, 191, 0) if i == 7 and lit else (
            ACCENT if lit else (226, 230, 240))
        d.rounded_rectangle([x, cy, x + cw - 14, cy + 108], radius=14, fill=col)
        d.text((x + (cw - 14) / 2 - d.textlength(str(bits[i]), font=f60) / 2,
                cy + 18), str(bits[i]), font=f60,
                fill=((60, 45, 0) if i == 7 and lit else (255, 255, 255)))
        d.text((x + (cw - 14) / 2 - d.textlength(str(weights[i]), font=f24) / 2,
               cy + 130), f"×{weights[i]}", font=f24,
               fill=(ACCENT_DARK if lit else MUTED))
        if lit:
            total += weights[i]
    d.text((300, 640), f"= {total}" + ("　（还没加完…）" if beat == 0 and n_lit < 8 else ""),
           font=f60, fill=ACCENT_DARK)
    if beat == 1:
        pulse = (math.sin(t * 2 * math.pi * 1.4) + 1) / 2
        x = cx0 + 7 * cw
        ring = tuple(int(255 - (255 - c) * pulse) for c in (200, 120, 0))
        d.rounded_rectangle([x - 6, cy - 6, x + cw - 8, cy + 114], radius=16,
                            outline=ring, width=6)
        d.text((cx0, 790), "最右一位 = 最低有效位 LSB：改它，200 只变 201",
               font=f34, fill=(160, 90, 0))


_BITSTACK = {}


def _bitstack_data():
    if not _BITSTACK:
        arr = np.asarray(Image.open(COVER).convert("L"))
        planes = [(arr >> k) & 1 for k in range(8)]
        recons = []
        acc = np.zeros_like(arr, dtype=np.uint8)
        for k in range(7, -1, -1):
            acc = acc + (planes[k] << k).astype(np.uint8)
            recons.append(acc.copy())
        _BITSTACK["recons"] = recons
        _BITSTACK["planes"] = planes
        _BITSTACK["orig"] = arr
    return _BITSTACK


@register_anim("bitstack")
def anim_bitstack(img, beat, t, d):
    data = _bitstack_data()
    f28, _ = fonts(28)
    f24, _ = fonts(24)
    k = 1 + min(7, int(((beat + min(t, 0.999)) / 3) * 8))   # layers added
    recon = Image.fromarray(data["recons"][k - 1]).resize((430, 430),
                                                          Image.NEAREST)
    img.paste(recon, (250, 300))
    d.rectangle([250, 300, 680, 730], outline=LINE, width=2)
    d.text((250, 260), f"已叠加最高 {k} 层（bit7 … bit{8-k}）", font=f28, fill=TEXT)
    d.text((250, 748), f"当前和 = {k}/8 层" + ("　= 原图" if k == 8 else ""),
           font=f28, fill=(TEAL if k == 8 else MUTED))
    if k < 8:
        nxt = data["planes"][7 - k]
        pn = Image.fromarray((nxt * 255).astype(np.uint8)).resize((430, 430),
                                                                  Image.NEAREST)
        img.paste(pn, (840, 300))
        d.rectangle([840, 300, 1270, 730], outline=LINE, width=2)
        d.text((840, 260), f"下一层：bit{7-k} 位平面", font=f28, fill=TEXT)
        d.text((840, 748), "+ " + ("有结构（轮廓）" if 7 - k >= 4 else "接近噪声"),
               font=f28, fill=MUTED)
    else:
        orig = Image.fromarray(data["orig"]).resize((430, 430), Image.NEAREST)
        img.paste(orig, (840, 300))
        d.rectangle([840, 300, 1270, 730], outline=(TEAL,), width=3) if False \
            else d.rectangle([840, 300, 1270, 730], outline=TEAL, width=3)
        d.text((840, 260), "叠满 8 层 = 原图", font=f28, fill=TEAL)
        d.text((840, 748), "高位管轮廓，低位像噪声", font=f28, fill=ACCENT_DARK)
    # layer strip
    for i in range(8):
        x = 1430 + (i % 2) * 160
        y = 300 + (i // 2) * 118
        on = i < k
        pl = data["planes"][7 - i]
        th = Image.fromarray((pl * 255).astype(np.uint8)).resize((140, 104),
                                                                 Image.NEAREST)
        if on:
            img.paste(th, (x, y))
        d.rectangle([x, y, x + 140, y + 104],
                    outline=(ACCENT if on else LINE), width=3 if on else 2)
        d.text((x + 44, y + 108), f"bit{7-i}", font=f24,
               fill=(ACCENT_DARK if on else MUTED))


@register_anim("overflow")
def anim_overflow(img, beat, t, d):
    f40, _ = fonts(40)
    f56, _ = fonts(56)
    f30m, _ = mono_fonts(40)
    # 优化：动画整体上移，底部文字远离字幕安全区
    cx, cy, r = 960, 450, 218
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(180, 188, 205), width=5)
    # 修复：0 和 255 在圆环顶部重合，合并显示为 "0(255)"
    # 标签列表：(数值, 显示文本)，0 和 255 合并为一个标签
    labels = [(0, "0(255)"), (64, "64"), (128, "128"), (192, "192")]
    for v, lab in labels:
        ang = v / 256 * 2 * math.pi - math.pi / 2
        x, y = cx + (r + 34) * math.cos(ang), cy + (r + 34) * math.sin(ang)
        # 轻微描边增强可读性
        d.text((x - d.textlength(lab, font=f40) / 2 - 1, y - 24), lab, font=f40,
               fill=(246, 247, 251))
        d.text((x - d.textlength(lab, font=f40) / 2 + 1, y - 24), lab, font=f40,
               fill=(246, 247, 251))
        d.text((x - d.textlength(lab, font=f40) / 2, y - 24), lab, font=f40,
               fill=MUTED)
    def pos(val, rad):
        ang = (val % 256) / 256 * 2 * math.pi - math.pi / 2
        return cx + rad * math.cos(ang), cy + rad * math.sin(ang)
    if beat == 0:
        sweep = ease(t) * 100                    # 200 -> 300
        for p in range(1, 61):
            v0 = 200 + sweep * (p - 1) / 60
            v1 = 200 + sweep * p / 60
            if 255 < v1:
                col = (214, 51, 108) if v0 > 255 else (180, 60, 90)
            else:
                col = ACCENT
            d.line([pos(v0, r), pos(v1, r)], fill=col, width=12)
        x, y = pos(200 + sweep, r + 46)
        d.ellipse([x - 20, y - 20, x + 20, y + 20], fill=(255, 191, 0),
                  outline=(180, 120, 0), width=3)
        d.text((cx - 130, cy - 34), f"{200 + sweep:.0f}", font=f56,
               fill=((214, 51, 108) if 200 + sweep > 255 else TEXT))
        if sweep >= 99.5:
            # 优化：底部说明文字上移，远离字幕安全区
            d.text((cx - 330, 760), "np.uint8(200) + np.uint8(100) == 44",
                   font=f30m, fill=(214, 51, 108))
    else:
        d.text((cx - 330, 760), "np.uint8(200) + np.uint8(100) == 44",
               font=f30m, fill=(214, 51, 108))
        if t > 0.25:
            d.text((cx - 330, 812), "所以翻转 LSB 用  v ^ 1（异或：不进位、不回绕）",
                   font=f40, fill=TEAL)
    d.text((cx - 130, 136), "uint8：0 到 255 的“数字环”", font=f40, fill=TEXT)


@register_anim("syndrome")
def anim_syndrome(img, beat, t, d):
    f30, _ = fonts(30)
    f26, _ = fonts(26)
    f34, _ = fonts(34)
    f28m, _ = mono_fonts(30)
    xbits = [0, 1, 0, 1, 1, 0, 1]
    m = [1, 1, 0]
    s = [0, 0, 1]
    dcol = [1, 1, 1]
    H = [[(j >> (0)) & 1 for j in range(1, 8)],   # row0: LSB of col number
         [(j >> 1) & 1 for j in range(1, 8)],
         [(j >> 2) & 1 for j in range(1, 8)]]
    hx, hy, hcw, hch = 220, 330, 92, 74
    # H matrix
    d.text((hx, 250), "校验矩阵 H（列 = 二进制的 1…7）", font=f30, fill=TEXT)
    prog = t if beat == 0 else 1.0
    lit_cols = [i for i in range(7) if xbits[i] == 1]
    n_lit = int(len(lit_cols) * min(1.0, prog * 1.5)) if beat == 0 else len(lit_cols)
    for c in range(7):
        for r in range(3):
            x, y = hx + c * hcw, hy + r * hch
            v = H[r][c]
            on = c in lit_cols[:n_lit]
            d.rectangle([x, y, x + hcw - 12, y + hch - 10],
                        fill=((226, 231, 250) if on else (255, 255, 255)),
                        outline=((ACCENT if on else LINE)), width=2)
            d.text((x + (hcw - 12) / 2 - d.textlength(str(v), font=f30) / 2,
                    y + 16), str(v), font=f30,
                   fill=(ACCENT_DARK if on else MUTED))
        d.text((hx + c * hcw + 24, hy + 3 * hch + 6), str(c + 1), font=f26,
               fill=MUTED)
    # pixel cells
    px, py, pcw = 220, 700, 92
    d.text((hx, 640), "块内 7 个像素的最低位 x", font=f30, fill=TEXT)
    for c in range(7):
        x = px + c * pcw
        flip = beat == 1 and t > 0.45 and c == 6
        val = (xbits[c] - 1 if flip and c == 6 else xbits[c])
        fresh = flip and t < 0.62 and c == 6
        d.rounded_rectangle([x, py, x + pcw - 12, py + 78], radius=12,
                            fill=((255, 246, 220) if fresh else (255, 255, 255)),
                            outline=((255, 160, 0) if flip and c == 6 else LINE),
                            width=4 if (flip and c == 6) else 2)
        d.text((x + (pcw - 12) / 2 - d.textlength(str(val), font=f34) / 2,
                py + 18), str(val), font=f34,
                fill=((200, 90, 0) if flip and c == 6 else TEXT))
    # registers
    rx, ry = 1380, 330
    def reg(name, vec, y, col, note=""):
        d.text((rx, y), name, font=f30, fill=TEXT)
        # 修复：增加标签与方块的间距，避免长标签（如"差值 d = s 异或 m"）与方块重叠
        name_w = d.textlength(name, font=f30)
        bx0 = rx + max(180, name_w + 36)
        for i, b in enumerate(vec):
            bx = bx0 + i * 60
            d.rounded_rectangle([bx, y - 8, bx + 48, y + 44], radius=10,
                                fill=col if b else (226, 230, 240))
            d.text((bx + 15, y - 2), str(b), font=f30,
                   fill=((255, 255, 255) if b else (120, 128, 148)))
        if note:
            d.text((rx, y + 56), note, font=f26, fill=MUTED)
    if beat == 0:
        reg("伴随式 s = H·x", s, ry, ACCENT,
            note="x 中取 1 的列异或起来" if t < 0.9 else "s = [0,0,1]")
    else:
        reg("当前 s", s, ry, ACCENT)
        reg("消息 m", m, ry + 130, TEAL)
        prog2 = min(1.0, t * 1.6)
        dvv = [int((s[i] ^ m[i]) * min(1.0, prog2 * 2)) for i in range(3)]
        reg("差值 d = s 异或 m", dvv, ry + 260, (214, 51, 108))
        if t > 0.3:
            # scan + hit column 7
            scan = int(min(1.0, (t - 0.3) / 0.35) * 7)
            for c in range(min(7, scan)):
                hit = (c == 6 and t > 0.55)
                x = hx + c * hcw
                d.rectangle([x - 3, hy - 3, x + hcw - 9, hy + 3 * hch - 7],
                            outline=((255, 160, 0) if hit else (188, 196, 214)),
                            width=5 if hit else 2)
            if t > 0.55:
                d.text((rx, ry + 390), "d = 第 7 列 → 翻第 7 位",
                       font=f30, fill=(200, 90, 0))
            if t > 0.75:
                d.text((rx, ry + 460), "验算 s' = m，命中！",
                       font=f30, fill=TEAL)


@register_anim("wetdry")
def anim_wetdry(img, beat, t, d):
    f30, _ = fonts(30)
    f26, _ = fonts(26)
    f34, _ = fonts(34)
    vals = [127, 130, 128, 134, 131, 129, 133]
    wet = {0, 2, 5}
    x0, y0, cw, ch = 300, 400, 150, 110
    if beat == 0:
        n_mark = int(3 * min(1.0, t * 1.4))
        marked = set(list(wet)[:n_mark])
        for i, v in enumerate(vals):
            x = x0 + i * cw
            is_wet = i in marked
            d.rounded_rectangle([x, y0, x + cw - 16, y0 + ch], radius=12,
                                fill=((250, 224, 228) if is_wet else
                                      (255, 255, 255)),
                                outline=((214, 51, 108) if is_wet else LINE),
                                width=3 if is_wet else 2)
            d.text((x + (cw - 16) / 2 - d.textlength(str(v), font=f34) / 2,
                    y0 + 16), str(v), font=f34,
                   fill=((214, 51, 108) if is_wet else TEXT))
            d.text((x + (cw - 16) / 2 - d.textlength(str((i + 1)), font=f26) / 2,
                    y0 + ch + 10), str(i + 1), font=f26, fill=MUTED)
        d.text((x0, 300), "一块 7 个像素（xv = 像素 − 128）", font=f30, fill=TEXT)
        if n_mark >= 1:
            d.text((x0, 600), "湿点：127 / 128 / 129 —— |xv| ≤ 1，减幅会撞零",
                   font=f30, fill=(214, 51, 108))
        if n_mark >= 2:
            d.text((x0, 660), "规则：写之前，先把湿点排除出可改集合", font=f30,
                   fill=MUTED)
    else:
        for i, v in enumerate(vals):
            x = x0 + i * cw
            is_wet = i in wet
            hit = i in (3, 6) and t > 0.55
            dec = hit and t > 0.75
            v2 = v - 1 if dec and i in (3, 6) else v
            d.rounded_rectangle([x, y0, x + cw - 16, y0 + ch], radius=12,
                                fill=((250, 224, 228) if is_wet else
                                      ((255, 246, 220) if hit else
                                       (255, 255, 255))),
                                outline=((214, 51, 108) if is_wet else
                                         ((255, 160, 0) if hit and t < 0.75 else
                                          (TEAL if hit else LINE))),
                                width=3 if (is_wet or hit) else 2)
            d.text((x + (cw - 16) / 2 - d.textlength(str(v2), font=f34) / 2,
                    y0 + 16), str(v2), font=f34,
                   fill=((214, 51, 108) if is_wet else
                         ((200, 90, 0) if dec else TEXT)))
            if dec:
                d.text((x + (cw - 16) / 2 - 10, y0 - 40), "↓", font=f30,
                       fill=(200, 90, 0))
            d.text((x + (cw - 16) / 2 - d.textlength(str(i + 1), font=f26) / 2,
                    y0 + ch + 10), str(i + 1), font=f26, fill=MUTED)
        d.text((x0, 300), "目标：伴随式变化 d = (1,1,0)，只在干点上解", font=f30,
               fill=TEXT)
        if t > 0.15:
            d.text((x0, 600), "单列命中？干列 2/4/5/7 都不等于 d —— 无", font=f30,
                   fill=MUTED)
        if t > 0.45:
            d.text((x0, 660), "双列命中：第 4 列 异或 第 7 列 = d —— 命中！",
                   font=f34, fill=TEAL)
        if t > 0.75:
            d.text((x0, 730), "只改 2 个干点（各减幅 1），湿点一动不动",
                   font=f34, fill=ACCENT_DARK)


def _perm(seed, n):
    rng = random.Random(seed)
    return rng.sample(range(n), n)


@register_anim("permute")
def anim_permute(img, beat, t, d):
    f30, _ = fonts(30)
    f26, _ = fonts(26)
    if beat == 0:
        cols, rows, cell, gp = 16, 10, 44, 3
        gw = cols * (cell + gp) - gp
        x0, y0 = (W - gw) / 2, 300
        for i in range(cols * rows):
            r, c = divmod(i, cols)
            x, y = x0 + c * (cell + gp), y0 + r * (cell + gp)
            d.rectangle([x, y, x + cell, y + cell], fill=(255, 255, 255),
                        outline=(224, 228, 238))
        n = int(min(1.0, t * 1.25) * cols * rows)
        pts = []
        for k in range(n):
            r, c = divmod(k, cols)
            pts.append((x0 + c * (cell + gp) + cell / 2,
                        y0 + r * (cell + gp) + cell / 2))
        if len(pts) > 1:
            d.line(pts, fill=(120, 128, 148), width=4)
        d.text((x0, 240), "不置乱的访问顺序：逐行扫描 —— 谁都猜得到（危险）",
               font=f30, fill=(214, 51, 108))
        return
    cols, rows, cell, gp = 16, 10, 42, 3
    gw = cols * (cell + gp) - gp
    panels = [(240, "口令 A", ACCENT, 11), (1080, "口令 B", TEAL, 23)]
    n = int(min(1.0, t * 1.2) * cols * rows)
    for x0, label, col, seed in panels:
        perm = _perm(seed, cols * rows)
        for i in range(cols * rows):
            r, c = divmod(i, cols)
            x, y = x0 + c * (cell + gp), 300 + r * (cell + gp)
            d.rectangle([x, y, x + cell, y + cell], fill=(255, 255, 255),
                        outline=(224, 228, 238))
        pts = []
        for k in range(n):
            idx = perm[k]
            r, c = divmod(idx, cols)
            pts.append((x0 + c * (cell + gp) + cell / 2,
                        300 + r * (cell + gp) + cell / 2))
        if len(pts) > 1:
            d.line(pts, fill=col, width=4)
        if pts:
            x, y = pts[-1]
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(255, 191, 0))
        d.text((x0 + gw / 2 - d.textlength(label, font=f30) / 2, 240), label,
               font=f30, fill=col)
    d.text((240, 810), "同一口令 → 恒同一条路径（自同步）；换口令 → 整张地图重画",
           font=f30, fill=TEXT)


@register_anim("gradient")
def anim_gradient(img, beat, t, d):
    f30, _ = fonts(30)
    f26, _ = fonts(26)
    # 优化：图表区上移，底部文字远离字幕安全区
    fx0, fy0, fx1, fy1 = 260, 260, 1700, 770
    f = lambda w: 0.32 * (w - 6) ** 2 + 30
    wmin, wmax, ymin, ymax = 0.0, 12.0, 25.0, 60.0
    def P(wv, fv):
        x = fx0 + (wv - wmin) / (wmax - wmin) * (fx1 - fx0)
        y = fy1 - (fv - ymin) / (ymax - ymin) * (fy1 - fy0)
        return x, y
    d.line([fx0, fy1, fx1, fy1], fill=(180, 188, 205), width=3)
    d.line([fx0, fy0, fx0, fy1], fill=(180, 188, 205), width=3)
    pts = [P(wmin + i * (wmax - wmin) / 200, f(wmin + i * (wmax - wmin) / 200))
           for i in range(201)]
    d.line(pts, fill=ACCENT, width=6)
    ws = [1.0]
    for _ in range(16):
        wv = ws[-1]
        ws.append(wv - 0.5 * (0.64 * (wv - 6)))
    total_steps = len(ws) - 1
    n = 6 if beat == 0 else min(total_steps, 7 + int(t * (total_steps - 7) / 0.85))
    n = max(1, min(n, total_steps))
    for i in range(1, n + 1):
        p0, p1 = P(ws[i - 1], f(ws[i - 1])), P(ws[i], f(ws[i]))
        mid = ((p0[0] + p1[0]) / 2, min(p0[1], p1[1]) - 26)
        d.line([p0, mid, p1], fill=(255, 160, 0), width=5)
    bx, by = P(ws[n], f(ws[n]))
    d.ellipse([bx - 20, by - 34, bx + 20, by + 6], fill=(255, 191, 0),
              outline=(180, 120, 0), width=3)
    d.text((fx0, 198), "损失 L(w) —— 猜错要扣的分", font=f30, fill=TEXT)
    wx, wy = P(6, f(6))
    if beat == 1 and t > 0.4:
        d.line([wx - 14, wy - 6, wx + 14, wy - 6], fill=TEAL, width=5)
        d.text((wx - 130, wy - 70), "谷底：损失最小", font=f30, fill=TEAL)
        d.text((fx0, 800), "三句话：损失=错得多离谱；训练=让损失最小；"
                           "梯度下降=顺着下坡一小步一小步走", font=f26, fill=MUTED)
    elif beat == 0:
        d.text((fx0, 800), "每一步都朝“下降最快的方向”挪一点 —— 这就是梯度下降",
               font=f26, fill=MUTED)


@register_anim("roc")
def anim_roc(img, beat, t, d):
    f30, _ = fonts(30)
    f26, _ = fonts(26)
    fx0, fy0, fx1, fy1 = 330, 260, 1000, 760
    k = 2.33
    tpr = lambda x: 1 - (1 - x) ** k
    def P(x):
        return (fx0 + x * (fx1 - fx0), fy1 - tpr(x) * (fy1 - fy0))
    d.line([fx0, fy1, fx1, fy1], fill=(180, 188, 205), width=3)
    d.line([fx0, fy0, fx0, fy1], fill=(180, 188, 205), width=3)
    d.line([P(0), P(1)], fill=(188, 196, 214), width=3)
    if beat == 0:
        n = int(min(1.0, t * 1.3) * 120)
        pts = [P(i / 120) for i in range(n + 1)]
        if len(pts) > 1:
            poly = pts + [(pts[-1][0], fy1), (fx0, fy1)]
            d.polygon(poly, fill=(252, 228, 233))
            d.line(pts, fill=(214, 51, 108), width=6)
        d.text((fx0 + 220, 460), "AUC ≈ 0.7（与阈值无关）", font=f30,
               fill=(214, 51, 108))
        d.text((fx0, 800), "横轴：误报率　纵轴：检出率　虚线：瞎猜（AUC=0.5）",
               font=f26, fill=MUTED)
    else:
        pts = [P(i / 120) for i in range(121)]
        poly = pts + [(pts[-1][0], fy1), (fx0, fy1)]
        d.polygon(poly, fill=(252, 228, 233))
        d.line(pts, fill=(214, 51, 108), width=6)
        x = 0.04 + ease(t) * 0.92
        px, py = P(x)
        d.ellipse([px - 16, py - 16, px + 16, py + 16], fill=(255, 191, 0),
                  outline=(150, 100, 0), width=3)
        rx = 1180
        d.text((rx, 290), f"阈值滑到 {1 - x:.2f}", font=f30, fill=TEXT)
        for i, (lab, val, col) in enumerate(
                (("检出率 TPR", tpr(x), ACCENT), ("误报率 FPR", x, (214, 51, 108)))):
            y = 380 + i * 140
            d.text((rx, y), f"{lab}：{val * 100:.0f}%", font=f30, fill=col)
            d.rectangle([rx, y + 56, rx + 560 * val, y + 92], fill=col)
        d.text((rx, 680), "阈值高（左端）：误报少，漏检多", font=f26, fill=MUTED)
        d.text((rx, 720), "阈值低（右端）：检出多，误报也多", font=f26, fill=MUTED)
        d.text((fx0, 800), "阈值 = 操作点：在“冤枉”与“放过”之间做取舍", font=f26,
               fill=MUTED)


@register_anim("speedup")
def anim_speedup(img, beat, t, d):
    f30, _ = fonts(30)
    f34, _ = fonts(34)
    f26, _ = fonts(26)
    x0, x1 = 480, 1560
    lmin, lmax = math.log10(0.05), math.log10(30)
    def X(sec):
        return x0 + (math.log10(max(sec, 0.05)) - lmin) / (lmax - lmin) * (x1 - x0)
    rows = [("确定性置换 · Python", 12.3, (120, 128, 148)),
            ("确定性置换 · C++", 0.223, ACCENT)]
    d.text((x0, 240), "4096² 图像确定性置换耗时（对数刻度）", font=f34, fill=TEXT)
    for lo, lab in ((0.1, "0.1s"), (1, "1s"), (10, "10s")):
        x = X(lo)
        d.line([x, 330, x, 700], fill=(224, 228, 238), width=2)
        d.text((x - 20, 706), lab, font=f26, fill=MUTED)
    grow = ease(min(1.0, t * 1.5))
    for i, (lab, sec, col) in enumerate(rows):
        y = 360 + i * 150
        full = X(sec) - x0
        d.rectangle([x0, y, x0 + full * (grow if i == 0 else min(1.0, t * 6)),
                     y + 74], fill=col)
        d.text((x0, y - 44), lab, font=f30, fill=TEXT)
        shown = sec * grow if i == 0 else min(sec, sec * t * 6)
        d.text((x0 + full + 24 if i == 0 else x0 + X(sec) - x0 + 24, y + 14),
               f"{shown:.2f} s" if i else f"{shown:.1f} s", font=f30, fill=col)
    if beat == 0 and t > 0.8 or beat == 1:
        d.text((640, 580), "≈ 263 ×", font=F_B(72), fill=(214, 51, 108))
    if beat == 1:
        # 优化：底部说明文字上移，远离字幕安全区
        d.text((x0, 760), "前提：两条路径输出像素级一致（cppembed.selfcheck）",
               font=f30, fill=TEAL if t > 0.3 else MUTED)
        d.text((x0, 810), "GPU 批量特征：约 410 张/秒，与 CPU 逐位一致", font=f30,
               fill=MUTED)


PIPE = ["原始数据", "预留测试集", "5 折 GroupKFold", "OOF 选模型",
        "校准集挑阈值", "全量重训", "测试集只评一次"]


@register_anim("pipeline")
def anim_pipeline(img, beat, t, d):
    f30, _ = fonts(30)
    bw, bh, gp = 370, 120, 56
    x0, y0 = 150, 330
    lit = (int(min(1.0, t * 1.15) * 7) if beat == 0 else 7)
    for i, name in enumerate(PIPE):
        r, c = divmod(i, 4)
        x, y = x0 + c * (bw + gp), y0 + r * (bh + 110)
        on = i < lit
        cur = i == lit - 1 and beat == 0
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=16,
                            fill=((ACCENT if i < 6 else TEAL) if on and i < 6
                                  else (TEAL if on else (255, 255, 255))),
                            outline=(LINE if not on else
                                     ((255, 160, 0) if cur else
                                      ((ACCENT if i < 6 else TEAL)))), width=3)
        d.text((x + bw / 2 - d.textlength(name, font=f30) / 2, y + 40), name,
               font=f30, fill=((255, 255, 255) if on else TEXT))
        if c < 3 and i < 6:
            d.line([x + bw + 8, y + bh / 2, x + bw + gp - 8, y + bh / 2],
                   fill=(188, 196, 214), width=4)
    if beat == 1 and t > 0.35:
        d.text((x0, 726), "红线一：测试集只碰一次", font=f30, fill=(214, 51, 108))
        d.text((x0, 778), "红线二：同一照片的变体绝不拆开（GroupKFold）", font=f30,
               fill=(214, 51, 108))
        d.text((x0, 830), "红线三：“改了 A 变好了”不足以服人，要按此流水线证明",
               font=f30, fill=(214, 51, 108))


CHAIN = ["载体 cover", "嵌入算法", "含密图 stego", "统计指纹", "ML 模型", "判读 / GUI"]


@register_anim("chain")
def anim_chain(img, beat, t, d):
    f30, _ = fonts(30)
    f26, _ = fonts(26)
    bw, bh = 262, 110
    x0, y = 108, 380
    lit = int(min(1.0, t * 1.2) * 6) if beat == 0 else 6
    for i, name in enumerate(CHAIN):
        x = x0 + i * (bw + 26)
        on = i < lit
        col = ACCENT if on else (255, 255, 255)
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=16, fill=col,
                            outline=(LINE if not on else ACCENT_DARK), width=3)
        d.text((x + bw / 2 - d.textlength(name, font=f30) / 2, y + 36), name,
               font=f30, fill=((255, 255, 255) if on else TEXT))
        if i < 5:
            d.line([x + bw + 3, y + bh / 2, x + bw + 23, y + bh / 2],
                   fill=((ACCENT_DARK if on else (188, 196, 214))), width=4)
    if beat == 1 and t > 0.2:
        tags = ["HUGO / UNIWARD 内容自适应", "深度隐写与隐写分析",
                "JPEG 域：yccstego", "可逆 / 鲁棒水印"]
        d.text((x0, 620), "下一步的地图：", font=f30, fill=TEXT)
        for i, tag in enumerate(tags):
            r, c = divmod(i, 2)
            x = x0 + c * 780
            yy = 690 + r * 90
            d.rounded_rectangle([x, yy, x + 730, yy + 64], radius=32,
                                outline=TEAL, width=3)
            d.text((x + 40, yy + 14), tag, font=f30, fill=TEAL)


# ---- ch03: pixel parking lot + chi-square pair flattening (from the demo)

BITS_HI = [int(b) for b in f"{0x48:08b}{0x69:08b}"]      # "Hi"


def park_setup():
    """Deterministic 64-pixel demo: exactly 8 flips for the 16 bits of "Hi",
    with two showcase cells (128 -> 129 and 135 -> 134)."""
    rng = random.Random(7)
    vals = [rng.randrange(40, 216) for _ in range(64)]
    bits = BITS_HI
    flip_slots = set(rng.sample(range(16), 8))
    remaining = list(range(64))
    rng.shuffle(remaining)
    order = []
    for k in range(16):
        want_flip = k in flip_slots
        pick = next((i for i in remaining
                     if (vals[i] & 1 != bits[k]) == want_flip), None)
        if pick is None:
            pick = remaining[0]
        remaining.remove(pick)
        order.append(pick)
    for k in range(16):
        if k in flip_slots and vals[order[k]] != 128 and bits[k] == 1:
            vals[order[k]] = 128
            break
    for k in range(16):
        if k in flip_slots and bits[k] == 0 and vals[order[k]] % 2 == 1:
            vals[order[k]] = 135
            break
    return vals, order


PARK_VALS, PARK_ORDER = park_setup()


@register_anim("park")
def anim_park(img, beat, t, d):
    vals, order = PARK_VALS, PARK_ORDER
    cell = 92, 78
    gap = 10
    cols = 16
    gw = cols * (cell[0] + gap) - gap
    x0 = (W - gw) // 2
    y0 = 320
    f_num, _ = fonts(30)
    f_small, _ = fonts(22)
    _, f_bit = fonts(34)

    if beat == 0:
        pulse = (math.sin(t * 2 * math.pi * 1.1) + 1) / 2
        ring = tuple(int(a + (b - a) * pulse) for a, b in
                     zip((205, 211, 228), ACCENT))
        for i in range(64):
            r, c = divmod(i, cols)
            x, y = x0 + c * (cell[0] + gap), y0 + r * (cell[0] + gap)
            d.rectangle([x, y, x + cell[0], y + cell[1]], fill=(255, 255, 255),
                        outline=(210, 216, 232), width=2)
            v = f"{vals[i]}"
            d.text((x + cell[0] / 2 - d.textlength(v, font=f_num) / 2, y + 12),
                   v, font=f_num, fill=TEXT)
            lsb = f"{vals[i] & 1}"
            d.text((x + cell[0] / 2 - d.textlength(lsb, font=f_small) / 2,
                    y + cell[1] - 30), "可停 " + lsb, font=f_small, fill=MUTED)
            if i % 8 == 3:
                d.rectangle([x, y, x + cell[0], y + cell[1]], outline=ring, width=4)
        d.text((x0, 250), "64 个像素 = 64 个“比特车位”（数字右下角是它的最低位）",
               font=f_small, fill=MUTED)
    else:
        n = len(BITS_HI)
        revealed = min(n, int(t * n / 0.82) + 1)
        flips, states = [], {}
        for k in range(revealed):
            i = order[k]
            want = BITS_HI[k]
            a = vals[i]
            if a & 1 != want:
                b = (a + 1) if a & 1 == 0 else (a - 1)
                flips.append((k, i, a, b))
                states[i] = (b, (revealed - 1 - k) <= 1)
        _, fb30 = fonts(34)
        d.text((x0, 242), "消息 “Hi” 的比特流：", font=f_small, fill=MUTED)
        bx = x0 + 250
        for k in range(n):
            x = bx + k * 52
            cur = k == revealed - 1
            done = k < revealed
            col = ((255, 191, 0) if cur else
                   ((61, 90, 241) if done else (226, 230, 240)))
            d.rounded_rectangle([x, 236, x + 42, 276], radius=8, fill=col)
            d.text((x + 21 - d.textlength(str(BITS_HI[k]), font=fb30) / 2, 240),
                   str(BITS_HI[k]), font=fb30,
                   fill=((40, 40, 40) if cur else (255, 255, 255)))
        for i in range(64):
            r, c = divmod(i, cols)
            x, y = x0 + c * (cell[0] + gap), y0 + r * (cell[0] + gap)
            cur = i == order[min(revealed, n) - 1]
            changed = i in states
            fresh = changed and states[i][1]
            d.rectangle([x, y, x + cell[0], y + cell[1]],
                        fill=((255, 246, 220) if fresh else (255, 255, 255)),
                        outline=((255, 160, 0) if cur else
                                 ((61, 90, 241) if changed else (210, 216, 232))),
                        width=4 if (cur or changed) else 2)
            v = str(states[i][0]) if changed else str(vals[i])
            col = ((200, 90, 0) if changed else TEXT)
            d.text((x + cell[0] / 2 - d.textlength(v, font=f_num) / 2, y + 12),
                   v, font=f_num, fill=col)
            lsb = f"{int(v) & 1}"
            d.text((x + cell[0] / 2 - d.textlength(lsb, font=f_small) / 2,
                    y + cell[1] - 30), lsb, font=f_small, fill=MUTED)
        d.text((x0, y0 + 4 * (cell[1] + gap) + 14),
               f"已写入 {revealed}/{n} 位 · 改动 {len(flips)} 处 · 每处只 ±1",
               font=fonts(30)[0], fill=ACCENT_DARK)


PAIRS = [(64, 41), (39, 58), (77, 45), (52, 66), (44, 39), (70, 47)]


@register_anim("pairs")
def anim_pairs(img, beat, t, d):
    x0, y0 = 260, 320
    bw, bgap, pgap = 88, 12, 88
    maxh = 420
    f_small, _ = fonts(26)
    f_mid, _ = fonts(30)
    top = max(max(PAIRS)) + 8

    def barh(v, grow):
        return int(maxh * v / top * grow)

    grow = ease(min(1.0, t * 1.6)) if beat == 0 else 1.0
    d.line([x0 - 30, y0 + maxh, x0 + 6 * (2 * bw + bgap + pgap), y0 + maxh],
           fill=(180, 188, 205), width=3)
    done_all = True
    for p, (he, ho) in enumerate(PAIRS):
        px = x0 + p * (2 * bw + bgap + pgap)
        if beat == 0:
            h1, h2 = barh(he, grow), barh(ho, grow)
            c1 = c2 = ACCENT
        else:
            m = (he + ho) / 2
            conv = ease(min(1.0, max(0.0, (t - 0.08) / 0.72)))
            h1 = barh(he + (m - he) * conv, 1)
            h2 = barh(ho + (m - ho) * conv, 1)
            flat = abs(he - ho) * (1 - conv) <= 1.5
            c1 = c2 = (214, 51, 108) if flat else ACCENT
            if not flat:
                done_all = False
        d.rectangle([px, y0 + maxh - h1, px + bw, y0 + maxh], fill=c1)
        d.rectangle([px + bw + bgap, y0 + maxh - h2, px + 2 * bw + bgap,
                     y0 + maxh], fill=c2)
        d.text((px + bw + bgap / 2 - d.textlength(f"{2*p}", font=f_small) / 2,
                y0 + maxh + 12), f"{2*p}", font=f_small, fill=MUTED)
        d.text((px + bw + bgap + bw / 2 - d.textlength(f"{2*p+1}",
               font=f_small) / 2, y0 + maxh + 12), f"{2*p+1}", font=f_small,
               fill=MUTED)
        d.line([px, y0 + maxh + 48, px + 2 * bw + bgap, y0 + maxh + 48],
               fill=(210, 216, 232), width=2)
        if beat >= 1:
            conv = ease(min(1.0, max(0.0, (t - 0.08) / 0.72)))
            if conv < 1:
                up = he < ho
                ax = px + bw / 2 if up else px + bw + bgap + bw / 2
                ay = y0 + maxh - barh(he if up else ho, 1) - 18
                col = (214, 51, 108)
                if up:
                    d.polygon([ax, ay, ax - 10, ay + 14, ax + 10, ay + 14],
                              fill=col)
                else:
                    d.polygon([ax, ay + 14, ax - 10, ay, ax + 10, ay],
                              fill=col)
    d.text((x0, 250), "相邻灰度对 (2i, 2i+1) 的出现次数：", font=f_mid, fill=TEXT)
    if beat == 1 and done_all:
        d.text((x0 + 620, 246), "→ 全部被拉平！", font=f_mid,
               fill=(214, 51, 108))
    if beat == 2:
        d.text((x0, y0 + maxh + 86),
               "均匀 = 可疑：p 值越高越可疑；天然噪声照片会骗过卡方，需“本底随机度”修正",
               font=f_small, fill=MUTED)


# =================================================================
# decks
# =================================================================
DECKS = [
dict(num=1, title="数字图像与二进制", weeks="第 1 周", scenes=[
    title_scene(1, "数字图像与二进制", "一切魔法的地基：图像 = 一堆数字",
                "像素 · 二进制 · LSB · 位平面 · 冗余",
                "你好，欢迎来到 nsF5 隐写课。第一章，我们不谈算法，先攻一个直觉：一张图片，本质上就是一堆数字。这个直觉，是后面一切魔法的地基。",
                "这一章你会看到：像素是什么、二进制是什么、为什么图片里天然“有写作空间”。我们开始。", size=76),
    S("bullets", "一张图像，就是一堆数字", [
        B("先看灰度图。把照片放大到像素级，你会看到一张巨大的表格，每个格子一个 0 到 255 的整数：0 是纯黑，255 是纯白，中间是深浅不同的灰。计算机保存的，就是这张表格。", 1),
        B("彩色图呢？就是三张这样的表格叠在一起——红、绿、蓝各一张。你看到的橙色，其实是某一格写着：红 255、绿 128、蓝 0。", 2),
        B("所以在代码里，灰度图是二维数组，彩色图是三维数组。项目的 image_io 模块管两件事：把图读成数组，把数组存回图。以后所有算法，都在这张“数字表格”上操作。", 3),
    ], ["灰度图：0–255 的整数表格（0 黑、255 白）",
        "彩色图：R / G / B 三张表叠加，形状 (H, W, 3)",
        "代码里：灰度 = 二维数组，彩色 = 三维数组",
        "~image_io：把图读成数组、把数组存回图"]),
    S("anim", "二进制：200 是怎么写出来的", [
        B("计算机只认识 0 和 1。一个 0 或 1 叫一位，八个位组成一个字节，能表达 2 的 8 次方共 256 种组合。十进制的 200，就是 8 个权重里 128、64、8 三个亮起来的结果。", 0, anim_beat=0),
        B("最右边这一位，叫最低有效位，LSB。它在数值上最小，改动它，200 只会变成 201——视觉上几乎零差别。整个隐写世界，就建立在这个“最不重要的位”上。", 0, anim_beat=1),
    ], anim="bits200"),
    S("anim", "位平面：把一张图拆成 8 层", [
        B("把每个像素的二进制按“第几位”重新排列，一张图就能拆成 8 层位平面。我们拿项目里真实的封面图做实验：从最高位开始，一层一层往上叠，看画面怎么一步步变清晰。", 0, anim_beat=0),
        B("只叠最高位，只能看到模糊的轮廓；每叠一层，清晰一步；叠满 8 层，和原图一分不差。反过来注意最底层——它几乎全是噪声。", 0, anim_beat=1),
        B("这就得到本章最重要的结论：高位管轮廓，低位像噪声。修改高位，一眼穿帮；修改低位，眼睛看不见，但统计上留痕。隐写藏低位，检测测低位，根子都在这张图里。", 0, anim_beat=2),
    ], anim="bitstack"),
    S("bullets", "行话：cover 与 stego", [
        B("最后认两个行话。没藏东西的原图叫 cover，载体；藏进秘密之后叫 stego，含密图。项目里 img 目录的 cover.png 是演示载体，output 里的 stego 文件就是成品。", 2),
        B("顺便说这张封面图的来历：它是 run_e2e 脚本用 numpy 生成的——渐变背景加一点噪声。“一张自然图像怎么从数字长出来”，这段代码就是最好的注脚。", 3),
    ], ["cover = 原始载体（img/cover.png）",
        "stego = 藏好秘密的含密图（output/stego_*.png）",
        "~封面图来历：linspace 渐变 + 小噪声，纯 numpy 生成"]),
    close_scene("纯黑图、纯随机噪声图，哪个更适合做 LSB 隐写的载体？",
                "第 2 章 · 准备工具：Python、NumPy 与图像读写",
                "留一道思考题：一张纯黑的图，和一张纯随机噪声的图，哪个更适合做 LSB 隐写的载体？把答案写下来，第三章我们回来对答案。",
                "下一章，我们把 Python 环境搭好，让代码先跑起来。"),
]),

dict(num=2, title="准备工具：Python、NumPy 与图像读写", weeks="第 2 周", scenes=[
    title_scene(2, "准备工具：Python、NumPy 与图像读写",
                "装好环境，跑通第一个端到端脚本",
                "环境 · 数组思维 · uint8 的坑 · 统一接口",
                "欢迎回到 nsF5 隐写课。第二章是动手章：装好环境，跑通第一个端到端脚本，学会用 NumPy 的方式思考图像。学完这章，你做的每个实验都能立刻在项目里验证。",
                "这一章不啃理论，全是能敲的代码。我们开始。"),
    S("bullets", "安装与第一次自检", [
        B("项目依赖非常轻：核心就 NumPy 加 Pillow，做机器学习再加 scikit-learn。装包有个小窍门：用你运行脚本的那个解释器去装，命令是 python 横杠 m pip install，能避开九成的“装了却找不到”。", 2),
        B("装完先别急着看算法，跑两个自测脚本，再跑端到端的 run_e2e。它会完整演示一遍：生成封面、嵌入消息、解码比对、盲分析、画图。把输出里“嵌入多少比特、改动多少像素、分析概率多少”三组数字抄下来——第三章要考。", 4),
    ], ["核心依赖：NumPy + Pillow（ML 再加 scikit-learn、joblib）",
        "~装包窍门：python -m pip install（用对解释器）",
        "自检三连：test_core / test_steg / run_e2e",
        "~GUI 打不开 → 换带 tkinter 的解释器"]),
    S("anim", "新手第一坑：uint8 溢出回绕", [
        B("用 NumPy 思考图像，四个词就够：形状、类型、切片、向量化。但先带你看一个必踩的坑。像素的类型是 uint8，只能装 0 到 255。现在做加法：200 加 100，等于多少？", 0, anim_beat=0),
        B("不是 300，是 44！8 位装不下 300，超出的部分从 0 绕了回来，这叫溢出回绕。所以项目改最低位从来不用加减，而是用异或 1：翻转，不进位、不回绕。亲手敲一遍，这个 44 会帮你记一辈子。", 0, anim_beat=1),
    ], anim="overflow"),
    S("bullets", "图像读写：全项目的统一接口", [
        B("再看项目的图像读写接口，就两个函数。load_as_gray：任何图进来，先强制转灰度，再变成 uint8 数组；save_image：保存前先 ascontiguousarray，把内存铺连续。", 2),
        B("为什么多此一举？因为切片、转置产生的“视图”内存不连续，很多底层库不认。这两个函数是全项目的统一入口：嵌入、分析、机器学习，拿到的都是同一规格的数组。规格统一，才好协作。", 3),
    ], ["load_as_gray：任何图 → 强制灰度 → uint8 数组",
        "save_image：ascontiguousarray → 内存连续再保存",
        "~全项目统一入口：算法吃的都是同一规格的数组"]),
    S("bullets", "新手期高频报错速查", [
        B("新手期的高频报错就四种：模块找不到，是装错了解释器；提示图像太小，是消息超过容量，换大图或把消息改短；中文乱码，因为默认只支持 ASCII；界面闪退，是解释器缺 tkinter。对照这张表，基本不用搜索。", 4),
    ], ["ModuleNotFoundError → 装错解释器，python -m pip 重装",
        "“图像太小” → 换大图 / 调小 p / 缩短消息",
        "UnicodeDecodeError → 默认只支持 ASCII 消息",
        "GUI TclError → 换带 tkinter 的解释器"]),
    close_scene("为什么保存图像前要 ascontiguousarray？切片和转置产生的是什么？",
                "第 3 章 · LSB 隐写与它的统计“指纹”",
                "想一想：为什么保存图像前要 ascontiguousarray？提示：切片和转置产生的是“视图”，内存不连续。",
                "下一章进入正题：亲手藏一条消息，再亲手把它抓出来。"),
]),

# ---- ch03（已审定的 demo 内容，正式化）
dict(num=3, title="LSB 隐写与它的统计“指纹”", weeks="第 3–4 周", scenes=[
    S("title", None, [
        B("你好，欢迎回到 nsF5 隐写课。今天这一课，我们讲整个领域最经典的一对攻防：LSB 隐写，和抓住它的统计指纹。", 3),
        B("这节课你会亲眼看到：一段话，是怎么神不知鬼不觉地藏进一张图片的；也会看到，检测者是怎么用统计这把尺子，把它从图里揪出来的。我们开始。", 5)],
     ["__center__nsF5 隐写教学系列|200|30|muted|r", "__pillc__第 3 章|360|42",
      "__center__LSB 隐写与它的统计“指纹”|470|76",
      "__center__藏得住吗？—— 我们来现场抓一次|610|38|muted|r",
      "__center__加密 vs 隐写 · 藏进像素 · 卡方 · RS · 交叉印证|700|30|accentd|r"]),
    S("bullets", "加密 vs 隐写：先分清两件事", [
        B("先聊一个特别容易混淆的问题：加密和隐写，到底差在哪？打个比方：加密是把话变成天书，别人看得见密文，但读不懂；隐写呢，话还是人话，可你根本看不出他正在说话。", 2),
        B("所以业内有句口诀：加密保护内容，隐写保护存在。真实的专业系统，往往两条一起用：先把消息加密成近似随机的比特，再把这些比特藏进图片。这样即使被怀疑，也很难拿到证据。", 3),
        B("为什么要先加密？因为随机比特本身就像噪声。把它藏进 LSB 平面这种本来就是噪声的地方，相当于把一滴水藏进大海。", 4),
    ], ["加密：把话变成“天书” —— 看得见，看不懂",
        "隐写：话还是人话 —— 看不出他在说话",
        "口诀：加密保护“内容”，隐写保护“存在”",
        "~实战套路：先加密成随机比特，再藏进图片"]),
    S("bullets", "LSB：整场游戏的主角", [
        B("藏的办法，简单得出奇。看一个像素：灰度值 200，写成八位二进制是 11001000。最右边这一位，叫最低有效位，LSB，它是整个隐写世界的主角。", 1),
        B("把它从 0 改成 1，200 就变成 201。你盯着看也好，拿放大镜看也好，200 和 201 的差别，人眼完全无感。", 3),
        B("于是，藏一句话，就等于把每个字符拆成 8 个比特，挨个写进像素的最低位。改的永远是最不重要的那一位——这就是 LSB 替换。", 4),
    ], ["__mono__200  =  128 + 64 + 8   →   11001000",
        "最低有效位（LSB）= 最右边那一位",
        "改 LSB：200 变 201，人眼零感知",
        "~藏一句话 = 字符拆成 8 bit，挨个写进最低位"]),
    S("anim", "动手：把 “Hi” 藏进 64 个像素", [
        B("光说不练假把式。屏幕上这 64 个像素，就是我们的停车场：每个像素的最低位，都是一个空车位，能免费停一个比特。先记住它们现在的样子。", 0, anim_beat=0),
        B("消息进场了。盯住被点亮的格子：像素值只在正负 1 之间跳动，比如 128 变 129、135 变 134。十六位消息写完，八处改动，可画面上你几乎什么都没看出来。这就是视觉冗余——人眼，是一台非常宽容的相机。", 0, anim_beat=1),
    ], anim="park"),
    S("figure", "真实载体：藏过之后长什么样", [
        B("换成项目里真实的封面图，结论一样：左边是原图，中间是藏了随机比特的含密图，四分之一的像素被动过，肉眼零差别。", 2),
        B("但请注意右边这张：把两张图的差异放大 255 倍，那些亮闪闪的噪点，就是每一个被改动的像素。秘密并没有消失，只是人眼看不见了。请记住这句话：看不见，不等于不在。", 3, zoom=True),
    ], ["__fig__lsb_cover_stego.png",
        "__cap__真实数据：① 载体 img/cover.png ② 含密图（~25% 像素被改）③ 差异放大 255 倍 ④ 载体自身的 LSB 位平面",
        "__pill__看不见 ≠ 不在"]),
    S("anim", "检测者的第一把尺子：卡方检验", [
        B("那检测的人怎么抓？他不用眼睛，用直方图。自然图像里，灰度 100 和 101 这对邻居，出现的次数通常不相等，有高有矮、参差不齐——现在屏幕上就是这样。", 0, anim_beat=0),
        B("但 LSB 替换有个致命的副作用：它把奇数和偶数强行配对拉平。矮的被垫高，高的被削平，最后每一对都齐刷刷一样高。太整齐，反而不自然——这就是卡方检验抓的指纹。", 0, anim_beat=1),
        B("工程上还有两个细节：项目会把图切成 20 段，逐段算 p 值再取中位数，防止单段波动捣乱；而且注意方向是反的——p 越高越可疑。天然噪声照片会骗过卡方，所以还要先估计图像本底有多随机，再下结论。", 0, anim_beat=2),
    ], anim="pairs"),
    S("bullets", "更狠的一把尺子：RS 分析", [
        B("卡方之外，还有更狠的 RS 分析。它看的是另一种秩序：相邻像素的最低位，本来是互相有关系的，像一家人住在同一个小区。", 1),
        B("检测者用两种掩码去翻转这些最低位，统计画面变光滑还是变乱。干净图有明显的家族结构，Gn 通常在零点三到零点七；一旦藏过东西，位面变成纯随机，结构当场塌掉，Gn 掉到零附近。", 3),
        B("真实的项目不会只赌一个指标。项目的 analyze 函数，把卡方、RS、熵基线、前缀序列四路信号放在一起交叉印证，还提供三档灵敏度。本质上是在回答一个问题：你更怕冤枉好人，还是更怕放过坏人。", 4),
    ], ["RS 看另一种秩序：相邻像素 LSB 的“家族相关性”",
        "干净图：负掩码缺口 Gn ≈ 0.3 – 0.7（结构在）",
        "藏过之后：位面随机化 → Gn 塌缩到 0 附近",
        "~analyze()：卡方 + RS + 熵基线 + 前缀序列，四路交叉印证"]),
    close_scene("改动不到 1% 像素，卡方还查得到吗？RS 呢？",
                "第 4 章 · 矩阵编码与 F5：少改一点，藏得更多",
                "留一道思考题：如果只藏一点点消息，改动不到百分之一的像素，卡方还查得到吗？RS 呢？",
                "想不出来，没关系。下一章的矩阵编码会告诉你一个反直觉的答案：高手不是藏得更深，而是改得更少。我们下节课见。"),
]),

dict(num=4, title="矩阵编码与 F5：少改一点，藏得更多", weeks="第 5 周", scenes=[
    title_scene(4, "矩阵编码与 F5：少改一点，藏得更多",
                "怎么改得更少？答案是数学",
                "嵌入效率 · 校验矩阵 · 伴随式 · F5 收缩",
                "欢迎回到 nsF5 隐写课。上一章结尾留了悬念：改动越小越难检测。这一章回答“怎么改得更少”——答案是数学：汉明码。学完你能手算一个真实嵌入的例子。",
                "本章的核心画面，是一个“7 个像素藏 3 位、只翻 1 位”的动画。我们开始。"),
    S("bullets", "朴素 LSB 的浪费", [
        B("先算笔账。朴素 LSB 藏 1 个比特，平均要动半个像素——比特和像素最低位相同就不动、不同才动，概率对半。藏一条大消息，就要动几百万个像素，动静太大。", 2),
        B("矩阵嵌入换了个玩法：把 7 个像素捆成一组，通过最多改动其中 1 个，一次性写入 3 个比特，效率直接翻三倍多。怎么做到的？靠一个叫校验矩阵的工具。", 3),
    ], ["朴素 LSB：藏 1 bit 平均改 0.5 像素",
        "矩阵嵌入：7 个位置装 3 bit，至多改 1 位",
        "效率 α = p·2^p / (2^p − 1)：p=3 时约 3.43"]),
    S("anim", "现场手算：只翻一位的魔法", [
        B("屏幕上是我们的工具：校验矩阵 H，7 列恰好是二进制的 1 到 7，互不相同。下面 7 个像素的最低位是这串 0101101。第一步算伴随式：把取值为 1 的位置对应的列异或起来，得到 s，等于 001。", 0, anim_beat=0),
        B("想藏的消息 m 是 110。两者异或得差值 d，等于 111。在 H 里找等于 111 的那一列——第 7 列！只需翻转第 7 个像素。验算：新伴随式正好等于消息。7 个像素装 3 位，平均八成的组只改 1 位。这就是矩阵编码。", 0, anim_beat=1),
    ], anim="syndrome"),
    S("figure", "为什么改得少 = 更安全", [
        B("把不同 p 下的容量、改动率、效率画成曲线，规律很清楚：p 越大，改动率越低、每次改动携带的比特越多，代价是容量下降。虚线是朴素 LSB 的基准：改动率 0.5。", 2),
        B("记住这句就够了：同样的容量，改得越少，统计痕迹越小，越难被抓。这是整门课反复出现的主题。", 3, zoom=True),
    ], ["__fig__f5_efficiency.png",
        "__cap__真实计算：随 p 增大——容量下降、改动率大降、每次改动携带的比特数上升",
        "__pill__改得越少，越安全"]),
    S("bullets", "F5 与它的“收缩”难题", [
        B("F5 算法把这套数学搬到 JPEG 上：在 DCT 系数上做矩阵嵌入，修改方式是让系数绝对值减一。但问题来了：绝对值已经是 1 的系数，再减就变 0——而 0 在 JPEG 里意味着“这个频带不存在”，不能用了。", 2),
        B("这就是著名的“收缩”：块作废、重找位置、重新嵌入。后果是容量缩水、效率下降、直方图异常。收缩像个死结——下一章的 nsF5 会用“湿纸编码”一步解开它。", 3),
    ], ["F5：在 JPEG 系数上矩阵嵌入，修改 = |系数| 减 1",
        "收缩：|系数| = 1 → 减成 0 → 块作废、重试",
        "后果：容量缩水 / 效率下降 / 直方图异常"]),
    close_scene("F5 遇到收缩就跳过重藏，解码端怎么知道哪块被跳过了？",
                "第 5 章 · nsF5 与湿纸编码：项目的核心算法",
                "想一想：F5 遇到收缩就跳过重藏，解码端怎么知道哪一块被跳过了？这个问题，F5 自己答不好。",
                "下一章 nsF5 的答案漂亮得多：根本不给收缩发生的机会。"),
]),

dict(num=5, title="nsF5 与湿纸编码：项目的核心算法", weeks="第 6 周", scenes=[
    title_scene(5, "nsF5 与湿纸编码：项目的核心算法",
                "先划湿点，再解方程",
                "收缩 · 湿纸编码 · GF(2) 求解 · 无收缩嵌入",
                "欢迎回到 nsF5 隐写课。第五章，项目核心算法登场：nsF5 与湿纸编码。上一章的收缩问题，这一章用一个极优雅的思想根治——先划湿点，再解方程。",
                "学完这章，你能对着代码讲出 nsF5 嵌入的完整流程。"),
    S("bullets", "收缩的三重伤", [
        B("先把收缩的伤害说透。第一，容量低于理论值，因为块被浪费了；第二，效率低于理论值，因为要反复重试；第三，也是最致命的：被改到 0 的系数变多，直方图出现异常——等于在墙上留下指纹。", 2),
        B("项目在像素域做了一个聪明的类比：像素减 128 变成有符号值。那么 127、128、129 这三个值，绝对值小于等于 1，一减幅就会撞到零——它们就是像素域里的“危险分子”。", 3),
    ], ["收缩三重伤：容量 ↓ / 效率 ↓ / 直方图异常",
        "像素域类比：xv = 像素 − 128",
        "~127、128、129：|xv| ≤ 1，减幅撞零的“危险分子”"]),
    S("anim", "湿纸编码：先划湿点，再解方程", [
        B("湿纸编码的思想一句话：如果纸上有几处被水浸湿、写了也看不见，那就别写它们——只在干的地方写。看动画：一块 7 个像素，127、128、129 被标记成红色湿点，写之前就排除。", 0, anim_beat=0),
        B("要实现的伴随式变化是 d。先看干列里有没有一列直接等于 d——没有；再看有没有两列异或等于 d——第 4 列异或第 7 列，命中！只改这两个干点，湿点一动不动。没有收缩，不用重试，每个块一次成功。", 0, anim_beat=1),
    ], anim="wetdry"),
    S("bullets", "工程细节与兜底", [
        B("三个工程细节。第一，求解按“单列、双列、高斯消元”三步走，尽量少改；第二，高斯解方程时自由变量置零，让解出来的改动数最少；第三，万一干点太少、方程无解，就兜底翻转目标位，保证解码端一定能解。", 4),
        B("那解码端需要知道哪些是湿点吗？不需要！它只读最低位、算伴随式。湿点是嵌入端的事——这正是湿纸编码最优雅的地方：双方不需要约定任何额外信息。", 4),
    ], ["求解三步：单列命中 → 双列异或 → GF(2) 高斯兜底",
        "~高斯消元自由变量置 0 → 改动最少",
        "解码端只读 LSB 算伴随式，无需知道湿点",
        "~干点不足时兜底翻转目标位，保证可解码"]),
    S("bullets", "验证：湿点再多也能往返", [
        B("怎么验证？项目自测里专门有个用例，把像素强行设成 127、128、129 制造大片湿点，嵌入解码照样往返成功。对比实验也说明问题：普通图上 matrix 和 nsF5 差不多；但危险像素密集的图上，matrix 反复失效，nsF5 稳定完成。", 3),
    ], ["test_core：强制 127/128/129 制造湿点 → 往返成功",
        "普通图：matrix 与 nsF5 改动数接近",
        "~危险像素密集图：nsF5 无收缩完胜"]),
    close_scene("如果一块里湿点太多、干点张不成整个空间，会发生什么？",
                "第 6 章 · 口令、SHA-256 与“键控”安全设计",
                "想一想：如果一块里湿点太多，干点张不成整个消息空间，会发生什么？结合秩的论证想一想。",
                "算法已经很强，但还有个软肋：藏在哪，由谁说了算？下一章讲键控。"),
]),

dict(num=6, title="口令、SHA-256 与“键控”安全设计", weeks="第 6–7 周", scenes=[
    title_scene(6, "口令、SHA-256 与“键控”安全设计",
                "藏在哪，由谁说了算？",
                "固定路径的风险 · 种子规则 · 确定性置乱 · 篡改感知",
                "欢迎回到 nsF5 隐写课。第六章讲安全设计。假设你的隐写算法天下第一，但每次都藏在同样的位置——那一切都白搭。这一章讲：怎么让“藏在哪”，只有持有口令的人知道。",
                "两个原创动画等着你：一张是逐行扫描的危险，两张是口令画出的地图。"),
    S("bullets", "固定路径的三大风险", [
        B("如果每次都从左上角开始顺序嵌入，攻击者知道算法后能做三件事：直接读前 N 个像素还原消息；把消息原样复制到另一张图上；或者对着固定区域精准扰动，毁了你的消息还不动声色。", 3),
        B("解法只有一句话：把嵌入路径做成由密钥控制的伪随机顺序。不知道口令，连消息在哪都不知道，谈不上攻击。", 4),
    ], ["风险一：顺序读取前 N 像素 → 消息直接泄露",
        "风险二：位置替换——原样复制到另一张图",
        "风险三：对固定区域精准扰动",
        "~解法：路径由密钥决定（键控）"]),
    S("anim", "两条口令，两张地图", [
        B("先看反例：不用密钥时，访问顺序就是逐行扫描，谁都猜得到。现在给两把不同的口令：注意看，两条访问路径像乱针一样铺开，彼此完全不同，也无法预测。", 0, anim_beat=0),
        B("同一个口令，每次生成完全相同的排列——这叫自同步，是解码端能找到消息的前提。换一个字符，整张地图重画。安全的来源不是“藏得看不见”，而是“不知道位置”。", 0, anim_beat=1),
    ], anim="permute"),
    S("bullets", "两条种子规则：先认图，再找正文", [
        B("项目把像素分成两个池：头部池和正文池，用两条独立的种子规则。seed0 只由口令派生，控制头部池——里面预埋了原图字节的 SHA-256 哈希；seedB 由内容哈希加口令共同派生，控制正文池。", 2),
        B("为什么正文要掺入内容哈希？妙处在这：解码端先用自己的口令解开头部、拿到哈希，再重建正文路径。口令错了，或者图被改了一个像素，正文路径立刻错乱——篡改感知是白送的。", 3),
    ], ["seed0 = 仅口令 → 头部池（存 128 位 cover_hash）",
        "seedB = cover_hash + 口令 → 正文池",
        "~口令错 / 图被改 → 正文路径立刻错乱（篡改感知白送）"]),
    S("bullets", "边界：诚实地说清能防什么", [
        B("也要诚实讲边界。这套机制叫键控加篡改感知，不等于密码学里的完整性认证。头部哈希没有做密钥化 MAC，一个有能力重嵌整张图的攻击者，可以同步更新哈希。一句话：它能发现普通篡改，防不住蓄意重嵌。", 4),
    ], ["键控 + 篡改感知 ≠ 完整性认证（无密钥化 MAC）",
        "能发现：普通篡改、口令错误",
        "~防不住：重嵌整图并同步更新头部",
        "升级路线：引入密钥化 MAC（列为后续工作）"]),
    close_scene("两张不同原图，嵌入同一条消息，隐藏位置会一样吗？",
                "第 7 章 · 机器学习基础（写给第一次学的人）",
                "想一想：两张不同的原图，嵌入同一条消息，隐藏位置会一样吗？提示：正文种子由什么决定？",
                "下一章视角反转：从藏的人，变成抓的人。"),
]),

dict(num=7, title="机器学习基础（写给第一次学的人）", weeks="第 7–12 周", scenes=[
    title_scene(7, "机器学习基础", "从“藏的人”变成“抓的人”",
                "数据 · 特征 · 模型 · 评估 · 防作弊",
                "欢迎回到 nsF5 隐写课。第七章，视角反转：从藏的人变成抓的人。哪怕你从没学过机器学习，这一章也只要求你带走四个词、几张图和一个直觉。",
                "这一章是后面一切检测的地基，值得慢一点学。", size=76),
    S("bullets", "四个词，讲清监督学习", [
        B("隐写检测，本质是猜一张图藏没藏。整个监督学习就四样东西：数据，一堆带答案的例子；特征，用一串数字描述一张图，相当于尺子；模型，从特征到答案的判断规则；评估，验证这规则靠不靠谱。", 4),
        B("机器学习不背题，学的是规律——就像学生刷题不是为了背题库，而是为了见新题也会做。后面所有内容，都是把这四个词展开。", 4),
    ], ["数据 = 带答案的例子（干净=0，含密=1）",
        "特征 = 量图的一串数字（本项目 11 或 143 把尺子）",
        "模型 = 特征到答案的判断规则",
        "评估 = 这条规则靠谱吗"]),
    S("figure", "分类 = 画一条线", [
        B("模型学的是什么？在特征空间里画一条线：这边干净，那边含密。数学上就是个加权打分——每个特征乘权重再加偏置，分数过线判含密。权重越大，说明这把尺子越重要。", 2),
        B("注意看真实数据的散点：两类没有彻底分开，边界附近蓝红混杂。所以模型不该硬说零或一，而应该给出概率——“我有七成把握”。概率，比答案更诚实。", 2, zoom=True),
    ], ["__fig__ml_decision_boundary.png",
        "__cap__真实数据：两特征学出的决策边界——蓝=干净，红=含密，边界附近两类混杂",
        "__pill__输出概率，比输出 0/1 更诚实"]),
    S("anim", "模型怎么学会：损失与梯度下降", [
        B("怎么衡量模型错得有多离谱？用损失函数：猜得越离谱，扣分越狠。训练的目标就一件事：调整参数，让损失变小。看动画：小球顺着损失曲面往下走，每一步都朝“下降最快的方向”挪一点——这就是梯度下降。", 0, anim_beat=0),
        B("走到谷底，损失最小，训练完成。三句话总结：损失是错得有多离谱；训练是找参数让损失最小；梯度下降就是顺着下坡一小步一小步走。至于防“死记硬背”的正则化旋钮 C，项目里取 0.1，让模型保守一点。", 0, anim_beat=1),
    ], anim="gradient"),
    S("figure", "防作弊：同一张照片不能拆开", [
        B("接下来是全章最重要的一页：防作弊。同一张照片在数据集里有 7 个变体——1 干净 6 含密，像七胞胎。如果随机切分，七胞胎分居训练、测试两边，模型等于提前见过考题——这叫数据泄漏，分数虚高到离谱。", 2),
        B("项目的做法：按照片编号分组，同一照片的所有变体要么全在训练、要么全在测试，五折轮换。记住：评估的可信度，不取决于模型多花哨，而取决于切分多诚实。", 2, zoom=True),
    ], ["__fig__ml_groupkfold.png",
        "__cap__上排：随机切分=漏题；下排：GroupKFold 同照片同折=诚实",
        "__pill__切分不诚实，一切分数免谈"]),
    S("figure", "评估：别只盯准确率", [
        B("最后看评估。类别不平衡时准确率会骗人：一千张里九百张含密，模型无脑全判含密，准确率 90%——但所有干净图都被冤枉了。", 2),
        B("更靠谱的是 ROC 曲线和 AUC：只看模型能不能把含密排在干净前面，与阈值无关。0.5 是瞎猜，1 是完美。本项目 11 维特征约 0.7——多数时候排得对，弱密度还抓不住，这是实话。", 2, zoom=True),
    ], ["__fig__ml_roc_auc.png",
        "__cap__真实数据 OOF ROC：AUC ≈ 0.70——能排对，但弱密度仍难检出",
        "__pill__AUC 与阈值无关；阈值 = 操作点"]),
    close_scene("一篇论文说 AUC 0.95，却没说数据怎么切分，你先怀疑什么？",
                "第 8 章 · 用机器学习做隐写检测",
                "想一想：一篇论文说 AUC 0.95，却没说数据怎么切分的，你先怀疑什么？有没有按照片分组？阈值怎么选的？",
                "带着这个怀疑，下一章看项目自己的检测系统，怎么诚实地从 0.5 做到 0.9。"),
]),

dict(num=8, title="用机器学习做隐写检测", weeks="第 8–14 周", scenes=[
    title_scene(8, "用机器学习做隐写检测", "11 把尺子，和一次昂贵的教训",
                "特征三族 · 诚实训练 · 阈值取舍 · v1.4 演进",
                "欢迎回到 nsF5 隐写课。第八章，把上一章的方法论用到真实项目：造 11 把尺子，训练分类器，诚实地评估。还有一个大反直觉的结论：为什么不直接让深度学习看图？",
                "这一章还有 v1.4 的三次升级，和一堂昂贵的教训。", size=76),
    S("bullets", "反直觉：为什么不让 AI 直接看图", [
        B("深度学习认猫认狗那么强，为什么不直接把像素喂给神经网络？项目试过：验证 AUC 0.5，等于抛硬币。原因有三：隐写改动是极微弱的高频信号，信噪比太低；网络容易学到“风景还是人像”这类捷径；独立样本只有几百张，深度模型喂不饱。", 3),
        B("所以路线换成：用领域知识造尺子，量统计痕迹，再让简单模型判断。这不是说深度学习不行，而是样本少、信号弱时，可解释的特征是更稳的起点。", 4),
    ], ["实测：裸 CNN 验证 AUC ≈ 0.50（等于瞎猜）",
        "信号弱 + 样本少 → 深度模型喂不饱",
        "~替代路线：领域特征 + 简单分类器",
        "先证明信号存在，再上复杂模型"]),
    S("bullets", "11 把尺子在量什么", [
        B("11 个特征分三族。RS 族：核心是负掩码缺口 Gn，干净图有结构、值偏高，藏过东西就塌向零——最强的一把尺子。卡方族：灰度对被抹匀的程度。熵族：图像本底有多乱，用来认出“天生就乱”的照片，防止误伤。", 4),
    ], ["RS 族：Gn 塌缩 = 最强信号",
        "卡方族：奇偶灰度对被抹匀",
        "熵族：本底乱度 → 认出“天生乱”的图（兜底）",
        "~三族合起来 = 11 把尺子（详见手册 8.2 节）"]),
    S("figure", "看真实分布：Gn 有多能打", [
        B("看真实数据：左边是 Gn 的分布，干净图集中在偏高的位置，含密图明显塌向低处，两座山分得很开；右边 Gr 也有区分度，但不如 Gn 干净。所以 Gn 塌缩，是藏过东西的强力证据。", 2, zoom=True),
    ], ["__fig__feat_rs.png",
        "__cap__真实数据：干净图（蓝）与含密图（红）的 RS 缺口分布",
        "__pill__Gn 塌缩 = 强力证据"]),
    S("bullets", "数据与训练：三条纪律", [
        B("数据怎么来？每张源照片生成 1 张干净加 6 个含密变体，覆盖不同算法、不同强度。训练流水线严守三条纪律：先按照片预留四分之一做测试集，绝不参训；训练池五折分组交叉验证选模型；校准集挑阈值；最后测试集只碰一次。", 2),
        B("四个候选分类器——逻辑回归、随机森林、梯度提升、XGBoost——在这个 11 维特征上 AUC 几乎重叠。结论反直觉但重要：这一层的瓶颈不在分类器，在特征。", 2),
    ], ["数据：每照片 1 干净 + 6 含密（1+6）",
        "纪律：预留测试集 / GroupKFold OOF / 校准挑阈值 / 只评一次",
        "~11 维上 LR/RF/GB/XGB = 0.701/0.702/0.714/0.720：几乎重叠 → 瓶颈在特征"]),
    S("anim", "读结果：阈值是取舍，不是答案", [
        B("模型输出的是概率，要定一个阈值才能下结论。看动画：阈值从高往低滑，检出率上升，误报率也跟着涨。严一点，误报少但漏掉弱嵌入；松一点，抓得多但冤枉也多。", 0, anim_beat=0),
        B("项目用 Youden 准则自动选离对角线最远的点做默认阈值，再备一个低误报阈值给严格档。按密度分组看检出率：强嵌入九成以上，最弱的 nsF5 档只有五成——检测有物理上限，这是要接受的现实。", 0, anim_beat=1),
    ], anim="roc"),
    S("bullets", "v1.4 演进：三次升级，一堂贵课", [
        B("最后看版本演进的三课。SRM 高通滤波作为预处理层：当年（v1 口径）同源数据涨三个点、跨源反而亏——这条口径在当前版本没有复现，别当成定论。第二课是特征升级：11 维升到 143 维、变体 6 档升 12 档。", 2),
        B("最贵的一课是分布漂移：模型在训练数据上表现很好，遇到真实 JPEG 相机照片，却把干净图几乎全判成含密。修复办法是把真实 JPEG 干净图加进训练。最终双版本部署：143 维稳健版做默认，53 维可解释版给论文和教学。记住：新模型上线前，先做分布外测试。", 4),
    ], ["SRM 预处理：v1 口径下同源 +0.03、跨源反亏（未在当前版本复现）",
        "11 维 → 143 维、6 档 → 12 档",
        "~教训：真实 JPEG 干净图全判 1.0 → 分布漂移 → 加负样本修复",
        "双版本：143d 更准（默认，8-split 0.898）/ 53d 逐维可解释（0.846）"]),
    close_scene("如果有十万张独立照片，你还会坚持特征法，还是上深度学习？",
                "第 9 章 · 工程化：C++、GPU、GUI 与测试",
                "想一想：如果有十万张独立照片，你还会坚持特征法，还是上深度学习？为什么？",
                "算法讲完了。下一章看工程：怎么把算法变成不翻车的软件。"),
]),

dict(num=9, title="工程化：C++、GPU、GUI 与测试", weeks="第 10 周", scenes=[
    title_scene(9, "工程化：C++、GPU、GUI 与测试", "让算法变成不翻车的软件",
                "分层架构 · 加速与一致性 · GUI · 测试与 CI",
                "欢迎回到 nsF5 隐写课。第九章讲工程化。算法写出来只是起点，让它快几百倍、不出错、普通人会用，才是软件。这章三个词：加速、一致性、测试。",
                "有一组真实的测量数据，会颠覆你对 Python 速度的认知。"),
    S("bullets", "分层架构：算法层不依赖任何人", [
        B("项目分四层：最底下是 C++ 加速层，两个动态库；上面是算法核心 ns5_core；再上面是分析、数据集、训练这些功能层；最上是图形界面。分层的规矩是：算法层不依赖界面，服务器上能裸跑；加速层缺失就自动回退纯 Python，功能永远可用。", 3),
    ], ["四层：DLL 加速 → ns5_core → 功能层 → GUI",
        "~算法层不依赖 GUI：服务器 / CI 可裸跑",
        "DLL 缺失自动回退 Python：功能永远可用"]),
    S("anim", "快 263 倍，前提是“完全一样”", [
        B("Python 逐元素循环很慢，隐写恰好有两个热路径：像素置换和特征提取。看这组真实测量：四千见方的图做置换，Python 要 12 秒，C++ 只要 0.22 秒——263 倍。特征提取下沉到 GPU 批量算，每秒四百多张。", 0, anim_beat=0),
        B("但快不是重点，重点是“结果完全一样”。项目专门写了自校验：同一张图分别走 C++ 和 Python 两路嵌入，输出必须像素级一致；特征也逐个核对。遇到“有库能嵌、没库解不了”的灵异事件，先跑自检，不要碰算法。", 0, anim_beat=1),
    ], anim="speedup"),
    S("bullets", "GUI 与测试：重构不翻车靠护栏", [
        B("界面围绕嵌入、解码、分析三步设计，有两个教学彩蛋：矩阵编码演示，实时算伴随式、高亮命中列；载荷扫描，拖动嵌入密度，看三条统计曲线一起爬升——藏得越满越危险，一目了然。", 2),
        B("测试四层兜底：算法自测、分析自测、误报回归、界面冒烟，再接上持续集成：每次提交自动跑测试、自动打包、打标签自动发布。重构不翻车，靠的不是小心，是护栏。", 4),
    ], ["GUI：matrix_demo（实时 s/m/d）+ scan_panel（载荷扫描）",
        "~措辞严谨：单图概率 ≠ 数据集 AUC",
        "四层测试：core / steg / 误报回归 / GUI",
        "CI：自动测试 + 打包 + 打标签自动发布"]),
    close_scene("如果 Python 和 C++ 的置换排列不一致，会出现什么灾难？",
                "第 10 章 · 综合实践：从“读懂”到“做出来”",
                "想一想：如果 Python 和 C++ 的置换排列不一致，会出现什么灾难？提示：嵌入和解码，可能发生在不同的机器上。",
                "下一章是实践章：三个方向，两周做出一个可演示的改进实验。"),
]),

dict(num=10, title="综合实践：从“读懂”到“做出来”", weeks="第 11–12 周", scenes=[
    title_scene(10, "综合实践：从“读懂”到“做出来”", "两周，一个可演示的改进实验",
                "诚实评估 · 三个方向 · 交付与答辩",
                "欢迎回到 nsF5 隐写课。第十章，综合实践。接下来两周，你要完成一个可演示的改进实验。但先别急着写代码——这章先教你：怎么做实验，结论才算数。",
                "先看一条所有实验都必须遵守的流水线。"),
    S("anim", "先学会“怎么算才算数”", [
        B("跟着动画走一遍项目的训练流水线：数据进来，先按照片预留测试集；训练池五折分组交叉验证，用 OOF 分数选模型；校准集挑阈值；全量重训；最后测试集只评一次，保存模型。", 0, anim_beat=0),
        B("三条红线记牢：测试集只碰一次；同源样本绝不拆开；“我改了 A、结果变好了”不足以服人——要用这套流水线证明它真的变好。你后面做任何实验，都回到这条流水线上对照。", 0, anim_beat=1),
    ], anim="pipeline"),
    S("bullets", "三个方向，由易到难", [
        B("实践方向三选一，或者组合。方向 A，复现并批判性验证：挑论文里的结论重跑，尝试推翻它——复现不是照抄，是理解每个数字从哪来。方向 B，功能扩展：支持中文消息、扩展彩色通道、新增统计特征、实现朴素 LSB 做对比。方向 C，把矩阵编码演示包装成动画、题库、对比模式。", 4),
        B("提醒一句：方向 B 最容易“自我感觉良好”——加个特征，AUC 涨了 0.01 就宣布胜利。回到流水线：同一组测试照片、五折 OOF 做 A/B，否则那 0.01 只是随机波动。", 4),
    ], ["A 复现并批判性验证（最稳）",
        "B 功能扩展：UTF-8 / 彩色通道 / 新特征 / 对比 LSB",
        "~每次扩展都跑 test_core + test_steg",
        "C 教学演示再包装：动画 / 题库 / 对比模式"]),
    S("bullets", "交付清单与答辩高频题", [
        B("交付清单六件套：能讲清每处改动的代码 diff；不加工、不挑数的原始输出；两三张坐标图例完整的图；三到五页的报告——问题、方法、结果、局限、下一步；五分钟一条龙演示；最后，脱稿回答任意三个高频问题。", 4),
        B("答辩高频题先备着：LSB 为什么会被发现？矩阵编码为什么改得少？nsF5 好在哪？为什么不用裸 CNN？你的模型更好怎么证明？——每个答案，前面章节都讲过。", 4),
    ], ["代码 diff + 原始输出（不加工、不挑数）",
        "2–3 张图 + 3–5 页报告",
        "5 分钟一条龙演示",
        "~脱稿回答 3 个高频问题（手册 10.5 有题库）"]),
    close_scene("如果有人质疑你“反复调测试集才得到这个结果”，你怎么回应？",
                "第 11 章 · 边界、伦理与继续前进",
                "想一想：如果有人质疑你“反复调测试集才得到这个结果”，你怎么回应？把“测试集只用一次”这条红线讲清楚，并展示 OOF 和校准集的结果。",
                "最后一章，我们谈边界与伦理，然后给你一张继续前进的地图。"),
]),

dict(num=11, title="边界、伦理与继续前进", weeks="穿插学习 · 收官", scenes=[
    title_scene(11, "边界、伦理与继续前进", "最后一课：什么能做，下一步去哪",
                "伦理边界 · 项目局限 · 现代地图 · 收官练习",
                "欢迎回到 nsF5 隐写课，最后一课。技术讲完了，这一课谈三件事：什么能做、什么不能做；项目的边界在哪；如果兴趣被点燃了，下一步往哪走。",
                "学完这一课，整个系列就毕业了。", size=76),
    S("bullets", "法律与伦理边界", [
        B("隐写是双刃剑：它支撑版权水印、媒体溯源、隐蔽认证，也可能被用于恶意隐蔽通信。这门课的立场很明确：只在自有数据、公开数据集或授权场景做实验；把工具用于检测与取证，而不是协助隐藏；发表结果时说明局限，不夸大能力；绝不拿他人隐私图像练手。", 4),
        B("其实这个项目的分析部分——卡方、RS、机器学习——正是“盾”的一面：监管和取证，靠的就是它们来发现隐蔽信道。学攻击，是为了造更好的盾。", 4),
    ], ["只在自有 / 公开 / 授权数据上实验",
        "工具用于检测与取证，而非协助隐藏",
        "发表说明局限与误报风险，不夸大能力",
        "~不拿他人隐私图像当练习载体"]),
    S("bullets", "项目已知边界：看懂边界才算读懂", [
        B("看懂边界，才算真读懂项目。几条硬边界：消息默认只支持 ASCII；彩色图只用红通道；哈希键控不是密钥化认证，防不住重嵌攻击；像素域实现怕 JPEG；弱密度和跨源仍是检出难点。任何新模型，上线前先做分布外测试。", 4),
        B("这些局限不是缺陷清单，而是下一批研究问题的清单——你甚至可以从中挑一个，当作自己的毕业设计。", 4),
    ], ["默认 ASCII；彩色只用 R 通道",
        "哈希键控 ≠ 密钥化 MAC",
        "像素域怕 JPEG → 需 DCT 系数实现（yccstego）",
        "~弱密度 / 跨源难检出；新模型先 OOD 测试"]),
    S("anim", "全貌与下一步", [
        B("把这一学期连成一条线：载体，经嵌入算法变成含密图；含密图留下统计指纹；机器学习读指纹、给判读；界面把一切交给用户。每个环节，你都在代码里亲手摸过。", 0, anim_beat=0),
        B("如果兴趣被点燃，地图上有这些方向：内容自适应嵌入 HUGO、UNIWARD；深度学习隐写与隐写分析；JPEG 域——项目里的 yccstego 就是一步之遥；还有可逆与鲁棒水印。下一步建议：把湿纸编码读回原始论文，再对照 yccstego 学 JPEG 域。", 0, anim_beat=1),
    ], anim="chain"),
    close_scene("收官练习：不看资料，用 500 字讲清“nsF5 为什么比朴素 LSB 更好”。",
                "本系列完 · 感谢观看",
                "收官练习：不看任何资料，用五百字向一位同学讲清楚——nsF5 为什么比朴素 LSB 更好。写完再打开 README 对照，查漏补缺。能写清，才算真正学完。",
                "十二周前，你以为隐写就是把字藏进图里；现在，你能讲清冗余、指纹、汉明码、湿纸编码，还有机器学习怎么诚实地给出把握。感谢一路看到这里——我们下一个项目见。",
                finished=True),
]),
]
