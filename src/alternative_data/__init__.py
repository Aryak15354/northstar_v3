"""
Alternative Data Intelligence Layer for Northstar V3

This module transforms raw alternative data into structured signals for:
- Macro Transmission Engine (GST + power consumption)
- Intelligence Stack (all five sources as feature blocks)
- Valuation Engine (credit ratings + promoter pledges)
- Risk Management System (pledge ratios + credit deterioration)

Data sources:
1. GST collections (monthly, leading economic indicator)
2. CEA power consumption (daily, industrial activity proxy)
3. Credit ratings (continuous, distress signals)
4. BSE bulk deals (daily, institutional smart money)
5. Promoter pledges (quarterly, distress risk indicator)
"""

from .alternative_state import (
    AlternativeDataState,
    GSTSignalState,
    PowerSignalState,
    CreditSignalState,
    SmartMoneyState,
    PromoterRiskState,
    EconomicActivityRegime,
    SmartMoneySignal
)

from .alternative_feature_block import AlternativeFeatureBlock
from .macro_alternative_bridge import MacroAlternativeBridge
from .valuation_alternative_bridge import ValuationAlternativeBridge
from .risk_alternative_bridge import RiskAlternativeBridge
from .alternative_pipeline_runner import AlternativePipelineRunner, AlternativePipelineResult

__all__ = [
    # State objects
    'AlternativeDataState',
    'GSTSignalState',
    'PowerSignalState',
    'CreditSignalState',
    'SmartMoneyState',
    'PromoterRiskState',
    'EconomicActivityRegime',
    'SmartMoneySignal',
    # Feature block
    'AlternativeFeatureBlock',
    # Bridges
    'MacroAlternativeBridge',
    'ValuationAlternativeBridge',
    'RiskAlternativeBridge',
    # Pipeline runner
    'AlternativePipelineRunner',
    'AlternativePipelineResult'
]
