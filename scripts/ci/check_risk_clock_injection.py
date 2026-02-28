#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_FILES = [
    ROOT / "src/risk/risk_policy.py",
    ROOT / "src/risk/risk_controller.py",
    ROOT / "src/execution/execution_gateway.py",
]
BANNED_PATTERNS = {
    "datetime.now": re.compile(r"\bdatetime\.now\s*\("),
    "datetime.utcnow": re.compile(r"\bdatetime\.utcnow\s*\("),
    "time.time": re.compile(r"\btime\.time\s*\("),
    "pd.Timestamp.utcnow": re.compile(r"\bpd\.Timestamp\.utcnow\s*\("),
    "pd.Timestamp.now": re.compile(r"\bpd\.Timestamp\.now\s*\("),
}


def main() -> int:
    violations: list[dict] = []

    for path in SCAN_FILES:
        if not path.exists():
            violations.append({"file": str(path.relative_to(ROOT)), "error": "missing"})
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for lineno, line in enumerate(lines, start=1):
            # Allow direct clock call only in SystemClock.now provider implementation.
            if "datetime.now(" in line:
                window = "\n".join(lines[max(0, lineno - 6):lineno])
                if "class SystemClock" in window and "def now" in window:
                    continue
            for token, pattern in BANNED_PATTERNS.items():
                if pattern.search(line):
                    violations.append(
                        {
                            "file": str(path.relative_to(ROOT)),
                            "line": lineno,
                            "token": token,
                            "source": line.strip(),
                        }
                    )

    print(json.dumps({"check": "risk_clock_injection", "violations": violations[:200], "count": len(violations)}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
