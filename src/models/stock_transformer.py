"""Transformer encoder for per-stock return prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import nn


@dataclass
class TransformerConfig:
    d_model: int = 64
    n_heads: int = 4
    n_layers: int = 4
    d_ff: int = 256
    dropout: float = 0.1
    seq_len: int = 252
    n_features: int = 28
    learning_rate: float = 1e-4
    batch_size: int = 512
    epochs: int = 50
    early_stopping_patience: int = 10


DEFAULT_TRANSFORMER_CONFIG = TransformerConfig()


class StockTransformer(nn.Module):
    """Input: (B, seq_len, n_features). Output: (B, 1)."""

    def __init__(self, config: TransformerConfig | dict[str, Any] | None = None):
        super().__init__()
        cfg = config if isinstance(config, TransformerConfig) else TransformerConfig(**dict(config or {}))
        self.config = cfg

        self.input_proj = nn.Linear(cfg.n_features, cfg.d_model)
        self.pos_embedding = nn.Parameter(torch.zeros(1, cfg.seq_len, cfg.d_model))
        self.dropout = nn.Dropout(cfg.dropout)

        enc_layer = nn.TransformerEncoderLayer(
            d_model=cfg.d_model,
            nhead=cfg.n_heads,
            dim_feedforward=cfg.d_ff,
            dropout=cfg.dropout,
            batch_first=True,
            activation="gelu",
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=cfg.n_layers)

        self.head = nn.Sequential(
            nn.Linear(cfg.d_model, 32),
            nn.GELU(),
            nn.Dropout(cfg.dropout),
            nn.Linear(32, 1),
        )

        self._reset_parameters()

    def _reset_parameters(self) -> None:
        nn.init.normal_(self.pos_embedding, mean=0.0, std=0.02)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    @staticmethod
    def _causal_mask(seq_len: int, device: torch.device) -> torch.Tensor:
        return torch.triu(torch.ones(seq_len, seq_len, dtype=torch.bool, device=device), diagonal=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3:
            raise ValueError(f"Expected input (B, seq_len, n_features), got {tuple(x.shape)}")
        if x.shape[-1] != self.config.n_features:
            raise ValueError(
                f"Expected n_features={self.config.n_features}, got {int(x.shape[-1])}"
            )

        b, seq_len, _ = x.shape
        h = self.input_proj(x)
        h = h + self.pos_embedding[:, :seq_len, :]
        h = self.dropout(h)

        mask = self._causal_mask(seq_len=seq_len, device=x.device)
        h = self.encoder(h, mask=mask)

        pooled = h.mean(dim=1)
        out = self.head(pooled)
        return out.view(b, 1)


__all__ = [
    "TransformerConfig",
    "DEFAULT_TRANSFORMER_CONFIG",
    "StockTransformer",
]
