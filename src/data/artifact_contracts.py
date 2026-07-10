"""Canonical artifact contracts for Northstar V3 data access.

This module defines the intended source of truth for major data domains and
records legacy aliases that still exist for backwards compatibility. It is
read-only and does not migrate, delete, or rewrite historical data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ArtifactContract:
    name: str
    canonical_path: str
    required_columns: tuple[str, ...]
    date_columns: tuple[str, ...] = ()
    min_rows: int = 1
    aliases: tuple[str, ...] = ()
    description: str = ""

    def canonical_file(self, project_root: Path | None = None) -> Path:
        return (project_root or PROJECT_ROOT) / self.canonical_path

    def alias_files(self, project_root: Path | None = None) -> list[Path]:
        root = project_root or PROJECT_ROOT
        return [root / alias for alias in self.aliases]


@dataclass
class ArtifactValidation:
    name: str
    path: str
    ok: bool
    rows: int = 0
    columns: list[str] = field(default_factory=list)
    latest: str | None = None
    problems: list[str] = field(default_factory=list)


CONTRACTS: dict[str, ArtifactContract] = {
    "equity_prices_daily": ArtifactContract(
        name="equity_prices_daily",
        canonical_path="data/canonical/prices/equity_prices_daily.parquet",
        aliases=("data/processed/prices.parquet", "data/market/daily_prices.parquet"),
        required_columns=("date", "ticker", "open", "high", "low", "close", "volume", "availability_date", "source"),
        date_columns=("date", "availability_date"),
        min_rows=1_000_000,
        description="Point-in-time daily equity price panel. This is the canonical price source.",
    ),
    "fundamentals_annual": ArtifactContract(
        name="fundamentals_annual",
        canonical_path="data/canonical/fundamentals/fundamentals_annual_panel.parquet",
        aliases=("data/market/financials.parquet", "data/processed/fundamentals.parquet"),
        required_columns=("ticker", "fiscal_year", "availability_date"),
        date_columns=("availability_date",),
        min_rows=1_000,
        description="Annual fundamental panel with availability dates.",
    ),
    "fundamentals_quarterly": ArtifactContract(
        name="fundamentals_quarterly",
        canonical_path="data/canonical/fundamentals/fundamentals_quarterly_panel.parquet",
        aliases=(),
        required_columns=("ticker", "quarter", "availability_date"),
        date_columns=("availability_date",),
        min_rows=1_000,
        description="Quarterly fundamental panel with availability dates.",
    ),
    "macro_regime_features": ArtifactContract(
        name="macro_regime_features",
        canonical_path="data/canonical/macro/macro_regime_features.parquet",
        aliases=("data/processed/macro_factors.parquet", "data/macro/comprehensive_rbi_data.parquet"),
        required_columns=("date", "availability_date", "ticker"),
        date_columns=("date", "availability_date"),
        min_rows=10,
        description="Canonical macro regime feature surface.",
    ),
    "company_news_history": ArtifactContract(
        name="company_news_history",
        canonical_path="data/canonical/news/company_news_history.parquet",
        aliases=("data/processed/news/news_dataset.parquet",),
        required_columns=("date", "availability_date", "ticker", "headline", "source"),
        date_columns=("date", "availability_date"),
        min_rows=10_000,
        description="Company-linked news history.",
    ),
    "company_sentiment_daily": ArtifactContract(
        name="company_sentiment_daily",
        canonical_path="data/canonical/sentiment/company_sentiment_daily.parquet",
        aliases=("data/processed/sentiment/ticker_sentiment_daily.parquet",),
        required_columns=("ticker", "date", "availability_date", "sentiment_polarity", "sentiment_conviction"),
        date_columns=("date", "availability_date"),
        min_rows=10_000,
        description="Daily company sentiment panel.",
    ),
    "market_sentiment_daily": ArtifactContract(
        name="market_sentiment_daily",
        canonical_path="data/canonical/sentiment/market_sentiment_daily.parquet",
        aliases=("data/processed/sentiment/market_sentiment_daily.parquet",),
        required_columns=("date", "availability_date"),
        date_columns=("date", "availability_date"),
        min_rows=100,
        description="Daily market sentiment panel.",
    ),
    "bulk_deals": ArtifactContract(
        name="bulk_deals",
        canonical_path="data/canonical/alternative/bulk_deals_nse_all.parquet",
        aliases=("data/processed/alternative/bulk_deals_nse_all.parquet", "data/processed/alternative/bulk_deals_all.parquet"),
        required_columns=("date", "availability_date", "nse_ticker", "source"),
        date_columns=("date", "availability_date"),
        min_rows=10_000,
        description="Canonical NSE bulk deal event history.",
    ),
    "announcements": ArtifactContract(
        name="announcements",
        canonical_path="data/canonical/alternative/announcements_all.parquet",
        aliases=("data/processed/alternative/announcements_all.parquet", "data/processed/alternative/announcements_all.csv"),
        required_columns=("date", "availability_date", "nse_ticker", "headline", "source"),
        date_columns=("date", "availability_date"),
        min_rows=1_000,
        description="Canonical NSE announcement history.",
    ),
}


def get_contract(name: str) -> ArtifactContract:
    try:
        return CONTRACTS[name]
    except KeyError as exc:
        raise KeyError(f"unknown_artifact_contract:{name}") from exc


def resolve_artifact(name: str, *, project_root: Path | None = None, allow_alias: bool = False) -> Path:
    contract = get_contract(name)
    canonical = contract.canonical_file(project_root)
    if canonical.exists():
        return canonical
    if allow_alias:
        for alias in contract.alias_files(project_root):
            if alias.exists():
                return alias
    raise FileNotFoundError(f"artifact_missing:{name}:{canonical}")


def read_artifact(
    name: str,
    *,
    project_root: Path | None = None,
    columns: Iterable[str] | None = None,
    allow_alias: bool = False,
) -> pd.DataFrame:
    path = resolve_artifact(name, project_root=project_root, allow_alias=allow_alias)
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, usecols=list(columns) if columns else None)
    return pd.read_parquet(path, columns=list(columns) if columns else None)


def validate_contract(name: str, *, project_root: Path | None = None) -> ArtifactValidation:
    contract = get_contract(name)
    path = contract.canonical_file(project_root)
    problems: list[str] = []
    if not path.exists():
        return ArtifactValidation(name=name, path=str(path), ok=False, problems=["missing"])

    try:
        if path.suffix.lower() == ".csv":
            df_head = pd.read_csv(path, nrows=5)
            columns = list(df_head.columns)
            rows = sum(1 for _ in path.open("rb")) - 1
        else:
            pf = pq.ParquetFile(path)
            columns = list(pf.schema.names)
            rows = int(pf.metadata.num_rows)
    except Exception as exc:
        return ArtifactValidation(name=name, path=str(path), ok=False, problems=[f"unreadable:{type(exc).__name__}:{exc}"])

    missing_columns = [col for col in contract.required_columns if col not in columns]
    if missing_columns:
        problems.append(f"missing_columns:{','.join(missing_columns)}")
    if rows < contract.min_rows:
        problems.append(f"too_few_rows:{rows}<{contract.min_rows}")

    latest = None
    for date_col in contract.date_columns:
        if date_col not in columns:
            continue
        try:
            series = read_artifact(name, project_root=project_root, columns=[date_col])[date_col]
            parsed = pd.to_datetime(series, errors="coerce").dropna()
            if not parsed.empty:
                latest = str(pd.Timestamp(parsed.max()))
                break
        except Exception as exc:
            problems.append(f"date_check_failed:{date_col}:{type(exc).__name__}")

    return ArtifactValidation(
        name=name,
        path=str(path),
        ok=not problems,
        rows=rows,
        columns=columns,
        latest=latest,
        problems=problems,
    )


def validate_all_contracts(*, project_root: Path | None = None) -> list[ArtifactValidation]:
    return [validate_contract(name, project_root=project_root) for name in CONTRACTS]
