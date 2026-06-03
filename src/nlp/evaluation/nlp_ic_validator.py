"""Validate the cross-sectional IC of the new NLP sentiment signals."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


class NLPICValidator:
    """Computes weekly rank IC for company-level NLP sentiment."""

    def __init__(
        self,
        sentiment_path: str = "data/canonical/sentiment/company_sentiment_daily.parquet",
        prices_path: str = "data/canonical/prices/equity_prices_daily.parquet",
        universe_path: str = "data/processed/portfolio_weights.parquet",
    ) -> None:
        self._sentiment_path = sentiment_path
        self._prices_path = prices_path
        self._universe_path = universe_path

    def run_full_validation(
        self,
        forward_return_days: int = 5,
        min_stocks_per_week: int = 25,
        start_date: str = "2018-01-01",
        output_path: str = "data/nlp/evaluation/ic_reports/nlp_ic_report.json",
    ) -> dict[str, Any]:
        sentiment = pd.read_parquet(self._sentiment_path)
        prices = pd.read_parquet(self._prices_path)
        sentiment["date"] = pd.to_datetime(sentiment["date"], errors="coerce")
        sentiment["availability_date"] = pd.to_datetime(sentiment.get("availability_date", sentiment["date"]), errors="coerce")
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")

        price_panel = prices.pivot(index="date", columns="ticker", values="close").sort_index()
        forward_returns = price_panel.pct_change(periods=forward_return_days, fill_method=None).shift(-forward_return_days)
        if self._universe_path and Path(self._universe_path).exists():
            universe = pd.read_parquet(self._universe_path)
            covered_tickers = set(universe.get("ticker", pd.Series(dtype=str)).astype(str))
            if covered_tickers:
                sentiment = sentiment[sentiment["ticker"].isin(covered_tickers)]

        weekly_rows: list[dict[str, Any]] = []
        for week_end in pd.date_range(start=start_date, end=prices["date"].max(), freq="W-FRI"):
            eligible = sentiment[sentiment["availability_date"] <= week_end].sort_values(["ticker", "availability_date"], kind="mergesort")
            latest = eligible.groupby("ticker", sort=False).tail(1)
            if len(latest) < min_stocks_per_week or week_end not in forward_returns.index:
                continue
            fwd = forward_returns.loc[week_end].rename("forward_return").reset_index()
            merged = latest.merge(fwd, on="ticker", how="inner").dropna(subset=["sentiment_polarity", "forward_return"])
            if len(merged) < 15:
                continue
            ic, pvalue = spearmanr(merged["sentiment_polarity"], merged["forward_return"])
            weekly_rows.append(
                {
                    "date": week_end,
                    "ic": float(ic) if pd.notna(ic) else 0.0,
                    "pvalue": float(pvalue) if pd.notna(pvalue) else 1.0,
                    "n_stocks": int(len(merged)),
                    "year": int(week_end.year),
                }
            )

        if not weekly_rows:
            return {"status": "no_data"}
        ic_df = pd.DataFrame(weekly_rows)
        mean_ic = float(ic_df["ic"].mean())
        std_ic = float(ic_df["ic"].std(ddof=0))
        hit_rate = float((ic_df["ic"] > 0).mean())
        ir = float(mean_ic / std_ic) if std_ic > 0 else 0.0
        t_stat = float(mean_ic / (std_ic / np.sqrt(len(ic_df)))) if std_ic > 0 else 0.0
        result = {
            "mean_ic": mean_ic,
            "std_ic": std_ic,
            "ic_ir": ir,
            "hit_rate": hit_rate,
            "t_statistic": t_stat,
            "n_weeks": int(len(ic_df)),
            "by_year": ic_df.groupby("year")["ic"].agg(["mean", "std", "count"]).to_dict("index"),
            "pass": bool(mean_ic > 0.015 and t_stat > 1.5),
            "model_version": "nlp_finbert",
            "run_date": pd.Timestamp.utcnow().isoformat(),
        }
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        logger.info("NLP IC validation mean_ic=%.4f t_stat=%.2f pass=%s", mean_ic, t_stat, result["pass"])
        return result
