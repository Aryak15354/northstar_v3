#!/usr/bin/env python3
"""
Filter bulk deals to Nifty 500 stocks only.

This creates a clean dataset of bulk deals for large-cap NSE stocks
that are actually used in the trading system.
"""

import pandas as pd
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


def _normalize_ticker(symbol):
    """Normalize to NSE ticker format."""
    s = str(symbol or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def filter_to_nifty_500():
    """Filter bulk deals to Nifty 500 stocks only."""
    print("=" * 80)
    print("FILTERING BULK DEALS TO NIFTY 500")
    print("=" * 80)
    
    # Load Nifty 500 to BSE mapping (comprehensive)
    mapping_path = PROJECT_ROOT / "data" / "raw" / "nifty500_bse_mapping.csv"
    if mapping_path.exists():
        mapping_df = pd.read_csv(mapping_path)
        # Create BSE code to NSE ticker map
        bse_to_nse = dict(zip(
            mapping_df['bse_code'].astype(str).str.strip(),
            mapping_df['ticker'].astype(str).str.strip()
        ))
        # Create NSE symbol set
        nifty_symbols = set(mapping_df['Symbol'].astype(str).str.strip().str.upper())
        print(f"Loaded {len(bse_to_nse)} Nifty 500 BSE-NSE mappings")
    else:
        # Fallback to universe file
        nifty_path = PROJECT_ROOT / "universe" / "nifty500.csv"
        if not nifty_path.exists():
            print(f"ERROR: {nifty_path} not found")
            return
        
        nifty_df = pd.read_csv(nifty_path)
        nifty_symbols = set(nifty_df["Symbol"].dropna().astype(str).str.strip().str.upper())
        bse_to_nse = {}
        print(f"Loaded {len(nifty_symbols)} Nifty 500 symbols (no BSE mapping)")
    
    # Load full bulk deals
    bulk_path = PROJECT_ROOT / "data" / "processed" / "alternative" / "bulk_deals_all.csv"
    if not bulk_path.exists():
        print(f"ERROR: {bulk_path} not found")
        return
    
    print(f"\nLoading {bulk_path}...")
    bulk_df = pd.read_csv(bulk_path, parse_dates=["date"], low_memory=False)
    print(f"Loaded {len(bulk_df):,} total bulk deals")
    
    # Map BSE codes to NSE tickers using Nifty 500 mapping
    bulk_df["mapped_nse_ticker"] = bulk_df["scrip_code"].astype(str).str.strip().map(bse_to_nse)
    
    # Filter: Either already has NSE ticker ending in .NS, or mapped from BSE code
    nse_mask = bulk_df["nse_ticker"].str.endswith(".NS", na=False)
    mapped_mask = bulk_df["mapped_nse_ticker"].notna() & (bulk_df["mapped_nse_ticker"] != "")
    
    # Use mapped ticker where available
    bulk_df.loc[mapped_mask, "nse_ticker"] = bulk_df.loc[mapped_mask, "mapped_nse_ticker"]
    
    # Combined mask
    valid_mask = nse_mask | mapped_mask
    print(f"\nNSE-mapped (direct + BSE): {valid_mask.sum():,} ({valid_mask.sum()/len(bulk_df)*100:.1f}%)")
    
    valid_df = bulk_df[valid_mask].copy()
    
    # Extract symbol from ticker
    valid_df["symbol"] = valid_df["nse_ticker"].str.replace(".NS", "", regex=False)
    
    # Filter to Nifty 500 symbols
    nifty_mask = valid_df["symbol"].isin(nifty_symbols)
    print(f"Nifty 500 deals: {nifty_mask.sum():,} ({nifty_mask.sum()/len(valid_df)*100:.1f}%)")
    
    # Create filtered dataset
    nifty_deals = valid_df[nifty_mask].copy()
    
    # Sort
    nifty_deals = nifty_deals.sort_values(["date", "symbol"])
    
    # Statistics
    print("\n" + "=" * 60)
    print("STATISTICS")
    print("=" * 60)
    print(f"Total bulk deals: {len(bulk_df):,}")
    print(f"NSE-mapped: {len(valid_df):,}")
    print(f"Nifty 500: {len(nifty_deals):,}")
    print(f"Date range: {nifty_deals['date'].min().date()} to {nifty_deals['date'].max().date()}")
    print(f"Unique stocks: {nifty_deals['symbol'].nunique()}")
    print(f"Unique clients: {nifty_deals['client_name'].nunique()}")
    
    # Deal type distribution
    print("\nDeal type distribution:")
    print(nifty_deals["deal_type"].value_counts())
    
    # Top stocks by deal volume
    print("\nTop 20 stocks by deal count:")
    top_stocks = nifty_deals.groupby("symbol").size().sort_values(ascending=False).head(20)
    for symbol, count in top_stocks.items():
        print(f"  {symbol}: {count:,} deals")
    
    # Save
    output_dir = PROJECT_ROOT / "data" / "processed" / "alternative"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save full Nifty 500 dataset
    output_path = output_dir / "bulk_deals_nifty500.csv"
    nifty_deals.to_csv(output_path, index=False)
    print(f"\nSaved to {output_path}")
    
    # Save parquet for faster loading
    parquet_path = output_dir / "bulk_deals_nifty500.parquet"
    nifty_deals.to_parquet(parquet_path, index=False)
    print(f"Saved parquet to {parquet_path}")
    
    # Save recent (last 90 days) for quick loading
    recent_date = nifty_deals["date"].max() - pd.Timedelta(days=90)
    recent = nifty_deals[nifty_deals["date"] >= recent_date]
    recent_path = output_dir / "bulk_deals_nifty500_recent.csv"
    recent.to_csv(recent_path, index=False)
    print(f"Saved recent (90 days) to {recent_path} ({len(recent)} rows)")
    
    # Show sample
    print("\n" + "=" * 60)
    print("SAMPLE RECENT DEALS")
    print("=" * 60)
    print(recent[["date", "symbol", "scrip_name", "client_name", "deal_type", "quantity", "price"]].head(15))


if __name__ == "__main__":
    filter_to_nifty_500()
