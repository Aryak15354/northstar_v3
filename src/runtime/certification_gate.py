"""Certification validity gate with TTL and invalidation checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .contracts import CertificationCheckResult, CertificationSnapshot, TradeProposal
from .hash_utils import canonical_hash


@dataclass(frozen=True)
class CertificationGateConfig:
    ttl_days: int = 30


def build_certification_snapshot(
    *,
    model_hash: str,
    param_hash: str,
    feature_hash: str,
    data_revision_hash: str,
    config_hash: str,
    created_at: Optional[datetime] = None,
    ttl_days: int = 30,
    drift_guard_version: str = "v1",
) -> CertificationSnapshot:
    created = created_at or datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    valid_until = created + timedelta(days=max(1, int(ttl_days)))
    payload = {
        "model_hash": str(model_hash),
        "param_hash": str(param_hash),
        "feature_hash": str(feature_hash),
        "data_revision_hash": str(data_revision_hash),
        "config_hash": str(config_hash),
        "created_at": created.isoformat(),
        "valid_until": valid_until.isoformat(),
        "drift_guard_version": str(drift_guard_version),
    }
    snapshot_hash = canonical_hash(payload)
    return CertificationSnapshot(
        snapshot_hash=snapshot_hash,
        model_hash=str(model_hash),
        param_hash=str(param_hash),
        feature_hash=str(feature_hash),
        data_revision_hash=str(data_revision_hash),
        config_hash=str(config_hash),
        created_at=created,
        valid_until=valid_until,
        drift_guard_version=str(drift_guard_version),
    )


class CertificationGate:
    """Validate proposal certification hash, TTL, and invalidation context."""

    def __init__(self, store: Any, config: CertificationGateConfig | None = None):
        self.store = store
        self.config = config or CertificationGateConfig()

    def validate(
        self,
        proposal: TradeProposal,
        current_context: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> CertificationCheckResult:
        now_utc = now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)
        snapshot = self.store.get_certification_snapshot(proposal.certification_snapshot_hash)
        if not snapshot:
            return CertificationCheckResult(False, "certification.missing_snapshot", proposal.certification_snapshot_hash)

        valid_until = datetime.fromisoformat(str(snapshot.get("valid_until")))
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        if now_utc > valid_until:
            return CertificationCheckResult(False, "certification.ttl_expired", proposal.certification_snapshot_hash)

        ctx = dict(current_context or {})
        if bool(ctx.get("feature_drift_breach", False)):
            return CertificationCheckResult(False, "certification.feature_drift_breach", proposal.certification_snapshot_hash)

        for key in ("data_revision_hash", "config_hash", "model_hash", "param_hash", "feature_hash"):
            expected = ctx.get(key)
            if expected is None:
                continue
            observed = snapshot.get(key)
            if str(expected) != str(observed):
                return CertificationCheckResult(False, "certification.context_mismatch", proposal.certification_snapshot_hash)

        expected_drift_ver = ctx.get("drift_guard_version")
        if expected_drift_ver is not None and str(expected_drift_ver) != str(snapshot.get("drift_guard_version", "")):
            return CertificationCheckResult(False, "certification.context_mismatch", proposal.certification_snapshot_hash)

        return CertificationCheckResult(True, "", proposal.certification_snapshot_hash)
