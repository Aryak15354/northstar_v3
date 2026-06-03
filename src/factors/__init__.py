"""
Northstar V3 Factor Library — Academically-grounded factor signals.

This module provides production-ready implementations of five
literature-validated factor signals:

1. BAB (Betting Against Beta) — Frazzini & Pedersen (2014)
2. Amihud Illiquidity — Amihud (2002)
3. Piotroski F-Score — Piotroski (2000)
4. MAX Lottery Factor — Bali, Cakici, Whitelaw (2011)
5. Earnings Quality (Accruals) — Sloan (1996)

All factors are:
- PIT-compliant (no lookahead bias)
- Cross-sectionally normalized
- Cached for efficient historical computation
- Auditable (computation logs written to data/factors/)

Usage:
    from src.factors import FactorRegistry, FactorStore
    
    registry = FactorRegistry(ingestion_registry, config)
    factor_features = registry.compute_all(as_of_date, tickers)
"""

from .base_factor import BaseFactor
from .bab_factor import BABFactor
from .amihud_factor import AmihudFactor
from .piotroski_factor import PiotroskiFactor
from .max_factor import MAXFactor
from .earnings_quality_factor import EarningsQualityFactor
from .operating_profitability_factor import OperatingProfitabilityFactor
from .earnings_surprise_factor import EarningsSurpriseFactor
from .promoter_pledge_factor import PromoterPledgeFactor
from .bulk_deal_factor import BulkDealFactor
from .gap9_academic_factors import Gap9AcademicFactors
from .ivol_factor import IVOLFactor
from .factor_registry import FactorRegistry
from .factor_store import FactorStore

__all__ = [
    'BaseFactor',
    'BABFactor',
    'AmihudFactor',
    'PiotroskiFactor',
    'MAXFactor',
    'EarningsQualityFactor',
    'OperatingProfitabilityFactor',
    'EarningsSurpriseFactor',
    'PromoterPledgeFactor',
    'BulkDealFactor',
    'Gap9AcademicFactors',
    'IVOLFactor',
    'FactorRegistry',
    'FactorStore',
]
