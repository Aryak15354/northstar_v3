#!/usr/bin/env python3
"""
Unified dashboard adapter.
Read-only bridge from V3 artifacts into lightweight dashboard structures.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.dashboard.v3_data_hub import V3DataHub
from src.dashboard.observers.automation_observer import AutomationObserver
from src.dashboard.observers.intelligence_observer import IntelligenceObserver
from src.dashboard.observers.risk_observer import RiskObserver
from src.dashboard.observers.validation_observer import ValidationObserver


class UnifiedDashboardAdapter:
    def __init__(self, as_of: Optional[datetime] = None):
        self.as_of = as_of
        self.data_hub = V3DataHub()
        self._intelligence = IntelligenceObserver(data_hub=self.data_hub)
        self._risk = RiskObserver(data_hub=self.data_hub)
        self._validation = ValidationObserver(data_hub=self.data_hub)
        self._automation = AutomationObserver(data_hub=self.data_hub)

    def intelligence(self) -> IntelligenceObserver:
        return self._intelligence

    def risk(self) -> RiskObserver:
        return self._risk

    def validation(self) -> ValidationObserver:
        return self._validation

    def automation(self) -> AutomationObserver:
        return self._automation

    def current_state(self) -> Dict[str, Any]:
        ims = self.data_hub.intelligent_market_state()
        market = {}
        if ims is not None and not ims.empty:
            latest = ims.iloc[-1]
            market = {
                "regime": latest.get("regime") or latest.get("macro_regime"),
                "risk_on_probability": latest.get("risk_on_probability"),
                "allowed_exposure": latest.get("allowed_exposure"),
                "macro_score": latest.get("macro_score"),
            }

        return {
            "market": market,
            "intelligence": self.intelligence().intelligence_summary(),
            "risk": self.risk().risk_summary(),
            "validation": self.validation().validation_summary(),
            "automation": self.automation().automation_summary(),
        }

    def _get_fallback_state(self) -> Dict[str, Any]:
        return {
            "market": {},
            "intelligence": {},
            "risk": {},
            "validation": {},
            "automation": {},
        }

    def _benchmark_close(self, benchmark: Optional[str] = None) -> Optional[pd.Series]:
        key = (benchmark or "nifty_50").strip().lower().replace(" ", "_")
        aliases = {
            "nifty": "nifty_50",
            "nsei": "nifty_50",
            "nifty50": "nifty_50",
        }
        key = aliases.get(key, key)
        df = self.data_hub.index_series(key)
        if df is None or df.empty:
            return None

        cands = [c for c in ["close", "Close", "adj_close", "Adj Close"] if c in df.columns]
        if not cands:
            return None
        s = pd.to_numeric(df[cands[0]], errors="coerce").dropna()
        if s.empty:
            return None
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s.dropna()
        return s.sort_index()

    @staticmethod
    def _window_cutoff(window: str) -> datetime:
        now = datetime.now()
        table = {
            "1D": timedelta(days=1),
            "1W": timedelta(days=7),
            "1M": timedelta(days=31),
            "3M": timedelta(days=92),
            "6M": timedelta(days=183),
            "1Y": timedelta(days=366),
            "3Y": timedelta(days=3 * 366),
        }
        return now - table.get(window.upper(), timedelta(days=31))

    def market_ts(self, window: str = "1M") -> pd.DataFrame:
        df = self.data_hub.intelligent_market_state()
        if df is None or df.empty:
            df = self.data_hub.market_regime()
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy()
        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out = out.dropna(subset=["date"]).set_index("date")
        elif "Date" in out.columns:
            out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
            out = out.dropna(subset=["Date"]).set_index("Date")
        else:
            out.index = pd.to_datetime(out.index, errors="coerce")

        out = out.sort_index()
        cutoff = self._window_cutoff(window)
        return out[out.index >= cutoff]

    def belief_ts(self) -> pd.DataFrame:
        data = self.data_hub.belief_evolution() or {}
        if not data:
            return pd.DataFrame()
        try:
            df = pd.DataFrame(data.get("history") or data)
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
                df = df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            return df
        except Exception:
            return pd.DataFrame()

    def risk_ts(self) -> pd.DataFrame:
        return self.risk().risk_timeseries()

    @staticmethod
    def _risk_bucket(v):
        try:
            x = float(v)
        except Exception:
            return "unknown"
        if x >= 0.66:
            return "high"
        if x >= 0.33:
            return "medium"
        return "low"

    def portfolio_ts(self, view: str = "Absolute", benchmark: Optional[str] = None) -> pd.DataFrame:
        pnl = self.data_hub.pnl_series()
        if pnl is None or pnl.empty:
            return pd.DataFrame()

        df = pnl.copy()
        date_col = "date" if "date" in df.columns else ("Date" if "Date" in df.columns else None)
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
        else:
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df.sort_index()

        value_col = None
        for c in ["equity", "portfolio_value", "nav", "value", "cumulative_pnl"]:
            if c in df.columns:
                value_col = c
                break

        ret_col = None
        for c in ["return", "returns", "daily_return", "pnl_return"]:
            if c in df.columns:
                ret_col = c
                break

        out = pd.DataFrame(index=df.index)
        if value_col:
            out["portfolio"] = pd.to_numeric(df[value_col], errors="coerce")
        elif ret_col:
            r = pd.to_numeric(df[ret_col], errors="coerce").fillna(0.0)
            out["portfolio"] = (1.0 + r).cumprod()
        else:
            return pd.DataFrame()

        bench = self._benchmark_close(benchmark)
        if bench is not None and not bench.empty:
            aligned = out.join(bench.rename("benchmark"), how="inner")
            if not aligned.empty:
                aligned["benchmark"] = aligned["benchmark"] / max(float(aligned["benchmark"].iloc[0]), 1e-6)
                aligned["portfolio"] = aligned["portfolio"] / max(float(aligned["portfolio"].iloc[0]), 1e-6)
                out = aligned

        if view.strip().lower() == "relative" and "benchmark" in out.columns:
            out["active"] = out["portfolio"] - out["benchmark"]

        return out.dropna(how="all")

    def narrative(self) -> str:
        df = self.data_hub.daily_narrative()
        if df is None or df.empty:
            return ""
        for c in ["narrative", "daily_narrative", "summary", "text"]:
            if c in df.columns:
                val = df.iloc[-1][c]
                return "" if pd.isna(val) else str(val)
        return ""

    @staticmethod
    def _age_days(ts) -> str:
        try:
            t = pd.to_datetime(ts)
            d = (datetime.now() - t.to_pydatetime()).days
            return f"{d}d"
        except Exception:
            return "N/A"

    def sector_pie(self) -> Dict[str, Any]:
        w = self.data_hub.portfolio_weights()
        if w is None or w.empty:
            return {"labels": [], "values": []}

        sector_col = None
        for c in ["sector", "Sector", "industry", "Industry"]:
            if c in w.columns:
                sector_col = c
                break
        weight_col = "weight" if "weight" in w.columns else ("final_weight" if "final_weight" in w.columns else None)
        if not sector_col or not weight_col:
            return {"labels": [], "values": []}

        g = (
            w[[sector_col, weight_col]]
            .assign(weight=pd.to_numeric(w[weight_col], errors="coerce").fillna(0.0))
            .groupby(sector_col, dropna=False)["weight"]
            .sum()
            .sort_values(ascending=False)
        )
        return {"labels": g.index.astype(str).tolist(), "values": g.values.tolist()}

    def live_value(self) -> str:
        analytics = self.data_hub.portfolio_analytics() or {}
        value = analytics.get("portfolio_value") or analytics.get("market_value")
        if value is None:
            return "N/A"
        try:
            return f"{float(value):,.2f}"
        except Exception:
            return str(value)

    def live_return(self) -> str:
        pnl = self.data_hub.pnl_series()
        if pnl is None or pnl.empty:
            return "N/A"
        for c in ["daily_return", "return", "returns", "pnl_return"]:
            if c in pnl.columns:
                s = pd.to_numeric(pnl[c], errors="coerce").dropna()
                if not s.empty:
                    return f"{float(s.iloc[-1]):+.2%}"
        return "N/A"

    def live_vol(self) -> str:
        pnl = self.data_hub.pnl_series()
        if pnl is None or pnl.empty:
            return "N/A"
        for c in ["daily_return", "return", "returns", "pnl_return"]:
            if c in pnl.columns:
                s = pd.to_numeric(pnl[c], errors="coerce").dropna()
                if len(s) > 5:
                    vol = float(s.std() * np.sqrt(252))
                    return f"{vol:.2%}"
        return "N/A"

    def active_positions(self) -> int:
        w = self.data_hub.portfolio_weights()
        if w is None or w.empty:
            return 0
        col = "weight" if "weight" in w.columns else ("final_weight" if "final_weight" in w.columns else None)
        if not col:
            return int(len(w))
        ws = pd.to_numeric(w[col], errors="coerce").fillna(0.0)
        return int((ws > 0).sum())

    def cpu(self) -> str:
        try:
            import psutil  # type: ignore

            return f"{psutil.cpu_percent(interval=0.05):.1f}%"
        except Exception:
            return "N/A"

    def memory(self) -> str:
        try:
            import psutil  # type: ignore

            return f"{psutil.virtual_memory().percent:.1f}%"
        except Exception:
            return "N/A"

    def latency(self) -> str:
        log = self.data_hub.system_execution_log() or {}
        total = log.get("total_duration_seconds")
        if total is None:
            return "N/A"
        try:
            return f"{float(total):.2f}s"
        except Exception:
            return str(total)

    def automation_logs(self) -> pd.DataFrame:
        return self.automation().execution_history(limit=100)

    def attribution(self) -> Dict[str, float]:
        analytics = self.data_hub.portfolio_analytics() or {}
        for k in ["attribution", "sector_attribution", "contribution"]:
            v = analytics.get(k)
            if isinstance(v, dict):
                out: Dict[str, float] = {}
                for kk, vv in v.items():
                    try:
                        out[str(kk)] = float(vv)
                    except Exception:
                        continue
                return out
        return {}
