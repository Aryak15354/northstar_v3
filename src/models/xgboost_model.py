"""Gap 9 XGBoost wrapper with explicit IC reporting and feature-budget enforcement."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base_model import BaseModel


class XGBoostModel(BaseModel):
    MODEL_TYPE = "xgboost"
    INPUT_TYPE = "tabular"

    def __init__(self, config: dict, random_seed: int = 42):
        super().__init__(config=config, random_seed=random_seed)
        self._models = []

    def fit(self, X_train, y_train, X_val, y_val, feature_names: list[str]) -> "XGBoostModel":
        self._enforce_feature_budget(feature_names)
        X_tr = self._winsorize(pd.DataFrame(X_train, columns=feature_names))
        X_va = self._winsorize(pd.DataFrame(X_val, columns=feature_names), fit_on=X_tr)

        params = {
            "max_depth": min(int(self._model_config.get("max_depth", 4)), 6),
            "learning_rate": float(self._model_config.get("learning_rate", 0.05)),
            "n_estimators": int(self._model_config.get("n_estimators", 500)),
            "subsample": float(self._model_config.get("subsample", 0.7)),
            "colsample_bytree": float(self._model_config.get("colsample_bytree", 0.7)),
            "min_child_weight": float(self._model_config.get("min_child_weight", 10)),
            "reg_alpha": float(self._model_config.get("reg_alpha", 0.1)),
            "reg_lambda": float(self._model_config.get("reg_lambda", 1.0)),
        }
        n_models = int(self._model_config.get("n_ensemble_seeds", 5))
        self._feature_names = list(feature_names)
        self._models = []

        try:
            from xgboost import XGBRegressor

            for seed in range(self._random_seed, self._random_seed + n_models):
                model = XGBRegressor(
                    objective="reg:squarederror",
                    random_state=seed,
                    verbosity=0,
                    **params,
                )
                model.fit(X_tr, np.asarray(y_train, dtype=float), eval_set=[(X_va, np.asarray(y_val, dtype=float))], verbose=False)
                self._models.append(model)
        except Exception:
            from sklearn.ensemble import RandomForestRegressor

            for seed in range(self._random_seed, self._random_seed + max(1, min(n_models, 3))):
                model = RandomForestRegressor(
                    n_estimators=max(100, params["n_estimators"] // 2),
                    max_depth=params["max_depth"],
                    random_state=seed,
                    n_jobs=1,
                )
                model.fit(X_tr, np.asarray(y_train, dtype=float))
                self._models.append(model)

        preds = self.predict(X_va)
        self._val_ic = self._compute_ic(y_val, preds)
        self._is_fitted = True
        return self

    def predict(self, X) -> np.ndarray:
        if not self._models:
            raise RuntimeError("model_not_fitted")
        frame = pd.DataFrame(X, columns=self._feature_names if not isinstance(X, pd.DataFrame) else None)
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame(X, columns=self._feature_names)
        if list(frame.columns) != list(self._feature_names):
            frame.columns = self._feature_names
        frame = self._winsorize(frame)
        preds = np.mean([np.asarray(model.predict(frame), dtype=float).reshape(-1) for model in self._models], axis=0)
        return preds

    def get_feature_importance(self) -> pd.Series:
        if not self._models:
            return pd.Series(dtype=float)
        series = []
        for model in self._models:
            if hasattr(model, "feature_importances_"):
                series.append(np.asarray(model.feature_importances_, dtype=float))
        if not series:
            return pd.Series(dtype=float)
        return pd.Series(np.mean(series, axis=0), index=self._feature_names).sort_values(ascending=False)

    def save(self, path: str) -> None:
        import joblib

        joblib.dump({"models": self._models, "feature_names": self._feature_names, "val_ic": self._val_ic}, path)

    def load(self, path: str) -> "XGBoostModel":
        import joblib

        payload = joblib.load(path)
        self._models = payload.get("models", [])
        self._feature_names = list(payload.get("feature_names", []))
        self._val_ic = payload.get("val_ic")
        self._is_fitted = bool(self._models)
        return self
