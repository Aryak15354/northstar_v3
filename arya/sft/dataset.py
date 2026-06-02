"""Dataset for Arya supervised fine-tuning."""

from __future__ import annotations

import json
from pathlib import Path

import torch
from torch.utils.data import Dataset
from tokenizers import Tokenizer


class SFTDataset(Dataset):
    def __init__(self, examples_path: str | Path, tokeniser_path: str | Path, max_len: int = 1024):
        self.examples = json.loads(Path(examples_path).read_text(encoding="utf-8"))
        self.tokeniser = Tokenizer.from_file(str(tokeniser_path))
        self.max_len = max_len
        self.assistant_id = self._required_token_id("<|assistant|>")
        self.pad_id = self._required_token_id("<|pad|>")
        self.eos_id = self._required_token_id("<|eos|>")

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        example = self.examples[idx]
        full = example["prompt"] + example["response"] + "<|eos|>"
        ids = self.tokeniser.encode(full).ids[: self.max_len]
        input_ids = torch.tensor(ids, dtype=torch.long)
        target = input_ids.clone()

        assistant_positions = (input_ids == self.assistant_id).nonzero(as_tuple=True)[0]
        if len(assistant_positions):
            target[: assistant_positions[-1].item() + 1] = -100
        else:
            target[:] = -100

        pad = self.max_len - len(input_ids)
        if pad > 0:
            input_ids = torch.cat([input_ids, torch.full((pad,), self.pad_id, dtype=torch.long)])
            target = torch.cat([target, torch.full((pad,), -100, dtype=torch.long)])
        if not (target != -100).any():
            raise ValueError(
                "SFT example has no assistant response tokens after truncation. "
                "Increase max_len or shorten the prompt."
            )
        return input_ids, target

    def _required_token_id(self, token: str) -> int:
        token_id = self.tokeniser.token_to_id(token)
        if token_id is None:
            raise ValueError(f"Tokeniser missing required token {token!r}.")
        return token_id
