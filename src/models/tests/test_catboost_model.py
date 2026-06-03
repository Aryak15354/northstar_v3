from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.catboost_model import CatBoostModel


def _config():
    return {
        "models": {
            "universe_size": 300,
            "catboost": {
                "iterations": 60,
                "learning_rate": 0.05,
                "depth": 4,
                "l2_leaf_reg": 3.0,
                "subsample": 0.8,
            }
        }
    }


def test_catboost_model_fit_predict_and_ic():
    rng = np.random.default_rng(11)
    X = pd.DataFrame(rng.normal(size=(72, 5)), columns=["f0", "f1", "f2", "sector_code", "regime_code"])
    X.loc[X.index[::7], "f2"] = np.nan
    y = 0.7 * X["f0"].fillna(0) - 0.3 * X["f1"] + rng.normal(scale=0.08, size=len(X))

    model = CatBoostModel(_config())
    model.fit(X.iloc[:54], y[:54], X.iloc[54:], y[54:], list(X.columns))

    preds = model.predict(X.iloc[54:])
    assert model.is_fitted()
    assert len(preds) == len(X.iloc[54:])
    assert np.isfinite(model.get_ic())
    assert len(model.get_feature_importance()) == len(X.columns)


def test_catboost_model_reports_wrapper_as_available():
    model = CatBoostModel(_config())
    assert model.is_available() is True
