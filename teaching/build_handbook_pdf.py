# -*- coding: utf-8 -*-
"""把 Markdown 手册(teaching/web)转成单册 PDF(用 xelatex + ctex 编译)。

用法: python teaching/build_handbook_pdf.py [zh|en]
- ps > xelatex(两次) 产生 docs/<name>.pdf
"""
from __future__ import annotations
import os, sys, re, subprocess, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = sys.argv[1] if len(sys.argv) > 1 else "zh"
WEB = os.path.join(ROOT, "teaching", "web", LANG)
CONTENT = os.path.join(WEB, "content")
ASSETS = os.path.join(WEB, "assets")
BUILD = os.path.join(ROOT, "_pdf_build", LANG)
PDF_OUT = os.path.join(ROOT, "docs",
                       "学习手册-从零读懂nsF5隐写项目.pdf" if LANG == "zh"
                       else "Learning-Handbook-From-Zero-to-nsF5-Steganography.pdf")

TOC_ORDER = ["intro", "ch01", "ch02", "ch03", "ch04", "ch05", "ch06",
             "ch07", "ch08", "ch09", "ch10", "ch11",
             "appA", "appB", "appC", "appD", "appE", "appF"]


def esc(t: str) -> str:
    """转义 LaTeX 特殊字符(用于正文文本, 不含数学)。"""
    out = []
    for ch in t:
        if ch in "&%#_{}~^$":
            out.append("\\" + ch)
        elif ch == "\\":
            out.append("\\textbackslash{}")
        else:
            out.append(ch)
    return "".join(out)


def inline(s: str) -> str:
    """行内: 数学/代码/加粗/斜体/链接 作为受保护片段直接输出, 仅普通文本转义。"""
    pattern = re.compile(
        r'(\$[^$]+\$'                    # 数学 $...$
        r'|`[^`]+`'                      # 代码 `...`
        r'|\*\*[^*\n]+\*\*'              # 加粗 **...**
        r'|(?<![\w*])\*[^*\n]+\*(?![\w*])'  # 斜体 *...*
        r'|\[[^\]]+\]\([^)\s]+\))'       # 链接 [text](url)
    )
    def trans(p: str) -> str:
        if len(p) > 2 and p[0] == "$" and p[-1] == "$":
            return p                                  # 数学, 直通
        if len(p) > 2 and p[0] == "`" and p[-1] == "`":
            return "\\texttt{" + esc(p[1:-1]) + "}"
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            return "\\textbf{" + inline(p[2:-2]) + "}"
        if p.startswith("[") and "]( " not in p:
            m = re.match(r'\[([^\]]+)\]\(([^)\s]+)\)', p)
            if m:
                url = m.group(2)
                if url.startswith("http"):
                    return "\\href{" + url + "}{" + inline(m.group(1)) + "}"
                return inline(m.group(1))          # 内部锚点, 只留文字
        if p.startswith("*") and p.endswith("*") and len(p) > 2:
            return "\\textit{" + inline(p[1:-1]) + "}"
        return esc(p)
    return "".join(trans(p) for p in pattern.split(s))


def caption_inline(s: str) -> str:
    """图片 alt 或 *说明*: 转义但保留文本。"""
    return inline(s)


def md_to_tex(text: str) -> str:
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("<!--"):
            while i < n and "-->" not in lines[i]:
                i += 1
            i += 1
            continue
        if not stripped:
            i += 1
            continue
        # 代码块
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i]); i += 1
            i += 1  # 跳过结束```
            out.append("\\begin{lstlisting}[language=%s,breaklines=true]\n%s\n\\end{lstlisting}"
                       % (lang if lang else "Python", "\n".join(code)))
            continue
        # 显示数学
        if stripped.startswith("$$"):
            i += 1
            eq = []
            while i < n and "$$" not in lines[i]:
                eq.append(lines[i]); i += 1
            if i < n:
                i += 1
            out.append("\\begin{equation*}\n%s\n\\end{equation*}" % "\n".join(eq))
            continue
        # 标题(不自动编号, 保留标题自带号码, 手动写目录)
        mm = re.match(r'^(#{1,4})\s+(.*)$', stripped)
        if mm:
            lvl = len(mm.group(1)); title = inline(mm.group(2))
            if lvl == 1:
                out.append("\\chapter*{%s}\\markboth{%s}{%s}\\addcontentsline{toc}{chapter}{%s}" % (title, title, title, title))
            elif lvl == 2:
                out.append("\\section*{%s}\\addcontentsline{toc}{section}{%s}" % (title, title))
            elif lvl == 3:
                out.append("\\subsection*{%s}\\addcontentsline{toc}{subsection}{%s}" % (title, title))
            else:
                out.append("\\subsubsection*{%s}" % title)
            i += 1
            continue
        # 图片
        mi = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)\s*$', stripped)
        if mi:
            alt = mi.group(1); src = os.path.basename(mi.group(2))
            out.append("\\begin{figure}[htbp]\\centering\\includegraphics[width=0.92\\linewidth]{%s}\\caption{%s}\\end{figure}" % (esc(src), alt))
            i += 1
            continue
        # 表格: 连续 | 开头行 (固定列宽 p{}, 让长文本换行, 不超版心)
        if stripped.startswith("|"):
            tbl = []
            while i < n and lines[i].strip().startswith("|"):
                tbl.append(lines[i]); i += 1
            rows = []
            for rline in tbl:
                cells = [c.strip() for c in rline.strip().strip("|").split("|")]
                rows.append(cells)
            if len(rows) > 1 and all(re.fullmatch(r':?-{2,}:?', c) for c in rows[1]):
                rows.pop(1)
            ncol = max(len(r) for r in rows)
            colspec = "@{}" + ">{\\raggedright\\arraybackslash}p{\\dimexpr\\linewidth/%d\\relax}" % ncol * ncol + "@{}"
            out.append("\\begingroup\\small\\setlength{\\tabcolsep}{3pt}\\renewcommand{\\arraystretch}{1.15}")
            out.append("\\begin{longtable}{%s}\\hline" % colspec)
            for r in rows:
                cells = [inline(c) for c in r] + [""] * (ncol - len(r))
                out.append(" & ".join(cells) + " \\\\ \\hline")
            out.append("\\end{longtable}\\endgroup")
            continue
        # 列表
        if re.match(r'^[-*]\s+', stripped):
            items = []
            while i < n and re.match(r'^\s*[-*]\s+', lines[i]):
                items.append(re.sub(r'^\s*[-*]\s+', '', lines[i])); i += 1
            out.append("\\begin{itemize}")
            for it in items:
                out.append("\\item " + inline(it))
            out.append("\\end{itemize}")
            continue
        if re.match(r'^\s*\d+\.\s+', stripped):
            items = []
            while i < n and re.match(r'^\s*\d+\.\s+', lines[i]):
                items.append(re.sub(r'^\s*\d+\.\s+', '', lines[i])); i += 1
            out.append("\\begin{enumerate}")
            for it in items:
                out.append("\\item " + inline(it))
            out.append("\\end{enumerate}")
            continue
        # 引用块(admonition)
        if stripped.startswith(">"):
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip()); i += 1
            body = " ".join(q for q in quote if q)
            if body.startswith("[🌐") or ("English version" in body) or ("中文版" in body and body.startswith("[", 0) is False and "🌐" in body):
                # 跨语言切换链接块, 跳过
                continue
            mlabel = re.match(r'\*\*([^*|]+)\|?\*\*\s*(.*)$', body)
            title = "说明"
            if mlabel:
                title = mlabel.group(1).strip()
                body = mlabel.group(2)
            out.append("\\begin{tcolorbox}[colback=blue!4,colframe=blue!55!black,title={%s},breakable]\\small %s\\end{tcolorbox}" % (esc(title), inline(body)))
            continue
        # 斜体说明行 *...*
        if stripped.startswith("*") and stripped.endswith("*") and len(stripped) > 2:
            body = stripped.strip("*")
            out.append("\\begin{quote}\\itshape\\small %s\\end{quote}" % inline(body))
            i += 1
            continue
        # 普通段落: 收集到空行
        para = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r'^(#|```|\$\$|\||>|!\[|[-*]\s|\d+\.\s|\*\*)', lines[i].strip()):
            para.append(lines[i].strip()); i += 1
        out.append("\\begin{quote}\\small " + inline(" ".join(para)) + "\\end{quote}" if False else inline(" ".join(para)))
    return "\n\n".join(out)


def main():
    os.makedirs(BUILD, exist_ok=True)
    shutil.rmtree(os.path.join(BUILD, "assets"), ignore_errors=True)
    shutil.copytree(ASSETS, os.path.join(BUILD, "assets"))
    body = []
    for name in TOC_ORDER:
        f = os.path.join(CONTENT, name + ".md")
        if os.path.exists(f):
            t = open(f, encoding="utf-8").read()
            body.append(md_to_tex(t))
    body_tex = "\n\n".join(body)

    title = "项目学习手册 · 从零读懂 nsF5 隐写" if LANG == "zh" else "Learning Handbook: From Zero to nsF5 Steganography"
    doc = r"""\documentclass[openany,UTF8,11pt]{ctexbook}
\usepackage[margin=2.2cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{amsmath,amssymb}
\usepackage{listings}
\usepackage{xcolor}
\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{hyperref}
\usepackage{caption}
\usepackage[most]{tcolorbox}
\tcbuselibrary{breakable,skins}
\usepackage{newunicodechar}
% 常用数学/符号映射(正文中出现, 非数学环境)
\newunicodechar{≈}{\ensuremath{\approx}}
\newunicodechar{≤}{\ensuremath{\leq}}
\newunicodechar{≥}{\ensuremath{\geq}}
\newunicodechar{≠}{\ensuremath{\neq}}
\newunicodechar{⊕}{\ensuremath{\oplus}}
\newunicodechar{×}{\ensuremath{\times}}
\newunicodechar{·}{\ensuremath{\cdot}}
\newunicodechar{→}{\ensuremath{\rightarrow}}
\newunicodechar{⇒}{\ensuremath{\Rightarrow}}
\newunicodechar{α}{\ensuremath{\alpha}}
\newunicodechar{β}{\ensuremath{\beta}}
\newunicodechar{λ}{\ensuremath{\lambda}}
\newunicodechar{μ}{\ensuremath{\mu}}
\newunicodechar{σ}{\ensuremath{\sigma}}
\newunicodechar{−}{-}
\newunicodechar{–}{--}
\newunicodechar{—}{---}
\newunicodechar{°}{\ensuremath{^{\circ}}}
\graphicspath{{@@P@@}}
\setCJKmainfont{Microsoft YaHei}
\lstset{basicstyle=\ttfamily\small,breaklines=true,frame=single,keywordstyle=\color{blue!70!black},commentstyle=\color{green!50!black}}
@@EN@@
\title{@@TITLE@@}
\author{nsF5 Steganography Project}
\begin{document}
\maketitle
\setcounter{tocdepth}{2}
\tableofcontents
\clearpage
@@BODY@@
\end{document}
"""
    enpreamble = (r"\renewcommand{\figurename}{Figure}" +
                  r"\renewcommand{\contentsname}{Contents}" +
                  r"\renewcommand{\listfigurename}{List of Figures}") if LANG == "en" else ""
    doc = (doc.replace("@@P@@", os.path.join(BUILD, "assets").replace("\\", "/"))
              .replace("@@EN@@", enpreamble)
              .replace("@@TITLE@@", title)
              .replace("@@BODY@@", body_tex))

    tex = os.path.join(BUILD, "handbook.tex")
    open(tex, "w", encoding="utf-8").write(doc)
    print("tex written:", tex, len(doc), "chars")
    # 编译
    for _ in range(2):
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                            "-output-directory", BUILD, tex], cwd=BUILD,
                           capture_output=True)
        if r.returncode != 0:
            print("=== XELATEX FAILED (pass) ===")
            print((r.stdout + r.stderr)[-4000:])
            return
    pdf = os.path.join(BUILD, "handbook.pdf")
    if os.path.exists(pdf):
        shutil.copy(pdf, PDF_OUT)
        print("PDF built ->", PDF_OUT, os.path.getsize(PDF_OUT)//1024, "KB")
    else:
        print("PDF not produced")
        for f in os.listdir(BUILD):
            if f.endswith(".log"):
                print("--- log tail ---")
                print(open(os.path.join(BUILD, f), encoding="utf-8", errors="ignore").read()[-3000:])


if __name__ == "__main__":
    main()
