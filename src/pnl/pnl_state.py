"""
PnLState — Real-time P&L status for UnifiedState

This dataclass provides a snapshot of current P&L status to the rest of the system.
Updated daily by EOD processing and available to risk controller, dashboard, and narrative engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PnLState:
    """Real-time P&L status snapshot"""
    
    # Today's P&L
    pnl_today_inr: float = 0.0
    pnl_today_equity_inr: float = 0.0
    pnl_today_options_inr: float = 0.0
    transaction_costs_today_inr: float = 0.0
    net_pnl_today_inr: float = 0.0
    
    # Running totals
    pnl_mtd_inr: float = 0.0
    pnl_ytd_inr: float = 0.0
    pnl_inception_inr: float = 0.0
    
    # NAV
    current_nav_inr: float = 0.0
    current_nav_per_unit: float = 0.0
    nav_return_since_inception_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    max_drawdown_to_date_pct: float = 0.0
    
    # Fund health
    fund_health: str = "UNKNOWN"  # "ON_TRACK", "WARNING", "BREACH"
    sharpe_ratio_30d: float = 0.0
    
    # Reconciliation
    last_reconciliation_status: str = "UNKNOWN"  # "CLEAN", "WARNING", "CRITICAL"
    last_reconciliation_date: Optional[datetime] = None
    
    # Execution quality
    avg_slippage_bps_30d: float = 0.0
    total_cost_drag_pct: float = 0.0
    
    # Last update
    last_updated: Optional[datetime] = None
    last_eod_processing: Optional[datetime] = None
    
    def to_dict(self):
        """Convert to dict for serialization"""
        return {
            'pnl_today_inr': self.pnl_today_inr,
            'pnl_today_equity_inr': self.pnl_today_equity_inr,
            'pnl_today_options_inr': self.pnl_today_options_inr,
            'transaction_costs_today_inr': self.transaction_costs_today_inr,
            'net_pnl_today_inr': self.net_pnl_today_inr,
            'pnl_mtd_inr': self.pnl_mtd_inr,
            'pnl_ytd_inr': self.pnl_ytd_inr,
            'pnl_inception_inr': self.pnl_inception_inr,
            'current_nav_inr': self.current_nav_inr,
            'current_nav_per_unit': self.current_nav_per_unit,
            'nav_return_since_inception_pct': self.nav_return_since_inception_pct,
            'current_drawdown_pct': self.current_drawdown_pct,
            'max_drawdown_to_date_pct': self.max_drawdown_to_date_pct,
            'fund_health': self.fund_health,
            'sharpe_ratio_30d': self.sharpe_ratio_30d,
            'last_reconciliation_status': self.last_reconciliation_status,
            'last_reconciliation_date': self.last_reconciliation_date.isoformat() if self.last_reconciliation_date else None,
            'avg_slippage_bps_30d': self.avg_slippage_bps_30d,
            'total_cost_drag_pct': self.total_cost_drag_pct,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'last_eod_processing': self.last_eod_processing.isoformat() if self.last_eod_processing else None,
        }
