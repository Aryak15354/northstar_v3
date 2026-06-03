"""
Unified P&L Ledger System for Northstar V3

This module provides institutional-grade P&L accounting with:
- Immutable append-only ledger (double-entry bookkeeping)
- Properly compounding NAV calculation
- P&L attribution by strategy, regime, and sector
- Automated reconciliation across books
- Execution quality measurement
- Paper fund management with benchmark comparison
"""

from .ledger import UnifiedPnLLedger, LedgerEntry, LedgerEntryType, LedgerBook
from .pnl_state import PnLState
from .nav_calculator import NAVCalculator
from .attribution import PnLAttributor
from .reconciliation import PnLReconciler
from .execution_quality import ExecutionQualityMonitor
from .paper_fund import PaperFundManager

__all__ = [
    'UnifiedPnLLedger',
    'LedgerEntry',
    'LedgerEntryType',
    'LedgerBook',
    'PnLState',
    'NAVCalculator',
    'PnLAttributor',
    'PnLReconciler',
    'ExecutionQualityMonitor',
    'PaperFundManager',
]
