#!/usr/bin/env python3
"""
📡 V3 DATA HUB
Single read-only access layer for real Northstar V3 artifacts.

Rules:
- Never fabricate data.
- If a file is missing or unreadable, return None/empty.
- No business logic beyond light normalization.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import json
import numpy as np
import pandas as pd

from src.data.price_access import (
    canonical_price_columns,
    canonical_price_path,
    prices_to_legacy_shape,
)
from src.data.query_engine import DuckDBQueryEngine


@dataclass
class V3DataHub:
    project_root: Path

    def __init__(self, project_root: Optional[Path] = None) -> None:
        if project_root is None:
            # src/dashboard -> project root
            self.project_root = Path(__file__).resolve().parents[2]
        else:
            self.project_root = Path(project_root)
        self.query = DuckDBQueryEngine(memory_limit_mb=768, threads=1)

    # ------------------------- helpers -------------------------
    def _read_parquet(self, rel_path: str) -> Optional[pd.DataFrame]:
        path = self.project_root / rel_path
        if not path.exists():
            return None
        try:
            if self.query.available:
                df = self.query.read_parquet(path)
                if isinstance(df, pd.DataFrame):
                    return df
            return pd.read_parquet(path)
        except Exception:
            return None

    def _read_json(self, rel_path: str) -> Optional[Dict[str, Any]]:
        path = self.project_root / rel_path
        if not path.exists():
            return None
        try:
            with path.open("r") as f:
                return json.load(f)
        except Exception:
            return None

    def _latest_by_mtime(self, pattern: str) -> Optional[Path]:
        candidates = list((self.project_root / Path(pattern).parent).glob(Path(pattern).name))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def _normalize_weights_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "ticker" not in out.columns and "symbol" in out.columns:
            out["ticker"] = out["symbol"].astype(str).map(
                lambda s: s if s.endswith(".NS") else f"{s}.NS"
            )
        if "symbol" not in out.columns and "ticker" in out.columns:
            out["symbol"] = out["ticker"].astype(str).str.replace(".NS", "", regex=False)

        weight_col = None
        for c in ["weight", "final_weight", "allocation", "w"]:
            if c in out.columns:
                weight_col = c
                break
        if weight_col and weight_col != "weight":
            out["weight"] = pd.to_numeric(out[weight_col], errors="coerce")
        elif "weight" in out.columns:
            out["weight"] = pd.to_numeric(out["weight"], errors="coerce")
        return out

    def _is_meaningful_weights(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            return False
        if "weight" not in df.columns:
            return False
        weight = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0)
        n_pos = int((weight > 0).sum())
        exposure = float(weight.sum())
        return n_pos >= 5 and exposure > 0.01

    def _canonical_prices_path(self) -> Optional[Path]:
        try:
            return canonical_price_path(project_root=self.project_root)
        except FileNotFoundError:
            return None

    def _legacy_price_columns(self, columns: Optional[Sequence[str]]) -> Optional[list[str]]:
        return canonical_price_columns(columns)

    def _prices_to_legacy_shape(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None
        return prices_to_legacy_shape(df)

    def _sanitize_proxy_close(
        self,
        series: pd.Series,
        *,
        jump_threshold: float = 0.20,
        ret_cap: float = 0.12,
    ) -> pd.Series:
        """
        Stitch ONLY genuine structural level breaks in synthetic proxy indices.

        Why:
        - Proxy index series can inherit constituent scale breaks (splits/source changes),
          which creates unrealistic cliffs/flatlines in charts.
        - We stitch single-day moves beyond `jump_threshold` (data-level shifts) back to a
          bounded step. We do NOT blanket-cap smaller moves: the previous version clipped
          EVERY daily return to ±12%, which silently rewrote genuine crash days (a real
          −13% index session became −12%). Real index moves have never exceeded ~15% in a
          day, so a >20% single-day move in a proxy index is a data artifact, while anything
          below is preserved as-is.
        """
        s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
        s = s.where(s > 0)
        if s.dropna().shape[0] < 3:
            return s

        base = float(s.dropna().iloc[0])
        r = s.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
        # Stitch only clear structural breaks; leave all real moves untouched.
        r = r.mask(r.abs() > jump_threshold, np.sign(r) * ret_cap).fillna(0.0)
        recon = base * (1.0 + r).cumprod()
        recon = recon.where(s.notna())
        recon.name = s.name
        return recon

    def _latest_timestamp(self, df: Optional[pd.DataFrame]) -> Optional[pd.Timestamp]:
        """Return latest timestamp from common date columns or datetime index."""
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None

        for col in ["Date", "date", "timestamp", "intelligence_timestamp_str"]:
            if col in df.columns:
                dts = pd.to_datetime(df[col], errors="coerce").dropna()
                if not dts.empty:
                    return pd.Timestamp(dts.max())

        if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
            idx = pd.to_datetime(df.index, errors="coerce")
            idx = idx[~idx.isna()]
            if len(idx) > 0:
                return pd.Timestamp(idx.max())
        return None

    def _normalize_market_regime_frame(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        """Normalize varied regime schemas into dashboard canonical columns."""
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None

        out = df.copy()
        date_col = next(
            (c for c in ["Date", "date", "timestamp", "intelligence_timestamp_str"] if c in out.columns),
            None,
        )
        if date_col is None:
            if isinstance(out.index, pd.DatetimeIndex):
                out = out.reset_index().rename(columns={out.index.name or "index": "Date"})
                date_col = "Date"
            else:
                return None

        out["Date"] = pd.to_datetime(out[date_col], errors="coerce")
        out = out.dropna(subset=["Date"]).sort_values("Date")
        if out.empty:
            return None

        def _pick(*cols: str) -> pd.Series:
            for c in cols:
                if c in out.columns:
                    return pd.to_numeric(out[c], errors="coerce")
            return pd.Series(np.nan, index=out.index, dtype="float64")

        norm = pd.DataFrame(
            {
                "Date": out["Date"],
                "breadth": _pick("breadth", "breadth_pct"),
                "participation": _pick("participation", "participation_score"),
                "volatility": _pick("volatility", "stress_score"),
                "correlation": _pick("correlation"),
                "risk_on_score": _pick("risk_on_score", "risk_on_probability", "risk_on"),
                "market_regime": (
                    out.get("market_regime")
                    if "market_regime" in out.columns
                    else (
                        out.get("macro_regime")
                        if "macro_regime" in out.columns
                        else (
                            out.get("regime_name")
                            if "regime_name" in out.columns
                            else out.get("regime")
                        )
                    )
                ),
            }
        )
        norm["market_regime"] = norm["market_regime"].astype(str).replace({"nan": "Unknown"})
        norm = norm.drop_duplicates(subset=["Date"], keep="last").sort_values("Date")
        return norm

    def _prepare_index_series(self, df: Optional[pd.DataFrame], *, sanitize_proxy: bool) -> Optional[pd.DataFrame]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None

        out = df.copy()
        if isinstance(out.columns, pd.MultiIndex):
            out.columns = [c[0] if isinstance(c, tuple) else c for c in out.columns]
        out = out.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))

        if "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out = out.dropna(subset=["date"]).sort_values("date").set_index("date")
        out.index = pd.to_datetime(out.index, errors="coerce")
        out = out[out.index.notna()]
        out.index.name = "Date"
        if not out.index.is_monotonic_increasing:
            out = out.sort_index()
        out = out[~out.index.duplicated(keep="last")]
        if out.empty:
            return None

        if "close" in out.columns:
            out["close"] = pd.to_numeric(out["close"], errors="coerce")
            out = out.dropna(subset=["close"])
            if out.empty:
                return None

        if sanitize_proxy and "proxy_constituents" in out.columns:
            out = out[out.index.dayofweek < 5]
            if "close" in out.columns:
                out["close"] = self._sanitize_proxy_close(out["close"])
                for c in ["open", "high", "low", "adj_close"]:
                    if c in out.columns:
                        out[c] = out[c].where(pd.to_numeric(out[c], errors="coerce").notna(), out["close"])

        if "close" in out.columns:
            close = pd.to_numeric(out["close"], errors="coerce")
            max_abs_ret = float(close.pct_change().abs().replace([np.inf, -np.inf], np.nan).max() or 0.0)
            if max_abs_ret > 0.35:
                out["close"] = self._sanitize_proxy_close(close)

        return out if not out.empty else None

    # ------------------------- core datasets -------------------------
    def market_state(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/market_state.parquet")

    def intelligent_market_state(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/intelligent_market_state.parquet")

    def exposure_history(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/exposure_history.parquet")

    def exposure_state(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/exposure_state.parquet")

    def risk_state(self) -> Optional[pd.DataFrame]:
        for rel in [
            "data/processed/risk_state.parquet",
            "data/risk/risk_state.parquet",
            "data/risk/emergency_signal.parquet",
        ]:
            df = self._read_parquet(rel)
            if df is not None and not df.empty:
                return df
        return None

    def portfolio_weights(self) -> Optional[pd.DataFrame]:
        fallback_df: Optional[pd.DataFrame] = None

        # 1) Canonical file
        primary = self._read_parquet("data/processed/portfolio_weights.parquet")
        if primary is not None and not primary.empty:
            primary = self._normalize_weights_frame(primary)
            if self._is_meaningful_weights(primary):
                return primary
            fallback_df = primary

        # 2) Most recent backup (often preserves last valid snapshot when canonical turns degenerate)
        backup = self._latest_by_mtime("data/processed/backups/portfolio_weights_*.parquet")
        if backup is not None and backup.exists():
            try:
                bdf = self._normalize_weights_frame(pd.read_parquet(backup))
                if self._is_meaningful_weights(bdf):
                    return bdf
                if fallback_df is None and not bdf.empty:
                    fallback_df = bdf
            except Exception:
                pass

        # 3) Weekly snapshot latest pointer
        latest_weekly = self._read_json("data/portfolio/weekly/latest.json") or {}
        snap_path = latest_weekly.get("path")
        if isinstance(snap_path, str) and snap_path:
            try:
                sp = Path(snap_path)
                if not sp.is_absolute():
                    sp = self.project_root / sp
                sdf = self._normalize_weights_frame(pd.read_parquet(sp))
                if self._is_meaningful_weights(sdf):
                    return sdf
                if fallback_df is None and not sdf.empty:
                    fallback_df = sdf
            except Exception:
                pass

        # 4) Legacy fallbacks
        for rel in [
            "data/portfolio/final_weights.parquet",
            "data/processed/stock_weights_risk.parquet",
            "data/processed/stock_weights_raw.parquet",
        ]:
            df = self._read_parquet(rel)
            if df is not None and not df.empty:
                df = self._normalize_weights_frame(df)
                if self._is_meaningful_weights(df):
                    return df
                if fallback_df is None:
                    fallback_df = df

        if fallback_df is not None and not fallback_df.empty:
            return fallback_df
        return None

    def pnl_series(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/portfolio/pnl_on_paper.parquet")

    def nifty_series(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/nifty.parquet")

    def prices(self) -> Optional[pd.DataFrame]:
        path = self._canonical_prices_path()
        if path is None:
            return None
        try:
            if self.query.available:
                return self._prices_to_legacy_shape(self.query.read_parquet(path))
            return self._prices_to_legacy_shape(pd.read_parquet(path))
        except Exception:
            return None

    def prices_filtered(
        self,
        tickers: Sequence[str],
        *,
        columns: Optional[Sequence[str]] = None,
    ) -> Optional[pd.DataFrame]:
        """Load a subset of prices for the given tickers.

        This avoids loading the full ~2M row price table into memory when the
        dashboard only needs a handful of series.
        """
        if not tickers:
            return None
        path = self._canonical_prices_path()
        if path is None or not path.exists():
            return None
        read_columns = self._legacy_price_columns(columns)
        try:
            if self.query.available:
                df = self.query.read_parquet(
                    path,
                    columns=read_columns,
                    in_filters={"ticker": list(tickers)},
                )
                return self._prices_to_legacy_shape(df)
            # pandas fallback
            df = pd.read_parquet(
                path,
                columns=read_columns,
                filters=[("ticker", "in", list(tickers))],
            )
            return self._prices_to_legacy_shape(df)
        except Exception:
            return None

    def regime_fingerprints(self) -> Optional[pd.DataFrame]:
        for rel in [
            "data/processed/regime_fingerprints_extended.parquet",
            "data/processed/regime_fingerprints.parquet",
            "data/processed/simple_regime_fingerprints.parquet",
        ]:
            df = self._read_parquet(rel)
            if df is not None and not df.empty:
                return df
        return None

    def regime_transitions(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/regime_transitions.parquet")

    def sector_flows(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/sector_flows.parquet")

    def market_regime(self) -> Optional[pd.DataFrame]:
        direct = self._normalize_market_regime_frame(self._read_parquet("data/processed/market_regime.parquet"))
        intelligent = self._normalize_market_regime_frame(self._read_parquet("data/processed/intelligent_market_state.parquet"))
        market_state = self._normalize_market_regime_frame(self._read_parquet("data/processed/market_state.parquet"))

        candidates = [c for c in [direct, intelligent, market_state] if isinstance(c, pd.DataFrame) and not c.empty]
        if not candidates:
            return None

        # Prefer freshest artifact; fallback to longest series if tied.
        scored = []
        for c in candidates:
            latest = self._latest_timestamp(c)
            scored.append((latest or pd.Timestamp.min, len(c), c))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2]

    def daily_narrative(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/daily_narrative.parquet")

    def allocation_history(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/allocation_history.parquet")

    def pulse_history(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/pulse_history.parquet")

    def belief_evolution(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/belief_evolution.json")

    def unified_beliefs(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/unified_beliefs.json")

    def unified_intelligence_state(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/unified_intelligence_state.json")

    def regime_intelligence_feed(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/regime_intelligence_feed.json")

    def portfolio_analytics(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/portfolio_analytics.json")

    def capital_allocations(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/capital_allocations.json")

    def options_dashboard_state(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/options/live/options_dashboard_state.json")

    def edge_half_life(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/edge_half_life.json")

    def liquidity_risk(self) -> Optional[pd.DataFrame]:
        return self._read_parquet("data/processed/liquidity_risk.parquet")

    def trades_latest(self) -> Optional[pd.DataFrame]:
        latest = self._latest_by_mtime("data/portfolio/trades/*.parquet")
        if latest is None:
            return None
        try:
            return pd.read_parquet(latest)
        except Exception:
            return None

    def trades_history(self) -> Optional[pd.DataFrame]:
        trade_dir = self.project_root / "data/portfolio/trades"
        if not trade_dir.exists():
            return None
        frames = []
        for path in sorted(trade_dir.glob("*.parquet")):
            try:
                df = pd.read_parquet(path)
                df["snapshot"] = path.stem
                frames.append(df)
            except Exception:
                continue
        if not frames:
            return None
        return pd.concat(frames, ignore_index=True)

    def benchmark_from_yfinance(self, ticker: str, period: str = "3y") -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf  # type: ignore
        except Exception:
            return None
        try:
            df = yf.download(ticker, period=period, auto_adjust=False, progress=False)
            if df is None or df.empty:
                return None
        except Exception:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))
        df.index = pd.to_datetime(df.index)
        df.index.name = "Date"
        return df

    def index_series(self, name: str) -> Optional[pd.DataFrame]:
        candidates: list[pd.DataFrame] = []

        index_dir = self.project_root / "data/processed/index_data"
        index_candidate = index_dir / f"{name}.parquet"
        if index_candidate.exists():
            try:
                df_idx = pd.read_parquet(index_candidate)
                cooked = self._prepare_index_series(df_idx, sanitize_proxy=True)
                if isinstance(cooked, pd.DataFrame) and not cooked.empty:
                    candidates.append(cooked)
            except Exception:
                pass

        # For NIFTY 50, keep legacy source only as a secondary candidate.
        if str(name).lower() == "nifty_50":
            legacy = self._read_parquet("data/processed/nifty.parquet")
            cooked = self._prepare_index_series(legacy, sanitize_proxy=False)
            if isinstance(cooked, pd.DataFrame) and not cooked.empty:
                candidates.append(cooked)

        if not candidates:
            return None

        scored = []
        for c in candidates:
            latest = self._latest_timestamp(c)
            scored.append((latest or pd.Timestamp.min, len(c), c))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return scored[0][2]

    def system_execution_log(self) -> Optional[Dict[str, Any]]:
        return self._read_json("data/processed/system_execution_log.json")

    # ------------------------- reports -------------------------
    def latest_validation_reports(self) -> Dict[str, Any]:
        reports: Dict[str, Any] = {}

        stress_path = self._latest_by_mtime("reports/validation/stress_test_report_*.json")
        walk_path = self._latest_by_mtime("reports/validation/walk_forward_analysis_report_*.json")

        if stress_path is not None:
            try:
                reports["stress_test"] = json.loads(stress_path.read_text())
            except Exception:
                pass

        if walk_path is not None:
            try:
                reports["walk_forward"] = json.loads(walk_path.read_text())
            except Exception:
                pass

        return reports
