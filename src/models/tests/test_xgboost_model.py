from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.xgboost_model import XGBoostModel


def _config():
    return {
        "models": {
            "universe_size": 300,
            "xgboost": {
                "max_depth": 4,
                "learning_rate": 0.05,
                "n_estimators": 50,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "min_child_weight": 10,
                "reg_alpha": 0.1,
                "reg_lambda": 1.0,
                "n_ensemble_seeds": 2,
            }
        }
    }


def _dataset(n_rows=64, n_features=6):
    rng = np.random.default_rng(7)
    X = pd.DataFrame(rng.normal(size=(n_rows, n_features)), columns=[f"f{i}" for i in range(n_features)])
    y = 0.9 * X["f0"] - 0.4 * X["f1"] + rng.normal(scale=0.05, size=n_rows)
    return X.iloc[:48], y[:48], X.iloc[48:], y[48:], list(X.columns)


def test_xgboost_model_fit_predict_and_ic():
    X_train, y_train, X_val, y_val, feature_names = _dataset()
    model = XGBoostModel(_config())
    model.fit(X_train, y_train, X_val, y_val, feature_names)

    preds = model.predict(X_val)
    assert model.is_fitted()
    assert len(preds) == len(X_val)
    assert np.isfinite(model.get_ic())
    assert list(model.get_feature_importance().index) == feature_names or len(model.get_feature_importance()) == len(feature_names)


def test_xgboost_feature_budget_enforced():
    X = pd.DataFrame(np.random.default_rng(1).normal(size=(40, 61)), columns=[f"f{i}" for i in range(61)])
    y = np.random.default_rng(2).normal(size=40)
    model = XGBoostModel(_config())
    with pytest.raises(ValueError, match="N/5 budget"):
        model.fit(X.iloc[:30], y[:30], X.iloc[30:], y[30:], list(X.columns))
