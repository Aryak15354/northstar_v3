from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.models.ensemble import NorthstarEnsemble
from src.models.model_zoo import ModelZoo


def _config():
    return {
        "models": {
            "universe_size": 300,
            "xgboost": {
                "max_depth": 4,
                "learning_rate": 0.05,
                "n_estimators": 40,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_weight": 10,
                "reg_alpha": 0.1,
                "reg_lambda": 1.0,
                "n_ensemble_seeds": 2,
            },
            "catboost": {
                "iterations": 50,
                "learning_rate": 0.05,
                "depth": 4,
                "l2_leaf_reg": 3.0,
                "subsample": 0.8,
            },
        }
    }


def _dataset():
    rng = np.random.default_rng(19)
    X = pd.DataFrame(rng.normal(size=(90, 6)), columns=[f"f{i}" for i in range(6)])
    y = 0.8 * X["f0"] - 0.5 * X["f1"] + 0.2 * X["f2"] + rng.normal(scale=0.08, size=len(X))
    return X.iloc[:60], y[:60], X.iloc[60:75], y[60:75], X.iloc[75:], y[75:]


def test_ensemble_fit_and_predict():
    X_train, y_train, X_val, y_val, X_test, _ = _dataset()
    zoo = ModelZoo(_config())
    ensemble = NorthstarEnsemble(zoo, _config())

    results = ensemble.fit_all(X_train, y_train, X_val, y_val, feature_names_tab=list(X_train.columns))
    preds = ensemble.predict(
        X_test,
        unified_state=SimpleNamespace(
            market_state=SimpleNamespace(india_vix_zscore=0.2, nifty_above_200d_sma=True)
        ),
        tickers=list(X_test.index.astype(str)),
    )

    assert set(results.keys()) == {"xgboost", "catboost"}
    assert len(preds) == len(X_test)
    assert preds.notna().all()
    assert abs(sum(ensemble._base_weights.values()) - 1.0) < 1e-9


def test_ensemble_regime_weights_within_bounds():
    ensemble = NorthstarEnsemble(ModelZoo(_config()), _config())
    for regime_weights in ensemble._regime_weights.values():
        for value in regime_weights.values():
            assert 0.5 <= value <= 1.5


def test_ensemble_raises_when_no_models_are_fitted():
    ensemble = NorthstarEnsemble(ModelZoo(_config()), _config())
    with pytest.raises(RuntimeError, match="no_fitted_models"):
        ensemble.predict(pd.DataFrame({"f0": [1.0], "f1": [2.0]}))
