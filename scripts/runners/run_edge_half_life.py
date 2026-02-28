#!/usr/bin/env python3
"""Run edge half-life tracker."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script (python scripts/...).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.edge_half_life import EdgeHalfLifeTracker


def main() -> None:
    tracker = EdgeHalfLifeTracker()
    results = tracker.run()
    n = len(results)
    n_ok = sum(1 for r in results.values() if getattr(r, "status", "") == "ok")
    n_ins = sum(1 for r in results.values() if getattr(r, "status", "") != "ok")
    print(f"edge_half_life: strategies={n}, ok={n_ok}, insufficient={n_ins}")
    if results:
        ranked = sorted(
            results.values(),
            key=lambda r: float(getattr(r, "remaining_half_life", 0.0)),
            reverse=True,
        )[:3]
        top = ", ".join(
            f"{r.strategy}:{float(r.remaining_half_life):.1f}d" for r in ranked
        )
        print(f"edge_half_life_top3: {top}")


if __name__ == "__main__":
    main()
