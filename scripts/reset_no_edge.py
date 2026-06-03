#!/usr/bin/env python3
"""
Force-reset the NO_EDGE state after stale or invalid suppressions.
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.no_edge_detector import NoEdgeDetector


RESET_REASON = (
    "Manual reset 2026-03-20: stale or invalid NO_EDGE state after coherence repairs "
    "to validation, data contracts, and runtime control surfaces."
)


def main() -> int:
    detector = NoEdgeDetector()
    previous = detector.get_current_state()
    print(f"Current NO_EDGE state: {previous.get('state')} (cap={previous.get('exposure_cap')})")
    result = detector.force_reset(RESET_REASON)
    print(f"Reset at: {datetime.now().isoformat()}")
    print(f"Updated NO_EDGE state: {result.get('state')} (cap={result.get('exposure_cap')})")
    print(f"Reason: {RESET_REASON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
