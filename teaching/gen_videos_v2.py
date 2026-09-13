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
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from video_engine_v2 import (TMP, QA, build_video, qa_sheet,  # noqa
                             qa_sheet_from_video, vencode)
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
    ap.add_argument("--sheets-only", action="store_true",
                    help="只从已渲染的 mp4 重建质检图 (等间隔抽帧), 不重新编码、"
                         "不需要 TTS 联网; 用于补回缺失/损坏的质检图")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)

    if args.sheets_only:
        # 只补质检图: 视频必须在, 缺视频说明该章根本没渲染过, 直接报错。
        want = None
        if args.ch not in ("all", "missing"):
            want = {int(x) for x in re.split(r"[,\s]+", args.ch) if x}
        todo = [d for d in DECKS if want is None or d["num"] in want]
        missing_mp4 = [d["num"] for d in todo
                       if not (OUT_DIR / f"ch{d['num']:02d}.mp4").exists()]
        if missing_mp4:
            print("以下章节没有 mp4, 无法只补质检图 (需完整重跑): "
                  + ",".join(str(n) for n in missing_mp4), flush=True)
            sys.exit(1)
        for deck in todo:
            num = deck["num"]
            mp4 = OUT_DIR / f"ch{num:02d}.mp4"
            out_png = QA / f"v2_ch{num:02d}_sheet.png"
            times = qa_sheet_from_video(mp4, out_png)
            print(f"[ch{num:02d}] 质检图已重建 {out_png.name} "
                  f"({len(times)} 帧, 等间隔)", flush=True)
        return

    if args.ch == "all":
        todo = DECKS
    elif args.ch == "missing":
        done = {m["num"] for m in json.loads(DUR.read_text("utf-8"))} \
            if DUR.exists() else set()
        todo = [d for d in DECKS if d["num"] not in done]
    else:
        want = {int(x) for x in re.split(r"[,\s]+", args.ch) if x}
        todo = [d for d in DECKS if d["num"] in want]

    # 单章失败不得中断其余章节: 历史上 ch02 (空质检图) 与 ch07 (缺质检图) 就是
    # 这样被静默漏掉的 —— 一次异常让后面所有章节都没跑, 而早已在 durations.json
    # 里的章节又永远不会被 '--ch missing' 重试。失败的章节**不**写回元数据,
    # 这样它仍是 missing, 下次能自动重试。
    failures = []
    for deck in todo:
        num = deck["num"]
        out = OUT_DIR / f"ch{num:02d}.mp4"
        try:
            print(f"[ch{num:02d}] building: {deck['title']} "
                  f"(encoder: {'h264_nvenc' if 'nvenc' in vencode()[1] else 'libx264'})",
                  flush=True)
            dur_s, stamps = build_video(deck, out, voice=args.voice, rate=args.rate,
                                        workers=args.workers)
            qa_sheet(out, stamps, QA / f"v2_ch{num:02d}_sheet.png")
            update_meta(deck, dur_s, len(stamps))
            mm, ss = divmod(int(round(dur_s)), 60)
            print(f"[ch{num:02d}] done {out.name} {mm}:{ss:02d} "
                  f"({len(stamps)} beats)", flush=True)
        except Exception as exc:  # noqa: BLE001 - 逐章隔离, 最后统一汇总
            failures.append((num, deck["title"], repr(exc)))
            print(f"[ch{num:02d}] FAILED: {exc!r}", flush=True)
            traceback.print_exc()

    if failures:
        print(f"\n{len(failures)}/{len(todo)} 章失败:", flush=True)
        for num, title, err in failures:
            print(f"  ch{num:02d} {title}: {err}", flush=True)
        print("重试: python teaching/gen_videos_v2.py --ch "
              + ",".join(str(n) for n, _, _ in failures), flush=True)
        sys.exit(1)
    print(f"\n全部完成: {len(todo)} 章", flush=True)


if __name__ == "__main__":
    main()
