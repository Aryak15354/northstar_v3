#!/usr/bin/env python3
"""
Validation observer for dashboard surfaces.
Real-data only summaries across integrity/walk-forward/stress artifacts.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub


class ValidationObserver:
    def __init__(self, unified_state=None, data_hub: Optional[V3DataHub] = None):
        self.state = unified_state
        self.data_hub = data_hub or V3DataHub()

    def validation_status(self) -> str:
        reports = self.data_hub.latest_validation_reports()
        if not reports:
            return "NO_DATA"
        if reports.get("critical", 0) > 0:
            return "INVALID"
        if reports.get("warn", 0) > 0:
            return "DEGRADED"
        return "VALID"

    def certification_level(self) -> str:
        status = self.validation_status()
        return {
            "VALID": "CERTIFIED",
            "DEGRADED": "CONDITIONAL",
            "INVALID": "BLOCKED",
            "NO_DATA": "UNKNOWN",
        }.get(status, "UNKNOWN")

    def last_full_validation(self) -> Optional[datetime]:
        report_path = self.data_hub.project_root / "data/processed/integrity/v3_integrity_report_latest.json"
        if not report_path.exists():
            return None
        return datetime.fromtimestamp(report_path.stat().st_mtime)

    def walk_forward_health(self) -> Dict[str, Any]:
        path = self.data_hub.project_root / "data/processed/macro_conditioned_alpha/composite_ic_summary.csv"
        if not path.exists():
            return {}
        try:
            df = pd.read_csv(path)
            if df.empty:
                return {}
            best = df.sort_values("mean_ic", ascending=False).iloc[0]
            return {
                "best_composite": str(best.get("composite")),
                "mean_ic": float(best.get("mean_ic", 0.0)),
                "stability_ratio": float(best.get("stability_ratio", 0.0)),
                "pct_positive": float(best.get("pct_positive", 0.0)),
            }
        except Exception:
            return {}

    def stress_test_summary(self) -> Dict[str, Any]:
        edge = self.data_hub.edge_half_life() or {}
        rows = edge.get("rows") or []
        return {
            "strategies": int(len(rows)) if isinstance(rows, list) else 0,
            "available": bool(edge),
        }

    def signal_validity(self) -> Dict[str, Any]:
        wf = self.walk_forward_health()
        if not wf:
            return {"valid": None, "reason": "no_data"}
        mean_ic = wf.get("mean_ic", 0.0)
        return {
            "valid": bool(mean_ic and mean_ic > 0.015),
            "mean_ic": mean_ic,
            "reason": "ic_threshold",
        }

    def signal_decay_ts(self) -> pd.DataFrame:
        path = self.data_hub.project_root / "data/processed/macro_conditioned_alpha/ic_time_series_regime_conditioned.csv"
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_csv(path)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date"]).set_index("date").sort_index()
            return df
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _col(df: pd.DataFrame, name: str) -> pd.Series:
        if name not in df.columns:
            return pd.Series(dtype="float64")
        return pd.to_numeric(df[name], errors="coerce")

    def stability_metrics(self) -> Dict[str, Any]:
        wf = self.walk_forward_health()
        if not wf:
            return {}
        return {
            "stability_ratio": wf.get("stability_ratio"),
            "pct_positive": wf.get("pct_positive"),
        }

    def safeguard_flags(self) -> List[str]:
        flags: List[str] = []
        reports = self.data_hub.latest_validation_reports()
        if reports.get("critical", 0) > 0:
            flags.append("critical_validation_issues")
        if reports.get("warn", 0) > 0:
            flags.append("validation_warnings")
        validity = self.signal_validity()
        if validity.get("valid") is False:
            flags.append("signal_validity_below_threshold")
        return flags

    def capital_readiness(self) -> str:
        if self.validation_status() == "INVALID":
            return "BLOCKED"
        if self.safeguard_flags():
            return "CONDITIONAL"
        return "READY"

    def validation_summary(self) -> Dict[str, Any]:
        return {
            "status": self.validation_status(),
            "certification": self.certification_level(),
            "last_validation": self.last_full_validation(),
            "walk_forward": self.walk_forward_health(),
            "stress": self.stress_test_summary(),
            "safeguards": self.safeguard_flags(),
            "capital_readiness": self.capital_readiness(),
        }
