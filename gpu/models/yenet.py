"""
yenet —— Ye-Net (Ye et al., IEEE TIFS 2017) 的复现。

⚠ 依论文描述自行复现, 非作者官方实现; 绝对数值不可与原文逐位对比。

结构 (输入 1×256×256 灰度, 输出 1 个 logit):
    SRM 固定高通层 30×5x5 (不参与梯度) → 缩放 1/q → TLU(clamp ±T)
    Conv5x5 30→64   BN ReLU AvgPool2     256 → 128
    Conv5x5 64→64   BN ReLU AvgPool2     128 → 64
    Conv3x3 64→128  BN ReLU AvgPool2      64 → 32
    Conv3x3 128→128 BN ReLU AvgPool2      32 → 16
    GAP → FC 128 → 1

SRM 核复用项目自己的 `src/srm_filter.SRM_KERNELS` (30 个, 已按类内归一化,
3x3 核对齐到 5x5), 与 `gpu/featurize_v2_gpu.py` 提 v2 特征时用的是同一组核
—— 这样 Ye-Net 与 143d LGB 基线看到的是同一个残差空间, 对比才有意义。

零填充: 与 `src/srm_filter.py` 的 `srm_residuals_*` 保持一致的 padding=2
(原文用镜像填充; 此处沿用项目既有口径, 以免同仓两套残差定义)。

⚠ 偏离原文之处 (缩放 1/q): 实测本仓 SRM_KERNELS 在真实照片上的残差
std ≈ 7–13, 若照原文直接 TLU(±3) 会截掉 7%–60% 的系数、通道几乎饱和。
原文的 SRM 量化是 trunc_T(round(res/q)), q 是逐核量化步长; 这里取统一
q=4 —— 与本仓 `src/srm_filter.py::DEFAULT_T = 4.0` 认定"|残差|≤4 为有效带"
的尺度约定一致 —— 再 TLU(±3)。q 与 T 均为可调参数, 不是拟合出来的。
"""
from __future__ import annotations

import os
import sys

import numpy as np
import torch
import torch.nn as nn

_SRC = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from srm_filter import SRM_KERNELS  # noqa: E402

TLU_T = 3.0
TLU_Q = 4.0


class SRMLayer(nn.Module):
    """固定 (不训练) 的 SRM 高通卷积层 + 1/q 缩放 + TLU 截断。"""

    def __init__(self, T: float = TLU_T, q: float = TLU_Q):
        super().__init__()
        k = torch.from_numpy(np.ascontiguousarray(SRM_KERNELS, dtype=np.float32))
        self.conv = nn.Conv2d(1, k.shape[0], 5, padding=2, bias=False)
        with torch.no_grad():
            self.conv.weight.copy_(k[:, None, :, :])
        self.conv.weight.requires_grad_(False)
        self.T = T
        self.q = q

    def forward(self, x):
        return torch.clamp(self.conv(x) / self.q, -self.T, self.T)


class YeNet(nn.Module):
    def __init__(self, in_ch: int = 1, n_classes: int = 1,
                 T: float = TLU_T, q: float = TLU_Q):
        super().__init__()
        if in_ch != 1:
            raise ValueError("Ye-Net 的 SRM 高通层按单通道灰度设计; "
                             "彩色图应先转灰度再送入")
        self.in_ch = in_ch
        self.srm = SRMLayer(T, q)

        def block(cin, cout, k, pool=True):
            layers = [nn.Conv2d(cin, cout, k, padding=k // 2, bias=False),
                      nn.BatchNorm2d(cout),
                      nn.ReLU(inplace=True)]
            if pool:
                layers.append(nn.AvgPool2d(2))
            return layers

        self.features = nn.Sequential(
            *block(30, 64, 5),
            *block(64, 64, 5),
            *block(64, 128, 3),
            *block(128, 128, 3),
        )
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(128, n_classes)

    def forward(self, x):
        x = self.srm(x)
        x = self.features(x)
        x = self.gap(x).flatten(1)
        return self.head(x)

    def extra_repr(self):
        return "Ye-Net replication (Ye et al. 2017), not authors' official code"
