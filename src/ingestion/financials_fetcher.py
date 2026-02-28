#!/usr/bin/env python3
"""
YFinance quarterly financials fetcher.

Writes/updates:
- data/raw/financials_quarterly/<TICKER>_income.csv
- data/raw/financials_quarterly/<TICKER>_balance.csv
- data/raw/financials_quarterly/<TICKER>_cashflow.csv

This module is intentionally idempotent:
- deduplicates by quarter date
- keeps the latest fetched row for a duplicate date
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import yfinance as yf


UNIVERSE_FILE = Path("universe/nifty500.csv")
RAW_FIN_DIR = Path("data/raw/financials_quarterly")
MANIFEST_PATH = RAW_FIN_DIR / "last_update_manifest.json"


def normalize_ticker(ticker: str) -> str:
    t = str(ticker).strip().upper()
    if not t.endswith(".NS"):
        t = f"{t}.NS"
    return t


def _to_quarterly_frame(statement: pd.DataFrame) -> pd.DataFrame:
    if statement is None or statement.empty:
        return pd.DataFrame()
    out = statement.T.copy()
    out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()]
    if out.empty:
        return pd.DataFrame()
    out.index.name = "Date"
    out = out.reset_index()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return out


def _merge_statement_rows(new_rows: pd.DataFrame, out_file: Path) -> int:
    if new_rows is None or new_rows.empty:
        return 0
    if out_file.exists():
        old = pd.read_csv(out_file)
        merged = pd.concat([old, new_rows], ignore_index=True, sort=False)
    else:
        merged = new_rows.copy()
    merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce")
    merged = merged.dropna(subset=["Date"])
    merged = merged.sort_values("Date")
    merged = merged.drop_duplicates(subset=["Date"], keep="last")
    merged["Date"] = merged["Date"].dt.strftime("%Y-%m-%d")
    merged.to_csv(out_file, index=False)
    return len(new_rows)


def _statement_from_ticker(stock: yf.Ticker, candidates: Iterable[str]) -> pd.DataFrame:
    for attr in candidates:
        try:
            data = getattr(stock, attr)
            if isinstance(data, pd.DataFrame) and not data.empty:
                return data
        except Exception:
            continue
    return pd.DataFrame()


def fetch_financials_for_ticker(ticker: str, raw_dir: Path, sleep_seconds: float = 0.0) -> dict:
    t = normalize_ticker(ticker)
    stock = yf.Ticker(t)

    income = _statement_from_ticker(stock, ["quarterly_income_stmt", "quarterly_financials"])
    balance = _statement_from_ticker(stock, ["quarterly_balance_sheet"])
    cashflow = _statement_from_ticker(stock, ["quarterly_cash_flow", "quarterly_cashflow"])

    income_df = _to_quarterly_frame(income)
    balance_df = _to_quarterly_frame(balance)
    cashflow_df = _to_quarterly_frame(cashflow)

    raw_dir.mkdir(parents=True, exist_ok=True)
    n_income = _merge_statement_rows(income_df, raw_dir / f"{t}_income.csv")
    n_balance = _merge_statement_rows(balance_df, raw_dir / f"{t}_balance.csv")
    n_cashflow = _merge_statement_rows(cashflow_df, raw_dir / f"{t}_cashflow.csv")

    if sleep_seconds > 0:
        time.sleep(max(0.0, float(sleep_seconds)))

    return {
        "ticker": t,
        "income_rows": int(len(income_df)),
        "balance_rows": int(len(balance_df)),
        "cashflow_rows": int(len(cashflow_df)),
        "written_income_rows": int(n_income),
        "written_balance_rows": int(n_balance),
        "written_cashflow_rows": int(n_cashflow),
        "ok": bool(len(income_df) or len(balance_df) or len(cashflow_df)),
    }


def _load_universe_tickers(universe_file: Path) -> List[str]:
    if not universe_file.exists():
        raise FileNotFoundError(f"Universe file not found: {universe_file}")
    uni = pd.read_csv(universe_file)
    if "Symbol" not in uni.columns:
        raise ValueError("Universe file must contain 'Symbol' column")
    return [normalize_ticker(x) for x in uni["Symbol"].dropna().astype(str).tolist()]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fetch quarterly financials from yfinance")
    p.add_argument("--tickers", type=str, default="", help="Comma-separated tickers; defaults to universe")
    p.add_argument("--universe-file", type=str, default=str(UNIVERSE_FILE))
    p.add_argument("--raw-dir", type=str, default=str(RAW_FIN_DIR))
    p.add_argument("--max-tickers", type=int, default=0, help="Optional cap for faster ad-hoc runs")
    p.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep between requests")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = Path(args.raw_dir)

    if args.tickers.strip():
        tickers = [normalize_ticker(t) for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = _load_universe_tickers(Path(args.universe_file))

    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[: args.max_tickers]

    results = []
    ok_count = 0
    fail_count = 0
    for idx, ticker in enumerate(tickers, start=1):
        print(f"[{idx}/{len(tickers)}] Fetching {ticker} ...")
        try:
            res = fetch_financials_for_ticker(
                ticker=ticker,
                raw_dir=raw_dir,
                sleep_seconds=args.sleep_seconds,
            )
            results.append(res)
            if res["ok"]:
                ok_count += 1
            else:
                fail_count += 1
        except Exception as e:
            fail_count += 1
            results.append({"ticker": ticker, "ok": False, "error": str(e)})
            print(f"   ❌ {ticker}: {e}")

    manifest = {
        "tickers_requested": len(tickers),
        "success": ok_count,
        "failed": fail_count,
        "results": results,
        "raw_dir": str(raw_dir),
    }
    raw_dir.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"✅ Financial fetch complete: requested={len(tickers)}, success={ok_count}, failed={fail_count}, "
        f"manifest={MANIFEST_PATH}"
    )
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
