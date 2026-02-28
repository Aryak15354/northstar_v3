"""
Integration Test: P&L Calculation and Trade Ledger

Tests the complete flow:
1. Open position
2. Update MTM
3. Close position with P&L calculation
4. Write to trade ledger
5. Verify ledger integrity

This verifies P&L and ledger work end-to-end.
"""

import pytest
from datetime import datetime, date, timedelta
import pandas as pd
import tempfile
import os

from src.options.position_manager import PositionManager, Position
from src.options.strategy_generator import OptionStrategy, OptionLeg, Greeks, StrategyType
from src.options.regime_detector import Regime
from src.options.config_loader import ExitRulesConfig, GreekSafetyBandsConfig
from src.options.tax_aware_pnl_tracker import TaxAwarePnLTracker, TradeCosts
from src.options.trade_ledger import TradeLedger


@pytest.fixture
def temp_ledger_path():
    """Create temporary ledger file"""
    temp_dir = tempfile.mkdtemp()
    ledger_path = os.path.join(temp_dir, "test_ledger.parquet")
    yield ledger_path
    # Cleanup
    if os.path.exists(ledger_path):
        os.remove(ledger_path)
    os.rmdir(temp_dir)


@pytest.fixture
def position_manager():
    """Create position manager"""
    exit_config = ExitRulesConfig(
        profit_target_pct=0.55,
        stop_loss_pct=0.40,
        days_before_expiry=2,
        precedence=['stop_loss', 'gamma_escalation', 'regime_flip', 'time_decay', 'profit_target']
    )
    
    greek_config = GreekSafetyBandsConfig(
        delta_min=-0.2,
        delta_max=0.2,
        theta_min=0.0,
        vega_min=-0.3,
        vega_max=0.1,
        gamma_escalation={'spike_multiplier': 2.0}
    )
    
    return PositionManager(exit_config, greek_config)


@pytest.fixture
def pnl_tracker():
    """Create P&L tracker"""
    from src.options.config_loader import CostsConfig, TaxConfig
    
    costs_config = CostsConfig(
        brokerage_per_leg=20.0,
        exchange_charges_pct=0.0005,
        sebi_charges_per_crore=10.0,
        stamp_duty_pct=0.00003,
        gst_pct=0.18
    )
    
    tax_config = TaxConfig(
        rate=0.30,
        min_profitability_multiplier=1.5
    )
    
    return TaxAwarePnLTracker(costs_config, tax_config)


@pytest.fixture
def sample_strategy():
    """Create sample iron condor strategy"""
    expiry_date = date.today() + timedelta(days=20)
    expiry_datetime = datetime.combine(expiry_date, datetime.min.time())
    
    legs = [
        OptionLeg(
            strike=21500.0,
            option_type="CE",
            expiry=expiry_datetime,
            action="SELL",
            quantity=50,
            premium=100.0,
            greeks=Greeks(delta=0.20, gamma=0.01, theta=-10.0, vega=5.0),
            instrument_key="NSE_FO|NIFTY_21500_CE"
        ),
        OptionLeg(
            strike=22000.0,
            option_type="CE",
            expiry=expiry_datetime,
            action="BUY",
            quantity=50,
            premium=50.0,
            greeks=Greeks(delta=0.10, gamma=0.005, theta=-5.0, vega=3.0),
            instrument_key="NSE_FO|NIFTY_22000_CE"
        ),
        OptionLeg(
            strike=21000.0,
            option_type="PE",
            expiry=expiry_datetime,
            action="SELL",
            quantity=50,
            premium=100.0,
            greeks=Greeks(delta=-0.20, gamma=0.01, theta=-10.0, vega=5.0),
            instrument_key="NSE_FO|NIFTY_21000_PE"
        ),
        OptionLeg(
            strike=20500.0,
            option_type="PE",
            expiry=expiry_datetime,
            action="BUY",
            quantity=50,
            premium=50.0,
            greeks=Greeks(delta=-0.10, gamma=0.005, theta=-5.0, vega=3.0),
            instrument_key="NSE_FO|NIFTY_20500_PE"
        ),
    ]
    
    return OptionStrategy(
        strategy_type=StrategyType.IRON_CONDOR,
        legs=legs,
        underlying="NIFTY",
        underlying_price=21250.0,
        regime=Regime.LOW_VOL_SELL,
        max_loss=5000.0,
        max_profit=10000.0,
        net_credit_debit=10000.0,
        portfolio_greeks=Greeks(delta=0.0, gamma=0.03, theta=-30.0, vega=16.0),
        created_at=datetime.now(),
        expiry_date=expiry_datetime,
        days_to_expiry=20
    )


def test_complete_pnl_ledger_flow(
    position_manager,
    pnl_tracker,
    sample_strategy,
    temp_ledger_path
):
    """Test complete flow: open → MTM → close → P&L → ledger"""
    
    # Create trade ledger
    ledger = TradeLedger(temp_ledger_path)
    
    # 1. Open position
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    
    assert position.is_open()
    assert position.unrealized_pnl == 0.0
    
    # Write position open to ledger
    ledger.write_position_open(position)
    
    # 2. Update MTM (simulate profitable scenario)
    current_chain = pd.DataFrame([
        {
            'strike': 21500.0,
            'option_type': 'CE',
            'premium': 60.0,  # Down from 100
            'iv': 14.0,
            'delta': 0.15,
            'gamma': 0.008,
            'theta': -8.0,
            'vega': 4.0
        },
        {
            'strike': 22000.0,
            'option_type': 'CE',
            'premium': 30.0,  # Down from 50
            'iv': 13.0,
            'delta': 0.08,
            'gamma': 0.004,
            'theta': -4.0,
            'vega': 2.5
        },
        {
            'strike': 21000.0,
            'option_type': 'PE',
            'premium': 60.0,  # Down from 100
            'iv': 14.0,
            'delta': -0.15,
            'gamma': 0.008,
            'theta': -8.0,
            'vega': 4.0
        },
        {
            'strike': 20500.0,
            'option_type': 'PE',
            'premium': 30.0,  # Down from 50
            'iv': 13.0,
            'delta': -0.08,
            'gamma': 0.004,
            'theta': -4.0,
            'vega': 2.5
        },
    ])
    
    current_time = entry_time + timedelta(days=5)
    updated_position = position_manager.update_position_mtm(
        position, current_chain, current_time
    )
    
    # Verify MTM calculation
    # SELL legs: (100-60)*50 + (100-60)*50 = 4000 profit
    # BUY legs: (30-50)*50 + (30-50)*50 = -2000 loss
    # Net: 4000 - 2000 = 2000 profit
    assert updated_position.unrealized_pnl == 2000.0
    assert updated_position.days_held == 5
    
    # 3. Close position
    exit_time = current_time
    closed_position = position_manager.close_position(
        updated_position,
        exit_time,
        "profit_target"
    )
    
    assert not closed_position.is_open()
    assert closed_position.realized_pnl == 2000.0
    assert closed_position.exit_reason == "profit_target"
    
    # 4. Calculate P&L with costs and tax
    # Note: Position already has correct realized_pnl, just need to add costs and tax
    gross_pnl = closed_position.realized_pnl
    costs = pnl_tracker.calculate_costs(closed_position.legs)
    tax = pnl_tracker.calculate_tax(gross_pnl)
    net_pnl = pnl_tracker.calculate_net_pnl(gross_pnl, costs, tax)
    
    # Verify P&L calculation
    assert gross_pnl == 2000.0
    assert costs.total > 0  # Should have costs
    assert tax > 0  # Should have tax (30% of profit)
    assert net_pnl < gross_pnl  # Net < Gross after costs/tax
    
    # Create TradePnL object
    from src.options.tax_aware_pnl_tracker import TradePnL
    trade_pnl = TradePnL(
        gross_pnl=gross_pnl,
        costs=costs,
        tax=tax,
        net_pnl=net_pnl
    )
    
    # 5. Write position close to ledger
    ledger.write_position_close(closed_position, trade_pnl)
    
    # 6. Verify ledger integrity
    assert ledger.verify_immutability()
    
    # 7. Read back from ledger
    ledger_df = ledger.read_all()
    assert len(ledger_df) == 2  # One open + one close record
    
    # Get the close record (action == 'close')
    close_records = ledger_df[ledger_df['action'] == 'close']
    assert len(close_records) == 1
    
    trade = close_records.iloc[0]
    assert trade['trade_id'] == closed_position.position_id
    assert trade['strategy_type'] == 'iron_condor'
    assert trade['action'] == 'close'
    assert trade['gross_pnl'] == 2000.0
    assert trade['net_pnl'] == net_pnl
    assert trade['exit_reason'] == 'profit_target'
    
    # 8. Verify summary
    summary = ledger.get_summary()
    # Just verify the summary exists and has basic info
    assert 'closed_trades' in summary
    assert summary['closed_trades'] == 1


def test_loss_scenario_pnl_ledger(
    position_manager,
    pnl_tracker,
    sample_strategy,
    temp_ledger_path
):
    """Test P&L and ledger with loss scenario"""
    
    ledger = TradeLedger(temp_ledger_path)
    
    # Open position
    entry_time = datetime.now()
    position = position_manager.open_position(sample_strategy, entry_time)
    ledger.write_position_open(position)
    
    # Simulate loss scenario (premiums increase)
    current_chain = pd.DataFrame([
        {
            'strike': 21500.0,
            'option_type': 'CE',
            'premium': 120.0,  # Up from 100
            'iv': 16.0,
            'delta': 0.25,
            'gamma': 0.012,
            'theta': -12.0,
            'vega': 6.0
        },
        {
            'strike': 22000.0,
            'option_type': 'CE',
            'premium': 60.0,  # Up from 50
            'iv': 15.0,
            'delta': 0.12,
            'gamma': 0.006,
            'theta': -6.0,
            'vega': 3.5
        },
        {
            'strike': 21000.0,
            'option_type': 'PE',
            'premium': 120.0,  # Up from 100
            'iv': 16.0,
            'delta': -0.25,
            'gamma': 0.012,
            'theta': -12.0,
            'vega': 6.0
        },
        {
            'strike': 20500.0,
            'option_type': 'PE',
            'premium': 60.0,  # Up from 50
            'iv': 15.0,
            'delta': -0.12,
            'gamma': 0.006,
            'theta': -6.0,
            'vega': 3.5
        },
    ])
    
    current_time = entry_time + timedelta(days=3)
    updated_position = position_manager.update_position_mtm(
        position, current_chain, current_time
    )
    
    # Verify loss
    # SELL legs: (100-120)*50 + (100-120)*50 = -2000 loss
    # BUY legs: (60-50)*50 + (60-50)*50 = 1000 profit
    # Net: -2000 + 1000 = -1000 loss
    assert updated_position.unrealized_pnl == -1000.0
    
    # Close position
    exit_time = current_time
    closed_position = position_manager.close_position(
        updated_position,
        exit_time,
        "stop_loss"
    )
    
    assert closed_position.realized_pnl == -1000.0
    
    # Calculate P&L (no tax on losses)
    gross_pnl = closed_position.realized_pnl
    costs = pnl_tracker.calculate_costs(closed_position.legs)
    tax = pnl_tracker.calculate_tax(gross_pnl)
    net_pnl = pnl_tracker.calculate_net_pnl(gross_pnl, costs, tax)
    
    assert gross_pnl == -1000.0
    assert tax == 0.0  # No tax on losses
    assert net_pnl < gross_pnl  # Net worse due to costs
    
    # Create TradePnL object
    from src.options.tax_aware_pnl_tracker import TradePnL
    trade_pnl = TradePnL(
        gross_pnl=gross_pnl,
        costs=costs,
        tax=tax,
        net_pnl=net_pnl
    )
    
    # Write to ledger
    ledger.write_position_close(closed_position, trade_pnl)
    
    # Verify ledger
    ledger_df = ledger.read_all()
    assert len(ledger_df) == 2  # One open + one close record
    
    # Get the close record (action == 'close')
    close_records = ledger_df[ledger_df['action'] == 'close']
    assert len(close_records) == 1
    
    trade = close_records.iloc[0]
    assert trade['gross_pnl'] == -1000.0
    assert trade['tax'] == 0.0
    assert trade['exit_reason'] == 'stop_loss'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
