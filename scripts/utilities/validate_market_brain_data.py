#!/usr/bin/env python3
"""
🔍 MARKET BRAIN DATA VALIDATION - NORTHSTAR V3
Validate available real data for Market Brain components

This script checks what real data is available and provides
recommendations for Market Brain configuration based on
actual data availability.

No synthetic data - only real data validation.
"""

import os
import pandas as pd
import glob
from datetime import datetime, timedelta

def check_rbi_macro_data():
    """Check RBI macro data availability"""
    
    print("🏦 RBI MACRO DATA")
    print("-" * 40)
    
    data_sources = {
        'Processed RBI': 'data/macro/factors/macro_score.parquet',
        'Cleaned RBI': 'data/macro/cleaned/macro_cleaned.parquet',
        'Raw RBI Files': 'data/macro/raw/'
    }
    
    available_data = {}
    
    for source_name, path in data_sources.items():
        if source_name == 'Raw RBI Files':
            # Check directory for CSV files
            if os.path.exists(path):
                csv_files = glob.glob(os.path.join(path, '*.csv'))
                if csv_files:
                    print(f"✅ {source_name}: {len(csv_files)} files")
                    available_data[source_name] = csv_files
                    
                    # Show file details
                    for file_path in csv_files[:3]:  # Show first 3
                        filename = os.path.basename(file_path)
                        try:
                            df = pd.read_csv(file_path)
                            print(f"   📄 {filename}: {len(df)} rows, {len(df.columns)} columns")
                        except:
                            print(f"   📄 {filename}: Could not read")
                else:
                    print(f"❌ {source_name}: No CSV files found")
            else:
                print(f"❌ {source_name}: Directory not found")
        else:
            # Check individual files
            if os.path.exists(path):
                try:
                    if path.endswith('.parquet'):
                        df = pd.read_parquet(path)
                    else:
                        df = pd.read_csv(path)
                    
                    print(f"✅ {source_name}: {len(df)} rows, {len(df.columns)} columns")
                    if not df.empty:
                        print(f"   📅 Date range: {df.index[0] if hasattr(df.index, 'date') else 'N/A'} to {df.index[-1] if hasattr(df.index, 'date') else 'N/A'}")
                    available_data[source_name] = path
                except Exception as e:
                    print(f"⚠️ {source_name}: File exists but could not read - {e}")
            else:
                print(f"❌ {source_name}: File not found")
    
    return available_data

def check_market_data():
    """Check market structure data availability"""
    
    print("\n📊 MARKET STRUCTURE DATA")
    print("-" * 40)
    
    data_sources = {
        'Options Data': 'data/options/live/market_data_latest.json',
        'NIFTY Data': 'data/processed/nifty.parquet',
        'Market Health': 'data/processed/market_health.parquet'
    }
    
    available_data = {}
    
    for source_name, path in data_sources.items():
        if os.path.exists(path):
            try:
                if path.endswith('.json'):
                    import json
                    with open(path, 'r') as f:
                        data = json.load(f)
                    print(f"✅ {source_name}: JSON with {len(data)} keys")
                    if 'market_health' in data:
                        health = data['market_health']
                        print(f"   📊 Market health metrics: {len(health)} indicators")
                elif path.endswith('.parquet'):
                    df = pd.read_parquet(path)
                    print(f"✅ {source_name}: {len(df)} rows, {len(df.columns)} columns")
                    if not df.empty:
                        print(f"   📅 Date range: {df.index[0] if hasattr(df.index, 'date') else 'N/A'} to {df.index[-1] if hasattr(df.index, 'date') else 'N/A'}")
                
                available_data[source_name] = path
            except Exception as e:
                print(f"⚠️ {source_name}: File exists but could not read - {e}")
        else:
            print(f"❌ {source_name}: File not found")
    
    return available_data

def check_flow_data():
    """Check FII/DII flow data availability"""
    
    print("\n💧 FLOW DATA")
    print("-" * 40)
    
    data_sources = {
        'FII/DII Flows': 'data/flows/fii_dii.csv',
        'FX Data': 'data/macro/fx.csv',
        'Liquidity Data': 'data/macro/liquidity.csv'
    }
    
    available_data = {}
    
    for source_name, path in data_sources.items():
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                print(f"✅ {source_name}: {len(df)} rows, {len(df.columns)} columns")
                print(f"   📊 Columns: {list(df.columns)}")
                available_data[source_name] = path
            except Exception as e:
                print(f"⚠️ {source_name}: File exists but could not read - {e}")
        else:
            print(f"❌ {source_name}: File not found")
    
    return available_data

def check_sector_data():
    """Check sector index data availability"""
    
    print("\n🏭 SECTOR DATA")
    print("-" * 40)
    
    sector_dir = 'data/sector_indices/'
    
    if os.path.exists(sector_dir):
        sector_files = glob.glob(os.path.join(sector_dir, '*.csv'))
        
        if sector_files:
            print(f"✅ Sector indices: {len(sector_files)} files")
            
            available_sectors = []
            for file_path in sector_files:
                sector_name = os.path.basename(file_path).replace('.csv', '')
                try:
                    df = pd.read_csv(file_path)
                    print(f"   📊 {sector_name}: {len(df)} rows")
                    available_sectors.append(sector_name)
                except:
                    print(f"   ❌ {sector_name}: Could not read")
            
            return available_sectors
        else:
            print("❌ Sector indices: No CSV files found")
    else:
        print("❌ Sector indices: Directory not found")
    
    return []

def check_stock_data():
    """Check individual stock data availability"""
    
    print("\n🏢 STOCK DATA")
    print("-" * 40)
    
    stock_dir = 'data/raw/prices_daily/'
    
    if os.path.exists(stock_dir):
        stock_files = glob.glob(os.path.join(stock_dir, '*.csv'))
        
        if stock_files:
            print(f"✅ Stock files: {len(stock_files)} files")
            
            # Sample a few files to check quality
            sample_files = stock_files[:5]
            valid_stocks = 0
            
            for file_path in sample_files:
                stock_name = os.path.basename(file_path).replace('.csv', '')
                try:
                    df = pd.read_csv(file_path)
                    if len(df) > 50:  # Minimum data requirement
                        print(f"   ✅ {stock_name}: {len(df)} rows")
                        valid_stocks += 1
                    else:
                        print(f"   ⚠️ {stock_name}: {len(df)} rows (insufficient)")
                except:
                    print(f"   ❌ {stock_name}: Could not read")
            
            # Estimate total valid stocks
            estimated_valid = int((valid_stocks / len(sample_files)) * len(stock_files))
            print(f"   📊 Estimated valid stocks: {estimated_valid}/{len(stock_files)}")
            
            return len(stock_files), estimated_valid
        else:
            print("❌ Stock files: No CSV files found")
    else:
        print("❌ Stock files: Directory not found")
    
    return 0, 0

def check_yield_data():
    """Check yield curve data availability"""
    
    print("\n📈 YIELD CURVE DATA")
    print("-" * 40)
    
    yield_sources = {
        'Yield Curve': 'data/macro/yields.csv',
        'Bond Data': 'data/macro/bonds.csv',
        'Credit Spreads': 'data/macro/credit_spreads.csv'
    }
    
    available_data = {}
    
    for source_name, path in yield_sources.items():
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                print(f"✅ {source_name}: {len(df)} rows, {len(df.columns)} columns")
                print(f"   📊 Columns: {list(df.columns)}")
                available_data[source_name] = path
            except Exception as e:
                print(f"⚠️ {source_name}: File exists but could not read - {e}")
        else:
            print(f"❌ {source_name}: File not found")
    
    return available_data

def generate_recommendations(validation_results):
    """Generate Market Brain configuration recommendations"""
    
    print("\n🎯 MARKET BRAIN RECOMMENDATIONS")
    print("=" * 60)
    
    # Count available data sources
    rbi_available = len(validation_results['rbi']) > 0
    market_available = len(validation_results['market']) > 0
    flows_available = len(validation_results['flows']) > 0
    sectors_available = len(validation_results['sectors']) > 0
    stocks_available = validation_results['stocks'][1] > 10  # At least 10 valid stocks
    yields_available = len(validation_results['yields']) > 0
    
    total_available = sum([rbi_available, market_available, flows_available, 
                          sectors_available, stocks_available, yields_available])
    
    print(f"Data Availability Score: {total_available}/6")
    
    if total_available >= 4:
        print("✅ RECOMMENDATION: Market Brain can be deployed")
        print("   You have sufficient real data for meaningful analysis")
        
        # Specific recommendations
        if rbi_available:
            print("   🏦 Monetary forces: ENABLED (RBI data available)")
        else:
            print("   ⚠️ Monetary forces: DISABLED (no RBI data)")
        
        if yields_available:
            print("   📈 Credit forces: ENABLED (yield data available)")
        else:
            print("   ⚠️ Credit forces: DISABLED (no yield data)")
        
        if flows_available:
            print("   💧 Flow forces: ENABLED (FII/DII data available)")
        else:
            print("   ⚠️ Flow forces: DISABLED (no flow data)")
        
        if market_available:
            print("   📊 Market structure: ENABLED (market health data available)")
        else:
            print("   ⚠️ Market structure: DISABLED (no market health data)")
        
        if sectors_available:
            print(f"   🏭 Sector forces: ENABLED ({len(validation_results['sectors'])} sectors)")
        else:
            print("   ⚠️ Sector forces: DISABLED (no sector data)")
        
        if stocks_available:
            print(f"   🏢 Corporate forces: ENABLED ({validation_results['stocks'][1]} valid stocks)")
        else:
            print("   ⚠️ Corporate forces: DISABLED (insufficient stock data)")
        
    elif total_available >= 2:
        print("⚠️ RECOMMENDATION: Limited Market Brain deployment")
        print("   You have some real data but missing key components")
        print("   Consider focusing on available data sources only")
        
    else:
        print("❌ RECOMMENDATION: Market Brain not ready")
        print("   Insufficient real data for meaningful analysis")
        print("   Focus on data collection first")
    
    # Configuration suggestions
    print(f"\n📋 SUGGESTED CONFIGURATION:")
    print("   Enable only components with real data:")
    
    config_suggestions = []
    if rbi_available:
        config_suggestions.append("- Monetary forces (RBI data)")
    if yields_available:
        config_suggestions.append("- Credit forces (yield data)")
    if flows_available:
        config_suggestions.append("- Flow forces (FII/DII data)")
    if market_available:
        config_suggestions.append("- Market structure (health data)")
    if sectors_available:
        config_suggestions.append(f"- Sector forces ({len(validation_results['sectors'])} sectors)")
    if stocks_available:
        config_suggestions.append(f"- Corporate forces ({validation_results['stocks'][1]} stocks)")
    
    if config_suggestions:
        for suggestion in config_suggestions:
            print(f"   ✅ {suggestion}")
    else:
        print("   ❌ No components can be enabled with current data")

def main():
    """Run complete data validation"""
    
    print("🔍 NORTHSTAR MARKET BRAIN - DATA VALIDATION")
    print("=" * 70)
    print(f"Validation started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Checking availability of REAL DATA ONLY (no synthetic data)")
    print()
    
    # Run all validation checks
    validation_results = {
        'rbi': check_rbi_macro_data(),
        'market': check_market_data(),
        'flows': check_flow_data(),
        'sectors': check_sector_data(),
        'stocks': check_stock_data(),
        'yields': check_yield_data()
    }
    
    # Generate recommendations
    generate_recommendations(validation_results)
    
    print(f"\n🎯 VALIDATION COMPLETE")
    print("=" * 70)
    print("Use these recommendations to configure Market Brain")
    print("with only real data sources that you actually have.")

if __name__ == "__main__":
    main()