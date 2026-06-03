"""
Unified Regime Detection Engine for Volatility Trading

Consolidates regime detection from:
- src/processing/market_regime.py: Market breadth, participation, correlation
- src/processing/options_regime.py: Options-specific regime classification
- src/options/options_regime_detector.py: IV-based regime detection with percentile ranks
- src/intelligence/regime_aware_specialists.py: Macro regime detection

Provides single authoritative regime classification for the unified volatility engine.

Regime Types:
- LOW_VOL: Low volatility environment, suitable for premium selling
- HIGH_VOL: Elevated volatility, suitable for premium selling
- CRISIS: Extreme volatility, defensive positioning only
- TRANSITION: Regime change in progress, reduce exposure

Key Features:
- Probabilistic regime classification with confidence scores
- Multi-factor regime detection (breadth, IV rank, correlation, skew)
- Regime history tracking and transition detection
- Integration with market state and options metrics
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Volatility regime classifications for options trading"""
    LOW_VOL = "low_vol"           # IV rank < 30%, stable vol - premium selling
    HIGH_VOL = "high_vol"         # IV rank > 70%, elevated but stable - premium selling
    CRISIS = "crisis"             # IV rank > 80% + vol-of-vol elevated - defensive only
    TRANSITION = "transition"     # Regime change in progress - reduce exposure


@dataclass
class RegimeMetrics:
    """Metrics used for regime detection"""
    # Market metrics
    breadth: float                    # Fraction above EMA(200)
    participation: float              # Fraction near highs
    market_correlation: float         # Average correlation to market
    market_volatility: float          # Daily market volatility
    
    # Options metrics
    iv_rank: float                    # IV percentile rank (0-1)
    iv_trend: str                     # "rising", "falling", "stable"
    skew: float                       # Put-call skew
    vol_of_vol_elevated: bool         # Volatility of volatility flag
    
    # Composite scores
    risk_on_score: float              # 0-1, higher = more risk-on
    regime_confidence: float          # 0-1, confidence in classification


@dataclass
class RegimeState:
    """Current regime state with full context"""
    regime: VolatilityRegime
    metrics: RegimeMetrics
    timestamp: datetime
    confidence: float                 # 0-1, overall confidence
    days_in_regime: int              # Consecutive days in current regime
    transition_probability: Dict[VolatilityRegime, float]  # Transition probabilities
    reason: str                       # Human-readable classification reason


class RegimeDetector:
    """
    Unified regime detector for volatility trading
    
    Implements:
    - Market regime detection (breadth, participation, correlation)
    - IV-based regime classification (percentile rank, trend, skew)
    - Vol-of-vol monitoring for instability detection
    - Regime persistence tracking
    - Probabilistic regime transitions
    
    System Laws:
    - R1: Regime changes require 3+ days persistence (avoid whipsaws)
    - R2: CRISIS regime has absolute priority (safety first)
    - R3: Vol-of-vol elevation blocks premium selling (protect capital)
    - R4: Regime confidence must exceed 0.6 for trading (quality threshold)
    """
    
    def __init__(
        self,
        iv_rank_lookback: int = 252,
        vol_of_vol_threshold: float = 1.5,
        persistence_days: int = 3,
        confidence_threshold: float = 0.6
    ):
        """
        Initialize regime detector
        
        Args:
            iv_rank_lookback: Days for IV percentile rank calculation
            vol_of_vol_threshold: Threshold for vol-of-vol elevation
            persistence_days: Days required for regime confirmation
            confidence_threshold: Minimum confidence for trading
        """
        self.iv_rank_lookback = iv_rank_lookback
        self.vol_of_vol_threshold = vol_of_vol_threshold
        self.persistence_days = persistence_days
        self.confidence_threshold = confidence_threshold
        
        # Regime history: list of (timestamp, regime) tuples
        self.regime_history: List[Tuple[datetime, VolatilityRegime]] = []
        
        logger.info(
            f"RegimeDetector initialized: lookback={iv_rank_lookback}, "
            f"vol_of_vol_threshold={vol_of_vol_threshold}, "
            f"persistence={persistence_days} days"
        )
    
    def detect_regime(
        self,
        market_data: pd.DataFrame,
        iv_history: pd.Series,
        option_chain: Optional[pd.DataFrame] = None,
        current_time: Optional[datetime] = None
    ) -> RegimeState:
        """
        Detect current volatility regime
        
        Args:
            market_data: Market regime data with columns:
                - breadth, participation, volatility, correlation, risk_on_score
            iv_history: Historical IV series (252+ days recommended)
            option_chain: Current option chain for skew calculation (optional)
            current_time: Current timestamp (defaults to now)
        
        Returns:
            RegimeState with detected regime and full context
        """
        if current_time is None:
            current_time = datetime.utcnow()
        
        logger.info(f"Detecting regime at {current_time}")
        
        # Calculate metrics
        metrics = self._calculate_metrics(market_data, iv_history, option_chain)
        
        # Classify regime
        regime, confidence, reason = self._classify_regime(metrics)
        
        # Update regime history
        self._update_regime_history(regime, current_time)
        
        # Get days in current regime
        days_in_regime = self._get_days_in_regime(regime)
        
        # Calculate transition probabilities
        transition_probs = self._calculate_transition_probabilities(metrics)
        
        state = RegimeState(
            regime=regime,
            metrics=metrics,
            timestamp=current_time,
            confidence=confidence,
            days_in_regime=days_in_regime,
            transition_probability=transition_probs,
            reason=reason
        )
        
        logger.info(
            f"Regime: {regime.value}, confidence: {confidence:.2f}, "
            f"days: {days_in_regime}, reason: {reason}"
        )
        
        return state
    
    def _calculate_metrics(
        self,
        market_data: pd.DataFrame,
        iv_history: pd.Series,
        option_chain: Optional[pd.DataFrame]
    ) -> RegimeMetrics:
        """Calculate all regime detection metrics"""
        
        # Get latest market metrics
        if not market_data.empty:
            latest_market = market_data.iloc[-1]
            breadth = float(latest_market.get('breadth', 0.5))
            participation = float(latest_market.get('participation', 0.5))
            market_correlation = float(latest_market.get('correlation', 0.5))
            market_volatility = float(latest_market.get('volatility', 0.015))
            risk_on_score = float(latest_market.get('risk_on_score', 0.5))
        else:
            # Fallback to neutral values
            breadth = 0.5
            participation = 0.5
            market_correlation = 0.5
            market_volatility = 0.015
            risk_on_score = 0.5
        
        # Calculate IV metrics
        current_iv = float(iv_history.iloc[-1]) if not iv_history.empty else 0.20
        iv_rank = self._calculate_iv_rank(current_iv, iv_history)
        iv_trend = self._classify_iv_trend(iv_history)
        vol_of_vol_elevated = self._check_vol_of_vol(iv_history)
        
        # Calculate skew if option chain available
        if option_chain is not None and not option_chain.empty:
            skew = self._calculate_skew(option_chain)
        else:
            skew = 0.0
        
        # Calculate regime confidence based on metric consistency
        regime_confidence = self._calculate_regime_confidence(
            breadth, participation, iv_rank, market_volatility
        )
        
        return RegimeMetrics(
            breadth=breadth,
            participation=participation,
            market_correlation=market_correlation,
            market_volatility=market_volatility,
            iv_rank=iv_rank,
            iv_trend=iv_trend,
            skew=skew,
            vol_of_vol_elevated=vol_of_vol_elevated,
            risk_on_score=risk_on_score,
            regime_confidence=regime_confidence
        )
    
    def _calculate_iv_rank(self, current_iv: float, iv_history: pd.Series) -> float:
        """
        Calculate IV percentile rank
        
        Returns percentile (0-1) of current IV vs historical distribution
        """
        if len(iv_history) < 2:
            return 0.5  # Neutral if insufficient data
        
        # Use configured lookback or available data
        lookback = min(self.iv_rank_lookback, len(iv_history))
        recent_history = iv_history.tail(lookback)
        
        # Calculate percentile rank
        rank = float((recent_history < current_iv).sum()) / len(recent_history)
        
        logger.debug(
            f"IV rank: {rank:.2%} (current: {current_iv:.4f}, "
            f"lookback: {lookback} days)"
        )
        
        return rank
    
    def _classify_iv_trend(self, iv_history: pd.Series) -> str:
        """
        Classify IV trend: rising, falling, or stable
        
        Compares 5-day MA vs 20-day MA
        """
        if len(iv_history) < 20:
            return "stable"
        
        iv_5d = float(iv_history.tail(5).mean())
        iv_20d = float(iv_history.tail(20).mean())
        
        diff_pct = (iv_5d - iv_20d) / iv_20d if iv_20d > 0 else 0.0
        
        if diff_pct > 0.05:
            return "rising"
        elif diff_pct < -0.05:
            return "falling"
        else:
            return "stable"
    
    def _check_vol_of_vol(self, iv_history: pd.Series) -> bool:
        """
        Check if volatility-of-volatility is elevated
        
        Elevated vol-of-vol indicates unstable regime - blocks premium selling
        """
        if len(iv_history) < 20:
            return False
        
        iv_5d_std = float(iv_history.tail(5).std())
        iv_20d_std = float(iv_history.tail(20).std())
        
        if iv_20d_std == 0:
            return False
        
        ratio = iv_5d_std / iv_20d_std
        elevated = ratio > self.vol_of_vol_threshold
        
        logger.debug(
            f"Vol-of-vol: {ratio:.2f} (threshold: {self.vol_of_vol_threshold}, "
            f"elevated: {elevated})"
        )
        
        return elevated
    
    def _calculate_skew(self, option_chain: pd.DataFrame) -> float:
        """
        Calculate volatility skew: (OTM put IV - ATM IV) / ATM IV
        
        Positive skew = fear (puts expensive)
        Negative skew = complacency (calls expensive)
        """
        if option_chain.empty or 'strike' not in option_chain.columns:
            return 0.0
        
        try:
            spot = float(option_chain['underlying_price'].iloc[0])
            
            # Find ATM strike
            option_chain['distance_to_atm'] = abs(option_chain['strike'] - spot)
            atm_strike = option_chain.loc[
                option_chain['distance_to_atm'].idxmin(), 'strike'
            ]
            
            # Get ATM IV
            atm_options = option_chain[option_chain['strike'] == atm_strike]
            if atm_options.empty:
                return 0.0
            atm_iv = float(atm_options['iv'].mean())
            
            # Find OTM put (5% below spot)
            otm_put_strike = spot * 0.95
            put_options = option_chain[
                (option_chain['option_type'] == 'P') &
                (option_chain['strike'] <= otm_put_strike)
            ]
            
            if put_options.empty:
                return 0.0
            
            # Get closest OTM put IV
            put_options['distance'] = abs(put_options['strike'] - otm_put_strike)
            otm_put_iv = float(
                put_options.loc[put_options['distance'].idxmin(), 'iv']
            )
            
            # Calculate skew
            skew = (otm_put_iv - atm_iv) / atm_iv if atm_iv > 0 else 0.0
            
            logger.debug(
                f"Skew: {skew:.4f} (ATM IV: {atm_iv:.4f}, "
                f"OTM put IV: {otm_put_iv:.4f})"
            )
            
            return skew
            
        except Exception as e:
            logger.warning(f"Skew calculation failed: {e}")
            return 0.0
    
    def _calculate_regime_confidence(
        self,
        breadth: float,
        participation: float,
        iv_rank: float,
        volatility: float
    ) -> float:
        """
        Calculate confidence in regime classification
        
        Higher confidence when metrics are consistent and extreme
        """
        # Check metric consistency
        market_metrics = [breadth, participation]
        market_consistency = 1.0 - float(np.std(market_metrics))
        
        # Check metric extremity (distance from neutral 0.5)
        extremity = abs(iv_rank - 0.5) * 2  # 0-1 scale
        
        # Combine factors
        confidence = 0.6 * market_consistency + 0.4 * extremity
        
        return float(np.clip(confidence, 0, 1))
    
    def _classify_regime(
        self,
        metrics: RegimeMetrics
    ) -> Tuple[VolatilityRegime, float, str]:
        """
        Classify regime based on metrics
        
        Returns: (regime, confidence, reason)
        
        Priority order (System Law R2):
        1. CRISIS: IV rank > 80% + vol-of-vol elevated
        2. HIGH_VOL: IV rank > 70%, stable vol
        3. LOW_VOL: IV rank < 30%, stable vol
        4. TRANSITION: Regime change in progress
        """
        # CRISIS: Highest priority (System Law R2)
        if metrics.iv_rank > 0.80 and metrics.vol_of_vol_elevated:
            return (
                VolatilityRegime.CRISIS,
                0.95,
                f"IV rank {metrics.iv_rank:.1%} + vol-of-vol elevated - "
                f"defensive only"
            )
        
        # Vol-of-vol elevation blocks premium selling (System Law R3)
        if metrics.vol_of_vol_elevated:
            return (
                VolatilityRegime.TRANSITION,
                0.70,
                f"Vol-of-vol elevated - unstable regime, reduce exposure"
            )
        
        # HIGH_VOL: Premium selling opportunity
        if metrics.iv_rank > 0.70:
            if metrics.iv_trend == "falling" or metrics.iv_trend == "stable":
                return (
                    VolatilityRegime.HIGH_VOL,
                    0.85 * metrics.regime_confidence,
                    f"High IV rank {metrics.iv_rank:.1%}, {metrics.iv_trend} trend - "
                    f"premium selling"
                )
            else:
                return (
                    VolatilityRegime.TRANSITION,
                    0.60,
                    f"IV rank {metrics.iv_rank:.1%} but rising - "
                    f"wait for stability"
                )
        
        # LOW_VOL: Premium selling opportunity (lower premium)
        if metrics.iv_rank < 0.30:
            if metrics.iv_trend == "stable" or metrics.iv_trend == "falling":
                return (
                    VolatilityRegime.LOW_VOL,
                    0.80 * metrics.regime_confidence,
                    f"Low IV rank {metrics.iv_rank:.1%}, {metrics.iv_trend} trend - "
                    f"modest premium selling"
                )
            else:
                return (
                    VolatilityRegime.TRANSITION,
                    0.55,
                    f"IV rank {metrics.iv_rank:.1%} but rising - "
                    f"potential regime change"
                )
        
        # TRANSITION: Neutral zone or unclear regime
        return (
            VolatilityRegime.TRANSITION,
            0.50,
            f"IV rank in neutral zone {metrics.iv_rank:.1%} - "
            f"no clear regime"
        )
    
    def _update_regime_history(
        self,
        regime: VolatilityRegime,
        timestamp: datetime
    ) -> None:
        """Update regime history"""
        self.regime_history.append((timestamp, regime))
        
        # Keep only recent history (90 days)
        cutoff = timestamp - timedelta(days=90)
        self.regime_history = [
            (ts, r) for ts, r in self.regime_history if ts > cutoff
        ]
    
    def _get_days_in_regime(self, current_regime: VolatilityRegime) -> int:
        """Get number of consecutive days in current regime"""
        if not self.regime_history:
            return 0
        
        days = 0
        for _, regime in reversed(self.regime_history):
            if regime == current_regime:
                days += 1
            else:
                break
        
        return days
    
    def _calculate_transition_probabilities(
        self,
        metrics: RegimeMetrics
    ) -> Dict[VolatilityRegime, float]:
        """
        Calculate regime transition probabilities
        
        Based on current metrics and typical regime transitions
        """
        # Initialize uniform probabilities
        probs = {regime: 0.25 for regime in VolatilityRegime}
        
        # Adjust based on IV rank
        if metrics.iv_rank > 0.80:
            probs[VolatilityRegime.CRISIS] = 0.50
            probs[VolatilityRegime.HIGH_VOL] = 0.30
        elif metrics.iv_rank > 0.70:
            probs[VolatilityRegime.HIGH_VOL] = 0.50
            probs[VolatilityRegime.CRISIS] = 0.20
        elif metrics.iv_rank < 0.30:
            probs[VolatilityRegime.LOW_VOL] = 0.50
            probs[VolatilityRegime.TRANSITION] = 0.30
        else:
            probs[VolatilityRegime.TRANSITION] = 0.50
        
        # Adjust for vol-of-vol
        if metrics.vol_of_vol_elevated:
            probs[VolatilityRegime.TRANSITION] += 0.20
            probs[VolatilityRegime.CRISIS] += 0.10
        
        # Normalize to sum to 1.0
        total = sum(probs.values())
        probs = {regime: prob / total for regime, prob in probs.items()}
        
        return probs
    
    def check_regime_persistence(self, regime: VolatilityRegime) -> bool:
        """
        Check if regime has persisted long enough for trading (System Law R1)
        
        Args:
            regime: Regime to check
        
        Returns:
            True if regime has persisted >= required days
        """
        days_in_regime = self._get_days_in_regime(regime)
        persistent = days_in_regime >= self.persistence_days
        
        logger.debug(
            f"Regime persistence: {days_in_regime} days "
            f"(required: {self.persistence_days}, persistent: {persistent})"
        )
        
        return persistent
    
    def is_tradeable_regime(self, state: RegimeState) -> bool:
        """
        Check if regime is suitable for trading (System Law R4)
        
        Requires:
        - Confidence >= threshold
        - Persistence >= required days
        - Not in CRISIS (unless explicitly allowed)
        
        Args:
            state: Current regime state
        
        Returns:
            True if regime is tradeable
        """
        # Check confidence threshold
        if state.confidence < self.confidence_threshold:
            logger.info(
                f"Regime not tradeable: confidence {state.confidence:.2f} "
                f"< threshold {self.confidence_threshold}"
            )
            return False
        
        # Check persistence
        if not self.check_regime_persistence(state.regime):
            logger.info(
                f"Regime not tradeable: persistence {state.days_in_regime} days "
                f"< required {self.persistence_days}"
            )
            return False
        
        # CRISIS regime blocks trading (System Law R2)
        if state.regime == VolatilityRegime.CRISIS:
            logger.info("Regime not tradeable: CRISIS regime - defensive only")
            return False
        
        return True
