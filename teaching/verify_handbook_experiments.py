"""
teaching/verify_handbook_experiments.py — 执行手册里的 python 代码片段。

背景 (2026-09-14)
-----------------
手册里有大量 ```python 片段, 但从来没人执行过: `handbook_facts.py` 只校验
**数字与结论**对不对, 不校验"照着抄能不能跑"; notebook 是真跑的, 手册片段不是。
对教学材料来说, 一段跑不通的示例代码和一句错的结论一样糟。

做法
----
1. 扫 `teaching/web/{zh,en}/content/*.md`, 取出 ```python 代码块;
2. 用启发式把**教学示意片段**标为 skip (含 `...`/`→`/CSV 表头行/外部网络操作/
   依赖不入库数据集的片段), 其余逐块执行;
3. 同一个文件里的块**共享命名空间**, 后面的块可以用前面定义的变量;
4. 支持期望输出断言: 代码块后面紧跟的 `<!-- expect: 子串 -->` 会被检查;
5. 打印"总块数 / 执行 / 跳过(带原因) / 失败", 有失败即非零退出。

用法
----
    python teaching/verify_handbook_experiments.py           # 全部
    python teaching/verify_handbook_experiments.py --lang zh
    python teaching/verify_handbook_experiments.py --list     # 只列判定, 不执行
    python teaching/verify_handbook_experiments.py -v         # 打印每个块的结论
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import re
import sys
import traceback

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "src")
WEBDIR = {"zh": os.path.join(PROJ, "teaching", "web", "zh", "content"),
          "en": os.path.join(PROJ, "teaching", "web", "en", "content")}

FENCE = re.compile(r"```(\w*)\n(.*?)```", re.S)
EXPECT = re.compile(r"<!--\s*expect:\s*(.*?)\s*-->")

# 显式例外清单: (文件名, 片段首行前缀) -> 为什么它不该被当"可运行样例"
# 这些都是**函数体/上下文摘录**, 讲解清楚但单独跑不了; 值里必须写清理由。
ILLUSTRATIVE = {
    ("ch03.md", "groups = flat[:m].reshape(-1, 4)"):
        "RS 逐组统计的函数体摘录: flat 来自上文, 不是独立样例",
    ("ch04.md", "xl = (c[pos] & 1).astype(np.uint8)"):
        "矩阵编码内层循环摘录 (含 continue/continue 上下文)",
    ("ch07.md", "from sklearn.model_selection import GroupKFold"):
        "交叉验证写法摘录: 用到上下文里的 X/y/groups/clf",
    ("ch07.md", "from sklearn.metrics import roc_curve"):
        "Youden 阈值写法摘录: 用到上下文里的 y_true/proba",
    ("ch07.md", "def lr(seed=0)"):
        "分类器工厂摘录: make_pipeline/StandardScaler 等依赖上文导入",
    ("ch08.md", "gi = groups.astype(np.int16)"):
        "卡方配对的函数体摘录",
    ("ch08.md", "even = counts[0::2]"):
        "卡方统计量的函数体摘录 (含 return)",
    ("ch08.md", 'if self.sensitivity.startswith'):
        "MLPredictor._threshold() 的方法体摘录 (含 return)",
    ("ch08.md", "def lr(seed=0)"):
        "分类器工厂摘录: 依赖上文导入",
}


def _excerpt_like(code: str) -> str | None:
    """能不能一眼看出它不是独立程序 (只在函数体/循环体里才合法)。"""
    try:
        compile(code, "<probe>", "exec")
        return None
    except SyntaxError as exc:
        msg = (exc.msg or "")
        for key in ("'return' outside function", "'continue' not properly in loop",
                    "'break' outside loop", "unexpected indent",
                    "unexpected character after line continuation"):
            if key in msg:
                return f"语法上就是片段 ({key})"
    return None


# 期望输出: (语言, 文件, 片段首行前缀) -> 输出里必须出现的子串。
# 只挑"输出含义明确、且不随环境变化"的片段 —— 断言的价值在于: 光"没报错"可能
# 只是这段什么都没干。
EXPECTATIONS = {
    ("zh", "ch01.md", "v = 200"): "201",                       # 200 ^ 1
    ("en", "ch01.md", "v = 200"): "201",
    ("zh", "ch01.md", "import numpy as np"): "[1 1 0 0 1 0 0 0]",   # LSB 位平面
    ("en", "ch01.md", "import numpy as np"): "[1 1 0 0 1 0 0 0]",
    ("zh", "ch02.md", "import numpy as np"): "100",            # 数组均值
    ("en", "ch02.md", "import numpy as np"): "100",
    ("zh", "ch03.md", 'import sys; sys.path.insert(0, "src")'): "Gn=",   # RS 指标
    ("en", "ch03.md", 'import sys; sys.path.insert(0, "src")'): "Gn=",
    ("zh", "ch05.md", "# 对比 matrix 与 nsF5"): "nsF5",         # 两种方法都跑了
    ("en", "ch05.md", "# compare modified-pixel counts"): "nsF5",
    ("zh", "ch06.md", 'import sys; sys.path.insert(0, "src")'): "解码失败",   # 口令/篡改
    ("en", "ch06.md", 'import sys; sys.path.insert(0, "src")'): "decode failed",
    ("zh", "ch08.md", "# 3) 对单张图做 ML 判定"): "probability",
    ("en", "ch08.md", "# 3) single-image ML judgment"): "probability",
}


def _is_illustrative(code: str) -> str | None:
    """返回跳过原因; 返回 None 表示"这段应该能跑"。"""
    lines = [ln for ln in code.strip().splitlines() if ln.strip()]
    if not lines:
        return "空块"
    joined = "\n".join(lines)
    # 一眼能看出是片段的: 语法上就不成立
    frag = _excerpt_like(code)
    if frag:
        return frag
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*(,[A-Za-z_][A-Za-z0-9_]*)+", lines[0]):
        return "CSV 表头示例"
    if re.search(r"(^|\s)\.\.\.(\s|$)|…|→|<-|⋯", joined):
        return "含省略号/箭头, 是示意"
    if re.search(r"^\s*(pip install|git clone|\$ |python -m pip|python src|py src)", joined, re.M):
        return "外部命令片段"
    if "..." in joined or "……" in joined:
        return "含省略号, 是示意"
    # 依赖不入库的数据集 (校园语料 / 外部语料) 的片段跳过
    for m in re.finditer(r"[\"'](data/[A-Za-z0-9_./-]+\.csv)[\"']", joined):
        if not os.path.exists(os.path.join(PROJ, m.group(1))):
            return f"依赖不入库的数据集 {m.group(1)}"
    if re.search(r"[\"'](campus_jpg|external)/", joined):
        return "依赖不入库的数据目录"
    # 纯注释块
    if all(ln.strip().startswith("#") for ln in lines):
        return "纯注释"
    return None


def _collect(lang: str) -> list:
    """返回 [(file, first_line, code, expect)]。"""
    out = []
    d = WEBDIR[lang]
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"):
            continue
        txt = io.open(os.path.join(d, fn), encoding="utf-8").read()
        for m in FENCE.finditer(txt):
            if m.group(1).strip().lower() not in ("python", "py"):
                continue
            code = m.group(2)
            tail = txt[m.end():m.end() + 200]
            exp = EXPECT.search(tail)
            first = code.strip().splitlines()[0][:60] if code.strip() else ""
            out.append((fn, first, code, exp.group(1) if exp else None))
    return out


def _run_block(code: str, ns: dict, expect: str | None) -> str:
    """执行一块, 返回捕获的 stdout; 断言失败/异常会抛出。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<handbook>", "exec"), ns)
    out = buf.getvalue()
    if expect and expect not in out:
        raise AssertionError(f"期望输出 {expect!r} 未出现; 实际输出: {out.strip()[-300:]!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="执行手册里的 python 片段")
    ap.add_argument("--lang", choices=("zh", "en", "both"), default="both")
    ap.add_argument("--list", action="store_true", help="只列判定, 不执行")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.path.insert(0, SRC)
    os.chdir(PROJ)                      # 片段用相对路径 img/cover.png 之类

    langs = ("zh", "en") if args.lang == "both" else (args.lang,)
    total = run = skipped = failed = asserted = 0
    failures = []
    for lang in langs:
        blocks = _collect(lang)
        ns = {"__name__": f"handbook_{lang}"}      # 每语言一份命名空间
        print(f"\n=== {lang}: {len(blocks)} 个 python 片段 ===")
        for fn, first, code, exp in blocks:
            total += 1
            reason = _is_illustrative(code)
            if reason is None:
                for (ifn, iprefix), why in ILLUSTRATIVE.items():
                    if fn == ifn and first.startswith(iprefix):
                        reason = f"显式例外: {why}"
                        break
            if reason:
                skipped += 1
                if args.verbose:
                    print(f"  SKIP  [{reason}] {fn}: {first}")
                continue
            if args.list:
                run += 1
                print(f"  RUN   {fn}: {first}")
                continue
            want = None
            for (elang, efn, eprefix), etext in EXPECTATIONS.items():
                if elang == lang and efn == fn and first.startswith(eprefix):
                    want = etext
                    break
            if want is None:
                want = exp                     # 也支持 markdown 里的 <!-- expect: ... -->
            if want:
                asserted += 1
            try:
                out = _run_block(code, ns, want)
                run += 1
                if args.verbose:
                    tail = out.strip().splitlines()[-1][:60] if out.strip() else "(无输出)"
                    mark = " [断言通过]" if want else ""
                    print(f"  OK    {fn}: {first}  -> {tail}{mark}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                failures.append((fn, first, f"{type(exc).__name__}: {exc}",
                                 traceback.format_exc().strip().splitlines()[-3:]))
                print(f"  FAIL  {fn}: {first}")
    print(f"\n合计 {total} 个片段: 执行 {run} (其中 {asserted} 条带期望输出断言), "
          f"跳过 {skipped}, 失败 {failed}")
    for fn, first, err, ctx in failures[:12]:
        print(f"  - {fn}: {first}\n      {err}")
    if failures:
        print("\n失败片段需要二选一: 修好它, 或者在 _is_illustrative() 里给出跳过理由。")
        return 1
    print("所有可执行片段均通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
