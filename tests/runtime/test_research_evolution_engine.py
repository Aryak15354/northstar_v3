from __future__ import annotations

import pandas as pd

from src.runtime.conditional_parameter_engine import ConditionalParameterEngine
from src.runtime.regime_state_engine import BayesianRegimeStateEngine
from src.runtime.research_evolution_engine import ResearchEvolutionEngine


class _StubADE:
    def compute_strategy_diagnostics(self):
        return pd.DataFrame(
            [
                {"strategy_id": "s1", "avg_err": 0.45, "edge_decay": -0.04, "stability_score": 0.70},
                {"strategy_id": "s2", "avg_err": 0.55, "edge_decay": -0.03, "stability_score": 0.65},
            ]
        )


def test_research_evolution_cycle_emits_advisory_payload():
    regime_engine = BayesianRegimeStateEngine(
        n_states=3,
        confidence_threshold=0.55,
        min_persistence_days=3,
        cusum_h=0.05,
        cusum_k=0.002,
    )
    param_engine = ConditionalParameterEngine(
        {"lookback": 20.0},
        n_states=3,
        max_step_norm=0.15,
        min_regime_confidence=0.55,
        min_regime_persistence_days=3,
        require_structural_break=False,
    )
    param_engine.set_surface("lookback", [5.0, 0.0, -5.0])
    evo = ResearchEvolutionEngine(
        regime_engine=regime_engine,
        parameter_engine=param_engine,
        ade_engine=_StubADE(),
        lock_drawdown_threshold=0.2,
        degrade_err_threshold=0.60,
        degrade_decay_threshold=-0.02,
    )
    result = None
    for _ in range(5):
        result = evo.run_cycle(
            portfolio_snapshot={"regime_context": {}, "drawdown_ratio": 0.02},
            risk_snapshot={
                "trend_signal": -0.6,
                "vol_percentile": 0.9,
                "vol_of_vol": 0.85,
                "liquidity_quality": 0.3,
                "impact_risk": 0.8,
                "crowding_signal": 0.7,
                "breadth": 0.2,
                "correlation": 0.85,
                "drawdown_ratio": 0.02,
            },
        )
    assert result is not None
    payload = result.to_dict()
    assert "regime_state" in payload
    assert "parameter_update" in payload
    assert payload["performance_degraded"] is True
    assert payload["advisory_actions"]["action"] in {"hold", "apply_shadow_only", "freeze_parameter_mutation"}


def test_research_evolution_crisis_lock_prevents_mutation():
    regime_engine = BayesianRegimeStateEngine(n_states=3, confidence_threshold=0.5, min_persistence_days=1)
    param_engine = ConditionalParameterEngine(
        {"threshold": 1.0},
        n_states=3,
        require_structural_break=False,
        min_regime_confidence=0.5,
        min_regime_persistence_days=1,
    )
    param_engine.set_surface("threshold", [0.5, 0.0, -0.5])
    evo = ResearchEvolutionEngine(regime_engine=regime_engine, parameter_engine=param_engine, ade_engine=None, lock_drawdown_threshold=0.05)
    out = evo.run_cycle(
        portfolio_snapshot={"drawdown_ratio": 0.10},
        risk_snapshot={
            "trend_signal": 0.2,
            "vol_percentile": 0.3,
            "vol_of_vol": 0.3,
            "liquidity_quality": 0.7,
            "impact_risk": 0.3,
            "crowding_signal": 0.3,
            "breadth": 0.6,
            "correlation": 0.4,
            "drawdown_ratio": 0.10,
        },
    )
    payload = out.to_dict()
    assert payload["crisis_lock"] is True
    assert payload["parameter_update"]["mutated"] is False
    assert payload["advisory_actions"]["action"] == "freeze_parameter_mutation"
