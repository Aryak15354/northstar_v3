import os
import pandas as pd
import numpy as np

PRICES = "data/processed/prices.parquet"
SCORES = "data/processed/scores.parquet"
UNIVERSE = "universe/nifty500.csv"
OUT = "data/processed/sector_rotation.parquet"

# Keep a meaningful rolling history for dashboard trend charts.
HISTORY_TRADING_DAYS = 252
WARMUP_TRADING_DAYS = 340
MIN_TICKERS_PER_INDUSTRY = 5

print("🔄 Building Sector Rotation Engine...")

prices = pd.read_parquet(PRICES)
scores = pd.read_parquet(SCORES) if os.path.exists(SCORES) else pd.DataFrame()
universe = pd.read_csv(UNIVERSE)
universe["ticker"] = universe["Symbol"] + ".NS"

if "Date" not in prices.columns or "Close" not in prices.columns or "Volume" not in prices.columns:
    raise ValueError("prices.parquet must contain Date, Close, Volume")

# Attach Industry mapping from universe.
prices = prices.merge(universe[["ticker", "Industry"]], on="ticker", how="left")
prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
prices = prices.dropna(subset=["Date", "ticker", "Industry"]).sort_values(["ticker", "Date"])

# Trim to manageable history window with warmup for rolling signals.
all_dates = np.array(sorted(prices["Date"].dropna().unique()))
if len(all_dates) > WARMUP_TRADING_DAYS:
    cutoff = all_dates[-WARMUP_TRADING_DAYS]
    prices = prices[prices["Date"] >= cutoff].copy()

g = prices.groupby("ticker", sort=False)
prices["relative_return"] = g["Close"].pct_change()
prices["volume_growth"] = g["Volume"].pct_change()
prices["ma50"] = g["Close"].transform(lambda s: s.rolling(50, min_periods=10).mean())
prices["trend_flag"] = (prices["Close"] > prices["ma50"]).astype(float)

# Clean obvious outliers that distort downstream flow charts.
prices["relative_return"] = (
    pd.to_numeric(prices["relative_return"], errors="coerce")
    .replace([np.inf, -np.inf], np.nan)
    .clip(lower=-0.20, upper=0.20)
)
prices["volume_growth"] = (
    pd.to_numeric(prices["volume_growth"], errors="coerce")
    .replace([np.inf, -np.inf], np.nan)
    .clip(lower=-5.0, upper=5.0)
)

daily_sector = (
    prices.groupby(["Date", "Industry"], as_index=False)
    .agg(
        relative_performance=("relative_return", "mean"),
        volume_growth=("volume_growth", "mean"),
        trend_strength=("trend_flag", "mean"),
        volatility=("relative_return", "std"),
        n_tickers=("ticker", "nunique"),
    )
)

daily_sector = daily_sector[daily_sector["n_tickers"] >= MIN_TICKERS_PER_INDUSTRY].copy()
daily_sector["capital_flow"] = (
    pd.to_numeric(daily_sector["relative_performance"], errors="coerce").fillna(0.0)
    * pd.to_numeric(daily_sector["volume_growth"], errors="coerce").fillna(0.0)
    * pd.to_numeric(daily_sector["trend_strength"], errors="coerce").fillna(0.0)
)

# Attach industry-level score context.
daily_sector["northstar_score"] = np.nan
if not scores.empty:
    score_col = None
    for cand in ["northstar_score", "score", "final_score"]:
        if cand in scores.columns:
            score_col = cand
            break

    if score_col:
        scores = scores.copy()
        if "Industry" not in scores.columns:
            scores = scores.merge(universe[["ticker", "Industry"]], on="ticker", how="left")
        score_by_industry = (
            scores.dropna(subset=[score_col, "Industry"])
            .groupby("Industry")[score_col]
            .mean()
        )
        daily_sector["northstar_score"] = daily_sector["Industry"].map(score_by_industry)

# Rank industries daily (best score = rank 1).
daily_sector["northstar_rank"] = daily_sector.groupby("Date")["northstar_score"].rank(
    ascending=False, method="min"
)

# Keep only recent trading-day history for this run.
sector_dates = np.array(sorted(daily_sector["Date"].dropna().unique()))
if len(sector_dates) > HISTORY_TRADING_DAYS:
    hist_cutoff = sector_dates[-HISTORY_TRADING_DAYS]
    snapshot_history = daily_sector[daily_sector["Date"] >= hist_cutoff].copy()
else:
    snapshot_history = daily_sector.copy()

snapshot_history = snapshot_history.sort_values(["Date", "Industry"])

# Merge with existing file to preserve continuity across runs.
if os.path.exists(OUT):
    try:
        existing = pd.read_parquet(OUT)
    except Exception:
        existing = pd.DataFrame()
else:
    existing = pd.DataFrame()

if not existing.empty:
    combined = pd.concat([existing, snapshot_history], ignore_index=True)
else:
    combined = snapshot_history.copy()

if "Date" in combined.columns:
    combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce")
    combined = combined.dropna(subset=["Date", "Industry"])
    combined = combined.sort_values(["Date", "Industry"])
    combined = combined.drop_duplicates(subset=["Date", "Industry"], keep="last")

    max_date = combined["Date"].max()
    if pd.notna(max_date):
        combined = combined[combined["Date"] >= (max_date - pd.Timedelta(days=730))]

combined.to_parquet(OUT, index=False)

latest_date = combined["Date"].max() if not combined.empty else None
latest_snapshot = combined[combined["Date"] == latest_date] if latest_date is not None else pd.DataFrame()
latest_snapshot = latest_snapshot.sort_values("capital_flow", ascending=False)

print(f"✅ Sector Rotation built: {len(latest_snapshot)} sectors (latest snapshot)")
print(f"📚 Sector Rotation history rows: {len(combined)}")
print("📁 Saved to data/processed/sector_rotation.parquet")
