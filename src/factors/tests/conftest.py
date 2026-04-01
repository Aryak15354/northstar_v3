from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def make_price_panel(close_map: dict[str, pd.Series], volume_map: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    rows = []
    for ticker, close in close_map.items():
        close = pd.Series(close).sort_index()
        volume = pd.Series(1_000_000, index=close.index) if volume_map is None else pd.Series(volume_map[ticker]).reindex(close.index)
        for dt, px in close.items():
            rows.append(
                {
                    "Date": pd.Timestamp(dt),
                    "Ticker": ticker,
                    "close": float(px),
                    "adj_close": float(px),
                    "volume": float(volume.loc[dt]),
                }
            )
    return pd.DataFrame(rows).set_index(["Date", "Ticker"]).sort_index()


@dataclass
class DummyMarketLoader:
    prices: pd.DataFrame
    index_df: pd.DataFrame | None = None

    def load(self, as_of_date, tickers=None, fields=None, start_date=None):
        df = self.prices.reset_index()
        df = df[df["Date"] <= pd.Timestamp(as_of_date)]
        if start_date is not None:
            df = df[df["Date"] >= pd.Timestamp(start_date)]
        if tickers is not None:
            df = df[df["Ticker"].isin(tickers)]
        df = df.set_index(["Date", "Ticker"]).sort_index()
        if fields:
            return df[[c for c in fields if c in df.columns]]
        return df

    def load_index(self, as_of_date, index_name=None, start_date=None, fields=None, **kwargs):
        if self.index_df is None:
            return pd.DataFrame()
        df = self.index_df.copy()
        df = df[df.index <= pd.Timestamp(as_of_date)]
        if start_date is not None:
            df = df[df.index >= pd.Timestamp(start_date)]
        if fields:
            return df[[c for c in fields if c in df.columns]]
        return df


@dataclass
class DummyFundamentalLoader:
    factor_financials: dict[str, dict] | None = None
    earnings_history: dict[str, list[dict]] | None = None
    free_float: dict[str, dict] | None = None

    def get_factor_financials(self, as_of_date, tickers=None, frequency="annual", periods=2, reporting_lag_days=None):
        data = dict(self.factor_financials or {})
        if tickers is None:
            return data
        return {ticker: data.get(ticker, {}) for ticker in tickers}

    def get_earnings_history(self, as_of_date, tickers=None, n_quarters=12, safety_lag_days=0, date_field='announcement_date'):
        data = dict(self.earnings_history or {})
        if tickers is None:
            return data
        return {ticker: data.get(ticker, []) for ticker in tickers}

    def get_free_float(self, as_of_date, tickers=None):
        data = dict(self.free_float or {})
        if tickers is None:
            return data
        return {ticker: data.get(ticker, {}) for ticker in tickers}


@dataclass
class DummyAlternativeLoader:
    bulk_history: dict[str, pd.DataFrame] | None = None
    pledge_history: dict[str, pd.DataFrame] | None = None

    def get_bulk_deal_history(self, as_of_date, tickers=None, lookback_days=63, safety_lag_days=1, apply_pit_universe_filter=True):
        data = dict(self.bulk_history or {})
        if tickers is None:
            return data
        return {ticker: data.get(ticker, pd.DataFrame()) for ticker in tickers}

    def load_bulk_deal_history(self, as_of_date, **kwargs):
        return self.get_bulk_deal_history(as_of_date, **kwargs)

    def get_promoter_pledge_history(self, as_of_date, tickers=None, safety_lag_days=25):
        data = dict(self.pledge_history or {})
        if tickers is None:
            return data
        return {ticker: data.get(ticker, pd.DataFrame()) for ticker in tickers}

    def load_promoter_pledge_history(self, as_of_date, **kwargs):
        return self.get_promoter_pledge_history(as_of_date, **kwargs)


@dataclass
class DummyRegistry:
    market: DummyMarketLoader | None = None
    fundamentals: DummyFundamentalLoader | None = None
    alternative: DummyAlternativeLoader | None = None
