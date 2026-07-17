"""
ValuationFeatureBlock — Screener-backed valuation features for research.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.valuation.aggregation import BayesianValuationAggregator
from src.valuation.buffett_module.moat_score import MoatScorer
from src.valuation.core.normalized_financials import FinancialNormalizer
from src.valuation.forensic.earnings_quality import EarningsQualityAnalyzer
from src.valuation.intrinsic_value.dcf_engine import DCFEngine

logger = logging.getLogger(__name__)


class ValuationFeatureBlock:
    """
    Bridge the valuation stack into research-ready cross-sectional features.
    """

    FEATURE_NAMES = [
        "val_discount_to_fair_pct",
        "val_margin_of_safety",
        "val_owner_earnings_yield",
        "val_dcf_confidence",
        "val_moat_score",
        "val_roce_5yr_avg",
        "val_revenue_cagr_5yr",
        "val_earnings_consistency",
        "val_earnings_quality_score",
        "val_accruals_ratio",
        "val_debt_safety_score",
        "val_interest_coverage",
        "val_composite_score",
        "val_quality_composite",
        "val_safety_composite",
    ]

    CACHE_PATH = Path("data/processed/valuation_scores.parquet")

    def __init__(self, config: Optional[dict] = None):
        self._config = dict(config or {})
        self._valuation_cfg = self._config.get("valuation", {}) or {}
        self._normalizer = FinancialNormalizer(self._config)
        self._dcf = DCFEngine(config=self._config)
        self._moat = MoatScorer(self._config)
        self._eq = EarningsQualityAnalyzer(self._config)
        self._aggregator = BayesianValuationAggregator()
        # I.1: keep the accumulated cache in memory and flush to disk in batches
        # instead of reading + rewriting the entire cache file on every daily
        # date (which is quadratic in the number of dates). ``_cache_frame`` is
        # loaded once, updated in memory, and persisted every
        # ``_cache_flush_every`` writes plus on an explicit ``flush_cache()``.
        self._cache_frame: Optional[pd.DataFrame] = None
        self._cache_loaded = False
        self._cache_dirty = False
        self._pending_writes = 0
        self._cache_flush_every = int(self._valuation_cfg.get("cache_flush_every", 50) or 50)

    def compute(
        self,
        as_of_date: datetime,
        tickers: list[str],
        market_prices: dict,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        requested = [str(t) for t in (tickers or [])]

        # I.2: split the request into tickers already cached for this date and
        # the ones that must be computed. Previously a single missing ticker
        # rejected the whole cache entry and forced a full recompute of every
        # ticker for the date.
        cached_raw = self._load_cached_raw(as_of_date, requested) if use_cache else None
        have = set(cached_raw.index.astype(str)) if cached_raw is not None else set()
        missing = [t for t in requested if t not in have]

        rows: dict[str, dict] = {}
        for ticker in missing:
            try:
                rows[str(ticker)] = self._compute_ticker(
                    str(ticker),
                    as_of_date,
                    pd.to_numeric(market_prices.get(str(ticker)), errors="coerce"),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Valuation features failed for %s on %s: %s", ticker, as_of_date, exc)
                rows[str(ticker)] = {name: np.nan for name in self.FEATURE_NAMES}

        computed = pd.DataFrame.from_dict(rows, orient="index") if rows else pd.DataFrame(columns=self.FEATURE_NAMES)
        computed.index.name = "ticker"

        # Persist only the newly-computed raw rows to the cache (in-memory,
        # batched to disk). Cache stores raw features only; z-scores are always
        # recomputed fresh over the requested set below.
        if use_cache and not computed.empty:
            self._store_raw_rows(as_of_date, computed)

        # Assemble raw features for the full requested ticker set.
        parts: list[pd.DataFrame] = []
        if cached_raw is not None and not cached_raw.empty:
            parts.append(cached_raw)
        if not computed.empty:
            parts.append(computed[[c for c in self.FEATURE_NAMES if c in computed.columns]])
        raw = pd.concat(parts, axis=0) if parts else pd.DataFrame(columns=self.FEATURE_NAMES)
        if not raw.empty:
            raw = raw[~raw.index.astype(str).duplicated(keep="last")]
        df = raw.reindex(requested)
        df.index.name = "ticker"
        for col in self.FEATURE_NAMES:
            if col not in df.columns:
                df[col] = np.nan
            df[col] = pd.to_numeric(df[col], errors="coerce")

        for col in self.FEATURE_NAMES:
            series = pd.to_numeric(df[col], errors="coerce")
            non_null = series.dropna()
            if len(non_null) >= 10:
                mean = float(non_null.mean())
                std = float(non_null.std())
                if np.isfinite(std) and std > 0:
                    series = series.clip(lower=mean - 3.0 * std, upper=mean + 3.0 * std)
                    df[col] = series
                    z = (series - float(series.dropna().mean())) / (float(series.dropna().std()) + 1e-9)
                    df[f"{col}_zscore"] = z
                    continue
            df[f"{col}_zscore"] = np.nan

        return df[[*self.FEATURE_NAMES, *[f"{c}_zscore" for c in self.FEATURE_NAMES]]]

    def _compute_ticker(
        self,
        ticker: str,
        as_of_date: datetime,
        current_price: Optional[float],
    ) -> dict:
        fin = self._normalizer.load_latest(ticker, as_of_date, "annual")
        history = self._normalizer.load_history(ticker, as_of_date, n_periods=10, frequency="annual")
        if not fin:
            return {name: np.nan for name in self.FEATURE_NAMES}
        # PIT-CRITICAL: use only the point-in-time price passed in (from the
        # research panel for this as_of_date). Do NOT fall back to
        # ``fin.get("current_price")`` — that field is today's Screener snapshot
        # price and would value historical rows at a future price, leaking into
        # val_discount_to_fair_pct / val_margin_of_safety. If no PIT price is
        # available for this ticker/date, those features stay NaN.
        effective_price = pd.to_numeric(current_price, errors="coerce")

        features = {name: np.nan for name in self.FEATURE_NAMES}
        dcf_result: dict[str, float] = {}
        moat_result: dict[str, float] = {}
        eq_result: dict[str, float] = {}

        try:
            dcf_result = self._dcf.run(
                ticker=ticker,
                fin=fin,
                as_of_date=as_of_date,
                history=history,
                current_price=float(effective_price) if pd.notna(effective_price) else None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("DCF failed for %s: %s", ticker, exc)

        fair_value = pd.to_numeric(dcf_result.get("fair_value"), errors="coerce")
        if pd.notna(fair_value) and float(fair_value) > 0 and pd.notna(effective_price) and float(effective_price) > 0:
            features["val_discount_to_fair_pct"] = ((float(fair_value) - float(effective_price)) / float(fair_value)) * 100.0
            features["val_margin_of_safety"] = float(np.clip(1.0 - (float(effective_price) / float(fair_value)), -1.0, 1.0))
        features["val_owner_earnings_yield"] = pd.to_numeric(dcf_result.get("owner_earnings_yield"), errors="coerce")
        features["val_dcf_confidence"] = pd.to_numeric(dcf_result.get("confidence"), errors="coerce")

        try:
            moat_result = self._moat.score(
                ticker=ticker,
                as_of_date=as_of_date,
                fin=fin,
                fin_history=history,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Moat failed for %s: %s", ticker, exc)

        features["val_moat_score"] = pd.to_numeric(moat_result.get("moat_score"), errors="coerce")
        features["val_roce_5yr_avg"] = self._roce_5yr(history)
        features["val_revenue_cagr_5yr"] = self._revenue_cagr(history, years=5)
        features["val_earnings_consistency"] = self._earnings_consistency(history)

        try:
            eq_result = self._eq.analyze(
                ticker=ticker,
                as_of_date=as_of_date,
                fin=fin,
                fin_history=history,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Earnings quality failed for %s: %s", ticker, exc)

        quality_score = pd.to_numeric(eq_result.get("quality_score"), errors="coerce")
        features["val_earnings_quality_score"] = (quality_score / 10.0) if pd.notna(quality_score) else np.nan
        features["val_accruals_ratio"] = self._accruals_ratio(fin, history)
        features["val_debt_safety_score"] = self._debt_safety(fin)
        features["val_interest_coverage"] = self._interest_coverage(fin)

        quality_components = [
            features.get("val_moat_score"),
            self._scale_pct_to_decile(features.get("val_roce_5yr_avg")),
            self._scale_fraction_to_decile(features.get("val_earnings_consistency")),
        ]
        valid_q = [float(v) for v in quality_components if pd.notna(v)]
        features["val_quality_composite"] = float(np.mean(valid_q)) if valid_q else np.nan

        safety_components = [
            features.get("val_earnings_quality_score"),
            self._scale_fraction_to_decile(features.get("val_debt_safety_score")),
            self._scale_interest_coverage_to_decile(features.get("val_interest_coverage")),
        ]
        valid_s = [float(v) for v in safety_components if pd.notna(v)]
        features["val_safety_composite"] = float(np.mean(valid_s)) if valid_s else np.nan
        features["val_composite_score"] = self._aggregate_composite(
            ticker=ticker,
            as_of_date=as_of_date,
            current_price=effective_price,
            fair_value=fair_value,
            features=features,
        )
        return features

    def _aggregate_composite(
        self,
        ticker: str,
        as_of_date: datetime,
        current_price: Optional[float],
        fair_value: Optional[float],
        features: dict,
    ) -> float:
        price = float(current_price) if pd.notna(current_price) and float(current_price) > 0 else None
        ref_value = (
            price
            if price is not None
            else float(fair_value)
            if pd.notna(fair_value) and float(fair_value) > 0
            else 1.0
        )

        dcf_conf = self._clip_or_default(features.get("val_dcf_confidence"), 0.1, 1.0, 0.25)
        quality_gap = self._score_to_gap(features.get("val_quality_composite"), scale=10.0)
        safety_gap = self._score_to_gap(features.get("val_safety_composite"), scale=10.0)
        moat_gap = self._score_to_gap(features.get("val_moat_score"), scale=10.0)
        margin_gap = self._clip_or_default(features.get("val_margin_of_safety"), -1.0, 1.0, np.nan)

        families = pd.DataFrame(
            [
                {
                    "ticker": ticker,
                    "date": pd.Timestamp(as_of_date),
                    "reference_value": ref_value,
                    "macro_adjustment_factor": 1.0,
                    "credit_stress_score": float(np.clip((1.0 - self._clip_or_default(features.get("val_debt_safety_score"), 0.0, 1.0, 0.5)) * 100.0, 0.0, 100.0)),
                    "default_probability": float(np.clip(1.0 - self._clip_or_default(features.get("val_debt_safety_score"), 0.0, 1.0, 0.5), 0.01, 0.50)),
                    "core_gap": margin_gap,
                    "core_variance": 1.0 / max(dcf_conf, 1e-6),
                    "core_confidence": dcf_conf,
                    "residual_gap": quality_gap,
                    "residual_variance": 1.0,
                    "residual_confidence": self._clip_or_default(features.get("val_quality_composite"), 0.0, 10.0, 4.0) / 10.0,
                    "credit_gap": safety_gap,
                    "credit_variance": 1.0,
                    "credit_confidence": self._clip_or_default(features.get("val_safety_composite"), 0.0, 10.0, 4.0) / 10.0,
                    "real_option_gap": moat_gap,
                    "real_option_variance": 1.2,
                    "real_option_confidence": self._clip_or_default(features.get("val_moat_score"), 0.0, 10.0, 4.0) / 10.0,
                }
            ]
        )
        posterior = self._aggregator.combine(families)
        if posterior.empty:
            return np.nan
        posterior_gap = pd.to_numeric(posterior.iloc[0].get("posterior_gap"), errors="coerce")
        if pd.isna(posterior_gap):
            return np.nan
        return float(np.clip(50.0 + 50.0 * float(posterior_gap), 0.0, 100.0))

    @staticmethod
    def _clip_or_default(value: object, lower: float, upper: float, default: float) -> float:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return float(default)
        return float(np.clip(float(numeric), lower, upper))

    @staticmethod
    def _score_to_gap(value: object, scale: float = 10.0) -> float:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return np.nan
        centered = (float(numeric) / float(scale)) - 0.5
        return float(np.clip(centered * 2.0, -1.0, 1.0))

    @staticmethod
    def _scale_pct_to_decile(value: object, clip_pct: float = 40.0) -> float:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return np.nan
        return float(np.clip((float(numeric) / clip_pct) * 10.0, 0.0, 10.0))

    @staticmethod
    def _scale_fraction_to_decile(value: object) -> float:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return np.nan
        return float(np.clip(float(numeric) * 10.0, 0.0, 10.0))

    @staticmethod
    def _scale_interest_coverage_to_decile(value: object, cap: float = 20.0) -> float:
        numeric = pd.to_numeric(value, errors="coerce")
        if pd.isna(numeric):
            return np.nan
        return float(np.clip((float(numeric) / cap) * 10.0, 0.0, 10.0))

    def _quarantine_corrupt_cache(self, exc: Exception) -> None:
        if not self.CACHE_PATH.exists():
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.CACHE_PATH.with_name(f"{self.CACHE_PATH.stem}.corrupt_{stamp}{self.CACHE_PATH.suffix}")
        try:
            self.CACHE_PATH.replace(backup)
            logger.warning(
                "Valuation cache corrupted; moved %s to %s after read failure: %s",
                self.CACHE_PATH,
                backup,
                exc,
            )
        except Exception as move_exc:  # noqa: BLE001
            logger.warning(
                "Valuation cache corrupted but quarantine failed for %s: %s (original error: %s)",
                self.CACHE_PATH,
                move_exc,
                exc,
            )

    def _safe_read_cache(self) -> Optional[pd.DataFrame]:
        if not self.CACHE_PATH.exists():
            return None
        try:
            df = pd.read_parquet(self.CACHE_PATH)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return df
        except Exception as exc:  # noqa: BLE001
            self._quarantine_corrupt_cache(exc)
            return None

    @staticmethod
    def _interest_coverage(fin: dict) -> float:
        op = pd.to_numeric(fin.get("operating_profit", fin.get("operating_income")), errors="coerce")
        interest = pd.to_numeric(fin.get("interest_expense"), errors="coerce")
        if pd.isna(op) or pd.isna(interest) or float(interest) <= 0:
            return np.nan
        return float(min(float(op) / float(interest), 20.0))

    @staticmethod
    def _roce_5yr(history: list[dict]) -> float:
        roces: list[float] = []
        for fin in history[-5:]:
            roce = pd.to_numeric(fin.get("roce_pct"), errors="coerce")
            if pd.notna(roce):
                roces.append(float(roce))
                continue
            op = pd.to_numeric(fin.get("operating_profit"), errors="coerce")
            debt = pd.to_numeric(fin.get("total_borrowings"), errors="coerce")
            equity = pd.to_numeric(fin.get("equity_capital"), errors="coerce")
            reserves = pd.to_numeric(fin.get("reserves"), errors="coerce")
            capital_employed = (
                (0.0 if pd.isna(equity) else float(equity))
                + (0.0 if pd.isna(reserves) else float(reserves))
                + (0.0 if pd.isna(debt) else float(debt))
            )
            if pd.notna(op) and capital_employed > 0:
                roces.append((float(op) / capital_employed) * 100.0)
        return float(np.mean(roces)) if roces else np.nan

    @staticmethod
    def _revenue_cagr(history: list[dict], years: int = 5) -> float:
        if len(history) < years + 1:
            return np.nan
        rev_start = pd.to_numeric(history[-(years + 1)].get("revenue", history[-(years + 1)].get("sales")), errors="coerce")
        rev_end = pd.to_numeric(history[-1].get("revenue", history[-1].get("sales")), errors="coerce")
        if pd.isna(rev_start) or pd.isna(rev_end) or float(rev_start) <= 0:
            return np.nan
        return float((((float(rev_end) / float(rev_start)) ** (1.0 / years)) - 1.0) * 100.0)

    @staticmethod
    def _earnings_consistency(history: list[dict]) -> float:
        profits = [pd.to_numeric(row.get("net_profit"), errors="coerce") for row in history[-10:]]
        profits = [float(p) for p in profits if pd.notna(p)]
        if len(profits) < 2:
            return np.nan
        positive = sum(1 for p in profits if p > 0)
        growing = sum(1 for i in range(1, len(profits)) if profits[i] > profits[i - 1])
        return float((positive + growing) / max((len(profits) + len(profits) - 1), 1))

    @staticmethod
    def _accruals_ratio(curr: dict, history: list[dict]) -> float:
        if len(history) < 2:
            return np.nan
        prior = history[-2]
        ni = pd.to_numeric(curr.get("net_profit"), errors="coerce")
        ocf = pd.to_numeric(curr.get("cash_from_operations"), errors="coerce")
        assets_c = pd.to_numeric(curr.get("total_assets"), errors="coerce")
        assets_p = pd.to_numeric(prior.get("total_assets"), errors="coerce")
        if pd.isna(ni) or pd.isna(ocf) or pd.isna(assets_c) or pd.isna(assets_p):
            return np.nan
        avg_assets = (float(assets_c) + float(assets_p)) / 2.0
        if avg_assets <= 0:
            return np.nan
        return float((float(ni) - float(ocf)) / avg_assets)

    @staticmethod
    def _debt_safety(fin: dict) -> float:
        d2e = pd.to_numeric(fin.get("debt_to_equity"), errors="coerce")
        if pd.isna(d2e):
            debt = pd.to_numeric(fin.get("total_borrowings"), errors="coerce")
            equity = pd.to_numeric(fin.get("equity_capital"), errors="coerce")
            reserves = pd.to_numeric(fin.get("reserves"), errors="coerce")
            eq_total = (0.0 if pd.isna(equity) else float(equity)) + (0.0 if pd.isna(reserves) else float(reserves))
            if pd.notna(debt) and eq_total > 0:
                d2e = float(debt) / eq_total
        if pd.isna(d2e):
            return np.nan
        return float(1.0 / (1.0 + max(float(d2e), 0.0)))

    def _ensure_cache_loaded(self) -> None:
        if self._cache_loaded:
            return
        self._cache_frame = self._safe_read_cache()
        self._cache_loaded = True

    def _load_cached_raw(self, as_of_date: datetime, tickers: list[str]) -> Optional[pd.DataFrame]:
        """Return the raw (pre-zscore) cached feature rows for the requested
        tickers on the resolved date — the intersection, not all-or-nothing (I.2).
        """
        self._ensure_cache_loaded()
        df = self._cache_frame
        if df is None or df.empty or "date" not in df.columns:
            return None
        try:
            requested = pd.Timestamp(as_of_date).normalize()
            date_col = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
            if bool((date_col == requested).any()):
                use_date = requested
            else:
                if not bool(self._valuation_cfg.get("allow_prior_cache_fallback", True)):
                    return None
                prior = date_col[date_col <= requested]
                if prior.empty:
                    return None
                use_date = pd.Timestamp(prior.max()).normalize()
                max_age_days = int(self._valuation_cfg.get("max_cache_fallback_age_days", 7) or 7)
                cache_age_days = int((requested - use_date).days)
                if cache_age_days < 0 or cache_age_days > max_age_days:
                    return None

            cached = df.loc[date_col == use_date].copy()
            if cached.empty:
                return None
            cached = cached.set_index("ticker")
            cached.index = cached.index.astype(str)
            keep = [c for c in self.FEATURE_NAMES if c in cached.columns]
            want = [str(t) for t in tickers]
            sub = cached.loc[cached.index.intersection(want), keep]
            return sub if not sub.empty else None
        except Exception:  # noqa: BLE001
            return None

    def _store_raw_rows(self, as_of_date: datetime, computed: pd.DataFrame) -> None:
        """Update the in-memory cache frame with newly-computed raw rows and
        flush to disk in batches (I.1) instead of rewriting the whole file each
        date.
        """
        try:
            self._ensure_cache_loaded()
            raw_cols = [c for c in self.FEATURE_NAMES if c in computed.columns]
            new_rows = computed[raw_cols].copy()
            new_rows["date"] = pd.Timestamp(as_of_date).normalize()
            new_rows["ticker"] = new_rows.index.astype(str)
            new_rows = new_rows.reset_index(drop=True)

            existing = self._cache_frame
            if existing is not None and not existing.empty:
                ex_date = pd.to_datetime(existing["date"], errors="coerce").dt.normalize()
                same_date = ex_date == pd.Timestamp(as_of_date).normalize()
                # Drop only the rows for the tickers being (re)written on this date.
                overwrite = same_date & existing["ticker"].astype(str).isin(set(new_rows["ticker"]))
                kept = existing.loc[~overwrite]
                self._cache_frame = pd.concat([kept, new_rows], ignore_index=True)
            else:
                self._cache_frame = new_rows

            self._cache_dirty = True
            self._pending_writes += 1
            if self._pending_writes >= max(1, self._cache_flush_every):
                self.flush_cache()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Valuation cache update failed for %s: %s", as_of_date, exc)

    def flush_cache(self) -> None:
        """Persist the in-memory cache frame to disk atomically (single write)."""
        if not self._cache_dirty or self._cache_frame is None:
            return
        tmp = None
        try:
            self.CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.CACHE_PATH.with_name(
                f"{self.CACHE_PATH.stem}.tmp.{os.getpid()}.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{self.CACHE_PATH.suffix}"
            )
            self._cache_frame.to_parquet(tmp, index=False)
            tmp.replace(self.CACHE_PATH)
            self._cache_dirty = False
            self._pending_writes = 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("Valuation cache flush failed: %s", exc)
            try:
                if tmp is not None and Path(tmp).exists():
                    Path(tmp).unlink()
            except Exception:
                pass

    def __del__(self):  # noqa: D401
        try:
            self.flush_cache()
        except Exception:
            pass
