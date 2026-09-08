"""GUI 冒烟测试: 构建窗口→载入图像→模拟嵌入→教学面板→(不开 mainloop)。

覆盖主窗口、菜单、快捷键、进度条、差异视图、矩阵编码演示面板、
扫描面板构建、主题配置, 以及线程安全回调队列。
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import tkinter as tk
import numpy as np

import image_io as IO
import gui
from gui import App


def main():
    root = tk.Tk()
    gui._configure_theme(root)          # 主题配置不应崩溃
    app = App(root)
    assert hasattr(app, "progress") and hasattr(app, "cb_diff")
    assert app._queue is not None
    # 菜单与快捷键
    assert root.cget("menu"), "应有菜单栏"
    for pat in ("<Control-o>", "<Control-e>", "<Control-d>", "<Control-a>", "<Control-s>"):
        assert root.bind(pat), f"应绑定快捷键 {pat}"

    # 构造测试图并载入
    x = np.linspace(0, 100, 256)[None, :]
    y = np.linspace(0, 80, 256)[:, None]
    gray = np.clip(120 + x + y, 0, 255).astype(np.uint8)
    test_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "img", "_smoke.png")
    IO.save_image(gray, test_path)
    app.cover_path = test_path
    app.cover_img = gray
    app._show_in(app.lbl_cover, gray)
    app.var_msg.delete("1.0", "end")
    app.var_msg.insert("1.0", "smoke test")
    root.update()
    # 状态栏与演示图/复制方法
    app._refresh_statusbar()
    assert "图尺寸" in app.statusbar.cget("text")
    assert callable(app._load_demo) and callable(app._copy_out)

    from ns5_core import embed_string
    stego, rep, nb = embed_string(gray, "smoke test", method="nsF5", p=3)
    app._show_in(app.lbl_stego, stego)
    app.stego_img = stego
    app.stego = stego
    app.cb_diff.configure(state="normal")   # 嵌入后差异视图应可用
    root.update()
    assert app.var_diff.get() is False
    app.var_diff.set(True); app._toggle_diff(); root.update()
    assert "差异" in app.lbl_stego_hdr.cget("text")
    app.var_diff.set(False); app._toggle_diff(); root.update()
    assert "含密图" in app.lbl_stego_hdr.cget("text")

    # 矩阵编码演示 + 自动动画
    top = app._demo_matrix()
    root.update()
    assert hasattr(top, "_md_hcv") and len(top._md_hcv.find_all()) > 0
    app._md_anim_play(top)
    root.update()
    assert top._md_play["step"] == 1, "自动演示应在第一轮生成随机块"
    app._md_anim_stop(top)
    top.destroy()
    root.update()

    # 扫描面板构建(不触发真实扫描: 取消防抖回调)
    sp = app._scan_panel()
    root.update()
    if sp._sp_id is not None:
        sp.after_cancel(sp._sp_id)
        sp._sp_id = None
    assert sp._sp["stat"] is not None and sp._sp["ph"] is not None
    sp.destroy()
    root.update()

    root.destroy()
    print("[OK] GUI 冒烟测试通过 (窗口/菜单/快捷键/差异/教学面板/扫描面板/主题/线程队列 正常)")


if __name__ == "__main__":
    main()
