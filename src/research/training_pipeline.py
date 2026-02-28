"""Leakage-safe walk-forward training pipeline."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional
import logging

import numpy as np
import pandas as pd

from .research_types import ModelRunResult, ResearchDataset, ResearchWindowResult
from .splits import rolling_time_splits
from .walk_forward_validator import aggregate_metrics, compute_window_metrics

logger = logging.getLogger(__name__)


class TrainingPipeline:
    """Run rolling walk-forward validation for one model."""

    def __init__(
        self,
        train_periods: int = 756,
        valid_periods: int = 126,
        test_periods: int = 126,
        step_periods: int = 63,
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
        self.max_windows = int(max_windows)
        self.start_window = max(0, int(start_window))
        self.portfolio_cfg = dict(portfolio_cfg or {})
        self.holdout_train_end_date = str(holdout_train_end_date).strip() if holdout_train_end_date else ""
        self.holdout_test_start_date = str(holdout_test_start_date).strip() if holdout_test_start_date else ""
        self.holdout_test_end_date = str(holdout_test_end_date).strip() if holdout_test_end_date else ""
        self.holdout_valid_periods = int(holdout_valid_periods) if holdout_valid_periods is not None else int(valid_periods)
        self.holdout_min_train_periods = max(20, int(holdout_min_train_periods))

    def _fixed_holdout_split(self, frame: pd.DataFrame, date_col: str = "date") -> Optional[Dict[str, np.ndarray]]:
        if (not self.holdout_train_end_date) and (not self.holdout_test_start_date):
            return None
        if frame.empty or date_col not in frame.columns:
            return None
        d = pd.to_datetime(frame[date_col], errors="coerce")
        ok = d.notna().to_numpy()
        if not ok.any():
            return None
        unique_dates = np.array(sorted(pd.Index(d[ok].unique())))
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

    def run(
        self,
        model: Any,
        dataset: ResearchDataset,
        regime_col: str = "regime",
        progress_callback: Optional[Any] = None,
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

        windows: List[ResearchWindowResult] = []
        metrics_raw: List[Dict[str, float]] = []
        regime_bucket: Dict[str, List[Dict[str, float]]] = {}
        ls_q = float(self.portfolio_cfg.get("long_short_quantile", 0.20))
        min_assets = int(self.portfolio_cfg.get("min_assets_per_day", 8))
        max_w = float(self.portfolio_cfg.get("max_weight_per_asset", 0.10))
        use_vol = bool(self.portfolio_cfg.get("use_vol_scaling", True))
        rebalance_days = int(self.portfolio_cfg.get("rebalance_frequency_days", 1))
        sector_neutralize = bool(self.portfolio_cfg.get("sector_neutralize", False))
        max_sector_weight = float(self.portfolio_cfg.get("max_sector_weight", 1.0))
        txn_cost_bps = float(self.portfolio_cfg.get("transaction_cost_bps_per_side", 0.0))

        fixed_split = self._fixed_holdout_split(frame, date_col="date")
        if fixed_split is not None:
            splits_iter = [fixed_split]
            target_windows = 1
        else:
            splits_iter = rolling_time_splits(
                frame,
                date_col="date",
                train_periods=self.train_periods,
                valid_periods=self.valid_periods,
                test_periods=self.test_periods,
                step_periods=self.step_periods,
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

            n = min(len(y_pred), len(y_true))
            y_pred = y_pred[:n]
            y_true = y_true[:n]
            pred_indices = pred_indices[:n]

            if n == 0:
                continue

            dates = frame.iloc[pred_indices]["date"].to_numpy()
            tickers = frame.iloc[pred_indices]["ticker"].to_numpy(dtype=str) if "ticker" in frame.columns else None
            sector_col = next((c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in frame.columns), None)
            sectors = frame.iloc[pred_indices][sector_col].to_numpy(dtype=str) if sector_col is not None else None
            vol = frame.iloc[pred_indices]["vol_20d"].to_numpy(dtype=float) if "vol_20d" in frame.columns else None
            m = compute_window_metrics(
                y_true=y_true,
                y_pred=y_pred,
                dates=dates,
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
            )
            metrics_raw.append(m)
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
                        dates=np.asarray(dates)[mask],
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
        if fixed_split is not None:
            payload["split_mode"] = "fixed_holdout"
            payload["holdout_train_end_date"] = self.holdout_train_end_date or None
            payload["holdout_test_start_date"] = self.holdout_test_start_date or None
            payload["holdout_test_end_date"] = self.holdout_test_end_date or None
        payload["feature_importance"] = getattr(model, "feature_importance", lambda: {})()
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
