"""端到端验证: 生成封面图 → 嵌入 → 解码 → 分析 → 绘图。"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(PROJECT, "img"); OUT = os.path.join(PROJECT, "output")
os.makedirs(IMG, exist_ok=True); os.makedirs(OUT, exist_ok=True)

import image_io as IO
from ns5_core import embed_string, extract_string, get_image_hash
import steganalysis as SA
from efficiency import plot_code_family_and_efficiency

def main():
    # 1) 平滑自然感封面图 (256x256 灰度)
    rng = np.random.default_rng(42)
    y = np.linspace(0, 220, 256)[None, :]
    x = np.linspace(0, 90, 256)[:, None]
    img = np.clip(110 + y + x + rng.integers(-6, 7, (256, 256)), 12, 255).astype(np.uint8)
    cover_path = os.path.join(IMG, "cover.png")
    IO.save_image(img, cover_path)
    msg = "nsF5 steganography demo - syndrome matrix coding + wet paper!"
    print("封面图:", cover_path, img.shape, "SHA256:", get_image_hash(img)[:16])

    # 2) 嵌入多层(不同口令)往返
    for pwd, tag in [("", "nopwd"), ("secret123", "pwd")]:
        stego, report, nbits = embed_string(img, msg, method="nsF5", p=3, password=pwd)
        got = extract_string(stego, method="nsF5", p=3, password=pwd)
        assert got == msg, f"[{tag}] 解码不一致: {got!r}"
        stego_path = os.path.join(OUT, f"stego_{tag}.png")
        IO.save_image(stego, stego_path)
        print(f"[{tag}] 嵌入 {nbits} 比特, 改动 {report['cover_changed']} 像素, 解码一致 ✓ -> {stego_path}")

    # 3) 盲隐写分析: 干净 vs 密
    stego_path = os.path.join(OUT, "stego_pwd.png")
    stego = IO.load_as_gray(stego_path)
    rc, rs = SA.analyze(img), SA.analyze(stego)
    print(f"分析 封面: prob={rc['stego_probability']:.2f} ({rc['verdict']})  Gn={rc['RS_Gn']:.2f}")
    print(f"分析 含密: prob={rs['stego_probability']:.2f} ({rs['verdict']})  Gn={rs['RS_Gn']:.2f}")

    # 4) 效率图
    plot_path = plot_code_family_and_efficiency(p_max=6)
    print("效率图:", plot_path)

    # 汇总
    print("\n端到端验证通过: 嵌入/解码一致 + 分析可用 + 绘图生成")

if __name__ == "__main__":
    main()