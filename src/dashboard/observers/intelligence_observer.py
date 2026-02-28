#!/usr/bin/env python3
"""
Intelligence observer for dashboard surfaces.
Real-data only adapters over V3 artifacts.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub


class IntelligenceObserver:
    def __init__(self, unified_state=None, data_hub: Optional[V3DataHub] = None):
        self.state = unified_state
        self.data_hub = data_hub or V3DataHub()

    # ------------------------------------------------------------------
    # EDGE
    # ------------------------------------------------------------------
    def edge_strength(self) -> float:
        feed = self.data_hub.regime_intelligence_feed() or {}
        cm = feed.get("confidence_metrics") or {}
        v = cm.get("overall")
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass

        ims = self.data_hub.intelligent_market_state()
        if ims is not None and not ims.empty and "risk_on_probability" in ims.columns:
            try:
                return float(pd.to_numeric(ims["risk_on_probability"], errors="coerce").dropna().iloc[-1])
            except Exception:
                pass
        return 0.0

    def edge_present(self) -> bool:
        return self.edge_strength() >= 0.5

    def edge_reason(self) -> str:
        feed = self.data_hub.regime_intelligence_feed() or {}
        cur = (feed.get("current_regime") or {}).get("name")
        conf = self.edge_strength()
        if cur:
            return f"regime={cur}, confidence={conf:.1%}"
        return f"confidence={conf:.1%}"

    # ------------------------------------------------------------------
    # SIGNAL HEALTH
    # ------------------------------------------------------------------
    def signal_health_ts(self) -> pd.DataFrame:
        mr = self.data_hub.market_regime()
        if mr is not None and not mr.empty:
            df = mr.copy()
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
            else:
                df.index = pd.to_datetime(df.index, errors="coerce")
                df = df.sort_index()

            cols = [c for c in ["breadth", "participation", "volatility", "correlation", "risk_on_score"] if c in df.columns]
            if cols:
                out = pd.DataFrame(index=df.index)
                ranked = {}
                for c in cols:
                    s = pd.to_numeric(df[c], errors="coerce")
                    if c in {"volatility", "correlation"}:
                        ranked[c] = 1.0 - s.rank(pct=True)
                    else:
                        ranked[c] = s.rank(pct=True)
                health = sum(ranked.values()) / max(len(ranked), 1)
                out["health_score"] = health.clip(0, 1)
                out["decay_rate"] = (-out["health_score"].diff()).clip(lower=0)
                out["correlation"] = pd.to_numeric(df["correlation"], errors="coerce") if "correlation" in df.columns else np.nan
                return out.dropna(how="all")

        pulse = self.data_hub.pulse_history()
        if pulse is None or pulse.empty:
            return pd.DataFrame()

        p = pulse.copy()
        if "date" in p.columns:
            p["date"] = pd.to_datetime(p["date"], errors="coerce")
            p = p.dropna(subset=["date"]).sort_values("date").set_index("date")
        else:
            p.index = pd.to_datetime(p.index, errors="coerce")
            p = p.sort_index()

        intensity = pd.to_numeric(p.get("pulse_intensity"), errors="coerce")
        n_signals = pd.to_numeric(p.get("n_pulse_signals"), errors="coerce")
        denom = float(n_signals.dropna().max()) if not n_signals.dropna().empty else 1.0
        breadth = (n_signals / max(denom, 1.0)).clip(0, 1)
        health = (0.6 * intensity.rank(pct=True) + 0.4 * breadth).clip(0, 1)

        out = pd.DataFrame(index=p.index)
        out["health_score"] = health
        out["decay_rate"] = (-health.diff()).clip(lower=0)
        out["correlation"] = pd.to_numeric(p.get("regime_similarity"), errors="coerce")
        return out.dropna(how="all")

    def signal_health_status(self) -> str:
        ts = self.signal_health_ts()
        if ts.empty or "health_score" not in ts.columns:
            return "No Data"
        v = float(pd.to_numeric(ts["health_score"], errors="coerce").dropna().iloc[-1])
        if v >= 0.75:
            return "Healthy"
        if v >= 0.50:
            return "Degrading"
        return "Critical"

    # ------------------------------------------------------------------
    # BELIEF VS CONFIDENCE
    # ------------------------------------------------------------------
    def conviction_confidence_gap(self) -> Dict[str, float]:
        beliefs = self.data_hub.unified_beliefs() or {}
        confidence = ((beliefs.get("confidence_metrics") or {}).get("overall_confidence"))
        conviction = beliefs.get("unified_conviction")
        if confidence is None or conviction is None:
            return {}
        try:
            return {"unified": abs(float(conviction) - float(confidence))}
        except Exception:
            return {}

    def disagreement_level(self) -> str:
        gap = self.conviction_confidence_gap().get("unified")
        if gap is None:
            return "No Data"
        if gap < 0.1:
            return "Aligned"
        if gap < 0.3:
            return "Cautious"
        return "High Disagreement"

    # ------------------------------------------------------------------
    # UNCERTAINTY
    # ------------------------------------------------------------------
    def allocation_uncertainty(self) -> pd.DataFrame:
        allocations = self.data_hub.capital_allocations() or {}
        allocs = allocations.get("allocations") or {}
        if not allocs:
            return pd.DataFrame()

        hist = self.data_hub.allocation_history()
        hist_df = None
        if hist is not None and not hist.empty:
            df = hist.copy()
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date"]).sort_values("date").set_index("date")
            else:
                df.index = pd.to_datetime(df.index, errors="coerce")
                df = df.sort_index()
            hist_df = df

        rows = []
        for strategy, mean_val in allocs.items():
            try:
                mean_alloc = float(mean_val)
            except Exception:
                continue

            lower = mean_alloc
            upper = mean_alloc
            if hist_df is not None and strategy in hist_df.columns:
                s = pd.to_numeric(hist_df[strategy], errors="coerce").dropna()
                if len(s) >= 10:
                    lower = float(s.quantile(0.05))
                    upper = float(s.quantile(0.95))
                    mean_alloc = float(s.mean())

            if lower > upper:
                lower, upper = upper, lower

            rows.append(
                {
                    "strategy": strategy,
                    "mean": mean_alloc,
                    "lower_5pct": lower,
                    "upper_95pct": upper,
                    "uncertainty_width": upper - lower,
                }
            )

        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values("mean", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------------
    # REGIME MEMORY CONTEXT
    # ------------------------------------------------------------------
    def regime_similarity(self) -> Dict[str, Any]:
        pulse = self.data_hub.pulse_history()
        if pulse is not None and not pulse.empty:
            latest = pulse.iloc[-1]
            return {
                "name": latest.get("market_phase") or latest.get("regime") or "Unknown",
                "similarity": float(pd.to_numeric(pd.Series([latest.get("regime_similarity")]), errors="coerce").fillna(0).iloc[0]),
                "period": str(latest.get("date") or ""),
                "outcome": "",
            }

        feed = self.data_hub.regime_intelligence_feed() or {}
        cur = feed.get("current_regime") or {}
        return {
            "name": cur.get("name") or "Unknown",
            "similarity": float(cur.get("stability", 0.0) or 0.0),
            "period": "",
            "outcome": "",
        }

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    def intelligence_summary(self) -> Dict[str, Any]:
        unc = self.allocation_uncertainty()
        uncertainty = None
        if not unc.empty and "uncertainty_width" in unc.columns:
            uncertainty = float(pd.to_numeric(unc["uncertainty_width"], errors="coerce").dropna().mean())

        return {
            "edge": self.edge_present(),
            "edge_strength": self.edge_strength(),
            "edge_reason": self.edge_reason(),
            "signal_health": self.signal_health_status(),
            "disagreement": self.disagreement_level(),
            "uncertainty": uncertainty,
        }
