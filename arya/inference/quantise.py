"""Checkpoint loading and optional quantised model loading for Arya."""

from __future__ import annotations

from pathlib import Path

import torch

from arya.model.config import AryaConfig
from arya.model.transformer import Arya


def save_arya_checkpoint(model: Arya, path: str | Path) -> Path:
    checkpoint_path = Path(path)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": model.cfg.to_dict(), "model": model.state_dict()}, checkpoint_path)
    return checkpoint_path


def load_arya_checkpoint(path: str | Path, device: str | torch.device = "cpu") -> Arya:
    checkpoint_path = Path(path)
    payload = torch.load(checkpoint_path, map_location=device)
    cfg = AryaConfig.from_dict(payload["config"])
    model = Arya(cfg)
    model.load_state_dict(payload["model"])
    model.to(device)
    model.eval()
    return model


def load_quantised_arya(checkpoint_path: str | Path, device: str | torch.device = "cpu"):
    """Load Arya for inference.

    Local `.pt` checkpoints are loaded directly. Directory checkpoints can be
    passed through Hugging Face + bitsandbytes when available, which is the path
    intended for large Kaggle-trained artifacts.
    """

    path = Path(checkpoint_path)
    if path.is_file():
        return load_arya_checkpoint(path, device=device)

    try:
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError(
            "Directory checkpoint loading requires transformers and bitsandbytes. "
            "Use a local .pt Arya checkpoint for lightweight tests."
        ) from exc

    try:
        import bitsandbytes  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("4-bit quantised loading requires bitsandbytes.") from exc

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )
    return AutoModelForCausalLM.from_pretrained(
        str(path),
        quantization_config=bnb_config,
        device_map=device,
    )

