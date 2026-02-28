#!/usr/bin/env python3
"""
Builds market internals parquet for gating macro regimes.
Outputs: data/macro/factors/market_stress.parquet with columns:
- MarketStress (z-ish proxy from sector dispersion and index move)
- breadth (0-1 fraction of sectors positive)
- participation (0-1 scaled average absolute sector move)
"""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np

OUT_FILE = "data/macro/factors/market_stress.parquet"
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)


def safe_load_json(path):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def compute_from_live_json(live):
    if not live or 'indices' not in live:
        return None
    indices = live['indices']
    sector_changes = []
    for name, d in indices.items():
        if name == 'NIFTY':
            continue
        if 'pct_change' in d:
            change = d['pct_change']
        elif 'net_change' in d and 'close' in d:
            prev_close = d['close'] - d['net_change']
            change = (d['net_change'] / prev_close * 100) if prev_close else 0
        else:
            change = 0
        sector_changes.append(change)
    if not sector_changes:
        return None
    pos = sum(1 for x in sector_changes if x > 0)
    total = len(sector_changes)
    breadth = pos / total
    participation = min(1.0, np.mean([abs(x) for x in sector_changes]) / 2.0)  # 2% avg = 1.0 cap
    # Stress proxy: high negative mean and/or high dispersion => stress up
    mean_move = np.mean(sector_changes)
    dispersion = np.std(sector_changes)
    market_stress = max(0.0, (-mean_move/2.0) + (dispersion/2.0))  # rough scale
    now = pd.Timestamp(datetime.now().date())
    return pd.DataFrame({
        'MarketStress': [market_stress],
        'breadth': [breadth],
        'participation': [participation]
    }, index=[now])


def main():
    live = safe_load_json('data/options/live/market_data_latest.json')
    df_live = compute_from_live_json(live)

    if df_live is None:
        print("⚠️ No market indices found in live JSON; writing empty frame if not present")
        if not os.path.exists(OUT_FILE):
            pd.DataFrame(columns=['MarketStress','breadth','participation']).to_parquet(OUT_FILE)
        return

    # Append to existing if available
    if os.path.exists(OUT_FILE):
        try:
            prev = pd.read_parquet(OUT_FILE)
            combined = pd.concat([prev, df_live], axis=0)
            combined = combined[~combined.index.duplicated(keep='last')]
            combined = combined.sort_index()
            combined.to_parquet(OUT_FILE)
        except Exception:
            df_live.to_parquet(OUT_FILE)
    else:
        df_live.to_parquet(OUT_FILE)

    print(f"✅ Market internals updated: {OUT_FILE}")


if __name__ == "__main__":
    main()
