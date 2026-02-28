"""
Intelligence Engine Implementation for Northstar V3 System Cohesion

This module implements the intelligence engine with correctness laws that enforce
regime consistency, signal decay validation, and intelligence state consistency.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from enum import Enum

from src.service_interfaces import IIntelligenceEngine, ValidationResult, IStateManager
from src.unified_state_manager import AuthorityLevel

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classifications"""
    NORMAL = "Normal"
    CRISIS = "Crisis"
    RECOVERY = "Recovery"
    BUBBLE = "Bubble"
    BEAR_MARKET = "Bear_Market"
    BULL_MARKET = "Bull_Market"

class SignalType(Enum):
    """Types of investment signals"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    CARRY = "carry"
    VOLATILITY = "volatility"
    QUALITY = "quality"
    VALUE = "value"

@dataclass
class IntelligenceState:
    """Complete intelligence state representation"""
    market_regime: MarketRegime
    regime_confidence: float
    risk_on_probability: float
    volatility_regime: str
    market_stress: float
    breadth_metrics: Dict[str, float]
    signal_strengths: Dict[SignalType, float]
    strategy_allocations: Dict[str, float]
    timestamp: datetime
    version: int
    data_sources: List[str] = field(default_factory=list)
    
    def validate_consistency(self) -> ValidationResult:
        """Validate intelligence state consistency"""
        errors = []
        warnings = []
        
        # Check probability bounds
        if not (0.0 <= self.regime_confidence <= 1.0):
            errors.append(f"Regime confidence {self.regime_confidence} not in [0,1]")
        
        if not (0.0 <= self.risk_on_probability <= 1.0):
            errors.append(f"Risk-on probability {self.risk_on_probability} not in [0,1]")
        
        # Check signal strengths
        for signal_type, strength in self.signal_strengths.items():
            if not (-1.0 <= strength <= 1.0):
                errors.append(f"Signal strength {strength} for {signal_type} not in [-1,1]")
        
        # Check strategy allocations sum to 1
        total_allocation = sum(self.strategy_allocations.values())
        if abs(total_allocation - 1.0) > 0.01:  # 1% tolerance
            errors.append(f"Strategy allocations sum to {total_allocation:.3f}, not 1.0")
        
        # Check regime consistency with allocations
        if self.market_regime == MarketRegime.CRISIS:
            momentum_allocation = self.strategy_allocations.get('momentum', 0.0)
            if momentum_allocation > 0.20:  # 20% max momentum in crisis
                warnings.append(f"High momentum allocation {momentum_allocation:.1%} in crisis regime")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

@dataclass
class SignalHistory:
    """Historical signal performance tracking"""
    signal_type: SignalType
    timestamps: List[datetime]
    values: List[float]
    information_coefficients: List[float]
    decay_rates: List[float]
    
    def calculate_signal_decay(self, lookback_days: int = 180) -> float:
        """Calculate signal decay over time"""
        if len(self.information_coefficients) < 2:
            return 0.0
        
        # Find ICs within lookback period
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_ics = []
        recent_timestamps = []
        
        for i, timestamp in enumerate(self.timestamps):
            if timestamp >= cutoff_date:
                recent_ics.append(self.information_coefficients[i])
                recent_timestamps.append(timestamp)
        
        if len(recent_ics) < 2:
            return 0.0
        
        # Calculate decay rate (negative slope indicates decay)
        days_from_start = [(ts - recent_timestamps[0]).days for ts in recent_timestamps]
        
        # Simple linear regression
        n = len(recent_ics)
        sum_x = sum(days_from_start)
        sum_y = sum(recent_ics)
        sum_xy = sum(x * y for x, y in zip(days_from_start, recent_ics))
        sum_x2 = sum(x * x for x in days_from_start)
        
        if n * sum_x2 - sum_x * sum_x == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        return slope

class IntelligenceEngine(IIntelligenceEngine):
    """
    Intelligence engine with correctness laws.
    
    Implements the intelligence system invariants:
    - Regime Consistency (I1)
    - Signal Decay Enforcement (I2)
    - Intelligence State Consistency (I3)
    """
    
    def __init__(self, state_manager: IStateManager):
        self.state_manager = state_manager
        self.current_intelligence_state = IntelligenceState(
            market_regime=MarketRegime.NORMAL,
            regime_confidence=0.5,
            risk_on_probability=0.5,
            volatility_regime="Normal",
            market_stress=0.0,
            breadth_metrics={},
            signal_strengths={signal: 0.0 for signal in SignalType},
            strategy_allocations={
                'momentum': 0.25,
                'mean_reversion': 0.25,
                'carry': 0.25,
                'volatility': 0.25
            },
            timestamp=datetime.now(),
            version=1
        )
        
        self.signal_histories: Dict[SignalType, SignalHistory] = {}
        self.regime_history: List[Tuple[datetime, MarketRegime, float]] = []
        
        # Initialize signal histories
        for signal_type in SignalType:
            self.signal_histories[signal_type] = SignalHistory(
                signal_type=signal_type,
                timestamps=[],
                values=[],
                information_coefficients=[],
                decay_rates=[]
            )
    
    def update_market_regime(self, 
                           market_data: pd.DataFrame, 
                           as_of: datetime) -> Dict[str, Any]:
        """
        Update market regime assessment.
        
        Implements Property 17: Regime Consistency (I1)
        """
        try:
            # Calculate market metrics
            volatility = self._calculate_volatility(market_data)
            breadth = self._calculate_market_breadth(market_data)
            stress = self._calculate_market_stress(market_data)
            
            # Determine regime
            new_regime = self._classify_regime(volatility, breadth, stress)
            regime_confidence = self._calculate_regime_confidence(volatility, breadth, stress)
            
            # Calculate risk-on probability
            risk_on_prob = self._calculate_risk_on_probability(new_regime, volatility, breadth)
            
            # Update intelligence state
            old_state = self.current_intelligence_state
            
            self.current_intelligence_state = IntelligenceState(
                market_regime=new_regime,
                regime_confidence=regime_confidence,
                risk_on_probability=risk_on_prob,
                volatility_regime=self._classify_volatility_regime(volatility),
                market_stress=stress,
                breadth_metrics={
                    'advance_decline': breadth.get('advance_decline', 0.0),
                    'new_highs_lows': breadth.get('new_highs_lows', 0.0),
                    'sector_rotation': breadth.get('sector_rotation', 0.0)
                },
                signal_strengths=self.current_intelligence_state.signal_strengths.copy(),
                strategy_allocations=self._calculate_regime_allocations(new_regime),
                timestamp=as_of,
                version=old_state.version + 1,
                data_sources=['market_data']
            )
            
            # Validate consistency
            validation_result = self.current_intelligence_state.validate_consistency()
            if not validation_result.is_valid:
                logger.error(f"Intelligence state consistency violation: {validation_result.errors}")
                # Revert to previous state
                self.current_intelligence_state = old_state
                return old_state.__dict__
            
            # Update regime history
            self.regime_history.append((as_of, new_regime, regime_confidence))
            
            # Update state manager
            state_dict = self.current_intelligence_state.__dict__.copy()
            
            # Convert enums to strings for serialization
            state_dict['market_regime'] = state_dict['market_regime'].value
            state_dict['signal_strengths'] = {
                signal_type.value: strength 
                for signal_type, strength in state_dict['signal_strengths'].items()
            }
            
            self.state_manager.update_state(
                component='intelligence',
                updates=state_dict,
                authority=AuthorityLevel.SYSTEM,
                reason=f"Market regime update: {new_regime.value}",
                timestamp=as_of
            )
            
            logger.info(f"Market regime updated to {new_regime.value} with {regime_confidence:.1%} confidence")
            
            return self.current_intelligence_state.__dict__
            
        except Exception as e:
            logger.error(f"Error updating market regime: {e}")
            return self.current_intelligence_state.__dict__
    
    def get_strategy_allocations(self, 
                               market_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Get strategy allocations for market state.
        
        Implements Property 17: Regime Consistency (I1)
        """
        # Handle both 'regime' and 'market_regime' keys for compatibility
        regime_value = market_state.get('market_regime') or market_state.get('regime', 'Normal')
        
        # Convert string to enum if needed
        if isinstance(regime_value, str):
            regime = MarketRegime(regime_value)
        else:
            regime = regime_value
            
        return self._calculate_regime_allocations(regime)
    
    def validate_signal_consistency(self) -> ValidationResult:
        """
        Validate signal consistency across time.
        
        Implements Property 18: Signal Decay Enforcement (I2)
        """
        errors = []
        warnings = []
        
        for signal_type, history in self.signal_histories.items():
            if len(history.information_coefficients) >= 2:
                # Check for signal decay
                decay_rate = history.calculate_signal_decay()
                
                # Signals should lose power over time (negative decay is expected)
                if decay_rate > 0.01:  # Positive decay indicates strengthening over time (suspicious)
                    warnings.append(
                        f"Signal {signal_type.value} shows strengthening over time "
                        f"(decay rate: {decay_rate:.4f}) - possible overfitting"
                    )
                
                # Check for unrealistic IC values
                max_ic = max(history.information_coefficients)
                if max_ic > 0.20:  # 20% IC is very high
                    warnings.append(
                        f"Signal {signal_type.value} has very high IC {max_ic:.3f} - "
                        f"verify for overfitting"
                    )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def detect_overfitting(self, 
                         signal_history: pd.DataFrame) -> ValidationResult:
        """
        Detect potential overfitting in signals.
        
        Implements Property 18: Signal Decay Enforcement (I2)
        """
        errors = []
        warnings = []
        
        if len(signal_history) < 60:  # Need at least 60 data points
            warnings.append("Insufficient data for overfitting detection")
            return ValidationResult(is_valid=True, errors=[], warnings=warnings)
        
        # Calculate rolling information coefficients
        window_size = 30
        rolling_ics = []
        
        for i in range(window_size, len(signal_history)):
            window_data = signal_history.iloc[i-window_size:i]
            if 'signal' in window_data.columns and 'returns' in window_data.columns:
                ic = window_data['signal'].corr(window_data['returns'])
                if not np.isnan(ic):
                    rolling_ics.append(ic)
        
        if len(rolling_ics) < 2:
            warnings.append("Insufficient valid IC calculations")
            return ValidationResult(is_valid=True, errors=[], warnings=warnings)
        
        # Check for decay over time
        early_ics = rolling_ics[:len(rolling_ics)//3]  # First third
        late_ics = rolling_ics[-len(rolling_ics)//3:]  # Last third
        
        early_mean = np.mean(early_ics)
        late_mean = np.mean(late_ics)
        
        # Signal should decay over time
        if late_mean >= early_mean:
            warnings.append(
                f"Signal does not show expected decay: "
                f"early IC {early_mean:.3f} vs late IC {late_mean:.3f}"
            )
        
        # Check for excessive stability (sign of overfitting)
        ic_std = np.std(rolling_ics)
        if ic_std < 0.01:  # Very stable IC might indicate overfitting
            warnings.append(
                f"Signal shows excessive stability (std: {ic_std:.4f}) - "
                f"possible overfitting"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def update_signal_strength(self, 
                             signal_type: SignalType, 
                             strength: float, 
                             information_coefficient: float,
                             timestamp: datetime = None) -> bool:
        """
        Update signal strength with validation.
        
        Implements Property 18: Signal Decay Enforcement (I2)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Validate signal strength bounds
        if not (-1.0 <= strength <= 1.0):
            logger.error(f"Invalid signal strength {strength} for {signal_type}")
            return False
        
        # Update signal history
        history = self.signal_histories[signal_type]
        history.timestamps.append(timestamp)
        history.values.append(strength)
        history.information_coefficients.append(information_coefficient)
        
        # Calculate decay rate
        decay_rate = history.calculate_signal_decay()
        history.decay_rates.append(decay_rate)
        
        # Update current state
        self.current_intelligence_state.signal_strengths[signal_type] = strength
        self.current_intelligence_state.version += 1
        self.current_intelligence_state.timestamp = timestamp
        
        # Validate signal consistency
        validation_result = self.validate_signal_consistency()
        if validation_result.warnings:
            for warning in validation_result.warnings:
                logger.warning(f"Signal consistency warning: {warning}")
        
        return True
    
    def _calculate_volatility(self, market_data: pd.DataFrame) -> float:
        """Calculate market volatility"""
        if 'returns' in market_data.columns and len(market_data) > 1:
            return float(market_data['returns'].std() * np.sqrt(252))  # Annualized
        return 0.15  # Default volatility
    
    def _calculate_market_breadth(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate market breadth metrics"""
        breadth = {
            'advance_decline': 0.0,
            'new_highs_lows': 0.0,
            'sector_rotation': 0.0
        }
        
        if 'advances' in market_data.columns and 'declines' in market_data.columns:
            total_stocks = market_data['advances'].iloc[-1] + market_data['declines'].iloc[-1]
            if total_stocks > 0:
                breadth['advance_decline'] = market_data['advances'].iloc[-1] / total_stocks
        
        return breadth
    
    def _calculate_market_stress(self, market_data: pd.DataFrame) -> float:
        """Calculate market stress indicator"""
        if 'vix' in market_data.columns:
            return float(market_data['vix'].iloc[-1] / 100.0)  # Normalize VIX
        return 0.0
    
    def _classify_regime(self, volatility: float, breadth: Dict[str, float], stress: float) -> MarketRegime:
        """Classify market regime based on metrics"""
        if stress > 0.35 or volatility > 0.30:
            return MarketRegime.CRISIS
        elif volatility < 0.10 and breadth.get('advance_decline', 0.5) > 0.7:
            return MarketRegime.BULL_MARKET
        elif volatility > 0.25 and breadth.get('advance_decline', 0.5) < 0.3:
            return MarketRegime.BEAR_MARKET
        else:
            return MarketRegime.NORMAL
    
    def _calculate_regime_confidence(self, volatility: float, breadth: Dict[str, float], stress: float) -> float:
        """Calculate confidence in regime classification"""
        # Simple confidence based on how extreme the metrics are
        vol_confidence = min(volatility / 0.30, 1.0) if volatility > 0.20 else 0.5
        stress_confidence = min(stress / 0.35, 1.0) if stress > 0.20 else 0.5
        breadth_confidence = abs(breadth.get('advance_decline', 0.5) - 0.5) * 2
        
        return np.mean([vol_confidence, stress_confidence, breadth_confidence])
    
    def _calculate_risk_on_probability(self, regime: MarketRegime, volatility: float, breadth: Dict[str, float]) -> float:
        """Calculate risk-on probability"""
        base_prob = {
            MarketRegime.CRISIS: 0.1,
            MarketRegime.BEAR_MARKET: 0.2,
            MarketRegime.NORMAL: 0.5,
            MarketRegime.RECOVERY: 0.7,
            MarketRegime.BULL_MARKET: 0.8,
            MarketRegime.BUBBLE: 0.9
        }.get(regime, 0.5)
        
        # Adjust based on breadth
        breadth_adj = (breadth.get('advance_decline', 0.5) - 0.5) * 0.4
        
        return max(0.0, min(1.0, base_prob + breadth_adj))
    
    def _classify_volatility_regime(self, volatility: float) -> str:
        """Classify volatility regime"""
        if volatility < 0.10:
            return "Low"
        elif volatility < 0.20:
            return "Normal"
        elif volatility < 0.30:
            return "High"
        else:
            return "Extreme"
    
    def _calculate_regime_allocations(self, regime: MarketRegime) -> Dict[str, float]:
        """
        Calculate strategy allocations based on regime.
        
        Implements Property 17: Regime Consistency (I1)
        """
        allocations = {
            MarketRegime.CRISIS: {
                'momentum': 0.10,      # Low momentum in crisis
                'mean_reversion': 0.30,
                'carry': 0.20,
                'volatility': 0.40     # High vol strategies in crisis
            },
            MarketRegime.BEAR_MARKET: {
                'momentum': 0.15,
                'mean_reversion': 0.35,
                'carry': 0.25,
                'volatility': 0.25
            },
            MarketRegime.NORMAL: {
                'momentum': 0.25,
                'mean_reversion': 0.25,
                'carry': 0.25,
                'volatility': 0.25
            },
            MarketRegime.BULL_MARKET: {
                'momentum': 0.40,      # High momentum in bull market
                'mean_reversion': 0.20,
                'carry': 0.25,
                'volatility': 0.15
            },
            MarketRegime.RECOVERY: {
                'momentum': 0.35,
                'mean_reversion': 0.25,
                'carry': 0.25,
                'volatility': 0.15
            },
            MarketRegime.BUBBLE: {
                'momentum': 0.20,      # Reduce momentum in bubble
                'mean_reversion': 0.40,
                'carry': 0.20,
                'volatility': 0.20
            }
        }
        
        return allocations.get(regime, allocations[MarketRegime.NORMAL])
    
    def get_intelligence_state(self) -> Dict[str, Any]:
        """Get current intelligence state"""
        return self.current_intelligence_state.__dict__
    
    def get_regime_history(self, lookback_days: int = 30) -> List[Dict[str, Any]]:
        """Get regime history for specified period"""
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        
        return [
            {
                'timestamp': timestamp,
                'regime': regime.value,
                'confidence': confidence
            }
            for timestamp, regime, confidence in self.regime_history
            if timestamp >= cutoff_date
        ]
    
    def initialize(self) -> bool:
        """Initialize the intelligence engine"""
        try:
            # Validate initial state
            validation_result = self.current_intelligence_state.validate_consistency()
            if not validation_result.is_valid:
                logger.error(f"Initial intelligence state invalid: {validation_result.errors}")
                return False
            
            logger.info("Intelligence engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize intelligence engine: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown the intelligence engine"""
        logger.info("Intelligence engine shutdown")
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get intelligence engine health status"""
        # Check signal health
        healthy_signals = sum(
            1 for history in self.signal_histories.values()
            if len(history.information_coefficients) > 0 and 
            abs(history.information_coefficients[-1]) < 0.30  # Not too extreme
        )
        
        # Check state consistency
        state_validation = self.current_intelligence_state.validate_consistency()
        
        return {
            'healthy': state_validation.is_valid and healthy_signals >= len(SignalType) // 2,
            'current_regime': self.current_intelligence_state.market_regime.value,
            'regime_confidence': self.current_intelligence_state.regime_confidence,
            'healthy_signals': healthy_signals,
            'total_signals': len(SignalType),
            'state_errors': len(state_validation.errors),
            'message': f"Intelligence engine: {self.current_intelligence_state.market_regime.value} regime"
        }