#!/usr/bin/env python3
"""Run roadmap preflight checks for one phase or all phases."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.research_roadmap_gate import run_preflight


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Northstar V3 roadmap preflight checks")
    ap.add_argument("--base-config", default="config/research_policy.yaml")
    ap.add_argument("--output-root", default="data/results/research/reports/roadmap")
    ap.add_argument("--phase", default="all", choices=["all", "phase1", "phase2", "phase3", "phase4"])
    args = ap.parse_args()

    repo_root = REPO_ROOT
    base_config = (repo_root / str(args.base_config)).resolve()
    out_root = (repo_root / str(args.output_root)).resolve()

    phases = [str(args.phase)] if str(args.phase) != "all" else ["phase1", "phase2", "phase3", "phase4"]
    rc = 0
    for phase in phases:
        out_dir = out_root / phase
        code = run_preflight(
            repo_root=repo_root,
            base_config=base_config,
            output_dir=out_dir,
            phase=phase,
        )
        rc = max(rc, int(code))
        print(f"[roadmap-preflight] phase={phase} status_code={code} out_dir={out_dir}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
