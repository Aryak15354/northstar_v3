#!/usr/bin/env python3
"""
Enhanced End-of-Day Rebalancing Script with Gap 5 P&L Integration

Performs end-of-day portfolio rebalancing with unified P&L accounting.
"""

import argparse
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
import yaml
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pnl.ledger import UnifiedPnLLedger
from src.pnl.nav_calculator import NAVCalculator
from src.pnl.attribution import PnLAttributor
from src.pnl.reconciliation import PnLReconciler
from src.pnl.execution_quality import ExecutionQualityMonitor
from src.pnl.paper_fund import PaperFundManager
from src.core.state import UnifiedState


logger = logging.getLogger(__name__)


def _empty_result() -> dict:
    """Return an explicit empty mapping for unavailable optional data."""
    return dict()


def load_config():
    """Load P&L configuration"""
    config_path = Path("config/pnl_config.yaml")
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    else:
        # Default config
        return {
            'pnl': {
                'nav': {
                    'starting_capital_inr': 10_000_000,
                    'inception_date': '2024-09-01',
                    'nav_unit_size': 1000,
                    'benchmark': 'NIFTY500_TR',
                    'risk_free_rate_pct': 6.5
                },
                'paper_fund': {
                    'inception_date': '2024-09-01',
                    'starting_capital_inr': 10_000_000,
                    'fund_name': 'Northstar V3 Paper Fund',
                    'target_monthly_return_pct': 2.0,
                    'max_acceptable_drawdown_pct': -15.0,
                    'min_sharpe_ratio': 1.2
                },
                'reconciliation': {
                    'equity_options_tolerance_inr': 100,
                    'live_shadow_threshold_pct': 0.5,
                    'legacy_tolerance_inr': 1000
                }
            }
        }


def load_current_positions() -> dict:
    """Load current equity positions from canonical runtime or portfolio weights."""
    current_positions_path = Path("data/portfolio/current_positions.json")
    if current_positions_path.exists():
        payload = json.loads(current_positions_path.read_text(encoding="utf-8"))
        positions = payload.get("positions") or {}
        normalized = {}
        for ticker, position in positions.items():
            if not isinstance(position, dict):
                continue
            normalized[str(ticker)] = {
                "quantity": float(position.get("quantity") or 0.0),
                "avg_cost": float(position.get("avg_price") or position.get("avg_cost") or position.get("current_price") or 0.0),
                "strategy_id": position.get("position_role"),
                "weight": float(position.get("weight") or position.get("weight_pct") or 0.0),
            }
        if normalized:
            return normalized

    weights_path = Path("data/processed/portfolio_weights.parquet")
    if not weights_path.exists():
        raise FileNotFoundError(
            "Current positions not found at data/portfolio/current_positions.json or "
            "data/processed/portfolio_weights.parquet"
        )

    weights = pd.read_parquet(weights_path)
    ticker_col = "ticker" if "ticker" in weights.columns else "symbol"
    weight_col = "weight" if "weight" in weights.columns else "final_weight"
    if ticker_col not in weights.columns or weight_col not in weights.columns:
        raise ValueError("portfolio_weights.parquet missing ticker/symbol or weight/final_weight")

    return {
        str(row[ticker_col]): {
            "quantity": 0.0,
            "avg_cost": 0.0,
            "weight": float(row.get(weight_col) or 0.0),
            "strategy_id": row.get("position_role"),
        }
        for _, row in weights.iterrows()
    }


def load_eod_prices(tickers: list[str], trade_date: datetime) -> dict:
    """Load end-of-day equity prices from the canonical processed price store."""
    prices_path = Path("data/processed/prices.parquet")
    if not prices_path.exists():
        raise FileNotFoundError(f"Price data not found at {prices_path}")

    prices = pd.read_parquet(prices_path, columns=["Date", "Close", "ticker"])
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce").dt.normalize()
    filtered = prices[prices["Date"] == pd.Timestamp(trade_date).normalize()]
    if tickers:
        filtered = filtered[filtered["ticker"].isin(tickers)]
    if filtered.empty:
        raise ValueError(f"No EOD prices found for {trade_date:%Y-%m-%d}")
    return filtered.drop_duplicates(subset=["ticker"], keep="last").set_index("ticker")["Close"].astype(float).to_dict()


def resolve_effective_rebalance_date(tickers: list[str], requested_date: datetime) -> datetime:
    """Resolve the most recent available EOD date at or before the requested date."""
    prices_path = Path("data/processed/prices.parquet")
    if not prices_path.exists():
        raise FileNotFoundError(f"Price data not found at {prices_path}")

    prices = pd.read_parquet(prices_path, columns=["Date", "ticker"])
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce").dt.normalize()
    prices = prices.dropna(subset=["Date"])
    if tickers:
        prices = prices[prices["ticker"].isin(tickers)]
    prices = prices[prices["Date"] <= pd.Timestamp(requested_date).normalize()]
    if prices.empty:
        raise ValueError(f"No EOD price history available on or before {requested_date:%Y-%m-%d}")
    return pd.Timestamp(prices["Date"].max()).to_pydatetime()


def load_options_positions() -> dict:
    """Load current options positions from the canonical runtime state."""
    runtime_path = Path("data/options/live/options_runtime_state.json")
    if not runtime_path.exists():
        logger.warning("Options runtime state not found - assuming no open options positions")
        return _empty_result()

    payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    open_positions = payload.get("open_positions") or {}
    if isinstance(open_positions, list):
        normalized = {}
        for idx, position in enumerate(open_positions):
            if not isinstance(position, dict):
                continue
            position_id = str(position.get("position_id") or position.get("symbol") or f"options_{idx}")
            normalized[position_id] = position
        return normalized
    if isinstance(open_positions, dict):
        return {str(key): value for key, value in open_positions.items() if isinstance(value, dict)}
    return _empty_result()


def load_options_eod_prices(trade_date: Optional[datetime] = None) -> dict:
    """Load options EOD price marks from the dashboard/runtime state when available."""
    dashboard_path = Path("data/options/live/options_dashboard_state.json")
    if not dashboard_path.exists():
        logger.warning("Options dashboard state not found - returning empty options prices")
        return _empty_result()

    payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
    latest_prices = payload.get("latest_prices")
    if isinstance(latest_prices, dict):
        return latest_prices

    market_snapshot = payload.get("market_snapshot") or {}
    if isinstance(market_snapshot, dict):
        option_contracts = market_snapshot.get("option_contracts")
        if isinstance(option_contracts, dict):
            return option_contracts

    logger.warning("Options price marks unavailable in dashboard state - returning empty options prices")
    return _empty_result()


def eod_rebalance_with_pnl(*, dry_run: bool = False) -> bool:
    """Perform EOD rebalancing with P&L accounting"""
    print("=" * 80)
    print("END-OF-DAY REBALANCING WITH UNIFIED P&L ACCOUNTING")
    print(f"Time: {datetime.now()}")
    print("=" * 80)
    
    today = datetime.now()
    
    # Load configuration
    print("\n1. Loading configuration...")
    config = load_config()
    print("   ✓ Configuration loaded")
    
    # Initialize P&L system
    print("\n2. Initializing P&L system...")
    ledger = UnifiedPnLLedger("data/pnl/master_ledger.parquet", config)
    nav_calculator = NAVCalculator(ledger, config)
    attributor = PnLAttributor(ledger, None, config)  # registry=None for now
    reconciler = PnLReconciler(ledger, nav_calculator, config)
    execution_monitor = ExecutionQualityMonitor(ledger, config)
    paper_fund = PaperFundManager(ledger, nav_calculator, attributor, config)
    print("   ✓ P&L system initialized")
    
    # Load UnifiedState
    print("\n3. Loading UnifiedState...")
    state = UnifiedState()
    print("   ✓ UnifiedState loaded")
    
    # Get current positions and prices
    print("\n4. Loading portfolio data...")
    equity_positions = load_current_positions()
    effective_trade_date = resolve_effective_rebalance_date(list(equity_positions.keys()), today)
    if effective_trade_date.date() != today.date():
        print(
            f"   ⚠ Requested {today:%Y-%m-%d} but using latest available EOD date "
            f"{effective_trade_date:%Y-%m-%d}"
        )
    equity_prices = load_eod_prices(list(equity_positions.keys()), effective_trade_date)
    options_positions = load_options_positions()
    options_prices = load_options_eod_prices(effective_trade_date)
    print(f"   ✓ Equity positions: {len(equity_positions)}")
    print(f"   ✓ Options positions: {len(options_positions)}")
    print(f"   ✓ Equity prices: {len(equity_prices)}")
    print(f"   ✓ Options prices: {len(options_prices)}")

    if dry_run:
        print("\nDRY RUN COMPLETE")
        print("   ✓ Real EOD data inputs loaded successfully")
        return bool(equity_positions) and bool(equity_prices)
    
    # === CORE EOD PROCESSING ===
    
    # Step 1: Record EOD mark-to-market
    print("\n5. Recording EOD mark-to-market...")
    try:
        ledger.record_eod_mark(
            date=today,
            equity_positions=equity_positions,
            equity_prices=equity_prices,
            options_positions=options_positions,
            options_prices=options_prices
        )
        print("   ✓ EOD marks recorded")
    except Exception as e:
        print(f"   ⚠ Warning: EOD mark recording failed: {e}")
    
    # Step 2: Flush ledger to disk
    print("\n6. Flushing ledger to disk...")
    ledger.flush()
    print("   ✓ Ledger flushed")
    
    # Step 3: Write daily attribution
    print("\n7. Computing daily attribution...")
    try:
        attributor.write_daily_attribution(today)
        print("   ✓ Attribution written")
    except Exception as e:
        print(f"   ⚠ Warning: Attribution failed: {e}")
    
    # Step 4: Compute execution quality
    print("\n8. Computing execution quality...")
    try:
        execution_monitor.write_daily_execution_quality(today)
        print("   ✓ Execution quality written")
    except Exception as e:
        print(f"   ⚠ Warning: Execution quality failed: {e}")
    
    # Step 5: Run daily reconciliation
    print("\n9. Running daily reconciliation...")
    recon_result = None
    try:
        recon_result = reconciler.run_daily_reconciliation(today)
        reconciler.write_reconciliation_log(recon_result)
        
        status_symbol = "✓" if recon_result.overall_status == "CLEAN" else "⚠"
        print(f"   {status_symbol} Reconciliation status: {recon_result.overall_status}")
        
        if recon_result.overall_status == 'CRITICAL':
            print(f"   ✗ CRITICAL: Reconciliation failures detected!")
            for action in recon_result.action_required:
                print(f"      - {action}")
            # TODO: Emit event to event bus
        elif recon_result.overall_status == 'WARNING':
            print(f"   ⚠ WARNING: Minor reconciliation issues")
            for action in recon_result.action_required:
                print(f"      - {action}")
    except Exception as e:
        print(f"   ✗ Reconciliation failed: {e}")
    
    # Step 6: Update PnLState in UnifiedState
    print("\n10. Updating PnLState...")
    try:
        # Today's P&L
        state.pnl_state.pnl_today_inr = ledger.get_total_pnl(today)
        
        # Current NAV
        nav_df = nav_calculator.compute_daily_nav(
            config['pnl']['nav']['inception_date'],
            today
        )
        if len(nav_df) > 0:
            state.pnl_state.current_nav_inr = nav_df['nav_combined'].iloc[-1]
            state.pnl_state.current_nav_per_unit = nav_df['nav_per_unit'].iloc[-1]
            state.pnl_state.current_drawdown_pct = nav_df['drawdown'].iloc[-1] * 100
        
        # Fund health
        fund_status = paper_fund.compute_current_fund_status()
        state.pnl_state.fund_health = fund_status.get('fund_health', 'UNKNOWN')
        
        # Reconciliation status
        if recon_result is not None:
            state.pnl_state.last_reconciliation_status = recon_result.overall_status
            state.pnl_state.last_reconciliation_date = today
        
        # Update timestamp
        state.pnl_state.last_updated = datetime.now()
        state.pnl_state.last_eod_processing = today
        
        print("   ✓ PnLState updated")
        print(f"      Today's P&L: ₹{state.pnl_state.pnl_today_inr:,.2f}")
        print(f"      Current NAV: ₹{state.pnl_state.current_nav_inr:,.2f}")
        print(f"      Fund Health: {state.pnl_state.fund_health}")
    except Exception as e:
        print(f"   ⚠ Warning: PnLState update failed: {e}")
    
    # Step 7: Check paper fund health
    print("\n11. Checking paper fund health...")
    try:
        alerts = paper_fund.check_fund_health_alerts()
        if alerts:
            print(f"   ⚠ {len(alerts)} fund health alerts:")
            for alert in alerts:
                print(f"      - {alert}")
        else:
            print("   ✓ No fund health alerts")
    except Exception as e:
        print(f"   ⚠ Warning: Fund health check failed: {e}")
    
    
    # Step 8: Export NAV history for dashboard
    print("\n12. Exporting NAV history for dashboard...")
    try:
        nav_history_path = Path("data/pnl/nav_history.parquet")
        if len(nav_df) > 0:
            # Prepare NAV history for dashboard
            nav_export = nav_df.reset_index()
            nav_export.columns = ['date'] + list(nav_export.columns[1:])
            nav_export.to_parquet(nav_history_path, index=False)
            print(f"   ✓ NAV history exported to {nav_history_path}")
        else:
            print("   ⚠ No NAV data to export")
    except Exception as e:
        print(f"   ⚠ Warning: NAV history export failed: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("EOD PROCESSING COMPLETE")
    print("=" * 80)
    print(f"\n✓ Ledger entries: {len(ledger.query())}")
    print(f"✓ Today's P&L: ₹{state.pnl_state.pnl_today_inr:,.2f}")
    print(f"✓ Reconciliation: {recon_result.overall_status}")
    print(f"✓ Fund Health: {state.pnl_state.fund_health}")
    
    # Write summary to log
    summary_path = Path("logs/eod_pnl_summary.log")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, 'a') as f:
        f.write(f"\n{today.date()} | P&L: {state.pnl_state.pnl_today_inr:.2f} | ")
        f.write(f"NAV: {state.pnl_state.current_nav_inr:.2f} | ")
        f.write(f"Recon: {recon_result.overall_status} | ")
        f.write(f"Health: {state.pnl_state.fund_health}\n")
    

    # === Gap 7: Run EOD State Reconciliation ===
    print("\n" + "=" * 60)
    print("Running EOD State Reconciliation")
    print("=" * 60)
    
    try:
        from src.core.state_authority import StateAuthority
        from src.core.state_reconciler import StateReconciler
        from src.core.state_bridges.options_bridge import OptionsStateBridge
        from src.core.state_bridges.shadow_bridge import ShadowStateBridge
        from src.core.state_bridges.valuation_bridge import ValuationStateBridge
        from src.core.state_bridges.runtime_bridge import RuntimeStateBridge
        
        # Initialize state management
        state = UnifiedState()
        state_authority = StateAuthority(state)
        
        # Initialize bridges (with minimal dependencies for EOD)
        options_bridge = None  # Would need actual position_manager
        shadow_bridge = ShadowStateBridge(state_authority)
        valuation_bridge = ValuationStateBridge(state_authority)
        runtime_bridge = RuntimeStateBridge(state_authority)
        
        # Initialize reconciler
        reconciler = StateReconciler(
            unified_state=state,
            options_bridge=options_bridge,
            shadow_bridge=shadow_bridge,
            valuation_bridge=valuation_bridge,
            runtime_bridge=runtime_bridge,
            state_authority=state_authority
        )
        
        # Run full reconciliation
        report = reconciler.run_full_reconciliation(datetime.now())
        
        print(f"\nReconciliation Status: {report.overall_status}")
        print(f"Can Trade Tomorrow: {report.can_trade}")
        
        if report.action_required:
            print("\nActions Required:")
            for action in report.action_required:
                print(f"  - {action}")
        
        # Write report
        reconciler.write_reconciliation_report(report)
        
        if not report.can_trade:
            print("\n⚠️  WARNING: State reconciliation failed")
            print("   System should not trade until issues are resolved")
        
    except Exception as e:
        print(f"\n⚠️ EOD reconciliation failed: {e}")
        import traceback
        traceback.print_exc()

    return True


def main():
    parser = argparse.ArgumentParser(description="Run EOD rebalance with unified P&L accounting")
    parser.add_argument("--dry-run", action="store_true", help="Load real data inputs and exit before mutating the ledger")
    args = parser.parse_args()
    try:
        success = eod_rebalance_with_pnl(dry_run=bool(args.dry_run))
        return 0 if success else 1
    except Exception as e:
        print(f"\n✗ EOD processing failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
