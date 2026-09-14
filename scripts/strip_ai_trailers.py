"""
scripts/strip_ai_trailers.py — 从提交信息里剔除 AI 协作工具的署名尾注。

背景
----
Claude Code 之类的工具在提交时会自动追加

    Co-Authored-By: Claude Code <noreply@anthropic.com>

这类尾注会被 GitHub 当成**共同作者**显示在提交流里（作者是你，共同作者是它）。
删掉分支并不能去掉它 —— 提交一旦并入主干, 归属就跟着提交走, 只能改写提交信息。

用法（两种都行）
---------------
    # 1) 内置 filter-branch, 只重写需要改的那一段历史
    git filter-branch -f --msg-filter 'python scripts/strip_ai_trailers.py' -- <起点>^..HEAD

    # 2) git-filter-repo（更快, 需 pip install git-filter-repo）
    git filter-repo --message-callback \
      'import subprocess,sys; sys.stdout.buffer.write(subprocess.run(["python","scripts/strip_ai_trailers.py"],input=message,capture_output=True).stdout)'

改写会改变 SHAs, 需要 `git push --force-with-lease`; 改写前请先
`git bundle create ../backup.bundle --all` 做全量备份。

本脚本同时被 `.githooks/commit-msg` 复用: 以后任何工具再追加这类尾注, 提交时就会被去掉。
"""
from __future__ import annotations

import re
import sys

# 需要剔除的尾注 (大小写不敏感, 按行匹配)
_TRAILER_PATTERNS = [
    # Claude Code / Claude
    re.compile(rb"^Co-[Aa]uthored-[Bb]y:\s*Claude(\s+Code)?\s*<noreply@anthropic\.com>\s*$"),
    # 其它常见 AI 协作身份 (Trae / Codex / Copilot)
    re.compile(rb"^Co-[Aa]uthored-[Bb]y:.*<ai@trae\.local>\s*$"),
    re.compile(rb"^Co-[Aa]uthored-[Bb]y:.*<[^>]*@openai\.com>\s*$"),
    re.compile(rb"^Co-[Aa]uthored-[Bb]y:\s*(Codex|GitHub Copilot|Copilot)\b.*$"),
    # "🤖 Generated with [Claude Code](...)" 之类的一整行
    re.compile(rb"^.*[Gg]enerated with \[?Claude Code\]?.*$"),
    re.compile(rb"^.*[Gg]enerated with \[?Codex\]?.*$"),
]


def strip_ai_trailers(message: bytes) -> bytes:
    """返回值可能去掉若干行之后的提交信息 (顺带清掉由此产生的多余空行)。"""
    text = message.decode("utf-8", errors="replace")
    lines = text.splitlines()
    kept = [ln for ln in lines
            if not any(p.match(ln.strip().encode("utf-8")) for p in _TRAILER_PATTERNS)]
    out = "\n".join(kept).rstrip("\n") + "\n"
    # 折叠连续空行 (去掉尾注后常见)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.encode("utf-8")


def main() -> int:
    sys.stdout.buffer.write(strip_ai_trailers(sys.stdin.buffer.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
