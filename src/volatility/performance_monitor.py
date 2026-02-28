"""
Performance Monitoring and Attribution for Unified Volatility Engine

Implements real-time P&L tracking with:
- Greeks P&L decomposition (Delta, Gamma, Vega, Theta contributions)
- Realized vs implied volatility tracking
- Variance P&L computation
- Performance attribution (alpha vs beta)
- Regime-conditional performance analysis
- Performance degradation detection

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque

from .greeks_aggregator import Position, PortfolioGreeks, Greeks

logger = logging.getLogger(__name__)


@dataclass
class GreeksPnL:
    """P&L decomposition by Greeks"""
    delta_pnl: float  # P&L from delta exposure
    gamma_pnl: float  # P&L from gamma exposure
    vega_pnl: float   # P&L from vega exposure
    theta_pnl: float  # P&L from theta decay
    total_pnl: float  # Total P&L
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class VariancePnL:
    """Variance P&L tracking"""
    position_id: str
    realized_variance: float  # Actual variance from price moves
    implied_variance: float   # Variance paid in option premium
    variance_pnl: float       # P&L from variance difference
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceAttribution:
    """Performance attribution analysis"""
    alpha: float  # Strategy skill (excess return)
    beta: float   # Market exposure
    total_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RegimePerformance:
    """Regime-conditional performance statistics"""
    regime: str
    total_return: float
    sharpe_ratio: float
    win_rate: float
    num_trades: int
    avg_return: float


@dataclass
class PerformanceDegradation:
    """Performance degradation alert"""
    metric: str
    current_value: float
    historical_avg: float
    deviation_pct: float
    severity: str  # 'LOW', 'MEDIUM', 'HIGH'
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)


class PerformanceMonitor:
    """
    Real-time performance monitoring and attribution.
    
    Implements:
    - Real-time P&L tracking with Greeks decomposition
    - Realized vs implied volatility tracking
    - Performance attribution (alpha/beta separation)
    - Regime-conditional performance analysis
    - Performance degradation detection
    
    Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7
    """
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        
        # P&L tracking
        self.pnl_history: deque = deque(maxlen=history_size)
        self.greeks_pnl_history: deque = deque(maxlen=history_size)
        self.variance_pnl_history: deque = deque(maxlen=history_size)
        
        # Performance tracking
        self.returns_history: deque = deque(maxlen=history_size)
        self.attribution_history: deque = deque(maxlen=history_size)
        
        # Regime-conditional tracking
        self.regime_performance: Dict[str, List[float]] = {}
        
        # Position tracking for variance P&L
        self.position_entry_data: Dict[str, Dict] = {}
        
        logger.info("Initialized PerformanceMonitor")
    
    def compute_greeks_pnl(
        self,
        current_greeks: PortfolioGreeks,
        previous_greeks: PortfolioGreeks,
        spot_change: float,
        vol_change: float,
        time_elapsed_days: float
    ) -> GreeksPnL:
        """
        Compute P&L decomposition into Greeks contributions.
        
        Requirements: 14.1
        """
        # Delta P&L: delta * spot_change
        delta_pnl = previous_greeks.delta * spot_change
        
        # Gamma P&L: 0.5 * gamma * spot_change^2
        gamma_pnl = 0.5 * previous_greeks.gamma * (spot_change ** 2)
        
        # Vega P&L: vega * vol_change (vega is per 1% vol change)
        vega_pnl = previous_greeks.vega * vol_change * 100
        
        # Theta P&L: theta * time_elapsed
        theta_pnl = previous_greeks.theta * time_elapsed_days
        
        # Total P&L
        total_pnl = delta_pnl + gamma_pnl + vega_pnl + theta_pnl
        
        greeks_pnl = GreeksPnL(
            delta_pnl=delta_pnl,
            gamma_pnl=gamma_pnl,
            vega_pnl=vega_pnl,
            theta_pnl=theta_pnl,
            total_pnl=total_pnl
        )
        
        self.greeks_pnl_history.append(greeks_pnl)
        
        return greeks_pnl
    
    def track_variance_pnl(
        self,
        position: Position,
        price_history: List[float],
        entry_iv: float
    ) -> VariancePnL:
        """
        Track realized vs implied volatility and compute variance P&L.
        
        Requirements: 14.2
        """
        # Compute realized variance from price history
        if len(price_history) < 2:
            realized_variance = 0.0
        else:
            returns = np.diff(np.log(price_history))
            realized_variance = np.var(returns) * 252  # Annualized
        
        # Implied variance from entry IV
        implied_variance = entry_iv ** 2
        
        # Variance P&L: (realized - implied) * vega * quantity
        # Simplified: variance difference scaled by position size
        variance_diff = realized_variance - implied_variance
        
        # Approximate variance P&L
        # In practice, this would be computed from actual hedging P&L
        variance_pnl = variance_diff * abs(position.quantity) * position.spot_price * 0.01
        
        var_pnl = VariancePnL(
            position_id=position.position_id,
            realized_variance=realized_variance,
            implied_variance=implied_variance,
            variance_pnl=variance_pnl
        )
        
        self.variance_pnl_history.append(var_pnl)
        
        return var_pnl
    
    def compute_performance_attribution(
        self,
        portfolio_returns: List[float],
        market_returns: List[float],
        risk_free_rate: float = 0.05
    ) -> PerformanceAttribution:
        """
        Separate alpha (strategy skill) from beta (market exposure).
        
        Requirements: 14.3
        """
        if len(portfolio_returns) < 2 or len(market_returns) < 2:
            return PerformanceAttribution(
                alpha=0.0,
                beta=0.0,
                total_return=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                max_drawdown=0.0,
                win_rate=0.0
            )
        
        # Ensure same length
        min_len = min(len(portfolio_returns), len(market_returns))
        port_ret = np.array(portfolio_returns[-min_len:])
        mkt_ret = np.array(market_returns[-min_len:])
        
        # Compute beta using linear regression
        if np.std(mkt_ret) > 0:
            beta = np.cov(port_ret, mkt_ret)[0, 1] / np.var(mkt_ret)
        else:
            beta = 0.0
        
        # Compute alpha: portfolio return - (risk_free + beta * market_excess_return)
        avg_port_ret = np.mean(port_ret)
        avg_mkt_ret = np.mean(mkt_ret)
        alpha = avg_port_ret - (risk_free_rate / 252 + beta * (avg_mkt_ret - risk_free_rate / 252))
        
        # Total return
        total_return = np.sum(port_ret)
        
        # Sharpe ratio
        if np.std(port_ret) > 0:
            sharpe_ratio = (avg_port_ret - risk_free_rate / 252) / np.std(port_ret) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        # Sortino ratio (downside deviation)
        downside_returns = port_ret[port_ret < 0]
        if len(downside_returns) > 0 and np.std(downside_returns) > 0:
            sortino_ratio = (avg_port_ret - risk_free_rate / 252) / np.std(downside_returns) * np.sqrt(252)
        else:
            sortino_ratio = sharpe_ratio
        
        # Maximum drawdown
        cumulative = np.cumsum(port_ret)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max)
        max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0.0
        
        # Win rate
        win_rate = np.sum(port_ret > 0) / len(port_ret) if len(port_ret) > 0 else 0.0
        
        attribution = PerformanceAttribution(
            alpha=alpha,
            beta=beta,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate
        )
        
        self.attribution_history.append(attribution)
        
        return attribution
    
    def track_regime_performance(
        self,
        regime: str,
        returns: List[float]
    ) -> RegimePerformance:
        """
        Track performance statistics by regime.
        
        Requirements: 14.6
        """
        if regime not in self.regime_performance:
            self.regime_performance[regime] = []
        
        self.regime_performance[regime].extend(returns)
        
        regime_returns = self.regime_performance[regime]
        
        if len(regime_returns) < 2:
            return RegimePerformance(
                regime=regime,
                total_return=0.0,
                sharpe_ratio=0.0,
                win_rate=0.0,
                num_trades=0,
                avg_return=0.0
            )
        
        # Compute statistics
        total_return = np.sum(regime_returns)
        avg_return = np.mean(regime_returns)
        
        if np.std(regime_returns) > 0:
            sharpe_ratio = avg_return / np.std(regime_returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        win_rate = np.sum(np.array(regime_returns) > 0) / len(regime_returns)
        
        return RegimePerformance(
            regime=regime,
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            num_trades=len(regime_returns),
            avg_return=avg_return
        )
    
    def detect_performance_degradation(
        self,
        recent_returns: List[float],
        lookback_window: int = 60
    ) -> List[PerformanceDegradation]:
        """
        Detect performance degradation by comparing recent to historical.
        
        Requirements: 14.5, 14.7
        """
        if len(self.returns_history) < lookback_window:
            return []  # Need sufficient history
        
        degradations = []
        
        # Get historical returns
        historical_returns = list(self.returns_history)[-lookback_window:]
        
        if len(recent_returns) < 10:
            return []
        
        # Compute metrics
        recent_avg = np.mean(recent_returns)
        historical_avg = np.mean(historical_returns)
        
        recent_sharpe = recent_avg / np.std(recent_returns) * np.sqrt(252) if np.std(recent_returns) > 0 else 0
        historical_sharpe = historical_avg / np.std(historical_returns) * np.sqrt(252) if np.std(historical_returns) > 0 else 0
        
        recent_win_rate = np.sum(np.array(recent_returns) > 0) / len(recent_returns)
        historical_win_rate = np.sum(np.array(historical_returns) > 0) / len(historical_returns)
        
        # Check for degradation
        # Average return degradation
        if historical_avg > 0:
            return_deviation = ((recent_avg - historical_avg) / abs(historical_avg)) * 100
            if return_deviation < -20:  # 20% worse
                severity = "HIGH" if return_deviation < -40 else "MEDIUM"
                degradations.append(PerformanceDegradation(
                    metric="average_return",
                    current_value=recent_avg,
                    historical_avg=historical_avg,
                    deviation_pct=return_deviation,
                    severity=severity,
                    recommendation="Review strategy parameters and market conditions"
                ))
        
        # Sharpe ratio degradation
        if historical_sharpe > 0:
            sharpe_deviation = ((recent_sharpe - historical_sharpe) / abs(historical_sharpe)) * 100
            if sharpe_deviation < -25:  # 25% worse
                severity = "HIGH" if sharpe_deviation < -50 else "MEDIUM"
                degradations.append(PerformanceDegradation(
                    metric="sharpe_ratio",
                    current_value=recent_sharpe,
                    historical_avg=historical_sharpe,
                    deviation_pct=sharpe_deviation,
                    severity=severity,
                    recommendation="Increase risk management or reduce position sizes"
                ))
        
        # Win rate degradation
        if historical_win_rate > 0:
            winrate_deviation = ((recent_win_rate - historical_win_rate) / historical_win_rate) * 100
            if winrate_deviation < -20:  # 20% worse
                severity = "MEDIUM" if winrate_deviation < -40 else "LOW"
                degradations.append(PerformanceDegradation(
                    metric="win_rate",
                    current_value=recent_win_rate,
                    historical_avg=historical_win_rate,
                    deviation_pct=winrate_deviation,
                    severity=severity,
                    recommendation="Review entry/exit criteria and market regime"
                ))
        
        return degradations
    
    def record_return(self, return_value: float):
        """Record a return for tracking"""
        self.returns_history.append(return_value)
    
    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary"""
        if len(self.returns_history) < 2:
            return {}
        
        returns = np.array(list(self.returns_history))
        
        return {
            "total_return": np.sum(returns),
            "avg_return": np.mean(returns),
            "volatility": np.std(returns) * np.sqrt(252),
            "sharpe_ratio": np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0,
            "win_rate": np.sum(returns > 0) / len(returns),
            "num_observations": len(returns),
            "max_return": np.max(returns),
            "min_return": np.min(returns)
        }

    def update_performance(
        self,
        state: Any,
        orders: List[Any],
        portfolio_greeks: PortfolioGreeks
    ) -> Dict[str, float]:
        """
        Update performance metrics after a trading cycle.
        
        Args:
            state: Current volatility state
            orders: Orders submitted in this cycle
            portfolio_greeks: Current portfolio Greeks
            
        Returns:
            Dict with performance metrics
        """
        # Compute Greeks P&L
        greeks_pnl = self.compute_greeks_pnl(
            current_greeks=portfolio_greeks,
            spot_change=0.0,  # Would need actual spot change
            vol_change=0.0,   # Would need actual vol change
            time_decay=1.0/252  # One day
        )
        
        # Track in history
        self.greeks_pnl_history.append(greeks_pnl)
        
        # Compute attribution
        attribution = self.compute_performance_attribution(
            portfolio_greeks=portfolio_greeks,
            returns=np.array([0.0]),  # Would need actual returns
            market_returns=np.array([0.0]),  # Would need market returns
            regime=state.regime.regime if hasattr(state, 'regime') else 'unknown'
        )
        
        self.attribution_history.append(attribution)
        
        # Return summary metrics
        return {
            "greeks_pnl": greeks_pnl.total_pnl,
            "delta_pnl": greeks_pnl.delta_pnl,
            "gamma_pnl": greeks_pnl.gamma_pnl,
            "vega_pnl": greeks_pnl.vega_pnl,
            "theta_pnl": greeks_pnl.theta_pnl,
            "alpha": attribution.alpha,
            "beta": attribution.beta,
            "sharpe_ratio": attribution.sharpe_ratio
        }
    
    def get_current_metrics(self) -> Dict[str, float]:
        """
        Get current performance metrics.
        
        Returns:
            Dict with current metrics
        """
        if not self.greeks_pnl_history:
            return {
                "total_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0
            }
        
        # Get recent P&L
        recent_pnl = [pnl.total_pnl for pnl in list(self.greeks_pnl_history)[-20:]]
        
        return {
            "total_pnl": sum(recent_pnl),
            "avg_pnl": np.mean(recent_pnl) if recent_pnl else 0.0,
            "sharpe_ratio": np.mean(recent_pnl) / np.std(recent_pnl) if len(recent_pnl) > 1 and np.std(recent_pnl) > 0 else 0.0,
            "win_rate": sum(1 for p in recent_pnl if p > 0) / len(recent_pnl) if recent_pnl else 0.0
        }
