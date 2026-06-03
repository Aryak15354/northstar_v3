#!/usr/bin/env python3
"""
🔄 UPDATE REAL DATA PIPELINES
Update your RBI macro data and market data for the real data cockpit

This script runs:
1. RBI Daily Updater (downloads fresh RBI XLSX files, processes to CSV)
2. Integrated Data Pipeline (combines RBI + YFinance data)
3. Market State Spine integration (unified market state)
"""

import os
import sys
import subprocess
from datetime import datetime

def update_rbi_data():
    """Update RBI macro data"""
    
    print("🏛️ UPDATING RBI MACRO DATA")
    print("-" * 40)
    
    try:
        result = subprocess.run([
            sys.executable, "src/ingestion/rbi_daily_updater.py", "--force"
        ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            print("✅ RBI data updated successfully")
            return True
        else:
            print(f"⚠️ RBI update had issues: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ RBI update timed out (>30 minutes)")
        return False
    except Exception as e:
        print(f"❌ RBI update error: {e}")
        return False

def update_market_data():
    """Update market data via integrated pipeline"""
    
    print("\n📈 UPDATING MARKET DATA")
    print("-" * 40)
    
    try:
        result = subprocess.run([
            sys.executable, "src/ingestion/integrated_data_pipeline.py", "--market-only"
        ], capture_output=True, text=True, timeout=900)  # 15 min timeout
        
        if result.returncode == 0:
            print("✅ Market data updated successfully")
            return True
        else:
            print(f"⚠️ Market data update had issues: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Market data update timed out (>15 minutes)")
        return False
    except Exception as e:
        print(f"❌ Market data update error: {e}")
        return False

def update_full_pipeline():
    """Update complete integrated pipeline"""
    
    print("\n🔄 UPDATING FULL INTEGRATED PIPELINE")
    print("-" * 40)
    
    try:
        result = subprocess.run([
            sys.executable, "src/ingestion/integrated_data_pipeline.py"
        ], capture_output=True, text=True, timeout=2400)  # 40 min timeout
        
        if result.returncode == 0:
            print("✅ Full pipeline updated successfully")
            return True
        else:
            print(f"⚠️ Full pipeline update had issues: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Full pipeline update timed out (>40 minutes)")
        return False
    except Exception as e:
        print(f"❌ Full pipeline update error: {e}")
        return False

def check_data_status():
    """Check status of data files"""
    
    print("\n📊 DATA STATUS CHECK")
    print("-" * 40)
    
    # Check RBI data
    rbi_dir = "data/macro/raw"
    if os.path.exists(rbi_dir):
        csv_files = [f for f in os.listdir(rbi_dir) if f.endswith('.csv')]
        print(f"📁 RBI CSV files: {len(csv_files)}")
        
        if csv_files:
            latest_file = max([os.path.join(rbi_dir, f) for f in csv_files], key=os.path.getmtime)
            age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_file))).total_seconds() / 3600
            print(f"   Latest: {os.path.basename(latest_file)} ({age_hours:.1f}h ago)")
    else:
        print("📁 RBI data directory not found")
    
    # Check market data
    market_file = "data/options/live/market_data_latest.json"
    if os.path.exists(market_file):
        age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(market_file))).total_seconds() / 3600
        print(f"📈 Market data: Updated {age_hours:.1f}h ago")
    else:
        print("📈 Market data file not found")
    
    # Check Market State Spine
    spine_file = "data/processed/market_state.parquet"
    if os.path.exists(spine_file):
        age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(spine_file))).total_seconds() / 3600
        print(f"🧠 Market State Spine: Updated {age_hours:.1f}h ago")
    else:
        print("🧠 Market State Spine not found")
    
    # Check portfolio data
    portfolio_file = "data/processed/portfolio_weights.parquet"
    if os.path.exists(portfolio_file):
        age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(portfolio_file))).total_seconds() / 3600
        print(f"💼 Portfolio data: Updated {age_hours:.1f}h ago")
    else:
        print("💼 Portfolio data not found")

def main():
    """Main function"""
    
    print("🔄 REAL DATA PIPELINE UPDATER")
    print("=" * 50)
    print(f"Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    import argparse
    parser = argparse.ArgumentParser(description="Update Real Data Pipelines")
    parser.add_argument("--rbi-only", action="store_true", help="Update only RBI data")
    parser.add_argument("--market-only", action="store_true", help="Update only market data")
    parser.add_argument("--status-only", action="store_true", help="Check data status only")
    
    args = parser.parse_args()
    
    # Check status first
    check_data_status()
    
    if args.status_only:
        print("\n✅ Status check complete")
        return
    
    success_count = 0
    total_count = 0
    
    if args.rbi_only:
        print("\n🔄 RBI-only mode")
        total_count = 1
        if update_rbi_data():
            success_count += 1
    elif args.market_only:
        print("\n🔄 Market-only mode")
        total_count = 1
        if update_market_data():
            success_count += 1
    else:
        print("\n🔄 Full pipeline mode")
        total_count = 1
        if update_full_pipeline():
            success_count += 1
    
    # Final status check
    check_data_status()
    
    # Summary
    print(f"\n{'='*50}")
    print("UPDATE SUMMARY")
    print(f"{'='*50}")
    
    if success_count == total_count:
        print("✅ ALL UPDATES SUCCESSFUL")
        print("   Your real data cockpit is ready!")
        print("   Run: python scripts/launch_ultimate_real_data_cockpit.py --skip-update")
    else:
        print(f"⚠️ PARTIAL SUCCESS: {success_count}/{total_count}")
        print("   Some updates failed - check logs above")
        print("   Dashboard may still work with existing data")

if __name__ == "__main__":
    main()