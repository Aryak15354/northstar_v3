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
    "Security",
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
    wide: bool = False  # render full-width (multi-panel cockpits need the room)


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
    # The live option chain is served from the freshest of three sources at
    # runtime (see data_manager.load_live_options_data); the two legacy parquet
    # twins (nifty_options_latest / live_option_chain) are long dead, so the
    # FRESHNESS badge points at the canonical live options surface the engine
    # rewrites every cycle instead of a Dec-frozen parquet.
    "options_chain": "data/options/live/options_dashboard_state.json",
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
    "pipeline_freshness": "data/runtime/refresh_state.json",
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


from src.dashboard import visuals_extra as _vx


def _spec(vid, title, desc, tab, subsection, level, builder, source, *, wide=False):
    return DashboardVisualSpec(
        visual_id=vid, title=title, description=desc, tab=tab, subsection=subsection,
        level=level, data_dependency=(vid,), data_source=source,
        refresh_frequency=REFRESH_HOURLY, builder=builder, legacy_section=tab,
        wide=wide,
    )


# High-density additions: Options cockpit, market movers/watchlist, consolidated
# all-in-one panels, and alternative-data views (new chart types: tables,
# treemaps, heatmaps, gauges, multi-panel subplots).
NEW_VISUAL_SPECS = [
    # --- Data Truth Panel: the dashboard telling you when IT is wrong (top of Overview) ---
    _spec("overview_data_truth", "Data Truth Panel — is the dashboard telling the truth?",
          "Every canonical artifact with its content-age and freshness. Worst-first. If a panel elsewhere looks wrong, this says whether its data is stale.",
          "Overview", "Topline", PRIMARY, _vx.data_truth_panel,
          "all canonical artifacts (content-age)", wide=True),
    # --- Overview: rich all-in-one executive panels ---
    _spec("overview_market_pulse", "Market Pulse (vitals)",
          "Gauge cluster of the current tape: breadth, risk-on, participation, health, opportunity, coherence.",
          "Overview", "Topline", PRIMARY, _vx.overview_market_pulse, "data/processed/market_state.parquet"),
    _spec("overview_whats_changed", "What Changed",
          "Everything that moved recently: sentiment surprises, bulk-deal prints, rating actions, new options positions.",
          "Overview", "Topline", PRIMARY, _vx.whats_changed,
          "data/processed/alternative/bulk_deals_nse_all.parquet + data/processed/sentiment/ticker_sentiment_daily.parquet"),
    _spec("overview_exec_cockpit", "Executive Cockpit (all-in-one)",
          "NAV & drawdown, capital allocation, exposure policy, and sentiment read in a single view.",
          "Overview", "Topline", PRIMARY, _vx.overview_exec_cockpit,
          "data/pnl/nav_history.parquet + data/processed/market_state.parquet", wide=True),
    # --- Options cockpit (wired to the OptionsOrgan suggestions) ---
    _spec("options_cockpit_table", "Options Suggestions — Live Book",
          "All shorts/longs/hedges/opportunities from the options organ with economics, greeks, and continuity.",
          "Options", "Suggestions Cockpit", PRIMARY, _vx.options_cockpit_table,
          "data/options/suggestions/options_suggestions_latest.json"),
    _spec("options_risk_reward", "Options Risk / Reward Map",
          "Max-loss vs max-profit per suggestion, sized by conviction, coloured by type.",
          "Options", "Suggestions Cockpit", PRIMARY, _vx.options_risk_reward,
          "data/options/suggestions/options_suggestions_latest.json"),
    _spec("options_category_greeks", "Book Composition & Aggregate Greeks",
          "Suggestion mix and net delta/vega/theta by strategy type.",
          "Options", "Suggestions Cockpit", PRIMARY, _vx.options_category_greeks,
          "data/options/suggestions/options_suggestions_latest.json"),
    _spec("options_persistence", "Persistent Convictions",
          "How many days each name has been continuously flagged (history-aware).",
          "Options", "Suggestions Cockpit", SECONDARY, _vx.options_persistence,
          "data/options/suggestions/suggestion_history.parquet"),
    # --- Market movers / watchlist / sector / universe ---
    _spec("market_movers_table", "Market Movers — Strongest & Weakest",
          "Top and bottom names by v3 score with sector, quintile, and suggested weight.",
          "Market", "Watchlist", PRIMARY, _vx.market_movers_table, "data/processed/scores.parquet"),
    _spec("market_cockpit", "Market Cockpit (all-in-one)",
          "Universe breadth, score distribution, quintiles, and top/bottom sectors in one view.",
          "Market", "Watchlist", PRIMARY, _vx.market_cockpit, "data/processed/scores.parquet", wide=True),
    _spec("sector_strength", "Sector Strength",
          "Mean v3 score by sector — where strength and weakness are concentrated.",
          "Market", "Watchlist", PRIMARY, _vx.sector_strength, "data/processed/scores.parquet"),
    _spec("market_exposure_truth", "Exposure Truth — actual vs intended",
          "The paper fund's real daily equity exposure vs the governor's intended gross and the cash floor. Replaces the dead unified_daily exposure charts.",
          "Market", "Exposure Policy", PRIMARY, _vx.exposure_truth,
          "data/pnl/nav_history.parquet + data/processed/portfolio_weights.parquet"),
    _spec("universe_treemap", "Universe Map (treemap)",
          "Sector × name, sized by weight and coloured by v3 score — the whole book at a glance.",
          "Market", "Watchlist", SECONDARY, _vx.universe_treemap, "data/processed/scores.parquet"),
    # --- Alternative data (previously had no figures) ---
    _spec("alt_bulk_deal_flow", "Smart-Money Bulk-Deal Flow",
          "Net institutional buy/sell pressure per day and top net names (last 60d).",
          "Sentiment", "Alternative Data", PRIMARY, _vx.alt_bulk_deal_flow,
          "data/processed/alternative/bulk_deals_nse_all.parquet"),
    _spec("alt_promoter_pledge", "Promoter Pledge Risk",
          "Highest promoter-pledged companies — a governance / financial-stress signal.",
          "Sentiment", "Alternative Data", PRIMARY, _vx.alt_promoter_pledge,
          "data/processed/alternative/promoter_pledge_all.csv"),
    _spec("alt_gst_trend", "Macro Activity — GST & E-way Bills",
          "Monthly GST revenue and e-way bill volume as an economic-activity proxy.",
          "Sentiment", "Alternative Data", SECONDARY, _vx.alt_gst_trend,
          "data/canonical/macro/gst_ewaybill_market_monthly.parquet"),
    # ---- Portfolio: the ₹100cr paper fund — the one truth — at the top ----
    _spec("paper_fund_cockpit", "Paper Fund Cockpit — ₹100cr NAV vs NIFTY",
          "The fund headline: mark-to-market NAV vs NIFTY-50 to the honest last-market date, live P&L, drawdown, and cost/tax drag from the one truth.",
          "Portfolio", "Paper Fund", PRIMARY, _vx.paper_fund_cockpit,
          "data/pnl/nav_history.parquet + paper_fund_summary + strategy_benchmark_nav", wide=True),
    _spec("paper_fund_blotter", "Holdings Blotter (marked to market)",
          "The real position book: quantity, average cost, last price, market value, weight and unrealized P&L.",
          "Portfolio", "Paper Fund", PRIMARY, _vx.paper_fund_blotter,
          "data/pnl/current_positions.parquet", wide=True),
    _spec("paper_fund_liquidation", "Liquidation Schedule",
          "Trading days to fully exit each name at the 15%-of-ADV daily cap — the book cannot be dumped in a day.",
          "Portfolio", "Paper Fund", PRIMARY, _vx.paper_fund_liquidation,
          "data/pnl/liquidation_schedule.parquet"),
    _spec("strategy_benchmark_race", "Strategy Race — V3 vs famous strategies",
          "V3 vs Buffett / Magic Formula / Piotroski / Graham vs NIFTY, all run through the same ₹100cr engine. The yardstick future alpha must beat.",
          "Portfolio", "Paper Fund", PRIMARY, _vx.strategy_benchmark_race,
          "data/pnl/strategy_benchmark_nav.parquet"),
    # legacy target-weight cockpit kept as secondary (target vs actual)
    _spec("portfolio_cockpit", "Target Book (v3 weights)",
          "The v3 target: equity curve, sector allocation and core/satellite role mix.",
          "Portfolio", "Target", SECONDARY, _vx.portfolio_cockpit,
          "data/processed/portfolio_weights.parquet · data/pnl/nav_history.parquet", wide=True),
    _spec("portfolio_blotter", "Target Weights",
          "The v3 target book with role, conviction and valuation stance.",
          "Portfolio", "Target", SECONDARY, _vx.portfolio_blotter,
          "data/processed/portfolio_weights.parquet"),
    # ---- Risk: 'where is the risk?' cockpit + hotspot table at the top ----
    _spec("risk_cockpit", "Risk Cockpit — where is the risk?",
          "Single-name & sector concentration, live drawdown and net options greeks, each flagged at prudent thresholds.",
          "Risk", "Where Is The Risk", PRIMARY, _vx.risk_cockpit,
          "data/processed/portfolio_weights.parquet · data/pnl/nav_history.parquet", wide=True),
    _spec("risk_hotspots", "Risk Hotspots",
          "Largest positions crossed with governance stress (promoter pledge) — the names to watch.",
          "Risk", "Where Is The Risk", PRIMARY, _vx.risk_hotspots,
          "data/processed/portfolio_weights.parquet · data/processed/alternative/promoter_pledge_all.csv"),
]


EXTRA_SPECS = NEW_VISUAL_SPECS + [
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


# TRUE per-visual dependencies (traced from each builder's actual bundle reads,
# 2026-07 dashboard rebuild). The old code slapped a whole-SECTION mega-bundle on
# every visual, so one dead artifact (unified_daily, daily_sentiment) poisoned the
# freshness tag for an entire tab even though most panels read a fresh file. Each
# visual now advertises only what it actually consumes, so the freshness badge
# tells the truth per panel.
CUSTOM_VISUAL_DEPS: dict[str, tuple[str, ...]] = {
    # Overview
    "overview_pnl_mix": ("nav", "ledger"),
    "overview_market_regime_timeline": ("regime_history",),
    "overview_governor_fractions": ("governor_budgets",),
    "overview_pipeline_age": ("pipeline_freshness",),
    "overview_runtime_age": ("pipeline_freshness",),
    "overview_component_status": ("component_status",),
    # Performance
    "performance_monthly_heatmap": ("nav",),
    "performance_ledger_book": ("ledger",),
    "performance_ledger_strategy": ("ledger",),
    "perf_avg_slippage": ("execution_quality",),
    "performance_shadow_nav": ("nav", "shadow_pnl"),
    # Market
    "market_regime_timeline": ("regime_history",),
    "market_transition_matrix": ("regime_history",),
    "market_vol_regime_counts": ("market_state",),
    "market_risk_on_vs_stress": ("market_state",),
    "market_unified_macro_exposure": ("unified_daily",),
    "market_exposure_allowed_vs_actual": ("exposure_history",),
    # Sentiment
    "sentiment_top_positive": ("latest_ticker_sentiment",),
    "sentiment_top_negative": ("latest_ticker_sentiment",),
    "sentiment_source_coverage": ("latest_ticker_sentiment",),
    "alternative_bulk_daily": ("bulk_deals",),
    "alternative_announce_categories": ("announcements",),
    # Portfolio
    "portfolio_role_donut": ("portfolio_weights",),
    "portfolio_sector_exposure": ("portfolio_weights",),
    "portfolio_mispricing_weight": ("portfolio_weights", "valuation_engines"),
    "portfolio_top_scores": ("portfolio_weights", "scores"),
    "portfolio_strategy_area": ("allocation_history",),
    "portfolio_strategy_heatmap": ("allocation_history",),
    "portfolio_governor_donut": ("governor_budgets",),
    "portfolio_governor_budget": ("governor_budgets",),
    "portfolio_stock_roles": ("stock_roles",),
    # Options
    "options_iv_smile": ("options_chain",),
    "options_oi": ("options_chain",),
    "options_volume": ("options_chain",),
    "options_delta": ("options_chain",),
    "options_gamma": ("options_chain",),
    "options_theta": ("options_chain",),
    "options_vega": ("options_chain",),
    "options_iv_heatmap": ("options_chain",),
    "options_active_greeks": ("active_option_positions",),
    "options_active_underlyings": ("active_option_positions",),
    "options_governance_events": ("options_governance",),
    "options_runtime_iv": ("option_iv_history",),
    "options_volatility_regimes": ("volatility_state",),
}

# Legacy `_spec_*` visual ids encode their source in the 2nd colon token, e.g.
# "Market & Regime:market_state:...:risk_on_probability" reads `market_state`.
_SECTION_DEFAULT_DEP = {
    "Market & Regime": ("market_state",),
    "Sentiment & Alternative Data": ("market_sentiment",),
    "Portfolio & Governor": ("portfolio_weights",),
    "Options & Risk": ("options_chain",),
    "Valuation & Research": ("valuation_engines",),
    "Alpha OS & Operations": ("alpha_os_timeseries",),
}


def _infer_dependencies(spec: Any) -> tuple[str, ...]:
    vid = spec.visual_id
    if vid.startswith("overview_nav") or "shadow_nav" in vid:
        return ("nav", "benchmark", "shadow_pnl")
    if vid in CUSTOM_VISUAL_DEPS:
        return CUSTOM_VISUAL_DEPS[vid]
    # Auto `_spec_*` visuals: the 2nd colon token is the real bundle key.
    if ":" in vid:
        token = vid.split(":")[1]
        if token in DEPENDENCY_SOURCES:
            deps = [token]
            # alt-data spec_* charts additionally read their event source
            if "bulk" in vid:
                deps.append("bulk_deals")
            if "announce" in vid:
                deps.append("announcements")
            if "pledge" in vid:
                deps.append("promoter_pledge")
            return tuple(deps)
    if "pnl" in vid or "ledger" in vid or "monthly_heatmap" in vid:
        return ("nav", "ledger")
    return _SECTION_DEFAULT_DEP.get(spec.section, ("pipeline_freshness",))


# Visuals removed from the dashboard entirely (dead/duplicative — 2026-07 rebuild).
RETIRED_VISUAL_IDS: frozenset[str] = frozenset({
    "market_risk_on_vs_stress",                 # scatter of two gauges already shown
    "market_unified_macro_exposure",            # reads dead unified_daily
    "market_exposure_allowed_vs_actual",        # reads dead exposure_history (replaced by exposure_truth)
    "options_volatility_regimes",               # only consumer of dormant volatility_state.parquet (Dec)
    "Sentiment & Alternative Data:daily_sentiment:sentiment_mean",       # dead daily_sentiment aggregate,
    "Sentiment & Alternative Data:daily_sentiment:conviction_mean",      # duplicates canonical market gauges
    "Sentiment & Alternative Data:daily_sentiment:uncertainty_mean",
    "Sentiment & Alternative Data:daily_sentiment:headline_count",
})

# Visuals disabled for now (alpha/strategy-driven — parked until the Kaggle
# experiments return; NOT deleted, they come back with the results).
PARKED_VISUAL_IDS: frozenset[str] = frozenset({
    "overview_alpha_probs",
    "portfolio_strategy_area",
    "portfolio_strategy_heatmap",
    "Portfolio & Governor:strategy_weights:strategy:weight:bar",
    "Portfolio & Governor:strategy_performance:strategy:total_return:bar",
})


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


# Tabs excluded from the active dashboard for now. Research + Alpha OS live
# entirely in the Kaggle experiment loop until the 24 experiments finish and
# their results are folded back into v3; rendering their frozen Q1 artifacts here
# only produced false signals.
EXCLUDED_TABS: frozenset[str] = frozenset({"Research", "Alpha OS"})


def build_visual_registry() -> list[DashboardVisualSpec]:
    positions: dict[str, int] = {}
    visuals = [_convert_legacy_spec(spec, positions) for spec in visual_catalog.VISUAL_SPECS]
    # New high-density panels are placed FIRST so movers/cockpit/pulse land at
    # the top of each page; then legacy visuals; then the risk extras.
    risk_extras = EXTRA_SPECS[len(NEW_VISUAL_SPECS):]
    combined = NEW_VISUAL_SPECS + visuals + risk_extras
    kept: list[DashboardVisualSpec] = []
    for spec in combined:
        if spec.tab in EXCLUDED_TABS:
            continue
        if spec.visual_id in RETIRED_VISUAL_IDS or spec.visual_id in PARKED_VISUAL_IDS:
            continue
        kept.append(spec)
    return kept


VISUALS = build_visual_registry()


def get_visuals_for_tab(tab: str) -> list[DashboardVisualSpec]:
    return [spec for spec in VISUALS if spec.tab == tab]


def visual_counts_by_tab() -> dict[str, int]:
    return {tab: len(get_visuals_for_tab(tab)) for tab in TAB_ORDER}
