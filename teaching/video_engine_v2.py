# -*- coding: utf-8 -*-
"""v2 teaching-video engine (narrated & animated, one MP4 per chapter).

See video_scenes_zh.py for the per-chapter scene scripts and animations.
Key properties (approved on the ch03 demo, 2026-09):
  * neural zh-CN narration via edge-tts (default zh-CN-YunxiNeural),
    one clip per narration "beat" -> reveals synced to the voice;
  * bullet/figure elements fade+rise in step with the narration, figures get a
    gentle Ken-Burns push-in, subtitles burned in per beat;
  * per-scene PIL animations registered in ANIMS;
  * fully resumable (per-beat narration WAVs are cached on disk).
"""
import asyncio
import math
import multiprocessing as mp
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_videos import (ACCENT, ACCENT_DARK, BG, LINE, MUTED, TEAL, TEXT, W, H,
                        fonts, mono_fonts, get_ffmpeg, wrap)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "web" / "zh" / "assets"
COVER = ROOT / "img" / "cover.png"
TMP = ROOT / "teaching" / "videos" / "_tmp_v2"
QA = ROOT / "teaching" / "videos" / "qa"

FPS = 24
REVEAL_F = 13
DELAY, GAP = 0.2, 0.45
# 优化布局：图表区上移，为字幕留出充足安全空间，避免遮挡
FIGBOX = (95, 200, 1825, 700)
# 字幕安全区：底部 220px 保留给字幕，关键内容不应进入此区域
SUBTITLE_SAFE_Y = 860

COLORS = {"accent": ACCENT, "accentd": ACCENT_DARK, "muted": MUTED,
          "teal": TEAL, "text": TEXT, "white": (255, 255, 255)}

ANIMS = {}


def register_anim(name):
    def deco(fn):
        ANIMS[name] = fn
        return fn
    return deco


def ease(t):
    return 1 - (1 - t) ** 3


_scratch = ImageDraw.Draw(Image.new("RGB", (8, 8)))


# ---------------------------------------------------------------- elements
def _rgba(canvas):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    return layer, ImageDraw.Draw(layer)


def el_bullet(text, x, y, maxw, size=40, mono=False, level=0):
    fr, fb = fonts(size)
    fm, _ = mono_fonts(size)
    off_m = fr.getmetrics()[0] - fm.getmetrics()[0]
    marker_w = 44 if not level else 74
    lines = wrap(_scratch, text, fr, maxw - marker_w)
    lh = int(sum(fr.getmetrics()) * 1.3)
    end_y = y + len(lines) * lh

    def draw(canvas, alpha, dy):
        layer, d = _rgba(canvas)
        a = int(255 * alpha)
        yy = y + dy
        for j, ln in enumerate(lines):
            if level:
                d.rectangle([x + 34, yy + lh * 0.42, x + 52, yy + lh * 0.42 + 5],
                            fill=(ACCENT[0], ACCENT[1], ACCENT[2], a))
                cx = x + marker_w
            else:
                d.ellipse([x + 12, yy + lh * 0.36, x + 30, yy + lh * 0.36 + 18],
                          fill=(ACCENT[0], ACCENT[1], ACCENT[2], a))
                cx = x + marker_w
            if j == 0 and "：" in ln and ln.index("：") <= 14:
                lead, rest = ln.split("：", 1)
                d.text((cx, yy), lead + "：", font=fb,
                       fill=(ACCENT_DARK[0], ACCENT_DARK[1], ACCENT_DARK[2], a))
                cx += d.textlength(lead + "：", font=fb)
                ln = rest
            for ch in ln:
                latin = ord(ch) < 0x2E80 and ch.isalnum()
                f = fm if (mono or latin) else fr
                d.text((cx, yy + (off_m if latin and not mono else 0)), ch,
                       font=f, fill=(TEXT[0], TEXT[1], TEXT[2], a))
                cx += d.textlength(ch, font=f)
            yy += lh
        return Image.alpha_composite(canvas, layer)

    return draw, end_y


def el_center(text, y, size, color=TEXT, bold=True, mono=False):
    fr, fb = fonts(size)
    fm, _ = mono_fonts(size)
    f = fm if mono else (fb if bold else fr)

    def draw(canvas, alpha, dy):
        layer, d = _rgba(canvas)
        a = int(255 * alpha)
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y + dy), text, font=f,
               fill=(color[0], color[1], color[2], a))
        return Image.alpha_composite(canvas, layer)

    return draw, y + size * 1.4


def el_pill(text, cy, size=40, fill=ACCENT, fg=(255, 255, 255), outline=False):
    fr, _ = fonts(size)
    tw = _scratch.textlength(text, font=fr)
    pw, ph = tw + 84, size + 42
    end_y = cy + ph / 2

    def draw(canvas, alpha, dy):
        layer, d = _rgba(canvas)
        a = int(255 * alpha)
        x0, y0 = (W - pw) / 2, cy - ph / 2 + dy
        col = (fill[0], fill[1], fill[2], a)
        if outline:
            d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2,
                                outline=col, width=4)
            d.text((x0 + 42, y0 + 17), text, font=fr, fill=col)
        else:
            d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=col)
            d.text((x0 + 42, y0 + 17), text, font=fr,
                   fill=(fg[0], fg[1], fg[2], a))
        return Image.alpha_composite(canvas, layer)

    return draw, end_y


def el_figure(path, box=FIGBOX):
    fig = Image.open(path).convert("RGB")
    bw, bh = box[2] - box[0], box[3] - box[1]
    s = min(bw / fig.width, bh / fig.height)
    if s < 1:
        fig = fig.resize((int(fig.width * s), int(fig.height * s)), Image.LANCZOS)
    fx = box[0] + (bw - fig.width) // 2
    fy = box[1]

    def draw(canvas, alpha, dy):
        layer, d = _rgba(canvas)
        a = int(255 * alpha)
        layer.paste(fig, (fx, int(fy + dy)))
        layer.putalpha(layer.getchannel("A").point(lambda v: (v * a) // 255))
        d.rectangle([fx, fy + dy, fx + fig.width, fy + fig.height + dy],
                    outline=(LINE[0], LINE[1], LINE[2], a), width=2)
        return Image.alpha_composite(canvas, layer)

    return draw, fy + fig.height


def el_caption(text, cy, maxw=1500, size=27):
    fr, _ = fonts(size)
    lines = wrap(_scratch, text, fr, maxw)[:2]
    end_y = cy + len(lines) * 38

    def draw(canvas, alpha, dy):
        layer, d = _rgba(canvas)
        a = int(255 * alpha)
        yy = cy + dy
        for ln in lines:
            w = d.textlength(ln, font=fr)
            d.text(((W - w) / 2, yy), ln, font=fr,
                   fill=(MUTED[0], MUTED[1], MUTED[2], a))
            yy += 38
        return Image.alpha_composite(canvas, layer)

    return draw, end_y


def build_elements(scene):
    els, y = [], 226
    for item in scene.get("elements", []):
        if item.startswith("__fig__"):
            fn, y2 = el_figure(ASSETS / item[7:])
        elif item.startswith("__cap__"):
            # 优化：图注位置上移，紧跟图表下方，远离字幕区
            fn, y2 = el_caption(item[7:], 728)
        elif item.startswith("__pill__"):
            fn, y2 = el_pill(item[8:], 810, 36, fill=TEAL, outline=True)
        elif item.startswith("__mono__"):
            fn, y2 = el_bullet(item[8:], 90, y + 14, W - 220, size=42, mono=True)
        elif item.startswith("__center__"):
            p = item[10:].split("|")
            fn, y2 = el_center(p[0], int(p[1]), int(p[2]),
                               color=COLORS.get(p[3], TEXT) if len(p) > 3 else TEXT,
                               bold=not (len(p) > 4 and p[4] == "r"))
        elif item.startswith("__pillc__"):
            p = item[8:].split("|")
            fn, y2 = el_pill(p[0], int(p[1]), int(p[2]) if len(p) > 2 else 40,
                             fill=COLORS.get(p[3], ACCENT) if len(p) > 3 else ACCENT)
        else:
            level = item.startswith("~")
            fn, y2 = el_bullet(item[1:] if level else item, 90, y, W - 220,
                               size=40, level=1 if level else 0)
        els.append(fn)
        y = y2 + 26
    return els


# ---------------------------------------------------------------- chrome
def base_canvas(scene_idx, total, title=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 6], fill=ACCENT)
    fs, _ = fonts(26)
    d.text((70, 22), "nsF5 隐写教学系列", font=fs, fill=MUTED)
    label = f"第 {scene_idx} 幕 / 共 {total} 幕"
    d.text((W - 70 - d.textlength(label, font=fs), 22), label, font=fs, fill=MUTED)
    if title:
        ft, _ = fonts(50)
        while d.textlength(title, font=ft) > W - 300:
            ft, _ = fonts(ft.size - 4)
        d.rectangle([70, 84, 84, 146], fill=ACCENT)
        d.text((110, 84), title, font=ft, fill=TEXT)
    frac = scene_idx / total
    d.rectangle([0, H - 8, W, H], fill=(226, 230, 240))
    d.rectangle([0, H - 8, int(W * frac), H], fill=ACCENT)
    return img


def subtitle_band(canvas, text):
    if not text:
        return canvas
    fr, _ = fonts(30)
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lines = wrap(_scratch, text, fr, 1600)[:2]
    lh = 42
    bh = len(lines) * lh + 22
    # 字幕位置优化：更靠下、更紧凑，减少对内容区的遮挡
    y0 = H - 40 - bh
    widths = [d.textlength(ln, font=fr) for ln in lines]
    bw = max(widths) + 64
    # 更柔和的半透明背景，降低视觉干扰
    d.rounded_rectangle([(W - bw) / 2, y0, (W + bw) / 2, y0 + bh],
                        radius=14, fill=(255, 255, 255, 178),
                        outline=(210, 216, 232, 200), width=1)
    yy = y0 + 11
    for ln, lw in zip(lines, widths):
        d.text(((W - lw) / 2, yy), ln, font=fr, fill=(36, 42, 58, 255))
        yy += lh
    return Image.alpha_composite(canvas.convert("RGBA"), layer).convert("RGB")


# ---------------------------------------------------------------- encoding
def run(cmd, **kw):
    if cmd[0] == "ffmpeg":
        cmd = [get_ffmpeg()] + cmd[1:]
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + r.stderr[-1800:])
    return r


_VCODEC = None


def vencode():
    """Video codec args: NVENC (GPU) when available, else libx264."""
    global _VCODEC
    if _VCODEC is None:
        try:
            r = run(["ffmpeg", "-hide_banner", "-encoders"])
            if "h264_nvenc" in r.stdout:
                _VCODEC = ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq",
                           "-rc", "vbr", "-cq", "21", "-b:v", "0",
                           "-maxrate", "20M", "-bufsize", "40M",
                           "-pix_fmt", "yuv420p"]
            else:
                _VCODEC = ["-c:v", "libx264", "-preset", "veryfast",
                           "-crf", "19", "-pix_fmt", "yuv420p"]
        except Exception:
            _VCODEC = ["-c:v", "libx264", "-preset", "veryfast",
                       "-crf", "19", "-pix_fmt", "yuv420p"]
    return list(_VCODEC)


def encode_frames(dirpath, out, fps_in=10):
    run(["ffmpeg", "-y", "-framerate", str(fps_in), "-i",
         str(dirpath / "f_%04d.png"), *vencode(), "-r", str(FPS), str(out)])


def encode_hold(frame_png, out, dur, zoom=False):
    if zoom:
        vf = ("scale=3200:1800:flags=lanczos,"
              "zoompan=z='min(1.0+0.00018*on,1.07)'"
              ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d=1:s={W}x{H}:fps={FPS}")
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t",
             f"{dur:.3f}", "-i", str(frame_png), "-vf", vf, *vencode(),
             str(out)])
    else:
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-t",
             f"{dur:.3f}", "-i", str(frame_png), *vencode(), str(out)])


def concat(parts, out):
    lst = out.parent / (out.stem + "_list.txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts),
                   encoding="ascii")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", "-movflags", "+faststart", str(out)])


def tts(text, wav, voice, rate, ffmpeg):
    import edge_tts
    if wav.exists() and wav.stat().st_size > 1000:
        with wave.open(str(wav), "rb") as w:
            return w.getnframes() / w.getframerate()
    mp3 = wav.with_suffix(".mp3")

    async def once():
        c = edge_tts.Communicate(text, voice, rate=rate)
        await c.save(str(mp3))

    for attempt in range(6):
        try:
            asyncio.run(once())
            if mp3.exists() and mp3.stat().st_size > 500:
                break
        except Exception:
            if attempt == 5:
                raise
            time.sleep(min(30.0, 2.0 ** attempt))
    run([ffmpeg, "-y", "-i", str(mp3), "-ar", "44100", "-ac", "2", str(wav)])
    mp3.unlink()
    with wave.open(str(wav), "rb") as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- build
def _full_state(base, els, n, say):
    img = base.copy().convert("RGBA")
    for el in els[:n]:
        img = el(img, 1.0, 0.0)
    return subtitle_band(img.convert("RGB"), say)


def produce_beat(job):
    """Render + encode + mux one beat (runs in a worker process)."""
    (scene, beat, shown_prev, si, total, bdir, voice, rate) = job
    bdir = Path(bdir)
    bdir.mkdir(exist_ok=True)
    els = build_elements(scene)
    base = base_canvas(si, total, scene.get("title"))
    wav = bdir / "voice.wav"
    with wave.open(str(wav), "rb") as w:
        audio_dur = w.getnframes() / w.getframerate()
    seg_dur = DELAY + audio_dur + GAP
    show = beat.get("show", 0)
    new = els[shown_prev:show]
    shown_prev = show
    parts = []
    if scene["kind"] == "anim":
        anim_fn = ANIMS[scene["anim"]]
        n = max(8, int(seg_dur * 10))
        for fi in range(n):
            t = fi / max(1, n - 1)
            img = base.copy()
            d = ImageDraw.Draw(img)
            anim_fn(img, beat.get("anim_beat", 0), t, d)
            subtitle_band(img, beat["say"]).save(bdir / f"f_{fi:04d}.png")
        encode_frames(bdir, bdir / "v.mp4", fps_in=10)
        parts.append(bdir / "v.mp4")
    else:
        if new:
            for fi in range(1, REVEAL_F + 1):
                t = ease(fi / REVEAL_F)
                img = base.copy().convert("RGBA")
                for el in els[:shown_prev - len(new)]:
                    img = el(img, 1.0, 0.0)
                for el in new:
                    img = el(img, t, (1 - t) * 18)
                subtitle_band(img.convert("RGB"), beat["say"]).save(
                    bdir / f"f_{fi:04d}.png")
            encode_frames(bdir, bdir / "v1.mp4", fps_in=FPS)
            parts.append(bdir / "v1.mp4")
            _full_state(base, els, shown_prev, beat["say"]).save(
                bdir / "hold.png")
        else:
            _full_state(base, els, shown_prev, beat["say"]).save(bdir / "hold.png")
        hold_t = seg_dur - (REVEAL_F / FPS if new else 0)
        encode_hold(bdir / "hold.png", bdir / "v2.mp4", hold_t,
                    zoom=beat.get("zoom", False))
        parts.append(bdir / "v2.mp4")
        if len(parts) == 2:
            concat(parts, bdir / "v.mp4")
            parts = [bdir / "v.mp4"]
    seg = bdir / "seg.mp4"
    af = (f"adelay={int(DELAY*1000)}|{int(DELAY*1000)},"
          f"apad,atrim=0:{seg_dur:.3f},"
          f"afade=t=out:st={max(0.0, seg_dur-0.25):.3f}:d=0.25")
    run(["ffmpeg", "-y", "-i", str(parts[0]), "-i", str(wav),
         "-filter_complex", f"[1:a]{af}[a]", "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", str(seg)])
    return str(seg), seg_dur


def build_video(deck, out_path, voice="zh-CN-YunxiNeural", rate="-4%",
                log=True, workers=None):
    scenes = deck["scenes"]
    total = len(scenes)
    work = TMP / f"ch{deck['num']:02d}"
    work.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg()

    # phase 1 -- narration (network-bound, sequential, cached)
    jobs = []
    for si, scene in enumerate(scenes, start=1):
        for bi, beat in enumerate(scene["beats"]):
            bdir = work / f"s{si:02d}b{bi:02d}"
            bdir.mkdir(exist_ok=True)
            dur = tts(beat["say"], bdir / "voice.wav", voice, rate, ffmpeg)
            jobs.append([scene, beat, 0, si, total, str(bdir), voice, rate])
            if log:
                print(f"  [{deck['num']:02d}] tts scene {si}/{total} "
                      f"beat {bi+1}/{len(scene['beats'])} {dur:.1f}s", flush=True)

    # shown_prev = elements visible BEFORE this beat (fill in scene order)
    k = 0
    for si, scene in enumerate(scenes, start=1):
        prev = 0
        for _bi, beat in enumerate(scene["beats"]):
            jobs[k][2] = prev
            prev = beat.get("show", 0)
            k += 1

    workers = workers or min(6, os.cpu_count() or 4)
    segs, stamps, t_clock = [], [], 0.0
    ctx = mp.get_context("spawn")
    if workers > 1:
        with ctx.Pool(workers) as pool:
            for seg_s, seg_dur in pool.imap(produce_beat, jobs):
                segs.append(Path(seg_s))
                stamps.append(t_clock + seg_dur / 2)
                t_clock += seg_dur
                if log:
                    print(f"  [{deck['num']:02d}] seg {len(segs)}/{len(jobs)} "
                          f"{seg_dur:.1f}s", flush=True)
    else:
        for job in jobs:
            seg_s, seg_dur = produce_beat(job)
            segs.append(Path(seg_s))
            stamps.append(t_clock + seg_dur / 2)
            t_clock += seg_dur
    concat(segs, out_path)
    return t_clock, stamps


def qa_sheet(mp4, times, out_png):
    frames = []
    tmp = out_png.parent / "_qa_f.png"
    for t in times:
        run(["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1",
             "-q:v", "3", str(tmp)])
        frames.append(Image.open(tmp).resize((480, 270), Image.LANCZOS))
    tmp.unlink(missing_ok=True)
    cols = 4
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cols * 484, rows * 274), (255, 255, 255))
    for i, fr in enumerate(frames):
        sheet.paste(fr, ((i % cols) * 484 + 2, (i // cols) * 274 + 2))
    sheet.save(out_png)
