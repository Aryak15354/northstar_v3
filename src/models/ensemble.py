"""IC-weighted tabular ensemble for Gap 9 foundation."""

from __future__ import annotations

import numpy as np
import pandas as pd


class NorthstarEnsemble:
    def __init__(self, model_zoo, config: dict):
        self._zoo = model_zoo
        self._config = dict(config or {})
        self._base_weights: dict[str, float] = {}
        self._regime_weights = {
            "low_vol_uptrend": {"xgboost": 1.2, "catboost": 1.1},
            "high_vol_uptrend": {"xgboost": 0.8, "catboost": 0.9},
            "low_vol_downtrend": {"xgboost": 1.3, "catboost": 1.3},
            "high_vol_downtrend": {"xgboost": 1.0, "catboost": 1.1},
        }

    def fit_all(self, X_tab_train, y_train, X_tab_val, y_val, feature_names_tab=None) -> dict:
        results = {}
        for name in self._zoo.names():
            model = self._zoo.get(name)
            if model is None or not model.is_available():
                results[name] = 0.0
                continue
            try:
                model.fit(X_tab_train, y_train, X_tab_val, y_val, list(feature_names_tab or X_tab_train.columns))
                results[name] = model.get_ic()
            except Exception:
                results[name] = 0.0
        self._base_weights = self._compute_ic_weights(results)
        return results

    def predict(self, X_tab: pd.DataFrame, unified_state=None, tickers: list[str] | None = None) -> pd.Series:
        predictions = {}
        for name in self._zoo.names():
            model = self._zoo.get(name)
            if model is not None and model.is_fitted():
                predictions[name] = model.predict(X_tab)
        if not predictions:
            raise RuntimeError("no_fitted_models")

        regime = self._get_regime(unified_state)
        multipliers = self._regime_weights.get(regime, {})
        weights = {}
        for name in predictions:
            base = float(self._base_weights.get(name, 0.0))
            mult = float(multipliers.get(name, 1.0))
            weights[name] = base * max(0.5, min(1.5, mult))
        total = sum(weights.values()) or 1.0
        weights = {k: v / total for k, v in weights.items()}

        ensemble = np.zeros(len(next(iter(predictions.values()))), dtype=float)
        for name, pred in predictions.items():
            ranked = pd.Series(np.asarray(pred, dtype=float)).rank(pct=True).fillna(0.5).to_numpy(dtype=float)
            ensemble += weights.get(name, 0.0) * ranked
        if tickers is None:
            tickers = list(X_tab.index) if hasattr(X_tab, "index") else list(range(len(ensemble)))
        return pd.Series(ensemble, index=tickers)

    def _compute_ic_weights(self, ic_results: dict[str, float]) -> dict[str, float]:
        positive = {k: max(0.0, float(v)) for k, v in ic_results.items()}
        total = sum(positive.values())
        if total <= 0.0:
            n = max(1, len(positive))
            return {k: 1.0 / n for k in positive}
        return {k: v / total for k, v in positive.items()}

    def _get_regime(self, unified_state) -> str:
        try:
            vix_z = float(unified_state.market_state.india_vix_zscore)
            above_200d = bool(unified_state.market_state.nifty_above_200d_sma)
            vol = "high_vol" if vix_z > 0.5 else "low_vol"
            trend = "uptrend" if above_200d else "downtrend"
            return f"{vol}_{trend}"
        except Exception:
            return "low_vol_uptrend"
