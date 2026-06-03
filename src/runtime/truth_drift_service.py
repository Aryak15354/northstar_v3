"""Background truth-drift service for continuous PRS integrity checks."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .portfolio_runtime_service import PortfolioRuntimeService

logger = logging.getLogger(__name__)


class TruthDriftService:
    def __init__(
        self,
        prs: PortfolioRuntimeService,
        *,
        shadow_state_path: str = "data/processed/shadow_state_current.json",
        poll_interval_seconds: float = 30.0,
        extra_derived_paths: Optional[list[str]] = None,
    ):
        self.prs = prs
        self.shadow_state_path = Path(shadow_state_path)
        self.poll_interval_seconds = max(1.0, float(poll_interval_seconds))
        self.extra_derived_paths = list(extra_derived_paths or [])

    def _load_shadow_state(self) -> Dict[str, Any]:
        if not self.shadow_state_path.exists():
            return {}
        try:
            payload = json.loads(self.shadow_state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def run_once(self) -> Optional[Dict[str, Any]]:
        shadow = self._load_shadow_state()
        incident = self.prs.run_truth_drift_check(
            shadow_state=shadow,
            extra_derived_paths=self.extra_derived_paths,
        )
        if incident is not None:
            logger.error("truth_drift_detected incident_id=%s breach_count=%s", incident.get("incident_id"), incident.get("breach_count"))
        return incident

    def run_forever(self) -> None:
        while True:
            self.run_once()
            time.sleep(self.poll_interval_seconds)
