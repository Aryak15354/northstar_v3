#!/usr/bin/env python3
"""
Fix credit ratings data by improving ticker matching.

This script:
1. Loads all existing credit ratings CSVs
2. Uses improved ticker matching with multiple strategies
3. Saves enhanced data with better ticker coverage
"""

import re
from pathlib import Path
from datetime import date

import pandas as pd
import difflib

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Stopwords for company name normalization
STOPWORDS = {
    "LTD", "LIMITED", "CO", "COMPANY", "CORP", "CORPORATION", 
    "INC", "PVT", "PRIVATE", "PUBLIC", "PLC", "LLP", "THE", "OF", "AND"
}


def _normalize_ticker(value):
    """Normalize ticker to standard format."""
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _norm_company(value):
    """Normalize company name for matching."""
    s = str(value or "").upper().replace("&", " AND ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t and t not in STOPWORDS]
    return " ".join(toks)


def _similarity(a, b):
    """Compute similarity between two strings."""
    if not a or not b:
        return 0.0
    ta = set(a.split())
    tb = set(b.split())
    inter = len(ta & tb)
    token = (2.0 * inter / (len(ta) + len(tb))) if ta and tb else 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    return max(token, seq)


def _load_universe():
    """Load universe of companies with tickers."""
    rows = []
    universe_paths = [
        PROJECT_ROOT / "universe" / "nifty500.csv",
        PROJECT_ROOT / "universe" / "nifty_500.csv",
        PROJECT_ROOT / "data" / "universe" / "nifty500.csv",
    ]
    
    for p in universe_paths:
        if p.exists():
            try:
                df = pd.read_csv(p)
                for _, r in df.iterrows():
                    name = str(r.get("Company Name") or "").strip()
                    tk = _normalize_ticker(r.get("Symbol"))
                    if name and tk:
                        rows.append((name, tk))
                if rows:
                    print(f"Loaded {len(rows)} companies from {p}")
                    break
            except Exception as e:
                print(f"Error loading {p}: {e}")
    
    return rows


def _match_ticker(name, universe):
    """
    Match company name to ticker using multiple strategies.
    """
    n = _norm_company(name)
    
    if not universe or not n:
        return ""
    
    # Strategy 1: Exact match on normalized name
    for cname, tk in universe:
        if _norm_company(cname) == n:
            return tk
    
    # Strategy 2: Fuzzy match (threshold 0.70)
    best = (0.0, "")
    for cname, tk in universe:
        s = _similarity(n, _norm_company(cname))
        if s > best[0]:
            best = (s, tk)
    
    if best[0] >= 0.70:
        return best[1]
    
    # Strategy 3: Token overlap (2+ tokens match)
    name_tokens = set(n.split())
    for cname, tk in universe:
        cname_tokens = set(_norm_company(cname).split())
        if len(name_tokens & cname_tokens) >= 2:
            return tk
    
    # Strategy 4: Partial match - check if company name contains ticker-like pattern
    ticker_pattern = r'\b([A-Z]{2,6})\b'
    matches = re.findall(ticker_pattern, name.upper())
    for match in matches:
        for cname, tk in universe:
            if tk.startswith(match + ".") or tk.startswith(match + "N"):
                return tk
    
    return ""


def _extract_ratings_from_text(text):
    """Extract ratings from text using regex."""
    if pd.isna(text) or not text:
        return None, None
    
    rating_pattern = r'\b(?:AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B|C|D)\b'
    matches = re.findall(rating_pattern, str(text).upper())
    
    if len(matches) >= 2:
        return matches[0], matches[1]
    elif len(matches) == 1:
        return matches[0], matches[0]
    return None, None


def _infer_instrument_type(text):
    """Infer instrument type from text."""
    u = str(text or "").upper()
    if "NCD" in u:
        return "NCD"
    if "COMMERCIAL PAPER" in u or "CP" in u:
        return "Commercial Paper"
    if "LONG" in u and "TERM" in u:
        return "Long Term"
    if "SHORT" in u and "TERM" in u:
        return "Short Term"
    if "BANK" in u and "FACIL" in u:
        return "Bank Facilities"
    return ""


def main():
    print("=" * 80)
    print("CREDIT RATINGS TICKER FIX")
    print("=" * 80)
    
    # Load universe
    universe = _load_universe()
    print(f"Universe size: {len(universe)} companies")
    
    # Load all existing ratings
    ratings_dir = PROJECT_ROOT / "data" / "raw" / "shared" / "alternative" / "credit_ratings"
    all_frames = []
    
    print(f"\nLoading existing ratings from {ratings_dir}...")
    for csv_file in sorted(ratings_dir.glob("*.csv")):
        try:
            df = pd.read_csv(csv_file)
            print(f"  {csv_file.name}: {len(df)} rows")
            all_frames.append(df)
        except Exception as e:
            print(f"  Error reading {csv_file}: {e}")
    
    if not all_frames:
        print("No ratings data found!")
        return
    
    # Combine all data
    combined = pd.concat(all_frames, ignore_index=True)
    print(f"\nCombined: {len(combined)} rows")
    
    # Current ticker match rate
    current_valid = combined['nse_ticker'].notna() & (combined['nse_ticker'].astype(str).str.strip() != '')
    print(f"Current valid tickers: {current_valid.sum()} / {len(combined)} ({current_valid.sum()/len(combined)*100:.1f}%)")
    
    # Apply improved ticker matching to rows without ticker
    print("\nApplying improved ticker matching...")
    
    def match_row(row):
        if pd.notna(row.get('nse_ticker')) and str(row.get('nse_ticker', '')).strip():
            return row['nse_ticker']
        return _match_ticker(row.get('company_name', ''), universe)
    
    combined['nse_ticker_improved'] = combined.apply(match_row, axis=1)
    
    # Also try to extract ratings from other columns
    print("Extracting ratings from available text...")
    
    def extract_row_ratings(row):
        old, new = row.get('old_rating'), row.get('new_rating')
        
        # If both are present, return as-is
        if pd.notna(old) and pd.notna(new) and str(old).strip() and str(new).strip():
            return pd.Series([old, new])
        
        # Try to extract from outlook or other text columns
        for col in ['outlook', 'instrument_type', 'agency']:
            if col in row and pd.notna(row[col]):
                extracted_old, extracted_new = _extract_ratings_from_text(row[col])
                if extracted_old:
                    old = old if pd.notna(old) else extracted_old
                if extracted_new:
                    new = new if pd.notna(new) else extracted_new
        
        return pd.Series([old, new])
    
    extracted = combined.apply(extract_row_ratings, axis=1)
    combined['old_rating_improved'] = extracted[0]
    combined['new_rating_improved'] = extracted[1]
    
    # New ticker match rate
    new_valid = combined['nse_ticker_improved'].notna() & (combined['nse_ticker_improved'].astype(str).str.strip() != '')
    print(f"\nNew valid tickers: {new_valid.sum()} / {len(combined)} ({new_valid.sum()/len(combined)*100:.1f}%)")
    print(f"Improvement: +{new_valid.sum() - current_valid.sum()} tickers matched")
    
    # New rating match rate
    current_has_rating = combined['old_rating'].notna() | combined['new_rating'].notna()
    new_has_rating = combined['old_rating_improved'].notna() | combined['new_rating_improved'].notna()
    print(f"\nCurrent rows with ratings: {current_has_rating.sum()} / {len(combined)} ({current_has_rating.sum()/len(combined)*100:.1f}%)")
    print(f"New rows with ratings: {new_has_rating.sum()} / {len(combined)} ({new_has_rating.sum()/len(combined)*100:.1f}%)")
    print(f"Improvement: +{new_has_rating.sum() - current_has_rating.sum()} rows with ratings")
    
    # Save enhanced data
    output_dir = PROJECT_ROOT / "data" / "raw" / "shared" / "alternative" / "credit_ratings"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save combined enhanced file
    output_file = output_dir / "credit_ratings_enhanced.csv"
    
    # Create output dataframe with improved columns
    output_df = combined.copy()
    output_df['nse_ticker'] = output_df['nse_ticker_improved'].fillna(output_df['nse_ticker'])
    output_df['old_rating'] = output_df['old_rating_improved'].fillna(output_df['old_rating'])
    output_df['new_rating'] = output_df['new_rating_improved'].fillna(output_df['new_rating'])
    
    # Select final columns
    final_cols = ['date', 'company_name', 'nse_ticker', 'agency', 'instrument_type', 
                  'old_rating', 'new_rating', 'action_type', 'outlook']
    output_df = output_df[final_cols]
    output_df = output_df.drop_duplicates(subset=['date', 'company_name', 'agency'])
    
    output_df.to_csv(output_file, index=False)
    print(f"\nSaved enhanced data to {output_file}")
    print(f"Final rows: {len(output_df)}")
    
    # Final stats
    final_valid = output_df['nse_ticker'].notna() & (output_df['nse_ticker'].astype(str).str.strip() != '')
    final_has_rating = output_df['old_rating'].notna() | output_df['new_rating'].notna()
    print(f"\n=== FINAL STATS ===")
    print(f"Total rows: {len(output_df)}")
    print(f"Valid tickers: {final_valid.sum()} ({final_valid.sum()/len(output_df)*100:.1f}%)")
    print(f"Rows with ratings: {final_has_rating.sum()} ({final_has_rating.sum()/len(output_df)*100:.1f}%)")
    
    # Show sample with valid ticker and ratings
    print(f"\n=== SAMPLE ENHANCED DATA ===")
    valid_with_rating = output_df[final_valid & final_has_rating]
    if len(valid_with_rating) > 0:
        print(valid_with_rating[['date', 'company_name', 'nse_ticker', 'agency', 'old_rating', 'new_rating', 'action_type']].head(15))
    else:
        print("No rows with both valid ticker and ratings found")


if __name__ == "__main__":
    main()
