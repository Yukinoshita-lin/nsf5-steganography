# -*- coding: utf-8 -*-
"""Legacy static-slide video generator (superseded by gen_videos_v2.py).

Pipeline (Windows-oriented, offline):
  1. Render each slide (deck in video_decks_zh.py) to a 1920x1080 PNG (Pillow).
  2. Synthesize zh-CN narration per slide with Windows SAPI (Microsoft Huihui)
     via PowerShell -> WAV.
  3. Build one H.264/AAC segment per slide (image + narration, gentle fades)
     with ffmpeg (NSF5_FFMPEG env / %USERNAME%\\.zcode\\bin / PATH /
     imageio-ffmpeg), then concat -c copy.

Usage:
  python teaching/gen_videos.py                 # build all 11 chapters + index
  python teaching/gen_videos.py --only 3,5      # rebuild selected chapters
  python teaching/gen_videos.py --index-only    # just rebuild index.html

Outputs: teaching/videos/zh/chNN.mp4, index.html, durations.json (+ _tmp/, qa/).
"""
import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video_decks_zh import DECKS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "teaching" / "videos" / "zh"
TMP_DIR = ROOT / "teaching" / "videos" / "_tmp"
QA_DIR = ROOT / "teaching" / "videos" / "qa"

W, H = 1920, 1080
FPS = 24
LEAD, TAIL = 0.55, 0.9          # silence before / after narration (s)
SERIES = "nsF5 隐写教学系列 · 中文讲解"

BG = (246, 247, 251)
TEXT = (28, 34, 51)
MUTED = (96, 106, 128)
ACCENT = (61, 90, 241)
ACCENT_DARK = (38, 58, 180)
ACCENT_SOFT = (226, 231, 250)
TEAL = (13, 148, 136)
CODE_BG = (22, 27, 38)
CODE_FG = (232, 237, 245)
CODE_COMMENT = (134, 201, 147)
LINE = (218, 224, 238)

FONT_DIR = Path("C:/Windows/Fonts")


def _font(name, size, index=0):
    return ImageFont.truetype(str(FONT_DIR / name), size, index=index)


def fonts(size):
    """YaHei regular/bold pair at a given size."""
    return (_font("msyh.ttc", size), _font("msyhbd.ttc", size))


def mono_fonts(size):
    return (_font("consola.ttf", size), _font("msyh.ttc", int(size * 0.94)))


def get_ffmpeg():
    """Locate ffmpeg without C:-drive project artifacts:
    env NSF5_FFMPEG -> D:\\Users\\<user>\\.zcode\\bin -> PATH -> imageio-ffmpeg."""
    candidates = (
        os.environ.get("NSF5_FFMPEG"),
        Path("D:/Users") / os.environ.get("USERNAME", "") / ".zcode" / "bin"
        / "ffmpeg.exe",
        shutil.which("ffmpeg"),
    )
    for cand in candidates:
        if cand and Path(cand).exists():
            return str(cand)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    sys.exit("ffmpeg not found: set NSF5_FFMPEG, or place a binary at "
             r"D:\Users\<you>\.zcode\bin\ffmpeg.exe")


# ---------------------------------------------------------------- text utils
def tokenize(text):
    """Split into latin runs + single CJK chars so wrapping keeps words intact."""
    tokens, buf = [], ""
    for ch in text:
        if ord(ch) < 0x2E80 and not ch.isspace() or ch == " ":
            buf += ch
        else:
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
    if buf:
        tokens.append(buf)
    return tokens


def wrap(draw, text, font, maxw):
    lines, cur = [], ""
    for tok in tokenize(text):
        trial = cur + tok
        if cur and draw.textlength(trial, font=font) > maxw:
            lines.append(cur.rstrip())
            cur = tok.lstrip() if tok.strip() else ""
        else:
            cur = trial
    if cur.strip():
        lines.append(cur.rstrip())
    return lines or [""]


def rich_lead(text):
    """('lead', 'rest') when a short '…：' lead-in should be bolded."""
    if "：" in text:
        lead, rest = text.split("：", 1)
        if 0 < len(lead) <= 14 and rest:
            return lead + "：", rest
    return None, text


# ---------------------------------------------------------------- slide chrome
def chrome(draw, deck, idx, total, label):
    draw.rectangle([0, 0, W, 6], fill=ACCENT)
    f_small, _ = fonts(26)
    draw.text((70, 22), SERIES, font=f_small, fill=MUTED)
    draw.text((W - 70 - draw.textlength(label, font=f_small), 22),
              label, font=f_small, fill=MUTED)
    # footer
    left = f"{deck['num']:02d} · {deck['title']}"
    f_foot, _ = fonts(25)
    draw.text((70, H - 52), left, font=f_foot, fill=MUTED)
    page = f"{idx + 1:02d} / {total:02d}"
    draw.text((W - 70 - draw.textlength(page, font=f_foot), H - 52),
              page, font=f_foot, fill=MUTED)
    # progress bar
    frac = (idx + 1) / total
    draw.rectangle([0, H - 10, W, H], fill=(226, 230, 240))
    draw.rectangle([0, H - 10, int(W * frac), H], fill=ACCENT)


def slide_title_card(deck):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_series, _ = fonts(30)
    t = SERIES
    d.text(((W - d.textlength(t, font=f_series)) / 2, 200), t,
           font=f_series, fill=MUTED)

    f_pill, _ = fonts(42)
    pill = f"第 {deck['num']} 章"
    pw = d.textlength(pill, font=f_pill) + 88
    x0, y0 = (W - pw) / 2, 350
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + 86], radius=43, fill=ACCENT)
    d.text(((W - d.textlength(pill, font=f_pill)) / 2, y0 + 16),
           pill, font=f_pill, fill=(255, 255, 255))

    f_big, _ = fonts(78)
    f_mid, _ = fonts(64)
    title, f_use = deck["title"], f_big
    while d.textlength(title, font=f_use) > W - 320 and f_use.size > 52:
        f_use, _ = fonts(f_use.size - 6)
    d.text(((W - d.textlength(title, font=f_use)) / 2, 500),
           title, font=f_use, fill=TEXT)

    f_week, _ = fonts(38)
    d.text(((W - d.textlength(deck["weeks"], font=f_week)) / 2, 640),
           deck["weeks"], font=f_week, fill=MUTED)

    # LSB-bit decorative strip (pseudorandom, seeded per chapter)
    rnd = random.Random(1000 + deck["num"])
    n, size, gap = 72, 16, 8
    total_w = n * (size + gap) - gap
    x = (W - total_w) / 2
    for i in range(n):
        on = rnd.random() < 0.45
        color = ACCENT if on else ACCENT_SOFT
        d.rounded_rectangle([x, 830, x + size, 830 + size], radius=4, fill=color)
        x += size + gap
    f_hint, _ = fonts(26)
    hint = "配套双语手册 · teaching/web · 每章配 Colab 笔记本"
    d.text(((W - d.textlength(hint, font=f_hint)) / 2, 905), hint,
           font=f_hint, fill=MUTED)
    d.rectangle([0, 0, W, 6], fill=ACCENT)
    d.rectangle([0, H - 10, W, H], fill=ACCENT)
    return img


def slide_close_card(deck):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    chrome(d, deck, len(deck["slides"]) + 1, len(deck["slides"]) + 2,
           "想一想 · 收尾")
    f_pill, _ = fonts(40)
    pill = "想一想"
    pw = d.textlength(pill, font=f_pill) + 84
    x0 = (W - pw) / 2
    d.rounded_rectangle([x0, 240, x0 + pw, 240 + 82], radius=41, fill=TEAL)
    d.text(((W - d.textlength(pill, font=f_pill)) / 2, 254), pill,
           font=f_pill, fill=(255, 255, 255))

    f_q, _ = fonts(46)
    lines = wrap(d, deck["question"], f_q, 1480)
    y = 420 - (len(lines) - 1) * 34
    for ln in lines:
        d.text(((W - d.textlength(ln, font=f_q)) / 2, y), ln, font=f_q, fill=TEXT)
        y += 72

    f_label, _ = fonts(28)
    if deck.get("next"):
        lab = "下一章预告"
        d.text(((W - d.textlength(lab, font=f_label)) / 2, 700), lab,
               font=f_label, fill=TEAL)
        f_n, _ = fonts(38)
        d.text(((W - d.textlength(deck["next"], font=f_n)) / 2, 752),
               deck["next"], font=f_n, fill=MUTED)
    else:
        lab = "本系列完 · 感谢观看"
        d.text(((W - d.textlength(lab, font=f_label)) / 2, 726), lab,
               font=f_label, fill=TEAL)
    return img


def render_bullets(d, bullets, x0, y0, maxw, maxh):
    """Draw bullet list with auto-shrink; returns bottom y."""
    for size in (42, 39, 36, 33, 30):
        fr, fb = fonts(size)
        lh = int((fr.getmetrics()[0] + fr.getmetrics()[1]) * 1.28)
        gap = int(size * 0.5)
        blocks = []
        for b in bullets:
            lvl = b.startswith("~")
            text = b[1:] if lvl else b
            w_max = maxw - (44 if not lvl else 74)
            lines = wrap(d, text, fr, w_max)
            blocks.append((lvl, lines))
        total = sum(len(ls) * lh for _, ls in blocks) + gap * (len(blocks) - 1)
        if total <= maxh or size == 30:
            y = y0 + max(0, (maxh - total) // 3)   # slight top bias
            for lvl, lines in blocks:
                if lvl:
                    d.rectangle([x0 + 34, y + lh * 0.42, x0 + 52, y + lh * 0.42 + 5],
                                fill=ACCENT)
                    bx = x0 + 74
                else:
                    d.ellipse([x0 + 12, y + lh * 0.38, x0 + 30, y + lh * 0.38 + 18],
                              fill=ACCENT)
                    bx = x0 + 44
                for j, ln in enumerate(lines):
                    lead, rest = rich_lead(ln) if j == 0 else (None, ln)
                    cx = bx
                    if lead:
                        d.text((cx, y), lead, font=fb, fill=ACCENT_DARK)
                        cx += d.textlength(lead, font=fb)
                    d.text((cx, y), rest, font=fr, fill=TEXT)
                    y += lh
                y += gap
            return y
    raise AssertionError


def slide_content(deck, idx, slide, assets_dir):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    label = {"bullets": "讲解", "code": "代码", "side": "图解", "full": "图解"}
    chrome(d, deck, idx + 1, len(deck["slides"]) + 2,
           label.get(slide.get("layout", "bullets"), "讲解"))

    # slide title
    f_t, _ = fonts(50)
    title = slide["t"]
    while d.textlength(title, font=f_t) > W - 300 and f_t.size > 38:
        f_t, _ = fonts(f_t.size - 4)
    d.rectangle([70, 84, 84, 84 + 62], fill=ACCENT)
    d.text((110, 84), title, font=f_t, fill=TEXT)

    y0 = 210
    bottom = 960
    layout = slide.get("layout", "bullets")

    if layout == "bullets":
        render_bullets(d, slide["bullets"], 90, y0 + 20, W - 190, bottom - y0)
    elif layout == "code":
        mono_r, cjk_r = mono_fonts(30)
        lh = 48
        lines = slide["code"]
        box_h = len(lines) * lh + 64
        max_lines = int((bottom - y0 - 70) / lh)
        if len(lines) > max_lines:            # shrink
            mono_r, cjk_r = mono_fonts(26)
            lh = 42
            box_h = len(lines) * lh + 56
        d.rounded_rectangle([90, y0, W - 90, y0 + box_h], radius=18, fill=CODE_BG)
        if slide.get("caption"):
            f_cap, _ = fonts(27)
            d.text((96, y0 + box_h + 18), "备注：" + slide["caption"],
                   font=f_cap, fill=MUTED)
        y = y0 + 32
        for ln in lines:
            x = 130
            if "#" in ln:
                cut = ln.index("#")
                head, comment = ln[:cut], ln[cut:]
            else:
                head, comment = ln, ""
            for ch in head:                   # mixed mono/CJK rendering
                f = cjk_r if ord(ch) > 0x2E80 else mono_r
                d.text((x, y), ch, font=f, fill=CODE_FG)
                x += d.textlength(ch, font=f)
            for ch in comment:
                f = cjk_r if ord(ch) > 0x2E80 else mono_r
                d.text((x, y), ch, font=f, fill=CODE_COMMENT)
                x += d.textlength(ch, font=f)
            y += lh
    elif layout in ("side", "full"):
        name = Path(slide["img"]).name
        full = layout == "full"
        if not full:      # wide figures read better full-width
            probe = load_figure(assets_dir / name, (0, 0, 760, 690))
            full = probe.width / probe.height > 1.55
        if full:
            box = (95, y0, W - 95, 872)
            fig = load_figure(assets_dir / name, box)
            fx = box[0] + (box[2] - box[0] - fig.width) // 2
            img.paste(fig, (fx, box[1]))
            d.rectangle([fx, box[1], fx + fig.width, box[1] + fig.height],
                        outline=LINE, width=2)
            fig_bottom = box[1] + fig.height
            cap_w = box[2] - box[0]
        else:
            box = (1010, y0, W - 95, 900)
            fig = load_figure(assets_dir / name, box)
            fx = box[0] + (box[2] - box[0] - fig.width) // 2
            fy = box[1] + max(0, (box[3] - box[1] - fig.height) // 2 - 30)
            img.paste(fig, (fx, fy))
            d.rectangle([fx, fy, fx + fig.width, fy + fig.height],
                        outline=LINE, width=2)
            fig_bottom = fy + fig.height
            cap_w = fig.width
            if slide.get("bullets"):
                render_bullets(d, slide["bullets"], 90, y0 + 20, 810, bottom - y0)
        if slide.get("caption"):
            f_cap, _ = fonts(26)
            cy = fig_bottom + 16
            for ln in wrap(d, slide["caption"], f_cap, cap_w)[:2]:
                cx = fx + (cap_w - d.textlength(ln, font=f_cap)) / 2
                d.text((cx, cy), ln, font=f_cap, fill=MUTED)
                cy += 36
    return img


def load_figure(path, box):
    fig = Image.open(path)
    if fig.mode in ("RGBA", "LA", "P"):
        fig = fig.convert("RGBA")
        base = Image.new("RGB", fig.size, (255, 255, 255))
        base.paste(fig, mask=fig.split()[-1])
        fig = base
    else:
        fig = fig.convert("RGB")
    bw, bh = box[2] - box[0], box[3] - box[1]
    scale = min(bw / fig.width, bh / fig.height)
    if scale < 1:
        fig = fig.resize((int(fig.width * scale), int(fig.height * scale)),
                         Image.LANCZOS)
    return fig


# ---------------------------------------------------------------- TTS (SAPI)
PS_TTS = r"""
param([string]$List)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice('Microsoft Huihui Desktop')
$s.Rate = {rate}
$lines = [System.IO.File]::ReadAllLines($List, [System.Text.Encoding]::UTF8)
foreach ($line in $lines) {{
  if ($line.Trim().Length -eq 0) {{ continue }}
  $i = $line.IndexOf("`t")
  if ($i -lt 0) {{ continue }}
  $txtPath = $line.Substring(0, $i)
  $wavPath = $line.Substring($i + 1)
  $txt = [System.IO.File]::ReadAllText($txtPath, [System.Text.Encoding]::UTF8)
  $s.SetOutputToWaveFile($wavPath)
  $s.Speak($txt)
  $s.SetOutputToNull()
}}
$s.Dispose()
Write-Output 'TTS-DONE'
"""


def tts_batch(items, workdir, rate):
    """items: list of (name, text). Returns {name: wav_path}."""
    list_path = workdir / "tts_list.txt"
    ps1 = workdir / "tts_run.ps1"
    lines = []
    for name, text in items:
        txt = workdir / f"{name}.txt"
        wav = workdir / f"{name}.wav"
        txt.write_text(text, encoding="utf-8")
        if wav.exists():
            wav.unlink()
        lines.append(f"{txt}\t{wav}")
    list_path.write_text("\n".join(lines), encoding="utf-8-sig")
    ps1.write_text(PS_TTS.format(rate=rate), encoding="utf-8-sig")
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(ps1), "-List", str(list_path)],
        capture_output=True, text=True, timeout=600)
    if "TTS-DONE" not in (r.stdout or ""):
        raise RuntimeError(f"TTS failed: {r.stdout}\n{r.stderr}")
    return {name: workdir / f"{name}.wav" for name, _ in items}


def wav_duration(path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


# ---------------------------------------------------------------- assembly
def build_segment(ffmpeg, png, wav, out, dur, fade_in, fade_out):
    vf = (f"scale={W}:{H}:flags=lanczos,format=yuv420p,"
          f"fade=t=in:st=0:d={fade_in:.2f},"
          f"fade=t=out:st={max(0.0, dur - fade_out):.2f}:d={fade_out:.2f}")
    af = ("aformat=sample_rates=44100:channel_layouts=stereo,"
          f"adelay={int(LEAD * 1000)}|{int(LEAD * 1000)},"
          f"apad,atrim=0:{dur:.3f},"
          f"afade=t=out:st={max(0.0, dur - 0.4):.2f}:d=0.4")
    cmd = [ffmpeg, "-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}",
           "-i", str(png), "-i", str(wav),
           "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
           "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg segment failed:\n{r.stderr[-2000:]}")


def probe_duration(ffmpeg, mp4):
    r = subprocess.run([ffmpeg, "-i", str(mp4)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", r.stderr)
    if not m:
        return None
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def build_chapter(deck, ffmpeg, out_dir, tmp_root, rate):
    ch = f"ch{deck['num']:02d}"
    work = tmp_root / ch
    work.mkdir(parents=True, exist_ok=True)
    # figures live in the handbook asset dir
    assets = Path(__file__).resolve().parent / "web" / "zh" / "assets"

    # 1) slides
    slides = [("title", slide_title_card(deck))]
    for i, s in enumerate(deck["slides"]):
        slides.append((f"s{i:02d}", slide_content(deck, i, s, assets)))
    slides.append(("close", slide_close_card(deck)))

    names = [n for n, _ in slides]
    for name, im in slides:
        im.save(work / f"slide_{name}.png")

    # 2) narration
    narr = [deck["say_intro"]] + [s["say"] for s in deck["slides"]] + [deck["say_close"]]
    wavs = tts_batch(list(zip(names, narr)), work, rate)

    # 3) segments
    seg_files, times = [], []
    total = len(names)
    for i, name in enumerate(names):
        wav = wavs[name]
        dur = LEAD + (wav_duration(wav) if wav.exists() else 2.0) + TAIL
        seg = work / f"seg_{i:02d}.mp4"
        build_segment(ffmpeg, work / f"slide_{name}.png", wav, seg, dur,
                      fade_in=0.9 if i == 0 else 0.4,
                      fade_out=1.1 if i == total - 1 else 0.4)
        seg_files.append(seg)
        times.append(dur)

    lst = work / "concat.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in seg_files),
                   encoding="utf-8")
    out = out_dir / f"{ch}.mp4"
    r = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i",
                        str(lst), "-c", "copy", "-movflags", "+faststart",
                        str(out)], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"concat failed:\n{r.stderr[-2000:]}")
    dur = probe_duration(ffmpeg, out)
    return out, times, dur


def qa_sheet(mp4, times, out_png, ffmpeg):
    """Extract one frame per slide and tile into a contact sheet."""
    frames = []
    t0 = 0.0
    for dur in times:
        t = t0 + min(dur * 0.6, max(dur - 1.0, 0.2))
        tmp = out_png.with_name(out_png.stem + "_f.png")
        subprocess.run([ffmpeg, "-y", "-ss", f"{t:.2f}", "-i", str(mp4),
                        "-frames:v", "1", "-q:v", "3", str(tmp)],
                       capture_output=True, text=True)
        if tmp.exists():
            frames.append(Image.open(tmp).resize((480, 270), Image.LANCZOS))
            tmp.unlink()
        t0 += dur
    if not frames:
        return
    cols = 3
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cols * 484, rows * 274), (255, 255, 255))
    for i, fr in enumerate(frames):
        sheet.paste(fr, ((i % cols) * 484 + 2, (i // cols) * 274 + 2))
    sheet.save(out_png)


# ---------------------------------------------------------------- index page
def build_index(out_dir, meta):
    cards = []
    for m in meta:
        cards.append(f"""
    <div class="card">
      <video controls preload="metadata" src="{m['file']}"></video>
      <div class="body">
        <div class="num">第 {m['num']} 章 · {m['weeks']}</div>
        <h3>{m['title']}</h3>
        <div class="meta">{m['slides']} 页幻灯 · 时长 {m['dur']}</div>
      </div>
    </div>""")
    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<title>nsF5 隐写教学系列 · 章节视频</title>
<style>
  :root {{ --accent:#3d5af1; --bg:#f6f7fb; --text:#1c2233; --muted:#606a80; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
         font-family:"Microsoft YaHei",system-ui,sans-serif; }}
  header {{ background:linear-gradient(120deg,#263ab4,#3d5af1); color:#fff;
            padding:52px 8vw 40px; }}
  header h1 {{ margin:0 0 8px; font-size:30px; }}
  header p {{ margin:0; opacity:.85; }}
  main {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr));
          gap:22px; padding:32px 8vw 60px; }}
  .card {{ background:#fff; border-radius:14px; overflow:hidden;
           box-shadow:0 2px 10px rgba(28,34,51,.08); }}
  .card video {{ width:100%; aspect-ratio:16/9; background:#000; display:block; }}
  .body {{ padding:14px 18px 18px; }}
  .num {{ color:var(--accent); font-size:13px; font-weight:700; }}
  h3 {{ margin:4px 0 6px; font-size:18px; }}
  .meta {{ color:var(--muted); font-size:13px; }}
</style></head><body>
<header><h1>nsF5 隐写教学系列 · 章节视频</h1>
<p>与双语学习手册配套的第 1–11 章讲解视频 · 由 teaching/gen_videos.py 生成</p></header>
<main>{''.join(cards)}
</main></body></html>"""
    (out_dir / "index.html").write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="", help="comma list of chapter numbers")
    ap.add_argument("--rate", type=int, default=-1,
                    help="SAPI TTS rate (-10..10; default -1, teaching pace)")
    ap.add_argument("--no-qa", action="store_true")
    ap.add_argument("--index-only", action="store_true")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg()

    if args.index_only:
        meta = json.loads((OUT_DIR / "durations.json").read_text("utf-8"))
        build_index(OUT_DIR, meta)
        print(f"index rebuilt -> {OUT_DIR / 'index.html'}")
        return

    decks = DECKS
    if args.only:
        want = {int(x) for x in re.split(r"[,\s]+", args.only) if x}
        decks = [d for d in DECKS if d["num"] in want]

    meta = []
    for deck in decks:
        ch = f"ch{deck['num']:02d}"
        print(f"[{ch}] rendering {deck['title']} ...", flush=True)
        out, times, dur = build_chapter(deck, ffmpeg, OUT_DIR, TMP_DIR, args.rate)
        if not args.no_qa:
            qa_sheet(out, times, QA_DIR / f"{ch}_sheet.png", ffmpeg)
        mm, ss = divmod(int(round(dur or 0)), 60)
        print(f"[{ch}] done  {out.name}  {mm}:{ss:02d}  "
              f"({len(times)} slides)", flush=True)
        meta.append(dict(num=deck["num"], title=deck["title"],
                         weeks=deck["weeks"], file=out.name,
                         slides=len(times),
                         dur=f"{mm}:{ss:02d}"))

    prev = {m["num"]: m for m in
            json.loads((OUT_DIR / "durations.json").read_text("utf-8"))} \
        if (OUT_DIR / "durations.json").exists() else {}
    for m in meta:
        prev[m["num"]] = m
    meta = [prev[k] for k in sorted(prev)]
    (OUT_DIR / "durations.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    build_index(OUT_DIR, meta)
    print(f"all done -> {OUT_DIR}")


if __name__ == "__main__":
    main()
