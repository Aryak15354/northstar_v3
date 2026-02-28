"""Research model adapters for production research workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging
import os
import warnings

import numpy as np
import pandas as pd


def _safe_n_jobs(params: Dict[str, Any], default: int = 1) -> int:
    """Use conservative parallelism by default to avoid loky hangs/leaks on laptops."""
    try:
        val = int(params.get("n_jobs", default))
    except Exception:
        val = default
    # Keep in safe range; callers can still opt into >1 explicitly.
    return max(1, val)


def _safe_torch_device(torch_module: Any, params: Optional[Dict[str, Any]] = None) -> Any:
    cfg = dict(params or {})
    disable_flag = str(os.getenv("NORTHSTAR_DISABLE_MPS", "")).strip().lower() in {"1", "true", "yes", "on"}
    if bool(cfg.get("disable_mps", False)):
        disable_flag = True
    if (not disable_flag) and hasattr(torch_module.backends, "mps") and torch_module.backends.mps.is_available():
        return torch_module.device("mps")
    return torch_module.device("cpu")


@dataclass
class ModelConfig:
    name: str
    params: Dict[str, Any]


class BaseResearchModel:
    """Uniform interface for research models."""

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}

    def fit(self, X: np.ndarray, y: np.ndarray) -> "BaseResearchModel":
        raise NotImplementedError

    def predict(self, X: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def feature_importance(self) -> Dict[str, float]:
        return {}


class SklearnRegressorModel(BaseResearchModel):
    def __init__(self, estimator: Any, name: str, params: Optional[Dict[str, Any]] = None):
        super().__init__(name=name, params=params)
        self.estimator = estimator
        self._feature_names: list[str] = []

    def _as_named_frame(self, X: np.ndarray, *, fit_mode: bool) -> pd.DataFrame:
        arr = np.asarray(X, dtype=float)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        n_features = int(arr.shape[1]) if arr.ndim == 2 else 0
        if fit_mode or len(self._feature_names) != n_features:
            self._feature_names = [f"f{i}" for i in range(n_features)]
        return pd.DataFrame(arr, columns=self._feature_names)

    def fit(self, X: np.ndarray, y: np.ndarray) -> "SklearnRegressorModel":
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        X_df = self._as_named_frame(X, fit_mode=True)
        self.estimator.fit(X_df, y_arr)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_df = self._as_named_frame(X, fit_mode=False)
        out = self.estimator.predict(X_df)
        return np.asarray(out, dtype=float).reshape(-1)

    def feature_importance(self) -> Dict[str, float]:
        fi = {}
        if hasattr(self.estimator, "feature_importances_"):
            arr = np.asarray(getattr(self.estimator, "feature_importances_"), dtype=float)
            fi = {f"f{i}": float(v) for i, v in enumerate(arr)}
        return fi


class LightGBMModel(SklearnRegressorModel):
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        try:
            from lightgbm import LGBMRegressor

            model = LGBMRegressor(
                n_estimators=int(p.get("n_estimators", 250)),
                learning_rate=float(p.get("learning_rate", 0.03)),
                max_depth=int(p.get("max_depth", -1)),
                num_leaves=int(p.get("num_leaves", 31)),
                random_state=int(p.get("random_state", 42)),
                subsample=float(p.get("subsample", 0.9)),
                colsample_bytree=float(p.get("colsample_bytree", 0.9)),
                n_jobs=_safe_n_jobs(p, default=1),
            )
            name = "lightgbm"
        except Exception:
            from sklearn.ensemble import HistGradientBoostingRegressor

            model = HistGradientBoostingRegressor(
                learning_rate=float(p.get("learning_rate", 0.03)),
                max_depth=None if int(p.get("max_depth", 6)) <= 0 else int(p.get("max_depth", 6)),
                max_iter=int(p.get("n_estimators", 250)),
                random_state=int(p.get("random_state", 42)),
            )
            name = "lightgbm_fallback_hgbr"
        super().__init__(model, name=name, params=p)


class XGBoostModel(SklearnRegressorModel):
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        try:
            from xgboost import XGBRegressor

            model = XGBRegressor(
                n_estimators=int(p.get("n_estimators", 300)),
                learning_rate=float(p.get("learning_rate", 0.03)),
                max_depth=int(p.get("max_depth", 6)),
                subsample=float(p.get("subsample", 0.9)),
                colsample_bytree=float(p.get("colsample_bytree", 0.9)),
                reg_alpha=float(p.get("reg_alpha", 0.0)),
                reg_lambda=float(p.get("reg_lambda", 1.0)),
                random_state=int(p.get("random_state", 42)),
                n_jobs=_safe_n_jobs(p, default=1),
            )
            name = "xgboost"
        except Exception:
            from sklearn.ensemble import RandomForestRegressor

            model = RandomForestRegressor(
                n_estimators=int(p.get("n_estimators", 300)),
                max_depth=None if int(p.get("max_depth", 8)) <= 0 else int(p.get("max_depth", 8)),
                min_samples_leaf=int(p.get("min_samples_leaf", 2)),
                random_state=int(p.get("random_state", 42)),
                n_jobs=_safe_n_jobs(p, default=1),
            )
            name = "xgboost_fallback_rf"
        super().__init__(model, name=name, params=p)


class CatBoostModel(SklearnRegressorModel):
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        try:
            from catboost import CatBoostRegressor

            model = CatBoostRegressor(
                iterations=int(p.get("iterations", 250)),
                depth=int(p.get("depth", 6)),
                learning_rate=float(p.get("learning_rate", 0.03)),
                loss_function="RMSE",
                random_seed=int(p.get("random_state", 42)),
                thread_count=_safe_n_jobs(p, default=1),
                verbose=False,
            )
            name = "catboost"
        except Exception:
            from sklearn.ensemble import ExtraTreesRegressor

            model = ExtraTreesRegressor(
                n_estimators=int(p.get("iterations", 300)),
                max_depth=None if int(p.get("depth", 8)) <= 0 else int(p.get("depth", 8)),
                min_samples_leaf=int(p.get("min_samples_leaf", 2)),
                random_state=int(p.get("random_state", 42)),
                n_jobs=_safe_n_jobs(p, default=1),
            )
            name = "catboost_fallback_extra_trees"
        super().__init__(model, name=name, params=p)


class RandomForestModel(SklearnRegressorModel):
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        from sklearn.ensemble import RandomForestRegressor

        model = RandomForestRegressor(
            n_estimators=int(p.get("n_estimators", 300)),
            max_depth=None if int(p.get("max_depth", 10)) <= 0 else int(p.get("max_depth", 10)),
            min_samples_leaf=int(p.get("min_samples_leaf", 2)),
            random_state=int(p.get("random_state", 42)),
            n_jobs=_safe_n_jobs(p, default=1),
        )
        super().__init__(model, name="random_forest", params=p)


class LSTMModel(BaseResearchModel):
    """Sequence LSTM with sklearn fallback when torch is unavailable."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        super().__init__(name="lstm", params=p)
        self.lookback = int(p.get("lookback", 20))
        self._torch_mode = False
        self._fallback = None
        self._model = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "LSTMModel":
        try:
            import torch
            import torch.nn as nn

            from .sequence_builder import create_sequences

            Xs, ys = create_sequences(X, y, self.lookback)
            if len(Xs) == 0:
                raise RuntimeError("insufficient sequence samples")

            hidden_dim = int(self.params.get("hidden_dim", 64))
            epochs = int(self.params.get("epochs", 12))
            lr = float(self.params.get("lr", 1e-3))

            class _Net(nn.Module):
                def __init__(self, in_dim: int, h: int):
                    super().__init__()
                    self.lstm = nn.LSTM(in_dim, h, batch_first=True)
                    self.fc = nn.Linear(h, 1)

                def forward(self, x):
                    out, _ = self.lstm(x)
                    return self.fc(out[:, -1, :]).squeeze(-1)

            device = _safe_torch_device(torch, self.params)
            net = _Net(int(X.shape[1]), hidden_dim).to(device)
            opt = torch.optim.Adam(net.parameters(), lr=lr)
            loss_fn = nn.MSELoss()

            Xt = torch.tensor(Xs, dtype=torch.float32, device=device)
            yt = torch.tensor(ys, dtype=torch.float32, device=device)

            net.train()
            for _ in range(max(1, epochs)):
                opt.zero_grad()
                pred = net(Xt)
                loss = loss_fn(pred, yt)
                loss.backward()
                opt.step()

            self._model = (net, device)
            self._torch_mode = True
            return self
        except Exception:
            from sklearn.neural_network import MLPRegressor

            self._fallback = MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                random_state=int(self.params.get("random_state", 42)),
                max_iter=int(self.params.get("max_iter", 300)),
            )
            self._fallback.fit(X, y)
            self._torch_mode = False
            return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._torch_mode and self._model is not None:
            try:
                import torch

                from .sequence_builder import create_sequences

                net, device = self._model
                Xs, _ = create_sequences(X, np.zeros(len(X), dtype=float), self.lookback)
                if len(Xs) == 0:
                    return np.zeros(len(X), dtype=float)
                net.eval()
                with torch.no_grad():
                    Xt = torch.tensor(Xs, dtype=torch.float32, device=device)
                    pred = net(Xt).detach().cpu().numpy().reshape(-1)
                # Pad front to keep length aligned.
                pad = np.full(self.lookback, pred[0] if len(pred) else 0.0)
                return np.concatenate([pad, pred])[: len(X)]
            except Exception:
                pass

        if self._fallback is None:
            return np.zeros(len(X), dtype=float)
        return np.asarray(self._fallback.predict(X), dtype=float).reshape(-1)


class TCNModel(BaseResearchModel):
    """Temporal convolution model with sklearn fallback."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        super().__init__(name="tcn", params=p)
        self.lookback = int(p.get("lookback", 20))
        self._torch_mode = False
        self._model = None
        self._fallback = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "TCNModel":
        try:
            import torch
            import torch.nn as nn

            from .sequence_builder import create_sequences

            Xs, ys = create_sequences(X, y, self.lookback)
            if len(Xs) == 0:
                raise RuntimeError("insufficient sequence samples")

            channels = int(self.params.get("channels", 32))
            epochs = int(self.params.get("epochs", 10))
            lr = float(self.params.get("lr", 1e-3))

            class _TCN(nn.Module):
                def __init__(self, in_dim: int, c: int):
                    super().__init__()
                    self.conv1 = nn.Conv1d(in_dim, c, kernel_size=3, padding=2, dilation=2)
                    self.conv2 = nn.Conv1d(c, c, kernel_size=3, padding=4, dilation=4)
                    self.relu = nn.ReLU()
                    self.fc = nn.Linear(c, 1)

                def forward(self, x):
                    # x: [B, T, F] -> [B, F, T]
                    z = x.transpose(1, 2)
                    z = self.relu(self.conv1(z))
                    z = self.relu(self.conv2(z))
                    z = z[:, :, -1]
                    return self.fc(z).squeeze(-1)

            device = _safe_torch_device(torch, self.params)
            net = _TCN(int(X.shape[1]), channels).to(device)
            opt = torch.optim.Adam(net.parameters(), lr=lr)
            loss_fn = nn.MSELoss()

            Xt = torch.tensor(Xs, dtype=torch.float32, device=device)
            yt = torch.tensor(ys, dtype=torch.float32, device=device)

            net.train()
            for _ in range(max(1, epochs)):
                opt.zero_grad()
                pred = net(Xt)
                loss = loss_fn(pred, yt)
                loss.backward()
                opt.step()

            self._model = (net, device)
            self._torch_mode = True
            return self
        except Exception:
            from sklearn.ensemble import GradientBoostingRegressor

            self._fallback = GradientBoostingRegressor(
                n_estimators=int(self.params.get("n_estimators", 300)),
                learning_rate=float(self.params.get("learning_rate", 0.03)),
                random_state=int(self.params.get("random_state", 42)),
            )
            self._fallback.fit(X, y)
            self._torch_mode = False
            return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._torch_mode and self._model is not None:
            try:
                import torch

                from .sequence_builder import create_sequences

                net, device = self._model
                Xs, _ = create_sequences(X, np.zeros(len(X), dtype=float), self.lookback)
                if len(Xs) == 0:
                    return np.zeros(len(X), dtype=float)
                net.eval()
                with torch.no_grad():
                    Xt = torch.tensor(Xs, dtype=torch.float32, device=device)
                    pred = net(Xt).detach().cpu().numpy().reshape(-1)
                pad = np.full(self.lookback, pred[0] if len(pred) else 0.0)
                return np.concatenate([pad, pred])[: len(X)]
            except Exception:
                pass

        if self._fallback is None:
            return np.zeros(len(X), dtype=float)
        return np.asarray(self._fallback.predict(X), dtype=float).reshape(-1)


class TransformerModel(BaseResearchModel):
    """TFT-style transformer with static/known/observed context and fallback."""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        p = dict(params or {})
        super().__init__(name="transformer", params=p)
        self.lookback = max(2, int(p.get("lookback", 30)))
        self._torch_mode = False
        self._model = None
        self._fallback = None
        self._scalers: Dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._seq_index_map: Optional[np.ndarray] = None
        self._seq_index_map_key: Optional[tuple] = None
        self._feature_proxy: Dict[str, float] = {}

    def _scale_X(self, X: np.ndarray, fit: bool, key: str = "plain") -> np.ndarray:
        Z = np.asarray(X, dtype=float)
        if fit or key not in self._scalers:
            mu = np.nanmean(Z, axis=0)
            sigma = np.nanstd(Z, axis=0)
            sigma = np.where((~np.isfinite(sigma)) | (sigma <= 1e-8), 1.0, sigma)
            mu = np.where(np.isfinite(mu), mu, 0.0)
            self._scalers[key] = (mu, sigma)
        mu, sigma = self._scalers[key]
        out = (Z - mu) / sigma
        out[~np.isfinite(out)] = 0.0
        return out.astype(np.float32, copy=False)

    def _scale_seq(self, X: np.ndarray, fit: bool, key: str) -> np.ndarray:
        Z = np.asarray(X, dtype=float)
        if Z.ndim != 3:
            raise ValueError("sequence tensor must be 3D")
        flat = Z.reshape(-1, Z.shape[-1])
        flat_scaled = self._scale_X(flat, fit=fit, key=key)
        return flat_scaled.reshape(Z.shape[0], Z.shape[1], Z.shape[2]).astype(np.float32, copy=False)

    def _build_seq_index_map(self, dataset: Any) -> np.ndarray:
        n = int(len(dataset.y))
        key = (
            n,
            self.lookback,
            int(np.asarray(dataset.index).shape[0]) if hasattr(dataset, "index") else n,
            int(np.asarray(dataset.tickers).shape[0]) if hasattr(dataset, "tickers") else n,
        )
        if self._seq_index_map is not None and self._seq_index_map_key == key:
            return self._seq_index_map

        idx_map = np.full((n, self.lookback), -1, dtype=np.int64)
        tickers = np.asarray(getattr(dataset, "tickers", np.arange(n)), dtype=object)
        if len(tickers) != n:
            tickers = np.arange(n, dtype=np.int64)

        # Build lookback windows per ticker to avoid cross-ticker leakage.
        for tk in pd.Series(tickers, dtype="object").drop_duplicates().tolist():
            grp = np.where(tickers == tk)[0]
            if len(grp) <= self.lookback:
                continue
            for p in range(self.lookback, len(grp)):
                t_idx = int(grp[p])
                idx_map[t_idx, :] = grp[p - self.lookback : p]

        self._seq_index_map = idx_map
        self._seq_index_map_key = key
        return idx_map

    def _dataset_context_arrays(self, dataset: Any) -> Dict[str, np.ndarray]:
        n = int(len(dataset.y))
        obs = np.asarray(
            getattr(dataset, "observed_dynamic_features", None)
            if getattr(dataset, "observed_dynamic_features", None) is not None
            else dataset.X,
            dtype=np.float32,
        )
        if obs.ndim != 2 or len(obs) != n:
            obs = np.asarray(dataset.X, dtype=np.float32)

        known = getattr(dataset, "known_dynamic_features", None)
        if known is None:
            known_arr = np.empty((n, 0), dtype=np.float32)
        else:
            known_arr = np.asarray(known, dtype=np.float32)
            if known_arr.ndim != 2 or len(known_arr) != n:
                known_arr = np.empty((n, 0), dtype=np.float32)

        static = getattr(dataset, "static_features", None)
        if static is None:
            static_arr = np.empty((n, 0), dtype=np.float32)
        else:
            static_arr = np.asarray(static, dtype=np.float32)
            if static_arr.ndim != 2 or len(static_arr) != n:
                static_arr = np.empty((n, 0), dtype=np.float32)

        ticker_ids = getattr(dataset, "ticker_ids", None)
        if ticker_ids is None:
            ticker_arr = np.zeros(n, dtype=np.int64)
        else:
            ticker_arr = np.asarray(ticker_ids, dtype=np.int64).reshape(-1)
            if len(ticker_arr) != n:
                ticker_arr = np.zeros(n, dtype=np.int64)

        sector_ids = getattr(dataset, "sector_ids", None)
        if sector_ids is None:
            sector_arr = np.zeros(n, dtype=np.int64)
        else:
            sector_arr = np.asarray(sector_ids, dtype=np.int64).reshape(-1)
            if len(sector_arr) != n:
                sector_arr = np.zeros(n, dtype=np.int64)

        return {
            "obs": obs,
            "known": known_arr,
            "static": static_arr,
            "ticker_ids": ticker_arr,
            "sector_ids": sector_arr,
        }

    def _extract_context(self, dataset: Any, target_indices: np.ndarray) -> Dict[str, np.ndarray]:
        seq_map = self._build_seq_index_map(dataset)
        idx = np.asarray(target_indices, dtype=np.int64).reshape(-1)
        idx = idx[(idx >= 0) & (idx < seq_map.shape[0])]
        if len(idx) == 0:
            return {"indices": np.empty((0,), dtype=np.int64)}
        valid = idx[seq_map[idx, 0] >= 0]
        if len(valid) == 0:
            return {"indices": np.empty((0,), dtype=np.int64)}

        hist = seq_map[valid]
        ctx = self._dataset_context_arrays(dataset)
        obs_seq = ctx["obs"][hist]
        known_seq = ctx["known"][hist] if ctx["known"].shape[1] > 0 else np.empty((len(valid), self.lookback, 0), dtype=np.float32)
        static = ctx["static"][valid] if ctx["static"].shape[1] > 0 else np.empty((len(valid), 0), dtype=np.float32)

        return {
            "indices": valid.astype(np.int64, copy=False),
            "obs_seq": np.asarray(obs_seq, dtype=np.float32),
            "known_seq": np.asarray(known_seq, dtype=np.float32),
            "static": np.asarray(static, dtype=np.float32),
            "ticker_ids": np.asarray(ctx["ticker_ids"][valid], dtype=np.int64),
            "sector_ids": np.asarray(ctx["sector_ids"][valid], dtype=np.int64),
            "y": np.asarray(dataset.y[valid], dtype=np.float32),
        }

    @staticmethod
    def _flatten_context(ctx: Dict[str, np.ndarray]) -> np.ndarray:
        if len(ctx.get("indices", [])) == 0:
            return np.empty((0, 0), dtype=np.float32)
        parts = [ctx["obs_seq"].reshape(len(ctx["indices"]), -1)]
        if ctx["known_seq"].shape[2] > 0:
            parts.append(ctx["known_seq"].reshape(len(ctx["indices"]), -1))
        if ctx["static"].shape[1] > 0:
            parts.append(ctx["static"])
        return np.concatenate(parts, axis=1).astype(np.float32, copy=False)

    def _torch_fit_context(self, train_ctx: Dict[str, np.ndarray], valid_ctx: Optional[Dict[str, np.ndarray]] = None) -> None:
        import torch
        import torch.nn as nn

        from .transformer_model import TimeSeriesTransformerNet

        d_model = int(self.params.get("d_model", 64))
        nhead = int(self.params.get("nhead", 4))
        nhead = max(1, min(nhead, d_model))
        while d_model % nhead != 0 and nhead > 1:
            nhead -= 1

        num_layers = int(self.params.get("num_layers", 2))
        dim_feedforward = int(self.params.get("dim_feedforward", 128))
        dropout = float(self.params.get("dropout", 0.1))
        epochs = int(self.params.get("epochs", 12))
        lr = float(self.params.get("lr", 1e-3))
        batch_size = int(self.params.get("batch_size", 128))
        patience = int(self.params.get("patience", 4))
        embed_dim = int(self.params.get("embed_dim", 16))

        risk_q = float(self.params.get("risk_quantile", 0.2))
        risk_q = min(0.45, max(0.05, risk_q))
        risk_threshold = float(np.quantile(train_ctx["y"], risk_q))

        direction_target = (train_ctx["y"] > 0.0).astype(np.float32)
        risk_target = (train_ctx["y"] <= risk_threshold).astype(np.float32)

        w_reg = float(self.params.get("loss_weight_return", 0.6))
        w_dir = float(self.params.get("loss_weight_direction", 0.2))
        w_risk = float(self.params.get("loss_weight_risk", 0.2))
        total_w = max(1e-8, w_reg + w_dir + w_risk)
        w_reg, w_dir, w_risk = (w_reg / total_w, w_dir / total_w, w_risk / total_w)

        obs_train = self._scale_seq(train_ctx["obs_seq"], fit=True, key="obs")
        known_train = (
            self._scale_seq(train_ctx["known_seq"], fit=True, key="known")
            if train_ctx["known_seq"].shape[2] > 0
            else train_ctx["known_seq"]
        )
        static_train = (
            self._scale_X(train_ctx["static"], fit=True, key="static")
            if train_ctx["static"].shape[1] > 0
            else train_ctx["static"]
        )

        obs_valid = known_valid = static_valid = None
        y_valid = d_valid = r_valid = None
        if valid_ctx is not None and len(valid_ctx.get("indices", [])) > 0:
            obs_valid = self._scale_seq(valid_ctx["obs_seq"], fit=False, key="obs")
            known_valid = (
                self._scale_seq(valid_ctx["known_seq"], fit=False, key="known")
                if valid_ctx["known_seq"].shape[2] > 0
                else valid_ctx["known_seq"]
            )
            static_valid = (
                self._scale_X(valid_ctx["static"], fit=False, key="static")
                if valid_ctx["static"].shape[1] > 0
                else valid_ctx["static"]
            )
            y_valid = np.asarray(valid_ctx["y"], dtype=np.float32)
            d_valid = (y_valid > 0.0).astype(np.float32)
            r_valid = (y_valid <= risk_threshold).astype(np.float32)

        train_tmax = int(np.max(train_ctx["ticker_ids"])) if len(train_ctx["ticker_ids"]) else 0
        train_smax = int(np.max(train_ctx["sector_ids"])) if len(train_ctx["sector_ids"]) else 0
        valid_tmax = (
            int(np.max(valid_ctx["ticker_ids"]))
            if valid_ctx is not None and len(valid_ctx.get("ticker_ids", []))
            else 0
        )
        valid_smax = (
            int(np.max(valid_ctx["sector_ids"]))
            if valid_ctx is not None and len(valid_ctx.get("sector_ids", []))
            else 0
        )
        n_tickers = int(max(train_tmax, valid_tmax) + 1)
        n_sectors = int(max(train_smax, valid_smax) + 1)

        device = _safe_torch_device(torch, self.params)
        net = TimeSeriesTransformerNet(
            observed_dim=int(obs_train.shape[2]),
            known_dim=int(known_train.shape[2]) if known_train.ndim == 3 else 0,
            static_dim=int(static_train.shape[1]) if static_train.ndim == 2 else 0,
            d_model=d_model,
            nhead=max(1, nhead),
            num_layers=max(1, num_layers),
            dim_feedforward=max(d_model, dim_feedforward),
            dropout=dropout,
            max_len=max(256, self.lookback + 8),
            n_tickers=max(0, n_tickers),
            n_sectors=max(0, n_sectors),
            embed_dim=max(4, embed_dim),
        ).to(device)

        opt = torch.optim.AdamW(
            net.parameters(),
            lr=lr,
            weight_decay=float(self.params.get("weight_decay", 1e-4)),
        )
        mse_loss = nn.MSELoss()
        bce_loss = nn.BCEWithLogitsLoss()

        obs_t = torch.tensor(obs_train, dtype=torch.float32, device=device)
        y_t = torch.tensor(train_ctx["y"], dtype=torch.float32, device=device)
        d_t = torch.tensor(direction_target, dtype=torch.float32, device=device)
        r_t = torch.tensor(risk_target, dtype=torch.float32, device=device)
        known_t = torch.tensor(known_train, dtype=torch.float32, device=device) if known_train.shape[2] > 0 else None
        static_t = torch.tensor(static_train, dtype=torch.float32, device=device) if static_train.shape[1] > 0 else None
        ticker_t = torch.tensor(train_ctx["ticker_ids"], dtype=torch.long, device=device)
        sector_t = torch.tensor(train_ctx["sector_ids"], dtype=torch.long, device=device)

        if obs_valid is not None:
            obs_v = torch.tensor(obs_valid, dtype=torch.float32, device=device)
            y_v = torch.tensor(y_valid, dtype=torch.float32, device=device)
            d_v = torch.tensor(d_valid, dtype=torch.float32, device=device)
            r_v = torch.tensor(r_valid, dtype=torch.float32, device=device)
            known_v = torch.tensor(known_valid, dtype=torch.float32, device=device) if known_valid is not None and known_valid.shape[2] > 0 else None
            static_v = torch.tensor(static_valid, dtype=torch.float32, device=device) if static_valid is not None and static_valid.shape[1] > 0 else None
            ticker_v = torch.tensor(valid_ctx["ticker_ids"], dtype=torch.long, device=device)
            sector_v = torch.tensor(valid_ctx["sector_ids"], dtype=torch.long, device=device)
        else:
            obs_v = y_v = d_v = r_v = known_v = static_v = ticker_v = sector_v = None

        n = int(obs_t.shape[0])
        batch_size = int(max(16, min(batch_size, n)))
        best_loss = float("inf")
        best_state = None
        stale_epochs = 0

        for _ in range(max(1, epochs)):
            net.train()
            perm = torch.randperm(n, device=device)
            running = 0.0
            seen = 0
            for start in range(0, n, batch_size):
                idx = perm[start : start + batch_size]
                xb = obs_t[idx]
                yb = y_t[idx]
                db = d_t[idx]
                rb = r_t[idx]
                kb = known_t[idx] if known_t is not None else None
                sb = static_t[idx] if static_t is not None else None
                tb = ticker_t[idx]
                qb = sector_t[idx]

                opt.zero_grad()
                out = net(observed=xb, known=kb, static=sb, ticker_id=tb, sector_id=qb)
                loss = (
                    w_reg * mse_loss(out["return_pred"], yb)
                    + w_dir * bce_loss(out["direction_logit"], db)
                    + w_risk * bce_loss(out["risk_logit"], rb)
                )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), float(self.params.get("grad_clip", 1.0)))
                opt.step()
                bs = int(xb.shape[0])
                running += float(loss.detach().cpu().item()) * bs
                seen += bs

            train_loss = running / max(1, seen)
            metric_loss = train_loss
            if obs_v is not None:
                net.eval()
                with torch.no_grad():
                    out_v = net(observed=obs_v, known=known_v, static=static_v, ticker_id=ticker_v, sector_id=sector_v)
                    metric_loss = float(
                        (
                            w_reg * mse_loss(out_v["return_pred"], y_v)
                            + w_dir * bce_loss(out_v["direction_logit"], d_v)
                            + w_risk * bce_loss(out_v["risk_logit"], r_v)
                        )
                        .detach()
                        .cpu()
                        .item()
                    )

            if metric_loss + 1e-8 < best_loss:
                best_loss = metric_loss
                best_state = {k: v.detach().cpu().clone() for k, v in net.state_dict().items()}
                stale_epochs = 0
            else:
                stale_epochs += 1
                if stale_epochs >= max(1, patience):
                    break

        if best_state is not None:
            net.load_state_dict(best_state)

        self._model = (net, device)
        self._torch_mode = True

        with torch.no_grad():
            obs_w = net.observed_proj.weight.detach().abs().mean(dim=0).cpu().numpy().reshape(-1)
        self._feature_proxy = {f"obs_f{i}": float(v) for i, v in enumerate(obs_w)}
        if hasattr(net, "static_proj") and net.static_proj is not None:
            with torch.no_grad():
                st_w = net.static_proj.weight.detach().abs().mean(dim=0).cpu().numpy().reshape(-1)
            for i, v in enumerate(st_w):
                self._feature_proxy[f"static_f{i}"] = float(v)

    def fit_with_context(
        self,
        dataset: Any,
        train_indices: np.ndarray,
        valid_indices: Optional[np.ndarray] = None,
    ) -> "TransformerModel":
        train_ctx = self._extract_context(dataset, np.asarray(train_indices, dtype=np.int64))
        valid_ctx = self._extract_context(dataset, np.asarray(valid_indices, dtype=np.int64)) if valid_indices is not None else None
        if len(train_ctx.get("indices", [])) < max(24, self.lookback * 2):
            # Fall back to tabular when sequence support is too sparse.
            return self.fit(dataset.X[np.asarray(train_indices, dtype=np.int64)], dataset.y[np.asarray(train_indices, dtype=np.int64)])
        try:
            self._torch_fit_context(train_ctx, valid_ctx=valid_ctx)
            return self
        except Exception:
            from sklearn.ensemble import GradientBoostingRegressor

            Xf = self._flatten_context(train_ctx)
            self._fallback = GradientBoostingRegressor(
                n_estimators=int(self.params.get("n_estimators", 300)),
                learning_rate=float(self.params.get("learning_rate", 0.03)),
                random_state=int(self.params.get("random_state", 42)),
            )
            self._fallback.fit(Xf, train_ctx["y"])
            self._torch_mode = False
            return self

    def predict_with_context(self, dataset: Any, target_indices: np.ndarray) -> Dict[str, np.ndarray]:
        ctx = self._extract_context(dataset, np.asarray(target_indices, dtype=np.int64))
        if len(ctx.get("indices", [])) == 0:
            return {
                "indices": np.empty((0,), dtype=np.int64),
                "predictions": np.empty((0,), dtype=float),
            }

        if self._torch_mode and self._model is not None:
            try:
                import torch

                net, device = self._model
                obs = self._scale_seq(ctx["obs_seq"], fit=False, key="obs")
                known = (
                    self._scale_seq(ctx["known_seq"], fit=False, key="known")
                    if ctx["known_seq"].shape[2] > 0
                    else ctx["known_seq"]
                )
                static = (
                    self._scale_X(ctx["static"], fit=False, key="static")
                    if ctx["static"].shape[1] > 0
                    else ctx["static"]
                )

                obs_t = torch.tensor(obs, dtype=torch.float32, device=device)
                known_t = torch.tensor(known, dtype=torch.float32, device=device) if known.shape[2] > 0 else None
                static_t = torch.tensor(static, dtype=torch.float32, device=device) if static.shape[1] > 0 else None
                ticker_t = torch.tensor(ctx["ticker_ids"], dtype=torch.long, device=device)
                sector_t = torch.tensor(ctx["sector_ids"], dtype=torch.long, device=device)

                net.eval()
                with torch.no_grad():
                    out = net(observed=obs_t, known=known_t, static=static_t, ticker_id=ticker_t, sector_id=sector_t)
                    pred = out["return_pred"].detach().cpu().numpy().reshape(-1)
                return {"indices": ctx["indices"], "predictions": pred}
            except Exception:
                pass

        if self._fallback is not None:
            Xf = self._flatten_context(ctx)
            pred = np.asarray(self._fallback.predict(Xf), dtype=float).reshape(-1)
            return {"indices": ctx["indices"], "predictions": pred}

        return {
            "indices": np.empty((0,), dtype=np.int64),
            "predictions": np.empty((0,), dtype=float),
        }

    def fit(self, X: np.ndarray, y: np.ndarray) -> "TransformerModel":
        """Compatibility path for non-context callers (ensemble fallbacks)."""
        try:
            import torch
            import torch.nn as nn

            from .sequence_builder import create_sequences
            from .transformer_model import TimeSeriesTransformerNet

            Xz = self._scale_X(X, fit=True, key="plain")
            y_arr = np.asarray(y, dtype=float)
            y_arr = np.where(np.isfinite(y_arr), y_arr, 0.0)
            Xs, ys = create_sequences(Xz, y_arr, self.lookback)
            if len(Xs) == 0:
                raise RuntimeError("insufficient sequence samples")

            d_model = int(self.params.get("d_model", 64))
            nhead = int(self.params.get("nhead", 4))
            nhead = max(1, min(nhead, d_model))
            while d_model % nhead != 0 and nhead > 1:
                nhead -= 1

            device = _safe_torch_device(torch, self.params)
            net = TimeSeriesTransformerNet(
                observed_dim=int(X.shape[1]),
                known_dim=0,
                static_dim=0,
                d_model=d_model,
                nhead=max(1, nhead),
                num_layers=max(1, int(self.params.get("num_layers", 2))),
                dim_feedforward=max(d_model, int(self.params.get("dim_feedforward", 128))),
                dropout=float(self.params.get("dropout", 0.1)),
                max_len=max(256, self.lookback + 8),
            ).to(device)

            opt = torch.optim.AdamW(
                net.parameters(),
                lr=float(self.params.get("lr", 1e-3)),
                weight_decay=float(self.params.get("weight_decay", 1e-4)),
            )
            mse_loss = nn.MSELoss()
            Xt = torch.tensor(Xs, dtype=torch.float32, device=device)
            yt = torch.tensor(ys, dtype=torch.float32, device=device)
            n = int(Xt.shape[0])
            batch_size = int(max(16, min(int(self.params.get("batch_size", 128)), n)))

            for _ in range(max(1, int(self.params.get("epochs", 8)))):
                net.train()
                perm = torch.randperm(n, device=device)
                for start in range(0, n, batch_size):
                    idx = perm[start : start + batch_size]
                    opt.zero_grad()
                    out = net(observed=Xt[idx])["return_pred"]
                    loss = mse_loss(out, yt[idx])
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(net.parameters(), float(self.params.get("grad_clip", 1.0)))
                    opt.step()

            self._model = (net, device)
            self._torch_mode = True
            with torch.no_grad():
                obs_w = net.observed_proj.weight.detach().abs().mean(dim=0).cpu().numpy().reshape(-1)
            self._feature_proxy = {f"obs_f{i}": float(v) for i, v in enumerate(obs_w)}
            return self
        except Exception:
            from sklearn.ensemble import GradientBoostingRegressor

            Xz = self._scale_X(X, fit=True, key="plain")
            self._fallback = GradientBoostingRegressor(
                n_estimators=int(self.params.get("n_estimators", 300)),
                learning_rate=float(self.params.get("learning_rate", 0.03)),
                random_state=int(self.params.get("random_state", 42)),
            )
            self._fallback.fit(Xz, y)
            self._torch_mode = False
            return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self._torch_mode and self._model is not None:
            try:
                import torch

                from .sequence_builder import create_sequences

                net, device = self._model
                Xz = self._scale_X(X, fit=False, key="plain")
                Xs, _ = create_sequences(Xz, np.zeros(len(X), dtype=float), self.lookback)
                if len(Xs) == 0:
                    return np.zeros(len(X), dtype=float)

                net.eval()
                with torch.no_grad():
                    Xt = torch.tensor(Xs, dtype=torch.float32, device=device)
                    out = net(observed=Xt)["return_pred"]
                    pred = out.detach().cpu().numpy().reshape(-1)
                pad = np.full(self.lookback, pred[0] if len(pred) else 0.0)
                return np.concatenate([pad, pred])[: len(X)]
            except Exception:
                pass

        if self._fallback is None:
            return np.zeros(len(X), dtype=float)
        Xz = self._scale_X(X, fit=False, key="plain")
        return np.asarray(self._fallback.predict(Xz), dtype=float).reshape(-1)

    def feature_importance(self) -> Dict[str, float]:
        if self._feature_proxy:
            return dict(self._feature_proxy)
        if self._fallback is not None and hasattr(self._fallback, "feature_importances_"):
            arr = np.asarray(getattr(self._fallback, "feature_importances_"), dtype=float)
            return {f"f{i}": float(v) for i, v in enumerate(arr)}
        return {}

class HMMRegimeModel:
    """Regime probability model with robust calibration and strict fit semantics."""

    def __init__(
        self,
        n_states: int = 3,
        random_state: int = 42,
        max_iter: int = 300,
        tol: float = 1e-3,
        n_init: int = 5,
        min_samples_per_state: int = 25,
        allow_kmeans_fallback: bool = False,
    ):
        self.n_states = int(max(2, n_states))
        self.random_state = int(random_state)
        self.max_iter = int(max(50, max_iter))
        self.tol = float(max(1e-6, tol))
        self.n_init = int(max(1, n_init))
        self.min_samples_per_state = int(max(5, min_samples_per_state))
        self.allow_kmeans_fallback = bool(allow_kmeans_fallback)
        self._model = None
        self._mode = "none"
        self._keep_cols: Optional[np.ndarray] = None
        self._mu: Optional[np.ndarray] = None
        self._sigma: Optional[np.ndarray] = None
        self.fit_info: Dict[str, Any] = {}

    @staticmethod
    def _normalize_rows(p: np.ndarray, n_states: int) -> np.ndarray:
        if p.size == 0:
            return np.full((0, n_states), 1.0 / float(n_states), dtype=float)
        out = np.asarray(p, dtype=float)
        out[~np.isfinite(out)] = 0.0
        out = np.clip(out, 0.0, None)
        s = out.sum(axis=1, keepdims=True)
        bad = (s <= 1e-12).reshape(-1)
        if np.any(bad):
            out[bad, :] = 1.0 / float(n_states)
            s = out.sum(axis=1, keepdims=True)
        return out / np.maximum(s, 1e-12)

    def _prepare_fit(self, X: np.ndarray) -> np.ndarray:
        Z = np.asarray(X, dtype=float)
        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)
        if Z.size == 0:
            return np.empty((0, 1), dtype=float)

        Z = np.where(np.isfinite(Z), Z, np.nan)
        col_med = np.nanmedian(Z, axis=0)
        col_med = np.where(np.isfinite(col_med), col_med, 0.0)
        bad = ~np.isfinite(Z)
        if np.any(bad):
            Z[bad] = np.take(col_med, np.where(bad)[1])

        col_std = np.nanstd(Z, axis=0)
        keep = np.asarray(col_std > 1e-8, dtype=bool)
        if not np.any(keep):
            keep = np.ones(Z.shape[1], dtype=bool)
        Z = Z[:, keep]

        mu = np.mean(Z, axis=0)
        sigma = np.std(Z, axis=0)
        sigma = np.where((~np.isfinite(sigma)) | (sigma <= 1e-8), 1.0, sigma)
        mu = np.where(np.isfinite(mu), mu, 0.0)
        Z = (Z - mu) / sigma
        Z[~np.isfinite(Z)] = 0.0

        self._keep_cols = keep
        self._mu = mu
        self._sigma = sigma
        return np.asarray(Z, dtype=float)

    def _prepare_predict(self, X: np.ndarray) -> np.ndarray:
        Z = np.asarray(X, dtype=float)
        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)
        if Z.size == 0:
            return np.empty((0, 1), dtype=float)
        Z = np.where(np.isfinite(Z), Z, np.nan)
        col_med = np.nanmedian(Z, axis=0)
        col_med = np.where(np.isfinite(col_med), col_med, 0.0)
        bad = ~np.isfinite(Z)
        if np.any(bad):
            Z[bad] = np.take(col_med, np.where(bad)[1])

        if self._keep_cols is not None and len(self._keep_cols) == Z.shape[1]:
            Z = Z[:, self._keep_cols]
        elif self._mu is not None:
            # Dimensional drift guard.
            dim = min(Z.shape[1], len(self._mu))
            Z = Z[:, :dim]
        if self._mu is not None and self._sigma is not None:
            dim = min(Z.shape[1], len(self._mu), len(self._sigma))
            mu = self._mu[:dim]
            sigma = self._sigma[:dim]
            Z = (Z[:, :dim] - mu) / sigma
        Z[~np.isfinite(Z)] = 0.0
        return np.asarray(Z, dtype=float)

    def fit(self, X: np.ndarray) -> "HMMRegimeModel":
        Z = self._prepare_fit(X)
        n = int(len(Z))
        min_samples = int(max(self.n_states + 5, self.n_states * self.min_samples_per_state))
        if n < min_samples:
            raise ValueError(
                f"insufficient_samples_for_hmm: n={n} required>={min_samples}"
            )

        best_model = None
        best_score = -np.inf
        best_converged = False
        last_exc: Optional[Exception] = None

        try:
            from hmmlearn.hmm import GaussianHMM
            logging.getLogger("hmmlearn").setLevel(logging.ERROR)

            for i in range(self.n_init):
                rs = int(self.random_state + i)
                model = GaussianHMM(
                    n_components=self.n_states,
                    covariance_type="diag",
                    n_iter=self.max_iter,
                    tol=self.tol,
                    random_state=rs,
                    min_covar=1e-4,
                )
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        model.fit(Z)
                        score = float(model.score(Z))
                    converged = bool(getattr(getattr(model, "monitor_", None), "converged", False))
                    if not np.isfinite(score):
                        continue
                    if (converged and not best_converged) or (
                        converged == best_converged and score > best_score
                    ):
                        best_model = model
                        best_score = score
                        best_converged = converged
                except Exception as exc:
                    last_exc = exc
                    continue

            if best_model is not None:
                self._model = best_model
                self._mode = "hmmlearn"
                self.fit_info = {
                    "mode": "hmmlearn",
                    "converged": bool(best_converged),
                    "score": float(best_score),
                    "n_samples": int(n),
                    "n_features": int(Z.shape[1]),
                    "n_init": int(self.n_init),
                }
                return self
        except Exception as exc:
            last_exc = exc

        if self.allow_kmeans_fallback:
            from sklearn.cluster import KMeans

            km = KMeans(n_clusters=self.n_states, random_state=self.random_state, n_init=20)
            km.fit(Z)
            self._model = km
            self._mode = "kmeans"
            self.fit_info = {
                "mode": "kmeans",
                "converged": True,
                "score": float("nan"),
                "n_samples": int(n),
                "n_features": int(Z.shape[1]),
                "reason": "hmm_failed",
                "error": str(last_exc) if last_exc is not None else None,
            }
            return self

        raise RuntimeError(f"hmm_fit_failed:{last_exc}")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Z = self._prepare_predict(X)
        if self._model is None:
            raise RuntimeError("hmm_not_fitted")

        if self._mode == "hmmlearn":
            try:
                p = self._model.predict_proba(Z)
                p = self._normalize_rows(p, self.n_states)
                if np.isfinite(p).all():
                    return p
            except Exception:
                pass
            # Soft fallback from emission means.
            means = getattr(self._model, "means_", None)
            if means is not None:
                centers = np.asarray(means, dtype=float)
                if centers.ndim == 1:
                    centers = centers.reshape(-1, 1)
                dim = min(centers.shape[1], Z.shape[1])
                if dim > 0:
                    d = np.linalg.norm(Z[:, None, :dim] - centers[None, :, :dim], axis=2)
                    inv = 1.0 / (d + 1e-8)
                    return self._normalize_rows(inv, self.n_states)

        if self._mode == "kmeans":
            centers = np.asarray(self._model.cluster_centers_, dtype=float)
            dim = min(centers.shape[1], Z.shape[1])
            if dim > 0:
                d = np.linalg.norm(Z[:, None, :dim] - centers[None, :, :dim], axis=2)
                inv = 1.0 / (d + 1e-8)
                return self._normalize_rows(inv, self.n_states)

        raise RuntimeError("hmm_predict_failed_no_valid_probabilities")


class DynamicFactorModel:
    """Latent macro factor extractor with statsmodels optional path."""

    def __init__(self, n_factors: int = 3, random_state: int = 42):
        self.n_factors = int(max(1, n_factors))
        self.random_state = int(random_state)
        self._mode = "none"
        self._model = None

    def fit(self, X: np.ndarray) -> "DynamicFactorModel":
        Z = np.asarray(X, dtype=float)
        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)
        # Robust default: PCA factor extraction.
        from sklearn.decomposition import PCA

        pca = PCA(n_components=min(self.n_factors, Z.shape[1]), random_state=self.random_state)
        pca.fit(Z)
        self._model = pca
        self._mode = "pca"
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        Z = np.asarray(X, dtype=float)
        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)
        if self._model is None:
            return np.zeros((len(Z), self.n_factors), dtype=float)
        return np.asarray(self._model.transform(Z), dtype=float)

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return self.fit(X).transform(X)
