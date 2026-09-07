"""Generate per-chapter Jupyter notebooks for the nsF5 teaching project.

Each notebook is Colab-ready: the first code cell clones the repository (when
the notebook is not already running inside it), installs missing packages, and
adds ``src`` to ``sys.path``. Run this script from the repository root:

    python teaching/build_notebooks.py
"""

from __future__ import annotations

import json
import os
import sys

REPO_URL = "https://github.com/Yukinoshita-lin/nsf5-steganography.git"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "notebooks")


def nb(md_cells, code_cells):
    cells = []
    for kind, content in [("md", md_cells), ("code", code_cells)]:
        if isinstance(content, str):
            content = [content]
        for chunk in content:
            cells.append({
                "cell_type": kind,
                "metadata": {},
                "source": chunk.splitlines(keepends=True),
                "outputs": [] if kind == "code" else None,
                "execution_count": None if kind == "code" else None,
            })
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python",
                           "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
            "colab": {"provenance": [], "name": "nsF5 teaching notebook",
                      "toc_visible": True},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


SETUP_MD = (
    "## 运行准备（一次性）\n\n"
    "- 本 Notebook 可在 **Colab** 或本机 **Jupyter** 中一键运行；\n"
    "- 若当前目录不是项目仓库，会先自动 `git clone` 到当前工作目录；\n"
    "- 依赖（numpy / Pillow / matplotlib 等）缺失时自动安装。"
)

SETUP_CODE = (
    "import os, subprocess, sys\n"
    "if not os.path.exists(os.path.join('src', 'ns5_core.py')):\n"
    "    subprocess.run(['git', 'clone', '--depth', '1', "
    "'https://github.com/Yukinoshita-lin/nsf5-steganography.git', '.'], check=True)\n"
    "sys.path.insert(0, os.path.join(os.getcwd(), 'src'))\n"
    "for mod, pkg in [('numpy', 'numpy'), ('PIL', 'Pillow'),\n"
    "                 ('matplotlib', 'matplotlib'), ('sklearn', 'scikit-learn'),\n"
    "                 ('joblib', 'joblib'), ('pandas', 'pandas')]:\n"
    "    try:\n"
    "        __import__(mod)\n"
    "    except ImportError:\n"
    "        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)\n"
    "import numpy as np\n"
    "print('project ready:', os.path.exists('src/ns5_core.py'))"
)


def chapter01():
    md = [
        "# 第 1 章 · 数字图像与二进制（像素与 LSB）\n\n"
        "对应学习手册第 1 章。学习目标：把“图像 = 数字矩阵”焊死，"
        "会做二进制/字节运算，理解最低有效位（LSB）。",
        "## 1.1 图像即矩阵\n\n"
        "灰度图是 0–255 整数矩阵，彩色图是 R/G/B 三个矩阵叠加。"
        "用 Pillow + NumPy 读取并检查数组形状。",
        "## 1.2 位与 LSB\n\n"
        "200 的二进制是 `11001000`，最低位就是 LSB。翻转 LSB 视觉上几乎不可察觉。",
        "## 1.3 动手\n\n"
        "生成一张渐变图，读取像素、拆分位平面、统计 LSB。",
    ]
    code = [
        SETUP_CODE,
        "import numpy as np\n"
        "import matplotlib.pyplot as plt\n"
        "from PIL import Image\n"
        "\n"
        "# 生成 128x128 渐变灰度图\n"
        "y = np.linspace(0, 255, 128)[None, :]\n"
        "x = np.linspace(0, 200, 128)[:, None]\n"
        "img = np.clip(30 + x + y, 0, 255).astype(np.uint8)\n"
        "Image.fromarray(img).save('output_demo.png')\n"
        "print('shape:', img.shape, 'dtype:', img.dtype, 'range:', img.min(), img.max())",
        "v = 200\n"
        "print(bin(v))            # 0b11001000\n"
        "print('LSB =', v & 1)\n"
        "print('flip ->', v ^ 1)\n"
        "print('clear ->', v & 0b11111110)",
        "bitplane = (img >> 0) & 1   # LSB 位平面\n"
        "print('LSB=1 比例: %.3f' % bitplane.mean())\n"
        "fig, ax = plt.subplots(1, 2, figsize=(8, 4))\n"
        "ax[0].imshow(img, cmap='gray'); ax[0].set_title('original')\n"
        "ax[1].imshow(bitplane * 255, cmap='gray'); ax[1].set_title('LSB plane')\n"
        "plt.show()",
    ]
    return nb(md, code)


def chapter02():
    md = [
        "# 第 2 章 · Python / NumPy / Pillow 工具链\n\n"
        "对应学习手册第 2 章。目标：装好环境、跑通端到端脚本、会用数组读写图像。",
        "## 2.1 运行项目自检\n\n"
        "先跑 `test_core.py` 与 `test_steg.py`，确认算法核心与分析链路正常。",
        "## 2.2 端到端\n\n"
        "`run_e2e.py` 覆盖 生成封面图 → 嵌入 → 解码 → 盲分析 → 绘图。",
    ]
    code = [
        SETUP_CODE,
        "import subprocess, sys\n"
        "print(subprocess.run([sys.executable, 'src/test_core.py'], capture_output=True, text=True).stdout)",
        "print(subprocess.run([sys.executable, 'src/test_steg.py'], capture_output=True, text=True).stdout)",
        "import image_io as IO\n"
        "img = IO.load_as_gray('img/cover.png')\n"
        "print('cover:', img.shape, img.dtype, float(img.mean()))\n"
        "IO.save_image(img, 'my_copy.png')",
        "import subprocess, sys\n"
        "r = subprocess.run([sys.executable, 'src/run_e2e.py'], capture_output=True, text=True)\n"
        "print(r.stdout[-2000:])",
    ]
    return nb(md, code)


def chapter03():
    md = [
        "# 第 3 章 · LSB 隐写与卡方/RS 盲分析\n\n"
        "对应学习手册第 3 章。藏一句话 → 用项目 API 解码 → 比较干净图与含密图的分析概率。",
        "## 3.1 嵌入与解码\n\n"
        "`embed_string(image, text, method, p, password)` / `extract_string(...)`。",
        "## 3.2 盲隐写分析\n\n"
        "`steganalysis.analyze()` 综合卡方 p 值、RS 缺口与内容随机度基线给出 0–1 倾向概率。",
    ]
    code = [
        SETUP_CODE,
        "import image_io as IO\n"
        "from ns5_core import embed_string, extract_string\n"
        "import steganalysis as SA\n"
        "\n"
        "clean = IO.load_as_gray('img/cover.png')\n"
        "stego, report, nbits = embed_string(clean, 'Hello nsF5!', method='nsF5', p=3)\n"
        "print('changed pixels:', report['cover_changed'], '/ total', clean.size)\n"
        "print('decoded:', extract_string(stego, method='nsF5', p=3))",
        "for name, im in (('clean', clean), ('stego', stego)):\n"
        "    r = SA.analyze(im)\n"
        "    print(name, 'Gn=%.3f' % r['RS_Gn'], 'chi2p=%.3f' % r['chi2_pvalue'],\n"
        "          'prob=%.2f' % r['stego_probability'], r['verdict'])",
        "# 强化练习: 换一条 5000 字符消息, 观察改动占比与概率\n"
        "s2, rep2, nb2 = embed_string(clean, 'S' * 5000, method='nsF5', p=3)\n"
        "r2 = SA.analyze(s2)\n"
        "print('density=%.3f' % (rep2['cover_changed'] / clean.size),\n"
        "      'prob=%.2f' % r2['stego_probability'], r2['verdict'])",
    ]
    return nb(md, code)


def chapter04():
    md = [
        "# 第 4 章 · 矩阵嵌入与 F5：汉明伴随式编码\n\n"
        "对应学习手册第 4 章。核心：n=2^p-1 个位置承载 p 位消息，块内至多改 1 位。",
        "## 4.1 单步演示\n\n"
        "`matrix_demo.demo_step` 返回 syndrome s、目标 m、差值 d 与命中的列。",
        "## 4.2 效率曲线\n\n"
        "理论 α(p)=p·2^p/(2^p−1) vs 实测，见 `efficiency.plot_code_family_and_efficiency`。",
    ]
    code = [
        SETUP_CODE,
        "import numpy as np\n"
        "import matrix_demo as MD\n"
        "r = MD.demo_step(3, MD.random_block(3, seed=1), '110')\n"
        "print('s=%s m=%s d=%s -> flip col %s' % (r['s_bin'], r['m_bin'], r['d_bin'], r['col'] + 1))\n"
        "print('verified:', r['verified'])",
        "# 多轮统计: p=3 时平均改动次数应接近 0.875/块\n"
        "changes = 0\n"
        "for seed in range(400):\n"
        "    rr = MD.demo_step(3, MD.random_block(3, seed=seed), '110')\n"
        "    changes += int(rr['modified'] and rr['valid_col'])\n"
        "print('avg changes per block: %.3f (theory %.3f)' % (changes / 400, (2**3 - 1) / 2**3))",
        "import sys, os\n"
        "sys.path.insert(0, 'src')\n"
        "from efficiency import plot_code_family_and_efficiency\n"
        "path = plot_code_family_and_efficiency(p_max=6, save_path='efficiency_demo.png')\n"
        "print(path)",
    ]
    return nb(md, code)


def chapter05():
    md = [
        "# 第 5 章 · nsF5 与湿纸编码\n\n"
        "对应学习手册第 5 章。湿纸编码把会减幅撞零的位置标记为“湿点”，"
        "只在“干点”上解 GF(2) 方程，从而无收缩嵌入。",
        "## 5.1 算法自测\n\n"
        "`test_core.py` 的 `test_wet_paper_needed()` 专门构造 127/128/129 像素验证湿纸路径。",
        "## 5.2 置换一致性\n\n"
        "`permute_index` 保证同种子同排列（Python/C++ 两实现一致），是自同步的基础。",
    ]
    code = [
        SETUP_CODE,
        "import numpy as np\n"
        "from ns5_core import embed_string, extract_string, build_hamming, syndrome, permute_index\n"
        "\n"
        "img = np.random.default_rng(0).integers(0, 256, (128, 128), dtype=np.uint8)\n"
        "for method in ('matrix', 'nsF5'):\n"
        "    stego, rep, nb = embed_string(img, 'wet paper demo', method=method, p=3)\n"
        "    got = extract_string(stego, method=method, p=3)\n"
        "    print(method, 'ok' if got == 'wet paper demo' else got,\n"
        "          'changed', rep['cover_changed'])",
        "# 湿纸需要“危险像素”: 127/128/129 (|x-128|<=1)\n"
        "danger = np.zeros_like(img)\n"
        "danger[:, :] = img\n"
        "danger[:20, :] = 128\n"
        "stego, rep, nb = embed_string(danger, 'wet test 0123456789', method='nsF5', p=3)\n"
        "print('nsF5 with danger zone ok:', extract_string(stego, method='nsF5', p=3) == 'wet test 0123456789')",
        "p = 3\n"
        "perm = permute_index(1000, seed=42)\n"
        "perm2 = permute_index(1000, seed=42)\n"
        "print('deterministic:', np.array_equal(perm, perm2))",
    ]
    return nb(md, code)


def chapter06():
    md = [
        "# 第 6 章 · 口令、SHA-256 与键控安全设计\n\n"
        "对应学习手册第 6 章。隐藏路径由“口令 + 内容哈希”决定，"
        "解码端可自同步并感知篡改。",
    ]
    code = [
        SETUP_CODE,
        "import image_io as IO\n"
        "from ns5_core import embed_string, extract_string, get_image_hash\n"
        "\n"
        "img = IO.load_as_gray('img/cover.png')\n"
        "stego, report, _ = embed_string(img, 'secret', method='nsF5', p=3, password='A')\n"
        "print('embed cover_hash:', report['cover_hash'][:16])\n"
        "print('password A ok:', extract_string(stego, method='nsF5', p=3, password='A'))",
        "try:\n"
        "    print(extract_string(stego, method='nsF5', p=3, password='B'))\n"
        "except Exception as e:\n"
        "    print('wrong password rejected:', type(e).__name__)",
        "tampered = stego.copy()\n"
        "tampered[0, 0] ^= 1\n"
        "print('hash changed:', get_image_hash(stego)[:16] != get_image_hash(tampered)[:16])\n"
        "print('decode after tamper:', repr(extract_string(tampered, method='nsF5', p=3, password='A')))",
    ]
    return nb(md, code)


def chapter08():
    md = [
        "# 第 8 章 · 机器学习隐写检测（11 维 → 143 维 → 双版本模型）\n\n"
        "对应学习手册第 8 章。用一个可复现的微型实验演示：构建 clean/stego 样本、"
        "提取特征、训练分类器、输出概率；再对比默认 143d 与 53d 可解释模型。",
        "## 8.1 微型实验（教学用）\n\n"
        "真实研究需要数百上千张独立照片（见 `make_dataset.py` / BOSSbase）；"
        "这里用少量图仅演示完整流程与 GroupKFold 思想。",
        "## 8.2 双版本推理\n\n"
        "`MLPredictor()` 默认 143d；传入 `model_path` 可切换 53d 可解释版。",
    ]
    code = [
        SETUP_CODE,
        "import numpy as np\n"
        "from ns5_core import embed_string\n"
        "from fsfeatures import get_lib\n"
        "\n"
        "def make_pairs(n=6):\n"
        "    clean, stego = [], []\n"
        "    for i in range(n):\n"
        "        y = np.linspace(0, 200, 512)[None, :]\n"
        "        x = np.linspace(0, 120 + i * 8, 512)[:, None]\n"
        "        c = np.clip(90 + x + y + np.random.default_rng(i).integers(-8, 9, (512, 512)), 0, 255).astype(np.uint8)\n"
        "        s, _, _ = embed_string(c, 'S' * 3000, method='nsF5', p=3)\n"
        "        clean.append(c); stego.append(s)\n"
        "    return clean, stego\n"
        "clean, stego = make_pairs()\n"
        "print('samples:', len(clean), 'clean +', len(stego), 'stego')",
        "# 纯 Python 11 维特征（无需 Windows DLL，可在 Colab/Linux 运行）\n"
        "from py_features import features as py_features\n"
        "FEAT = ['Rm', 'Sm', 'Rn', 'Sn', 'RS_Gr', 'RS_Gn', 'chi2_pvalue',\n"
        "       'diff_entropy', 'lsb_diff_entropy', 'median_prefix_p', 'chi2_stat']\n"
        "def feats(im):\n"
        "    f = py_features(im)\n"
        "    return [f[k] for k in FEAT]\n"
        "X = np.vstack([feats(im) for im in clean + stego])\n"
        "y = np.array([0] * len(clean) + [1] * len(stego))\n"
        "print('X', X.shape, 'labels', y.sum(), 'stego /', len(y))",
        "from sklearn.linear_model import LogisticRegression\n"
        "from sklearn.model_selection import cross_val_score\n"
        "clf = LogisticRegression(max_iter=2000)\n"
        "auc = cross_val_score(clf, X, y, cv=3, scoring='roc_auc')\n"
        "print('3-fold AUC (illustrative demo): %.3f' % np.mean(auc))",
        "import sys, os\n"
        "sys.path.insert(0, 'src')\n"
        "from ml_predict import MLPredictor\n"
        "pred_143 = MLPredictor()\n"
        "print('143d available:', pred_143.available)\n"
        "if pred_143.available:\n"
        "    print('clean prob: %.3f' % pred_143.predict(clean[0])['probability'])\n"
        "    print('stego prob: %.3f' % pred_143.predict(stego[0])['probability'])",
        "pred_53 = MLPredictor(\n"
        "    model_path='models/stego_classifier_v2_jpeg_lgb_51d.joblib',\n"
        "    clip_outliers=False)\n"
        "if pred_53.available:\n"
        "    print('53d stego prob: %.3f' % pred_53.predict(stego[0])['probability'])",
    ]
    return nb(md, code)


NOTEBOOKS = {
    "01_bits_and_pixels.ipynb": chapter01,
    "02_python_toolchain.ipynb": chapter02,
    "03_lsb_steganalysis.ipynb": chapter03,
    "04_matrix_embedding.ipynb": chapter04,
    "05_nsf5_wet_paper.ipynb": chapter05,
    "06_hash_keying.ipynb": chapter06,
    "08_ml_steganalysis.ipynb": chapter08,
}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, fn in NOTEBOOKS.items():
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(fn(), fh, ensure_ascii=False, indent=1)
        print("wrote", path)


if __name__ == "__main__":
    main()
