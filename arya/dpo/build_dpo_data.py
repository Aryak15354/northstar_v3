"""Helpers for building Arya DPO preference pairs."""

from __future__ import annotations

import json
from pathlib import Path


def build_overconfidence_rejection(chosen_example: dict, wrong_action: str = "REDUCE_GROSS") -> dict[str, str]:
    """Create a simple rejected response from a labelled SFT-style example."""

    response = json.loads(chosen_example["response"])
    rejected = dict(response)
    rejected["portfolio_action"] = wrong_action
    rejected["confidence"] = 0.95
    rejected.setdefault("rationale", "Overconfident action without sufficient evidence.")
    return {
        "prompt": chosen_example["prompt"],
        "chosen": chosen_example["response"],
        "rejected": json.dumps(rejected, ensure_ascii=False, sort_keys=True),
    }


def write_pairs(pairs: list[dict[str, str]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pairs, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

