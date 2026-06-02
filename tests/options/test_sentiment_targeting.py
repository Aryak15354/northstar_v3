from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import scripts.run_integrated_options_paper_engine as options_engine_module
from src.options.strategy_generator import Greeks, OptionStrategy, StrategyType
from src.volatility.regime_detector import VolatilityRegime


def _write_company_sentiment(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_market_sentiment(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_intraday_company_trends(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _strategy(strategy_type: StrategyType, underlying: str = "NIFTY") -> OptionStrategy:
    created_at = datetime(2026, 3, 20, 9, 30)
    expiry = datetime(2026, 3, 27, 15, 30)
    return OptionStrategy(
        strategy_type=strategy_type,
        legs=[],
        underlying=underlying,
        underlying_price=100.0,
        regime=VolatilityRegime.TRANSITION,
        max_loss=10_000.0,
        max_profit=20_000.0,
        net_credit_debit=-1_500.0,
        portfolio_greeks=Greeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0),
        created_at=created_at,
        expiry_date=expiry,
        days_to_expiry=7,
        is_valid=True,
    )


def test_negative_sentiment_returns_put_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(options_engine_module, "PROJECT_ROOT", tmp_path)

    _write_company_sentiment(
        tmp_path / "data/canonical/sentiment/company_sentiment_daily.parquet",
        [
            {
                "ticker": "RELIANCE.NS",
                "date": "2026-03-18",
                "availability_date": "2026-03-19",
                "sentiment_polarity": -0.70,
                "sentiment_conviction": 0.95,
            },
            {
                "ticker": "HDFCBANK.NS",
                "date": "2026-03-18",
                "availability_date": "2026-03-19",
                "sentiment_polarity": -0.45,
                "sentiment_conviction": 0.80,
            },
            {
                "ticker": "TCS.NS",
                "date": "2026-03-18",
                "availability_date": "2026-03-19",
                "sentiment_polarity": 0.60,
                "sentiment_conviction": 0.90,
            },
        ],
    )

    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}

    buckets = engine.get_sentiment_ranked_underlyings(
        ["RELIANCE", "TCS", "HDFCBANK"],
        datetime(2026, 3, 20, 10, 0),
        top_n=3,
    )

    assert buckets["put_candidates"][:2] == ["RELIANCE", "HDFCBANK"]


def test_positive_market_prioritizes_call_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(options_engine_module, "PROJECT_ROOT", tmp_path)

    _write_company_sentiment(
        tmp_path / "data/canonical/sentiment/company_sentiment_daily.parquet",
        [
            {
                "ticker": "TCS.NS",
                "date": "2026-03-18",
                "availability_date": "2026-03-19",
                "sentiment_polarity": 0.75,
                "sentiment_conviction": 0.90,
            },
            {
                "ticker": "RELIANCE.NS",
                "date": "2026-03-18",
                "availability_date": "2026-03-19",
                "sentiment_polarity": -0.25,
                "sentiment_conviction": 0.70,
            },
            {
                "ticker": "HDFCBANK.NS",
                "date": "2026-03-18",
                "availability_date": "2026-03-19",
                "sentiment_polarity": 0.15,
                "sentiment_conviction": 0.60,
            },
        ],
    )
    _write_market_sentiment(
        tmp_path / "data/canonical/sentiment/market_sentiment_daily.parquet",
        [
            {
                "date": "2026-03-20",
                "availability_date": "2026-03-20",
                "india_market_polarity": 0.70,
                "india_market_conviction": 0.80,
                "global_risk_sentiment": 0.75,
            }
        ],
    )

    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.portfolio_overlay_enabled = False
    engine.underlyings = ["RELIANCE", "TCS", "HDFCBANK"]
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}

    overlay: dict = {}
    ordered = engine._resolve_cycle_underlyings(overlay)

    assert ordered[0] == "TCS"
    assert overlay["sentiment_targeting"]["selection_mode"] == "call_priority"


def test_crisis_override_selects_bear_put_and_bypasses_alpha_gate() -> None:
    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}
    engine.portfolio_overlay = {
        "sentiment_targeting": {
            "market_signal": {
                "sentiment_crisis_detected": True,
                "effective_global_risk_sentiment": -0.95,
            }
        }
    }
    engine.alpha_os_enabled = True
    engine.alpha_os_enforce_mode = True
    engine.alpha_os_last_intent = {
        "mode": "enforce",
        "strategy_weights": {
            "bear_put_spread": -0.25,
            "long_straddle": 0.75,
        },
    }
    engine.strategy_generator = SimpleNamespace(
        generate_strategy=lambda **kwargs: [],
    )
    engine.position_manager = SimpleNamespace(
        calculate_portfolio_greeks=lambda: Greeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0),
    )
    engine._generate_strategy_candidate = lambda strategy_name, **kwargs: {
        "bear_put_spread": _strategy(StrategyType.BEAR_PUT_SPREAD),
        "long_straddle": _strategy(StrategyType.LONG_STRADDLE),
    }.get(strategy_name)
    engine._indicative_candidate_lots = lambda *args, **kwargs: 1
    engine._prs_liquidity_snapshot = lambda *args, **kwargs: {}
    engine._passes_net_profit_gate = lambda *args, **kwargs: {
        "passed": True,
        "expected_net_pnl": 250.0,
        "min_threshold": 0.0,
    }
    engine._score_strategy_candidate = lambda strategy, **kwargs: (
        0.95 if strategy.strategy_type == StrategyType.LONG_STRADDLE else 0.60,
        {},
    )

    strategy, selector = engine._generate_portfolio_aware_strategy(
        underlying="NIFTY",
        routed_regime="transition",
        option_chain=pd.DataFrame({"underlying_price": [100.0]}),
        objective="balanced_overlay",
        overlay=engine.portfolio_overlay,
    )

    assert strategy is not None
    assert strategy.strategy_type == StrategyType.BEAR_PUT_SPREAD
    assert selector["crisis_override_applied"] is True
    assert engine._alpha_os_strategy_blocked("bear_put_spread")[0] is True
    assert engine._should_bypass_alpha_os_strategy_gate(
        "NIFTY",
        "bear_put_spread",
        engine.portfolio_overlay,
    ) is True


def test_index_execution_requires_explicit_hedge_mode() -> None:
    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}

    allowed, meta = engine._execution_allowed_for_underlying(
        "NIFTY",
        {"objective": "event_shock_hedge"},
        {
            "index_objectives": {"NIFTY": "event_shock_hedge"},
            "sentiment_targeting": {"execution_candidates": ["TATASTEEL"]},
            "explicit_hedge_mode": False,
        },
    )

    assert allowed is False
    assert meta["eligibility_reason"] == "index_scan_only_until_explicit_hedge_mode"


def test_index_execution_is_allowed_when_explicit_hedge_mode_is_on() -> None:
    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}

    allowed, meta = engine._execution_allowed_for_underlying(
        "NIFTY",
        {"objective": "event_shock_hedge"},
        {
            "index_objectives": {"NIFTY": "event_shock_hedge"},
            "sentiment_targeting": {"execution_candidates": ["TATASTEEL"]},
            "explicit_hedge_mode": True,
        },
    )

    assert allowed is True
    assert meta["eligibility_reason"] == "explicit_hedge_mode_active"


def test_sentiment_unavailability_falls_back_to_unranked_universe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(options_engine_module, "PROJECT_ROOT", tmp_path)

    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}

    buckets = engine.get_sentiment_ranked_underlyings(
        ["NIFTY", "BANKNIFTY", "RELIANCE"],
        datetime(2026, 3, 20, 10, 0),
        top_n=3,
    )

    assert buckets["call_candidates"] == ["NIFTY", "BANKNIFTY", "RELIANCE"]
    assert buckets["put_candidates"] == ["NIFTY", "BANKNIFTY", "RELIANCE"]
    assert buckets["straddle_candidates"] == ["NIFTY", "BANKNIFTY", "RELIANCE"]


def test_intraday_nlp_signal_drives_execution_candidates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(options_engine_module, "PROJECT_ROOT", tmp_path)

    _write_company_sentiment(
        tmp_path / "data/canonical/sentiment/company_sentiment_daily.parquet",
        [
            {
                "ticker": "RELIANCE.NS",
                "date": "2026-03-25",
                "availability_date": "2026-03-26",
                "sentiment_polarity": 0.30,
                "sentiment_conviction": 0.70,
                "headline_count": 2,
                "market_moving_count": 0,
            },
            {
                "ticker": "TCS.NS",
                "date": "2026-03-25",
                "availability_date": "2026-03-26",
                "sentiment_polarity": 0.10,
                "sentiment_conviction": 0.45,
                "headline_count": 1,
                "market_moving_count": 0,
            },
            {
                "ticker": "HDFCBANK.NS",
                "date": "2026-03-25",
                "availability_date": "2026-03-26",
                "sentiment_polarity": -0.18,
                "sentiment_conviction": 0.55,
                "headline_count": 2,
                "market_moving_count": 1,
            },
        ],
    )
    _write_intraday_company_trends(
        tmp_path / "data/sentiment/v3/company_sentiment_trends.parquet",
        [
            {
                "timestamp": "2026-03-26T04:15:00+00:00",
                "ticker": "TCS.NS",
                "sentiment_score": 0.82,
                "sentiment_label": "positive",
                "trend_score": 0.76,
                "event_shock_factor": 0.18,
                "headline_count": 7,
            },
            {
                "timestamp": "2026-03-26T04:15:00+00:00",
                "ticker": "HDFCBANK.NS",
                "sentiment_score": -0.72,
                "sentiment_label": "negative",
                "trend_score": 0.66,
                "event_shock_factor": 0.24,
                "headline_count": 6,
            },
        ],
    )

    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}

    buckets = engine.get_sentiment_ranked_underlyings(
        ["RELIANCE", "TCS", "HDFCBANK"],
        datetime(2026, 3, 26, 10, 0),
        top_n=3,
    )

    assert buckets["call_candidates"][0] == "TCS"
    assert buckets["put_candidates"][0] == "HDFCBANK"
    assert {"TCS", "HDFCBANK"}.issubset(set(buckets["execution_candidates"][:2]))
    assert (
        buckets["signal_scores"]["TCS"]["exact_sentiment_signal"]
        > buckets["signal_scores"]["RELIANCE"]["exact_sentiment_signal"]
    )


def test_resolve_cycle_underlyings_adds_exact_sentiment_execution_plan(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(options_engine_module, "PROJECT_ROOT", tmp_path)

    _write_company_sentiment(
        tmp_path / "data/canonical/sentiment/company_sentiment_daily.parquet",
        [
            {
                "ticker": "TCS.NS",
                "date": "2026-03-25",
                "availability_date": "2026-03-26",
                "sentiment_polarity": 0.28,
                "sentiment_conviction": 0.80,
                "headline_count": 3,
                "market_moving_count": 1,
            },
            {
                "ticker": "RELIANCE.NS",
                "date": "2026-03-25",
                "availability_date": "2026-03-26",
                "sentiment_polarity": -0.24,
                "sentiment_conviction": 0.75,
                "headline_count": 2,
                "market_moving_count": 1,
            },
            {
                "ticker": "HDFCBANK.NS",
                "date": "2026-03-25",
                "availability_date": "2026-03-26",
                "sentiment_polarity": 0.05,
                "sentiment_conviction": 0.40,
                "headline_count": 1,
                "market_moving_count": 0,
            },
        ],
    )
    _write_intraday_company_trends(
        tmp_path / "data/sentiment/v3/company_sentiment_trends.parquet",
        [
            {
                "timestamp": "2026-03-26T04:15:00+00:00",
                "ticker": "TCS.NS",
                "sentiment_score": 0.85,
                "sentiment_label": "positive",
                "trend_score": 0.72,
                "event_shock_factor": 0.12,
                "headline_count": 8,
            },
            {
                "timestamp": "2026-03-26T04:15:00+00:00",
                "ticker": "RELIANCE.NS",
                "sentiment_score": -0.78,
                "sentiment_label": "negative",
                "trend_score": 0.64,
                "event_shock_factor": 0.28,
                "headline_count": 7,
            },
        ],
    )

    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.portfolio_overlay_enabled = True
    engine.underlyings = ["TCS", "RELIANCE", "HDFCBANK"]
    engine.stock_key_reverse_map = {}
    engine.instrument_key_reverse_map = {}
    engine._resolve_key = lambda symbol: f"KEY::{symbol}"
    engine.stock_loader = SimpleNamespace(
        get_stock=lambda symbol: SimpleNamespace(sector="technology", instrument_key=f"KEY::{symbol}"),
        get_all_symbols=lambda: [],
    )

    overlay = {
        "dynamic_underlyings": ["TCS", "RELIANCE", "HDFCBANK"],
        "stock_objectives": {},
        "index_objectives": {},
        "sentiment_context": {},
    }

    ordered = engine._resolve_cycle_underlyings(overlay)

    assert ordered[0] == "TCS"
    assert {"TCS", "RELIANCE"}.issubset(set(overlay["sentiment_targeting"]["execution_candidates"][:2]))
    assert overlay["stock_objectives"]["TCS"]["objective"] == "alpha_momentum"
    assert overlay["stock_objectives"]["RELIANCE"]["objective"] in {"protect_core", "event_shock_hedge"}
