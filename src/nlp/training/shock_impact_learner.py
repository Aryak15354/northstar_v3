"""Learn shock-to-sector impacts from realized sector price reactions."""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class ShockImpactLearner:
    """Maintains learned sector impact adjustments on top of the static shock KB."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        weights_path: str = "data/nlp/shock_impact_weights.json",
    ) -> None:
        self._config = config or {}
        learner_cfg = self._config.get("nlp", {}).get("shock_impact_learner", {})
        self._weights_path = Path(learner_cfg.get("output_path", weights_path))
        self._momentum = float(learner_cfg.get("momentum", 0.95))
        self._min_events = int(learner_cfg.get("min_events_to_update", 5))
        self._weights = self._load_weights()

    def update_from_price_reaction(self, shock_type: str, shock_date: str, sector_returns: dict[str, float]) -> None:
        del shock_date
        entry = self._weights.setdefault(
            str(shock_type),
            {"event_count": 0, "last_updated": None, "sector_impacts": {}},
        )
        entry["event_count"] = int(entry.get("event_count", 0)) + 1
        if sector_returns:
            max_abs = max(abs(float(value)) for value in sector_returns.values()) or 1.0
            for sector, observed in sector_returns.items():
                sector_entry = entry["sector_impacts"].setdefault(
                    str(sector),
                    {"score": 0.0, "observation_count": 0, "static_prior": 0.0},
                )
                normalized = max(-1.0, min(1.0, float(observed) / (max_abs * 3.0)))
                count = int(sector_entry.get("observation_count", 0))
                if count < self._min_events:
                    sector_entry["observation_count"] = count + 1
                else:
                    new_score = self._momentum * float(sector_entry.get("score", 0.0)) + (1.0 - self._momentum) * normalized
                    sector_entry["score"] = 0.70 * new_score + 0.30 * float(sector_entry.get("static_prior", 0.0))
                    sector_entry["observation_count"] = count + 1
        entry["last_updated"] = datetime.now().isoformat()
        self._save_weights()

    def learn_from_event_frame(
        self,
        events_df: pd.DataFrame,
        sector_return_frame: pd.DataFrame,
        *,
        shock_col: str = "shock_type",
        date_col: str = "date",
    ) -> dict[str, Any]:
        if events_df.empty or sector_return_frame.empty:
            return {"status": "skipped", "reason": "no_data"}
        work_events = events_df.copy()
        work_events[date_col] = pd.to_datetime(work_events[date_col], errors="coerce").dt.normalize()
        sector_returns = sector_return_frame.copy()
        sector_returns[date_col] = pd.to_datetime(sector_returns[date_col], errors="coerce").dt.normalize()
        applied = 0
        for _, row in work_events.dropna(subset=[shock_col, date_col]).iterrows():
            realized = sector_returns[sector_returns[date_col] == row[date_col]]
            if realized.empty:
                continue
            payload = {
                column: float(pd.to_numeric(realized.iloc[0][column], errors="coerce") or 0.0)
                for column in realized.columns
                if column != date_col
            }
            self.update_from_price_reaction(str(row[shock_col]), str(row[date_col]), payload)
            applied += 1
        return {"status": "ok", "applied_events": int(applied)}

    def get_sector_impacts(self, shock_type: str) -> dict[str, float]:
        token = str(shock_type or "")
        if token not in self._weights:
            return self._get_static_impacts(token)
        entry = self._weights[token]
        if int(entry.get("event_count", 0)) < self._min_events:
            return self._get_static_impacts(token)
        return {
            sector: float(payload.get("score", 0.0))
            for sector, payload in dict(entry.get("sector_impacts", {}) or {}).items()
        }

    def get_learning_summary(self) -> dict[str, Any]:
        return {
            shock_type: {
                "event_count": int(entry.get("event_count", 0)),
                "sectors_with_data": int(
                    sum(1 for payload in dict(entry.get("sector_impacts", {}) or {}).values() if int(payload.get("observation_count", 0)) >= self._min_events)
                ),
                "last_updated": entry.get("last_updated"),
                "using_learned": int(entry.get("event_count", 0)) >= self._min_events,
            }
            for shock_type, entry in self._weights.items()
        }

    def _load_weights(self) -> dict[str, Any]:
        if self._weights_path.exists():
            return json.loads(self._weights_path.read_text(encoding="utf-8"))
        return self._init_from_static_kb()

    def _init_from_static_kb(self) -> dict[str, Any]:
        from src.intelligence.shock_engine.shock_knowledge_base import SHOCK_KNOWLEDGE_BASE

        weights: dict[str, Any] = {}
        for shock_type, profile in SHOCK_KNOWLEDGE_BASE.items():
            weights[shock_type] = {"event_count": 0, "last_updated": None, "sector_impacts": {}}
            for sector, payload in dict(profile.get("sector_impacts", {}) or {}).items():
                score = float(payload.get("score", 0.0) if isinstance(payload, dict) else payload)
                weights[shock_type]["sector_impacts"][sector] = {
                    "score": score,
                    "observation_count": 0,
                    "static_prior": score,
                }
        return deepcopy(weights)

    def _get_static_impacts(self, shock_type: str) -> dict[str, float]:
        from src.intelligence.shock_engine.shock_knowledge_base import SHOCK_KNOWLEDGE_BASE

        payload = SHOCK_KNOWLEDGE_BASE.get(str(shock_type), {})
        return {
            sector: float(item.get("score", 0.0) if isinstance(item, dict) else item)
            for sector, item in dict(payload.get("sector_impacts", {}) or {}).items()
        }

    def _save_weights(self) -> None:
        self._weights_path.parent.mkdir(parents=True, exist_ok=True)
        self._weights_path.write_text(json.dumps(self._weights, indent=2, default=str), encoding="utf-8")
