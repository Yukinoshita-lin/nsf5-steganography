"""
teaching/export_handbook_pdf_word.py — 把 DOCX 源稿导出为入库 PDF (docs/*.pdf)。

为什么需要这个脚本 (2026-09-15)
-------------------------------
入库的两份手册 PDF 一直是"用 Word 从 DOCX 导出的", 但这一步此前**没有脚本** ——
想重新导出只能靠回忆"用 Word 另存为 PDF"。于是它成了一个维护陷阱: 源稿与 PDF 的
对应关系只写在某次提交信息里, 改了 DOCX (例如 ``handbook_facts.py --fix`` 之后)
也没有任何人知道 PDF 该怎么跟着更新, 结果就是 PDF 带旧口径 / 指向已删除的文件。

本脚本把这一步固定下来。与另一个构建脚本的分工:

  - ``teaching/export_handbook_pdf_word.py`` (本脚本): DOCX -> PDF, 版式与历史交付
    一致 (Word 排版, 会做字体回退);
  - ``teaching/build_handbook_pdf.py``: 网页 markdown -> PDF, 用 xelatex 重排,
    内容更全 (网页版是增量最丰富的那一份), 但不做字体回退, 个别符号会缺字形。

入库的是前者。配对规则很简单: **DOCX 与 PDF 同名**, 所以脚本里没有任何中文路径
常量 —— 早先那版用 PowerShell 写死了中文文件名, 结果在 Windows PowerShell 5.1
下按代码页读取 .ps1、中文路径被读坏, 报了一个"DOCX 不在"的假跳过。

依赖: Windows + 已安装 Word + ``pywin32`` (``pip install pywin32``)。
Word 不可用时 (CI、Linux) 会**明确跳过并返回 0**, 而不是失败。

用法
----
    python teaching/export_handbook_pdf_word.py            # 导出 docs/src 下所有 DOCX
    python teaching/export_handbook_pdf_word.py --only zh  # 只导出中文那本
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
import tempfile
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJ, "docs", "src")
OUT = os.path.join(PROJ, "docs")

WD_FORMAT_PDF = 17
WD_STAT_PAGES = 2


def find_docx(only: str = "") -> list:
    """docs/src/*.docx (跳过 --fix 留下的 .orig.docx 备份与 Word 锁文件 ~$*)。"""
    pats = sorted(glob.glob(os.path.join(SRC, "*.docx")))
    out = []
    for p in pats:
        name = os.path.basename(p)
        if name.startswith("~$") or name.endswith(".orig.docx"):
            continue
        if only == "zh" and name.startswith("Learning"):
            continue
        if only == "en" and not name.startswith("Learning"):
            continue
        out.append(p)
    return out


def export_one(app, docx: str) -> dict:
    pdf = os.path.join(OUT, os.path.splitext(os.path.basename(docx))[0] + ".pdf")
    t0 = time.time()
    doc = retry(lambda: app.Documents.Open(docx), "打开 DOCX")
    try:
        # SaveAs2(..., FileFormat=17) 就是"另存为 PDF"。用 ExportAsFixedFormat 也
        # 可以, 但它的 14 个变体参数在 PowerShell / 动态派发下很容易传错, 传错的
        # 表现是弹出一个**看不见的模态框**把进程挂死 (实测卡了 5 分钟以上)。
        retry(lambda: doc.SaveAs2(pdf, WD_FORMAT_PDF), "导出 PDF")
        pages = int(retry(lambda: doc.ComputeStatistics(WD_STAT_PAGES), "统计页数"))
    finally:
        doc.Close(False)
    return {
        "docx": os.path.relpath(docx, PROJ),
        "pdf": os.path.relpath(pdf, PROJ),
        "pages": pages,
        "kb": round(os.path.getsize(pdf) / 1024),
        "seconds": round(time.time() - t0, 1),
    }


def retry(fn, what: str, timeout: float = 90.0, pause: float = 3.0):
    """调用 Word COM, 遇到 "被呼叫方拒绝接收呼叫" (0x8001010A) 就重试。

    这是 Office 自动化的经典毛病: Word 还没把消息队列转起来时, 任何调用都会
    被立刻拒绝。第一次成功导出这两本手册之前, 这里试过三种写法, 失败表现分别是
    (a) 挂在不可见模态框上 5 分钟以上, (b) `AttributeError: Open.SaveAs2`
    (动态派发把 Open 解析成了方法对象), (c) 立刻抛这个 com_error。最终可用组合是
    `gencache.EnsureDispatch` (拿到带类型库的 Document) + 重试。
    """
    import pythoncom
    t0 = time.time()
    while True:
        try:
            return fn()
        except pythoncom.com_error as exc:
            if time.time() - t0 > timeout:
                raise
            print(f"  [retry] {what}: {exc.hresult & 0xFFFFFFFF:#010x}; {pause:.0f} 秒后重试")
            time.sleep(pause)


def _dispatch_word():
    """拿一个可用的 Word.Application。

    先清掉 gen_py 缓存, 再 EnsureDispatch (生成类型库包装, Document 才有
    SaveAs2)。缓存与已注册组件的版本对不上时, 动态派发会退化成"属性访问",
    表现是 `AttributeError: Open.SaveAs2` 这种莫名其妙的错误; 而在 import 期间
    重建缓存又可能撞上 win32com 自己的循环导入 (`cannot import name
    '_get_good_object_'`), 随后每次调用都被 Word 拒绝 (0x80010001)。
    先清缓存 + 在干净的导入状态下 EnsureDispatch 是实测唯一稳定的组合。
    """
    shutil.rmtree(os.path.join(tempfile.gettempdir(), "gen_py"), ignore_errors=True)
    import win32com.client as win32
    return win32.gencache.EnsureDispatch("Word.Application")


def main() -> int:
    ap = argparse.ArgumentParser(description="用 Word 把 DOCX 手册导出为入库 PDF")
    ap.add_argument("--only", default="", choices=["", "zh", "en"],
                    help="只导出其中一本 (默认两本都导出)")
    args = ap.parse_args()

    docx = find_docx(args.only)
    if not docx:
        print(f"跳过: {os.path.relpath(SRC, PROJ)} 下没有 DOCX 源稿 "
              f"(docs/src 按约定不入库, 请先放回源稿)")
        return 0

    try:
        import win32com.client  # noqa: F401  (pywin32)
    except ImportError:
        print("跳过: 未安装 pywin32 (pip install pywin32); 该步骤需要 Windows + Word")
        return 0

    app = _dispatch_word()
    app.Visible = False
    app.DisplayAlerts = 0
    try:
        app.AutomationSecurity = 3          # 不执行文档里的宏
    except Exception:                        # noqa: BLE001 - 老版本没有这个属性
        pass

    try:
        for path in docx:
            info = export_one(app, path)
            print(f"  [ok] {info['pdf']}  {info['pages']} 页  "
                  f"{info['kb']} KB  ({info['seconds']}s)")
    finally:
        app.Quit()

    print("下一步: python teaching/handbook_facts.py --check   "
          "(校验入库 PDF 的文本口径, CI 里也会跑)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
