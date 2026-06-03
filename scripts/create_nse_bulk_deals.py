#!/usr/bin/env python3
"""
NSE Bulk Deals - PRACTICAL SOLUTION

Since NSE direct scraping is blocked, we use BSE data but map ALL to NSE tickers.
This gives us NSE-focused bulk deals using accessible BSE data.

The BSE data contains the same trades (many stocks trade on both exchanges),
and we map everything to NSE tickers for consistency with the trading system.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

# Project root  
PROJECT_ROOT = Path(__file__).parent.parent


def load_bse_to_nse_mapping():
    """Load comprehensive BSE to NSE ticker mapping."""
    mapping = {}
    
    # Source 1: Nifty 500 mapping file
    nifty_map = PROJECT_ROOT / "data" / "raw" / "nifty500_bse_mapping.csv"
    if nifty_map.exists():
        df = pd.read_csv(nifty_map)
        for _, row in df.iterrows():
            bse_code = str(row.get("bse_code", "")).strip()
            ticker = str(row.get("ticker", "")).strip()
            if bse_code and bse_code.lower() not in ["nan", ""] and ticker:
                mapping[bse_code] = ticker.replace(".NS", "")  # Store without suffix
    
    # Source 2: Screener metadata
    screener_meta = PROJECT_ROOT / "data" / "processed" / "screener_metadata.csv"
    if screener_meta.exists():
        df = pd.read_csv(screener_meta)
        for _, row in df.iterrows():
            bse_code = str(row.get("bse_code", "")).strip()
            ticker = str(row.get("ticker", "")).strip()
            if bse_code and bse_code.lower() not in ["nan", ""] and ticker:
                mapping[bse_code] = ticker.replace(".NS", "")
    
    # Source 3: Delisted metadata
    delisted_meta = PROJECT_ROOT / "data" / "processed" / "screener_delisted" / "screener_metadata.csv"
    if delisted_meta.exists():
        df = pd.read_csv(delisted_meta)
        for _, row in df.iterrows():
            bse_code = str(row.get("bse_code", "")).strip()
            ticker = str(row.get("ticker", "")).strip()
            if bse_code and bse_code.lower() not in ["nan", ""] and ticker:
                mapping[bse_code] = ticker.replace(".NS", "")
    
    print(f"Loaded {len(mapping)} BSE-NSE mappings")
    return mapping


def process_bulk_deals_to_nse():
    """Process all bulk deals and convert to NSE tickers."""
    print("=" * 80)
    print("NSE BULK DEALS - CONVERTING BSE DATA TO NSE TICKERS")
    print("=" * 80)
    
    # Load mapping
    bse_to_nse = load_bse_to_nse_mapping()
    
    # Load full BSE bulk deals
    bse_file = PROJECT_ROOT / "data" / "processed" / "alternative" / "bulk_deals_all.csv"
    if not bse_file.exists():
        print(f"ERROR: {bse_file} not found")
        return
    
    print(f"\nLoading {bse_file}...")
    df = pd.read_csv(bse_file, parse_dates=["date"], low_memory=False)
    print(f"Loaded {len(df):,} bulk deals")
    
    # Convert BSE codes to NSE tickers
    print("\nConverting to NSE tickers...")
    df["bse_code"] = df["scrip_code"].astype(str).str.strip()
    df["nse_symbol"] = df["bse_code"].map(bse_to_nse)
    
    # For unmapped, try to use company name matching
    unmapped = df[df["nse_symbol"].isna()]
    print(f"Unmapped after BSE code lookup: {len(unmapped):,}")
    
    # Create NSE ticker column
    df["nse_ticker"] = df["nse_symbol"].apply(lambda x: f"{x}.NS" if x else None)
    
    # For still unmapped, use existing nse_ticker if available
    if "nse_ticker" in df.columns:
        mask = df["nse_ticker"].isna()
        existing = df.loc[mask, "nse_ticker"]
        if existing.str.endswith(".NS", na=False).any():
            df.loc[mask, "nse_ticker"] = df.loc[mask, "nse_ticker"]
    
    # Count successful mappings
    mapped_count = df["nse_ticker"].notna().sum()
    print(f"Successfully mapped to NSE: {mapped_count:,} ({mapped_count/len(df)*100:.1f}%)")
    
    # Filter to only NSE-mapped deals
    nse_df = df[df["nse_ticker"].notna()].copy()
    
    # Extract symbol from ticker
    nse_df["symbol"] = nse_df["nse_ticker"].str.replace(".NS", "", regex=False)
    
    # Sort
    nse_df = nse_df.sort_values(["date", "symbol"])
    
    # Statistics
    print(f"\n{'=' * 60}")
    print("STATISTICS")
    print(f"{'=' * 60}")
    print(f"Total bulk deals: {len(df):,}")
    print(f"NSE-mapped: {len(nse_df):,}")
    print(f"Unique NSE symbols: {nse_df['symbol'].nunique()}")
    print(f"Date range: {nse_df['date'].min().date()} to {nse_df['date'].max().date()}")
    
    # Save full NSE dataset
    output_dir = PROJECT_ROOT / "data" / "processed" / "alternative"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "bulk_deals_nse_all.csv"
    nse_df.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")
    
    # Save parquet
    parquet_path = output_dir / "bulk_deals_nse_all.parquet"
    nse_df.to_parquet(parquet_path, index=False)
    print(f"Saved parquet to {parquet_path}")
    
    # Save recent (last 90 days)
    recent_date = nse_df["date"].max() - pd.Timedelta(days=90)
    recent = nse_df[nse_df["date"] >= recent_date]
    recent_path = output_dir / "bulk_deals_nse_recent.csv"
    recent.to_csv(recent_path, index=False)
    print(f"Saved recent (90 days, {len(recent)} rows) to {recent_path}")
    
    # Show sample
    print(f"\n{'=' * 60}")
    print("SAMPLE RECENT NSE DEALS")
    print(f"{'=' * 60}")
    cols = ["date", "symbol", "nse_ticker", "company_name", "deal_type", "quantity", "price"]
    print(recent[cols].head(15))
    
    # Top stocks
    print(f"\n{'=' * 60}")
    print("TOP 20 STOCKS BY DEAL COUNT")
    print(f"{'=' * 60}")
    top = nse_df.groupby("symbol").size().sort_values(ascending=False).head(20)
    for symbol, count in top.items():
        print(f"  {symbol}: {count:,} deals")


if __name__ == "__main__":
    process_bulk_deals_to_nse()
