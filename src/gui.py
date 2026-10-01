"""
nsF5 隐写工具 —— tkinter GUI
功能: 嵌入(ASCII 字符串) / 解码 / 盲隐写分析 / 码族与效率绘图。
"""
from __future__ import annotations
import os
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
import traceback

import numpy as np
from PIL import Image, ImageTk

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_DIR, "src"))

from ns5_core import embed_string, extract_string, get_image_hash
import steganalysis as SA
import image_io as IO
from efficiency import plot_code_family_and_efficiency
from pathutil import app_version, output_dir
from ml_predict import get_predictor
import matrix_demo as MD
import scan_panel as SP

# 源码运行 -> 仓库 output/; pip 安装后 PROJECT_DIR 是解释器根,
# 产物必须落到工作目录, 不能写进 site-packages (见 pathutil.output_dir)。
OUTPUT_DIR = output_dir(PROJECT_DIR)


# 蓝白"国企风"色板: ttk 主题 (_configure_theme) 与非 ttk 控件 (横幅/画布/
# 文本框) 共用这一份, 防止两处各写各的灰。朴素原则: 大面积白 + 极浅蓝,
# 深蓝只出现在横幅/主按钮/标题这些"锚点"上。
C_BG = "#f4f7fb"          # 窗口底
C_CARD = "#ffffff"        # 内容卡片
C_FG = "#1f2a37"          # 正文
C_MUTED = "#5f6f80"       # 次要文字
C_NAVY = "#1f4e79"        # 深蓝锚点: 横幅 / 主按钮 / 标题
C_NAVY_DARK = "#16395c"   # 主按钮按下
C_NAVY_HOVER = "#265f92"  # 主按钮悬停
C_BLUE = "#2e75b6"        # 亮蓝: 状态 / 进度条 / 强调
C_BLUE_LIGHT = "#e8f1fa"  # 浅蓝: 状态栏 / 标签页底
C_BORDER = "#b9cfe6"      # 统一浅蓝边框
C_CANVAS = "#eef3f9"      # 图像预览画布底
def _ui_family():
    """跨平台 UI 字型: 各平台取原生黑体, Tk 对缺失字型自动回退默认。"""
    if sys.platform == "darwin":
        return "PingFang SC"
    if os.name == "nt":
        return "Microsoft YaHei UI"
    return "Noto Sans CJK SC"


FONT_FAMILY = _ui_family()
FONT_UI = (FONT_FAMILY, 10)
FONT_UI_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_BANNER = (FONT_FAMILY, 13, "bold")


class Tooltip:
    """轻量气泡提示 (纯 tk, 无第三方依赖): 悬停 600ms 后显示。"""

    def __init__(self, widget, text, delay=600):
        self.widget, self.text, self.delay = widget, text, delay
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _hide(self, _=None):
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def _show(self):
        if self._tip is not None:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, justify="left", bg=C_BLUE_LIGHT,
                 fg=C_FG, font=FONT_SMALL, relief="solid", borderwidth=1,
                 padx=8, pady=4).pack()


def _rgb(img: np.ndarray):
    """灰度/彩图 → RGB 便于显示。"""
    a = np.ascontiguousarray(img)
    if a.ndim == 3:
        return a
    return np.stack([a, a, a], axis=-1)


def generate_demo_cover(path: str) -> np.ndarray:
    """生成教学演示封面 (256x256 灰度, 平滑渐变 + 轻噪声)。

    配方与 run_e2e.py 的封面完全一致 (seed=42): 同一种子在任何机器生成
    的图逐字节相同, GUI 与 CLI/e2e 的演示内容因此可互相对照。"""
    rng = np.random.default_rng(42)
    y = np.linspace(0, 220, 256)[None, :]
    x = np.linspace(0, 90, 256)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (256, 256)), 12, 255).astype(np.uint8)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    IO.save_image(img, path)
    return img


def _style_text(w: tk.Text, height: int | None = None) -> tk.Text:
    """白底浅蓝边框的多行文本框 (嵌入内容 / 日志 / 结果输出 共用观感)。"""
    w.configure(bg=C_CARD, fg=C_FG, insertbackground=C_FG, relief="flat",
                padx=6, pady=4, font=FONT_UI,
                selectbackground="#cfe2f6", selectforeground=C_FG,
                highlightthickness=1, highlightbackground=C_BORDER,
                highlightcolor=C_BLUE)
    if height is not None:
        w.configure(height=height)
    return w


class ImageViewer(ttk.Frame):
    """可缩放的图像预览: 滚轮缩放, 拖拽平移, 双击复位。"""

    def __init__(self, master, placeholder="(空)"):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=C_CANVAS, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="both", expand=True)
        self._img = None
        self._photo = None
        self._zoom = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self._placeholder = placeholder
        self._drag = None
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Double-Button-1>", lambda e: self._reset())
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<Configure>", lambda e: self._draw())
        self.show_placeholder(placeholder)

    def set_image(self, img: np.ndarray):
        self._img = img
        self._zoom = 1.0
        self._ox = self._oy = 0.0
        self._draw()

    def show_placeholder(self, text: str | None = None):
        self._img = None
        if text is not None:
            self._placeholder = text
        self._draw_placeholder()

    def _draw_placeholder(self):
        self.canvas.delete("all")
        self.canvas.configure(bg="#f8fafc")   # 空态近乎融入白卡, 消除大色块
        cw = max(1, self.canvas.winfo_width()); ch = max(1, self.canvas.winfo_height())
        if cw < 10 or ch < 10:
            return
        self.canvas.create_text(cw / 2, ch / 2 - 10, text=self._placeholder,
                                fill="#5f6f80", font=(FONT_FAMILY, 10))
        self.canvas.create_text(cw / 2, ch / 2 + 14,
                                text="载入后可滚轮缩放 / 拖拽平移",
                                fill="#a9b8c8", font=(FONT_FAMILY, 9))

    def _reset(self):
        self._zoom = 1.0
        self._ox = self._oy = 0.0
        self._draw()

    def _draw(self):
        self.canvas.delete("all")
        if self._img is None:
            self._draw_placeholder(); return
        self.canvas.configure(bg=C_CANVAS)   # 载入后恢复画布底色
        cw = max(1, self.canvas.winfo_width()); ch = max(1, self.canvas.winfo_height())
        if cw < 10 or ch < 10:
            return
        im = Image.fromarray(_rgb(self._img))
        iw, ih = im.size
        scale = min(cw / iw, ch / ih) * self._zoom
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        resample = getattr(Image, "Resampling", Image).LANCZOS
        sim = im.resize((nw, nh), resample)
        ph = ImageTk.PhotoImage(sim)
        self._photo = ph
        self.canvas.create_image(cw / 2 + self._ox, ch / 2 + self._oy, image=ph, anchor="center")
        self.canvas.create_text(8, 8, anchor="nw", fill=C_MUTED,
                                font=(FONT_FAMILY, 9),
                                text=f"{nw}×{nh}  ({self._zoom:.1f}× · 滚轮缩放/拖拽平移)")

    def _on_wheel(self, e):
        if self._img is None:
            return
        self._zoom = max(0.2, min(8.0, self._zoom * (1.15 if e.delta > 0 else 1 / 1.15)))
        self._draw()

    def _on_press(self, e):
        self._drag = (e.x, e.y)

    def _on_motion(self, e):
        if self._drag:
            self._ox += e.x - self._drag[0]
            self._oy += e.y - self._drag[1]
            self._drag = (e.x, e.y)
            self._draw()


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        # 标题栏带版本号: 用户报问题时截图即含版本 (源码未安装则不显示)
        from pathutil import app_version
        _v = app_version()
        root.title("nsF5 隐写工具" + (f" v{_v}" if _v else "")
                   + " — 伴随式矩阵编码 + 湿纸编码 + 盲隐写分析")
        root.geometry("1120x720")
        root.minsize(900, 560)
        self._center(root)
        self.cover_path = None
        self.stego_path = None
        self.cover_img = None
        self.stego_img = None
        # 线程安全的"主线程回调"队列: 后台线程只入队, 主线程 _poll 依次执行
        self._queue = queue.Queue()
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()
        self._poll()

    def _poll(self):
        try:
            while True:
                fn, args = self._queue.get_nowait()
                try:
                    fn(*args)
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    # ------------------------------------------------------- 窗口基础
    def _center(self, root):
        root.update_idletasks()
        w, h = 1120, 740   # 日志移入右栏页签后, 740 已足够容纳全部行
        x = (root.winfo_screenwidth() - w) // 2
        y = (root.winfo_screenheight() - h) // 2
        root.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        mfile = tk.Menu(menubar, tearoff=0)
        mfile.add_command(label="载入原始图 / 含密图…", accelerator="Ctrl+O", command=self._load)
        mfile.add_command(label="保存含密图…", accelerator="Ctrl+S", command=self._save_stego)
        mfile.add_separator()
        mfile.add_command(label="打开输出目录", command=self._open_output)
        mfile.add_separator()
        mfile.add_command(label="退出", accelerator="Esc", command=self.root.destroy)
        menubar.add_cascade(label="文件", menu=mfile)
        mhelp = tk.Menu(menubar, tearoff=0)
        mhelp.add_command(label="关于", command=self._about)
        menubar.add_cascade(label="帮助", menu=mhelp)
        self.root.config(menu=menubar)

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self._load())
        self.root.bind("<Control-e>", lambda e: self._embed())
        self.root.bind("<Control-d>", lambda e: self._decode())
        self.root.bind("<Control-a>", lambda e: self._analyze())
        self.root.bind("<Control-s>", lambda e: self._save_stego())

    def _about(self):
        messagebox.showinfo(
            "关于",
            "nsF5 隐写工具\n\n"
            "伴随式矩阵编码 + 湿纸编码 + 盲隐写分析\n"
            "算法核心: ns5_core.py  |  分析: steganalysis.py  |  ML: ml_predict.py\n\n"
            "快捷键: Ctrl+O 载入 · Ctrl+E 嵌入 · Ctrl+D 解码 · Ctrl+A 分析 · Ctrl+S 保存含密图\n\n"
            "联系与反馈: eu-lin@foxmail.com")

    def _save_stego(self):
        if self.stego_img is None:
            messagebox.showwarning("提示", "请先嵌入生成含密图"); return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG 图像", "*.png"), ("BMP 图像", "*.bmp")],
            initialfile=os.path.basename(self.stego_path or "stego.png"))
        if not path:
            return
        try:
            IO.save_image(self.stego_img, path)
            self._log("含密图已保存: " + path)
            self._wait("已保存")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def _open_output(self):
        outdir = OUTPUT_DIR
        os.makedirs(outdir, exist_ok=True)
        try:
            os.startfile(outdir)
        except Exception as e:
            self._log("无法打开输出目录: " + str(e))

    # ------------------------------------------------------- UI 构建
    def _build_ui(self):
        # 顶部深蓝横幅: 蓝白"国企风"的视觉锚点 (应用名 + 副标题 + 版本)
        banner = tk.Frame(self.root, bg=C_NAVY)
        banner.pack(fill="x")
        tk.Label(banner, text="nsF5 隐写工具", bg=C_NAVY, fg="#ffffff",
                 font=FONT_BANNER).pack(side="left", padx=(14, 8), pady=9)
        tk.Label(banner, text="伴随式矩阵编码 · 湿纸编码 · 盲隐写分析",
                 bg=C_NAVY, fg="#cfe0f3", font=FONT_UI
                 ).pack(side="left", pady=9)
        _v = app_version()
        tk.Label(banner, text=("v" + _v) if _v else "",
                 bg=C_NAVY, fg="#9fc0e2", font=FONT_UI
                 ).pack(side="right", padx=14)

        # 窗口图标 (iconphoto 跨平台; 资产缺失时静默跳过)
        _icon_path = os.path.join(PROJECT_DIR, "img", "app-icon.png")
        if os.path.exists(_icon_path):
            try:
                self._win_icon = tk.PhotoImage(file=_icon_path)
                self.root.iconphoto(True, self._win_icon)
            except Exception:
                pass

        mf = ttk.Frame(self.root, padding=6)
        mf.pack(fill="both", expand=True)
        mf.columnconfigure(0, weight=1, uniform="a")
        mf.columnconfigure(1, weight=1, uniform="a")
        mf.rowconfigure(0, weight=1)

        self.left = self._build_left(mf)
        self.right = self._build_right(mf)

        # 进度条仅在忙时显示, 不占常驻空间
        self._prog_frame = ttk.Frame(mf)
        self._prog_frame.grid(row=1, column=0, columnspan=2, sticky="ew",
                              pady=(4, 0))
        self.progress = ttk.Progressbar(self._prog_frame, mode="indeterminate")
        self.progress.pack(fill="x")
        self._prog_frame.grid_remove()

        sbf = ttk.Frame(mf)
        sbf.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        self.statusbar = ttk.Label(sbf, text="", anchor="w",
                                   style="Status.TLabel")
        self.statusbar.pack(fill="x")
        self._refresh_statusbar()
        self._log("就绪。请载入图片进行操作。")

        # 新手引导第一步: 打开即载入演示封面, 首屏就有图可看
        try:
            demo = os.path.join(PROJECT_DIR, "img", "cover.png")
            if not os.path.exists(demo):
                demo = os.path.join(OUTPUT_DIR, "demo_cover.png")
                generate_demo_cover(demo)
            self._load_path(demo)
            self._guide("第一次用? 已为你载入一张演示图 —— "
                        "直接点下方蓝色「嵌入并保存」试试 (Ctrl+E)")
        except Exception:
            pass   # 自动载入失败不打断启动, 用户可手动载入

    def _build_left(self, parent):
        f = ttk.LabelFrame(parent, text="操作台", padding=10)
        f.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        f.columnconfigure(0, weight=1)

        # 新手引导条: 始终指明"下一步点哪里" (随操作状态推进)
        self.guide = ttk.Label(f, text="", style="Guide.TLabel",
                               wraplength=470, justify="left")
        self.guide.grid(row=0, column=0, sticky="ew")

        def sec(row, text):
            box = ttk.Frame(f, style="Card.TFrame")
            box.grid(row=row, column=0, sticky="ew", pady=(12, 5))
            ttk.Label(box, text=text, style="Section.TLabel").pack(
                side="left", pady=(0, 3))
            ttk.Separator(box, orient="horizontal").pack(fill="x")

        # ---- 输入: 按工作流排在最前 ----
        sec(1, "输入")
        bf = ttk.Frame(f, style="Card.TFrame")
        bf.grid(row=2, column=0, sticky="ew")
        bf.columnconfigure(0, weight=1)
        b_load = ttk.Button(bf, text="载入原始图 / 含密图", command=self._load)
        b_load.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        b_demo = ttk.Button(bf, text="演示图", command=self._load_demo)
        b_demo.grid(row=0, column=1)
        Tooltip(b_load, "打开图片文件 (Ctrl+O)\n支持 PNG / BMP / JPEG / TIFF")
        Tooltip(b_demo, "一键载入内置演示封面\n(256x256, 与教学手册同一张图)")

        ttk.Label(f, text="待嵌入的文本 (UTF-8):").grid(
            row=3, column=0, sticky="w", pady=(8, 2))
        self.var_msg = _style_text(tk.Text(f, height=5, width=40))
        self.var_msg.grid(row=4, column=0, sticky="nsew")
        self.var_msg.insert("1.0", "Hello, nsF5 steganography!")
        ttk.Label(f, text="解码时需使用相同的 方法 / p / 口令",
                  style="Muted.TLabel").grid(row=5, column=0, sticky="w")
        f.rowconfigure(4, weight=1)   # 余量给文本框, 长文本自然扩展

        # ---- 参数 ----
        sec(6, "参数")
        pf = ttk.Frame(f, style="Card.TFrame")
        pf.grid(row=7, column=0, sticky="ew")
        pf.columnconfigure(1, weight=1, uniform="h")
        pf.columnconfigure(3, weight=1, uniform="h")
        self.var_method = tk.StringVar(value="nsF5")
        _cbm = ttk.Combobox(pf, textvariable=self.var_method, state="readonly",
                            values=["nsF5 (减幅+湿纸)", "matrix (LSB矩阵编码)"])
        self.var_p = tk.StringVar(value="3")
        pbox = ttk.Combobox(pf, textvariable=self.var_p, state="readonly",
                            values=[str(i) for i in range(1, 9)])
        self.var_pwd = tk.StringVar(value="")
        _pwd = ttk.Entry(pf, textvariable=self.var_pwd, show="*")
        self.var_sens = tk.StringVar(value="均衡")
        sbox = ttk.Combobox(pf, textvariable=self.var_sens, state="readonly",
                            values=["严格 (低误报)", "均衡", "宽松 (高检出)"])
        ttk.Label(pf, text="算法:").grid(row=0, column=0, sticky="w")
        _cbm.grid(row=0, column=1, sticky="ew", padx=(2, 10), pady=2)
        ttk.Label(pf, text="参数 p:").grid(row=0, column=2, sticky="w")
        pbox.grid(row=0, column=3, sticky="ew", padx=(2, 0), pady=2)
        ttk.Label(pf, text="口令:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        _pwd.grid(row=1, column=1, sticky="ew", padx=(2, 10), pady=(6, 0))
        l_sens = ttk.Label(pf, text="灵敏度:")
        l_sens.grid(row=1, column=2, sticky="w", pady=(6, 0))
        sbox.grid(row=1, column=3, sticky="ew", padx=(2, 0), pady=(6, 0))
        Tooltip(l_sens, "严格: 少误报干净图\n均衡: 默认\n宽松: 更易检出弱嵌入")
        Tooltip(_pwd, "可选。留空则不加口令\n解码时必须输入完全相同的口令")
        _cbm.bind("<<ComboboxSelected>>", lambda *_: self._refresh_statusbar())
        pbox.bind("<<ComboboxSelected>>", lambda *_: self._refresh_statusbar())

        # ---- 执行 ----
        sec(8, "执行")
        af = ttk.Frame(f, style="Card.TFrame")
        af.grid(row=9, column=0, sticky="ew")
        af.columnconfigure(0, weight=1, uniform="x")
        af.columnconfigure(1, weight=1, uniform="x")
        af.columnconfigure(2, weight=1, uniform="x")
        b_embed = ttk.Button(af, text="嵌入并保存", style="Primary.TButton",
                             command=self._embed)
        b_dec = ttk.Button(af, text="解码提取", style="Primary.TButton",
                           command=self._decode)
        b_ana = ttk.Button(af, text="分析", style="Primary.TButton",
                           command=self._analyze)
        b_embed.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        b_dec.grid(row=0, column=1, sticky="ew", padx=6)
        b_ana.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        Tooltip(b_embed, "把文本写入图片并保存 (Ctrl+E)")
        Tooltip(b_dec, "从含密图还原文本 (Ctrl+D)")
        Tooltip(b_ana, "卡方 + RS + ML 盲隐写分析 (Ctrl+A)")
        af2 = ttk.Frame(f, style="Card.TFrame")
        af2.grid(row=10, column=0, sticky="ew", pady=(10, 0))
        af2.columnconfigure(0, weight=1, uniform="y")
        af2.columnconfigure(1, weight=1, uniform="y")
        af2.columnconfigure(2, weight=1, uniform="y")
        ttk.Button(af2, text="生成效率图", command=self._plot).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(af2, text="编码演示", command=self._demo_matrix).grid(
            row=0, column=1, sticky="ew", padx=6)
        ttk.Button(af2, text="载荷扫描", command=self._scan_panel).grid(
            row=0, column=2, sticky="ew", padx=(6, 0))

        # ---- 状态 ----
        self.status = ttk.Label(f, text="状态: 就绪", foreground=C_BLUE)
        self.status.grid(row=11, column=0, sticky="w", pady=(12, 0))
        return f

    def _build_right(self, parent):
        f = ttk.LabelFrame(parent, text="预览与结果", padding=8)
        f.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        f.columnconfigure(0, weight=1, uniform="b")
        f.columnconfigure(1, weight=1, uniform="b")
        f.rowconfigure(1, weight=1)

        ttk.Label(f, text="原始 / 封面").grid(row=0, column=0)
        self.lbl_stego_hdr = ttk.Label(f, text="含密图")
        self.lbl_stego_hdr.grid(row=0, column=1)
        self.lbl_cover = ImageViewer(
            f, placeholder="(未载入 - 点「演示图」或 Ctrl+O)")
        self.lbl_cover.grid(row=1, column=0, sticky="nsew")
        self.lbl_stego = ImageViewer(f, placeholder="(未生成 - 嵌入后显示)")
        self.lbl_stego.grid(row=1, column=1, sticky="nsew")

        # 差异图切换
        ctrl = ttk.Frame(f, style="Card.TFrame")
        ctrl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.var_diff = tk.BooleanVar(value=False)
        self.cb_diff = ttk.Checkbutton(ctrl, text="查看差异(×255)",
                                       variable=self.var_diff,
                                       command=self._toggle_diff,
                                       state="disabled")
        self.cb_diff.pack(side="left")
        ttk.Label(ctrl, text="  仅在有含密图时可用",
                  style="Muted.TLabel").pack(side="left", padx=6)

        # 文本结果与日志收进页签: 结果是主角, 日志退居次要
        nb = ttk.Notebook(f)
        nb.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        tab_out = ttk.Frame(nb, style="Card.TFrame")
        tab_log = ttk.Frame(nb, style="Card.TFrame")
        nb.add(tab_out, text=" 分析结果 ")
        nb.add(tab_log, text=" 运行日志 ")
        tab_out.columnconfigure(0, weight=1)
        tab_out.rowconfigure(1, weight=1)
        ttk.Button(tab_out, text="复制结果", command=self._copy_out).grid(
            row=0, column=0, sticky="e", padx=8, pady=(2, 2))
        self.out = _style_text(tk.Text(tab_out, height=8, state="disabled",
                                       wrap="word"))
        self.out.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        tab_log.columnconfigure(0, weight=1)
        tab_log.rowconfigure(0, weight=1)
        self.log = _style_text(tk.Text(tab_log, height=8, state="disabled",
                                       wrap="word"))
        self.log.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        f.rowconfigure(3, weight=1)
        return f

    def _toggle_diff(self):
        """在 含密图 与 |cover-stego|*255 之间切换右侧预览。"""
        if self.cover_img is None or self.stego_img is None:
            self.var_diff.set(False)
            self.cb_diff.configure(state="disabled")
            return
        if self.var_diff.get():
            diff = np.abs(self.cover_img.astype(np.int16) - self.stego_img.astype(np.int16)).clip(0, 255).astype(np.uint8)
            self.lbl_stego_hdr.configure(text="差异(×255)")
            self._show_in(self.lbl_stego, diff)
        else:
            self.lbl_stego_hdr.configure(text="含密图")
            self._show_in(self.lbl_stego, self.stego_img)

    # ------------------------------------------------------- 工具
    def _log(self, msg: str):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_out(self, msg: str):
        self.out.configure(state="normal")
        self.out.delete("1.0", "end")
        self.out.insert("end", msg)
        self.out.configure(state="disabled")

    def _copy_out(self):
        txt = self.out.get("1.0", "end").strip()
        if not txt:
            messagebox.showinfo("提示", "当前无可复制的结果"); return
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        self._log("结果已复制到剪贴板")

    def _refresh_statusbar(self):
        m = self.var_method.get()
        size = (f"{self.cover_img.shape[1]}×{self.cover_img.shape[0]}"
                if self.cover_img is not None else "-")
        self.statusbar.configure(text=f"方法: {m}  ·  p={self.var_p.get()}  ·  图尺寸: {size}")

    def _wait(self, t):
        self.status.configure(text="状态: " + t)

    def _guide(self, text):
        """新手引导条: 始终告诉用户"下一步点哪里"。"""
        self.guide.configure(text=text)

    def _show_in(self, widget: ttk.Label, image: np.ndarray):
        if hasattr(widget, "set_image"):        # ImageViewer
            widget.set_image(image); return
        w = widget.winfo_width()
        h = widget.winfo_height()
        if w < 40 or h < 40:
            w, h = 320, 240
        im = Image.fromarray(_rgb(image))
        im.thumbnail((w, h))
        ph = ImageTk.PhotoImage(im)
        widget.configure(image=ph)
        widget.image = ph

    def _busy(self, fn, on_done, *args, **kwargs):
        """后台线程执行, 结果通过队列回主线程执行 on_done (线程安全)。"""
        self._wait("处理中…")
        self._prog_frame.grid()
        self.progress.start(12)
        def worker():
            try:
                res = fn(*args, **kwargs)
                self._queue.put((on_done, (res,)))
            except Exception as e:
                traceback.print_exc()
                self._queue.put((self._on_busy_error, (e,)))
            finally:
                self._queue.put((self._on_busy_end, ()))
        threading.Thread(target=worker, daemon=True).start()

    def _on_busy_end(self):
        self.progress.stop()
        self._prog_frame.grid_remove()

    def _on_busy_error(self, e):
        self._set_out(f"出错: {e}")
        self._wait("失败")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("图像", (".png", ".bmp", ".jpg", ".jpeg", ".tif", ".tiff"))])
        if not path:
            return
        self._load_path(path)

    def _load_demo(self):
        p = os.path.join(PROJECT_DIR, "img", "cover.png")
        if not os.path.exists(p):
            # 演示图随仓库分发, 但 wheel 安装布局里没有 —— 与其提示"不存在"
            # 就结束, 不如当场生成 (确定性配方, 任何机器生成的都一致)。
            if not messagebox.askyesno(
                    "生成演示图",
                    "演示图不存在:\n%s\n\n要现在生成吗?\n"
                    "(与 run_e2e.py 相同的确定性封面)" % p):
                return
            try:
                generate_demo_cover(p)
            except Exception as e:
                messagebox.showerror("生成失败", str(e)); return
            self._log("已生成演示图: " + p)
        self._load_path(p)

    def _load_path(self, path: str):
        try:
            gray = IO.load_as_gray(path)
        except Exception as e:
            messagebox.showerror("载入失败", str(e)); return
        self.cover_path = path
        self.cover_img = gray
        self.stego_path = None
        self.stego_img = None
        self.stego = None
        self._show_in(self.lbl_cover, gray)
        self.lbl_stego.show_placeholder("(未生成)")
        self.lbl_stego_hdr.configure(text="含密图")
        self.var_diff.set(False)
        self.cb_diff.configure(state="disabled")
        self._log(f"载入: {path}  尺寸 {gray.shape[1]}x{gray.shape[0]}  "
                  f"SHA256={get_image_hash(gray)[:12]}…")
        self._guide("已载入图片。下一步: 确认文本 → 点「嵌入并保存」(Ctrl+E)")
        self._refresh_statusbar()

    def _params(self):
        m = self.var_method.get()
        method = "nsF5" if m.startswith("nsF5") else "matrix"
        p = int(self.var_p.get())
        return method, p, self.var_pwd.get()

    # ------------------------------------------------------- 动作
    def _embed(self):
        if self.cover_img is None:
            messagebox.showwarning("提示", "请先载入原始图"); return
        msg = self.var_msg.get("1.0", "end").rstrip("\n")
        if not msg:
            messagebox.showwarning("提示", "请输入待嵌入字符串"); return
        method, p, pwd = self._params()
        out = IO.default_out_path(self.cover_path, "stego", OUTPUT_DIR)
        os.makedirs(os.path.dirname(out), exist_ok=True)

        def work():
            stego, report, nbits = embed_string(self.cover_img, msg, method=method, p=p, password=pwd)
            changed = int((stego != self.cover_img).sum())
            IO.save_image(stego, out)
            return stego, out, report, nbits, changed

        def done(res):
            stego, out, report, nbits, changed = res
            self.stego_img = stego
            self.stego = stego
            self.stego_path = out
            self._show_in(self.lbl_stego, stego)
            self.lbl_stego_hdr.configure(text="含密图")
            self.var_diff.set(False)
            self.cb_diff.configure(state="normal")
            self._set_out(
                f"嵌入成功\n保存: {out}\n"
                f"算法: {method}  p={self.var_p.get()}\n"
                f"嵌入比特: {nbits}  改动像素: {changed} ({changed/self.cover_img.size*100:.1f}%)\n"
                f"封面SHA256: {report['cover_hash']}\n\n"
                "提示: 解码时需使用相同的 方法/p/口令。")
            self._log("嵌入完成, 含密图已保存 " + out)
            self._wait("嵌入完成")
            self._guide(
                "嵌入完成! 只改动了 {} 个像素 ({:.1f}%), 肉眼无法分辨。"
                "勾选「查看差异」能放大看到改动位置; 下一步: 点「解码提取」"
                "验证还原".format(changed, changed / self.cover_img.size * 100))
        self._busy(work, done)

    def _decode(self):
        if self.stego is None and self.cover_img is None:
            messagebox.showwarning("提示", "请先载入图片"); return
        method, p, pwd = self._params()
        # 解码/分析的对象是"当前待解读图": 优先用刚嵌入生成的含密图 (stego),
        # 否则用载入的图。G1: 之前恒用 cover_img, 导致"嵌入→解码"必然失败。
        image = self.stego if self.stego is not None else self.cover_img

        def work():
            return extract_string(image, method=method, p=p, password=pwd)

        def done(text):
            text = (text or "").strip()
            if text:
                self._set_out(f"解码成功 (方法={method}, p={p}):\n\n{text}")
                self._guide("解码成功, “藏进去 -> 完整取出来”闭环达成! "
                            "进阶: 换个口令重新嵌入(解码会失败), 或点「编码演示」"
                            "看算法内部")
            else:
                self._set_out(f"未提取到内容 (方法={method}, p={p})。\n请确认: 待解读的图片/方法/p/口令 与嵌入时一致。")
            self._log("解码完成")
            self._wait("解码完成")
        self._busy(work, done)

    def _analyze(self):
        if self.stego is None and self.cover_img is None:
            messagebox.showwarning("提示", "请先载入图片"); return
        # 优先分析"当前待检图" = stego (若已嵌入), 否则载入的图。
        image = self.stego if self.stego is not None else self.cover_img
        sens = self.var_sens.get()
        def work():
            return (SA.analyze(image, sensitivity=sens), get_image_hash(image),
                    get_predictor(sensitivity=sens).predict(image))
        def done(res):
            r, h, ml = res
            ml_line = (f"ML 分类含密概率: {ml['probability']*100:.1f}%  (阈值 {ml['threshold']:.3f}, {ml['verdict']})\n"
                       if ml["probability"] is not None else
                       "ML 分类: 模型未加载(请先运行 train_model.py)\n")
            self._set_out(
                f"图像 SHA256: {h}\n"
                f"判定灵敏度: {r['sensitivity']}\n"
                f"卡方统计量 χ²={r['chi2_stat']:.2f}  (df={'-'})\n"
                f"卡方 p 值: {r['chi2_pvalue']:.4f}\n"
                f"前缀中位 p: {r['median_prefix_p']:.4f}\n"
                f"内容本底噪声: 灰度熵 {r['diff_entropy']:.2f}  LSB熵 {r['lsb_diff_entropy']:.3f}\n"
                f"RS 掩码缺口 Gr={r['RS_Gr']:.3f}  Gn={r['RS_Gn']:.3f}\n"
                f"估计嵌入率: {r['est_rate']*100:.1f}%\n"
                f"\n隐写概率: {r['stego_probability']*100:.1f}%\n"
                f"判读: {r['verdict']}\n"
                f"{ml_line}\n")
            self._wait("分析完成")
        self._busy(work, done)

    def _plot(self):
        def work():
            # plot_code_family_and_efficiency 返回计算行(list), 图片写至 save_path
            out = os.path.join(OUTPUT_DIR, "efficiency.png")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            plot_code_family_and_efficiency(p_max=6, save_path=out)
            return out
        def done(path):
            try:
                im = Image.open(path).convert("RGB")
                scr_w = self.root.winfo_screenwidth()
                scr_h = self.root.winfo_screenheight()
                resample = getattr(Image, "Resampling", Image).LANCZOS
                # 预览尽量接近原始分辨率(大图基本 1:1), 文字清晰; 仅在超出屏幕时按比例缩放
                im.thumbnail((int(scr_w * 0.9), int(scr_h * 0.78)), resample)
                ph = ImageTk.PhotoImage(im)
                top = tk.Toplevel(self.root)
                top.title(f"码族与嵌入效率 ({im.width}×{im.height})")
                lab = ttk.Label(top, image=ph); lab.image = ph
                lab.pack(padx=8, pady=8)
                ttk.Label(top, text=f"已保存: {path}").pack(padx=8, pady=(0, 8))
            except Exception as e:
                self._log(f"绘图预览失败: {e}")
            self._wait("绘图已生成")
            self._log("码族与嵌入效率图已生成: " + path)
        self._busy(work, done)

    # ------------------------------------------------------- 增强面板 1: 矩阵编码演示
    def _demo_matrix(self):
        top = tk.Toplevel(self.root, bg=C_CARD)
        top.title("伴随式矩阵编码演示 (syndrome 查找与系数翻转)")
        pv, tv = tk.StringVar(value="3"), tk.StringVar(value="110")
        top._md_pvar, top._md_tvar, top._md_x = pv, tv, MD.random_block(3)
        top._md_cv, top._md_hcv, top._md_cell, top._md_n = None, None, 30, 7
        top._md_play = {"id": None, "stop": False, "phase": "show",
                        "delay": 1200, "step": 0}

        # 参数行
        bar = ttk.Frame(top, style="Card.TFrame", padding=(8, 6)); bar.pack(fill="x")
        ttk.Label(bar, text="参数 p:").pack(side="left")
        cbbp = ttk.Combobox(bar, textvariable=pv, state="readonly", width=4,
                            values=[str(i) for i in range(1, 5)])
        cbbp.pack(side="left", padx=(2, 8))
        cbbp.bind("<<ComboboxSelected>>", lambda *_: self._md_render(top))
        ttk.Label(bar, text="目标伴随式 m (二进制):").pack(side="left")
        ttk.Entry(bar, textvariable=tv, width=10).pack(side="left", padx=2)
        ttk.Button(bar, text="随机块", command=lambda: self._md_random(top)
                   ).pack(side="left", padx=8)
        ttk.Button(bar, text="执行修改", command=lambda: self._md_flip(top)
                   ).pack(side="left", padx=2)

        # 动画行
        anim = ttk.Frame(top, style="Card.TFrame"); anim.pack(fill="x", padx=8, pady=2)
        ttk.Button(anim, text="\u25b6 自动演示",
                   command=lambda: self._md_anim_play(top)).pack(side="left")
        ttk.Button(anim, text="\u25a0 停止",
                   command=lambda: self._md_anim_stop(top)).pack(side="left", padx=4)
        ttk.Label(anim, text="速度:").pack(side="left", padx=(6, 0))
        spd = ttk.Combobox(anim, state="readonly", width=7,
                           values=["0.6 s", "1.2 s", "2.0 s", "3.0 s"])
        spd.set("1.2 s"); spd.pack(side="left", padx=(2, 6))
        top._md_speed = spd

        # 主体: 左=LSB 块, 右=校验矩阵 H
        body = ttk.Frame(top, style="Card.TFrame"); body.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.Frame(body, style="Card.TFrame"); left.pack(side="left", fill="y", padx=(0, 10))
        ttk.Label(left, text="LSB 块 (点格子可手动翻转)").pack(anchor="w", pady=(0, 2))
        cv = tk.Canvas(left, width=top._md_n * top._md_cell + 8, height=70,
                       bg=C_CANVAS, highlightthickness=1,
                       highlightbackground=C_BORDER)
        cv.pack(); cv.bind("<Button-1>", lambda e: self._md_click(top, e))
        top._md_cv = cv
        right = ttk.Frame(body, style="Card.TFrame"); right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="校验矩阵 H (列=像素位; 绿框=命中列)").pack(anchor="w", pady=(0, 2))
        hcv = tk.Canvas(right, width=20 * top._md_n + 8, height=70,
                        bg=C_CANVAS, highlightthickness=1,
                        highlightbackground=C_BORDER)
        hcv.pack(anchor="w"); top._md_hcv = hcv

        top._md_anim_lbl = ttk.Label(top,
                                     text="自动演示：每轮随机块 → 观察 s/m/d 与命中列 → 自动执行修改",
                                     foreground=C_BLUE)
        top._md_anim_lbl.pack(anchor="w", padx=8, pady=(4, 0))
        top._md_info = ttk.Label(top, text="", justify="left", foreground=C_BLUE, padding=(8, 4))
        top._md_info.pack(fill="x", padx=4)
        self._md_render(top)
        top.bind("<Destroy>", lambda e: self._md_anim_stop(top, destroy=True))
        _ = pv, tv
        return top

    def _md_anim_delay(self, top):
        try:
            return int(float(str(top._md_speed.get()).split()[0]) * 1000)
        except Exception:
            return 1200

    def _md_anim_play(self, top):
        self._md_anim_stop(top)
        top._md_play = {"id": None, "stop": False, "phase": "show",
                        "delay": self._md_anim_delay(top), "step": 0}
        self._md_anim_step(top)

    def _md_anim_stop(self, top, destroy=False):
        st = getattr(top, "_md_play", None)
        if st and st["id"] is not None:
            try:
                top.after_cancel(st["id"])
            except Exception:
                pass
        if st is not None:
            st["stop"] = True
            st["id"] = None
        if not destroy and hasattr(top, "_md_anim_lbl"):
            top._md_anim_lbl.configure(text="自动演示已停止（点 ▶ 继续）")

    def _md_anim_step(self, top):
        st = top._md_play
        if st is None or st["stop"]:
            return
        st["delay"] = self._md_anim_delay(top)
        if st["phase"] == "show":
            p = int(top._md_pvar.get())
            top._md_x = MD.random_block(p, seed=int(np.random.randint(0, 1 << 30)))
            m = ""
            for _ in range(8):
                m = "".join(str(int(np.random.randint(0, 2))) for _ in range(p))
                try:
                    if MD.demo_step(p, top._md_x, m)["s_val"] != int(m, 2):
                        break
                except Exception:
                    break
            top._md_tvar.set(m)
            st["step"] += 1
            top._md_anim_lbl.configure(
                text=f"第 {st['step']} 轮：观察当前 syndrome s 与目标 m，注意黄色高亮列")
            self._md_render(top)
            st["phase"] = "apply"
            st["id"] = top.after(st["delay"], lambda: self._md_anim_step(top))
        else:
            self._md_flip(top)
            top._md_anim_lbl.configure(text="已自动执行修改：H·x 与目标 m 匹配 ✓")
            st["phase"] = "show"
            st["id"] = top.after(st["delay"], lambda: self._md_anim_step(top))

    def _md_random(self, top):
        p = int(top._md_pvar.get())
        top._md_x = MD.random_block(p)
        self._md_render(top)

    def _md_flip(self, top):
        try:
            r = MD.demo_step(int(top._md_pvar.get()), top._md_x, top._md_tvar.get().strip())
        except Exception as e:
            top._md_info.configure(text="参数错误: " + str(e)); return
        if r["modified"] and r["valid_col"]:
            top._md_x[r["col"]] ^= 1
        self._md_render(top)

    def _md_click(self, top, ev):
        i = (int(ev.x) - 4) // top._md_cell
        if 0 <= i < top._md_n:
            top._md_x[i] ^= 1
            self._md_render(top)

    def _md_render(self, top):
        p, tv = int(top._md_pvar.get()), top._md_tvar.get().strip()
        m = tv.zfill(p)[-p:] if tv else "0" * p
        top._md_tvar.set(m)
        try:
            r = MD.demo_step(p, top._md_x, m)
        except Exception as e:
            top._md_info.configure(text="参数错误: " + str(e)); return
        from ns5_core import build_hamming
        n, cell = r["n"], top._md_cell
        top._md_n = n
        hcol = r["col"] if (r["modified"] and r["valid_col"]) else None

        # --- LSB 块 canvas ---
        cv = top._md_cv
        cv.configure(width=n * cell + 8, height=70)
        cv.delete("all")
        for i in range(n):
            x = i * cell + 4
            val = int(r["x"][i])
            is_hit = (i == hcol)
            fill = "#ffd54f" if is_hit else ("#2e7d32" if val else "#eceff1")
            outline = "#c62828" if is_hit else "#90a4ae"
            cv.create_rectangle(x, 6, x + cell, 6 + cell - 8, fill=fill,
                                outline=outline, width=(3 if is_hit else 1))
            cv.create_text(x + cell / 2, 6 + (cell - 8) / 2, text=str(val),
                           font=("Arial", 14, "bold"),
                           fill=("#ffffff" if (is_hit or val) else "#37474f"))
            cv.create_text(x + cell / 2, 6 + cell + 10, text=str(i + 1),
                           font=("Arial", 8), fill="#78909c")
        cv.create_text(4, 6 + cell + 24, anchor="w", text="黄/红框=命中列 · 绿=1 灰=0",
                       font=("Arial", 8), fill="#78909c")

        # --- 校验矩阵 H canvas ---
        H = build_hamming(p)
        hcv = top._md_hcv
        hcell = 20
        hcw = n * hcell + 8
        hch = p * (hcell - 2) + 30
        hcv.configure(width=hcw, height=hch)
        hcv.delete("all")
        for ci in range(n):
            for ri in range(p):
                x = ci * hcell + 4
                y = ri * (hcell - 2) + 4
                v = int(H[ri, ci])
                is_hit = (ci == hcol)
                fill = "#ffd54f" if is_hit else ("#90caf9" if v else "#f4f4f4")
                outline, w = ("#c62828", 2) if is_hit else ("#90a4ae", 1)
                hcv.create_rectangle(x, y, x + hcell, y + (hcell - 2),
                                     fill=fill, outline=outline, width=w)
                hcv.create_text(x + hcell / 2, y + (hcell - 2) / 2, text=str(v),
                                font=("Arial", 9, "bold"), fill=("#5d4037" if is_hit else "#37474f"))
            x = ci * hcell + 4
            hcv.create_text(x + hcell / 2, p * (hcell - 2) + 16, text=str(ci + 1),
                            font=("Arial", 8), fill="#78909c")

        # --- 结构化状态 ---
        if r["modified"] and r["valid_col"]:
            info = (f"s = {r['s_bin']} ({r['s_val']})      m = {r['m_bin']} ({r['m_val']})\n"
                    f"d = s⊕m = {r['d_bin']} ({r['d_val']})  →  H 命中第 {r['col'] + 1} 列\n"
                    f"把第 {r['col'] + 1} 个系数 {r['flip_from']}→{r['flip_to']}；"
                    f"翻转后 H·x′ = {r['s2_bin']} = m  ✓")
        else:
            info = (f"s = {r['s_bin']} ({r['s_val']})  已等于目标 m = {r['m_bin']} ({r['m_val']})\n"
                    f"该块无需任何改动  ✓")
        top._md_info.configure(text=info)

    # ------------------------------------------------------- 增强面板 2: 隐写分析扫描
    def _scan_panel(self):
        if self.cover_img is None:
            messagebox.showwarning("提示", "请先载入一张图片再扫描"); return
        top = tk.Toplevel(self.root, bg=C_CARD)
        top.title("隐写分析随载荷扫描")
        # 参数行
        bar = ttk.Frame(top, style="Card.TFrame", padding=8); bar.pack(fill="x")
        ttk.Label(bar, text="算法:").pack(side="left")
        mvar = tk.StringVar(value=self.var_method.get())
        ttk.Combobox(bar, textvariable=mvar, state="readonly", width=14,
                     values=["nsF5 (减幅+湿纸)", "matrix (LSB矩阵编码)"]).pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="p:").pack(side="left")
        pvar = tk.StringVar(value=self.var_p.get())
        ttk.Combobox(bar, textvariable=pvar, state="readonly", width=4,
                     values=[str(i) for i in range(1, 9)]).pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="最大 payload:").pack(side="left")
        maxv = tk.DoubleVar(value=0.30)
        sc = tk.Scale(bar, from_=0.0, to=0.4, resolution=0.01, orient="horizontal",
                      variable=maxv, length=240, bg=C_CARD, troughcolor=C_BLUE_LIGHT,
                      highlightthickness=0)
        sc.pack(side="left", padx=6)
        vlbl = ttk.Label(bar, text="0.30"); vlbl.pack(side="left")
        btn = ttk.Button(bar, text="重新扫描"); btn.pack(side="left", padx=8)
        # 进度/状态
        prog = ttk.Progressbar(top, mode="indeterminate")
        prog.pack(fill="x", padx=8)
        stat = ttk.Label(top, text="就绪", foreground=C_BLUE)
        stat.pack(anchor="w", padx=8)
        ph = ttk.Label(top, text="(等待计算…)"); ph.pack(padx=8, pady=8)
        ttk.Label(top, text="AUC 需整组正/负样本集合判定, 单张图无法给出真值; "
                            "此处以 ML 含密概率曲线作为区分能力趋势示意。",
                  style="Muted.TLabel").pack(pady=(0, 6))
        top._sp = dict(mvar=mvar, pvar=pvar, maxv=maxv, vlbl=vlbl,
                       prog=prog, stat=stat, ph=ph, btn=btn)
        top._sp_id = None

        def refresh(*_a):
            vlbl.configure(text=f"{maxv.get():.2f}")
            if top._sp_id is not None:
                top.after_cancel(top._sp_id)
            top._sp_id = top.after(350, lambda: self._scan_go(top))
        sc.configure(command=refresh)
        btn.configure(command=lambda: (top.after_cancel(top._sp_id)
                                       if top._sp_id is not None else None,
                                       self._scan_go(top)))
        refresh()
        return top

    def _scan_go(self, top):
        cfg = top._sp
        m = cfg["mvar"].get()
        method = "nsF5" if m.startswith("nsF5") else "matrix"
        p = int(cfg["pvar"].get()); pwd = self.var_pwd.get()
        val = round(float(cfg["maxv"].get()), 2)
        cfg["btn"].configure(state="disabled")
        cfg["prog"].start(12)
        cfg["stat"].configure(text=f"计算中… 载荷 0→{val:.2f} ({method} p={p})")

        def work():
            try:
                densities = np.linspace(0, val, 7)
                res = SP.scan_curves(self.cover_img, method=method, p=p,
                                     password=pwd, densities=densities)
                path = os.path.join(OUTPUT_DIR, "scan_curves.png")
                SP.plot_scan(res, path)
                return path, None
            except Exception as e:
                return None, e

        def done(res):
            cfg["prog"].stop(); cfg["btn"].configure(state="normal")
            path, err = res
            if path is None:
                cfg["stat"].configure(text="扫描失败: " + str(err)); return
            try:
                im = Image.open(path).convert("RGB")
                im.thumbnail((int(self.root.winfo_screenwidth() * 0.92),
                              int(self.root.winfo_screenheight() * 0.5)),
                             getattr(Image, "Resampling", Image).LANCZOS)
                ph = ImageTk.PhotoImage(im)
                cfg["ph"].configure(image=ph, text="")
                cfg["ph"].image = ph
            except Exception as e:
                cfg["ph"].configure(text="绘图失败: " + str(e))
            cfg["stat"].configure(text=f"完成 · 载荷 0→{float(cfg['maxv'].get()):.2f}  ({os.path.basename(path)})")

        def worker():
            res = work()
            self._queue.put((done, (res,)))
        threading.Thread(target=worker, daemon=True).start()


def _configure_theme(root: tk.Tk):
    """蓝白"国企风"主题: 白色卡片 + 深蓝横幅/主按钮, 朴素不花哨。

    色板 (集中定义, 面板内不再各写各的灰):
    深蓝 NAVY 用于横幅/主按钮/标签框标题, 亮蓝 BLUE 用于状态与强调,
    其余大面积是白卡片 + 极浅蓝底, 边框统一浅蓝灰。"""
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        bg = C_BG; card = C_CARD; fg = C_FG; muted = C_MUTED
        navy = C_NAVY; navy_dark = C_NAVY_DARK; navy_hover = C_NAVY_HOVER
        blue = C_BLUE; blue_light = C_BLUE_LIGHT; border = C_BORDER
        font_ui = FONT_UI

        root.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg, font=font_ui)
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        # 白色卡片: 标签框与其内的标签/控件
        style.configure("TLabelframe", background=card, bordercolor=border,
                        lightcolor=border, darkcolor=border, borderwidth=1,
                        relief="solid")
        style.configure("TLabelframe.Label", background=card, foreground=navy,
                        font=(font_ui[0], 11, "bold"))
        style.configure("TLabel", background=card, foreground=fg)
        style.configure("Muted.TLabel", background=card, foreground=muted)
        style.configure("Section.TLabel", background=card, foreground=navy,
                        font=(font_ui[0], 10.5, "bold"))
        style.configure("Guide.TLabel", background=blue_light, foreground=navy,
                        font=(font_ui[0], 10), padding=(10, 7))
        style.configure("Status.TLabel", background=blue_light, foreground=navy,
                        padding=(8, 4))
        # 按钮: 默认白底蓝字, 主要动作用深蓝底白字
        style.configure("TButton", padding=(8, 5), background=card,
                        foreground=navy, bordercolor=border,
                        lightcolor="#ffffff", darkcolor="#dfe9f4")
        style.map("TButton",
                  background=[("pressed", "#dce8f5"), ("active", "#eaf2fb")],
                  foreground=[("disabled", "#9db6d0")])
        style.configure("Primary.TButton", background=navy, foreground="#ffffff",
                        bordercolor=navy, lightcolor=navy, darkcolor=navy,
                        padding=(10, 6), font=(font_ui[0], 10, "bold"))
        style.map("Primary.TButton",
                  background=[("pressed", navy_dark), ("active", navy_hover)],
                  foreground=[("disabled", "#9db6d0")])
        # 输入控件
        style.configure("TCombobox", padding=2, fieldbackground=card,
                        background=card, bordercolor=border, arrowcolor=navy)
        style.map("TCombobox",
                  fieldbackground=[("readonly", card)],
                  bordercolor=[("focus", blue)])
        style.configure("TEntry", padding=(4, 2), fieldbackground=card,
                        bordercolor=border, lightcolor=border, darkcolor=border)
        style.map("TEntry", bordercolor=[("focus", blue)])
        style.configure("TCheckbutton", background=card, foreground=fg)
        style.map("TCheckbutton", background=[("active", card), ("pressed", card),
                                              ("disabled", card)])
        # 进度条 / 标签页
        style.configure("TProgressbar", background=blue, troughcolor="#dfe9f4",
                        bordercolor=bg, lightcolor=blue, darkcolor=blue)
        style.configure("TNotebook", background=bg, bordercolor=border)
        style.configure("TNotebook.Tab", background=blue_light, foreground=navy,
                        padding=(12, 5))
        style.map("TNotebook.Tab",
                  background=[("selected", card)],
                  foreground=[("selected", navy)])
    except Exception:
        pass


def main():
    try:
        root = tk.Tk()
    except Exception as e:
        # tkinter 缺失 / 无显示环境时给可行动的提示, 而不是 TclError 栈回溯
        sys.stderr.write("[错误] 无法启动图形界面: %s\n" % e)
        sys.stderr.write(
            "       缺 tkinter 时: Ubuntu/Debian 执行 sudo apt install python3-tk\n"
            "       服务器/无显示环境请改用命令行: nsf5stego embed / extract / analyze\n")
        return 1
    _configure_theme(root)
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    main()
