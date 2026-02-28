#!/usr/bin/env python3
"""
Automation observer for dashboard surfaces.
Real-data only: reads system execution logs and exposes compact summaries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub


class AutomationObserver:
    def __init__(self, unified_state=None, data_hub: Optional[V3DataHub] = None):
        self.state = unified_state
        self.data_hub = data_hub or V3DataHub()

    def execution_history(self, limit: int = 50) -> pd.DataFrame:
        log = self.data_hub.system_execution_log()
        if not log:
            return pd.DataFrame()

        rows = []
        for step in log.get("steps", []) or []:
            rows.append(
                {
                    "timestamp": step.get("ended_at") or step.get("started_at"),
                    "step": step.get("name"),
                    "status": step.get("status"),
                    "duration_seconds": step.get("duration_seconds"),
                    "message": step.get("message"),
                }
            )

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.sort_values("timestamp", ascending=False)
        return df.head(limit).reset_index(drop=True)

    def recent_failures(self, limit: int = 20) -> pd.DataFrame:
        df = self.execution_history(limit=500)
        if df.empty:
            return df
        failed = df[df["status"].astype(str).str.lower().eq("failed")]
        return failed.head(limit).reset_index(drop=True)

    def recovery_status(self) -> str:
        failures = self.recent_failures(limit=30)
        if failures.empty:
            return "stable"
        recent = failures["timestamp"].dropna()
        if recent.empty:
            return "degraded"
        latest = recent.max()
        if pd.isna(latest):
            return "degraded"
        hours = (datetime.now() - latest.to_pydatetime()).total_seconds() / 3600.0
        return "recovering" if hours < 24 else "degraded"

    def automation_summary(self) -> Dict[str, Any]:
        history = self.execution_history(limit=10)
        if history.empty:
            return {
                "last_run_status": "N/A",
                "last_run_time": None,
                "recovery": "unknown",
                "failures": 0,
            }

        last = history.iloc[0]
        return {
            "last_run_status": str(last.get("status", "N/A")),
            "last_run_time": last.get("timestamp"),
            "recovery": self.recovery_status(),
            "failures": int(len(self.recent_failures(limit=50))),
        }
