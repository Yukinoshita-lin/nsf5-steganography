"""
nsF5 隐写工具 —— tkinter GUI
功能: 嵌入(ASCII 字符串) / 解码 / 盲隐写分析 / 码族与效率绘图。
"""
from __future__ import annotations
import os
import threading
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
        self.cover_path = None
        self.stego_path = None
        self.cover_img = None
        self.stego_img = None
        self._build_ui()

    # ------------------------------------------------------- UI 构建
    def _build_ui(self):
        mf = ttk.Frame(self.root, padding=6)
        mf.pack(fill="both", expand=True)
        mf.columnconfigure(0, weight=1, uniform="a")
        mf.columnconfigure(1, weight=1, uniform="a")
        mf.rowconfigure(0, weight=1)

        self.left = self._build_left(mf)
        self.right = self._build_right(mf)
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

        # 状态
        self.status = ttk.Label(f, text="状态: 就绪", foreground="#1a73e8")
        self.status.grid(row=8, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # 日志
        ttk.Label(f, text="日志:").grid(row=9, column=0, sticky="nw", pady=(6, 0))
        self.log = tk.Text(f, height=9, state="disabled", wrap="word")
        self.log.grid(row=10, column=0, columnspan=2, sticky="nsew", pady=2)
        return f

    def _build_right(self, parent):
        f = ttk.LabelFrame(parent, text="图像预览 / 分析结果", padding=8)
        f.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        f.columnconfigure(0, weight=1, uniform="b")
        f.columnconfigure(1, weight=1, uniform="b")
        f.rowconfigure(1, weight=1)

        ttk.Label(f, text="原始 / 封面").grid(row=0, column=0)
        ttk.Label(f, text="含密图").grid(row=0, column=1)
        self.lbl_cover = ttk.Label(f, text="(未载入)", anchor="center")
        self.lbl_cover.grid(row=1, column=0, sticky="nsew")
        self.lbl_stego = ttk.Label(f, text="(未生成)", anchor="center")
        self.lbl_stego.grid(row=1, column=1, sticky="nsew")

        ttk.Label(f, text="分析结果与解码输出:").grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 2))
        self.out = tk.Text(f, height=9, state="disabled", wrap="word")
        self.out.grid(row=3, column=0, columnspan=2, sticky="nsew")
        return f

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
        """后台线程执行, 完成后通过 after 回主线程。"""
        self._wait("处理中…")
        def worker():
            try:
                res = fn(*args, **kwargs)
                self.root.after(0, lambda: on_done(res))
            except Exception as e:
                traceback.print_exc()
                self.root.after(0, lambda: (self._set_out(f"出错: {e}"),
                                            self._wait("失败")))
        threading.Thread(target=worker, daemon=True).start()

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
            self._set_out(
                f"嵌入成功\n保存: {out}\n"
                f"算法: {method}  p={self.var_p.get()}\n"
                f"嵌入比特: {nbits}  改动像素: {changed}\n"
                f"封面SHA256: {report['cover_hash']}\n\n"
                "提示: 解码时需使用相同的 方法/p/口令。")
            self._log("嵌入完成, 含密图已保存 " + out)
            self._wait("嵌入完成")
        self._busy(work, done)

    def _decode(self):
        if self.stego is None and self.cover_img is None:
            messagebox.showwarning("提示", "请先载入图片"); return
        method, p, pwd = self._params()
        image = self.cover_img  # 当前载入图像即待解读图

        def work():
            return extract_string(image, method=method, p=p, password=pwd)

        def done(text):
            self._set_out(f"解码成功 (方法={method}, p={p}):\n\n{text}")
            self._log("解码完成")
            self._wait("解码完成")
        self._busy(work, done)

    def _analyze(self):
        if self.stego is None and self.cover_img is None:
            messagebox.showwarning("提示", "请先载入图片"); return
        image = self.cover_img
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


def main():
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()