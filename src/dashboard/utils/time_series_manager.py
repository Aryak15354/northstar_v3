#!/usr/bin/env python3
"""
Time-series store for dashboard enhancements.
No synthetic generation: reads/writes only persisted snapshots.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


class TimeSeriesDataManager:
    def __init__(self, data_dir: str = "data/dashboard/time_series"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.portfolio_history_file = self.data_dir / "portfolio_history.parquet"
        self.trades_history_file = self.data_dir / "trades_history.parquet"
        self.returns_history_file = self.data_dir / "returns_history.parquet"
        self.metrics_history_file = self.data_dir / "metrics_history.parquet"

        self._initialize_data_files()

    def _initialize_data_files(self) -> None:
        for p in [
            self.portfolio_history_file,
            self.trades_history_file,
            self.returns_history_file,
            self.metrics_history_file,
        ]:
            if not p.exists():
                pd.DataFrame().to_parquet(p)

    def _safe_read(self, path: Path) -> pd.DataFrame:
        try:
            return pd.read_parquet(path)
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _recent(df: pd.DataFrame, days_back: int) -> pd.DataFrame:
        if df.empty:
            return df
        date_col = "date" if "date" in df.columns else ("Date" if "Date" in df.columns else None)
        if date_col is None:
            if isinstance(df.index, pd.DatetimeIndex):
                cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=days_back)
                return df[df.index >= cutoff]
            return df
        out = df.copy()
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.dropna(subset=[date_col])
        cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=days_back)
        return out[out[date_col] >= cutoff]

    def get_portfolio_changes(self, days_back: int = 30) -> Dict[str, Any]:
        df = self._recent(self._safe_read(self.portfolio_history_file), days_back)
        return {
            "rows": int(len(df)),
            "days_back": days_back,
            "latest": None if df.empty else df.tail(1).to_dict("records")[0],
        }

    def get_trades_summary(self, days_back: int = 30) -> Dict[str, Any]:
        df = self._recent(self._safe_read(self.trades_history_file), days_back)
        if df.empty:
            return {"rows": 0, "days_back": days_back, "turnover_sum": 0.0}

        turnover_col = None
        for c in ["turnover", "turnover_ratio", "turnover_pct"]:
            if c in df.columns:
                turnover_col = c
                break

        turnover_sum = 0.0
        if turnover_col:
            turnover_sum = float(pd.to_numeric(df[turnover_col], errors="coerce").fillna(0.0).sum())

        return {
            "rows": int(len(df)),
            "days_back": days_back,
            "turnover_sum": turnover_sum,
        }

    def get_returns_analysis(self, days_back: int = 30) -> Dict[str, Any]:
        df = self._recent(self._safe_read(self.returns_history_file), days_back)
        if df.empty:
            return {"rows": 0, "mean": None, "vol": None}

        col = None
        for c in ["return", "returns", "daily_return", "pnl_return"]:
            if c in df.columns:
                col = c
                break
        if not col:
            return {"rows": int(len(df)), "mean": None, "vol": None}

        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if s.empty:
            return {"rows": int(len(df)), "mean": None, "vol": None}

        return {
            "rows": int(len(df)),
            "mean": float(s.mean()),
            "vol": float(s.std()),
            "sharpe_daily": float(s.mean() / s.std()) if s.std() > 0 else None,
        }

    def get_metrics_trends(self, days_back: int = 30) -> Dict[str, Any]:
        df = self._recent(self._safe_read(self.metrics_history_file), days_back)
        if df.empty:
            return {"rows": 0, "columns": []}
        return {
            "rows": int(len(df)),
            "columns": [c for c in df.columns if c.lower() not in {"date", "timestamp"}],
        }

    def add_current_data(self, portfolio_data: Dict, trades_data: List[Dict], returns_data: Dict, metrics_data: Dict) -> None:
        now = datetime.now().isoformat()

        if portfolio_data:
            pf = self._safe_read(self.portfolio_history_file)
            row = dict(portfolio_data)
            row.setdefault("timestamp", now)
            pf = pd.concat([pf, pd.DataFrame([row])], ignore_index=True)
            pf.to_parquet(self.portfolio_history_file, index=False)

        if trades_data:
            tf = self._safe_read(self.trades_history_file)
            rows = []
            for r in trades_data:
                d = dict(r)
                d.setdefault("timestamp", now)
                rows.append(d)
            tf = pd.concat([tf, pd.DataFrame(rows)], ignore_index=True)
            tf.to_parquet(self.trades_history_file, index=False)

        if returns_data:
            rf = self._safe_read(self.returns_history_file)
            row = dict(returns_data)
            row.setdefault("timestamp", now)
            rf = pd.concat([rf, pd.DataFrame([row])], ignore_index=True)
            rf.to_parquet(self.returns_history_file, index=False)

        if metrics_data:
            mf = self._safe_read(self.metrics_history_file)
            row = dict(metrics_data)
            row.setdefault("timestamp", now)
            mf = pd.concat([mf, pd.DataFrame([row])], ignore_index=True)
            mf.to_parquet(self.metrics_history_file, index=False)


time_series_manager = TimeSeriesDataManager()
