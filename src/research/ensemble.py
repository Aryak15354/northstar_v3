"""Ensemble and stacking models for research."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np


class WeightedEnsemble:
    def __init__(self, models: Sequence, weights: Sequence[float] | None = None):
        self.models = list(models)
        self.weights = np.asarray(weights, dtype=float) if weights is not None else None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "WeightedEnsemble":
        for m in self.models:
            m.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self.models:
            return np.zeros(len(X), dtype=float)
        preds = np.vstack([np.asarray(m.predict(X), dtype=float).reshape(1, -1) for m in self.models])
        if self.weights is None or len(self.weights) != len(self.models):
            return np.mean(preds, axis=0)
        w = self.weights / (np.sum(self.weights) + 1e-12)
        return np.average(preds, axis=0, weights=w)

    def fit_with_context(
        self,
        dataset: Any,
        train_indices: np.ndarray,
        valid_indices: np.ndarray | None = None,
    ) -> "WeightedEnsemble":
        tr = np.asarray(train_indices, dtype=int)
        va = np.asarray(valid_indices, dtype=int) if valid_indices is not None else None
        for m in self.models:
            if hasattr(m, "fit_with_context"):
                m.fit_with_context(dataset=dataset, train_indices=tr, valid_indices=va)
            else:
                m.fit(dataset.X[tr], dataset.y[tr])
        return self

    def predict_with_context(self, dataset: Any, target_indices: np.ndarray) -> Dict[str, np.ndarray]:
        if not self.models:
            return {
                "indices": np.empty((0,), dtype=int),
                "predictions": np.empty((0,), dtype=float),
            }
        target = np.asarray(target_indices, dtype=int)
        pred_maps: List[Dict[int, float]] = []
        for m in self.models:
            if hasattr(m, "predict_with_context"):
                out = m.predict_with_context(dataset=dataset, target_indices=target)
                idx = np.asarray(out.get("indices", []), dtype=int).reshape(-1)
                pred = np.asarray(out.get("predictions", []), dtype=float).reshape(-1)
            else:
                idx = target
                pred = np.asarray(m.predict(dataset.X[target]), dtype=float).reshape(-1)
            n = min(len(idx), len(pred))
            pred_maps.append({int(idx[i]): float(pred[i]) for i in range(n)})

        if not pred_maps:
            return {
                "indices": np.empty((0,), dtype=int),
                "predictions": np.empty((0,), dtype=float),
            }

        common = set(pred_maps[0].keys())
        for pm in pred_maps[1:]:
            common &= set(pm.keys())
        if not common:
            return {
                "indices": np.empty((0,), dtype=int),
                "predictions": np.empty((0,), dtype=float),
            }

        idx_sorted = np.asarray(sorted(common), dtype=int)
        mat = np.vstack([[pm[int(i)] for i in idx_sorted] for pm in pred_maps])
        if self.weights is None or len(self.weights) != len(self.models):
            pred = np.mean(mat, axis=0)
        else:
            w = self.weights / (np.sum(self.weights) + 1e-12)
            pred = np.average(mat, axis=0, weights=w)
        return {"indices": idx_sorted, "predictions": np.asarray(pred, dtype=float)}


class StackingMetaLearner:
    """Train base models, then ridge meta learner on base predictions."""

    def __init__(self, base_models: Sequence, alpha: float = 1.0):
        self.base_models = list(base_models)
        self.alpha = float(alpha)
        self.meta = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "StackingMetaLearner":
        from sklearn.linear_model import Ridge

        if not self.base_models:
            self.meta = Ridge(alpha=self.alpha)
            self.meta.fit(np.zeros((len(X), 1), dtype=float), y)
            return self

        preds = []
        for model in self.base_models:
            model.fit(X, y)
            preds.append(np.asarray(model.predict(X), dtype=float))
        P = np.column_stack(preds)
        self.meta = Ridge(alpha=self.alpha)
        self.meta.fit(P, y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.meta is None:
            return np.zeros(len(X), dtype=float)
        if not self.base_models:
            return np.asarray(self.meta.predict(np.zeros((len(X), 1), dtype=float)), dtype=float)
        preds = [np.asarray(model.predict(X), dtype=float) for model in self.base_models]
        P = np.column_stack(preds)
        return np.asarray(self.meta.predict(P), dtype=float)

    def summary(self) -> Dict[str, float]:
        if self.meta is None or not hasattr(self.meta, "coef_"):
            return {}
        coef = np.asarray(self.meta.coef_, dtype=float).reshape(-1)
        return {f"base_{i}": float(v) for i, v in enumerate(coef)}

    def fit_with_context(
        self,
        dataset: Any,
        train_indices: np.ndarray,
        valid_indices: np.ndarray | None = None,
    ) -> "StackingMetaLearner":
        from sklearn.linear_model import Ridge

        tr = np.asarray(train_indices, dtype=int)
        if not self.base_models:
            self.meta = Ridge(alpha=self.alpha)
            self.meta.fit(np.zeros((len(tr), 1), dtype=float), dataset.y[tr])
            return self

        pred_maps: List[Dict[int, float]] = []
        for model in self.base_models:
            if hasattr(model, "fit_with_context"):
                model.fit_with_context(dataset=dataset, train_indices=tr, valid_indices=valid_indices)
                out = model.predict_with_context(dataset=dataset, target_indices=tr)
                idx = np.asarray(out.get("indices", []), dtype=int).reshape(-1)
                pred = np.asarray(out.get("predictions", []), dtype=float).reshape(-1)
            else:
                model.fit(dataset.X[tr], dataset.y[tr])
                idx = tr
                pred = np.asarray(model.predict(dataset.X[tr]), dtype=float).reshape(-1)
            n = min(len(idx), len(pred))
            pred_maps.append({int(idx[i]): float(pred[i]) for i in range(n)})

        common = set(pred_maps[0].keys()) if pred_maps else set()
        for pm in pred_maps[1:]:
            common &= set(pm.keys())
        if not common:
            self.meta = Ridge(alpha=self.alpha)
            self.meta.fit(np.zeros((len(tr), 1), dtype=float), dataset.y[tr])
            return self

        idx_sorted = np.asarray(sorted(common), dtype=int)
        P = np.column_stack([[pm[int(i)] for i in idx_sorted] for pm in pred_maps])
        self.meta = Ridge(alpha=self.alpha)
        self.meta.fit(P, np.asarray(dataset.y[idx_sorted], dtype=float))
        return self

    def predict_with_context(self, dataset: Any, target_indices: np.ndarray) -> Dict[str, np.ndarray]:
        if self.meta is None:
            return {
                "indices": np.empty((0,), dtype=int),
                "predictions": np.empty((0,), dtype=float),
            }
        target = np.asarray(target_indices, dtype=int)
        if not self.base_models:
            pred = np.asarray(self.meta.predict(np.zeros((len(target), 1), dtype=float)), dtype=float)
            return {"indices": target, "predictions": pred}

        pred_maps: List[Dict[int, float]] = []
        for model in self.base_models:
            if hasattr(model, "predict_with_context"):
                out = model.predict_with_context(dataset=dataset, target_indices=target)
                idx = np.asarray(out.get("indices", []), dtype=int).reshape(-1)
                pred = np.asarray(out.get("predictions", []), dtype=float).reshape(-1)
            else:
                idx = target
                pred = np.asarray(model.predict(dataset.X[target]), dtype=float).reshape(-1)
            n = min(len(idx), len(pred))
            pred_maps.append({int(idx[i]): float(pred[i]) for i in range(n)})

        common = set(pred_maps[0].keys()) if pred_maps else set()
        for pm in pred_maps[1:]:
            common &= set(pm.keys())
        if not common:
            return {
                "indices": np.empty((0,), dtype=int),
                "predictions": np.empty((0,), dtype=float),
            }
        idx_sorted = np.asarray(sorted(common), dtype=int)
        P = np.column_stack([[pm[int(i)] for i in idx_sorted] for pm in pred_maps])
        pred = np.asarray(self.meta.predict(P), dtype=float).reshape(-1)
        return {"indices": idx_sorted, "predictions": pred}
