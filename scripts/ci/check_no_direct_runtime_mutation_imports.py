#!/usr/bin/env python3
"""Static guard: prevent legacy modules from importing PRS mutation-layer internals."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BLOCKED_IMPORT_PATTERNS = [
    r"from\s+src\.runtime\.state\s+import",
    r"from\s+src\.runtime\.storage\s+import",
    r"from\s+src\.runtime\.portfolio_runtime_service\s+import\s+PortfolioRuntimeService",
]

BLOCKED_RUNTIME_DB_PATTERNS = [
    r"sqlite3\.connect\([^)]*runtime[^)]*\.db",
    r"sqlite3\.connect\([^)]*portfolio_runtime[^)]*\.db",
]

LEGACY_FALLBACK_PATTERNS = [
    r"NORTHSTAR_PRS_.*_ENABLED",
    r"legacy fallback",
]

SCAN_DIRS = [
    PROJECT_ROOT / "src/backtesting",
    PROJECT_ROOT / "src/live",
    PROJECT_ROOT / "src/execution",
    PROJECT_ROOT / "src/validation",
    PROJECT_ROOT / "scripts",
]

ALLOWLIST = {
    str(PROJECT_ROOT / "scripts/run_integrated_options_paper_engine.py"),
    str(PROJECT_ROOT / "scripts/run_truth_drift_monitor.py"),
}

FALLBACK_ENFORCEMENT_FILES = {
    str(PROJECT_ROOT / "src/backtesting/backtest_engine.py"),
    str(PROJECT_ROOT / "src/execution/shadow_fund_engine.py"),
    str(PROJECT_ROOT / "src/validation/advanced_shadow_executor.py"),
    str(PROJECT_ROOT / "src/live/daily_shadow_trader.py"),
}


def main() -> int:
    failures: list[str] = []
    for root in SCAN_DIRS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            p = str(path)
            if p in ALLOWLIST:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except Exception:
                continue
            for patt in BLOCKED_IMPORT_PATTERNS:
                if re.search(patt, content):
                    failures.append(f"{path}: blocked import pattern `{patt}`")
            for patt in BLOCKED_RUNTIME_DB_PATTERNS:
                if re.search(patt, content, flags=re.IGNORECASE):
                    failures.append(f"{path}: blocked direct runtime sqlite usage `{patt}`")
            if p in FALLBACK_ENFORCEMENT_FILES:
                for patt in LEGACY_FALLBACK_PATTERNS:
                    if re.search(patt, content, flags=re.IGNORECASE):
                        failures.append(f"{path}: legacy PRS fallback pattern `{patt}` must be removed")

    if failures:
        print("❌ Direct runtime mutation imports found:")
        for f in failures:
            print(f" - {f}")
        return 1

    print("✅ No direct runtime mutation imports found in legacy paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
