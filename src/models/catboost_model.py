"""Gap 9 CatBoost wrapper with native-NaN support and IC reporting."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base_model import BaseModel


class CatBoostModel(BaseModel):
    MODEL_TYPE = "catboost"
    INPUT_TYPE = "tabular"

    def __init__(self, config: dict, random_seed: int = 42):
        super().__init__(config=config, random_seed=random_seed)
        self._model = None
        self._backend_name = "uninitialized"

    def is_available(self) -> bool:
        try:
            import catboost  # noqa: F401

            return True
        except Exception:
            try:
                from sklearn.ensemble import ExtraTreesRegressor  # noqa: F401

                return True
            except Exception:
                return False

    def fit(self, X_train, y_train, X_val, y_val, feature_names: list[str]) -> "CatBoostModel":
        self._enforce_feature_budget(feature_names)
        X_tr = pd.DataFrame(X_train, columns=feature_names)
        X_va = pd.DataFrame(X_val, columns=feature_names)
        X_tr = self._winsorize_numerical(X_tr, feature_names)
        X_va = self._winsorize_numerical(X_va, feature_names, fit_on=X_tr)

        self._feature_names = list(feature_names)
        cat_idx = self._resolve_cat_feature_indices(feature_names)
        try:
            from catboost import CatBoostRegressor

            self._model = CatBoostRegressor(
                iterations=int(self._model_config.get("iterations", 500)),
                learning_rate=float(self._model_config.get("learning_rate", 0.05)),
                depth=min(int(self._model_config.get("depth", 6)), 8),
                l2_leaf_reg=float(self._model_config.get("l2_leaf_reg", 3.0)),
                min_data_in_leaf=max(1, int(self._model_config.get("min_data_in_leaf", 1))),
                subsample=float(self._model_config.get("subsample", 0.8)),
                loss_function=str(self._model_config.get("loss_function", "RMSE")),
                boosting_type=str(self._model_config.get("boosting_type", "Plain")),
                thread_count=max(1, int(self._model_config.get("thread_count", 1))),
                allow_writing_files=bool(self._model_config.get("allow_writing_files", False)),
                random_seed=self._random_seed,
                verbose=False,
                cat_features=cat_idx if cat_idx else None,
            )
            self._model.fit(X_tr, np.asarray(y_train, dtype=float), eval_set=(X_va, np.asarray(y_val, dtype=float)), verbose=False)
            self._backend_name = "catboost"
        except Exception:
            from sklearn.ensemble import ExtraTreesRegressor

            self._model = ExtraTreesRegressor(
                n_estimators=max(200, int(self._model_config.get("iterations", 500)) // 2),
                max_depth=min(int(self._model_config.get("depth", 6)), 8),
                min_samples_leaf=max(1, int(self._model_config.get("min_data_in_leaf", 1))),
                random_state=self._random_seed,
                n_jobs=1,
            )
            self._model.fit(X_tr.fillna(0.0), np.asarray(y_train, dtype=float))
            self._backend_name = "extratrees_fallback"

        self._val_ic = self._compute_ic(y_val, self.predict(X_va))
        self._is_fitted = True
        return self

    def predict(self, X) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("model_not_fitted")
        frame = pd.DataFrame(X, columns=self._feature_names if not isinstance(X, pd.DataFrame) else None)
        if list(frame.columns) != list(self._feature_names):
            frame.columns = self._feature_names
        frame = self._winsorize_numerical(frame, self._feature_names)
        if "catboost" not in type(self._model).__module__.lower():
            frame = frame.fillna(0.0)
        return np.asarray(self._model.predict(frame), dtype=float).reshape(-1)

    def _winsorize_numerical(self, X: pd.DataFrame, feature_names: list[str], fit_on: pd.DataFrame | None = None) -> pd.DataFrame:
        out = X.copy()
        cat_cols = [n for n in feature_names if "sector" in n.lower() or "regime" in n.lower()]
        num_cols = [n for n in feature_names if n not in cat_cols and n in out.columns]
        ref = fit_on[num_cols] if fit_on is not None else out[num_cols]
        for col in num_cols:
            low = pd.to_numeric(ref[col], errors="coerce").quantile(0.01)
            high = pd.to_numeric(ref[col], errors="coerce").quantile(0.99)
            out[col] = pd.to_numeric(out[col], errors="coerce").clip(lower=low, upper=high)
        return out

    def get_feature_importance(self) -> pd.Series:
        if self._model is None:
            return pd.Series(dtype=float)
        if hasattr(self._model, "get_feature_importance"):
            values = np.asarray(self._model.get_feature_importance(), dtype=float)
        elif hasattr(self._model, "feature_importances_"):
            values = np.asarray(self._model.feature_importances_, dtype=float)
        else:
            return pd.Series(dtype=float)
        return pd.Series(values, index=self._feature_names).sort_values(ascending=False)

    def save(self, path: str) -> None:
        import joblib

        joblib.dump(
            {
                "model": self._model,
                "feature_names": self._feature_names,
                "val_ic": self._val_ic,
                "backend_name": self._backend_name,
            },
            path,
        )

    def load(self, path: str) -> "CatBoostModel":
        import joblib

        payload = joblib.load(path)
        self._model = payload.get("model")
        self._feature_names = list(payload.get("feature_names", []))
        self._val_ic = payload.get("val_ic")
        self._backend_name = str(payload.get("backend_name", "loaded_model"))
        self._is_fitted = self._model is not None
        return self

    def _resolve_cat_feature_indices(self, feature_names: list[str]) -> list[int]:
        configured = self._model_config.get("cat_features")
        if isinstance(configured, (list, tuple)):
            indices: list[int] = []
            for raw in configured:
                if isinstance(raw, int):
                    if 0 <= raw < len(feature_names):
                        indices.append(int(raw))
                    continue
                name = str(raw).strip()
                if name in feature_names:
                    indices.append(feature_names.index(name))
            if indices:
                return indices
        return [
            i
            for i, name in enumerate(feature_names)
            if "sector" in name.lower() or "regime" in name.lower()
        ]
