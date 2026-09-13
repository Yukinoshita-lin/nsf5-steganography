"""
xunet —— Xu-Net (Xu et al., IEEE SPL 2016) 的复现。

⚠ 依论文描述自行复现, 非作者官方实现; 绝对数值不可与原文逐位对比。

结构 (输入 1×256×256 灰度, 输出 1 个 logit):
    Conv5x5 1→8    BN Tanh
    Conv5x5 8→16   BN Tanh AvgPool2      256 → 128
    Conv1x1 16→32  BN Tanh
    Conv1x1 32→64  BN Tanh AvgPool2      128 → 64
    Conv1x1 64→128 BN Tanh AvgPool2       64 → 32
    Conv1x1 128→256 BN Tanh AvgPool2      32 → 16
    Flatten(256*16*16) → FC 128 BN Tanh → FC 1

设计要点遵循原文: 前两层用 5x5 大核吸收局部残差相关性, 之后全用 1x1 逐点
卷积 (只做通道混合, 不再扩大感受野), 激活统一用 Tanh 且在 BN 之后。
"""
from __future__ import annotations

import torch
import torch.nn as nn


class XuNet(nn.Module):
    def __init__(self, in_ch: int = 1, n_classes: int = 1):
        super().__init__()
        self.in_ch = in_ch

        def block(cin, cout, k, pool=False):
            layers = [nn.Conv2d(cin, cout, k, padding=k // 2, bias=False),
                      nn.BatchNorm2d(cout),
                      nn.Tanh()]
            if pool:
                layers.append(nn.AvgPool2d(2))
            return layers

        self.features = nn.Sequential(
            *block(in_ch, 8, 5),
            *block(8, 16, 5, pool=True),
            *block(16, 32, 1),
            *block(32, 64, 1, pool=True),
            *block(64, 128, 1, pool=True),
            *block(128, 256, 1, pool=True),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(256 * 16 * 16, 128),
            nn.BatchNorm1d(128),
            nn.Tanh(),
            nn.Linear(128, n_classes),
        )

    def forward(self, x):
        return self.head(self.features(x))

    def extra_repr(self):
        return "Xu-Net replication (Xu et al. 2016), not authors' official code"
