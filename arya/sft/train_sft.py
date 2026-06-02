"""Supervised fine-tuning loop for Arya."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from arya.inference.quantise import save_arya_checkpoint


@dataclass
class SFTConfig:
    learning_rate: float = 2e-5
    epochs: int = 2
    batch_size: int = 4
    grad_accum: int = 8
    weight_decay: float = 0.01
    lr_schedule: str = "cosine_with_restarts"
    max_grad_norm: float = 1.0
    output_checkpoint: str | None = None
    num_workers: int = 0


def train_sft(model: torch.nn.Module, dataset, cfg: SFTConfig) -> list[dict]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.train()
    loader = DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
    )
    optimiser = torch.optim.AdamW(model.parameters(), lr=cfg.learning_rate, weight_decay=cfg.weight_decay)
    logs: list[dict] = []
    global_step = 0
    for epoch in range(cfg.epochs):
        for input_ids, targets in loader:
            input_ids = input_ids.to(device)
            targets = targets.to(device)
            _, loss = model(input_ids, targets)
            (loss / cfg.grad_accum).backward()
            if (global_step + 1) % cfg.grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.max_grad_norm)
                optimiser.step()
                optimiser.zero_grad(set_to_none=True)
            logs.append({"epoch": epoch, "step": global_step, "loss": float(loss.item())})
            global_step += 1
    if cfg.output_checkpoint:
        save_arya_checkpoint(model, Path(cfg.output_checkpoint))
    return logs
