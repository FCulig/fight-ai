"""Temporal CNN over pose windows (plan/04-stage2-model.md step 2).

Deliberately small: a few hundred labelled strikes cannot support an ST-GCN's
parameter count without memorising the one fight that supplies most of them.
Input is (B, IN_CHANNELS, T); first differences are appended inside forward()
so velocity — the main signal a strike carries — is explicit.
"""

import torch
from torch import nn

from .config import CLASSES, IN_CHANNELS, TARGETS


class _Block(nn.Module):
    def __init__(self, ch: int, dilation: int, dropout: float):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(ch, ch, 5, padding=2 * dilation, dilation=dilation),
            nn.BatchNorm1d(ch),
            nn.GELU(),
            nn.Dropout(dropout),
        )

    def forward(self, x):
        return x + self.net(x)


class ActionNet(nn.Module):
    def __init__(self, hidden: int = 96, dropout: float = 0.3):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(IN_CHANNELS * 2, hidden, 1),
            nn.BatchNorm1d(hidden),
            nn.GELU(),
        )
        self.blocks = nn.Sequential(*[_Block(hidden, d, dropout) for d in (1, 2, 4)])
        self.family_head = nn.Linear(hidden * 2, len(CLASSES))
        self.target_head = nn.Linear(hidden * 2, len(TARGETS))
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        dx = torch.diff(x, dim=2, prepend=x[:, :, :1])
        h = self.blocks(self.stem(torch.cat([x, dx], dim=1)))
        # The strike is at the centre, but pooling over the whole window lets
        # wind-up and recoil contribute; centre sample + mean keeps both.
        centre = h[:, :, h.shape[2] // 2]
        z = self.drop(torch.cat([centre, h.mean(dim=2)], dim=1))
        return self.family_head(z), self.target_head(z)
