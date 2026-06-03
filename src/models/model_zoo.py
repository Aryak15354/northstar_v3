"""Canonical model registry for Gap 9 foundation."""

from __future__ import annotations

from .catboost_model import CatBoostModel
from .xgboost_model import XGBoostModel


class ModelZoo:
    MODEL_CLASSES = {
        "xgboost": XGBoostModel,
        "catboost": CatBoostModel,
    }

    def __init__(self, config: dict):
        self._config = dict(config or {})
        self._models = {name: cls(self._config) for name, cls in self.MODEL_CLASSES.items()}

    def get(self, name: str):
        return self._models.get(str(name).strip().lower())

    def names(self) -> list[str]:
        return list(self._models.keys())

    def as_dict(self) -> dict[str, object]:
        return dict(self._models)
