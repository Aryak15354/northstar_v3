#!/usr/bin/env python3
"""
Gap 5 P&L System Demo

Demonstrates the Unified P&L Ledger System in action.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pnl.ledger import UnifiedPnLLedger, LedgerBook
from src.pnl.nav_calculator import NAVCalculator
from src.pnl.attribution import PnLAttributor
from src.pnl.reconciliation import PnLReconciler
from src.pnl.execution_quality import ExecutionQualityMonitor
from src.pnl.paper_fund import PaperFundManager
from src.core.state import UnifiedState


def demo_basic_ledger():
    """Demonstrate basic ledger operations"""
    print("\n" + "="*80)
    print("DEMO 1: Basic Ledger Operations")
    print("="*80)
    
    ledger = UnifiedPnLLedger("data/pnl/demo_ledger.parquet")
    
    # Record some equity trades
    print("\n1. Recording equity trades...")
    ledger.record_equity_trade(
        ticker="RELIANCE",
        quantity=100,
        price=2500.0,
        strategy_id="momentum_specialist",
        transaction_cost=-125.0
    )
    print("   ✓ Bought 100 RELIANCE @ ₹2500")
    
    ledger.record_equity_trade(
        ticker="TCS",
        quantity=50,
        price=3500.0,
        strategy_id="quality_specialist",
        transaction_cost=-87.50
    )
    print("   ✓ Bought 50 TCS @ ₹3500")
    
    # Record an options trade
    print("\n2. Recording options trade...")
    ledger.record_options_trade(
        ticker="NIFTY",
        quantity=50,
        price=200.0,
        option_type="CE",
        strike=25000.0,
        expiry=datetime.now() + timedelta(days=30),
        greeks={"delta": 0.54, "gamma": 0.0007, "theta": -8.96, "vega": 18.39},
        strategy_id="volatility_specialist",
        transaction_cost=-50.0
    )
    print("   ✓ Bought 50 NIFTY 25000 CE @ ₹200")
    
    # Flush to disk
    print("\n3. Flushing ledger to disk...")
    ledger.flush()
    print("   ✓ Ledger written to data/pnl/demo_ledger.parquet")
    
    # Query ledger
    print("\n4. Querying ledger...")
    df = ledger.query()
    print(f"   ✓ Total entries: {len(df)}")
    print(f"   ✓ Equity entries: {len(df[df['book'] == 'EQUITY'])}")
    print(f"   ✓ Options entries: {len(df[df['book'] == 'OPTIONS'])}")
    
    # Get total P&L
    total_pnl = ledger.get_total_pnl(datetime.now())
    print(f"\n5. Total P&L: ₹{total_pnl:,.2f}")
    
    # Get open positions
    positions = ledger.get_open_positions(datetime.now())
    print(f"\n6. Open positions: {len(positions)}")
    for _, pos in positions.iterrows():
        print(f"   - {pos['ticker']}: {pos['quantity']} shares @ ₹{pos['avg_cost']:.2f}")


def demo_nav_calculation():
    """Demonstrate NAV calculation"""
    print("\n" + "="*80)
    print("DEMO 2: NAV Calculation")
    print("="*80)
    
    ledger = UnifiedPnLLedger("data/pnl/demo_ledger.parquet")
    
    config = {
        'pnl': {
            'nav': {
                'starting_capital_inr': 10_000_000,
                'inception_date': '2024-09-01',
                'nav_unit_size': 1000,
                'benchmark': 'NIFTY500_TR',
                'risk_free_rate_pct': 6.5
            }
        }
    }
    
    nav_calc = NAVCalculator(ledger, config)
    
    print(f"\n1. Fund Configuration:")
    print(f"   Starting Capital: ₹{nav_calc.starting_capital:,.0f}")
    print(f"   Inception Date: {nav_calc.inception_date.date()}")
    print(f"   NAV Unit Size: ₹{nav_calc.nav_unit_size}")
    print(f"   Initial Units: {nav_calc.initial_units:,.0f}")
    
    # Compute NAV (would need actual data)
    print(f"\n2. NAV Calculation:")
    print(f"   (Requires historical ledger data for full demonstration)")


def demo_state_integration():
    """Demonstrate PnLState integration"""
    print("\n" + "="*80)
    print("DEMO 3: UnifiedState Integration")
    print("="*80)
    
    state = UnifiedState()
    
    print("\n1. PnLState in UnifiedState:")
    print(f"   ✓ Has pnl_state: {hasattr(state, 'pnl_state')}")
    
    print("\n2. PnLState Fields:")
    pnl_dict = state.pnl_state.to_dict()
    for key, value in list(pnl_dict.items())[:10]:
        print(f"   - {key}: {value}")
    
    print(f"\n3. Total PnLState fields: {len(pnl_dict)}")


def demo_multi_book_accounting():
    """Demonstrate multi-book accounting"""
    print("\n" + "="*80)
    print("DEMO 4: Multi-Book Accounting")
    print("="*80)
    
    ledger = UnifiedPnLLedger("data/pnl/demo_multibook_ledger.parquet")
    
    # Record live trade
    print("\n1. Recording LIVE trade...")
    ledger.record_equity_trade(
        ticker="INFY",
        quantity=100,
        price=1500.0,
        strategy_id="test",
        transaction_cost=-75.0,
        source='LIVE'
    )
    print("   ✓ LIVE: Bought 100 INFY @ ₹1500")
    
    # Record shadow trade (for execution quality comparison)
    print("\n2. Recording SHADOW trade (expected price)...")
    ledger.record_equity_trade(
        ticker="INFY",
        quantity=100,
        price=1495.0,  # Expected VWAP
        strategy_id="test",
        transaction_cost=-75.0,
        source='PAPER'
    )
    print("   ✓ SHADOW: Expected 100 INFY @ ₹1495")
    
    ledger.flush()
    
    # Query by book
    print("\n3. Querying by book...")
    live_df = ledger.query(books=[LedgerBook.EQUITY])
    shadow_df = ledger.query(books=[LedgerBook.SHADOW])
    
    print(f"   ✓ LIVE book: {len(live_df)} entries")
    print(f"   ✓ SHADOW book: {len(shadow_df)} entries")
    
    # Compute slippage
    live_cost = live_df['notional'].sum()
    shadow_cost = shadow_df['notional'].sum()
    slippage = live_cost - shadow_cost
    slippage_bps = (slippage / shadow_cost * 10000) if shadow_cost > 0 else 0
    
    print(f"\n4. Execution Quality:")
    print(f"   Live cost: ₹{live_cost:,.2f}")
    print(f"   Expected cost: ₹{shadow_cost:,.2f}")
    print(f"   Slippage: ₹{slippage:,.2f} ({slippage_bps:.2f} bps)")


def main():
    """Run all demos"""
    print("\n" + "="*80)
    print("GAP 5: UNIFIED P&L LEDGER SYSTEM - DEMONSTRATION")
    print("="*80)
    print(f"Demo started at: {datetime.now()}")
    
    try:
        demo_basic_ledger()
        demo_nav_calculation()
        demo_state_integration()
        demo_multi_book_accounting()
        
        print("\n" + "="*80)
        print("✓ ALL DEMOS COMPLETED SUCCESSFULLY")
        print("="*80)
        print("\nThe Unified P&L Ledger System is operational.")
        print("\nKey Features Demonstrated:")
        print("  ✓ Immutable ledger with equity and options trades")
        print("  ✓ Multi-book accounting (EQUITY, OPTIONS, SHADOW)")
        print("  ✓ NAV calculation framework")
        print("  ✓ UnifiedState integration")
        print("  ✓ Execution quality measurement")
        
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
