"""Canonical model interface for Gap 9 foundation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd


class BaseModel(ABC):
    MODEL_TYPE: str = ""
    INPUT_TYPE: str = "tabular"

    def __init__(self, config: dict, random_seed: int = 42):
        self._config = dict(config or {})
        models_cfg = self._config.get("models", {}) or {}
        self._model_config = models_cfg.get(self.MODEL_TYPE, {})
        self._universe_size = int(models_cfg.get("universe_size", self._model_config.get("universe_size", 300)) or 300)
        self._random_seed = int(random_seed)
        self._is_fitted = False
        self._val_ic: Optional[float] = None
        self._feature_names: list[str] = []

    @abstractmethod
    def fit(self, X_train, y_train, X_val, y_val, feature_names: list[str]) -> "BaseModel":
        pass

    @abstractmethod
    def predict(self, X) -> np.ndarray:
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        pass

    @abstractmethod
    def load(self, path: str) -> "BaseModel":
        pass

    def is_available(self) -> bool:
        return True

    def is_fitted(self) -> bool:
        return bool(self._is_fitted)

    def get_ic(self) -> float:
        if self._val_ic is None:
            raise RuntimeError("model_not_fitted")
        return float(self._val_ic)

    def get_feature_importance(self) -> Optional[pd.Series]:
        return None

    def _compute_ic(self, y_true, y_pred) -> float:
        from scipy.stats import spearmanr

        yt = pd.to_numeric(pd.Series(y_true), errors="coerce")
        yp = pd.to_numeric(pd.Series(np.asarray(y_pred).reshape(-1)), errors="coerce")
        valid = yt.notna() & yp.notna()
        if int(valid.sum()) < 10:
            return 0.0
        ic, _ = spearmanr(yp[valid], yt[valid])
        return float(ic) if np.isfinite(ic) else 0.0

    def _enforce_feature_budget(self, feature_names: list[str]) -> None:
        max_features = max(1, int(self._universe_size) // 5)
        if len(list(feature_names or [])) > max_features:
            raise ValueError(
                f"Feature count {len(list(feature_names or []))} exceeds N/5 budget {max_features} "
                f"for universe size {self._universe_size}."
            )

    def _winsorize(self, frame: pd.DataFrame, fit_on: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        out = frame.copy()
        ref = fit_on if fit_on is not None else out
        for col in out.columns:
            if not pd.api.types.is_numeric_dtype(out[col]):
                continue
            low = pd.to_numeric(ref[col], errors="coerce").quantile(0.01)
            high = pd.to_numeric(ref[col], errors="coerce").quantile(0.99)
            out[col] = pd.to_numeric(out[col], errors="coerce").clip(lower=low, upper=high)
        return out
