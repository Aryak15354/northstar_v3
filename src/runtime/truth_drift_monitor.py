"""Continuous truth drift checker for live/shadow/derived state consistency."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from uuid import uuid4

from .contracts import TruthDriftIncident
from .hash_utils import canonical_hash, file_sha256


class TruthDriftMonitor:
    def __init__(self, freeze_escalation_breaches: int = 3):
        self.freeze_escalation_breaches = max(1, int(freeze_escalation_breaches))
        self._breach_count = 0

    @staticmethod
    def _hash_or_empty(obj: Any) -> str:
        if obj is None:
            return ""
        return canonical_hash(obj)

    @staticmethod
    def _hash_files(paths: Iterable[str]) -> str:
        digests = []
        for p in paths:
            path = Path(p)
            if path.exists() and path.is_file():
                try:
                    digests.append((str(path), file_sha256(str(path))))
                except Exception:
                    digests.append((str(path), ""))
            else:
                digests.append((str(path), ""))
        return canonical_hash(digests)

    @staticmethod
    def _derived_state_hash(paths: Iterable[str]) -> str:
        for p in paths:
            path = Path(p)
            if not path.exists() or not path.is_file():
                continue
            if path.suffix.lower() != ".json":
                continue
            try:
                import json

                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return canonical_hash(payload)
            except Exception:
                continue
        return ""

    def check(
        self,
        *,
        live_state: Dict[str, Any],
        shadow_state: Optional[Dict[str, Any]],
        derived_view_paths: Iterable[str],
    ) -> Optional[TruthDriftIncident]:
        live_hash = self._hash_or_empty(live_state)
        shadow_hash = self._hash_or_empty(shadow_state)
        derived_state_hash = self._derived_state_hash(derived_view_paths)
        derived_hash = self._hash_files(derived_view_paths)

        mismatch = False
        details: Dict[str, Any] = {
            "live_state_hash": live_hash,
            "shadow_state_hash": shadow_hash,
            "derived_state_hash": derived_state_hash,
            "derived_view_hash": derived_hash,
        }

        if shadow_hash and live_hash != shadow_hash:
            mismatch = True
            details["live_shadow_mismatch"] = True
        if derived_state_hash and live_hash != derived_state_hash:
            mismatch = True
            details["live_derived_mismatch"] = True

        if not mismatch:
            self._breach_count = 0
            return None

        self._breach_count += 1
        escalated = self._breach_count >= self.freeze_escalation_breaches

        return TruthDriftIncident(
            incident_id=f"drift_{uuid4().hex[:16]}",
            timestamp_utc=datetime.now(timezone.utc),
            live_state_hash=live_hash,
            shadow_state_hash=shadow_hash,
            derived_view_hash=derived_hash,
            breach_count=self._breach_count,
            escalated_freeze=bool(escalated),
            details=details,
        )
