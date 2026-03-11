"""Leakage-safe walk-forward training pipeline."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence, Tuple
import logging

import numpy as np
import pandas as pd

from .regime_engine import RegimeEngine
from .research_types import ModelRunResult, ResearchDataset, ResearchWindowResult
from .splits import eligible_trading_dates, rolling_time_splits
from .walk_forward_validator import (
    aggregate_metrics,
    build_cross_sectional_portfolio_returns,
    compute_window_metrics,
)

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Run rolling walk-forward validation for one model."""

    def __init__(
        self,
        train_periods: int = 756,
        valid_periods: int = 126,
        test_periods: int = 126,
        step_periods: int = 63,
        min_tickers_per_date: int = 50,
        max_windows: int = 12,
        start_window: int = 0,
        portfolio_cfg: Optional[Dict[str, Any]] = None,
        holdout_train_end_date: Optional[str] = None,
        holdout_test_start_date: Optional[str] = None,
        holdout_test_end_date: Optional[str] = None,
        holdout_valid_periods: Optional[int] = None,
        holdout_min_train_periods: int = 252,
    ):
        self.train_periods = int(train_periods)
        self.valid_periods = int(valid_periods)
        self.test_periods = int(test_periods)
        self.step_periods = int(step_periods)
        self.min_tickers_per_date = max(1, int(min_tickers_per_date))
        self.max_windows = int(max_windows)
        self.start_window = max(0, int(start_window))
        self.portfolio_cfg = dict(portfolio_cfg or {})
        self.holdout_train_end_date = str(holdout_train_end_date).strip() if holdout_train_end_date else ""
        self.holdout_test_start_date = str(holdout_test_start_date).strip() if holdout_test_start_date else ""
        self.holdout_test_end_date = str(holdout_test_end_date).strip() if holdout_test_end_date else ""
        self.holdout_valid_periods = int(holdout_valid_periods) if holdout_valid_periods is not None else int(valid_periods)
        self.holdout_min_train_periods = max(20, int(holdout_min_train_periods))

    def _apply_label_embargo(
        self,
        *,
        frame: pd.DataFrame,
        train_mask: np.ndarray,
        test_mask: np.ndarray,
        date_col: str = "date",
        embargo_periods: int = 0,
    ) -> Tuple[np.ndarray, int]:
        """Drop train/valid rows whose labels can overlap into the test horizon."""
        emb = max(0, int(embargo_periods))
        if emb <= 0 or frame.empty or date_col not in frame.columns:
            return train_mask, 0

        d = pd.to_datetime(frame[date_col], errors="coerce")
        test_dates = np.array(sorted(pd.Index(d[np.asarray(test_mask, dtype=bool) & d.notna()].unique())))
        all_dates = np.array(sorted(pd.Index(d[d.notna()].unique())))
        if len(test_dates) == 0 or len(all_dates) == 0:
            return train_mask, 0

        first_test = test_dates[0]
        test_idx = int(np.searchsorted(all_dates, first_test))
        if test_idx <= 0:
            return train_mask, 0

        emb_start = max(0, test_idx - emb)
        embargo_dates = set(all_dates[emb_start:test_idx].tolist())
        if not embargo_dates:
            return train_mask, 0

        row_dates = d.to_numpy()
        embargo_row_mask = np.array([x in embargo_dates for x in row_dates], dtype=bool)
        filtered = np.asarray(train_mask, dtype=bool) & ~embargo_row_mask
        dropped = int(np.sum(np.asarray(train_mask, dtype=bool) & embargo_row_mask))
        return filtered, dropped

    @staticmethod
    def _apply_regime_policy_to_predictions(
        *,
        y_pred: np.ndarray,
        regimes: Sequence[Any] | None,
        active_regimes: Optional[Sequence[str]] = None,
        invert_regimes: Optional[Sequence[str]] = None,
        regime_scales: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        out = np.asarray(y_pred, dtype=float).reshape(-1).copy()
        if len(out) == 0 or regimes is None:
            return out
        reg = pd.Series(regimes, dtype="string").fillna("").str.strip().astype(str).to_numpy(dtype=object)
        n = min(len(out), len(reg))
        out = out[:n]
        reg = reg[:n]

        active_set = {str(x).strip() for x in (active_regimes or []) if str(x).strip()}
        if active_set:
            keep = np.asarray([str(x) in active_set for x in reg], dtype=bool)
            out[~keep] = 0.0

        inv = {str(x).strip() for x in (invert_regimes or []) if str(x).strip()}
        if inv:
            flip = np.asarray([str(x) in inv for x in reg], dtype=bool)
            out[flip] = -out[flip]

        scales = dict(regime_scales or {})
        if scales:
            default_scale = float(scales.get("default", 1.0) or 1.0)
            mul = np.asarray([float(scales.get(str(x), default_scale) or default_scale) for x in reg], dtype=float)
            out = out * mul
        return out

    @staticmethod
    def _apply_prediction_transform(
        *,
        y_pred: np.ndarray,
        dates: Sequence[Any] | None,
        mode: str = "raw",
        rank_power: float = 1.5,
        tanh_scale: float = 3.0,
    ) -> np.ndarray:
        out = np.asarray(y_pred, dtype=float).reshape(-1).copy()
        if len(out) == 0 or dates is None:
            return out
        m = str(mode or "raw").strip().lower()
        if m in {"", "raw", "none"}:
            return out

        d = pd.to_datetime(pd.Series(dates), errors="coerce")
        n = min(len(out), len(d))
        if n <= 0:
            return out
        s = pd.Series(out[:n], dtype=float)
        g = d.iloc[:n]

        if m == "zscore":
            mu = s.groupby(g, sort=False).transform("mean")
            sd = s.groupby(g, sort=False).transform("std").replace(0.0, np.nan)
            z = (s - mu) / (sd + 1e-12)
            out[:n] = z.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
            return out

        if m == "rank":
            r = s.groupby(g, sort=False).rank(method="average", pct=True)
            out[:n] = (r.fillna(0.5) - 0.5).to_numpy(dtype=float)
            return out

        if m == "rank_power":
            r = s.groupby(g, sort=False).rank(method="average", pct=True)
            rc = (r.fillna(0.5) - 0.5).to_numpy(dtype=float)
            p = float(max(1.0, rank_power))
            out[:n] = np.sign(rc) * np.power(np.abs(rc), p)
            return out

        if m == "tanh":
            mu = s.groupby(g, sort=False).transform("mean")
            sd = s.groupby(g, sort=False).transform("std").replace(0.0, np.nan)
            z = (s - mu) / (sd + 1e-12)
            z = z.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
            k = float(max(0.1, tanh_scale))
            out[:n] = np.tanh(k * z)
            return out

        return out

    @staticmethod
    def _neutralize_predictions(
        *,
        y_pred: np.ndarray,
        slice_frame: pd.DataFrame,
        dates: Sequence[Any] | None,
        factor_cols: Sequence[str] | None = None,
        sector_col: str | None = None,
        sector_neutralize: bool = False,
    ) -> np.ndarray:
        out = np.asarray(y_pred, dtype=float).reshape(-1).copy()
        if len(out) == 0 or dates is None:
            return out
        n = min(len(out), len(slice_frame))
        if n <= 0:
            return out

        d = pd.to_datetime(pd.Series(dates).iloc[:n], errors="coerce")
        s = pd.Series(out[:n], dtype=float)

        if bool(sector_neutralize) and sector_col and sector_col in slice_frame.columns:
            sec = slice_frame.iloc[:n][sector_col].astype(str).fillna("UNKNOWN")
            key = pd.MultiIndex.from_arrays([d, sec])
            sec_mean = s.groupby(key, sort=False).transform("mean")
            s = s - sec_mean

        facs = [str(c) for c in (factor_cols or []) if str(c) in slice_frame.columns]
        if facs:
            # Date-wise cross-sectional neutralization to remove linear factor loads.
            for dt, idx in pd.Series(np.arange(n), index=d).groupby(level=0, sort=False):
                ii = np.asarray(idx.to_numpy(dtype=int), dtype=int)
                if len(ii) < 8:
                    continue
                yv = s.iloc[ii].to_numpy(dtype=float)
                X = slice_frame.iloc[ii][facs].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
                if X.ndim != 2 or X.shape[0] != len(ii):
                    continue
                mask = np.isfinite(yv)
                if X.size > 0:
                    mask &= np.all(np.isfinite(X), axis=1)
                if int(mask.sum()) < max(6, (X.shape[1] + 2 if X.size > 0 else 6)):
                    continue
                Xw = X[mask]
                yw = yv[mask]
                # add intercept
                Xw = np.column_stack([np.ones(len(Xw), dtype=float), Xw])
                try:
                    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
                    fitted = Xw @ beta
                    resid = yw - fitted
                    yv2 = yv.copy()
                    yv2[mask] = resid
                    s.iloc[ii] = yv2
                except Exception:
                    continue

        out[:n] = s.replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
        return out

    def _fixed_holdout_split(self, frame: pd.DataFrame, date_col: str = "date") -> Optional[Dict[str, np.ndarray]]:
        if (not self.holdout_train_end_date) and (not self.holdout_test_start_date):
            return None
        if frame.empty or date_col not in frame.columns:
            return None
        d = pd.to_datetime(frame[date_col], errors="coerce")
        ok = d.notna().to_numpy()
        if not ok.any():
            return None
        unique_dates = eligible_trading_dates(
            frame,
            date_col=date_col,
            ticker_col="ticker",
            min_tickers_per_date=self.min_tickers_per_date,
        )
        if len(unique_dates) < (self.holdout_min_train_periods + 10):
            return None

        train_end = pd.to_datetime(self.holdout_train_end_date, errors="coerce") if self.holdout_train_end_date else pd.NaT
        test_start = pd.to_datetime(self.holdout_test_start_date, errors="coerce") if self.holdout_test_start_date else pd.NaT
        test_end = pd.to_datetime(self.holdout_test_end_date, errors="coerce") if self.holdout_test_end_date else pd.NaT

        if pd.isna(train_end) and pd.notna(test_start):
            prior = unique_dates[unique_dates < np.datetime64(test_start)]
            if len(prior) == 0:
                return None
            train_end = pd.Timestamp(prior[-1])
        if pd.isna(test_start) and pd.notna(train_end):
            nxt = unique_dates[unique_dates > np.datetime64(train_end)]
            if len(nxt) == 0:
                return None
            test_start = pd.Timestamp(nxt[0])
        if pd.isna(train_end) or pd.isna(test_start):
            return None
        if test_start <= train_end:
            return None
        if pd.notna(test_end) and test_end < test_start:
            return None

        train_unique = unique_dates[unique_dates <= np.datetime64(train_end)]
        test_unique = unique_dates[unique_dates >= np.datetime64(test_start)]
        if pd.notna(test_end):
            test_unique = test_unique[test_unique <= np.datetime64(test_end)]
        if len(train_unique) < self.holdout_min_train_periods or len(test_unique) < 20:
            return None

        valid_n = max(0, min(int(self.holdout_valid_periods), max(0, len(train_unique) - self.holdout_min_train_periods)))
        if valid_n > 0:
            valid_dates = set(train_unique[-valid_n:])
            train_dates = set(train_unique[:-valid_n])
        else:
            valid_dates = set()
            train_dates = set(train_unique)
        test_dates = set(test_unique)

        row_dates = d.to_numpy()
        train_mask = np.array([x in train_dates for x in row_dates], dtype=bool)
        valid_mask = np.array([x in valid_dates for x in row_dates], dtype=bool)
        test_mask = np.array([x in test_dates for x in row_dates], dtype=bool)
        if not train_mask.any() or not test_mask.any():
            return None
        return {
            "train_mask": train_mask,
            "valid_mask": valid_mask,
            "test_mask": test_mask,
            "train_start": str(np.min(train_unique)),
            "train_end": str(np.max(train_unique)),
            "test_start": str(np.min(test_unique)),
            "test_end": str(np.max(test_unique)),
            "split_mode": "fixed_holdout",
        }

    def _holdout_requested(self) -> bool:
        return bool(
            str(self.holdout_train_end_date or "").strip()
            or str(self.holdout_test_start_date or "").strip()
            or str(self.holdout_test_end_date or "").strip()
        )

    @staticmethod
    def _usable_regime_values(series: pd.Series) -> list[str]:
        vals = (
            series.astype("string")
            .fillna("")
            .str.strip()
            .replace({"<NA>": "", "nan": "", "None": "", "unknown": ""})
        )
        return sorted([str(x) for x in vals.unique().tolist() if str(x)])

    def _ensure_regime_labels(self, frame: pd.DataFrame, dataset: ResearchDataset, regime_col: str) -> pd.DataFrame:
        work = frame.copy()
        if regime_col in work.columns and len(self._usable_regime_values(work[regime_col])) >= 2:
            return work
        if "date" not in work.columns:
            return work

        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work = work.dropna(subset=["date"]).copy()
        if work.empty:
            return work

        engine = RegimeEngine(
            {
                "regime_labels_path": str(
                    dataset.metadata.get("regime_labels_path", "data/processed/regime_labels.parquet")
                )
            }
        )
        start = pd.to_datetime(work["date"], errors="coerce").min()
        end = pd.to_datetime(work["date"], errors="coerce").max()
        reg_series = engine.get_regime_series(start, end)

        if reg_series.empty:
            close_col = next((c for c in ["close", "Close", "adj_close", "Adj Close"] if c in work.columns), None)
            prices_for_engine = work[["date"]].copy()
            if "ticker" in work.columns:
                prices_for_engine["ticker"] = work["ticker"].astype(str)
            if close_col is not None:
                prices_for_engine["Close"] = pd.to_numeric(work[close_col], errors="coerce")
            else:
                # Last-resort deterministic proxy if close is unavailable.
                if "vol_20d" in work.columns:
                    proxy = pd.to_numeric(work["vol_20d"], errors="coerce").fillna(method="ffill").fillna(0.0)
                else:
                    proxy = pd.Series(np.linspace(1.0, 2.0, len(work)), index=work.index, dtype=float)
                prices_for_engine["Close"] = (100.0 + proxy.rank(method="first")).to_numpy()
            try:
                _ = engine.build_historical_regimes(prices_df=prices_for_engine, macro_df=None)
                reg_series = engine.get_regime_series(start, end)
            except Exception:
                reg_series = pd.Series(dtype=object)

        if not reg_series.empty:
            reg_map = pd.Series(reg_series.astype(str).to_numpy(), index=pd.DatetimeIndex(reg_series.index).normalize())
            work[regime_col] = pd.to_datetime(work["date"], errors="coerce").dt.normalize().map(reg_map)
            if len(self._usable_regime_values(work[regime_col])) >= 2:
                return work

        # Fallback (kept for backward compatibility only).
        vol_src = pd.to_numeric(work.get("vol_20d"), errors="coerce") if "vol_20d" in work.columns else pd.Series(np.nan, index=work.index)
        vol_daily = vol_src.groupby(work["date"], sort=False).mean()
        vol_med = float(pd.to_numeric(vol_daily, errors="coerce").median()) if len(vol_daily) else 0.0
        vol_state = pd.Series(
            np.where(pd.to_numeric(vol_daily, errors="coerce").fillna(vol_med).to_numpy() >= vol_med, "high_vol", "low_vol"),
            index=vol_daily.index,
            dtype="object",
        )
        trend_src = pd.to_numeric(work.get("mom_20d"), errors="coerce") if "mom_20d" in work.columns else pd.Series(np.nan, index=work.index)
        trend_daily = trend_src.groupby(work["date"], sort=False).mean()
        trend_state = pd.Series(
            np.where(pd.to_numeric(trend_daily, errors="coerce").fillna(0.0).to_numpy() >= 0.0, "uptrend", "downtrend"),
            index=trend_daily.index,
            dtype="object",
        )
        idx = sorted(set(vol_state.index).intersection(set(trend_state.index)))
        reg_daily = pd.Series([f"{vol_state.loc[i]}|{trend_state.loc[i]}" for i in idx], index=pd.DatetimeIndex(idx))
        work[regime_col] = pd.to_datetime(work["date"], errors="coerce").dt.normalize().map(reg_daily).fillna("unknown").astype(str)
        return work

    def run(
        self,
        model: Any,
        dataset: ResearchDataset,
        regime_col: str = "regime",
        progress_callback: Optional[Any] = None,
        regime_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        frame = dataset.frame.copy()
        if frame.empty or "date" not in frame.columns:
            return {
                "model": getattr(model, "name", type(model).__name__),
                "status": "failed",
                "error": "dataset_frame_missing_date",
                "windows": [],
                "aggregate_metrics": {},
                "regime_metrics": {},
            }

        X = dataset.X
        y = dataset.y
        target_horizon_days = int(dataset.metadata.get("target_horizon_days", 1) or 1)
        target_realized_col = str(dataset.metadata.get("target_realized_col", "") or "").strip()
        frame = self._ensure_regime_labels(frame, dataset, regime_col)

        windows: List[ResearchWindowResult] = []
        metrics_raw: List[Dict[str, float]] = []
        regime_bucket: Dict[str, List[Dict[str, float]]] = {}
        portfolio_series_rows: List[Dict[str, Any]] = []
        rebalance_snapshots: List[Dict[str, Any]] = []
        ls_q = float(self.portfolio_cfg.get("long_short_quantile", 0.20))
        min_assets = int(self.portfolio_cfg.get("min_assets_per_day", 8))
        max_w = float(self.portfolio_cfg.get("max_weight_per_asset", 0.10))
        use_vol = bool(self.portfolio_cfg.get("use_vol_scaling", True))
        turnover_cap = float(self.portfolio_cfg.get("turnover_cap", 0.30))
        high_vol_exposure_scale = float(self.portfolio_cfg.get("high_vol_exposure_scale", 0.50))
        regime_exposure_scales_raw = self.portfolio_cfg.get("regime_exposure_scales", {}) or {}
        regime_exposure_scales: Dict[str, float] = {}
        if isinstance(regime_exposure_scales_raw, dict):
            for k, v in regime_exposure_scales_raw.items():
                key = str(k or "").strip()
                if not key:
                    continue
                try:
                    regime_exposure_scales[key] = float(v)
                except Exception:
                    continue
        elif isinstance(regime_exposure_scales_raw, str):
            for token in str(regime_exposure_scales_raw).split(","):
                part = str(token).strip()
                if not part or ":" not in part:
                    continue
                k, v = part.split(":", 1)
                key = str(k or "").strip()
                if not key:
                    continue
                try:
                    regime_exposure_scales[key] = float(v)
                except Exception:
                    continue
        portfolio_mode = str(self.portfolio_cfg.get("portfolio_mode", "long_short") or "long_short").strip().lower()
        if portfolio_mode not in {"long_short", "long_only", "short_only"}:
            portfolio_mode = "long_short"
        pred_transform = str(self.portfolio_cfg.get("prediction_transform", "raw") or "raw").strip().lower()
        pred_rank_power = float(self.portfolio_cfg.get("prediction_rank_power", 1.5) or 1.5)
        pred_tanh_scale = float(self.portfolio_cfg.get("prediction_tanh_scale", 3.0) or 3.0)
        pred_sector_neutral = bool(self.portfolio_cfg.get("prediction_sector_neutralize", False))
        pred_neutral_factors_cfg = self.portfolio_cfg.get("prediction_neutralize_factors", []) or []
        if isinstance(pred_neutral_factors_cfg, str):
            pred_neutral_factors = [x.strip() for x in str(pred_neutral_factors_cfg).split(",") if x.strip()]
        else:
            pred_neutral_factors = [str(x).strip() for x in list(pred_neutral_factors_cfg) if str(x).strip()]
        # Use horizon-aligned rebalance cadence by default to avoid overlap inflation.
        default_rebalance_days = max(1, int(target_horizon_days))
        rebalance_days = int(self.portfolio_cfg.get("rebalance_frequency_days", default_rebalance_days))
        sector_neutralize = bool(self.portfolio_cfg.get("sector_neutralize", False))
        max_sector_weight = float(self.portfolio_cfg.get("max_sector_weight", 1.0))
        txn_cost_bps = float(self.portfolio_cfg.get("transaction_cost_bps_per_side", 0.0))
        cfg_embargo = int(self.portfolio_cfg.get("label_embargo_periods", 0) or 0)
        label_embargo_periods = max(0, cfg_embargo if cfg_embargo > 0 else int(target_horizon_days))

        fixed_split = self._fixed_holdout_split(frame, date_col="date")
        holdout_requested = self._holdout_requested()
        if fixed_split is not None:
            splits_iter = [fixed_split]
            target_windows = 1
        else:
            if holdout_requested:
                date_min = str(pd.to_datetime(frame["date"], errors="coerce").min()) if "date" in frame.columns else "NA"
                date_max = str(pd.to_datetime(frame["date"], errors="coerce").max()) if "date" in frame.columns else "NA"
                required_start = "NA"
                if self.holdout_train_end_date:
                    try:
                        train_end = pd.to_datetime(self.holdout_train_end_date, errors="coerce")
                        if pd.notna(train_end):
                            required_start = str(train_end - pd.Timedelta(days=int(self.holdout_min_train_periods)))
                    except Exception:
                        required_start = "NA"
                raise ValueError(
                    "training_pipeline_holdout_split_unavailable:"
                    f"train_end={self.holdout_train_end_date or 'NA'}:"
                    f"test_start={self.holdout_test_start_date or 'NA'}:"
                    f"test_end={self.holdout_test_end_date or 'NA'}:"
                    f"frame_start={date_min}:frame_end={date_max}:"
                    f"required_train_start~={required_start}"
                )
            splits_iter = rolling_time_splits(
                frame,
                date_col="date",
                ticker_col="ticker",
                train_periods=self.train_periods,
                valid_periods=self.valid_periods,
                test_periods=self.test_periods,
                step_periods=self.step_periods,
                min_tickers_per_date=self.min_tickers_per_date,
            )
            target_windows = int(self.max_windows)

        seen_windows = 0
        for i, split in enumerate(splits_iter):
            if i < self.start_window:
                continue
            if seen_windows >= self.max_windows:
                break
            seen_windows += 1
            if callable(progress_callback):
                progress_callback(
                    event="window_start",
                    index=int(seen_windows),
                    total=int(target_windows),
                    model=str(getattr(model, "name", type(model).__name__)),
                )

            tr = split["train_mask"]
            va = split["valid_mask"]
            te = split["test_mask"]

            train_mask = tr | va
            train_mask, _embargo_dropped_rows = self._apply_label_embargo(
                frame=frame,
                train_mask=train_mask,
                test_mask=te,
                date_col="date",
                embargo_periods=label_embargo_periods,
            )
            if train_mask.sum() < 50 or te.sum() < 20:
                continue

            X_train, y_train = X[train_mask], y[train_mask]
            X_test, y_test = X[te], y[te]

            train_indices = np.where(train_mask)[0]
            valid_indices = np.where(va)[0]
            test_indices = np.where(te)[0]

            pred_indices = test_indices
            if hasattr(model, "fit_with_context") and hasattr(model, "predict_with_context"):
                model.fit_with_context(
                    dataset=dataset,
                    train_indices=train_indices,
                    valid_indices=valid_indices,
                )
                pred_obj = model.predict_with_context(dataset=dataset, target_indices=test_indices)
                if isinstance(pred_obj, dict):
                    pred_indices = np.asarray(pred_obj.get("indices", test_indices), dtype=int).reshape(-1)
                    y_pred = np.asarray(pred_obj.get("predictions", []), dtype=float).reshape(-1)
                else:
                    y_pred = np.asarray(pred_obj, dtype=float).reshape(-1)
            else:
                model.fit(X_train, y_train)
                y_pred = np.asarray(model.predict(X_test), dtype=float).reshape(-1)
                pred_indices = test_indices

            y_true = np.asarray(y[pred_indices], dtype=float).reshape(-1)
            y_realized = (
                np.asarray(frame.iloc[pred_indices][target_realized_col], dtype=float).reshape(-1)
                if target_realized_col and target_realized_col in frame.columns
                else np.asarray(y_true, dtype=float).reshape(-1)
            )

            n = min(len(y_pred), len(y_true), len(y_realized))
            y_pred = y_pred[:n]
            y_true = y_true[:n]
            y_realized = y_realized[:n]
            pred_indices = pred_indices[:n]

            if n == 0:
                continue

            dates = frame.iloc[pred_indices]["date"].to_numpy()
            regimes = (
                frame.iloc[pred_indices][regime_col].to_numpy(dtype=object)
                if regime_col in frame.columns
                else None
            )
            slice_frame = frame.iloc[pred_indices].copy()
            sector_col = next((c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in frame.columns), None)
            if regime_policy:
                active_regimes_cfg = regime_policy.get("active_regimes", None)
                if not active_regimes_cfg:
                    active_raw = str(regime_policy.get("active_regime", "") or "").strip()
                    active_regimes_cfg = [x.strip() for x in active_raw.split(",") if x.strip()] if active_raw else []
                y_pred = self._apply_regime_policy_to_predictions(
                    y_pred=y_pred,
                    regimes=regimes,
                    active_regimes=list(active_regimes_cfg or []),
                    invert_regimes=list(regime_policy.get("invert_regimes", []) or []),
                    regime_scales=dict(regime_policy.get("regime_scales", {}) or {}),
                )
            if pred_neutral_factors or pred_sector_neutral:
                y_pred = self._neutralize_predictions(
                    y_pred=y_pred,
                    slice_frame=slice_frame,
                    dates=dates,
                    factor_cols=pred_neutral_factors,
                    sector_col=sector_col,
                    sector_neutralize=pred_sector_neutral,
                )
            y_pred = self._apply_prediction_transform(
                y_pred=y_pred,
                dates=dates,
                mode=pred_transform,
                rank_power=pred_rank_power,
                tanh_scale=pred_tanh_scale,
            )
            tickers = slice_frame["ticker"].to_numpy(dtype=str) if "ticker" in slice_frame.columns else None
            sectors = slice_frame[sector_col].to_numpy(dtype=str) if sector_col is not None else None
            vol = slice_frame["vol_20d"].to_numpy(dtype=float) if "vol_20d" in slice_frame.columns else None
            m = compute_window_metrics(
                y_true=y_true,
                y_pred=y_pred,
                realized_returns=y_realized,
                dates=dates,
                regimes=regimes,
                tickers=tickers,
                sectors=sectors,
                vol=vol,
                long_short_quantile=ls_q,
                min_assets_per_day=min_assets,
                max_weight_per_asset=max_w,
                use_vol_scaling=use_vol,
                rebalance_frequency_days=rebalance_days,
                sector_neutralize=sector_neutralize,
                max_sector_weight=max_sector_weight,
                transaction_cost_bps_per_side=txn_cost_bps,
                target_horizon_days=target_horizon_days,
                portfolio_mode=portfolio_mode,
                turnover_cap=turnover_cap,
                high_vol_exposure_scale=high_vol_exposure_scale,
                regime_exposure_scales=regime_exposure_scales,
            )
            metrics_raw.append(m)

            # Emit cycle-level portfolio trace for strategy duplication / turnover integrity gates.
            trace = build_cross_sectional_portfolio_returns(
                y_true=y_realized,
                y_pred=y_pred,
                dates=dates,
                regimes=regimes,
                tickers=tickers,
                sectors=sectors,
                vol=vol,
                long_short_quantile=ls_q,
                min_assets_per_day=min_assets,
                max_weight_per_asset=max_w,
                use_vol_scaling=use_vol,
                rebalance_frequency_days=rebalance_days,
                sector_neutralize=sector_neutralize,
                max_sector_weight=max_sector_weight,
                transaction_cost_bps_per_side=txn_cost_bps,
                target_horizon_days=target_horizon_days,
                portfolio_mode=portfolio_mode,
                turnover_cap=turnover_cap,
                high_vol_exposure_scale=high_vol_exposure_scale,
                regime_exposure_scales=regime_exposure_scales,
                return_diagnostics=True,
            )
            if isinstance(trace, dict):
                ret_arr = np.asarray(trace.get("returns", np.asarray([], dtype=float)), dtype=float)
                ret_dates = trace.get("return_dates", [])
                for d_raw, ret in zip(ret_dates, ret_arr.tolist()):
                    if not np.isfinite(float(ret)):
                        continue
                    portfolio_series_rows.append(
                        {
                            "date": str(d_raw),
                            "return": float(ret),
                        }
                    )
                snap_rows = trace.get("rebalance_snapshots", [])
                if isinstance(snap_rows, list):
                    for snap in snap_rows:
                        if not isinstance(snap, dict):
                            continue
                        rebalance_snapshots.append(
                            {
                                "date": str(snap.get("date", "")),
                                "tickers": list(snap.get("tickers", [])) if isinstance(snap.get("tickers", []), list) else [],
                                "weights": dict(snap.get("weights", {})) if isinstance(snap.get("weights", {}), dict) else {},
                                "gross_exposure": float(snap.get("gross_exposure", 0.0) or 0.0),
                                "turnover": float(snap.get("turnover", 0.0) or 0.0),
                                "transaction_cost": float(snap.get("transaction_cost", 0.0) or 0.0),
                            }
                        )
            if callable(progress_callback):
                progress_callback(
                    event="window_done",
                    index=int(seen_windows),
                    total=int(target_windows),
                    model=str(getattr(model, "name", type(model).__name__)),
                    metrics=m,
                )

            win = ResearchWindowResult(
                train_start=str(split["train_start"]),
                train_end=str(split["train_end"]),
                test_start=str(split["test_start"]),
                test_end=str(split["test_end"]),
                n_train=int(train_mask.sum()),
                n_test=int(te.sum()),
                metrics=m,
            )
            windows.append(win)

            # Regime-sliced performance on test set.
            if regime_col in frame.columns:
                reg_series = frame.iloc[pred_indices][regime_col].astype(str).reset_index(drop=True)
                for regime in reg_series.unique():
                    mask = reg_series.eq(regime).to_numpy()
                    if mask.sum() < 10:
                        continue
                    rm = compute_window_metrics(
                        y_true=y_true[mask],
                        y_pred=y_pred[mask],
                        realized_returns=y_realized[mask],
                        dates=np.asarray(dates)[mask],
                        regimes=np.asarray(regimes)[mask] if regimes is not None else None,
                        tickers=np.asarray(tickers)[mask] if tickers is not None else None,
                        sectors=np.asarray(sectors)[mask] if sectors is not None else None,
                        vol=np.asarray(vol, dtype=float)[mask] if vol is not None else None,
                        long_short_quantile=ls_q,
                        min_assets_per_day=min_assets,
                        max_weight_per_asset=max_w,
                        use_vol_scaling=use_vol,
                        rebalance_frequency_days=rebalance_days,
                        sector_neutralize=sector_neutralize,
                        max_sector_weight=max_sector_weight,
                        transaction_cost_bps_per_side=txn_cost_bps,
                        target_horizon_days=target_horizon_days,
                        turnover_cap=turnover_cap,
                        high_vol_exposure_scale=high_vol_exposure_scale,
                        regime_exposure_scales=regime_exposure_scales,
                    )
                    regime_bucket.setdefault(regime, []).append(rm)

        agg = aggregate_metrics(metrics_raw)
        regime_metrics = {k: aggregate_metrics(v) for k, v in regime_bucket.items()}

        result = ModelRunResult(
            model_name=getattr(model, "name", type(model).__name__),
            params=getattr(model, "params", {}),
            windows=windows,
            aggregate_metrics=agg,
        )
        payload = asdict(result)
        payload["status"] = "ok" if windows else "insufficient_windows"
        payload["regime_metrics"] = regime_metrics
        if portfolio_series_rows:
            series_df = pd.DataFrame(portfolio_series_rows)
            series_df["date"] = pd.to_datetime(series_df["date"], errors="coerce")
            series_df["return"] = pd.to_numeric(series_df["return"], errors="coerce")
            series_df = series_df.dropna(subset=["date", "return"])
            if not series_df.empty:
                agg_series = (
                    series_df.groupby("date", as_index=False)["return"]
                    .mean()
                    .sort_values("date")
                    .reset_index(drop=True)
                )
                payload["portfolio_return_series"] = [
                    {
                        "date": pd.Timestamp(row["date"]).isoformat(),
                        "return": float(row["return"]),
                    }
                    for _, row in agg_series.iterrows()
                ]
            else:
                payload["portfolio_return_series"] = []
        else:
            payload["portfolio_return_series"] = []

        if rebalance_snapshots:
            # Deduplicate repeated snapshot dates from overlapping windows.
            by_date: Dict[str, Dict[str, Any]] = {}
            for snap in rebalance_snapshots:
                dt = str(snap.get("date", "")).strip()
                if not dt:
                    continue
                old = by_date.get(dt)
                if old is None or len(snap.get("tickers", [])) >= len(old.get("tickers", [])):
                    by_date[dt] = snap
            payload["rebalance_snapshots"] = [by_date[k] for k in sorted(by_date.keys())]
        else:
            payload["rebalance_snapshots"] = []
        payload["split_mode"] = "fixed_holdout" if fixed_split is not None else "rolling"
        payload["holdout_train_end_date"] = self.holdout_train_end_date or None
        payload["holdout_test_start_date"] = self.holdout_test_start_date or None
        payload["holdout_test_end_date"] = self.holdout_test_end_date or None
        payload["feature_importance"] = getattr(model, "feature_importance", lambda: {})()
        payload["label_embargo_periods"] = int(label_embargo_periods)
        logger.info(
            "TrainingPipeline complete model=%s status=%s windows=%s avg_sharpe=%.4f avg_dd=%.4f ic=%.4f",
            str(payload.get("model_name", "unknown")),
            str(payload.get("status", "unknown")),
            int(len(windows)),
            float(agg.get("avg_sharpe", 0.0)),
            float(agg.get("avg_max_drawdown", 0.0)),
            float(agg.get("ic_mean", 0.0)),
        )
        return payload
