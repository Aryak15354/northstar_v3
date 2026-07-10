import argparse
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

UNIVERSE_FILE = "universe/nifty500.csv"
RAW_PRICE_DIR = "data/raw/prices_daily"

os.makedirs(RAW_PRICE_DIR, exist_ok=True)


def normalize_ticker(t):
    t = str(t).strip().upper()
    if not t.endswith(".NS"):
        t = t + ".NS"
    return t


def get_last_date(filepath):
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath)
    if df.empty:
        return None
    return pd.to_datetime(df["Date"]).max()

def get_first_date(filepath):
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath)
    if df.empty:
        return None
    return pd.to_datetime(df["Date"]).min()


class DownloadFailed(Exception):
    """A yfinance download errored (network/blocking) — distinct from 'no data'."""


def _download_slice(ticker, start_dt, end_dt, *, timeout_seconds=8):
    if start_dt >= end_dt:
        return pd.DataFrame()
    try:
        data = yf.download(
            ticker,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            progress=False,
            threads=False,
            timeout=max(1, int(timeout_seconds)),
            # Pin explicitly: newer yfinance flipped the default to True. A mix
            # of adjusted/unadjusted fetches is exactly what created the
            # pre-2025 scale discontinuities (TCS 34x) — never rely on defaults.
            auto_adjust=True,
        )
    except Exception as exc:
        raise DownloadFailed(f"{ticker}: {exc}") from exc
    # yf.download swallows per-ticker errors and returns an empty frame; the
    # only reliable failure signal is yf.shared._ERRORS. Surface it so callers
    # can distinguish "Yahoo is broken/blocking" from "no data in range".
    try:
        import yfinance.shared as _yfs
        err = (_yfs._ERRORS or {}).get(ticker)
        if err and data.empty:
            raise DownloadFailed(f"{ticker}: {err}")
    except DownloadFailed:
        raise
    except Exception:
        pass
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)
    if data.empty:
        return pd.DataFrame()
    data.reset_index(inplace=True)
    data["Date"] = data["Date"].dt.strftime("%Y-%m-%d")
    return data[["Date", "Open", "High", "Low", "Close", "Volume"]]


def fetch_and_update(symbol, *, start_year=None, history_years=5, download_timeout=8):
    """Refresh one ticker's daily history by re-downloading the WHOLE window in a
    single request, so the entire series sits on ONE dividend/split adjustment
    basis.

    Why not incremental append: yfinance with auto_adjust=True re-bases the whole
    adjusted series whenever a dividend/split occurs. The old code appended
    today's (newly-rebased) forward slice onto cached rows that were adjusted
    as-of their original fetch date, leaving a permanent discontinuity at the
    append seam. price_sanitizer only catches jumps outside [0.4, 2.5], so a 2:1
    split (0.5) and every dividend (~1% step) passed through silently and
    contaminated returns/momentum. A full re-download eliminates the seam by
    construction — it is still one request per ticker, just a wider date range.
    Cached data is preserved if the download fails, so a network outage never
    destroys history (and DownloadFailed still propagates so the caller's
    broken-feed gate works)."""
    ticker = normalize_ticker(symbol)
    filepath = f"{RAW_PRICE_DIR}/{ticker}.csv"

    if start_year is not None:
        start_floor = datetime(int(start_year), 1, 1)
    else:
        start_floor = datetime.today() - timedelta(days=365 * int(history_years))

    # Never drop existing history: extend the window back to the earliest cached
    # date if it predates the requested floor.
    cached_first = get_first_date(filepath)
    effective_start = start_floor
    if cached_first is not None and cached_first < start_floor:
        effective_start = cached_first

    print(f"⬇ Full refresh {ticker} from {effective_start.date()} (single adjustment basis)")
    try:
        full = _download_slice(
            ticker,
            effective_start,
            datetime.today() + timedelta(days=1),
            timeout_seconds=download_timeout,
        )
    except DownloadFailed:
        # Keep the cached CSV intact; re-raise so main()'s failure gate counts it.
        if os.path.exists(filepath):
            print(f"⚠ full refresh failed for {ticker}; keeping cached history")
        raise

    if full.empty:
        # Yahoo returned nothing (delisted / bad symbol). Preserve any cached
        # history rather than blanking the file.
        if os.path.exists(filepath):
            print(f"⚠ no fresh data for {ticker}; keeping cached history")
            return "cached"
        print(f"⚠ No data for {ticker}")
        return "no_data"

    full = full.drop_duplicates(subset=["Date"]).sort_values("Date")
    full.to_csv(filepath, index=False)
    print(f"✅ {ticker}: {len(full)} rows (last {full['Date'].max()})")
    return "updated"


def main():
    ap = argparse.ArgumentParser(description="Fetch daily price history for the Nifty universe.")
    ap.add_argument("--start-year", type=int, default=None, help="Backfill history starting from this year.")
    ap.add_argument("--history-years", type=int, default=5, help="Default history length if no start-year.")
    ap.add_argument("--max-tickers", type=int, default=0, help="Probe mode: limit tickers processed (0 = all).")
    ap.add_argument(
        "--download-timeout",
        type=int,
        default=8,
        help="Per-request yfinance timeout in seconds.",
    )
    args = ap.parse_args()

    df = pd.read_csv(UNIVERSE_FILE)
    symbols = df["Symbol"].tolist()
    if int(args.max_tickers) > 0:
        symbols = symbols[: int(args.max_tickers)]

    print(f"🚀 Downloading prices for {len(symbols)} Nifty stocks")

    failed = 0
    for sym in symbols:
        try:
            fetch_and_update(
                sym,
                start_year=args.start_year,
                history_years=args.history_years,
                download_timeout=args.download_timeout,
            )
        except DownloadFailed as e:
            failed += 1
            print(f"❌ {sym}: {e}")
        except Exception as e:
            failed += 1
            print(f"❌ {sym}: {e}")

    # Honest exit: if a large share of the universe failed to download, the
    # feed is broken (Yahoo blocking / network / API change) — say so loudly
    # instead of letting stale caches masquerade as a successful refresh.
    fail_frac = failed / max(1, len(symbols))
    print(f"📊 price fetch complete: {len(symbols) - failed}/{len(symbols)} ok, {failed} failed")
    if fail_frac > 0.5:
        print(f"🛑 {fail_frac:.0%} of downloads failed — price feed is BROKEN, refusing to report success")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
