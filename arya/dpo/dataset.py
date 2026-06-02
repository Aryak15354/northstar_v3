"""Preference-pair dataset for Arya DPO."""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset
from tokenizers import Tokenizer


class DPODataset(Dataset):
    """Loads JSON examples with prompt, chosen, and rejected fields."""

    def __init__(self, pairs_path: str | Path, tokeniser_path: str | Path, max_len: int = 1024):
        self.pairs = json.loads(Path(pairs_path).read_text(encoding="utf-8"))
        self.tokeniser = Tokenizer.from_file(str(tokeniser_path))
        self.max_len = max_len
        self.pad_id = self._required_token_id("<|pad|>")
        self.eos_id = self._required_token_id("<|eos|>")

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        pair = self.pairs[idx]
        chosen = self._encode(pair["prompt"] + pair["chosen"] + "<|eos|>")
        rejected = self._encode(pair["prompt"] + pair["rejected"] + "<|eos|>")
        return {
            "chosen_ids": chosen[0],
            "chosen_mask": chosen[1],
            "rejected_ids": rejected[0],
            "rejected_mask": rejected[1],
        }

    def _encode(self, text: str) -> tuple[torch.Tensor, torch.Tensor]:
        ids = self.tokeniser.encode(text).ids[: self.max_len]
        mask = [1] * len(ids)
        pad = self.max_len - len(ids)
        if pad > 0:
            ids.extend([self.pad_id] * pad)
            mask.extend([0] * pad)
        return torch.tensor(ids, dtype=torch.long), torch.tensor(mask, dtype=torch.long)

    def _required_token_id(self, token: str) -> int:
        token_id = self.tokeniser.token_to_id(token)
        if token_id is None:
            raise ValueError(f"Tokeniser missing required token {token!r}.")
        return token_id

