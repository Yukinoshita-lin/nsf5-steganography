# -*- coding: utf-8 -*-
"""Build the official (v2) narrated & animated teaching videos.

Usage:
  python teaching/gen_videos_v2.py                 # all missing chapters
  python teaching/gen_videos_v2.py --ch 3,5        # rebuild selected chapters
  python teaching/gen_videos_v2.py --ch all        # force-rebuild everything
  python teaching/gen_videos_v2.py --voice zh-CN-XiaoxiaoNeural
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video_engine_v2 import TMP, QA, build_video, qa_sheet, vencode  # noqa
from video_scenes_zh import DECKS  # noqa: E402
from gen_videos import OUT_DIR, build_index  # noqa: E402

DUR = OUT_DIR / "durations.json"


def update_meta(deck, dur_s, n_beats):
    meta = json.loads(DUR.read_text("utf-8")) if DUR.exists() else []
    by_num = {m["num"]: m for m in meta}
    mm, ss = divmod(int(round(dur_s)), 60)
    by_num[deck["num"]] = dict(num=deck["num"], title=deck["title"],
                               weeks=deck["weeks"], file=f"ch{deck['num']:02d}.mp4",
                               slides=n_beats, dur=f"{mm}:{ss:02d}")
    meta = [by_num[k] for k in sorted(by_num)]
    DUR.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    build_index(OUT_DIR, meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ch", default="missing",
                    help="'missing' (default), 'all', or comma list like 3,5")
    ap.add_argument("--voice", default="zh-CN-YunxiNeural")
    ap.add_argument("--rate", default="-4%")
    ap.add_argument("--workers", type=int, default=6,
                    help="parallel beat producers (GPU NVENC + CPU render)")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)

    if args.ch == "all":
        todo = DECKS
    elif args.ch == "missing":
        done = {m["num"] for m in json.loads(DUR.read_text("utf-8"))} \
            if DUR.exists() else set()
        todo = [d for d in DECKS if d["num"] not in done]
    else:
        want = {int(x) for x in re.split(r"[,\s]+", args.ch) if x}
        todo = [d for d in DECKS if d["num"] in want]

    for deck in todo:
        out = OUT_DIR / f"ch{deck['num']:02d}.mp4"
        print(f"[ch{deck['num']:02d}] building: {deck['title']} "
              f"(encoder: {'h264_nvenc' if 'nvenc' in vencode()[1] else 'libx264'})",
              flush=True)
        dur_s, stamps = build_video(deck, out, voice=args.voice, rate=args.rate,
                                    workers=args.workers)
        qa_sheet(out, stamps, QA / f"v2_ch{deck['num']:02d}_sheet.png")
        update_meta(deck, dur_s, len(stamps))
        mm, ss = divmod(int(round(dur_s)), 60)
        print(f"[ch{deck['num']:02d}] done {out.name} {mm}:{ss:02d} "
              f"({len(stamps)} beats)", flush=True)


if __name__ == "__main__":
    main()
