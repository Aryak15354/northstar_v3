#!/usr/bin/env python3
"""Backfill the point-in-time ``availability_date`` column on canonical
alternative-data artifacts (bulk deals, announcements).

Why this exists
---------------
``src/data/artifact_contracts.py`` requires every canonical artifact to carry an
``availability_date`` column so downstream point-in-time (PIT) filtering has an
explicit "when did we know this" timestamp rather than inferring one. The NSE
bulk-deal and announcement canonical parquets were built before that column was
part of the contract, so ``make invariants`` / ``check_canonical_artifact_contracts``
flags them as ``missing_columns:availability_date``.

The alternative-data *loader* (``src/ingestion/alternative_loader.py``) already
synthesizes a conservative ``availability_date`` at read time when the column is
absent, so this is not a correctness hole in the live path — it is the canonical
*artifact* not persisting the column the contract promises. This script writes it
in, using the same convention as the loader, so the artifact is self-describing
and the contract passes.

PIT convention (matches the loader / exchange reality)
------------------------------------------------------
* bulk_deals  : deals are disseminated after market close on the trade date, so
                ``availability_date = date + 1 business day`` (the loader's
                ``safety_lag_days=1`` default).
* announcements: the exchange stamps the exact public-dissemination time, so use
                ``dissemination_datetime`` when present, falling back to
                ``broadcast_datetime`` -> ``receipt_datetime`` -> ``date``.

Idempotent: re-running is a no-op once the column is present and non-null. Only
rewrites a file it actually changed.

    python scripts/backfill_availability_date_canonical.py            # apply
    python scripts/backfill_availability_date_canonical.py --check    # report only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BULK_DEALS = PROJECT_ROOT / "data/canonical/alternative/bulk_deals_nse_all.parquet"
ANNOUNCEMENTS = PROJECT_ROOT / "data/canonical/alternative/announcements_all.parquet"

BULK_DEAL_SAFETY_LAG_BDAYS = 1


def _needs_backfill(df: pd.DataFrame) -> bool:
    return "availability_date" not in df.columns or df["availability_date"].isna().all()


def _bulk_deal_availability(df: pd.DataFrame) -> pd.Series:
    date = pd.to_datetime(df["date"], errors="coerce")
    return date + BDay(BULK_DEAL_SAFETY_LAG_BDAYS)


def _announcement_availability(df: pd.DataFrame) -> pd.Series:
    # Coalesce, most-precise source first, down to the plain event date.
    out = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    for col in ("dissemination_datetime", "broadcast_datetime", "receipt_datetime", "date"):
        if col in df.columns:
            out = out.fillna(pd.to_datetime(df[col], errors="coerce"))
    return out


def backfill(path: Path, builder, *, check_only: bool) -> bool:
    if not path.exists():
        print(f"SKIP  {path.name}: file not found")
        return True
    df = pd.read_parquet(path)
    if not _needs_backfill(df):
        print(f"OK    {path.name}: availability_date already present ({len(df):,} rows)")
        return True
    if check_only:
        print(f"NEEDS {path.name}: availability_date missing/all-null ({len(df):,} rows)")
        return False
    df["availability_date"] = builder(df)
    null_count = int(df["availability_date"].isna().sum())
    if null_count:
        print(f"WARN  {path.name}: {null_count:,} rows have no derivable availability_date")
    df.to_parquet(path, index=False)
    print(f"WROTE {path.name}: availability_date backfilled ({len(df):,} rows)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report only; do not write")
    args = parser.parse_args()

    ok = True
    ok &= backfill(BULK_DEALS, _bulk_deal_availability, check_only=args.check)
    ok &= backfill(ANNOUNCEMENTS, _announcement_availability, check_only=args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
