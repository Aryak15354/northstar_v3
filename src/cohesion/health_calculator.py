"""
Health Calculator - Meaningful System Health Metrics

Calculates system health as a weighted combination of:
- Data Freshness (40%): How recent are the canonical state files
- Market Consistency (30%): Alignment between allowed and actual exposure
- Portfolio Stability (30%): Recent portfolio turnover

Formula: overall_health = 0.4 * data_freshness + 0.3 * market_consistency + 0.3 * portfolio_stability

Note: The "zero component < 50%" property cannot be satisfied with a weighted sum formula
when components sum to 1.0. We prioritize data freshness with 40% weight.
"""

import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

from src.cohesion.state_file_manager import StateFileManager

logger = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    """
    System health metrics.
    
    Attributes:
        overall_health: Weighted combination of components [0.0, 1.0]
        data_freshness: How recent the data is [0.0, 1.0]
        market_consistency: Alignment between market and portfolio [0.0, 1.0]
        portfolio_stability: Stability of portfolio weights [0.0, 1.0]
        components: Detailed breakdown of calculations
    """
    overall_health: float
    data_freshness: float
    market_consistency: float
    portfolio_stability: float
    components: Dict[str, Any]
    
    def __post_init__(self):
        """Validate health metrics are in valid ranges"""
        assert 0.0 <= self.overall_health <= 1.0, f"overall_health {self.overall_health} not in [0.0, 1.0]"
        assert 0.0 <= self.data_freshness <= 1.0, f"data_freshness {self.data_freshness} not in [0.0, 1.0]"
        assert 0.0 <= self.market_consistency <= 1.0, f"market_consistency {self.market_consistency} not in [0.0, 1.0]"
        assert 0.0 <= self.portfolio_stability <= 1.0, f"portfolio_stability {self.portfolio_stability} not in [0.0, 1.0]"


class HealthCalculator:
    """
    Calculates meaningful system health metrics.
    
    Health is calculated as a weighted combination:
    - Data Freshness: 40% weight
    - Market Consistency: 30% weight
    - Portfolio Stability: 30% weight
    """
    
    # Weights for health calculation
    FRESHNESS_WEIGHT = 0.4
    CONSISTENCY_WEIGHT = 0.3
    STABILITY_WEIGHT = 0.3
    
    # Thresholds
    MAX_AGE_MINUTES = 60  # Data older than 1 hour is considered stale
    EXPOSURE_TOLERANCE = 0.05  # 5% tolerance for exposure mismatch
    HIGH_TURNOVER_THRESHOLD = 0.5  # 50% turnover is considered high
    
    def __init__(self, state_manager: Optional[StateFileManager] = None):
        """
        Initialize the health calculator.
        
        Args:
            state_manager: StateFileManager instance (creates new if None)
        """
        self.state_manager = state_manager or StateFileManager()
        logger.info("HealthCalculator initialized")
    
    def _get_file_age_minutes(self, file_path: Path) -> float:
        """
        Get age of file in minutes.
        
        Args:
            file_path: Path to file
            
        Returns:
            Age in minutes, or infinity if file doesn't exist
        """
        if not file_path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return float('inf')
        
        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
        age = (datetime.now() - file_time).total_seconds() / 60.0
        return age
    
    def _calculate_data_freshness(self) -> tuple[float, Dict[str, Any]]:
        """
        Calculate data freshness score.
        
        Freshness is based on the age of canonical state files.
        Files older than MAX_AGE_MINUTES get a score of 0.
        
        Returns:
            Tuple of (freshness_score, components_dict)
        """
        # Get ages of critical files
        market_age = self._get_file_age_minutes(self.state_manager.MARKET_STATE_PATH)
        portfolio_age = self._get_file_age_minutes(self.state_manager.PORTFOLIO_WEIGHTS_PATH)
        risk_age = self._get_file_age_minutes(self.state_manager.RISK_STATE_PATH)
        
        # Use the oldest file age (most conservative)
        max_age = max(market_age, portfolio_age, risk_age)
        
        # Calculate freshness score
        if max_age == float('inf'):
            freshness = 0.0
        else:
            # Linear decay from 1.0 to 0.0 over MAX_AGE_MINUTES
            freshness = max(0.0, 1.0 - (max_age / self.MAX_AGE_MINUTES))
        
        components = {
            'market_state_age_minutes': market_age,
            'portfolio_age_minutes': portfolio_age,
            'risk_age_minutes': risk_age,
            'max_age_minutes': max_age,
            'threshold_minutes': self.MAX_AGE_MINUTES
        }
        
        logger.debug(f"Data freshness: {freshness:.2%} (max_age={max_age:.1f}min)")
        return freshness, components
    
    def _calculate_market_consistency(self) -> tuple[float, Dict[str, Any]]:
        """
        Calculate market consistency score.
        
        Consistency measures alignment between allowed exposure (from market brain)
        and actual exposure (from portfolio).
        
        Returns:
            Tuple of (consistency_score, components_dict)
        """
        try:
            # Read market state and portfolio
            market_state = self.state_manager.read_market_state()
            portfolio_weights = self.state_manager.read_portfolio_weights()
            
            # Get latest values
            allowed_exposure = market_state['allowed_exposure'].iloc[-1]
            actual_exposure = portfolio_weights['exposure'].sum()
            
            # Calculate alignment
            divergence = abs(allowed_exposure - actual_exposure)
            
            # Consistency score: 1.0 when perfectly aligned, 0.0 when divergence >= tolerance
            if divergence <= self.EXPOSURE_TOLERANCE:
                consistency = 1.0 - (divergence / self.EXPOSURE_TOLERANCE)
            else:
                consistency = 0.0
            
            components = {
                'allowed_exposure': allowed_exposure,
                'actual_exposure': actual_exposure,
                'divergence': divergence,
                'tolerance': self.EXPOSURE_TOLERANCE
            }
            
            logger.debug(
                f"Market consistency: {consistency:.2%} "
                f"(allowed={allowed_exposure:.1%}, actual={actual_exposure:.1%})"
            )
            return consistency, components
            
        except FileNotFoundError as e:
            logger.warning(f"Cannot calculate market consistency: {e}")
            return 0.0, {'error': str(e)}
        except Exception as e:
            logger.error(f"Market consistency calculation failed: {e}")
            return 0.0, {'error': str(e)}
    
    def _calculate_portfolio_stability(self, lookback_days: int = 5) -> tuple[float, Dict[str, Any]]:
        """
        Calculate portfolio stability score.
        
        Stability measures recent portfolio turnover. High turnover indicates
        instability and gets a low score.
        
        Args:
            lookback_days: Number of days to look back for turnover calculation
            
        Returns:
            Tuple of (stability_score, components_dict)
        """
        try:
            # Read portfolio weights
            portfolio_weights = self.state_manager.read_portfolio_weights()
            
            if len(portfolio_weights) == 0:
                logger.warning("Empty portfolio weights")
                return 0.0, {'error': 'Empty portfolio'}
            
            # Get unique dates
            dates = sorted(portfolio_weights['date'].unique())
            
            if len(dates) < 2:
                # Not enough history to calculate turnover
                logger.debug("Insufficient history for stability calculation")
                return 1.0, {'turnover': 0.0, 'note': 'Insufficient history'}
            
            # Calculate turnover over lookback period
            recent_dates = dates[-min(lookback_days, len(dates)):]
            
            total_turnover = 0.0
            for i in range(1, len(recent_dates)):
                prev_date = recent_dates[i-1]
                curr_date = recent_dates[i]
                
                # Get weights for each date
                prev_weights = portfolio_weights[portfolio_weights['date'] == prev_date].set_index('symbol')['weight']
                curr_weights = portfolio_weights[portfolio_weights['date'] == curr_date].set_index('symbol')['weight']
                
                # Align weights (fill missing with 0)
                all_symbols = set(prev_weights.index) | set(curr_weights.index)
                prev_aligned = pd.Series({s: prev_weights.get(s, 0.0) for s in all_symbols})
                curr_aligned = pd.Series({s: curr_weights.get(s, 0.0) for s in all_symbols})
                
                # Turnover is sum of absolute weight changes
                turnover = (curr_aligned - prev_aligned).abs().sum()
                total_turnover += turnover
            
            # Average turnover per day
            avg_turnover = total_turnover / (len(recent_dates) - 1)
            
            # Stability score: 1.0 when no turnover, 0.0 when turnover >= threshold
            if avg_turnover <= self.HIGH_TURNOVER_THRESHOLD:
                stability = 1.0 - (avg_turnover / self.HIGH_TURNOVER_THRESHOLD)
            else:
                stability = 0.0
            
            components = {
                'avg_daily_turnover': avg_turnover,
                'lookback_days': len(recent_dates) - 1,
                'threshold': self.HIGH_TURNOVER_THRESHOLD
            }
            
            logger.debug(f"Portfolio stability: {stability:.2%} (turnover={avg_turnover:.1%})")
            return stability, components
            
        except FileNotFoundError as e:
            logger.warning(f"Cannot calculate portfolio stability: {e}")
            return 0.0, {'error': str(e)}
        except Exception as e:
            logger.error(f"Portfolio stability calculation failed: {e}")
            return 0.0, {'error': str(e)}
    
    def calculate_system_health(self) -> HealthMetrics:
        """
        Calculate overall system health.
        
        Health is a weighted combination of:
        - Data Freshness (40%)
        - Market Consistency (30%)
        - Portfolio Stability (30%)
        
        Returns:
            HealthMetrics with overall health and component scores
        """
        # Calculate component scores
        data_freshness, freshness_components = self._calculate_data_freshness()
        market_consistency, consistency_components = self._calculate_market_consistency()
        portfolio_stability, stability_components = self._calculate_portfolio_stability()
        
        # Calculate weighted overall health
        overall_health = (
            self.FRESHNESS_WEIGHT * data_freshness +
            self.CONSISTENCY_WEIGHT * market_consistency +
            self.STABILITY_WEIGHT * portfolio_stability
        )
        
        # Combine all components
        all_components = {
            'freshness': freshness_components,
            'consistency': consistency_components,
            'stability': stability_components,
            'weights': {
                'freshness': self.FRESHNESS_WEIGHT,
                'consistency': self.CONSISTENCY_WEIGHT,
                'stability': self.STABILITY_WEIGHT
            }
        }
        
        # Log health status
        logger.info(
            f"System Health: {overall_health:.1%} "
            f"(freshness={data_freshness:.1%}, "
            f"consistency={market_consistency:.1%}, "
            f"stability={portfolio_stability:.1%})"
        )
        
        return HealthMetrics(
            overall_health=overall_health,
            data_freshness=data_freshness,
            market_consistency=market_consistency,
            portfolio_stability=portfolio_stability,
            components=all_components
        )
