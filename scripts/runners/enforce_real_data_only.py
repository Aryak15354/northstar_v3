#!/usr/bin/env python3
"""
Enforce real-data-only policy on core production modules.

This scanner intentionally targets execution-critical modules and blocks:
- random data generators (np.random / random.*)
- mock/synthetic helper functions in production paths
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]

STRICT_FILES = [
    # NOTE: two paths here drifted (root script moved to scripts/, the narrative
    # engine was renamed) and the resulting "missing strict file" hard-failed the
    # entire daily canonical_rebuild (refresh_v3_artifacts exit 1) even though the
    # core artifacts refreshed fine. Corrected to current locations 2026-07.
    "scripts/run_complete_v3_system.py",
    "scripts/runners/refresh_v3_artifacts.py",
    "scripts/runners/run_institutional_hardening.py",
    "src/api/server.py",
    "src/backtesting/backtest_engine.py",
    "src/live/daily_shadow_trader.py",
    "src/risk/emergency_brake.py",
    "src/intelligence/market_brain/market_tensor.py",
    "src/intelligence/narrative_intelligence_engine.py",
    "src/intelligence/narrative_engine.py",
    "src/intelligence/strategy_beliefs.py",
    "src/scoring/northstar_model.py",
    "src/validation/universe_manager.py",
    "src/validation/institutional_hardening.py",
    "src/validation/multi_timeline_walk_forward_engine.py",
    "src/validation/enhanced_backtesting_engine.py",
    "src/validation/enhanced_reality_check_engine.py",
]


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _contains_mock_name(name: str) -> bool:
    n = name.lower()
    return ("mock" in n) or ("synthetic" in n)


def scan_file(path: Path) -> List[Tuple[int, str]]:
    findings: List[Tuple[int, str]] = []
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except Exception as e:
        findings.append((1, f"parse_error: {e}"))
        return findings

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _contains_mock_name(node.name):
                findings.append((node.lineno, f"forbidden function name: {node.name}"))

        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            lname = name.lower()
            if lname.startswith("np.random") or lname.startswith("random."):
                findings.append((node.lineno, f"forbidden random generator call: {name}"))
            if "create_mock" in lname or "synthetic" in lname:
                findings.append((node.lineno, f"forbidden mock/synthetic call: {name}"))

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and _contains_mock_name(target.id):
                    findings.append((node.lineno, f"forbidden mock/synthetic variable: {target.id}"))

    return findings


def main() -> int:
    failures = []
    for rel in STRICT_FILES:
        p = PROJECT_ROOT / rel
        if not p.exists():
            failures.append((rel, 1, "missing strict file"))
            continue
        for line, msg in scan_file(p):
            failures.append((rel, line, msg))

    if failures:
        print("❌ Real-data-only enforcement failed:")
        for rel, line, msg in failures:
            print(f"  - {rel}:{line}: {msg}")
        return 1

    print("✅ Real-data-only enforcement passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
