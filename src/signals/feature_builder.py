"""Alternative feature normalization utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class AlternativeFeatureBuilder:
    """
    Build normalized alternative-data feature variants.

    Uses the same cross-sectional normalization style as research FeatureFactory.
    """

    FEATURE_GROUPS = {
        "bulk_deals": [
            "bulk_net_volume_5d",
            "bulk_buy_count_5d",
            "bulk_deal_value_pct_mcap",
            "institutional_buy_flag",
        ],
        "pledge": [
            "pledge_pct",
            "pledge_change_1q",
            "pledge_high_flag",
            "pledge_increasing_flag",
        ],
        "earnings": [
            "days_since_earnings",
            "earnings_gap_days",
        ],
        "ratings": [
            "rating_numeric",
            "rating_change_1y",
            "recent_downgrade_flag",
            "watch_negative_flag",
        ],
        "announcements": [
            "order_win_count_90d",
            "order_win_flag_30d",
            "insider_buy_flag_30d",
            "insider_sell_flag_30d",
        ],
    }

    @staticmethod
    def _group_zscore(values: pd.Series, groups: pd.Series, clip_abs: float = 6.0) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        mu = v.groupby(groups, sort=False).transform("mean")
        sd = v.groupby(groups, sort=False).transform("std").replace(0.0, np.nan)
        z = (v - mu) / (sd + 1e-12)
        z = z.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        if float(clip_abs) > 0:
            z = z.clip(-float(clip_abs), float(clip_abs))
        return z.astype(float)

    @staticmethod
    def _group_rank_centered(values: pd.Series, groups: pd.Series) -> pd.Series:
        v = pd.to_numeric(values, errors="coerce")
        r = v.groupby(groups, sort=False).rank(method="average", pct=True)
        return (r.fillna(0.5) - 0.5).astype(float)

    @classmethod
    def feature_columns(cls) -> list[str]:
        out: list[str] = []
        for cols in cls.FEATURE_GROUPS.values():
            out.extend([str(c) for c in cols])
        return out

    @classmethod
    def normalize(cls, frame: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        if frame is None or frame.empty or date_col not in frame.columns:
            return pd.DataFrame() if frame is None else frame
        out = frame.copy()
        for col in cls.feature_columns():
            if col not in out.columns:
                continue
            out[col] = pd.to_numeric(out[col], errors="coerce")
            out[f"{col}_cs_z"] = cls._group_zscore(out[col], out[date_col], clip_abs=6.0)
            out[f"{col}_cs_rank"] = cls._group_rank_centered(out[col], out[date_col])
        return out

    @classmethod
    def normalize_feature_columns(cls, features: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
        """Normalize a feature-only matrix using an external date index."""
        if features is None or features.empty:
            return pd.DataFrame(index=features.index if isinstance(features, pd.DataFrame) else None)
        out = pd.DataFrame(index=features.index)
        for col in features.columns:
            s = pd.to_numeric(features[col], errors="coerce")
            out[f"{col}_cs_z"] = cls._group_zscore(s, dates, clip_abs=6.0)
            out[f"{col}_cs_rank"] = cls._group_rank_centered(s, dates)
        return out.replace([np.inf, -np.inf], np.nan)
