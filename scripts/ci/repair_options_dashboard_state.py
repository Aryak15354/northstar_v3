#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.options.dashboard_state_contract import (
    load_json_file,
    missing_dashboard_fields,
    normalize_dashboard_state,
)
from src.options.state_io import StateIOManager

LIVE_DIR = ROOT / "data/options/live"
RUNTIME_PATH = LIVE_DIR / "options_runtime_state.json"
DASHBOARD_PATH = LIVE_DIR / "options_dashboard_state.json"


def main() -> int:
    runtime = load_json_file(RUNTIME_PATH)
    if not runtime:
        raise SystemExit("options runtime state missing or unreadable; cannot repair dashboard state")

    before = load_json_file(DASHBOARD_PATH)
    normalized = normalize_dashboard_state(before, runtime)
    manager = StateIOManager(LIVE_DIR)
    if not manager.write_dashboard_state(normalized):
        raise SystemExit("failed to write normalized options dashboard state")

    after = load_json_file(DASHBOARD_PATH)
    report = {
        "status": "ok",
        "runtime_path": str(RUNTIME_PATH),
        "dashboard_path": str(DASHBOARD_PATH),
        "missing_fields_before": missing_dashboard_fields(before),
        "missing_fields_after": missing_dashboard_fields(after),
        "schema_version": after.get("schema_version"),
        "active_positions": len(after.get("active_positions") or []),
        "net_equity": after.get("net_equity"),
        "risk_remaining": after.get("risk_remaining"),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
