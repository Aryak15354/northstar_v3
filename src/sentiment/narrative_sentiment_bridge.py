"""
NarrativeSentimentBridge — Connects SentimentState to the narrative engine.

The narrative engine explains what the market is doing. Without sentiment, it can only
explain price action and fundamentals. With sentiment, it can explain the narrative shift:
"Despite strong fundamentals, news flow has turned cautious — market is pricing in
uncertainty not reflected in earnings."

This bridge is intentionally thin. It takes SentimentState and returns a structured dict
that narrative_engine.py can consume via a new parameter. It does no narrative generation itself.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .sentiment_state import SentimentState, SentimentRegime, SentimentTrend

logger = logging.getLogger(__name__)


@dataclass
class SentimentNarrativeInput:
    """
    Structured sentiment context for the narrative engine.
    
    Designed to be human-readable so the narrative engine can
    incorporate it naturally into generated text.
    """
    regime_label: str              # "Fear", "Panic", "Neutral", "Optimism", "Euphoria"
    trend_label: str               # "Deteriorating", "Stable", "Improving"
    is_diverging_from_price: bool  # True if sentiment and price action disagree
    divergence_description: str    # e.g. "Prices rising but news tone is cautious"
    confidence: float              # How confident is the regime classification
    is_fresh: bool                 # Whether to trust this input or use fallback language
    key_narrative_flag: Optional[str]  # e.g. "SENTIMENT_CRISIS", "EXTREME_OPTIMISM", None


class NarrativeSentimentBridge:
    """
    Bridge between SentimentState and narrative engine.
    
    Translates technical sentiment state into human-readable narrative context.
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize bridge with configuration.
        
        Args:
            config: Configuration dict with narrative_sentiment section
        """
        self.config = config or {}
        narrative_config = self.config.get('narrative_sentiment', {})
        
        # Divergence threshold for flagging
        self.divergence_threshold = narrative_config.get('divergence_threshold', 0.5)
    
    def build_narrative_input(
        self,
        sentiment_state: SentimentState,
        market_state=None
    ) -> SentimentNarrativeInput:
        """
        Translate SentimentState into narrative-ready input.
        
        Args:
            sentiment_state: Current SentimentState from UnifiedState
            market_state: Optional MarketState for price action context
            
        Returns:
            SentimentNarrativeInput ready for narrative engine consumption
        """
        # Check freshness first
        if not sentiment_state.is_fresh:
            return SentimentNarrativeInput(
                regime_label="Unavailable (pipeline stale)",
                trend_label="Unknown",
                is_diverging_from_price=False,
                divergence_description="",
                confidence=0.0,
                is_fresh=False,
                key_narrative_flag=None
            )
        
        # Convert regime to human-readable label
        regime_label = self._format_regime_label(sentiment_state.market_sentiment_regime)
        
        # Convert trend to human-readable label
        trend_label = self._format_trend_label(sentiment_state.sentiment_trend)
        
        # Check for divergence
        is_diverging = sentiment_state.sentiment_divergence > self.divergence_threshold
        
        # Build divergence description
        divergence_description = ""
        if is_diverging and market_state is not None:
            divergence_description = self._build_divergence_description(
                sentiment_state,
                market_state
            )
        
        # Determine key narrative flag
        key_flag = self._determine_narrative_flag(sentiment_state)
        
        return SentimentNarrativeInput(
            regime_label=regime_label,
            trend_label=trend_label,
            is_diverging_from_price=is_diverging,
            divergence_description=divergence_description,
            confidence=sentiment_state.regime_confidence,
            is_fresh=True,
            key_narrative_flag=key_flag
        )
    
    def _format_regime_label(self, regime: SentimentRegime) -> str:
        """Convert SentimentRegime enum to human-readable label."""
        labels = {
            SentimentRegime.PANIC: "Panic",
            SentimentRegime.FEAR: "Fear",
            SentimentRegime.NEUTRAL: "Neutral",
            SentimentRegime.OPTIMISM: "Optimism",
            SentimentRegime.EUPHORIA: "Euphoria",
            SentimentRegime.UNAVAILABLE: "Unavailable"
        }
        return labels.get(regime, "Unknown")
    
    def _format_trend_label(self, trend: SentimentTrend) -> str:
        """Convert SentimentTrend enum to human-readable label."""
        labels = {
            SentimentTrend.DETERIORATING: "Deteriorating",
            SentimentTrend.STABLE: "Stable",
            SentimentTrend.IMPROVING: "Improving",
            SentimentTrend.UNKNOWN: "Unknown"
        }
        return labels.get(trend, "Unknown")
    
    def _build_divergence_description(
        self,
        sentiment_state: SentimentState,
        market_state
    ) -> str:
        """
        Build human-readable divergence description.
        
        Args:
            sentiment_state: Current sentiment state
            market_state: Current market state
            
        Returns:
            Human-readable divergence description
        """
        # Determine price direction
        if hasattr(market_state, 'nifty_return_5d'):
            price_rising = market_state.nifty_return_5d > 0
        else:
            price_rising = True  # Default assumption
        
        # Determine sentiment direction
        sentiment_improving = sentiment_state.sentiment_momentum_1w > 0
        
        if price_rising and not sentiment_improving:
            return "Prices rising but news tone is cautious"
        elif not price_rising and sentiment_improving:
            return "Prices falling but news tone is improving"
        elif not price_rising and not sentiment_improving:
            return "Both prices and sentiment declining together"
        else:
            return "Prices and sentiment aligned"
    
    def _determine_narrative_flag(self, sentiment_state: SentimentState) -> Optional[str]:
        """
        Determine key narrative flag for special conditions.
        
        Args:
            sentiment_state: Current sentiment state
            
        Returns:
            Narrative flag string or None
        """
        regime = sentiment_state.market_sentiment_regime
        trend = sentiment_state.sentiment_trend
        
        # Crisis conditions
        if regime == SentimentRegime.PANIC:
            return "SENTIMENT_CRISIS"
        
        # Extreme optimism
        if regime == SentimentRegime.EUPHORIA:
            return "EXTREME_OPTIMISM"
        
        # Deteriorating into fear
        if regime == SentimentRegime.FEAR and trend == SentimentTrend.DETERIORATING:
            return "SENTIMENT_DETERIORATING"
        
        # No special flag
        return None
