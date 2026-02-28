"""
Configuration Management for Unified Volatility Engine

Implements centralized configuration with:
- Schema validation
- Configuration templates (aggressive, moderate, conservative)
- Hot-reloading for non-critical parameters
- Configuration versioning and audit trail

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy

logger = logging.getLogger(__name__)


class ConfigMode(Enum):
    """Configuration operating modes"""
    AGGRESSIVE = "aggressive"
    MODERATE = "moderate"
    CONSERVATIVE = "conservative"
    CUSTOM = "custom"


class PrimitiveType(Enum):
    """Primitive exposure types for strategy generation"""
    LONG_VOL = "long_vol"
    SHORT_VOL = "short_vol"
    LONG_GAMMA = "long_gamma"
    SHORT_GAMMA = "short_gamma"
    DIRECTIONAL_LONG = "directional_long"
    DIRECTIONAL_SHORT = "directional_short"
    THETA_POSITIVE = "theta_positive"
    THETA_NEGATIVE = "theta_negative"


@dataclass
class TargetGreeks:
    """Target Greeks for strategy generation"""
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    
    # More lenient tolerances for Indian markets
    delta_tolerance: float = 0.5   # 50% tolerance (was 20%)
    gamma_tolerance: float = 0.8   # 80% tolerance (was 10%)
    vega_tolerance: float = 0.6    # 60% tolerance (was 20%)
    theta_tolerance: float = 0.7   # 70% tolerance (was 10%)


@dataclass
class Constraints:
    """Strategy generation constraints"""
    max_legs: int = 8              # Allow more complex strategies
    max_cost: float = 200000.0     # ₹2L max for Indian markets
    max_spread_width: float = 0.15 # 15% max spread (was 5%)
    allowed_underlyings: List[str] = field(default_factory=lambda: ["NIFTY"])
    max_dte: int = 120             # 120 days (was 90)
    min_dte: int = 3               # 3 days (was 7)


@dataclass
class MarketState:
    """Market state for strategy generation"""
    spot_price: float
    implied_vol: float
    risk_free_rate: float = 0.05
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_atm_strike(self) -> float:
        """Get at-the-money strike"""
        return self.spot_price


@dataclass
class PrimitiveExposure:
    """Primitive exposure specification"""
    type: PrimitiveType
    size: float
    priority: int = 1


@dataclass
class GreeksLimitsConfig:
    """Greeks risk limits configuration"""
    max_delta: float = 1000.0
    max_gamma: float = 100.0
    max_vega: float = 5000.0
    max_theta: float = -500.0
    max_delta_per_underlying: float = 500.0
    max_vega_per_underlying: float = 2000.0
    max_gamma_per_underlying: float = 50.0


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Position limits
    max_position_size: float = 1000000.0
    max_positions_per_underlying: int = 10
    max_total_positions: int = 100
    
    # Greeks limits
    greeks_limits: GreeksLimitsConfig = field(default_factory=GreeksLimitsConfig)
    
    # Concentration limits
    max_concentration_pct: float = 0.25  # Max 25% in single underlying
    
    # Margin requirements
    initial_margin_multiplier: float = 1.5
    maintenance_margin_multiplier: float = 1.2
    
    # Emergency thresholds
    emergency_var_threshold: float = 0.10  # 10% portfolio loss
    emergency_drawdown_threshold: float = 0.15  # 15% drawdown


@dataclass
class VolatilityConfig:
    """Volatility surface and processing configuration"""
    # IV Surface fitting
    surface_model: str = "SVI"  # SVI or SABR
    min_quotes_for_fit: int = 10
    max_fit_iterations: int = 100
    fit_tolerance: float = 1e-6
    
    # Quality thresholds
    min_surface_quality: float = 0.7
    max_arbitrage_violation: float = 0.01
    
    # Extrapolation
    enable_extrapolation: bool = True
    max_extrapolation_distance: float = 0.5  # 50% beyond last strike


@dataclass
class RegimeConfig:
    """Regime detection configuration"""
    # VIX thresholds
    crisis_vix_threshold: float = 40.0
    high_vol_vix_threshold: float = 25.0
    low_vol_vix_threshold: float = 15.0
    
    # Correlation thresholds
    crisis_correlation_threshold: float = 0.8
    
    # Regime confidence
    min_regime_confidence: float = 0.6
    
    # History tracking
    regime_history_days: int = 365


@dataclass
class StrategyConfig:
    """Strategy generation configuration"""
    # Target Greeks tolerances
    delta_tolerance: float = 0.1
    gamma_tolerance: float = 0.05
    vega_tolerance: float = 0.1
    theta_tolerance: float = 0.1
    
    # Structure generation
    max_structures_to_generate: int = 20
    max_legs_per_structure: int = 6
    
    # Ranking
    cost_efficiency_weight: float = 0.6
    greeks_match_weight: float = 0.4


@dataclass
class CapitalAllocationConfig:
    """Capital allocation configuration"""
    # Kelly criterion
    kelly_fraction: float = 0.25  # Fractional Kelly for safety
    
    # Allocation bounds
    min_allocation_pct: float = 0.05  # Min 5% per strategy
    max_allocation_pct: float = 0.40  # Max 40% per strategy
    
    # Drawdown management
    drawdown_threshold: float = 0.10  # 10% drawdown triggers reduction
    max_drawdown: float = 0.20  # 20% max drawdown


@dataclass
class MonteCarloConfig:
    """Monte Carlo simulation configuration"""
    # Simulation parameters
    num_paths: int = 10000
    horizon_days: int = 30
    time_step_days: float = 1.0
    
    # Distribution parameters
    use_fat_tails: bool = True
    student_t_df: int = 5  # Degrees of freedom for Student-t
    
    # Risk metrics
    var_confidence_levels: List[float] = field(default_factory=lambda: [0.95, 0.99, 0.999])


@dataclass
class PerformanceConfig:
    """Performance monitoring configuration"""
    # Computation targets
    greeks_computation_target_ms: float = 50.0
    state_update_target_ms: float = 100.0
    
    # Monitoring
    enable_performance_logging: bool = True
    log_slow_operations: bool = True


@dataclass
class VolatilityEngineConfig:
    """Complete Unified Volatility Engine configuration"""
    # Metadata
    version: str = "1.0.0"
    mode: ConfigMode = ConfigMode.MODERATE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_by: str = "system"
    
    # Component configurations
    risk: RiskConfig = field(default_factory=RiskConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    capital_allocation: CapitalAllocationConfig = field(default_factory=CapitalAllocationConfig)
    monte_carlo: MonteCarloConfig = field(default_factory=MonteCarloConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Hot-reload settings
    hot_reload_enabled: bool = True
    hot_reload_check_interval_seconds: int = 60


@dataclass
class ConfigChange:
    """Record of configuration change"""
    timestamp: str
    parameter: str
    old_value: Any
    new_value: Any
    modified_by: str
    reason: str = ""


class ConfigurationManager:
    """
    Centralized configuration management system.
    
    Features:
    - Schema validation
    - Configuration templates
    - Hot-reloading
    - Version history and audit trail
    
    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7
    """
    
    # Parameters that can be hot-reloaded without restart
    HOT_RELOAD_PARAMS = {
        'risk.greeks_limits',
        'strategy.delta_tolerance',
        'strategy.gamma_tolerance',
        'strategy.vega_tolerance',
        'strategy.theta_tolerance',
        'capital_allocation.kelly_fraction',
        'capital_allocation.drawdown_threshold',
        'performance.enable_performance_logging',
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self.config_path = config_path or Path("config/volatility_engine.json")
        self.config: VolatilityEngineConfig = VolatilityEngineConfig()
        self.change_history: List[ConfigChange] = []
        self._last_load_time: Optional[datetime] = None
        
    def load_config(self, path: Optional[Path] = None) -> VolatilityEngineConfig:
        """
        Load configuration from file.
        
        Requirements: 15.1
        """
        config_file = path or self.config_path
        
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_file}, using defaults")
            return self.config
        
        try:
            with open(config_file, 'r') as f:
                config_dict = json.load(f)
            
            # Validate and load
            self.config = self._dict_to_config(config_dict)
            self._last_load_time = datetime.now()
            
            logger.info(f"Loaded configuration from {config_file}")
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_file}: {e}")
            logger.info("Using default configuration")
            return self.config
    
    def save_config(self, path: Optional[Path] = None) -> None:
        """
        Save configuration to file.
        
        Requirements: 15.1
        """
        config_file = path or self.config_path
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            config_dict = self._config_to_dict(self.config)
            
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            logger.info(f"Saved configuration to {config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_file}: {e}")
            raise
    
    def validate_config(self, config: VolatilityEngineConfig) -> List[str]:
        """
        Validate configuration parameters.
        
        Requirements: 15.2
        """
        errors = []
        
        # Risk validation
        if config.risk.greeks_limits.max_delta <= 0:
            errors.append("risk.greeks_limits.max_delta must be positive")
        if config.risk.max_position_size <= 0:
            errors.append("risk.max_position_size must be positive")
        if not 0 < config.risk.max_concentration_pct <= 1:
            errors.append("risk.max_concentration_pct must be between 0 and 1")
        
        # Volatility validation
        if config.volatility.surface_model not in ["SVI", "SABR"]:
            errors.append("volatility.surface_model must be 'SVI' or 'SABR'")
        if config.volatility.min_quotes_for_fit < 5:
            errors.append("volatility.min_quotes_for_fit must be at least 5")
        if not 0 <= config.volatility.min_surface_quality <= 1:
            errors.append("volatility.min_surface_quality must be between 0 and 1")
        
        # Regime validation
        if config.regime.crisis_vix_threshold <= config.regime.high_vol_vix_threshold:
            errors.append("regime.crisis_vix_threshold must be > high_vol_vix_threshold")
        if config.regime.high_vol_vix_threshold <= config.regime.low_vol_vix_threshold:
            errors.append("regime.high_vol_vix_threshold must be > low_vol_vix_threshold")
        
        # Strategy validation
        if config.strategy.max_legs_per_structure < 2:
            errors.append("strategy.max_legs_per_structure must be at least 2")
        
        # Capital allocation validation
        if not 0 < config.capital_allocation.kelly_fraction <= 1:
            errors.append("capital_allocation.kelly_fraction must be between 0 and 1")
        if config.capital_allocation.min_allocation_pct >= config.capital_allocation.max_allocation_pct:
            errors.append("capital_allocation.min_allocation_pct must be < max_allocation_pct")
        
        # Monte Carlo validation
        if config.monte_carlo.num_paths < 1000:
            errors.append("monte_carlo.num_paths should be at least 1000")
        if config.monte_carlo.horizon_days < 1:
            errors.append("monte_carlo.horizon_days must be at least 1")
        
        return errors
    
    def update_parameter(
        self,
        parameter_path: str,
        new_value: Any,
        modified_by: str = "system",
        reason: str = ""
    ) -> bool:
        """
        Update a single configuration parameter with validation.
        
        Requirements: 15.2, 15.3, 15.4
        """
        # Get current value
        try:
            old_value = self._get_nested_value(parameter_path)
        except ValueError as e:
            logger.error(f"Invalid parameter path {parameter_path}: {e}")
            return False
        
        # Create temporary config with new value
        temp_config = copy.deepcopy(self.config)
        try:
            self._set_nested_value(temp_config, parameter_path, new_value)
        except Exception as e:
            logger.error(f"Failed to set parameter {parameter_path}: {e}")
            return False
        
        # Validate new configuration
        errors = self.validate_config(temp_config)
        if errors:
            logger.error(f"Configuration validation failed: {errors}")
            return False
        
        # Check if hot-reload is allowed
        if not self._can_hot_reload(parameter_path):
            logger.warning(
                f"Parameter {parameter_path} requires system restart. "
                f"Change will be applied on next restart."
            )
        
        # Apply change
        self.config = temp_config
        self.config.modified_at = datetime.now().isoformat()
        self.config.modified_by = modified_by
        
        # Record change
        change = ConfigChange(
            timestamp=datetime.now().isoformat(),
            parameter=parameter_path,
            old_value=old_value,
            new_value=new_value,
            modified_by=modified_by,
            reason=reason
        )
        self.change_history.append(change)
        
        logger.info(
            f"Updated {parameter_path}: {old_value} -> {new_value} "
            f"(by {modified_by})"
        )
        
        return True
    
    def get_template(self, mode: ConfigMode) -> VolatilityEngineConfig:
        """
        Get configuration template for specified mode.
        
        Requirements: 15.6
        """
        if mode == ConfigMode.AGGRESSIVE:
            return self._create_aggressive_template()
        elif mode == ConfigMode.MODERATE:
            return self._create_moderate_template()
        elif mode == ConfigMode.CONSERVATIVE:
            return self._create_conservative_template()
        else:
            return VolatilityEngineConfig()
    
    def get_change_history(self, limit: Optional[int] = None) -> List[ConfigChange]:
        """
        Get configuration change history.
        
        Requirements: 15.4
        """
        if limit:
            return self.change_history[-limit:]
        return self.change_history
    
    def _dict_to_config(self, config_dict: Dict[str, Any]) -> VolatilityEngineConfig:
        """Convert dictionary to configuration object"""
        # Handle nested dataclasses
        if 'risk' in config_dict and isinstance(config_dict['risk'], dict):
            if 'greeks_limits' in config_dict['risk']:
                config_dict['risk']['greeks_limits'] = GreeksLimitsConfig(
                    **config_dict['risk']['greeks_limits']
                )
            config_dict['risk'] = RiskConfig(**config_dict['risk'])
        
        if 'volatility' in config_dict:
            config_dict['volatility'] = VolatilityConfig(**config_dict['volatility'])
        
        if 'regime' in config_dict:
            config_dict['regime'] = RegimeConfig(**config_dict['regime'])
        
        if 'strategy' in config_dict:
            config_dict['strategy'] = StrategyConfig(**config_dict['strategy'])
        
        if 'capital_allocation' in config_dict:
            config_dict['capital_allocation'] = CapitalAllocationConfig(
                **config_dict['capital_allocation']
            )
        
        if 'monte_carlo' in config_dict:
            config_dict['monte_carlo'] = MonteCarloConfig(**config_dict['monte_carlo'])
        
        if 'performance' in config_dict:
            config_dict['performance'] = PerformanceConfig(**config_dict['performance'])
        
        if 'mode' in config_dict and isinstance(config_dict['mode'], str):
            config_dict['mode'] = ConfigMode(config_dict['mode'])
        
        return VolatilityEngineConfig(**config_dict)
    
    def _config_to_dict(self, config: VolatilityEngineConfig) -> Dict[str, Any]:
        """Convert configuration object to dictionary"""
        config_dict = asdict(config)
        
        # Convert enums to strings
        if 'mode' in config_dict:
            config_dict['mode'] = config_dict['mode'].value if isinstance(
                config_dict['mode'], ConfigMode
            ) else config_dict['mode']
        
        return config_dict
    
    def _get_nested_value(self, path: str) -> Any:
        """Get value from nested configuration path"""
        parts = path.split('.')
        value = self.config
        
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                raise ValueError(f"Invalid configuration path: {path}")
        
        return value
    
    def _set_nested_value(self, config: VolatilityEngineConfig, path: str, value: Any) -> None:
        """Set value in nested configuration path"""
        parts = path.split('.')
        obj = config
        
        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            else:
                raise ValueError(f"Invalid configuration path: {path}")
        
        if hasattr(obj, parts[-1]):
            setattr(obj, parts[-1], value)
        else:
            raise ValueError(f"Invalid configuration path: {path}")
    
    def _can_hot_reload(self, parameter_path: str) -> bool:
        """Check if parameter can be hot-reloaded"""
        return parameter_path in self.HOT_RELOAD_PARAMS
    
    def _create_aggressive_template(self) -> VolatilityEngineConfig:
        """Create aggressive configuration template"""
        config = VolatilityEngineConfig(mode=ConfigMode.AGGRESSIVE)
        
        # Higher risk limits
        config.risk.greeks_limits.max_delta = 2000.0
        config.risk.greeks_limits.max_vega = 10000.0
        config.risk.max_concentration_pct = 0.35
        
        # More aggressive capital allocation
        config.capital_allocation.kelly_fraction = 0.5
        config.capital_allocation.max_allocation_pct = 0.50
        
        # Higher drawdown tolerance
        config.capital_allocation.drawdown_threshold = 0.15
        config.capital_allocation.max_drawdown = 0.30
        
        return config
    
    def _create_moderate_template(self) -> VolatilityEngineConfig:
        """Create moderate configuration template (default)"""
        return VolatilityEngineConfig(mode=ConfigMode.MODERATE)
    
    def _create_conservative_template(self) -> VolatilityEngineConfig:
        """Create conservative configuration template"""
        config = VolatilityEngineConfig(mode=ConfigMode.CONSERVATIVE)
        
        # Lower risk limits
        config.risk.greeks_limits.max_delta = 500.0
        config.risk.greeks_limits.max_vega = 2500.0
        config.risk.max_concentration_pct = 0.15
        
        # More conservative capital allocation
        config.capital_allocation.kelly_fraction = 0.125
        config.capital_allocation.max_allocation_pct = 0.25
        
        # Lower drawdown tolerance
        config.capital_allocation.drawdown_threshold = 0.05
        config.capital_allocation.max_drawdown = 0.10
        
        return config


# Convenience function to create configuration manager
def create_config_manager(config_path: Optional[Path] = None) -> ConfigurationManager:
    """
    Create and initialize configuration manager.
    
    Requirements: 15.1
    """
    manager = ConfigurationManager(config_path)
    manager.load_config()
    return manager
