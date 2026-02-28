import pandas as pd

PRICES = "data/processed/prices.parquet"
SCORES = "data/processed/scores.parquet"
UNIVERSE = "universe/nifty500.csv"
OUT = "data/processed/sector_rotation.parquet"

print("🔄 Building Sector Rotation Engine...")

prices = pd.read_parquet(PRICES)
scores = pd.read_parquet(SCORES)
universe = pd.read_csv(UNIVERSE)
universe["ticker"] = universe["Symbol"] + ".NS"

# Merge Industry info into scores and prices
scores = scores.merge(universe[["ticker", "Industry"]], on="ticker", how="left")
prices = prices.merge(universe[["ticker", "Industry"]], on="ticker", how="left")

latest = prices.sort_values("Date").groupby("ticker").tail(60)

sector_data = []

for sector, g in latest.groupby("Industry"):
    if len(g["ticker"].unique()) < 5:
        continue

    g = g.sort_values(["ticker", "Date"]) 
    # Robust returns and simple sector volatility proxy
    rets = g.groupby("ticker")["Close"].pct_change()
    rel_perf = pd.to_numeric(rets, errors="coerce").replace([float('inf'), float('-inf')], pd.NA).mean()
    sec_vol = pd.to_numeric(rets, errors="coerce").std()

    # Volume growth (robust)
    volchg = g.groupby("ticker")["Volume"].pct_change()
    volchg = pd.to_numeric(volchg, errors="coerce").replace([float('inf'), float('-inf')], 0).fillna(0)
    volume = volchg.mean()

    # Trend strength
    trend = (g["Close"] > g["Close"].rolling(50, min_periods=10).mean()).mean()

    # Average score by Industry (scores may have Industry or Industry_y)
    ind_col = "Industry_y" if "Industry_y" in scores.columns else ("Industry" if "Industry" in scores.columns else None)
    if ind_col:
        avg_score = scores[scores[ind_col] == sector]["northstar_score"].mean()
    else:
        avg_score = pd.NA

    # Capital flow proxy
    try:
        capital_flow = float(rel_perf) * float(volume) * float(trend)
    except Exception:
        capital_flow = 0.0

    sector_data.append({
        "Industry": sector,
        "Date": g["Date"].max(),
        "relative_performance": rel_perf,
        "volume_growth": volume,
        "trend_strength": trend,
        "northstar_score": avg_score,
        "capital_flow": capital_flow,
        "volatility": sec_vol,
    })

df = pd.DataFrame(sector_data).sort_values("capital_flow", ascending=False)

df["northstar_rank"] = df["northstar_score"].rank(ascending=False)

df.to_parquet(OUT, index=False)

print(f"✅ Sector Rotation built: {len(df)} sectors")
print("📁 Saved to data/processed/sector_rotation.parquet")
