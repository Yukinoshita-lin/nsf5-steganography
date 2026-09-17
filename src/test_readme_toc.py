"""README 目录的同步自测 (2026-09-17)。

README 已经有 14 个二级小节、60 KB 以上, 却一直没有目录; 而**手写目录会立刻腐烂**:
改标题、挪小节、删一段, 链接就指向不存在的地方 —— 本项目这几天已经因为"指向不存在
的东西"修过三处 (已删除的 `thesis/`、独立仓库 `yccstego`、手册图注)。

所以目录由 `scripts/readme_toc.py` 从二级标题**生成**, 并由本文件钉进 `pytest`:
标题改了而目录没跟着改, 这里就红。

(锚点是 GitHub 规则的近似实现, 目的是"目录不腐烂", 不是"锚点绝对精确"。)
"""
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(PROJ, "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import readme_toc as RT  # noqa: E402


def test_readme_has_a_toc():
    text = open(RT.README, encoding="utf-8").read()
    assert RT.current_block(text), "README 没有目录块; 跑 python scripts/readme_toc.py --fix"


def test_toc_is_in_sync_with_headings():
    problems = RT.check(RT.README)
    assert problems == [], "\n".join(problems)


def test_toc_anchors_resolve_to_real_headings():
    """目录里的每个锚点都必须命中某个真实标题 (防手改出死链)。"""
    text = open(RT.README, encoding="utf-8").read()
    valid = {a for _, a in RT.anchors(RT._doc_h2(text))}
    block = RT.current_block(text)
    import re
    links = re.findall(r"\]\(#([^)]+)\)", block)
    assert links, "目录里一条链接都没有"
    missing = [a for a in links if a not in valid]
    assert missing == [], f"目录里的锚点找不到对应标题: {missing}"


def test_toc_covers_every_h2():
    """二级标题一个都不能漏 —— 否则目录会"看起来正常但少了内容"。"""
    text = open(RT.README, encoding="utf-8").read()
    heads = [t for _, t in RT._doc_h2(text)]
    block = RT.current_block(text)
    for t in heads:
        assert f"[{t}](#" in block, f"二级标题 {t!r} 不在目录里"


def test_heading_parser_ignores_fenced_code():
    """README 里到处是 `# 注释`; 它们不能被当成标题 (否则目录会收录代码注释)。"""
    sample = "# Title\n\n```python\n# 这不是标题\n```\n\n## 真标题\n\n~~~\n# 也不是\n~~~\n"
    got = [t for _, t in RT.headings(sample, 2)]
    assert got == ["Title", "真标题"], got


def test_slug_keeps_cjk_and_drops_punctuation():
    assert RT.slug("更正记录：曾经出现过的错误") == "更正记录曾经出现过的错误"
    assert RT.slug("GPU 版 (v1.2)：PyTorch") == "gpu-版-v12pytorch"
    assert RT.slug("a_b-c") == "a_b-c"
