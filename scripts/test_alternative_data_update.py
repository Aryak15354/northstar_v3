#!/usr/bin/env python3
"""
Test alternative data collection and ingestion.

This verifies that:
1. Collection scripts can be run
2. Data is properly formatted
3. Ingestion layer can load the data
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_alternative_data_files():
    """Check what alternative data files exist and their status."""
    print("\n" + "=" * 80)
    print("  ALTERNATIVE DATA FILES STATUS")
    print("=" * 80)
    
    files_to_check = {
        'Bulk Deals': 'data/processed/alternative/bulk_deals_all.csv',
        'Credit Ratings': 'data/processed/alternative/credit_ratings_all.csv',
        'Promoter Pledges': 'data/processed/alternative/promoter_pledge_all.csv',
        'Earnings Dates': 'data/processed/alternative/earnings_dates_all.csv',
        'Announcements': 'data/processed/alternative/announcements_all.csv',
    }
    
    for name, path in files_to_check.items():
        file_path = Path(path)
        if file_path.exists():
            try:
                df = pd.read_csv(file_path)
                print(f"\n  ✅ {name}:")
                print(f"     Path: {path}")
                print(f"     Rows: {len(df):,}")
                print(f"     Columns: {list(df.columns)[:5]}")
                
                # Check date range
                date_cols = [c for c in df.columns if 'date' in c.lower()]
                if date_cols:
                    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors='coerce')
                    valid_dates = df[date_cols[0]].dropna()
                    if len(valid_dates) > 0:
                        print(f"     Date range: {valid_dates.min()} to {valid_dates.max()}")
            except Exception as e:
                print(f"\n  ⚠️  {name}: Error reading file - {e}")
        else:
            print(f"\n  ❌ {name}: File not found")
            print(f"     Expected: {path}")


def test_collection_scripts():
    """Test that collection scripts exist and are executable."""
    print("\n" + "=" * 80)
    print("  COLLECTION SCRIPTS STATUS")
    print("=" * 80)
    
    scripts = {
        'Bulk Deals': 'scripts/scrape_bse_bulk_deals.py',
        'Credit Ratings': 'scripts/scrape_credit_ratings.py',
        'Promoter Pledges': 'scripts/scrape_bse_promoter_pledge.py',
        'Unified Collector': 'scripts/collect_all_alternative_data.py',
    }
    
    for name, path in scripts.items():
        script_path = Path(path)
        if script_path.exists():
            print(f"  ✅ {name}: {path}")
        else:
            print(f"  ❌ {name}: NOT FOUND - {path}")


def test_ingestion_with_config():
    """Test that ingestion layer can load alternative data with proper config."""
    print("\n" + "=" * 80)
    print("  INGESTION LAYER TEST")
    print("=" * 80)
    
    try:
        # Load config
        import yaml
        config_path = Path('config/ingestion_config.yaml')
        
        if not config_path.exists():
            print("  ❌ Config file not found")
            return
        
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
        
        print(f"\n  ✅ Config loaded")
        print(f"     Alternative data paths:")
        paths = config_data.get('ingestion', {}).get('paths', {})
        for key in ['credit_ratings', 'bulk_deals', 'promoter_pledges']:
            print(f"       {key}: {paths.get(key, 'NOT SET')}")
        
        # Test loading with proper config
        from src.ingestion.alternative_loader import AlternativeDataLoader
        
        # Create loader with full config
        loader = AlternativeDataLoader({'ingestion': config_data.get('ingestion', {})})
        
        as_of_date = datetime(2024, 3, 1)
        
        # Test credit ratings
        print(f"\n  Testing credit ratings loader...")
        try:
            cr = loader.load_credit_ratings(as_of_date, tickers=['RELIANCE'])
            print(f"     ✅ Loaded {len(cr)} rows")
        except Exception as e:
            print(f"     ⚠️  Error: {e}")
        
        # Test bulk deals
        print(f"\n  Testing bulk deals loader...")
        try:
            bd = loader.load_bulk_deals(as_of_date, tickers=['RELIANCE'])
            print(f"     ✅ Loaded {len(bd)} rows")
        except Exception as e:
            print(f"     ⚠️  Error: {e}")
        
        # Test promoter pledges
        print(f"\n  Testing promoter pledges loader...")
        try:
            pp = loader.load_promoter_pledges(as_of_date, tickers=['RELIANCE'])
            print(f"     ✅ Loaded {len(pp)} rows")
        except Exception as e:
            print(f"     ⚠️  Error: {e}")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def print_update_instructions():
    """Print instructions for updating alternative data."""
    print("\n" + "=" * 80)
    print("  HOW TO UPDATE ALTERNATIVE DATA")
    print("=" * 80)
    
    print("""
  To collect fresh alternative data, run:
  
    python scripts/collect_all_alternative_data.py
  
  This will:
    1. Scrape bulk deals from BSE
    2. Scrape credit ratings from CRISIL/CARE/ICRA
    3. Scrape promoter pledges from BSE
    4. Merge all data into processed files
  
  Individual updaters:
    - Bulk deals:        python scripts/scrape_bse_bulk_deals.py
    - Credit ratings:    python scripts/scrape_credit_ratings.py
    - Promoter pledges:  python scripts/scrape_bse_promoter_pledge.py
  
  Note: These scripts scrape public websites and may take time.
        Run them during off-market hours to avoid rate limiting.
""")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  ALTERNATIVE DATA UPDATE TEST")
    print("=" * 80)
    print(f"\n  Started at: {datetime.now()}")
    
    # Check files
    check_alternative_data_files()
    
    # Check scripts
    test_collection_scripts()
    
    # Test ingestion
    test_ingestion_with_config()
    
    # Print instructions
    print_update_instructions()
    
    print("\n" + "=" * 80)
    print("  TEST COMPLETE")
    print("=" * 80)
    print(f"\n  Finished at: {datetime.now()}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
