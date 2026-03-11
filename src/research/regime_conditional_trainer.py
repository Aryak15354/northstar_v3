"""Train and serve regime-conditional models for Northstar v3."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


def _safe_spearman(a: np.ndarray, b: np.ndarray) -> float:
    xa = np.asarray(a, dtype=float).reshape(-1)
    xb = np.asarray(b, dtype=float).reshape(-1)
    n = min(len(xa), len(xb))
    if n < 8:
        return 0.0
    sa = pd.Series(xa[:n])
    sb = pd.Series(xb[:n])
    val = sa.corr(sb, method="spearman")
    return float(val) if np.isfinite(val) else 0.0


class RegimeConditionalTrainer:
    """
    Trains one model per regime.
    Falls back to base regime model when extended regime has < 500 obs.
    Stores all models in models/regime_models/
    """

    def __init__(self, config: dict | None = None, model_dir: str = "models/regime_models"):
        self.config = dict(config or {})
        self.model_dir = Path(str(self.config.get("model_dir", model_dir)))
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.min_obs = int(self.config.get("min_obs_per_regime", 500) or 500)
        self.random_state = int(self.config.get("random_state", 42) or 42)
        self._registry_path = self.model_dir / "regime_model_registry.json"
        self._last_prediction_meta: dict[str, Any] = {}

    @staticmethod
    def _safe_name(regime: str) -> str:
        s = str(regime or "unknown").strip().lower()
        s = s.replace("|", "_")
        s = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in s)
        while "__" in s:
            s = s.replace("__", "_")
        return s.strip("_") or "unknown"

    @staticmethod
    def _base_regime(regime: str) -> str:
        parts = [p for p in str(regime or "").split("|") if p]
        if len(parts) >= 2:
            return "|".join(parts[:2])
        return str(regime or "").strip()

    def _build_model(self, n_obs: int = 10000):
        """
        Build XGBoost model with adaptive regularization based on sample size.
        
        For thin regimes (<10k obs), use stronger regularization to prevent overfitting.
        For well-sampled regimes (>50k obs), use standard regularization.
        """
        try:
            from xgboost import XGBRegressor

            # Adaptive regularization based on sample size
            if n_obs < 5000:
                # Very thin regime: aggressive regularization
                max_depth = 2
                min_child_weight = 50.0
                subsample = 0.6
                colsample_bytree = 0.6
                reg_alpha = 0.5
                reg_lambda = 5.0
                n_estimators = 100
                learning_rate = 0.03
            elif n_obs < 10000:
                # Thin regime: strong regularization
                max_depth = 3
                min_child_weight = 40.0
                subsample = 0.7
                colsample_bytree = 0.7
                reg_alpha = 0.3
                reg_lambda = 3.0
                n_estimators = 150
                learning_rate = 0.04
            elif n_obs < 30000:
                # Medium regime: moderate regularization
                max_depth = 3
                min_child_weight = 30.0
                subsample = 0.75
                colsample_bytree = 0.75
                reg_alpha = 0.2
                reg_lambda = 2.0
                n_estimators = 180
                learning_rate = 0.05
            else:
                # Well-sampled regime: standard regularization
                max_depth = 4
                min_child_weight = 20.0
                subsample = 0.8
                colsample_bytree = 0.8
                reg_alpha = 0.1
                reg_lambda = 1.0
                n_estimators = 200
                learning_rate = 0.05

            model = XGBRegressor(
                n_estimators=n_estimators,
                learning_rate=learning_rate,
                max_depth=max_depth,
                min_child_weight=min_child_weight,
                subsample=subsample,
                colsample_bytree=colsample_bytree,
                reg_alpha=reg_alpha,
                reg_lambda=reg_lambda,
                n_jobs=int(self.config.get("n_jobs", 1) or 1),
                random_state=self.random_state,
            )
            return model, "xgboost"
        except Exception:
            from sklearn.ensemble import HistGradientBoostingRegressor

            model = HistGradientBoostingRegressor(
                learning_rate=float(self.config.get("sk_learning_rate", 0.03) or 0.03),
                max_iter=int(self.config.get("sk_n_estimators", 300) or 300),
                max_depth=int(self.config.get("sk_max_depth", 6) or 6),
                random_state=self.random_state,
            )
            return model, "sklearn_hist_gradient_boosting"

    def _feature_importance(self, model: Any, feature_cols: list[str]) -> dict[str, float]:
        if hasattr(model, "feature_importances_"):
            vals = np.asarray(getattr(model, "feature_importances_"), dtype=float).reshape(-1)
            out = {
                str(f): float(v)
                for f, v in zip(feature_cols, vals.tolist())
                if np.isfinite(float(v))
            }
            return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))
        return {str(f): 0.0 for f in feature_cols}

    def _load_registry(self) -> dict[str, Any]:
        if not self._registry_path.exists():
            return {"models": {}, "fallbacks": {}}
        try:
            return dict(json.loads(self._registry_path.read_text()) or {"models": {}, "fallbacks": {}})
        except Exception:
            return {"models": {}, "fallbacks": {}}

    def _save_registry(self, payload: dict[str, Any]) -> None:
        self._registry_path.write_text(json.dumps(payload, indent=2))

    def train_all_regimes(self, panel_df, feature_cols, target_col, regime_col):
        """
        For each regime: train model, store feature importances,
        store IC per regime, store model file.

        Returns dict: regime -> model
        """
        frame = panel_df.copy() if isinstance(panel_df, pd.DataFrame) else pd.DataFrame()
        if frame.empty:
            return {}

        feats = [str(c) for c in list(feature_cols or []) if str(c) in frame.columns]
        if not feats:
            raise ValueError("regime_trainer_missing_feature_columns")
        if target_col not in frame.columns:
            raise ValueError(f"regime_trainer_missing_target:{target_col}")
        if regime_col not in frame.columns:
            raise ValueError(f"regime_trainer_missing_regime_col:{regime_col}")

        frame = frame.copy()
        frame[regime_col] = frame[regime_col].astype(str).fillna("")
        frame[target_col] = pd.to_numeric(frame[target_col], errors="coerce")
        for c in feats:
            frame[c] = pd.to_numeric(frame[c], errors="coerce")
        frame = frame.dropna(subset=[target_col, regime_col]).copy()
        if frame.empty:
            return {}

        models: dict[str, Any] = {}
        registry = {"models": {}, "fallbacks": {}}

        unique_regimes = sorted([str(r) for r in frame[regime_col].dropna().astype(str).unique().tolist() if str(r)])
        for regime in unique_regimes:
            local = frame[frame[regime_col].astype(str) == str(regime)].copy()
            trained_on = str(regime)
            fallback_base = ""

            if len(local) < self.min_obs:
                base = self._base_regime(regime)
                if base:
                    base_mask = frame[regime_col].astype(str).eq(base) | frame[regime_col].astype(str).str.startswith(base + "|")
                    alt = frame[base_mask].copy()
                    if len(alt) >= self.min_obs:
                        local = alt
                        trained_on = base
                        fallback_base = base

            if len(local) < self.min_obs:
                continue

            X = local[feats].replace([np.inf, -np.inf], np.nan)
            X = X.fillna(X.median(numeric_only=True)).fillna(0.0)
            y = pd.to_numeric(local[target_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)

            # Pass n_obs for adaptive regularization
            model, backend = self._build_model(n_obs=len(local))
            model.fit(X.to_numpy(dtype=float), y)
            pred = np.asarray(model.predict(X.to_numpy(dtype=float)), dtype=float).reshape(-1)
            ic_train = _safe_spearman(y, pred)
            fi = self._feature_importance(model, feats)

            safe_name = self._safe_name(regime)
            model_path = self.model_dir / f"regime_{safe_name}.pkl"
            with model_path.open("wb") as f:
                pickle.dump(
                    {
                        "model": model,
                        "backend": backend,
                        "feature_cols": feats,
                        "regime": str(regime),
                    },
                    f,
                )

            models[str(regime)] = model
            registry["models"][str(regime)] = {
                "regime": str(regime),
                "trained_on_regime": str(trained_on),
                "fallback_base": str(fallback_base or ""),
                "n_obs": int(len(local)),
                "train_ic": float(ic_train),
                "oos_ic": None,
                "backend": str(backend),
                "feature_importance": fi,
                "feature_cols": feats,
                "model_path": str(model_path),
            }
            if fallback_base:
                registry["fallbacks"][str(regime)] = str(fallback_base)

        self._save_registry(registry)
        return models

    def _resolve_model_record(self, regime: str) -> dict[str, Any] | None:
        reg = self._load_registry()
        models = dict(reg.get("models", {}) or {})
        fallbacks = dict(reg.get("fallbacks", {}) or {})

        if regime in models:
            return dict(models[regime])

        base = self._base_regime(regime)
        if base in models:
            return dict(models[base])

        mapped = str(fallbacks.get(regime, "") or "")
        if mapped and mapped in models:
            return dict(models[mapped])

        # Final fallback: any model with same base prefix.
        if base:
            for k, v in models.items():
                ks = str(k)
                if ks == base or ks.startswith(base + "|"):
                    return dict(v)

        return None

    def predict(self, features_df, regime):
        """
        Load the appropriate regime model and score stocks.
        Falls back to base regime model if exact regime model not found.
        """
        frame = features_df.copy() if isinstance(features_df, pd.DataFrame) else pd.DataFrame()
        if frame.empty:
            return np.asarray([], dtype=float)

        regime_key = str(regime or "").strip()
        rec = self._resolve_model_record(regime_key)
        if rec is None:
            self._last_prediction_meta = {
                "requested_regime": regime_key,
                "resolved_regime": None,
                "model_path": None,
                "train_ic": None,
                "oos_ic": None,
                "backend": None,
            }
            return np.zeros(len(frame), dtype=float)

        model_path = Path(str(rec.get("model_path", "")))
        if not model_path.exists():
            return np.zeros(len(frame), dtype=float)

        with model_path.open("rb") as f:
            payload = pickle.load(f)
        model = payload.get("model")
        feats = [str(c) for c in list(payload.get("feature_cols", []))]

        use_cols = [c for c in feats if c in frame.columns]
        if not use_cols:
            return np.zeros(len(frame), dtype=float)

        X = frame[use_cols].replace([np.inf, -np.inf], np.nan)
        X = X.fillna(X.median(numeric_only=True)).fillna(0.0)

        pred = np.asarray(model.predict(X.to_numpy(dtype=float)), dtype=float).reshape(-1)
        self._last_prediction_meta = {
            "requested_regime": regime_key,
            "resolved_regime": str(rec.get("regime", regime_key)),
            "trained_on_regime": str(rec.get("trained_on_regime", "")),
            "model_path": str(model_path),
            "train_ic": rec.get("train_ic"),
            "oos_ic": rec.get("oos_ic"),
            "backend": rec.get("backend"),
        }
        return pred

    def get_best_features_for_regime(self, regime, top_n=20):
        """Return top N features for a given regime."""
        rec = self._resolve_model_record(str(regime or ""))
        if rec is None:
            return []
        fi = dict(rec.get("feature_importance", {}) or {})
        rows = sorted(fi.items(), key=lambda kv: float(kv[1]), reverse=True)
        n = max(1, int(top_n))
        return rows[:n]

    def get_last_prediction_meta(self) -> dict[str, Any]:
        return dict(self._last_prediction_meta)
