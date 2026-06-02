"""Training configuration for Arya pretraining."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrainingConfig:
    tokens_train: str = "/kaggle/input/arya-corpus/train.bin"
    tokens_val: str = "/kaggle/input/arya-corpus/val.bin"
    checkpoint_dir: str = "/kaggle/working/checkpoints"
    run_name: str = "arya-1b-run1"

    seq_len: int = 1024
    batch_size: int = 8
    grad_accum: int = 16
    lr_max: float = 3e-4
    lr_min: float = 3e-5
    weight_decay: float = 0.1
    grad_clip: float = 1.0
    warmup_steps: int = 2_000
    total_steps: int = 100_000

    checkpoint_every: int = 500
    eval_every: int = 250
    log_every: int = 50
    keep_last_checkpoints: int = 3
    num_workers: int = 2
    use_bfloat16: bool = True

    @classmethod
    def local_smoke(cls, checkpoint_dir: str, tokens_train: str, tokens_val: str) -> "TrainingConfig":
        return cls(
            tokens_train=tokens_train,
            tokens_val=tokens_val,
            checkpoint_dir=checkpoint_dir,
            run_name="arya-local-smoke",
            seq_len=8,
            batch_size=2,
            grad_accum=1,
            lr_max=1e-3,
            lr_min=1e-4,
            warmup_steps=2,
            total_steps=4,
            checkpoint_every=2,
            eval_every=2,
            log_every=1,
            num_workers=0,
            use_bfloat16=False,
        )

