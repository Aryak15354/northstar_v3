"""Credit rating feature engineering."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay


RATING_SCALE = {
    "AAA": 10,
    "AA+": 9,
    "AA": 8,
    "AA-": 7,
    "A+": 6,
    "A": 5,
    "A-": 4,
    "BBB+": 3,
    "BBB": 2,
    "BBB-": 1,
}


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def rating_to_numeric(rating: object) -> float:
    text = str(rating or "").upper().strip()
    if not text:
        return np.nan
    text = re.sub(r"\([^)]*\)", "", text).strip()
    # Match strict grade tokens first so AA- does not get captured as AA.
    for code, val in sorted(RATING_SCALE.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])", text):
            return float(val)
    if any(x in text for x in ["BB", "B", "C", "D"]):
        return 0.0
    return np.nan


def compute_rating_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute PIT-safe rating action features.

    PIT rule:
    - Rating action date D is available from D+1 business day.
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "ticker",
                "date",
                "availability_date",
                "rating_numeric",
                "rating_change_1y",
                "recent_downgrade_flag",
                "recent_upgrade_flag",
                "watch_negative_flag",
                "investment_grade_flag",
                "rating_momentum_1y",
            ]
        )

    out = df.copy()
    tk_col = "nse_ticker" if "nse_ticker" in out.columns else ("ticker" if "ticker" in out.columns else None)
    dt_col = "date" if "date" in out.columns else ("action_date" if "action_date" in out.columns else None)
    if tk_col is None or dt_col is None:
        return pd.DataFrame()

    out["ticker"] = out[tk_col].map(_normalize_ticker)
    out["date"] = pd.to_datetime(out[dt_col], errors="coerce")
    out["new_rating"] = out.get("new_rating", np.nan)
    out["action_type"] = out.get("action_type", "").astype(str).str.upper().fillna("")
    out["outlook"] = out.get("outlook", "").astype(str).str.upper().fillna("")

    out = out.dropna(subset=["ticker", "date"]).copy()
    if out.empty:
        return pd.DataFrame()

    out["rating_numeric"] = out["new_rating"].map(rating_to_numeric)
    # PIT safety for rating action events.
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce") + BDay(1)
    out = out.sort_values(["ticker", "availability_date"], kind="mergesort")

    pieces: list[pd.DataFrame] = []
    for tk, grp in out.groupby("ticker", sort=False):
        g = grp.copy().sort_values("availability_date", kind="mergesort")

        ref = g[["availability_date", "rating_numeric"]].copy()
        ref["lag_date"] = ref["availability_date"] + pd.Timedelta(days=365)
        lag_source = (
            ref[["lag_date", "rating_numeric"]]
            .rename(columns={"lag_date": "availability_date", "rating_numeric": "rating_1y_ago"})
            .sort_values("availability_date", kind="mergesort")
        )
        lagged = pd.merge_asof(
            g[["availability_date"]].sort_values("availability_date"),
            lag_source,
            on="availability_date",
            direction="backward",
            allow_exact_matches=True,
        )
        g["rating_1y_ago"] = pd.to_numeric(lagged["rating_1y_ago"], errors="coerce").to_numpy()
        g["rating_change_1y"] = pd.to_numeric(g["rating_numeric"], errors="coerce") - pd.to_numeric(
            g["rating_1y_ago"], errors="coerce"
        )

        action_score = np.select(
            [g["action_type"].str.contains("UPGRADE", na=False), g["action_type"].str.contains("DOWNGRADE", na=False)],
            [1.0, -1.0],
            default=0.0,
        )
        g["recent_downgrade_flag"] = (
            pd.Series((action_score < 0).astype(float), index=g.index)
            .rolling(90, min_periods=1)
            .max()
            .astype(float)
        )
        g["recent_upgrade_flag"] = (
            pd.Series((action_score > 0).astype(float), index=g.index)
            .rolling(90, min_periods=1)
            .max()
            .astype(float)
        )
        g["watch_negative_flag"] = (
            g["outlook"].str.contains("NEGATIVE|WATCH_NEGATIVE", regex=True, na=False)
            | g["action_type"].str.contains("WATCH_NEGATIVE", regex=True, na=False)
        ).astype(float)
        g["investment_grade_flag"] = (pd.to_numeric(g["rating_numeric"], errors="coerce") >= 1.0).astype(float)

        momentum = pd.Series(action_score, index=g.index).rolling(365, min_periods=1).sum()
        g["rating_momentum_1y"] = np.where(momentum > 0.0, 1.0, np.where(momentum < 0.0, -1.0, 0.0))
        pieces.append(g)

    out = pd.concat(pieces, ignore_index=True) if pieces else out
    cols = [
        "ticker",
        "date",
        "availability_date",
        "rating_numeric",
        "rating_change_1y",
        "recent_downgrade_flag",
        "recent_upgrade_flag",
        "watch_negative_flag",
        "investment_grade_flag",
        "rating_momentum_1y",
    ]
    return out[cols].sort_values(["ticker", "availability_date"], kind="mergesort").reset_index(drop=True)
