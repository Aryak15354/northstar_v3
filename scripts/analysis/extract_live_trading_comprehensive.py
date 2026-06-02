#!/usr/bin/env python3
"""
Extract Comprehensive Live Trading Data from All Available Sources
Combines shadow trading, execution logs, and portfolio state data
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = Path("data/results/analysis/live_trading")

def extract_comprehensive_live_data():
    """Extract comprehensive live trading data from all sources"""
    
    print("🚀 Extracting Comprehensive Live Trading Data...")
    print("=" * 60)
    
    all_live_data = []
    data_sources = []
    
    # 1. Shadow Trading Execution Data
    print("\n📊 1. Shadow Trading Execution Data")
    shadow_files = [
        ('data/execution/shadow_fund_report.json', 'shadow_fund_report'),
        ('data/shadow_reality/shadow_execution_log.parquet', 'shadow_execution_log'),
        ('data/shadow_reality/shadow_portfolio_state.parquet', 'shadow_portfolio_state'),
        ('data/shadow_reality/shadow_metadata.json', 'shadow_metadata')
    ]
    
    for file_path, data_type in shadow_files:
        if os.path.exists(file_path):
            print(f"   📄 Loading {data_type}...")
            try:
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    
                    # Convert to DataFrame if possible
                    if isinstance(data, dict):
                        if 'performance' in data or 'trades' in data or 'positions' in data:
                            df = pd.json_normalize(data)
                            df['data_source'] = data_type
                            df['timestamp'] = datetime.now()
                            all_live_data.append(df)
                            data_sources.append(data_type)
                            print(f"      ✅ Loaded JSON data: {len(df)} records")
                        
                elif file_path.endswith('.parquet'):
                    df = pd.read_parquet(file_path)
                    df['data_source'] = data_type
                    
                    # Filter to last 6 months if date column exists
                    date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
                    if date_cols:
                        df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                        end_date = df[date_cols[0]].max()
                        start_date = end_date - timedelta(days=6*30)
                        df_6m = df[df[date_cols[0]] >= start_date].copy()
                        
                        if len(df_6m) > 0:
                            all_live_data.append(df_6m)
                            data_sources.append(data_type)
                            print(f"      ✅ Loaded {len(df_6m)} records (6-month filtered)")
                        else:
                            all_live_data.append(df)
                            data_sources.append(data_type)
                            print(f"      ✅ Loaded {len(df)} records (all data)")
                    else:
                        all_live_data.append(df)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df)} records")
                        
            except Exception as e:
                print(f"      ❌ Error loading {data_type}: {e}")
    
    # 2. Portfolio State and Performance Data
    print("\n📊 2. Portfolio State and Performance Data")
    portfolio_files = [
        ('data/portfolio/pnl_on_paper.parquet', 'portfolio_pnl'),
        ('data/portfolio/final_weights.parquet', 'portfolio_weights'),
        ('data/dashboard/performance_tracking.parquet', 'performance_tracking'),
        ('data/processed/performance_summary.parquet', 'performance_summary')
    ]
    
    for file_path, data_type in portfolio_files:
        if os.path.exists(file_path):
            print(f"   📄 Loading {data_type}...")
            try:
                df = pd.read_parquet(file_path)
                df['data_source'] = data_type
                
                # Filter to last 6 months if date column exists
                date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_cols:
                    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                    end_date = df[date_cols[0]].max()
                    start_date = end_date - timedelta(days=6*30)
                    df_6m = df[df[date_cols[0]] >= start_date].copy()
                    
                    if len(df_6m) > 0:
                        all_live_data.append(df_6m)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df_6m)} records (6-month filtered)")
                    else:
                        all_live_data.append(df)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df)} records (all data)")
                else:
                    all_live_data.append(df)
                    data_sources.append(data_type)
                    print(f"      ✅ Loaded {len(df)} records")
                    
            except Exception as e:
                print(f"      ❌ Error loading {data_type}: {e}")
    
    # 3. Live System State Data
    print("\n📊 3. Live System State Data")
    state_files = [
        ('data/state/unified_state.parquet', 'unified_state'),
        ('data/state/unified_state_history.parquet', 'state_history'),
        ('data/live/previous_weights.parquet', 'previous_weights'),
        ('data/intelligence/allocation_history.parquet', 'allocation_history')
    ]
    
    for file_path, data_type in state_files:
        if os.path.exists(file_path):
            print(f"   📄 Loading {data_type}...")
            try:
                df = pd.read_parquet(file_path)
                df['data_source'] = data_type
                
                # Filter to last 6 months if date column exists
                date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_cols:
                    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                    end_date = df[date_cols[0]].max()
                    start_date = end_date - timedelta(days=6*30)
                    df_6m = df[df[date_cols[0]] >= start_date].copy()
                    
                    if len(df_6m) > 0:
                        all_live_data.append(df_6m)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df_6m)} records (6-month filtered)")
                    else:
                        all_live_data.append(df)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df)} records (all data)")
                else:
                    all_live_data.append(df)
                    data_sources.append(data_type)
                    print(f"      ✅ Loaded {len(df)} records")
                    
            except Exception as e:
                print(f"      ❌ Error loading {data_type}: {e}")
    
    # 4. Market Data and Intelligence
    print("\n📊 4. Market Data and Intelligence")
    market_files = [
        ('data/processed/unified_daily.parquet', 'daily_market_data'),
        ('data/processed/market_state.parquet', 'market_state'),
        ('data/intelligence/engine_decisions.parquet', 'engine_decisions'),
        ('data/processed/regime_transitions.parquet', 'regime_transitions')
    ]
    
    for file_path, data_type in market_files:
        if os.path.exists(file_path):
            print(f"   📄 Loading {data_type}...")
            try:
                df = pd.read_parquet(file_path)
                df['data_source'] = data_type
                
                # Filter to last 6 months if date column exists
                date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_cols:
                    df[date_cols[0]] = pd.to_datetime(df[date_cols[0]])
                    end_date = df[date_cols[0]].max()
                    start_date = end_date - timedelta(days=6*30)
                    df_6m = df[df[date_cols[0]] >= start_date].copy()
                    
                    if len(df_6m) > 0:
                        all_live_data.append(df_6m)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df_6m)} records (6-month filtered)")
                    else:
                        all_live_data.append(df)
                        data_sources.append(data_type)
                        print(f"      ✅ Loaded {len(df)} records (all data)")
                else:
                    all_live_data.append(df)
                    data_sources.append(data_type)
                    print(f"      ✅ Loaded {len(df)} records")
                    
            except Exception as e:
                print(f"      ❌ Error loading {data_type}: {e}")
    
    # Combine and save results
    if all_live_data:
        print(f"\n✅ Successfully loaded data from {len(data_sources)} sources:")
        for source in data_sources:
            print(f"   - {source}")
        
        # Save each data source separately for clarity
        print(f"\n💾 Saving individual data sources...")
        
        for i, (df, source) in enumerate(zip(all_live_data, data_sources)):
            filename = OUTPUT_DIR / f"live_data_{source}.csv"
            df.to_csv(filename, index=False)
            print(f"   📄 {filename}: {len(df)} records")
        
        # Create a comprehensive summary
        summary_data = []
        total_records = 0
        
        for df, source in zip(all_live_data, data_sources):
            # Find date columns
            date_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
            
            summary = {
                'data_source': source,
                'total_records': len(df),
                'columns': len(df.columns),
                'date_range_start': df[date_cols[0]].min() if date_cols else 'N/A',
                'date_range_end': df[date_cols[0]].max() if date_cols else 'N/A',
                'key_columns': ', '.join(df.columns[:10].tolist())  # First 10 columns
            }
            summary_data.append(summary)
            total_records += len(df)
        
        # Save summary
        summary_df = pd.DataFrame(summary_data)
        summary_path = OUTPUT_DIR / 'live_trading_data_summary.csv'
        summary_df.to_csv(summary_path, index=False)
        
        print(f"\n🎯 Live Trading Data Extraction Complete!")
        print(f"   📊 Total Records: {total_records:,}")
        print(f"   📁 Data Sources: {len(data_sources)}")
        print(f"   📄 Summary File: {summary_path}")
        
        return all_live_data, data_sources
    else:
        print("\n❌ No live trading data could be loaded")
        return None, None

def create_unified_live_trading_report():
    """Create a unified live trading performance report"""
    
    print("\n📊 Creating Unified Live Trading Report...")
    
    # Look for key performance files
    key_files = [
        'data/execution/shadow_fund_report.json',
        'data/portfolio/pnl_on_paper.parquet',
        'data/dashboard/performance_tracking.parquet'
    ]
    
    report_data = {}
    
    for file_path in key_files:
        if os.path.exists(file_path):
            try:
                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    report_data[os.path.basename(file_path)] = data
                elif file_path.endswith('.parquet'):
                    df = pd.read_parquet(file_path)
                    # Convert to summary statistics
                    summary = {
                        'total_records': len(df),
                        'columns': df.columns.tolist(),
                        'date_range': f"{df.index.min()} to {df.index.max()}" if hasattr(df.index, 'min') else 'N/A'
                    }
                    
                    # Add numeric column summaries
                    numeric_cols = df.select_dtypes(include=[np.number]).columns
                    for col in numeric_cols[:5]:  # First 5 numeric columns
                        summary[f'{col}_mean'] = df[col].mean()
                        summary[f'{col}_std'] = df[col].std()
                    
                    report_data[os.path.basename(file_path)] = summary
                    
            except Exception as e:
                print(f"   ⚠️ Could not process {file_path}: {e}")
    
    # Save unified report
    if report_data:
        import json
        with open('unified_live_trading_report.json', 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"   ✅ Unified report saved: unified_live_trading_report.json")
        print(f"   📊 Report includes data from {len(report_data)} sources")
    
    return report_data

if __name__ == "__main__":
    # Extract comprehensive live data
    live_data, sources = extract_comprehensive_live_data()
    
    # Create unified report
    report = create_unified_live_trading_report()
    
    print("\n" + "=" * 60)
    print("🎯 COMPREHENSIVE LIVE DATA EXTRACTION COMPLETE!")
    
    if live_data:
        print(f"✅ Successfully extracted data from {len(sources)} sources")
        print("📁 Individual CSV files created for each data source")
        print("📊 Summary file: live_trading_data_summary.csv")
        print("📋 Unified report: unified_live_trading_report.json")
    else:
        print("❌ No live trading data available")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
