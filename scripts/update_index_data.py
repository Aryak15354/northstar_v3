#!/usr/bin/env python3
"""
📈 INDEX DATA UPDATER

Primary source:
- yfinance (Yahoo)

Fallback source (offline/network degraded):
- locally synthesized proxy indices from `data/processed/prices.parquet`
  + `universe/nifty500.csv`

This keeps dashboard benchmark artifacts fresh even when Yahoo DNS fails.

Usage:
  python scripts/update_index_data.py
  python scripts/update_index_data.py --period 5y
"""

import argparse
import re
import socket
from pathlib import Path

import numpy as np
import pandas as pd

INDEX_MAP = {
    "nifty_50": "^NSEI",
    "nifty_100": "^CNX100",
    "nifty_500": "^CRSLDX",
    # Sector & thematic indices (optional dashboard benchmarks)
    "nifty_bank": "^NSEBANK",
    "nifty_it": "^CNXIT",
    "nifty_fmcg": "^CNXFMCG",
    "nifty_auto": "^CNXAUTO",
    "nifty_pharma": "^CNXPHARMA",
    "nifty_metal": "^CNXMETAL",
    "nifty_realty": "^CNXREALTY",
    "nifty_energy": "^CNXENERGY",
    "nifty_psu": "^CNXPSE",
}


def _parse_period_days(period: str) -> int | None:
    p = str(period).strip().lower()
    if p == "max":
        return None
    m = re.fullmatch(r"(\d+)\s*([dwmy])", p)
    if not m:
        return 365 * 5
    n = int(m.group(1))
    u = m.group(2)
    if u == "d":
        return n
    if u == "w":
        return n * 7
    if u == "m":
        return n * 30
    return n * 365


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.rename(columns=lambda c: str(c).strip().lower().replace(" ", "_"))
    df.index.name = "Date"
    return df.sort_index()


def _stitch_price_levels(
    series: pd.Series,
    *,
    jump_threshold: float = 0.35,
    max_scale_step: float = 50.0,
    max_abs_scale: float = 1e6,
) -> pd.Series:
    """
    Remove structural level breaks (splits/source scaling) while preserving returns.

    We treat very large one-day jumps as data-level shifts and rescale the subsequent
    segment to keep continuity. This makes proxy index construction robust.
    """
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if s.dropna().shape[0] < 3:
        return s

    raw = s.to_numpy(dtype=float)
    out = np.full_like(raw, np.nan, dtype=float)
    scale = 1.0
    prev = np.nan
    for i, v in enumerate(raw):
        if not np.isfinite(v) or v <= 0:
            out[i] = np.nan
            continue
        cur = v * scale
        if np.isfinite(prev) and prev > 0:
            r = (cur / prev) - 1.0
            if abs(r) > jump_threshold:
                step = float(prev / max(v, 1e-12))
                step = float(np.clip(step, 1.0 / max_scale_step, max_scale_step))
                scale *= step
                scale = float(np.clip(scale, 1.0 / max_abs_scale, max_abs_scale))
                cur = v * scale
        out[i] = cur
        prev = cur
    return pd.Series(out, index=s.index, name=s.name)


def _robustify_cross_sectional_returns(ret_w: pd.DataFrame) -> pd.DataFrame:
    """
    Winsorize constituent returns cross-sectionally per date to reduce outlier bleed.
    """
    if ret_w.empty:
        return ret_w

    ret = ret_w.replace([np.inf, -np.inf], np.nan).copy()

    def _clip_row(row: pd.Series) -> pd.Series:
        vals = row.dropna()
        if vals.empty:
            return row
        if len(vals) >= 8:
            q_lo = float(vals.quantile(0.05))
            q_hi = float(vals.quantile(0.95))
            lo = max(q_lo, -0.20)
            hi = min(q_hi, 0.20)
        else:
            lo, hi = -0.20, 0.20
        return row.clip(lower=lo, upper=hi)

    return ret.apply(_clip_row, axis=1)


def _load_local_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices_path = Path("data/processed/prices.parquet")
    universe_path = Path("universe/nifty500.csv")
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing {prices_path}")
    if not universe_path.exists():
        raise FileNotFoundError(f"Missing {universe_path}")

    prices = pd.read_parquet(prices_path)
    required = {"Date", "ticker", "Close", "Volume"}
    if not required.issubset(prices.columns):
        raise ValueError(f"{prices_path} missing required columns: {sorted(required - set(prices.columns))}")

    prices = prices[["Date", "ticker", "Close", "Volume"]].copy()
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices["Volume"] = pd.to_numeric(prices["Volume"], errors="coerce").fillna(0.0)
    prices = prices.dropna(subset=["Date", "ticker", "Close"]).sort_values(["Date", "ticker"])
    prices = prices[prices["Date"].dt.dayofweek < 5].copy()

    universe = pd.read_csv(universe_path)
    if "Symbol" not in universe.columns:
        raise ValueError(f"{universe_path} missing Symbol column")
    universe["ticker"] = universe["Symbol"].astype(str).str.strip() + ".NS"
    if "Industry" not in universe.columns:
        universe["Industry"] = "Unknown"
    if "Company Name" not in universe.columns:
        universe["Company Name"] = universe["ticker"]

    return prices, universe


def _select_constituents(index_name: str, universe: pd.DataFrame, liquid_rank: pd.Series) -> list[str]:
    u = universe.copy()

    def _by_industry(names: list[str]) -> list[str]:
        mask = u["Industry"].astype(str).str.lower().isin([n.lower() for n in names])
        return sorted(set(u.loc[mask, "ticker"].astype(str)))

    if index_name == "nifty_50":
        return liquid_rank.head(50).index.astype(str).tolist()
    if index_name == "nifty_100":
        return liquid_rank.head(100).index.astype(str).tolist()
    if index_name == "nifty_500":
        return liquid_rank.head(500).index.astype(str).tolist()
    if index_name == "nifty_bank":
        # Bank index proxy: Financial Services names with bank-heavy companies.
        banks = u[
            u["Industry"].astype(str).str.lower().eq("financial services")
            & u["Company Name"].astype(str).str.contains("bank|finance", case=False, regex=True)
        ]["ticker"].astype(str).tolist()
        return sorted(set(banks))
    if index_name == "nifty_it":
        return _by_industry(["Information Technology"])
    if index_name == "nifty_fmcg":
        return _by_industry(["Fast Moving Consumer Goods"])
    if index_name == "nifty_auto":
        return _by_industry(["Automobile and Auto Components"])
    if index_name == "nifty_pharma":
        return _by_industry(["Healthcare"])
    if index_name == "nifty_metal":
        return _by_industry(["Metals & Mining"])
    if index_name == "nifty_realty":
        return _by_industry(["Realty"])
    if index_name == "nifty_energy":
        return _by_industry(["Oil Gas & Consumable Fuels", "Power"])
    if index_name == "nifty_psu":
        # No explicit PSU tag in universe; use diversified public-economy sectors proxy.
        return _by_industry(["Power", "Oil Gas & Consumable Fuels", "Financial Services"])
    return liquid_rank.head(100).index.astype(str).tolist()


def _build_proxy_index(index_name: str, prices: pd.DataFrame, universe: pd.DataFrame, period_days: int | None) -> pd.DataFrame:
    p = prices.copy()
    if period_days is not None:
        cutoff = p["Date"].max() - pd.Timedelta(days=int(period_days) + 120)
        p = p[p["Date"] >= cutoff]

    # Liquidity ranking for broad-index constituent selection.
    p["dollar_vol"] = p["Close"] * p["Volume"]
    liquid_rank = (
        p.groupby("ticker")["dollar_vol"]
        .mean()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
        .sort_values(ascending=False)
    )
    if liquid_rank.empty:
        raise ValueError("No valid liquidity ranking from local prices")

    constituents = _select_constituents(index_name, universe, liquid_rank)
    if not constituents:
        constituents = liquid_rank.head(100).index.astype(str).tolist()

    px = p[p["ticker"].isin(constituents)].copy()
    if px.empty:
        raise ValueError(f"No local prices available for {index_name} constituents")

    close_w = px.pivot_table(index="Date", columns="ticker", values="Close", aggfunc="last").sort_index()
    stitched_close_w = close_w.apply(_stitch_price_levels, axis=0)
    ret_w = stitched_close_w.pct_change(fill_method=None)
    ret_w = _robustify_cross_sectional_returns(ret_w)
    # Equal-weight over available constituents each day.
    idx_ret = ret_w.mean(axis=1, skipna=True).fillna(0.0)
    idx_ret = idx_ret.clip(lower=-0.12, upper=0.12)

    if period_days is not None:
        idx_ret = idx_ret[idx_ret.index >= (idx_ret.index.max() - pd.Timedelta(days=int(period_days)))]
    if idx_ret.empty:
        raise ValueError(f"Insufficient return history for proxy {index_name}")

    base = 100.0
    close = base * (1.0 + idx_ret).cumprod()
    vol = (
        px.groupby("Date")["Volume"]
        .sum()
        .reindex(close.index)
        .fillna(0.0)
    )

    out = pd.DataFrame(
        {
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "adj_close": close,
            "volume": vol,
            "proxy_constituents": float(len(constituents)),
        },
        index=close.index,
    )
    out.index.name = "Date"
    return out.sort_index()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="5y", help="period (e.g. 1y, 5y, 10y, max)")
    args = parser.parse_args()

    out_dir = Path("data/processed/index_data")
    out_dir.mkdir(parents=True, exist_ok=True)
    period_days = _parse_period_days(args.period)

    # Lazy local-load only if needed for fallback.
    local_prices = None
    local_universe = None

    yf = None
    try:
        import yfinance as yf_module  # type: ignore
        yf = yf_module
    except Exception:
        print("⚠️ yfinance unavailable; using local proxy fallback only.")

    # Avoid repeated noisy Yahoo failures when DNS is down.
    if yf is not None:
        try:
            socket.gethostbyname("guce.yahoo.com")
        except Exception:
            print("⚠️ Yahoo DNS unavailable (`guce.yahoo.com`); using local proxy fallback only.")
            yf = None

    saved = 0
    for name, ticker in INDEX_MAP.items():
        print(f"Downloading {name} ({ticker})...")
        out_path = out_dir / f"{name}.parquet"
        df = None

        if yf is not None:
            try:
                raw = yf.download(ticker, period=args.period, auto_adjust=False, progress=False, threads=False)
                if raw is not None and not raw.empty:
                    df = _normalize_ohlcv(raw)
                    print(f"  ✅ Yahoo source ok ({len(df)} rows)")
            except Exception as e:
                print(f"  ⚠️ Yahoo source failed: {e}")

        if df is None or df.empty:
            try:
                if local_prices is None or local_universe is None:
                    local_prices, local_universe = _load_local_inputs()
                df = _build_proxy_index(name, local_prices, local_universe, period_days)
                print(f"  ✅ Local proxy source used ({len(df)} rows)")
            except Exception as e:
                print(f"  ❌ Local proxy fallback failed: {e}")
                if out_path.exists():
                    print(f"  ⚠️ Keeping existing file: {out_path}")
                    continue
                print(f"  ❌ No index data available for {name}")
                continue

        df.to_parquet(out_path)
        saved += 1
        print(f"  Saved {out_path}")

    if saved == 0:
        raise SystemExit("No index artifacts were produced")
    print(f"✅ Index update complete: {saved}/{len(INDEX_MAP)} artifacts refreshed")


if __name__ == "__main__":
    main()
