"""
Configuration loader for Options Trading System

Loads configuration from YAML files and environment variables.
Validates configuration on startup.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger("options.config")


@dataclass
class CapitalConfig:
    """Capital and risk configuration"""
    base_capital: float
    base_risk_pct: float
    max_risk_pct: float
    min_risk_pct: float


@dataclass
class UpstoxConfig:
    """Upstox API configuration"""
    api_key: str
    api_secret: str
    access_token: str
    rate_limit_per_second: int
    max_instruments_per_request: int
    endpoints: Dict[str, str]


@dataclass
class StrategyConfig:
    """Strategy configuration"""
    allowed: list
    iron_condor: Dict[str, Any]
    calendar_spread: Dict[str, Any]
    long_straddle: Dict[str, Any]


@dataclass
class RegimeConfig:
    """Regime detection configuration"""
    iv_rank_lookback_days: int
    vol_of_vol_threshold: float
    regime_persistence_days: int
    thresholds: Dict[str, float]


@dataclass
class EligibilityConfig:
    """Trade eligibility configuration"""
    max_bid_ask_spread_pct: float
    min_liquidity_depth_multiplier: float
    min_days_to_expiry: int
    event_buffer_days: int
    late_cycle_days: int
    late_cycle_size_reduction: float
    max_expected_slippage_bps: float = 120.0
    max_transaction_cost_pct_of_max_loss: float = 0.20


@dataclass
class CapitalScalingConfig:
    """Capital scaling configuration"""
    profit_milestone_pct: float
    profit_scaling_increment: float
    drawdown_threshold_1: float
    drawdown_threshold_2: float
    drawdown_descaling_1: float
    drawdown_descaling_2: float
    min_weeks_before_scaling: int
    recovery_profitable_trades: int


@dataclass
class SurvivalRulesConfig:
    """Survival rules configuration"""
    weekly_loss_limit_pct: float
    trauma_loss_threshold_pct: float
    trauma_cooldown_weeks: int
    portfolio_risk_cap_pct: float
    max_trades_per_week: int
    no_trade_times: list
    no_trade_days: list


@dataclass
class ExitRulesConfig:
    """Exit rules configuration"""
    profit_target_pct: float
    stop_loss_pct: float
    days_before_expiry: int
    precedence: list
    regime_flip_min_hold_minutes: int = 30
    regime_flip_confirmation_cycles: int = 2
    regime_flip_market_open_grace_minutes: int = 30


@dataclass
class GreekSafetyBandsConfig:
    """Greek safety bands configuration"""
    delta_min: float
    delta_max: float
    theta_min: float
    vega_min: float
    vega_max: float
    gamma_escalation: Dict[str, Any]


@dataclass
class CostsConfig:
    """Trading costs configuration"""
    brokerage_per_leg: float
    exchange_charges_pct: float
    sebi_charges_per_crore: float
    stamp_duty_pct: float
    gst_pct: float


@dataclass
class TaxConfig:
    """Tax configuration"""
    rate: float
    min_profitability_multiplier: float


@dataclass
class MacroEvent:
    """Macro event definition"""
    event_type: str
    dates: list
    buffer_days: int


@dataclass
class DashboardConfig:
    """Dashboard configuration"""
    refresh_interval_seconds: int
    greek_chart_lookback_days: int
    trade_history_limit: int
    alerts: Dict[str, bool]


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str
    file: str
    max_bytes: int
    backup_count: int
    log_decisions: Dict[str, bool]


@dataclass
class AlphaOSConfig:
    """AlphaOS dual-track migration and safety controls"""
    enabled: bool = False
    shadow_mode: bool = True
    enforce_mode: bool = False
    write_legacy_artifacts: bool = True
    canonical_state_max_age_seconds: int = 2700
    hmm_model_path: str = "data/models/regime_hmm_latest.pkl"
    hmm_retrain_interval_days: int = 30
    hmm_min_samples: int = 260
    hmm_transition_smoothing: float = 0.02
    meta_regret_half_life_days: int = 20
    meta_hysteresis_relative_change: float = 0.10
    meta_max_weight_shift_per_cycle: float = 0.15
    meta_min_gross_exposure_floor: float = 0.25
    valuation_bridge_enabled: bool = True
    valuation_beta: float = 0.12


@dataclass
class DataPathsConfig:
    """Data storage paths"""
    trade_ledger: str
    regime_history: str
    iv_history: str
    position_snapshots: str


@dataclass
class OptionsConfig:
    """Complete options trading configuration"""
    capital: CapitalConfig
    upstox: UpstoxConfig
    strategies: StrategyConfig
    regime_detection: RegimeConfig
    eligibility: EligibilityConfig
    capital_scaling: CapitalScalingConfig
    survival_rules: SurvivalRulesConfig
    exit_rules: ExitRulesConfig
    greek_safety_bands: GreekSafetyBandsConfig
    costs: CostsConfig
    tax: TaxConfig
    event_calendar: list
    lot_sizes: Dict[str, int]
    dashboard: DashboardConfig
    logging: LoggingConfig
    alpha_os: AlphaOSConfig
    data_paths: DataPathsConfig


class ConfigLoader:
    """Loads and validates options trading configuration"""
    
    def __init__(self, config_path: Optional[str] = None, env_path: Optional[str] = None):
        """
        Initialize configuration loader
        
        Args:
            config_path: Path to options_trading.yaml (default: config/options_trading.yaml)
            env_path: Path to .env.options file (default: .env.options)
        """
        self.config_path = config_path or "config/options_trading.yaml"
        self.env_path = env_path or ".env.options"
        self._config: Optional[OptionsConfig] = None
    
    def load(self) -> OptionsConfig:
        """
        Load configuration from files and environment
        
        Returns:
            OptionsConfig: Validated configuration object
        
        Raises:
            FileNotFoundError: If config file not found
            ValueError: If configuration is invalid
        """
        # Load environment variables
        self._load_env_file()
        
        # Load YAML configuration
        config_dict = self._load_yaml()
        
        # Substitute environment variables
        config_dict = self._substitute_env_vars(config_dict)
        
        # Validate and create config object
        self._config = self._create_config_object(config_dict)
        
        # Validate configuration
        self._validate_config()
        
        logger.info(f"Configuration loaded successfully from {self.config_path}")
        return self._config
    
    def _load_env_file(self) -> None:
        """Load environment variables from .env.options file without clobbering live overrides."""
        if not os.path.exists(self.env_path):
            logger.warning(f"Environment file {self.env_path} not found, using system environment")
            return

        loaded = 0
        preserved = 0
        with open(self.env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    if key in os.environ:
                        preserved += 1
                        continue
                    os.environ[key] = value.strip()
                    loaded += 1

        logger.info(
            "Environment variables loaded from %s (loaded=%d preserved_existing=%d)",
            self.env_path,
            loaded,
            preserved,
        )
    
    def _load_yaml(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        return config
    
    def _substitute_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively substitute ${VAR} with environment variables"""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            var_name = config[2:-1]
            value = os.environ.get(var_name)
            if value is None:
                raise ValueError(f"Environment variable {var_name} not found")
            return value
        else:
            return config
    
    def _create_config_object(self, config_dict: Dict[str, Any]) -> OptionsConfig:
        """Create OptionsConfig object from dictionary"""
        alpha_os_defaults = {
            "enabled": False,
            "shadow_mode": True,
            "enforce_mode": False,
            "write_legacy_artifacts": False,
            "canonical_state_max_age_seconds": 2700,
            "hmm_model_path": "data/models/regime_hmm_latest.pkl",
            "hmm_retrain_interval_days": 30,
            "hmm_min_samples": 260,
            "hmm_transition_smoothing": 0.02,
            "meta_regret_half_life_days": 20,
            "meta_hysteresis_relative_change": 0.10,
            "meta_max_weight_shift_per_cycle": 0.15,
            "meta_min_gross_exposure_floor": 0.25,
            "valuation_bridge_enabled": True,
            "valuation_beta": 0.12,
        }
        alpha_os_config = {
            **alpha_os_defaults,
            **(config_dict.get("alpha_os") or {}),
        }

        eligibility_dict = {
            **config_dict['eligibility'],
            'max_bid_ask_spread_pct': config_dict['eligibility']['max_bid_ask_spread_pct'] / 100.0,
        }
        survival_rules_dict = {
            **config_dict['survival_rules'],
            'weekly_loss_limit_pct': config_dict['survival_rules']['weekly_loss_limit_pct'] / 100.0,
            'trauma_loss_threshold_pct': config_dict['survival_rules']['trauma_loss_threshold_pct'] / 100.0,
        }
        exit_rules_dict = {
            **config_dict['exit_rules'],
            'profit_target_pct': config_dict['exit_rules']['profit_target_pct'] / 100.0,
            'stop_loss_pct': config_dict['exit_rules']['stop_loss_pct'] / 100.0,
        }

        return OptionsConfig(
            capital=CapitalConfig(**config_dict['capital']),
            upstox=UpstoxConfig(**config_dict['upstox']),
            strategies=StrategyConfig(**config_dict['strategies']),
            regime_detection=RegimeConfig(**config_dict['regime_detection']),
            eligibility=EligibilityConfig(**eligibility_dict),
            capital_scaling=CapitalScalingConfig(**config_dict['capital_scaling']),
            survival_rules=SurvivalRulesConfig(**survival_rules_dict),
            exit_rules=ExitRulesConfig(**exit_rules_dict),
            greek_safety_bands=GreekSafetyBandsConfig(**config_dict['greek_safety_bands']),
            costs=CostsConfig(**config_dict['costs']),
            tax=TaxConfig(**config_dict['tax']),
            event_calendar=[MacroEvent(**event) for event in config_dict['event_calendar']],
            lot_sizes=config_dict['lot_sizes'],
            dashboard=DashboardConfig(**config_dict['dashboard']),
            logging=LoggingConfig(**config_dict['logging']),
            alpha_os=AlphaOSConfig(**alpha_os_config),
            data_paths=DataPathsConfig(**config_dict['data_paths'])
        )
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        if self._config is None:
            raise ValueError("Configuration not loaded")
        
        # Validate capital
        if self._config.capital.base_capital <= 0:
            raise ValueError("base_capital must be positive")
        if not (0 < self._config.capital.base_risk_pct <= self._config.capital.max_risk_pct):
            raise ValueError("Invalid risk percentages")
        
        # Validate Upstox credentials
        if not self._config.upstox.api_key:
            raise ValueError("Upstox API key not configured")
        if not self._config.upstox.api_secret:
            raise ValueError("Upstox API secret not configured")
        if not self._config.upstox.access_token:
            raise ValueError("Upstox access token not configured")
        
        # Validate exit/survival/eligibility percentages are stored as 0-1 fractions,
        # not percentage points. These fields gate stop-loss/profit-target/weekly-loss/
        # trauma-cooldown/spread-eligibility checks; a value > 1.0 here means the
        # config-loading conversion regressed and these safety checks would silently
        # stop firing (see _create_config_object).
        fraction_fields = [
            ("exit_rules.stop_loss_pct", self._config.exit_rules.stop_loss_pct),
            ("exit_rules.profit_target_pct", self._config.exit_rules.profit_target_pct),
            ("survival_rules.weekly_loss_limit_pct", self._config.survival_rules.weekly_loss_limit_pct),
            ("survival_rules.trauma_loss_threshold_pct", self._config.survival_rules.trauma_loss_threshold_pct),
            ("eligibility.max_bid_ask_spread_pct", self._config.eligibility.max_bid_ask_spread_pct),
        ]
        for field_name, value in fraction_fields:
            if not (0.0 < value <= 1.0):
                raise ValueError(
                    f"{field_name}={value} must be a 0-1 fraction after config loading "
                    "(e.g. 0.05 for 5%), not a percentage point. Check the YAML value and "
                    "the conversion in ConfigLoader._create_config_object."
                )

        # Validate regime thresholds
        thresholds = self._config.regime_detection.thresholds
        if not (0 < thresholds['rising_vol_buy_iv_rank'] < thresholds['low_vol_sell_iv_rank'] < thresholds['high_vol_sell_iv_rank'] < 1):
            raise ValueError("Invalid IV rank thresholds")
        
        # Validate lot sizes
        if self._config.lot_sizes['NIFTY'] <= 0 or self._config.lot_sizes['BANKNIFTY'] <= 0:
            raise ValueError("Lot sizes must be positive")

        # Validate AlphaOS controls
        if self._config.alpha_os.enforce_mode and self._config.alpha_os.shadow_mode:
            logger.warning(
                "alpha_os.enforce_mode=true overrides alpha_os.shadow_mode=true; "
                "keeping dual-write but execution uses AlphaOS intent."
            )
        if self._config.alpha_os.canonical_state_max_age_seconds <= 0:
            raise ValueError("alpha_os.canonical_state_max_age_seconds must be positive")
        if self._config.alpha_os.hmm_retrain_interval_days < 30:
            raise ValueError("alpha_os.hmm_retrain_interval_days must be >= 30 (daily retraining is prohibited)")
        if self._config.alpha_os.hmm_min_samples <= 0:
            raise ValueError("alpha_os.hmm_min_samples must be positive")
        if not (0.0 <= self._config.alpha_os.hmm_transition_smoothing <= 1.0):
            raise ValueError("alpha_os.hmm_transition_smoothing must be within [0, 1]")
        if not (0.0 <= self._config.alpha_os.meta_hysteresis_relative_change <= 1.0):
            raise ValueError("alpha_os.meta_hysteresis_relative_change must be within [0, 1]")
        if not (0.0 <= self._config.alpha_os.meta_max_weight_shift_per_cycle <= 1.0):
            raise ValueError("alpha_os.meta_max_weight_shift_per_cycle must be within [0, 1]")
        if not (0.0 <= self._config.alpha_os.meta_min_gross_exposure_floor <= 1.0):
            raise ValueError("alpha_os.meta_min_gross_exposure_floor must be within [0, 1]")
        if not (0.0 <= self._config.alpha_os.valuation_beta <= 1.0):
            raise ValueError("alpha_os.valuation_beta must be within [0, 1]")
        
        # Validate data paths
        for path_name, path_value in vars(self._config.data_paths).items():
            path_dir = os.path.dirname(path_value)
            if path_dir and not os.path.exists(path_dir):
                os.makedirs(path_dir, exist_ok=True)
                logger.info(f"Created directory: {path_dir}")
        
        logger.info("Configuration validation passed")
    
    @property
    def config(self) -> OptionsConfig:
        """Get loaded configuration"""
        if self._config is None:
            raise ValueError("Configuration not loaded. Call load() first.")
        return self._config


# Global configuration instance
_config_loader: Optional[ConfigLoader] = None


def get_config(reload: bool = False) -> OptionsConfig:
    """
    Get global configuration instance
    
    Args:
        reload: Force reload configuration from files
    
    Returns:
        OptionsConfig: Configuration object
    """
    global _config_loader
    
    if _config_loader is None or reload:
        _config_loader = ConfigLoader()
        _config_loader.load()
    
    return _config_loader.config


if __name__ == "__main__":
    # Test configuration loading
    logging.basicConfig(level=logging.INFO)
    config = get_config()
    print(f"Configuration loaded successfully")
    print(f"Base capital: ₹{config.capital.base_capital:,.0f}")
    print(f"Base risk: {config.capital.base_risk_pct}%")
    print(f"Allowed strategies: {config.strategies.allowed}")
