#!/usr/bin/env python3
"""
Real-time Options System Monitor

Displays current positions, recent trades, and system status.
Run this in a separate terminal while the engine is running.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_positions_state():
    """Load current positions state"""
    state_file = Path("data/options/positions_state.json")
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text())
    except Exception as e:
        print(f"Error loading positions state: {e}")
        return None


def load_trade_ledger():
    """Load trade ledger"""
    ledger_file = Path("data/options/trade_ledger.parquet")
    if not ledger_file.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(ledger_file)
    except Exception as e:
        print(f"Error loading trade ledger: {e}")
        return pd.DataFrame()


def load_capital_state():
    """Load capital scaling state"""
    state_file = Path("data/options/capital_scaling_state.json")
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text())
    except Exception as e:
        print(f"Error loading capital state: {e}")
        return None


def format_currency(amount):
    """Format amount as Indian currency"""
    if amount is None:
        return "₹0"
    return f"₹{amount:,.0f}"


def format_percentage(value):
    """Format as percentage"""
    if value is None:
        return "0.00%"
    return f"{value:.2f}%"


def main():
    print("\n" + "="*70)
    print("📊 NORTHSTAR V3 OPTIONS SYSTEM - LIVE MONITOR")
    print("="*70)
    print(f"⏰ Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")

    # Load data
    state = load_positions_state()
    ledger = load_trade_ledger()
    capital = load_capital_state()

    if state is None:
        print("⚠️  No positions state found. Engine may not have run yet.")
        print("   Run: python scripts/run_integrated_options_paper_engine.py --mode single")
        return

    # System Status
    print("🔧 SYSTEM STATUS")
    print("-" * 70)
    print(f"  Last Update: {state.get('last_updated', 'Unknown')}")
    print(f"  Aggressive Mode: {'✅ Yes' if state.get('aggressive', False) else '❌ No'}")
    print(f"  Market Hours Only: {'✅ Yes' if state.get('market_hours_only', False) else '❌ No'}")
    print()

    # Capital & Risk
    print("💰 CAPITAL & RISK")
    print("-" * 70)
    if capital:
        print(f"  Current Equity: {format_currency(capital.get('current_equity'))}")
        print(f"  High Water Mark: {format_currency(capital.get('equity_high_water_mark'))}")
        print(f"  Risk per Trade: {format_percentage(capital.get('current_risk_pct'))}")
        print(f"  Drawdown: {format_percentage(capital.get('current_drawdown_pct') * 100)}")
        print(f"  Weeks Trading: {capital.get('weeks_trading', 0)}")
        print(f"  Can Scale: {'✅ Yes' if capital.get('can_scale', False) else '❌ No'}")
    else:
        print("  ⚠️  No capital state found")
    print()

    # Open Positions
    print("📈 OPEN POSITIONS")
    print("-" * 70)
    positions = state.get("active_positions", [])
    if positions:
        total_unrealized = 0
        for i, pos in enumerate(positions, 1):
            print(f"\n  Position {i}: {pos.get('position_id', 'Unknown')}")
            print(f"    Strategy: {pos.get('strategy_type', 'Unknown')}")
            print(f"    Entry: {pos.get('entry_time', 'Unknown')}")
            print(f"    Days Held: {pos.get('days_held', 0)}")
            print(f"    Max Loss: {format_currency(pos.get('max_loss'))}")
            print(f"    Max Profit: {format_currency(pos.get('max_profit'))}")
            print(f"    Unrealized P&L: {format_currency(pos.get('unrealized_pnl'))}")
            
            greeks = pos.get('greeks', {})
            if greeks:
                print(f"    Greeks: Δ={greeks.get('delta', 0):.2f} Γ={greeks.get('gamma', 0):.4f} "
                      f"Θ={greeks.get('theta', 0):.2f} ν={greeks.get('vega', 0):.2f}")
            
            total_unrealized += pos.get('unrealized_pnl', 0)
        
        print(f"\n  Total Unrealized P&L: {format_currency(total_unrealized)}")
    else:
        print("  No open positions")
    print()

    # Recent Trades
    print("📊 RECENT TRADES")
    print("-" * 70)
    if not ledger.empty:
        recent = ledger.tail(5)
        print(f"  Total Trades: {len(ledger)}")
        print(f"\n  Last 5 Trades:")
        for _, trade in recent.iterrows():
            action = trade.get('action', 'unknown')
            symbol = trade.get('position_id', 'Unknown')
            timestamp = trade.get('timestamp', 'Unknown')
            pnl = trade.get('pnl', 0)
            
            pnl_str = format_currency(pnl) if pnl != 0 else "-"
            emoji = "🟢" if action == "open" else ("🔴" if pnl < 0 else "🟢")
            
            print(f"    {emoji} {action.upper()}: {symbol} @ {timestamp} | P&L: {pnl_str}")
    else:
        print("  No trades yet")
    print()

    # Trade Metrics
    print("📈 PERFORMANCE METRICS")
    print("-" * 70)
    metrics = state.get("trade_metrics", {})
    print(f"  Total Trades: {metrics.get('total_trades', 0)}")
    print(f"  Winning Trades: {metrics.get('winning_trades', 0)}")
    print(f"  Losing Trades: {metrics.get('losing_trades', 0)}")
    print(f"  Win Rate: {format_percentage(metrics.get('win_rate', 0) * 100)}")
    print(f"  Total P&L: {format_currency(metrics.get('total_pnl', 0))}")
    print(f"  Avg Win: {format_currency(metrics.get('avg_win', 0))}")
    print(f"  Avg Loss: {format_currency(metrics.get('avg_loss', 0))}")
    print()

    # Last Regime Detection
    print("🌡️  LAST REGIME DETECTION")
    print("-" * 70)
    last_regime = state.get("last_regime_detection", {})
    if last_regime:
        print(f"  Timestamp: {last_regime.get('timestamp', 'Unknown')}")
        print(f"  Underlying: {last_regime.get('underlying', 'Unknown')}")
        print(f"  Regime: {last_regime.get('regime', 'Unknown')}")
        print(f"  Routed Regime: {last_regime.get('routed_regime', 'Unknown')}")
        print(f"  IV Rank: {format_percentage(last_regime.get('iv_rank', 0) * 100)}")
        print(f"  Confidence: {format_percentage(last_regime.get('confidence', 0) * 100)}")
    else:
        print("  No regime detection data")
    print()

    # Last Trade Eligibility
    print("✅ LAST ELIGIBILITY CHECK")
    print("-" * 70)
    eligibility = state.get("last_trade_eligibility", {})
    if eligibility:
        print(f"  Signal Generated: {'✅ Yes' if eligibility.get('signal_generated') else '❌ No'}")
        print(f"  Rejected: {'❌ Yes' if eligibility.get('rejected') else '✅ No'}")
        print(f"  Strategy Type: {eligibility.get('strategy_type', 'Unknown')}")
        print(f"  Regime: {eligibility.get('regime', 'Unknown')}")
        
        violations = eligibility.get('violations', [])
        if violations:
            print(f"  Violations: {', '.join(violations)}")
    else:
        print("  No eligibility check data")
    print()

    # Weekly Risk Usage
    print("📊 WEEKLY RISK USAGE")
    print("-" * 70)
    weekly = state.get("weekly_risk_usage", {})
    print(f"  Trades Used: {weekly.get('trades_used', 0)} / {weekly.get('max_trades', 0)}")
    print(f"  Capital Used: {format_currency(weekly.get('capital_used', 0))} / "
          f"{format_currency(weekly.get('max_capital', 0))}")
    print()

    print("="*70)
    print("💡 TIP: Run this script periodically to monitor system status")
    print("   Or use: watch -n 30 python scripts/monitor_options.py")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Monitor stopped")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
