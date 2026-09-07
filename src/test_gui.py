"""GUI 冒烟测试: 构建窗口→载入图像→模拟嵌入→销毁(不进入 mainloop)。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import tkinter as tk
import numpy as np

import image_io as IO
from gui import App

def main():
    root = tk.Tk()
    app = App(root)
    # 构造一张测试图并载入 (256x256 足够容纳头部+正文)
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
    # 直接渲染嵌入(同步)
    from ns5_core import embed_string
    stego, rep, nb = embed_string(gray, "smoke test", method="nsF5", p=3)
    app._show_in(app.lbl_stego, stego)
    root.update()
    # 教学面板冒烟: 打开矩阵编码演示并启动/停止自动演示动画
    top = app._demo_matrix()
    root.update()
    app._md_anim_play(top)
    root.update()
    assert top._md_play["step"] == 1, "自动演示应在第一轮生成随机块"
    app._md_anim_stop(top)
    top.destroy()
    root.update()
    root.destroy()
    print("[OK] GUI 冒烟测试通过 (窗口构建/载入/预览/教学动画正常)")

if __name__ == "__main__":
    main()
