"""Canonical price access helpers with legacy dashboard/backtest columns."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .artifact_contracts import PROJECT_ROOT, resolve_artifact
from .query_engine import DuckDBQueryEngine


_LEGACY_TO_CANONICAL = {
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}
_CANONICAL_TO_LEGACY = {value: key for key, value in _LEGACY_TO_CANONICAL.items()}


def canonical_price_path(*, project_root: Path | None = None) -> Path:
    return resolve_artifact("equity_prices_daily", project_root=project_root or PROJECT_ROOT)


def canonical_price_columns(columns: Iterable[str] | None) -> list[str] | None:
    if columns is None:
        return None
    out: list[str] = []
    for column in columns:
        mapped = _LEGACY_TO_CANONICAL.get(str(column), str(column))
        if mapped not in out:
            out.append(mapped)
    return out


def prices_to_legacy_shape(df: pd.DataFrame) -> pd.DataFrame:
    out = df.rename(columns={k: v for k, v in _CANONICAL_TO_LEGACY.items() if k in df.columns})
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    return out


def read_prices_legacy(
    *,
    project_root: Path | None = None,
    columns: Sequence[str] | None = None,
    tickers: Sequence[str] | None = None,
    start_date: pd.Timestamp | str | None = None,
    end_date: pd.Timestamp | str | None = None,
    query: DuckDBQueryEngine | None = None,
) -> pd.DataFrame:
    """Read canonical prices while returning legacy columns such as Date/Close."""
    path = canonical_price_path(project_root=project_root)
    read_columns = canonical_price_columns(columns)
    engine = query or DuckDBQueryEngine(memory_limit_mb=768, threads=1)
    ticker_values = [str(ticker) for ticker in list(tickers or []) if str(ticker)]
    if engine.available:
        df = engine.read_parquet(
            path,
            columns=read_columns,
            date_col="date",
            start_date=start_date,
            end_date=end_date,
            in_filters={"ticker": ticker_values} if ticker_values else None,
        )
    else:
        filters = []
        if ticker_values:
            filters.append(("ticker", "in", ticker_values))
        df = pd.read_parquet(path, columns=read_columns, filters=filters or None)
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"], errors="coerce")
            if start_date is not None:
                df = df.loc[dates >= pd.to_datetime(start_date, errors="coerce")]
            if end_date is not None:
                df = df.loc[dates <= pd.to_datetime(end_date, errors="coerce")]
    return prices_to_legacy_shape(df)
