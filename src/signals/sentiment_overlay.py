"""Live score overlays from sentiment and macro context."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay

from src.research.regime_engine import RegimeEngine


class SentimentOverlay:
    """
    Adjust model scores using near-real-time sentiment signals.

    This is a live overlay layer and does not modify model training weights.
    """

    def __init__(self, config: dict | None = None):
        self.config = dict(config or {})
        self.sentiment_path = Path(
            str(
                self.config.get(
                    "sentiment_path",
                    "data/processed/sentiment/ticker_sentiment_daily.parquet",
                )
            )
        )
        self.market_sentiment_path = Path(
            str(
                self.config.get(
                    "market_sentiment_path",
                    "data/processed/sentiment/market_sentiment_daily.parquet",
                )
            )
        )
        self.macro_path = Path(
            str(self.config.get("macro_regime_path", "data/processed/macro/macro_regime_features.parquet"))
        )
        self.regime_engine = RegimeEngine(
            {
                "regime_labels_path": str(
                    self.config.get("regime_labels_path", "data/processed/regime_labels.parquet")
                )
            }
        )
        self.v3_ticker_fallback_path = Path("data/sentiment/v3/company_sentiment_trends.parquet")
        self.v3_market_fallback_path = Path("data/sentiment/v3/market_sentiment_india.parquet")
        self.news_dataset_path = Path("data/processed/news/news_dataset.parquet")

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

    @staticmethod
    def _normalize_dates(values: object) -> pd.Series:
        d = pd.to_datetime(values, errors="coerce")
        try:
            d = d.dt.tz_convert(None)
        except Exception:
            try:
                d = d.dt.tz_localize(None)
            except Exception:
                pass
        return d.dt.normalize()

    def _load_sentiment_as_of(self, as_of_date: object) -> pd.DataFrame:
        sent = pd.DataFrame()
        if self.sentiment_path.exists():
            sent = pd.read_parquet(self.sentiment_path)
        if sent.empty:
            sent = self._load_v3_ticker_fallback()
        if sent.empty:
            sent = self._load_news_dataset_ticker_fallback()
        if sent.empty:
            return pd.DataFrame(columns=["ticker", "sentiment_polarity", "sentiment_conviction", "news_volume"])
        sent["ticker"] = sent["ticker"].map(self._normalize_ticker)
        sent["availability_date"] = pd.to_datetime(sent.get("availability_date", sent.get("date")), errors="coerce")
        date = pd.to_datetime(as_of_date, errors="coerce")
        sent = sent[sent["availability_date"] <= date].copy()
        if sent.empty:
            return pd.DataFrame(columns=["ticker", "sentiment_polarity", "sentiment_conviction", "news_volume"])
        sent = sent.sort_values(["ticker", "availability_date"], kind="mergesort")
        latest = sent.groupby("ticker", as_index=False).tail(1)
        keep = [
            "ticker",
            "sentiment_polarity",
            "sentiment_conviction",
            "sentiment_surprise",
            "sentiment_uncertainty",
            "news_volume",
        ]
        for c in keep:
            if c not in latest.columns:
                latest[c] = np.nan
        return latest[keep]

    def _load_v3_ticker_fallback(self) -> pd.DataFrame:
        if not self.v3_ticker_fallback_path.exists():
            return pd.DataFrame()
        try:
            raw = pd.read_parquet(self.v3_ticker_fallback_path)
        except Exception:
            return pd.DataFrame()
        if raw.empty or "ticker" not in raw.columns:
            return pd.DataFrame()

        out = pd.DataFrame()
        out["ticker"] = raw["ticker"].map(self._normalize_ticker)
        out["date"] = self._normalize_dates(raw.get("timestamp", raw.get("date")))
        out["availability_date"] = out["date"] + BDay(1)
        out["sentiment_polarity"] = pd.to_numeric(
            raw.get("sentiment_polarity", raw.get("sentiment_score")), errors="coerce"
        ).clip(-1.0, 1.0)
        trend = pd.to_numeric(raw.get("trend_score"), errors="coerce")
        trend_abs = trend.abs()
        if trend_abs.notna().any() and float(trend_abs.max()) > 0.0:
            out["sentiment_conviction"] = (trend_abs / float(trend_abs.max())).clip(0.0, 1.0)
        else:
            out["sentiment_conviction"] = 0.5
        out["sentiment_surprise"] = pd.to_numeric(raw.get("event_shock_factor"), errors="coerce").abs().clip(0.0, 1.0)
        out["sentiment_uncertainty"] = (1.0 - pd.to_numeric(out["sentiment_conviction"], errors="coerce")).clip(0.0, 1.0)
        out["news_volume"] = pd.to_numeric(raw.get("headline_count"), errors="coerce").fillna(0).astype(int)

        out = out.dropna(subset=["ticker", "date"]).copy()
        if out.empty:
            return pd.DataFrame()
        out = (
            out.sort_values(["ticker", "availability_date"], kind="mergesort")
            .drop_duplicates(subset=["ticker", "date"], keep="last")
            .reset_index(drop=True)
        )
        return out

    def _load_news_dataset_ticker_fallback(self) -> pd.DataFrame:
        paths = [self.news_dataset_path, Path("data/processed/news/news_dataset.csv")]
        raw = pd.DataFrame()
        for p in paths:
            if not p.exists():
                continue
            try:
                raw = pd.read_parquet(p) if p.suffix.lower() == ".parquet" else pd.read_csv(p)
                break
            except Exception:
                continue
        if raw.empty or "ticker" not in raw.columns:
            return pd.DataFrame()

        out = pd.DataFrame()
        out["ticker"] = raw["ticker"].map(self._normalize_ticker)
        out["date"] = self._normalize_dates(raw.get("date", raw.get("timestamp")))
        out["availability_date"] = out["date"] + BDay(1)
        out["sentiment_polarity"] = pd.to_numeric(
            raw.get("sentiment", raw.get("sentiment_polarity")), errors="coerce"
        ).clip(-1.0, 1.0)
        out["sentiment_conviction"] = pd.to_numeric(
            raw.get("sentiment_conviction"), errors="coerce"
        ).fillna(pd.to_numeric(out["sentiment_polarity"], errors="coerce").abs()).clip(0.0, 1.0)
        out["sentiment_surprise"] = pd.to_numeric(raw.get("sentiment_surprise"), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        out["sentiment_uncertainty"] = (
            pd.to_numeric(raw.get("sentiment_uncertainty"), errors="coerce")
            .fillna(1.0 - pd.to_numeric(out["sentiment_conviction"], errors="coerce"))
            .clip(0.0, 1.0)
        )
        out["news_volume"] = 1

        out = out.dropna(subset=["ticker", "date"]).copy()
        if out.empty:
            return pd.DataFrame()
        out = (
            out.groupby(["ticker", "date"], as_index=False)
            .agg(
                availability_date=("availability_date", "max"),
                sentiment_polarity=("sentiment_polarity", "mean"),
                sentiment_conviction=("sentiment_conviction", "mean"),
                sentiment_surprise=("sentiment_surprise", "mean"),
                sentiment_uncertainty=("sentiment_uncertainty", "mean"),
                news_volume=("news_volume", "sum"),
            )
            .sort_values(["ticker", "date"], kind="mergesort")
        )
        return out

    def _load_market_sentiment_as_of(self, as_of_date: object) -> dict | None:
        ms = pd.DataFrame()
        if self.market_sentiment_path.exists():
            ms = pd.read_parquet(self.market_sentiment_path)
        if ms.empty:
            ms = self._load_v3_market_fallback()
        if ms.empty:
            ms = self._load_news_dataset_market_fallback()
        if ms.empty:
            return None
        ms["availability_date"] = pd.to_datetime(ms.get("availability_date", ms.get("date")), errors="coerce")
        date = pd.to_datetime(as_of_date, errors="coerce")
        ms = ms[ms["availability_date"] <= date].sort_values("availability_date", kind="mergesort")
        if ms.empty:
            return None
        return dict(ms.iloc[-1].to_dict())

    def _load_v3_market_fallback(self) -> pd.DataFrame:
        if not self.v3_market_fallback_path.exists():
            return pd.DataFrame()
        try:
            raw = pd.read_parquet(self.v3_market_fallback_path)
        except Exception:
            return pd.DataFrame()
        if raw.empty:
            return pd.DataFrame()

        out = pd.DataFrame()
        out["date"] = self._normalize_dates(raw.get("date", raw.get("timestamp")))
        out["availability_date"] = out["date"] + BDay(1)
        out["india_market_polarity"] = pd.to_numeric(
            raw.get("india_market_polarity", raw.get("polarity")), errors="coerce"
        )
        out["india_market_conviction"] = pd.to_numeric(
            raw.get("india_market_conviction", raw.get("conviction")), errors="coerce"
        )
        out["india_market_uncertainty"] = pd.to_numeric(
            raw.get("india_market_uncertainty", raw.get("uncertainty")), errors="coerce"
        )
        out["global_risk_sentiment"] = pd.to_numeric(
            raw.get("global_risk_sentiment", raw.get("polarity")), errors="coerce"
        )
        out["news_volume_total"] = pd.to_numeric(raw.get("news_volume_total"), errors="coerce")
        out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort")
        return out.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)

    def _load_news_dataset_market_fallback(self) -> pd.DataFrame:
        t = self._load_news_dataset_ticker_fallback()
        if t.empty:
            return pd.DataFrame()
        out = (
            t.groupby("date", as_index=False)
            .agg(
                india_market_polarity=("sentiment_polarity", "mean"),
                india_market_conviction=("sentiment_conviction", "mean"),
                india_market_uncertainty=("sentiment_uncertainty", "mean"),
                global_risk_sentiment=("sentiment_polarity", "mean"),
                news_volume_total=("news_volume", "sum"),
                availability_date=("availability_date", "max"),
            )
            .sort_values("date", kind="mergesort")
        )
        return out

    def apply(self, scores_df: pd.DataFrame, as_of_date: object) -> pd.DataFrame:
        """
        Apply ticker-level and market-level sentiment multipliers.
        """
        if scores_df is None or scores_df.empty:
            return pd.DataFrame(columns=["ticker", "model_score", "sentiment_multiplier", "adjusted_score"])

        out = scores_df.copy()
        out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out["model_score"] = pd.to_numeric(out.get("model_score"), errors="coerce").fillna(0.0)

        sent = self._load_sentiment_as_of(as_of_date)
        out = out.merge(sent, on="ticker", how="left")

        out["sentiment_multiplier"] = 1.0
        out["sentiment_override"] = False
        out["override_reason"] = ""

        reduce_mask = pd.to_numeric(out["sentiment_polarity"], errors="coerce") < -0.2
        out.loc[reduce_mask, "sentiment_multiplier"] = 0.6

        # Strong negative sentiment is a heavy penalty, NOT annihilation: a
        # x0.0 multiplier deleted names from the book on the strength of a
        # single (possibly wrong or stale) news read — 7 names were hard-zeroed
        # in the 2026-07-06 audit. Floor at 0.3 so sentiment can never be the
        # sole reason a name's score becomes exactly zero.
        zero_mask = (
            (pd.to_numeric(out["sentiment_polarity"], errors="coerce") < -0.5)
            & (pd.to_numeric(out["sentiment_conviction"], errors="coerce") > 0.7)
        )
        out.loc[zero_mask, "sentiment_multiplier"] = 0.3
        out.loc[zero_mask, "sentiment_override"] = True
        out.loc[zero_mask, "override_reason"] = "strong_negative_sentiment"

        market_sent = self._load_market_sentiment_as_of(as_of_date)
        if market_sent is not None:
            try:
                if float(market_sent.get("india_market_polarity", 0.0) or 0.0) < -0.4:
                    out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce") * 0.7
            except Exception:
                pass

        out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce").clip(0.0, 1.0)
        out["adjusted_score"] = pd.to_numeric(out["model_score"], errors="coerce") * out["sentiment_multiplier"]
        return out

    def apply_macro_overlay(
        self,
        scores_df: pd.DataFrame,
        as_of_date: object,
        macro_df: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """
        Apply macro regime multipliers after sentiment overlay.

        Logic:
        - contraction: all scores x0.8
        - expansion: all scores x1.1
        - sector_activity_zscore < -1.5: sector x0.7
        - sector_activity_zscore > 1.5: sector x1.15
        """
        out = scores_df.copy()
        if out.empty:
            return out
        if "sentiment_multiplier" not in out.columns:
            out["sentiment_multiplier"] = 1.0
        out["base_sentiment_multiplier"] = pd.to_numeric(out.get("sentiment_multiplier"), errors="coerce").fillna(1.0)
        out["macro_multiplier"] = 1.0
        if "model_score" not in out.columns:
            out["model_score"] = 0.0

        date = pd.to_datetime(as_of_date, errors="coerce")

        # Macro regime scalar from canonical regime label.
        regime_key = ""
        if "regime" in out.columns and out["regime"].notna().any():
            regime_key = str(out["regime"].dropna().astype(str).iloc[0]).strip().lower()
        if not regime_key:
            regime_key = str(self.regime_engine.get_regime_as_of(date)).strip().lower()
        parts = [p for p in regime_key.split("|") if p]
        macro_label = parts[2] if len(parts) >= 3 else ""
        regime_mult = 1.0
        if macro_label == "contraction":
            regime_mult = 0.8
        elif macro_label == "expansion":
            regime_mult = 1.1

        macro = macro_df
        if macro is None:
            if not self.macro_path.exists():
                out["macro_multiplier"] = pd.to_numeric(out["macro_multiplier"], errors="coerce") * regime_mult
                out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce") * regime_mult
                return out
            macro = pd.read_parquet(self.macro_path)

        if macro is None or macro.empty:
            out["macro_multiplier"] = pd.to_numeric(out["macro_multiplier"], errors="coerce") * regime_mult
            out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce") * regime_mult
            return out

        m = macro.copy()
        m["availability_date"] = pd.to_datetime(m.get("availability_date", m.get("date")), errors="coerce")
        m = m[m["availability_date"] <= date].copy()
        if m.empty:
            out["macro_multiplier"] = pd.to_numeric(out["macro_multiplier"], errors="coerce") * regime_mult
            out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce") * regime_mult
            return out

        # Fallback to latest macro label from market features when regime label lacks macro dimension.
        if not macro_label:
            market_rows = m[m.get("ticker", "").astype(str).str.upper() == "MARKET"].copy()
            if not market_rows.empty and "macro_regime_label" in market_rows.columns:
                latest_market = market_rows.sort_values("availability_date", kind="mergesort").tail(1)
                lbl = str(latest_market["macro_regime_label"].iloc[0]).strip().lower()
                if lbl == "contraction":
                    regime_mult = 0.8
                elif lbl == "expansion":
                    regime_mult = 1.1

        out["macro_multiplier"] = pd.to_numeric(out["macro_multiplier"], errors="coerce") * regime_mult
        out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce") * regime_mult

        if "sector" in out.columns:
            sector_rows = m[m.get("ticker", "").astype(str) != "MARKET"].copy()
            if "sector" in sector_rows.columns and "sector_activity_zscore" in sector_rows.columns:
                sector_latest = (
                    sector_rows.sort_values(["sector", "availability_date"], kind="mergesort")
                    .groupby("sector", as_index=False)
                    .tail(1)
                )
                out = out.merge(
                    sector_latest[["sector", "sector_activity_zscore"]],
                    on="sector",
                    how="left",
                    suffixes=("", "_macro"),
                )
                low = pd.to_numeric(out["sector_activity_zscore"], errors="coerce") < -1.5
                high = pd.to_numeric(out["sector_activity_zscore"], errors="coerce") > 1.5
                out.loc[low, "macro_multiplier"] = pd.to_numeric(out.loc[low, "macro_multiplier"], errors="coerce") * 0.7
                out.loc[low, "sentiment_multiplier"] = pd.to_numeric(out.loc[low, "sentiment_multiplier"], errors="coerce") * 0.7
                out.loc[high, "macro_multiplier"] = pd.to_numeric(out.loc[high, "macro_multiplier"], errors="coerce") * 1.15
                out.loc[high, "sentiment_multiplier"] = pd.to_numeric(out.loc[high, "sentiment_multiplier"], errors="coerce") * 1.15

        out["sentiment_multiplier"] = pd.to_numeric(out["sentiment_multiplier"], errors="coerce").clip(0.0, 1.5)
        out["adjusted_score"] = pd.to_numeric(out["model_score"], errors="coerce") * out["sentiment_multiplier"]
        return out
