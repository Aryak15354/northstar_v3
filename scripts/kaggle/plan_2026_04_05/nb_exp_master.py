#!/usr/bin/env python3
"""Single master notebook/script entrypoint for the compendium experiment suite."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_05.run_plan_suite import run_suite


def run_master_experiments(
    *,
    export_dir: str | Path,
    output_root: str | Path,
    exp_ids: list[str] | None = None,
    profile: str = "full",
    max_splits: int | None = None,
    version: str = "v1",
) -> dict[str, Any]:
    return run_suite(
        export_dir=Path(export_dir),
        output_root=Path(output_root),
        exp_ids=exp_ids,
        profile=profile,
        max_splits=max_splits,
        version=version,
    )
