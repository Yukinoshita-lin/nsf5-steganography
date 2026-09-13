"""
gpu/models —— 隐写分析 CNN 结构。

⚠ 重要声明: 本目录下的 Xu-Net / Ye-Net 是依据论文公开描述自行复现的实现,
**不是**原作者发布的官方代码。层配置取自:

    [XU]  Xu, Ni, Shi. "Structural Design of Convolutional Neural Networks
         for Steganalysis." IEEE SPL 23(5), 2016.
    [YE]  Ye, Ni, Yi. "Deep Learning Hierarchical Representations for Image
         Steganalysis." IEEE TIFS 12(11), 2017.

因此绝对数值**不可**与原文报告的 AUC 逐位对比, 只能用于同一评测协议下的
相对比较。训练预算 (8000 crop / 40 epoch) 也远低于原文量级。
"""
from __future__ import annotations

from .xunet import XuNet
from .yenet import YeNet

MODEL_ZOO = {
    "xunet": XuNet,
    "yenet": YeNet,
}

__all__ = ["XuNet", "YeNet", "MODEL_ZOO"]
