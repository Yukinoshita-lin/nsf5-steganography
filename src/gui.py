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
from efficiency import plot_code_family_and_efficiency, OUTPUT_DIR
from ml_predict import get_predictor
import matrix_demo as MD
import scan_panel as SP


def _rgb(img: np.ndarray):
    """灰度/彩图 → RGB 便于显示。"""
    a = np.ascontiguousarray(img)
    if a.ndim == 3:
        return a
    return np.stack([a, a, a], axis=-1)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("nsF5 隐写工具 — 伴随式矩阵编码 + 湿纸编码 + 盲隐写分析")
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
        w, h = 1120, 720
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
            "快捷键: Ctrl+O 载入 · Ctrl+E 嵌入 · Ctrl+D 解码 · Ctrl+A 分析 · Ctrl+S 保存含密图")

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
        outdir = os.path.join(PROJECT_DIR, "output")
        os.makedirs(outdir, exist_ok=True)
        try:
            os.startfile(outdir)
        except Exception as e:
            self._log("无法打开输出目录: " + str(e))

    # ------------------------------------------------------- UI 构建
    def _build_ui(self):
        mf = ttk.Frame(self.root, padding=6)
        mf.pack(fill="both", expand=True)
        mf.columnconfigure(0, weight=1, uniform="a")
        mf.columnconfigure(1, weight=1, uniform="a")
        mf.rowconfigure(0, weight=1)

        self.left = self._build_left(mf)
        self.right = self._build_right(mf)
        prog = ttk.Frame(mf)
        prog.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.progress = ttk.Progressbar(prog, mode="indeterminate")
        self.progress.pack(fill="x")
        self._log("就绪。请载入图片进行操作。")

    def _build_left(self, parent):
        f = ttk.LabelFrame(parent, text="参数与操作", padding=8)
        f.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        f.columnconfigure(1, weight=1)

        # 方法
        ttk.Label(f, text="算法:").grid(row=0, column=0, sticky="w", pady=2)
        self.var_method = tk.StringVar(value="nsF5")
        ttk.Combobox(f, textvariable=self.var_method, state="readonly", width=18,
                     values=["nsF5 (减幅+湿纸)", "matrix (LSB矩阵编码)"]
                     ).grid(row=0, column=1, sticky="ew", pady=2)

        # p
        ttk.Label(f, text="参数 p (每块比特):").grid(row=1, column=0, sticky="w", pady=2)
        self.var_p = tk.StringVar(value="3")
        pbox = ttk.Combobox(f, textvariable=self.var_p, state="readonly", width=18,
                            values=[str(i) for i in range(1, 9)])
        pbox.grid(row=1, column=1, sticky="ew", pady=2)

        # 口令
        ttk.Label(f, text="口令(可选):").grid(row=2, column=0, sticky="w", pady=2)
        self.var_pwd = tk.StringVar(value="")
        ttk.Entry(f, textvariable=self.var_pwd, show="*").grid(row=2, column=1, sticky="ew", pady=2)

        # 分析灵敏度
        ttk.Label(f, text="判定灵敏度:").grid(row=3, column=0, sticky="w", pady=2)
        self.var_sens = tk.StringVar(value="均衡")
        sbox = ttk.Combobox(f, textvariable=self.var_sens, state="readonly", width=18,
                            values=["严格 (低误报)", "均衡", "宽松 (高检出)"])
        sbox.grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(f, text="  严格→少误报干净图; 宽松→更易检出弱嵌入",
                  foreground="#666").grid(row=3, column=1, sticky="w", pady=2, padx=(150, 0))

        # 载入
        bf = ttk.Frame(f); bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(bf, text="载入原始图 / 含密图", command=self._load).pack(side="left", fill="x", expand=True)

        # 待嵌入字符串
        ttk.Label(f, text="待嵌入字符串(ASCII):").grid(row=5, column=0, sticky="nw", pady=2)
        self.var_msg = tk.Text(f, height=6, width=40)
        self.var_msg.grid(row=5, column=1, sticky="nsew", pady=2)
        self.var_msg.insert("1.0", "Hello, nsF5 steganography!")

        # 动作
        af = ttk.Frame(f); af.grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)
        ttk.Button(af, text="1 嵌入并保存", command=self._embed).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(af, text="2 解码提取", command=self._decode).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(af, text="3 分析", command=self._analyze).pack(side="left", fill="x", expand=True, padx=2)

        # 绘图
        gf = ttk.Frame(f); gf.grid(row=7, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(gf, text="生成码族与效率图", command=self._plot).pack(fill="x")
        gf2 = ttk.Frame(f); gf2.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 2))
        ttk.Button(gf2, text="矩阵编码演示", command=self._demo_matrix
                   ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(gf2, text="隐写分析扫描", command=self._scan_panel
                   ).pack(side="left", fill="x", expand=True)

        # 状态
        self.status = ttk.Label(f, text="状态: 就绪", foreground="#1a73e8")
        self.status.grid(row=9, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # 日志
        ttk.Label(f, text="日志:").grid(row=10, column=0, sticky="nw", pady=(6, 0))
        self.log = tk.Text(f, height=9, state="disabled", wrap="word")
        self.log.grid(row=11, column=0, columnspan=2, sticky="nsew", pady=2)
        return f

    def _build_right(self, parent):
        f = ttk.LabelFrame(parent, text="图像预览 / 分析结果", padding=8)
        f.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        f.columnconfigure(0, weight=1, uniform="b")
        f.columnconfigure(1, weight=1, uniform="b")
        f.rowconfigure(1, weight=1)

        ttk.Label(f, text="原始 / 封面").grid(row=0, column=0)
        self.lbl_stego_hdr = ttk.Label(f, text="含密图")
        self.lbl_stego_hdr.grid(row=0, column=1)
        self.lbl_cover = ttk.Label(f, text="(未载入)", anchor="center")
        self.lbl_cover.grid(row=1, column=0, sticky="nsew")
        self.lbl_stego = ttk.Label(f, text="(未生成)", anchor="center")
        self.lbl_stego.grid(row=1, column=1, sticky="nsew")

        # 差异图切换
        ctrl = ttk.Frame(f); ctrl.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.var_diff = tk.BooleanVar(value=False)
        self.cb_diff = ttk.Checkbutton(ctrl, text="查看差异(×255)", variable=self.var_diff,
                                       command=self._toggle_diff, state="disabled")
        self.cb_diff.pack(side="left")
        ttk.Label(ctrl, text="  仅在有含密图时可用", foreground="#888").pack(side="left", padx=6)

        ttk.Label(f, text="分析结果与解码输出:").grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 2))
        self.out = tk.Text(f, height=9, state="disabled", wrap="word")
        self.out.grid(row=4, column=0, columnspan=2, sticky="nsew")
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

    def _wait(self, t):
        self.status.configure(text="状态: " + t)

    def _show_in(self, widget: ttk.Label, image: np.ndarray):
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
        self.progress.start(12)
        def worker():
            try:
                res = fn(*args, **kwargs)
                self._queue.put((on_done, (res,)))
            except Exception as e:
                traceback.print_exc()
                self._queue.put((self._on_busy_error, (e,)))
            finally:
                self._queue.put((self.progress.stop, ()))
        threading.Thread(target=worker, daemon=True).start()

    def _on_busy_error(self, e):
        self._set_out(f"出错: {e}")
        self._wait("失败")

    def _load(self):
        path = filedialog.askopenfilename(
            filetypes=[("图像", (".png", ".bmp", ".jpg", ".jpeg", ".tif", ".tiff"))])
        if not path:
            return
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
        self.lbl_stego.configure(text="(未生成)")
        self.lbl_stego_hdr.configure(text="含密图")
        self.var_diff.set(False)
        self.cb_diff.configure(state="disabled")
        self._log(f"载入: {path}  尺寸 {gray.shape[1]}x{gray.shape[0]}  "
                  f"SHA256={get_image_hash(gray)[:12]}…")

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
        out = IO.default_out_path(self.cover_path, "stego", os.path.join(PROJECT_DIR, "output"))
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
            out = os.path.join(PROJECT_DIR, "output", "efficiency.png")
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
        top = tk.Toplevel(self.root)
        top.title("伴随式矩阵编码演示 (syndrome 查找与系数翻转)")
        pv, tv = tk.StringVar(value="3"), tk.StringVar(value="110")
        top._md_pvar, top._md_tvar, top._md_x = pv, tv, MD.random_block(3)
        top._md_cv, top._md_hcv, top._md_cell, top._md_n = None, None, 30, 7
        top._md_play = {"id": None, "stop": False, "phase": "show",
                        "delay": 1200, "step": 0}

        # 参数行
        bar = ttk.Frame(top, padding=(8, 6)); bar.pack(fill="x")
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
        anim = ttk.Frame(top); anim.pack(fill="x", padx=8, pady=2)
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
        body = ttk.Frame(top); body.pack(fill="both", expand=True, padx=8, pady=4)
        left = ttk.Frame(body); left.pack(side="left", fill="y", padx=(0, 10))
        ttk.Label(left, text="LSB 块 (点格子可手动翻转)").pack(anchor="w", pady=(0, 2))
        cv = tk.Canvas(left, width=top._md_n * top._md_cell + 8, height=70,
                       bg="#fafafa", highlightthickness=1)
        cv.pack(); cv.bind("<Button-1>", lambda e: self._md_click(top, e))
        top._md_cv = cv
        right = ttk.Frame(body); right.pack(side="left", fill="both", expand=True)
        ttk.Label(right, text="校验矩阵 H (列=像素位; 绿框=命中列)").pack(anchor="w", pady=(0, 2))
        hcv = tk.Canvas(right, width=20 * top._md_n + 8, height=70,
                        bg="#fafafa", highlightthickness=1)
        hcv.pack(anchor="w"); top._md_hcv = hcv

        top._md_anim_lbl = ttk.Label(top,
                                     text="自动演示：每轮随机块 → 观察 s/m/d 与命中列 → 自动执行修改",
                                     foreground="#1a73e8")
        top._md_anim_lbl.pack(anchor="w", padx=8, pady=(4, 0))
        top._md_info = ttk.Label(top, text="", justify="left", foreground="#1a73e8", padding=(8, 4))
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
        top = tk.Toplevel(self.root)
        top.title("隐写分析随载荷扫描")
        # 参数行
        bar = ttk.Frame(top, padding=8); bar.pack(fill="x")
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
                      variable=maxv, length=240)
        sc.pack(side="left", padx=6)
        vlbl = ttk.Label(bar, text="0.30"); vlbl.pack(side="left")
        btn = ttk.Button(bar, text="重新扫描"); btn.pack(side="left", padx=8)
        # 进度/状态
        prog = ttk.Progressbar(top, mode="indeterminate")
        prog.pack(fill="x", padx=8)
        stat = ttk.Label(top, text="就绪", foreground="#1a73e8")
        stat.pack(anchor="w", padx=8)
        ph = ttk.Label(top, text="(等待计算…)"); ph.pack(padx=8, pady=8)
        ttk.Label(top, text="AUC 需整组正/负样本集合判定, 单张图无法给出真值; "
                            "此处以 ML 含密概率曲线作为区分能力趋势示意。",
                  foreground="#666").pack(pady=(0, 6))
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
                path = os.path.join(PROJECT_DIR, "output", "scan_curves.png")
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
    """统一 ttk 主题与浅色配色, 让主窗/各面板观感一致。"""
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        bg = "#f5f6f8"; fg = "#1f2a37"; accent = "#1a73e8"
        root.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabelframe", background=bg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", padding=(6, 3))
        style.configure("TCombobox", padding=2)
        style.configure("TNotebook", background=bg)
        style.map("TButton",
                  foreground=[("pressed", accent), ("active", "#0b57d0")])
    except Exception:
        pass


def main():
    root = tk.Tk()
    _configure_theme(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
