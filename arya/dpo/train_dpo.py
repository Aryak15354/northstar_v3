"""DPO training loop for Arya."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from arya.dpo.loss import dpo_loss
from arya.inference.quantise import save_arya_checkpoint


@dataclass
class DPOConfig:
    learning_rate: float = 1e-6
    epochs: int = 1
    batch_size: int = 2
    beta: float = 0.1
    max_grad_norm: float = 1.0
    output_checkpoint: str | None = None
    num_workers: int = 0


def train_dpo(policy_model: torch.nn.Module, reference_model: torch.nn.Module, dataset, cfg: DPOConfig) -> list[dict]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy_model.to(device).train()
    reference_model.to(device).eval()
    for param in reference_model.parameters():
        param.requires_grad_(False)

    loader = DataLoader(dataset, batch_size=cfg.batch_size, shuffle=True, num_workers=cfg.num_workers)
    optimiser = torch.optim.AdamW(policy_model.parameters(), lr=cfg.learning_rate)
    logs: list[dict] = []
    global_step = 0
    for epoch in range(cfg.epochs):
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            loss, margin = dpo_loss(
                policy_model,
                reference_model,
                batch["chosen_ids"],
                batch["chosen_mask"],
                batch["rejected_ids"],
                batch["rejected_mask"],
                beta=cfg.beta,
            )
            optimiser.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(policy_model.parameters(), cfg.max_grad_norm)
            optimiser.step()
            logs.append({"epoch": epoch, "step": global_step, "loss": float(loss.item()), "reward_margin": margin})
            global_step += 1
    if cfg.output_checkpoint:
        save_arya_checkpoint(policy_model, Path(cfg.output_checkpoint))
    return logs

