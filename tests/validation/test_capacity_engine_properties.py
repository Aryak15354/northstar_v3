#!/usr/bin/env python3
"""
Property tests for Capacity Engine components.

Feature: capacity-engine
- Property 1: ADV constraint enforcement
- Property 2: Market impact monotonicity
- Property 3: Crowding penalty consistency
- Property 4: Capacity degradation with AUM
- Property 5: Liquidity classification stability
- Property 6: Execution cost realism
- Property 7: Stress conservatism
- Property 8: Capital conservation
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from src.execution.execution_reality_engine import ExecutionRealityEngine
from src.execution.market_impact_model import MarketImpactModel
from src.intelligence.adv_database import ADVConfig, ADVDatabase
from src.intelligence.crowding_penalty_system import CrowdingPenaltySystem
from src.intelligence.position_governor import GovernorConfig, PositionGovernor
from src.portfolio.liquidity_aware_constructor import LiquidityAwarePortfolioConstructor
from src.validation.capacity_analysis_engine import CapacityAnalysisEngine
from src.validation.capacity_stress_tester import CapacityStressTester


def _build_adv_db() -> ADVDatabase:
    np.random.seed(123)
    adv_db = ADVDatabase(
        ADVConfig(
            min_adv_threshold=1_000_000,
            mid_cap_threshold=5_000_000,
            large_cap_threshold=50_000_000,
            max_staleness_days=36500,  # historical synthetic data should not be rejected as stale
        )
    )
    dates = pd.date_range("2025-01-01", periods=200, freq="D")
    symbols = {
        "LARGE.NS": (4_000_000, 1800.0),
        "MID.NS": (900_000, 450.0),
        "SMALL.NS": (120_000, 120.0),
    }
    for sym, (vol, px) in symbols.items():
        vol_series = vol * np.clip(np.random.normal(1.0, 0.08, len(dates)), 0.2, None)
        px_series = px * np.clip(np.random.normal(1.0, 0.03, len(dates)), 0.4, None)
        adv_db.add_volume_data(
            sym,
            pd.DataFrame({"date": dates, "volume": vol_series}),
            pd.DataFrame({"date": dates, "close": px_series}),
        )
    return adv_db


@given(
    w1=st.floats(min_value=0.01, max_value=0.80),
    w2=st.floats(min_value=0.01, max_value=0.80),
    w3=st.floats(min_value=0.01, max_value=0.80),
)
@settings(max_examples=25, deadline=5000)
def test_property_1_adv_constraint_enforcement(w1: float, w2: float, w3: float) -> None:
    adv_db = _build_adv_db()
    governor = PositionGovernor(
        adv_db,
        GovernorConfig(
            alpha_factors={"large_cap": 0.05, "mid_cap": 0.03, "small_cap": 0.01, "default": 0.03}
        ),
    )

    weights = {"LARGE.NS": w1, "MID.NS": w2, "SMALL.NS": w3}
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}
    portfolio_value = 100_000_000.0

    constrained = governor.apply_liquidity_constraints(weights, portfolio_value=portfolio_value)
    for symbol, w in constrained.items():
        lim = governor.calculate_max_position(symbol)
        if lim.max_position_value <= 0:
            assert w == 0.0
        else:
            assert abs(w) * portfolio_value <= lim.max_position_value + 1e-6


@given(
    small=st.floats(min_value=100_000, max_value=2_000_000),
    large=st.floats(min_value=2_100_000, max_value=8_000_000),
    volatility=st.floats(min_value=0.05, max_value=0.80),
)
@settings(max_examples=30, deadline=5000)
def test_property_2_market_impact_monotonicity(small: float, large: float, volatility: float) -> None:
    model = MarketImpactModel()
    adv = 20_000_000.0
    i_small = model.calculate_impact(small, adv, volatility)
    i_large = model.calculate_impact(large, adv, volatility)
    assert i_large >= i_small


@given(corr=st.floats(min_value=0.70, max_value=0.99))
@settings(max_examples=25, deadline=5000)
def test_property_3_crowding_penalty_consistency(corr: float) -> None:
    system = CrowdingPenaltySystem()
    p = system.penalty_for_correlation(corr)
    assert 0.0 < p <= 1.0
    if corr > 0.70:
        assert p < 1.0

    combined = system.combined_penalty({"mtum": corr, "qual": corr})
    assert combined <= p + 1e-12  # multiplicative penalties should not be weaker


def test_property_4_capacity_degradation_with_aum() -> None:
    engine = CapacityAnalysisEngine()
    report = engine.run_capacity_sweep()
    cagr = [m.cagr for m in report.metrics]
    # Conservative model should be monotonic non-increasing.
    for i in range(1, len(cagr)):
        assert cagr[i] <= cagr[i - 1] + 1e-12


def test_property_5_liquidity_classification_stability() -> None:
    adv_db = _build_adv_db()
    # Simulate month-long daily checks; tiers should remain stable under normal data.
    dates = pd.date_range("2025-06-01", periods=30, freq="D")
    tiers = []
    for d in dates:
        data = adv_db.calculate_rolling_adv("MID.NS", as_of_date=d.to_pydatetime())
        assert data is not None
        tiers.append(data.liquidity_tier.value)
    changes = sum(1 for i in range(1, len(tiers)) if tiers[i] != tiers[i - 1])
    assert changes <= 1


def test_property_6_execution_cost_realism() -> None:
    engine = ExecutionRealityEngine()
    result = engine.simulate_execution(
        symbol="LARGE.NS",
        side="buy",
        order_notional=6_000_000.0,  # >5% ADV when ADV=100M
        mid_price=1000.0,
        adv=100_000_000.0,
        volatility=0.25,
        liquidity_tier="large_cap",
        market_stress=False,
    )
    assert result.num_slices >= 2
    assert result.implementation_shortfall >= 0.0
    assert result.total_cost >= 0.0
    assert result.average_fill_price >= result.theoretical_mid_price


def test_property_7_stress_conservatism() -> None:
    engine = CapacityAnalysisEngine()
    normal = engine.run_capacity_sweep()
    stress = CapacityStressTester(engine).run_stress_tests()
    assert stress.stress_adjusted_recommendation <= normal.max_recommended_aum


@given(
    a=st.floats(min_value=0.01, max_value=0.90),
    b=st.floats(min_value=0.01, max_value=0.90),
    c=st.floats(min_value=0.01, max_value=0.90),
)
@settings(max_examples=25, deadline=5000)
def test_property_8_capital_conservation(a: float, b: float, c: float) -> None:
    adv_db = _build_adv_db()
    governor = PositionGovernor(
        adv_db,
        GovernorConfig(
            alpha_factors={"large_cap": 0.05, "mid_cap": 0.03, "small_cap": 0.01, "default": 0.03}
        ),
    )
    constructor = LiquidityAwarePortfolioConstructor(adv_db, governor, min_cash_buffer=0.20)

    weights = {"LARGE.NS": a, "MID.NS": b, "SMALL.NS": c}
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    result = constructor.construct_portfolio(weights, portfolio_value=100_000_000.0, market_stress=False)
    total_weight = sum(float(v) for v in result.weights.values())
    assert total_weight <= 1.0 + 1e-9
    assert result.weights.get("CASH", 0.0) >= 0.20 - 1e-9

