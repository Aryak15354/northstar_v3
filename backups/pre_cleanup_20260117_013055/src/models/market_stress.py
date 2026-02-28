#!/usr/bin/env python3
"""
Market Stress Engine - Equity-based stress composite
Combines breadth, participation, correlation, volatility and alpha density
into a single MarketStress factor suitable to blend with RBI Stress.

Outputs: data/macro/factors/market_stress.parquet
"""
import os
from datetime import datetime
import pandas as pd
import numpy as np

OUT_FILE = "data/macro/factors/market_stress.parquet"

os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)


def safe_read(path):
    try:
        if os.path.exists(path):
            return pd.read_parquet(path)
    except Exception:
        return None
    return None


def expanding_z(series: pd.Series) -> pd.Series:
    m = series.expanding().mean()
    s = series.expanding().std().replace(0, np.nan)
    return (series - m) / (s + 1e-12)


def resample_weekly(df, date_col=None):
    if df is None or df.empty:
        return df
    if isinstance(df.index, pd.DatetimeIndex):
        return df.resample('W-FRI').last()
    if date_col and date_col in df.columns:
        tmp = df.copy()
        tmp[date_col] = pd.to_datetime(tmp[date_col], errors='coerce')
        tmp = tmp.dropna(subset=[date_col]).set_index(date_col)
        return tmp.resample('W-FRI').last()
    # try first col as date
    c0 = df.columns[0]
    tmp = df.copy()
    tmp[c0] = pd.to_datetime(tmp[c0], errors='coerce')
    tmp = tmp.dropna(subset=[c0]).set_index(c0)
    return tmp.resample('W-FRI').last()


def compute_market_stress():
    market = safe_read("data/processed/market_regime.parquet")
    opp = safe_read("data/processed/opportunity_surface.parquet")

    breadth = participation = corr = vol = None
    alpha_density = None

    if market is not None and not market.empty:
        m = market.copy()
        # Normalize date and weekly resample
        date_col = 'Date' if 'Date' in m.columns else None
        m_w = resample_weekly(m, date_col)
        cols = m_w.columns
        breadth = m_w.get('breadth')
        participation = m_w.get('participation')
        corr = m_w.get('correlation')
        vol = m_w.get('volatility')

    if opp is not None and not opp.empty:
        o = opp.copy()
        # Ensure Date if present
        if 'Date' in o.columns:
            o['Date'] = pd.to_datetime(o['Date'], errors='coerce')
        # Scale if stored 0-1
        if 'mispricing' in o.columns and o['mispricing'].max() <= 1.0:
            o['mispricing'] = o['mispricing'] * 100
        if 'confirmation' in o.columns and o['confirmation'].max() <= 1.0:
            o['confirmation'] = o['confirmation'] * 100
        # Alpha density per date
        if 'Date' in o.columns:
            grp = o.groupby(o['Date'].dt.to_period('W-FRI'))
            total = grp.size().astype(float)
            high_conv = grp.apply(lambda g: ((g.get('mispricing', 0) > 50) & (g.get('confirmation', 0) > 50)).sum()).astype(float)
            ad = (high_conv / total).replace([np.inf, -np.inf], np.nan)
            ad.index = ad.index.to_timestamp()
            alpha_density = ad.resample('W-FRI').last()

    # Build DataFrame of components
    frames = []
    if breadth is not None: frames.append(breadth.rename('breadth'))
    if participation is not None: frames.append(participation.rename('participation'))
    if corr is not None: frames.append(corr.rename('correlation'))
    if vol is not None: frames.append(vol.rename('volatility'))
    if alpha_density is not None: frames.append(alpha_density.rename('alpha_density'))
    if not frames:
        print("❌ No inputs available to compute MarketStress")
        return
    df = pd.concat(frames, axis=1).sort_index()

    # Construct stress components (higher is worse)
    # breadth/participation: lower -> worse, so invert
    if 'breadth' in df: df['z_breadth'] = expanding_z(1 - df['breadth'])
    if 'participation' in df: df['z_participation'] = expanding_z(1 - df['participation'])
    if 'correlation' in df: df['z_corr'] = expanding_z(df['correlation'])
    if 'volatility' in df: df['z_vol'] = expanding_z(df['volatility'])
    if 'alpha_density' in df: df['z_alpha'] = expanding_z(1 - df['alpha_density'])

    # Weighted composite (defaults per RFC)
    w = {
        'z_breadth': 0.25,
        'z_participation': 0.25,
        'z_corr': 0.20,
        'z_vol': 0.20,
        'z_alpha': 0.10,
    }
    ms = 0
    for k, wt in w.items():
        if k in df:
            ms = ms + wt * df[k].fillna(0)
    df['MarketStress'] = ms

    # Save
    out_cols = [c for c in ['MarketStress','z_breadth','z_participation','z_corr','z_vol','z_alpha','breadth','participation','correlation','volatility','alpha_density'] if c in df]
    df[out_cols].to_parquet(OUT_FILE)
    print(f"✅ Saved market stress: {OUT_FILE} ({len(df)} rows)")


if __name__ == "__main__":
    compute_market_stress()
