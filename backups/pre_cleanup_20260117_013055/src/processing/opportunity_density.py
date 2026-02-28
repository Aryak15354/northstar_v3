import pandas as pd
import numpy as np

IN = "data/processed/opportunity_surface.parquet"
OUT = "data/processed/opportunity_density.parquet"

print("🎯 Building Opportunity Density...")

df = pd.read_parquet(IN)

# Normalize date column name
if "date" not in df.columns and "Date" in df.columns:
    df = df.rename(columns={"Date": "date"})

# Harmonize opportunity_type labels to canonical names used by dashboard
if "opportunity_type" in df.columns:
    map_types = {
        "Momentum": "Momentum Breakouts",
        "Overheated": "Deteriorations",
        "Value Trap": "Value Traps",
    }
    df["opportunity_type"] = df["opportunity_type"].replace(map_types)

if "date" not in df.columns:
    # No temporal dimension; build a daily snapshot for today
    today = pd.Timestamp.today().normalize()
    counts = df["opportunity_type"].value_counts()
    row = {
        "date": today,
        "Alpha Core": int(counts.get("Alpha Core", 0)),
        "Momentum Breakouts": int(counts.get("Momentum Breakouts", 0)),
        "Deteriorations": int(counts.get("Deteriorations", 0)),
    }
    # Load existing if present and append
    try:
        exist = pd.read_parquet(OUT)
        out = pd.concat([exist, pd.DataFrame([row])], ignore_index=True)
    except Exception:
        out = pd.DataFrame([row])
    # Compute derived fields
    out = out.sort_values("date")
    # Ensure series with proper index for derived columns
    if "Alpha Core" in out.columns:
        out["alpha_density"] = out["Alpha Core"].fillna(0)
    else:
        out["alpha_density"] = 0
    if "Value Traps" in out.columns:
        out["risk_density"] = out["Value Traps"].fillna(0)
    else:
        out["risk_density"] = 0
    out["alpha_30d_change"] = out["alpha_density"].diff(30)
    out["opportunity_state"] = out["alpha_30d_change"].apply(lambda x: "Expanding" if pd.notna(x) and x > 0 else "Shrinking")
    out.to_parquet(OUT, index=False)
    print("✅ Opportunity density snapshot appended")
else:
    # Ensure types
    df["date"] = pd.to_datetime(df["date"]) 
    # Daily counts per type
    daily = (
        df.groupby("date")["opportunity_type"].value_counts().unstack().fillna(0)
    )
    # Key densities
    alpha_core_col = "Alpha Core"
    value_trap_col = "Value Traps" if "Value Traps" in daily.columns else ("Value Trap" if "Value Trap" in daily.columns else None)

    daily["alpha_density"] = daily.get(alpha_core_col, 0)
    daily["risk_density"] = daily.get(value_trap_col, 0) if value_trap_col else 0

    # 30-day change in alpha density
    daily["alpha_30d_change"] = daily["alpha_density"].diff(30)
    daily["opportunity_state"] = daily["alpha_30d_change"].apply(lambda x: "Expanding" if pd.notna(x) and x > 0 else "Shrinking")

    out = daily.reset_index()
    out.to_parquet(OUT, index=False)
    print("✅ Opportunity density saved")
