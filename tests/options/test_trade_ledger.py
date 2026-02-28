"""
Tests for Trade Ledger

Verifies immutable append-only behavior and data integrity.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, date
import pandas as pd

from src.options.trade_ledger import TradeLedger, LedgerEntry
from src.options.position_manager import Position, PositionLeg, Greeks
from src.options.regime_detector import Regime
from src.options.tax_aware_pnl_tracker import TradePnL, TradeCosts


@pytest.fixture
def temp_ledger_path():
    """Create temporary ledger path"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_ledger.parquet"


@pytest.fixture
def sample_position():
    """Create sample position for testing"""
    legs = [
        PositionLeg(
            symbol="NIFTY_21500_CE",
            strike=21500.0,
            option_type="call",
            action="sell",
            quantity=50,
            entry_premium=100.0,
            current_premium=100.0,
            entry_iv=15.0,
            current_iv=15.0,
            delta=0.20,
            gamma=0.01,
            theta=-10.0,
            vega=5.0
        ),
        PositionLeg(
            symbol="NIFTY_21500_PE",
            strike=21500.0,
            option_type="put",
            action="sell",
            quantity=50,
            entry_premium=100.0,
            current_premium=100.0,
            entry_iv=15.0,
            current_iv=15.0,
            delta=-0.20,
            gamma=0.01,
            theta=-10.0,
            vega=5.0
        ),
    ]
    
    position = Position(
        position_id="POS_20240115_100000_iron_condor",
        strategy_type="iron_condor",
        regime_at_entry=Regime.LOW_VOL_SELL,
        legs=legs,
        entry_time=datetime(2024, 1, 15, 10, 0, 0),
        expiry=date(2024, 2, 1),
        max_loss=5000.0,
        max_profit=10000.0,
        entry_credit_debit=10000.0,
        current_value=10000.0,
        unrealized_pnl=0.0,
        days_held=0,
        greeks=Greeks(delta=0.0, gamma=0.02, theta=-20.0, vega=10.0),
        entry_greeks=Greeks(delta=0.0, gamma=0.02, theta=-20.0, vega=10.0)
    )
    
    return position


@pytest.fixture
def sample_trade_pnl():
    """Create sample trade P&L for testing"""
    costs = TradeCosts(
        brokerage=80.0,
        exchange_charges=50.0,
        sebi_charges=1.0,
        stamp_duty=3.0,
        gst=23.4,
        total=157.4
    )
    
    return TradePnL(
        gross_pnl=5500.0,
        costs=costs,
        tax=1650.0,  # 30% of 5500
        net_pnl=3692.6  # 5500 - 157.4 - 1650
    )


def test_ledger_initialization(temp_ledger_path):
    """Test ledger creates empty file on initialization"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    assert temp_ledger_path.exists()
    
    df = ledger.read_all()
    assert len(df) == 0
    assert list(df.columns) == [
        'trade_id', 'timestamp', 'action', 'strategy_type', 'regime_at_entry',
        'underlying', 'expiry', 'legs', 'entry_credit_debit', 'exit_value',
        'gross_pnl', 'costs', 'tax', 'net_pnl', 'days_held', 'exit_reason',
        'greeks_at_entry', 'greeks_at_exit'
    ]


def test_write_position_open(temp_ledger_path, sample_position):
    """Test writing position open to ledger"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Write position open
    ledger.write_position_open(sample_position)
    
    # Verify entry
    df = ledger.read_all()
    assert len(df) == 1
    
    entry = df.iloc[0]
    assert entry['trade_id'] == sample_position.position_id
    assert entry['action'] == 'open'
    assert entry['strategy_type'] == 'iron_condor'
    assert entry['regime_at_entry'] == 'low_vol_sell'
    assert entry['entry_credit_debit'] == 10000.0
    assert pd.isna(entry['exit_value'])
    assert pd.isna(entry['net_pnl'])


def test_write_position_close(temp_ledger_path, sample_position, sample_trade_pnl):
    """Test writing position close to ledger"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Write position open first
    ledger.write_position_open(sample_position)
    
    # Close position
    sample_position.exit_time = datetime(2024, 1, 20, 15, 30, 0)
    sample_position.exit_reason = "profit_target"
    sample_position.current_value = 15500.0
    sample_position.realized_pnl = 5500.0
    sample_position.days_held = 5
    
    # Write position close
    ledger.write_position_close(sample_position, sample_trade_pnl)
    
    # Verify entries
    df = ledger.read_all()
    assert len(df) == 2
    
    # Check open entry
    open_entry = df[df['action'] == 'open'].iloc[0]
    assert open_entry['trade_id'] == sample_position.position_id
    
    # Check close entry
    close_entry = df[df['action'] == 'close'].iloc[0]
    assert close_entry['trade_id'] == sample_position.position_id
    assert close_entry['exit_value'] == 15500.0
    assert close_entry['gross_pnl'] == 5500.0
    assert close_entry['costs'] == 157.4
    assert close_entry['tax'] == 1650.0
    assert close_entry['net_pnl'] == 3692.6
    assert close_entry['days_held'] == 5
    assert close_entry['exit_reason'] == 'profit_target'


def test_ledger_immutability(temp_ledger_path, sample_position):
    """Test that ledger is append-only (record count never decreases)"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Initial count
    assert ledger.get_trade_count() == 0
    assert ledger.verify_immutability()
    
    # Add entry
    ledger.write_position_open(sample_position)
    assert ledger.get_trade_count() == 1
    assert ledger.verify_immutability()
    
    # Add another entry
    sample_position.position_id = "POS_20240116_100000_iron_condor"
    ledger.write_position_open(sample_position)
    assert ledger.get_trade_count() == 2
    assert ledger.verify_immutability()


def test_read_by_trade_id(temp_ledger_path, sample_position, sample_trade_pnl):
    """Test reading entries by trade ID"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Write open and close
    ledger.write_position_open(sample_position)
    
    sample_position.exit_time = datetime(2024, 1, 20, 15, 30, 0)
    sample_position.exit_reason = "profit_target"
    sample_position.realized_pnl = 5500.0
    
    ledger.write_position_close(sample_position, sample_trade_pnl)
    
    # Read by trade ID
    df = ledger.read_by_trade_id(sample_position.position_id)
    assert len(df) == 2
    assert df['action'].tolist() == ['open', 'close']


def test_read_closed_trades(temp_ledger_path, sample_position, sample_trade_pnl):
    """Test reading only closed trades"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Write first position (open only)
    ledger.write_position_open(sample_position)
    
    # Write second position (open + close)
    sample_position.position_id = "POS_20240116_100000_iron_condor"
    ledger.write_position_open(sample_position)
    
    sample_position.exit_time = datetime(2024, 1, 20, 15, 30, 0)
    sample_position.exit_reason = "profit_target"
    sample_position.realized_pnl = 5500.0
    
    ledger.write_position_close(sample_position, sample_trade_pnl)
    
    # Read closed trades
    closed_df = ledger.read_closed_trades()
    assert len(closed_df) == 1
    assert closed_df.iloc[0]['action'] == 'close'


def test_get_summary(temp_ledger_path, sample_position, sample_trade_pnl):
    """Test ledger summary statistics"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Empty ledger
    summary = ledger.get_summary()
    assert summary['total_entries'] == 0
    assert summary['closed_trades'] == 0
    
    # Add winning trade
    ledger.write_position_open(sample_position)
    sample_position.exit_time = datetime(2024, 1, 20, 15, 30, 0)
    sample_position.exit_reason = "profit_target"
    sample_position.realized_pnl = 5500.0
    sample_position.days_held = 5
    ledger.write_position_close(sample_position, sample_trade_pnl)
    
    # Add losing trade
    sample_position.position_id = "POS_20240117_100000_iron_condor"
    sample_position.entry_time = datetime(2024, 1, 17, 10, 0, 0)
    ledger.write_position_open(sample_position)
    
    sample_position.exit_time = datetime(2024, 1, 22, 15, 30, 0)
    sample_position.exit_reason = "stop_loss"
    sample_position.realized_pnl = -2000.0
    sample_position.days_held = 5
    
    losing_pnl = TradePnL(
        gross_pnl=-2000.0,
        costs=sample_trade_pnl.costs,
        tax=0.0,  # No tax on losses
        net_pnl=-2157.4
    )
    ledger.write_position_close(sample_position, losing_pnl)
    
    # Check summary
    summary = ledger.get_summary()
    assert summary['total_entries'] == 4  # 2 open + 2 close
    assert summary['closed_trades'] == 2
    assert summary['winning_trades'] == 1
    assert summary['losing_trades'] == 1
    assert summary['win_rate'] == 0.5
    assert summary['total_net_pnl'] == pytest.approx(3692.6 - 2157.4)
    assert summary['avg_days_held'] == 5.0


def test_cannot_close_open_position(temp_ledger_path, sample_position, sample_trade_pnl):
    """Test that closing an open position raises error"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Try to close without setting exit_time
    with pytest.raises(ValueError, match="Cannot write close record for open position"):
        ledger.write_position_close(sample_position, sample_trade_pnl)


def test_read_by_date_range(temp_ledger_path, sample_position):
    """Test reading entries by date range"""
    ledger = TradeLedger(str(temp_ledger_path))
    
    # Write entries on different dates
    sample_position.entry_time = datetime(2024, 1, 15, 10, 0, 0)
    ledger.write_position_open(sample_position)
    
    sample_position.position_id = "POS_20240120_100000_iron_condor"
    sample_position.entry_time = datetime(2024, 1, 20, 10, 0, 0)
    ledger.write_position_open(sample_position)
    
    sample_position.position_id = "POS_20240125_100000_iron_condor"
    sample_position.entry_time = datetime(2024, 1, 25, 10, 0, 0)
    ledger.write_position_open(sample_position)
    
    # Read date range
    df = ledger.read_by_date_range(
        datetime(2024, 1, 18, 0, 0, 0),
        datetime(2024, 1, 22, 23, 59, 59)
    )
    
    assert len(df) == 1
    assert df.iloc[0]['timestamp'] == pd.Timestamp(datetime(2024, 1, 20, 10, 0, 0))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
