from __future__ import annotations

from datetime import datetime, timezone

from src.runtime.alpha_mortality_controller import (
    AlphaMortalityController,
    AlphaMortalityProfile,
    MortalityState,
)


def _profile() -> AlphaMortalityProfile:
    return AlphaMortalityProfile(
        strategy_id="alpha_x",
        prior_mean=0.02,
        prior_variance=0.04,
        mc_sharpe_mean=0.8,
        mc_sharpe_std=0.2,
        mc_drawdown_mean=0.12,
        mc_drawdown_std=0.05,
        recovery_days_median=20.0,
        recovery_sigma=0.25,
        regime_sharpe_profile={"state_1": 0.8},
        regime_sigma=0.2,
        baseline_vol_cluster_acf1=0.1,
        baseline_skew=0.0,
        baseline_convexity=0.0,
        baseline_decay_lambda=0.01,
        capacity_limit_estimate=100.0,
        freeze_drawdown_limit=0.90,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def test_alpha_mortality_controller_transitions_to_shadow_then_freeze():
    controller = AlphaMortalityController(
        degrade_threshold=0.30,
        shadow_threshold=0.45,
        freeze_threshold=0.70,
        persistence_degrade=1,
        persistence_shadow=1,
        persistence_freeze=2,
        min_dwell_updates=1,
        entropy_gate=0.99,
    )

    state = {}
    bad_returns = [-0.03] * 96

    d1, state = controller.update_strategy(
        strategy_id="alpha_x",
        profile=_profile(),
        strategy_returns=bad_returns,
        regime_probabilities={"state_1": 1.0},
        strategy_state_payload=state,
        current_notional=10.0,
    )
    d2, state = controller.update_strategy(
        strategy_id="alpha_x",
        profile=_profile(),
        strategy_returns=bad_returns,
        regime_probabilities={"state_1": 1.0},
        strategy_state_payload=state,
        current_notional=10.0,
    )
    d3, state = controller.update_strategy(
        strategy_id="alpha_x",
        profile=_profile(),
        strategy_returns=bad_returns,
        regime_probabilities={"state_1": 1.0},
        strategy_state_payload=state,
        current_notional=10.0,
    )

    assert d1.state in {MortalityState.DEGRADING.value, MortalityState.SHADOW.value, MortalityState.FROZEN.value}
    assert d2.state in {MortalityState.SHADOW.value, MortalityState.FROZEN.value, MortalityState.DEGRADING.value}
    assert d3.state in {MortalityState.SHADOW.value, MortalityState.FROZEN.value}
    assert d3.capital_multiplier <= 0.60


def test_alpha_mortality_controller_capacity_breach_freezes():
    controller = AlphaMortalityController(min_dwell_updates=1)
    profile = _profile()
    profile = AlphaMortalityProfile(
        **{**profile.to_dict(), "capacity_limit_estimate": 50.0}
    )
    decision, _state = controller.update_strategy(
        strategy_id="alpha_x",
        profile=profile,
        strategy_returns=[0.001] * 64,
        regime_probabilities={"state_1": 1.0},
        strategy_state_payload={},
        current_notional=80.0,
    )
    assert decision.state == MortalityState.FROZEN.value
    assert decision.freeze is True
    assert decision.freeze_reason == "phase6.capacity_breach"
