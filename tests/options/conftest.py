"""
Pytest fixtures for options property-based tests

Provides properly configured instances of all options system components
for use in property-based testing.
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Mock config classes for testing
@dataclass
class MockSurvivalRulesConfig:
    """Mock survival rules config for testing"""
    weekly_loss_limit_pct: float = 0.02
    trauma_loss_threshold_pct: float = 0.80
    trauma_cooldown_weeks: int = 2
    portfolio_risk_cap_pct: float = 0.02
    max_trades_per_week: int = 2
    no_trade_times: List[Dict[str, str]] = None
    no_trade_days: List[str] = None
    
    def __post_init__(self):
        if self.no_trade_times is None:
            self.no_trade_times = [
                {"day": "Monday", "start": "09:15", "end": "10:00"}
            ]
        if self.no_trade_days is None:
            self.no_trade_days = ["Tuesday"]


@dataclass
class MockRegimeConfig:
    """Mock regime config for testing"""
    iv_rank_lookback_days: int = 252
    vol_of_vol_threshold: float = 1.5
    regime_persistence_days: int = 2
    low_vol_sell_iv_rank: float = 0.70
    high_vol_sell_iv_rank: float = 0.80
    rising_vol_buy_iv_rank: float = 0.30


@dataclass
class MockCapitalScalingConfig:
    """Mock capital scaling config for testing"""
    base_capital: float = 500000
    base_risk_pct: float = 0.010
    max_risk_pct: float = 0.015
    profit_milestone_pct: float = 0.08
    profit_scaling_increment: float = 0.0025
    drawdown_threshold_1: float = 0.03
    drawdown_threshold_2: float = 0.05
    drawdown_descaling_1: float = 0.0025
    drawdown_descaling_2: float = 0.005
    min_weeks_before_scaling: int = 8
    recovery_profitable_trades: int = 2


@dataclass
class MockCostsConfig:
    """Mock costs config for testing"""
    brokerage_per_leg: float = 20.0
    exchange_charges_pct: float = 0.0005
    sebi_charges_per_crore: float = 10.0
    stamp_duty_pct: float = 0.00003
    gst_pct: float = 0.18


@dataclass
class MockTaxConfig:
    """Mock tax config for testing"""
    rate: float = 0.30
    min_profitability_multiplier: float = 1.5


@dataclass
class MockEligibilityConfig:
    """Mock eligibility config for testing"""
    max_bid_ask_spread_pct: float = 0.08
    min_liquidity_depth_multiplier: float = 2.0
    min_days_to_expiry: int = 5
    event_buffer_days: int = 2
    late_cycle_days: int = 10
    late_cycle_size_reduction: float = 0.5


@dataclass
class MockStrategyConfig:
    """Mock strategy config for testing"""
    lot_sizes: Dict[str, int] = None
    
    def __post_init__(self):
        if self.lot_sizes is None:
            self.lot_sizes = {"NIFTY": 50, "BANKNIFTY": 15}


# Fixtures
@pytest.fixture
def survival_config():
    """Provide survival rules config for testing"""
    return MockSurvivalRulesConfig()


@pytest.fixture
def regime_config():
    """Provide regime detection config for testing"""
    return MockRegimeConfig()


@pytest.fixture
def capital_scaling_config():
    """Provide capital scaling config for testing"""
    return MockCapitalScalingConfig()


@pytest.fixture
def costs_config():
    """Provide costs config for testing"""
    return MockCostsConfig()


@pytest.fixture
def tax_config():
    """Provide tax config for testing"""
    return MockTaxConfig()


@pytest.fixture
def eligibility_config():
    """Provide eligibility config for testing"""
    return MockEligibilityConfig()


@pytest.fixture
def strategy_config():
    """Provide strategy config for testing"""
    return MockStrategyConfig()


@pytest.fixture
def base_capital():
    """Provide base capital for testing"""
    return 500000.0


# Component fixtures
@pytest.fixture
def survival_engine(survival_config, base_capital):
    """Provide configured survival rules engine"""
    from src.options.survival_rules_engine import SurvivalRulesEngine
    return SurvivalRulesEngine(config=survival_config, base_capital=base_capital)


@pytest.fixture
def regime_detector(regime_config):
    """Provide configured regime detector"""
    from src.options.options_regime_detector import RegimeDetector
    return RegimeDetector(config=regime_config)


@pytest.fixture
def capital_scaling_engine(capital_scaling_config):
    """Provide configured capital scaling engine"""
    from src.options.capital_scaling_engine import CapitalScalingEngine
    return CapitalScalingEngine(config=capital_scaling_config)


@pytest.fixture
def pnl_tracker(costs_config, tax_config):
    """Provide configured P&L tracker"""
    from src.options.tax_aware_pnl_tracker import TaxAwarePnLTracker
    return TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)


@pytest.fixture
def eligibility_validator(eligibility_config):
    """Provide configured eligibility validator"""
    from src.options.trade_eligibility_validator import TradeEligibilityValidator
    return TradeEligibilityValidator(config=eligibility_config)


@pytest.fixture
def strategy_generator(strategy_config):
    """Provide configured strategy generator"""
    from src.options.strategy_generator import StrategyGenerator
    return StrategyGenerator(config=strategy_config)


@pytest.fixture
def position_manager():
    """Provide position manager"""
    from src.options.position_manager import PositionManager
    return PositionManager()


@pytest.fixture
def trade_ledger(tmp_path):
    """Provide trade ledger with temporary path"""
    from src.options.trade_ledger import TradeLedger
    ledger_path = str(tmp_path / "test_ledger.parquet")
    return TradeLedger(ledger_path=ledger_path)


@pytest.fixture
def system_hygiene():
    """Provide system hygiene checker"""
    from src.options.system_hygiene import SystemHygiene
    return SystemHygiene()
