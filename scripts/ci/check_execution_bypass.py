#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTRY_FILES = [
    ROOT / "scripts" / "run_complete_v3_system.py",
]
SCAN_DIRS = [ROOT / "src/execution"]
FORBIDDEN_TOKENS = [
    "OptionsRiskValidator(",
    "SurvivalRulesEngine(",
    "CapitalScalingEngine(",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def main() -> int:
    violations = []

    gateway_path = ROOT / "src/execution/execution_gateway.py"
    gateway_src = _read(gateway_path)
    if not gateway_src:
        violations.append({"file": str(gateway_path.relative_to(ROOT)), "error": "missing_execution_gateway"})
    else:
        required = ["RiskDecision", "decision.allowed", "Trading is frozen", "_risk_state_lock"]
        for token in required:
            if token not in gateway_src:
                violations.append({"file": str(gateway_path.relative_to(ROOT)), "error": f"missing_required_token:{token}"})

    for path in ENTRY_FILES:
        src = _read(path)
        for token in FORBIDDEN_TOKENS:
            if token in src:
                violations.append({"file": str(path.relative_to(ROOT)), "error": f"forbidden_direct_risk_call:{token}"})

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for path in sorted(scan_dir.rglob("*.py")):
            src = _read(path)
            for token in FORBIDDEN_TOKENS:
                if token in src:
                    violations.append({"file": str(path.relative_to(ROOT)), "error": f"forbidden_direct_risk_call:{token}"})

    print(json.dumps({"check": "execution_bypass", "violations": violations[:200], "count": len(violations)}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
