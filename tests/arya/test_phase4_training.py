import numpy as np
import torch
import torch.nn as nn

from arya.training.config import TrainingConfig
from arya.training.dataset import TokenDataset
from arya.training.train import cosine_lr, save_checkpoint


def test_phase4_token_dataset_memmap(tmp_path):
    path = tmp_path / "tokens.bin"
    np.arange(40, dtype=np.uint16).tofile(path)
    ds = TokenDataset(path, seq_len=8)
    assert len(ds) == 4
    x, y = ds[0]
    assert x.tolist() == list(range(8))
    assert y.tolist() == list(range(1, 9))


def test_phase4_cosine_lr_and_checkpoint_retention(tmp_path):
    cfg = TrainingConfig.local_smoke(
        checkpoint_dir=str(tmp_path / "ckpts"),
        tokens_train="train.bin",
        tokens_val="val.bin",
    )
    assert 0 < cosine_lr(0, cfg) <= cfg.lr_max
    assert cfg.lr_min <= cosine_lr(cfg.total_steps, cfg) <= cfg.lr_max

    model = nn.Linear(2, 2)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    for step in range(5):
        save_checkpoint(model, opt, step, val_loss=1.0, cfg=cfg)
    kept = sorted((tmp_path / "ckpts").glob("step_*.pt"))
    assert len(kept) == cfg.keep_last_checkpoints
    assert kept[-1].name == "step_0000004.pt"

