"""Inject a cross-language switch link into every generated handbook page.

MyST renders bare ``.md`` relative links to files outside the current book as
an unresolved xref (a plain span), so we use absolute GitHub Pages URLs, which
Jupyter Book reliably emits as real anchors.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
PAIRS = [("zh", "en"), ("en", "zh")]
LABELS = {"zh": "🌐 English version", "en": "🌐 中文版"}
MARK = "<!-- lang-switch -->"
BASE = "https://yukinoshita-lin.github.io/nsf5-steganography"


def inject(content_dir: pathlib.Path, other: str, label: str) -> int:
    changed = 0
    for p in sorted(content_dir.glob("*.md")):
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        # drop any previous injected switch block
        lines = [ln for ln in lines
                 if MARK not in ln and not ln.lstrip().startswith("> [🌐")]
        for i, line in enumerate(lines):
            if line.startswith("# "):
                target = f"{other}/content/{p.name[:-3]}.html"
                block = (
                    f"\n{MARK}\n> [{label}]({BASE}/{target})\n\n"
                )
                lines.insert(i + 1, block)
                p.write_text("".join(lines), encoding="utf-8")
                changed += 1
                break
    return changed


def main():
    for lang, other in PAIRS:
        n = inject(ROOT / lang / "content", other, LABELS[lang])
        print(f"{lang}: updated {n} pages")


if __name__ == "__main__":
    main()
