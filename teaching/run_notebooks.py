"""
teaching/run_notebooks.py — 逐个执行 `notebooks/*.ipynb`（CI 与本地共用）。

为什么需要它 (2026-09-14 审计)
-----------------------------
这 10 本 notebook 是教学交付物, 但此前**从未被执行过**: 仓库里没有任何地方
跑它们, CI 只跑 pytest 与自测脚本。也就是说 `src/` 一改, 教学笔记本就可能
悄悄失效, 而没人会发现 —— 对教学材料来说这不可接受。

本脚本把"可执行性"变成可检查的事实:

  - 用 nbclient 在仓库根目录逐个执行 (相对路径 img/cover.png、src/ 都能对上);
  - 强制 MPLBACKEND=Agg, 无头环境也不弹窗;
  - **不写回** notebook (执行在内存里完成), 因此不会把工作区弄脏;
  - 任一 cell 抛错就打印出错 cell 的源码片段与异常, 非零退出。

用法
----
    python teaching/run_notebooks.py                 # 全部 10 本
    python teaching/run_notebooks.py --only 08       # 只跑文件名含 08 的
    python teaching/run_notebooks.py --timeout 900   # 单本超时 (秒)

依赖: nbclient, ipykernel (pip install nbclient ipykernel)。
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
import traceback

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NB_DIR = os.path.join(PROJ, "notebooks")


def run_one(path: str, timeout: int, verbose: bool) -> tuple:
    """执行一本 notebook, 返回 (ok, seconds, err_msg)。执行结果不写回磁盘。"""
    import nbformat
    from nbclient import NotebookClient
    from nbclient.exceptions import CellExecutionError

    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb, timeout=timeout, kernel_name="python3", allow_errors=False,
        resources={"metadata": {"path": PROJ}},
    )
    t0 = time.time()
    try:
        client.execute()
    except CellExecutionError as exc:
        # 找出出错的那个 cell, 打印它的源码与异常首行
        bad = ""
        for cell in nb.cells:
            if cell.cell_type == "code" and cell.get("outputs"):
                for o in cell["outputs"]:
                    if o.get("output_type") == "error":
                        bad = "".join(cell["source"])[:300]
                        break
            if bad:
                break
        msg = f"{str(exc).strip().splitlines()[-1] if str(exc).strip() else exc}"
        if bad:
            msg += f"\n      出错 cell: {bad.splitlines()[0][:120]}"
        return False, time.time() - t0, msg
    except Exception as exc:  # noqa: BLE001 - 超时/内核启动失败等
        detail = traceback.format_exc().strip().splitlines()[-1]
        return False, time.time() - t0, f"{type(exc).__name__}: {detail}"
    return True, time.time() - t0, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="执行教学 notebook (CI 友好)")
    ap.add_argument("--dir", default=NB_DIR)
    ap.add_argument("--only", default="", help="只跑文件名含该子串的 notebook")
    ap.add_argument("--timeout", type=int, default=600, help="单本超时秒数")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--keep-outputs", action="store_true",
                    help="保留 notebook 生成的文件 (默认执行后清理, 免得弄脏工作区)")
    args = ap.parse_args()

    os.environ.setdefault("MPLBACKEND", "Agg")     # 无头环境不弹窗
    paths = sorted(glob.glob(os.path.join(args.dir, "*.ipynb")))
    if args.only:
        paths = [p for p in paths if args.only in os.path.basename(p)]
    if not paths:
        print(f"没有找到 notebook: {args.dir}")
        return 1

    print(f"执行 {len(paths)} 本 notebook (单本超时 {args.timeout}s, MPLBACKEND=Agg)")
    fails = []
    for p in paths:
        name = os.path.basename(p)
        before = set(os.listdir(PROJ))
        ok, dt, err = run_one(p, args.timeout, args.verbose)
        print(f"  {'OK  ' if ok else 'FAIL'} {name:<42} {dt:6.1f}s")
        if not args.keep_outputs:
            # notebook 会把演示图存到仓库根 (如 output_demo.png); 执行完顺手清掉,
            # 免得把工作区弄脏 —— 只删"本次新出现"的文件。
            for f in sorted(set(os.listdir(PROJ)) - before):
                fp = os.path.join(PROJ, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except OSError:
                        pass
        if not ok:
            print(f"       {err}")
            fails.append(name)
    if fails:
        print(f"\n{len(fails)} 本失败: {', '.join(fails)}")
        return 1
    print(f"\n全部 {len(paths)} 本 notebook 执行通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
