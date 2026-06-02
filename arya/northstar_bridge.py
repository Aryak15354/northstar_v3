"""Northstar integration bridge for Arya."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from arya.inference.quantise import load_quantised_arya
from arya.inference.runtime import AryaRuntime


ARYA_CHECKPOINT_ENV = "ARYA_CHECKPOINT_PATH"
ARYA_TOKENISER_ENV = "ARYA_TOKENISER_PATH"


@lru_cache(maxsize=1)
def get_arya_runtime() -> AryaRuntime:
    checkpoint = Path(os.environ.get(ARYA_CHECKPOINT_ENV, "checkpoints/arya-instruct.pt"))
    tokeniser = Path(os.environ.get(ARYA_TOKENISER_ENV, "arya-tokeniser.json"))

    if not checkpoint.exists():
        raise FileNotFoundError(
            f"Arya checkpoint not found: {checkpoint}. "
            f"Set {ARYA_CHECKPOINT_ENV} to a .pt checkpoint or model directory."
        )
    if not tokeniser.exists():
        raise FileNotFoundError(
            f"Arya tokeniser not found: {tokeniser}. Set {ARYA_TOKENISER_ENV}."
        )

    device = os.environ.get("ARYA_DEVICE", "cuda" if _cuda_available() else "cpu")
    model = load_quantised_arya(checkpoint, device=device)
    return AryaRuntime(model, tokeniser, device=device)


def _cuda_available() -> bool:
    try:
        import torch

        return torch.cuda.is_available()
    except Exception:
        return False

