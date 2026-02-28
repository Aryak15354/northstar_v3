from __future__ import annotations

import numpy as np

from src.models.regime_probability_engine import FrozenRegimeHMM
from src.validation.regime_drift_monitor import RegimeDriftMonitor


def _model() -> FrozenRegimeHMM:
    k = 4
    d = 3
    return FrozenRegimeHMM(
        states=["LOW_VOL", "HIGH_VOL", "CRISIS", "TRANSITION"],
        transition_matrix=np.array(
            [
                [0.80, 0.10, 0.02, 0.08],
                [0.15, 0.65, 0.10, 0.10],
                [0.05, 0.20, 0.60, 0.15],
                [0.25, 0.30, 0.15, 0.30],
            ],
            dtype=float,
        ),
        emission_means=np.zeros((k, d), dtype=float),
        emission_covs=np.array([np.eye(d, dtype=float) for _ in range(k)]),
        initial_probs=np.full(k, 1.0 / k, dtype=float),
        feature_names=["a", "b", "c"],
        model_version="test",
        trained_at="2026-01-01T00:00:00+00:00",
        training_rows=1000,
        metadata={},
    )


def test_regime_drift_monitor_updates_and_flags_on_drift() -> None:
    monitor = RegimeDriftMonitor()
    model = _model()

    # Build baseline
    for _ in range(90):
        payload = monitor.update(
            feature_vector=[0.01, 0.02, -0.01],
            regime_probs={"LOW_VOL": 0.7, "HIGH_VOL": 0.2, "CRISIS": 0.05, "TRANSITION": 0.05},
            model=model,
        )
    assert "metrics" in payload

    # Inject drift: high entropy + large feature displacement + transition churn.
    for i in range(40):
        payload = monitor.update(
            feature_vector=[8.0, -8.0, 7.0],
            regime_probs={"LOW_VOL": 0.25, "HIGH_VOL": 0.25, "CRISIS": 0.25, "TRANSITION": 0.25},
            model=model,
            dominant_regime=["LOW_VOL", "HIGH_VOL", "CRISIS", "TRANSITION"][i % 4],
        )
    assert payload["drift_detected"] is True
    assert payload["severity"] in {"watch", "elevated", "high"}
