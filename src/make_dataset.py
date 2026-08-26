"""
批量生成监督学习数据集 (clean=0 / stego=1)。

- 输入: F:\\DCIM\\Camera 下的校园照片 (414 张 JPG)
- 每张: 降采样到 WORK 尺寸灰度 (LANCZOS), 得到 1 个干净样本,
        再以 nsF5 / matrix 嵌入不同密度消息, 得到 6 个含密变体。
- 嵌入: 由 C++ 库 nsf5embed.dll 加速 (与纯 Python 像素级一致)。
- 特征: 全部由 C++ 库 fsfeatures.dll 提取 (RS / 卡方 / 差分熵 / LSB 熵 / 前缀 p)。
- 输出: data/dataset.csv (11 特征 + label + 元数据列, 元数据不参与训练)

用法:  python src/make_dataset.py [照片目录] [工作尺寸]
"""
from __future__ import annotations
import sys, os, csv, glob, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from fsfeatures import get_lib
from cppembed import embed_string  # C++ 加速嵌入 (与 ns5_core 像素级一致)

DEFAULT_PHOTO_DIR = r"F:\DCIM\Camera"
WORK = (512, 512)  # 降采样工作尺寸
SMOKE_LIMIT = int(os.environ.get("DS_LIMIT", "0"))  # >0 仅处理前 N 张(冒烟)

# 含密变体定义: (method, p, density)；density 为"占满容量比例"。
# 6 档覆盖 弱(nsF5 p3)~强(matrix p2), 强度由改像素比例决定。
VARIANTS = [
    ("nsF5", 3, 0.25),   # 弱密度 (p3)
    ("nsF5", 3, 0.55),   # 中弱
    ("nsF5", 2, 0.35),   # 中 (p2)
    ("nsF5", 2, 0.85),   # 中强
    ("matrix", 3, 0.50), # 中 (矩阵编码)
    ("matrix", 2, 0.80), # 强
]
FEAT_KEYS = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
             "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
             "median_prefix_p", "chi2_stat"]


def capacity_bytes(npix: int, p: int, head_pixels: int) -> int:
    """正文区可嵌入的比特数换算为消息字节近似。"""
    cap_bits = (npix - head_pixels) * p // ((1 << p) - 1)
    return max(1, cap_bits // 8)


def main(photo_dir: str = DEFAULT_PHOTO_DIR, work=(512, 512)):
    photos = sorted(glob.glob(os.path.join(photo_dir, "*.jpg")))
    if SMOKE_LIMIT > 0:
        photos = photos[:SMOKE_LIMIT]
    if not photos:
        print(f"未在 {photo_dir} 找到 jpg"); return
    print(f"共 {len(photos)} 张照片, 工作尺寸 {work[0]}x{work[1]}")
    fe = get_lib()

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "dataset.csv")
    header = FEAT_KEYS + ["label", "photo_id", "variant", "method", "p", "density", "changed_frac"]

    n_clean = n_stego = 0
    t_start = time.perf_counter()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header)
        for pi, path in enumerate(photos):
            try:
                im = Image.open(path).convert("L").resize(work, Image.LANCZOS)
                a = np.asarray(im, dtype=np.uint8)
            except Exception as e:
                print(f"  [跳过] {os.path.basename(path)}: {e}"); continue
            if a.size < 64 * 64:
                print(f"  [跳过-过小] {os.path.basename(path)}"); continue
            npix = a.size

            # 干净样本
            cpp = fe.features(a)
            w.writerow([cpp[k] for k in FEAT_KEYS] + [0, pi, "clean", "", "", "", ""])
            n_clean += 1

            # 含密变体
            for vi, (method, p, dens) in enumerate(VARIANTS):
                cb = capacity_bytes(npix, p, head_pixels=0)
                nbytes = int(cb * dens)
                try:
                    stego, rep, nb = embed_string(a, "S" * nbytes, method=method, p=p,
                                      check=False, fast_permute=True)
                except Exception as e:
                    print(f"  [嵌入失败] {os.path.basename(path)} {method} p={p} d={dens}: {e}")
                    continue
                fv = fe.features(stego)
                changed = float(np.sum(stego != a)) / npix
                w.writerow([fv[k] for k in FEAT_KEYS] +
                           [1, pi, f"v{vi}", method, p, dens, f"{changed:.4f}"])
                n_stego += 1

            if (pi + 1) % 50 == 0:
                el = time.perf_counter() - t_start
                print(f"  进度 {pi+1}/{len(photos)}  clean={n_clean} stego={n_stego}  耗时 {el:.0f}s")

    el = time.perf_counter() - t_start
    print(f"\n完成: photo={len(photos)} clean={n_clean} stego={n_stego} "
          f"合计={n_clean+n_stego} 耗时 {el:.0f}s")
    print(f"已写出 -> {csv_path}")


if __name__ == "__main__":
    args = sys.argv[1:]
    d = args[0] if len(args) > 0 else DEFAULT_PHOTO_DIR
    work = tuple(map(int, args[1].split("x"))) if len(args) > 1 else WORK
    main(d, work)