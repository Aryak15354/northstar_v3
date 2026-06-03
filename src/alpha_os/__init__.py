"""
Alpha OS - The Operating System for Alpha Generation Strategies

This module provides the governance layer that sits above alpha generation
and enforces the rules of the strategy lifecycle.

Components:
- StrategyRegistry: Single source of truth for all strategies
- StrategyOrchestrator: Runtime strategy weights and signal aggregation
- StrategyTribunal: Facade over Bayesian tribunal with evidence updates
- StrategyLifecycleManager: Complete lifecycle from research to retirement
- StrategyRedundancyDetector: Identifies duplicate strategies
"""

from .strategy_registry import (
    StrategyRegistry,
    StrategyRecord,
    StrategyStatus,
    StrategyFamily,
    StrategyPerformanceRecord
)

from .strategy_orchestrator import StrategyOrchestrator

from .strategy_tribunal import StrategyTribunal

from .strategy_lifecycle import StrategyLifecycleManager, PromotionEvaluationResult

from .strategy_redundancy import StrategyRedundancyDetector, RedundancyCheckResult

from .alpha_os_state import AlphaOSState

__all__ = [
    'StrategyRegistry',
    'StrategyRecord',
    'StrategyStatus',
    'StrategyFamily',
    'StrategyPerformanceRecord',
    'StrategyOrchestrator',
    'StrategyTribunal',
    'StrategyLifecycleManager',
    'PromotionEvaluationResult',
    'StrategyRedundancyDetector',
    'RedundancyCheckResult',
    'AlphaOSState',
]
