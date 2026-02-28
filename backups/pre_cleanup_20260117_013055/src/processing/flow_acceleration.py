import pandas as pd
import numpy as np

SECTORS = "data/processed/sector_rotation.parquet"
OUT = "data/processed/sector_flows.parquet"

print("🌊 Building Capital Flow Acceleration...")

df = pd.read_parquet(SECTORS)

# Derive relative_return if missing
if "relative_return" not in df.columns:
    if "relative_performance" in df.columns:
        df["relative_return"] = pd.to_numeric(df["relative_performance"], errors="coerce")
    else:
        df["relative_return"] = np.nan

# Ensure volume_growth exists
if "volume_growth" not in df.columns:
    df["volume_growth"] = np.nan

# Initialize volatility column if absent
if "volatility" not in df.columns:
    df["volatility"] = np.nan

# If Date present, estimate per-sector volatility of relative_return over time
if "Date" in df.columns:
    df = df.sort_values(["Industry", "Date"]) 
    try:
        vol_est = (
            df.groupby("Industry")["relative_return"].transform(lambda s: pd.to_numeric(s, errors="coerce").rolling(20, min_periods=5).std())
        )
        df["volatility"] = df["volatility"].where(df["volatility"].notna(), vol_est)
    except Exception:
        pass

# Fallback volatility to 1.0 where still missing/zero to avoid NaNs
df["volatility"] = pd.to_numeric(df["volatility"], errors="coerce").replace(0, np.nan).fillna(1.0)

# Flow strength = (return * volume) / volatility
rr = pd.to_numeric(df["relative_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
vg = pd.to_numeric(df["volume_growth"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
num = rr * vg
den = df["volatility"].replace([np.inf, -np.inf], np.nan)
df["flow_strength"] = (num / den).replace([np.inf, -np.inf], np.nan).fillna(0.0)

# Acceleration: 10d and 30d diffs within Industry over time (if Date exists)
if "Date" in df.columns:
    df = df.sort_values(["Industry", "Date"]) 
    df["flow_10d"] = df.groupby("Industry")["flow_strength"].diff(10)
    df["flow_30d"] = df.groupby("Industry")["flow_strength"].diff(30)
else:
    df["flow_10d"] = np.nan
    df["flow_30d"] = np.nan

# State label
def _state(row):
    if pd.notna(row.get("flow_10d")):
        return "Accelerating" if row["flow_10d"] > 0 else "Decelerating"
    # fallback when no history
    fs = row.get("flow_strength")
    if pd.isna(fs) or fs == 0:
        return "Stable"
    return "Inflow" if fs > 0 else "Outflow"

df["flow_state"] = df.apply(_state, axis=1)

df.to_parquet(OUT, index=False)
print("✅ Capital flow acceleration saved")
