from __future__ import annotations

import numpy as np

from src.runtime.conditional_parameter_engine import ConditionalParameterEngine


def test_conditional_parameter_engine_gates_on_confidence_and_break():
    engine = ConditionalParameterEngine(
        {"lookback": 20.0, "threshold": 1.5},
        n_states=3,
        max_step_norm=0.2,
        min_regime_confidence=0.8,
        min_regime_persistence_days=5,
        require_structural_break=True,
    )
    engine.set_surface("lookback", np.array([5.0, 0.0, -5.0], dtype=float))
    engine.set_surface("threshold", np.array([0.2, 0.0, -0.2], dtype=float))

    no_update = engine.update(
        regime_state={
            "state_probabilities": {"state_0": 0.7, "state_1": 0.2, "state_2": 0.1},
            "confidence": 0.60,
            "persistence_days": 6,
            "structural_break": True,
        },
        performance_degraded=True,
        crisis_lock=False,
    )
    assert no_update.mutated is False
    assert no_update.reason == "regime_confidence_below_threshold"


def test_conditional_parameter_engine_updates_with_bounded_step():
    engine = ConditionalParameterEngine(
        {"lookback": 20.0, "threshold": 1.5},
        n_states=3,
        max_step_norm=0.1,
        min_regime_confidence=0.5,
        min_regime_persistence_days=2,
        require_structural_break=False,
    )
    engine.set_surface("lookback", np.array([10.0, 0.0, -10.0], dtype=float))
    engine.set_surface("threshold", np.array([1.0, 0.0, -1.0], dtype=float))
    out = engine.update(
        regime_state={
            "state_probabilities": {"state_0": 1.0, "state_1": 0.0, "state_2": 0.0},
            "confidence": 0.9,
            "persistence_days": 3,
            "structural_break": False,
        },
        performance_degraded=True,
        crisis_lock=False,
    )
    assert out.mutated is True
    assert out.applied_step_norm <= 0.1000001
    assert out.parameters["lookback"] > 20.0


def test_conditional_parameter_engine_crisis_lock_holds_parameters():
    engine = ConditionalParameterEngine({"a": 1.0}, n_states=3, require_structural_break=False)
    engine.set_surface("a", np.array([1.0, 0.0, -1.0], dtype=float))
    out = engine.update(
        regime_state={
            "state_probabilities": {"state_0": 0.9, "state_1": 0.1, "state_2": 0.0},
            "confidence": 0.95,
            "persistence_days": 10,
            "structural_break": True,
        },
        performance_degraded=True,
        crisis_lock=True,
    )
    assert out.mutated is False
    assert out.reason == "crisis_lock"
    assert out.parameters["a"] == 1.0


def test_conditional_parameter_engine_state_roundtrip():
    engine = ConditionalParameterEngine({"a": 1.0}, n_states=3, require_structural_break=False)
    engine.set_surface("a", np.array([0.2, 0.0, -0.2], dtype=float))
    engine.update(
        regime_state={
            "state_probabilities": {"state_0": 1.0, "state_1": 0.0, "state_2": 0.0},
            "confidence": 0.95,
            "persistence_days": 3,
            "structural_break": True,
        },
        performance_degraded=True,
        crisis_lock=False,
    )
    payload = engine.to_state_dict()
    restored = ConditionalParameterEngine({"a": 1.0}, n_states=3, require_structural_break=False)
    restored.load_state_dict(payload)
    assert "a" in restored.current_parameters
    assert restored.current_parameters["a"] == engine.current_parameters["a"]
