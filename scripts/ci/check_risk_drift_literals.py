#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = [ROOT / "src", ROOT / "scripts", ROOT / "config", ROOT / "run.py", ROOT / "run_complete_v3_system.py"]
EXTENSIONS = {".py", ".yaml", ".yml", ".json", ".toml"}
ALLOWLIST = {
    "src/risk/risk_policy.py",
    "config/risk.yaml",
    "config/risk.yml",
    "config/risk.json",
}
BASELINE_DEFAULT = ROOT / "audit/risk_drift_baseline.json"
PATTERNS = {
    "portfolio_risk_cap_pct_symbol": re.compile(r"\bportfolio_risk_cap_pct\b"),
    "literal_0_02": re.compile(r"(?<![0-9])0\.02(?![0-9])"),
    "literal_0_04": re.compile(r"(?<![0-9])0\.04(?![0-9])"),
    "equity_times_literal": re.compile(r"\b(?:net_)?equity\s*\*\s*0\.\d+"),
    "capital_times_literal": re.compile(r"\bbase_capital\s*\*\s*0\.\d+"),
}


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for item in SCAN_DIRS:
        if item.is_file() and item.suffix in EXTENSIONS:
            out.append(item)
            continue
        if item.is_dir():
            for path in item.rglob("*"):
                if not path.is_file() or path.suffix not in EXTENSIONS:
                    continue
                rel = str(path.relative_to(ROOT))
                if rel.startswith(("archive/", "tests/", "venv/", "data/", "logs/", "snapshots/", "github_repo/")):
                    continue
                out.append(path)
    return sorted(set(out))


def _collect_violations() -> list[dict]:
    violations = []
    for path in _iter_files():
        rel = str(path.relative_to(ROOT))
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for name, pattern in PATTERNS.items():
                if pattern.search(line):
                    source = line.strip()
                    stable_digest = hashlib.sha256(f"{rel}\0{name}\0{source}".encode("utf-8")).hexdigest()[:16]
                    violations.append(
                        {
                            "id": f"{rel}:{name}:{stable_digest}",
                            "legacy_id": f"{rel}:{lineno}:{name}",
                            "file": rel,
                            "line": lineno,
                            "pattern": name,
                            "source": source,
                        }
                    )
    return violations


def _write_baseline(path: Path, violations: list[dict]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "allowlist": sorted(v["id"] for v in violations),
        "count": len(violations),
        "id_scheme": "stable_source_hash_v1",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Risk drift literal detector")
    parser.add_argument("--baseline", default=str(BASELINE_DEFAULT))
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    violations = _collect_violations()

    if args.update_baseline:
        _write_baseline(baseline_path, violations)
        print(json.dumps({"check": "risk_drift_literals", "updated": str(baseline_path), "count": len(violations)}, indent=2))
        return 0

    if not baseline_path.exists():
        print(json.dumps({"check": "risk_drift_literals", "error": "baseline_missing", "baseline": str(baseline_path)}, indent=2))
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    allow = set(baseline.get("allowlist", []))
    new_violations = [
        v for v in violations
        if v["id"] not in allow and v.get("legacy_id") not in allow
    ]

    print(json.dumps({
        "check": "risk_drift_literals",
        "baseline": str(baseline_path),
        "current_count": len(violations),
        "new_count": len(new_violations),
        "new_violations": new_violations[:300],
    }, indent=2))

    return 1 if new_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
