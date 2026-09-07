"""Convert the bilingual DOCX handbooks into Jupyter Book markdown.

Usage:
    python teaching/web/docx2md.py \
        --docx "thesis/学习手册-从零读懂nsF5隐写项目.docx" \
        --out teaching/web/zh --lang zh
    python teaching/web/docx2md.py \
        --docx "thesis/Learning-Handbook-From-Zero-to-nsF5-Steganography.docx" \
        --out teaching/web/en --lang en

The converter understands the handbook's own layout: direct-formatted headings,
real tables, one-cell callout boxes, monospace code boxes, and embedded images.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

import docx
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph


def heading_level(p: Paragraph):
    """Return 1/2/3 when p is a direct-formatted handbook heading."""
    sizes = []
    for r in p.runs:
        if r.font.size is not None:
            sizes.append(r.font.size.pt)
    if not sizes:
        return None
    size = max(sizes)
    bold = any(r.bold for r in p.runs)
    if bold and abs(size - 16) < 0.5:
        return 1
    if bold and abs(size - 13) < 0.5:
        return 2
    if bold and abs(size - 12) < 0.5:
        return 3
    return None


def run_is_code(r) -> bool:
    rf = r._element.rPr.rFonts if (r._element.rPr is not None and
                                   r._element.rPr.rFonts is not None) else None
    if rf is None:
        return False
    return (rf.get(qn("w:ascii")) or "").lower().startswith("consolas")


def para_md(p: Paragraph) -> str:
    parts = []
    for r in p.runs:
        text = r.text
        if not text:
            continue
        if run_is_code(r):
            parts.append("`" + text + "`")
        elif r.bold and r.italic:
            parts.append("***" + text + "***")
        elif r.bold:
            parts.append("**" + text + "**")
        elif r.italic:
            parts.append("*" + text + "*")
        else:
            parts.append(text)
    return "".join(parts).strip()


def list_marker(p: Paragraph, doc, counters) -> str | None:
    """Return a markdown list prefix when p belongs to a real numbering list."""
    ppr = p._p.pPr
    if ppr is None:
        return None
    numpr = ppr.find(qn("w:numPr"))
    if numpr is None:
        return None
    numid_el = numpr.find(qn("w:numId"))
    ilvl_el = numpr.find(qn("w:ilvl"))
    numid = int(numid_el.get(qn("w:val"))) if numid_el is not None else 0
    ilvl = int(ilvl_el.get(qn("w:val"))) if ilvl_el is not None else 0
    key = (numid, ilvl)
    fmt = None
    try:
        numbering = doc.part.numbering_part.numbering_definitions._numbering
        for num in numbering.findall(qn("w:num")):
            if int(num.get(qn("w:numId"))) != numid:
                continue
            aid_el = num.find(qn("w:abstractNumId"))
            aid = int(aid_el.get(qn("w:val")))
            for ab in numbering.findall(qn("w:abstractNum")):
                if int(ab.get(qn("w:abstractNumId"))) != aid:
                    continue
                for lvl in ab.findall(qn("w:lvl")):
                    if int(lvl.get(qn("w:ilvl"))) == ilvl:
                        nf = lvl.find(qn("w:numFmt"))
                        fmt = nf.get(qn("w:val")) if nf is not None else "bullet"
    except Exception:
        fmt = "bullet"
    if fmt == "decimal" or fmt == "lowerLetter":
        counters[key] = counters.get(key, 0) + 1
        return f"{counters[key]}. "
    if ilvl == 0:
        return "- "
    return "  - "


def cell_md(cell) -> str:
    lines = []
    for p in cell.paragraphs:
        t = para_md(p)
        if t:
            lines.append(t)
    return "<br>".join(lines).replace("|", "\\|")


def table_md(table) -> str:
    rows = []
    for row in table.rows:
        rows.append([cell_md(c) for c in row.cells])
    if not rows:
        return ""
    out = ["| " + " | ".join(rows[0]) + " |",
           "| " + " | ".join("---" for _ in rows[0]) + " |"]
    out.extend("| " + " | ".join(r) + " |" for r in rows[1:])
    return "\n".join(out)


def _cell_para(cell):
    return [p for p in cell.paragraphs]


def cell_one_md(cell) -> str:
    """Convert a one-cell table: code fence, callout, or plain text."""
    ps = _cell_para(cell)
    code_lines = []
    code = False
    text_lines = []
    for p in ps:
        runs = p.runs
        if runs and run_is_code(runs[0]):
            code = True
            code_lines.append("".join(r.text for r in runs))
        else:
            text_lines.append(para_md(p))
    if code:
        return "```python\n" + "\n".join(code_lines).rstrip() + "\n```"
    if not text_lines:
        return ""
    # callout: leading bold label, e.g. **动手做｜** or **Try it |**
    first_md = text_lines[0] if text_lines else ""
    m = re.match(r"\*\*(.+?)\*\*\s*(.*)$", first_md, re.S)
    if m:
        label, rest = m.group(1), m.group(2)
        body = "\n\n".join([rest] + text_lines[1:]).strip()
        body = body.replace("\n", "\n> ")
        return f"> **{label.strip()}** {body}".strip()
    return "> " + "\n> ".join(text_lines)


def extract_image(doc_part, run, asset_dir, idx):
    blips = run._element.findall(".//" + qn("a:blip"))
    for blip in blips:
        rid = blip.get(qn("r:embed"))
        if not rid:
            continue
        image_part = doc_part.related_parts[rid]
        ext = os.path.splitext(image_part.partname)[1] or ".png"
        name = f"img{idx:03d}{ext}"
        path = os.path.join(asset_dir, name)
        with open(path, "wb") as fh:
            fh.write(image_part.blob)
        return path
    return None


def slugify(text: str, idx: int, lang: str, is_appendix=False):
    if is_appendix:
        m = re.search(r"([A-E])", text)
        return f"app{m.group(1)}" if m else f"app{idx}"
    m = re.search(r"(?:第\s*)?(?:Chapter\s*)?(\d+)", text)
    return f"ch{int(m.group(1)):02d}" if m else f"part{idx:02d}"


def convert(docx_path: str, out_dir: str, lang: str) -> list:
    doc = docx.Document(docx_path)
    content_dir = os.path.join(out_dir, "content")
    asset_dir = os.path.join(out_dir, "assets")
    os.makedirs(content_dir, exist_ok=True)
    os.makedirs(asset_dir, exist_ok=True)

    current = None  # [filename, lines]
    files = []
    img_idx = 0
    list_counters = {}

    def flush():
        if current is not None:
            path = os.path.join(content_dir, current[0])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n\n".join(line for line in current[1] if line) + "\n")
            files.append(path)

    first_h1 = True
    h1_count = 0
    for child in doc.element.body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            level = heading_level(p)
            text = para_md(p)
            if level == 1:
                flush()
                h1_count += 1
                appendix = bool(re.search(r"(附录|Appendix)", text))
                if first_h1:
                    name = "intro.md"
                    first_h1 = False
                else:
                    name = slugify(text, h1_count, lang, is_appendix=appendix) + ".md"
                current = [name, [f"# {text.replace('**', '')}"]]
            elif level == 2 and current is not None:
                current[1].append(f"## {text.replace('**', '')}")
            elif level == 3 and current is not None:
                current[1].append(f"### {text.replace('**', '')}")
            elif current is not None and text:
                marker = list_marker(p, doc, list_counters)
                if marker is not None:
                    current[1].append(marker + text)
                else:
                    current[1].append(text)
            # embedded images (inline paragraph run)
            if current is not None and p.runs:
                for run in p.runs:
                    if run._element.findall(".//" + qn("a:blip")):
                        img_idx += 1
                        rel = extract_image(doc.part, run, asset_dir, img_idx)
                        if rel:
                            rel_name = os.path.basename(rel)
                            current[1].append(f"![fig-{img_idx}](assets/{rel_name})")
        elif tag == "tbl" and current is not None:
            from docx.table import Table
            t = Table(child, doc)
            ncol = len(t.columns)
            nrow = len(t.rows)
            if ncol == 1 and nrow == 1:
                current[1].append(cell_one_md(t.rows[0].cells[0]))
            elif ncol > 1 and nrow > 1:
                current[1].append(table_md(t))
            else:
                pass
    flush()
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", required=True, choices=["zh", "en"])
    args = ap.parse_args()
    files = convert(args.docx, args.out, args.lang)
    print(f"converted {len(files)} files -> {args.out}")


if __name__ == "__main__":
    main()
