#!/usr/bin/env python3
"""
Risk observer for dashboard surfaces.
Real-data only; no synthetic values.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub


class RiskObserver:
    def __init__(self, unified_state=None, data_hub: Optional[V3DataHub] = None):
        self.state = unified_state
        self.data_hub = data_hub or V3DataHub()

    @staticmethod
    def _as_fraction(v) -> Optional[float]:
        if v is None:
            return None
        try:
            x = float(v)
        except Exception:
            return None
        if not np.isfinite(x):
            return None
        return x / 100.0 if x > 1.0 else x

    def risk_status(self) -> str:
        df = self.data_hub.risk_state()
        if df is not None and not df.empty:
            for c in ["risk_status", "status", "overall_risk", "regime_risk_level"]:
                if c in df.columns:
                    v = str(df[c].iloc[-1])
                    if v:
                        return v.upper()
        return "UNKNOWN"

    def active_risk_layer(self) -> str:
        ims = self.data_hub.intelligent_market_state()
        if ims is not None and not ims.empty and "regime" in ims.columns:
            return str(ims["regime"].iloc[-1])
        return "N/A"

    def active_constraints(self) -> List[str]:
        constraints: List[str] = []
        cap = self.exposure_cap()
        util = self.exposure_utilization()
        if cap is not None:
            constraints.append(f"Exposure cap {cap:.1%}")
        if util is not None:
            constraints.append(f"Exposure utilization {util:.1%}")
        if self.emergency_active():
            constraints.append("Emergency brake active")
        return constraints

    def exposure_cap(self) -> Optional[float]:
        ims = self.data_hub.intelligent_market_state()
        if ims is None or ims.empty or "allowed_exposure" not in ims.columns:
            return None
        s = pd.to_numeric(ims["allowed_exposure"], errors="coerce").dropna()
        if s.empty:
            return None
        return self._as_fraction(s.iloc[-1])

    def exposure_utilization(self) -> Optional[float]:
        cap = self.exposure_cap()
        analytics = self.data_hub.portfolio_analytics() or {}
        ex = analytics.get("total_exposure")
        if ex is None:
            weights = self.data_hub.portfolio_weights()
            if weights is not None and not weights.empty:
                wcol = "weight" if "weight" in weights.columns else ("final_weight" if "final_weight" in weights.columns else None)
                if wcol:
                    ex = float(pd.to_numeric(weights[wcol], errors="coerce").fillna(0).sum())
        if ex is None:
            return None
        exf = self._as_fraction(ex)
        if exf is None or cap is None or cap <= 0:
            return exf
        return exf / cap

    def emergency_active(self) -> bool:
        df = self.data_hub.risk_state()
        if df is None or df.empty:
            return False
        for c in ["emergency_active", "kill_switch_active", "emergency_brake_active"]:
            if c in df.columns:
                try:
                    return bool(df[c].iloc[-1])
                except Exception:
                    continue
        return False

    @staticmethod
    def _distance(current: float, threshold: float, higher_is_worse: bool) -> Optional[float]:
        if current is None or threshold is None:
            return None
        if higher_is_worse:
            if threshold == 0:
                return None
            return (threshold - current) / abs(threshold)
        if current == 0:
            return None
        return (current - threshold) / abs(current)

    def distance_to_emergency(self) -> Dict[str, float]:
        df = self.data_hub.risk_state()
        out: Dict[str, float] = {}
        if df is None or df.empty:
            return out
        latest = df.iloc[-1]
        dd = self._as_fraction(latest.get("current_drawdown"))
        dd_lim = self._as_fraction(latest.get("max_allowed_drawdown"))
        vol = self._as_fraction(latest.get("volatility_20d"))
        vol_lim = 0.30

        if dd is not None and dd_lim is not None:
            out["drawdown"] = float(self._distance(abs(dd), abs(dd_lim), higher_is_worse=True) or 0.0)
        if vol is not None:
            out["volatility"] = float(self._distance(vol, vol_lim, higher_is_worse=True) or 0.0)
        return out

    def next_emergency_trigger(self) -> str:
        dist = self.distance_to_emergency()
        if not dist:
            return "Unknown"
        k = min(dist, key=dist.get)
        return f"{k} ({dist[k]:+.2f})"

    def risk_timeseries(self) -> pd.DataFrame:
        df = self.data_hub.risk_state()
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out = out.dropna(subset=["date"]).set_index("date").sort_index()
        else:
            out.index = pd.to_datetime(out.index, errors="coerce")
            out = out.sort_index()
        cols = [c for c in ["current_drawdown", "volatility_20d", "emergency_active"] if c in out.columns]
        return out[cols] if cols else out

    def shock_warnings(self) -> List[str]:
        warnings: List[str] = []
        lr = self.data_hub.liquidity_risk()
        if lr is not None and not lr.empty:
            latest = lr.iloc[-1]
            score = pd.to_numeric(pd.Series([latest.get("liquidity_risk_score")]), errors="coerce").fillna(0).iloc[0]
            if score > 0.7:
                warnings.append(f"Liquidity risk elevated ({score:.2f})")

        dist = self.distance_to_emergency()
        if dist.get("volatility", 1.0) < 0.10:
            warnings.append("Volatility near emergency threshold")
        if dist.get("drawdown", 1.0) < 0.10:
            warnings.append("Drawdown near emergency threshold")
        return warnings

    def latest_risk_narrative(self) -> str:
        warns = self.shock_warnings()
        if warns:
            return "; ".join(warns)
        return f"Risk status {self.risk_status()}"

    def risk_summary(self) -> Dict[str, Any]:
        return {
            "status": self.risk_status(),
            "active_layer": self.active_risk_layer(),
            "exposure_cap": self.exposure_cap(),
            "exposure_utilization": self.exposure_utilization(),
            "emergency_active": self.emergency_active(),
            "next_trigger": self.next_emergency_trigger(),
            "warnings": self.shock_warnings(),
            "narrative": self.latest_risk_narrative(),
        }
