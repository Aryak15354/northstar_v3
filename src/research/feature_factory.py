"""Historical feature factory for research mode."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from src.core.panel_math import (
    coalesce_rowwise,
    group_rank_centered as _shared_group_rank_centered,
    group_zscore as _shared_group_zscore,
    normalize_ticker as _shared_normalize_ticker,
    sector_string,
)
from src.factors.gap9_academic_factors import Gap9AcademicFactors
from src.nlp.features.event_features import add_event_features
from src.nlp.features.narrative_features import add_narrative_features
from src.nlp.features.sentiment_features import add_sentiment_features

logger = logging.getLogger(__name__)


def _safe_ratio_divide(
    numerator: pd.Series,
    denominator: pd.Series,
    *,
    min_abs_denominator: float = 1e-6,
) -> pd.Series:
    """Divide with an epsilon floor on the denominator (never a bare divide).

    An exact-zero guard alone still lets a near-zero denominator blow the ratio
    up to an absurd magnitude; the floor bounds it at source instead of relying
    on a downstream clip.
    """
    den = pd.to_numeric(denominator, errors="coerce").astype(float)
    num = pd.to_numeric(numerator, errors="coerce").astype(float)
    safe_den = den.where(den.abs() >= float(min_abs_denominator))
    return (num / safe_den).replace([np.inf, -np.inf], np.nan)


DEFAULT_COMPANY_SENTIMENT_REDUCED = [
    "sent_northstar_score",
    "sentiment_polarity",
    "sentiment_conviction_x_polarity",
    "sentiment_surprise",
    "sentiment_polarity_momentum",
    "sent_cohesive_alpha_score",
    "narrative_strength",
    "topic_drift",
    "sentiment_uncertainty",
    "agreement_score",
    "sent_trend_score",
    "sentiment_volume_spike",
    "sent_event_shock_factor",
    "sent_momentum_score",
    "sentiment_shock",
]

DEFAULT_MARKET_SENTIMENT_REDUCED = [
    "macro_sentiment_polarity",
    "macro_sentiment_conviction",
    "macro_sentiment_uncertainty",
    "macro_sentiment_event_shock",
    "macro_sentiment_regime_headwind",
    "macro_sentiment_risk_multiplier",
    "macro_sentiment_news_signal",
    "macro_sentiment_delta_polarity",
    "macro_sentiment_micro_shift",
    "macro_sentiment_change_velocity",
    "mkt_sent_polarity",
    "mkt_sent_conviction",
    "mkt_sent_narrative_cohesion",
    "mkt_sent_delta_polarity",
    "mkt_sent_uncertainty",
]


class FeatureFactory:
    """Builds cross-sectional + time-series features from historical artifacts."""

    def __init__(
        self,
        target_horizon_days: int = 5,
        *,
        enable_pit_fundamentals: bool = True,
        pit_fundamental_lag_days: int = 60,
        pit_announcement_plus_days: int = 1,
        use_announcement_dates: bool = True,
        use_et500_features: bool = False,
        use_screener_features: bool = False,
        screener_fundamentals_path: str = "data/canonical/fundamentals/fundamentals_annual_panel.parquet",
        screener_shareholding_path: str = "data/canonical/fundamentals/shareholding_quarterly.parquet",
        use_screener_extended_features: bool = False,  # backward-compat alias
        config: Optional[dict[str, Any]] = None,
    ):
        _init_started = time.monotonic()
        self.config = dict(config or {})
        self.target_horizon_days = int(max(1, target_horizon_days))
        self.enable_pit_fundamentals = bool(enable_pit_fundamentals)
        self.pit_fundamental_lag_days = int(max(0, pit_fundamental_lag_days))
        self.pit_announcement_plus_days = int(max(0, pit_announcement_plus_days))
        self.pit_financials_plus_days = int(
            max(0, self.config.get("pit_financials_plus_days", self.pit_announcement_plus_days))
        )
        self.pit_earnings_announcement_plus_days = int(
            max(0, self.config.get("pit_earnings_announcement_plus_days", self.pit_announcement_plus_days))
        )
        self.use_announcement_dates = bool(use_announcement_dates)
        self.use_et500_features = bool(use_et500_features)
        self.use_screener_features = bool(
            self.config.get("use_screener_features", use_screener_features)
            or self.config.get("use_screener_extended_features", use_screener_extended_features)
        )
        self.screener_fundamentals_path = str(
            self.config.get(
                "screener_fundamentals_path",
                self.config.get("screener_annual_path", screener_fundamentals_path),
            )
        )
        self.screener_quarterly_path = str(
            self.config.get(
                "screener_quarterly_path",
                "data/canonical/fundamentals/fundamentals_quarterly_panel.parquet",
            )
        )
        self.screener_shareholding_path = str(
            self.config.get(
                "screener_shareholding_path",
                screener_shareholding_path,
            )
        )
        self.use_alternative_features = bool(self.config.get("use_alternative_features", False))
        self.alternative_data_path = str(self.config.get("alternative_data_path", "data/canonical/alternative"))
        self.alternative_features_available = self.config.get("alternative_features_available", {}) or {}
        self.use_sentiment_features = bool(self.config.get("use_sentiment_features", False))
        self.use_sentiment_regime = bool(self.config.get("use_sentiment_regime", False))
        self.sentiment_feature_mode = str(self.config.get("sentiment_feature_mode", "full")).strip().lower()
        if self.sentiment_feature_mode not in {"full", "reduced"}:
            self.sentiment_feature_mode = "full"
        self.sentiment_path = str(
            self.config.get("sentiment_path", "data/canonical/sentiment/company_sentiment_daily.parquet")
        )
        self.market_sentiment_path = str(
            self.config.get("market_sentiment_path", "data/canonical/sentiment/market_sentiment_daily.parquet")
        )
        self.use_macro_features = bool(self.config.get("use_macro_features", False))
        feature_groups_cfg = self.config.get("feature_groups", {}) or {}
        gap9_cfg = feature_groups_cfg.get("gap9_academic_factors", {}) or {}
        self.use_gap9_academic_factors = bool(
            self.config.get("use_gap9_academic_factors", gap9_cfg.get("enabled", False))
        )
        self._gap9_academic_block = Gap9AcademicFactors(
            factor_lookback_days=int(gap9_cfg.get("factor_lookback_days", 252) or 252),
            beta_lookback_days=int(gap9_cfg.get("beta_lookback_days", 252) or 252),
            beta_min_observations=int(gap9_cfg.get("beta_min_observations", 120) or 120),
            amihud_lookback_days=int(gap9_cfg.get("amihud_lookback_days", 20) or 20),
            amihud_min_observations=int(gap9_cfg.get("amihud_min_observations", 10) or 10),
            max_lookback_days=int(gap9_cfg.get("max_lookback_days", 20) or 20),
            max_min_observations=int(gap9_cfg.get("max_min_observations", 10) or 10),
            min_piotroski_signals=int(gap9_cfg.get("min_piotroski_signals", 6) or 6),
        )
        self.macro_features_path = str(
            self.config.get("macro_features_path", "data/canonical/macro/macro_regime_features.parquet")
        )
        self.rbi_macro_weekly_path = str(
            self.config.get("rbi_macro_weekly_path", "data/processed/macro/rbi_macro_weekly.parquet")
        )
        self.credit_quarterly_path = str(
            self.config.get("credit_quarterly_path", "data/processed/sector_financials/credit_quarterly.parquet")
        )
        self.announcement_dates_path = str(
            self.config.get(
                "announcement_dates_path",
                self.config.get("earnings_dates_path", ""),
            )
        )
        self.require_announcement_dates_for_sue = bool(
            self.config.get("require_announcement_dates_for_sue", False)
        )
        self.announcement_dates_min_coverage = float(
            self.config.get("announcement_dates_min_coverage", 0.60) or 0.60
        )
        self._announcement_dates: Optional[pd.DataFrame] = None

        self._screener_annual: Optional[pd.DataFrame] = None
        self._screener_shareholding: Optional[pd.DataFrame] = None
        if bool(self.use_screener_features):
            self._screener_annual = self._load_screener_annual()
            self._screener_shareholding = self._load_screener_shareholding()

        valuation_cfg = self.config.get("valuation", {}) or {}
        self.use_valuation_features = bool(valuation_cfg.get("features_enabled", True))
        self._valuation_feature_columns_mode = str(
            valuation_cfg.get("feature_columns", "zscore_only")
        ).strip().lower()
        self._valuation_block = None
        if self.use_valuation_features:
            try:
                from src.valuation.valuation_feature_block import ValuationFeatureBlock

                self._valuation_block = ValuationFeatureBlock(self.config)
                logger.info("Valuation feature block initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize valuation feature block: {e}")
                self._valuation_block = None
        
        # Gap 9: Academic Factor Library
        factors_cfg = self.config.get('factors', {}) or {}
        self.use_academic_factors = bool(
            self.config.get('use_academic_factors', False) or factors_cfg.get('enabled', False)
        )
        self._factor_feature_columns_mode = str(factors_cfg.get('feature_columns', 'zscore_only')).strip().lower()
        self._factor_registry = None
        if self.use_academic_factors:
            try:
                from src.factors.factor_registry import FactorRegistry
                from src.ingestion import IngestionRegistry
                self._factor_registry = FactorRegistry(IngestionRegistry(self.config), self.config)
                logger.info("Academic Factor Library initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Academic Factor Library: {e}")
                self._factor_registry = None

        # G.4: surface construction cost. A fresh FeatureFactory (screener loads,
        # Gap9/valuation/registry setup) is built per DatasetManager, which is
        # per chunk in the chunked build — this makes the repeated cost visible.
        logger.debug("FeatureFactory initialized in %.2fs", time.monotonic() - _init_started)

    @staticmethod
    def _as_date(df: pd.DataFrame, preferred: Iterable[str]) -> pd.Series:
        for c in preferred:
            if c in df.columns:
                out = pd.to_datetime(df[c], errors="coerce")
                try:
                    if getattr(out.dt, "tz", None) is not None:
                        out = out.dt.tz_localize(None)
                except Exception:
                    pass
                try:
                    out = out.astype("datetime64[ns]")
                except Exception:
                    out = pd.to_datetime(out, errors="coerce")
                return out
        return pd.Series(pd.NaT, index=df.index)

    @staticmethod
    def _merge_asof_by_ticker(
        left: pd.DataFrame,
        right: pd.DataFrame,
        *,
        left_on: str = "date",
        right_on: str = "date",
    ) -> pd.DataFrame:
        ldf = left.copy()
        rdf = right.copy()
        for frame in (ldf, rdf):
            if "ticker" in frame.columns:
                continue
            for candidate in ["ticker_x", "Ticker", "Ticker_x", "symbol", "nse_ticker", "ticker_y", "Ticker_y"]:
                if candidate in frame.columns:
                    frame["ticker"] = frame[candidate]
                    break

        if ldf.empty or rdf.empty or "ticker" not in ldf.columns or "ticker" not in rdf.columns:
            return left

        # F.1: a single vectorized merge_asof with by="ticker" replaces the old
        # per-ticker Python loop (which scanned the full right frame once per
        # ticker and concatenated hundreds of small frames). Same match semantics
        # (backward, exact matches allowed, matched within ticker), same output.
        ldf["ticker"] = ldf["ticker"].astype(str)
        rdf["ticker"] = rdf["ticker"].astype(str)
        ldf[left_on] = pd.to_datetime(ldf[left_on], errors="coerce").astype("datetime64[ns]")
        rdf[right_on] = pd.to_datetime(rdf[right_on], errors="coerce").astype("datetime64[ns]")
        ldf = ldf.dropna(subset=["ticker", left_on])
        # Drop a duplicate right-hand ticker key only if the asof key is a
        # different column; merge_asof(by=...) keeps a single ticker column.
        rdf = rdf.dropna(subset=["ticker", right_on])
        # merge_asof requires both frames globally sorted by the on-key.
        ldf = ldf.sort_values([left_on, "ticker"], kind="mergesort")
        rdf = rdf.sort_values([right_on, "ticker"], kind="mergesort")
        merged_all = pd.merge_asof(
            ldf,
            rdf,
            left_on=left_on,
            right_on=right_on,
            by="ticker",
            direction="backward",
            allow_exact_matches=True,
            suffixes=("", "_rmerge"),
        )
        drop_dupes = [c for c in merged_all.columns if str(c).endswith("_rmerge")]
        if drop_dupes:
            merged_all = merged_all.drop(columns=drop_dupes, errors="ignore")
        return merged_all.sort_values([left_on, "ticker"], kind="mergesort").reset_index(drop=True)

    _group_zscore = staticmethod(_shared_group_zscore)
    _group_rank_centered = staticmethod(_shared_group_rank_centered)

    @staticmethod
    def _concat_new_columns(frame: pd.DataFrame, new_cols: dict[str, pd.Series]) -> pd.DataFrame:
        """Append many columns at once to avoid DataFrame fragmentation."""
        if not new_cols:
            return frame
        add = pd.DataFrame(new_cols, index=frame.index)
        overlap = [c for c in add.columns if c in frame.columns]
        base = frame.drop(columns=overlap, errors="ignore") if overlap else frame
        return pd.concat([base, add], axis=1)

    def _append_cross_sectional_transforms(
        self,
        frame: pd.DataFrame,
        cols: Iterable[str],
        *,
        groups: Optional[pd.Series] = None,
        clip_abs: float = 6.0,
        coerce_source: bool = False,
    ) -> pd.DataFrame:
        if frame.empty:
            return frame
        out = frame
        grp = groups if groups is not None else out["date"]
        source_updates: dict[str, pd.Series] = {}
        derived: dict[str, pd.Series] = {}
        for col in cols:
            if col not in out.columns:
                continue
            series = pd.to_numeric(out[col], errors="coerce")
            if coerce_source:
                source_updates[str(col)] = series
            derived[f"{col}_cs_z"] = self._group_zscore(series, grp, clip_abs=clip_abs)
            derived[f"{col}_cs_rank"] = self._group_rank_centered(series, grp)
        if source_updates:
            out = out.copy()
            source_df = pd.DataFrame(source_updates, index=out.index)
            out.loc[:, list(source_df.columns)] = source_df
        return self._concat_new_columns(out, derived)

    _normalize_ticker = staticmethod(_shared_normalize_ticker)

    def _ensure_primary_ticker_column(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        out = frame.copy()
        ticker = None
        for candidate in ["ticker", "ticker_x", "Ticker", "Ticker_x", "symbol", "nse_ticker", "ticker_y", "Ticker_y"]:
            if candidate not in out.columns:
                continue
            current = out[candidate].map(self._normalize_ticker)
            if ticker is None:
                ticker = current
                continue
            missing = ticker.isna() | ticker.eq("")
            ticker = ticker.where(~missing, current)
        if ticker is None:
            return out
        out["ticker"] = ticker
        drop_cols = [c for c in ["ticker_x", "ticker_y", "Ticker_x", "Ticker_y"] if c in out.columns]
        if drop_cols:
            out = out.drop(columns=drop_cols, errors="ignore")
        return out

    @staticmethod
    def _resolve_column(columns: Iterable[str], aliases: Iterable[str]) -> Optional[str]:
        norm_cols = {re.sub(r"[^a-z0-9]+", "", str(c).lower()): str(c) for c in columns}
        for alias in aliases:
            key = re.sub(r"[^a-z0-9]+", "", str(alias).lower())
            if key in norm_cols:
                return norm_cols[key]
        return None

    @staticmethod
    def _timeseries_zscore_by_date(values: pd.Series, dates: pd.Series, window: int = 252) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        d = pd.to_datetime(dates, errors="coerce")
        work = pd.DataFrame({"date": d, "value": v}).dropna(subset=["date"])
        if work.empty:
            return pd.Series(0.0, index=values.index, dtype=float)
        work = work.sort_values("date", kind="mergesort")
        by_date = work.groupby("date", as_index=False)["value"].last()
        roll_win = max(20, int(window))
        mu = by_date["value"].rolling(roll_win, min_periods=20).mean()
        sd = by_date["value"].rolling(roll_win, min_periods=20).std().replace(0.0, np.nan)
        z = ((by_date["value"] - mu) / (sd + 1e-12)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        by_date["z"] = z.clip(-6.0, 6.0)
        mapped = pd.DataFrame({"date": d}).merge(by_date[["date", "z"]], on="date", how="left")["z"]
        return pd.to_numeric(mapped, errors="coerce").fillna(0.0).astype(float)

    @staticmethod
    def _timeseries_diff_by_date(values: pd.Series, dates: pd.Series, periods: int = 65) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        d = pd.to_datetime(dates, errors="coerce")
        work = pd.DataFrame({"date": d, "value": v}).dropna(subset=["date"])
        if work.empty:
            return pd.Series(np.nan, index=values.index, dtype=float)
        work = work.sort_values("date", kind="mergesort")
        by_date = work.groupby("date", as_index=False)["value"].last()
        by_date["diff"] = by_date["value"] - by_date["value"].shift(max(1, int(periods)))
        mapped = pd.DataFrame({"date": d}).merge(by_date[["date", "diff"]], on="date", how="left")["diff"]
        return pd.to_numeric(mapped, errors="coerce").astype(float)

    def _feature_group_config(self, group_name: str) -> dict[str, Any]:
        groups = self.config.get("feature_groups", {}) or {}
        cfg = groups.get(group_name, {}) if isinstance(groups, dict) else {}
        return cfg if isinstance(cfg, dict) else {}

    def _reduced_sentiment_keep(self, group_name: str, defaults: list[str]) -> set[str]:
        cfg = self._feature_group_config(group_name)
        raw = cfg.get("reduced_keep", defaults)
        if not isinstance(raw, (list, tuple, set)):
            raw = defaults
        return {str(x) for x in raw if str(x).strip()}

    def apply_sentiment_feature_mode(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty:
            return frame
        if self.sentiment_feature_mode != "reduced":
            return frame

        keep_company = self._reduced_sentiment_keep(
            "company_sentiment_nlp",
            DEFAULT_COMPANY_SENTIMENT_REDUCED,
        )
        keep_market = self._reduced_sentiment_keep(
            "market_sentiment_macro_overlay",
            DEFAULT_MARKET_SENTIMENT_REDUCED,
        )

        company_prefixes = ("sent_", "sentiment_", "event_", "narrative_", "topic_")
        market_prefixes = ("macro_sentiment_", "mkt_sent_")
        drop_cols: list[str] = []
        for column in frame.columns:
            name = str(column)
            if any(name.startswith(prefix) for prefix in company_prefixes) and name not in keep_company:
                drop_cols.append(name)
            elif any(name.startswith(prefix) for prefix in market_prefixes) and name not in keep_market:
                drop_cols.append(name)

        if not drop_cols:
            return frame

        logger.info(
            "[sentiment] reduced mode active: dropping %d sentiment columns",
            int(len(drop_cols)),
        )
        return frame.drop(columns=sorted(set(drop_cols)), errors="ignore")

    def _merge_rbi_dbie_macro_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty or "date" not in panel.columns:
            return panel

        max_date = pd.to_datetime(panel["date"], errors="coerce").max()
        if pd.isna(max_date):
            return panel

        try:
            from src.ingestion.macro_loader import MacroLoader

            raw = MacroLoader(self.config).load_rbi_data(max_date.to_pydatetime())
        except Exception as exc:  # noqa: BLE001
            logger.warning("[macro] RBI DBIE feature merge skipped: %s", exc)
            return panel

        if raw is None or raw.empty or "period_date" not in raw.columns:
            return panel

        work = raw.copy()
        work["period_date"] = pd.to_datetime(work["period_date"], errors="coerce")
        release_col = "release_date" if "release_date" in work.columns else "period_date"
        work["availability_date"] = pd.to_datetime(work[release_col], errors="coerce")
        work = work.dropna(subset=["availability_date"]).sort_values("availability_date", kind="mergesort")
        if work.empty:
            return panel

        def _pick_column(preferred: list[str], contains: list[str]) -> str | None:
            for name in preferred:
                if name in work.columns:
                    return name
            lowered = {str(col).lower(): str(col) for col in work.columns}
            for token in contains:
                token_l = token.lower()
                for lower_col, original in lowered.items():
                    if token_l in lower_col:
                        return original
            return None

        repo_col = _pick_column(
            ["weekly_core_Policy Repo Rate (%)", "daily_other_REPO RATE (OVERNIGHT)"],
            ["policy repo rate", "repo rate (overnight)"],
        )
        gsec_col = _pick_column(
            ["weekly_core_10-Year G-Sec Yield (FBIL) (%)"],
            ["10-year g-sec yield"],
        )
        tbill_col = _pick_column(
            ["weekly_core_91-Day Treasury Bill (Primary) Yield (%)"],
            ["91-day treasury bill"],
        )
        cpi_col = _pick_column(
            [
                "monthly_core_Consumer Price Index (2012=100)",
                "monthly_other_All India New Consumer Price Index - Rural,Urban,Combined (Base 2012 = 100)",
            ],
            ["consumer price index (2012=100)", "all india new consumer price index"],
        )

        features = pd.DataFrame({"availability_date": work["availability_date"]})
        if repo_col is not None:
            features["rbi_repo_rate_level"] = pd.to_numeric(work[repo_col], errors="coerce")
        if gsec_col is not None and tbill_col is not None:
            gsec = pd.to_numeric(work[gsec_col], errors="coerce")
            tbill = pd.to_numeric(work[tbill_col], errors="coerce")
            features["yield_curve_slope"] = gsec - tbill
        if cpi_col is not None:
            cpi = pd.to_numeric(work[cpi_col], errors="coerce")
            consensus = cpi.shift(1).rolling(3, min_periods=3).mean()
            features["cpi_surprise"] = cpi - consensus

        merge_cols = [c for c in ["rbi_repo_rate_level", "yield_curve_slope", "cpi_surprise"] if c in features.columns]
        if not merge_cols:
            return panel

        features = (
            features.dropna(subset=["availability_date"])
            .groupby("availability_date", as_index=False)
            .last()
            .sort_values("availability_date", kind="mergesort")
        )
        features.loc[:, merge_cols] = features[merge_cols].ffill()

        out = panel.copy()
        out["_macro_orig_order"] = np.arange(len(out), dtype=int)
        out = pd.merge_asof(
            out.sort_values("date", kind="mergesort"),
            features[["availability_date"] + merge_cols].sort_values("availability_date", kind="mergesort"),
            left_on="date",
            right_on="availability_date",
            direction="backward",
            allow_exact_matches=True,
        )
        out = out.drop(columns=["availability_date"], errors="ignore")

        if "rbi_repo_rate_level" in out.columns:
            out["rbi_repo_rate_ts_z"] = self._timeseries_zscore_by_date(out["rbi_repo_rate_level"], out["date"], window=252)
            out["rbi_repo_rate_change_13w"] = self._timeseries_diff_by_date(out["rbi_repo_rate_level"], out["date"], periods=65)
        if "yield_curve_slope" in out.columns:
            out["yield_curve_slope_ts_z"] = self._timeseries_zscore_by_date(out["yield_curve_slope"], out["date"], window=252)
        if "cpi_surprise" in out.columns:
            out["cpi_surprise_ts_z"] = self._timeseries_zscore_by_date(out["cpi_surprise"], out["date"], window=252)

        out = out.sort_values("_macro_orig_order", kind="mergesort").drop(columns=["_macro_orig_order"], errors="ignore")
        return out.reset_index(drop=True)

    @staticmethod
    def _winsorize_series(values: pd.Series, lower_q: float = 0.01, upper_q: float = 0.99) -> pd.Series:
        s = pd.to_numeric(values, errors="coerce")
        if s.empty:
            return s
        ql = float(lower_q) if lower_q is not None else None
        qu = float(upper_q) if upper_q is not None else None
        if ql is None or qu is None or not (0.0 <= ql < qu <= 1.0):
            return s
        try:
            lo = s.quantile(ql)
            hi = s.quantile(qu)
        except Exception:
            return s
        if not np.isfinite(lo) or not np.isfinite(hi):
            return s
        return s.clip(lower=lo, upper=hi)

    @staticmethod
    def _safe_log1p(values: pd.Series) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        return np.log1p(v.where(v > -1.0, np.nan)).replace([np.inf, -np.inf], np.nan)

    def _load_nifty_series(self) -> pd.DataFrame:
        path = Path(self.config.get("nifty_prices_path", "data/processed/nifty.parquet"))
        df = self._safe_load_table(path)
        if df.empty:
            return pd.DataFrame(columns=["date", "close", "ret_1d"])
        work = df.copy()
        if "date" not in work.columns:
            if "Date" in work.columns:
                work["date"] = work["Date"]
            else:
                # Parquet uses Date index in some files.
                try:
                    work = work.reset_index()
                    if "Date" in work.columns:
                        work["date"] = work["Date"]
                except Exception:
                    work["date"] = pd.NaT
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        close_col = "close" if "close" in work.columns else ("Close" if "Close" in work.columns else None)
        if close_col is None:
            return pd.DataFrame(columns=["date", "close", "ret_1d"])
        work["close"] = pd.to_numeric(work[close_col], errors="coerce")
        work = work.dropna(subset=["date", "close"]).sort_values("date", kind="mergesort")
        work["ret_1d"] = work["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        return work[["date", "close", "ret_1d"]].drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    def _load_india_vix_series(self) -> pd.DataFrame:
        path = Path(self.config.get("india_vix_path", "data/processed/india_vix.parquet"))
        df = self._safe_load_table(path)
        if df.empty:
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

    def _load_announcement_dates(self) -> pd.DataFrame:
        raw_path = str(self.announcement_dates_path or "").strip()
        if not raw_path:
            raw_path = str(Path(self.alternative_data_path) / "earnings_dates_all.csv")
        path = Path(raw_path)
        df = self._safe_load_table(path)
        if df.empty:
            return pd.DataFrame(columns=["ticker", "announcement_date", "fiscal_year_end"])

        work = df.copy()
        tk_col = None
        for c in ["nse_ticker", "ticker", "symbol", "Symbol"]:
            if c in work.columns:
                tk_col = c
                break
        ann_col = None
        for c in ["announcement_date", "announcementDate", "date", "Date", "announced_at"]:
            if c in work.columns:
                ann_col = c
                break
        fye_col = None
        for c in ["fiscal_year_end", "quarter_end", "period_end", "period_end_date", "fy_end"]:
            if c in work.columns:
                fye_col = c
                break

        if tk_col is None or ann_col is None:
            return pd.DataFrame(columns=["ticker", "announcement_date", "fiscal_year_end"])

        work["ticker"] = work[tk_col].map(self._normalize_ticker)
        work["announcement_date"] = pd.to_datetime(work[ann_col], errors="coerce")
        if fye_col is not None:
            work["fiscal_year_end"] = pd.to_datetime(work[fye_col], errors="coerce")
        else:
            work["fiscal_year_end"] = pd.NaT

        work = work.dropna(subset=["ticker", "announcement_date"]).sort_values(
            ["ticker", "announcement_date"], kind="mergesort"
        )
        work = work.drop_duplicates(subset=["ticker", "announcement_date"], keep="last")
        return work[["ticker", "announcement_date", "fiscal_year_end"]].reset_index(drop=True)

    def _get_announcement_dates(self) -> pd.DataFrame:
        if self._announcement_dates is None:
            self._announcement_dates = self._load_announcement_dates()
        return self._announcement_dates.copy()

    @staticmethod
    def _safe_load_table(path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            if path.suffix.lower() in {".parquet", ".pq"}:
                return pd.read_parquet(path)
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _is_alternative_family_enabled(self, family: str) -> bool:
        cfg = self.alternative_features_available
        if not isinstance(cfg, dict) or not cfg:
            return True
        aliases = {
            "bulk_deals": ("bulk_deals",),
            "pledge": ("pledge", "promoter_pledge"),
            "earnings": ("earnings", "earnings_dates"),
            "ratings": ("ratings", "credit_ratings"),
            "announcements": ("announcements", "order_announcements"),
        }
        for key in aliases.get(family, (family,)):
            if key in cfg:
                return bool(cfg.get(key))
        return True

    def _merge_sentiment_training_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        sent = self._safe_load_table(Path(self.sentiment_path))
        if sent.empty:
            return panel

        out = panel.copy()
        sent = sent.copy()
        sent["date"] = self._as_date(sent, ["date", "Date", "timestamp"])
        if "availability_date" in sent.columns:
            sent["availability_date"] = self._as_date(sent, ["availability_date"])
        else:
            # PIT safety fallback: sentiment dated D is only tradable from D+1 BDay.
            sent["availability_date"] = self._as_date(sent, ["date"]) + pd.offsets.BDay(1)
        if "ticker" not in sent.columns:
            return out
        sent["ticker"] = sent["ticker"].map(self._normalize_ticker)
        sent = sent.dropna(subset=["ticker", "availability_date"]).sort_values(["ticker", "availability_date"], kind="mergesort")
        if sent.empty:
            return out

        sent = add_sentiment_features(sent)
        sent = add_event_features(sent)
        sent = add_narrative_features(sent)
        sent["sentiment_availability_date"] = sent["availability_date"]

        merge_cols = [
            "ticker",
            "sentiment_availability_date",
            "sentiment_polarity",
            "sentiment_conviction",
            "sentiment_surprise",
            "sentiment_uncertainty",
            "sentiment_polarity_5d_ma",
            "sentiment_polarity_momentum",
            "sentiment_volume_spike",
            "sentiment_conviction_x_polarity",
            "event_positive_flag",
            "event_negative_flag",
            "event_macro_flag",
            "event_market_moving_intensity",
            "narrative_momentum",
            "topic_drift",
            "narrative_strength",
        ]
        out = self._merge_asof_by_ticker(out, sent[merge_cols], left_on="date", right_on="sentiment_availability_date")
        out = out.drop(columns=["sentiment_availability_date"], errors="ignore")
        feat_cols = [c for c in merge_cols if c not in {"ticker", "sentiment_availability_date"}]
        out = self._append_cross_sectional_transforms(
            out,
            feat_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _merge_macro_feature_pack(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        macro_path = Path(self.macro_features_path)
        macro_df = self._safe_load_table(macro_path)
        if macro_df.empty:
            return panel

        out = panel.copy()
        m = macro_df.copy()
        m["date"] = self._as_date(m, ["date", "Date", "timestamp"])
        m["availability_date"] = self._as_date(m, ["availability_date", "date", "Date", "timestamp"])
        if "ticker" in m.columns:
            m["ticker"] = m["ticker"].astype(str)
        else:
            m["ticker"] = ""
        m = m.dropna(subset=["availability_date"]).sort_values("availability_date", kind="mergesort")
        if m.empty:
            return out

        market = m[m["ticker"].astype(str).eq("MARKET")].copy()
        market_cols = [
            c
            for c in [
                "power_yoy_growth",
                "gst_yoy_growth",
                "macro_activity_composite",
                "macro_regime_label",
                "india_market_polarity",
                "india_market_uncertainty",
            ]
            if c in market.columns
        ]
        if not market.empty and market_cols:
            market = market.rename(columns={"availability_date": "macro_availability_date"})
            out = pd.merge_asof(
                out.sort_values("date"),
                market[["macro_availability_date"] + market_cols].sort_values("macro_availability_date", kind="mergesort"),
                left_on="date",
                right_on="macro_availability_date",
                direction="backward",
                allow_exact_matches=True,
            )
            out = out.drop(columns=["macro_availability_date"], errors="ignore")

            market_num_cols = [c for c in market_cols if c != "macro_regime_label"]
            if market_num_cols:
                numeric_updates = {c: pd.to_numeric(out[c], errors="coerce") for c in market_num_cols}
                out = out.copy()
                out.loc[:, market_num_cols] = pd.DataFrame(numeric_updates, index=out.index)
                ts_features = {
                    f"{c}_ts_z": self._timeseries_zscore_by_date(out[c], out["date"], window=252)
                    for c in market_num_cols
                }
                out = self._concat_new_columns(out, ts_features)

        sector_cols = [c for c in ["sector_gst_yoy", "sector_activity_zscore"] if c in m.columns]
        if sector_cols:
            sector_col = next((c for c in ["sector_name", "Industry", "industry", "Sector", "sector"] if c in out.columns), None)
            sec_rows = m[m["ticker"].astype(str).ne("MARKET")].copy()
            if sector_col and "sector" in sec_rows.columns and not sec_rows.empty:
                sec_rows["sector"] = sec_rows["sector"].astype(str)
                left = out.copy()
                left["_merge_sector"] = left[sector_col].astype(str)
                sec_merge = sec_rows.rename(columns={"availability_date": "macro_sector_availability_date"})[
                    ["macro_sector_availability_date", "sector"] + sector_cols
                ].sort_values("macro_sector_availability_date", kind="mergesort")
                merged_parts: list[pd.DataFrame] = []
                for sec, grp in left.groupby("_merge_sector", sort=False):
                    rhs = sec_merge[sec_merge["sector"] == str(sec)]
                    lg = grp.sort_values("date", kind="mergesort")
                    if rhs.empty:
                        for c in sector_cols:
                            lg[c] = np.nan
                        merged_parts.append(lg)
                        continue
                    mg = pd.merge_asof(
                        lg,
                        rhs.drop(columns=["sector"], errors="ignore"),
                        left_on="date",
                        right_on="macro_sector_availability_date",
                        direction="backward",
                        allow_exact_matches=True,
                    )
                    mg = mg.drop(columns=["macro_sector_availability_date"], errors="ignore")
                    merged_parts.append(mg)
                out = pd.concat(merged_parts, ignore_index=True) if merged_parts else left
                out = out.drop(columns=["_merge_sector"], errors="ignore")

            out = self._append_cross_sectional_transforms(
                out,
                sector_cols,
                groups=out["date"],
                clip_abs=6.0,
                coerce_source=True,
            )

        out = self._merge_rbi_weekly_macro_features(out)
        return self._merge_rbi_dbie_macro_features(out)

    def _merge_rbi_weekly_macro_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty or "date" not in panel.columns:
            return panel

        path = Path(self.rbi_macro_weekly_path)
        weekly = self._safe_load_table(path)
        if weekly.empty or "date" not in weekly.columns:
            return panel

        macro = weekly.copy()
        macro["date"] = pd.to_datetime(macro["date"], errors="coerce").dt.normalize()
        macro = macro.dropna(subset=["date"]).sort_values("date", kind="mergesort")
        if macro.empty:
            return panel

        # F.2: skip columns with no non-null data. A blanket prefix-and-merge of
        # every numeric column imports empty/legacy-schema series that become
        # zeroed cross-sectional signals downstream (a root cause of the RBI
        # column bloat and dead macro columns that repairs then re-drop each build).
        numeric_cols = [
            c for c in macro.columns
            if c != "date"
            and pd.api.types.is_numeric_dtype(macro[c])
            and bool(pd.to_numeric(macro[c], errors="coerce").notna().any())
        ]
        if not numeric_cols:
            return panel

        rename = {c: f"rbi_{c}" if not str(c).startswith("rbi_") else str(c) for c in numeric_cols}
        macro = macro[["date"] + numeric_cols].rename(columns=rename)
        repo_candidates = [
            col
            for col in macro.columns
            if col != "date"
            and (
                "policy_repo" in str(col).lower()
                or "repo_rate" in str(col).lower()
                or "repo rate" in str(col).lower()
            )
        ]
        if repo_candidates and "rbi_rate_chg" not in macro.columns:
            repo = pd.to_numeric(macro[repo_candidates[0]], errors="coerce")
            macro["rbi_rate_chg"] = repo.diff()

        out = panel.copy()
        out["_rbi_orig_order"] = np.arange(len(out), dtype=int)
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
        out = pd.merge_asof(
            out.sort_values("date", kind="mergesort"),
            macro.sort_values("date", kind="mergesort"),
            on="date",
            direction="backward",
            allow_exact_matches=True,
        )
        out = out.sort_values("_rbi_orig_order", kind="mergesort").drop(columns=["_rbi_orig_order"], errors="ignore")
        return out.reset_index(drop=True)

    def _prepare_credit_quarterly_frame(self) -> pd.DataFrame:
        xbrl = self._safe_load_table(Path(self.credit_quarterly_path))
        frames: list[pd.DataFrame] = []
        if not xbrl.empty:
            work = xbrl.copy()
            if "ticker" not in work.columns and "symbol" in work.columns:
                work["ticker"] = work["symbol"]
            if "ticker" in work.columns:
                work["ticker"] = work["ticker"].map(self._normalize_ticker)
                work["availability_date"] = self._as_date(work, ["availability_date", "date", "Date", "period_end"])
                work["period_end"] = self._as_date(work, ["period_end", "date", "Date"])
                preferred_basis = work.get("basis", pd.Series("", index=work.index)).astype(str).str.lower()
                work["_basis_rank"] = np.select(
                    [
                        preferred_basis.eq("standalone"),
                        preferred_basis.eq("consolidated"),
                    ],
                    [2, 1],
                    default=0,
                )
                value_cols = [
                    "gnpa_pct",
                    "nnpa_pct",
                    "roa",
                    "cet1_ratio",
                    "at1_ratio",
                    "provision_coverage_ratio",
                    "credit_cost_to_nii",
                    "net_interest_income",
                    "provisions",
                    "operating_profit_pre_prov",
                    "interest_earned",
                    "interest_expended",
                ]
                keep = ["ticker", "availability_date", "period_end", "_basis_rank"] + [
                    c for c in value_cols if c in work.columns
                ]
                work = work[keep].dropna(subset=["ticker", "availability_date"]).copy()
                if not work.empty:
                    work = work.sort_values(
                        ["ticker", "period_end", "_basis_rank", "availability_date"],
                        kind="mergesort",
                    )
                    work = work.drop_duplicates(subset=["ticker", "period_end"], keep="last")
                    for c in value_cols:
                        if c in work.columns:
                            work[c] = pd.to_numeric(work[c], errors="coerce")
                    work = work.rename(
                        columns={
                            "gnpa_pct": "credit_gnpa_pct",
                            "nnpa_pct": "credit_nnpa_pct",
                            "roa": "credit_roa",
                            "cet1_ratio": "credit_cet1_ratio",
                            "at1_ratio": "credit_at1_ratio",
                            "provision_coverage_ratio": "credit_provision_coverage_ratio",
                            "credit_cost_to_nii": "credit_cost_to_nii",
                            "net_interest_income": "credit_net_interest_income",
                            "provisions": "credit_provisions",
                            "operating_profit_pre_prov": "credit_operating_profit_pre_prov",
                            "interest_earned": "credit_interest_earned",
                            "interest_expended": "credit_interest_expended",
                        }
                    )
                    frames.append(work.drop(columns=["_basis_rank"], errors="ignore"))

        screener = self._safe_load_table(Path(self.screener_quarterly_path))
        if not screener.empty and "ticker" in screener.columns:
            sq = screener.copy()
            sq["ticker"] = sq["ticker"].map(self._normalize_ticker)
            sq["availability_date"] = self._as_date(sq, ["availability_date", "date", "Date"])
            keep = [
                "ticker",
                "availability_date",
                "gross_npa_pct",
                "net_npa_pct",
                "financing_margin_pct",
                "financing_profit",
            ]
            sq = sq[[c for c in keep if c in sq.columns]].dropna(subset=["ticker", "availability_date"]).copy()
            if not sq.empty:
                sq = sq.rename(
                    columns={
                        "gross_npa_pct": "credit_screener_gnpa_pct",
                        "net_npa_pct": "credit_screener_nnpa_pct",
                        "financing_margin_pct": "credit_screener_financing_margin_pct",
                        "financing_profit": "credit_screener_financing_profit",
                    }
                )
                for c in sq.columns:
                    if c not in {"ticker", "availability_date"}:
                        sq[c] = pd.to_numeric(sq[c], errors="coerce")
                frames.append(sq)

        if not frames:
            return pd.DataFrame()

        merged = pd.concat(frames, ignore_index=True, sort=False)
        merged["availability_date"] = pd.to_datetime(merged["availability_date"], errors="coerce").dt.normalize()
        merged = merged.dropna(subset=["ticker", "availability_date"]).sort_values(
            ["ticker", "availability_date"], kind="mergesort"
        )
        value_cols = [c for c in merged.columns if c not in {"ticker", "availability_date", "period_end"}]
        collapsed = merged.groupby(["ticker", "availability_date"], as_index=False)[value_cols].last()

        collapsed["credit_gnpa_pct"] = pd.to_numeric(
            collapsed.get("credit_gnpa_pct", pd.Series(np.nan, index=collapsed.index)),
            errors="coerce",
        ).where(
            pd.to_numeric(collapsed.get("credit_gnpa_pct", pd.Series(np.nan, index=collapsed.index)), errors="coerce").notna(),
            pd.to_numeric(collapsed.get("credit_screener_gnpa_pct", pd.Series(np.nan, index=collapsed.index)), errors="coerce"),
        )
        collapsed["credit_nnpa_pct"] = pd.to_numeric(
            collapsed.get("credit_nnpa_pct", pd.Series(np.nan, index=collapsed.index)),
            errors="coerce",
        ).where(
            pd.to_numeric(collapsed.get("credit_nnpa_pct", pd.Series(np.nan, index=collapsed.index)), errors="coerce").notna(),
            pd.to_numeric(collapsed.get("credit_screener_nnpa_pct", pd.Series(np.nan, index=collapsed.index)), errors="coerce"),
        )
        collapsed = collapsed.sort_values(["ticker", "availability_date"], kind="mergesort")
        for base in [
            "credit_gnpa_pct",
            "credit_nnpa_pct",
            "credit_net_interest_income",
            "credit_provisions",
            "credit_operating_profit_pre_prov",
        ]:
            if base not in collapsed.columns:
                continue
            collapsed[base] = pd.to_numeric(collapsed[base], errors="coerce")
            numeric = collapsed[base]
            grp = collapsed.groupby("ticker", sort=False)[base]
            if base.endswith("_pct"):
                # B.1/F.4: for a metric ALREADY on a percentage scale (e.g. GNPA%
                # moving 0.01% -> 100%), pct_change yields a legitimate-but-absurd
                # ~9999% "relative change" that no inf-filter or ratio bound
                # catches, and it also poisons the cross-sectional z/rank derived
                # from it. Use absolute percentage-point diffs instead (same
                # pattern as the _chg_4q term below).
                collapsed[f"{base}_qoq"] = (numeric - grp.shift(1)).replace([np.inf, -np.inf], np.nan)
                collapsed[f"{base}_yoy"] = (numeric - grp.shift(4)).replace([np.inf, -np.inf], np.nan)
                collapsed[f"{base}_chg_4q"] = numeric - grp.shift(4)
            else:
                collapsed[f"{base}_qoq"] = grp.pct_change(1, fill_method=None).replace([np.inf, -np.inf], np.nan)
                collapsed[f"{base}_yoy"] = grp.pct_change(4, fill_method=None).replace([np.inf, -np.inf], np.nan)

        return collapsed.reset_index(drop=True)

    def _merge_credit_feature_pack(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty or "date" not in panel.columns or "ticker" not in panel.columns:
            return panel
        credit = self._prepare_credit_quarterly_frame()
        if credit.empty:
            return panel

        credit_cols = [c for c in credit.columns if c not in {"ticker", "availability_date"}]
        if not credit_cols:
            return panel

        out = self._merge_asof_by_ticker(
            panel,
            credit[["ticker", "availability_date"] + credit_cols],
            left_on="date",
            right_on="availability_date",
        )
        out = out.drop(columns=["availability_date"], errors="ignore")
        numeric_credit_cols = [
            c for c in credit_cols
            if c in out.columns and pd.api.types.is_numeric_dtype(out[c])
        ]
        out = self._append_cross_sectional_transforms(
            out,
            numeric_credit_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _prepare_screener_annual_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        out = raw.copy()
        if "ticker" in out.columns:
            out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out["availability_date"] = self._as_date(out, ["availability_date", "date", "Date", "timestamp"])
        out = out.dropna(subset=["ticker", "availability_date"]).sort_values(
            ["ticker", "availability_date"], kind="mergesort"
        )

        alias_map = {
            "screener_raw_sales": ["sales", "revenue"],
            "screener_raw_operating_profit": ["operating_profit", "operating profit", "ebit", "ebitda"],
            "screener_raw_net_profit": ["net_profit", "net profit", "pat"],
            "screener_raw_roce": ["roce_pct", "roce %", "roce"],
            "screener_raw_debtor_days": ["debtor_days", "debtor days"],
            "screener_raw_cash_conversion_cycle": ["cash_conversion_cycle", "cash conversion cycle"],
            "screener_raw_cash_from_operating_activity": [
                "cash_from_operating_activity",
                "cash from operating activity",
                "cash_from_operating_activities",
                "cash from operating activities",
            ],
        }
        keep = ["ticker", "availability_date"]
        for target, aliases in alias_map.items():
            src = self._resolve_column(out.columns, aliases)
            if src is None:
                out[target] = np.nan
                keep.append(target)
                continue
            out[target] = pd.to_numeric(out[src], errors="coerce")
            keep.append(target)

        out = out[keep].copy()
        out["pat_prev_year"] = out.groupby("ticker", sort=False)["screener_raw_net_profit"].shift(1)
        out["sales_prev_year"] = out.groupby("ticker", sort=False)["screener_raw_sales"].shift(1)
        out["screener_pat_growth_1y"] = (
            (out["screener_raw_net_profit"] - out["pat_prev_year"])
            / out["pat_prev_year"].abs().replace(0.0, np.nan)
        ) * 100.0
        out["screener_revenue_growth_1y"] = (
            (out["screener_raw_sales"] - out["sales_prev_year"])
            / out["sales_prev_year"].abs().replace(0.0, np.nan)
        ) * 100.0
        out = out.drop(columns=["pat_prev_year", "sales_prev_year"], errors="ignore")
        out = out.sort_values(["ticker", "availability_date"], kind="mergesort")
        out = out.drop_duplicates(subset=["ticker", "availability_date"], keep="last")
        return out.reset_index(drop=True)

    def _prepare_screener_shareholding_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        out = raw.copy()
        if "ticker" in out.columns:
            out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out["availability_date"] = self._as_date(out, ["availability_date", "date", "Date", "timestamp"])
        out = out.dropna(subset=["ticker", "availability_date"]).sort_values(
            ["ticker", "availability_date"], kind="mergesort"
        )

        alias_map = {
            "screener_raw_promoter_pct": ["promoter_pct", "promoters_pct", "promoter"],
            "screener_raw_fii_pct": ["fii_pct", "fiis_pct", "fii"],
            "screener_raw_dii_pct": ["dii_pct", "diis_pct", "dii"],
            "screener_raw_public_pct": ["public_pct", "public"],
            "screener_raw_govt_pct": ["govt_pct", "government_pct", "govt"],
        }
        keep = ["ticker", "availability_date"]
        for target, aliases in alias_map.items():
            src = self._resolve_column(out.columns, aliases)
            if src is None:
                out[target] = np.nan
                keep.append(target)
                continue
            out[target] = pd.to_numeric(out[src], errors="coerce")
            keep.append(target)

        out = out[keep].copy()
        out["screener_promoter_change_1q"] = out.groupby("ticker", sort=False)["screener_raw_promoter_pct"].diff(1)
        out["screener_promoter_change_4q"] = out.groupby("ticker", sort=False)["screener_raw_promoter_pct"].diff(4)
        out["screener_fii_change_1q"] = out.groupby("ticker", sort=False)["screener_raw_fii_pct"].diff(1)
        out["screener_institutional_pct"] = (
            pd.to_numeric(out["screener_raw_fii_pct"], errors="coerce")
            + pd.to_numeric(out["screener_raw_dii_pct"], errors="coerce")
        )
        out = out.sort_values(["ticker", "availability_date"], kind="mergesort")
        out = out.drop_duplicates(subset=["ticker", "availability_date"], keep="last")
        return out.reset_index(drop=True)

    def _load_screener_annual(self) -> Optional[pd.DataFrame]:
        path = Path(self.screener_fundamentals_path)
        if not path.exists():
            logger.warning("[screener] annual fundamentals not found at %s", path)
            return None
        try:
            raw = self._safe_load_table(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[screener] failed to read annual fundamentals at %s: %s", path, exc)
            return None
        if raw.empty:
            return None
        return self._prepare_screener_annual_frame(raw)

    def _load_screener_shareholding(self) -> Optional[pd.DataFrame]:
        path = Path(self.screener_shareholding_path)
        if not path.exists():
            logger.warning("[screener] shareholding not found at %s", path)
            return None
        try:
            raw = self._safe_load_table(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[screener] failed to read shareholding at %s: %s", path, exc)
            return None
        if raw.empty:
            return None
        return self._prepare_screener_shareholding_frame(raw)

    @staticmethod
    def _drop_screener_collision_columns(frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        drops: list[str] = []
        for col in out.columns:
            if not str(col).endswith("_screener"):
                continue
            base = str(col)[: -len("_screener")]
            if base in out.columns:
                drops.append(col)
        if drops:
            out = out.drop(columns=drops, errors="ignore")
        return out

    @staticmethod
    def _series_or_nan(frame: pd.DataFrame, col: str) -> pd.Series:
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce")
        return pd.Series(np.nan, index=frame.index, dtype=float)

    def _merge_screener_annual(
        self,
        df: pd.DataFrame,
        screener_annual: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        source = screener_annual if isinstance(screener_annual, pd.DataFrame) else self._screener_annual
        if isinstance(source, pd.DataFrame) and not source.empty and "screener_raw_sales" not in source.columns:
            source = self._prepare_screener_annual_frame(source)
        if df.empty or not isinstance(source, pd.DataFrame) or source.empty:
            return df
        left = df.copy()
        left["ticker"] = left["ticker"].map(self._normalize_ticker)
        left["date"] = self._as_date(left, ["date"])

        right = source.copy()
        right["ticker"] = right["ticker"].map(self._normalize_ticker)
        right["availability_date"] = self._as_date(right, ["availability_date", "date", "Date", "timestamp"])
        right = right.rename(columns={"availability_date": "screener_availability_date"})
        right = right.dropna(subset=["ticker", "screener_availability_date"]).sort_values(
            ["ticker", "screener_availability_date"], kind="mergesort"
        )

        # F.1: single vectorized asof-merge matched within ticker, replacing the
        # per-ticker Python loop over the full right frame.
        left = left.dropna(subset=["ticker", "date"]).sort_values(["date", "ticker"], kind="mergesort")
        merged = pd.merge_asof(
            left,
            right.sort_values(["screener_availability_date", "ticker"], kind="mergesort"),
            left_on="date",
            right_on="screener_availability_date",
            by="ticker",
            direction="backward",
            suffixes=("", "_screener"),
        )
        out = merged.sort_values(["date", "ticker"], kind="mergesort")
        out = self._drop_screener_collision_columns(out)

        op = self._series_or_nan(out, "screener_raw_operating_profit")
        sales = self._series_or_nan(out, "screener_raw_sales")
        net_profit = self._series_or_nan(out, "screener_raw_net_profit")
        cfo = self._series_or_nan(out, "screener_raw_cash_from_operating_activity")
        # B.2: route OPM% through the epsilon-floored divide (same as canonical
        # operating_margin) instead of a bare exact-zero-guarded division.
        out["screener_opm_pct"] = _safe_ratio_divide(op, sales) * 100.0
        out["screener_pat_growth_1y"] = self._series_or_nan(out, "screener_pat_growth_1y")
        out["screener_revenue_growth_1y"] = self._series_or_nan(out, "screener_revenue_growth_1y")
        out["screener_roce"] = self._series_or_nan(out, "screener_raw_roce")
        out["screener_debtor_days"] = self._series_or_nan(out, "screener_raw_debtor_days")
        out["screener_cash_conversion_cycle"] = self._series_or_nan(out, "screener_raw_cash_conversion_cycle")
        out["screener_cfo_to_pat"] = (cfo / net_profit.replace(0.0, np.nan)).clip(-5.0, 5.0)
        out["screener_availability_date"] = pd.to_datetime(
            out.get("screener_availability_date", pd.NaT), errors="coerce"
        )

        annual_cols = [
            "screener_opm_pct",
            "screener_pat_growth_1y",
            "screener_revenue_growth_1y",
            "screener_roce",
            "screener_debtor_days",
            "screener_cash_conversion_cycle",
            "screener_cfo_to_pat",
        ]
        out = self._append_cross_sectional_transforms(
            out,
            annual_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _merge_screener_shareholding(
        self,
        df: pd.DataFrame,
        screener_shareholding: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        source = (
            screener_shareholding if isinstance(screener_shareholding, pd.DataFrame) else self._screener_shareholding
        )
        if isinstance(source, pd.DataFrame) and not source.empty and "screener_raw_promoter_pct" not in source.columns:
            source = self._prepare_screener_shareholding_frame(source)
        if df.empty or not isinstance(source, pd.DataFrame) or source.empty:
            return df
        left = df.copy()
        left["ticker"] = left["ticker"].map(self._normalize_ticker)
        left["date"] = self._as_date(left, ["date"])

        right = source.copy()
        right["ticker"] = right["ticker"].map(self._normalize_ticker)
        right["availability_date"] = self._as_date(right, ["availability_date", "date", "Date", "timestamp"])
        right = right.rename(columns={"availability_date": "screener_shareholding_availability_date"})
        right = right.dropna(subset=["ticker", "screener_shareholding_availability_date"]).sort_values(
            ["ticker", "screener_shareholding_availability_date"], kind="mergesort"
        )

        # F.1: single vectorized asof-merge matched within ticker.
        left = left.dropna(subset=["ticker", "date"]).sort_values(["date", "ticker"], kind="mergesort")
        merged = pd.merge_asof(
            left,
            right.sort_values(["screener_shareholding_availability_date", "ticker"], kind="mergesort"),
            left_on="date",
            right_on="screener_shareholding_availability_date",
            by="ticker",
            direction="backward",
            suffixes=("", "_screener"),
        )
        out = merged.sort_values(["date", "ticker"], kind="mergesort")
        out = self._drop_screener_collision_columns(out)

        out["screener_promoter_pct"] = self._series_or_nan(out, "screener_raw_promoter_pct")
        out["screener_promoter_change_1q"] = self._series_or_nan(out, "screener_promoter_change_1q")
        out["screener_promoter_change_4q"] = self._series_or_nan(out, "screener_promoter_change_4q")
        out["screener_fii_pct"] = self._series_or_nan(out, "screener_raw_fii_pct")
        out["screener_fii_change_1q"] = self._series_or_nan(out, "screener_fii_change_1q")
        out["screener_dii_pct"] = self._series_or_nan(out, "screener_raw_dii_pct")
        out["screener_institutional_pct"] = self._series_or_nan(out, "screener_institutional_pct")
        out["screener_public_pct"] = self._series_or_nan(out, "screener_raw_public_pct")
        out["screener_govt_pct"] = self._series_or_nan(out, "screener_raw_govt_pct")

        free_float = (
            pd.to_numeric(out["screener_public_pct"], errors="coerce")
            + pd.to_numeric(out["screener_fii_pct"], errors="coerce")
            + pd.to_numeric(out["screener_dii_pct"], errors="coerce")
        )
        # F.3: fall back PER ROW where the public/fii/dii sum is missing but the
        # promoter-based estimate is available — not only when the entire column
        # is empty (the whole-column .isna().all() guard almost never fires and
        # left ~40% of rows unfilled).
        promoter = pd.to_numeric(out["screener_promoter_pct"], errors="coerce")
        govt = pd.to_numeric(out["screener_govt_pct"], errors="coerce")
        promoter_fallback = 100.0 - promoter - govt.fillna(0.0)
        out["screener_free_float_pct"] = coalesce_rowwise(free_float, promoter_fallback)
        out["screener_shareholding_availability_date"] = pd.to_datetime(
            out.get("screener_shareholding_availability_date", pd.NaT), errors="coerce"
        )

        share_cols = [
            "screener_promoter_pct",
            "screener_promoter_change_1q",
            "screener_promoter_change_4q",
            "screener_fii_pct",
            "screener_fii_change_1q",
            "screener_dii_pct",
            "screener_institutional_pct",
            "screener_public_pct",
            "screener_govt_pct",
            "screener_free_float_pct",
        ]
        out = self._append_cross_sectional_transforms(
            out,
            share_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=True,
        )
        return out

    def _apply_sector_lookup(self, panel: pd.DataFrame, sector_lookup: Optional[dict[str, str]]) -> pd.DataFrame:
        if panel.empty or "ticker" not in panel.columns or not sector_lookup:
            return panel
        out = panel.copy()
        tk_norm = out["ticker"].map(self._normalize_ticker)
        mapped = tk_norm.map(sector_lookup)
        sector_col = next((c for c in ["Industry", "industry", "Sector", "sector"] if c in out.columns), None)
        if sector_col is None:
            out["sector"] = mapped.astype("string")
        else:
            cur = out[sector_col].astype("string")
            out[sector_col] = cur.where(cur.notna() & cur.str.strip().ne(""), mapped).astype("string")
        return out

    def _add_fundamental_factor_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        if panel.empty:
            return panel
        out = panel.copy()
        eps = 1e-12
        def to_num(c: str) -> pd.Series:
            if c in out.columns:
                return pd.to_numeric(out[c], errors="coerce")
            return pd.Series(np.nan, index=out.index, dtype=float)

        net_income = to_num("net_income")
        equity = to_num("equity")
        revenue = to_num("revenue")
        op_inc = to_num("operating_income")
        ebitda = to_num("ebitda")
        op_cf = to_num("operating_cash_flow")
        total_assets = to_num("total_assets")
        debt = to_num("total_debt")
        interest = to_num("interest_expense")

        safe_divide = _safe_ratio_divide

        out["roe"] = safe_divide(net_income, equity)
        out["operating_margin"] = safe_divide(op_inc, revenue)
        out["ebitda_margin"] = safe_divide(ebitda, revenue)
        # CRITICAL: Accruals formula for Indian market - INDIA SIGN CORRECTION (Phase 0.2)
        # Formula: (Net_Income - Operating_Cash_Flow) / Total_Assets
        # Indian market behavior: High accruals → HIGHER returns (Sehgal et al. 2012)
        # This is OPPOSITE to US Sloan effect - we LONG high accruals in India
        # Reference: Northstar V3 Signal Engineering Plan, Phase 0.2
        # Sign: POSITIVE for India (high accruals = positive signal)
        out["accruals_ratio"] = safe_divide(net_income - op_cf, total_assets)
        out["cash_conversion"] = safe_divide(op_cf, net_income)
        out["asset_turnover"] = safe_divide(revenue, total_assets)
        out["debt_to_equity"] = safe_divide(debt, equity)
        out["interest_coverage"] = safe_divide(op_inc, interest.abs(), min_abs_denominator=1.0)

        if "ticker" in out.columns:
            g = out.groupby("ticker", sort=False)
            out["roe_qoq_change"] = g["roe"].diff(1)
            out["operating_margin_change"] = g["operating_margin"].diff(1)
        else:
            out["roe_qoq_change"] = np.nan
            out["operating_margin_change"] = np.nan
        return out

    def _add_structural_alpha_features(self, panel: pd.DataFrame) -> pd.DataFrame:
        out = panel.copy()
        if out.empty or "date" not in out.columns:
            return out

        sector_col = next((c for c in ["Industry", "industry", "Sector", "sector"] if c in out.columns), None)
        if sector_col is None:
            sector = pd.Series("UNKNOWN", index=out.index, dtype="object")
        else:
            sector = sector_string(out[sector_col])
        out["sector_name"] = sector

        # Sector-relative factors: cross-sectional de-biasing from broad beta.
        sector_group = [out["date"], sector]
        sector_rel_cols = [
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "mom_5d",
            "mom_10d",
            "mom_20d",
            "mom_60d",
            "vol_20d",
            "vol_60d",
            "price_to_sma20",
        ]
        for col in sector_rel_cols:
            if col not in out.columns:
                continue
            v = pd.to_numeric(out[col], errors="coerce")
            sec_mean = v.groupby(sector_group, sort=False).transform("mean")
            out[f"{col}_sector_rel"] = v - sec_mean

        if {"mom_20d_sector_rel", "vol_20d"}.issubset(set(out.columns)):
            sec_vol = (
                pd.to_numeric(out["vol_20d"], errors="coerce")
                .abs()
                .groupby(sector_group, sort=False)
                .transform("mean")
            )
            out["mom_20d_sector_ir"] = pd.to_numeric(out["mom_20d_sector_rel"], errors="coerce") / (sec_vol + 1e-6)

        fundamental_cols = [
            "roe",
            "roe_qoq_change",
            "operating_margin",
            "operating_margin_change",
            "ebitda_margin",
            "accruals_ratio",
            "cash_conversion",
            "asset_turnover",
            "debt_to_equity",
            "interest_coverage",
        ]
        sector_z_updates: dict[str, pd.Series] = {}
        for col in fundamental_cols:
            if col not in out.columns:
                continue
            sector_z_updates[f"{col}_sector_z"] = self._group_zscore(
                out[col],
                pd.MultiIndex.from_arrays([out["date"], sector]),
                clip_abs=6.0,
            )
        out = self._concat_new_columns(out, sector_z_updates)

        # Residual momentum engine: sector-neutral daily return accumulation.
        # B.3: ret_1d_sector_resid is NOT a regression residual — it is the
        # sector-mean-relative return, identical to ret_1d_sector_rel, and is
        # dropped from the export by EXACT_DUPLICATE_DROP_PAIRS. It survives here
        # only as the base series for the res_mom_* features (which ARE exported
        # and correctly named). Kept as an internal intermediate, not a shipped
        # feature.
        if "ret_1d" in out.columns and "ticker" in out.columns:
            ret_1d = pd.to_numeric(out["ret_1d"], errors="coerce")
            sec_ret_1d = ret_1d.groupby(sector_group, sort=False).transform("mean")
            out["ret_1d_sector_resid"] = ret_1d - sec_ret_1d
            g_ticker = out.groupby("ticker", sort=False)
            resid = pd.to_numeric(out["ret_1d_sector_resid"], errors="coerce").fillna(0.0)

            out["res_mom_5d"] = (
                g_ticker["ret_1d_sector_resid"].rolling(5, min_periods=3).sum().reset_index(level=0, drop=True)
            )
            out["res_mom_20d"] = (
                g_ticker["ret_1d_sector_resid"].rolling(20, min_periods=10).sum().reset_index(level=0, drop=True)
            )
            out["res_mom_60d"] = (
                g_ticker["ret_1d_sector_resid"].rolling(60, min_periods=30).sum().reset_index(level=0, drop=True)
            )
            out["res_mom_20d_slope_5d"] = g_ticker["res_mom_20d"].diff(5)
            out["res_mom_20d_accel_5d"] = g_ticker["res_mom_20d_slope_5d"].diff(5)

            if "vol_20d" in out.columns:
                vol_scale = pd.to_numeric(out["vol_20d"], errors="coerce").abs() * np.sqrt(20.0)
                out["res_mom_20d_ir"] = pd.to_numeric(out["res_mom_20d"], errors="coerce") / (vol_scale + 1e-6)
            if {"res_mom_20d", "vol_z20"}.issubset(set(out.columns)):
                out["res_mom20_x_liquidity"] = (
                    pd.to_numeric(out["res_mom_20d"], errors="coerce")
                    * pd.to_numeric(out["vol_z20"], errors="coerce")
                )

        # Structural interactions.
        if {"mom_20d", "vol_z20"}.issubset(set(out.columns)):
            out["mom20_x_liquidity"] = (
                pd.to_numeric(out["mom_20d"], errors="coerce") * pd.to_numeric(out["vol_z20"], errors="coerce")
            )
        if {"vol_20d", "regime_modifier"}.issubset(set(out.columns)):
            out["vol20_x_regime_modifier"] = (
                pd.to_numeric(out["vol_20d"], errors="coerce")
                * pd.to_numeric(out["regime_modifier"], errors="coerce")
            )
        if {"mkt_sent_uncertainty", "mkt_sent_narrative_conflict"}.issubset(set(out.columns)):
            out["sent_conflict_x_uncertainty"] = (
                pd.to_numeric(out["mkt_sent_uncertainty"], errors="coerce")
                * pd.to_numeric(out["mkt_sent_narrative_conflict"], errors="coerce")
            )
        if {"mom_20d", "macro_regime_score"}.issubset(set(out.columns)):
            out["mom20_x_macro_regime"] = (
                pd.to_numeric(out["mom_20d"], errors="coerce")
                * pd.to_numeric(out["macro_regime_score"], errors="coerce")
            )

        # Cross-sectional transforms per date: ranking and z-score variants.
        cs_seed_cols = [
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "mom_5d",
            "mom_10d",
            "mom_20d",
            "mom_60d",
            "mom_63d_1m_lag",
            "vol_20d",
            "vol_60d",
            "price_to_sma20",
            "vol_surge_5d",
            "amihud_illiquidity",
            "size_x_amihud",
            "bab_beta",
            "max_lottery_21d",
            "max_lottery_5d",
            "max_lottery_top5_21d",
            "piotroski_f_score",
            "piotroski_f_score_norm",
            "eps_sue",
            "rev_sue",
            "eps_sue_decay",
            "rev_sue_decay",
            "combined_sue",
            "earnings_quality_score",
            "accruals_volatility",
            "nifty_above_200d",
            "india_vix",
            "india_vix_z",
            "india_vix_norm",
            "vol_z20",
            "posterior_gap",
            "posterior_variance",
            "agreement_score",
            "regime_modifier",
            "mom_20d_sector_rel",
            "mom_60d_sector_rel",
            "ret_20d_sector_rel",
            "mom_20d_sector_ir",
            "ret_1d_sector_resid",
            "res_mom_5d",
            "res_mom_20d",
            "res_mom_60d",
            "res_mom_20d_slope_5d",
            "res_mom_20d_accel_5d",
            "res_mom_20d_ir",
            "res_mom20_x_liquidity",
            "mom20_x_liquidity",
            "vol20_x_regime_modifier",
            "sent_conflict_x_uncertainty",
            "mom20_x_macro_regime",
            "roe",
            "roe_qoq_change",
            "operating_margin",
            "operating_margin_change",
            "ebitda_margin",
            "accruals_ratio",
            "cash_conversion",
            "asset_turnover",
            "debt_to_equity",
            "interest_coverage",
            "debtor_days",
            "inventory_days",
            "days_payable",
            "cash_conversion_cycle",
            "working_capital_days",
            "promoter_pct",
            "fii_pct",
            "dii_pct",
            "promoter_change_1q",
            "fii_change_1q",
            "institutional_total_pct",
            "et500_rank_change",
        ]
        cs_numeric_cols = [c for c in cs_seed_cols if c in out.columns and pd.api.types.is_numeric_dtype(out[c])]
        out = self._append_cross_sectional_transforms(
            out,
            cs_numeric_cols,
            groups=out["date"],
            clip_abs=6.0,
            coerce_source=False,
        )

        # Directional signals per plan (penalize illiquidity, high beta, lottery tails).
        if "amihud_illiquidity_cs_rank" in out.columns:
            out["amihud_liquidity_rank"] = -pd.to_numeric(out["amihud_illiquidity_cs_rank"], errors="coerce")
        if "bab_beta_cs_rank" in out.columns:
            out["bab_beta_signal"] = -pd.to_numeric(out["bab_beta_cs_rank"], errors="coerce")
        if "max_lottery_21d_cs_rank" in out.columns:
            out["max_lottery_21d_signal"] = -pd.to_numeric(out["max_lottery_21d_cs_rank"], errors="coerce")
        if "max_lottery_5d_cs_rank" in out.columns:
            out["max_lottery_5d_signal"] = -pd.to_numeric(out["max_lottery_5d_cs_rank"], errors="coerce")

        return out

    def _add_academic_factor_features(self, panel: pd.DataFrame, as_of_date: datetime = None) -> pd.DataFrame:
        """
        Add canonical academic factor features for every stock-date row in the panel.

        This uses FactorRegistry as the only source of BAB/Amihud/MAX/Piotroski/
        Earnings Quality values and then recreates any legacy compatibility columns
        from the canonical outputs rather than from duplicate inline calculations.
        """
        if panel.empty:
            return panel

        if not self.use_academic_factors or self._factor_registry is None:
            return panel

        out = panel.copy()
        if 'ticker' not in out.columns or 'date' not in out.columns:
            return out

        out = self._ensure_primary_ticker_column(out)
        out['date'] = pd.to_datetime(out['date'], errors='coerce').dt.normalize()
        base = out.dropna(subset=['date', 'ticker']).copy()
        if base.empty:
            return out

        factor_rows: list[pd.DataFrame] = []
        try:
            for factor_date, group in base.groupby('date', sort=True):
                tickers = sorted(group['ticker'].astype(str).unique().tolist())
                if not tickers:
                    continue
                computed = self._factor_registry.compute_all(
                    as_of_date=pd.Timestamp(factor_date).to_pydatetime(),
                    tickers=tickers,
                    use_cache=True,
                )
                if computed.empty:
                    continue
                frame = computed.reset_index().rename(columns={'index': 'ticker'})
                frame['date'] = pd.Timestamp(factor_date)
                factor_rows.append(frame)
        except Exception as e:
            logger.warning(f"Academic factor features failed for {as_of_date}: {e}")
            return out

        if not factor_rows:
            return out

        factor_features = pd.concat(factor_rows, ignore_index=True)
        factor_features['ticker'] = factor_features['ticker'].map(self._normalize_ticker)
        factor_features['date'] = pd.to_datetime(factor_features['date'], errors='coerce').dt.normalize()

        merge_cols = ['date', 'ticker']
        merge_fields = [c for c in factor_features.columns if c not in merge_cols]
        out = out.merge(factor_features[merge_cols + merge_fields], on=merge_cols, how='left', sort=False)
        out = self._add_legacy_academic_factor_aliases(out)

        if self._factor_feature_columns_mode == 'zscore_only':
            drop_cols = [c for c in merge_fields if c.endswith('_raw') or c.endswith('_rank') or c.endswith('_available')]
            out = out.drop(columns=drop_cols, errors='ignore')
        elif self._factor_feature_columns_mode == 'zscore_and_rank':
            drop_cols = [c for c in merge_fields if c.endswith('_raw') or c.endswith('_available')]
            out = out.drop(columns=drop_cols, errors='ignore')

        if factor_rows:
            logger.info("Added academic factor features for %d dates", len(factor_rows))
        return out

    def _add_legacy_academic_factor_aliases(self, panel: pd.DataFrame) -> pd.DataFrame:
        """Backfill legacy report-facing names from canonical factor outputs."""
        out = panel.copy()

        if 'bab_raw' in out.columns:
            out['bab_beta'] = -pd.to_numeric(out['bab_raw'], errors='coerce')
        if 'bab_zscore' in out.columns:
            out['bab_beta_signal'] = pd.to_numeric(out['bab_zscore'], errors='coerce')

        if 'amihud_raw' in out.columns:
            out['amihud_illiquidity'] = pd.to_numeric(out['amihud_raw'], errors='coerce')
        if 'amihud_rank' in out.columns:
            out['amihud_liquidity_rank'] = -pd.to_numeric(out['amihud_rank'], errors='coerce')

        if 'max_raw' in out.columns:
            max5 = -pd.to_numeric(out['max_raw'], errors='coerce')
            out['max_lottery_top5_21d'] = max5
            out['max_lottery_21d'] = max5
        if 'max_zscore' in out.columns:
            out['max_lottery_21d_signal'] = pd.to_numeric(out['max_zscore'], errors='coerce')
            out['max_lottery_5d_signal'] = pd.to_numeric(out['max_zscore'], errors='coerce')

        if 'piotroski_raw' in out.columns:
            raw = pd.to_numeric(out['piotroski_raw'], errors='coerce')
            out['piotroski_f_score'] = raw
            out['piotroski_f_score_norm'] = raw / 9.0

        if 'earnings_quality_raw' in out.columns:
            out['earnings_quality_score'] = pd.to_numeric(out['earnings_quality_raw'], errors='coerce')

        return out

    def _add_valuation_features(self, panel: pd.DataFrame, as_of_date: datetime | None = None) -> pd.DataFrame:
        """
        Add Screener-backed valuation features to every stock-date row in the panel.
        """
        if panel.empty or not self.use_valuation_features or self._valuation_block is None:
            return panel

        out = panel.copy()
        if "ticker" not in out.columns or "date" not in out.columns:
            return out

        out = self._ensure_primary_ticker_column(out)
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
        base = out.dropna(subset=["date", "ticker"]).copy()
        if base.empty:
            return out

        # Weekly exports keep only each ticker's last row per W-FRI week
        # (resample_daily_panel_to_weekly tail(1)), so valuations computed on
        # any other day are discarded. "weekly_tail" restricts the compute to
        # exactly the surviving (ticker, date) rows — ~5x cheaper, identical
        # weekly output. Off-anchor rows keep NaN val_* in the daily panel.
        cadence = str((self.config.get("valuation", {}) or {}).get("compute_cadence", "daily")).lower()
        if cadence == "weekly_tail":
            week = base["date"].dt.to_period("W-FRI")
            tail_mask = base.groupby(["ticker", week])["date"].transform("max").eq(base["date"])
            n_before = len(base)
            base = base.loc[tail_mask]
            logger.info(
                "[valuation] weekly_tail cadence: %d of %d daily rows selected (%d dates)",
                len(base), n_before, base["date"].nunique(),
            )

        valuation_rows: list[pd.DataFrame] = []
        try:
            for valuation_date, group in base.groupby("date", sort=True):
                tickers = sorted(group["ticker"].astype(str).unique().tolist())
                if not tickers:
                    continue
                price_lookup: dict[str, float] = {}
                if "close" in group.columns:
                    latest_prices = (
                        group.sort_values("ticker", kind="mergesort")
                        .drop_duplicates(subset=["ticker"], keep="last")
                        .set_index("ticker")["close"]
                    )
                    price_lookup = {
                        self._normalize_ticker(ticker): pd.to_numeric(price, errors="coerce")
                        for ticker, price in latest_prices.items()
                    }
                computed = self._valuation_block.compute(
                    as_of_date=pd.Timestamp(valuation_date).to_pydatetime(),
                    tickers=tickers,
                    market_prices=price_lookup,
                    use_cache=True,
                )
                critical_coverage = 0.0
                if not computed.empty and "val_discount_to_fair_pct" in computed.columns:
                    critical_coverage = float(pd.to_numeric(computed["val_discount_to_fair_pct"], errors="coerce").notna().mean())
                # G.5 retry heals a partially-poisoned cache by recomputing the
                # whole date uncached. With a marker-attested precomputed cache
                # (the export path) it is pure waste: cache rows ARE fresh
                # computes, so the retry re-pays ~116ms/ticker to produce the
                # same values — and on sparse 2017-18 dates it alone can blow
                # Kaggle's 12h cap. Gate it.
                retry_enabled = bool((self.config.get("valuation", {}) or {}).get("low_coverage_retry_enabled", True))
                if retry_enabled and (computed.empty or (len(tickers) >= 10 and critical_coverage < 0.40)):
                    # G.5: this uncached recompute doubles valuation cost on the
                    # dates most likely to be sparse; count/log it so its real
                    # frequency is visible rather than silently multiplying cost.
                    self._valuation_retry_count = getattr(self, "_valuation_retry_count", 0) + 1
                    logger.debug(
                        "Valuation low-coverage retry #%d for %s (coverage=%.2f)",
                        self._valuation_retry_count,
                        valuation_date,
                        critical_coverage,
                    )
                    computed = self._valuation_block.compute(
                        as_of_date=pd.Timestamp(valuation_date).to_pydatetime(),
                        tickers=tickers,
                        market_prices=price_lookup,
                        use_cache=False,
                    )
                if computed.empty:
                    continue
                frame = computed.reset_index().rename(columns={"index": "ticker"})
                frame["date"] = pd.Timestamp(valuation_date)
                valuation_rows.append(frame)
        except Exception as e:
            logger.warning(f"Valuation feature block failed for {as_of_date}: {e}")
            try:
                self._valuation_block.flush_cache()
            except Exception:
                pass
            return out

        # I.1: persist the batched valuation cache once at the end of the daily
        # loop instead of rewriting the whole file per date.
        try:
            self._valuation_block.flush_cache()
        except Exception:
            pass

        if not valuation_rows:
            return out

        valuation_features = pd.concat(valuation_rows, ignore_index=True)
        valuation_features["ticker"] = valuation_features["ticker"].map(self._normalize_ticker)
        valuation_features["date"] = pd.to_datetime(valuation_features["date"], errors="coerce").dt.normalize()

        raw_feature_cols = [
            c for c in getattr(self._valuation_block, "FEATURE_NAMES", []) if c in valuation_features.columns
        ]
        zscore_cols = [c for c in valuation_features.columns if c.endswith("_zscore")]
        coverage = valuation_features[raw_feature_cols].notna().mean() if raw_feature_cols else pd.Series(dtype=float)
        low_cov = coverage[coverage < 0.40]
        for col, cov in low_cov.items():
            logger.warning("Valuation feature %s coverage %.1f%% below 40%%", col, float(cov) * 100.0)

        if self._valuation_feature_columns_mode == "raw_and_zscore":
            merge_fields = raw_feature_cols + zscore_cols
        else:
            merge_fields = zscore_cols

        out = out.merge(
            valuation_features[["date", "ticker"] + merge_fields],
            on=["date", "ticker"],
            how="left",
            sort=False,
        )
        if valuation_rows:
            logger.info("Added valuation features for %d dates", len(valuation_rows))
        return out

    def _add_et500_features(
        self,
        panel: pd.DataFrame,
        et500_membership: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        if panel.empty or not bool(self.use_et500_features):
            return panel
        if not isinstance(et500_membership, pd.DataFrame) or et500_membership.empty:
            return panel
        need = {"year", "nse_ticker", "rank", "prev_rank"}
        if not need.issubset(set(et500_membership.columns)):
            return panel

        ref = et500_membership.copy()
        ref["ticker"] = ref["nse_ticker"].map(self._normalize_ticker)
        ref["et500_year"] = pd.to_numeric(ref["year"], errors="coerce")
        ref["et500_rank"] = pd.to_numeric(ref["rank"], errors="coerce")
        ref["et500_prev_rank"] = pd.to_numeric(ref["prev_rank"], errors="coerce")
        ref["et500_rank_change"] = ref["et500_prev_rank"] - ref["et500_rank"]
        ref["et500_availability_date"] = pd.to_datetime(
            ref["et500_year"].astype("Int64").astype("string") + "-12-31",
            errors="coerce",
        )
        ref = ref.dropna(subset=["ticker", "et500_availability_date"]).copy()
        ref = ref.sort_values(["ticker", "et500_availability_date", "et500_rank"], kind="mergesort")
        ref = ref.drop_duplicates(subset=["ticker", "et500_availability_date"], keep="first")
        keep = [
            "ticker",
            "et500_availability_date",
            "et500_rank_change",
        ]
        return self._merge_asof_by_ticker(panel, ref[keep], left_on="date", right_on="et500_availability_date")

    # H.1: _compute_piotroski_features and _compute_earnings_quality_features
    # were removed as dead code — they were never called from build_features()
    # and their column names (piotroski_f_score) did not even match the export
    # (piotroski_fscore). Gap9AcademicFactors is the real, wired-in producer of
    # piotroski_fscore / earnings_quality_ratio and their cs_z/cs_rank variants.

    def _compute_sue_features(self, screener_quarterly: pd.DataFrame) -> pd.DataFrame:
        if screener_quarterly is None or screener_quarterly.empty or "ticker" not in screener_quarterly.columns:
            return pd.DataFrame(columns=["ticker", "availability_date", "eps_sue", "rev_sue"])
        q = screener_quarterly.copy()
        q["ticker"] = q["ticker"].map(self._normalize_ticker)
        has_explicit_availability = "availability_date" in q.columns and pd.to_datetime(
            q["availability_date"], errors="coerce"
        ).notna().any()
        q["availability_date"] = self._as_date(q, ["availability_date", "date", "Date", "quarter"])
        if "quarter" in q.columns and q["availability_date"].isna().all():
            q["availability_date"] = pd.to_datetime(q["quarter"], errors="coerce")
        if "fiscal_year_end" in q.columns:
            q["fiscal_year_end"] = pd.to_datetime(q["fiscal_year_end"], errors="coerce")
        q["quarter_end"] = q["availability_date"]
        if "fiscal_year_end" in q.columns:
            q["quarter_end"] = q["quarter_end"].where(q["quarter_end"].notna(), q["fiscal_year_end"])

        ann_dates = pd.DataFrame()
        if bool(self.use_announcement_dates):
            ann_dates = self._get_announcement_dates()
        ann_date = pd.Series(pd.NaT, index=q.index)
        if not ann_dates.empty:
            ann_dates = ann_dates.dropna(subset=["ticker", "announcement_date"]).copy()
            ann_dates["announcement_date"] = pd.to_datetime(ann_dates["announcement_date"], errors="coerce")
            ann_dates = ann_dates.dropna(subset=["announcement_date"]).sort_values(
                ["ticker", "announcement_date"], kind="mergesort"
            )
            if "fiscal_year_end" in ann_dates.columns and "fiscal_year_end" in q.columns:
                ann_exact = ann_dates.dropna(subset=["fiscal_year_end"]).copy()
                ann_exact["fiscal_year_end"] = pd.to_datetime(ann_exact["fiscal_year_end"], errors="coerce")
                ann_exact = ann_exact.dropna(subset=["fiscal_year_end"])
                ann_exact = (
                    ann_exact.groupby(["ticker", "fiscal_year_end"], sort=False)["announcement_date"]
                    .min()
                    .reset_index()
                )
                merged = q[["ticker", "quarter_end"]].copy()
                merged["fiscal_year_end"] = pd.to_datetime(merged["quarter_end"], errors="coerce")
                merged = merged.merge(ann_exact, on=["ticker", "fiscal_year_end"], how="left")
                merged.index = q.index
                ann_date = merged["announcement_date"].copy()

            for tk, grp in q.groupby("ticker", sort=False):
                ann = ann_dates[ann_dates["ticker"] == tk]
                if ann.empty:
                    continue
                ann_vals = ann["announcement_date"].to_numpy(dtype="datetime64[ns]")
                if ann_vals.size == 0:
                    continue
                q_idx = grp.index
                q_dates = pd.to_datetime(grp["quarter_end"], errors="coerce").to_numpy(dtype="datetime64[ns]")
                mask = ~np.isnat(q_dates)
                if not bool(mask.any()):
                    continue
                existing = pd.to_datetime(ann_date.loc[q_idx], errors="coerce")
                fill_mask = mask.copy()
                if existing.notna().any():
                    fill_mask = mask & (~existing.notna().to_numpy())
                if not bool(fill_mask.any()):
                    continue
                pos = np.searchsorted(ann_vals, q_dates[fill_mask], side="left")
                cand = np.full(fill_mask.sum(), np.datetime64("NaT"), dtype="datetime64[ns]")
                valid_pos = pos < ann_vals.size
                if bool(valid_pos.any()):
                    cand[valid_pos] = ann_vals[pos[valid_pos]]
                cutoff = q_dates[fill_mask] + np.timedelta64(180, "D")
                cand = np.where(cand <= cutoff, cand, np.datetime64("NaT"))
                filled = np.full(q_dates.shape, np.datetime64("NaT"), dtype="datetime64[ns]")
                filled[fill_mask] = cand
                ann_date.loc[q_idx] = pd.to_datetime(filled)

            coverage = float(pd.to_datetime(ann_date, errors="coerce").notna().mean()) if len(ann_date) else 0.0
            if bool(self.require_announcement_dates_for_sue):
                if ann_dates.empty:
                    if not bool(has_explicit_availability):
                        raise ValueError("sue_missing_announcement_dates")
                    logger.warning(
                        "[sue] announcement dates unavailable; falling back to explicit availability_date coverage"
                    )
                elif coverage < float(self.announcement_dates_min_coverage):
                    if not bool(has_explicit_availability):
                        raise ValueError(f"sue_announcement_coverage_low:{coverage:.2f}")
                    logger.warning(
                        "[sue] announcement coverage %.1f%% below threshold %.1f%%; using fallback availability dates",
                        coverage * 100.0,
                        float(self.announcement_dates_min_coverage) * 100.0,
                    )
            if coverage > 0:
                logger.info("[sue] announcement coverage=%.1f%%", coverage * 100.0)

        fallback = pd.to_datetime(q["availability_date"], errors="coerce")
        if not bool(has_explicit_availability):
            fallback = fallback.where(
                fallback.notna(),
                pd.to_datetime(q["quarter_end"], errors="coerce") + pd.Timedelta(days=int(self.pit_fundamental_lag_days)),
            )
        if ann_date.notna().any():
            ann_avail = pd.to_datetime(ann_date, errors="coerce") + pd.Timedelta(
                days=int(self.pit_earnings_announcement_plus_days)
            )
            q["availability_date"] = ann_avail.where(pd.to_datetime(ann_date, errors="coerce").notna(), fallback)
        else:
            q["availability_date"] = fallback

        q = q.dropna(subset=["ticker", "availability_date"]).sort_values(
            ["ticker", "availability_date"], kind="mergesort"
        )
        if q.empty:
            return pd.DataFrame(columns=["ticker", "availability_date", "eps_sue", "rev_sue"])

        eps = pd.to_numeric(q.get("eps_in_rs"), errors="coerce")
        if eps.isna().all():
            return pd.DataFrame(columns=["ticker", "availability_date", "eps_sue", "rev_sue"])
        rev = pd.to_numeric(q.get("revenue", q.get("sales")), errors="coerce")

        eps_surprise = eps - eps.groupby(q["ticker"], sort=False).shift(4)
        eps_std = eps_surprise.groupby(q["ticker"], sort=False).rolling(8, min_periods=4).std().reset_index(level=0, drop=True)
        eps_sue = eps_surprise / eps_std.replace(0.0, np.nan)

        rev_surprise = rev - rev.groupby(q["ticker"], sort=False).shift(4)
        rev_std = rev_surprise.groupby(q["ticker"], sort=False).rolling(8, min_periods=4).std().reset_index(level=0, drop=True)
        rev_sue = rev_surprise / rev_std.replace(0.0, np.nan)

        eps_sue = self._winsorize_series(eps_sue, lower_q=0.05, upper_q=0.95)
        rev_sue = self._winsorize_series(rev_sue, lower_q=0.05, upper_q=0.95)

        out = pd.DataFrame(
            {
                "ticker": q["ticker"].astype(str),
                "availability_date": q["availability_date"],
                "eps_sue": eps_sue,
                "rev_sue": rev_sue,
            }
        )
        out = out.dropna(subset=["ticker", "availability_date"]).drop_duplicates(
            subset=["ticker", "availability_date"], keep="last"
        )
        return out.reset_index(drop=True)

    def build_features(
        self,
        prices: pd.DataFrame,
        fundamentals: Optional[pd.DataFrame] = None,
        screener_annual: Optional[pd.DataFrame] = None,
        screener_quarterly: Optional[pd.DataFrame] = None,
        screener_shareholding: Optional[pd.DataFrame] = None,
        macro: Optional[pd.DataFrame] = None,
        valuation_posterior: Optional[pd.DataFrame] = None,
        sentiment_company: Optional[pd.DataFrame] = None,
        sentiment_market: Optional[pd.DataFrame] = None,
        sector_lookup: Optional[dict[str, str]] = None,
        et500_membership: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        if prices is None or prices.empty:
            return pd.DataFrame()

        p = prices.copy()
        p["date"] = self._as_date(p, ["date", "Date", "timestamp"])
        close_col = "Close" if "Close" in p.columns else ("close" if "close" in p.columns else None)
        if close_col is None or "ticker" not in p.columns:
            return pd.DataFrame()

        p["close"] = pd.to_numeric(p[close_col], errors="coerce")
        p["volume"] = pd.to_numeric(p.get("Volume", p.get("volume", np.nan)), errors="coerce")
        p = p.dropna(subset=["date", "ticker", "close"])
        p = p.loc[p["close"] > 0.0].sort_values(["ticker", "date"])
        if p.empty:
            return pd.DataFrame()

        g = p.groupby("ticker", sort=False)
        p["ret_1d"] = g["close"].pct_change(fill_method=None)
        p["ret_5d"] = g["close"].pct_change(5, fill_method=None)
        p["ret_20d"] = g["close"].pct_change(20, fill_method=None)
        p["vol_20d"] = g["ret_1d"].rolling(20).std().reset_index(level=0, drop=True)
        p["vol_60d"] = g["ret_1d"].rolling(60).std().reset_index(level=0, drop=True)
        # Skip-1 momentum convention avoids 1-day reversal contamination.
        p["mom_5d"] = g["close"].shift(1) / g["close"].shift(6) - 1.0
        p["mom_10d"] = g["close"].shift(1) / g["close"].shift(11) - 1.0
        p["mom_20d"] = g["close"].shift(1) / g["close"].shift(21) - 1.0
        p["mom_60d"] = g["close"].shift(1) / g["close"].shift(61) - 1.0
        p["price_to_sma20"] = p["close"] / g["close"].rolling(20).mean().reset_index(level=0, drop=True)

        if p["volume"].notna().any():
            vol_roll = g["volume"].rolling(20)
            p["vol_z20"] = (
                p["volume"] - vol_roll.mean().reset_index(level=0, drop=True)
            ) / (vol_roll.std().reset_index(level=0, drop=True) + 1e-12)
        else:
            p["vol_z20"] = 0.0

        vol5 = pd.to_numeric(p["volume"], errors="coerce").groupby(p["ticker"], sort=False).rolling(5, min_periods=3).mean().reset_index(level=0, drop=True)
        vol63 = pd.to_numeric(p["volume"], errors="coerce").groupby(p["ticker"], sort=False).rolling(63, min_periods=20).mean().reset_index(level=0, drop=True)
        p["vol_surge_5d"] = vol5 / (vol63 + 1e-12)

        p["mom_63d_1m_lag"] = np.log(
            (g["close"].shift(21) / g["close"].shift(63)).replace([np.inf, -np.inf], np.nan)
        )

        p["forward_return_5d"] = g["close"].shift(-self.target_horizon_days) / p["close"] - 1.0

        panel = p[
            [
                "date",
                "ticker",
                "close",
                "volume",
                "ret_1d",
                "ret_5d",
                "ret_20d",
                "vol_20d",
                "vol_60d",
                "mom_5d",
                "mom_10d",
                "mom_20d",
                "mom_60d",
                "mom_63d_1m_lag",
                "price_to_sma20",
                "vol_z20",
                "vol_surge_5d",
                "forward_return_5d",
            ]
        ].copy()

        if isinstance(fundamentals, pd.DataFrame) and not fundamentals.empty:
            f = fundamentals.copy()
            # The canonical fundamentals panel dates its rows with `report_date`
            # (not `date`), so the old candidate list left fundamental_date all-NaN
            # and the merge_asof below matched nothing — silently emptying the
            # entire fundamentals family (accruals_ratio, roe, operating_margin,
            # earnings_quality...). Include report_date, and prefer the canonical
            # PIT-correct availability_date when it is already present.
            f["fundamental_date"] = self._as_date(
                f, ["date", "Date", "timestamp", "report_date", "fiscal_quarter_end_date", "screener_report_date"]
            )
            existing_avail = (
                pd.to_datetime(f["availability_date"], errors="coerce")
                if "availability_date" in f.columns else pd.Series(pd.NaT, index=f.index)
            )
            ann = self._as_date(
                f,
                [
                    "announcement_date",
                    "announcementDate",
                    "results_announcement_date",
                    "results_announced_at",
                    "report_announcement_date",
                ],
            )
            has_announcement = bool(self.use_announcement_dates and ann.notna().any())
            if bool(self.enable_pit_fundamentals):
                if has_announcement:
                    availability = ann + pd.Timedelta(days=int(self.pit_financials_plus_days))
                else:
                    availability = f["fundamental_date"] + pd.Timedelta(days=int(self.pit_fundamental_lag_days))
            else:
                availability = f["fundamental_date"]
            availability = pd.to_datetime(availability, errors="coerce")
            # Fall back to the canonical availability_date wherever our computed one
            # is missing (e.g. fundamental_date still NaN for an odd row).
            f["availability_date"] = availability.fillna(existing_avail)
            needed = [
                "fundamental_date",
                "availability_date",
                "ticker",
                "Industry",
                "industry",
                "Sector",
                "sector",
                "revenue",
                "ebitda",
                "operating_income",
                "net_income",
                "equity",
                "total_assets",
                "total_debt",
                "operating_cash_flow",
                "free_cash_flow",
                "interest_expense",
                "shares_outstanding",
                "gross_profit",
                "cost_of_revenue",
                "working_capital",
                "cash_and_equivalents",
                "receivables",
                "inventory",
                "payables",
                "deferred_revenue",
                "lease_liabilities",
            ]
            keep = [c for c in needed if c in f.columns]
            f = f[keep].copy()
            non_numeric_cols = {
                "fundamental_date",
                "availability_date",
                "ticker",
                "Industry",
                "industry",
                "Sector",
                "sector",
            }
            for c in keep:
                if c not in non_numeric_cols:
                    f[c] = pd.to_numeric(f[c], errors="coerce")
            panel = self._merge_asof_by_ticker(panel, f, left_on="date", right_on="availability_date")
            def _safe_ratio(numerator: pd.Series, denominator: pd.Series, *, min_abs_denominator: float = 1e-6) -> pd.Series:
                den = pd.to_numeric(denominator, errors="coerce").astype(float)
                num = pd.to_numeric(numerator, errors="coerce").astype(float)
                safe_den = den.where(den.abs() >= float(min_abs_denominator))
                return (num / safe_den).replace([np.inf, -np.inf], np.nan)

            if {"net_income", "revenue"}.issubset(set(panel.columns)):
                panel["ni_margin"] = _safe_ratio(panel["net_income"], panel["revenue"])
            if {"total_debt", "equity"}.issubset(set(panel.columns)):
                panel["debt_to_equity"] = _safe_ratio(panel["total_debt"], panel["equity"])
            if {"free_cash_flow", "operating_cash_flow"}.issubset(set(panel.columns)):
                panel["fcf_to_ocf"] = _safe_ratio(panel["free_cash_flow"], panel["operating_cash_flow"])
            panel = self._add_fundamental_factor_features(panel)

            # Canonical academic factor features are merged later via FactorRegistry.

        if isinstance(screener_quarterly, pd.DataFrame) and not screener_quarterly.empty:
            sue = self._compute_sue_features(screener_quarterly)
            if not sue.empty:
                sue = sue.rename(columns={"availability_date": "sue_availability_date"})
                panel = self._merge_asof_by_ticker(panel, sue, left_on="date", right_on="sue_availability_date")
                if "sue_availability_date" in panel.columns:
                    sue_date = pd.to_datetime(panel["sue_availability_date"], errors="coerce")
                    cur = pd.to_datetime(panel["date"], errors="coerce")
                    days_since = (cur - sue_date).dt.days
                    decay = (1.0 - (days_since / 63.0)).clip(lower=0.0, upper=1.0)
                    if "eps_sue" in panel.columns:
                        panel["eps_sue_decay"] = pd.to_numeric(panel["eps_sue"], errors="coerce") * decay
                    if "rev_sue" in panel.columns:
                        panel["rev_sue_decay"] = pd.to_numeric(panel["rev_sue"], errors="coerce") * decay
                    if {"eps_sue", "rev_sue"}.issubset(set(panel.columns)):
                        panel["combined_sue"] = 0.5 * pd.to_numeric(panel["eps_sue"], errors="coerce") + 0.5 * pd.to_numeric(panel["rev_sue"], errors="coerce")
                panel = panel.drop(columns=["sue_availability_date"], errors="ignore")
        if bool(self.use_screener_features):
            panel = self._merge_screener_annual(panel, screener_annual=screener_annual)
            panel = self._merge_screener_shareholding(panel, screener_shareholding=screener_shareholding)

        if bool(self.use_alternative_features):
            try:
                from src.signals.signal_loader import AlternativeDataLoader
                from src.signals.feature_builder import AlternativeFeatureBuilder

                alt_loader = AlternativeDataLoader(
                    {
                        **self.config,
                        "alternative_data_path": self.alternative_data_path,
                    }
                )
                print("[progress]   ...alternative/bulk-deal features", flush=True)
                alt_features = alt_loader.get_features_as_of_frame(panel)
                if isinstance(alt_features, pd.DataFrame) and not alt_features.empty:
                    # Debug coverage for alternative features.
                    bulk_cols = [c for c in alt_features.columns if str(c).startswith("bulk_")]
                    pledge_cols = [c for c in alt_features.columns if str(c).startswith("pledge_")]
                    rating_cols = [c for c in alt_features.columns if str(c).startswith("rating_")]
                    any_mask = alt_features.notna().any(axis=1)
                    bulk_rows = int(alt_features[bulk_cols].notna().any(axis=1).sum()) if bulk_cols else 0
                    pledge_rows = int(alt_features[pledge_cols].notna().any(axis=1).sum()) if pledge_cols else 0
                    rating_rows = int(alt_features[rating_cols].notna().any(axis=1).sum()) if rating_cols else 0
                    matched_tickers = int(panel.loc[any_mask, "ticker"].nunique()) if bool(any_mask.any()) else 0
                    logger.info(
                        "alt_features_joined bulk_deal_rows=%d pledge_rows=%d ratings_rows=%d matched_tickers=%d",
                        bulk_rows,
                        pledge_rows,
                        rating_rows,
                        matched_tickers,
                    )

                    col_to_family: dict[str, str] = {}
                    for fam, fam_cols in AlternativeFeatureBuilder.FEATURE_GROUPS.items():
                        for c in fam_cols:
                            col_to_family[str(c)] = str(fam)
                    raw_updates: dict[str, pd.Series] = {}
                    cs_updates: dict[str, pd.Series] = {}
                    family_counts: dict[str, int] = {}
                    for col in alt_features.columns:
                        fam = col_to_family.get(str(col))
                        if fam and not self._is_alternative_family_enabled(fam):
                            continue
                        series = pd.to_numeric(alt_features[col], errors="coerce")
                        if len(series) != len(panel):
                            continue
                        series = pd.Series(series.to_numpy(), index=panel.index, dtype=float)
                        # Skip empty columns so missing/disabled families do not
                        # silently become zeroed cross-sectional signals.
                        if not bool(series.notna().any()):
                            continue
                        raw_updates[str(col)] = series
                        if fam:
                            family_counts[str(fam)] = int(family_counts.get(str(fam), 0) + 1)
                        cs_updates[f"{col}_cs_z"] = self._group_zscore(series, panel["date"], clip_abs=6.0)
                        cs_updates[f"{col}_cs_rank"] = self._group_rank_centered(series, panel["date"])
                    if raw_updates:
                        panel = panel.copy()
                        panel.loc[:, list(raw_updates.keys())] = pd.DataFrame(raw_updates, index=panel.index)
                        panel = self._concat_new_columns(panel, cs_updates)
                        logger.info(
                            "[alternative] merged raw_cols=%d cs_cols=%d family_counts=%s",
                            int(len(raw_updates)),
                            int(len(cs_updates)),
                            dict(sorted(family_counts.items())),
                        )
                    else:
                        logger.info("[alternative] enabled but no usable alternative columns were merged")
            except Exception as exc:  # noqa: BLE001
                logger.warning("[alternative] feature merge skipped: %s", exc)

        if isinstance(macro, pd.DataFrame) and not macro.empty:
            m = macro.copy()
            m["date"] = self._as_date(m, ["date", "Date", "timestamp", "intelligence_timestamp_str"])
            m = m.dropna(subset=["date"]).sort_values("date")

            # Prefix numeric macro columns to prevent collisions.
            # F.2: skip all-null columns so a legacy/aspirational macro schema
            # (e.g. never-populated sentiment_* fields) does not import ~76 dead
            # macro_* columns that repairs then discard every build.
            macro_numeric = [
                c
                for c in m.columns
                if c != "date"
                and pd.api.types.is_numeric_dtype(m[c])
                and bool(pd.to_numeric(m[c], errors="coerce").notna().any())
            ]
            rename = {c: f"macro_{c}" for c in macro_numeric}
            m = m.rename(columns=rename)

            # Keep one daily record for asof merge.
            merge_cols = ["date"] + list(rename.values())
            m = m[merge_cols].drop_duplicates(subset=["date"], keep="last")
            panel = pd.merge_asof(panel.sort_values("date"), m.sort_values("date"), on="date", direction="backward")
            panel = self._ensure_primary_ticker_column(panel)

            if "macro_regime" in macro.columns:
                regime = macro[["date", "macro_regime"]].copy()
                regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
                regime = regime.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
                panel = pd.merge_asof(panel.sort_values("date"), regime.sort_values("date"), on="date", direction="backward")
            elif "regime" in macro.columns:
                regime = macro[["date", "regime"]].copy()
                regime["date"] = pd.to_datetime(regime["date"], errors="coerce")
                regime = regime.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last")
                panel = pd.merge_asof(panel.sort_values("date"), regime.sort_values("date"), on="date", direction="backward")

        if isinstance(valuation_posterior, pd.DataFrame) and not valuation_posterior.empty:
            v = valuation_posterior.copy()
            v["date"] = self._as_date(v, ["date", "Date", "timestamp"])
            keep = [
                c
                for c in [
                    "date",
                    "ticker",
                    "posterior_gap",
                    "posterior_variance",
                    "agreement_score",
                    "posterior_confidence",
                    "regime_modifier",
                    "macro_compression",
                ]
                if c in v.columns
            ]
            v = v[keep].copy()
            for c in keep:
                if c not in {"date", "ticker"}:
                    v[c] = pd.to_numeric(v[c], errors="coerce")
            panel = self._merge_asof_by_ticker(panel, v)

        if isinstance(sentiment_company, pd.DataFrame) and not sentiment_company.empty:
            s = sentiment_company.copy()
            s["date"] = self._as_date(s, ["date", "Date", "timestamp"])
            if "ticker" not in s.columns and "symbol" in s.columns:
                s["ticker"] = s["symbol"].astype(str)
            if "ticker" in s.columns:
                s["ticker"] = s["ticker"].astype(str)
            keep = [
                c
                for c in [
                    "date",
                    "ticker",
                    "sentiment_score",
                    "trend_score",
                    "event_shock_factor",
                    "headline_count",
                    "sentiment_intensity",
                    "signed_sentiment_intensity",
                    "northstar_score",
                    "momentum_score",
                    "mispricing",
                    "confirmation",
                    "cohesive_alpha_score",
                ]
                if c in s.columns
            ]
            if {"date", "ticker"}.issubset(set(keep)):
                s = s[keep].copy()
                for c in keep:
                    if c not in {"date", "ticker"}:
                        s[c] = pd.to_numeric(s[c], errors="coerce")
                rename = {c: f"sent_{c}" for c in s.columns if c not in {"date", "ticker"}}
                s = s.rename(columns=rename)
                panel = self._merge_asof_by_ticker(panel, s)

        if isinstance(sentiment_market, pd.DataFrame) and not sentiment_market.empty:
            ms = sentiment_market.copy()
            ms["date"] = self._as_date(ms, ["date", "Date", "timestamp"])
            keep = [
                c
                for c in [
                    "date",
                    "polarity",
                    "conviction",
                    "uncertainty",
                    "narrative_cohesion",
                    "policy_weight",
                    "narrative_conflict",
                    "delta_polarity",
                    "delta_uncertainty",
                    "delta_conviction",
                    "change_velocity",
                    "micro_shift_score",
                ]
                if c in ms.columns
            ]
            if "date" in keep:
                ms = ms[keep].copy()
                for c in keep:
                    if c != "date":
                        ms[c] = pd.to_numeric(ms[c], errors="coerce")
                rename = {c: f"mkt_sent_{c}" for c in ms.columns if c != "date"}
                ms = ms.rename(columns=rename)
                ms = ms.dropna(subset=["date"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")
                panel_sorted = panel.sort_values("date").copy()
                panel_sorted["date"] = pd.to_datetime(panel_sorted["date"], errors="coerce").astype("datetime64[ns]")
                ms_sorted = ms.sort_values("date").copy()
                ms_sorted["date"] = pd.to_datetime(ms_sorted["date"], errors="coerce").astype("datetime64[ns]")
                panel = pd.merge_asof(
                    panel_sorted,
                    ms_sorted,
                    on="date",
                    direction="backward",
                )

        nifty_daily = self._load_nifty_series()
        if not nifty_daily.empty:
            n = nifty_daily.copy()
            n = n.rename(columns={"close": "nifty_close"})
            n["nifty_sma_200"] = n["nifty_close"].rolling(200, min_periods=60).mean()
            n["nifty_above_200d"] = (n["nifty_close"] > n["nifty_sma_200"]).astype(float)
            panel = pd.merge_asof(
                panel.sort_values("date"),
                n[["date", "nifty_close", "nifty_sma_200", "nifty_above_200d"]].sort_values("date"),
                on="date",
                direction="backward",
            )

        vix_daily = self._load_india_vix_series()
        if not vix_daily.empty:
            v = vix_daily.copy()
            v["vix_63d_mean"] = v["vix"].rolling(63, min_periods=20).mean()
            v["vix_63d_std"] = v["vix"].rolling(63, min_periods=20).std().replace(0.0, np.nan)
            v["india_vix_z"] = (v["vix"] - v["vix_63d_mean"]) / (v["vix_63d_std"] + 1e-12)
            v["india_vix_norm"] = self._winsorize_series(v["india_vix_z"], lower_q=0.01, upper_q=0.99)
            v = v.rename(columns={"vix": "india_vix"})
            panel = pd.merge_asof(
                panel.sort_values("date"),
                v[["date", "india_vix", "india_vix_z", "india_vix_norm"]].sort_values("date"),
                on="date",
                direction="backward",
            )

        if bool(self.use_sentiment_features):
            panel = self._merge_sentiment_training_features(panel)

        panel = self._ensure_primary_ticker_column(panel)
        panel = self._apply_sector_lookup(panel, sector_lookup)
        if bool(self.use_macro_features):
            panel = self._merge_macro_feature_pack(panel)
            panel = self._ensure_primary_ticker_column(panel)
        panel = self._merge_credit_feature_pack(panel)
        panel = self._ensure_primary_ticker_column(panel)
        panel = self.apply_sentiment_feature_mode(panel)
        panel = self._add_et500_features(panel, et500_membership)
        panel = self._ensure_primary_ticker_column(panel)
        panel["trade_date"] = panel["date"]

        if self.use_gap9_academic_factors:
            panel = self._gap9_academic_block.transform(panel)

        # Gap 9: Add academic factor features before structural transforms so the
        # canonical factor outputs are the only source of these signals.
        if self.use_academic_factors:
            print("[progress]   ...academic factor features", flush=True)
            as_of_date = pd.to_datetime(panel["date"], errors="coerce").max() if "date" in panel.columns else None
            panel = self._add_academic_factor_features(panel, as_of_date)
        if self.use_valuation_features:
            print("[progress]   ...valuation features", flush=True)
            as_of_date = pd.to_datetime(panel["date"], errors="coerce").max() if "date" in panel.columns else None
            panel = self._add_valuation_features(panel, as_of_date)

        if {"shares_outstanding", "amihud_illiquidity", "close"}.issubset(set(panel.columns)):
            mcap = (
                pd.to_numeric(panel["close"], errors="coerce")
                * pd.to_numeric(panel["shares_outstanding"], errors="coerce")
            )
            size = np.log(mcap.replace(0.0, np.nan))
            panel["size_x_amihud"] = pd.to_numeric(panel["amihud_illiquidity"], errors="coerce") * size

        panel = self._add_structural_alpha_features(panel)

        if {"availability_date", "trade_date"}.issubset(set(panel.columns)):
            av = pd.to_datetime(panel["availability_date"], errors="coerce")
            td = pd.to_datetime(panel["trade_date"], errors="coerce")
            mask = av.notna() & td.notna()
            if bool(mask.any()) and not bool((av[mask] <= td[mask]).all()):
                raise ValueError("pit_leak_detected:availability_date_after_trade_date")

        for av_col in ["screener_availability_date", "screener_shareholding_availability_date"]:
            if {av_col, "trade_date"}.issubset(set(panel.columns)):
                av = pd.to_datetime(panel[av_col], errors="coerce")
                td = pd.to_datetime(panel["trade_date"], errors="coerce")
                mask = av.notna() & td.notna()
                if bool(mask.any()) and not bool((av[mask] <= td[mask]).all()):
                    raise ValueError(f"pit_leak_detected:{av_col}_after_trade_date")

        # Replace non-finite values only on numeric columns; object columns may
        # legitimately contain array-like payloads from upstream artifacts.
        numeric_cols = list(panel.select_dtypes(include=[np.number]).columns)
        if numeric_cols:
            panel.loc[:, numeric_cols] = panel[numeric_cols].replace([np.inf, -np.inf], np.nan)
        panel = self._ensure_primary_ticker_column(panel)
        if "ticker" not in panel.columns:
            raise ValueError("feature_panel_missing_ticker")
        panel = panel.sort_values(["date", "ticker"])
        if bool(self.config.get("drop_unlabeled_target_rows", True)):
            panel = panel.dropna(subset=["forward_return_5d"])
        return panel

    def build_feature_matrix(
        self,
        as_of_date: datetime | str,
        universe_tickers: list[str],
        *,
        lookback_days: int = 420,
    ) -> pd.DataFrame:
        """
        Convenience wrapper that builds the latest cross-sectional feature matrix.

        This uses the canonical ingestion registry and returns one row per ticker
        for the requested as-of date.
        """
        from src.ingestion import IngestionRegistry

        as_of_ts = pd.Timestamp(as_of_date).normalize()
        registry = IngestionRegistry(self.config)
        tickers = [self._normalize_ticker(t) for t in list(universe_tickers or [])]

        prices = registry.market.load(
            as_of_date=as_of_ts.to_pydatetime(),
            tickers=tickers,
            start_date=(as_of_ts - pd.Timedelta(days=int(max(60, lookback_days)))).to_pydatetime(),
        )
        price_frame = prices.reset_index() if isinstance(prices.index, pd.MultiIndex) else prices.copy()
        if 'Ticker' in price_frame.columns and 'ticker' not in price_frame.columns:
            price_frame = price_frame.rename(columns={'Ticker': 'ticker'})

        fundamentals = registry.fundamentals.load_financials(
            as_of_date=as_of_ts.to_pydatetime(),
            tickers=tickers,
            frequency='annual',
        )
        fundamentals = fundamentals.reset_index() if isinstance(fundamentals.index, pd.MultiIndex) else fundamentals.copy()
        if 'Ticker' in fundamentals.columns and 'ticker' not in fundamentals.columns:
            fundamentals = fundamentals.rename(columns={'Ticker': 'ticker'})

        screener_quarterly = registry.fundamentals._load_factor_panel('quarterly')
        if isinstance(screener_quarterly, pd.DataFrame) and not screener_quarterly.empty:
            screener_quarterly = screener_quarterly[
                screener_quarterly['ticker'].isin(tickers)
                & (pd.to_datetime(screener_quarterly.get('availability_date'), errors='coerce') <= as_of_ts)
            ].copy()

        screener_shareholding = registry.fundamentals._load_factor_panel('shareholding')
        if isinstance(screener_shareholding, pd.DataFrame) and not screener_shareholding.empty:
            screener_shareholding = screener_shareholding[
                screener_shareholding['ticker'].isin(tickers)
                & (pd.to_datetime(screener_shareholding.get('availability_date'), errors='coerce') <= as_of_ts)
            ].copy()

        use_academic_factors = self.use_academic_factors
        try:
            # build_features() can span long histories to compute rolling price features.
            # For the one-date convenience wrapper we add canonical factor features only
            # on the final slice to avoid recomputing every factor on every historical row.
            self.use_academic_factors = False
            panel = self.build_features(
                prices=price_frame,
                fundamentals=fundamentals,
                screener_quarterly=screener_quarterly,
                screener_shareholding=screener_shareholding,
            )
        finally:
            self.use_academic_factors = use_academic_factors
        if panel.empty:
            return pd.DataFrame(index=tickers)

        panel_dates = pd.to_datetime(panel['date'], errors='coerce').dt.normalize()
        valid_dates = panel_dates[panel_dates <= as_of_ts]
        if valid_dates.empty:
            return pd.DataFrame(index=tickers)
        latest_date = valid_dates.max()
        latest = panel[panel_dates == latest_date].copy()
        latest = latest[latest['ticker'].isin(tickers)].copy()
        if use_academic_factors:
            latest = self._add_academic_factor_features(latest, latest_date.to_pydatetime())
        latest = latest.drop_duplicates(subset=['ticker'], keep='last').set_index('ticker')
        return latest.reindex(tickers)

    @staticmethod
    def build_tft_feature_split(
        panel: pd.DataFrame,
        *,
        target_col: str = "forward_return_5d",
    ) -> dict:
        """Create TFT-style static/known/observed feature groups.

        Returns a dict with:
        - static_features/static_feature_names
        - known_dynamic_features/known_dynamic_feature_names
        - observed_dynamic_features/observed_dynamic_feature_names
        - ticker_ids/sector_ids
        """
        if panel is None or panel.empty:
            return {
                "static_features": np.empty((0, 0), dtype=np.float32),
                "known_dynamic_features": np.empty((0, 0), dtype=np.float32),
                "observed_dynamic_features": np.empty((0, 0), dtype=np.float32),
                "static_feature_names": [],
                "known_dynamic_feature_names": [],
                "observed_dynamic_feature_names": [],
                "ticker_ids": np.empty((0,), dtype=np.int64),
                "sector_ids": np.empty((0,), dtype=np.int64),
            }

        df = panel.copy()
        if "date" not in df.columns:
            raise ValueError("panel must include date column for TFT split")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).copy()

        # ------------------------------------------------------------------
        # Known dynamic features: calendar/expiry-cycle terms known in advance.
        # ------------------------------------------------------------------
        dt = df["date"]
        dow = dt.dt.dayofweek.astype(float)
        month = dt.dt.month.astype(float)
        dom = dt.dt.day.astype(float)
        woy = dt.dt.isocalendar().week.astype(float)

        # India weekly index options mostly expire Thursday; create a deterministic
        # countdown feature [0..6] so model can learn expiry-cycle behavior.
        # weekday: Mon=0 ... Sun=6
        days_to_thu = ((3 - dt.dt.dayofweek) % 7).astype(float)

        known = pd.DataFrame(
            {
                "known_dow_sin": np.sin(2.0 * np.pi * dow / 7.0),
                "known_dow_cos": np.cos(2.0 * np.pi * dow / 7.0),
                "known_month_sin": np.sin(2.0 * np.pi * month / 12.0),
                "known_month_cos": np.cos(2.0 * np.pi * month / 12.0),
                "known_dom_sin": np.sin(2.0 * np.pi * dom / 31.0),
                "known_dom_cos": np.cos(2.0 * np.pi * dom / 31.0),
                "known_woy_sin": np.sin(2.0 * np.pi * woy / 52.0),
                "known_woy_cos": np.cos(2.0 * np.pi * woy / 52.0),
                "known_is_month_start": dt.dt.is_month_start.astype(float),
                "known_is_month_end": dt.dt.is_month_end.astype(float),
                "known_days_to_weekly_expiry": days_to_thu,
            },
            index=df.index,
        )

        # ------------------------------------------------------------------
        # Static features: slow-moving firm characteristics + valuation confidence.
        # ------------------------------------------------------------------
        static_candidates = [
            "ni_margin",
            "debt_to_equity",
            "fcf_to_ocf",
            "equity",
            "total_debt",
            "shares_outstanding",
            "posterior_confidence",
            "posterior_variance",
            "agreement_score",
            "macro_compression",
            "regime_modifier",
        ]
        static_cols = [c for c in static_candidates if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        static_df = df[static_cols].copy() if static_cols else pd.DataFrame(index=df.index)

        # ------------------------------------------------------------------
        # Observed dynamic features: market/macro/valuation terms only known at t.
        # ------------------------------------------------------------------
        base_observed = [
            "close",
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "vol_20d",
            "vol_60d",
            "mom_20d",
            "mom_60d",
            "price_to_sma20",
            "vol_z20",
            "posterior_gap",
            "posterior_variance",
            "agreement_score",
            "regime_code",
        ]
        macro_cols = [c for c in df.columns if c.startswith("macro_") and pd.api.types.is_numeric_dtype(df[c])]
        sentiment_cols = [
            c
            for c in df.columns
            if (c.startswith("sent_") or c.startswith("mkt_sent_")) and pd.api.types.is_numeric_dtype(df[c])
        ]
        observed_cols = [c for c in base_observed + macro_cols + sentiment_cols if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
        # Ensure no target leakage.
        observed_cols = [c for c in observed_cols if c != target_col and not c.startswith("forward_return")]
        observed_df = df[observed_cols].copy() if observed_cols else pd.DataFrame(index=df.index)

        # ------------------------------------------------------------------
        # Static categorical ids for embeddings.
        # ------------------------------------------------------------------
        ticker_codes = (
            sector_string(df["ticker"]).astype("category").cat.codes.astype(np.int64)
            if "ticker" in df.columns
            else np.zeros(len(df), dtype=np.int64)
        )

        sector_col = None
        for c in ["Industry", "industry", "Sector", "sector"]:
            if c in df.columns:
                sector_col = c
                break
        if sector_col is None:
            sector_codes = np.zeros(len(df), dtype=np.int64)
        else:
            sector_codes = sector_string(df[sector_col]).astype("category").cat.codes.astype(np.int64)

        def _to_numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
            if frame.empty:
                return frame
            out = frame.replace([np.inf, -np.inf], np.nan)
            out = out.apply(pd.to_numeric, errors="coerce")
            return out

        static_df = _to_numeric_frame(static_df)
        known = _to_numeric_frame(known)
        observed_df = _to_numeric_frame(observed_df)

        return {
            "static_features": static_df.to_numpy(dtype=np.float32) if not static_df.empty else np.empty((len(df), 0), dtype=np.float32),
            "known_dynamic_features": known.to_numpy(dtype=np.float32) if not known.empty else np.empty((len(df), 0), dtype=np.float32),
            "observed_dynamic_features": observed_df.to_numpy(dtype=np.float32) if not observed_df.empty else np.empty((len(df), 0), dtype=np.float32),
            "static_feature_names": list(static_df.columns),
            "known_dynamic_feature_names": list(known.columns),
            "observed_dynamic_feature_names": list(observed_df.columns),
            "ticker_ids": np.asarray(ticker_codes, dtype=np.int64),
            "sector_ids": np.asarray(sector_codes, dtype=np.int64),
        }
