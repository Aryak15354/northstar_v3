from __future__ import annotations

import pandas as pd

from src.research.meta import AlphaExperienceMemory, MetaPolicyStore, ResearchEvolutionEngineV2
from src.runtime.conditional_parameter_engine import ConditionalParameterEngine
from src.runtime.regime_state_engine import BayesianRegimeStateEngine
from src.runtime.research_evolution_engine import ResearchEvolutionEngine


class _StubADEForPhase7:
    def compute_strategy_diagnostics(self):
        return pd.DataFrame(
            [
                {
                    "strategy_id": "momentum",
                    "avg_err": 0.95,
                    "edge_decay": -0.01,
                    "stability_score": 0.80,
                    "sharpe": 1.10,
                    "certification_survival_ratio": 0.78,
                    "regime_sensitivity": 0.25,
                },
                {
                    "strategy_id": "reversion",
                    "avg_err": 0.72,
                    "edge_decay": -0.02,
                    "stability_score": 0.70,
                    "sharpe": 0.86,
                    "certification_survival_ratio": 0.68,
                    "regime_sensitivity": 0.35,
                },
            ]
        )


def test_phase7_engine_updates_versioned_policy(tmp_path):
    memory = AlphaExperienceMemory(db_path=str(tmp_path / "aem.db"))
    store = MetaPolicyStore(policy_path=str(tmp_path / "meta_policy.json"))
    engine = ResearchEvolutionEngineV2(memory=memory, policy_store=store, min_history_to_adapt=5)

    experiments = [
        {
            "experiment_id": f"exp_m_{i}",
            "family": "momentum",
            "parameter_vector": {"lookback": 20 + i, "holding": 5},
            "regime_features": {"regime": "state_1"},
            "metrics": {"wf_sharpe": 1.0, "mc_survival": 0.8, "phase6_longevity": 0.9, "surface_fragility": 0.2},
            "durability_score": 0.78,
        }
        for i in range(12)
    ]
    experiments.extend(
        {
            "experiment_id": f"exp_r_{i}",
            "family": "reversion",
            "parameter_vector": {"lookback": 3 + i, "holding": 2},
            "regime_features": {"regime": "state_2"},
            "metrics": {"wf_sharpe": 0.7, "mc_survival": 0.6, "phase6_longevity": 0.6, "surface_fragility": 0.5},
            "durability_score": 0.42,
        }
        for i in range(12)
    )

    safe_bounds = {
        "momentum": {"lookback": (5.0, 250.0), "holding": (1.0, 60.0)},
        "reversion": {"lookback": (1.0, 20.0), "holding": (1.0, 10.0)},
    }

    p1 = engine.run_cycle(experiments=experiments, safe_parameter_bounds=safe_bounds)
    p2 = engine.run_cycle(experiments=experiments, safe_parameter_bounds=safe_bounds)
    memory.close()

    assert int(p1.get("version", 0)) == 1
    assert int(p2.get("version", 0)) == 2
    weights = dict(p2.get("family_compute_weights", {}) or {})
    assert set(weights) >= {"momentum", "reversion"}
    assert abs(sum(float(v) for v in weights.values()) - 1.0) < 1e-6
    assert 0.05 <= float(p2.get("exploration_rate", 0.0)) <= 0.35


def test_runtime_research_evolution_engine_emits_phase7_policy(tmp_path):
    regime_engine = BayesianRegimeStateEngine(
        n_states=3,
        confidence_threshold=0.55,
        min_persistence_days=1,
    )
    param_engine = ConditionalParameterEngine(
        {"size_multiplier": 1.0, "lookback": 20.0},
        n_states=3,
        max_step_norm=0.10,
        min_regime_confidence=0.55,
        min_regime_persistence_days=1,
        require_structural_break=False,
        parameter_bounds={"size_multiplier": (0.5, 1.5), "lookback": (5.0, 120.0)},
    )
    param_engine.set_surface("size_multiplier", [0.1, 0.0, -0.1])

    memory = AlphaExperienceMemory(db_path=str(tmp_path / "aem_runtime.db"))
    store = MetaPolicyStore(policy_path=str(tmp_path / "meta_policy_runtime.json"))
    phase7_engine = ResearchEvolutionEngineV2(memory=memory, policy_store=store, min_history_to_adapt=1)

    evo = ResearchEvolutionEngine(
        regime_engine=regime_engine,
        parameter_engine=param_engine,
        ade_engine=_StubADEForPhase7(),
        phase7_engine=phase7_engine,
        lock_drawdown_threshold=0.2,
        degrade_err_threshold=0.90,
        degrade_decay_threshold=-0.02,
    )

    out = evo.run_cycle(
        portfolio_snapshot={"drawdown_ratio": 0.01},
        risk_snapshot={
            "trend_signal": 0.2,
            "vol_percentile": 0.4,
            "vol_of_vol": 0.35,
            "liquidity_quality": 0.8,
            "impact_risk": 0.25,
            "crowding_signal": 0.2,
            "breadth": 0.7,
            "correlation": 0.45,
            "drawdown_ratio": 0.01,
        },
    )
    payload = out.to_dict()
    phase7 = dict(payload.get("phase7_policy", {}) or {})
    memory.close()

    assert phase7.get("status") in {"updated", "no_data"}
    assert int(phase7.get("version", 0)) >= 1
    assert "family_compute_weights" in phase7
