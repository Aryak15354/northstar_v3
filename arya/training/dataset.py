"""Memory-mapped token dataset for causal language modelling."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


class TokenDataset(Dataset):
    def __init__(self, tokens_path: str | Path, seq_len: int = 2048):
        self.tokens_path = Path(tokens_path)
        self.seq_len = seq_len
        self.data = np.memmap(self.tokens_path, dtype=np.uint16, mode="r")
        self.n_seqs = max(0, (len(self.data) - 1) // seq_len)

    def __len__(self) -> int:
        return self.n_seqs

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        if idx < 0 or idx >= self.n_seqs:
            raise IndexError(idx)
        start = idx * self.seq_len
        x = torch.from_numpy(self.data[start : start + self.seq_len].astype(np.int64))
        y = torch.from_numpy(self.data[start + 1 : start + self.seq_len + 1].astype(np.int64))
        return x, y

