"""
🧠 MARKET BRAIN - INSTITUTIONAL GRADE MARKET INTELLIGENCE
Northstar V3 Market Brain Integration

This module adds causal understanding, regime memory, and market pulse
to the existing Northstar v3 intelligence stack.

Components:
- Market Tensor: Unified market sensory system
- Causal Graph: Market nervous system (what moves what)
- Regime Memory: Historical pattern recognition
- Market Pulse: Real-time force detection
- Survival Instincts: System stress monitoring

Integration Points:
- Feeds into existing Market State Spine
- Enhances Bayesian Engine with causal relationships
- Extends Memory Engine with regime patterns
- Upgrades Opportunity Surface with pulse detection
"""

__version__ = "1.0.0"
__author__ = "Northstar Intelligence Team"

from .market_tensor import MarketTensorEngine
try:
    from .causal_graph import CausalGraphEngine
except Exception:
    CausalGraphEngine = None
from .regime_memory import RegimeMemoryEngine
from .market_pulse import MarketPulseEngine
from .survival_instincts import SurvivalInstinctEngine

__all__ = ['MarketTensorEngine', 'RegimeMemoryEngine', 'MarketPulseEngine', 'SurvivalInstinctEngine']
if CausalGraphEngine is not None:
    __all__.append('CausalGraphEngine')
