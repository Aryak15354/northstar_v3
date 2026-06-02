#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from src.dashboard import visual_catalog

PRIMARY = "PRIMARY"
SECONDARY = "SECONDARY"
ADVANCED = "ADVANCED"

REFRESH_STATIC = "STATIC"
REFRESH_HOURLY = "HOURLY"
REFRESH_LIVE = "LIVE_5MIN"

TAB_ORDER = [
    "Overview",
    "Performance",
    "Market",
    "Sentiment",
    "Portfolio",
    "Risk",
    "Options",
    "Research",
    "Alpha OS",
]

LIVE_TABS = {"Market", "Sentiment", "Portfolio", "Risk", "Options"}


@dataclass(frozen=True)
class DashboardVisualSpec:
    visual_id: str
    title: str
    description: str
    tab: str
    subsection: str
    level: str
    data_dependency: tuple[str, ...]
    data_source: str
    refresh_frequency: str
    builder: Callable[[dict[str, Any]], Any]
    legacy_section: str


DEPENDENCY_SOURCES = {
    "nav": "data/pnl/nav_history.parquet",
    "ledger": "data/pnl/master_ledger.parquet",
    "execution_quality": "data/pnl/execution_quality.parquet",
    "shadow_pnl": "data/processed/shadow_pnl_series.parquet",
    "market_state": "data/processed/market_state.parquet",
    "regime_history": "data/processed/market_state.parquet + regime history contract",
    "unified_daily": "data/processed/unified_daily.parquet",
    "exposure_history": "data/processed/exposure_history.parquet",
    "market_sentiment": "data/processed/sentiment/market_sentiment_daily.parquet",
    "daily_sentiment": "data/processed/sentiment/daily_sentiment_aggregated.parquet",
    "latest_ticker_sentiment": "data/processed/sentiment/ticker_sentiment_daily.parquet",
    "bulk_deals": "data/processed/alternative/bulk_deals_nse_all.parquet",
    "announcements": "data/processed/alternative/announcements_all.csv",
    "promoter_pledge": "data/processed/alternative/promoter_pledge_all.csv",
    "shareholding": "data/processed/screener_shareholding.csv",
    "portfolio_weights": "data/processed/portfolio_weights.parquet + unified_portfolio enrichment",
    "unified_portfolio": "data/processed/unified_portfolio.parquet",
    "allocation_history": "data/processed/allocation_history.parquet",
    "state_history": "data/state/unified_state_history.parquet",
    "strategy_weights": "data/state/unified_state.json → alpha_os.strategy_weights",
    "governor_budgets": "data/state/unified_state.json → governor_state",
    "strategy_performance": "data/processed/strategy_performance.parquet",
    "stock_roles": "data/processed/stock_roles.parquet",
    "options_chain": "data/options/live/nifty_options_latest.parquet",
    "options_governance": "data/options/live/governance_events.parquet",
    "active_option_positions": "data/options/live/options_dashboard_state.json",
    "option_iv_history": "data/options/live/options_runtime_state.json",
    "volatility_state": "data/processed/volatility_state.parquet",
    "greeks_history": "data/pnl/master_ledger.parquet → greeks_at_entry",
    "risk_frame": "data/state/unified_state.json → risk/portfolio/market",
    "valuation": "data/processed/valuation.parquet",
    "valuation_posterior": "data/processed/valuation_posterior.parquet",
    "valuation_families": "data/processed/valuation_families.parquet",
    "valuation_engines": "data/processed/valuation_engines.parquet",
    "cohesive_alpha": "data/processed/cohesive_alpha_feed.parquet",
    "scores": "data/processed/scores.parquet",
    "alpha_os_timeseries": "data/processed/alpha_os_timeseries.parquet",
    "alpha_os_posteriors": "data/processed/alpha_os_strategy_posteriors.parquet",
    "strategy_regret": "data/processed/strategy_regret.parquet",
    "strategy_beliefs": "data/processed/strategy_beliefs.parquet",
    "pipeline_freshness": "status artifacts + runtime heartbeat surfaces",
    "component_status": "data/processed/system_execution_log.json",
    "state_log": "data/state/state_change_log.jsonl",
}

HOURLY_KEYS = {
    "market_state",
    "regime_history",
    "market_sentiment",
    "daily_sentiment",
    "latest_ticker_sentiment",
    "bulk_deals",
    "announcements",
    "promoter_pledge",
    "shareholding",
    "alpha_os_timeseries",
    "alpha_os_posteriors",
    "strategy_beliefs",
    "strategy_regret",
    "pipeline_freshness",
    "component_status",
    "state_log",
}

LIVE_KEYS = {
    "options_chain",
    "options_governance",
    "active_option_positions",
    "option_iv_history",
    "risk_frame",
    "greeks_history",
    "volatility_state",
    "pipeline_freshness",
}


def _risk_live_snapshot(bundle: dict[str, Any]):
    df = bundle.get("risk_frame")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    row = df.iloc[-1]
    metrics = pd.DataFrame(
        [
            {"metric": "Allowed Exposure", "value": pd.to_numeric(row.get("allowed_exposure"), errors="coerce")},
            {"metric": "Portfolio Exposure", "value": pd.to_numeric(row.get("portfolio_exposure"), errors="coerce")},
            {"metric": "Exposure Multiplier", "value": pd.to_numeric(row.get("exposure_multiplier"), errors="coerce")},
            {"metric": "System Stress", "value": pd.to_numeric(row.get("system_stress"), errors="coerce")},
        ]
    ).dropna(subset=["value"])
    return visual_catalog._bar_figure(metrics, "metric", "value", "Live Risk Snapshot", orientation="h")


def _risk_greeks_history(bundle: dict[str, Any]):
    df = bundle.get("greeks_history")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    return visual_catalog._multi_line_figure(df, "timestamp", ["delta", "gamma", "theta", "vega"], "Portfolio Greeks History")


def _risk_margin_stack(bundle: dict[str, Any]):
    df = bundle.get("risk_frame")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    row = df.iloc[-1]
    metrics = pd.DataFrame(
        [
            {"metric": "Margin Utilization", "value": pd.to_numeric(row.get("options_margin_utilization"), errors="coerce")},
            {"metric": "Delta Exposure", "value": pd.to_numeric(row.get("options_delta_exposure_inr"), errors="coerce")},
            {"metric": "Vega Exposure", "value": pd.to_numeric(row.get("options_vega_exposure_inr"), errors="coerce")},
            {"metric": "Max Loss Scenario", "value": pd.to_numeric(row.get("options_max_loss_scenario"), errors="coerce")},
        ]
    ).dropna(subset=["value"])
    return visual_catalog._bar_figure(metrics, "metric", "value", "Options Risk Surface", orientation="h")


EXTRA_SPECS = [
    DashboardVisualSpec(
        visual_id="risk_live_snapshot",
        title="Live Risk Snapshot",
        description="Current runtime exposure, stress, and sizing state from the canonical risk frame.",
        tab="Risk",
        subsection="Runtime Risk",
        level=PRIMARY,
        data_dependency=("risk_frame",),
        data_source=DEPENDENCY_SOURCES["risk_frame"],
        refresh_frequency=REFRESH_LIVE,
        builder=_risk_live_snapshot,
        legacy_section="Risk",
    ),
    DashboardVisualSpec(
        visual_id="risk_greeks_history",
        title="Portfolio Greeks History",
        description="Persisted options Greek history derived from ledger events.",
        tab="Risk",
        subsection="Greeks Engine",
        level=PRIMARY,
        data_dependency=("greeks_history",),
        data_source=DEPENDENCY_SOURCES["greeks_history"],
        refresh_frequency=REFRESH_LIVE,
        builder=_risk_greeks_history,
        legacy_section="Risk",
    ),
    DashboardVisualSpec(
        visual_id="risk_margin_stack",
        title="Options Risk Surface",
        description="Margin, delta, vega, and max-loss state from the live risk snapshot.",
        tab="Risk",
        subsection="Runtime Risk",
        level=SECONDARY,
        data_dependency=("risk_frame",),
        data_source=DEPENDENCY_SOURCES["risk_frame"],
        refresh_frequency=REFRESH_LIVE,
        builder=_risk_margin_stack,
        legacy_section="Risk",
    ),
]


def _default_tab(spec: Any) -> str:
    if spec.section == "Executive Overview":
        return "Overview"
    if spec.section == "Performance & P&L":
        return "Performance"
    if spec.section == "Market & Regime":
        return "Market"
    if spec.section == "Sentiment & Alternative Data":
        return "Sentiment"
    if spec.section == "Portfolio & Governor":
        return "Portfolio"
    if spec.section == "Valuation & Research":
        return "Research"
    if spec.section == "Alpha OS & Operations":
        return "Alpha OS"
    if spec.section == "Options & Risk":
        risk_ids = {
            "options_active_greeks",
            "options_runtime_iv",
            "options_volatility_regimes",
        }
        return "Risk" if spec.visual_id in risk_ids else "Options"
    return "Overview"


def _infer_dependencies(spec: Any) -> tuple[str, ...]:
    vid = spec.visual_id
    if vid.startswith("overview_nav") or "shadow_nav" in vid:
        return ("nav", "benchmark", "shadow_pnl")
    if "pnl" in vid or "ledger" in vid or "monthly_heatmap" in vid:
        return ("nav", "ledger", "execution_quality", "shadow_pnl")
    if spec.section == "Market & Regime":
        return ("market_state", "regime_history", "unified_daily", "exposure_history")
    if spec.section == "Sentiment & Alternative Data":
        keys = ["market_sentiment", "daily_sentiment", "latest_ticker_sentiment"]
        if "bulk" in vid:
            keys.append("bulk_deals")
        if "announce" in vid:
            keys.append("announcements")
        if "pledge" in vid:
            keys.append("promoter_pledge")
        if "shareholding" in vid:
            keys.append("shareholding")
        return tuple(keys)
    if spec.section == "Portfolio & Governor":
        return ("portfolio_weights", "unified_portfolio", "allocation_history", "state_history", "strategy_weights", "governor_budgets", "stock_roles", "strategy_performance")
    if spec.section == "Options & Risk":
        if spec.visual_id in {"options_active_greeks", "options_runtime_iv", "options_volatility_regimes"}:
            return ("active_option_positions", "option_iv_history", "volatility_state", "risk_frame", "greeks_history")
        return ("options_chain", "options_governance", "active_option_positions", "option_iv_history")
    if spec.section == "Valuation & Research":
        return ("valuation", "valuation_posterior", "valuation_families", "valuation_engines", "cohesive_alpha", "scores")
    if spec.section == "Alpha OS & Operations":
        return ("alpha_os_timeseries", "alpha_os_posteriors", "strategy_regret", "strategy_beliefs", "pipeline_freshness", "component_status", "state_log", "strategy_performance")
    return ("pipeline_freshness",)


def _infer_refresh(dependencies: tuple[str, ...]) -> str:
    dep_set = set(dependencies)
    if dep_set & LIVE_KEYS:
        return REFRESH_LIVE
    if dep_set & HOURLY_KEYS:
        return REFRESH_HOURLY
    return REFRESH_STATIC


def _infer_sources(dependencies: tuple[str, ...]) -> str:
    sources = [DEPENDENCY_SOURCES[key] for key in dependencies if key in DEPENDENCY_SOURCES]
    return " | ".join(dict.fromkeys(sources))


def _infer_subsection(tab: str, spec: Any) -> str:
    vid = spec.visual_id
    title = spec.title
    if tab == "Overview":
        return "Topline"
    if tab == "Performance":
        if "ledger" in vid or "slippage" in title.lower():
            return "Execution & Ledger"
        if "shadow" in vid:
            return "Parity"
        return "Returns & NAV"
    if tab == "Market":
        if "transition" in vid or "timeline" in vid or "vol_regime" in vid:
            return "Regime Engine"
        if "exposure" in vid:
            return "Exposure Policy"
        return "Market State"
    if tab == "Sentiment":
        if "bulk" in vid or "announce" in vid or "pledge" in vid or "shareholding" in vid:
            return "Alternative Data"
        if "ticker" in title.lower() or "coverage" in vid:
            return "Company Sentiment"
        return "Market Sentiment"
    if tab == "Portfolio":
        if "governor" in vid:
            return "Governor"
        if "strategy" in vid:
            return "Allocation Engine"
        return "Current Book"
    if tab == "Risk":
        if "greeks" in vid:
            return "Greeks Engine"
        return "Runtime Risk"
    if tab == "Options":
        if "iv" in vid and "runtime" not in vid:
            return "Market Surface"
        if "oi" in vid or "volume" in vid or "underlyings" in vid:
            return "Flow & Positioning"
        if "delta" in vid or "gamma" in vid or "theta" in vid or "vega" in vid:
            return "Greeks Engine"
        return "Risk Layer"
    if tab == "Research":
        if "family" in vid or "engine" in vid or "posterior" in vid:
            return "Engine Diagnostics"
        return "Valuation Surface"
    if tab == "Alpha OS":
        if "pipeline" in vid or "state_write" in vid or "component" in vid or "runtime" in vid:
            return "Operations"
        if "weight" in vid or "belief" in vid or "regret" in vid or "sharpe" in vid:
            return "Strategy Layer"
        return "Regime Engine"
    return "Overview"


PRIMARY_IDS = {
    "Overview": {
        "overview_nav_vs_benchmark",
        "overview_governor_fractions",
        "overview_market_regime_timeline",
        "overview_alpha_probs",
        "overview_pipeline_age",
        "overview_component_status",
    },
    "Performance": {
        "Performance & P&L:nav:nav:date",
    },
    "Market": {
        "Market & Regime:market_state:date:risk_on_probability",
    },
}


def _assign_level(tab: str, position: int) -> str:
    if position < 6:
        return PRIMARY
    if position < 12:
        return SECONDARY
    return ADVANCED


def _convert_legacy_spec(spec: Any, position_by_tab: dict[str, int]) -> DashboardVisualSpec:
    tab = _default_tab(spec)
    dependencies = _infer_dependencies(spec)
    position = position_by_tab.get(tab, 0)
    position_by_tab[tab] = position + 1
    return DashboardVisualSpec(
        visual_id=spec.visual_id,
        title=spec.title,
        description=spec.description,
        tab=tab,
        subsection=_infer_subsection(tab, spec),
        level=_assign_level(tab, position),
        data_dependency=dependencies,
        data_source=_infer_sources(dependencies),
        refresh_frequency=_infer_refresh(dependencies),
        builder=spec.builder,
        legacy_section=spec.section,
    )


def build_visual_registry() -> list[DashboardVisualSpec]:
    positions: dict[str, int] = {}
    visuals = [_convert_legacy_spec(spec, positions) for spec in visual_catalog.VISUAL_SPECS]
    return visuals + EXTRA_SPECS


VISUALS = build_visual_registry()


def get_visuals_for_tab(tab: str) -> list[DashboardVisualSpec]:
    return [spec for spec in VISUALS if spec.tab == tab]


def visual_counts_by_tab() -> dict[str, int]:
    return {tab: len(get_visuals_for_tab(tab)) for tab in TAB_ORDER}
