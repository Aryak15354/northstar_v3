"""
Unit tests for Signal Engineering Configuration

Tests configuration loading, validation, and YAML serialization.
"""

import pytest
import tempfile
from pathlib import Path
from src.signal_engineering.config import (
    XGBoostConfig,
    PITSafetyBuffers,
    FeatureBudgetConfig,
    PhaseGates,
    SignalEngineeringConfig
)


class TestXGBoostConfig:
    """Tests for XGBoost hyperparameter configuration"""
    
    def test_default_values(self):
        """Test default hyperparameter values"""
        config = XGBoostConfig()
        
        assert config.max_depth == 4
        assert config.min_child_weight == 20  # Critical: must be 20, not 3
        assert config.learning_rate == 0.05
        assert config.n_estimators == 200
        assert config.subsample == 0.8
        assert config.colsample_bytree == 0.8
    
    def test_validation_success(self):
        """Test validation passes with correct values"""
        config = XGBoostConfig()
        config.validate()  # Should not raise
    
    def test_validation_min_child_weight(self):
        """Test validation fails if min_child_weight < 20"""
        config = XGBoostConfig(min_child_weight=3)
        
        with pytest.raises(AssertionError, match="min_child_weight must be >= 20"):
            config.validate()
    
    def test_validation_learning_rate(self):
        """Test validation fails with invalid learning rate"""
        config = XGBoostConfig(learning_rate=0.5)
        
        with pytest.raises(AssertionError, match="learning_rate must be in"):
            config.validate()


class TestPITSafetyBuffers:
    """Tests for PIT safety buffer configuration"""
    
    def test_default_buffers(self):
        """Test default buffer values"""
        buffers = PITSafetyBuffers()
        
        assert buffers.quarterly_financials == 2
        assert buffers.annual_financials == 2
        assert buffers.earnings_announcements == 1
        assert buffers.bulk_deals == 0  # Same day
        assert buffers.price_data == 1
        assert buffers.analyst_estimates == 0
        assert buffers.shareholding == 2
    
    def test_get_buffer_known_type(self):
        """Test getting buffer for known data type"""
        buffers = PITSafetyBuffers()
        
        assert buffers.get_buffer('quarterly_financials') == 2
        assert buffers.get_buffer('bulk_deals') == 0
    
    def test_get_buffer_unknown_type(self):
        """Test getting buffer for unknown data type returns default"""
        buffers = PITSafetyBuffers()
        
        # Unknown type should return default of 1
        assert buffers.get_buffer('unknown_type') == 1


class TestFeatureBudgetConfig:
    """Tests for feature budget configuration"""
    
    def test_budget_calculation(self):
        """Test N/5 budget rule"""
        budget = FeatureBudgetConfig(universe_size=150)
        
        assert budget.budget == 30  # 150 / 5
    
    def test_utilization_calculation(self):
        """Test budget utilization percentage"""
        budget = FeatureBudgetConfig(universe_size=150)
        
        assert budget.utilization(15) == 50.0  # 15/30 = 50%
        assert budget.utilization(30) == 100.0  # 30/30 = 100%
    
    def test_is_exceeded(self):
        """Test budget exceeded check"""
        budget = FeatureBudgetConfig(universe_size=150)
        
        assert not budget.is_exceeded(30)  # At limit
        assert budget.is_exceeded(31)  # Over limit
        assert not budget.is_exceeded(29)  # Under limit
    
    def test_different_universe_sizes(self):
        """Test budget for different universe sizes"""
        assert FeatureBudgetConfig(150).budget == 30
        assert FeatureBudgetConfig(200).budget == 40
        assert FeatureBudgetConfig(300).budget == 60


class TestPhaseGates:
    """Tests for phase gate thresholds"""
    
    def test_default_gates(self):
        """Test default gate thresholds"""
        gates = PhaseGates()
        
        assert gates.phase_0 == 0.032
        assert gates.phase_1 == 0.037
        assert gates.phase_7 == 0.047
        assert gates.regime_minimum == 0.010
    
    def test_get_gate(self):
        """Test getting gate threshold by phase name"""
        gates = PhaseGates()
        
        assert gates.get_gate('phase_0') == 0.032
        assert gates.get_gate('Phase 3') == 0.040
        assert gates.get_gate('phase-5') == 0.043


class TestSignalEngineeringConfig:
    """Tests for main configuration class"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = SignalEngineeringConfig()
        
        assert config.version == "1.0"
        assert config.phase == "Phase 0"
        assert config.universe_size == 150
        assert config.liquidity_threshold_cr == 2.0
        assert config.leakage_shift_days == 5
        assert config.leakage_ic_ratio_threshold == 1.20
    
    def test_validation_success(self):
        """Test validation passes with default config"""
        config = SignalEngineeringConfig()
        config.validate()  # Should not raise
    
    def test_yaml_round_trip(self):
        """Test saving and loading configuration from YAML"""
        config = SignalEngineeringConfig()
        config.active_features = ['momentum', 'value', 'quality']
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            config.to_yaml(temp_path)
            
            # Load back
            loaded_config = SignalEngineeringConfig.from_yaml(temp_path)
            
            # Verify key values
            assert loaded_config.version == config.version
            assert loaded_config.phase == config.phase
            assert loaded_config.universe_size == config.universe_size
            assert loaded_config.xgboost.max_depth == config.xgboost.max_depth
            assert loaded_config.xgboost.min_child_weight == 20
            assert loaded_config.active_features == config.active_features
            
        finally:
            # Clean up
            if temp_path.exists():
                temp_path.unlink()
    
    def test_feature_budget_sync(self):
        """Test feature budget syncs with universe size"""
        config = SignalEngineeringConfig(universe_size=300)
        
        assert config.feature_budget.universe_size == 300
        assert config.feature_budget.budget == 60  # 300 / 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
