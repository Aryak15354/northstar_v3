from __future__ import annotations

import pickle
from datetime import datetime, timezone
from types import SimpleNamespace

import numpy as np
import pytest

from scripts import train_regime_hmm as trainer
from src.models.regime_probability_engine import DEFAULT_STATES, FrozenRegimeHMM, RegimeProbabilityEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def test_runtime_hmm_retraining_is_prohibited() -> None:
    engine = RegimeProbabilityEngine(model_path="data/models/does_not_exist.pkl")
    with pytest.raises(RuntimeError):
        engine.fit_em(np.ones((10, 3)))


def test_monthly_cadence_gate_skips_retraining(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "data/models/regime_hmm_latest.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)

    k = len(DEFAULT_STATES)
    d = 3
    model = FrozenRegimeHMM(
        states=list(DEFAULT_STATES),
        transition_matrix=np.full((k, k), 1.0 / k),
        emission_means=np.zeros((k, d), dtype=float),
        emission_covs=np.array([np.eye(d, dtype=float) for _ in range(k)]),
        initial_probs=np.full(k, 1.0 / k),
        feature_names=["a", "b", "c"],
        model_version="test",
        trained_at=_now_iso(),
        training_rows=500,
        metadata={},
    )
    with model_path.open("wb") as f:
        pickle.dump(model.to_payload(), f)

    alpha_os_cfg = SimpleNamespace(
        hmm_model_path="data/models/regime_hmm_latest.pkl",
        hmm_retrain_interval_days=30,
        hmm_min_samples=260,
        hmm_transition_smoothing=0.02,
    )
    cfg = SimpleNamespace(alpha_os=alpha_os_cfg)
    monkeypatch.setattr(trainer, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(trainer, "get_config", lambda: cfg)

    outcome = trainer.run_training(force=False)
    assert outcome.status == "skipped"
    assert "cadence gate" in outcome.reason
