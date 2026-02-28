"""
Unit tests for Configuration Management System

Tests parameter validation, configuration templates, and versioning.

Validates: Requirements 15.2, 15.5
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from src.volatility.config import (
    ConfigurationManager,
    VolatilityEngineConfig,
    ConfigMode,
    RiskConfig,
    VolatilityConfig,
    RegimeConfig,
    GreeksLimitsConfig,
    create_config_manager
)


@pytest.fixture
def temp_config_file():
    """Create temporary configuration file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def config_manager():
    """Create configuration manager instance"""
    return ConfigurationManager()


def test_default_config_creation(config_manager):
    """Test default configuration is created correctly"""
    config = config_manager.config
    
    assert config.version == "1.0.0"
    assert config.mode == ConfigMode.MODERATE
    assert config.risk is not None
    assert config.volatility is not None
    assert config.regime is not None


def test_config_validation_valid(config_manager):
    """Test validation passes for valid configuration"""
    config = VolatilityEngineConfig()
    errors = config_manager.validate_config(config)
    
    assert len(errors) == 0


def test_config_validation_invalid_risk_limits(config_manager):
    """Test validation fails for invalid risk limits"""
    config = VolatilityEngineConfig()
    config.risk.greeks_limits.max_delta = -100.0  # Invalid: negative
    
    errors = config_manager.validate_config(config)
    
    assert len(errors) > 0
    assert any("max_delta" in error for error in errors)


def test_config_validation_invalid_concentration(config_manager):
    """Test validation fails for invalid concentration"""
    config = VolatilityEngineConfig()
    config.risk.max_concentration_pct = 1.5  # Invalid: > 1.0
    
    errors = config_manager.validate_config(config)
    
    assert len(errors) > 0
    assert any("max_concentration_pct" in error for error in errors)


def test_config_validation_invalid_surface_model(config_manager):
    """Test validation fails for invalid surface model"""
    config = VolatilityEngineConfig()
    config.volatility.surface_model = "INVALID"
    
    errors = config_manager.validate_config(config)
    
    assert len(errors) > 0
    assert any("surface_model" in error for error in errors)


def test_config_validation_invalid_regime_thresholds(config_manager):
    """Test validation fails for invalid regime thresholds"""
    config = VolatilityEngineConfig()
    config.regime.crisis_vix_threshold = 20.0
    config.regime.high_vol_vix_threshold = 25.0  # Invalid: crisis < high_vol
    
    errors = config_manager.validate_config(config)
    
    assert len(errors) > 0
    assert any("crisis_vix_threshold" in error for error in errors)


def test_config_validation_invalid_kelly_fraction(config_manager):
    """Test validation fails for invalid Kelly fraction"""
    config = VolatilityEngineConfig()
    config.capital_allocation.kelly_fraction = 1.5  # Invalid: > 1.0
    
    errors = config_manager.validate_config(config)
    
    assert len(errors) > 0
    assert any("kelly_fraction" in error for error in errors)


def test_config_validation_invalid_monte_carlo_paths(config_manager):
    """Test validation fails for too few Monte Carlo paths"""
    config = VolatilityEngineConfig()
    config.monte_carlo.num_paths = 100  # Invalid: < 1000
    
    errors = config_manager.validate_config(config)
    
    assert len(errors) > 0
    assert any("num_paths" in error for error in errors)


def test_save_and_load_config(config_manager, temp_config_file):
    """Test configuration save and load"""
    # Modify configuration
    config_manager.config.risk.greeks_limits.max_delta = 1500.0
    config_manager.config.volatility.surface_model = "SABR"
    
    # Save
    config_manager.save_config(temp_config_file)
    assert temp_config_file.exists()
    
    # Load into new manager
    new_manager = ConfigurationManager(temp_config_file)
    new_manager.load_config()
    
    # Verify values
    assert new_manager.config.risk.greeks_limits.max_delta == 1500.0
    assert new_manager.config.volatility.surface_model == "SABR"


def test_update_parameter_valid(config_manager):
    """Test updating valid parameter"""
    old_value = config_manager.config.risk.greeks_limits.max_delta
    new_value = 1500.0
    
    success = config_manager.update_parameter(
        "risk.greeks_limits.max_delta",
        new_value,
        modified_by="test_user",
        reason="Testing parameter update"
    )
    
    assert success
    assert config_manager.config.risk.greeks_limits.max_delta == new_value
    
    # Check change history
    assert len(config_manager.change_history) == 1
    change = config_manager.change_history[0]
    assert change.parameter == "risk.greeks_limits.max_delta"
    assert change.new_value == new_value
    assert change.modified_by == "test_user"


def test_update_parameter_invalid(config_manager):
    """Test updating parameter with invalid value"""
    success = config_manager.update_parameter(
        "risk.greeks_limits.max_delta",
        -100.0,  # Invalid: negative
        modified_by="test_user"
    )
    
    assert not success
    # Original value should be unchanged
    assert config_manager.config.risk.greeks_limits.max_delta > 0


def test_update_parameter_nonexistent(config_manager):
    """Test updating non-existent parameter"""
    success = config_manager.update_parameter(
        "nonexistent.parameter",
        100.0,
        modified_by="test_user"
    )
    
    assert not success


def test_aggressive_template(config_manager):
    """Test aggressive configuration template"""
    config = config_manager.get_template(ConfigMode.AGGRESSIVE)
    
    assert config.mode == ConfigMode.AGGRESSIVE
    assert config.risk.greeks_limits.max_delta > 1000.0  # Higher than default
    assert config.capital_allocation.kelly_fraction > 0.25  # More aggressive
    assert config.capital_allocation.max_drawdown > 0.20  # Higher tolerance


def test_moderate_template(config_manager):
    """Test moderate configuration template"""
    config = config_manager.get_template(ConfigMode.MODERATE)
    
    assert config.mode == ConfigMode.MODERATE
    assert config.risk.greeks_limits.max_delta == 1000.0  # Default
    assert config.capital_allocation.kelly_fraction == 0.25  # Default


def test_conservative_template(config_manager):
    """Test conservative configuration template"""
    config = config_manager.get_template(ConfigMode.CONSERVATIVE)
    
    assert config.mode == ConfigMode.CONSERVATIVE
    assert config.risk.greeks_limits.max_delta < 1000.0  # Lower than default
    assert config.capital_allocation.kelly_fraction < 0.25  # More conservative
    assert config.capital_allocation.max_drawdown < 0.20  # Lower tolerance


def test_change_history_tracking(config_manager):
    """Test configuration change history is tracked"""
    # Make multiple changes
    config_manager.update_parameter(
        "risk.greeks_limits.max_delta",
        1500.0,
        modified_by="user1",
        reason="Increase risk limits"
    )
    
    config_manager.update_parameter(
        "capital_allocation.kelly_fraction",
        0.3,
        modified_by="user2",
        reason="Adjust Kelly fraction"
    )
    
    # Check history
    history = config_manager.get_change_history()
    assert len(history) == 2
    
    # Check first change
    assert history[0].parameter == "risk.greeks_limits.max_delta"
    assert history[0].modified_by == "user1"
    assert history[0].reason == "Increase risk limits"
    
    # Check second change
    assert history[1].parameter == "capital_allocation.kelly_fraction"
    assert history[1].modified_by == "user2"


def test_change_history_limit(config_manager):
    """Test getting limited change history"""
    # Make multiple changes
    for i in range(5):
        config_manager.update_parameter(
            "risk.greeks_limits.max_delta",
            1000.0 + i * 100,
            modified_by=f"user{i}"
        )
    
    # Get last 3 changes
    recent_history = config_manager.get_change_history(limit=3)
    assert len(recent_history) == 3


def test_hot_reload_parameter(config_manager):
    """Test hot-reloadable parameter update"""
    # This parameter can be hot-reloaded
    success = config_manager.update_parameter(
        "strategy.delta_tolerance",
        0.15,
        modified_by="test_user"
    )
    
    assert success
    assert config_manager.config.strategy.delta_tolerance == 0.15


def test_config_versioning(config_manager):
    """Test configuration version tracking"""
    initial_version = config_manager.config.version
    initial_modified_at = config_manager.config.modified_at
    
    # Update parameter
    config_manager.update_parameter(
        "risk.greeks_limits.max_delta",
        1500.0,
        modified_by="test_user"
    )
    
    # Version should remain same, but modified_at should update
    assert config_manager.config.version == initial_version
    assert config_manager.config.modified_at != initial_modified_at
    assert config_manager.config.modified_by == "test_user"


def test_nested_config_access(config_manager):
    """Test accessing nested configuration values"""
    value = config_manager._get_nested_value("risk.greeks_limits.max_delta")
    assert value == config_manager.config.risk.greeks_limits.max_delta


def test_create_config_manager_convenience():
    """Test convenience function for creating config manager"""
    manager = create_config_manager()
    
    assert isinstance(manager, ConfigurationManager)
    assert manager.config is not None


def test_config_to_dict_conversion(config_manager):
    """Test configuration to dictionary conversion"""
    config_dict = config_manager._config_to_dict(config_manager.config)
    
    assert isinstance(config_dict, dict)
    assert 'version' in config_dict
    assert 'risk' in config_dict
    assert 'volatility' in config_dict
    assert config_dict['mode'] == ConfigMode.MODERATE.value


def test_dict_to_config_conversion(config_manager):
    """Test dictionary to configuration conversion"""
    config_dict = {
        'version': '1.0.0',
        'mode': 'moderate',
        'risk': {
            'max_position_size': 1000000.0,
            'greeks_limits': {
                'max_delta': 1000.0,
                'max_gamma': 100.0,
                'max_vega': 5000.0
            }
        },
        'volatility': {
            'surface_model': 'SVI',
            'min_quotes_for_fit': 10
        }
    }
    
    config = config_manager._dict_to_config(config_dict)
    
    assert isinstance(config, VolatilityEngineConfig)
    assert config.version == '1.0.0'
    assert config.mode == ConfigMode.MODERATE
    assert config.risk.greeks_limits.max_delta == 1000.0


def test_invalid_config_file_handling(config_manager, temp_config_file):
    """Test handling of invalid configuration file"""
    # Write invalid JSON
    with open(temp_config_file, 'w') as f:
        f.write("{ invalid json }")
    
    # Should fall back to defaults without crashing
    manager = ConfigurationManager(temp_config_file)
    config = manager.load_config()
    
    assert config is not None
    assert config.version == "1.0.0"  # Default


def test_missing_config_file_handling(config_manager):
    """Test handling of missing configuration file"""
    nonexistent_path = Path("/nonexistent/config.json")
    manager = ConfigurationManager(nonexistent_path)
    config = manager.load_config()
    
    # Should use defaults
    assert config is not None
    assert config.version == "1.0.0"
