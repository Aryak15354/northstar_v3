#!/usr/bin/env python3
"""
Weekly Paper Trading Tracker for Northstar V3.

Run every Monday morning instead of run_morning_pipeline.py.

Features:
1. Runs the morning pipeline for today's date
2. Loads last week's portfolio from data/paper_trading/portfolio_YYYY-MM-DD.csv
3. Calculates last week's equal-weight return on previous top 20
4. Calculates Nifty 50 return for same period
5. Calculates alpha = portfolio return - nifty return
6. Saves this week's new portfolio to data/paper_trading/portfolio_YYYY-MM-DD.csv
7. Appends to data/paper_trading/performance_log.csv
8. Prints clean summary to terminal
"""

from __future__ import annotations

import argparse
import os
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.scoring.daily_scorer import DailyScorer


# Paper trading directories
PAPER_TRADING_DIR = Path("data/paper_trading")
PORTFOLIO_DIR = PAPER_TRADING_DIR
PERFORMANCE_LOG = PAPER_TRADING_DIR / "performance_log.csv"


def _resolve_date(raw: str) -> pd.Timestamp:
    """Resolve date string to Timestamp."""
    if str(raw).strip().lower() == "today":
        return pd.Timestamp.today().normalize()
    return pd.to_datetime(raw, errors="coerce").normalize()


def _load_config(config_path: str) -> dict:
    """Load research policy config."""
    path = Path(config_path)
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}
    return payload


def _get_prev_monday(dt: pd.Timestamp) -> pd.Timestamp:
    """Get previous Monday's date."""
    days_since_monday = dt.dayofweek
    if days_since_monday == 0:  # Today is Monday
        return dt - timedelta(days=7)
    return dt - timedelta(days=days_since_monday + 7)


def _load_prices() -> pd.DataFrame:
    """Load prices data for Nifty 50 returns."""
    prices_path = Path("data/processed/prices.parquet")
    if not prices_path.exists():
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(prices_path)
    except Exception:
        return pd.DataFrame()
    
    if df.empty:
        return df
    
    # Look for Nifty 50 column
    nifty_cols = ["NIFTY 50", "NIFTY50", "NSE S&P CNX NIFTY", "^NSEI", "NIFTY"]
    for col in nifty_cols:
        if col in df.columns:
            return df[["Date", "date"] + [col] if "Date" in df.columns else ["date"] + [col]].copy()
    
    # If no explicit Nifty column, use first column that looks like index
    return df.copy()


def _calculate_nifty_return(start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    """Calculate Nifty 50 return between two dates."""
    prices = _load_prices()
    if prices.empty:
        return 0.0
    
    # Normalize date column
    if "Date" in prices.columns:
        prices["date"] = pd.to_datetime(prices["Date"], errors="coerce")
    elif "date" in prices.columns:
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    else:
        return 0.0
    
    prices = prices.dropna(subset=["date"]).sort_values("date")
    
    # Find Nifty price column
    nifty_cols = ["NIFTY 50", "NIFTY50", "NSE S&P CNX NIFTY", "^NSEI", "NIFTY"]
    nifty_col = None
    for col in nifty_cols:
        if col in prices.columns:
            nifty_col = col
            break
    
    if nifty_col is None:
        # Use first numeric column that's not date
        for col in prices.columns:
            if col != "date" and pd.api.types.is_numeric_dtype(prices[col]):
                nifty_col = col
                break
    
    if nifty_col is None:
        return 0.0
    
    prices["nifty"] = pd.to_numeric(prices[nifty_col], errors="coerce")
    prices = prices.dropna(subset=["nifty"])
    
    if prices.empty:
        return 0.0
    
    # Get prices closest to start and end dates
    start_idx = prices["date"].sub(start_date).abs().idxmin()
    end_idx = prices["date"].sub(end_date).abs().idxmin()
    
    if start_idx == end_idx:
        return 0.0
    
    start_price = prices.loc[start_idx, "nifty"]
    end_price = prices.loc[end_idx, "nifty"]
    
    if start_price == 0 or not np.isfinite(start_price) or not np.isfinite(end_price):
        return 0.0
    
    return (end_price - start_price) / start_price


def _load_last_portfolio(current_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """Load last week's portfolio."""
    if not PORTFOLIO_DIR.exists():
        return pd.DataFrame(), None
    
    # Find most recent portfolio file before current date
    portfolio_files = sorted(PORTFOLIO_DIR.glob("portfolio_*.csv"), reverse=True)
    
    for pf_file in portfolio_files:
        # Extract date from filename
        try:
            date_str = pf_file.stem.replace("portfolio_", "")
            file_date = pd.to_datetime(date_str)
            if file_date < current_date:
                df = pd.read_csv(pf_file)
                return df, file_date
        except Exception:
            continue
    
    return pd.DataFrame(), None


def _calculate_portfolio_return(portfolio: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
    """Calculate equal-weight portfolio return."""
    if portfolio.empty or "ticker" not in portfolio.columns:
        return 0.0
    
    # Load prices
    prices = _load_prices()
    if prices.empty:
        return 0.0
    
    # Normalize date column
    if "Date" in prices.columns:
        prices["date"] = pd.to_datetime(prices["Date"], errors="coerce")
    elif "date" in prices.columns:
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    else:
        return 0.0
    
    prices = prices.dropna(subset=["date"]).sort_values("date")
    
    # Get tickers from portfolio
    tickers = portfolio["ticker"].astype(str).str.replace(".NS", "", regex=False).unique().tolist()
    
    if not tickers:
        return 0.0
    
    # Calculate return for each ticker
    returns = []
    for ticker in tickers:
        # Try both with and without .NS suffix
        ticker_cols = [ticker, f"{ticker}.NS", ticker.replace(".", ""), f"{ticker.replace('.', '')}.NS"]
        
        price_col = None
        for col in ticker_cols:
            if col in prices.columns:
                price_col = col
                break
        
        if price_col is None:
            continue
        
        prices[price_col] = pd.to_numeric(prices[price_col], errors="coerce")
        prices_clean = prices.dropna(subset=[price_col, "date"])
        
        if prices_clean.empty:
            continue
        
        # Get prices closest to start and end dates
        start_idx = prices_clean["date"].sub(start_date).abs().idxmin()
        end_idx = prices_clean["date"].sub(end_date).abs().idxmin()
        
        if start_idx == end_idx:
            continue
        
        start_price = prices_clean.loc[start_idx, price_col]
        end_price = prices_clean.loc[end_idx, price_col]
        
        if start_price == 0 or not np.isfinite(start_price) or not np.isfinite(end_price):
            continue
        
        ret = (end_price - start_price) / start_price
        returns.append(ret)
    
    if not returns:
        return 0.0
    
    # Equal-weight average return
    return float(np.mean(returns))


def _save_portfolio(portfolio: pd.DataFrame, date: pd.Timestamp) -> None:
    """Save portfolio to CSV."""
    PORTFOLIO_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"portfolio_{date.strftime('%Y-%m-%d')}.csv"
    filepath = PORTFOLIO_DIR / filename
    portfolio.to_csv(filepath, index=False)


def _append_performance_log(row: dict) -> None:
    """Append row to performance log."""
    PERFORMANCE_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    if PERFORMANCE_LOG.exists():
        existing = pd.read_csv(PERFORMANCE_LOG)
        existing = existing.append(pd.DataFrame([row]), ignore_index=True)
    else:
        existing = pd.DataFrame([row])
    
    existing.to_csv(PERFORMANCE_LOG, index=False)


def _fmt_pct(v: float) -> str:
    """Format as percentage."""
    sign = "+" if v >= 0 else ""
    return f"{sign}{100.0 * v:.2f}%"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run weekly paper trading tracker")
    p.add_argument("--date", type=str, default="today", help="Date to run for (default: today)")
    p.add_argument("--config", type=str, default="config/research_policy.yaml", help="Config file path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    current_date = _resolve_date(args.date)
    
    if pd.isna(current_date):
        print("ERROR: Invalid date")
        return 1
    
    # Get previous Monday
    prev_monday = _get_prev_monday(current_date)
    
    print("=" * 60)
    print(f"=== Weekly Paper Trading Tracker ===")
    print(f"Week: {prev_monday.strftime('%Y-%m-%d')} to {current_date.strftime('%Y-%m-%d')}")
    print("=" * 60)
    print("")
    
    # Load last week's portfolio
    last_portfolio, last_date = _load_last_portfolio(current_date)
    
    if last_portfolio.empty:
        print("No previous portfolio found (first run?)")
        portfolio_return = 0.0
        nifty_return = 0.0
        alpha = 0.0
    else:
        print(f"Last portfolio: {last_date.strftime('%Y-%m-%d')} ({len(last_portfolio)} positions)")
        
        # Calculate portfolio return
        portfolio_return = _calculate_portfolio_return(last_portfolio, prev_monday, current_date)
        
        # Calculate Nifty return
        nifty_return = _calculate_nifty_return(prev_monday, current_date)
        
        # Calculate alpha
        alpha = portfolio_return - nifty_return
        
        print(f"Portfolio return: {_fmt_pct(portfolio_return)}")
        print(f"Nifty 50 return:  {_fmt_pct(nifty_return)}")
        print(f"Alpha:            {_fmt_pct(alpha)}")
    
    print("")
    
    # Run morning pipeline for current date
    print(f"Running morning pipeline for {current_date.strftime('%Y-%m-%d')}...")
    config = _load_config(args.config)
    config.setdefault("max_weekly_turnover", 0.30)
    
    scorer = DailyScorer(config)
    scored = scorer.score(current_date)
    info = scorer.get_last_info()
    
    if scored.empty:
        print("ERROR: No scored universe for this date!")
        return 1
    
    # Get regime info
    regime = str(info.get("regime", "unknown"))
    print(f"Current Regime: {regime}")
    print("")
    
    # Get top 20 portfolio
    longs = scored[scored["suggested_weight"] > 0].sort_values("final_score", ascending=False).head(20)
    
    if longs.empty:
        print("ERROR: No long positions generated!")
        return 1
    
    # Save portfolio
    portfolio_to_save = longs[["ticker", "model_score", "final_score", "suggested_weight"]].copy()
    _save_portfolio(portfolio_to_save, current_date)
    print(f"Saved portfolio: {PORTFOLIO_DIR}/portfolio_{current_date.strftime('%Y-%m-%d')}.csv")
    
    # Get top 5 tickers
    top5_tickers = ", ".join(longs["ticker"].head(5).tolist())
    
    # Append to performance log
    perf_row = {
        "week_start": prev_monday.strftime("%Y-%m-%d"),
        "week_end": current_date.strftime("%Y-%m-%d"),
        "regime": regime,
        "n_positions": len(longs),
        "portfolio_return": portfolio_return,
        "nifty_return": nifty_return,
        "alpha": alpha,
        "cumulative_alpha": alpha,  # Will be updated with running total
        "top5_tickers": top5_tickers,
    }
    
    # Calculate cumulative alpha
    if PERFORMANCE_LOG.exists():
        try:
            log = pd.read_csv(PERFORMANCE_LOG)
            if "cumulative_alpha" in log.columns and not log.empty:
                perf_row["cumulative_alpha"] = log["cumulative_alpha"].iloc[-1] + alpha
        except Exception:
            pass
    
    _append_performance_log(perf_row)
    print(f"Updated performance log: {PERFORMANCE_LOG}")
    
    print("")
    print("=" * 60)
    print("=== This Week's Top 20 Positions ===")
    print("Rank  Ticker         Score   Weight")
    for i, (_, r) in enumerate(longs.iterrows(), start=1):
        print(f"{i:<5} {str(r['ticker']):<13} {float(r['final_score']):>6.2f}   {float(r['suggested_weight']):>6.1%}")
    
    print("")
    print(f"Top 5: {top5_tickers}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
