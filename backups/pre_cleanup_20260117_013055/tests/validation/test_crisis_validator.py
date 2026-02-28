#!/usr/bin/env python3
"""
🧪 CRISIS VALIDATOR TESTS
Unit tests for the Crisis Validator component

Tests cover:
- 2008 Financial Crisis validation
- 2020 COVID crash validation  
- 2022 Inflation shock validation
- Pre-crisis positioning analysis
- Emergency protocol activation
- Volatility-based position sizing
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.validation.crisis_validator import CrisisValidator, CrisisType, CrisisMetrics
from hypothesis import given, strategies as st, settings

class TestCrisisValidator:
    """Test suite for Crisis Validator"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.validator = CrisisValidator()
        
        # Create test portfolio data
        self.test_dates = pd.date_range('2007-01-01', '2023-12-31', freq='D')
        np.random.seed(42)
        
        # Simulate realistic portfolio returns
        base_returns = np.random.normal(0.0005, 0.012, len(self.test_dates))
        
        # Add crisis-specific impacts
        returns = base_returns.copy()
        
        # 2008 Crisis impact
        crisis_2008_mask = (
            (self.test_dates >= datetime(2007, 7, 1)) & 
            (self.test_dates <= datetime(2009, 3, 31))
        )
        returns[crisis_2008_mask] = np.random.normal(-0.003, 0.030, crisis_2008_mask.sum())
        
        # 2020 Crisis impact
        crisis_2020_mask = (
            (self.test_dates >= datetime(2020, 2, 1)) & 
            (self.test_dates <= datetime(2020, 5, 31))
        )
        returns[crisis_2020_mask] = np.random.normal(-0.004, 0.035, crisis_2020_mask.sum())
        
        # Build portfolio metrics
        equity = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        
        # Simulate exposure management (lower during crises)
        exposure = np.full(len(self.test_dates), 0.8)
        
        # Reduce exposure before/during 2008 crisis
        pre_2008_mask = (
            (self.test_dates >= datetime(2007, 6, 1)) & 
            (self.test_dates <= datetime(2009, 3, 31))
        )
        exposure[pre_2008_mask] = 0.4  # Reduced exposure
        
        # Reduce exposure before/during 2020 crisis
        pre_2020_mask = (
            (self.test_dates >= datetime(2020, 1, 1)) & 
            (self.test_dates <= datetime(2020, 5, 31))
        )
        exposure[pre_2020_mask] = 0.5  # Reduced exposure
        
        self.portfolio_data = pd.DataFrame({
            'date': self.test_dates,
            'daily_return': returns,
            'equity': equity,
            'drawdown': drawdown,
            'total_exposure': exposure,
            'cash_weight': 1.0 - exposure,
            'volatility': pd.Series(returns).rolling(21).std() * np.sqrt(252),
            'utilities_weight': np.where(pre_2008_mask | pre_2020_mask, 0.2, 0.1),
            'consumer_staples_weight': np.where(pre_2008_mask | pre_2020_mask, 0.15, 0.05),
            'healthcare_weight': np.where(pre_2008_mask | pre_2020_mask, 0.15, 0.05)
        })
    
    def test_crisis_validator_initialization(self):
        """Test crisis validator initializes correctly"""
        
        validator = CrisisValidator()
        
        assert validator.name == "Crisis Validator"
        assert len(validator.crisis_periods) == 3
        assert 'financial_crisis_2008' in validator.crisis_periods
        assert 'covid_crash_2020' in validator.crisis_periods
        assert 'inflation_shock_2022' in validator.crisis_periods
        
        # Check crisis period definitions
        crisis_2008 = validator.crisis_periods['financial_crisis_2008']
        assert crisis_2008['type'] == CrisisType.FINANCIAL_CRISIS
        assert crisis_2008['period'][0] == datetime(2007, 7, 1)
        assert crisis_2008['period'][1] == datetime(2009, 3, 31)
    
    def test_2008_financial_crisis_validation(self):
        """Test 2008 financial crisis validation - Requirements 4.1"""
        
        crisis_period = self.validator.crisis_periods['financial_crisis_2008']['period']
        
        metrics = self.validator.analyze_crisis_performance(
            self.portfolio_data, crisis_period, 'financial_crisis_2008'
        )
        
        # Verify crisis metrics structure
        assert isinstance(metrics, CrisisMetrics)
        assert metrics.crisis_name == 'financial_crisis_2008'
        assert metrics.period == crisis_period
        
        # Check performance metrics
        assert metrics.max_drawdown < 0  # Should have some drawdown
        assert metrics.recovery_time_days > 0
        assert isinstance(metrics.crisis_sharpe, float)
        
        # Check pre-crisis positioning (CRITICAL)
        assert 0 <= metrics.exposure_30d_before <= 1
        assert isinstance(metrics.anticipatory_de_risking, bool)
        assert 0 <= metrics.defensive_positioning_score <= 1
        
        # Check survival metrics
        assert isinstance(metrics.survived_without_intervention, bool)
        assert metrics.maximum_leverage_during_crisis >= 0
        assert 0 <= metrics.cash_reserves_maintained <= 1
        
        print(f"2008 Crisis - Max DD: {metrics.max_drawdown:.1%}, "
              f"Pre-crisis exposure: {metrics.exposure_30d_before:.1%}, "
              f"Anticipatory de-risking: {metrics.anticipatory_de_risking}")
    
    def test_2020_covid_crash_validation(self):
        """Test 2020 COVID crash validation - Requirements 4.2"""
        
        crisis_period = self.validator.crisis_periods['covid_crash_2020']['period']
        
        metrics = self.validator.analyze_crisis_performance(
            self.portfolio_data, crisis_period, 'covid_crash_2020'
        )
        
        # Verify COVID-specific characteristics
        assert metrics.crisis_name == 'covid_crash_2020'
        assert metrics.period == crisis_period
        
        # COVID crash was sharp but short - check recovery
        assert metrics.recovery_time_days <= 150  # Should recover within 5 months
        
        # Check regime adaptation capabilities
        assert metrics.regime_adaptation_speed_days > 0
        assert metrics.emergency_triggers_activated >= 0
        
        print(f"COVID Crisis - Max DD: {metrics.max_drawdown:.1%}, "
              f"Recovery time: {metrics.recovery_time_days} days, "
              f"Emergency triggers: {metrics.emergency_triggers_activated}")
    
    def test_2022_inflation_shock_validation(self):
        """Test 2022 inflation shock validation - Requirements 4.3"""
        
        crisis_period = self.validator.crisis_periods['inflation_shock_2022']['period']
        
        metrics = self.validator.analyze_crisis_performance(
            self.portfolio_data, crisis_period, 'inflation_shock_2022'
        )
        
        # Verify inflation shock characteristics
        assert metrics.crisis_name == 'inflation_shock_2022'
        assert metrics.period == crisis_period
        
        # Inflation shock was prolonged - check adaptation
        assert metrics.recovery_time_days >= 200  # Longer recovery expected
        
        # Check position size management
        assert metrics.position_size_reductions >= 0
        
        print(f"Inflation Shock - Max DD: {metrics.max_drawdown:.1%}, "
              f"Position reductions: {metrics.position_size_reductions}, "
              f"Volatility: {metrics.volatility_during_crisis:.1%}")
    
    def test_pre_crisis_positioning_analysis(self):
        """Test pre-crisis positioning analysis"""
        
        crisis_start = datetime(2008, 9, 15)  # Lehman Brothers collapse
        
        pre_crisis_metrics = self.validator.analyze_pre_crisis_positioning(
            self.portfolio_data, crisis_start
        )
        
        # Verify all required metrics are present
        required_keys = [
            'exposure_30d_before', 'risk_reduction_rate', 'defensive_positioning_score',
            'anticipatory_de_risking', 'cash_buildup_rate'
        ]
        
        for key in required_keys:
            assert key in pre_crisis_metrics
            assert isinstance(pre_crisis_metrics[key], (float, bool))
        
        # Check metric ranges
        assert 0 <= pre_crisis_metrics['exposure_30d_before'] <= 1
        assert 0 <= pre_crisis_metrics['defensive_positioning_score'] <= 1
        assert isinstance(pre_crisis_metrics['anticipatory_de_risking'], bool)
        
        print(f"Pre-crisis analysis - Exposure: {pre_crisis_metrics['exposure_30d_before']:.1%}, "
              f"Risk reduction: {pre_crisis_metrics['risk_reduction_rate']:.1%}, "
              f"Defensive score: {pre_crisis_metrics['defensive_positioning_score']:.2f}")
    
    def test_defensive_positioning_score_calculation(self):
        """Test defensive positioning score calculation"""
        
        # Create test data with defensive positioning
        defensive_data = pd.DataFrame({
            'date': pd.date_range('2008-06-01', '2008-07-01', freq='D'),
            'utilities_weight': [0.25] * 31,      # High utilities weight
            'consumer_staples_weight': [0.20] * 31,  # High staples weight
            'healthcare_weight': [0.15] * 31,     # High healthcare weight
            'cash_weight': [0.30] * 31,           # High cash weight
            'high_beta_weight': [0.05] * 31       # Low high-beta weight
        })
        
        score = self.validator._calculate_defensive_positioning_score(defensive_data)
        
        # Should be high due to defensive positioning
        assert 0.5 <= score <= 1.0
        
        # Test aggressive positioning
        aggressive_data = pd.DataFrame({
            'date': pd.date_range('2008-06-01', '2008-07-01', freq='D'),
            'utilities_weight': [0.05] * 31,      # Low utilities weight
            'consumer_staples_weight': [0.05] * 31,  # Low staples weight
            'healthcare_weight': [0.05] * 31,     # Low healthcare weight
            'cash_weight': [0.10] * 31,           # Low cash weight
            'high_beta_weight': [0.40] * 31       # High high-beta weight
        })
        
        aggressive_score = self.validator._calculate_defensive_positioning_score(aggressive_data)
        
        # Should be lower than defensive score
        assert aggressive_score < score
        
        print(f"Defensive score: {score:.2f}, Aggressive score: {aggressive_score:.2f}")
    
    def test_crisis_detection(self):
        """Test automatic crisis detection from market data"""
        
        # Create market data with embedded crisis
        market_dates = pd.date_range('2008-01-01', '2008-12-31', freq='D')
        
        # Simulate market crash
        prices = np.ones(len(market_dates)) * 100
        
        # Create crash in September-October 2008
        crash_start = 200  # Around September
        crash_end = 250    # Around October
        
        for i in range(crash_start, crash_end):
            prices[i] = prices[i-1] * 0.98  # 2% daily decline
        
        market_data = pd.DataFrame({
            'date': market_dates,
            'price': prices,
            'volume': np.random.uniform(1e6, 5e6, len(market_dates))
        })
        
        detected_crises = self.validator.detect_crisis_periods(market_data)
        
        # Should detect at least one crisis
        assert len(detected_crises) >= 1
        
        # Check crisis characteristics
        crisis = detected_crises[0]
        assert crisis['max_drawdown'] < -0.10  # At least 10% decline
        assert crisis['duration_days'] > 10    # At least 10 days
        
        print(f"Detected {len(detected_crises)} crises, "
              f"worst drawdown: {crisis['max_drawdown']:.1%}")
    
    def test_complete_crisis_validation_report(self):
        """Test complete crisis validation report generation"""
        
        report = self.validator.validate_crisis_performance(self.portfolio_data)
        
        # Verify report structure
        assert hasattr(report, 'validation_timestamp')
        assert hasattr(report, 'total_crises_analyzed')
        assert hasattr(report, 'crisis_metrics')
        assert hasattr(report, 'overall_survival_score')
        assert hasattr(report, 'pre_crisis_positioning_score')
        assert hasattr(report, 'risk_management_effectiveness')
        assert hasattr(report, 'recommendations')
        
        # Check report content
        assert report.total_crises_analyzed == 3
        assert len(report.crisis_metrics) == 3
        assert 0 <= report.overall_survival_score <= 1
        assert 0 <= report.pre_crisis_positioning_score <= 1
        assert 0 <= report.risk_management_effectiveness <= 1
        assert isinstance(report.recommendations, list)
        
        # Verify all expected crises are analyzed
        expected_crises = ['financial_crisis_2008', 'covid_crash_2020', 'inflation_shock_2022']
        for crisis in expected_crises:
            assert crisis in report.crisis_metrics
        
        print(f"Crisis Report - Survival: {report.overall_survival_score:.1%}, "
              f"Pre-crisis: {report.pre_crisis_positioning_score:.1%}, "
              f"Risk mgmt: {report.risk_management_effectiveness:.1%}")
        print(f"Recommendations: {len(report.recommendations)}")
    
    @given(
        market_decline=st.floats(min_value=-0.60, max_value=-0.05),
        volatility_spike=st.floats(min_value=0.20, max_value=0.80),
        exposure_before=st.floats(min_value=0.1, max_value=1.0)
    )
    @settings(max_examples=50)
    def test_emergency_protocol_activation_property(self, market_decline, volatility_spike, exposure_before):
        """
        Property test: Emergency protocols should activate for market declines > 10%
        **Validates: Requirements 4.4**
        """
        
        # Create crisis scenario
        crisis_dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')
        
        # Simulate market decline
        returns = np.full(len(crisis_dates), market_decline / len(crisis_dates))
        equity = np.cumprod(1 + returns)
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        
        crisis_data = pd.DataFrame({
            'date': crisis_dates,
            'daily_return': returns,
            'equity': equity,
            'drawdown': drawdown,
            'total_exposure': np.full(len(crisis_dates), exposure_before),
            'volatility': np.full(len(crisis_dates), volatility_spike)
        })
        
        # Count emergency triggers
        emergency_triggers = self.validator._count_emergency_triggers(crisis_data)
        
        # Property: Market declines > 10% should trigger emergency protocols
        if abs(market_decline) > 0.10:
            assert emergency_triggers > 0, f"No emergency triggers for {market_decline:.1%} decline"
        
        # Property: High volatility should trigger protocols
        if volatility_spike > 0.30:
            assert emergency_triggers > 0, f"No triggers for {volatility_spike:.1%} volatility"
    
    @given(
        initial_volatility=st.floats(min_value=0.10, max_value=0.25),
        volatility_spike=st.floats(min_value=0.30, max_value=0.80),
        initial_exposure=st.floats(min_value=0.5, max_value=1.0)
    )
    @settings(max_examples=50)
    def test_volatility_based_position_sizing_property(self, initial_volatility, volatility_spike, initial_exposure):
        """
        Property test: Position sizes should reduce when volatility exceeds norms
        **Validates: Requirements 4.5**
        """
        
        # Create volatility spike scenario
        dates = pd.date_range('2024-01-01', '2024-02-29', freq='D')
        
        # Simulate volatility increase
        volatilities = np.full(len(dates), initial_volatility)
        spike_start = len(dates) // 2
        volatilities[spike_start:] = volatility_spike
        
        # Simulate position size response
        exposures = np.full(len(dates), initial_exposure)
        
        # Reduce exposure when volatility spikes
        for i in range(spike_start, len(dates)):
            if volatilities[i] > volatilities[i-1] * 1.2:  # 20% vol increase
                exposures[i] = exposures[i-1] * 0.9  # 10% exposure reduction
        
        portfolio_data = pd.DataFrame({
            'date': dates,
            'volatility': volatilities,
            'total_exposure': exposures,
            'daily_return': np.random.normal(0, volatilities / np.sqrt(252))
        })
        
        # Count position reductions
        reductions = self.validator._count_position_reductions(portfolio_data)
        
        # Property: Volatility spikes should lead to position reductions
        if volatility_spike > initial_volatility * 1.5:  # 50% volatility increase
            assert reductions > 0, f"No position reductions for volatility spike from {initial_volatility:.1%} to {volatility_spike:.1%}"
        
        # Property: Final exposure should be lower than initial when volatility spikes
        if volatility_spike > 0.40:  # High volatility
            final_exposure = exposures[-1]
            assert final_exposure <= initial_exposure, f"Exposure increased during volatility spike: {initial_exposure:.1%} -> {final_exposure:.1%}"
    
    def test_crisis_survival_metrics(self):
        """Test crisis survival metrics calculation"""
        
        # Test survival scenario
        survival_data = pd.DataFrame({
            'date': pd.date_range('2008-09-01', '2008-12-31', freq='D'),
            'daily_return': np.random.normal(-0.001, 0.02, 122),  # Moderate losses
            'total_exposure': np.linspace(0.8, 0.4, 122),         # Reducing exposure
            'cash_weight': np.linspace(0.2, 0.6, 122),            # Increasing cash
            'leverage': np.full(122, 0.1)                         # Low leverage
        })
        
        survival_data['equity'] = np.cumprod(1 + survival_data['daily_return'])
        survival_data['drawdown'] = (survival_data['equity'] - survival_data['equity'].expanding().max()) / survival_data['equity'].expanding().max()
        
        metrics = self.validator.analyze_crisis_performance(
            survival_data, 
            (datetime(2008, 9, 1), datetime(2008, 12, 31)),
            'test_survival'
        )
        
        # Should survive with moderate drawdown
        assert metrics.survived_without_intervention
        assert metrics.max_drawdown > -0.50  # Less than 50% drawdown
        assert metrics.cash_reserves_maintained > 0.3  # Maintained cash
        
        print(f"Survival test - Survived: {metrics.survived_without_intervention}, "
              f"Max DD: {metrics.max_drawdown:.1%}, "
              f"Final cash: {metrics.cash_reserves_maintained:.1%}")

def test_crisis_validator_integration():
    """Integration test for crisis validator with real workflow"""
    
    print("\n🧪 CRISIS VALIDATOR INTEGRATION TEST")
    print("=" * 50)
    
    # Initialize validator
    validator = CrisisValidator()
    
    # Create comprehensive test data
    dates = pd.date_range('2007-01-01', '2023-12-31', freq='D')
    np.random.seed(123)
    
    # Simulate portfolio with crisis management
    returns = np.random.normal(0.0003, 0.012, len(dates))
    
    # Add realistic crisis impacts with recovery
    for crisis_name, crisis_info in validator.crisis_periods.items():
        crisis_start, crisis_end = crisis_info['period']
        crisis_mask = (dates >= crisis_start) & (dates <= crisis_end)
        
        # Simulate crisis-specific returns
        if 'financial_crisis' in crisis_name:
            crisis_returns = np.random.normal(-0.002, 0.025, crisis_mask.sum())
        elif 'covid_crash' in crisis_name:
            crisis_returns = np.random.normal(-0.003, 0.030, crisis_mask.sum())
        else:  # inflation shock
            crisis_returns = np.random.normal(-0.001, 0.020, crisis_mask.sum())
        
        returns[crisis_mask] = crisis_returns
    
    # Build comprehensive portfolio data
    equity = np.cumprod(1 + returns)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    
    # Simulate intelligent exposure management
    exposure = np.full(len(dates), 0.75)
    
    # Reduce exposure during crisis periods
    for crisis_name, crisis_info in validator.crisis_periods.items():
        pre_crisis_start = crisis_info['pre_crisis_start']
        crisis_end = crisis_info['period'][1]
        
        crisis_mask = (dates >= pre_crisis_start) & (dates <= crisis_end)
        exposure[crisis_mask] = 0.45  # Significant reduction
    
    portfolio_data = pd.DataFrame({
        'date': dates,
        'daily_return': returns,
        'equity': equity,
        'drawdown': drawdown,
        'total_exposure': exposure,
        'cash_weight': 1.0 - exposure,
        'volatility': pd.Series(returns).rolling(21).std() * np.sqrt(252),
        'utilities_weight': np.where(exposure < 0.6, 0.2, 0.05),
        'consumer_staples_weight': np.where(exposure < 0.6, 0.15, 0.05),
        'healthcare_weight': np.where(exposure < 0.6, 0.15, 0.05),
        'leverage': np.full(len(dates), 0.1)
    })
    
    # Run complete validation
    report = validator.validate_crisis_performance(portfolio_data)
    
    # Verify comprehensive results
    assert report.total_crises_analyzed == 3
    assert 0.15 <= report.overall_survival_score <= 1.0  # Realistic for crisis periods
    assert len(report.recommendations) > 0
    
    # Check individual crisis performance
    for crisis_name, metrics in report.crisis_metrics.items():
        print(f"\n{crisis_name}:")
        print(f"  Max Drawdown: {metrics.max_drawdown:.1%}")
        print(f"  Pre-crisis Exposure: {metrics.exposure_30d_before:.1%}")
        print(f"  Anticipatory De-risking: {metrics.anticipatory_de_risking}")
        print(f"  Survived: {metrics.survived_without_intervention}")
        
        # Basic sanity checks
        assert -1.0 <= metrics.max_drawdown <= 0.0
        assert 0.0 <= metrics.exposure_30d_before <= 1.0
        assert isinstance(metrics.anticipatory_de_risking, bool)
    
    print(f"\n📊 Overall Scores:")
    print(f"  Survival Score: {report.overall_survival_score:.1%}")
    print(f"  Pre-Crisis Positioning: {report.pre_crisis_positioning_score:.1%}")
    print(f"  Risk Management: {report.risk_management_effectiveness:.1%}")
    
    print(f"\n✅ Crisis validator integration test passed")
    
    return report

if __name__ == "__main__":
    # Run integration test
    test_crisis_validator_integration()