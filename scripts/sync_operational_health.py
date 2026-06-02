#!/usr/bin/env python3
"""Sync operational system health into canonical unified state."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.system_status_report import STATE_PATH, build_health_snapshot, collect_statuses
from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority


def _load_state() -> UnifiedState:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return state


def main() -> int:
    statuses = collect_statuses()
    snapshot = build_health_snapshot(statuses)
    state = _load_state()

    authority = StateAuthority(
        state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="operational_health_sync",
        allowed_sections=["health"],
        priority=WritePriority.RESEARCH,
    )

    updates = [
        StateUpdate(
            writer_id="operational_health_sync",
            section="health",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Operational health sync",
        )
        for field_path, value in snapshot.items()
    ]

    applied = authority.batch_update(updates)
    if applied != len(updates):
        raise RuntimeError(f"operational_health_sync_incomplete:{applied}/{len(updates)}")
    authority.checkpoint(force=True)

    print(json.dumps(snapshot, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
