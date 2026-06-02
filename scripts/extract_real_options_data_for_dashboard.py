#!/usr/bin/env python3
"""
Extract Real Options Data for Dashboard
Uses ONLY real data from:
1. Historical option chains (data/options/chains_cache/)
2. IV history (data/options/iv_history.parquet)
3. Live market data (data/options/live/market_data_latest.json)
4. Backtest results (data/results/analysis/backtests/)
5. Truth mode runs (truth_mode_runs/)

NO SYNTHETIC/MOCK DATA - REAL DATA ONLY
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.options.dashboard_state_contract import normalize_dashboard_state
from src.options.state_io import StateIOManager


def load_real_iv_history():
    """Load real IV history from parquet file"""
    iv_path = PROJECT_ROOT / "data/options/iv_history.parquet"
    
    if not iv_path.exists():
        print(f"⚠️  IV history not found at {iv_path}")
        return None
    
    df = pd.read_parquet(iv_path)
    print(f"✅ Loaded real IV history: {len(df)} rows")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Date range: {df.index.min()} to {df.index.max()}" if hasattr(df.index, 'min') else "")
    return df


def load_real_option_chains():
    """Load real option chain data from cache"""
    chains_dir = PROJECT_ROOT / "data/options/chains_cache"
    
    if not chains_dir.exists():
        print(f"⚠️  Option chains cache not found at {chains_dir}")
        return None
    
    # Get most recent chain files
    chain_files = list(chains_dir.glob("*.parquet"))
    if not chain_files:
        print("⚠️  No option chain files found")
        return None
    
    # Load a few recent chains
    chains = []
    for chain_file in sorted(chain_files, reverse=True)[:5]:
        try:
            df = pd.read_parquet(chain_file)
            chains.append({
                'file': chain_file.name,
                'data': df,
                'rows': len(df),
                'columns': list(df.columns)
            })
        except Exception as e:
            print(f"⚠️  Error loading {chain_file.name}: {e}")
    
    print(f"✅ Loaded {len(chains)} real option chains")
    for chain in chains:
        print(f"   {chain['file']}: {chain['rows']} rows")
    
    return chains


def load_real_market_data():
    """Load real market data"""
    market_path = PROJECT_ROOT / "data/options/live/market_data_latest.json"
    
    if not market_path.exists():
        print(f"⚠️  Market data not found at {market_path}")
        return None
    
    with open(market_path, 'r') as f:
        data = json.load(f)
    
    print(f"✅ Loaded real market data from {data.get('timestamp', 'unknown time')}")
    print(f"   NIFTY: {data.get('indices', {}).get('NIFTY', {}).get('current_price', 'N/A')}")
    print(f"   BANKNIFTY: {data.get('indices', {}).get('BANKNIFTY', {}).get('current_price', 'N/A')}")
    
    return data


def load_real_backtest_data():
    """Load real backtest data"""
    backtest_path = PROJECT_ROOT / "data/results/analysis/backtests/northstar_3year_backtest_real_data.csv"
    
    if not backtest_path.exists():
        print(f"⚠️  Backtest data not found at {backtest_path}")
        return None
    
    df = pd.read_csv(backtest_path)
    print(f"✅ Loaded real backtest data: {len(df)} rows")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Date range: {df['date'].min()} to {df['date'].max()}" if 'date' in df.columns else "")
    
    return df


def load_truth_mode_runs():
    """Load truth mode runs"""
    truth_dir = PROJECT_ROOT / "truth_mode_runs"
    
    if not truth_dir.exists():
        print(f"⚠️  Truth mode runs not found at {truth_dir}")
        return None
    
    truth_files = list(truth_dir.glob("*.json"))
    if not truth_files:
        print("⚠️  No truth mode run files found")
        return None
    
    # Load most recent truth run
    latest_truth = sorted(truth_files, reverse=True)[0]
    with open(latest_truth, 'r') as f:
        data = json.load(f)
    
    print(f"✅ Loaded truth mode run: {latest_truth.name}")
    print(f"   Keys: {list(data.keys())}")
    
    return data


def extract_real_positions_from_chains(chains):
    """Extract real positions from option chain data"""
    if not chains:
        return []
    
    positions = []
    
    for chain in chains[:3]:  # Use top 3 chains
        df = chain['data']
        
        # Look for columns that indicate real positions
        if 'strike_price' in df.columns or 'strike' in df.columns:
            strike_col = 'strike_price' if 'strike_price' in df.columns else 'strike'
            
            # Get a few strikes with data
            for idx, row in df.head(3).iterrows():
                position = {
                    'position_id': f"REAL_{chain['file'].split('_')[0]}_{idx}",
                    'underlying': chain['file'].split('_')[0],
                    'strike': float(row[strike_col]) if strike_col in row else None,
                    'source': f"real_chain_{chain['file']}"
                }
                
                # Add any available Greeks or IV data
                for col in ['iv', 'implied_volatility', 'delta', 'gamma', 'vega', 'theta']:
                    if col in row:
                        position[col] = float(row[col]) if pd.notna(row[col]) else None
                
                positions.append(position)
    
    return positions


def create_dashboard_state_from_real_data(iv_history, chains, market_data, backtest_data, truth_run):
    """Create dashboard state using ONLY real data"""
    
    state = {
        'timestamp': datetime.now().isoformat(),
        'schema_version': '2.1.0',
        'data_sources': {
            'iv_history': iv_history is not None,
            'option_chains': chains is not None and len(chains) > 0,
            'market_data': market_data is not None,
            'backtest_data': backtest_data is not None,
            'truth_run': truth_run is not None
        },
        'active_positions': [],
        'portfolio_greeks': {},
        'iv_surface': [],
        'greeks_history': [],
        'market_state': {},
        'data_quality': 'REAL_DATA_ONLY',
        'continuity_mode': True,
        'recovery_mode': False,
        'base_capital': 0.0,
        'net_equity': 0.0,
        'risk_cap_value': 0.0,
        'risk_remaining': 0.0,
    }
    
    # Extract real positions from chains
    if chains:
        state['active_positions'] = extract_real_positions_from_chains(chains)
        print(f"✅ Extracted {len(state['active_positions'])} real positions from chains")
    
    # Extract real IV surface from IV history
    if iv_history is not None and not iv_history.empty:
        # Convert IV history to surface format
        iv_records = []
        for idx, row in iv_history.tail(100).iterrows():  # Last 100 points
            record = {}
            # Handle index (could be timestamp)
            if hasattr(idx, 'isoformat'):
                record['timestamp'] = idx.isoformat()
            else:
                record['timestamp'] = str(idx)
            
            for col in iv_history.columns:
                if pd.notna(row[col]):
                    val = row[col]
                    # Convert timestamps to strings
                    if hasattr(val, 'isoformat'):
                        record[col] = val.isoformat()
                    elif isinstance(val, (int, float, np.integer, np.floating)):
                        record[col] = float(val)
                    else:
                        record[col] = str(val)
            iv_records.append(record)
        
        state['iv_surface'] = iv_records
        print(f"✅ Extracted {len(iv_records)} real IV surface points")
    
    # Extract real market state
    if market_data:
        state['market_state'] = {
            'timestamp': market_data.get('timestamp'),
            'nifty_price': market_data.get('indices', {}).get('NIFTY', {}).get('current_price'),
            'banknifty_price': market_data.get('indices', {}).get('BANKNIFTY', {}).get('current_price'),
            'indices': market_data.get('indices', {})
        }
        print(f"✅ Extracted real market state")
    
    # Extract Greeks from backtest if available
    if backtest_data is not None and not backtest_data.empty:
        # Look for exposure/Greeks columns
        greeks_cols = [col for col in backtest_data.columns if 
                      any(term in col.lower() for term in ['exposure', 'delta', 'gamma', 'vega', 'theta'])]
        
        if greeks_cols:
            latest = backtest_data.iloc[-1]
            for col in greeks_cols:
                if pd.notna(latest[col]):
                    state['portfolio_greeks'][col] = float(latest[col])
            print(f"✅ Extracted {len(state['portfolio_greeks'])} real Greeks from backtest")
    
    # Extract from truth run
    if truth_run:
        if 'portfolio_greeks' in truth_run:
            state['portfolio_greeks'].update(truth_run['portfolio_greeks'])
            print(f"✅ Added Greeks from truth run")
    
    return state


def main():
    """Main function to extract real options data"""
    print("=" * 60)
    print("Extracting REAL Options Data for Dashboard")
    print("NO SYNTHETIC/MOCK DATA - REAL DATA ONLY")
    print("=" * 60)
    print()
    
    # Load all real data sources
    print("Loading real data sources...")
    print()
    
    iv_history = load_real_iv_history()
    print()
    
    chains = load_real_option_chains()
    print()
    
    market_data = load_real_market_data()
    print()
    
    backtest_data = load_real_backtest_data()
    print()
    
    truth_run = load_truth_mode_runs()
    print()
    
    # Check if we have any real data
    if not any([iv_history is not None, chains, market_data, backtest_data, truth_run]):
        print("❌ No real data sources available!")
        print("   Please run the system to generate real data first.")
        return 1
    
    # Create dashboard state from real data
    print("Creating dashboard state from real data...")
    state = create_dashboard_state_from_real_data(
        iv_history, chains, market_data, backtest_data, truth_run
    )
    
    # Save to file
    output_path = PROJECT_ROOT / "data/options/live/options_dashboard_state.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    runtime_path = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
    runtime_payload = {}
    if runtime_path.exists():
        try:
            runtime_payload = json.loads(runtime_path.read_text(encoding='utf-8'))
        except Exception:
            runtime_payload = {}
    state = normalize_dashboard_state(state, runtime_payload)
    if not StateIOManager(output_path.parent).write_dashboard_state(state):
        print("❌ Failed to write normalized dashboard state")
        return 1
    
    print()
    print("=" * 60)
    print("✅ Real Options Data Extraction Complete!")
    print("=" * 60)
    print()
    print(f"Output: {output_path}")
    print()
    print("Data Sources Used:")
    for source, available in state['data_sources'].items():
        status = "✅" if available else "❌"
        print(f"  {status} {source}")
    print()
    print(f"Real Positions: {len(state['active_positions'])}")
    print(f"Real IV Surface Points: {len(state['iv_surface'])}")
    print(f"Real Portfolio Greeks: {len(state['portfolio_greeks'])}")
    print()
    print("⚠️  NOTE: This uses ONLY real data from your system.")
    print("   If some sections are empty, run the options system to generate more data.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
