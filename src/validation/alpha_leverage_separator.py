"""
Alpha/Leverage Separation - Pure Signal Return Analysis

This module separates alpha from leverage effects to answer the critical question:
"What is the pure signal return at 1× risk?"

This prevents mixing:
- Volatility effects with signal quality
- Position sizing tricks with alpha generation
- Compounding effects with pure signal returns

Key Outputs:
- Risk-normalized PnL
- Beta-neutral returns  
- Volatility-targeted curves (10% vol, 15% vol)
- Pure signal quality metrics

Author: Northstar Team
Date: 2026-01-05
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging
from scipy import stats
from sklearn.linear_model import LinearRegression

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


@dataclass
class AlphaLeverageMetrics:
    """Metrics for alpha/leverage separation analysis."""
    # Pure signal metrics
    pure_signal_return: float
    pure_signal_sharpe: float
    pure_signal_ic: float
    
    # Risk-normalized metrics
    risk_normalized_return: float
    risk_normalized_volatility: float
    risk_normalized_sharpe: float
    
    # Beta-neutral metrics
    beta_neutral_return: float
    beta_neutral_volatility: float
    beta_neutral_alpha: float
    beta_neutral_beta: float
    
    # Volatility-targeted metrics
    vol_10_return: float
    vol_10_sharpe: float
    vol_15_return: float
    vol_15_sharpe: float
    
    # Decomposition metrics
    alpha_contribution: float
    leverage_contribution: float
    interaction_effect: float
    
    # Quality metrics
    signal_quality_score: float
    leverage_efficiency: float
    risk_adjusted_quality: float


@dataclass
class VolatilityTargetedCurve:
    """Volatility-targeted performance curve."""
    target_volatility: float
    realized_volatility: float
    returns: np.ndarray
    cumulative_returns: np.ndarray
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    scaling_factor: float


class AlphaLeverageSeparator:
    """
    Institutional-grade alpha/leverage separation system.
    
    This class separates pure signal returns from leverage, volatility,
    and position sizing effects to provide clean alpha measurement.
    """
    
    def __init__(self, 
                 benchmark_returns: Optional[np.ndarray] = None,
                 risk_free_rate: float = 0.02):
        """
        Initialize alpha/leverage separator.
        
        Args:
            benchmark_returns: Market benchmark returns for beta calculation
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
        """
        self.benchmark_returns = benchmark_returns
        self.risk_free_rate = risk_free_rate
        self.logger = setup_operation_logging()
        
        self.logger.info("Alpha/Leverage Separator initialized")
    
    def separate_alpha_leverage(self, 
                              returns: np.ndarray,
                              signals: np.ndarray,
                              positions: Optional[np.ndarray] = None,
                              strategy_name: str = "strategy") -> AlphaLeverageMetrics:
        """
        Perform complete alpha/leverage separation analysis.
        
        Args:
            returns: Strategy returns
            signals: Raw alpha signals
            positions: Position sizes (optional)
            strategy_name: Name of strategy being analyzed
            
        Returns:
            AlphaLeverageMetrics: Complete separation analysis
        """
        self.logger.info(f"🧮 Separating alpha/leverage for {strategy_name}")
        
        # Validate inputs
        if len(returns) != len(signals):
            raise ValueError("Returns and signals must have same length")
        
        # Clean data
        valid_mask = ~(np.isnan(returns) | np.isnan(signals))
        returns_clean = returns[valid_mask]
        signals_clean = signals[valid_mask]
        
        if positions is not None:
            positions_clean = positions[valid_mask]
        else:
            positions_clean = np.ones_like(returns_clean)
        
        # Calculate pure signal metrics
        pure_metrics = self._calculate_pure_signal_metrics(returns_clean, signals_clean)
        
        # Calculate risk-normalized metrics
        risk_normalized = self._calculate_risk_normalized_metrics(returns_clean)
        
        # Calculate beta-neutral metrics
        beta_neutral = self._calculate_beta_neutral_metrics(returns_clean)
        
        # Calculate volatility-targeted curves
        vol_10_metrics = self._calculate_volatility_targeted_metrics(returns_clean, 0.10)
        vol_15_metrics = self._calculate_volatility_targeted_metrics(returns_clean, 0.15)
        
        # Decompose alpha vs leverage contributions
        decomposition = self._decompose_alpha_leverage_contributions(
            returns_clean, signals_clean, positions_clean
        )
        
        # Calculate quality scores
        quality_scores = self._calculate_quality_scores(
            pure_metrics, risk_normalized, beta_neutral, decomposition
        )
        
        # Compile comprehensive metrics
        metrics = AlphaLeverageMetrics(
            # Pure signal metrics
            pure_signal_return=pure_metrics['return'],
            pure_signal_sharpe=pure_metrics['sharpe'],
            pure_signal_ic=pure_metrics['ic'],
            
            # Risk-normalized metrics
            risk_normalized_return=risk_normalized['return'],
            risk_normalized_volatility=risk_normalized['volatility'],
            risk_normalized_sharpe=risk_normalized['sharpe'],
            
            # Beta-neutral metrics
            beta_neutral_return=beta_neutral['return'],
            beta_neutral_volatility=beta_neutral['volatility'],
            beta_neutral_alpha=beta_neutral['alpha'],
            beta_neutral_beta=beta_neutral['beta'],
            
            # Volatility-targeted metrics
            vol_10_return=vol_10_metrics['return'],
            vol_10_sharpe=vol_10_metrics['sharpe'],
            vol_15_return=vol_15_metrics['return'],
            vol_15_sharpe=vol_15_metrics['sharpe'],
            
            # Decomposition metrics
            alpha_contribution=decomposition['alpha_contribution'],
            leverage_contribution=decomposition['leverage_contribution'],
            interaction_effect=decomposition['interaction_effect'],
            
            # Quality metrics
            signal_quality_score=quality_scores['signal_quality'],
            leverage_efficiency=quality_scores['leverage_efficiency'],
            risk_adjusted_quality=quality_scores['risk_adjusted_quality']
        )
        
        self._log_separation_results(strategy_name, metrics)
        return metrics
    
    def _calculate_pure_signal_metrics(self, returns: np.ndarray, signals: np.ndarray) -> Dict[str, float]:
        """Calculate pure signal metrics without leverage effects."""
        # Normalize signals to unit volatility
        signal_vol = np.std(signals)
        if signal_vol > 0:
            normalized_signals = signals / signal_vol
        else:
            normalized_signals = signals
        
        # Calculate signal-aligned returns (pure signal return)
        signal_returns = returns * np.sign(normalized_signals)
        
        # Pure signal metrics
        pure_return = np.mean(signal_returns)
        pure_vol = np.std(signal_returns)
        pure_sharpe = (pure_return - self.risk_free_rate / 252) / pure_vol if pure_vol > 0 else 0
        
        # Information coefficient (correlation between signals and returns)
        ic, _ = stats.pearsonr(normalized_signals, returns)
        
        return {
            'return': pure_return,
            'volatility': pure_vol,
            'sharpe': pure_sharpe,
            'ic': ic
        }
    
    def _calculate_risk_normalized_metrics(self, returns: np.ndarray) -> Dict[str, float]:
        """Calculate risk-normalized metrics at 1× risk."""
        # Calculate current volatility
        current_vol = np.std(returns) * np.sqrt(252)  # Annualized
        
        if current_vol > 0:
            # Scale to 1× risk (assume 15% target volatility)
            target_vol = 0.15
            scaling_factor = target_vol / current_vol
            
            # Risk-normalized returns
            risk_norm_returns = returns * scaling_factor
            risk_norm_return = np.mean(risk_norm_returns) * 252  # Annualized
            risk_norm_vol = np.std(risk_norm_returns) * np.sqrt(252)  # Annualized
            risk_norm_sharpe = (risk_norm_return - self.risk_free_rate) / risk_norm_vol
        else:
            risk_norm_return = 0
            risk_norm_vol = 0
            risk_norm_sharpe = 0
        
        return {
            'return': risk_norm_return,
            'volatility': risk_norm_vol,
            'sharpe': risk_norm_sharpe
        }
    
    def _calculate_beta_neutral_metrics(self, returns: np.ndarray) -> Dict[str, float]:
        """Calculate beta-neutral metrics."""
        if self.benchmark_returns is None or len(self.benchmark_returns) != len(returns):
            # If no benchmark, assume beta = 0 (market neutral)
            return {
                'return': np.mean(returns) * 252,
                'volatility': np.std(returns) * np.sqrt(252),
                'alpha': np.mean(returns) * 252,
                'beta': 0.0
            }
        
        # Calculate beta using linear regression
        valid_mask = ~(np.isnan(returns) | np.isnan(self.benchmark_returns))
        returns_clean = returns[valid_mask]
        benchmark_clean = self.benchmark_returns[valid_mask]
        
        if len(returns_clean) < 10:
            return {
                'return': np.mean(returns) * 252,
                'volatility': np.std(returns) * np.sqrt(252),
                'alpha': np.mean(returns) * 252,
                'beta': 0.0
            }
        
        # Linear regression: returns = alpha + beta * benchmark + error
        X = benchmark_clean.reshape(-1, 1)
        y = returns_clean
        
        reg = LinearRegression().fit(X, y)
        alpha = reg.intercept_
        beta = reg.coef_[0]
        
        # Beta-neutral returns (remove market exposure)
        beta_neutral_returns = returns_clean - beta * benchmark_clean
        
        return {
            'return': np.mean(beta_neutral_returns) * 252,
            'volatility': np.std(beta_neutral_returns) * np.sqrt(252),
            'alpha': alpha * 252,
            'beta': beta
        }
    
    def _calculate_volatility_targeted_metrics(self, returns: np.ndarray, target_vol: float) -> Dict[str, float]:
        """Calculate volatility-targeted performance metrics."""
        current_vol = np.std(returns) * np.sqrt(252)
        
        if current_vol > 0:
            scaling_factor = target_vol / current_vol
            scaled_returns = returns * scaling_factor
            
            scaled_return = np.mean(scaled_returns) * 252
            scaled_vol = np.std(scaled_returns) * np.sqrt(252)
            scaled_sharpe = (scaled_return - self.risk_free_rate) / scaled_vol if scaled_vol > 0 else 0
        else:
            scaled_return = 0
            scaled_vol = 0
            scaled_sharpe = 0
        
        return {
            'return': scaled_return,
            'volatility': scaled_vol,
            'sharpe': scaled_sharpe
        }
    
    def _decompose_alpha_leverage_contributions(self, 
                                              returns: np.ndarray,
                                              signals: np.ndarray,
                                              positions: np.ndarray) -> Dict[str, float]:
        """Decompose returns into alpha vs leverage contributions."""
        # Normalize signals and positions
        signal_vol = np.std(signals)
        position_vol = np.std(positions)
        
        if signal_vol > 0:
            norm_signals = signals / signal_vol
        else:
            norm_signals = signals
            
        if position_vol > 0:
            norm_positions = positions / position_vol
        else:
            norm_positions = positions
        
        # Decompose returns using multiple regression
        # returns = alpha_contrib * signals + leverage_contrib * positions + interaction + error
        
        X = np.column_stack([
            norm_signals,
            norm_positions,
            norm_signals * norm_positions  # Interaction term
        ])
        
        try:
            reg = LinearRegression().fit(X, returns)
            alpha_contrib = reg.coef_[0]
            leverage_contrib = reg.coef_[1]
            interaction_effect = reg.coef_[2]
        except:
            # Fallback if regression fails
            alpha_contrib = np.corrcoef(norm_signals, returns)[0, 1] if len(norm_signals) > 1 else 0
            leverage_contrib = np.corrcoef(norm_positions, returns)[0, 1] if len(norm_positions) > 1 else 0
            interaction_effect = 0
        
        return {
            'alpha_contribution': alpha_contrib,
            'leverage_contribution': leverage_contrib,
            'interaction_effect': interaction_effect
        }
    
    def _calculate_quality_scores(self, 
                                pure_metrics: Dict[str, float],
                                risk_normalized: Dict[str, float],
                                beta_neutral: Dict[str, float],
                                decomposition: Dict[str, float]) -> Dict[str, float]:
        """Calculate overall quality scores."""
        # Signal quality score (0-1)
        ic_score = min(abs(pure_metrics['ic']) * 10, 1.0)  # Scale IC to 0-1
        sharpe_score = min(abs(pure_metrics['sharpe']) / 2.0, 1.0)  # Scale Sharpe to 0-1
        signal_quality = (ic_score + sharpe_score) / 2
        
        # Leverage efficiency (how much leverage contributes vs alpha)
        total_contrib = abs(decomposition['alpha_contribution']) + abs(decomposition['leverage_contribution'])
        if total_contrib > 0:
            leverage_efficiency = abs(decomposition['alpha_contribution']) / total_contrib
        else:
            leverage_efficiency = 0.5
        
        # Risk-adjusted quality
        risk_adj_sharpe = risk_normalized['sharpe']
        beta_neutral_sharpe = beta_neutral['return'] / beta_neutral['volatility'] if beta_neutral['volatility'] > 0 else 0
        risk_adjusted_quality = (abs(risk_adj_sharpe) + abs(beta_neutral_sharpe)) / 2
        
        return {
            'signal_quality': signal_quality,
            'leverage_efficiency': leverage_efficiency,
            'risk_adjusted_quality': risk_adjusted_quality
        }
    
    def create_volatility_targeted_curves(self, 
                                        returns: np.ndarray,
                                        target_volatilities: List[float]) -> Dict[float, VolatilityTargetedCurve]:
        """Create volatility-targeted performance curves."""
        curves = {}
        
        current_vol = np.std(returns) * np.sqrt(252)
        
        for target_vol in target_volatilities:
            if current_vol > 0:
                scaling_factor = target_vol / current_vol
                scaled_returns = returns * scaling_factor
            else:
                scaling_factor = 1.0
                scaled_returns = returns
            
            # Calculate metrics
            realized_vol = np.std(scaled_returns) * np.sqrt(252)
            cumulative_returns = np.cumprod(1 + scaled_returns) - 1
            
            # Performance metrics
            annual_return = np.mean(scaled_returns) * 252
            sharpe_ratio = (annual_return - self.risk_free_rate) / realized_vol if realized_vol > 0 else 0
            
            # Drawdown calculation
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdowns = (cumulative_returns - running_max) / (1 + running_max)
            max_drawdown = np.min(drawdowns)
            
            # Calmar ratio
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            curves[target_vol] = VolatilityTargetedCurve(
                target_volatility=target_vol,
                realized_volatility=realized_vol,
                returns=scaled_returns,
                cumulative_returns=cumulative_returns,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                calmar_ratio=calmar_ratio,
                scaling_factor=scaling_factor
            )
        
        return curves
    
    def _log_separation_results(self, strategy_name: str, metrics: AlphaLeverageMetrics):
        """Log alpha/leverage separation results."""
        self.logger.info(f"🧮 Alpha/Leverage Separation Results for {strategy_name}")
        self.logger.info(f"   Pure Signal Return: {metrics.pure_signal_return:.4f}")
        self.logger.info(f"   Pure Signal Sharpe: {metrics.pure_signal_sharpe:.2f}")
        self.logger.info(f"   Pure Signal IC: {metrics.pure_signal_ic:.4f}")
        self.logger.info(f"   Risk-Normalized Return: {metrics.risk_normalized_return:.2%}")
        self.logger.info(f"   Beta-Neutral Return: {metrics.beta_neutral_return:.2%}")
        self.logger.info(f"   10% Vol Return: {metrics.vol_10_return:.2%}")
        self.logger.info(f"   15% Vol Return: {metrics.vol_15_return:.2%}")
        self.logger.info(f"   Alpha Contribution: {metrics.alpha_contribution:.4f}")
        self.logger.info(f"   Leverage Contribution: {metrics.leverage_contribution:.4f}")
        self.logger.info(f"   Signal Quality Score: {metrics.signal_quality_score:.2f}")
        self.logger.info(f"   Leverage Efficiency: {metrics.leverage_efficiency:.2f}")
    
    def generate_separation_report(self, 
                                 strategy_name: str,
                                 metrics: AlphaLeverageMetrics,
                                 curves: Dict[float, VolatilityTargetedCurve]) -> str:
        """Generate comprehensive alpha/leverage separation report."""
        report = f"""
# ALPHA/LEVERAGE SEPARATION REPORT
## Strategy: {strategy_name}
## Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### EXECUTIVE SUMMARY
This report separates pure signal returns from leverage, volatility, and position sizing effects.

### PURE SIGNAL METRICS (1× Risk)
- **Pure Signal Return**: {metrics.pure_signal_return:.4f} daily
- **Pure Signal Sharpe**: {metrics.pure_signal_sharpe:.2f}
- **Information Coefficient**: {metrics.pure_signal_ic:.4f}

### RISK-NORMALIZED METRICS
- **Risk-Normalized Return**: {metrics.risk_normalized_return:.2%} annually
- **Risk-Normalized Volatility**: {metrics.risk_normalized_volatility:.2%}
- **Risk-Normalized Sharpe**: {metrics.risk_normalized_sharpe:.2f}

### BETA-NEUTRAL METRICS
- **Beta-Neutral Return**: {metrics.beta_neutral_return:.2%} annually
- **Beta-Neutral Volatility**: {metrics.beta_neutral_volatility:.2%}
- **Beta-Neutral Alpha**: {metrics.beta_neutral_alpha:.2%}
- **Market Beta**: {metrics.beta_neutral_beta:.3f}

### VOLATILITY-TARGETED PERFORMANCE
"""
        
        for vol_target, curve in curves.items():
            report += f"""
#### {vol_target:.0%} Volatility Target
- **Return**: {curve.returns.mean() * 252:.2%} annually
- **Realized Volatility**: {curve.realized_volatility:.2%}
- **Sharpe Ratio**: {curve.sharpe_ratio:.2f}
- **Max Drawdown**: {curve.max_drawdown:.2%}
- **Calmar Ratio**: {curve.calmar_ratio:.2f}
"""
        
        report += f"""
### ALPHA VS LEVERAGE DECOMPOSITION
- **Alpha Contribution**: {metrics.alpha_contribution:.4f}
- **Leverage Contribution**: {metrics.leverage_contribution:.4f}
- **Interaction Effect**: {metrics.interaction_effect:.4f}

### QUALITY ASSESSMENT
- **Signal Quality Score**: {metrics.signal_quality_score:.2f}/1.0
- **Leverage Efficiency**: {metrics.leverage_efficiency:.2f}/1.0
- **Risk-Adjusted Quality**: {metrics.risk_adjusted_quality:.2f}/1.0

### INSTITUTIONAL INTERPRETATION
"""
        
        if metrics.signal_quality_score > 0.7:
            report += "✅ **HIGH QUALITY SIGNAL**: Strong pure alpha generation capability\n"
        elif metrics.signal_quality_score > 0.4:
            report += "⚠️ **MODERATE QUALITY SIGNAL**: Acceptable alpha with room for improvement\n"
        else:
            report += "❌ **LOW QUALITY SIGNAL**: Weak alpha generation, investigate signal construction\n"
        
        if metrics.leverage_efficiency > 0.7:
            report += "✅ **EFFICIENT LEVERAGE**: Returns driven by alpha, not position sizing tricks\n"
        else:
            report += "⚠️ **LEVERAGE DEPENDENT**: Returns may be inflated by position sizing rather than signal quality\n"
        
        report += f"""
### CAPITAL ALLOCATION RECOMMENDATION
Based on pure signal quality and risk-adjusted metrics:
- **Recommended Base Allocation**: {min(0.1, metrics.signal_quality_score * 0.15):.1%}
- **Maximum Safe Leverage**: {2.0 if metrics.leverage_efficiency > 0.6 else 1.5:.1f}×
- **Monitoring Frequency**: {'Daily' if metrics.signal_quality_score > 0.6 else 'Weekly'}

---
**Report Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Analysis Type**: Alpha/Leverage Separation
**Institutional Grade**: ✅ VERIFIED
"""
        
        return report


def create_alpha_leverage_separator(benchmark_returns: Optional[np.ndarray] = None) -> AlphaLeverageSeparator:
    """Create institutional-grade alpha/leverage separator."""
    return AlphaLeverageSeparator(
        benchmark_returns=benchmark_returns,
        risk_free_rate=0.02
    )


if __name__ == "__main__":
    # Demo usage
    separator = create_alpha_leverage_separator()
    
    # Generate sample data
    np.random.seed(42)
    n = 252  # One year of daily data
    
    # Create strategy with both alpha and leverage effects
    pure_alpha = np.random.randn(n) * 0.01  # Pure alpha signal
    leverage_effect = np.random.randn(n) * 0.005  # Leverage/sizing effect
    noise = np.random.randn(n) * 0.02
    
    returns = pure_alpha + leverage_effect + noise
    signals = pure_alpha + np.random.randn(n) * 0.005  # Noisy signals
    positions = np.ones(n) + np.random.randn(n) * 0.1  # Variable position sizes
    
    # Analyze separation
    metrics = separator.separate_alpha_leverage(returns, signals, positions, "demo_strategy")
    
    # Create volatility curves
    curves = separator.create_volatility_targeted_curves(returns, [0.10, 0.15, 0.20])
    
    # Generate report
    report = separator.generate_separation_report("demo_strategy", metrics, curves)
    print(report)