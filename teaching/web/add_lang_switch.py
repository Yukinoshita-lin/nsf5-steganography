"""Inject a cross-language switch link into every generated handbook page.

MyST renders bare ``.md`` relative links to files outside the current book as
an unresolved xref (a plain span), so we use absolute GitHub Pages URLs, which
Jupyter Book reliably emits as real anchors.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
PAIRS = [("zh", "en"), ("en", "zh")]
LABELS = {"zh": "🌐 English version", "en": "🌐 中文版"}
MARK = "<!-- lang-switch -->"
BASE = "https://yukinoshita-lin.github.io/nsf5-steganography"

# 旧标记块 (含前后空行) 整块匹配, 替换后与正文之间恰好一个空行 —— 幂等。
BLOCK_RE = re.compile(r"\n*<!-- lang-switch -->\n> \[🌐[^\]]*\]\([^)]*\)\n*")


def inject(content_dir: pathlib.Path, other: str, label: str) -> int:
    changed = 0
    for p in sorted(content_dir.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        text = BLOCK_RE.sub("\n\n", text)
        # 对面书还没有这一页时 (例如 zh 2026-10 新增的第 12 章 / 附录 J-L 尚未
        # 翻成英文) 只清旧标记、不注入 —— 绝对链接指过去就是 404。
        target_page = ROOT / other / "content" / (p.stem + ".md")
        m = re.search(r"^# .*$", text, re.M)
        if m and target_page.exists():
            target = f"{other}/content/{p.stem}.html"
            ins = f"\n\n{MARK}\n> [{label}]({BASE}/{target})\n\n"
            text = text[:m.end()] + ins + text[m.end():]
            changed += 1
        p.write_text(text, encoding="utf-8")
    return changed


def main():
    for lang, other in PAIRS:
        n = inject(ROOT / lang / "content", other, LABELS[lang])
        print(f"{lang}: updated {n} pages")


if __name__ == "__main__":
    main()
