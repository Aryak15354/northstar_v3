#!/usr/bin/env python3
"""
DashboardDataContract — Loads dashboard data from authoritative persisted surfaces.

Primary sources:
1. data/state/unified_state.json
2. data/pnl/nav_history.parquet
3. data/state/reconciliation_reports.parquet or data/pnl/reconciliation_log.parquet
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from scripts.system_status_report import build_health_snapshot, collect_statuses
from src.dashboard.v3_data_hub import V3DataHub


class DataFreshness(str, Enum):
    LIVE = "LIVE"
    RECENT = "RECENT"
    STALE = "STALE"
    OLD = "OLD"
    UNKNOWN = "UNKNOWN"


@dataclass
class LabeledValue:
    value: Any
    source: str
    as_of: Optional[datetime]
    freshness: DataFreshness
    is_available: bool = True
    unavailability_reason: Optional[str] = None

    @property
    def source_timestamp(self) -> Optional[datetime]:
        return self.as_of

    @property
    def age_minutes(self) -> Optional[float]:
        if self.as_of is None:
            return None
        return max(0.0, (datetime.now() - self.as_of).total_seconds() / 60.0)


class DashboardDataContract:
    """Read-only contract over the system's persisted authoritative artifacts."""

    def __init__(
        self,
        state_path: str = "data/state/unified_state.json",
        nav_history_path: str = "data/pnl/nav_history.parquet",
        regime_dir: str = "data/processed/regime",
    ):
        self.project_root = Path(__file__).resolve().parents[2]
        self.state_path = self._resolve_path(state_path)
        self.nav_history_path = self._resolve_path(nav_history_path)
        self.regime_dir = self._resolve_path(regime_dir)
        self.reconciliation_report_path = self.project_root / "data/state/reconciliation_reports.parquet"
        self.pnl_reconciliation_path = self.project_root / "data/pnl/reconciliation_log.parquet"
        self.attribution_path = self.project_root / "data/pnl/attribution_daily.parquet"
        self.ledger_path = self.project_root / "data/pnl/master_ledger.parquet"
        self.execution_quality_path = self.project_root / "data/pnl/execution_quality.parquet"
        self.benchmark_nav_path = self.project_root / "data/processed/benchmark/nifty50.parquet"
        self.benchmark_returns_path = self.project_root / "data/pnl/benchmark_returns.parquet"
        self.market_refresh_status_path = self.project_root / "data/processed/market_refresh_status.json"
        self.sentiment_status_path = self.project_root / "data/sentiment/v3/sentiment_loop_status.json"
        self.alternative_status_path = self.project_root / "data/processed/alternative/alternative_pipeline_status.json"
        self.orchestrator_status_path = self.project_root / "data/options/live/trading_day_orchestrator_status.json"
        self.runtime_state_path = self.project_root / "data/options/live/options_runtime_state.json"
        self.dashboard_state_path = self.project_root / "data/options/live/options_dashboard_state.json"
        self.heartbeat_path = self.project_root / "data/options/live/live_engine_heartbeat.json"
        self.system_execution_log_path = self.project_root / "data/processed/system_execution_log.json"
        self.state_change_log_path = self.project_root / "data/state/state_change_log.jsonl"
        self.options_chain_path = self.project_root / "data/options/live/nifty_options_latest.parquet"
        self.options_governance_path = self.project_root / "data/options/live/governance_events.parquet"
        # The REAL options book (with per-trade greeks_at_entry) lives here, not
        # in master_ledger.parquet — that file is the equity paper-fund ledger
        # and has never carried an option_type column, so get_greeks_history()
        # was silently reading an unrelated, always-empty-for-options file.
        self.options_trade_ledger_path = self.project_root / "data/options/trade_ledger.parquet"
        self.unified_state_history_path = self.project_root / "data/state/unified_state_history.parquet"
        self.sector_mapping_path = self.project_root / "data/processed/sector_mapping.csv"
        self.valuation_path = self.project_root / "data/processed/valuation.parquet"
        self.valuation_families_path = self.project_root / "data/processed/valuation_families.parquet"
        self.valuation_posterior_path = self.project_root / "data/processed/valuation_posterior.parquet"
        self.valuation_engines_path = self.project_root / "data/processed/valuation_engines.parquet"
        self.portfolio_history_path = self.project_root / "data/processed/allocation_history.parquet"
        self.hub = V3DataHub(project_root=self.project_root)

        self._state_cache: Optional[dict] = None
        self._state_cache_time: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=30)

    def _resolve_path(self, path_value: str) -> Path:
        path = Path(path_value)
        return path if path.is_absolute() else self.project_root / path

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value in [None, "", "None", "NaT"]:
            return None
        if isinstance(value, datetime):
            return value
        try:
            try:
                parsed = pd.to_datetime(value, utc=False, format="mixed")
            except TypeError:
                parsed = pd.to_datetime(value, utc=False)
            if pd.isna(parsed):
                return None
            if getattr(parsed, "tzinfo", None) is not None:
                try:
                    parsed = parsed.tz_localize(None)
                except TypeError:
                    parsed = parsed.tz_convert(None)
            return parsed.to_pydatetime()
        except Exception:
            return None

    def _compute_freshness(self, as_of: Optional[datetime]) -> DataFreshness:
        if as_of is None:
            return DataFreshness.UNKNOWN

        age_minutes = (datetime.now() - as_of).total_seconds() / 60
        if age_minutes < 1:
            return DataFreshness.LIVE
        if age_minutes < 5:
            return DataFreshness.RECENT
        if age_minutes < 30:
            return DataFreshness.STALE
        return DataFreshness.OLD

    def _load_state_payload(self, force: bool = False) -> Optional[dict]:
        now = datetime.now()
        if (
            not force
            and self._state_cache is not None
            and self._state_cache_time is not None
            and now - self._state_cache_time < self._cache_ttl
        ):
            return self._state_cache

        if not self.state_path.exists():
            self._state_cache = None
            self._state_cache_time = now
            return None

        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                self._state_cache = json.load(handle)
        except Exception:
            self._state_cache = None

        self._state_cache_time = now
        return self._state_cache

    def _section(self, section_name: str) -> dict:
        payload = self._load_state_payload()
        if not isinstance(payload, dict):
            return {}
        section = payload.get(section_name, {})
        return section if isinstance(section, dict) else {}

    def _unavailable(self, source: str, reason: str) -> LabeledValue:
        return LabeledValue(
            value=None,
            source=source,
            as_of=None,
            freshness=DataFreshness.UNKNOWN,
            is_available=False,
            unavailability_reason=reason,
        )

    def _load_nav_from_file(self) -> Optional[pd.DataFrame]:
        if not self.nav_history_path.exists():
            return None
        try:
            return pd.read_parquet(self.nav_history_path)
        except Exception:
            return None

    def _nav_column(self, df: pd.DataFrame) -> Optional[str]:
        for candidate in ["nav_combined", "nav", "current_nav", "nav_per_unit"]:
            if candidate in df.columns:
                return candidate
        return None

    def _load_latest_reconciliation(self) -> Optional[dict]:
        for path in [self.reconciliation_report_path, self.pnl_reconciliation_path]:
            if not path.exists():
                continue
            try:
                df = pd.read_parquet(path)
                if df.empty:
                    continue
                latest = df.iloc[-1].to_dict()
                return latest
            except Exception:
                continue
        return None

    def _load_parquet(self, path: Path) -> Optional[pd.DataFrame]:
        if not path.exists():
            return None
        try:
            return pd.read_parquet(path)
        except Exception:
            return None

    def _load_csv(self, path: Path) -> Optional[pd.DataFrame]:
        if not path.exists():
            return None
        try:
            return pd.read_csv(path)
        except Exception:
            return None

    def _load_json_file(self, path: Path) -> Optional[dict]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _normalize_positions_frame(self, positions: Any) -> pd.DataFrame:
        if isinstance(positions, pd.DataFrame):
            return positions.copy()
        if isinstance(positions, dict) and positions:
            rows = []
            for ticker, payload in positions.items():
                row = {"ticker": ticker}
                if isinstance(payload, dict):
                    row.update(payload)
                rows.append(row)
            df = pd.DataFrame(rows)
            if "weight_pct" in df.columns and "weight" not in df.columns:
                df["weight"] = pd.to_numeric(df["weight_pct"], errors="coerce")
            if "avg_cost" in df.columns and "price" not in df.columns:
                df["price"] = pd.to_numeric(df["avg_cost"], errors="coerce")
            if "quantity" in df.columns:
                df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
            if "notional_value" not in df.columns and {"quantity", "price"}.issubset(df.columns):
                df["notional_value"] = df["quantity"] * df["price"]
            return df
        return pd.DataFrame()

    def _latest_per_group(self, df: pd.DataFrame, group_col: str, date_col: str) -> pd.DataFrame:
        if df is None or df.empty or group_col not in df.columns or date_col not in df.columns:
            return pd.DataFrame()
        working = df.copy()
        working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
        working = working.dropna(subset=[group_col, date_col]).sort_values(date_col)
        if working.empty:
            return pd.DataFrame()
        idx = working.groupby(group_col)[date_col].idxmax()
        return working.loc[idx].reset_index(drop=True)

    def _latest_date_in_df(self, df: Optional[pd.DataFrame]) -> Optional[datetime]:
        if df is None or df.empty:
            return None
        for col in ["date", "Date", "timestamp", "trade_date", "recorded_at", "availability_date"]:
            if col in df.columns:
                series = pd.to_datetime(df[col], errors="coerce").dropna()
                if not series.empty:
                    return series.max().to_pydatetime()
        if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
            series = pd.to_datetime(pd.Series(df.index), errors="coerce").dropna()
            if not series.empty:
                return series.max().to_pydatetime()
        return None

    def _today_date(self) -> datetime.date:
        return datetime.now().date()

    def _coerce_frame(self, df: Optional[pd.DataFrame], date_cols: tuple[str, ...] = ("date", "Date", "timestamp")) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        working = df.copy()
        for col in date_cols:
            if col in working.columns:
                working[col] = pd.to_datetime(working[col], errors="coerce")
        return working

    def get_equity_positions(self) -> LabeledValue:
        portfolio = self._section("portfolio")
        positions = portfolio.get("positions")
        as_of = self._parse_datetime(portfolio.get("last_updated"))

        if isinstance(positions, dict) and positions:
            return LabeledValue(
                value=positions,
                source="unified_state.json → portfolio.positions",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )

        return self._unavailable(
            "unified_state.json → portfolio.positions",
            "Equity positions are not available in unified_state.json",
        )

    def get_options_positions(self) -> LabeledValue:
        portfolio = self._section("portfolio")
        positions = portfolio.get("options_positions")
        as_of = self._parse_datetime(portfolio.get("last_updated"))

        if isinstance(positions, dict) and positions:
            return LabeledValue(
                value=positions,
                source="unified_state.json → portfolio.options_positions",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )

        return self._unavailable(
            "unified_state.json → portfolio.options_positions",
            "No options positions currently held",
        )

    def get_intraday_pnl(self) -> LabeledValue:
        pnl_state = self._section("pnl_state")
        value = (
            pnl_state.get("intraday_pnl")
            if "intraday_pnl" in pnl_state
            else pnl_state.get("pnl_today_inr", pnl_state.get("net_pnl_today_inr"))
        )
        as_of = self._parse_datetime(pnl_state.get("last_updated"))

        if value is None:
            return self._unavailable(
                "unified_state.json → pnl_state",
                "Intraday P&L is unavailable",
            )

        return LabeledValue(
            value=value,
            source="unified_state.json → pnl_state",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_options_greeks(self) -> LabeledValue:
        portfolio = self._section("portfolio")
        as_of = self._parse_datetime(portfolio.get("last_updated"))
        value = {
            "delta": portfolio.get("options_net_delta", 0),
            "gamma": portfolio.get("options_net_gamma", 0),
            "vega": portfolio.get("options_net_vega", 0),
            "theta": portfolio.get("options_net_theta", 0),
        }
        is_available = any(v not in [None, 0] for v in value.values())
        if not is_available and not portfolio:
            return self._unavailable(
                "unified_state.json → portfolio",
                "Options Greeks are unavailable",
            )

        return LabeledValue(
            value=value,
            source="unified_state.json → portfolio",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
            is_available=is_available,
            unavailability_reason=None if is_available else "Options Greeks are all zero",
        )

    def get_capital_structure(self) -> LabeledValue:
        governor = self._section("governor_state")
        as_of = self._parse_datetime(governor.get("last_updated") or governor.get("last_morning_decision"))

        if not governor:
            return self._unavailable(
                "unified_state.json → governor_state",
                "Governor state is unavailable",
            )

        value = {
            "equity_fraction": governor.get("equity_fraction", 0.0),
            "options_fraction": governor.get("options_fraction", 0.0),
            "cash_fraction": governor.get("cash_fraction", 0.0),
            "equity_budget_inr": governor.get("equity_budget_inr"),
            "options_budget_inr": governor.get("options_budget_inr"),
            "cash_reserve_inr": governor.get("cash_reserve_inr"),
            "current_regime": governor.get("current_regime", governor.get("capital_structure_regime")),
            "confidence": governor.get("confidence", governor.get("governance_confidence")),
            "decision_rationale": governor.get("decision_rationale", governor.get("primary_rationale")),
            "modifiers_applied": governor.get("modifiers_applied", []),
        }
        return LabeledValue(
            value=value,
            source="unified_state.json → governor_state",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_governor_regime(self) -> LabeledValue:
        capital_structure = self.get_capital_structure()
        if not capital_structure.is_available:
            return capital_structure

        value = capital_structure.value.get("current_regime")
        return LabeledValue(
            value=value,
            source=capital_structure.source,
            as_of=capital_structure.as_of,
            freshness=capital_structure.freshness,
            is_available=value is not None,
            unavailability_reason=None if value is not None else "Governor regime is unavailable",
        )

    def get_strategy_weights(self) -> LabeledValue:
        alpha_os = self._section("alpha_os")
        weights = alpha_os.get("strategy_weights")
        as_of = self._parse_datetime(alpha_os.get("last_updated"))

        if isinstance(weights, dict) and weights:
            return LabeledValue(
                value=weights,
                source="unified_state.json → alpha_os.strategy_weights",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )

        return self._unavailable(
            "unified_state.json → alpha_os.strategy_weights",
            "No active strategy weights are persisted",
        )

    def get_market_regime(self) -> LabeledValue:
        market = self._section("market")
        as_of = self._parse_datetime(market.get("last_updated"))
        if not market:
            return self._unavailable("unified_state.json → market", "Market regime is unavailable")

        value = {
            "regime": market.get("regime", "unknown"),
            "confidence": market.get("regime_confidence", market.get("risk_on_probability")),
            "volatility_regime": market.get("volatility_regime"),
        }
        return LabeledValue(
            value=value,
            source="unified_state.json → market",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_volatility_regime(self) -> LabeledValue:
        regime = self.get_market_regime()
        if not regime.is_available:
            return regime
        return LabeledValue(
            value=regime.value.get("volatility_regime"),
            source=regime.source,
            as_of=regime.as_of,
            freshness=regime.freshness,
            is_available=regime.value.get("volatility_regime") is not None,
            unavailability_reason=None if regime.value.get("volatility_regime") is not None else "Volatility regime is unavailable",
        )

    def get_sentiment_state(self) -> LabeledValue:
        sentiment = self._section("sentiment")
        as_of = self._parse_datetime(sentiment.get("last_updated"))

        if not sentiment:
            return self._unavailable("unified_state.json → sentiment", "Sentiment state is unavailable")

        regime = sentiment.get("regime", sentiment.get("market_sentiment_regime"))
        market_sentiment_score = sentiment.get(
            "market_sentiment_score",
            sentiment.get("market_sentiment_zscore"),
        )
        conviction = sentiment.get("conviction", sentiment.get("regime_confidence"))

        is_available = regime not in [None, "", "UNAVAILABLE", "SentimentRegime.UNAVAILABLE"]
        if not is_available:
            return self._unavailable("unified_state.json → sentiment", "Sentiment pipeline has not run recently")

        value = {
            "regime": regime,
            "market_sentiment_score": market_sentiment_score,
            "conviction": conviction,
            "trend": sentiment.get("sentiment_trend"),
        }
        return LabeledValue(
            value=value,
            source="unified_state.json → sentiment",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_alternative_data_state(self) -> LabeledValue:
        alt = self._section("alternative_data")
        as_of = self._parse_datetime(alt.get("last_updated"))

        if not alt:
            return self._unavailable(
                "unified_state.json → alternative_data",
                "Alternative data state is unavailable",
            )

        value = {
            "gst_yoy_growth": alt.get("gst_yoy_growth", alt.get("gst", {}).get("yoy_growth_pct", 0)),
            "gst_deviation": alt.get("gst_deviation", alt.get("gst", {}).get("deviation", 0)),
            "power_yoy_growth": alt.get("power_yoy_growth", alt.get("power", {}).get("yoy_growth_pct", 0)),
            "power_deviation_seasonal": alt.get(
                "power_deviation_seasonal",
                alt.get("power", {}).get("deviation_from_seasonal", alt.get("power", {}).get("deviation", 0)),
            ),
            "credit_upgrade_ratio": alt.get(
                "credit_upgrade_ratio",
                alt.get("credit_upgrade_downgrade_ratio", alt.get("credit", {}).get("market_upgrade_ratio", 0)),
            ),
            "credit_net_momentum": alt.get("credit_net_momentum", alt.get("credit", {}).get("net_momentum", 0)),
            "bulk_net_flow": alt.get("bulk_net_flow", alt.get("smart_money", {}).get("bulk_net_flow", 0)),
            "bulk_accumulation_breadth": alt.get(
                "bulk_accumulation_breadth",
                alt.get("smart_money", {}).get("accumulation_breadth", 0),
            ),
            "bulk_distribution_breadth": alt.get(
                "bulk_distribution_breadth",
                alt.get("smart_money", {}).get("distribution_breadth", 0),
            ),
            "bulk_signal_numeric": alt.get("bulk_signal_numeric", alt.get("smart_money", {}).get("signal_numeric", 0)),
            "credit_upgrade_downgrade_ratio": alt.get(
                "credit_upgrade_ratio",
                alt.get("credit_upgrade_downgrade_ratio", alt.get("credit", {}).get("market_upgrade_ratio", 0)),
            ),
            "economic_activity_regime": alt.get("economic_activity_regime"),
        }
        return LabeledValue(
            value=value,
            source="unified_state.json → alternative_data",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
            is_available=any(v not in [None, 0, ""] for v in value.values()),
            unavailability_reason="Alternative data exists but is empty"
            if not any(v not in [None, 0, ""] for v in value.values())
            else None,
        )

    def get_market_intelligence(self) -> LabeledValue:
        intelligence = self._section("intelligence_state")
        as_of = self._parse_datetime(
            intelligence.get("computed_at")
            or intelligence.get("last_updated")
            or intelligence.get("shock_detected_at")
        )

        if not intelligence:
            return self._unavailable(
                "unified_state.json → intelligence_state",
                "Market intelligence state is unavailable",
            )

        value = {
            "available": bool(intelligence.get("available", False)),
            "primary_shock_type": intelligence.get("primary_shock_type", "none"),
            "shock_severity": intelligence.get("shock_severity", "NONE"),
            "shock_direction": intelligence.get("shock_direction", "neutral"),
            "shock_confidence": float(intelligence.get("shock_confidence", 0.0) or 0.0),
            "sector_impacts": intelligence.get("sector_impacts", {}) or {},
            "requires_immediate_hedge": bool(intelligence.get("requires_immediate_hedge", False)),
            "requires_portfolio_rebalance": bool(intelligence.get("requires_portfolio_rebalance", False)),
            "options_opportunity_detected": bool(intelligence.get("options_opportunity_detected", False)),
            "selected_option_strategies": list(intelligence.get("selected_option_strategies", []) or []),
            "computed_at": intelligence.get("computed_at"),
            "source_timestamp": intelligence.get("computed_at"),
            "age_minutes": max(0.0, (datetime.now() - as_of).total_seconds() / 60.0) if as_of else None,
        }
        return LabeledValue(
            value=value,
            source="unified_state.json → intelligence_state",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
            is_available=bool(value["available"]),
            unavailability_reason=None if value["available"] else "Intelligence state exists but is marked unavailable",
        )

    def get_system_health(self) -> LabeledValue:
        payload = self._load_state_payload() or {}
        try:
            computed = build_health_snapshot(collect_statuses(), state_payload=payload)
        except Exception:
            computed = None

        if isinstance(computed, dict) and computed:
            as_of = self._parse_datetime(computed.get("last_updated"))
            return LabeledValue(
                value=computed,
                source="system_status_report → operational health",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )

        health = self._section("health")
        as_of = self._parse_datetime(health.get("last_updated"))
        if not health:
            return self._unavailable("unified_state.json → health", "System health is unavailable")

        return LabeledValue(
            value=health,
            source="unified_state.json → health",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_nav_history(self, lookback_days: int = 365) -> LabeledValue:
        nav_df = self._load_nav_from_file()
        if nav_df is None or nav_df.empty:
            return self._unavailable(
                "data/pnl/nav_history.parquet",
                "NAV history file not found",
            )

        working = nav_df.copy()
        date_column = next((c for c in ["date", "timestamp", "as_of_date"] if c in working.columns), None)
        if date_column:
            working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
            cutoff = datetime.now() - timedelta(days=lookback_days)
            working = working[working[date_column] >= cutoff]
            as_of = self._parse_datetime(working[date_column].iloc[-1]) if not working.empty else None
        else:
            as_of = None

        return LabeledValue(
            value=working,
            source="data/pnl/nav_history.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_performance_metrics(self) -> LabeledValue:
        nav_df = self._load_nav_from_file()
        if nav_df is not None and not nav_df.empty:
            nav_column = self._nav_column(nav_df)
            if nav_column:
                working = nav_df.copy()
                latest_nav = float(working[nav_column].iloc[-1])
                starting_nav = float(working[nav_column].iloc[0])
                total_return = ((latest_nav / starting_nav) - 1) * 100 if starting_nav else 0.0

                daily_return = working[nav_column].pct_change()
                sharpe = 0.0
                if daily_return.std() and not np.isnan(daily_return.std()) and daily_return.std() > 0:
                    sharpe = float((daily_return.mean() / daily_return.std()) * np.sqrt(252))

                rolling_high = working[nav_column].cummax()
                drawdown = (working[nav_column] - rolling_high) / rolling_high
                max_drawdown = float(drawdown.min() * 100) if not drawdown.empty else 0.0

                date_column = next((c for c in ["date", "timestamp", "as_of_date"] if c in working.columns), None)
                as_of = self._parse_datetime(working[date_column].iloc[-1]) if date_column else None

                return LabeledValue(
                    value={
                        "current_nav": latest_nav,
                        "total_return": total_return,
                        "sharpe_ratio": sharpe if not np.isnan(sharpe) else 0.0,
                        "max_drawdown": max_drawdown if not np.isnan(max_drawdown) else 0.0,
                    },
                    source="data/pnl/nav_history.parquet",
                    as_of=as_of,
                    freshness=self._compute_freshness(as_of),
                )

        pnl_state = self._section("pnl_state")
        as_of = self._parse_datetime(pnl_state.get("last_updated"))
        if pnl_state:
            return LabeledValue(
                value={
                    "current_nav": pnl_state.get("current_nav", pnl_state.get("current_nav_inr")),
                    "total_return": pnl_state.get("total_return_pct", pnl_state.get("nav_return_since_inception_pct", 0.0)),
                    "sharpe_ratio": pnl_state.get("sharpe_ratio", pnl_state.get("sharpe_ratio_30d", 0.0)),
                    "max_drawdown": pnl_state.get("max_drawdown_pct", pnl_state.get("max_drawdown_to_date_pct", 0.0)),
                },
                source="unified_state.json → pnl_state",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )

        return self._unavailable("performance_metrics", "Performance metrics are unavailable")

    def get_paper_fund_status(self) -> LabeledValue:
        pnl_state = self._section("pnl_state")
        as_of = self._parse_datetime(pnl_state.get("last_updated"))
        if pnl_state:
            value = {
                "fund_health": pnl_state.get("fund_health", "UNKNOWN"),
                "current_nav": pnl_state.get("current_nav_inr", pnl_state.get("current_nav")),
                "last_reconciliation_status": pnl_state.get("last_reconciliation_status"),
            }
            return LabeledValue(
                value=value,
                source="unified_state.json → pnl_state",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )

        nav_history = self.get_nav_history()
        if nav_history.is_available and isinstance(nav_history.value, pd.DataFrame):
            date_column = next((c for c in ["date", "timestamp", "as_of_date"] if c in nav_history.value.columns), None)
            days_running = 0
            if date_column and not nav_history.value.empty:
                series = pd.to_datetime(nav_history.value[date_column], errors="coerce").dropna()
                if not series.empty:
                    days_running = int((series.max() - series.min()).days)
            return LabeledValue(
                value={"fund_health": "ON_TRACK", "days_running": days_running},
                source="data/pnl/nav_history.parquet",
                as_of=nav_history.as_of,
                freshness=nav_history.freshness,
            )

        return self._unavailable("paper_fund_status", "Paper fund status is unavailable")

    def get_state_reconciliation_status(self) -> LabeledValue:
        latest = self._load_latest_reconciliation()
        if latest is None:
            return self._unavailable(
                "state_reconciliation",
                "Reconciliation report not found",
            )

        as_of = self._parse_datetime(latest.get("computed_at") or latest.get("timestamp") or latest.get("date"))
        value = {
            "overall_status": latest.get("overall_status", latest.get("status", "UNKNOWN")),
            "can_trade": latest.get("can_trade", True),
        }
        return LabeledValue(
            value=value,
            source="data/state/reconciliation_reports.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_attribution_today(self) -> LabeledValue:
        if not self.attribution_path.exists():
            return self._unavailable(
                "data/pnl/attribution_daily.parquet",
                "Attribution data not found",
            )
        try:
            df = pd.read_parquet(self.attribution_path)
            if df.empty:
                raise ValueError("Attribution file is empty")
            latest = df.iloc[-1].to_dict()
            as_of = self._parse_datetime(latest.get("date") or latest.get("timestamp"))
            return LabeledValue(
                value=latest,
                source="data/pnl/attribution_daily.parquet",
                as_of=as_of,
                freshness=self._compute_freshness(as_of),
            )
        except Exception:
            return self._unavailable(
                "data/pnl/attribution_daily.parquet",
                "Attribution data could not be read",
            )

    def get_benchmark_returns(self, lookback_days: int = 365) -> LabeledValue:
        benchmark_df = self._load_parquet(self.benchmark_nav_path)
        source = "data/processed/benchmark/nifty50.parquet"

        if benchmark_df is None or benchmark_df.empty:
            returns_df = self._load_parquet(self.benchmark_returns_path)
            if returns_df is not None and not returns_df.empty:
                benchmark_df = returns_df.copy()
                source = "data/pnl/benchmark_returns.parquet"

        if benchmark_df is None or benchmark_df.empty:
            benchmark_df = self.hub.index_series("nifty_50")
            source = "data/processed/index_data/nifty_50.parquet"

        if benchmark_df is None or benchmark_df.empty:
            return self._unavailable(source, "Benchmark history is unavailable")

        working = benchmark_df.copy()
        date_col = next((c for c in ["date", "Date"] if c in working.columns), None)
        if date_col is None and isinstance(working.index, pd.DatetimeIndex):
            working = working.reset_index().rename(columns={"index": "date", "Date": "date"})
            date_col = "date"
        if date_col:
            working[date_col] = pd.to_datetime(working[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=lookback_days)
            working = working[working[date_col] >= cutoff].sort_values(date_col)
            if "date" not in working.columns:
                working = working.rename(columns={date_col: "date"})
        if "close" not in working.columns and "return" in working.columns:
            working["close"] = (1.0 + pd.to_numeric(working["return"], errors="coerce").fillna(0.0)).cumprod()
        if "returns" not in working.columns and "return" in working.columns:
            working["returns"] = pd.to_numeric(working["return"], errors="coerce")
        elif "returns" not in working.columns and "close" in working.columns:
            working["returns"] = pd.to_numeric(working["close"], errors="coerce").pct_change()

        as_of = self._latest_date_in_df(working)
        return LabeledValue(
            value=working.reset_index(drop=True),
            source=source,
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_regime_history(self, lookback_days: int = 180) -> LabeledValue:
        regime_df = self.hub.market_regime()
        market_state = self.hub.market_state()

        if regime_df is None or regime_df.empty:
            regime_df = market_state
        unified_daily = self._load_parquet(self.project_root / "data/processed/unified_daily.parquet")
        if isinstance(unified_daily, pd.DataFrame) and not unified_daily.empty:
            working_daily = unified_daily.copy()
            if "date" not in working_daily.columns:
                if "Date" in working_daily.columns:
                    working_daily["date"] = working_daily["Date"]
                elif isinstance(working_daily.index, pd.DatetimeIndex):
                    working_daily = working_daily.reset_index().rename(columns={working_daily.index.name or "index": "date"})
            if "date" in working_daily.columns:
                regime_col = next(
                    (col for col in ["market_regime", "Regime", "regime", "macro_regime"] if col in working_daily.columns),
                    None,
                )
                if regime_col is not None:
                    fallback = pd.DataFrame(
                        {
                            "date": pd.to_datetime(working_daily["date"], errors="coerce"),
                            "regime": working_daily[regime_col].astype(str),
                            "breadth": pd.to_numeric(working_daily.get("MarketBreadth", working_daily.get("breadth")), errors="coerce"),
                            "participation": pd.to_numeric(working_daily.get("MarketParticipation", working_daily.get("participation")), errors="coerce"),
                            "volatility": pd.to_numeric(working_daily.get("volatility", working_daily.get("TrueStress")), errors="coerce"),
                            "correlation": pd.to_numeric(working_daily.get("correlation"), errors="coerce"),
                            "risk_on_score": pd.to_numeric(working_daily.get("risk_on_score"), errors="coerce"),
                        }
                    ).dropna(subset=["date"])
                    current_len = len(regime_df) if isinstance(regime_df, pd.DataFrame) else 0
                    current_as_of = self._latest_date_in_df(regime_df) if isinstance(regime_df, pd.DataFrame) else None
                    fallback_as_of = self._latest_date_in_df(fallback)
                    primary_missing = regime_df is None or regime_df.empty or current_len < 2
                    fallback_is_fresher = (
                        fallback_as_of is not None
                        and (current_as_of is None or fallback_as_of >= current_as_of)
                    )
                    fallback_is_richer = len(fallback) > current_len
                    if not fallback.empty and (primary_missing or fallback_is_fresher or fallback_is_richer):
                        regime_df = fallback

        if regime_df is None or regime_df.empty:
            return self._unavailable("market_regime", "Regime history is unavailable")

        working = regime_df.copy()
        if "Date" in working.columns and "date" not in working.columns:
            working = working.rename(columns={"Date": "date"})
        if "market_regime" in working.columns and "regime" not in working.columns:
            working = working.rename(columns={"market_regime": "regime"})
        if market_state is not None and not market_state.empty:
            state = market_state.copy()
            if "Date" in state.columns and "date" not in state.columns:
                state = state.rename(columns={"Date": "date"})
            merge_cols = [c for c in ["date", "sentiment_polarity", "sentiment_conviction", "stress_score", "volatility_regime", "confidence", "risk_on_probability", "allowed_exposure"] if c in state.columns]
            if "date" in merge_cols:
                state["date"] = pd.to_datetime(state["date"], errors="coerce")
                working["date"] = pd.to_datetime(working["date"], errors="coerce")
                working = working.merge(
                    state[merge_cols].drop_duplicates(subset=["date"], keep="last"),
                    on="date",
                    how="left",
                )

        working["date"] = pd.to_datetime(working["date"], errors="coerce")
        cutoff = datetime.now() - timedelta(days=lookback_days)
        working = working[working["date"] >= cutoff].sort_values("date")
        if "sentiment_score" not in working.columns and "sentiment_polarity" in working.columns:
            working["sentiment_score"] = working["sentiment_polarity"]
        if "conviction" not in working.columns and "sentiment_conviction" in working.columns:
            working["conviction"] = working["sentiment_conviction"]
        if "confidence" not in working.columns:
            working["confidence"] = np.nan

        as_of = self._latest_date_in_df(working)
        return LabeledValue(
            value=working.reset_index(drop=True),
            source="data/processed/market_state.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_macro_state(self) -> LabeledValue:
        macro = self._section("macro")
        market_state = self.hub.market_state()
        latest_market = {}
        market_as_of = None
        if market_state is not None and not market_state.empty:
            latest_market = market_state.iloc[-1].to_dict()
            market_as_of = self._latest_date_in_df(market_state)

        if not macro and not latest_market:
            return self._unavailable("macro_state", "Macro state is unavailable")

        value = {
            "inflation_regime": macro.get("inflation_regime"),
            "yield_curve_shape": macro.get("yield_curve_shape"),
            "liquidity_conditions": macro.get("liquidity_conditions"),
            "policy_stance": macro.get("policy_stance"),
            "macro_score": macro.get("macro_score", latest_market.get("macro_score")),
            "macro_regime": latest_market.get("macro_regime"),
            "macro_momentum": latest_market.get("macro_momentum"),
            "liquidity_state": latest_market.get("liquidity_state"),
        }
        as_of = self._parse_datetime(macro.get("last_updated")) or market_as_of
        return LabeledValue(
            value=value,
            source="unified_state.json → macro + market_state.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_todays_trades(self) -> LabeledValue:
        ledger = self._coerce_frame(self._load_parquet(self.ledger_path), ("trade_date", "settlement_date", "recorded_at"))
        if ledger.empty:
            return self._unavailable("data/pnl/master_ledger.parquet", "Trade ledger is unavailable")

        today = self._today_date()
        if "trade_date" in ledger.columns:
            today_df = ledger[ledger["trade_date"].dt.date == today].copy()
        else:
            today_df = pd.DataFrame()

        if today_df.empty:
            return LabeledValue(
                value=pd.DataFrame(columns=ledger.columns),
                source="data/pnl/master_ledger.parquet",
                as_of=self._latest_date_in_df(ledger),
                freshness=self._compute_freshness(self._latest_date_in_df(ledger)),
                is_available=True,
            )

        if "recorded_at" in today_df.columns and "timestamp" not in today_df.columns:
            today_df["timestamp"] = today_df["recorded_at"]
        if "entry_type" in today_df.columns and "side" not in today_df.columns:
            today_df["side"] = today_df["entry_type"].astype(str).str.extract(r"(BUY|SELL)$", expand=False).fillna("OTHER")
        if "net_pnl" in today_df.columns and "pnl" not in today_df.columns:
            today_df["pnl"] = pd.to_numeric(today_df["net_pnl"], errors="coerce")
        if "price" in today_df.columns and "execution_price" not in today_df.columns:
            today_df["execution_price"] = pd.to_numeric(today_df["price"], errors="coerce")

        as_of = self._latest_date_in_df(today_df)
        return LabeledValue(
            value=today_df.reset_index(drop=True),
            source="data/pnl/master_ledger.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_todays_orders(self) -> LabeledValue:
        trades = self.get_todays_trades()
        if not trades.is_available or not isinstance(trades.value, pd.DataFrame):
            return self._unavailable("data/pnl/master_ledger.parquet", "Order data is unavailable")

        df = trades.value.copy()
        if df.empty:
            return LabeledValue(
                value=pd.DataFrame(columns=["timestamp", "ticker", "status", "quantity", "price", "side", "source"]),
                source=trades.source,
                as_of=trades.as_of,
                freshness=trades.freshness,
            )

        orders = pd.DataFrame(
            {
                "timestamp": df.get("timestamp", df.get("recorded_at")),
                "ticker": df.get("ticker"),
                "status": "filled",
                "quantity": pd.to_numeric(df.get("quantity"), errors="coerce"),
                "price": pd.to_numeric(df.get("price"), errors="coerce"),
                "side": df.get("side"),
                "order_type": df.get("entry_type"),
                "source": df.get("source"),
            }
        )
        as_of = self._latest_date_in_df(orders)
        return LabeledValue(
            value=orders.reset_index(drop=True),
            source=trades.source,
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_realtime_risk(self) -> LabeledValue:
        risk = self._section("risk")
        portfolio = self._section("portfolio")
        market = self._section("market")

        if not risk and not portfolio and not market:
            return self._unavailable("unified_state.json", "Real-time risk state is unavailable")

        row = {
            "timestamp": risk.get("last_updated") or portfolio.get("last_updated") or market.get("last_updated"),
            "overall_risk_level": risk.get("overall_risk_level", risk.get("status")),
            "system_stress": risk.get("system_stress", market.get("market_stress")),
            "exposure_multiplier": risk.get("exposure_multiplier"),
            "allowed_exposure": market.get("allowed_exposure"),
            "portfolio_exposure": portfolio.get("total_exposure"),
            "options_delta_exposure_inr": risk.get("options_delta_exposure_inr"),
            "options_vega_exposure_inr": risk.get("options_vega_exposure_inr"),
            "options_margin_utilization": risk.get("options_margin_utilization"),
            "options_max_loss_scenario": risk.get("options_max_loss_scenario"),
        }
        df = pd.DataFrame([row])
        as_of = self._parse_datetime(row["timestamp"])
        return LabeledValue(
            value=df,
            source="unified_state.json → risk/portfolio/market",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_data_pipeline_health(self) -> LabeledValue:
        market_status = self._load_json_file(self.market_refresh_status_path) or {}
        sentiment_status = self._load_json_file(self.sentiment_status_path) or {}
        alternative_status = self._load_json_file(self.alternative_status_path) or {}

        loader_status = {
            "market": {
                "status": str(market_status.get("pipeline_status", "unknown")).lower(),
                "last_run": market_status.get("completed_at") or market_status.get("started_at"),
                "records_loaded": market_status.get("market_state_rows"),
            },
            "sentiment": {
                "status": str(sentiment_status.get("status", "unknown")).lower(),
                "last_run": sentiment_status.get("pipeline_last_run") or sentiment_status.get("last_updated"),
                "records_loaded": sentiment_status.get("companies_with_coverage"),
            },
            "alternative_data": {
                "status": str(alternative_status.get("pipeline_status", "unknown")).lower(),
                "last_run": alternative_status.get("finished_at") or alternative_status.get("started_at"),
                "records_loaded": alternative_status.get("sources_fresh_count"),
            },
        }
        failed_loaders = sum(1 for status in loader_status.values() if status.get("status") not in {"success", "ok", "healthy"})
        latest_times = [
            self._parse_datetime(status.get("last_run"))
            for status in loader_status.values()
            if status.get("last_run")
        ]
        last_successful_update = max((ts for ts in latest_times if ts is not None), default=None)
        statuses = [status.get("status") for status in loader_status.values()]
        ingestion_health = "healthy" if all(s in {"success", "ok", "healthy"} for s in statuses) else "degraded"

        value = {
            "ingestion_health": ingestion_health,
            "last_successful_update": last_successful_update.isoformat() if last_successful_update else None,
            "failed_loaders": failed_loaders,
            "loader_status": loader_status,
        }
        return LabeledValue(
            value=value,
            source="market_refresh_status.json + sentiment_loop_status.json + alternative_pipeline_status.json",
            as_of=last_successful_update,
            freshness=self._compute_freshness(last_successful_update),
        )

    def get_automation_status(self) -> LabeledValue:
        orchestrator = self._load_json_file(self.orchestrator_status_path) or {}
        heartbeat = self._load_json_file(self.heartbeat_path) or {}
        runtime_state = self._load_json_file(self.runtime_state_path) or {}

        job_status = {
            "trading_day_orchestrator": {
                "status": orchestrator.get("stage", "unknown"),
                "last_run": orchestrator.get("timestamp"),
                "next_run": None,
            },
            "live_engine": {
                "status": heartbeat.get("status", "unknown"),
                "last_run": heartbeat.get("timestamp"),
                "next_run": None,
            },
            "options_runtime": {
                "status": runtime_state.get("current_mode", "unknown"),
                "last_run": runtime_state.get("timestamp"),
                "next_run": None,
            },
        }
        latest_times = [
            self._parse_datetime(status.get("last_run"))
            for status in job_status.values()
            if status.get("last_run")
        ]
        as_of = max((ts for ts in latest_times if ts is not None), default=None)
        failed_jobs = sum(1 for status in job_status.values() if str(status.get("status", "")).lower() in {"failed", "error", "dead"})
        value = {
            "active_jobs": len(job_status),
            "failed_jobs": failed_jobs,
            "last_run": as_of.isoformat() if as_of else None,
            "job_status": job_status,
        }
        return LabeledValue(
            value=value,
            source="trading_day_orchestrator_status.json + live_engine_heartbeat.json + options_runtime_state.json",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_state_write_log(self, last_n: int = 20) -> LabeledValue:
        if not self.state_change_log_path.exists():
            return self._unavailable("data/state/state_change_log.jsonl", "State write log is unavailable")

        entries = []
        try:
            with self.state_change_log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            return self._unavailable("data/state/state_change_log.jsonl", "State write log could not be read")

        if not entries:
            return self._unavailable("data/state/state_change_log.jsonl", "State write log is empty")

        sliced = entries[-max(1, last_n):]
        as_of = self._parse_datetime(sliced[-1].get("timestamp"))
        return LabeledValue(
            value=sliced,
            source="data/state/state_change_log.jsonl",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_iv_surface_data(self) -> LabeledValue:
        df = self._coerce_frame(self._load_parquet(self.options_chain_path), ("timestamp", "date", "expiry"))
        if df.empty:
            return self._unavailable("data/options/live/nifty_options_latest.parquet", "Options chain is unavailable")
        as_of = self._latest_date_in_df(df)
        return LabeledValue(
            value=df.reset_index(drop=True),
            source="data/options/live/nifty_options_latest.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_greeks_history(self, lookback_days: int = 30) -> LabeledValue:
        # The real options book (with per-trade greeks_at_entry) lives in
        # data/options/trade_ledger.parquet, NOT master_ledger.parquet — that
        # file is the equity paper-fund's ledger and has no option_type column
        # at all, so this previously always returned "unavailable" regardless
        # of how much real options history existed.
        ledger = self._coerce_frame(self._load_parquet(self.options_trade_ledger_path), ("timestamp",))
        if ledger.empty or "greeks_at_entry" not in ledger.columns:
            return self._unavailable("data/options/trade_ledger.parquet", "Options Greeks history is unavailable")

        options = ledger[ledger["greeks_at_entry"].notna()].copy()
        if options.empty:
            return self._unavailable("data/options/trade_ledger.parquet", "No options history is available")

        def parse_greeks(payload: Any) -> dict:
            if isinstance(payload, dict):
                return payload
            if payload in [None, "", "nan"]:
                return {}
            try:
                return json.loads(payload)
            except Exception:
                return {}

        greeks = options["greeks_at_entry"].apply(parse_greeks)
        for greek in ["delta", "gamma", "vega", "theta"]:
            options[greek] = greeks.apply(lambda g: pd.to_numeric(g.get(greek), errors="coerce") if isinstance(g, dict) else np.nan)

        options["date"] = pd.to_datetime(options["timestamp"], errors="coerce")
        cutoff = datetime.now() - timedelta(days=lookback_days)
        options = options[options["date"] >= cutoff]
        history = (
            options.groupby(options["date"].dt.normalize())[["delta", "gamma", "vega", "theta"]]
            .sum(min_count=1)
            .reset_index()
            .rename(columns={"date": "timestamp"})
        )
        as_of = self._latest_date_in_df(history)
        return LabeledValue(
            value=history,
            source="data/options/trade_ledger.parquet → greeks_at_entry",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
            is_available=not history.empty,
            unavailability_reason="Options Greeks history is empty" if history.empty else None,
        )

    def get_portfolio_history(self, lookback_days: int = 90) -> LabeledValue:
        history = self._coerce_frame(self._load_parquet(self.unified_state_history_path), ("timestamp",))
        if history.empty:
            history = self._coerce_frame(self._load_parquet(self.portfolio_history_path), ("date", "timestamp"))
        if history.empty:
            return self._unavailable("portfolio_history", "Portfolio history is unavailable")

        date_col = "timestamp" if "timestamp" in history.columns else "date"
        history[date_col] = pd.to_datetime(history[date_col], errors="coerce")
        cutoff = datetime.now() - timedelta(days=lookback_days)
        history = history[history[date_col] >= cutoff].sort_values(date_col)

        if "kelly_multiplier" not in history.columns:
            history["kelly_multiplier"] = pd.to_numeric(history.get("market_allowed_exposure", history.get("allowed_exposure")), errors="coerce").fillna(0.0)
        if "exposure_multiplier" not in history.columns:
            history["exposure_multiplier"] = pd.to_numeric(history.get("risk_exposure_multiplier", history.get("market_allowed_exposure")), errors="coerce").fillna(0.0)
        if "gross_target" not in history.columns:
            gross_target = pd.to_numeric(history.get("governor_state_equity_budget_inr"), errors="coerce")
            if gross_target.isna().all():
                gross_target = pd.to_numeric(history.get("capital_allocated_capital"), errors="coerce")
            history["gross_target"] = gross_target

        as_of = self._latest_date_in_df(history)
        return LabeledValue(
            value=history.reset_index(drop=True),
            source="data/state/unified_state_history.parquet",
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
        )

    def get_sector_mapping(self) -> pd.DataFrame:
        mapping = self._load_csv(self.sector_mapping_path)
        return mapping if mapping is not None else pd.DataFrame()

    def get_governor_decisions(self, last_n: int = 20) -> LabeledValue:
        log = self.get_state_write_log(last_n=max(last_n * 10, 100))
        if not log.is_available or not isinstance(log.value, list):
            return self._unavailable("data/state/state_change_log.jsonl", "Governor decision log is unavailable")

        decisions = [
            entry for entry in log.value
            if str(entry.get("section")) == "governor_state" or str(entry.get("canonical_section")) == "governor_state"
        ]
        decisions = decisions[-last_n:]
        as_of = self._parse_datetime(decisions[-1].get("timestamp")) if decisions else None
        return LabeledValue(
            value=decisions,
            source=log.source,
            as_of=as_of,
            freshness=self._compute_freshness(as_of),
            is_available=bool(decisions),
            unavailability_reason="No governor decisions have been logged" if not decisions else None,
        )

    def get_valuation_summary(self) -> pd.DataFrame:
        df = self._load_parquet(self.valuation_path)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.copy()

    def get_dcf_components(self, ticker: str) -> dict:
        families = self._load_parquet(self.valuation_families_path)
        valuation = self._load_parquet(self.valuation_path)
        posterior = self._load_parquet(self.valuation_posterior_path)

        result: dict[str, Any] = {}
        if families is not None and not families.empty and "ticker" in families.columns:
            row = families[families["ticker"] == ticker]
            if not row.empty:
                latest = row.iloc[-1].to_dict()
                result.update({
                    "core_value": latest.get("core_value"),
                    "fcff_value": latest.get("fcff_value"),
                    "fcfe_value": latest.get("fcfe_value"),
                    "ddm_value": latest.get("ddm_value"),
                    "apv_value": latest.get("apv_value"),
                    "transaction_value": latest.get("transaction_value"),
                })
        if valuation is not None and not valuation.empty and "ticker" in valuation.columns:
            row = valuation[valuation["ticker"] == ticker]
            if not row.empty:
                latest = row.iloc[-1].to_dict()
                result.update({
                    "intrinsic_value": latest.get("dcf_intrinsic_value_per_share_v2", latest.get("intrinsic_value_estimate")),
                    "market_price": latest.get("Close", latest.get("market_price")),
                    "margin_of_safety_pct": latest.get("dcf_margin_of_safety_v2_pct", latest.get("margin_of_safety_pct")),
                })
        if posterior is not None and not posterior.empty and "ticker" in posterior.columns:
            row = posterior[posterior["ticker"] == ticker]
            if not row.empty:
                latest = row.iloc[-1].to_dict()
                result.update({
                    "posterior_value": latest.get("posterior_value"),
                    "posterior_gap": latest.get("posterior_gap"),
                    "posterior_confidence": latest.get("posterior_confidence"),
                })
        return result
