#!/usr/bin/env python3
"""
🧠 MACRO TRANSMISSION ENGINE - NORTHSTAR V3
Institutional Probabilistic Macro-Equity Intelligence

This is NOT feature engineering. This is a macro-aware probabilistic equity engine.

Evolution from Macro Impact Engine:
- Static OLS → Bayesian Hierarchical Model
- Fixed betas → Time-varying parameters (Kalman)
- Point estimates → Full posterior distributions
- Backward-looking → Forward-looking with macro forecasts
- Isolated analysis → Integrated with portfolio optimization

Components:
1. bayesian_model.py          - Hierarchical Bayesian transmission
2. kalman_filter.py            - Time-varying parameter estimation
3. macro_forecast.py           - Bayesian VAR forecasting
4. macro_alpha_adjuster.py     - Macro-adjusted signal weighting
5. macro_optimizer.py          - Macro-aware position sizing
6. stress_replay.py            - Historical stress simulation
7. global_transmission.py      - Cross-country macro spillovers

Key Differences from MIE:
- Probabilistic inference (not OLS)
- Time-varying sensitivities (not static)
- Forward-looking forecasts (not backward)
- Portfolio integration (not standalone)
- Regime awareness (not regime-blind)

Output:
- P(β > 0) for each macro sensitivity
- Time-varying β_t trajectories
- Macro-adjusted expected returns
- Stress-tested portfolio impacts
- Macro conviction scores
"""

__version__ = "2.0.0"
__author__ = "Northstar V3 Research Team"

from .bayesian_model import BayesianMacroTransmission
from .kalman_filter import TimeVaryingBetaKalman
from .macro_forecast import BayesianVARForecaster
from .macro_alpha_adjuster import MacroAlphaAdjuster
from .stress_replay import MacroStressReplay

# Production-grade numerical components
try:
    from .jax_kalman import JAXKalmanFilter, JAXKalmanFilterNumPy
    from .stochastic_volatility_kalman import StochasticVolatilityKalman, StochasticVolatilityKalmanNumPy
    JAX_COMPONENTS_AVAILABLE = True
except Exception:
    JAX_COMPONENTS_AVAILABLE = False

from .macro_optimizer import MacroAwareOptimizer

__all__ = [
    'BayesianMacroTransmission',
    'TimeVaryingBetaKalman',
    'BayesianVARForecaster',
    'MacroAlphaAdjuster',
    'MacroStressReplay',
    'MacroAwareOptimizer',
]

if JAX_COMPONENTS_AVAILABLE:
    __all__.extend([
        'JAXKalmanFilter',
        'JAXKalmanFilterNumPy',
        'StochasticVolatilityKalman',
        'StochasticVolatilityKalmanNumPy',
    ])
