"""
Northstar Valuation Engine v2
Institutional-grade valuation with forensic accounting and sector intelligence
"""

from .core.normalized_financials import FinancialNormalizer
from .core.adjusted_metrics import AdjustedMetricsCalculator
from .core.sector_mapper import SectorMapper

from .forensic.earnings_quality import EarningsQualityAnalyzer
from .forensic.accounting_distortions import AccountingDistortionDetector

from .intrinsic_value.owner_earnings import OwnerEarningsCalculator
from .intrinsic_value.dcf_engine import DCFEngine

from .buffett_module.moat_score import MoatScorer
from .valuation_feature_block import ValuationFeatureBlock

from .families import (
    CreditFamilyEngine,
    IntrinsicFamilyEngine,
    MacroValuationFamilyEngine,
    RealOptionsFamilyEngine,
    ResidualIncomeFamilyEngine,
    TransactionFamilyEngine,
)
from .aggregation import BayesianValuationAggregator
from .state import PortfolioValuationStateEngine

__all__ = [
    'FinancialNormalizer',
    'AdjustedMetricsCalculator',
    'SectorMapper',
    'EarningsQualityAnalyzer',
    'AccountingDistortionDetector',
    'OwnerEarningsCalculator',
    'DCFEngine',
    'MoatScorer',
    'ValuationFeatureBlock',
    'IntrinsicFamilyEngine',
    'ResidualIncomeFamilyEngine',
    'TransactionFamilyEngine',
    'MacroValuationFamilyEngine',
    'CreditFamilyEngine',
    'RealOptionsFamilyEngine',
    'BayesianValuationAggregator',
    'PortfolioValuationStateEngine',
]
