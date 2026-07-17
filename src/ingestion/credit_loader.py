"""PIT-safe loader for bank/NBFC credit factors from NSE XBRL results.

Reads ``data/processed/sector_financials/credit_quarterly.parquet`` (built by
``xbrl_results_fetcher``) and exposes the EXP-13 credit cross-section with correct
point-in-time discipline: a filing is visible only on/after its exchange broadcast
(``availability_date``), so there is no reporting-lag guesswork — the market genuinely
could not act on the numbers before that instant.

    from src.ingestion.credit_loader import CreditLoader
    df = CreditLoader().load(as_of_date=datetime(2025, 3, 1), tickers=["HDFCBANK"])
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CREDIT_PARQUET = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "credit_quarterly.parquet"

# Canonical credit factors surfaced to research. Ratios are fractions (0.0142 = 1.42%).
CREDIT_FACTORS = [
    "gnpa_pct", "nnpa_pct", "roa", "cet1_ratio", "at1_ratio",
    "net_interest_income", "provisions", "credit_cost_to_nii",
    "provision_coverage_ratio", "interest_earned", "interest_expended",
    "impairment_financial", "profit_before_tax",
]


class CreditLoader:
    def __init__(self, parquet_path: Optional[Path] = None, prefer_basis: str = "standalone"):
        self.parquet_path = Path(parquet_path) if parquet_path else CREDIT_PARQUET
        self.prefer_basis = prefer_basis

    def _read(self) -> pd.DataFrame:
        if not self.parquet_path.exists():
            return pd.DataFrame()
        df = pd.read_parquet(self.parquet_path)
        df["period_end"] = pd.to_datetime(df["period_end"], errors="coerce")
        df["availability_date"] = pd.to_datetime(df["availability_date"], errors="coerce")
        return df

    def load(
        self,
        as_of_date: Optional[datetime] = None,
        tickers: Optional[Iterable[str]] = None,
        basis: Optional[str] = None,
        latest_only: bool = False,
    ) -> pd.DataFrame:
        """Return credit rows visible as of ``as_of_date`` (by broadcast date).

        latest_only=True collapses to the most recent visible quarter per symbol.
        """
        df = self._read()
        if df.empty:
            return df
        basis = basis or self.prefer_basis
        if basis:
            # keep preferred basis; fall back to the other only where absent
            df["_rank"] = (df["basis"] == basis).astype(int)
            df = df.sort_values("_rank").drop_duplicates(
                subset=["symbol", "period_end"], keep="last"
            ).drop(columns="_rank")
        if as_of_date is not None:
            cutoff = pd.Timestamp(as_of_date)
            # PIT: only filings the market could see; availability_date must exist and be <= cutoff
            df = df[df["availability_date"].notna() & (df["availability_date"] <= cutoff)]
        if tickers is not None:
            wanted = {str(t).replace(".NS", "").upper() for t in tickers}
            df = df[df["symbol"].isin(wanted)]
        df = df.sort_values(["symbol", "period_end"])
        if latest_only and not df.empty:
            df = df.groupby("symbol", as_index=False).tail(1)
        return df.reset_index(drop=True)

    def load_factor_panel(
        self,
        as_of_date: Optional[datetime] = None,
        tickers: Optional[Iterable[str]] = None,
    ) -> pd.DataFrame:
        """Wide one-row-per-symbol panel of the latest visible credit factors."""
        latest = self.load(as_of_date=as_of_date, tickers=tickers, latest_only=True)
        if latest.empty:
            return latest
        keep = ["symbol", "period_end", "availability_date"] + [c for c in CREDIT_FACTORS if c in latest.columns]
        return latest[keep].reset_index(drop=True)
