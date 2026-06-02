#!/usr/bin/env python3
"""
Rebuild P&L Ledger from Actual Trading History - FINAL VERSION

This script:
1. Clears incorrect NAV history that predates the system
2. Rebuilds NAV from actual first trade date
3. Sets correct inception date based on actual trading start
4. Ensures P&L reflects only real trades, not simulated history
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil

print('=' * 80)
print('REBUILDING P&L LEDGER FROM ACTUAL TRADING HISTORY')
print('=' * 80)

# Paths
LEDGER_PATH = Path('data/pnl/master_ledger.parquet')
NAV_PATH = Path('data/pnl/nav_history.parquet')
ATTRIBUTION_PATH = Path('data/pnl/attribution_daily.parquet')
RECON_PATH = Path('data/pnl/reconciliation_log.parquet')
EXEC_PATH = Path('data/pnl/execution_quality.parquet')

# Backup existing files
print('\n1. BACKING UP EXISTING DATA')
backup_dir = Path('data/pnl/backup_before_rebuild')
backup_dir.mkdir(parents=True, exist_ok=True)

for path in [LEDGER_PATH, NAV_PATH, ATTRIBUTION_PATH, RECON_PATH, EXEC_PATH]:
    if path.exists():
        backup_path = backup_dir / f'{path.stem}_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.parquet'
        shutil.copy(path, backup_path)
        print(f'   ✓ Backed up {path.name}')

# Load and analyze ledger
print('\n2. ANALYZING ACTUAL TRADING HISTORY')
df = pd.read_parquet(LEDGER_PATH)
df['trade_date'] = pd.to_datetime(df['trade_date'], errors='coerce')

# Find actual first trade date
first_trade = df['trade_date'].min()
last_trade = df['trade_date'].max()
actual_trading_days = df['trade_date'].dt.date.nunique()

print(f'   First actual trade: {first_trade}')
print(f'   Last actual trade: {last_trade}')
print(f'   Total days with activity: {actual_trading_days}')

# Set inception date to first trade (rounded to start of day)
INCEPTION_DATE = first_trade.replace(hour=0, minute=0, second=0, microsecond=0)
print(f'   ✓ Setting inception date to: {INCEPTION_DATE.date()}')

# Clear incorrect NAV history
print('\n3. CLEARING INCORRECT NAV HISTORY')
if NAV_PATH.exists():
    nav_df = pd.read_parquet(NAV_PATH)
    old_nav_count = len(nav_df)
    
    # Date might be index or column
    if 'date' in nav_df.columns:
        date_col = 'date'
    elif nav_df.index.name == 'date':
        nav_df = nav_df.reset_index()
        date_col = 'date'
    else:
        # Assume first column is date or create date range
        print('   ⚠ No date column found, will regenerate NAV')
        nav_df = pd.DataFrame()
    
    if len(nav_df) > 0 and date_col in nav_df.columns:
        nav_df[date_col] = pd.to_datetime(nav_df[date_col], errors='coerce')
        
        # Filter to only dates on or after inception
        nav_df = nav_df[nav_df[date_col] >= INCEPTION_DATE].copy()
        
        # Save corrected NAV
        nav_df.to_parquet(NAV_PATH, index=False)
        print(f'   ✓ Removed {old_nav_count - len(nav_df)} fake NAV days')
        print(f'   ✓ Remaining NAV days: {len(nav_df)} (from {INCEPTION_DATE.date()})')
    else:
        print(f'   ✓ Cleared {old_nav_count} fake NAV days')

# Recompute NAV from ledger
print('\n4. RECOMPUTING NAV FROM LEDGER')
from src.pnl.ledger import UnifiedPnLLedger
from src.pnl.nav_calculator import NAVCalculator

ledger = UnifiedPnLLedger()
nav_calc = NAVCalculator(ledger, config={
    'pnl': {
        'nav': {
            'starting_capital_inr': 10000000,  # ₹1 crore
            'inception_date': INCEPTION_DATE.strftime('%Y-%m-%d'),
        }
    }
})

# Compute NAV from inception to today
nav_data = nav_calc.compute_daily_nav(
    start_date=INCEPTION_DATE,
    end_date=datetime.now()
)

# Ensure date column is saved
if nav_data.index.name != 'date':
    nav_data = nav_data.reset_index()
    nav_data = nav_data.rename(columns={'index': 'date'})

print(f'   ✓ Computed {len(nav_data)} days of NAV')
if len(nav_data) > 0 and 'nav_combined' in nav_data.columns:
    print(f'   ✓ Starting NAV: ₹{nav_data["nav_combined"].iloc[0]:,.0f}')
    print(f'   ✓ Current NAV: ₹{nav_data["nav_combined"].iloc[-1]:,.0f}')
    total_return = ((nav_data["nav_combined"].iloc[-1] / nav_data["nav_combined"].iloc[0]) - 1) * 100
    print(f'   ✓ Total return: {total_return:.2f}%')

# Save corrected NAV
nav_data.to_parquet(NAV_PATH, index=False)
print(f'   ✓ Saved corrected NAV to {NAV_PATH}')

# Update PnLState in config
print('\n5. UPDATING PNL STATE')
from src.core.state import UnifiedState
from src.pnl.pnl_state import PnLState

state = UnifiedState()

# Update state with current values
if len(nav_data) > 0 and 'nav_combined' in nav_data.columns:
    state.pnl_state.current_nav_inr = nav_data['nav_combined'].iloc[-1]
    state.pnl_state.current_nav_per_unit = nav_data.get('nav_per_unit', pd.Series([1000.0])).iloc[-1]
    total_return = ((nav_data['nav_combined'].iloc[-1] / nav_data['nav_combined'].iloc[0]) - 1) * 100
    state.pnl_state.nav_return_since_inception_pct = total_return
    
    # Compute drawdown
    if 'drawdown' in nav_data.columns:
        state.pnl_state.current_drawdown_pct = nav_data['drawdown'].iloc[-1]
        state.pnl_state.max_drawdown_to_date_pct = nav_data['max_drawdown_to_date'].iloc[-1]
    
    # Fund health
    if state.pnl_state.nav_return_since_inception_pct >= 0:
        state.pnl_state.fund_health = 'ON_TRACK'
    elif state.pnl_state.nav_return_since_inception_pct >= -10:
        state.pnl_state.fund_health = 'WARNING'
    else:
        state.pnl_state.fund_health = 'BREACH'
    
    state.pnl_state.last_updated = datetime.now()
    
    print(f'   ✓ PnLState updated')
    print(f'   ✓ Current NAV: ₹{state.pnl_state.current_nav_inr:,.0f}')
    print(f'   ✓ Return: {state.pnl_state.nav_return_since_inception_pct:.2f}%')
    print(f'   ✓ Fund health: {state.pnl_state.fund_health}')

# Generate summary report
print('\n6. GENERATING REBUILD REPORT')
report = {
    'rebuild_date': datetime.now().isoformat(),
    'inception_date': INCEPTION_DATE.isoformat(),
    'first_trade_date': str(first_trade),
    'last_trade_date': str(last_trade),
    'total_trading_days': int(actual_trading_days),
    'ledger_entries': len(df),
    'nav_days_before': old_nav_count if 'old_nav_count' in locals() else 0,
    'nav_days_after': len(nav_data),
    'starting_nav': float(nav_data['nav_combined'].iloc[0]) if len(nav_data) > 0 else None,
    'current_nav': float(nav_data['nav_combined'].iloc[-1]) if len(nav_data) > 0 else None,
    'total_return_pct': float(total_return) if len(nav_data) > 0 and 'total_return' in locals() else None,
    'entries_by_book': df['book'].value_counts().to_dict() if 'book' in df.columns else {},
    'entries_by_type': df['entry_type'].value_counts().to_dict() if 'entry_type' in df.columns else {},
}

import json
report_path = Path('data/pnl/rebuild_report.json')
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)

print(f'   ✓ Report saved to {report_path}')

print('\n' + '=' * 80)
print('✓ P&L LEDGER REBUILD COMPLETE')
print('=' * 80)
print(f'\nSummary:')
print(f'  Inception Date: {INCEPTION_DATE.date()}')
print(f'  Trading Days: {actual_trading_days}')
print(f'  Ledger Entries: {len(df):,}')
print(f'  NAV Days: {len(nav_data)}')
print(f'  Starting NAV: ₹{nav_data["nav_combined"].iloc[0]:,.0f}')
print(f'  Current NAV: ₹{nav_data["nav_combined"].iloc[-1]:,.0f}')
total_return = ((nav_data["nav_combined"].iloc[-1] / nav_data["nav_combined"].iloc[0]) - 1) * 100
print(f'  Total Return: {total_return:.2f}%')
print(f'  Fund Health: {state.pnl_state.fund_health}')
print('\nAll P&L data now reflects ACTUAL trading history only.')
print('=' * 80)
