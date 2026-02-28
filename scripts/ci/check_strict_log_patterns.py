#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PATTERNS = [
    re.compile(r"failed but continuing", re.IGNORECASE),
    re.compile(r"\bfallback\b", re.IGNORECASE),
    re.compile(r"\bignored\b", re.IGNORECASE),
    re.compile(r"continue on error", re.IGNORECASE),
    re.compile(r"\bskipping\b", re.IGNORECASE),
    re.compile(r"\bskipped\b", re.IGNORECASE),
    re.compile(r"\bdefaulting\b", re.IGNORECASE),
    re.compile(r"\brecovered\b", re.IGNORECASE),
    re.compile(r"\bretrying\b", re.IGNORECASE),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict log pattern checker")
    parser.add_argument("--log-dir", default="logs/ci")
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    violations = []

    for path in sorted(log_dir.glob("*.log")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pat in PATTERNS:
                if pat.search(line):
                    violations.append(
                        {
                            "file": str(path),
                            "line": lineno,
                            "pattern": pat.pattern,
                            "source": line.strip(),
                        }
                    )

    print(json.dumps({"check": "strict_log_patterns", "violations": violations[:200], "count": len(violations)}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
