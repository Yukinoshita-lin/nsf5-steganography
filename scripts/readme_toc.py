"""
scripts/readme_toc.py — README 的目录 (TOC) 生成器与校验器。

背景 (2026-09-17)
-----------------
README 已经 62 KB、14 个二级小节, 但**没有任何目录**: 想找"目录结构"或
"更正记录"只能一路滚。手写目录又会立刻腐烂 —— 改个标题、挪个小节, 链接就指向
不存在的地方 (本项目在本周已经因为"指向不存在的东西"修过三处: 已删除的 thesis/、
独立仓库 yccstego、以及 handbook 里的图注)。

所以目录由本脚本**从二级标题生成**, 并用 `--check` 钉进 `pytest`: 标题一改,
目录没跟着改就是 CI 红。

锚点规则是 GitHub 的近似实现 (小写 → 去标点 → 空格换连字符, 保留中文/数字/
`_`/`-`; 重名标题按 GitHub 的 `-1` 后缀处理)。它与 GitHub 的渲染应当一致,
但**不保证逐字符相同** —— 所以本脚本的价值是"目录不会腐烂", 不是"锚点绝对精确"。

用法
----
    python scripts/readme_toc.py --check      # 校验 README 的目录是最新的 (CI/pytest)
    python scripts/readme_toc.py --fix        # 重写目录块
    python scripts/readme_toc.py --print       # 只打印, 不改文件
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(PROJ, "README.md")

BEGIN = "<!-- TOC:BEGIN 由 scripts/readme_toc.py 生成, 勿手改 -->"
END = "<!-- TOC:END -->"
TOC_LEVEL = 2          # 只收录二级标题: 14 条, 一眼能看完


def headings(text: str, max_level: int = TOC_LEVEL) -> list:
    """抽取 ATX 标题 (跳过围栏代码块 —— README 里大量 `# 注释` 不是标题)。"""
    out, fence = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("```") or s.startswith("~~~"):
            fence = None if fence else s[:3]
            continue
        if fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if not m:
            continue
        lvl, title = len(m.group(1)), m.group(2).strip()
        title = re.sub(r"\s+#+\s*$", "", title).strip()      # 去掉结尾的 ### 闭合
        if lvl <= max_level and title:
            out.append((lvl, title))
    return out


def slug(title: str) -> str:
    """GitHub 风格的锚点。"""
    s = title.strip().lower()
    s = re.sub(r"[^\w\u4e00-\u9fff \-]", "", s)   # 去标点 (保留中文/字母/数字/_/-/空格)
    return s.replace(" ", "-")


def anchors(items: list) -> list:
    """(level, title) -> [(title, anchor)], 重名标题按 GitHub 规则加 -1/-2。"""
    seen, out = {}, []
    for lvl, title in items:
        base = slug(title)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append((title, base if n == 0 else f"{base}-{n}"))
    return out


def render(headings_list: list) -> str:
    lines = [BEGIN, "", "## 目录", ""]
    for title, anchor in anchors(headings_list):
        lines.append(f"- [{title}](#{anchor})")
    lines += ["", END]
    return "\n".join(lines)


def _doc_h2(text: str) -> list:
    """目录要收录的标题: **恰好二级**、且不是"目录"自己。

    (文档的一级标题是标题本身, 列进目录只是噪音。)
    """
    return [(l, t) for (l, t) in headings(text, TOC_LEVEL)
            if l == TOC_LEVEL and t != "目录"]


def replace_block(text: str, block: str) -> str:
    """把 README 里的目录块换成 block; 没有就插在第一个二级标题之前。"""
    if BEGIN in text and END in text:
        i = text.index(BEGIN)
        j = text.index(END) + len(END)
        return text[:i].rstrip("\n") + "\n\n" + block + text[j:]
    m = re.search(r"^## ", text, re.M)
    if not m:
        return text + "\n\n" + block + "\n"
    return text[:m.start()].rstrip("\n") + "\n\n" + block + "\n\n" + text[m.start():]


def current_block(text: str) -> str | None:
    if BEGIN not in text or END not in text:
        return None
    i = text.index(BEGIN)
    j = text.index(END) + len(END)
    return text[i:j]


def check(path: str = README) -> list:
    text = io.open(path, encoding="utf-8").read()
    want = render(_doc_h2(text))
    got = current_block(text)
    if got is None:
        return ["README 里没有目录块; 跑 python scripts/readme_toc.py --fix"]
    if got.strip() != want.strip():
        problems = ["README 的目录与标题不同步; 跑 python scripts/readme_toc.py --fix"]
        want_lines = set(want.splitlines())
        got_lines = set(got.splitlines())
        for line in sorted(got_lines - want_lines)[1:6]:
            problems.append(f"  多余/过时: {line}")
        for line in sorted(want_lines - got_lines)[1:6]:
            problems.append(f"  缺少: {line}")
        return problems
    # 目录里的锚点必须真的对应某个标题 (防止手改出死链)
    valid = {a for _, a in anchors(_doc_h2(text))}
    bad = [m.group(1) for m in re.finditer(r"\]\(#([^)]+)\)", got) if m.group(1) not in valid]
    if bad:
        return [f"目录里有指向不存在标题的锚点: {bad}"]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="README 目录的生成与校验")
    ap.add_argument("--check", action="store_true", help="校验目录是否最新")
    ap.add_argument("--fix", action="store_true", help="重写目录块")
    ap.add_argument("--print", dest="print_only", action="store_true", help="只打印")
    ap.add_argument("--file", default=README)
    args = ap.parse_args()

    text = io.open(args.file, encoding="utf-8").read()
    block = render(_doc_h2(text))

    if args.print_only:
        print(block)
        return 0
    if args.check:
        problems = check(args.file)
        if problems:
            for p in problems:
                print(p)
            return 1
        print(f"[ok] 目录与 {len(_doc_h2(text))} 个二级标题同步")
        return 0

    new = replace_block(text, block)
    if new != text:
        io.open(args.file, "w", encoding="utf-8", newline="\n").write(new)
        print(f"[ok] 已重写目录 ({len(_doc_h2(text))} 条) -> {_show(args.file)}")
    else:
        print("[ok] 目录本来就是最新的")
    return 0


def _show(path: str) -> str:
    """显示路径: 跨盘符时 `os.path.relpath` 会抛 ValueError, 退回绝对路径。"""
    try:
        return os.path.relpath(path, PROJ).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


if __name__ == "__main__":
    raise SystemExit(main())
