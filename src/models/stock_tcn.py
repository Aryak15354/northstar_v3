"""Temporal Convolutional Network for per-stock return prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn
from torch.nn.utils import weight_norm


@dataclass
class TCNConfig:
    n_channels: int = 64
    kernel_size: int = 3
    dilations: tuple[int, ...] = (1, 2, 4, 8, 16, 32)
    dropout: float = 0.1
    n_features: int = 28
    learning_rate: float = 1e-3
    batch_size: int = 512
    epochs: int = 50
    early_stopping_patience: int = 10


DEFAULT_TCN_CONFIG = TCNConfig()


class CausalConv1d(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = weight_norm(
            nn.Conv1d(
                in_channels=in_channels,
                out_channels=out_channels,
                kernel_size=kernel_size,
                dilation=dilation,
                padding=self.padding,
            )
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = self.conv(x)
        if self.padding > 0:
            y = y[..., :-self.padding]
        return y


class TCNBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size, dilation)
        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size, dilation)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.downsample = nn.Conv1d(in_channels, out_channels, kernel_size=1) if in_channels != out_channels else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.downsample(x)
        h = self.conv1(x)
        h = self.relu(h)
        h = self.dropout(h)
        h = self.conv2(h)
        h = self.relu(h)
        h = self.dropout(h)
        return self.relu(h + residual)


class StockTCN(nn.Module):
    """Input: (B, n_features, seq_len). Output: (B, 1)."""

    def __init__(self, config: TCNConfig | dict[str, Any] | None = None):
        super().__init__()
        cfg = config if isinstance(config, TCNConfig) else TCNConfig(**dict(config or {}))
        self.config = cfg

        blocks: list[nn.Module] = []
        in_ch = cfg.n_features
        for d in cfg.dilations:
            blocks.append(
                TCNBlock(
                    in_channels=in_ch,
                    out_channels=cfg.n_channels,
                    kernel_size=cfg.kernel_size,
                    dilation=int(d),
                    dropout=cfg.dropout,
                )
            )
            in_ch = cfg.n_channels
        self.network = nn.Sequential(*blocks)
        self.head = nn.Linear(cfg.n_channels, 1)

        self._reset_parameters()

    def _reset_parameters(self) -> None:
        for module in self.modules():
            if isinstance(module, (nn.Conv1d, nn.Linear)):
                nn.init.kaiming_normal_(module.weight, nonlinearity="relu")
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3:
            raise ValueError(f"Expected input (B, n_features, seq_len), got {tuple(x.shape)}")
        if x.shape[1] != self.config.n_features:
            raise ValueError(f"Expected n_features={self.config.n_features}, got {int(x.shape[1])}")

        h = self.network(x)
        last_step = h[:, :, -1]
        out = self.head(last_step)
        return out.view(x.shape[0], 1)


__all__ = [
    "TCNConfig",
    "DEFAULT_TCN_CONFIG",
    "StockTCN",
]
