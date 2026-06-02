#!/usr/bin/env python3
"""
Regenerate processed bulk deals from raw monthly files.

This script:
1. Loads all raw monthly bulk deals CSVs
2. Applies ticker mapping using all available sources
3. Marks unmapped stocks as BSE-only (.BO suffix)
4. Saves consolidated processed file with all historical data
"""

import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Data sources
SCREENER_META_PATHS = [
    PROJECT_ROOT / "data" / "processed" / "screener_metadata.csv",
    PROJECT_ROOT / "data" / "processed" / "screener_delisted" / "screener_metadata.csv",
]

UNIVERSE_PATHS = [
    PROJECT_ROOT / "universe" / "nifty500.csv",
    PROJECT_ROOT / "data" / "reference" / "et500_name_to_ticker.csv",
]


def _normalize_ticker(value):
    """Normalize ticker."""
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS") or s.endswith(".BO"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return s


def _normalize_name(name):
    """Normalize company name for matching."""
    s = str(name or "").upper()
    s = re.sub(r"[^A-Z0-9 ]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Remove common suffixes
    for suffix in [" LTD", " LIMITED", " PVT", " PRIVATE", " CORP", " CORPORATION", " CO", " AND ", " THE "]:
        s = s.replace(suffix, "")
    return s


def _load_all_mappings():
    """Load all available ticker mappings."""
    print("Loading ticker mappings from all sources...")
    
    code_map = {}  # BSE code -> NSE ticker
    name_map = {}  # Normalized name -> ticker
    
    # Source 1: Screener metadata (has BSE codes)
    for path in SCREENER_META_PATHS:
        if path.exists():
            try:
                df = pd.read_csv(path)
                for _, row in df.iterrows():
                    bse_code = str(row.get("bse_code", "")).strip()
                    ticker = _normalize_ticker(row.get("ticker", ""))
                    name = _normalize_name(row.get("company_name", ""))
                    
                    if bse_code and bse_code.lower() not in ["nan", "none", ""]:
                        code_map[bse_code] = ticker
                    if name and ticker:
                        name_map[name] = ticker
                        
                print(f"  Loaded from {path.name}: {len(code_map)} BSE codes, {len(name_map)} names")
            except Exception as e:
                print(f"  Error loading {path}: {e}")
    
    # Source 2: Universe files
    for path in UNIVERSE_PATHS:
        if path.exists():
            try:
                df = pd.read_csv(path)
                name_col = None
                ticker_col = None
                
                for c in ["Company Name", "company_name", "Security Name"]:
                    if c in df.columns:
                        name_col = c
                        break
                for c in ["Symbol", "nse_ticker", "NSE Ticker", "ticker"]:
                    if c in df.columns:
                        ticker_col = c
                        break
                
                if name_col and ticker_col:
                    for _, row in df.iterrows():
                        name = _normalize_name(row.get(name_col, ""))
                        ticker = _normalize_ticker(row.get(ticker_col, ""))
                        if name and ticker:
                            name_map[name] = ticker
                            
                print(f"  Loaded from {path.name}: {len(name_map)} names")
            except Exception as e:
                print(f"  Error loading {path}: {e}")
    
    print(f"\nFinal mappings: {len(code_map)} BSE codes, {len(name_map)} company names")
    return code_map, name_map


def _map_ticker(row, code_map, name_map):
    """Map a row to ticker using multiple strategies."""
    scrip_code = str(row.get("scrip_code", "")).strip()
    scrip_name = str(row.get("scrip_name", "")).strip()
    
    # Strategy 1: BSE code match -> NSE ticker
    if scrip_code in code_map:
        return code_map[scrip_code]
    
    # Strategy 2: Normalized name match
    norm_name = _normalize_name(scrip_name)
    if norm_name in name_map:
        return name_map[norm_name]
    
    # Strategy 3: Partial name match (try without common words)
    for suffix in [" LTD", " LIMITED", " PVT", " PRIVATE", " CORP", " CORPORATION", " CO"]:
        short_name = norm_name.replace(suffix, "")
        if short_name in name_map:
            return name_map[short_name]
    
    # Strategy 4: If already has ticker format, use it
    if ".NS" in scrip_name.upper() or ".BO" in scrip_name.upper():
        match = re.search(r"([A-Z]{2,6}\.(NS|BO))", scrip_name.upper())
        if match:
            return match.group(1)
    
    # No match found - return empty (will be marked as BSE-only)
    return ""


def _process_bulk_deals():
    """Process all raw bulk deals files."""
    print("=" * 80)
    print("BULK DEALS REGENERATION")
    print("=" * 80)
    
    # Load mappings
    code_map, name_map = _load_all_mappings()
    
    # Directories
    raw_dir = PROJECT_ROOT / "data" / "raw" / "exchanges" / "bse" / "alternative" / "bulk_deals"
    output_dir = PROJECT_ROOT / "data" / "processed" / "alternative"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_frames = []
    total_rows = 0
    nse_mapped = 0
    bse_only = 0
    
    raw_files = sorted(raw_dir.glob("bulk_deals_*.csv"))
    print(f"\nProcessing {len(raw_files)} raw monthly files...")
    
    for i, file_path in enumerate(raw_files):
        try:
            df = pd.read_csv(file_path)
            
            # Map tickers
            df["nse_ticker"] = df.apply(
                lambda row: _map_ticker(row, code_map, name_map),
                axis=1
            )
            
            # For unmapped stocks, create BSE ticker from scrip code
            unmapped = df["nse_ticker"] == ""
            if unmapped.any():
                # Use BSE code as ticker symbol for BSE-only stocks
                df.loc[unmapped, "nse_ticker"] = "BSE" + df.loc[unmapped, "scrip_code"].astype(str) + ".BO"
                bse_only += unmapped.sum()
            
            nse_mapped += (~unmapped).sum()
            total_rows += len(df)
            
            all_frames.append(df)
            
            if (i + 1) % 50 == 0:
                print(f"  Processed {i + 1}/{len(raw_files)} files...")
                
        except Exception as e:
            print(f"  Error processing {file_path}: {e}")
    
    if not all_frames:
        print("No data loaded!")
        return
    
    # Combine
    combined = pd.concat(all_frames, ignore_index=True)
    print(f"\nCombined: {len(combined)} rows")
    
    # Convert types
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined["quantity"] = pd.to_numeric(combined["quantity"], errors="coerce")
    combined["price"] = pd.to_numeric(combined["price"], errors="coerce")
    
    # Standardize deal_type
    deal_map = {"P": "BUY", "B": "BUY", "S": "SELL", "BUY": "BUY", "SELL": "SELL"}
    combined["deal_type"] = combined["deal_type"].str.upper().map(deal_map).fillna("UNKNOWN")
    
    # Filter valid dates
    combined = combined.dropna(subset=["date"])
    
    # Sort
    combined = combined.sort_values(["date", "scrip_code"])
    
    # Statistics
    nse_mask = combined["nse_ticker"].str.endswith(".NS")
    bse_mask = combined["nse_ticker"].str.endswith(".BO")
    
    print(f"\n{'=' * 60}")
    print("STATISTICS")
    print(f"{'=' * 60}")
    print(f"Total rows: {len(combined):,}")
    print(f"NSE-mapped: {nse_mask.sum():,} ({nse_mask.sum()/len(combined)*100:.1f}%)")
    print(f"BSE-only: {bse_mask.sum():,} ({bse_mask.sum()/len(combined)*100:.1f}%)")
    print(f"Unique tickers: {combined['nse_ticker'].nunique():,}")
    print(f"Date range: {combined['date'].min().date()} to {combined['date'].max().date()}")
    
    # Save CSV
    output_path = output_dir / "bulk_deals_all.csv"
    combined.to_csv(output_path, index=False)
    print(f"\nSaved CSV to {output_path}")
    
    # Save parquet
    parquet_path = output_dir / "bulk_deals_all.parquet"
    combined.to_parquet(parquet_path, index=False)
    print(f"Saved parquet to {parquet_path}")
    
    # Show sample NSE-mapped data
    nse_df = combined[nse_mask]
    if len(nse_df) > 0:
        print(f"\n{'=' * 60}")
        print("SAMPLE NSE-MAPPED DATA")
        print(f"{'=' * 60}")
        print(nse_df[["date", "scrip_name", "nse_ticker", "deal_type", "quantity", "price"]].head(10))
    
    # Show sample BSE-only data
    bse_df = combined[bse_mask]
    if len(bse_df) > 0:
        print(f"\n{'=' * 60}")
        print("SAMPLE BSE-ONLY DATA")
        print(f"{'=' * 60}")
        print(bse_df[["date", "scrip_name", "nse_ticker", "deal_type", "quantity", "price"]].head(10))


if __name__ == "__main__":
    _process_bulk_deals()
