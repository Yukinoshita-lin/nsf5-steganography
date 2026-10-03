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

# v1.9.0 tag 首跑实测: CI 的 GUI 作业 (无头 Linux + xvfb) 在这里挂死 40 分钟
# 以上 —— 作业本身没有 timeout, 一直是 in_progress, 连带 deploy 作业一起卡住。
# 原因不是死循环, 而是**模态弹窗**: CI 的 GUI 作业只装 numpy/pillow/matplotlib,
# 所以 yccstego 不可用, 而 gui._on_domain_change() 在"切到 JPEG 域但依赖缺失"
# 时会 messagebox.showwarning(...) —— 那是一等一的阻塞调用, 无头环境里没人能点
# 它 (Windows 上同样分支却会立刻返回, 所以本地一直没暴露)。
# 冒烟测试不允许被任何模态弹窗卡住: 这里把 messagebox 换成记录器, 弹窗该走的
# 分支照走 (反而把弹窗路径纳入覆盖), 但绝不进入对话框事件循环。
_DIALOGS = []


def _stub_messagebox():
    import tkinter.messagebox as mb
    _real = {n: getattr(mb, n) for n in
             ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel")}

    def _recorder(kind):
        def _call(title="", message="", **_kw):
            _DIALOGS.append((kind, str(title), str(message)))
            return True if kind in ("askyesno", "askokcancel") else "ok"
        return _call

    for name in _real:
        setattr(mb, name, _recorder(name))
    return _real


def _restore_messagebox(real):
    import tkinter.messagebox as mb
    for name, fn in real.items():
        setattr(mb, name, fn)


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

    # 演示图一键生成 (wheel 安装布局里没有 img/cover.png): 确定性 + 可载入
    import tempfile
    demo_p = os.path.join(tempfile.mkdtemp(), "cover.png")
    g1 = gui.generate_demo_cover(demo_p)
    assert g1.shape == (256, 256), "演示封面应为 256x256 灰度"
    assert (IO.load_as_gray(demo_p) == g1).all(), "生成后应能原样载入"
    assert (g1 == gui.generate_demo_cover(demo_p)).all(), \
        "seed=42 的确定性配方: 重生成必须逐字节一致"

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

    # 嵌入域选择 (v1.9.0): 默认像素域; 切 JPEG 域时质量框才可用
    import jpegstego
    import experiment as EXP
    assert app._domain() == "pixel"
    # 依赖缺失时 _on_domain_change 会弹模态警告 —— 换成记录器, 否则无头 CI 挂死
    _real_mb = _stub_messagebox()
    try:
        app.var_domain.set(gui._DOMAIN_JPEG); app._on_domain_change()
    finally:
        _restore_messagebox(_real_mb)
    if jpegstego.available():
        assert app._domain() == "jpeg"
        assert str(app.qbox.cget("state")) != "disabled"
        assert app.var_method.get().startswith("nsF5"), "JPEG 域固定 nsF5 语义"
        out_jpg = os.path.join(tempfile.mkdtemp(), "smoke_stego.jpg")
        jpg, jrep, jnbits, jrec = app._do_embed_jpeg(
            test_path, "smoke jpeg", 3, "", 85, out_jpg)
        assert jrec["algorithm"]["domain"] == "jpeg"
        assert jrec["result"]["cell_unit"] == "coefficients"
        assert "smoke jpeg" not in EXP.dumps(jrec), "档案不含消息明文"
        msg, tampered, _ = app._do_decode_jpeg(jpg, 3, "")
        assert msg == "smoke jpeg" and tampered is False
        ok, jch, unit, _, _ = app._do_selfcheck("jpeg", "nsF5", 3, "", "自检42")
        assert ok is True and unit == "个 DCT 系数"
        print("[OK] JPEG 域: 嵌入→解码往返 + 自检闭环 + 档案 schema")
    else:
        # CI 的 GUI 作业只装 numpy/pillow/matplotlib, 走的就是这条路:
        # 依赖缺失必须被拦下、回退像素域, 而且弹窗路径要真的走到 (记录器兜住)
        assert app._domain() == "pixel"
        assert any(k == "showwarning" and "JPEG 域不可用" in t
                   for k, t, _ in _DIALOGS), \
            f"依赖缺失切 JPEG 域应弹警告并回退 (实际弹窗: {_DIALOGS})"
        print("[SKIP] yccstego 未安装: JPEG 域回退 + 依赖缺失弹窗已验证")
    app.var_domain.set(gui._DOMAIN_PIXEL); app._on_domain_change()
    assert app._domain() == "pixel"

    # 往返自检 (像素域) + 实验档案生成
    ok, pch, punit, pnbits, _ = app._do_selfcheck("pixel", "nsF5", 3, "", "自检42")
    assert ok is True and punit == "个像素"
    stego2, out2, rep2, nb2, ch2, rec2 = app._do_embed_pixel(
        gray, "smoke test", "nsF5", 3, "", os.path.join(tempfile.mkdtemp(), "s.png"),
        test_path)
    assert rec2["schema"] == EXP.SCHEMA
    assert rec2["determinism"] == EXP.DET_BYTE
    assert rec2["payload"]["bits"] == nb2
    assert "smoke test" not in EXP.dumps(rec2)
    app.last_record = rec2
    assert callable(app._selfcheck) and callable(app._export_record)
    print("[OK] 像素域: 往返自检闭环 + 实验档案 schema")

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


def test_gui_smoke():
    """pytest 入口。

    Tk 需要显示环境。无显示时 `TclError: no display name and no $DISPLAY` 是
    环境限制而非缺陷, 所以这种情况下跳过 —— 否则 `pytest -q` 在任何无头机器
    上都会红, 而它本来只是没跑 GUI 而已。

    但不能因此让 GUI 测试悄悄消失: CI 的 `GUI 冒烟测试 (xvfb)` job 会设
    `NSF5_REQUIRE_GUI=1`, 那时跳过会变成失败。也就是说"跳过"必须在别处被
    真正跑过, 不允许两边都不跑。
    """
    try:
        main()
    except tk.TclError as exc:
        if "display" in str(exc).lower() and not os.environ.get("NSF5_REQUIRE_GUI"):
            import pytest
            pytest.skip(f"无显示环境, GUI 冒烟测试由 CI 的 xvfb job 负责: {exc}")
        raise


if __name__ == "__main__":
    main()
