#!/usr/bin/env python3
"""Reject bare local-package imports in active Northstar code.

The active package must import local modules through ``src.*`` so scripts,
tests, and operator entrypoints resolve the same implementation.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACTIVE_SCRIPTS = (
    "scripts/ns.py",
    "scripts/run_complete_v3_system.py",
    "scripts/northstar_v3_unified.py",
    "scripts/system_status_report.py",
    "scripts/eod_rebalance_with_pnl.py",
    "scripts/force_market_update.py",
)


def _local_packages() -> set[str]:
    return {path.name for path in (ROOT / "src").iterdir() if path.is_dir()}


def _python_files() -> list[Path]:
    files = sorted((ROOT / "src").rglob("*.py"))
    files.extend(ROOT / script for script in ACTIVE_SCRIPTS)
    return [path for path in files if path.exists()]


def main() -> int:
    local_packages = _local_packages()
    violations: list[dict[str, object]] = []

    for path in _python_files():
        rel = str(path.relative_to(ROOT))
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".", 1)[0]
                    if top_level in local_packages and top_level != "src":
                        violations.append({"file": rel, "line": node.lineno, "import": alias.name})
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                top_level = node.module.split(".", 1)[0]
                if top_level in local_packages and top_level != "src":
                    violations.append({"file": rel, "line": node.lineno, "import": node.module})

    print(json.dumps({"check": "active_import_prefixes", "count": len(violations), "violations": violations[:200]}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
