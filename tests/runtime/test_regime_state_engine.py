from __future__ import annotations

from src.runtime.regime_state_engine import BayesianRegimeStateEngine


def test_regime_state_probabilities_and_confidence_bounds():
    engine = BayesianRegimeStateEngine(n_states=3, min_persistence_days=3)
    obs = {
        "trend_signal": 0.2,
        "vol_percentile": 0.35,
        "vol_of_vol": 0.25,
        "liquidity_quality": 0.70,
        "impact_risk": 0.20,
        "crowding_signal": 0.30,
        "breadth": 0.65,
        "correlation": 0.40,
    }
    out = engine.update(obs)
    probs = out.state_probabilities
    assert abs(sum(probs.values()) - 1.0) < 1e-9
    assert 0.0 <= out.confidence <= 1.0
    assert out.persistence_days >= 1
    assert out.dominant_state in probs


def test_regime_transition_confirmation_requires_persistence():
    engine = BayesianRegimeStateEngine(n_states=3, min_persistence_days=4, confidence_threshold=0.55)
    low_risk_obs = {
        "trend_signal": 0.35,
        "vol_percentile": 0.20,
        "vol_of_vol": 0.20,
        "liquidity_quality": 0.75,
        "impact_risk": 0.20,
        "crowding_signal": 0.30,
        "breadth": 0.70,
        "correlation": 0.25,
    }
    confirmed = False
    for i in range(5):
        out = engine.update(
            low_risk_obs,
            timestamp_utc=f"2026-01-{i+1:02d}T00:00:00+00:00",
        )
        confirmed = confirmed or bool(out.transition_confirmed)
    assert confirmed is True
    assert out.persistence_days >= 4


def test_regime_structural_break_detected_under_extreme_shift():
    engine = BayesianRegimeStateEngine(n_states=3, cusum_h=0.04, cusum_k=0.002)
    calm = {
        "trend_signal": 0.10,
        "vol_percentile": 0.20,
        "vol_of_vol": 0.15,
        "liquidity_quality": 0.80,
        "impact_risk": 0.10,
        "crowding_signal": 0.20,
        "breadth": 0.75,
        "correlation": 0.20,
    }
    stress = {
        "trend_signal": -0.90,
        "vol_percentile": 0.98,
        "vol_of_vol": 0.96,
        "liquidity_quality": 0.10,
        "impact_risk": 0.95,
        "crowding_signal": 0.95,
        "breadth": 0.05,
        "correlation": 0.98,
    }
    for _ in range(6):
        engine.update(calm)
    found_break = False
    for _ in range(20):
        out = engine.update(stress)
        if out.structural_break:
            found_break = True
            break
    assert found_break is True


def test_same_day_updates_do_not_increment_persistence_counter():
    engine = BayesianRegimeStateEngine(n_states=3, min_persistence_days=10)
    obs = {
        "trend_signal": 0.25,
        "vol_percentile": 0.25,
        "vol_of_vol": 0.2,
        "liquidity_quality": 0.8,
        "impact_risk": 0.15,
        "crowding_signal": 0.2,
        "breadth": 0.7,
        "correlation": 0.3,
    }
    out1 = engine.update(obs, timestamp_utc="2026-01-10T09:00:00+00:00")
    out2 = engine.update(obs, timestamp_utc="2026-01-10T15:30:00+00:00")
    out3 = engine.update(obs, timestamp_utc="2026-01-11T09:00:00+00:00")
    assert out2.persistence_days == out1.persistence_days
    assert out3.persistence_days == out2.persistence_days + 1


def test_regime_engine_state_roundtrip_restores_posterior():
    engine = BayesianRegimeStateEngine(n_states=3, min_persistence_days=3)
    obs = {
        "trend_signal": -0.3,
        "vol_percentile": 0.85,
        "vol_of_vol": 0.75,
        "liquidity_quality": 0.25,
        "impact_risk": 0.85,
        "crowding_signal": 0.8,
        "breadth": 0.2,
        "correlation": 0.85,
    }
    for i in range(3):
        engine.update(obs, timestamp_utc=f"2026-02-{i+1:02d}T00:00:00+00:00")
    state = engine.to_state_dict()
    engine2 = BayesianRegimeStateEngine(n_states=3, min_persistence_days=3)
    engine2.load_state_dict(state)
    out = engine2.update(obs, timestamp_utc="2026-02-04T00:00:00+00:00")
    assert abs(sum(out.state_probabilities.values()) - 1.0) < 1e-9
    assert out.persistence_days >= 3
