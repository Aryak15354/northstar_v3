from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.alpha_os.strategy_registry import (
    StrategyFamily,
    StrategyRecord,
    StrategyRegistry,
    StrategyStatus,
)
from src.scoring.daily_scorer import DailyScorer


class ConstantModel:
    def __init__(self, value: float):
        self.value = float(value)

    def predict(self, X):
        return np.full(len(X), self.value, dtype=float)


def _write_model(path: Path, value: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": ConstantModel(value),
        "backend": "test_constant",
        "feature_cols": ["feature_1"],
        "regime": "BULL",
    }
    path.write_bytes(pickle.dumps(payload))


def _base_scorer(tmp_path: Path, registry_dir: Path) -> DailyScorer:
    scorer = DailyScorer(
        config={
            "project_root": str(tmp_path),
            "alpha_os_registry_path": str(registry_dir),
        }
    )
    scorer.regime_engine.get_regime_as_of = lambda dt: "BULL"
    scorer.regime_engine.get_exposure_scale = lambda regime: 1.0
    scorer._load_latest_universe_frame = lambda dt, regime=None: (
        pd.DataFrame({"ticker": ["AAA.NS"], "feature_1": [1.0]}),
        ["feature_1"],
    )
    scorer.overlay.apply = lambda frame, as_of_date=None: pd.DataFrame(
        {
            "ticker": frame["ticker"].astype(str),
            "sentiment_multiplier": [1.0],
            "sentiment_override": [False],
            "override_reason": [None],
            "sentiment_polarity": [0.0],
            "sentiment_conviction": [0.0],
            "news_volume": [0.0],
        }
    )
    scorer._build_weights = lambda frame, exposure_scale, mandate, apply_turnover=True: pd.Series([1.0], index=frame.index)
    scorer._save_prev_portfolio = lambda portfolio: None
    return scorer


def test_scorer_uses_alpha_os_model_path_when_active_strategy_has_one_registered(tmp_path: Path) -> None:
    registry_dir = tmp_path / "data/model_registry"
    active_model = registry_dir / "models/active.pkl"
    fallback_model = registry_dir / "models/fallback.pkl"
    _write_model(active_model, 0.75)
    _write_model(fallback_model, -0.25)

    registry = StrategyRegistry({"alpha_os_registry_path": str(registry_dir)})
    registry.register(
        StrategyRecord(
            strategy_id="ownership_accumulation",
            strategy_name="Ownership Accumulation",
            family=StrategyFamily.COMPOSITE,
            status=StrategyStatus.ACTIVE,
            discovered_date=datetime.utcnow(),
            model_artifact_path=str(active_model),
            model_registry_path=str(active_model),
        )
    )
    (registry_dir / "production.json").write_text(
        json.dumps({"active_strategy": "fallback", "model_path": str(fallback_model)}),
        encoding="utf-8",
    )

    scorer = _base_scorer(tmp_path, registry_dir)
    scorer.trainer.predict = lambda frame, regime=None: np.array([-999.0])

    out = scorer.score("2026-03-20")

    assert float(out.loc[0, "raw_model_score"]) == 0.75
    assert float(out.loc[0, "model_score"]) == 0.0


def test_scorer_falls_back_to_production_json_when_alpha_os_path_unavailable(tmp_path: Path) -> None:
    registry_dir = tmp_path / "data/model_registry"
    fallback_model = registry_dir / "models/fallback.pkl"
    _write_model(fallback_model, 0.33)

    registry = StrategyRegistry({"alpha_os_registry_path": str(registry_dir)})
    registry.register(
        StrategyRecord(
            strategy_id="ownership_accumulation",
            strategy_name="Ownership Accumulation",
            family=StrategyFamily.COMPOSITE,
            status=StrategyStatus.ACTIVE,
            discovered_date=datetime.utcnow(),
        )
    )
    (registry_dir / "production.json").write_text(
        json.dumps({"active_strategy": "fallback", "model_path": str(fallback_model)}),
        encoding="utf-8",
    )

    scorer = _base_scorer(tmp_path, registry_dir)
    scorer.trainer.predict = lambda frame, regime=None: np.array([-999.0])

    out = scorer.score("2026-03-20")

    assert float(out.loc[0, "raw_model_score"]) == 0.33
    assert float(out.loc[0, "model_score"]) == 0.0


def test_promoting_strategy_to_active_updates_production_json(tmp_path: Path) -> None:
    registry_dir = tmp_path / "data/model_registry"
    active_model = registry_dir / "models/promoted.pkl"
    _write_model(active_model, 0.5)

    registry = StrategyRegistry({"alpha_os_registry_path": str(registry_dir)})
    registry.register(
        StrategyRecord(
            strategy_id="ownership_accumulation",
            strategy_name="Ownership Accumulation",
            family=StrategyFamily.COMPOSITE,
            status=StrategyStatus.CANDIDATE,
            discovered_date=datetime.utcnow(),
        )
    )

    registry.promote_to_active("ownership_accumulation", str(active_model))

    production = json.loads((registry_dir / "production.json").read_text())
    assert production["active_strategy"] == "ownership_accumulation"
    assert production["model_path"] == str(active_model)
    assert registry.get("ownership_accumulation").status == StrategyStatus.ACTIVE
