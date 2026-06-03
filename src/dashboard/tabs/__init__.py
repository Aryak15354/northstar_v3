"""
Dashboard tabs module

Each tab is a self-contained module that renders one section of the unified dashboard.
All tabs receive a DashboardDataContract instance and call only its methods.
"""

# Import all tab modules
from . import live_trading
from . import portfolio_governor
from . import intelligence_regime
from . import performance
from . import options_system
from . import system_ops

__all__ = [
    'live_trading',
    'portfolio_governor',
    'intelligence_regime',
    'performance',
    'options_system',
    'system_ops'
]
