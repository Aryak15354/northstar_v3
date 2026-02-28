"""
Regime Detection Engine for Options Trading System

Classifies current options market regime based on:
- IV percentile rank (252-day history)
- IV trend (5-day vs 20-day MA)
- Volatility-of-volatility
- Skew
- Underlying equity regime (from Northstar v3)

Regimes determine which strategies are appropriate.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Tuple
from enum import Enum
from dataclasses import dataclass

from src.options.config_loader import RegimeConfig

logger = logging.getLogger("options.regime")


class Regime(Enum):
    """Options market regime types"""
    LOW_VOL_SELL = "low_vol_sell"          # IV rank > 70%, stable vol
    HIGH_VOL_SELL = "high_vol_sell"        # IV rank > 80%, elevated vol
    RISING_VOL_BUY = "rising_vol_buy"      # IV rank < 30%, vol expanding
    NEUTRAL = "neutral"                     # No clear regime
    CRASH_HEDGE = "crash_hedge"             # Extreme conditions or equity crisis


@dataclass
class RegimeMetrics:
    """Metrics used for regime detection"""
    current_iv: float
    iv_rank: float                    # Percentile rank (0-1)
    iv_position: float                # Min-max normalized (0-1)
    iv_trend: str                     # "rising", "falling", "stable"
    iv_5d_ma: float
    iv_20d_ma: float
    skew: float                       # (OTM put IV - ATM IV) / ATM IV
    vol_of_vol_elevated: bool         # std(iv_5d) > 1.5 * std(iv_20d)
    underlying_regime: Optional[str]  # From Northstar v3
    days_in_regime: int


@dataclass
class RegimeState:
    """Current regime state"""
    regime: Regime
    metrics: RegimeMetrics
    timestamp: datetime
    confidence: float                 # 0-1, how confident we are
    reason: str                       # Why this regime was selected


class RegimeDetector:
    """
    Detects options market regime based on volatility metrics
    
    Implements:
    - IV percentile rank calculation (252-day history)
    - IV position (min-max normalized)
    - IV trend analysis (5-day vs 20-day MA)
    - Skew calculation
    - Vol-of-vol check
    - Regime persistence tracking
    - Integration with equity regime
    """
    
    def __init__(self, config: RegimeConfig):
        """
        Initialize regime detector
        
        Args:
            config: Regime detection configuration
        """
        self.config = config
        self.regime_history: list = []  # List of (timestamp, regime) tuples
        
        logger.info("RegimeDetector initialized")
    
    def detect_regime(
        self,
        option_chain: pd.DataFrame,
        iv_history: pd.Series,
        underlying_regime: Optional[str] = None
    ) -> RegimeState:
        """
        Detect current options market regime
        
        Args:
            option_chain: Current option chain data
            iv_history: Historical IV data (252+ days)
            underlying_regime: Current equity regime from Northstar v3
        
        Returns:
            RegimeState with detected regime and metrics
        """
        logger.info("Detecting options market regime")
        
        # Calculate metrics
        metrics = self._calculate_metrics(option_chain, iv_history, underlying_regime)
        
        # Determine regime
        regime, confidence, reason = self._classify_regime(metrics)
        
        # Update regime history
        self._update_regime_history(regime)
        
        # Get days in current regime
        metrics.days_in_regime = self._get_days_in_regime(regime)
        
        state = RegimeState(
            regime=regime,
            metrics=metrics,
            timestamp=datetime.utcnow(),
            confidence=confidence,
            reason=reason
        )
        
        logger.info(f"Detected regime: {regime.value} (confidence: {confidence:.2f}, days: {metrics.days_in_regime})")
        logger.info(f"Reason: {reason}")
        
        return state
    
    def _calculate_metrics(
        self,
        option_chain: pd.DataFrame,
        iv_history: pd.Series,
        underlying_regime: Optional[str]
    ) -> RegimeMetrics:
        """Calculate all regime detection metrics"""
        
        # Get current ATM IV
        current_iv = self._get_atm_iv(option_chain)
        
        # Calculate IV percentile rank
        iv_rank = self.calculate_iv_rank(current_iv, iv_history)
        
        # Calculate IV position (min-max normalized)
        iv_position = self._calculate_iv_position(current_iv, iv_history)
        
        # Calculate IV trend
        iv_5d_ma = iv_history.tail(5).mean() if len(iv_history) >= 5 else current_iv
        iv_20d_ma = iv_history.tail(20).mean() if len(iv_history) >= 20 else current_iv
        iv_trend = self._classify_iv_trend(iv_5d_ma, iv_20d_ma)
        
        # Calculate skew
        skew = self.calculate_skew(option_chain)
        
        # Check vol-of-vol
        vol_of_vol_elevated = self.check_vol_of_vol(iv_history)
        
        return RegimeMetrics(
            current_iv=current_iv,
            iv_rank=iv_rank,
            iv_position=iv_position,
            iv_trend=iv_trend,
            iv_5d_ma=iv_5d_ma,
            iv_20d_ma=iv_20d_ma,
            skew=skew,
            vol_of_vol_elevated=vol_of_vol_elevated,
            underlying_regime=underlying_regime,
            days_in_regime=0  # Will be updated
        )
    
    def _get_atm_iv(self, option_chain: pd.DataFrame) -> float:
        """
        Get ATM implied volatility
        
        Uses average of ATM call and put IV
        """
        if option_chain.empty:
            raise ValueError("Empty option chain")
        
        spot = option_chain['underlying_price'].iloc[0]
        
        # Find ATM strike (closest to spot)
        option_chain['distance_to_atm'] = abs(option_chain['strike'] - spot)
        atm_strike = option_chain.loc[option_chain['distance_to_atm'].idxmin(), 'strike']
        
        # Get ATM options
        atm_options = option_chain[option_chain['strike'] == atm_strike]
        
        if atm_options.empty:
            # Fallback: use median IV
            return option_chain['iv'].median()
        
        # Average call and put IV
        atm_iv = atm_options['iv'].mean()
        
        logger.debug(f"ATM IV: {atm_iv:.4f} (strike: {atm_strike})")
        
        return atm_iv
    
    def calculate_iv_rank(self, current_iv: float, iv_history: pd.Series) -> float:
        """
        Calculate IV percentile rank
        
        Ranks current IV against historical IV (252-day lookback)
        Returns percentile (0-1)
        
        Args:
            current_iv: Current IV
            iv_history: Historical IV series
        
        Returns:
            Percentile rank (0-1)
        """
        if len(iv_history) < self.config.iv_rank_lookback_days:
            logger.warning(f"Insufficient IV history ({len(iv_history)} days, need {self.config.iv_rank_lookback_days})")
            # Use available data
            lookback = iv_history
        else:
            lookback = iv_history.tail(self.config.iv_rank_lookback_days)
        
        # Calculate percentile rank
        rank = (lookback < current_iv).sum() / len(lookback)
        
        logger.debug(f"IV rank: {rank:.2%} (current: {current_iv:.4f}, lookback: {len(lookback)} days)")
        
        return rank
    
    def _calculate_iv_position(self, current_iv: float, iv_history: pd.Series) -> float:
        """
        Calculate IV position (min-max normalized)
        
        Formula: (current_iv - min_iv) / (max_iv - min_iv)
        Returns 0-1
        """
        if len(iv_history) < self.config.iv_rank_lookback_days:
            lookback = iv_history
        else:
            lookback = iv_history.tail(self.config.iv_rank_lookback_days)
        
        min_iv = lookback.min()
        max_iv = lookback.max()
        
        if max_iv == min_iv:
            return 0.5  # Neutral if no range
        
        position = (current_iv - min_iv) / (max_iv - min_iv)
        position = np.clip(position, 0, 1)
        
        logger.debug(f"IV position: {position:.2%} (min: {min_iv:.4f}, max: {max_iv:.4f})")
        
        return position
    
    def _classify_iv_trend(self, iv_5d_ma: float, iv_20d_ma: float) -> str:
        """
        Classify IV trend
        
        Returns: "rising", "falling", or "stable"
        """
        diff_pct = (iv_5d_ma - iv_20d_ma) / iv_20d_ma
        
        if diff_pct > 0.05:  # 5% above
            return "rising"
        elif diff_pct < -0.05:  # 5% below
            return "falling"
        else:
            return "stable"
    
    def calculate_skew(self, option_chain: pd.DataFrame) -> float:
        """
        Calculate volatility skew
        
        Formula: (OTM put IV - ATM IV) / ATM IV
        
        Positive skew = fear (puts more expensive)
        Negative skew = complacency (calls more expensive)
        
        Args:
            option_chain: Option chain data
        
        Returns:
            Skew value
        """
        if option_chain.empty:
            return 0.0
        
        spot = option_chain['underlying_price'].iloc[0]
        
        # Find ATM strike
        option_chain['distance_to_atm'] = abs(option_chain['strike'] - spot)
        atm_strike = option_chain.loc[option_chain['distance_to_atm'].idxmin(), 'strike']
        
        # Get ATM IV
        atm_options = option_chain[option_chain['strike'] == atm_strike]
        if atm_options.empty:
            return 0.0
        atm_iv = atm_options['iv'].mean()
        
        # Find OTM put (10-15 delta, ~1 std dev below spot)
        otm_put_strike = spot * 0.95  # Approx 5% OTM
        put_options = option_chain[
            (option_chain['option_type'] == 'P') &
            (option_chain['strike'] <= otm_put_strike)
        ]
        
        if put_options.empty:
            return 0.0
        
        # Get closest OTM put
        put_options['distance'] = abs(put_options['strike'] - otm_put_strike)
        otm_put_iv = put_options.loc[put_options['distance'].idxmin(), 'iv']
        
        # Calculate skew
        skew = (otm_put_iv - atm_iv) / atm_iv if atm_iv > 0 else 0.0
        
        logger.debug(f"Skew: {skew:.4f} (ATM IV: {atm_iv:.4f}, OTM put IV: {otm_put_iv:.4f})")
        
        return skew
    
    def check_vol_of_vol(self, iv_history: pd.Series) -> bool:
        """
        Check if volatility-of-volatility is elevated
        
        Formula: std(iv_5d) > threshold * std(iv_20d)
        
        Elevated vol-of-vol indicates unstable volatility regime.
        Blocks short-vol strategies.
        
        Args:
            iv_history: Historical IV series
        
        Returns:
            True if vol-of-vol is elevated
        """
        if len(iv_history) < 20:
            logger.warning("Insufficient data for vol-of-vol check")
            return False
        
        # Calculate rolling standard deviations
        iv_5d_std = iv_history.tail(5).std()
        iv_20d_std = iv_history.tail(20).std()
        
        if iv_20d_std == 0:
            return False
        
        ratio = iv_5d_std / iv_20d_std
        elevated = ratio > self.config.vol_of_vol_threshold
        
        logger.debug(f"Vol-of-vol: {ratio:.2f} (threshold: {self.config.vol_of_vol_threshold}, elevated: {elevated})")
        
        return elevated
    
    def _classify_regime(self, metrics: RegimeMetrics) -> Tuple[Regime, float, str]:
        """
        Classify regime based on metrics
        
        Returns: (regime, confidence, reason)
        """
        # Check for equity crisis first (highest priority)
        if metrics.underlying_regime == "CRISIS":
            return (
                Regime.CRASH_HEDGE,
                1.0,
                "Underlying equity regime is CRISIS - correlation risk extreme"
            )
        
        # Check for vol-of-vol elevation (blocks short-vol)
        if metrics.vol_of_vol_elevated:
            if metrics.iv_rank < self.config.thresholds['rising_vol_buy_iv_rank']:
                return (
                    Regime.RISING_VOL_BUY,
                    0.8,
                    f"Vol-of-vol elevated + low IV rank ({metrics.iv_rank:.1%})"
                )
            else:
                return (
                    Regime.NEUTRAL,
                    0.6,
                    f"Vol-of-vol elevated - short-vol blocked"
                )
        
        # HIGH_VOL_SELL: IV rank > 80%, vol elevated but stable
        if metrics.iv_rank > self.config.thresholds['high_vol_sell_iv_rank']:
            if metrics.iv_trend == "falling":
                return (
                    Regime.HIGH_VOL_SELL,
                    0.9,
                    f"High IV rank ({metrics.iv_rank:.1%}) + falling trend"
                )
            else:
                return (
                    Regime.HIGH_VOL_SELL,
                    0.7,
                    f"High IV rank ({metrics.iv_rank:.1%})"
                )
        
        # LOW_VOL_SELL: IV rank > 70%, stable vol
        if metrics.iv_rank > self.config.thresholds['low_vol_sell_iv_rank']:
            if metrics.iv_trend == "stable" or metrics.iv_trend == "falling":
                return (
                    Regime.LOW_VOL_SELL,
                    0.85,
                    f"Elevated IV rank ({metrics.iv_rank:.1%}) + {metrics.iv_trend} trend"
                )
            else:
                return (
                    Regime.NEUTRAL,
                    0.5,
                    f"IV rank elevated ({metrics.iv_rank:.1%}) but rising - wait for stability"
                )
        
        # RISING_VOL_BUY: IV rank < 30%, vol expanding
        if metrics.iv_rank < self.config.thresholds['rising_vol_buy_iv_rank']:
            if metrics.iv_trend == "rising":
                return (
                    Regime.RISING_VOL_BUY,
                    0.9,
                    f"Low IV rank ({metrics.iv_rank:.1%}) + rising trend"
                )
            else:
                return (
                    Regime.RISING_VOL_BUY,
                    0.7,
                    f"Low IV rank ({metrics.iv_rank:.1%})"
                )
        
        # NEUTRAL: No clear regime
        return (
            Regime.NEUTRAL,
            0.5,
            f"IV rank in neutral zone ({metrics.iv_rank:.1%})"
        )
    
    def _update_regime_history(self, regime: Regime) -> None:
        """Update regime history"""
        self.regime_history.append((datetime.utcnow(), regime))
        
        # Keep only recent history (90 days)
        cutoff = datetime.utcnow() - timedelta(days=90)
        self.regime_history = [
            (ts, r) for ts, r in self.regime_history
            if ts > cutoff
        ]
    
    def _get_days_in_regime(self, current_regime: Regime) -> int:
        """
        Get number of consecutive days in current regime
        
        Returns:
            Days in current regime
        """
        if not self.regime_history:
            return 0
        
        days = 0
        for ts, regime in reversed(self.regime_history):
            if regime == current_regime:
                days += 1
            else:
                break
        
        return days
    
    def check_regime_persistence(self, regime: Regime) -> bool:
        """
        Check if regime has persisted long enough for trading
        
        Args:
            regime: Regime to check
        
        Returns:
            True if regime has persisted >= required days
        """
        days_in_regime = self._get_days_in_regime(regime)
        required_days = self.config.regime_persistence_days
        
        persistent = days_in_regime >= required_days
        
        logger.debug(f"Regime persistence: {days_in_regime} days (required: {required_days}, persistent: {persistent})")
        
        return persistent


if __name__ == "__main__":
    # Test regime detector
    import logging
    from src.options.config_loader import get_config
    
    logging.basicConfig(level=logging.INFO)
    
    config = get_config()
    detector = RegimeDetector(config.regime_detection)
    
    # Create sample data
    np.random.seed(42)
    
    # Sample option chain
    strikes = np.arange(25000, 26500, 50)
    spot = 25867
    
    option_data = []
    for strike in strikes:
        # Simple IV smile
        moneyness = strike / spot
        base_iv = 0.15
        iv = base_iv + 0.05 * (1 - moneyness)**2
        
        option_data.append({
            'strike': strike,
            'option_type': 'C',
            'iv': iv,
            'underlying_price': spot
        })
        option_data.append({
            'strike': strike,
            'option_type': 'P',
            'iv': iv * 1.1,  # Put skew
            'underlying_price': spot
        })
    
    option_chain = pd.DataFrame(option_data)
    
    # Sample IV history (252 days)
    iv_history = pd.Series(np.random.normal(0.15, 0.03, 252))
    iv_history = iv_history.clip(0.05, 0.40)
    
    # Detect regime
    state = detector.detect_regime(option_chain, iv_history, underlying_regime="NORMAL")
    
    print(f"\nDetected Regime: {state.regime.value}")
    print(f"Confidence: {state.confidence:.2%}")
    print(f"Reason: {state.reason}")
    print(f"\nMetrics:")
    print(f"  IV Rank: {state.metrics.iv_rank:.2%}")
    print(f"  IV Position: {state.metrics.iv_position:.2%}")
    print(f"  IV Trend: {state.metrics.iv_trend}")
    print(f"  Skew: {state.metrics.skew:.4f}")
    print(f"  Vol-of-Vol Elevated: {state.metrics.vol_of_vol_elevated}")
