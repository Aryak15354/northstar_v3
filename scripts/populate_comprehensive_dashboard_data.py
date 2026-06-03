#!/usr/bin/env python3
"""Deprecated sample/dashboard bootstrap entrypoint kept as a safe guardrail."""

from __future__ import annotations

import sys


MESSAGE = (
    "populate_comprehensive_dashboard_data.py is disabled because it used to overwrite "
    "canonical dashboard/state artifacts with synthetic data. Use "
    "scripts/run_complete_v3_system.py --data-only for real refreshes."
)


def main() -> int:
    print(MESSAGE)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
