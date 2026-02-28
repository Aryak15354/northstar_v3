"""Lightweight TFT-style transformer building blocks for research models."""

from __future__ import annotations

from typing import Dict

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - optional dependency in some envs
    torch = None
    nn = None


if nn is not None:

    class TimeSeriesTransformerNet(nn.Module):
        """Compact TFT-style encoder with static/known/observed pathways."""

        def __init__(
            self,
            observed_dim: int,
            known_dim: int = 0,
            static_dim: int = 0,
            d_model: int = 64,
            nhead: int = 4,
            num_layers: int = 2,
            dim_feedforward: int = 128,
            dropout: float = 0.1,
            max_len: int = 512,
            n_tickers: int = 0,
            n_sectors: int = 0,
            embed_dim: int = 16,
        ) -> None:
            super().__init__()
            self.observed_proj = nn.Linear(int(observed_dim), int(d_model))
            self.known_proj = nn.Linear(int(known_dim), int(d_model)) if int(known_dim) > 0 else None
            self.static_proj = nn.Linear(int(static_dim), int(d_model)) if int(static_dim) > 0 else None
            self.ticker_emb = (
                nn.Embedding(int(max(1, n_tickers)), int(embed_dim)) if int(n_tickers) > 0 else None
            )
            self.sector_emb = (
                nn.Embedding(int(max(1, n_sectors)), int(embed_dim)) if int(n_sectors) > 0 else None
            )
            self.embed_proj = (
                nn.Linear(int(embed_dim), int(d_model))
                if (self.ticker_emb is not None or self.sector_emb is not None)
                else None
            )
            self.pos_embedding = nn.Embedding(int(max_len), int(d_model))
            enc_layer = nn.TransformerEncoderLayer(
                d_model=int(d_model),
                nhead=int(nhead),
                dim_feedforward=int(dim_feedforward),
                dropout=float(dropout),
                batch_first=True,
                activation="gelu",
            )
            self.encoder = nn.TransformerEncoder(enc_layer, num_layers=int(num_layers))
            self.norm = nn.LayerNorm(int(d_model))
            self.dropout = nn.Dropout(float(dropout))

            self.return_head = nn.Linear(int(d_model), 1)
            self.direction_head = nn.Linear(int(d_model), 1)
            self.risk_head = nn.Linear(int(d_model), 1)

        def forward(
            self,
            observed: torch.Tensor,
            known: torch.Tensor | None = None,
            static: torch.Tensor | None = None,
            ticker_id: torch.Tensor | None = None,
            sector_id: torch.Tensor | None = None,
        ) -> Dict[str, torch.Tensor]:
            batch_size, seq_len, _ = observed.shape
            positions = torch.arange(seq_len, device=observed.device).unsqueeze(0).expand(batch_size, seq_len)
            h = self.observed_proj(observed)
            if self.known_proj is not None and known is not None and known.shape[-1] > 0:
                h = h + self.known_proj(known)
            h = h + self.pos_embedding(positions)
            h = self.encoder(h)
            z = self.dropout(self.norm(h[:, -1, :]))
            if self.static_proj is not None and static is not None and static.shape[-1] > 0:
                z = z + self.static_proj(static)
            if self.embed_proj is not None:
                emb_terms = []
                if self.ticker_emb is not None and ticker_id is not None:
                    emb_terms.append(self.ticker_emb(ticker_id))
                if self.sector_emb is not None and sector_id is not None:
                    emb_terms.append(self.sector_emb(sector_id))
                if emb_terms:
                    emb = emb_terms[0]
                    for e in emb_terms[1:]:
                        emb = emb + e
                    z = z + self.embed_proj(emb)
            return {
                "return_pred": self.return_head(z).squeeze(-1),
                "direction_logit": self.direction_head(z).squeeze(-1),
                "risk_logit": self.risk_head(z).squeeze(-1),
            }

else:

    class TimeSeriesTransformerNet:  # pragma: no cover - used only when torch missing
        def __init__(self, *args, **kwargs):
            raise RuntimeError("torch is unavailable; TimeSeriesTransformerNet cannot be constructed")
