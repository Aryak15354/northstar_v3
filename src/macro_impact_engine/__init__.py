#!/usr/bin/env python3
"""
🧠 MACRO IMPACT ENGINE (MIE) - NORTHSTAR V3
Institutional-Grade Macro-Equity Transmission System

This subsystem reveals causal relationships between RBI macro variables and company returns.

Answers:
- Which RBI variable affects which company?
- At what lag?
- With what sign and magnitude?
- How stable is that relationship?
- How does it vary by regime?

Components:
- data_loader: Load and align RBI macro + company returns
- preprocessing: Stationarize, standardize, lag construction
- lagged_regression: Multi-lag regression estimation
- granger_tests: Predictive causality testing
- rolling_beta: Time-varying sensitivity estimation
- stability_tests: Relationship stability measurement
- sector_aggregation: Sector-level macro fingerprints
- report_generator: Institutional-grade reports

Output:
- Company-level macro fingerprints
- Sector-level macro sensitivities
- Macro stress testing framework
- Portfolio macro exposure monitoring
"""

__version__ = "1.0.0"
__author__ = "Northstar V3 Research Team"

from .macro_engine_data_loader import MacroDataLoader
from .preprocessing import MacroPreprocessor
from .lagged_regression import LaggedRegressionEngine
from .granger_tests import GrangerCausalityTester
from .rolling_beta import RollingBetaEstimator
from .stability_tests import StabilityAnalyzer
from .sector_aggregation import SectorAggregator
from .report_generator import MacroImpactReportGenerator


class MacroImpactEngine:
    """Lightweight compatibility facade for the macro impact subsystem."""

    def __init__(self):
        self.data_loader = MacroDataLoader
        self.preprocessor = MacroPreprocessor
        self.regression_engine = LaggedRegressionEngine
        self.granger_tester = GrangerCausalityTester
        self.rolling_beta_estimator = RollingBetaEstimator
        self.stability_analyzer = StabilityAnalyzer
        self.sector_aggregator = SectorAggregator
        self.report_generator = MacroImpactReportGenerator


__all__ = [
    'MacroImpactEngine',
    'MacroDataLoader',
    'MacroPreprocessor',
    'LaggedRegressionEngine',
    'GrangerCausalityTester',
    'RollingBetaEstimator',
    'StabilityAnalyzer',
    'SectorAggregator',
    'MacroImpactReportGenerator',
]
