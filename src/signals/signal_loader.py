"""Loader for processed alternative datasets."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from .bulk_deals import compute_bulk_deal_features
from .credit_ratings import compute_rating_features
from .earnings_dates import compute_earnings_features
from .feature_builder import AlternativeFeatureBuilder
from .order_announcements import compute_announcement_features
from .promoter_pledge import compute_pledge_features

logger = logging.getLogger(__name__)


class AlternativeDataLoader:
    """
    Load processed alternative datasets and expose PIT-safe as-of merges.

    Usage:
        loader = AlternativeDataLoader(config)
        features = loader.get_features_as_of(date, tickers)
    """

    FAMILY_PATHS = {
        "bulk_deals": "bulk_deals_all.csv",
        "pledge": "promoter_pledge_all.csv",
        "earnings": "earnings_dates_all.csv",
        "ratings": "credit_ratings_all.csv",
        "announcements": "announcements_all.csv",
    }

    FAMILY_COLUMNS = {
        "bulk_deals": [
            "bulk_buy_volume_5d",
            "bulk_sell_volume_5d",
            "bulk_net_volume_5d",
            "bulk_buy_count_5d",
            "bulk_deal_flag",
            "bulk_deal_value_pct_mcap",
            "institutional_buy_flag",
        ],
        "pledge": [
            "pledge_pct",
            "pledge_change_1q",
            "pledge_change_4q",
            "pledge_high_flag",
            "pledge_increasing_flag",
            "pledge_decreasing_flag",
        ],
        "earnings": [
            "days_since_earnings",
            "earnings_frequency_annual",
            "earnings_gap_days",
        ],
        "ratings": [
            "rating_numeric",
            "rating_change_1y",
            "recent_downgrade_flag",
            "recent_upgrade_flag",
            "watch_negative_flag",
            "investment_grade_flag",
            "rating_momentum_1y",
        ],
        "announcements": [
            "order_win_count_90d",
            "order_win_flag_30d",
            "capex_announced_flag",
            "insider_buy_flag_30d",
            "insider_sell_flag_30d",
            "acquisition_flag_180d",
            "order_to_revenue_ratio",
        ],
    }

    def __init__(self, config: dict | None = None):
        self.config = dict(config or {})
        self.base_path = Path(str(self.config.get("alternative_data_path", "data/processed/alternative")))
        self.feature_availability = self.config.get("alternative_features_available", {}) or {}
        self.frames: dict[str, pd.DataFrame] = {}
        self._load_all()

    FAMILY_ALIASES = {
        "bulk_deals": ("bulk_deals",),
        "pledge": ("pledge", "promoter_pledge"),
        "earnings": ("earnings", "earnings_dates"),
        "ratings": ("ratings", "credit_ratings"),
        "announcements": ("announcements", "order_announcements"),
    }

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(".NS"):
            return s
        if "." in s:
            s = s.split(".", 1)[0]
        return f"{s}.NS"

    def _empty_family_frame(self, family: str) -> pd.DataFrame:
        cols = ["ticker", "availability_date"] + list(self.FAMILY_COLUMNS.get(family, []))
        return pd.DataFrame(columns=cols)

    def _is_family_enabled(self, family: str) -> bool:
        if not isinstance(self.feature_availability, dict) or not self.feature_availability:
            return True
        for key in self.FAMILY_ALIASES.get(family, (family,)):
            if key in self.feature_availability:
                return bool(self.feature_availability.get(key))
        return True

    def _load_one(self, family: str, path: Path) -> pd.DataFrame:
        if not path.exists():
            return pd.DataFrame()
        try:
            if path.suffix.lower() in {".parquet", ".pq"}:
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[alternative-data] failed reading %s: %s", path, exc)
            return pd.DataFrame()
        if df is None or df.empty:
            return pd.DataFrame()

        out = df.copy()
        ticker_col = "ticker" if "ticker" in out.columns else ("nse_ticker" if "nse_ticker" in out.columns else None)
        if ticker_col is not None:
            out["ticker"] = out[ticker_col].map(self._normalize_ticker)
            out = out[out["ticker"].astype(str) != ""].copy()
        else:
            out["ticker"] = ""

        if "availability_date" in out.columns:
            out["availability_date"] = pd.to_datetime(out["availability_date"], errors="coerce")
        elif "date" in out.columns:
            out["availability_date"] = pd.to_datetime(out["date"], errors="coerce")
        elif "announcement_date" in out.columns:
            out["availability_date"] = pd.to_datetime(out["announcement_date"], errors="coerce")

        return out.reset_index(drop=True)

    def _load_all(self) -> None:
        self.frames = {}
        for family, fname in self.FAMILY_PATHS.items():
            if not self._is_family_enabled(family):
                self.frames[family] = pd.DataFrame()
                continue
            path = self.base_path / fname
            self.frames[family] = self._load_one(family, path)

    def _standardize_feature_frame(self, family: str, frame: pd.DataFrame) -> pd.DataFrame:
        cols = self.FAMILY_COLUMNS.get(family, [])
        if frame is None or frame.empty:
            return self._empty_family_frame(family)

        out = frame.copy()
        if "ticker" not in out.columns:
            tcol = "nse_ticker" if "nse_ticker" in out.columns else None
            out["ticker"] = out[tcol].map(self._normalize_ticker) if tcol else ""
        else:
            out["ticker"] = out["ticker"].map(self._normalize_ticker)

        if "availability_date" in out.columns:
            out["availability_date"] = pd.to_datetime(out["availability_date"], errors="coerce")
        elif "date" in out.columns:
            out["availability_date"] = pd.to_datetime(out["date"], errors="coerce")
        else:
            out["availability_date"] = pd.NaT

        out = out.dropna(subset=["ticker", "availability_date"]).copy()
        for c in cols:
            if c not in out.columns:
                out[c] = np.nan
            out[c] = pd.to_numeric(out[c], errors="coerce")

        keep = ["ticker", "availability_date"] + cols
        return out[keep].sort_values(["ticker", "availability_date"], kind="mergesort").reset_index(drop=True)

    def _prepare_family_features(self, family: str, base_frame: pd.DataFrame) -> pd.DataFrame:
        cols = self.FAMILY_COLUMNS.get(family, [])
        if not self._is_family_enabled(family):
            return self._empty_family_frame(family)
        raw = self.frames.get(family, pd.DataFrame())
        if raw is None or raw.empty:
            return self._empty_family_frame(family)

        if {"ticker", "availability_date"}.issubset(set(raw.columns)) and any(c in raw.columns for c in cols):
            return self._standardize_feature_frame(family, raw)

        try:
            if family == "bulk_deals":
                computed = compute_bulk_deal_features(raw, prices_df=base_frame)
            elif family == "pledge":
                computed = compute_pledge_features(raw)
            elif family == "earnings":
                computed = compute_earnings_features(raw, prices_df=base_frame)
            elif family == "ratings":
                computed = compute_rating_features(raw)
            elif family == "announcements":
                fundamentals_df = None
                if "revenue" in base_frame.columns:
                    fundamentals_df = base_frame[[c for c in ["date", "ticker", "revenue"] if c in base_frame.columns]].copy()
                computed = compute_announcement_features(raw, prices_df=base_frame, fundamentals_df=fundamentals_df)
            else:
                computed = pd.DataFrame()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[alternative-data] compute failed for family=%s: %s", family, exc)
            computed = pd.DataFrame()

        return self._standardize_feature_frame(family, computed)

    def _asof_merge_family(self, left: pd.DataFrame, family: str, right: pd.DataFrame) -> pd.DataFrame:
        cols = self.FAMILY_COLUMNS.get(family, [])
        if right is None or right.empty:
            out = left.copy()
            for c in cols:
                out[c] = np.nan
            return out

        out_groups: list[pd.DataFrame] = []
        l = left.copy()
        for ticker, grp in l.groupby("ticker", sort=False):
            r = right[right["ticker"] == ticker]
            g = grp.sort_values("date", kind="mergesort").copy()
            if r.empty:
                for c in cols:
                    g[c] = np.nan
                out_groups.append(g)
                continue
            m = pd.merge_asof(
                g,
                r[["availability_date"] + cols].sort_values("availability_date", kind="mergesort"),
                left_on="date",
                right_on="availability_date",
                direction="backward",
                allow_exact_matches=True,
            )
            m = m.drop(columns=["availability_date"], errors="ignore")
            out_groups.append(m)

        out = pd.concat(out_groups, ignore_index=True) if out_groups else l
        return out

    def get_features_as_of(self, trade_date: object, tickers: list[str]) -> pd.DataFrame:
        """Get all alternative features as-of a single trade date for a ticker set."""
        dt = pd.to_datetime(trade_date, errors="coerce")
        if pd.isna(dt):
            return pd.DataFrame(columns=["ticker"] + AlternativeFeatureBuilder.feature_columns())

        base = pd.DataFrame({"ticker": [self._normalize_ticker(t) for t in tickers], "date": pd.Timestamp(dt)})
        base = base.dropna(subset=["date", "ticker"]).drop_duplicates(subset=["ticker", "date"])
        if base.empty:
            return pd.DataFrame(columns=["ticker"] + AlternativeFeatureBuilder.feature_columns())

        features = self.get_features_as_of_frame(base)
        out = pd.DataFrame({"ticker": base["ticker"].to_numpy()}, index=base.index)
        for col in AlternativeFeatureBuilder.feature_columns():
            out[col] = pd.to_numeric(features.get(col), errors="coerce") if col in features.columns else np.nan
        return out.reset_index(drop=True)

    def get_features_as_of_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        """PIT-safe as-of merge for a full research panel frame."""
        if frame is None or frame.empty:
            return pd.DataFrame()
        if not {"date", "ticker"}.issubset(set(frame.columns)):
            return pd.DataFrame(index=frame.index)

        base = frame.copy()
        base["date"] = pd.to_datetime(base["date"], errors="coerce")
        base["ticker"] = base["ticker"].map(self._normalize_ticker)
        base = base.dropna(subset=["date", "ticker"])
        if base.empty:
            return pd.DataFrame(index=frame.index)

        # Minimal columns used by family-specific feature builders.
        price_like = [c for c in ["date", "ticker", "close", "market_cap", "shares_outstanding"] if c in base.columns]
        base_for_compute = base[price_like].copy() if price_like else base[["date", "ticker"]].copy()

        prepared = {fam: self._prepare_family_features(fam, base_for_compute) for fam in self.FAMILY_PATHS}

        merged = base[["date", "ticker"]].copy()
        for family in self.FAMILY_PATHS:
            merged = self._asof_merge_family(merged, family, prepared.get(family, pd.DataFrame()))

        feat_cols = AlternativeFeatureBuilder.feature_columns()
        out = merged[feat_cols].copy() if feat_cols else pd.DataFrame(index=merged.index)
        for col in feat_cols:
            if col not in out.columns:
                out[col] = np.nan

        aligned = pd.DataFrame(index=frame.index)
        for col in feat_cols:
            aligned[col] = np.nan
        aligned.loc[base.index, feat_cols] = out[feat_cols].to_numpy()
        return aligned
