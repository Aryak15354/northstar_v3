#!/usr/bin/env python3
"""
📊 OPTIONS OBSERVER
READ-ONLY observer for options trading system.
Maps options state, positions, Greeks, and risk metrics into dashboard-ready outputs.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import sys
import os
import json
import logging
from pathlib import Path

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.append(project_root)

logger = logging.getLogger("dashboard.options_observer")

INDEX_CANDLE_FILE_MAP: Dict[str, str] = {
    "NIFTY": "nifty_50.parquet",
    "BANKNIFTY": "nifty_bank.parquet",
    "FINNIFTY": "nifty_fin_service.parquet",
    "MIDCPNIFTY": "nifty_midcap_select.parquet",
    "NIFTYIT": "nifty_it.parquet",
    "NIFTYAUTO": "nifty_auto.parquet",
    "NIFTYFMCG": "nifty_fmcg.parquet",
    "NIFTYMETAL": "nifty_metal.parquet",
    "NIFTYPHARMA": "nifty_pharma.parquet",
    "NIFTYREALTY": "nifty_realty.parquet",
    "NIFTYENERGY": "nifty_energy.parquet",
    "NIFTYPSU": "nifty_psu.parquet",
    "NIFTY100": "nifty_100.parquet",
    "NIFTY500": "nifty_500.parquet",
}


class OptionsObserver:
    """
    READ-ONLY observer for options trading system.
    Subscribes to options events from event bus and provides
    dashboard-ready data structures for display.
    """
    
    def __init__(self, unified_state=None, event_bus=None):
        """
        Initialize options observer
        
        Args:
            unified_state: V3 UnifiedState instance (optional)
            event_bus: V3 EventBus instance (optional)
        """
        self.state = unified_state
        self.event_bus = event_bus
        
        # Dashboard state cache
        self.current_regime = None
        self.regime_metrics = {}
        self.active_positions = []
        self.closed_positions = []
        self.portfolio_greeks_history = []
        self.kill_switch_status = {}
        self.risk_metrics = {}
        self.trade_eligibility = {}
        self._persisted_state_path = Path(project_root) / "data/options/live/options_dashboard_state.json"
        self._runtime_state_path = Path(project_root) / "data/options/live/options_runtime_state.json"
        self._market_data_path = Path(project_root) / "data/options/live/market_data_latest.json"
        self._options_historical_dir = Path(project_root) / "data/options/historical"
        self._options_chains_cache_dir = Path(project_root) / "data/options/chains_cache"
        self._trade_ledger_path = Path(project_root) / "data/options/trade_ledger.parquet"
        self._opportunity_surface_path = Path(project_root) / "data/processed/opportunity_surface.parquet"
        self._index_data_dir = Path(project_root) / "data/processed/index_data"
        self._raw_prices_daily_dir = Path(project_root) / "data/raw/prices_daily"
        self._backtest_reports_dir = Path(project_root) / "data/options/backtest_reports"
        self._sentiment_summary_path = Path(project_root) / "data/sentiment/v3/v3_sentiment_summary.json"
        self._sentiment_market_path = Path(project_root) / "data/sentiment/v3/market_sentiment_india.parquet"
        self._sentiment_loop_status_path = Path(project_root) / "data/sentiment/v3/sentiment_loop_status.json"
        self._options_engine_log_path = Path(project_root) / "logs/options_integrated_engine.log"
        self._centralized_pnl_path = Path(project_root) / "data/processed/v3_centralized_pnl.json"
        self._centralized_pnl_series_path = Path(project_root) / "data/processed/v3_centralized_pnl_timeseries.parquet"

        self._historical_health_cache: Dict[str, Any] = {}
        self._historical_health_cache_ts: Optional[datetime] = None
        self._loop_health_cache: Dict[str, Any] = {}
        self._loop_health_cache_ts: Optional[datetime] = None
        self._opportunity_cache: Dict[str, Any] = {}
        self._opportunity_cache_ts: Optional[datetime] = None
        self._backtest_cache: Dict[str, Any] = {}
        self._backtest_cache_ts: Optional[datetime] = None
        self._candle_cache: Dict[str, Dict[str, Any]] = {}
        self._candle_cache_ts: Dict[str, datetime] = {}
        
        # Subscribe to options events if event bus available
        if self.event_bus:
            self._subscribe_to_events()
        
        logger.info("OptionsObserver initialized")

    @staticmethod
    def _normalize_greek_payload(payload: Dict[str, Any]) -> Dict[str, float]:
        if not isinstance(payload, dict):
            return {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}
        return {
            'delta': float(payload.get('delta', 0.0) or 0.0),
            'gamma': float(payload.get('gamma', 0.0) or 0.0),
            'theta': float(payload.get('theta', 0.0) or 0.0),
            'vega': float(payload.get('vega', 0.0) or 0.0),
        }

    @staticmethod
    def _has_nonzero_greeks(greeks: Dict[str, float], eps: float = 1e-9) -> bool:
        if not isinstance(greeks, dict):
            return False
        for key in ('delta', 'gamma', 'theta', 'vega'):
            try:
                if abs(float(greeks.get(key, 0.0) or 0.0)) > eps:
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _normalize_violations(value: Any) -> List[str]:
        if isinstance(value, list):
            out: List[str] = []
            for v in value:
                txt = str(v).strip()
                if txt:
                    out.append(txt)
            return out
        if isinstance(value, str):
            txt = value.strip()
            if txt and txt.lower() not in {'n/a', 'na', 'none', 'null', 'unknown', 'nan'}:
                return [txt]
        return []

    def _resolve_decision_reason(self, row: Dict[str, Any], default: str = "N/A") -> str:
        if not isinstance(row, dict):
            return default

        reason = row.get('reason')
        if reason is not None:
            txt = str(reason).strip()
            if txt and txt.lower() not in {'n/a', 'na', 'none', 'null', 'unknown', 'nan'}:
                return txt

        violations = self._normalize_violations(row.get('violations'))
        if not violations:
            eligibility = row.get('eligibility')
            if isinstance(eligibility, dict):
                violations = self._normalize_violations(eligibility.get('violations'))
        if violations:
            return "; ".join(violations)

        for key in ("status_reason", "message", "error", "detail"):
            value = row.get(key)
            if value is None:
                continue
            txt = str(value).strip()
            if txt and txt.lower() not in {'n/a', 'na', 'none', 'null', 'unknown', 'nan'}:
                return txt

        selector = row.get("strategy_selector")
        if isinstance(selector, dict):
            sel_reason = selector.get("reason")
            if sel_reason is not None:
                txt = str(sel_reason).strip()
                if txt and txt.lower() not in {'n/a', 'na', 'none', 'null', 'unknown', 'nan'}:
                    return txt

        status = str(row.get('status', '') or '').strip().lower()
        if status.startswith('rejected'):
            return "Rejected by eligibility checks (reason unavailable)"
        if status.startswith('blocked'):
            return "Blocked by control rules (reason unavailable)"
        return default

    def _enrich_decision_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(row, dict):
            return {}
        out = dict(row)
        normalized_violations = self._normalize_violations(
            out.get('violations', (out.get('eligibility') or {}).get('violations') if isinstance(out.get('eligibility'), dict) else [])
        )
        out['violations'] = normalized_violations
        out['reason'] = self._resolve_decision_reason(out)
        return out

    @staticmethod
    def _to_datetime(value: Any) -> Optional[datetime]:
        """Best-effort timestamp parsing for mixed payload/file formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            ts = pd.to_datetime(value, errors="coerce")
            if pd.isna(ts):
                return None
            if isinstance(ts, pd.Timestamp):
                return ts.to_pydatetime()
        except Exception:
            return None
        return None

    @staticmethod
    def _iso_or_none(value: Any) -> Optional[str]:
        dt = OptionsObserver._to_datetime(value)
        if dt is None:
            return None
        try:
            return dt.isoformat()
        except Exception:
            return None

    @staticmethod
    def _file_mtime(path: Path) -> Optional[datetime]:
        if not path.exists():
            return None
        try:
            return datetime.fromtimestamp(path.stat().st_mtime)
        except Exception:
            return None

    @staticmethod
    def _freshness(
        timestamp: Optional[datetime],
        expected_interval_minutes: float = 5.0,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current = now or datetime.now().astimezone()
        if timestamp is None:
            return {"status": "missing", "age_minutes": None}
        try:
            local_tz = datetime.now().astimezone().tzinfo
            current_ts = pd.Timestamp(current)
            target_ts = pd.Timestamp(timestamp)
            current_local = current_ts.tz_localize(local_tz) if current_ts.tzinfo is None else current_ts.tz_convert(local_tz)
            target_local = target_ts.tz_localize(local_tz) if target_ts.tzinfo is None else target_ts.tz_convert(local_tz)
            current_utc = current_local.tz_convert("UTC")
            target_utc = target_local.tz_convert("UTC")
            age_minutes = max(0.0, float((current_utc - target_utc).total_seconds()) / 60.0)
        except Exception:
            return {"status": "missing", "age_minutes": None}
        if age_minutes <= max(2.0, expected_interval_minutes * 1.8):
            status = "fresh"
        elif age_minutes <= max(8.0, expected_interval_minutes * 4.0):
            status = "lagging"
        else:
            status = "stale"
        return {"status": status, "age_minutes": age_minutes}

    @staticmethod
    def _safe_json_read(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _pick_sample_files(files: List[Path], max_files: int = 24) -> List[Path]:
        if len(files) <= max_files:
            return files
        if max_files <= 1:
            return [files[0]]
        step = float(len(files) - 1) / float(max_files - 1)
        idxs = sorted({int(round(i * step)) for i in range(max_files)})
        return [files[i] for i in idxs if 0 <= i < len(files)]

    def _sample_chain_quality(self, files: List[Path], max_files: int = 24) -> Dict[str, Any]:
        sampled = self._pick_sample_files(files, max_files=max_files)
        metrics = {
            "sampled_files": len(sampled),
            "sampled_rows": 0,
            "ask_lt_bid": 0,
            "negative_ltp": 0,
            "delta_out_of_range": 0,
            "iv_out_of_range": 0,
            "sample_start": None,
            "sample_end": None,
        }
        ts_start: Optional[datetime] = None
        ts_end: Optional[datetime] = None

        for path in sampled:
            try:
                df = pd.read_parquet(path)
            except Exception:
                continue
            if df is None or df.empty:
                continue

            metrics["sampled_rows"] += int(len(df))
            cols = set(df.columns)

            if {"bid", "ask"}.issubset(cols):
                bid = pd.to_numeric(df["bid"], errors="coerce")
                ask = pd.to_numeric(df["ask"], errors="coerce")
                metrics["ask_lt_bid"] += int((ask < bid).fillna(False).sum())

            if "ltp" in cols:
                ltp = pd.to_numeric(df["ltp"], errors="coerce")
                metrics["negative_ltp"] += int((ltp < 0).fillna(False).sum())

            if "delta" in cols:
                delta = pd.to_numeric(df["delta"], errors="coerce")
                metrics["delta_out_of_range"] += int((delta.abs() > 1.25).fillna(False).sum())

            if "iv" in cols:
                iv = pd.to_numeric(df["iv"], errors="coerce")
                metrics["iv_out_of_range"] += int(((iv < 0) | (iv > 5)).fillna(False).sum())

            ts_col = next((c for c in ("timestamp", "date", "Date") if c in cols), None)
            if ts_col:
                # Force a unified timezone to avoid naive/aware comparison errors.
                ts = pd.to_datetime(df[ts_col], errors="coerce", utc=True).dropna()
                if not ts.empty:
                    cur_start = ts.min().to_pydatetime()
                    cur_end = ts.max().to_pydatetime()
                    ts_start = cur_start if ts_start is None else min(ts_start, cur_start)
                    ts_end = cur_end if ts_end is None else max(ts_end, cur_end)

        metrics["sample_start"] = ts_start.isoformat() if ts_start else None
        metrics["sample_end"] = ts_end.isoformat() if ts_end else None
        return metrics

    @staticmethod
    def _normalize_symbol_from_file(path: Path) -> Optional[str]:
        name = path.name
        suffix = "_option_chains.parquet"
        if not name.endswith(suffix):
            return None
        symbol = name[: -len(suffix)].strip().upper()
        return symbol or None

    def _resolve_manifest(self, interval_dir: Path) -> Optional[Path]:
        preferred = [
            interval_dir / "upstox_universe_manifest_latest.json",
            interval_dir / "groww_universe_manifest_latest.json",
        ]
        existing = [p for p in preferred if p.exists()]
        if existing:
            return max(existing, key=lambda p: p.stat().st_mtime)

        candidates = sorted(interval_dir.glob("*_universe_manifest_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None

    def _scan_historical_interval(self, interval: str, interval_dir: Path) -> Dict[str, Any]:
        files = sorted([p for p in interval_dir.glob("*_option_chains.parquet") if p.is_file()])
        total_bytes = int(sum(p.stat().st_size for p in files)) if files else 0
        latest_file = max(files, key=lambda p: p.stat().st_mtime) if files else None

        manifest_path = self._resolve_manifest(interval_dir)
        manifest = self._safe_json_read(manifest_path) if manifest_path else {}
        status_breakdown = manifest.get("status_breakdown", {}) if isinstance(manifest.get("status_breakdown"), dict) else {}

        requested = int(manifest.get("requested_symbols", 0) or 0)
        success = int(status_breakdown.get("SUCCESS", len(files)) or 0)
        failed = int(status_breakdown.get("FAILED", 0) or 0)
        skipped_no_options = int(status_breakdown.get("SKIPPED_NO_OPTIONS", 0) or 0)
        skipped_existing = int(status_breakdown.get("SKIPPED_EXISTING", 0) or 0)
        empty = int(status_breakdown.get("EMPTY", 0) or 0)

        rows_from_manifest = None
        if isinstance(manifest.get("results"), list):
            try:
                rows_from_manifest = int(
                    sum(
                        int((r or {}).get("rows", 0) or 0)
                        for r in manifest.get("results", [])
                        if str((r or {}).get("status", "")).strip().upper() == "SUCCESS"
                    )
                )
            except Exception:
                rows_from_manifest = None

        quality = self._sample_chain_quality(files, max_files=24)

        coverage_pct = (100.0 * success / requested) if requested > 0 else None
        data_status = "ready"
        if not files:
            data_status = "missing"
        elif requested > 0 and success <= 0:
            data_status = "missing"
        elif requested > 0 and coverage_pct is not None and coverage_pct < 95.0:
            data_status = "partial"

        return {
            "interval": interval,
            "dir": str(interval_dir),
            "status": data_status,
            "files": int(len(files)),
            "size_mb": round(total_bytes / (1024.0 * 1024.0), 2),
            "latest_file": latest_file.name if latest_file else None,
            "latest_file_mtime": self._iso_or_none(self._file_mtime(latest_file)) if latest_file else None,
            "manifest_path": str(manifest_path) if manifest_path else None,
            "manifest_mtime": self._iso_or_none(self._file_mtime(manifest_path)) if manifest_path else None,
            "provider": str(manifest.get("provider", "unknown") or "unknown").lower(),
            "start_date": manifest.get("start_date"),
            "end_date": manifest.get("end_date"),
            "requested_symbols": requested,
            "status_breakdown": {
                "success": success,
                "failed": failed,
                "skipped_no_options": skipped_no_options,
                "skipped_existing": skipped_existing,
                "empty": empty,
            },
            "coverage_pct": round(coverage_pct, 2) if coverage_pct is not None else None,
            "rows_from_manifest": rows_from_manifest,
            "quality": quality,
        }

    def get_historical_universe_health(self, ttl_seconds: int = 120) -> Dict[str, Any]:
        now = datetime.now()
        if (
            self._historical_health_cache
            and self._historical_health_cache_ts
            and (now - self._historical_health_cache_ts).total_seconds() < ttl_seconds
        ):
            return self._historical_health_cache

        intervals = {
            "1d": self._scan_historical_interval("1d", self._options_historical_dir),
            "1w": self._scan_historical_interval("1w", self._options_historical_dir / "1w"),
            "5m": self._scan_historical_interval("5m", self._options_historical_dir / "5m"),
        }
        daily = intervals["1d"]

        qc_totals = {
            "sampled_files": 0,
            "sampled_rows": 0,
            "ask_lt_bid": 0,
            "negative_ltp": 0,
            "delta_out_of_range": 0,
            "iv_out_of_range": 0,
        }
        for item in intervals.values():
            q = item.get("quality", {}) if isinstance(item, dict) else {}
            qc_totals["sampled_files"] += int(q.get("sampled_files", 0) or 0)
            qc_totals["sampled_rows"] += int(q.get("sampled_rows", 0) or 0)
            qc_totals["ask_lt_bid"] += int(q.get("ask_lt_bid", 0) or 0)
            qc_totals["negative_ltp"] += int(q.get("negative_ltp", 0) or 0)
            qc_totals["delta_out_of_range"] += int(q.get("delta_out_of_range", 0) or 0)
            qc_totals["iv_out_of_range"] += int(q.get("iv_out_of_range", 0) or 0)

        universe = {
            "provider": daily.get("provider", "unknown"),
            "requested_symbols": int(daily.get("requested_symbols", 0) or 0),
            "success_symbols": int((daily.get("status_breakdown") or {}).get("success", 0) or 0),
            "skipped_no_options": int((daily.get("status_breakdown") or {}).get("skipped_no_options", 0) or 0),
            "failed_symbols": int((daily.get("status_breakdown") or {}).get("failed", 0) or 0),
            "daily_range": {
                "start": daily.get("start_date"),
                "end": daily.get("end_date"),
            },
        }

        snapshot = {
            "generated_at": now.isoformat(),
            "intervals": intervals,
            "universe": universe,
            "calculation_qc": qc_totals,
        }

        self._historical_health_cache = snapshot
        self._historical_health_cache_ts = now
        return snapshot

    def get_live_loop_health(self, expected_interval_minutes: float = 5.0, ttl_seconds: int = 30) -> Dict[str, Any]:
        now = datetime.now()
        if (
            self._loop_health_cache
            and self._loop_health_cache_ts
            and (now - self._loop_health_cache_ts).total_seconds() < ttl_seconds
        ):
            return self._loop_health_cache

        persisted = self._load_persisted_state()
        dashboard_ts = self._to_datetime(persisted.get("timestamp")) if isinstance(persisted, dict) else None
        dashboard_mtime = self._file_mtime(self._persisted_state_path)
        dashboard_ref = dashboard_ts or dashboard_mtime
        dashboard_freshness = self._freshness(
            dashboard_ref,
            expected_interval_minutes=expected_interval_minutes,
            now=now,
        )

        market_payload = self._safe_json_read(self._market_data_path)
        market_ts = self._to_datetime(market_payload.get("timestamp")) if isinstance(market_payload, dict) else None
        market_mtime = self._file_mtime(self._market_data_path)
        market_ref = market_ts or market_mtime
        market_freshness = self._freshness(
            market_ref,
            expected_interval_minutes=expected_interval_minutes,
            now=now,
        )

        sentiment_summary = self._safe_json_read(self._sentiment_summary_path)
        sentiment_loop_state = self._safe_json_read(self._sentiment_loop_status_path)
        sentiment_loop_ts = self._to_datetime(sentiment_loop_state.get("timestamp")) if isinstance(sentiment_loop_state, dict) else None
        sentiment_ts = self._to_datetime(
            sentiment_summary.get("timestamp")
            or sentiment_summary.get("created_timestamp")
            or sentiment_summary.get("run_date")
        )
        sentiment_mtime = self._file_mtime(self._sentiment_summary_path)
        sentiment_ref = sentiment_ts or sentiment_mtime
        sentiment_freshness = self._freshness(
            sentiment_ref,
            expected_interval_minutes=expected_interval_minutes,
            now=now,
        )

        market_sentiment_last = None
        if self._sentiment_market_path.exists():
            try:
                sdf = pd.read_parquet(self._sentiment_market_path)
                if isinstance(sdf, pd.DataFrame) and not sdf.empty:
                    date_col = next((c for c in ("date", "Date", "timestamp") if c in sdf.columns), None)
                    if date_col:
                        dts = pd.to_datetime(sdf[date_col], errors="coerce").dropna()
                        if not dts.empty:
                            market_sentiment_last = dts.max().to_pydatetime().isoformat()
            except Exception:
                market_sentiment_last = None

        options_log_mtime = self._file_mtime(self._options_engine_log_path)
        sentiment_loop_freshness = self._freshness(
            sentiment_loop_ts,
            expected_interval_minutes=expected_interval_minutes,
            now=now,
        ) if sentiment_loop_ts else {"status": "missing", "age_minutes": None}

        overall = "healthy"
        components = [
            dashboard_freshness.get("status"),
            market_freshness.get("status"),
            sentiment_freshness.get("status"),
        ]
        if sentiment_loop_freshness.get("status") != "missing":
            components.append(sentiment_loop_freshness.get("status"))
        if any(s == "stale" for s in components):
            overall = "stale"
        elif any(s == "lagging" for s in components):
            overall = "lagging"
        elif any(s == "missing" for s in components):
            overall = "missing"

        snapshot = {
            "generated_at": now.isoformat(),
            "expected_interval_minutes": expected_interval_minutes,
            "overall_status": overall,
            "options_dashboard_state": {
                "path": str(self._persisted_state_path),
                "timestamp": self._iso_or_none(dashboard_ref),
                **dashboard_freshness,
            },
            "market_data": {
                "path": str(self._market_data_path),
                "timestamp": self._iso_or_none(market_ref),
                **market_freshness,
            },
            "sentiment_cycle": {
                "path": str(self._sentiment_summary_path),
                "timestamp": self._iso_or_none(sentiment_ref),
                "summary_status": str(sentiment_summary.get("status", "") or "").lower() if isinstance(sentiment_summary, dict) else "",
                "summary_message": str(sentiment_summary.get("message", "") or "") if isinstance(sentiment_summary, dict) else "",
                "market_last_date": market_sentiment_last,
                **sentiment_freshness,
            },
            "sentiment_loop": {
                "path": str(self._sentiment_loop_status_path),
                "timestamp": self._iso_or_none(sentiment_loop_ts),
                "last_status": str(sentiment_loop_state.get("status", "") or "").lower() if isinstance(sentiment_loop_state, dict) else "",
                **sentiment_loop_freshness,
            },
            "options_engine_log_mtime": self._iso_or_none(options_log_mtime),
        }

        self._loop_health_cache = snapshot
        self._loop_health_cache_ts = now
        return snapshot

    def get_opportunity_surface_summary(self, top_n: int = 16, ttl_seconds: int = 120) -> Dict[str, Any]:
        now = datetime.now()
        if (
            self._opportunity_cache
            and self._opportunity_cache_ts
            and (now - self._opportunity_cache_ts).total_seconds() < ttl_seconds
        ):
            return self._opportunity_cache

        payload: Dict[str, Any] = {
            "available": False,
            "path": str(self._opportunity_surface_path),
            "rows": 0,
            "score_column": None,
            "top": [],
            "type_distribution": [],
            "updated_at": self._iso_or_none(self._file_mtime(self._opportunity_surface_path)),
        }

        if self._opportunity_surface_path.exists():
            try:
                df = pd.read_parquet(self._opportunity_surface_path)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    score_col = next(
                        (
                            c
                            for c in (
                                "regime_adjusted_score",
                                "pulse_weighted_score",
                                "northstar_score",
                                "score",
                            )
                            if c in df.columns
                        ),
                        None,
                    )
                    payload["available"] = True
                    payload["rows"] = int(len(df))
                    payload["score_column"] = score_col

                    if score_col:
                        d = df.copy()
                        d[score_col] = pd.to_numeric(d[score_col], errors="coerce")
                        d = d.dropna(subset=[score_col]).sort_values(score_col, ascending=False)
                    else:
                        d = df.copy().head(top_n)

                    top_cols = [c for c in ("ticker", "Company Name", "opportunity_type", "regime_adjusted_score", "pulse_weighted_score", "northstar_score", "in_opportunity_zone") if c in d.columns]
                    top_df = d[top_cols].head(top_n).copy() if top_cols else d.head(top_n).copy()
                    if "ticker" in top_df.columns:
                        top_df["underlying"] = top_df["ticker"].astype(str).str.replace(".NS", "", regex=False).str.upper()
                    payload["top"] = top_df.to_dict("records")

                    if "opportunity_type" in df.columns:
                        type_dist = (
                            df["opportunity_type"]
                            .astype(str)
                            .value_counts(dropna=False)
                            .reset_index()
                        )
                        type_dist.columns = ["opportunity_type", "count"]
                        payload["type_distribution"] = type_dist.head(12).to_dict("records")
            except Exception as e:
                payload["error"] = str(e)

        self._opportunity_cache = payload
        self._opportunity_cache_ts = now
        return payload

    def get_available_chain_underlyings(self, limit: int = 600) -> List[str]:
        symbols: List[str] = []
        if self._options_chains_cache_dir.exists():
            for p in self._options_chains_cache_dir.glob("*.parquet"):
                prefix = p.stem.split("_")[0].strip().upper()
                if prefix and prefix not in symbols:
                    symbols.append(prefix)
        if self._options_historical_dir.exists():
            for p in self._options_historical_dir.glob("*_option_chains.parquet"):
                sym = self._normalize_symbol_from_file(p)
                if sym and sym not in symbols:
                    symbols.append(sym)
        return sorted(symbols)[:limit]

    def _latest_chain_file(self, underlying: str) -> Tuple[Optional[Path], str]:
        symbol = str(underlying or "").strip().upper()
        if not symbol:
            return None, "none"
        cache_files = sorted(self._options_chains_cache_dir.glob(f"{symbol}_*.parquet"), key=lambda p: p.stat().st_mtime)
        if cache_files:
            return cache_files[-1], "chains_cache"

        hist_file = self._options_historical_dir / f"{symbol.lower()}_option_chains.parquet"
        if hist_file.exists():
            return hist_file, "historical_1d"
        return None, "none"

    def get_chain_snapshot(self, underlying: str, strikes_around_atm: int = 10) -> Dict[str, Any]:
        file_path, source = self._latest_chain_file(underlying)
        symbol = str(underlying or "").strip().upper()
        if not file_path:
            return {"available": False, "underlying": symbol, "source": source, "rows": []}

        try:
            df = pd.read_parquet(file_path)
        except Exception as e:
            return {
                "available": False,
                "underlying": symbol,
                "source": source,
                "file_path": str(file_path),
                "error": str(e),
                "rows": [],
            }

        if df is None or df.empty:
            return {"available": False, "underlying": symbol, "source": source, "file_path": str(file_path), "rows": []}

        # Live cache snapshots can be intentionally compact. Fall back to richer
        # historical chain for dashboard visualization when cache is too sparse.
        if source == "chains_cache":
            hist_fallback = self._options_historical_dir / f"{symbol.lower()}_option_chains.parquet"
            if hist_fallback.exists():
                try:
                    hist_df = pd.read_parquet(hist_fallback)
                    if isinstance(hist_df, pd.DataFrame) and len(hist_df) > max(300, len(df) * 3):
                        df = hist_df
                        source = "historical_1d_fallback"
                        file_path = hist_fallback
                except Exception:
                    pass

        work = df.copy()
        cols = set(work.columns)
        ts_col = next((c for c in ("timestamp", "date", "Date") if c in cols), None)
        asof = None
        if ts_col:
            ts = pd.to_datetime(work[ts_col], errors="coerce", utc=True)
            valid = ts.notna()
            if valid.any():
                max_ts = ts[valid].max()
                work = work.loc[ts == max_ts].copy()
                asof = max_ts.to_pydatetime().isoformat()

        expiry_col = next((c for c in ("expiry", "expiry_date") if c in work.columns), None)
        expiry_selected = None
        if expiry_col:
            exp = pd.to_datetime(work[expiry_col], errors="coerce", utc=True)
            exp = exp.dt.tz_convert("UTC").dt.tz_localize(None)
            if exp.notna().any():
                today = pd.Timestamp.utcnow().normalize().tz_localize(None)
                unique_exp = sorted(exp.dropna().unique())
                future = [x for x in unique_exp if x >= today]
                if future:
                    # Prefer a near expiry with enough strikes for a meaningful chain view.
                    candidates = future[:4] if len(future) > 4 else future
                    expiry_selected = max(candidates, key=lambda d: int((exp == d).sum()))
                else:
                    expiry_selected = max(unique_exp, key=lambda d: int((exp == d).sum()))
                work = work.loc[exp == expiry_selected].copy()

        strike_col = "strike" if "strike" in work.columns else ("strike_price" if "strike_price" in work.columns else None)
        opt_col = "option_type" if "option_type" in work.columns else ("instrument_type" if "instrument_type" in work.columns else None)
        if not strike_col or not opt_col:
            return {
                "available": False,
                "underlying": symbol,
                "source": source,
                "file_path": str(file_path),
                "error": "missing strike/option_type columns",
                "rows": [],
            }

        work[strike_col] = pd.to_numeric(work[strike_col], errors="coerce")
        work = work.dropna(subset=[strike_col])
        if work.empty:
            return {"available": False, "underlying": symbol, "source": source, "file_path": str(file_path), "rows": []}

        if "underlying_price" in work.columns:
            spot_series = pd.to_numeric(work["underlying_price"], errors="coerce").dropna()
            spot = float(spot_series.median()) if not spot_series.empty else None
        else:
            spot = None
        if spot is None or not np.isfinite(spot):
            spot = float(work[strike_col].median())

        strikes = sorted(work[strike_col].dropna().unique().tolist())
        if not strikes:
            return {"available": False, "underlying": symbol, "source": source, "file_path": str(file_path), "rows": []}

        atm = min(strikes, key=lambda s: abs(float(s) - float(spot)))
        atm_idx = strikes.index(atm)
        lo = max(0, atm_idx - int(max(3, strikes_around_atm)))
        hi = min(len(strikes), atm_idx + int(max(3, strikes_around_atm)) + 1)
        selected_strikes = set(strikes[lo:hi])
        view = work[work[strike_col].isin(selected_strikes)].copy()

        view["_ot"] = view[opt_col].astype(str).str.upper().str[:1]
        call_df = view[view["_ot"] == "C"]
        put_df = view[view["_ot"] == "P"]

        oi_col = "oi" if "oi" in view.columns else None
        vol_col = "volume" if "volume" in view.columns else None
        pcr_oi = None
        pcr_volume = None
        if oi_col:
            call_oi = float(pd.to_numeric(call_df[oi_col], errors="coerce").fillna(0.0).sum())
            put_oi = float(pd.to_numeric(put_df[oi_col], errors="coerce").fillna(0.0).sum())
            if call_oi > 0:
                pcr_oi = put_oi / call_oi
        if vol_col:
            call_vol = float(pd.to_numeric(call_df[vol_col], errors="coerce").fillna(0.0).sum())
            put_vol = float(pd.to_numeric(put_df[vol_col], errors="coerce").fillna(0.0).sum())
            if call_vol > 0:
                pcr_volume = put_vol / call_vol

        rows: List[Dict[str, Any]] = []
        fields = ("ltp", "bid", "ask", "oi", "volume", "iv", "delta", "theta", "vega")
        for strike in sorted(selected_strikes):
            row: Dict[str, Any] = {"strike": float(strike)}
            ce = call_df[call_df[strike_col] == strike]
            pe = put_df[put_df[strike_col] == strike]
            ce_row = ce.iloc[0].to_dict() if not ce.empty else {}
            pe_row = pe.iloc[0].to_dict() if not pe.empty else {}
            for f in fields:
                row[f"ce_{f}"] = ce_row.get(f)
                row[f"pe_{f}"] = pe_row.get(f)
            rows.append(row)

        return {
            "available": True,
            "underlying": symbol,
            "source": source,
            "file_path": str(file_path),
            "asof": asof or self._iso_or_none(self._file_mtime(file_path)),
            "expiry": expiry_selected.date().isoformat() if expiry_selected is not None else None,
            "spot": float(spot),
            "atm_strike": float(atm),
            "strikes": int(len(selected_strikes)),
            "rows": rows,
            "pcr_oi": pcr_oi,
            "pcr_volume": pcr_volume,
        }

    @staticmethod
    def _normalize_candle_frame(df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        frame = df.copy()
        cols_lower = {str(c).lower(): c for c in frame.columns}

        ts_col = None
        for cand in ("timestamp", "datetime", "date"):
            if cand in cols_lower:
                ts_col = cols_lower[cand]
                break
        if ts_col is None and isinstance(frame.index, pd.DatetimeIndex):
            idx_name = str(frame.index.name) if frame.index.name else "index"
            frame = frame.reset_index().rename(columns={idx_name: "timestamp"})
            ts_col = "timestamp"
        elif ts_col is None and frame.index.name:
            idx_name = str(frame.index.name)
            if idx_name.lower() in {"date", "datetime", "timestamp"}:
                frame = frame.reset_index().rename(columns={idx_name: "timestamp"})
                ts_col = "timestamp"

        if ts_col is None:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        rename_map = {ts_col: "timestamp"}
        for target in ("open", "high", "low", "close", "volume"):
            src = cols_lower.get(target)
            if src is not None:
                rename_map[src] = target
        if cols_lower.get("adj_close") is not None and "close" not in rename_map.values():
            rename_map[cols_lower["adj_close"]] = "close"

        frame = frame.rename(columns=rename_map)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
        frame = frame.dropna(subset=["timestamp"])
        if frame.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        for col in ("open", "high", "low", "close", "volume"):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        if "close" not in frame.columns:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        frame = frame.sort_values("timestamp")
        frame["close"] = frame["close"].ffill()
        frame["open"] = frame["open"] if "open" in frame.columns else frame["close"].shift(1)
        frame["open"] = pd.to_numeric(frame["open"], errors="coerce").fillna(frame["close"])
        frame["high"] = frame["high"] if "high" in frame.columns else frame[["open", "close"]].max(axis=1)
        frame["low"] = frame["low"] if "low" in frame.columns else frame[["open", "close"]].min(axis=1)
        frame["high"] = pd.to_numeric(frame["high"], errors="coerce").fillna(frame[["open", "close"]].max(axis=1))
        frame["low"] = pd.to_numeric(frame["low"], errors="coerce").fillna(frame[["open", "close"]].min(axis=1))
        if "volume" not in frame.columns:
            frame["volume"] = np.nan
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
        frame = frame.dropna(subset=["close"])
        if frame.empty:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        frame = frame[["timestamp", "open", "high", "low", "close", "volume"]]
        frame = frame.drop_duplicates(subset=["timestamp"], keep="last")
        return frame.sort_values("timestamp")

    @staticmethod
    def _resample_candle_frame(df: pd.DataFrame, interval: str) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return df
        itv = str(interval or "1d").strip().lower()
        if itv == "1d":
            out = df.copy()
            out["date"] = pd.to_datetime(out["timestamp"], errors="coerce").dt.floor("D")
            out = out.dropna(subset=["date"]).set_index("date")
            agg = out.resample("1D").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            })
            agg = agg.dropna(subset=["close"]).reset_index().rename(columns={"date": "timestamp"})
            return agg

        if itv == "1w":
            out = df.copy()
            out["date"] = pd.to_datetime(out["timestamp"], errors="coerce")
            out = out.dropna(subset=["date"]).set_index("date")
            agg = out.resample("W-FRI").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            })
            agg = agg.dropna(subset=["close"]).reset_index().rename(columns={"date": "timestamp"})
            return agg

        if itv == "5m":
            out = df.copy()
            out["date"] = pd.to_datetime(out["timestamp"], errors="coerce")
            out = out.dropna(subset=["date"]).set_index("date")
            agg = out.resample("5min").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            })
            agg = agg.dropna(subset=["close"]).reset_index().rename(columns={"date": "timestamp"})
            return agg

        return df

    def _load_index_candles(self, underlying: str) -> Tuple[pd.DataFrame, str]:
        symbol = str(underlying or "").strip().upper()
        candidates: List[Path] = []

        mapped = INDEX_CANDLE_FILE_MAP.get(symbol)
        if mapped:
            candidates.append(self._index_data_dir / mapped)
        if symbol.startswith("NIFTY"):
            alias = symbol.replace("NIFTY", "nifty_").lower() + ".parquet"
            candidates.append(self._index_data_dir / alias)
        if symbol == "NIFTY":
            candidates.append(Path(project_root) / "data/processed/nifty.parquet")

        for path in candidates:
            if not path.exists():
                continue
            try:
                raw = pd.read_parquet(path)
                normalized = self._normalize_candle_frame(raw)
                if not normalized.empty:
                    return normalized, f"index_data:{path.name}"
            except Exception:
                continue

        return pd.DataFrame(), "index_data:missing"

    def _load_stock_candles(self, underlying: str) -> Tuple[pd.DataFrame, str]:
        symbol = str(underlying or "").strip().upper()
        if not symbol:
            return pd.DataFrame(), "stock_data:missing_symbol"

        candidates = [
            self._raw_prices_daily_dir / f"{symbol}.NS.csv",
            self._raw_prices_daily_dir / f"{symbol}.BO.csv",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                raw = pd.read_csv(path)
                normalized = self._normalize_candle_frame(raw)
                if not normalized.empty:
                    return normalized, f"raw_prices_daily:{path.name}"
            except Exception:
                continue

        # Fallback to consolidated prices parquet.
        prices_path = Path(project_root) / "data/processed/prices.parquet"
        if prices_path.exists():
            try:
                raw = pd.read_parquet(prices_path, filters=[("ticker", "=", f"{symbol}.NS")])
                normalized = self._normalize_candle_frame(raw)
                if not normalized.empty:
                    return normalized, "processed_prices:prices.parquet"
            except Exception:
                pass

        return pd.DataFrame(), "stock_data:missing"

    def _load_chain_spot_candles(self, underlying: str, interval_hint: str = "1d") -> Tuple[pd.DataFrame, str]:
        symbol = str(underlying or "").strip().upper()
        itv = str(interval_hint or "1d").strip().lower()
        candidates: List[Path] = []

        if itv == "5m":
            candidates.append(self._options_historical_dir / "5m" / f"{symbol.lower()}_option_chains.parquet")
            cache_files = sorted(
                self._options_chains_cache_dir.glob(f"{symbol}_*.parquet"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            candidates.extend(cache_files[:2])
        elif itv == "1w":
            candidates.append(self._options_historical_dir / "1w" / f"{symbol.lower()}_option_chains.parquet")
            candidates.append(self._options_historical_dir / f"{symbol.lower()}_option_chains.parquet")
        else:
            candidates.append(self._options_historical_dir / f"{symbol.lower()}_option_chains.parquet")

        for path in candidates:
            if not path.exists():
                continue
            try:
                raw = pd.read_parquet(path)
            except Exception:
                continue
            if raw is None or raw.empty or "underlying_price" not in raw.columns:
                continue

            ts_col = next((c for c in ("timestamp", "date", "Date") if c in raw.columns), None)
            if ts_col is None:
                continue
            work = raw[[ts_col, "underlying_price"]].copy()
            work["timestamp"] = pd.to_datetime(work[ts_col], errors="coerce")
            work["close"] = pd.to_numeric(work["underlying_price"], errors="coerce")
            work = work.dropna(subset=["timestamp", "close"])
            if work.empty:
                continue

            grouped = work.groupby("timestamp", as_index=False)["close"].median().sort_values("timestamp")
            grouped["open"] = grouped["close"].shift(1).fillna(grouped["close"])
            grouped["high"] = grouped[["open", "close"]].max(axis=1)
            grouped["low"] = grouped[["open", "close"]].min(axis=1)
            grouped["volume"] = np.nan
            out = grouped[["timestamp", "open", "high", "low", "close", "volume"]]
            if not out.empty:
                return out, f"option_chain_spot:{path.name}"

        return pd.DataFrame(), "option_chain_spot:missing"

    def get_underlying_candles(
        self,
        underlying: str,
        interval: str = "1d",
        lookback_bars: int = 220,
        ttl_seconds: int = 120,
    ) -> Dict[str, Any]:
        symbol = str(underlying or "").strip().upper()
        itv = str(interval or "1d").strip().lower()
        key = f"{symbol}|{itv}|{int(max(20, lookback_bars))}"

        now = datetime.now()
        ts = self._candle_cache_ts.get(key)
        if key in self._candle_cache and ts and (now - ts).total_seconds() < ttl_seconds:
            return self._candle_cache[key]

        frame = pd.DataFrame()
        source = "none"

        if symbol in INDEX_CANDLE_FILE_MAP or symbol.startswith("NIFTY"):
            frame, source = self._load_index_candles(symbol)

        if frame.empty:
            frame, source = self._load_stock_candles(symbol)

        if frame.empty:
            frame, source = self._load_chain_spot_candles(symbol, interval_hint=itv)

        if frame.empty:
            out = {
                "available": False,
                "underlying": symbol,
                "interval": itv,
                "source": source,
                "rows": [],
            }
            self._candle_cache[key] = out
            self._candle_cache_ts[key] = now
            return out

        resampled = self._resample_candle_frame(frame, interval=itv)
        if resampled.empty:
            resampled = frame
        resampled = resampled.sort_values("timestamp")
        bars = int(max(20, lookback_bars))
        if len(resampled) > bars:
            resampled = resampled.tail(bars)

        latest = resampled.iloc[-1].to_dict() if not resampled.empty else {}
        rows = resampled.copy()
        rows["timestamp"] = pd.to_datetime(rows["timestamp"], errors="coerce")
        rows = rows.dropna(subset=["timestamp"])
        rows["timestamp"] = rows["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")

        out = {
            "available": not rows.empty,
            "underlying": symbol,
            "interval": itv,
            "source": source,
            "rows": rows.to_dict("records"),
            "latest": {
                "timestamp": str(pd.to_datetime(latest.get("timestamp"), errors="coerce")) if latest else None,
                "open": float(latest.get("open", 0.0) or 0.0) if latest else None,
                "high": float(latest.get("high", 0.0) or 0.0) if latest else None,
                "low": float(latest.get("low", 0.0) or 0.0) if latest else None,
                "close": float(latest.get("close", 0.0) or 0.0) if latest else None,
            },
        }
        self._candle_cache[key] = out
        self._candle_cache_ts[key] = now
        return out

    def get_backtest_snapshot(self, ttl_seconds: int = 90) -> Dict[str, Any]:
        now = datetime.now()
        if (
            self._backtest_cache
            and self._backtest_cache_ts
            and (now - self._backtest_cache_ts).total_seconds() < ttl_seconds
        ):
            return self._backtest_cache

        summary_path = self._backtest_reports_dir / "options_backtest_summary_latest.json"
        trades_path = self._backtest_reports_dir / "options_backtest_trades_latest.parquet"
        equity_path = self._backtest_reports_dir / "options_backtest_equity_latest.parquet"

        if not summary_path.exists():
            candidates = sorted(
                self._backtest_reports_dir.glob("options_backtest_summary_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                summary_path = candidates[0]
        if not trades_path.exists():
            candidates = sorted(
                self._backtest_reports_dir.glob("options_backtest_trades_*.parquet"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                trades_path = candidates[0]
        if not equity_path.exists():
            candidates = sorted(
                self._backtest_reports_dir.glob("options_backtest_equity_*.parquet"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                equity_path = candidates[0]

        payload: Dict[str, Any] = {
            "available": False,
            "updated_at": None,
            "summary": {},
            "equity_curve": [],
            "recent_trades": [],
            "strategy_breakdown": [],
            "underlying_breakdown": [],
            "paths": {
                "summary": str(summary_path),
                "trades": str(trades_path),
                "equity": str(equity_path),
            },
        }

        summary = self._safe_json_read(summary_path)
        if isinstance(summary, dict) and summary:
            payload["summary"] = summary
            payload["updated_at"] = summary.get("generated_at") or self._iso_or_none(self._file_mtime(summary_path))

        trades_df = pd.DataFrame()
        if trades_path.exists():
            try:
                trades_df = pd.read_parquet(trades_path)
            except Exception:
                trades_df = pd.DataFrame()

        if isinstance(trades_df, pd.DataFrame) and not trades_df.empty:
            t = trades_df.copy()
            for col in ("entry_time", "exit_time"):
                if col in t.columns:
                    t[col] = pd.to_datetime(t[col], errors="coerce")

            payload["recent_trades"] = t.sort_values(
                "exit_time" if "exit_time" in t.columns else "entry_time",
                ascending=False,
            ).head(25).to_dict("records")

            if "strategy" in t.columns:
                s = t["strategy"].astype(str).value_counts().reset_index()
                s.columns = ["strategy", "count"]
                payload["strategy_breakdown"] = s.to_dict("records")
            if "underlying" in t.columns:
                u = t["underlying"].astype(str).value_counts().reset_index()
                u.columns = ["underlying", "count"]
                payload["underlying_breakdown"] = u.to_dict("records")

        if equity_path.exists():
            try:
                e = pd.read_parquet(equity_path)
                if isinstance(e, pd.DataFrame) and not e.empty:
                    if "timestamp" in e.columns:
                        e["timestamp"] = pd.to_datetime(e["timestamp"], errors="coerce")
                    elif "date" in e.columns:
                        e["timestamp"] = pd.to_datetime(e["date"], errors="coerce")
                    e = e.dropna(subset=["timestamp"]).sort_values("timestamp")
                    e["timestamp"] = e["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
                    payload["equity_curve"] = e.tail(420).to_dict("records")
            except Exception:
                pass

        payload["available"] = bool(payload["summary"]) or bool(payload["recent_trades"]) or bool(payload["equity_curve"])
        if payload["updated_at"] is None:
            payload["updated_at"] = self._iso_or_none(self._file_mtime(equity_path) or self._file_mtime(trades_path))

        self._backtest_cache = payload
        self._backtest_cache_ts = now
        return payload

    def _aggregate_cycle_strategy_greeks(self, persisted: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback aggregate Greeks from latest strategy candidates in options_cycle."""
        cycle = persisted.get('options_cycle', {}) if isinstance(persisted, dict) else {}
        underlyings = cycle.get('underlyings', []) if isinstance(cycle, dict) else []
        if not isinstance(underlyings, list):
            underlyings = []

        totals = {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}
        contributors: List[str] = []
        statuses = {
            'opened_position',
            'eligible',
            'ready_to_open',
        }

        for row in underlyings:
            if not isinstance(row, dict):
                continue
            strategy = row.get('strategy')
            if not isinstance(strategy, dict):
                continue

            status = str(row.get('status', '') or '').strip().lower()
            eligibility = row.get('eligibility', {})
            is_eligible = bool(eligibility.get('is_eligible', False)) if isinstance(eligibility, dict) else False
            if status not in statuses and not is_eligible:
                continue

            greeks = self._normalize_greek_payload(strategy.get('greeks', {}))
            if not self._has_nonzero_greeks(greeks):
                continue

            for k in totals:
                totals[k] += float(greeks.get(k, 0.0) or 0.0)

            underlying = str(row.get('underlying', 'UNKNOWN') or 'UNKNOWN').strip().upper()
            if underlying:
                contributors.append(underlying)

        if self._has_nonzero_greeks(totals):
            return {
                'greeks': totals,
                'source': 'cycle_strategies',
                'contributors': sorted(set(contributors)),
            }

        return {
            'greeks': {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0},
            'source': 'none',
            'contributors': [],
        }

    def _load_persisted_state(self) -> Dict[str, Any]:
        """Load persisted options dashboard state written by live paper engine."""
        if not self._persisted_state_path.exists():
            return {}
        try:
            return json.loads(self._persisted_state_path.read_text())
        except Exception as e:
            logger.debug(f"Failed reading persisted options state: {e}")
            return {}

    def _load_runtime_state(self) -> Dict[str, Any]:
        """Load runtime state for advanced fallbacks (e.g., regime-history derived metrics)."""
        if not self._runtime_state_path.exists():
            return {}
        try:
            return json.loads(self._runtime_state_path.read_text())
        except Exception as e:
            logger.debug(f"Failed reading runtime options state: {e}")
            return {}

    @staticmethod
    def _coerce_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            out = float(value)
            if np.isnan(out):
                return None
            return out
        except Exception:
            return None

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(float(value))
        except Exception:
            return None

    def _derive_days_in_regime(self, persisted: Optional[Dict[str, Any]] = None) -> int:
        """
        Derive regime stability days from runtime regime history when explicit days field is missing.
        """
        payload = persisted if isinstance(persisted, dict) else self._load_runtime_state()
        history = payload.get("regime_history", []) if isinstance(payload, dict) else []
        if not isinstance(history, list) or not history:
            return 0

        # Use last valid regime marker as anchor.
        anchor = None
        for row in reversed(history):
            if isinstance(row, dict):
                anchor = str(row.get("routed_regime") or row.get("regime") or "").strip().lower()
                if anchor:
                    break
        if not anchor:
            return 0

        seen_days: set[datetime.date] = set()
        for row in reversed(history):
            if not isinstance(row, dict):
                break
            regime = str(row.get("routed_regime") or row.get("regime") or "").strip().lower()
            if regime != anchor:
                break
            dt = self._to_datetime(row.get("timestamp"))
            if dt is None:
                continue
            seen_days.add(dt.date())

        return int(len(seen_days))
    
    def _subscribe_to_events(self):
        """Subscribe to options events from event bus"""
        try:
            # Subscribe to options events
            self.event_bus.subscribe("options_regime_change", self.on_regime_change)
            self.event_bus.subscribe("options_trade_signal", self.on_trade_signal)
            self.event_bus.subscribe("options_position_opened", self.on_position_opened)
            self.event_bus.subscribe("options_position_updated", self.on_position_updated)
            self.event_bus.subscribe("options_position_closed", self.on_position_closed)
            self.event_bus.subscribe("options_kill_switch_activated", self.on_kill_switch_activated)
            self.event_bus.subscribe("options_kill_switch_cleared", self.on_kill_switch_cleared)
            self.event_bus.subscribe("options_greeks_breach", self.on_greeks_breach)
            self.event_bus.subscribe("options_edge_decay", self.on_edge_decay)
            self.event_bus.subscribe("options_eligibility_rejected", self.on_eligibility_rejected)
            
            logger.info("Subscribed to options events")
        except Exception as e:
            logger.warning(f"Failed to subscribe to events: {e}")
    
    # ------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------
    
    def on_regime_change(self, event: Dict[str, Any]) -> None:
        """Handle regime change event"""
        self.current_regime = event.get('new_regime')
        self.regime_metrics = {
            'regime': event.get('new_regime'),
            'iv_rank': event.get('iv_rank'),
            'days_in_old_regime': event.get('days_in_old_regime'),
            'reason': event.get('reason'),
            'timestamp': event.get('timestamp', datetime.now())
        }
        logger.debug(f"Regime changed to {self.current_regime}")
    
    def on_trade_signal(self, event: Dict[str, Any]) -> None:
        """Handle trade signal event"""
        # Store latest trade signal for eligibility display
        self.trade_eligibility = {
            'signal_generated': True,
            'strategy_type': event.get('strategy_type'),
            'regime': event.get('regime'),
            'edge_score': event.get('edge_score'),
            'timestamp': event.get('timestamp', datetime.now())
        }
        logger.debug(f"Trade signal: {event.get('strategy_type')}")
    
    def on_position_opened(self, event: Dict[str, Any]) -> None:
        """Handle position opened event"""
        position = {
            'position_id': event.get('position_id'),
            'strategy_type': event.get('strategy_type'),
            'max_loss': event.get('max_loss'),
            'entry_time': event.get('entry_time'),
            'legs': event.get('legs', []),
            'unrealized_pnl': 0.0,
            'current_value': 0.0,
            'greeks': {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}
        }
        self.active_positions.append(position)
        logger.info(f"Position opened: {position['position_id']}")
    
    def on_position_updated(self, event: Dict[str, Any]) -> None:
        """Handle position update event"""
        position_id = event.get('position_id')
        
        # Update active position
        for pos in self.active_positions:
            if pos['position_id'] == position_id:
                pos['unrealized_pnl'] = event.get('unrealized_pnl', 0.0)
                pos['current_value'] = event.get('current_value', 0.0)
                break
        
        # Update portfolio Greeks history
        portfolio_greeks = event.get('portfolio_greeks', {})
        if portfolio_greeks:
            self.portfolio_greeks_history.append({
                'timestamp': event.get('timestamp', datetime.now()),
                'delta': portfolio_greeks.get('delta', 0.0),
                'gamma': portfolio_greeks.get('gamma', 0.0),
                'theta': portfolio_greeks.get('theta', 0.0),
                'vega': portfolio_greeks.get('vega', 0.0)
            })
            
            # Keep only last 30 days
            cutoff_utc = pd.Timestamp.utcnow() - pd.Timedelta(days=30)
            filtered = []
            for g in self.portfolio_greeks_history:
                g_ts = pd.to_datetime(g.get('timestamp'), errors='coerce', utc=True)
                if pd.notna(g_ts) and g_ts > cutoff_utc:
                    filtered.append(g)
            self.portfolio_greeks_history = filtered
        
        logger.debug(f"Position updated: {position_id}")
    
    def on_position_closed(self, event: Dict[str, Any]) -> None:
        """Handle position closed event"""
        position_id = event.get('position_id')
        
        # Move from active to closed
        for i, pos in enumerate(self.active_positions):
            if pos['position_id'] == position_id:
                closed_pos = self.active_positions.pop(i)
                closed_pos['realized_pnl'] = event.get('realized_pnl', 0.0)
                closed_pos['net_pnl'] = event.get('net_pnl', 0.0)
                closed_pos['exit_reason'] = event.get('exit_reason')
                closed_pos['hold_duration_days'] = event.get('hold_duration_days', 0)
                self.closed_positions.append(closed_pos)
                break
        
        logger.info(f"Position closed: {position_id}")
    
    def on_kill_switch_activated(self, event: Dict[str, Any]) -> None:
        """Handle kill switch activation event"""
        self.kill_switch_status = {
            'active': True,
            'type': event.get('kill_switch_type'),
            'reason': event.get('reason'),
            'cooldown_until': event.get('cooldown_until'),
            'triggered_rules': event.get('triggered_rules', []),
            'timestamp': event.get('timestamp', datetime.now())
        }
        logger.warning(f"Kill switch activated: {event.get('reason')}")
    
    def on_kill_switch_cleared(self, event: Dict[str, Any]) -> None:
        """Handle kill switch cleared event"""
        self.kill_switch_status = {
            'active': False,
            'type': event.get('kill_switch_type'),
            'reason': event.get('reason'),
            'timestamp': event.get('timestamp', datetime.now())
        }
        logger.info(f"Kill switch cleared: {event.get('reason')}")
    
    def on_greeks_breach(self, event: Dict[str, Any]) -> None:
        """Handle Greeks breach event"""
        logger.warning(
            f"Greeks breach: {event.get('greek_type')} = {event.get('current_value')} "
            f"(threshold: {event.get('threshold')})"
        )
    
    def on_edge_decay(self, event: Dict[str, Any]) -> None:
        """Handle edge decay event"""
        logger.warning(f"Edge decay detected: {event.get('strategy_type')}")
    
    def on_eligibility_rejected(self, event: Dict[str, Any]) -> None:
        """Handle eligibility rejection event"""
        self.trade_eligibility = {
            'signal_generated': False,
            'rejected': True,
            'strategy_type': event.get('strategy_type'),
            'violations': event.get('violations', []),
            'regime': event.get('regime'),
            'timestamp': event.get('timestamp', datetime.now())
        }
        logger.info(f"Trade rejected: {len(event.get('violations', []))} violations")
    
    # ------------------------------------------------------------------
    # REGIME STATUS
    # ------------------------------------------------------------------
    
    def get_current_regime(self) -> str:
        """Get current options regime"""
        if self.current_regime:
            return self.current_regime

        persisted = self._load_persisted_state()
        if persisted:
            return str(persisted.get('current_regime', 'NO DATA'))
        
        # Fallback to state if available
        if self.state and hasattr(self.state, 'options'):
            try:
                return self.state.options.current_regime
            except Exception:
                pass
        
        return "NO DATA"
    
    def get_regime_metrics(self) -> Dict[str, Any]:
        """Get regime metrics (IV rank, trend, vol-of-vol)"""
        if self.regime_metrics:
            metrics = dict(self.regime_metrics)
            iv_rank = self._coerce_float(metrics.get("iv_rank"))
            metrics["iv_rank"] = iv_rank if iv_rank is not None else 0.0
            days = (
                self._coerce_int(metrics.get("days_in_regime"))
                or self._coerce_int(metrics.get("days_in_old_regime"))
                or self._coerce_int(metrics.get("days_in_current_regime"))
                or 0
            )
            metrics["days_in_regime"] = int(days)
            metrics["days_in_old_regime"] = int(days)
            return metrics

        persisted = self._load_persisted_state()
        if persisted:
            metrics = persisted.get("regime_metrics", {}) or {}
            if isinstance(metrics, dict):
                out = dict(metrics)
                iv_rank = (
                    self._coerce_float(out.get("iv_rank"))
                    or self._coerce_float(out.get("iv_percentile"))
                    or self._coerce_float(out.get("ivp"))
                )
                out["iv_rank"] = iv_rank if iv_rank is not None else 0.0
                days = (
                    self._coerce_int(out.get("days_in_regime"))
                    or self._coerce_int(out.get("days_in_old_regime"))
                    or self._coerce_int(out.get("days_in_current_regime"))
                    or 0
                )
                if days <= 0:
                    days = self._derive_days_in_regime(self._load_runtime_state())
                out["days_in_regime"] = int(days)
                out["days_in_old_regime"] = int(days)
                ts = self._to_datetime(out.get("timestamp") or persisted.get("timestamp"))
                out["freshness"] = self._freshness(ts, expected_interval_minutes=15.0)
                return out
            return {}
        
        # Fallback to state if available
        if self.state and hasattr(self.state, 'options'):
            try:
                return {
                    'regime': self.state.options.current_regime,
                    'iv_rank': self.state.options.regime_metrics.iv_rank,
                    'days_in_regime': self.state.options.days_in_regime,
                    'timestamp': datetime.now()
                }
            except Exception:
                pass
        
        return {}
    
    def get_regime_stability_days(self) -> int:
        """Get days in current regime"""
        if self.regime_metrics:
            return (
                self._coerce_int(self.regime_metrics.get("days_in_regime"))
                or self._coerce_int(self.regime_metrics.get("days_in_old_regime"))
                or self._coerce_int(self.regime_metrics.get("days_in_current_regime"))
                or 0
            )

        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get("regime_metrics"), dict):
            rm = persisted.get("regime_metrics", {}) or {}
            days = (
                self._coerce_int(rm.get("days_in_regime"))
                or self._coerce_int(rm.get("days_in_old_regime"))
                or self._coerce_int(rm.get("days_in_current_regime"))
                or 0
            )
            if days <= 0:
                days = self._derive_days_in_regime(self._load_runtime_state())
            return int(days)

        if self.state and hasattr(self.state, 'options'):
            try:
                return self.state.options.days_in_regime
            except Exception:
                pass
        
        return 0
    
    # ------------------------------------------------------------------
    # ACTIVE POSITIONS
    # ------------------------------------------------------------------
    
    def get_active_positions(self) -> List[Dict[str, Any]]:
        """Get list of active positions"""
        if self.active_positions:
            return self.active_positions

        persisted = self._load_persisted_state()
        if persisted:
            return persisted.get('active_positions', []) or []
        
        # Fallback to state if available
        if self.state and hasattr(self.state, 'options'):
            try:
                positions = []
                for pos_id, pos in self.state.options.open_positions.items():
                    positions.append({
                        'position_id': pos_id,
                        'strategy_type': pos.strategy_type,
                        'max_loss': pos.max_loss,
                        'entry_time': pos.entry_time,
                        'unrealized_pnl': pos.unrealized_pnl,
                        'current_value': pos.current_value,
                        'greeks': {
                            'delta': pos.greeks.delta if pos.greeks else 0.0,
                            'gamma': pos.greeks.gamma if pos.greeks else 0.0,
                            'theta': pos.greeks.theta if pos.greeks else 0.0,
                            'vega': pos.greeks.vega if pos.greeks else 0.0
                        }
                    })
                return positions
            except Exception:
                pass
        
        return []
    
    def get_active_positions_count(self) -> int:
        """Get count of active positions"""
        return len(self.get_active_positions())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized P&L across all positions"""
        positions = self.get_active_positions()
        return sum(pos.get('unrealized_pnl', 0.0) for pos in positions)
    
    # ------------------------------------------------------------------
    # PORTFOLIO GREEKS
    # ------------------------------------------------------------------

    def get_portfolio_greeks_context(self) -> Dict[str, Any]:
        """Return current portfolio Greeks plus source metadata."""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted, dict):
            pg = self._normalize_greek_payload(persisted.get('portfolio_greeks', {}))
            if self._has_nonzero_greeks(pg):
                return {'greeks': pg, 'source': 'persisted_portfolio', 'contributors': []}

        positions = self.get_active_positions()
        if positions:
            total_delta = sum(float((pos.get('greeks') or {}).get('delta', 0.0) or 0.0) for pos in positions)
            total_gamma = sum(float((pos.get('greeks') or {}).get('gamma', 0.0) or 0.0) for pos in positions)
            total_theta = sum(float((pos.get('greeks') or {}).get('theta', 0.0) or 0.0) for pos in positions)
            total_vega = sum(float((pos.get('greeks') or {}).get('vega', 0.0) or 0.0) for pos in positions)
            agg = {'delta': total_delta, 'gamma': total_gamma, 'theta': total_theta, 'vega': total_vega}
            if self._has_nonzero_greeks(agg):
                return {'greeks': agg, 'source': 'active_positions', 'contributors': []}

        cycle_ctx = self._aggregate_cycle_strategy_greeks(persisted if isinstance(persisted, dict) else {})
        if self._has_nonzero_greeks(cycle_ctx.get('greeks', {})):
            return cycle_ctx

        # Preserve persisted zero vector when everything else is absent.
        if persisted and isinstance(persisted, dict):
            pg = self._normalize_greek_payload(persisted.get('portfolio_greeks', {}))
            return {'greeks': pg, 'source': 'persisted_portfolio', 'contributors': []}

        return {
            'greeks': {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0},
            'source': 'none',
            'contributors': [],
        }
    
    def get_portfolio_greeks(self) -> Dict[str, float]:
        """Get current portfolio Greeks"""
        return self.get_portfolio_greeks_context().get('greeks', {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0})
    
    def get_portfolio_greeks_history(self) -> pd.DataFrame:
        """Get portfolio Greeks time series"""
        def _rows_to_df(rows: Any) -> pd.DataFrame:
            if not isinstance(rows, list) or not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            if 'timestamp' not in df.columns:
                return pd.DataFrame()
            for col in ('delta', 'gamma', 'theta', 'vega'):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                else:
                    df[col] = np.nan
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
            df = df.dropna(subset=['timestamp'])
            if df.empty:
                return pd.DataFrame()
            return df[['timestamp', 'delta', 'gamma', 'theta', 'vega']].copy()

        def _has_signal(df: pd.DataFrame) -> bool:
            if not isinstance(df, pd.DataFrame) or df.empty:
                return False
            for col in ('delta', 'gamma', 'theta', 'vega'):
                if col in df.columns and (pd.to_numeric(df[col], errors='coerce').abs() > 1e-9).any():
                    return True
            return False

        frames: List[pd.DataFrame] = []
        persisted = self._load_persisted_state()
        if persisted:
            p_df = _rows_to_df(persisted.get('greeks_history', []) or [])
            if not p_df.empty:
                frames.append(p_df)

        # Backfill history from reset archives when current state was rotated/reset.
        archive_dir = self._persisted_state_path.parent / 'reset_archive'
        if archive_dir.exists():
            for state_path in sorted(archive_dir.glob('*/options_dashboard_state.json'))[-16:]:
                try:
                    archived = json.loads(state_path.read_text())
                except Exception:
                    continue
                a_df = _rows_to_df(archived.get('greeks_history', []) if isinstance(archived, dict) else [])
                if not a_df.empty:
                    frames.append(a_df)

        if self.portfolio_greeks_history:
            m_df = _rows_to_df(self.portfolio_greeks_history)
            if not m_df.empty:
                frames.append(m_df)

        if frames:
            hist = pd.concat(frames, ignore_index=True, sort=False)
            hist['timestamp'] = pd.to_datetime(hist['timestamp'], errors='coerce', utc=True)
            hist = hist.dropna(subset=['timestamp']).sort_values('timestamp')
            hist = hist.groupby('timestamp', as_index=False).last().sort_values('timestamp')
            if _has_signal(hist):
                return hist.set_index('timestamp')

        if not self.portfolio_greeks_history:
            ctx = self.get_portfolio_greeks_context()
            if str(ctx.get('source', '')).strip().lower() == 'cycle_strategies':
                # Avoid presenting indicative cycle Greeks as if they were live portfolio history.
                return pd.DataFrame()
            greeks = ctx.get('greeks', {})
            if self._has_nonzero_greeks(greeks):
                return pd.DataFrame(
                    [{
                        'timestamp': datetime.now(),
                        'delta': float(greeks.get('delta', 0.0) or 0.0),
                        'gamma': float(greeks.get('gamma', 0.0) or 0.0),
                        'theta': float(greeks.get('theta', 0.0) or 0.0),
                        'vega': float(greeks.get('vega', 0.0) or 0.0),
                    }]
                ).set_index('timestamp')
            return pd.DataFrame()
        
        df = pd.DataFrame(self.portfolio_greeks_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
        df = df.dropna(subset=['timestamp'])
        df = df.sort_values('timestamp').set_index('timestamp')

        return df
    
    def check_greek_violations(self) -> List[str]:
        """Check if portfolio Greeks violate safety bands"""
        ctx = self.get_portfolio_greeks_context()
        # Strategy-cycle fallback Greeks are indicative and not actual live portfolio exposure.
        if str(ctx.get('source', '')).strip().lower() == 'cycle_strategies':
            return []
        greeks = ctx.get('greeks', {}) if isinstance(ctx, dict) else self.get_portfolio_greeks()
        violations = []
        
        # Safety bands from config
        if greeks['delta'] < -0.2:
            violations.append(f"Delta {greeks['delta']:.2f} < -0.2")
        if greeks['delta'] > 0.2:
            violations.append(f"Delta {greeks['delta']:.2f} > 0.2")
        if greeks['theta'] < 0.0:
            violations.append(f"Theta {greeks['theta']:.2f} < 0.0")
        if greeks['vega'] < -0.3:
            violations.append(f"Vega {greeks['vega']:.2f} < -0.3")
        if greeks['vega'] > 0.1:
            violations.append(f"Vega {greeks['vega']:.2f} > 0.1")
        
        return violations
    
    # ------------------------------------------------------------------
    # TRADE HISTORY
    # ------------------------------------------------------------------
    
    def get_trade_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trade history"""
        if self.closed_positions:
            def _entry_sort_value(row: Dict[str, Any]) -> int:
                ts = pd.to_datetime(row.get('entry_time'), errors='coerce', utc=True)
                return int(ts.value) if pd.notna(ts) else -1

            # Sort by most recent first
            sorted_positions = sorted(
                self.closed_positions,
                key=_entry_sort_value,
                reverse=True
            )
            return sorted_positions[:limit]
        
        persisted = self._load_persisted_state()
        if persisted:
            rows = persisted.get('closed_positions', []) or []
            return rows[:limit]

        # Fallback to state if available
        if self.state and hasattr(self.state, 'options'):
            try:
                positions = []
                for pos in self.state.options.closed_positions[:limit]:
                    positions.append({
                        'position_id': pos.position_id,
                        'strategy_type': pos.strategy_type,
                        'entry_time': pos.entry_time,
                        'exit_time': pos.exit_time,
                        'realized_pnl': pos.realized_pnl,
                        'exit_reason': pos.exit_reason,
                        'hold_duration_days': pos.days_held
                    })
                return positions
            except Exception:
                pass
        
        return []
    
    def get_trade_metrics(self) -> Dict[str, Any]:
        """Calculate trade history metrics"""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('trade_metrics'), dict):
            return persisted.get('trade_metrics', {})

        trades = self.get_trade_history(limit=100)
        
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0
            }
        
        total_trades = len(trades)
        winning_trades = [t for t in trades if t.get('realized_pnl', 0) > 0]
        losing_trades = [t for t in trades if t.get('realized_pnl', 0) < 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        avg_profit = (
            sum(t.get('realized_pnl', 0) for t in winning_trades) / len(winning_trades)
            if winning_trades else 0.0
        )
        
        avg_loss = (
            sum(t.get('realized_pnl', 0) for t in losing_trades) / len(losing_trades)
            if losing_trades else 0.0
        )
        
        total_profit = sum(t.get('realized_pnl', 0) for t in winning_trades)
        total_loss = abs(sum(t.get('realized_pnl', 0) for t in losing_trades))
        profit_factor = total_profit / total_loss if total_loss > 0 else 0.0
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }

    def get_ytd_summary(self) -> Dict[str, Any]:
        """Return tax-aware YTD summary from persisted options state."""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('ytd'), dict):
            return persisted.get('ytd', {})
        return {}
    
    # ------------------------------------------------------------------
    # RISK METRICS
    # ------------------------------------------------------------------
    
    def get_kill_switch_status(self) -> Dict[str, Any]:
        """Get kill switch status"""
        if self.kill_switch_status:
            return self.kill_switch_status

        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('kill_switch_status'), dict):
            return persisted.get('kill_switch_status', {})
        
        # Fallback to state if available
        if self.state and hasattr(self.state, 'options'):
            try:
                return {
                    'active': self.state.options.kill_switch_active,
                    'reasons': self.state.options.kill_switch_reasons,
                    'cooldown_until': self.state.options.kill_switch_cooldown_until
                }
            except Exception:
                pass
        
        return {'active': False}
    
    def get_weekly_risk_usage(self) -> Dict[str, Any]:
        """Get weekly risk usage (trades and capital)"""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('weekly_risk_usage'), dict):
            return persisted.get('weekly_risk_usage', {})

        if self.state and hasattr(self.state, 'options'):
            try:
                return {
                    'trades_used': self.state.options.weekly_trades_count,
                    'trades_limit': 2,
                    'risk_used': self.state.options.weekly_risk_usage,
                    'risk_limit': 1.0
                }
            except Exception:
                pass
        
        return {
            'trades_used': 0,
            'trades_limit': 2,
            'risk_used': 0.0,
            'risk_limit': 1.0
        }
    
    def get_capital_scaling_status(self) -> Dict[str, Any]:
        """Get capital scaling status"""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('capital_scaling'), dict):
            return persisted.get('capital_scaling', {})

        if self.state and hasattr(self.state, 'options'):
            try:
                return {
                    'current_risk_pct': self.state.options.current_risk_pct,
                    'equity_high_water_mark': self.state.options.equity_high_water_mark,
                    'current_equity': self.state.options.current_equity
                }
            except Exception:
                pass
        
        return {
            'current_risk_pct': 1.0,
            'equity_high_water_mark': 0.0,
            'current_equity': 0.0
        }
    
    def get_portfolio_risk_usage(self) -> Dict[str, float]:
        """Get portfolio risk usage (% of capital at risk)"""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('portfolio_risk_usage'), dict):
            return persisted.get('portfolio_risk_usage', {})

        positions = self.get_active_positions()
        total_risk = sum(pos.get('max_loss', 0.0) for pos in positions)
        
        # Assume base capital of 500k (should come from config)
        base_capital = 500000.0
        risk_pct = (total_risk / base_capital) if base_capital > 0 else 0.0
        
        return {
            'total_risk': total_risk,
            'risk_cap': base_capital * 0.02,  # 2% cap
            'risk_pct': risk_pct,
            'risk_cap_pct': 0.02
        }

    def get_weekly_trade_activity(self) -> Dict[str, Any]:
        """
        Return raw weekly trade-event telemetry from trade_ledger.
        Helps explain high "trades used" values when running high-frequency loops.
        """
        out = {
            "window_start": None,
            "open_events": 0,
            "close_events": 0,
            "unique_underlyings_open": 0,
            "source": str(self._trade_ledger_path),
        }
        if not self._trade_ledger_path.exists():
            return out

        try:
            df = pd.read_parquet(self._trade_ledger_path)
        except Exception:
            return out
        if df is None or df.empty or "timestamp" not in df.columns or "action" not in df.columns:
            return out

        now_ist = datetime.now()
        week_start = (now_ist - timedelta(days=now_ist.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        out["window_start"] = week_start.isoformat()

        ts = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        valid = ts.notna()
        if not valid.any():
            return out

        week_start_utc = pd.Timestamp(week_start).tz_localize("Asia/Kolkata").tz_convert("UTC")
        weekly = df.loc[valid & (ts >= week_start_utc)].copy()
        if weekly.empty:
            return out

        action = weekly["action"].astype(str).str.lower()
        out["open_events"] = int((action == "open").sum())
        out["close_events"] = int((action == "close").sum())

        if "underlying" in weekly.columns:
            out["unique_underlyings_open"] = int(
                weekly.loc[action == "open", "underlying"].astype(str).str.upper().nunique()
            )
        return out
    
    # ------------------------------------------------------------------
    # TRADE ELIGIBILITY
    # ------------------------------------------------------------------
    
    def get_trade_eligibility(self) -> Dict[str, Any]:
        """Get next trade eligibility status"""
        payload: Dict[str, Any] = {}
        if self.trade_eligibility:
            payload = dict(self.trade_eligibility)
        else:
            persisted = self._load_persisted_state()
            if persisted and isinstance(persisted.get('trade_eligibility'), dict):
                payload = dict(persisted.get('trade_eligibility', {}))

        if not payload:
            payload = {
                'signal_generated': False,
                'rejected': False,
                'violations': [],
                'timestamp': datetime.now()
            }

        payload["signal_generated"] = bool(payload.get("signal_generated", False))
        payload["rejected"] = bool(payload.get("rejected", False))
        payload["violations"] = self._normalize_violations(payload.get("violations"))
        ts = self._to_datetime(payload.get("timestamp"))
        fresh = self._freshness(ts, expected_interval_minutes=15.0)
        payload["freshness"] = fresh
        payload["stale"] = fresh.get("status") == "stale"
        if payload.get("rejected") and not payload.get("reason"):
            vio = payload.get("violations") or []
            if vio:
                payload["reason"] = vio[0]
        return payload

        # Default: no signal
        return {
            'signal_generated': False,
            'rejected': False,
            'violations': [],
            'timestamp': datetime.now()
        }

    def get_market_snapshot(self) -> Dict[str, Any]:
        """Return latest market feed context for options dashboards."""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('market_snapshot'), dict):
            snap = persisted.get('market_snapshot', {}) or {}
            return {
                'option_contracts': int(snap.get('option_contracts', 0) or 0),
                'nifty_price': snap.get('NIFTY_price'),
                'banknifty_price': snap.get('BANKNIFTY_price'),
                'timestamp': persisted.get('timestamp'),
            }

        try:
            if self._market_data_path.exists():
                md = json.loads(self._market_data_path.read_text())
                idx = md.get('indices', {}) if isinstance(md, dict) else {}
                return {
                    'option_contracts': 0,
                    'nifty_price': (idx.get('NIFTY', {}) or {}).get('current_price'),
                    'banknifty_price': (idx.get('BANKNIFTY', {}) or {}).get('current_price'),
                    'timestamp': md.get('timestamp'),
                }
        except Exception:
            pass

        return {'option_contracts': 0, 'nifty_price': None, 'banknifty_price': None, 'timestamp': None}

    def get_active_limits(self) -> Dict[str, Any]:
        """Return currently active option risk/frequency limits."""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('active_limits'), dict):
            return persisted.get('active_limits', {})
        return {
            'aggressive_mode': False,
            'max_trades_per_week': 2,
            'portfolio_risk_cap_pct': 0.02,
            'source': {
                'max_trades_per_week': 'config',
                'portfolio_risk_cap_pct': 'config',
            }
        }

    def get_options_cycle(self) -> Dict[str, Any]:
        """Return latest cycle-level diagnostic payload from the live engine."""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('options_cycle'), dict):
            return persisted.get('options_cycle', {})
        return {}

    def get_portfolio_overlay(self) -> Dict[str, Any]:
        """Return portfolio-aware options overlay context from live engine."""
        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('portfolio_overlay'), dict):
            return persisted.get('portfolio_overlay', {})
        return {}

    def get_centralized_pnl(self) -> Dict[str, Any]:
        """Return centralized cross-system PnL snapshot and latest trend stats."""
        payload = self._safe_json_read(self._centralized_pnl_path)
        if not payload:
            return {
                "available": False,
                "path": str(self._centralized_pnl_path),
                "series_path": str(self._centralized_pnl_series_path),
            }

        out = dict(payload)
        out["available"] = True
        out["path"] = str(self._centralized_pnl_path)
        out["series_path"] = str(self._centralized_pnl_series_path)
        if self._centralized_pnl_series_path.exists():
            try:
                df = pd.read_parquet(self._centralized_pnl_series_path)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    out["series_rows"] = int(len(df))
                    latest = df.iloc[-1].to_dict()
                    out["latest_series"] = {
                        "timestamp": str(latest.get("timestamp")),
                        "combined_net_pnl_estimate": float(latest.get("combined_net_pnl_estimate", 0.0) or 0.0),
                        "options_ytd_net_pnl": float(latest.get("options_ytd_net_pnl", 0.0) or 0.0),
                        "weekly_portfolio_total_pnl": float(latest.get("weekly_portfolio_total_pnl", 0.0) or 0.0),
                        "shadow_total_pnl": float(latest.get("shadow_total_pnl", 0.0) or 0.0),
                    }
                    if len(df) >= 2 and "combined_net_pnl_estimate" in df.columns:
                        prev = float(df.iloc[-2].get("combined_net_pnl_estimate", 0.0) or 0.0)
                        cur = float(df.iloc[-1].get("combined_net_pnl_estimate", 0.0) or 0.0)
                        out["combined_net_delta"] = cur - prev
            except Exception:
                pass
        return out

    def get_underlying_decisions(self) -> List[Dict[str, Any]]:
        """Return per-underlying decisions from latest options cycle."""
        cycle = self.get_options_cycle()
        if isinstance(cycle, dict):
            rows = cycle.get('underlyings', [])
            if isinstance(rows, list):
                enriched: List[Dict[str, Any]] = []
                for row in rows:
                    if isinstance(row, dict):
                        enriched.append(self._enrich_decision_row(row))
                return enriched
        return []

    def get_decision_history(self, limit: int = 120) -> List[Dict[str, Any]]:
        """Return trailing compact decision history rows."""
        persisted = self._load_persisted_state()
        rows = persisted.get('options_decision_history', []) if isinstance(persisted, dict) else []
        if isinstance(rows, list):
            enriched: List[Dict[str, Any]] = []
            for row in rows[-limit:]:
                if isinstance(row, dict):
                    enriched.append(self._enrich_decision_row(row))
            return enriched
        return []
    
    def get_eligibility_checks(self) -> List[Dict[str, Any]]:
        """Get detailed eligibility check results"""
        eligibility = self.get_trade_eligibility()
        violations = self._normalize_violations(eligibility.get("violations"))

        def _pretty_name(raw: str) -> str:
            mapping = {
                "iv_rank_threshold": "IV Rank Threshold",
                "liquidity_spread": "Liquidity Spread",
                "liquidity_depth": "Liquidity Depth",
                "expiry_hygiene": "Expiry Hygiene",
                "event_calendar": "Event Calendar",
                "vol_of_vol": "Vol of Vol",
                "late_cycle_protection": "Late Cycle Protection",
            }
            key = str(raw or "").strip().lower()
            return mapping.get(key, str(raw or "Unknown").replace("_", " ").title())

        def _detail_for_failed(check_name: str, detail: str) -> str:
            txt = str(detail or "").strip()
            if txt.lower() not in {"", "failed", "fail", "false", "n/a"}:
                return txt
            cn = check_name.lower().strip()
            if cn == "expiry_hygiene":
                for v in violations:
                    if "expiry" in v.lower() or "days to expiry" in v.lower():
                        return v
            if violations:
                return violations[0]
            return "Failed"

        persisted = self._load_persisted_state()
        if persisted and isinstance(persisted.get('eligibility_checks'), list):
            out: List[Dict[str, Any]] = []
            for row in (persisted.get('eligibility_checks', []) or []):
                if not isinstance(row, dict):
                    continue
                name_raw = str(row.get("check", "Unknown"))
                passed = bool(row.get("passed", False))
                detail = str(row.get("detail", "") or "")
                if not passed:
                    detail = _detail_for_failed(name_raw, detail)
                out.append(
                    {
                        "check": _pretty_name(name_raw),
                        "passed": passed,
                        "detail": detail,
                        "stale": bool(eligibility.get("stale", False)),
                    }
                )
            return out

        checks = []
        
        # Regime stability
        days_in_regime = self.get_regime_stability_days()
        checks.append({
            'check': 'Regime Stability',
            'passed': days_in_regime >= 2,
            'detail': f"{days_in_regime} days (need 2+)",
            'stale': bool(eligibility.get("stale", False)),
        })
        
        # Kill switch
        kill_switch = self.get_kill_switch_status()
        checks.append({
            'check': 'Kill Switch',
            'passed': not kill_switch.get('active', False),
            'detail': kill_switch.get('reason', 'No active kill switches'),
            'stale': bool(eligibility.get("stale", False)),
        })
        
        # Weekly trade limit
        weekly_usage = self.get_weekly_risk_usage()
        checks.append({
            'check': 'Weekly Trade Limit',
            'passed': weekly_usage['trades_used'] < weekly_usage['trades_limit'],
            'detail': f"{weekly_usage['trades_used']}/{weekly_usage['trades_limit']} trades used",
            'stale': bool(eligibility.get("stale", False)),
        })
        
        # Portfolio risk cap
        risk_usage = self.get_portfolio_risk_usage()
        checks.append({
            'check': 'Portfolio Risk Cap',
            'passed': risk_usage['risk_pct'] < risk_usage['risk_cap_pct'],
            'detail': f"{risk_usage['risk_pct']:.1%} of {risk_usage['risk_cap_pct']:.1%} cap",
            'stale': bool(eligibility.get("stale", False)),
        })
        
        # Greek violations
        greek_violations = self.check_greek_violations()
        checks.append({
            'check': 'Greek Safety Bands',
            'passed': len(greek_violations) == 0,
            'detail': '; '.join(greek_violations) if greek_violations else 'All Greeks within bands',
            'stale': bool(eligibility.get("stale", False)),
        })
        
        return checks
    
    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    
    def get_options_summary(self) -> Dict[str, Any]:
        """Get comprehensive options summary for dashboard"""
        return {
            'regime': self.get_current_regime(),
            'regime_metrics': self.get_regime_metrics(),
            'active_positions_count': self.get_active_positions_count(),
            'total_unrealized_pnl': self.get_total_unrealized_pnl(),
            'portfolio_greeks': self.get_portfolio_greeks(),
            'portfolio_greeks_context': self.get_portfolio_greeks_context(),
            'greek_violations': self.check_greek_violations(),
            'trade_metrics': self.get_trade_metrics(),
            'ytd': self.get_ytd_summary(),
            'kill_switch_status': self.get_kill_switch_status(),
            'weekly_risk_usage': self.get_weekly_risk_usage(),
            'capital_scaling': self.get_capital_scaling_status(),
            'portfolio_risk_usage': self.get_portfolio_risk_usage(),
            'weekly_trade_activity': self.get_weekly_trade_activity(),
            'trade_eligibility': self.get_trade_eligibility(),
            'eligibility_checks': self.get_eligibility_checks(),
            'market_snapshot': self.get_market_snapshot(),
            'active_limits': self.get_active_limits(),
            'portfolio_overlay': self.get_portfolio_overlay(),
            'centralized_pnl': self.get_centralized_pnl(),
            'options_cycle': self.get_options_cycle(),
            'underlying_decisions': self.get_underlying_decisions(),
            'decision_history': self.get_decision_history(limit=200),
            'historical_universe_health': self.get_historical_universe_health(),
            'live_loop_health': self.get_live_loop_health(expected_interval_minutes=5.0),
            'opportunity_surface': self.get_opportunity_surface_summary(top_n=20),
            'options_backtest': self.get_backtest_snapshot(),
        }


if __name__ == "__main__":
    # Test options observer
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Create observer
    observer = OptionsObserver()
    
    # Simulate regime change event
    observer.on_regime_change({
        'old_regime': 'NEUTRAL',
        'new_regime': 'LOW_VOL_SELL',
        'iv_rank': 0.75,
        'days_in_old_regime': 5,
        'reason': 'IV rank exceeded 70%',
        'timestamp': datetime.now()
    })
    
    # Simulate position opened event
    observer.on_position_opened({
        'position_id': 'POS_20240115_123456',
        'strategy_type': 'IRON_CONDOR',
        'max_loss': 5000.0,
        'entry_time': datetime.now(),
        'legs': [],
        'timestamp': datetime.now()
    })
    
    # Get summary
    summary = observer.get_options_summary()
    print("\nOptions Summary:")
    print(f"  Regime: {summary['regime']}")
    print(f"  Active Positions: {summary['active_positions_count']}")
    print(f"  Portfolio Greeks: {summary['portfolio_greeks']}")
    print(f"  Kill Switch Active: {summary['kill_switch_status']['active']}")
