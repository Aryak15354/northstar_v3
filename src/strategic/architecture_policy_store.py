"""Versioned storage for strategic architecture policies (Phase 10)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class ArchitecturePolicyStore:
    def __init__(self, policy_path: str = "data/strategic/architecture_policy.json"):
        self.policy_path = Path(policy_path)
        self.policy_path.parent.mkdir(parents=True, exist_ok=True)
        self.history_dir = self.policy_path.parent / "architecture_policy_versions"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def load(self) -> Dict[str, Any]:
        if not self.policy_path.exists():
            return {
                "version": 0,
                "updated_at": "",
                "last_update_date": "",
                "theta": {},
                "diagnostics": {},
            }
        try:
            payload = json.loads(self.policy_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return {
            "version": 0,
            "updated_at": "",
            "last_update_date": "",
            "theta": {},
            "diagnostics": {},
        }

    def save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prev = self.load()
        version = int(prev.get("version", 0) or 0) + 1
        out = dict(payload or {})
        out["version"] = int(version)
        out["updated_at"] = self._now_iso()

        text = json.dumps(out, sort_keys=True, indent=2)
        self.policy_path.write_text(text, encoding="utf-8")
        version_path = self.history_dir / f"architecture_policy_v{version:05d}.json"
        version_path.write_text(text, encoding="utf-8")
        return out
