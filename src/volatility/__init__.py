"""
Unified Volatility Engine - Institutional-Grade Volatility Trading System

This module provides a cohesive volatility trading engine that consolidates
all volatility-related functionality into a single, well-architected system.

Components:
- VolatilityStateEngine: Single source of truth for all volatility state
- IVSurface: Implied volatility surface modeling
- RegimeDetector: Market regime classification
- GreeksAggregator: Portfolio-level Greeks computation
- StrategyGenerator: AST-based strategy generation
- RiskAuthority: Independent risk management with veto power
- CapitalAllocator: Regime-adaptive capital allocation
- DispersionModule: Correlation trading
- GammaScalper: Realized variance harvesting
- MonteCarloEngine: Tail risk simulation
"""

__version__ = "1.0.0"
__author__ = "Northstar Trading Systems"

# Core components
from .state_engine import VolatilityStateEngine, VolatilityState
from .risk_authority import (
    UnifiedRiskAuthority,
    RiskLimits,
    RiskViolation,
    TradeValidationResult,
    AuthorityLevel,
    RiskAction,
    create_risk_authority
)

# Regime detection
from .regime_detector import (
    RegimeDetector,
    VolatilityRegime,
    RegimeState,
    RegimeMetrics
)

# Volatility processing utilities
from .volatility_processor import (
    calculate_realized_volatility,
    calculate_atr,
    classify_volatility_regime,
    calculate_volatility_percentile,
    process_ticker_volatility,
    process_universe_volatility,
    calculate_implied_realized_spread,
    calculate_volatility_risk_premium,
)

# Intelligence engine
from .intelligence_engine import (
    UnifiedIntelligenceEngine,
    IntelligenceState,
    MarketRegime,
    SignalType,
    ValidationResult,
    SignalHistory
)

# IV Surface
from .iv_surface import (
    IVSurface,
    OptionQuote,
    SurfaceModel,
    SVIParameters,
    SABRParameters,
    SurfaceQuality,
    create_iv_surface_from_quotes
)

# Greeks Aggregator
from .greeks_aggregator import (
    GreeksAggregator,
    Greeks,
    PortfolioGreeks,
    Position,
    GreeksLimits,
    ConstraintViolation,
    Scenario
)

# Configuration Management
from .config import (
    ConfigurationManager,
    VolatilityEngineConfig,
    ConfigMode,
    RiskConfig,
    VolatilityConfig,
    RegimeConfig,
    StrategyConfig,
    CapitalAllocationConfig,
    MonteCarloConfig,
    PerformanceConfig,
    GreeksLimitsConfig,
    ConfigChange,
    create_config_manager
)

# Future components will be imported here as they are implemented
# from .strategy_generator import StrategyGenerator
# from .capital_allocator import CapitalAllocator
# from .dispersion_module import DispersionModule
# from .gamma_scalper import GammaScalper
# from .monte_carlo_engine import MonteCarloEngine

__all__ = [
    'VolatilityStateEngine',
    'VolatilityState',
    'UnifiedRiskAuthority',
    'RiskLimits',
    'RiskViolation',
    'TradeValidationResult',
    'AuthorityLevel',
    'RiskAction',
    'create_risk_authority',
    'RegimeDetector',
    'VolatilityRegime',
    'RegimeState',
    'RegimeMetrics',
    'calculate_realized_volatility',
    'calculate_atr',
    'classify_volatility_regime',
    'calculate_volatility_percentile',
    'process_ticker_volatility',
    'process_universe_volatility',
    'calculate_implied_realized_spread',
    'calculate_volatility_risk_premium',
    'UnifiedIntelligenceEngine',
    'IntelligenceState',
    'MarketRegime',
    'SignalType',
    'ValidationResult',
    'SignalHistory',
    'IVSurface',
    'OptionQuote',
    'SurfaceModel',
    'SVIParameters',
    'SABRParameters',
    'SurfaceQuality',
    'create_iv_surface_from_quotes',
    'GreeksAggregator',
    'Greeks',
    'PortfolioGreeks',
    'Position',
    'GreeksLimits',
    'ConstraintViolation',
    'Scenario',
    'ConfigurationManager',
    'VolatilityEngineConfig',
    'ConfigMode',
    'RiskConfig',
    'VolatilityConfig',
    'RegimeConfig',
    'StrategyConfig',
    'CapitalAllocationConfig',
    'MonteCarloConfig',
    'PerformanceConfig',
    'GreeksLimitsConfig',
    'ConfigChange',
    'create_config_manager',
]

