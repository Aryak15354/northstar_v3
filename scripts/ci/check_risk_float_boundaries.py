#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ROOT / "src/risk/risk_policy.py",
    ROOT / "src/risk/risk_controller.py",
    ROOT / "src/execution/execution_gateway.py",
]
COMPARE_RE = re.compile(r"(risk|drawdown|cap).*[<>]=?.*(risk|drawdown|cap)", re.IGNORECASE)


def main() -> int:
    violations = []
    checks = {}

    for path in FILES:
        rel = str(path.relative_to(ROOT))
        if not path.exists():
            violations.append({"file": rel, "error": "missing"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        checks[rel] = {
            "contains_epsilon": "epsilon" in text.lower() or "EPSILON" in text,
            "line_count": len(text.splitlines()),
        }
        for lineno, line in enumerate(text.splitlines(), start=1):
            if COMPARE_RE.search(line) and "eps" not in line.lower():
                violations.append(
                    {
                        "file": rel,
                        "line": lineno,
                        "source": line.strip(),
                        "error": "comparison_without_epsilon_context",
                    }
                )

    if not checks.get("src/risk/risk_policy.py", {}).get("contains_epsilon", False):
        violations.append({"file": "src/risk/risk_policy.py", "error": "missing_epsilon_definition"})

    print(json.dumps({"check": "risk_float_boundaries", "checks": checks, "violations": violations[:200], "count": len(violations)}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
