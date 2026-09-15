"""
teaching/handbook_facts.py — 手册事实的单一来源：修正 + 校验。

背景 (2026-09-14 审计)
----------------------
两本学习手册 (docs/src/*.docx) 与它们的网页版 (teaching/web/{zh,en}/content/*.md)
长期带着**已被推翻**的说法:

  - "8-split 平均 AUC 0.9085 / 0.9227"、"53d AUC 更高" —— 那是源图泄漏 +
    SRM 特征尺度错误下测出来的, 修正后是 0.8980 / 0.8461 且 **143d 更准**;
  - "SRM 90 维单特征 AUC 0.50–0.52（接近随机）/ 只在同源有效" —— 修好尺度后
    SRM 占 LightGBM gain 的 52.6%, 去掉它 OOF AUC 掉 0.05;
  - "OOD 1/8 / 3/8" —— n=8 没有统计意义, 现口径是 1514 张上的 9.58% / 28.86%;
  - 大量指向 thesis/、论文稿的引用 —— 那些文件 2026-09-14 已从项目中删除。

教学材料带着错结论比没有结论更糟, 所以这里把"手册该说什么"写成可执行的表:

    python teaching/handbook_facts.py --check    # CI: 陈旧的错误结论必须消失, 现口径必须出现
    python teaching/handbook_facts.py --fix      # 按表修正 DOCX 源稿 (首次会留 .orig.docx 备份)
    python teaching/handbook_facts.py --fix --web # 顺手把网页版 markdown 也一起改

修完请重新生成网页与 PDF:  `make web-convert` / `python teaching/web/docx2md.py ...`
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCX = {
    "zh": os.path.join(PROJ, "docs", "src", "学习手册-从零读懂nsF5隐写项目.docx"),
    "en": os.path.join(PROJ, "docs", "src",
                       "Learning-Handbook-From-Zero-to-nsF5-Steganography.docx"),
}
WEBDIR = {"zh": os.path.join(PROJ, "teaching", "web", "zh", "content"),
          "en": os.path.join(PROJ, "teaching", "web", "en", "content")}
PDF = {
    "zh": os.path.join(PROJ, "docs", "学习手册-从零读懂nsF5隐写项目.pdf"),
    "en": os.path.join(PROJ, "docs", "Learning-Handbook-From-Zero-to-nsF5-Steganography.pdf"),
}

# 旁白视频的脚本文稿 (教学面的第五处; 视频本体是生成物, 不入库)
VIDEO_FILES = {
    "zh": [os.path.join(PROJ, "teaching", "video_scenes_zh.py"),
           os.path.join(PROJ, "teaching", "video_decks_zh.py")],
}
VIDEO_FORBIDDEN = [
    "AUC 更高",          # 53d 不再"更高" —— 修正后 143d 更准
    "推到 0.81",         # v1 时期的 OOF 数字
    "OOF ≈ 0.814",
    "四者 AUC ≈ 0.70–0.72，几乎重叠",   # 该说法只在 11 维语料成立, 需写明范围
]
VIDEO_REQUIRED = [
    "未在当前版本复现",   # v1 时期的 SRM 预处理口径必须带这个限定
    "0.898",             # 现口径
]

# --------------------------------------------------------------------------
#  1) 必须出现的现口径 (两种语言都要有)
# --------------------------------------------------------------------------
REQUIRED = [
    "docs/RESULTS.md",       # 权威结果表成为唯一出处
    # 手册里提到姊妹项目 yccstego 时必须给出**能找到它的地址**: 2026-09-15 之前
    # 中英文手册都写成"项目 yccstego 扩展", 但 yccstego 是独立仓库与 PyPI 包,
    # 克隆本仓库根本找不到它 —— 和已删除的 thesis/ 是同一种悬空引用。
    "github.com/Yukinoshita-lin/yccstego",
    "0.8980",                # 143d 8-split 平均
    "0.8461",                # 53d 8-split 平均
    "0.8939",                # 143d held-out
    "0.8391",                # 53d held-out
    "9.58",                  # 143d OOD 误报率
    "28.86",                 # 53d OOD 误报率
    "52.6",                  # SRM 的 gain 占比
]

# --------------------------------------------------------------------------
#  2) 必须消失的错误结论 (子串匹配, 两种语言各自一套)
# --------------------------------------------------------------------------
FORBIDDEN = {
    "zh": [
        "也不代替论文",
        # 2026-09-15: 原来只禁 "（论文图" (左括号紧贴), 而实际文本是
        # "（log–log 坐标，论文图）" —— 子串匹配绕过, 于是这句指向已删除
        # thesis/ 的图注同时留在网页版与入库 PDF 里。现在按 "论文图" 匹配。
        "论文图",
        "thesis/thesis1.pdf", "thesis/data/",
        "0.9085", "0.9227", "0.9100", "0.8946",
        "85.3%", "87.2%", "1/8 fp", "3/8 fp",
        "0.50–0.52", "约 73% 的增益",
        "独立 photo_id（与原训练集完全 disjoint）",
        "SRM 90 维只在同源", "论文与代码对照",
    ],
    "en": [
        "or the project thesis",
        # 同上: 原文是 "(log-log axes, thesis figure)", 只禁 "(thesis figure"
        # 拦不住。注意不能用裸 "thesis" —— 它会命中 "hypothesis"。
        "thesis figure", "project thesis", "thesis/thesis1.pdf", "thesis/data/",
        "0.9085", "0.9227", "0.9100", "0.8946",
        "85.3%", "87.2%", "1/8 FP", "3/8 FP", "1/8 OOD FP",
        "0.50-0.52", "~73% of the gain",
        "independent photo_ids (fully disjoint",
        "SRM helps only within the same source domain",
        "the paper draft", "the README/thesis",
    ],
}

# --------------------------------------------------------------------------
#  3) 逐处替换
# --------------------------------------------------------------------------
INLINE = {
    "zh": [
        ("也不代替论文，", ""),
        ("论文图", "项目图"),
        # 姊妹项目 yccstego: 独立仓库与 PyPI 包, 不在本仓库里 —— 给出地址
        ("（yccstego 扩展正是走量化 DCT 系数路线）",
         "（姊妹项目 yccstego 走的正是量化 DCT 系数路线："
         "https://github.com/Yukinoshita-lin/yccstego ，独立仓库与 PyPI 包，不在本仓库内）"),
        ("JPEG 域需要 yccstego 那样的 DCT 系数实现。",
         "JPEG 域需要 yccstego 那样的 DCT 系数实现（姊妹项目，独立仓库与 PyPI 包："
         "https://github.com/Yukinoshita-lin/yccstego ）。"),
        ("yccstego：Y 通道量化 DCT 系数 nsF5",
         "yccstego：Y 通道量化 DCT 系数 nsF5（姊妹项目，独立仓库："
         "https://github.com/Yukinoshita-lin/yccstego ）"),
        ("再用 yccstego 对照学习 JPEG 量化域",
         "再用姊妹项目 yccstego（https://github.com/Yukinoshita-lin/yccstego ）"
         "对照学习 JPEG 量化域"),
        ("论文与 README 都把这个列为后续工作", "README 把这个列为后续工作"),
        ("选论文/README 中的 1～2 个结论", "选 README / docs/RESULTS.md 中的 1～2 个结论"),
        ("10.4 论文与代码对照阅读表", "10.4 文档与代码对照阅读表"),
        ("AUC 更高、可逐维解释", "AUC 略低、但可逐维解释"),
        ("论文章节 || 对应代码", "文档章节 || 对应代码"),
        ("避坑提醒｜SRM 的收益只在“同源”数据内出现。",
         "避坑提醒（v1 时期对照，数字未在当前版本复现）｜当年观察到：SRM 预处理的收益只在"
         "“同源”数据内出现。"),
    ],
    "en": [
        ("It does not replace a textbook or the project thesis.",
         "It does not replace a textbook."),
        ("thesis figure", "project figure"),
        # companion project yccstego — same reasoning as the Chinese rules above
        ("(the yccstego extension goes the quantized-DCT-coefficient route)",
         "(the companion project yccstego goes the quantized-DCT-coefficient route: "
         "https://github.com/Yukinoshita-lin/yccstego , a separate repository and PyPI "
         "package, not part of this repository)"),
        ("JPEG-domain work needs the yccstego-style DCT coefficient design.",
         "JPEG-domain work needs the yccstego-style DCT coefficient design (companion "
         "project: https://github.com/Yukinoshita-lin/yccstego )."),
        ("yccstego: nsF5 on quantized DCT coefficients of Y",
         "yccstego: nsF5 on quantized DCT coefficients of Y (companion project: "
         "https://github.com/Yukinoshita-lin/yccstego )"),
        ("study yccstego's quantized-DCT pipeline",
         "study the companion project yccstego's quantized-DCT pipeline "
         "(https://github.com/Yukinoshita-lin/yccstego )"),
        ("The README and thesis list a keyed MAC as future work",
         "The README lists a keyed MAC as future work"),
        ("Choose one or two claims from the README/thesis",
         "Choose one or two claims from the README / docs/RESULTS.md"),
        ("10.4 Paper-to-Code Reading Table", "10.4 Document-to-Code Reading Table"),
        ("higher AUC, per-dimension explanations", "lower AUC, per-dimension explanations"),
        ("Watch out | The gain is only within the same source domain.",
         "Watch out (v1-era comparison; not reproduced in the current revision) | At the time the "
         "gain appeared only within the same source domain."),
        ("Papers / defenses / teaching / per-image explanations",
         "Teaching / defenses / per-image explanations (AUC ~0.05 lower)"),
    ],
}

# 整段重写: (定位锚点, 新的整段文字)
PARAGRAPH = {
    "zh": [
        ("ML 检测从 11 维特征 + LR/XGB（AUC 约 0.75–0.79）",
         "ML 检测从 11 维特征 + LR/XGB（AUC 约 0.75–0.79）升级为 143 维 LGB 默认版"
         "（8-split 平均 0.8980）与 53d 可解释版（0.8461）：143d 更准、53d 每一维都能解释，"
         "详见 8.8 与 docs/RESULTS.md；"),
        ("v1.4 双版本模型（见 8.8）把 8-split 平均 AUC 提升到",
         "ROC 曲线把阈值从 1 扫到 0，画出“检出率 vs 误报率”。AUC 是曲线下面积：0.5 是瞎猜。"
         "v1 基线上 0.75 量级说明“大部分时候能把含密图排在干净图前面”，但弱密度仍容易漏；"
         "v1.4 双版本模型（见 8.8）把 8-split 平均 AUC 做到 0.8980（143d）/ 0.8461（53d），"
         "口径见 docs/RESULTS.md。"),
        ("弱档 nsF5 p3 d0.25 检出率从 67.9% 升到 85.3%",
         "v2 LR 在训练分布内 AUC 很高，但部署到真实 JPEG 干净照片时几乎全判 1.0：SRM 残差对 "
         "JPEG 高频噪声过于敏感。修复办法是把 414 张真实 JPEG 干净图加进训练，得到 "
         "dataset_campus_v2_jpeg.csv，再做 LGB 网格调优。【2026-09-14 审计更正】这批 JPEG 干净行"
         "当初被赋予了独立 photo_id，而其特征与对应 clean 行逐位相同（是副本）：同一张源图的样本"
         "因此可以跨训练/验证两侧，“按源图划分”名存实亡、指标被抬高；同一批 GPU 特征还把像素先"
         "除以 255 再过高通滤波，与推理端 CPU 特征相差约 30 倍。两处都已修复并重跑"
         "（修复方式见 experiments/add_jpeg_clean.py，细节见 docs/RESULTS.md 与 CHANGELOG 1.6.2）。"
         "现口径：143d held-out AUC 0.8939、8-split 平均 0.8980、弱档 nsF5 p3 d0.25 检出 50.0%；"
         "53d 为 0.8391 / 0.8461 / 41.4%。"),
        ("SRM 90 维的单特征 AUC 平均只有 0.50–0.52",
         "可解释性实验（2026-09-14 按修正后的特征口径重算）：143 维里 SRM 90 维贡献了 52.6% 的 "
         "LightGBM gain，BASE 11 占 20.7%、LSB PREFIX 20 占 20.6%、PREFIX 20 占 6.2%；"
         "消融显示去掉 SRM 90 维后 5 折 OOF AUC 从 0.9010 掉到 0.8513（约 +0.05 AUC）。"
         "也就是说修好尺度之后 SRM 不是“噪声特征”。于是项目保留两套模型："),
        ("v1.4 之后双版本模型在训练分布内已很强",
         "v1.4 之后双版本模型在训练分布内已很强，但真实部署前仍必须做 OOD 验证：本项目在 1514 张"
         "真实干净照片（校园 414 + DIV2K 100 + ALASKA#2 1000）上实测，143d 误报 9.58%"
         "（95%CI 8.20–11.16%）、53d 28.86%（26.64–31.20%）；DIV2K 这类 2K 高清图是主要失分来源"
         "（143d 约 51%）。评估脚本 experiments/ood_eval.py，结果见 docs/RESULTS.md 第 5 节。"),
        ("CPU 11 维合并训练 72898 样本",
         "数据侧：项目建立了纯校园照片基准 data/campus_jpg（414 张，移除早期 DIP4E 教材图），"
         "并引入隐写分析事实标准 BOSSbase 1.01（1 万张 512² 灰度 PGM）做多源合并。"
         "2026-09-14 复核（可追到 experiments/data/gpu_pipeline_metrics.csv）：GPU 单跑校园 "
         "imageset AUC 0.7903（Youden 阈值 0.713、acc 0.802），BOSSbase 单跑 AUC 0.6438"
         "（0.798 / 0.655）；合并训练因仓库现有的 BOSSbase 图像集为 10000 样本（早期为 50000），"
         "改按 3410+10000=13410 样本重跑，AUC 0.6672。make_dataset.py 支持多进程"
         "（16 核约 5.6 倍加速），GPU 图像集用 memmap 逐张落盘避免大数组 OOM。"),
        ("提示：论文草稿已更新为 thesis/thesis1.pdf",
         "提示：本项目不再随仓库分发论文稿；对外数字一律以 docs/RESULTS.md（权威结果表）为准，"
         "它逐行标注了语料、协议与是否可溯源。下表按早期论文章节举例，阅读时请对照该表。"),
        ("v2/143 维模型对训练分布外的真实 JPEG 干净图曾",
         "v2/143 维模型对训练分布外的真实 JPEG 干净图曾“过激”，修复依赖把 JPEG 干净样本加入训练；"
         "任何模型都要先做 OOD 测试再部署——本项目现口径是 1514 张真实干净照片上 143d 误报 9.58%、"
         "53d 28.86%；"),
        ("双版本模型各有取舍：143d 更稳（OOD 1/8 fp）",
         "双版本模型各有取舍：143d 更准（8-split 平均 AUC 0.8980、弱档检出 50.0%、真实干净照片 "
         "OOD 误报 9.58%）；53d 去掉 SRM 后每一维都能解释，代价是 AUC 约低 0.05"
         "（0.8461 / 41.4% / 28.86%）。GUI 切换仍在规划，当前用 API 指定 model_path；"),
        ("项目 README 与论文草稿 thesis/thesis1.pdf",
         "项目 README 与权威结果表 docs/RESULTS.md（SRM/143d/53d 与多源实验的现口径，附语料与"
         "协议标注）；GitHub：Yukinoshita-lin/nsf5-steganography；"),
    ],
    "en": [
        ("ML detection grew from 11-D features with LR/XGB",
         "ML detection grew from 11-D features with LR/XGB (AUC ~0.75-0.79) to a 143-D LightGBM "
         "default (8-split mean 0.8980) plus a 53-D interpretable model (0.8461): the 143-D model "
         "is the more accurate one, the 53-D one explains every dimension. See 8.8 and docs/RESULTS.md;"),
        ("raise the 8-split average AUC to 0.9085-0.9227",
         "The ROC curve sweeps the threshold from 1 to 0 and plots detection rate against "
         "false-positive rate. AUC is the area under it: 0.5 is random. The v1 baseline around 0.75 "
         "means \"usually ranks stego above clean,\" but weak densities still escape. The v1.4 dual "
         "models reach an 8-split mean AUC of 0.8980 (143-D) / 0.8461 (53-D); see docs/RESULTS.md "
         "for the protocol."),
        ("as independent photo_ids (fully disjoint from the original training groups)",
         "The v2 logistic-regression model scored well inside its training distribution but flagged "
         "almost every real JPEG clean photo as stego with probability 1.0: SRM residuals react "
         "strongly to JPEG high-frequency noise. The fix was to add 414 real JPEG clean photos to "
         "the training corpus, producing dataset_campus_v2_jpeg.csv, then grid-tune LightGBM. "
         "[Corrected 2026-09-14] Those rows were originally given independent photo_ids while their "
         "features were bit-identical to the matching clean row (a duplicate), so a source photo "
         "could straddle the train/validation split and the by-photo discipline was nominal only; "
         "the same corpus was also built with GPU features that scaled pixels by 1/255 before the "
         "high-pass filters, differing from the CPU inference path by ~30x. Both are fixed and "
         "rerun (see experiments/add_jpeg_clean.py, docs/RESULTS.md, CHANGELOG 1.6.2). Current "
         "numbers: 143-D held-out 0.8939, 8-split 0.8980, weak nsF5 p3 d0.25 detection 50.0%; "
         "53-D 0.8391 / 0.8461 / 41.4%."),
        ("average single-feature AUC 0.50-0.52 (near random)",
         "Interpretability, recomputed after the audit: within the 143-D set the 90 SRM dimensions "
         "carry 52.6% of the LightGBM gain (BASE 11: 20.7%, LSB PREFIX 20: 20.6%, PREFIX 20: 6.2%); "
         "ablation shows that dropping them costs 0.05 AUC (5-fold OOF 0.9010 -> 0.8513). SRM is "
         "not a noise block once the scale is right. The project therefore ships both:"),
        ("Since v1.4, dual models are strong inside their distribution",
         "Since v1.4, dual models are strong inside their distribution, but real-JPEG OOD validation "
         "remains mandatory: on 1,514 real clean photos (414 campus + 100 DIV2K + 1,000 ALASKA#2) "
         "the 143-D model false-positives 9.58% (95% CI 8.20-11.16%) and the 53-D model 28.86% "
         "(26.64-31.20%); 2K DIV2K images are the main failure source (~51%). Script: "
         "experiments/ood_eval.py; results: docs/RESULTS.md section 5."),
        ("GPU merged training used 52,070 samples",
         "On the data side, v1.4 established a pure campus-photo baseline data/campus_jpg "
         "(414 photos; earlier DIP4E textbook images were removed) and added the standard "
         "steganalysis benchmark BOSSbase 1.01 (10,000 512x512 grayscale PGM images) for "
         "multi-source training. Re-checked 2026-09-14 (experiments/data/gpu_pipeline_metrics.csv): "
         "GPU campus-only AUC 0.7903 (Youden 0.713, acc 0.802), BOSSbase-only AUC 0.6438 "
         "(0.798 / 0.655); the merged run uses the 10,000-sample BOSSbase imageset available in "
         "this repo (the older number used 50,000), so it was rerun as 3,410 + 10,000 = 13,410 "
         "samples with AUC 0.6672. make_dataset.py now supports multiprocessing (~5.6x on 16 cores) "
         "and the GPU imagesets are written per-image with memmap to avoid large-array OOM."),
        ("the paper draft has been updated to thesis/thesis1.pdf",
         "Note: this repository no longer ships the paper manuscripts; every reported number now "
         "lives in docs/RESULTS.md (the canonical results table), which labels each row with its "
         "corpus, protocol and traceability. The table below keeps the early paper's structure as "
         "an example - cross-reference that table."),
        ("The v2/143-D model was over-aggressive",
         "The v2/143-D model was over-aggressive on out-of-distribution real JPEG clean images; the "
         "fix requires JPEG clean samples in training - always run OOD tests before deployment "
         "(current numbers: 1,514 real clean photos, 143-D 9.58% / 53-D 28.86% false positives);"),
        ("The dual models trade off robustness and interpretability (143d: 1/8 OOD FP",
         "The dual models trade accuracy for interpretability (143-D: 8-split mean AUC 0.8980, "
         "weak-band detection 50.0%, OOD false-positive 9.58%; 53-D: 0.8461 / 41.4% / 28.86%, but "
         "every dimension is explainable); GUI switching is planned, use the API today;"),
        ("The project README and the thesis draft thesis/thesis1.pdf",
         "The project README and the canonical results table docs/RESULTS.md (current numbers for "
         "the SRM / 143-D / 53-D and multi-source experiments, with corpus and protocol labels); "
         "GitHub: Yukinoshita-lin/nsf5-steganography;"),
        ("SRM helps only within the same source domain",
         "SRM residuals are the single largest gain contributor (52.6% of LightGBM gain) once the "
         "feature scale is consistent, but they are also the least interpretable block - removing "
         "them is what makes the 53-D model explainable, at a cost of about 0.05 AUC;"),
    ],
}

# 表格单元格整格替换: (锚点, 新文本)
CELL = {
    "zh": [
        ("对比图 8-2 与 thesis/data/det_density.csv",
         "回到项目看代码｜对比 experiments/data/density_grid.csv（第 5 章实验产出的真实统计）："
         "lsb 各档几乎 100% 检出，matrix p2 d0.80 约 95%，而弱档 nsF5 p3 d0.25 只有约 47%、"
         "nsF5 p3 d0.55 约 55%。这说明“弱嵌入更难检测”不是玄学，而是统计足迹随密度衰减的直接结果。"),
        ("注意 photo_id 这一行",
         "注意 photo_id 这一行：同一张照片的干净样本与其变体必须共享同一个 id——这是防数据泄漏的关键。"
         "2026-09-14 的审计就是因为 414 个 JPEG 干净行各占了一个独立 id，让“按源图划分”失效、"
         "AUC 被抬高约 0.14；现在生成脚本（experiments/add_jpeg_clean.py）会强制把它绑回源图，"
         "训练脚本也会在开训前校验这条不变量。"),
    ],
    "en": [
        ("Compare Fig. 8-2 with thesis/data/det_density.csv",
         "Read the code | Compare experiments/data/density_grid.csv (real statistics produced by the "
         "chapter-5 experiments): LSB bands are near 100%, matrix p2 d0.80 is about 95%, while weak "
         "nsF5 p3 d0.25 reaches only ~47% and nsF5 p3 d0.55 ~55%. Weak embedding being harder to "
         "detect is not mysticism; it is the direct result of a smaller statistical footprint."),
        ("Note the photo_id column",
         "Note the photo_id column: a source photo and all its variants must share one id - that is "
         "the key defence against data leakage. The 2026-09-14 audit found 414 JPEG-clean rows that "
         "each held an independent id, which broke the by-photo split and inflated AUC by about "
         "0.14; the generator (experiments/add_jpeg_clean.py) now binds those rows back to their "
         "source photo, and the training script refuses corpora that break this invariant."),
    ],
}

# 表格整行替换: (行首单元格锚点, [新单元格文本...])
ROW = {
    "zh": [
        ("8-split 平均 AUC", ["8-split 平均 AUC", "0.8980", "0.8461"]),
        ("Held-out AUC", ["Held-out AUC", "0.8939", "0.8391"]),
        ("弱档 nsF5 p3 d0.25", ["弱档 nsF5 p3 d0.25", "50.0%", "41.4%"]),
        ("真实 JPEG 干净 OOD",
         ["真实 JPEG 干净 OOD", "9.58%（n=1514，95%CI 8.20–11.16%）",
          "28.86%（n=1514，95%CI 26.64–31.20%）"]),
        ("推荐场景", ["推荐场景", "通用部署 / 异构数据 / 真实图",
                   "教学 / 答辩 / 单图可解释（AUC 略低约 0.05）"]),
    ],
    "en": [
        ("8-split mean AUC", ["8-split mean AUC", "0.8980", "0.8461"]),
        ("Held-out AUC", ["Held-out AUC", "0.8939", "0.8391"]),
        ("Weak nsF5 p3 d0.25", ["Weak nsF5 p3 d0.25", "50.0%", "41.4%"]),
        ("Real-JPEG clean OOD",
         ["Real-JPEG clean OOD", "9.58% (n=1514, 95% CI 8.20-11.16%)",
          "28.86% (n=1514, 95% CI 26.64-31.20%)"]),
        ("Best for", ["Best for", "Deployment / mixed domains / real images",
                      "Teaching / defenses / per-image explanations (AUC ~0.05 lower)"]),
    ],
}

# --------------------------------------------------------------------------
#  网页版 markdown 的修正表
#  (网页版比 DOCX 丰富得多 —— 直接重新生成会删掉大量内容, 因此单独做文本替换,
#   不重新生成。2026-09-14 实测: docx2md 从当前 DOCX 只能产出 78 行的第 7 章,
#   而入库的 ch07.md 有 190 行。)
# --------------------------------------------------------------------------
WEB = {
    "zh": [
        ("它不代替教科书，也不代替论文，而是把", "它不代替教科书，而是把"),
        ("论文图", "项目图"),
        # 姊妹项目 yccstego: 网页版用 markdown 链接 (渲染后可直接点)
        ("（yccstego 扩展正是走量化 DCT 系数路线）",
         "（姊妹项目 [`yccstego`](https://github.com/Yukinoshita-lin/yccstego) 走的正是量化 "
         "DCT 系数路线；它是独立仓库与 PyPI 包，不在本仓库内）"),
        ("JPEG 域需要 yccstego 那样的 DCT 系数实现。",
         "JPEG 域需要 [`yccstego`](https://github.com/Yukinoshita-lin/yccstego) 那样的 "
         "DCT 系数实现（姊妹项目，独立仓库与 PyPI 包）。"),
        ("| JPEG 域隐写 | yccstego：Y 通道量化 DCT 系数 nsF5 | 本项目即可扩展 |",
         "| JPEG 域隐写 | [`yccstego`](https://github.com/Yukinoshita-lin/yccstego)："
         "Y 通道量化 DCT 系数 nsF5 | 姊妹项目（独立仓库与 PyPI 包） |"),
        ("再用 `yccstego` 对照学习 JPEG 量化域",
         "再用姊妹项目 [`yccstego`](https://github.com/Yukinoshita-lin/yccstego) "
         "对照学习 JPEG 量化域"),
        ("（项目 `yccstego` 扩展即此方向）",
         "（姊妹项目 [`yccstego`](https://github.com/Yukinoshita-lin/yccstego) 即此方向）"),
        ("- 项目 README 与论文草稿 thesis/thesis1.pdf（SRM/143d/53d 与多源实验见论文实验章）；",
         "- 项目 README 与权威结果表 `docs/RESULTS.md`（SRM/143d/53d 与多源实验的现口径）；"),
        ("| 研究主线 | 复现论文→找 gap→做改进→诚实评估 | 论文（appE）与 `thesis/`；",
         "| 研究主线 | 复现论文→找 gap→做改进→诚实评估 | 文献（appE）与 `docs/RESULTS.md`；"),
        ("> **回到项目看代码｜** 对比 `thesis/data/det_density.csv`：弱档 nsF5 p3 d≈0.3 检出约 48%~64%，"
         "强档 matrix p2/p3 接近 75%~99%。这就印证了 8.3 的话——**小密度统计足迹弱，特征信号弱，"
         "所以更难检出**，不是玄学。",
         "> **回到项目看代码｜** 对比 `experiments/data/density_grid.csv`（第 5 章实验产出的真实统计）："
         "lsb 各档几乎 100% 检出，matrix p2 d0.80 约 95%，而弱档 nsF5 p3 d0.25 只有约 47%、"
         "nsF5 p3 d0.55 约 55%。这就印证了 8.3 的话——**小密度统计足迹弱，特征信号弱，所以更难检出**，"
         "不是玄学。"),
        ("| 8-split 平均 AUC | 0.9085 | 0.9227 |",
         "| 8-split 平均 AUC | **0.8980** | 0.8461 |"),
        ("| Held-out AUC | 0.8946 | 0.9100 |",
         "| Held-out AUC | **0.8939** | 0.8391 |"),
        ("| 弱档 nsF5 p3 d0.25 | 85.3% | 87.2% |",
         "| 弱档 nsF5 p3 d0.25 | **50.0%** | 41.4% |"),
        ("| 真实 JPEG 干净 OOD | 1/8 fp（median 0.011） | 3/8 fp（median 0.028） |",
         "| 真实 JPEG 干净 OOD | **9.58%**（n=1514，95%CI 8.20–11.16%） | "
         "28.86%（26.64–31.20%） |"),
        ("| 适用场景 | 通用部署 / 异构数据 / 真实图 | 论文 / 答辩 / 教学 / 单图可解释 |",
         "| 适用场景 | 通用部署 / 异构数据 / 真实图 | 教学 / 答辩 / 单图可解释（AUC 略低约 0.05） |"),
        ("| **论文章节** | **对应代码** | **读它之前先掌握** |",
         "| **文档章节** | **对应代码** | **读它之前先掌握** |"),
        ("## 10.4 论文与代码对照阅读表", "## 10.4 文档与代码对照阅读表"),
        ("选论文/README 中的 1～2 个结论", "选 README / `docs/RESULTS.md` 中的 1～2 个结论"),
        ("### 8.8.1 SRM 高通滤波：同源有收益，跨源反而亏",
         "### 8.8.1 SRM 高通滤波：v1 时期同源有收益、跨源反而亏（该口径未在当前版本复现）"),
        ("# 53d 可解释版（去 SRM 90 维，AUC 更高、可逐维解释）",
         "# 53d 可解释版（去 SRM 90 维；AUC 略低，但每一维都能解释）"),
        ("SRM 同源有收益、跨源反而亏（ch08.8.1）",
         "SRM 预处理在 v1 口径下同源有收益、跨源反而亏（ch08.8.1；该口径未在当前版本复现）"),
        ("v2 逻辑回归在训练分布内 AUC 很高，但部署到真实 JPEG 干净照片时**几乎全判 1.0**："
         "SRM 残差对 JPEG 高频噪声过于敏感。修复办法是把 414 张真实 JPEG 干净图作为独立 "
         "`photo_id`（与原训练集完全不相交）加入训练，得 `dataset_campus_v2_jpeg.csv`，"
         "再做 LGB 网格调优。最终 LGB tuned 成为新默认：held-out AUC 0.8946、8-split 平均 "
         "0.9085，弱档 nsF5 p3 d0.25 检出率从 67.9% 升到 85.3%。",
         "v2 逻辑回归在训练分布内 AUC 很高，但部署到真实 JPEG 干净照片时**几乎全判 1.0**："
         "SRM 残差对 JPEG 高频噪声过于敏感。修复办法是把 414 张真实 JPEG 干净图加进训练，"
         "得 `dataset_campus_v2_jpeg.csv`，再做 LGB 网格调优。"
         "**2026-09-14 审计更正：** 这批 JPEG 干净行当初被赋予了独立 `photo_id`，而特征与对应 "
         "`clean` 行逐位相同（是副本）——同一张源图的样本因此可以跨训练/验证两侧；同一批 GPU "
         "特征还把像素先除以 255 再过高通滤波，与推理端 CPU 特征相差约 30 倍。两处都已修复并重跑"
         "（见 `experiments/add_jpeg_clean.py` 与 `docs/RESULTS.md`）。现口径：143d held-out "
         "**0.8939**、8-split **0.8980**、弱档 nsF5 p3 d0.25 检出 **50.0%**；53d 为 "
         "0.8391 / 0.8461 / 41.4%。"),
        ("可解释性实验发现：143 维里约 73% 的增益来自 31 个可解释特征（BASE 11 + PREFIX 20）；"
         "SRM 90 维单个特征 AUC 平均只有 0.50~0.52（接近随机），但在 LGB 里起到“过滤 JPEG "
         "噪声、提升 OOD 鲁棒性”的作用。于是保留两套模型：",
         "可解释性实验（2026-09-14 按修正后的特征口径重算）：143 维里 SRM 90 维贡献了 **52.6%** "
         "的 LightGBM gain（BASE 11 占 20.7%、LSB PREFIX 20 占 20.6%、PREFIX 20 占 6.2%）；"
         "消融显示去掉 SRM 90 维后 5 折 OOF AUC 从 0.9010 掉到 0.8513（约 +0.05 AUC）。"
         "也就是说修好尺度之后 SRM 不是“噪声特征”。于是保留两套模型："),
        ("- 双版本模型各有取舍：143d 更稳（OOD 1/8 fp）、53d AUC 更高更可解释（OOD 3/8 fp），"
         "GUI 切换仍在规划，当前用 API 指定 model_path；",
         "- 双版本模型各有取舍：143d 更准（8-split 平均 AUC 0.8980、弱档检出 50.0%、真实干净照片 OOD "
         "误报 9.58%）、53d 每一维都能解释但 AUC 约低 0.05（0.8461 / 41.4% / 28.86%）；"
         "GUI 切换仍在规划，当前用 API 指定 model_path；"),
        ("*提示：论文草稿已更新为 thesis/thesis1.pdf（v1.4.0 实验，含 SRM/143d/53d 与多源数据），"
         "上表以早期论文章节为例，阅读时按新论文目录对照。*",
         "*提示：本项目不再随仓库分发论文稿；对外数字一律以 `docs/RESULTS.md`（权威结果表）为准，"
         "它逐行标注了语料、协议与是否可溯源。上表按早期论文章节举例，阅读时请对照该表。*"),
        ("- ML 检测从 11 维特征 + LR/XGB（AUC 约 0.75–0.79）升级为 143 维 LGB 默认版"
         "（8 折平均 0.9085）与 53d 可解释版（0.9227），详见 8.8；",
         "- ML 检测从 11 维特征 + LR/XGB（AUC 约 0.75–0.79）升级为 143 维 LGB 默认版"
         "（8-split 平均 0.8980）与 53d 可解释版（0.8461）：143d 更准、53d 每一维都能解释，"
         "详见 8.8 与 `docs/RESULTS.md`；"),
    ],
    "en": [
        ("It does not replace a textbook or the project thesis.", "It does not replace a textbook."),
        ("thesis figure", "project figure"),
        ("(the yccstego extension goes the quantized-DCT-coefficient route)",
         "(the companion project [yccstego](https://github.com/Yukinoshita-lin/yccstego) "
         "goes the quantized-DCT-coefficient route; it is a separate repository and PyPI "
         "package, not part of this repository)"),
        ("JPEG-domain work needs the yccstego-style DCT coefficient design.",
         "JPEG-domain work needs the [yccstego](https://github.com/Yukinoshita-lin/yccstego)"
         "-style DCT coefficient design (companion project, separate repository and PyPI "
         "package)."),
        ("| JPEG-domain hiding | yccstego: nsF5 on quantized DCT coefficients of Y | Direct extension of this project |",
         "| JPEG-domain hiding | [yccstego](https://github.com/Yukinoshita-lin/yccstego): "
         "nsF5 on quantized DCT coefficients of Y | Companion project (separate repository "
         "and PyPI package) |"),
        ("study yccstego's quantized-DCT pipeline",
         "study the companion project [yccstego](https://github.com/Yukinoshita-lin/yccstego)"
         "'s quantized-DCT pipeline"),
        ("(the project's `yccstego` extension is this direction)",
         "(the companion project [yccstego](https://github.com/Yukinoshita-lin/yccstego) "
         "is this direction)"),
        ("- The project README and the thesis draft thesis/thesis1.pdf "
         "(SRM / 143-D / 53-D experiments are in the experimental chapter);",
         "- The project README and the canonical results table `docs/RESULTS.md` "
         "(current numbers for the SRM / 143-D / 53-D experiments);"),
        ("papers (appE) and `thesis/`;", "literature (appE) and `docs/RESULTS.md`;"),
        ("> **Back to the code |** Compare `thesis/data/det_density.csv`: weak nsF5 p3 band around "
         "48-64%, strong matrix p2/p3 75-99%.",
         "> **Back to the code |** Compare `experiments/data/density_grid.csv` (real statistics "
         "produced by the chapter-5 experiments): LSB bands are near 100%, matrix p2 d0.80 is "
         "about 95%, while weak nsF5 p3 d0.25 reaches only ~47% and nsF5 p3 d0.55 ~55%."),
        ("| 8-split mean AUC | 0.9085 | 0.9227 |",
         "| 8-split mean AUC | **0.8980** | 0.8461 |"),
        ("| Held-out AUC | 0.8946 | 0.9100 |",
         "| Held-out AUC | **0.8939** | 0.8391 |"),
        ("| Weak nsF5 p3 d0.25 | 85.3% | 87.2% |",
         "| Weak nsF5 p3 d0.25 | **50.0%** | 41.4% |"),
        ("| Real-JPEG clean OOD | 1/8 fp (median 0.011) | 3/8 fp (median 0.028) |",
         "| Real-JPEG clean OOD | **9.58%** (n=1514, 95% CI 8.20-11.16%) | "
         "28.86% (26.64-31.20%) |"),
        ("| Best for | Deployment / mixed domains / real images | "
         "Papers / defenses / teaching / per-image explanations |",
         "| Best for | Deployment / mixed domains / real images | "
         "Teaching / defenses / per-image explanations (AUC ~0.05 lower) |"),
        ("- The dual models trade off robustness and interpretability (143d: 1/8 OOD FP; "
         "53d: higher AUC but 3/8 OOD FP);",
         "- The dual models trade accuracy for interpretability (143-D: 8-split mean AUC 0.8980, "
         "weak-band detection 50.0%, OOD false-positive 9.58%; 53-D: 0.8461 / 41.4% / 28.86%, "
         "but every dimension is explainable);"),
        ("*Tip: the paper draft has been updated to thesis/thesis1.pdf (v1.4.0 experiments, "
         "incl. SRM/143d/53d and multi-source data); the table above uses the early paper's "
         "sections as an example - cross-reference the new paper's table of contents.*",
         "*Tip: this repository no longer ships the paper manuscripts; every number now lives in "
         "`docs/RESULTS.md` (the canonical results table), which labels each row with its corpus, "
         "protocol and traceability. The table below keeps the early paper's structure as an "
         "example - cross-reference that table.*"),
        ("The v2 logistic model scored well inside its training distribution, but on real JPEG "
         "clean photos it **flagged almost everything as 1.0**: SRM residuals react strongly to "
         "JPEG high-frequency noise. The fix: add 414 real JPEG clean photos as independent "
         "`photo_id` (fully disjoint from the original training groups), producing "
         "`dataset_campus_v2_jpeg.csv`, then grid-tune LightGBM. The tuned LGB became default: "
         "held-out AUC 0.8946, 8-split average 0.9085, weak nsF5 p3 d0.25 detection up from 67.9% "
         "to 85.3%.",
         "The v2 logistic model scored well inside its training distribution, but on real JPEG "
         "clean photos it **flagged almost everything as 1.0**: SRM residuals react strongly to "
         "JPEG high-frequency noise. The fix: add 414 real JPEG clean photos to the training "
         "corpus, producing `dataset_campus_v2_jpeg.csv`, then grid-tune LightGBM. "
         "**Corrected 2026-09-14:** those rows were originally given independent `photo_id`s "
         "while their features were bit-identical to the matching `clean` row (a duplicate), so a "
         "source photo could straddle the train/validation split; the corpus was also built with "
         "GPU features that scaled pixels by 1/255 before the high-pass filters, differing from "
         "the CPU inference path by ~30x. Both are fixed and rerun (see "
         "`experiments/add_jpeg_clean.py` and `docs/RESULTS.md`). Current numbers: 143-D held-out "
         "**0.8939**, 8-split **0.8980**, weak nsF5 p3 d0.25 **50.0%**; 53-D 0.8391 / 0.8461 / "
         "41.4%."),
        ("Interpretability experiments showed ~73% of the 143-D gain comes from 31 explainable "
         "features (BASE 11 + PREFIX 20); the SRM 90 dimensions average single-feature AUC "
         "0.50-0.52 (near random) yet serve as a buffer that filters JPEG noise and improves OOD "
         "robustness. So two models are kept:",
         "Interpretability, recomputed after the audit: within the 143-D set the 90 SRM dimensions "
         "carry **52.6%** of the LightGBM gain (BASE 11: 20.7%, LSB PREFIX 20: 20.6%, "
         "PREFIX 20: 6.2%); ablation shows that dropping them costs 0.05 AUC (5-fold OOF 0.9010 -> "
         "0.8513). So two models are kept:"),
        ("- SRM helps only within the same source domain and hurts across heterogeneous sources;",
         "- The 90 SRM residual statistics are the single largest gain contributor (52.6%) once "
         "the feature scale is consistent, but they are also the least interpretable block - that "
         "is the trade-off the 53-D model removes;"),
        ("### 8.8.1 SRM High-Pass Filtering: Same-Source Gain, Cross-Source Loss",
         "### 8.8.1 SRM High-Pass Filtering: v1-Era Same-Source Gain, Cross-Source Loss "
         "(not reproduced in the current revision)"),
        ("# 53d interpretable model (SRM 90 removed; higher AUC)",
         "# 53d interpretable model (SRM 90 removed; slightly lower AUC, fully interpretable)"),
        ("SRM gains on same-source but loses on cross-source (ch08.8.1)",
         "In the v1-era protocol SRM gains on same-source but loses on cross-source "
         "(ch08.8.1; not reproduced in the current revision)"),
        ("> **Watch out |** The gain only appears within **same-source** data.",
         "> **Watch out (v1-era protocol; not reproduced in the current revision) |** "
         "In that protocol the gain only appeared within **same-source** data."),
        ("- ML detection grew from 11-D features with LR/XGB (AUC ~0.75-0.79) to a 143-D LightGBM "
         "default (0.9085 average) plus a 53-D interpretable model (0.9227); see 8.8;",
         "- ML detection grew from 11-D features with LR/XGB (AUC ~0.75-0.79) to a 143-D LightGBM "
         "default (8-split mean 0.8980) plus a 53-D interpretable model (0.8461): the 143-D model "
         "is the more accurate one, the 53-D one explains every dimension; see 8.8 and "
         "`docs/RESULTS.md`;"),
    ],
}


# --------------------------------------------------------------------------
#  docx 读写工具
# --------------------------------------------------------------------------
def set_paragraph_text(p, text: str) -> None:
    """把整段文字替换为 text, 尽量保留第一个 run 的格式。"""
    if p.runs:
        p.runs[0].text = text
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(text)


def replace_in_paragraph(p, old: str, new: str) -> int:
    """段落内替换。先试单个 run, 跨 run 时重建整段 (牺牲该段内的局部格式)。"""
    if old not in p.text:
        return 0
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new)
            return 1
    set_paragraph_text(p, p.text.replace(old, new))
    return 1


def iter_paragraphs(doc):
    for p in doc.paragraphs:
        yield p
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def fix_docx(path: str, lang: str, apply: bool) -> list:
    from docx import Document
    doc = Document(path)
    hits = []

    # 整段重写
    for anchor, new in PARAGRAPH[lang]:
        for p in iter_paragraphs(doc):
            if anchor in p.text:
                hits.append(f"段落锚点 {anchor[:28]}…")
                if apply:
                    set_paragraph_text(p, new)
                break
    # 单元格整格
    for anchor, new in CELL[lang]:
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    if anchor in cell.text:
                        hits.append(f"单元格锚点 {anchor[:24]}…")
                        if apply:
                            set_paragraph_text(cell.paragraphs[0], new)
                            for extra in cell.paragraphs[1:]:
                                set_paragraph_text(extra, "")
                        break
    # 整行
    for anchor, cells in ROW[lang]:
        for t in doc.tables:
            for row in t.rows:
                # 必须**整格相等**且列数一致 —— 2026-09-14 踩过的坑: 用子串匹配
                # 会连"弱档 nsF5 p3 d0.25 检出"(v1 时期 SRM 对照表)一起改掉,
                # 把另一张表的数字覆盖成部署表的数字。
                if row.cells[0].text.strip() == anchor and len(row.cells) == len(cells):
                    hits.append(f"行锚点 {anchor}")
                    if apply:
                        for cell, text in zip(row.cells, cells):
                            set_paragraph_text(cell.paragraphs[0], text)
                    break            # 只改第一张匹配的表
    # 行内替换
    for old, new in INLINE[lang]:
        n = 0
        for p in iter_paragraphs(doc):
            n += replace_in_paragraph(p, old, new)
        if n:
            hits.append(f"行内 {old[:24]}… x{n}")
    if apply:
        backup = path + ".orig.docx"
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        doc.save(path)
    return hits


def docx_text(path: str) -> str:
    from docx import Document
    d = Document(path)
    parts = [p.text for p in _all_paragraphs(d)]
    for t in d.tables:
        for row in t.rows:
            parts.extend(c.text for c in row.cells)
    return "\n".join(parts)


def _all_paragraphs(d):
    for p in d.paragraphs:
        yield p
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    yield p


def web_text(lang: str) -> str:
    d = WEBDIR[lang]
    parts = []
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".md"):
            parts.append(io.open(os.path.join(d, fn), encoding="utf-8").read())
    return "\n".join(parts)


def fix_web(lang: str, apply: bool) -> list:
    """把网页版 markdown 里的陈旧结论就地替换 (不重新生成 —— 见 WEB 表的说明)。"""
    hits = []
    d = WEBDIR[lang]
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"):
            continue
        p = os.path.join(d, fn)
        txt = io.open(p, encoding="utf-8").read()
        new = txt
        for old, rep in WEB[lang]:
            if old in new:
                new = new.replace(old, rep)
                hits.append(f"{fn}: {old[:34]}…")
        if apply and new != txt:
            io.open(p, "w", encoding="utf-8", newline="\n").write(new)
    return hits


def check(include_web: bool) -> int:
    bad = 0
    for lang in ("zh", "en"):
        sources = []
        if os.path.exists(DOCX[lang]):
            sources.append(("docx", docx_text(DOCX[lang])))
        else:
            print(f"  [跳过] {lang} 的 DOCX 源稿不在 (docs/src/ 不入库); "
                  f"本地跑 `make handbook-fix` 前请先放回源稿")
        if include_web:
            sources.append(("web", web_text(lang)))
        pdf_text = _pdf_text(PDF[lang])
        if pdf_text:
            sources.append(("pdf", pdf_text))
        for label, text in sources:
            if not text:
                continue
            for s in FORBIDDEN[lang]:
                if s in text:
                    print(f"  [陈旧结论] {lang}/{label}: 仍含 {s!r}")
                    bad += 1
            for s in REQUIRED:
                if s not in text:
                    print(f"  [缺现口径] {lang}/{label}: 缺 {s!r}")
                    bad += 1
    # 视频脚本文稿 (只有中文旁白)
    for p in VIDEO_FILES["zh"]:
        if not os.path.exists(p):
            continue
        txt = io.open(p, encoding="utf-8").read()
        for s in VIDEO_FORBIDDEN:
            if s in txt:
                print(f"  [陈旧结论] video/{os.path.basename(p)}: 仍含 {s!r}")
                bad += 1
        for s in VIDEO_REQUIRED:
            if s not in txt:
                print(f"  [缺现口径] video/{os.path.basename(p)}: 缺 {s!r}")
                bad += 1
    if bad:
        print(f"\n手册校验未通过: {bad} 处。跑 `python teaching/handbook_facts.py --fix` 修正源稿。")
        return 1
    print("手册校验通过: 无陈旧结论, 现口径齐全")
    return 0


def _pdf_text(path: str) -> str:
    """抽取 PDF 全文用于校验 (入库的 PDF 是最容易被读者看到的那份)。

    pypdf 缺失或文件不存在时返回空串 —— 校验会据此跳过该来源, 而不是报错。
    """
    if not os.path.exists(path):
        return ""
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"  [跳过] 未安装 pypdf, 不校验 {os.path.basename(path)}")
        return ""
    try:
        return "".join((p.extract_text() or "") for p in PdfReader(path).pages)
    except Exception as exc:  # noqa: BLE001
        print(f"  [跳过] 读取 {os.path.basename(path)} 失败: {type(exc).__name__}")
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="手册事实修正/校验")
    ap.add_argument("--fix", action="store_true", help="按表修正 DOCX 源稿")
    ap.add_argument("--check", action="store_true", help="只校验 (默认行为)")
    ap.add_argument("--web", action="store_true", help="--fix 时同时改写网页版 markdown")
    ap.add_argument("--no-web-check", action="store_true", help="校验时跳过 teaching/web")
    args = ap.parse_args()

    if args.fix:
        for lang in ("zh", "en"):
            hits = fix_docx(DOCX[lang], lang, apply=True)
            print(f"[{lang}] 修正 {len(hits)} 处:")
            for h in hits:
                print("   -", h)
        if args.web:
            for lang in ("zh", "en"):
                hits = fix_web(lang, apply=True)
                print(f"[{lang}/web] 修正 {len(hits)} 处:")
                for h in hits:
                    print("   -", h)
            print("提示: 网页版是独立内容 (比 DOCX 丰富), 不要用 `make web-convert` 覆盖它。")
        return 0
    return check(include_web=not args.no_web_check)


if __name__ == "__main__":
    raise SystemExit(main())
