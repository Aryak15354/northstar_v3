"""Builders for Arya instruction-tuning examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ARYA_SYSTEM_PROMPT = (
    "You are Arya, the Northstar V3 intelligence engine for Indian financial markets.\n"
    "Analyse market events and portfolio state and return the requested structured output."
)


def build_nil_example(event: dict[str, Any], state_summary: str, response: dict[str, Any]) -> dict[str, str]:
    prompt = (
        f"<|system|>\n{ARYA_SYSTEM_PROMPT}\n"
        "<|user|>\n<|nil_event|>\n"
        f"{json.dumps(event, ensure_ascii=False, sort_keys=True)}\n"
        f"PORTFOLIO STATE: {state_summary}\n"
        "<|assistant|>\n<|nil_action|>\n"
    )
    return {"prompt": prompt, "response": json.dumps(response, ensure_ascii=False, sort_keys=True)}


def write_examples(examples: list[dict[str, str]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(examples, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

