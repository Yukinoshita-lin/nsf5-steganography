"""Download public datasets used by the teaching notebooks.

Currently supports BOSSbase 1.01 (10,000 512x512 grayscale PGM images), the
standard benchmark for steganalysis. The archive is large (~1.6 GB), so the
script streams the download and resumes nothing - keep the connection stable.

Usage:
    python scripts/download_datasets.py --out data/BOSSbase_1.01
    python scripts/download_datasets.py --out data/BOSSbase_1.01 --url <mirror>
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
import zipfile

DEFAULT_URL = "https://dde.binghamton.edu/download/BOSSbase_1.01.zip"


def download(url: str, dest_zip: str) -> None:
    tmp = dest_zip + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "nsf5-teaching/1.0"})
    with urllib.request.urlopen(req) as src, open(tmp, "wb") as out:
        total = int(src.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // max(total, 1)
                print(f"\r  downloaded {done / 1e6:.1f} / {total / 1e6:.1f} MB "
                      f"({pct}%)", end="", flush=True)
    print()
    os.replace(tmp, dest_zip)


def extract(zip_path: str, out_dir: str) -> int:
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            if member.is_dir() or not member.filename.lower().endswith(".pgm"):
                continue
            target = os.path.join(out_dir, os.path.basename(member.filename))
            with zf.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
            count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/BOSSbase_1.01",
                    help="Directory where .pgm files are extracted")
    ap.add_argument("--url", default=DEFAULT_URL, help="BOSSbase zip mirror URL")
    ap.add_argument("--zip", default=None,
                    help="Keep the downloaded zip at this path (default: next to --out)")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    existing = [f for f in os.listdir(out_dir)
                if f.lower().endswith(".pgm")] if os.path.isdir(out_dir) else []
    if len(existing) >= 1000:
        print(f"[skip] {out_dir} already has {len(existing)} .pgm files")
        return 0

    zip_path = args.zip or os.path.join(os.path.dirname(out_dir),
                                        os.path.basename(out_dir) + ".zip")
    print(f"[1/2] downloading {args.url}")
    download(args.url, zip_path)
    print(f"[2/2] extracting PGM files to {out_dir}")
    n = extract(zip_path, out_dir)
    print(f"done: {n} PGM images in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
