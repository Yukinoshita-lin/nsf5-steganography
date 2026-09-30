"""`make help` 必须把真实的 target 都列出来 (2026-09-30 审计)。

为什么值得一条测试: 这个文档漂移在本项目**犯过两次** —— 2026-09-17 审计发现
`make help` 漏了 `core/steg/fp/pipeline/pyfeatures/cpp-clean/gui/exp-data/
handbook-check`, 还列了一个根本不存在的 `handbook-check-`; 9-30 又发现新加的
`readme-toc-check` 没进 help。help 是使用者唯一的目标清单(README 也让它当索引),
漏一个就等于那个功能"不存在"。

规则: `.PHONY` 里声明的每个 target, 要么出现在 help 文本里, 要么在下面的
`INTERNAL` 白名单里(内部/元目标, 故意不列)。help 里支持 `a|b|c` 写法代表一组。
"""
import io
import os
import re

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE = os.path.join(PROJ, "Makefile")

# 内部/元目标: 不面向使用者, 故意不进 help
INTERNAL = {
    "help",          # 就是 help 自己
    "pytest",        # 由 make test / readme 说明; 实际已在 help 里, 留着无妨
}


def _phony(text: str) -> set:
    m = re.search(r"\.PHONY:(.*?)\n\n", text, re.S)
    assert m, "Makefile 里找不到 .PHONY 段"
    raw = m.group(1).replace("\\\n", " ")
    return {t for t in raw.split() if t and t != "\\"}


def _documented(text: str) -> set:
    m = re.search(r"^help:\n(.*?)\n\n", text, re.S | re.M)
    assert m, "Makefile 里找不到 help: 段"
    out = set()
    for line in m.group(1).splitlines():
        # help 行的形态是 `@echo "  make install   - ..."` —— 引号后可能先有空格
        mm = re.match(r"\s*@echo\s+\"\s*make\s+([^\s\"]+)", line)
        if not mm:
            continue
        for name in mm.group(1).split("|"):      # `core|steg|fp` 代表一组
            name = name.strip()
            if name:
                out.add(name)
    return out


def test_every_phony_target_is_documented():
    text = io.open(MAKEFILE, encoding="utf-8").read()
    phony = _phony(text)
    documented = _documented(text)
    missing = sorted(phony - documented - INTERNAL)
    assert missing == [], (
        f"这些 target 没出现在 make help 里: {missing}; "
        f"请在 Makefile 的 help 段补一行, 或加进 INTERNAL 白名单(内部目标)")


def test_help_does_not_document_imaginary_targets():
    """反向检查: help 里写的名字必须真的存在 —— 2026-09-17 曾列出过
    `handbook-check-`(多一个连字符), 使用者照着敲只会得到 "No rule to make target"."""
    text = io.open(MAKEFILE, encoding="utf-8").read()
    phony = _phony(text)
    documented = _documented(text)
    bogus = sorted(documented - phony)
    assert bogus == [], f"make help 列了并不存在的 target: {bogus}"
