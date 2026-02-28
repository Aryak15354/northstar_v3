"""
Bounded Exposure Calculator

Calculates exposure with mathematical guarantees:
- Always returns values in [0.0, 1.0]
- Handles NaN → 0.0
- Handles Infinity → 1.0
- Logs all bound violations
"""

import math
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BoundedExposure:
    """
    Result of bounded exposure calculation.
    
    Attributes:
        value: Bounded exposure value, always in [0.0, 1.0]
        raw_value: Unbounded calculation result (for diagnostics)
        was_bounded: True if bounds were applied
        bound_reason: Explanation if bounds were applied
    """
    value: float
    raw_value: float
    was_bounded: bool
    bound_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate that value is properly bounded"""
        assert 0.0 <= self.value <= 1.0, f"BoundedExposure value {self.value} not in [0.0, 1.0]"


class BoundedExposureCalculator:
    """
    Calculates exposure with mathematical guarantees.
    
    All exposure calculations are bounded to [0.0, 1.0] with special handling
    for NaN and infinity values. All bound violations are logged for diagnostics.
    """
    
    def __init__(self):
        """Initialize the calculator"""
        self.violation_count = 0
        logger.info("BoundedExposureCalculator initialized")
    
    def _apply_bounds(self, raw_value: float, context: str = "") -> BoundedExposure:
        """
        Apply bounds to a raw exposure value.
        
        Args:
            raw_value: Unbounded exposure value
            context: Context string for logging
            
        Returns:
            BoundedExposure with value in [0.0, 1.0]
        """
        # Handle NaN
        if math.isnan(raw_value):
            self.violation_count += 1
            reason = f"NaN detected in {context}"
            logger.warning(f"Exposure bound violation: {reason}")
            return BoundedExposure(
                value=0.0,
                raw_value=raw_value,
                was_bounded=True,
                bound_reason=reason
            )
        
        # Handle positive infinity
        if math.isinf(raw_value) and raw_value > 0:
            self.violation_count += 1
            reason = f"Positive infinity detected in {context}"
            logger.warning(f"Exposure bound violation: {reason}")
            return BoundedExposure(
                value=1.0,
                raw_value=raw_value,
                was_bounded=True,
                bound_reason=reason
            )
        
        # Handle negative infinity
        if math.isinf(raw_value) and raw_value < 0:
            self.violation_count += 1
            reason = f"Negative infinity detected in {context}"
            logger.warning(f"Exposure bound violation: {reason}")
            return BoundedExposure(
                value=0.0,
                raw_value=raw_value,
                was_bounded=True,
                bound_reason=reason
            )
        
        # Apply min/max bounds
        bounded_value = max(0.0, min(1.0, raw_value))
        was_bounded = (bounded_value != raw_value)
        
        if was_bounded:
            self.violation_count += 1
            if raw_value < 0.0:
                reason = f"Negative value {raw_value:.6f} bounded to 0.0 in {context}"
            else:
                reason = f"Excessive value {raw_value:.6f} bounded to 1.0 in {context}"
            logger.warning(f"Exposure bound violation: {reason}")
            
            return BoundedExposure(
                value=bounded_value,
                raw_value=raw_value,
                was_bounded=True,
                bound_reason=reason
            )
        
        # Value was already in bounds
        return BoundedExposure(
            value=bounded_value,
            raw_value=raw_value,
            was_bounded=False,
            bound_reason=None
        )
    
    def calculate_allowed_exposure(
        self,
        risk_on: float,
        stress_score: float,
        regime: str
    ) -> BoundedExposure:
        """
        Calculate allowed exposure based on market conditions.
        
        This is the main exposure calculation that combines risk-on sentiment,
        stress levels, and regime information to determine how much capital
        should be allocated to the market.
        
        Args:
            risk_on: Risk-on sentiment [0.0, 1.0]
            stress_score: Market stress level [0.0, 1.0]
            regime: Market regime (e.g., 'expansion', 'contraction')
            
        Returns:
            BoundedExposure with value in [0.0, 1.0]
        """
        context = f"calculate_allowed_exposure(risk_on={risk_on:.3f}, stress={stress_score:.3f}, regime={regime})"
        
        try:
            # Base exposure from risk-on sentiment
            base_exposure = risk_on
            
            # Reduce exposure based on stress
            # High stress (close to 1.0) should reduce exposure significantly
            stress_adjustment = 1.0 - stress_score
            
            # Regime multiplier
            regime_multipliers = {
                'early-expansion': 1.0,
                'late-expansion': 0.9,
                'early-contraction': 0.6,
                'late-contraction': 0.4,
                'unknown': 0.5
            }
            regime_mult = regime_multipliers.get(regime, 0.5)
            
            # Calculate raw exposure
            raw_exposure = base_exposure * stress_adjustment * regime_mult
            
            # Apply bounds
            return self._apply_bounds(raw_exposure, context)
            
        except Exception as e:
            # If calculation fails, return safe default
            logger.error(f"Exposure calculation failed: {e}")
            return BoundedExposure(
                value=0.0,
                raw_value=float('nan'),
                was_bounded=True,
                bound_reason=f"Calculation exception: {e}"
            )
    
    def calculate_risk_scaled_exposure(
        self,
        portfolio_volatility: float,
        target_volatility: float = 0.15
    ) -> BoundedExposure:
        """
        Calculate exposure scaled by portfolio risk.
        
        This scales exposure inversely with portfolio volatility to maintain
        consistent risk levels. If portfolio vol is high, exposure is reduced.
        
        Args:
            portfolio_volatility: Estimated portfolio volatility (annualized)
            target_volatility: Target volatility level (default 15%)
            
        Returns:
            BoundedExposure with value in [0.0, 1.0]
        """
        context = f"calculate_risk_scaled_exposure(vol={portfolio_volatility:.3f}, target={target_volatility:.3f})"
        
        try:
            # Avoid division by zero
            if portfolio_volatility <= 0.0:
                logger.warning(f"Non-positive portfolio volatility: {portfolio_volatility}")
                return BoundedExposure(
                    value=1.0,
                    raw_value=1.0,
                    was_bounded=False,
                    bound_reason=None
                )
            
            # Scale exposure inversely with volatility
            raw_exposure = target_volatility / portfolio_volatility
            
            # Apply bounds
            return self._apply_bounds(raw_exposure, context)
            
        except Exception as e:
            logger.error(f"Risk-scaled exposure calculation failed: {e}")
            return BoundedExposure(
                value=0.5,
                raw_value=float('nan'),
                was_bounded=True,
                bound_reason=f"Calculation exception: {e}"
            )
    
    def combine_exposures(
        self,
        allowed_exposure: float,
        risk_scaled_exposure: float
    ) -> BoundedExposure:
        """
        Combine multiple exposure constraints by taking the minimum.
        
        This implements the conservative principle: when multiple constraints
        exist, use the most restrictive one.
        
        Args:
            allowed_exposure: Exposure allowed by market conditions
            risk_scaled_exposure: Exposure allowed by risk constraints
            
        Returns:
            BoundedExposure with value = min(allowed, risk_scaled)
        """
        context = f"combine_exposures(allowed={allowed_exposure:.3f}, risk_scaled={risk_scaled_exposure:.3f})"
        
        try:
            # Take the minimum (most conservative)
            raw_exposure = min(allowed_exposure, risk_scaled_exposure)
            
            # Apply bounds (should already be bounded, but double-check)
            result = self._apply_bounds(raw_exposure, context)
            
            # Log the decision
            logger.info(
                f"Combined exposure: allowed={allowed_exposure:.1%}, "
                f"risk_scaled={risk_scaled_exposure:.1%}, "
                f"final={result.value:.1%}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Exposure combination failed: {e}")
            return BoundedExposure(
                value=0.0,
                raw_value=float('nan'),
                was_bounded=True,
                bound_reason=f"Calculation exception: {e}"
            )
    
    def get_violation_count(self) -> int:
        """Get total number of bound violations detected"""
        return self.violation_count
    
    def reset_violation_count(self) -> None:
        """Reset the violation counter"""
        self.violation_count = 0
        logger.info("Violation count reset")
