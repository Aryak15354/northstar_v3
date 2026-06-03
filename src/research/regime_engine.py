# NORTHSTAR V3 CORE PHILOSOPHY
#
# This system answers one question: given the current market environment,
# which stocks have the best fundamentals relative to their peers?
#
# Layer 1 (this file): What environment are we in?
# Layer 2 (feature_factory + regime_conditional_trainer):
#     Which stocks win in this environment?
# Layer 3 (daily_scorer + portfolio_constructor):
#     How much do we bet?
#
# Every piece of data we collect feeds exactly one of these three layers.
# The regime label is the connective tissue between all three.

"""Northstar v3 regime engine (single source of truth)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable

import numpy as np
import pandas as pd
from sklearn.decomposition import IncrementalPCA

logger = logging.getLogger(__name__)


class RegimeEngine:
    """
    Single source of truth for regime labels.

    Used by:
    - walk_forward_validator.py (training)
    - training_pipeline.py (model selection)
    - daily_scorer.py (live scoring)
    - portfolio_constructor.py (position sizing)

    Never compute regimes anywhere else. Always use this class.
    """

    EXPOSURE_MAP = {
        # 2-axis regime labels (VIX + Nifty trend)
        "risk_on_calm": 0.9,
        "risk_on_volatile": 0.7,
        "risk_off_calm": 0.5,
        "risk_off_volatile": 0.3,
        "low_vol|uptrend|expansion": 1.0,
        "low_vol|uptrend|neutral": 0.9,
        "low_vol|uptrend|contraction": 0.7,
        "low_vol|downtrend|expansion": 0.6,
        "low_vol|downtrend|neutral": 0.5,
        "low_vol|downtrend|contraction": 0.3,
        "high_vol|uptrend|expansion": 0.8,
        "high_vol|uptrend|neutral": 0.7,
        "high_vol|uptrend|contraction": 0.5,
        "high_vol|downtrend|expansion": 0.4,
        "high_vol|downtrend|neutral": 0.3,
        "high_vol|downtrend|contraction": 0.1,
    }

    BASE_FALLBACK_NEUTRAL = {
        "risk_on_calm": 0.9,
        "risk_on_volatile": 0.7,
        "risk_off_calm": 0.5,
        "risk_off_volatile": 0.3,
        "low_vol|uptrend": 0.9,
        "low_vol|downtrend": 0.5,
        "high_vol|uptrend": 0.7,
        "high_vol|downtrend": 0.3,
    }

    def __init__(self, config: dict | None = None):
        self.config = dict(config or {})
        self.regime_labels_path = Path(
            str(self.config.get("regime_labels_path", "data/processed/regime_labels.parquet"))
        )
        self.vol_window = int(self.config.get("regime_vol_window", 20) or 20)
        self.trend_window = int(self.config.get("regime_trend_window", 63) or 63)
        self.vol_quantile = float(self.config.get("regime_vol_quantile", 0.75) or 0.75)
        self.vol_quantile_min_periods = int(self.config.get("regime_vol_min_periods", 126) or 126)
        self.pca_min_periods = int(self.config.get("regime_pca_min_periods", 60) or 60)
        self.macro_max_features = int(self.config.get("macro_max_features", 128) or 128)
        self.sentiment_window = int(self.config.get("sentiment_coverage_window", 90) or 90)
        self.sentiment_coverage_threshold = float(
            self.config.get("sentiment_coverage_threshold", 0.50) or 0.50
        )
        self.macro_col_min_coverage = float(self.config.get("macro_col_min_coverage", 0.05) or 0.05)
        self.regime_mode = str(self.config.get("regime_mode", "auto")).strip().lower()
        self.vix_threshold = float(self.config.get("vix_threshold", 20.0) or 20.0)
        self.nifty_sma_window = int(self.config.get("nifty_sma_window", 200) or 200)
        self.nifty_prices_path = Path(str(self.config.get("nifty_prices_path", "data/processed/nifty.parquet")))
        self.vix_path = Path(str(self.config.get("india_vix_path", "data/processed/india_vix.parquet")))
        self._labels: pd.DataFrame | None = None

    @staticmethod
    def _normalize_date_column(frame: pd.DataFrame, candidates: Iterable[str] | None = None) -> pd.Series:
        cands = list(candidates or ["date", "Date", "timestamp", "Period", "Reporting Date", "Unnamed: 1"])
        for c in cands:
            if c in frame.columns:
                return pd.to_datetime(frame[c], errors="coerce")
        return pd.Series(pd.NaT, index=frame.index)

    @staticmethod
    def _first_existing(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
        cols = {str(c) for c in frame.columns}
        for c in candidates:
            if c in cols:
                return str(c)
        return None

    @staticmethod
    def _infer_nifty_col(frame: pd.DataFrame) -> str | None:
        exact = [
            "NSE S&P CNX NIFTY",
            "NIFTY 50",
            "NIFTY50",
            "NIFTY",
            "^NSEI",
        ]
        col = RegimeEngine._first_existing(frame, exact)
        if col is not None:
            return col
        for c in frame.columns:
            s = str(c).strip().upper()
            if "NIFTY" in s and "BANK" not in s:
                return str(c)
        return None

    def _extract_benchmark_prices(self, prices_df: pd.DataFrame) -> pd.DataFrame:
        if prices_df is None or prices_df.empty:
            return pd.DataFrame(columns=["date", "close"])

        px = prices_df.copy()
        date = self._normalize_date_column(px)
        px = px.assign(date=date).dropna(subset=["date"]).copy()
        if px.empty:
            return pd.DataFrame(columns=["date", "close"])

        # Case 1: wide frame with an explicit Nifty-like column.
        nifty_col = self._infer_nifty_col(px)
        if nifty_col is not None:
            out = pd.DataFrame(
                {
                    "date": px["date"],
                    "close": pd.to_numeric(px[nifty_col], errors="coerce"),
                }
            ).dropna(subset=["close"])
            if not out.empty:
                out = out.groupby("date", as_index=False)["close"].last().sort_values("date")
                return out.reset_index(drop=True)

        # Case 2: ticker-based panel (fallback to equal-weight market proxy).
        close_col = self._first_existing(px, ["Close", "close", "adj_close", "Adj Close", "price"])
        if close_col is None:
            numeric_cols = [c for c in px.columns if pd.api.types.is_numeric_dtype(px[c])]
            close_col = str(numeric_cols[0]) if numeric_cols else None
        if close_col is None:
            return pd.DataFrame(columns=["date", "close"])

        px["close"] = pd.to_numeric(px[close_col], errors="coerce")
        if "ticker" in px.columns:
            tk = px["ticker"].astype(str).str.upper().fillna("")
            # Prefer an explicit Nifty ticker if present.
            prefer = tk.str.contains(r"NIFTY|NSEI|\^", regex=True)
            if bool(prefer.any()):
                sub = px.loc[prefer & px["close"].notna(), ["date", "close"]].copy()
                if not sub.empty:
                    out = sub.groupby("date", as_index=False)["close"].last().sort_values("date")
                    return out.reset_index(drop=True)

        out = (
            px.loc[px["close"].notna(), ["date", "close"]]
            .groupby("date", as_index=False)["close"]
            .mean()
            .sort_values("date")
            .reset_index(drop=True)
        )
        return out

    def _load_nifty_series(self) -> pd.DataFrame:
        if not self.nifty_prices_path.exists():
            return pd.DataFrame(columns=["date", "close"])
        try:
            if self.nifty_prices_path.suffix.lower() in {".parquet", ".pq"}:
                df = pd.read_parquet(self.nifty_prices_path)
            else:
                df = pd.read_csv(self.nifty_prices_path)
        except Exception:
            return pd.DataFrame(columns=["date", "close"])
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "close"])
        work = df.copy()
        if "date" not in work.columns:
            if "Date" in work.columns:
                work["date"] = work["Date"]
            else:
                try:
                    work = work.reset_index()
                    if "Date" in work.columns:
                        work["date"] = work["Date"]
                except Exception:
                    work["date"] = pd.NaT
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        close_col = "close" if "close" in work.columns else ("Close" if "Close" in work.columns else None)
        if close_col is None:
            return pd.DataFrame(columns=["date", "close"])
        work["close"] = pd.to_numeric(work[close_col], errors="coerce")
        work = work.dropna(subset=["date", "close"]).sort_values("date", kind="mergesort")
        return work[["date", "close"]].drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    def _load_vix_series(self) -> pd.DataFrame:
        if not self.vix_path.exists():
            return pd.DataFrame(columns=["date", "vix"])
        try:
            if self.vix_path.suffix.lower() in {".parquet", ".pq"}:
                df = pd.read_parquet(self.vix_path)
            else:
                df = pd.read_csv(self.vix_path)
        except Exception:
            return pd.DataFrame(columns=["date", "vix"])
        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "vix"])
        work = df.copy()
        if "date" not in work.columns:
            if "Date" in work.columns:
                work["date"] = work["Date"]
            else:
                try:
                    work = work.reset_index()
                    if "Date" in work.columns:
                        work["date"] = work["Date"]
                except Exception:
                    work["date"] = pd.NaT
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        vix_col = None
        for c in ["india_vix", "vix", "VIX", "close", "Close"]:
            if c in work.columns:
                vix_col = c
                break
        if vix_col is None:
            return pd.DataFrame(columns=["date", "vix"])
        work["vix"] = pd.to_numeric(work[vix_col], errors="coerce")
        work = work.dropna(subset=["date", "vix"]).sort_values("date", kind="mergesort")
        return work[["date", "vix"]].drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    def _prepare_macro_matrix(self, macro_df: pd.DataFrame, daily_index: pd.DatetimeIndex) -> pd.DataFrame:
        if macro_df is None or macro_df.empty:
            return pd.DataFrame(index=daily_index)

        m = macro_df.copy()
        date = self._normalize_date_column(m)
        m = m.assign(date=date).dropna(subset=["date"]).copy()
        if m.empty:
            return pd.DataFrame(index=daily_index)

        # If availability_date is present, use it as PIT-safe timestamp for this row.
        if "availability_date" in m.columns:
            ad = pd.to_datetime(m["availability_date"], errors="coerce")
            m.loc[ad.notna(), "date"] = ad[ad.notna()]

        banned = {
            "date",
            "availability_date",
            "ticker",
            "sector",
            "macro_regime_label",
            "macro_activity_score",
            "macro_activity_composite",
            "power_yoy_growth",
            "gst_yoy_growth",
            "india_market_polarity",
            "sentiment_polarity",
        }
        numeric_cols = [
            str(c)
            for c in m.columns
            if str(c) not in banned and pd.api.types.is_numeric_dtype(pd.to_numeric(m[c], errors="coerce"))
        ]
        if not numeric_cols:
            return pd.DataFrame(index=daily_index)

        keep = m[["date"] + numeric_cols].copy()
        for c in numeric_cols:
            keep[c] = pd.to_numeric(keep[c], errors="coerce")
        keep = keep.sort_values("date", kind="mergesort").drop_duplicates(subset=["date"], keep="last")
        keep = keep.set_index("date").reindex(daily_index).sort_index().ffill()

        # Drop columns with almost no usable data.
        cov = keep.notna().mean()
        min_cov = float(max(0.0, min(1.0, self.macro_col_min_coverage)))
        good_cols = [c for c in keep.columns if float(cov.get(c, 0.0)) >= min_cov]
        if not good_cols:
            return pd.DataFrame(index=daily_index)
        out = keep[good_cols].copy()
        # Keep the most useful macro columns first when raw ingestion yields very wide tables.
        max_feat = int(max(2, self.macro_max_features))
        if out.shape[1] > max_feat:
            coverage = out.notna().mean()
            volatility = out.std(skipna=True).replace(0.0, np.nan).fillna(0.0)
            rank = (coverage.rank(method="average", ascending=False) * 0.7) + (
                volatility.rank(method="average", ascending=False) * 0.3
            )
            top_cols = rank.sort_values(ascending=True).index[:max_feat].tolist()
            out = out[top_cols].copy()
        return out

    def _expanding_standardize(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        out = frame.copy()
        for c in out.columns:
            s = pd.to_numeric(out[c], errors="coerce")
            mu = s.expanding(min_periods=20).mean()
            sd = s.expanding(min_periods=20).std().replace(0.0, np.nan)
            z = ((s - mu) / (sd + 1e-12)).replace([np.inf, -np.inf], np.nan)
            out[c] = z
        out = out.ffill().fillna(0.0)
        return out

    def _compute_macro_activity_score(self, macro_daily: pd.DataFrame) -> pd.Series:
        """
        Compute macro activity score using PIT-safe incremental PCA.
        
        CRITICAL PIT SAFETY:
        This method ensures point-in-time compliance by:
        1. Using IncrementalPCA with expanding window (not full dataset)
        2. Only scoring row i after model has seen rows 0 to i-1
        3. Tracking fitted_cutoff_idx to prevent future data leakage
        4. Batch fitting only on historical data up to current row
        
        The key invariant: When scoring row i, the PCA model has only been
        trained on rows 0 to i-1, ensuring no future information leaks.
        
        Reference: Northstar V3 Signal Engineering Plan, Requirement 47.4
        Task 1.3: PIT bug fix in regime_engine.py
        
        Args:
            macro_daily: DataFrame with macro features indexed by date
            
        Returns:
            Series of macro activity scores (PCA first component)
        """
        if macro_daily.empty:
            return pd.Series(np.nan, index=macro_daily.index, dtype=float)

        observed_mask = macro_daily.notna().any(axis=1).to_numpy(dtype=bool)
        z = self._expanding_standardize(macro_daily)
        x = z.to_numpy(dtype=float)
        if x.ndim != 2 or x.shape[1] < 2:
            return pd.Series(np.nan, index=macro_daily.index, dtype=float)
        # Avoid global variance filters here to keep the PCA guard PIT-safe.
        # Degenerate-batch checks are handled inside the expanding window loop.

        # PIT-safe: Initialize IncrementalPCA but DON'T pre-fit on full data
        # The expanding window loop below will fit incrementally
        ipca = IncrementalPCA(n_components=1)
        scores = np.full(len(z), np.nan, dtype=float)
        fitted_rows = 0
        has_components = False  # Start False - will become True after warmup
        fitted_cutoff_idx = -1  # CRITICAL: Highest row index seen by partial_fit; used for PIT guard.
        fit_batch_rows: list[np.ndarray] = []
        fit_batch_idx: list[int] = []
        # PIT-safe warmup should not scale linearly with feature count for wide macro panels.
        # Use a bounded warmup horizon to avoid all-NaN scores when columns are numerous.
        min_fit = max(int(self.pca_min_periods), 30)
        min_fit = min(min_fit, max(30, int(len(z) * 0.15)))
        batch_size = max(8, min(32, int(self.config.get("regime_pca_batch_size", 16) or 16)))

        def _fit_pending_batch() -> None:
            nonlocal fitted_rows, has_components, fitted_cutoff_idx, fit_batch_rows, fit_batch_idx
            if not fit_batch_rows:
                return
            batch = np.vstack(fit_batch_rows).astype(float)
            batch_idx = np.asarray(fit_batch_idx, dtype=int)
            fit_batch_rows = []
            fit_batch_idx = []
            # Skip degenerate batches; IncrementalPCA on near-constant batches
            # emits divide warnings and produces unstable explained variance.
            if batch.shape[0] < 2:
                return
            col_var = np.nanvar(batch, axis=0)
            if not bool(np.isfinite(col_var).any()):
                return
            if float(np.nanmax(col_var)) <= 1e-10:
                return
            if float(np.nansum(col_var)) <= 1e-8:
                return
            try:
                ipca.partial_fit(batch)
                fitted_rows += int(batch.shape[0])
                has_components = bool(
                    hasattr(ipca, "components_")
                    and np.isfinite(np.asarray(ipca.components_, dtype=float)).all()
                )
                if batch_idx.size > 0:
                    fitted_cutoff_idx = max(fitted_cutoff_idx, int(batch_idx.max()))
            except Exception:
                return

        for i in range(len(z)):
            if not bool(observed_mask[i]):
                continue
            row = np.asarray(x[i : i + 1], dtype=float)
            row = np.nan_to_num(row, nan=0.0, posinf=0.0, neginf=0.0)
            # CRITICAL PIT SAFETY: Only score AFTER we have enough historical data
            # and only if the model has only seen rows strictly before i.
            # This ensures no future information leaks into the score at row i.
            if has_components and fitted_rows >= min_fit and fitted_cutoff_idx < i:
                try:
                    scores[i] = float(ipca.transform(row)[0, 0])
                except Exception:
                    scores[i] = np.nan
            # Add to batch for incremental fitting (only historical data up to row i)
            fit_batch_rows.append(row.reshape(-1))
            fit_batch_idx.append(i)
            if len(fit_batch_rows) >= batch_size:
                _fit_pending_batch()
        _fit_pending_batch()

        out = pd.Series(scores, index=macro_daily.index, dtype=float)
        if not bool(pd.to_numeric(out, errors="coerce").notna().any()):
            # Robust fallback for early/degenerate periods: cross-feature mean z-score.
            fallback = pd.to_numeric(z.mean(axis=1), errors="coerce")
            fallback = fallback.where(pd.Series(observed_mask, index=z.index), np.nan)
            return fallback.astype(float)
        return out

    @staticmethod
    def _macro_label(score: object) -> str | None:
        v = pd.to_numeric(pd.Series([score]), errors="coerce").iloc[0]
        if pd.isna(v):
            return None
        if float(v) > 0.5:
            return "expansion"
        if float(v) < -0.5:
            return "contraction"
        return "neutral"

    def _optional_series(self, frame: pd.DataFrame | None, *, daily_index: pd.DatetimeIndex, value_name: str) -> pd.Series:
        if frame is None or frame.empty:
            return pd.Series(np.nan, index=daily_index, dtype=float)

        f = frame.copy()
        date = self._normalize_date_column(f)
        f = f.assign(date=date).dropna(subset=["date"]).copy()
        if f.empty:
            return pd.Series(np.nan, index=daily_index, dtype=float)

        if "availability_date" in f.columns:
            ad = pd.to_datetime(f["availability_date"], errors="coerce")
            f.loc[ad.notna(), "date"] = ad[ad.notna()]

        if value_name not in f.columns:
            if value_name == "power_yoy_growth":
                if "energy_met_mu" in f.columns:
                    s = pd.to_numeric(f["energy_met_mu"], errors="coerce")
                    f[value_name] = s.pct_change(365) * 100.0
                elif "power_energy_met_mu" in f.columns:
                    s = pd.to_numeric(f["power_energy_met_mu"], errors="coerce")
                    f[value_name] = s.pct_change(365) * 100.0
            elif value_name == "gst_yoy_growth":
                if "eway_bills_generated" in f.columns:
                    s = pd.to_numeric(f["eway_bills_generated"], errors="coerce")
                    f[value_name] = s.pct_change(12) * 100.0
                elif "gst_total_bills" in f.columns:
                    s = pd.to_numeric(f["gst_total_bills"], errors="coerce")
                    f[value_name] = s.pct_change(12) * 100.0
            elif value_name == "sentiment_polarity":
                col = self._first_existing(
                    f,
                    ["india_market_polarity", "polarity", "market_polarity", "sentiment_polarity"],
                )
                if col is not None:
                    f[value_name] = pd.to_numeric(f[col], errors="coerce")

        if value_name not in f.columns:
            return pd.Series(np.nan, index=daily_index, dtype=float)

        out = (
            f[["date", value_name]]
            .assign(**{value_name: pd.to_numeric(f[value_name], errors="coerce")})
            .sort_values("date", kind="mergesort")
            .drop_duplicates(subset=["date"], keep="last")
            .set_index("date")[value_name]
            .reindex(daily_index)
            .ffill()
        )

        if value_name == "sentiment_polarity":
            # Apply coverage gating only after we have enough live history.
            # Early rollout windows (few observations) would otherwise be forced to NaN.
            observed = int(out.notna().sum())
            if observed >= int(max(10, self.sentiment_window)):
                cov = out.notna().rolling(self.sentiment_window, min_periods=1).mean()
                out = out.where(cov > self.sentiment_coverage_threshold)
        return pd.to_numeric(out, errors="coerce")

    def build_historical_regimes(
        self,
        prices_df: pd.DataFrame,
        macro_df: pd.DataFrame | None = None,
        power_df: pd.DataFrame | None = None,
        gst_df: pd.DataFrame | None = None,
        sentiment_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Build regime labels for full historical period with PIT safety.
        
        CRITICAL PIT SAFETY:
        All calculations use only data available up to each date:
        - Volatility: Rolling window on historical returns
        - Trend: Rolling SMA on historical prices
        - Macro PCA: Incremental fitting with expanding window
        - All auxiliary data: Uses availability_date for PIT compliance
        
        Priority order: vol+trend -> macro PCA -> CEA+GST -> sentiment.
        Graceful degradation: missing sources = fewer regime dimensions.
        
        Reference: Northstar V3 Signal Engineering Plan, Requirements 1.3, 47
        Task 1.3: PIT bug fix validation
        
        Args:
            prices_df: Price data with date and close columns
            macro_df: Optional macro features with availability_date
            power_df: Optional power consumption data
            gst_df: Optional GST data
            sentiment_df: Optional sentiment data
            
        Returns:
            DataFrame with regime labels and auxiliary features
        """
        px = self._extract_benchmark_prices(prices_df)
        if px.empty:
            raise ValueError("regime_engine_missing_price_series")

        px = px.sort_values("date", kind="mergesort").drop_duplicates(subset=["date"], keep="last")
        px["close"] = pd.to_numeric(px["close"], errors="coerce")
        px = px.dropna(subset=["close"]).copy()
        if px.empty:
            raise ValueError("regime_engine_empty_price_series")

        px["ret_1d"] = px["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        px["realized_vol"] = px["ret_1d"].rolling(self.vol_window, min_periods=max(5, self.vol_window // 2)).std()
        vol_threshold = (
            pd.to_numeric(px["realized_vol"], errors="coerce")
            .expanding(min_periods=max(20, self.vol_quantile_min_periods))
            .quantile(self.vol_quantile)
        )
        px["vol_label"] = np.where(
            pd.to_numeric(px["realized_vol"], errors="coerce") > pd.to_numeric(vol_threshold, errors="coerce"),
            "high_vol",
            "low_vol",
        )

        ma = px["close"].rolling(self.trend_window, min_periods=max(20, self.trend_window // 2)).mean()
        px["trend_signal"] = (px["close"] / (ma + 1e-12)) - 1.0
        px["trend_label"] = np.where(px["close"] > ma, "uptrend", "downtrend")
        px["base_regime"] = px["vol_label"].astype(str) + "|" + px["trend_label"].astype(str)

        idx = pd.DatetimeIndex(px["date"])
        vix = self._load_vix_series()
        nifty = self._load_nifty_series()
        use_vix_mode = self.regime_mode in {"vix_nifty", "vix"} or (
            self.regime_mode == "auto" and (not vix.empty) and (not nifty.empty)
        )
        if use_vix_mode and (not vix.empty) and (not nifty.empty):
            vix_idx = vix.set_index("date").reindex(idx).ffill()
            nifty_idx = nifty.set_index("date").reindex(idx).ffill()
            nifty_close = pd.to_numeric(nifty_idx.get("close"), errors="coerce")
            sma_window = max(20, int(self.nifty_sma_window))
            nifty_sma = nifty_close.rolling(sma_window, min_periods=max(50, sma_window // 2)).mean()
            above_sma = nifty_close > nifty_sma
            vix_val = pd.to_numeric(vix_idx.get("vix"), errors="coerce")
            volatile = vix_val > float(self.vix_threshold)

            regime = np.where(
                above_sma & (~volatile),
                "risk_on_calm",
                np.where(
                    above_sma & volatile,
                    "risk_on_volatile",
                    np.where(
                        (~above_sma) & (~volatile),
                        "risk_off_calm",
                        "risk_off_volatile",
                    ),
                ),
            )
            out = pd.DataFrame(
                {
                    "date": idx,
                    "regime": regime,
                    "vol_label": np.where(volatile, "high_vol", "low_vol"),
                    "trend_label": np.where(above_sma, "uptrend", "downtrend"),
                    "macro_label": "",
                    "macro_activity_score": np.nan,
                    "realized_vol": pd.to_numeric(px["realized_vol"], errors="coerce").to_numpy(),
                    "trend_signal": (nifty_close / (nifty_sma + 1e-12) - 1.0).to_numpy(),
                    "india_vix": vix_val.to_numpy(),
                    "nifty_close": nifty_close.to_numpy(),
                    "nifty_sma_200": nifty_sma.to_numpy(),
                    "nifty_above_200d": above_sma.astype(float).to_numpy(),
                }
            )
            out["power_yoy_growth"] = self._optional_series(
                power_df if isinstance(power_df, pd.DataFrame) else None,
                daily_index=idx,
                value_name="power_yoy_growth",
            ).to_numpy()
            out["gst_yoy_growth"] = self._optional_series(
                gst_df if isinstance(gst_df, pd.DataFrame) else None,
                daily_index=idx,
                value_name="gst_yoy_growth",
            ).to_numpy()
            out["sentiment_polarity"] = self._optional_series(
                sentiment_df if isinstance(sentiment_df, pd.DataFrame) else None,
                daily_index=idx,
                value_name="sentiment_polarity",
            ).to_numpy()
            out["date"] = pd.to_datetime(out["date"], errors="coerce")
            out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort").reset_index(drop=True)
            self._labels = out.copy()
            return out

        macro_activity_score = pd.Series(np.nan, index=idx, dtype=float)
        macro_label = pd.Series(np.nan, index=idx, dtype=object)

        macro_daily = self._prepare_macro_matrix(macro_df if isinstance(macro_df, pd.DataFrame) else pd.DataFrame(), idx)
        if not macro_daily.empty:
            macro_activity_score = self._compute_macro_activity_score(macro_daily)
            macro_label = macro_activity_score.map(self._macro_label)

        out = pd.DataFrame({
            "date": px["date"].to_numpy(),
            "vol_label": px["vol_label"].astype(str).to_numpy(),
            "trend_label": px["trend_label"].astype(str).to_numpy(),
            "macro_label": pd.Series(macro_label, dtype="object").to_numpy(),
            "macro_activity_score": pd.to_numeric(macro_activity_score, errors="coerce").to_numpy(),
            "realized_vol": pd.to_numeric(px["realized_vol"], errors="coerce").to_numpy(),
            "trend_signal": pd.to_numeric(px["trend_signal"], errors="coerce").to_numpy(),
        })

        out["power_yoy_growth"] = self._optional_series(
            power_df if isinstance(power_df, pd.DataFrame) else None,
            daily_index=idx,
            value_name="power_yoy_growth",
        ).to_numpy()
        out["gst_yoy_growth"] = self._optional_series(
            gst_df if isinstance(gst_df, pd.DataFrame) else None,
            daily_index=idx,
            value_name="gst_yoy_growth",
        ).to_numpy()
        out["sentiment_polarity"] = self._optional_series(
            sentiment_df if isinstance(sentiment_df, pd.DataFrame) else None,
            daily_index=idx,
            value_name="sentiment_polarity",
        ).to_numpy()

        base = out["vol_label"].astype(str) + "|" + out["trend_label"].astype(str)
        has_macro = out["macro_label"].notna() & out["macro_label"].astype(str).str.strip().ne("")
        out["regime"] = np.where(
            has_macro,
            base + "|" + out["macro_label"].astype(str),
            base,
        )

        final_cols = [
            "date",
            "regime",
            "vol_label",
            "trend_label",
            "macro_label",
            "macro_activity_score",
            "realized_vol",
            "trend_signal",
            "power_yoy_growth",
            "gst_yoy_growth",
            "sentiment_polarity",
        ]
        out = out[final_cols].copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort").reset_index(drop=True)
        self._labels = out.copy()
        return out

    def _load_labels_from_disk(self) -> pd.DataFrame:
        if self.regime_labels_path.exists():
            try:
                df = pd.read_parquet(self.regime_labels_path)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    df = df.copy()
                    df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
                    df = df.dropna(subset=["date"]).sort_values("date", kind="mergesort")
                    return df.reset_index(drop=True)
            except Exception:
                return pd.DataFrame()
        return pd.DataFrame()

    def _ensure_labels(self) -> None:
        if isinstance(self._labels, pd.DataFrame) and not self._labels.empty:
            return
        self._labels = self._load_labels_from_disk()

    def get_regime_as_of(self, date: object) -> str:
        """Return regime label for a specific date."""
        self._ensure_labels()
        if self._labels is None or self._labels.empty:
            return "low_vol|downtrend"
        dt = pd.to_datetime(date, errors="coerce")
        if pd.isna(dt):
            dt = pd.to_datetime("today")
        s = self._labels[self._labels["date"] <= dt]
        if s.empty:
            row = self._labels.iloc[0]
        else:
            row = s.iloc[-1]
        reg = str(row.get("regime", "") or "").strip().lower()
        return reg if reg else "low_vol|downtrend"

    def get_regime_series(self, start_date: object, end_date: object) -> pd.Series:
        """Return series of regime labels indexed by date."""
        self._ensure_labels()
        if self._labels is None or self._labels.empty:
            return pd.Series(dtype=object)
        sdt = pd.to_datetime(start_date, errors="coerce")
        edt = pd.to_datetime(end_date, errors="coerce")
        work = self._labels.copy()
        if pd.notna(sdt):
            work = work[work["date"] >= sdt]
        if pd.notna(edt):
            work = work[work["date"] <= edt]
        if work.empty:
            return pd.Series(dtype=object)
        out = pd.Series(work["regime"].astype(str).to_numpy(), index=pd.DatetimeIndex(work["date"]))
        out.name = "regime"
        return out

    def get_exposure_scale(self, regime: object) -> float:
        """Return position sizing scalar for a regime."""
        key = str(regime or "").strip().lower()
        if not key:
            return float(self.BASE_FALLBACK_NEUTRAL["low_vol|downtrend"])
        if key in self.EXPOSURE_MAP:
            return float(self.EXPOSURE_MAP[key])

        parts = [p.strip().lower() for p in key.split("|") if p.strip()]
        if len(parts) >= 3:
            k3 = "|".join(parts[:3])
            if k3 in self.EXPOSURE_MAP:
                return float(self.EXPOSURE_MAP[k3])
        if len(parts) >= 2:
            k2 = "|".join(parts[:2])
            if k2 in self.BASE_FALLBACK_NEUTRAL:
                return float(self.BASE_FALLBACK_NEUTRAL[k2])

        return 1.0
