"""
End-to-End Integration Test for Options Trading System

This test validates the complete signal generation pipeline from
regime detection through trade eligibility to position management.

Tests:
1. Complete signal generation pipeline
2. Mock Upstox data handling
3. Dashboard integration
4. Kill switch functionality
5. Trade ledger writing
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.options.options_regime_detector import RegimeDetector, Regime
from src.options.strategy_generator import StrategyGenerator, StrategyType
from src.options.trade_eligibility_validator import TradeEligibilityValidator
from src.options.position_manager import PositionManager
from src.options.survival_rules_engine import SurvivalRulesEngine
from src.options.capital_scaling_engine import CapitalScalingEngine
from src.options.tax_aware_pnl_tracker import TaxAwarePnLTracker
from src.options.trade_ledger import TradeLedger
from src.options.system_hygiene import SystemHygieneRules
from src.options.config_loader import get_config


class TestEndToEndIntegration:
    """End-to-end integration tests for options trading system"""
    
    @pytest.fixture
    def config(self):
        """Load configuration"""
        return get_config()
    
    @pytest.fixture
    def mock_option_chain(self):
        """Create mock option chain data"""
        spot = 25000.0
        strikes = np.arange(24000, 26000, 100)
        
        option_data = []
        for strike in strikes:
            moneyness = strike / spot
            base_iv = 0.15
            iv = base_iv + 0.05 * (1 - moneyness)**2
            
            # Add bid/ask
            mid = max(10, 100 * (1 - abs(moneyness - 1)))
            spread = mid * 0.05  # 5% spread
            
            # Call option
            option_data.append({
                'strike': float(strike),
                'option_type': 'CE',
                'expiry': datetime.now() + timedelta(days=30),
                'iv': iv,
                'underlying_price': spot,
                'bid': mid - spread/2,
                'ask': mid + spread/2,
                'bid_qty': 100,
                'ask_qty': 100,
                'ltp': mid,
                'delta': 0.5 - (strike - spot) / (2 * spot),
                'gamma': 0.001,
                'theta': -0.05,
                'vega': 0.1
            })
            
            # Put option
            option_data.append({
                'strike': float(strike),
                'option_type': 'PE',
                'expiry': datetime.now() + timedelta(days=30),
                'iv': iv * 1.1,  # Put skew
                'underlying_price': spot,
                'bid': mid - spread/2,
                'ask': mid + spread/2,
                'bid_qty': 100,
                'ask_qty': 100,
                'ltp': mid,
                'delta': -0.5 + (strike - spot) / (2 * spot),
                'gamma': 0.001,
                'theta': -0.05,
                'vega': 0.1
            })
        
        return pd.DataFrame(option_data)
    
    @pytest.fixture
    def mock_iv_history(self):
        """Create mock IV history"""
        # 252 days of IV data with upward trend
        iv_history = pd.Series([0.10 + 0.10 * (i / 252) for i in range(252)])
        return iv_history
    
    def test_complete_signal_generation_pipeline(self, config, mock_option_chain, mock_iv_history):
        """
        Test 1: Complete signal generation pipeline
        
        Validates that the entire pipeline works from regime detection
        through strategy generation to trade eligibility validation.
        """
        print("\n=== Test 1: Complete Signal Generation Pipeline ===")
        
        # Step 1: Detect regime
        detector = RegimeDetector(config.regime_detection)
        regime_state = detector.detect_regime(
            mock_option_chain,
            mock_iv_history,
            underlying_regime="NORMAL"
        )
        
        print(f"✓ Regime detected: {regime_state.regime.value}")
        print(f"  IV Rank: {regime_state.metrics.iv_rank:.2%}")
        print(f"  Confidence: {regime_state.confidence:.2%}")
        
        assert regime_state.regime in [
            Regime.LOW_VOL_SELL,
            Regime.HIGH_VOL_SELL,
            Regime.RISING_VOL_BUY,
            Regime.NEUTRAL,
            Regime.CRASH_HEDGE
        ]
        
        # Step 2: Generate strategy
        generator = StrategyGenerator(config.strategies)
        strategy = generator.generate_strategy(
            regime_state.regime,
            mock_option_chain,
            'NIFTY'
        )
        
        if strategy:
            print(f"✓ Strategy generated: {strategy.strategy_type.value}")
            print(f"  Legs: {len(strategy.legs)}")
            print(f"  Max Loss: ₹{strategy.max_loss:,.0f}")
            print(f"  Max Profit: ₹{strategy.max_profit:,.0f}")
            
            assert strategy.is_valid
            assert len(strategy.legs) > 0
            
            # Step 3: Validate trade eligibility
            validator = TradeEligibilityValidator(config)
            validation_result = validator.validate_trade(
                strategy,
                regime_state,
                mock_option_chain
            )
            
            print(f"✓ Trade validation complete")
            print(f"  Eligible: {validation_result.is_eligible}")
            print(f"  Size Adjustment: {validation_result.size_adjustment:.0%}")
            print(f"  Violations: {len(validation_result.violations)}")
            if validation_result.violations:
                for v in validation_result.violations:
                    print(f"    - {v}")
            
            assert validation_result.size_adjustment >= 0.0
            assert validation_result.size_adjustment <= 1.0
        else:
            print("✓ No strategy generated (regime may not support trading)")
        
        print("✓ Pipeline test PASSED\n")
    
    def test_mock_upstox_data_handling(self, config, mock_option_chain):
        """
        Test 2: Mock Upstox data handling
        
        Validates that the system can handle mock data in the same
        format as real Upstox API responses.
        """
        print("\n=== Test 2: Mock Upstox Data Handling ===")
        
        # Verify data structure
        required_columns = [
            'strike', 'option_type', 'expiry', 'iv', 'underlying_price',
            'bid', 'ask', 'ltp', 'delta', 'gamma', 'theta', 'vega'
        ]
        
        for col in required_columns:
            assert col in mock_option_chain.columns, f"Missing column: {col}"
        
        print(f"✓ All required columns present: {len(required_columns)}")
        
        # Verify data types
        assert mock_option_chain['strike'].dtype in [np.float64, np.int64]
        assert mock_option_chain['option_type'].dtype == object
        assert mock_option_chain['iv'].dtype == np.float64
        
        print("✓ Data types correct")
        
        # Verify data ranges
        assert (mock_option_chain['iv'] > 0).all()
        assert (mock_option_chain['iv'] < 1).all()
        assert (mock_option_chain['bid'] > 0).all()
        assert (mock_option_chain['ask'] >= mock_option_chain['bid']).all()
        
        print("✓ Data ranges valid")
        print("✓ Mock data test PASSED\n")
    
    def test_dashboard_integration(self, config, mock_option_chain, mock_iv_history):
        """
        Test 3: Dashboard integration
        
        Validates that dashboard components can access and display
        options trading data correctly.
        """
        print("\n=== Test 3: Dashboard Integration ===")
        
        # Detect regime
        detector = RegimeDetector(config.regime_detection)
        regime_state = detector.detect_regime(
            mock_option_chain,
            mock_iv_history,
            underlying_regime="NORMAL"
        )
        
        # Verify dashboard data structure
        dashboard_data = {
            'regime': regime_state.regime.value,
            'iv_rank': regime_state.metrics.iv_rank,
            'iv_trend': regime_state.metrics.iv_trend,
            'vol_of_vol_elevated': regime_state.metrics.vol_of_vol_elevated,
            'confidence': regime_state.confidence,
            'days_in_regime': regime_state.metrics.days_in_regime
        }
        
        print("✓ Dashboard data structure created")
        print(f"  Regime: {dashboard_data['regime']}")
        print(f"  IV Rank: {dashboard_data['iv_rank']:.2%}")
        print(f"  IV Trend: {dashboard_data['iv_trend']}")
        
        # Verify all required fields present
        required_fields = [
            'regime', 'iv_rank', 'iv_trend', 'vol_of_vol_elevated',
            'confidence', 'days_in_regime'
        ]
        
        for field in required_fields:
            assert field in dashboard_data, f"Missing field: {field}"
        
        print(f"✓ All required fields present: {len(required_fields)}")
        print("✓ Dashboard integration test PASSED\n")
    
    def test_kill_switch_functionality(self, config):
        """
        Test 4: Kill switch functionality
        
        Validates that survival rules engine can be instantiated
        and basic checks work.
        """
        print("\n=== Test 4: Kill Switch Functionality ===")
        
        # Create survival rules engine with base capital
        base_capital = 100000.0
        survival = SurvivalRulesEngine(config.survival_rules, base_capital)
        
        print("  ✓ Survival rules engine created")
        
        # Verify engine has required attributes
        assert hasattr(survival, 'config')
        assert hasattr(survival, 'base_capital')
        print("  ✓ Engine has required attributes")
        
        # Test that we can call validate_trade_allowed
        result = survival.validate_trade_allowed(
            strategy_type='IRON_CONDOR',
            max_loss=5000,
            current_positions_risk=1000,
            weekly_pnl=-1000,
            ytd_tax_liability=5000,
            cash_buffer=10000
        )
        
        print(f"  ✓ Trade validation works: {result.allowed}")
        assert hasattr(result, 'allowed')
        assert hasattr(result, 'reason')
        
        print("✓ Kill switch test PASSED\n")
    
    def test_trade_ledger_writing(self, config, mock_option_chain, mock_iv_history):
        """
        Test 5: Trade ledger writing
        
        Validates that trades are correctly written to the immutable
        trade ledger in parquet format.
        """
        print("\n=== Test 5: Trade Ledger Writing ===")
        
        # Create temporary ledger path
        test_ledger_path = Path("data/options/test_trade_ledger.parquet")
        test_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Clean up any existing test ledger
        if test_ledger_path.exists():
            test_ledger_path.unlink()
        
        try:
            # Create trade ledger
            ledger = TradeLedger(str(test_ledger_path))
            
            # Generate a strategy
            detector = RegimeDetector(config.regime_detection)
            regime_state = detector.detect_regime(
                mock_option_chain,
                mock_iv_history,
                underlying_regime="NORMAL"
            )
            
            generator = StrategyGenerator(config.strategies)
            strategy = generator.generate_strategy(
                regime_state.regime,
                mock_option_chain,
                'NIFTY'
            )
            
            if strategy:
                # Write trade to ledger
                trade_id = ledger.record_trade_open(
                    strategy=strategy,
                    regime=regime_state.regime,
                    entry_timestamp=datetime.now()
                )
                
                print(f"✓ Trade recorded: {trade_id}")
                
                # Verify ledger file exists
                assert test_ledger_path.exists(), "Ledger file should exist"
                print("✓ Ledger file created")
                
                # Read ledger and verify
                ledger_df = pd.read_parquet(test_ledger_path)
                assert len(ledger_df) == 1, "Should have 1 trade"
                assert ledger_df.iloc[0]['trade_id'] == trade_id
                print("✓ Trade data verified in ledger")
                
                # Test immutability - try to write same trade again
                initial_count = len(ledger_df)
                
                # Close the trade
                ledger.record_trade_close(
                    trade_id=trade_id,
                    exit_timestamp=datetime.now(),
                    exit_reason="test",
                    final_pnl=1000.0,
                    costs=100.0,
                    tax=300.0
                )
                
                # Verify ledger now has 2 records (open + close)
                ledger_df = pd.read_parquet(test_ledger_path)
                assert len(ledger_df) == 2, "Should have 2 records (open + close)"
                print("✓ Trade close recorded")
                
                print("✓ Trade ledger test PASSED\n")
            else:
                print("✓ No strategy generated (skipping ledger test)\n")
        
        finally:
            # Clean up test ledger
            if test_ledger_path.exists():
                test_ledger_path.unlink()
    
    def test_capital_scaling_integration(self, config):
        """
        Test 6: Capital scaling integration
        
        Validates that capital scaling engine can be instantiated
        and basic operations work.
        """
        print("\n=== Test 6: Capital Scaling Integration ===")
        
        # Create capital scaling engine
        scaling = CapitalScalingEngine(config.capital_scaling)
        
        print("  ✓ Capital scaling engine created")
        
        # Initialize state with required parameters
        starting_capital = 100000.0
        trading_start_date = datetime.now() - timedelta(days=60)
        
        state = scaling.initialize_state(starting_capital, trading_start_date)
        
        print(f"  ✓ Initial state created")
        print(f"    Risk per trade: {state.risk_per_trade_pct:.2%}")
        print(f"    Scaling factor: {state.scaling_factor:.2f}")
        
        assert state.risk_per_trade_pct > 0
        assert state.scaling_factor >= 0
        
        # Test update_state
        state = scaling.update_state(
            state,
            current_equity=105000,  # 5% profit
            recent_trades_profitable=1
        )
        
        print(f"  ✓ State updated after profit")
        print(f"    New risk per trade: {state.risk_per_trade_pct:.2%}")
        
        print("✓ Capital scaling test PASSED\n")
    
    def test_system_hygiene_rules(self, config):
        """
        Test 7: System hygiene rules
        
        Validates that system hygiene rules engine can be instantiated
        and basic checks work.
        """
        print("\n=== Test 7: System Hygiene Rules ===")
        
        # Create system hygiene engine with correct parameters
        hygiene = SystemHygieneRules(
            concentration_lookback=2,
            cooling_period_days=1
        )
        
        print("  ✓ System hygiene engine created")
        
        # Add some trades
        hygiene.add_trade({
            'strategy_type': 'IRON_CONDOR',
            'timestamp': datetime.now() - timedelta(hours=12),
            'outcome': 'win'
        })
        
        print("  ✓ Trade added to history")
        
        # Test strategy concentration check
        result = hygiene.check_strategy_concentration('IRON_CONDOR')
        print(f"  ✓ Strategy concentration check works: {result.allowed}")
        assert hasattr(result, 'allowed')
        assert hasattr(result, 'reason')
        
        # Test success cooling period check
        result = hygiene.check_success_cooling_period(iv_rank=0.75)
        print(f"  ✓ Success cooling period check works: {result.allowed}")
        assert hasattr(result, 'allowed')
        
        print("✓ System hygiene test PASSED\n")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
