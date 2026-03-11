"""Bridge NS-USO sentiment into v3 processed files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pandas.tseries.offsets import BDay


try:
    import duckdb  # type: ignore
except Exception:  # pragma: no cover
    duckdb = None  # type: ignore


@dataclass
class SentimentBridge:
    """
    Reads NS-USO outputs and exports v3-compatible sentiment files.

    Primary source: DuckDB.
    Fallback source: NS-USO parquet exports.
    """

    duckdb_path: str
    output_dir: Path = Path("data/processed/sentiment")

    def __init__(self, duckdb_path: str, output_dir: str = "data/processed/sentiment"):
        self.duckdb_path = str(duckdb_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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
    def _add_availability(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
        out = df.copy()
        out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
        # PIT safety: sentiment from D becomes tradable on D+1 business day.
        out["availability_date"] = out[date_col] + BDay(1)
        return out

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

    def _can_query_duckdb(self) -> bool:
        return duckdb is not None and Path(self.duckdb_path).exists()

    def _duckdb_tables(self) -> set[str]:
        if not self._can_query_duckdb():
            return set()
        try:
            con = duckdb.connect(self.duckdb_path)
            tables = con.execute("SHOW TABLES").fetchdf()["name"].astype(str).tolist()
            con.close()
            return set(tables)
        except Exception:
            return set()

    def _load_ticker_from_duckdb(self) -> pd.DataFrame:
        if not self._can_query_duckdb():
            return pd.DataFrame()
        tables = self._duckdb_tables()
        if not {"sentiment_records", "content_items"}.issubset(tables):
            return pd.DataFrame()

        query = """
            SELECT
                COALESCE(
                    json_extract_string(ci.metadata, '$.ticker'),
                    json_extract_string(ci.metadata, '$.symbol'),
                    json_extract_string(ci.metadata, '$.nse_ticker')
                ) AS ticker,
                CAST(ci.published_at AS DATE) AS date,
                AVG(sr.polarity) AS sentiment_polarity,
                AVG(sr.conviction) AS sentiment_conviction,
                AVG(sr.surprise) AS sentiment_surprise,
                AVG(sr.uncertainty) AS sentiment_uncertainty,
                COUNT(*) AS news_volume,
                'news' AS source
            FROM sentiment_records sr
            JOIN content_items ci ON ci.id = sr.content_id
            GROUP BY 1, 2
        """
        try:
            con = duckdb.connect(self.duckdb_path)
            df = con.execute(query).fetchdf()
            con.close()
        except Exception:
            return pd.DataFrame()
        if df.empty:
            return df
        df["ticker"] = df["ticker"].map(self._normalize_ticker)
        df = df[df["ticker"] != ""].copy()
        return df

    def _load_market_from_duckdb(self) -> pd.DataFrame:
        if not self._can_query_duckdb():
            return pd.DataFrame()
        tables = self._duckdb_tables()
        if "aggregated_signals" not in tables:
            return pd.DataFrame()

        query = """
            SELECT
                CAST(generated_at AS DATE) AS date,
                AVG(polarity) AS india_market_polarity,
                AVG(conviction) AS india_market_conviction,
                AVG(uncertainty) AS india_market_uncertainty,
                AVG(bias) AS global_risk_sentiment,
                COUNT(*) AS news_volume_total
            FROM aggregated_signals
            WHERE LOWER(COALESCE(market, '')) IN ('india', 'indian', 'india equities')
               OR LOWER(COALESCE(asset_class, '')) LIKE '%equit%'
            GROUP BY 1
        """
        try:
            con = duckdb.connect(self.duckdb_path)
            df = con.execute(query).fetchdf()
            con.close()
        except Exception:
            return pd.DataFrame()
        return df

    @staticmethod
    def _load_first_existing(paths: list[Path]) -> pd.DataFrame:
        for p in paths:
            if not p.exists():
                continue
            try:
                return pd.read_parquet(p)
            except Exception:
                continue
        return pd.DataFrame()

    def _load_ticker_fallback(self) -> pd.DataFrame:
        paths = [
            Path("data/sentiment/v3/company_sentiment_trends.parquet"),
            Path("ns_uso/exports/v3/company_sentiment_trends.parquet"),
        ]
        raw = self._load_first_existing(paths)
        if raw.empty:
            return pd.DataFrame()

        df = raw.copy()
        if "timestamp" not in df.columns or "ticker" not in df.columns:
            return pd.DataFrame()

        df["date"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.tz_localize(None).dt.normalize()
        df["ticker"] = df["ticker"].map(self._normalize_ticker)
        df["sentiment_polarity"] = pd.to_numeric(df.get("sentiment_score"), errors="coerce").clip(-1.0, 1.0)

        trend = pd.to_numeric(df.get("trend_score"), errors="coerce")
        trend_abs = trend.abs()
        if trend_abs.notna().any() and float(trend_abs.max()) > 0:
            conv = (trend_abs / float(trend_abs.max())).clip(0.0, 1.0)
        else:
            conv = pd.Series(0.5, index=df.index, dtype=float)
        df["sentiment_conviction"] = conv

        df["sentiment_surprise"] = pd.to_numeric(df.get("event_shock_factor"), errors="coerce").abs().clip(0.0, 1.0)
        df["sentiment_uncertainty"] = (1.0 - df["sentiment_conviction"]).clip(0.0, 1.0)
        df["news_volume"] = pd.to_numeric(df.get("headline_count"), errors="coerce").fillna(0).astype(int)
        df["source"] = df.get("source_mode", "combined").astype(str)

        out = (
            df.groupby(["ticker", "date"], as_index=False)
            .agg(
                sentiment_polarity=("sentiment_polarity", "mean"),
                sentiment_conviction=("sentiment_conviction", "mean"),
                sentiment_surprise=("sentiment_surprise", "mean"),
                sentiment_uncertainty=("sentiment_uncertainty", "mean"),
                news_volume=("news_volume", "sum"),
                source=("source", "last"),
            )
        )
        return out

    def _load_news_dataset_ticker_fallback(self) -> pd.DataFrame:
        paths = [
            Path("data/processed/news/news_dataset.parquet"),
            Path("data/processed/news/news_dataset.csv"),
        ]
        raw = pd.DataFrame()
        for p in paths:
            if not p.exists():
                continue
            try:
                raw = pd.read_parquet(p) if p.suffix.lower() == ".parquet" else pd.read_csv(p)
                break
            except Exception:
                continue
        if raw.empty:
            return pd.DataFrame()

        date_col = "date" if "date" in raw.columns else "timestamp" if "timestamp" in raw.columns else None
        if date_col is None:
            return pd.DataFrame()

        df = raw.copy()
        if "ticker" not in df.columns:
            return pd.DataFrame()
        df["ticker"] = df["ticker"].map(self._normalize_ticker)
        df["date"] = self._normalize_dates(df[date_col])
        if "sentiment" in df.columns:
            df["sentiment_polarity"] = pd.to_numeric(df["sentiment"], errors="coerce").clip(-1.0, 1.0)
        else:
            return pd.DataFrame()
        if "sentiment_conviction" in df.columns:
            df["sentiment_conviction"] = pd.to_numeric(df["sentiment_conviction"], errors="coerce").clip(0.0, 1.0)
        else:
            df["sentiment_conviction"] = pd.to_numeric(df["sentiment_polarity"], errors="coerce").abs().clip(0.0, 1.0)
        df["sentiment_surprise"] = pd.to_numeric(df.get("sentiment_surprise"), errors="coerce").fillna(0.0).clip(0.0, 1.0)
        df["sentiment_uncertainty"] = (
            pd.to_numeric(df.get("sentiment_uncertainty"), errors="coerce")
            .fillna(1.0 - pd.to_numeric(df["sentiment_conviction"], errors="coerce"))
            .clip(0.0, 1.0)
        )
        if "headline" in df.columns:
            df["news_volume"] = 1
        else:
            df["news_volume"] = pd.to_numeric(df.get("news_volume"), errors="coerce").fillna(1).astype(int)
        df["source"] = df.get("source_type", df.get("source", "news")).astype(str)
        out = (
            df.dropna(subset=["ticker", "date"])
            .groupby(["ticker", "date"], as_index=False)
            .agg(
                sentiment_polarity=("sentiment_polarity", "mean"),
                sentiment_conviction=("sentiment_conviction", "mean"),
                sentiment_surprise=("sentiment_surprise", "mean"),
                sentiment_uncertainty=("sentiment_uncertainty", "mean"),
                news_volume=("news_volume", "sum"),
                source=("source", "last"),
            )
        )
        return out

    def _load_market_fallback(self, ticker_df: pd.DataFrame | None = None) -> pd.DataFrame:
        paths = [
            Path("data/sentiment/v3/market_sentiment_india.parquet"),
            Path("ns_uso/exports/v3/market_sentiment_india.parquet"),
        ]
        raw = self._load_first_existing(paths)
        if not raw.empty and "date" in raw.columns:
            df = raw.copy()
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["india_market_polarity"] = pd.to_numeric(df.get("polarity"), errors="coerce")
            df["india_market_conviction"] = pd.to_numeric(df.get("conviction"), errors="coerce")
            df["india_market_uncertainty"] = pd.to_numeric(df.get("uncertainty"), errors="coerce")
            df["global_risk_sentiment"] = pd.to_numeric(
                df.get("global_risk_sentiment", df.get("polarity", np.nan)), errors="coerce"
            )
            if ticker_df is not None and not ticker_df.empty:
                vol = ticker_df.groupby("date", as_index=False)["news_volume"].sum().rename(
                    columns={"news_volume": "news_volume_total"}
                )
                df = df.merge(vol, on="date", how="left")
            if "news_volume_total" not in df.columns:
                df["news_volume_total"] = np.nan
            keep = [
                "date",
                "india_market_polarity",
                "india_market_conviction",
                "india_market_uncertainty",
                "global_risk_sentiment",
                "news_volume_total",
            ]
            return df[keep].dropna(subset=["date"]).sort_values("date", kind="mergesort")

        if ticker_df is not None and not ticker_df.empty:
            df = (
                ticker_df.groupby("date", as_index=False)
                .agg(
                    india_market_polarity=("sentiment_polarity", "mean"),
                    india_market_conviction=("sentiment_conviction", "mean"),
                    india_market_uncertainty=("sentiment_uncertainty", "mean"),
                    global_risk_sentiment=("sentiment_polarity", "mean"),
                    news_volume_total=("news_volume", "sum"),
                )
                .sort_values("date", kind="mergesort")
            )
            return df

        return pd.DataFrame()

    def export_ticker_sentiment(self, start_date: str | None = None) -> pd.DataFrame:
        """Export daily ticker sentiment to v3 processed schema."""
        df = self._load_ticker_from_duckdb()
        if df.empty:
            df = self._load_ticker_fallback()
        if df.empty:
            df = self._load_news_dataset_ticker_fallback()
        if df.empty:
            out = pd.DataFrame(
                columns=[
                    "ticker",
                    "date",
                    "availability_date",
                    "sentiment_polarity",
                    "sentiment_conviction",
                    "sentiment_surprise",
                    "sentiment_uncertainty",
                    "news_volume",
                    "source",
                ]
            )
            out.to_parquet(self.output_dir / "ticker_sentiment_daily.parquet", index=False)
            return out

        out = df.copy()
        out["ticker"] = out["ticker"].map(self._normalize_ticker)
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
        out = out.dropna(subset=["ticker", "date"])
        out = self._add_availability(out, date_col="date")

        for col in ["sentiment_polarity", "sentiment_conviction", "sentiment_surprise", "sentiment_uncertainty"]:
            out[col] = pd.to_numeric(out.get(col), errors="coerce")
        out["sentiment_polarity"] = out["sentiment_polarity"].clip(-1.0, 1.0)
        out["sentiment_conviction"] = out["sentiment_conviction"].clip(0.0, 1.0)
        out["sentiment_surprise"] = out["sentiment_surprise"].clip(0.0, 1.0)
        out["sentiment_uncertainty"] = out["sentiment_uncertainty"].clip(0.0, 1.0)
        out["news_volume"] = pd.to_numeric(out.get("news_volume"), errors="coerce").fillna(0).astype(int)
        out["source"] = out.get("source", "combined").astype(str)

        if start_date:
            sd = pd.to_datetime(start_date, errors="coerce")
            if pd.notna(sd):
                out = out[out["date"] >= sd]

        out = out.sort_values(["ticker", "date"], kind="mergesort")
        out = out.drop_duplicates(subset=["ticker", "date", "source"], keep="last")
        keep = [
            "ticker",
            "date",
            "availability_date",
            "sentiment_polarity",
            "sentiment_conviction",
            "sentiment_surprise",
            "sentiment_uncertainty",
            "news_volume",
            "source",
        ]
        out = out[keep].reset_index(drop=True)
        out.to_parquet(self.output_dir / "ticker_sentiment_daily.parquet", index=False)
        return out

    def export_market_sentiment(self, start_date: str | None = None) -> pd.DataFrame:
        """Export daily market sentiment to v3 processed schema."""
        m = self._load_market_from_duckdb()
        ticker_fallback = None
        if m.empty:
            ticker_fallback = self._load_ticker_fallback()
            if ticker_fallback.empty:
                ticker_fallback = self._load_news_dataset_ticker_fallback()
            m = self._load_market_fallback(ticker_fallback)

        if m.empty:
            out = pd.DataFrame(
                columns=[
                    "date",
                    "availability_date",
                    "india_market_polarity",
                    "india_market_conviction",
                    "india_market_uncertainty",
                    "global_risk_sentiment",
                    "news_volume_total",
                ]
            )
            out.to_parquet(self.output_dir / "market_sentiment_daily.parquet", index=False)
            return out

        out = m.copy()
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
        out = out.dropna(subset=["date"]).sort_values("date", kind="mergesort")
        out = self._add_availability(out, date_col="date")

        for c in [
            "india_market_polarity",
            "india_market_conviction",
            "india_market_uncertainty",
            "global_risk_sentiment",
            "news_volume_total",
        ]:
            out[c] = pd.to_numeric(out.get(c), errors="coerce")

        if start_date:
            sd = pd.to_datetime(start_date, errors="coerce")
            if pd.notna(sd):
                out = out[out["date"] >= sd]

        out = out.drop_duplicates(subset=["date"], keep="last")
        keep = [
            "date",
            "availability_date",
            "india_market_polarity",
            "india_market_conviction",
            "india_market_uncertainty",
            "global_risk_sentiment",
            "news_volume_total",
        ]
        out = out[keep].reset_index(drop=True)
        out.to_parquet(self.output_dir / "market_sentiment_daily.parquet", index=False)
        return out

    def export_all(self, start_date: str | None = None) -> dict[str, Any]:
        """Run both exports and print summary."""
        t = self.export_ticker_sentiment(start_date=start_date)
        m = self.export_market_sentiment(start_date=start_date)

        if t.empty:
            t_summary = "0 rows"
        else:
            t_summary = f"{int(t['ticker'].nunique())} tickers, {t['date'].min().date()} to {t['date'].max().date()}"
        if m.empty:
            m_summary = "0 rows"
        else:
            m_summary = f"{m['date'].min().date()} to {m['date'].max().date()}"

        print(f"[sentiment-bridge] ticker sentiment: {t_summary}")
        print(f"[sentiment-bridge] market sentiment: {m_summary}")
        return {"ticker": t, "market": m}
