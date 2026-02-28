from __future__ import annotations

from src.risk.survival_core_mode import SurvivalCoreMode


def test_survival_core_activates_on_two_conditions_and_clamps() -> None:
    mode = SurvivalCoreMode()
    state = mode.evaluate(
        crisis_probability=0.75,
        convexity_score=0.20,
        drawdown=0.05,
        entropy=0.30,
        n_states=4,
    )
    assert state["active"] is True

    weights = {"short_vol": 0.8, "long_vol": 0.2}
    adjusted, report = mode.apply_overrides(
        weights=weights,
        strategy_metadata={
            "short_vol": {"is_short_convexity": True, "convexity_score": 0.4},
            "long_vol": {"is_short_convexity": False, "convexity_score": 0.1},
        },
        allowed_gross_cap=1.0,
    )
    assert adjusted["short_vol"] == 0.0
    assert sum(abs(v) for v in adjusted.values()) <= 0.40 + 1e-9
    assert report["lock_new_risk"] is True


def test_survival_core_hysteresis_exit() -> None:
    mode = SurvivalCoreMode()
    mode.evaluate(
        crisis_probability=0.70,
        convexity_score=0.20,
        drawdown=0.20,
        entropy=2.0,
        n_states=4,
    )
    # keep active for minimum cycles
    for _ in range(max(1, mode.config.min_active_cycles)):
        mode.evaluate(
            crisis_probability=0.35,
            convexity_score=0.01,
            drawdown=0.01,
            entropy=0.01,
            n_states=4,
        )
    state = mode.evaluate(
        crisis_probability=0.35,
        convexity_score=0.01,
        drawdown=0.01,
        entropy=0.01,
        n_states=4,
    )
    assert state["active"] is False
