#!/usr/bin/env python3
"""Deprecated sample-state writer kept as a safe guardrail."""

from __future__ import annotations

import sys


MESSAGE = (
    "populate_dashboard_state.py is disabled because sample payloads must not overwrite "
    "data/state/unified_state.json. Use scripts/run_complete_v3_system.py --data-only "
    "or scripts/populate_real_dashboard_data.py instead."
)


def main() -> int:
    print(MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
