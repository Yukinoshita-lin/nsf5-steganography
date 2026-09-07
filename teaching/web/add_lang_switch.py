"""Inject a cross-language switch link into every generated handbook page.

Pages live at ``/zh/content/*.html`` and ``/en/content/*.html``; from any page
the relative link ``../../<other-lang>/content/<same-name>.html`` switches to
the same page (chapter/appendix/intro) in the other language.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
PAIRS = [("zh", "en"), ("en", "zh")]
LABELS = {"zh": "🌐 English version", "en": "🌐 中文版"}
MARK = "<!-- lang-switch -->"


def inject(content_dir: pathlib.Path, other: str, label: str) -> int:
    changed = 0
    for p in sorted(content_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if MARK in text:
            continue
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith("# "):
                link = f"../../{other}/content/{p.name}"
                block = (
                    f"\n{MARK}\n> [{label}]({link})\n\n"
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
