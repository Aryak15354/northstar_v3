#!/usr/bin/env python3
"""Validate Northstar V3 canonical artifact contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data.artifact_contracts import validate_all_contracts  # noqa: E402


def main() -> int:
    results = validate_all_contracts(project_root=PROJECT_ROOT)
    payload = [
        {
            "name": result.name,
            "ok": result.ok,
            "rows": result.rows,
            "latest": result.latest,
            "path": result.path,
            "problems": result.problems,
        }
        for result in results
    ]
    print(json.dumps(payload, indent=2))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
