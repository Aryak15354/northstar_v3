#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Sequence

from src.dashboard.view_model_loader import dataset_age_hours


@dataclass(frozen=True)
class ChartContract:
    chart_id: str
    required_data_keys: Sequence[str]
    required_any_keys: Sequence[str]
    required_columns: Mapping[str, Sequence[str]]
    freshness_sla_hours: float
    degraded_mode: str  # block|warn|allow
    description: str


CHART_REGISTRY: Dict[str, ChartContract] = {
    "market_pressure_surface": ChartContract(
        chart_id="market_pressure_surface",
        required_data_keys=("market_regime", "alpha_os_timeseries"),
        required_any_keys=(),
        required_columns={
            "market_regime": ("Date", "volatility", "correlation", "risk_on_score"),
            "alpha_os_timeseries": ("timestamp", "regime_crisis", "regime_entropy"),
        },
        freshness_sla_hours=48.0,
        degraded_mode="block",
        description="Executive market pressure surface",
    ),
    "portfolio_expression_surface": ChartContract(
        chart_id="portfolio_expression_surface",
        required_data_keys=("pnl", "index_nifty50", "allocation_history"),
        required_any_keys=(),
        required_columns={
            "pnl": ("Date", "Equity", "Return"),
            "index_nifty50": ("close",),
            "allocation_history": ("date",),
        },
        freshness_sla_hours=48.0,
        degraded_mode="block",
        description="Executive portfolio expression surface",
    ),
    "survival_engine_surface": ChartContract(
        chart_id="survival_engine_surface",
        required_data_keys=("pnl", "alpha_os_timeseries"),
        required_any_keys=(),
        required_columns={
            "pnl": ("Date", "Equity", "Return"),
            "alpha_os_timeseries": ("timestamp", "regime_crisis", "regime_entropy"),
        },
        freshness_sla_hours=48.0,
        degraded_mode="block",
        description="Executive survival engine surface",
    ),
    "market_state_regime_pressure": ChartContract(
        chart_id="market_state_regime_pressure",
        required_data_keys=("market_regime",),
        required_any_keys=(),
        required_columns={"market_regime": ("Date",)},
        freshness_sla_hours=24.0,
        degraded_mode="block",
        description="Regime and risk-pressure live monitor",
    ),
    "portfolio_expression_vs_benchmark": ChartContract(
        chart_id="portfolio_expression_vs_benchmark",
        required_data_keys=("pnl", "index_nifty50"),
        required_any_keys=(),
        required_columns={"pnl": ("Date", "Equity"), "index_nifty50": ("close",)},
        freshness_sla_hours=24.0,
        degraded_mode="block",
        description="Portfolio vs benchmark normalized curve",
    ),
    "portfolio_expression_allocation_heatmap": ChartContract(
        chart_id="portfolio_expression_allocation_heatmap",
        required_data_keys=("allocation_history",),
        required_any_keys=(),
        required_columns={"allocation_history": ("date",)},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Recent allocation heatmap",
    ),
    "portfolio_expression_exposure": ChartContract(
        chart_id="portfolio_expression_exposure",
        required_data_keys=("allocation_history",),
        required_any_keys=(),
        required_columns={"allocation_history": ("date",)},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Portfolio total exposure over time",
    ),
    "portfolio_edge_health": ChartContract(
        chart_id="portfolio_edge_health",
        required_data_keys=("edge_half_life",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Edge health by strategy",
    ),
    "portfolio_exit_risk": ChartContract(
        chart_id="portfolio_exit_risk",
        required_data_keys=("liquidity_risk",),
        required_any_keys=(),
        required_columns={"liquidity_risk": ("ticker", "exit_risk")},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Liquidity exit-risk panel",
    ),
    "risk_survival_crisis_probability": ChartContract(
        chart_id="risk_survival_crisis_probability",
        required_data_keys=("alpha_os_timeseries",),
        required_any_keys=(),
        required_columns={"alpha_os_timeseries": ("timestamp",)},
        freshness_sla_hours=24.0,
        degraded_mode="block",
        description="Crisis probability trajectory",
    ),
    "risk_survival_drawdown_surface": ChartContract(
        chart_id="risk_survival_drawdown_surface",
        required_data_keys=("pnl",),
        required_any_keys=(),
        required_columns={"pnl": ("Date", "Return")},
        freshness_sla_hours=24.0,
        degraded_mode="warn",
        description="Empirical drawdown risk surface",
    ),
    "risk_survival_regime_entropy": ChartContract(
        chart_id="risk_survival_regime_entropy",
        required_data_keys=("alpha_os_timeseries",),
        required_any_keys=(),
        required_columns={"alpha_os_timeseries": ("timestamp", "regime_entropy")},
        freshness_sla_hours=24.0,
        degraded_mode="warn",
        description="Regime entropy uncertainty track",
    ),
    "risk_survival_systemic_stress": ChartContract(
        chart_id="risk_survival_systemic_stress",
        required_data_keys=("narrative_events",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=24.0,
        degraded_mode="warn",
        description="News systemic stress",
    ),
    "news_layer_narrative_shock_intensity": ChartContract(
        chart_id="news_layer_narrative_shock_intensity",
        required_data_keys=("narrative_events",),
        required_any_keys=(),
        required_columns={"narrative_events": ("date", "magnitude")},
        freshness_sla_hours=24.0,
        degraded_mode="warn",
        description="Narrative shock intensity",
    ),
    "market_state_macro_news_pressure": ChartContract(
        chart_id="market_state_macro_news_pressure",
        required_data_keys=("index_nifty50", "market_regime"),
        required_any_keys=(),
        required_columns={"index_nifty50": ("close",), "market_regime": ("Date",)},
        freshness_sla_hours=24.0,
        degraded_mode="block",
        description="Macro + news pressure integrated panel",
    ),
    "market_state_macro_heatmap": ChartContract(
        chart_id="market_state_macro_heatmap",
        required_data_keys=(),
        required_any_keys=("macro_factors_v2", "macro_factors"),
        required_columns={},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Macro factor activity heatmap",
    ),
    "market_state_sector_sentiment_vs_flows": ChartContract(
        chart_id="market_state_sector_sentiment_vs_flows",
        required_data_keys=("sector_flows",),
        required_any_keys=(),
        required_columns={"sector_flows": ("Industry", "flow_strength")},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Sector sentiment vs flow divergence",
    ),
    "news_layer_macro_news_pressure": ChartContract(
        chart_id="news_layer_macro_news_pressure",
        required_data_keys=("index_nifty50", "market_regime"),
        required_any_keys=(),
        required_columns={"index_nifty50": ("close",), "market_regime": ("Date",)},
        freshness_sla_hours=24.0,
        degraded_mode="warn",
        description="News layer macro pressure panel",
    ),
    "news_layer_sector_sentiment_vs_flows": ChartContract(
        chart_id="news_layer_sector_sentiment_vs_flows",
        required_data_keys=("sector_flows",),
        required_any_keys=(),
        required_columns={"sector_flows": ("Industry", "flow_strength")},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="News layer sector sentiment-flow divergence",
    ),
    "system_health_runtime_metrics": ChartContract(
        chart_id="system_health_runtime_metrics",
        required_data_keys=("system_log",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=24.0,
        degraded_mode="block",
        description="Runtime/system health trend",
    ),
    "system_health_sector_allocation": ChartContract(
        chart_id="system_health_sector_allocation",
        required_data_keys=("portfolio_weights",),
        required_any_keys=(),
        required_columns={"portfolio_weights": ("Industry", "weight")},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Real-time sector allocation snapshot",
    ),
    "market_state_sector_macro_heatmap": ChartContract(
        chart_id="market_state_sector_macro_heatmap",
        required_data_keys=("macro_impact_sector_heatmap",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=72.0,
        degraded_mode="warn",
        description="Sector-level macro sensitivity heatmap",
    ),
    "kalman_betas_chart": ChartContract(
        chart_id="kalman_betas_chart",
        required_data_keys=("macro_transmission_kalman",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Kalman filter macro beta estimates",
    ),
    "macro_expected_change_chart": ChartContract(
        chart_id="macro_expected_change_chart",
        required_data_keys=("macro_transmission_expected",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Macro expected change forecasts",
    ),
    "macro_adjusted_scores_chart": ChartContract(
        chart_id="macro_adjusted_scores_chart",
        required_data_keys=("macro_transmission_adjusted",),
        required_any_keys=(),
        required_columns={},
        freshness_sla_hours=48.0,
        degraded_mode="warn",
        description="Macro adjusted scores over time",
    ),
}


def evaluate_chart_contract(
    *,
    chart_id: str,
    data: Dict[str, object],
    meta: Dict[str, object],
    live_mode: bool,
) -> Dict[str, object]:
    contract = CHART_REGISTRY.get(chart_id)
    if contract is None:
        return {
            "status": "unknown",
            "badge": "⚪ Unregistered",
            "message": f"Chart contract missing for {chart_id}",
            "block": bool(live_mode),
        }

    missing_keys = [k for k in contract.required_data_keys if k not in data or data.get(k) is None]
    if missing_keys:
        block = bool(live_mode and contract.degraded_mode == "block")
        return {
            "status": "missing",
            "badge": "🔴 Missing Inputs",
            "message": f"Missing data keys: {', '.join(missing_keys)}",
            "block": block,
        }

    present_any_keys = []
    if contract.required_any_keys:
        present_any_keys = [k for k in contract.required_any_keys if k in data and data.get(k) is not None]
        if not present_any_keys:
            block = bool(live_mode and contract.degraded_mode == "block")
            return {
                "status": "missing",
                "badge": "🔴 Missing Inputs",
                "message": f"Missing any-of data keys: {', '.join(contract.required_any_keys)}",
                "block": block,
            }

    missing_cols = []
    for key, cols in contract.required_columns.items():
        frame = data.get(key)
        if not hasattr(frame, "columns"):
            continue
        frame_cols = set(getattr(frame, "columns"))
        for col in cols:
            if col not in frame_cols:
                missing_cols.append(f"{key}.{col}")
    if missing_cols:
        block = bool(live_mode and contract.degraded_mode == "block")
        return {
            "status": "missing",
            "badge": "🔴 Schema Gap",
            "message": f"Missing required columns: {', '.join(missing_cols)}",
            "block": block,
        }

    age_keys = list(contract.required_data_keys)
    if present_any_keys:
        age_keys.extend(present_any_keys)
    elif contract.required_any_keys:
        age_keys.extend(contract.required_any_keys)

    ages = [dataset_age_hours(meta, key) for key in age_keys]
    ages = [a for a in ages if a is not None]
    if not ages:
        return {
            "status": "unknown",
            "badge": "⚪ Freshness Unknown",
            "message": "No dataset freshness metadata",
            "block": False,
        }

    age = max(ages)
    if age <= contract.freshness_sla_hours:
        return {
            "status": "fresh",
            "badge": f"🟢 Fresh ({age:.1f}h)",
            "message": f"Within SLA ({contract.freshness_sla_hours:.0f}h)",
            "block": False,
        }

    if age <= contract.freshness_sla_hours * 7:
        return {
            "status": "stale",
            "badge": f"🟡 Stale ({age:.1f}h)",
            "message": f"SLA {contract.freshness_sla_hours:.0f}h breached",
            "block": False,
        }

    # Live-mode hard rule: expired charts are blocked regardless of degraded_mode.
    block = bool(live_mode)
    return {
        "status": "expired",
        "badge": f"🔴 Expired ({age:.1f}h)",
        "message": f"Expired beyond SLA {contract.freshness_sla_hours:.0f}h",
        "block": block,
    }
