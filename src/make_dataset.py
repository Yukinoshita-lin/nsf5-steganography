"""
批量生成监督学习数据集 (clean=0 / stego=1)。

- 输入: F:\\Steganography\\data\\<photo_dir> 下的灰度/jpg 照片
- 每张: 降采样到 WORK 尺寸灰度 (LANCZOS), 得到 1 个干净样本,
        再以 nsF5 / matrix / lsb 嵌入不同密度消息, 得到 N 个含密变体。
- 嵌入: nsF5/matrix 由 C++ 库 nsf5embed.dll 加速, lsb 由 Python 直写 (per-pixel LSB)
- 特征: 11 维 (v1, CPU C++ 库) 或 143 维 (v2, GPU featurize_v2_gpu) — 由 --feature-set 选择
- 输出: data/dataset_<NAME>.csv (N_FEAT 维特征 + label + 元数据列, 元数据不参与训练)

用法:  python src/make_dataset.py [照片目录] [工作尺寸] [--out NAME] [--id-offset N] [--feature-set v1|v2] [--preprocess none|srm] [--variants ...]
"""
from __future__ import annotations
import sys, os, csv, glob, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from fsfeatures import get_lib
from cppembed import embed_string  # C++ 加速嵌入 (与 ns5_core 像素级一致)
from srm_filter import preprocess_for_features  # SRM 高通滤波预处理层

# 兼容旧 v1 CSV (11 维) 训练
V1_FEAT_KEYS = ["Rm", "Sm", "Rn", "Sn", "RS_Gr", "RS_Gn",
                "chi2_pvalue", "diff_entropy", "lsb_diff_entropy",
                "median_prefix_p", "chi2_stat"]

DEFAULT_PHOTO_DIR = r"F:\Steganography\data\campus_jpg"
WORK = (512, 512)
SMOKE_LIMIT = int(os.environ.get("DS_LIMIT", "0"))

IM_EXTS = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tif", "*.tiff", "*.pgm")

# 默认 8 档变体: 6 个原档 + 1 个 LSB + 1 个 0.40 补档
DEFAULT_VARIANTS = [
    ("nsF5", 3, 0.25),
    ("nsF5", 3, 0.40),  # 新增
    ("nsF5", 3, 0.55),
    ("nsF5", 2, 0.35),
    ("nsF5", 2, 0.85),
    ("matrix", 3, 0.50),
    ("matrix", 2, 0.80),
    ("lsb", 0, 0.50),    # 新增: LSB 直接替换, p=0 由 cppembed 识别
]


def capacity_bytes(npix: int, p: int, head_pixels: int) -> int:
    cap_bits = (npix - head_pixels) * p // ((1 << p) - 1) if p >= 1 else (npix - head_pixels) // 8
    return max(1, cap_bits // 8)


def _load_lsb_featurizer():
    """v2 特征: 延迟加载 GPU 端 featurize_v2_gpu, 同时取得列名."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gpu"))
    from featurize_v2_gpu import NAMES as V2_NAMES, extract_features_v2_gpu
    return V2_NAMES, extract_features_v2_gpu


def _process_photo_worker(payload):
    """子进程单元: 处理单张照片, 返回该张的样本行列表。
    payload=(path, work, base_id, preprocess, feature_set, variants)
    """
    path, work, base_id, preprocess, feature_set, variants = payload
    fe = get_lib()
    try:
        im = Image.open(path).convert("L").resize(work, Image.LANCZOS)
        a = np.asarray(im, dtype=np.uint8)
    except Exception as e:
        print(f"  [跳过] {os.path.basename(path)}: {e}"); return []
    if a.size < 64 * 64:
        print(f"  [跳过-过小] {os.path.basename(path)}"); return []
    npix = a.size
    # 嵌入阶段: 全部用原图, 与 preprocess 解耦
    a_clean_hp = preprocess_for_features(a, use_srm=(preprocess == "srm"))
    # 特征: 按 feature_set 选择, 11 维用 C++, 143 维用 GPU
    if feature_set == "v1":
        clean_feats = fe.features(a_clean_hp)
    else:
        # v2: GPU 一次性算所有 143 维 (含 SRM 残差统计), 不再二次过 SRM 单通道图
        # 把 SRM 单独成 preprocessed image 仅用于 11 维; v2 完全用原图就够了.
        from featurize_v2_gpu import extract_features_v2_gpu
        F = extract_features_v2_gpu(a[None], chunk=1, device="cuda")
        clean_feats_v2 = F[0]
    rows = []
    # 干净样本
    if feature_set == "v1":
        row = [clean_feats[k] for k in V1_FEAT_KEYS] + [0, base_id, "clean", "", "", "", ""]
    else:
        row = list(clean_feats_v2) + [0, base_id, "clean", "", "", "", ""]
    rows.append(row)
    # 含密变体
    for vi, (method, p, dens) in enumerate(variants):
        if method == "lsb":
            # LSB 直接: density 直接是"占满可用 LSB 比例". 简化: 写 nbytes=占总像素比例 * dens
            nbytes = max(0, int(npix * dens // 8))
        else:
            cb = capacity_bytes(npix, p, head_pixels=0)
            nbytes = int(cb * dens)
        try:
            stego, rep, nb = embed_string(a, "S" * nbytes, method=method, p=max(1, p),
                              check=False, fast_permute=True)
        except Exception as e:
            print(f"  [嵌入失败] {os.path.basename(path)} {method} p={p} d={dens}: {e}")
            continue
        stego_hp = preprocess_for_features(stego, use_srm=(preprocess == "srm"))
        if feature_set == "v1":
            fv = fe.features(stego_hp)
            row = [fv[k] for k in V1_FEAT_KEYS] + [1, base_id, f"v{vi}", method, p, dens, ""]
        else:
            F2 = extract_features_v2_gpu(stego[None], chunk=1, device="cuda")
            fv2 = F2[0]
            row = list(fv2) + [1, base_id, f"v{vi}", method, p, dens, ""]
        changed = float(np.sum(stego != a)) / npix
        row[-1] = f"{changed:.4f}"
        rows.append(row)
    return rows


def _process_photo_direct(path, work, base_id, fe, preprocess="none", feature_set="v1", variants=None):
    payload = (path, work, base_id, preprocess, feature_set, variants or DEFAULT_VARIANTS)
    _PROC_FE[0] = fe
    return _process_photo_worker(payload)


def _chunk_worker(chunk):
    tasks, tmp_path = chunk
    cnt = 0
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for t in tasks:
            for row in _process_photo_worker(t):
                w.writerow(row); cnt += 1
    return cnt


_PROC_FE = [None]


def main(photo_dir: str = DEFAULT_PHOTO_DIR, work=(512, 512), out_name: str = "",
         id_offset: int = 0, workers: int = 0, preprocess: str = "none",
         feature_set: str = "v1", variants=None):
    import multiprocessing as mp
    photos = sorted({os.path.normcase(p) for ext in IM_EXTS
                     for p in glob.glob(os.path.join(photo_dir, ext))})
    if SMOKE_LIMIT > 0:
        photos = photos[:SMOKE_LIMIT]
    if not photos:
        print(f"未在 {photo_dir} 找到图像"); return
    variants = variants or DEFAULT_VARIANTS
    print(f"共 {len(photos)} 张照片, 工作尺寸 {work[0]}x{work[1]}, 变体 {len(variants)} 档")
    n_proc = workers if workers > 0 else max(1, (os.cpu_count() or 4) - 1)
    if n_proc > len(photos):
        n_proc = len(photos)

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    os.makedirs(out_dir, exist_ok=True)
    fname = f"dataset_{out_name}.csv" if out_name else "dataset.csv"
    csv_path = os.path.join(out_dir, fname)
    if feature_set == "v1":
        feat_names = V1_FEAT_KEYS
    else:
        V2_NAMES, _ = _load_lsb_featurizer()
        feat_names = V2_NAMES
    header = feat_names + ["label", "photo_id", "variant", "method", "p", "density", "changed_frac"]
    if preprocess not in ("none", "srm"):
        raise SystemExit(f"未知 --preprocess 值: {preprocess} (可选 none|srm)")
    if feature_set not in ("v1", "v2"):
        raise SystemExit(f"未知 --feature-set 值: {feature_set} (可选 v1|v2)")
    print(f"特征集: {feature_set} ({len(feat_names)} 维), 预处理: {preprocess}, 变体: {variants}")

    t_start = time.perf_counter()
    tasks = [(path, work, id_offset + i, preprocess, feature_set, variants) for i, path in enumerate(photos)]
    n_clean = n_stego = 0
    n_proc = 1 if n_proc == 0 else max(1, n_proc)

    if n_proc == 1 or feature_set == "v2":
        # v2 必须单进程(每张图独占 GPU, 多进程会争抢)
        if feature_set == "v2" and n_proc > 1:
            print("  v2 特征强绑单进程(GPU 单卡)")
            n_proc = 1
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(header)
            for pj, t in enumerate(tasks):
                for row in _process_photo_worker(t):
                    w.writerow(row)
                    if row[-5] == "clean":
                        n_clean += 1
                    else:
                        n_stego += 1
                if (pj + 1) % 50 == 0:
                    print(f"  进度 {pj+1}/{len(photos)}  耗时 {time.perf_counter()-t_start:.0f}s")
    else:
        batch = max(1, len(tasks) // (n_proc * 8))
        chunks = [tasks[i:i + batch] for i in range(0, len(tasks), batch)]
        tmp_paths = [csv_path + f".j{p}" for p in range(len(chunks))]
        work_items = list(zip(chunks, tmp_paths))
        with mp.Pool(n_proc) as pool:
            pool.map(_chunk_worker, work_items)
        with open(csv_path, "w", newline="", encoding="utf-8") as fo:
            wo = csv.writer(fo); wo.writerow(header)
            for tp in tmp_paths:
                if not os.path.exists(tp):
                    continue
                with open(tp, "r", newline="", encoding="utf-8") as fi:
                    for line in fi:
                        if line.strip():
                            fo.write(line)
                os.remove(tp)
        n_clean = n_stego = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            for r in csv.reader(f):
                if len(r) == 1 and r[0] == V1_FEAT_KEYS[0]:
                    continue
                if r[-5] == "clean":
                    n_clean += 1
                else:
                    n_stego += 1

    el = time.perf_counter() - t_start
    print(f"\n完成: photo={len(photos)} clean={n_clean} stego={n_stego} "
          f"合计={n_clean+n_stego} 耗时 {el:.0f}s ({n_proc} 进程)")
    print(f"已写出 -> {csv_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*", help="照片目录(可多个, 依次生成)")
    ap.add_argument("work", nargs="?", type=str, default=f"{WORK[0]}x{WORK[1]}")
    ap.add_argument("--out", default="", help="输出 dataset_<NAME>.csv (默认 dataset.csv)")
    ap.add_argument("--id-offset", type=int, default=0)
    ap.add_argument("--workers", "-j", type=int, default=0)
    ap.add_argument("--preprocess", choices=("none", "srm"), default="none")
    ap.add_argument("--feature-set", choices=("v1", "v2"), default="v1",
                    help="v1=11维 C++ (CPU); v2=143维 (GPU, 30残差统计+20段前缀p+texture/est_rate+lsb20段)")
    ap.add_argument("--variants", default="default",
                    help="default=8档(含LSB+0.40) | minimal=6档(与原 dataset.csv 一致)")
    a = ap.parse_args()
    variants = DEFAULT_VARIANTS
    if a.variants == "minimal":
        variants = [v for v in DEFAULT_VARIANTS if v[0] != "lsb" and v != ("nsF5", 3, 0.40)]
    elif a.variants == "all":
        variants = DEFAULT_VARIANTS + [
            ("matrix", 3, 0.40),
            ("matrix", 3, 0.60),
            ("lsb", 0, 0.30),
            ("lsb", 0, 0.70),
        ]
    for i, d in enumerate(a.dirs or [DEFAULT_PHOTO_DIR]):
        work = tuple(map(int, a.work.lower().split("x"))) if "x" in a.work else WORK
        main(d, work, a.out, a.id_offset, a.workers, a.preprocess, a.feature_set, variants)
