#!/usr/bin/env python3
"""
High-conviction anti-override safeguards.

Blocks unauthorized modifications to core trading logic during stress, logs
attempts immutably, and provides escalation metadata for audit workflows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import hashlib
import json
import pandas as pd

try:
    from src.intelligence.crisis_conviction_contract import CrisisConvictionContract
except Exception:  # pragma: no cover - optional dependency in some environments
    CrisisConvictionContract = None  # type: ignore


@dataclass(frozen=True)
class SystemChange:
    """Requested change to core behavior."""

    actor: str
    module: str
    change_type: str
    payload: Dict[str, Any]
    justification: str
    stress_level: float = 0.0
    emergency: bool = False


@dataclass(frozen=True)
class InterceptionResult:
    """Result of anti-override interception."""

    allowed: bool
    reason: str
    escalation_required: bool
    cooling_off_minutes: int
    attempt_hash: str


class AntiOverrideSystem:
    """
    Enforce conviction by blocking non-structural overrides.

    Rules:
    - Core change types are blocked by default.
    - In higher stress regimes, cooling-off period increases.
    - Emergency maintenance can be allowlisted and still logged.
    - Every attempt is persisted to immutable append-only artifacts.
    """

    CORE_BLOCKED_TYPES = {
        "exposure_override",
        "manual_regime_override",
        "position_size_override",
        "stop_rule_override",
        "thesis_override",
        "disable_shutdown",
    }

    ALLOWED_MAINTENANCE_TYPES = {
        "logging_config",
        "observability_config",
        "non_trading_metadata",
    }

    def __init__(
        self,
        *,
        log_dir: str | Path = "data/processed/anti_override",
        base_cooling_minutes: int = 30,
        escalation_stress_threshold: float = 0.7,
        conviction_contract: Optional[Any] = None,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.base_cooling_minutes = int(base_cooling_minutes)
        self.escalation_stress_threshold = float(escalation_stress_threshold)

        if conviction_contract is not None:
            self.conviction_contract = conviction_contract
        elif CrisisConvictionContract is not None:
            self.conviction_contract = CrisisConvictionContract()
        else:
            self.conviction_contract = None

    def _attempt_hash(self, change: SystemChange, timestamp: datetime) -> str:
        blob = json.dumps(
            {
                "timestamp": timestamp.isoformat(),
                "actor": change.actor,
                "module": change.module,
                "change_type": change.change_type,
                "payload": change.payload,
                "justification": change.justification,
                "stress_level": change.stress_level,
                "emergency": change.emergency,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _cooling_minutes(self, stress_level: float) -> int:
        stress = max(0.0, float(stress_level))
        return int(round(self.base_cooling_minutes * (1.0 + 2.0 * stress)))

    def is_modification_authorized(self, change: SystemChange) -> bool:
        """Authorization policy for requested system changes."""

        ctype = str(change.change_type).strip().lower()
        if ctype in self.CORE_BLOCKED_TYPES:
            return False
        if ctype in self.ALLOWED_MAINTENANCE_TYPES:
            return True
        # Unknown types are blocked unless explicitly marked emergency.
        return bool(change.emergency)

    def intercept_modification(self, change: SystemChange) -> InterceptionResult:
        """
        Intercept and classify a requested modification.

        Also forwards a validation call to the conviction contract when available.
        """

        now = datetime.now(timezone.utc)
        attempt_hash = self._attempt_hash(change, now)
        authorized = self.is_modification_authorized(change)

        escalation = (not authorized) or (float(change.stress_level) >= self.escalation_stress_threshold)
        cooling = self._cooling_minutes(change.stress_level) if escalation else 0

        reason = "authorized_maintenance_change"
        if not authorized:
            reason = "blocked_core_override"
        elif escalation:
            reason = "authorized_but_escalated_for_stress_review"

        # Optional conviction contract check (best-effort).
        if self.conviction_contract is not None:
            try:
                current_state = {
                    "regime_state": "HOSTILE" if change.stress_level > 0.6 else "SUPPORTIVE",
                    "position_size": 0.0,
                    "daily_pnl": 0.0,
                }
                proposed = {
                    "manual_regime_override": change.change_type == "manual_regime_override",
                    "discretionary_sizing": change.change_type == "position_size_override",
                    "manual_exit": change.change_type == "thesis_override",
                }
                contract_ok = bool(
                    self.conviction_contract.validate_engine_action(
                        "system_change", current_state, proposed
                    )
                )
                if not contract_ok:
                    authorized = False
                    escalation = True
                    reason = "blocked_by_conviction_contract"
                    cooling = max(cooling, self._cooling_minutes(max(0.8, change.stress_level)))
            except Exception:
                # Keep anti-override protective even if contract call fails.
                pass

        self._persist_attempt(
            timestamp=now,
            change=change,
            result=InterceptionResult(
                allowed=authorized,
                reason=reason,
                escalation_required=escalation,
                cooling_off_minutes=cooling,
                attempt_hash=attempt_hash,
            ),
        )

        return InterceptionResult(
            allowed=authorized,
            reason=reason,
            escalation_required=escalation,
            cooling_off_minutes=cooling,
            attempt_hash=attempt_hash,
        )

    def escalate_unauthorized_attempt(self, result: InterceptionResult) -> Dict[str, Any]:
        """Return structured escalation instructions for operators/automation."""

        next_review = datetime.now(timezone.utc) + timedelta(minutes=result.cooling_off_minutes)
        return {
            "attempt_hash": result.attempt_hash,
            "escalation_required": result.escalation_required,
            "reason": result.reason,
            "cooling_off_minutes": result.cooling_off_minutes,
            "next_review_time_utc": next_review.isoformat(),
        }

    def _persist_attempt(
        self,
        *,
        timestamp: datetime,
        change: SystemChange,
        result: InterceptionResult,
    ) -> None:
        """Append immutable attempt records to parquet and JSONL logs."""

        row = {
            "timestamp": timestamp.isoformat(),
            "actor": change.actor,
            "module": change.module,
            "change_type": change.change_type,
            "justification": change.justification,
            "stress_level": float(change.stress_level),
            "emergency": bool(change.emergency),
            "allowed": bool(result.allowed),
            "reason": result.reason,
            "escalation_required": bool(result.escalation_required),
            "cooling_off_minutes": int(result.cooling_off_minutes),
            "attempt_hash": result.attempt_hash,
            "payload_json": json.dumps(change.payload, sort_keys=True, default=str),
        }

        parquet_path = self.log_dir / "override_attempts.parquet"
        if parquet_path.exists():
            try:
                old = pd.read_parquet(parquet_path)
                df = pd.concat([old, pd.DataFrame([row])], ignore_index=True)
            except Exception:
                df = pd.DataFrame([row])
        else:
            df = pd.DataFrame([row])

        # Deduplicate by hash while preserving latest timestamp ordering.
        if "attempt_hash" in df.columns:
            df = df.drop_duplicates(subset=["attempt_hash"], keep="last")
        df = df.sort_values("timestamp")
        df.to_parquet(parquet_path, index=False)

        jsonl_path = self.log_dir / "override_attempts.jsonl"
        with jsonl_path.open("a") as f:
            f.write(json.dumps(row) + "\n")

