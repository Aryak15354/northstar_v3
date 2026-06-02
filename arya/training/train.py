"""Fault-tolerant pretraining loop for Arya."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Iterable

import torch
from torch.utils.data import DataLoader

from arya.training.config import TrainingConfig
from arya.training.dataset import TokenDataset


def cosine_lr(step: int, cfg: TrainingConfig) -> float:
    if step < cfg.warmup_steps:
        return cfg.lr_max * max(step, 1) / max(cfg.warmup_steps, 1)
    progress = (step - cfg.warmup_steps) / max(cfg.total_steps - cfg.warmup_steps, 1)
    progress = min(max(progress, 0.0), 1.0)
    return cfg.lr_min + 0.5 * (cfg.lr_max - cfg.lr_min) * (1 + math.cos(math.pi * progress))


def save_checkpoint(
    model: torch.nn.Module,
    optimiser: torch.optim.Optimizer,
    step: int,
    val_loss: float,
    cfg: TrainingConfig,
) -> Path:
    checkpoint_dir = Path(cfg.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    path = checkpoint_dir / f"step_{step:07d}.pt"
    torch.save(
        {
            "step": step,
            "val_loss": val_loss,
            "model": model.state_dict(),
            "optimiser": optimiser.state_dict(),
            "config": cfg.__dict__,
        },
        path,
    )

    checkpoints = sorted(checkpoint_dir.glob("step_*.pt"))
    for old in checkpoints[: -cfg.keep_last_checkpoints]:
        old.unlink()
    return path


def latest_checkpoint(checkpoint_dir: str | Path) -> Path | None:
    checkpoints = sorted(Path(checkpoint_dir).glob("step_*.pt"))
    return checkpoints[-1] if checkpoints else None


def train(model: torch.nn.Module, cfg: TrainingConfig) -> list[dict]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    if cfg.use_bfloat16 and device.type == "cuda":
        model = model.bfloat16()

    optimiser = torch.optim.AdamW(
        model.parameters(),
        lr=cfg.lr_max,
        weight_decay=cfg.weight_decay,
        betas=(0.9, 0.95),
    )

    start_step = _resume_if_available(model, optimiser, cfg, device)
    train_dl = DataLoader(
        TokenDataset(cfg.tokens_train, cfg.seq_len),
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        pin_memory=device.type == "cuda",
    )
    val_dl = DataLoader(
        TokenDataset(cfg.tokens_val, cfg.seq_len),
        batch_size=cfg.batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        pin_memory=device.type == "cuda",
    )

    logs: list[dict] = []
    optimiser.zero_grad(set_to_none=True)
    t0 = time.time()

    for step, (x, y) in enumerate(_infinite_loader(train_dl), start=start_step):
        if step >= cfg.total_steps:
            break
        lr = cosine_lr(step, cfg)
        for group in optimiser.param_groups:
            group["lr"] = lr

        x = x.to(device)
        y = y.to(device)
        with _autocast_context(device, cfg):
            _, loss = model(x, y)
            scaled_loss = loss / cfg.grad_accum
        scaled_loss.backward()

        if (step + 1) % cfg.grad_accum == 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
            optimiser.step()
            optimiser.zero_grad(set_to_none=True)

        if step % cfg.log_every == 0:
            logs.append({"step": step, "loss": float(loss.item()), "lr": lr, "elapsed_s": time.time() - t0})

        if step % cfg.eval_every == 0:
            val_loss = evaluate(model, val_dl, device, cfg)
            logs.append({"step": step, "val_loss": val_loss, "ppl": math.exp(min(val_loss, 20.0))})

        if step > 0 and step % cfg.checkpoint_every == 0:
            save_checkpoint(model, optimiser, step, logs[-1].get("val_loss", float("nan")), cfg)

    _write_log(Path(cfg.checkpoint_dir) / "log.jsonl", logs)
    return logs


@torch.no_grad()
def evaluate(
    model: torch.nn.Module,
    val_loader: Iterable,
    device: torch.device,
    cfg: TrainingConfig,
    n_batches: int = 50,
) -> float:
    model.eval()
    total = 0.0
    count = 0
    for i, (x, y) in enumerate(val_loader):
        if i >= n_batches:
            break
        x = x.to(device)
        y = y.to(device)
        with _autocast_context(device, cfg):
            _, loss = model(x, y)
        total += float(loss.item())
        count += 1
    model.train()
    return total / max(count, 1)


def _resume_if_available(
    model: torch.nn.Module,
    optimiser: torch.optim.Optimizer,
    cfg: TrainingConfig,
    device: torch.device,
) -> int:
    checkpoint = latest_checkpoint(cfg.checkpoint_dir)
    if checkpoint is None:
        return 0
    payload = torch.load(checkpoint, map_location=device)
    model.load_state_dict(payload["model"])
    optimiser.load_state_dict(payload["optimiser"])
    return int(payload["step"]) + 1


def _infinite_loader(loader: Iterable) -> Iterable:
    while True:
        for batch in loader:
            yield batch


def _autocast_context(device: torch.device, cfg: TrainingConfig):
    if device.type == "cuda" and cfg.use_bfloat16:
        return torch.autocast(device_type="cuda", dtype=torch.bfloat16)
    return torch.autocast(device_type="cpu", enabled=False)


def _write_log(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

