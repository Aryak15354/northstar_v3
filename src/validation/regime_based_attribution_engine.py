"""
Regime-Based Attribution Engine

Decomposes performance by Phase 3 regime classifications and transitions.
Calculates regime-specific Sharpe ratios, drawdowns, and transition impacts.
Tracks performance across different regime similarity thresholds.

This engine provides institutional-grade performance attribution that:
- Decomposes returns by Phase 3 regime classifications and transitions
- Calculates regime-specific Sharpe ratios and drawdowns
- Measures regime transition impact on performance
- Tracks performance across different regime similarity thresholds
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from scipy import stats

from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class RegimePerformanceMetrics:
    """Performance metrics for a specific regime"""
    regime_name: str
    total_return: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    average_win: float
    average_loss: float
    periods_in_regime: int
    regime_duration_days: int

@dataclass
class RegimeTransitionMetrics:
    """Performance metrics during regime transitions"""
    from_regime: str
    to_regime: str
    transition_return: float
    transition_volatility: float
    transition_duration_days: int
    transition_impact: float  # Performance impact of transition
    transition_accuracy: float  # How well transition was predicted

@dataclass
class RegimeAttributionResult:
    """Complete regime-based attribution result"""
    attribution_period: Tuple[datetime, datetime]
    total_portfolio_return: float
    benchmark_return: Optional[float]
    regime_performance: Dict[str, RegimePerformanceMetrics]
    transition_performance: List[RegimeTransitionMetrics]
    regime_attribution: Dict[str, float]  # Attribution by regime
    transition_attribution: float  # Attribution from transitions
    regime_timing_alpha: float  # Alpha from regime timing
    unexplained_alpha: float
    regime_similarity_analysis: Dict[float, float]  # Performance by similarity threshold

class RegimeBasedAttributionEngine:
    """
    Regime-Based Attribution Engine
    
    Decomposes portfolio performance by Phase 3 regime classifications,
    providing detailed attribution analysis for institutional reporting.
    """
    
    def __init__(self):
        self.name = "Regime-Based Attribution Engine"
        self.version = "1.0"
        
        # Initialize Phase 3 regime memory system
        self.regime_memory = RegimeMemorySystem()
        
        # Attribution parameters
        self.min_regime_periods = 5  # Minimum periods for regime analysis
        self.similarity_thresholds = [0.6, 0.7, 0.8, 0.9]  # Similarity thresholds to analyze
        self.transition_window_days = 5  # Days around transition to analyze
        
        logger.info(f"🎯 {self.name} v{self.version} initialized")
        logger.info(f"💡 Regime similarity thresholds: {self.similarity_thresholds}")
    
    def calculate_regime_attribution(
        self,
        portfolio_returns: pd.Series,
        regime_history: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        regime_similarity_scores: Optional[pd.Series] = None
    ) -> RegimeAttributionResult:
        """
        Calculate performance attribution by Phase 3 regimes
        
        Args:
            portfolio_returns: Portfolio returns time series
            regime_history: Regime classifications time series
            benchmark_returns: Optional benchmark returns for comparison
            regime_similarity_scores: Optional regime similarity scores
            
        Returns:
            Complete regime attribution analysis
        """
        logger.info(f"🎯 {self.name} - Calculating Regime Attribution")
        logger.info(f"📊 Portfolio periods: {len(portfolio_returns)}")
        logger.info(f"🧠 Unique regimes: {regime_history.nunique()}")
        
        # Align data
        aligned_data = self._align_attribution_data(
            portfolio_returns, regime_history, benchmark_returns, regime_similarity_scores
        )
        
        # Calculate regime performance metrics
        regime_performance = self._calculate_regime_performance_metrics(
            aligned_data['returns'], aligned_data['regimes']
        )
        
        # Calculate transition performance
        transition_performance = self._calculate_transition_performance(
            aligned_data['returns'], aligned_data['regimes']
        )
        
        # Calculate regime attribution
        regime_attribution = self._calculate_regime_attribution_values(
            aligned_data['returns'], aligned_data['regimes'], 
            aligned_data.get('benchmark'), regime_performance
        )
        
        # Calculate regime timing alpha
        regime_timing_alpha = self._calculate_regime_timing_alpha(
            aligned_data['returns'], aligned_data['regimes'], regime_performance
        )
        
        # Analyze performance by similarity thresholds
        similarity_analysis = self._analyze_performance_by_similarity(
            aligned_data['returns'], aligned_data.get('similarity_scores')
        )
        
        # Calculate transition attribution
        transition_attribution = sum(tm.transition_impact for tm in transition_performance)
        
        # Calculate unexplained alpha
        total_attribution = sum(regime_attribution.values()) + transition_attribution
        total_return = aligned_data['returns'].sum()
        benchmark_return = aligned_data.get('benchmark', pd.Series([0])).sum()
        unexplained_alpha = total_return - benchmark_return - total_attribution
        
        attribution_result = RegimeAttributionResult(
            attribution_period=(aligned_data['returns'].index[0], aligned_data['returns'].index[-1]),
            total_portfolio_return=total_return,
            benchmark_return=benchmark_return if benchmark_returns is not None else None,
            regime_performance=regime_performance,
            transition_performance=transition_performance,
            regime_attribution=regime_attribution,
            transition_attribution=transition_attribution,
            regime_timing_alpha=regime_timing_alpha,
            unexplained_alpha=unexplained_alpha,
            regime_similarity_analysis=similarity_analysis
        )
        
        logger.info(f"✅ Regime attribution completed")
        logger.info(f"📈 Total return: {total_return:.3f}")
        logger.info(f"🎯 Regime timing alpha: {regime_timing_alpha:.3f}")
        logger.info(f"❓ Unexplained alpha: {unexplained_alpha:.3f}")
        
        return attribution_result
    
    def _align_attribution_data(
        self,
        portfolio_returns: pd.Series,
        regime_history: pd.Series,
        benchmark_returns: Optional[pd.Series],
        regime_similarity_scores: Optional[pd.Series]
    ) -> Dict[str, pd.Series]:
        """Align all data series for attribution calculation"""
        
        # Start with portfolio returns as base
        aligned_data = {'returns': portfolio_returns.copy()}
        
        # Align regime history
        aligned_regimes = regime_history.reindex(portfolio_returns.index, method='ffill')
        aligned_data['regimes'] = aligned_regimes
        
        # Align benchmark if provided
        if benchmark_returns is not None:
            aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index, method='ffill')
            aligned_data['benchmark'] = aligned_benchmark.fillna(0)
        
        # Align similarity scores if provided
        if regime_similarity_scores is not None:
            aligned_similarity = regime_similarity_scores.reindex(portfolio_returns.index, method='ffill')
            aligned_data['similarity_scores'] = aligned_similarity
        
        # Remove any periods with missing regime data
        valid_mask = aligned_data['regimes'].notna()
        for key in aligned_data:
            aligned_data[key] = aligned_data[key][valid_mask]
        
        return aligned_data
    
    def _calculate_regime_performance_metrics(
        self,
        returns: pd.Series,
        regimes: pd.Series
    ) -> Dict[str, RegimePerformanceMetrics]:
        """Calculate performance metrics for each regime"""
        
        regime_performance = {}
        
        for regime in regimes.unique():
            if pd.isna(regime):
                continue
                
            # Get returns for this regime
            regime_mask = regimes == regime
            regime_returns = returns[regime_mask]
            
            if len(regime_returns) < self.min_regime_periods:
                logger.warning(f"Insufficient data for regime {regime}: {len(regime_returns)} periods")
                continue
            
            # Calculate basic metrics
            total_return = regime_returns.sum()
            periods = len(regime_returns)
            
            # Annualized return (assuming daily returns)
            annualized_return = (1 + regime_returns.mean()) ** 252 - 1
            
            # Volatility
            volatility = regime_returns.std() * np.sqrt(252)
            
            # Sharpe ratio
            sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
            
            # Max drawdown
            cumulative = (1 + regime_returns).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min()
            
            # Win/loss metrics
            wins = regime_returns[regime_returns > 0]
            losses = regime_returns[regime_returns < 0]
            win_rate = len(wins) / len(regime_returns) if len(regime_returns) > 0 else 0
            average_win = wins.mean() if len(wins) > 0 else 0
            average_loss = losses.mean() if len(losses) > 0 else 0
            
            # Duration analysis
            regime_periods = regime_mask.sum()
            regime_duration_days = regime_periods  # Assuming daily data
            
            regime_performance[regime] = RegimePerformanceMetrics(
                regime_name=regime,
                total_return=total_return,
                annualized_return=annualized_return,
                volatility=volatility,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                average_win=average_win,
                average_loss=average_loss,
                periods_in_regime=periods,
                regime_duration_days=regime_duration_days
            )
        
        return regime_performance
    
    def _calculate_transition_performance(
        self,
        returns: pd.Series,
        regimes: pd.Series
    ) -> List[RegimeTransitionMetrics]:
        """Calculate performance during regime transitions"""
        
        transition_performance = []
        
        # Find regime changes
        regime_changes = regimes != regimes.shift(1)
        transition_dates = regimes[regime_changes].index[1:]  # Skip first date
        
        for transition_date in transition_dates:
            try:
                # Get transition window
                start_date = transition_date - pd.Timedelta(days=self.transition_window_days)
                end_date = transition_date + pd.Timedelta(days=self.transition_window_days)
                
                # Get returns in transition window
                transition_mask = (returns.index >= start_date) & (returns.index <= end_date)
                transition_returns = returns[transition_mask]
                
                if len(transition_returns) < 2:
                    continue
                
                # Get from and to regimes
                from_regime = regimes.loc[:transition_date].iloc[-2] if len(regimes.loc[:transition_date]) > 1 else None
                to_regime = regimes.loc[transition_date]
                
                if pd.isna(from_regime) or pd.isna(to_regime):
                    continue
                
                # Calculate transition metrics
                transition_return = transition_returns.sum()
                transition_volatility = transition_returns.std() * np.sqrt(252)
                transition_duration = len(transition_returns)
                
                # Calculate transition impact (vs expected return)
                expected_return = returns.mean() * len(transition_returns)
                transition_impact = transition_return - expected_return
                
                # Simple transition accuracy (placeholder - would need more sophisticated prediction)
                transition_accuracy = 0.5  # Neutral assumption
                
                transition_performance.append(RegimeTransitionMetrics(
                    from_regime=from_regime,
                    to_regime=to_regime,
                    transition_return=transition_return,
                    transition_volatility=transition_volatility,
                    transition_duration_days=transition_duration,
                    transition_impact=transition_impact,
                    transition_accuracy=transition_accuracy
                ))
                
            except Exception as e:
                logger.warning(f"Error calculating transition performance for {transition_date}: {str(e)}")
                continue
        
        return transition_performance
    
    def _calculate_regime_attribution_values(
        self,
        returns: pd.Series,
        regimes: pd.Series,
        benchmark_returns: Optional[pd.Series],
        regime_performance: Dict[str, RegimePerformanceMetrics]
    ) -> Dict[str, float]:
        """Calculate attribution values for each regime"""
        
        regime_attribution = {}
        
        # Calculate benchmark performance by regime if available
        benchmark_regime_performance = {}
        if benchmark_returns is not None:
            for regime in regimes.unique():
                if pd.isna(regime):
                    continue
                regime_mask = regimes == regime
                benchmark_regime_returns = benchmark_returns[regime_mask]
                if len(benchmark_regime_returns) > 0:
                    benchmark_regime_performance[regime] = benchmark_regime_returns.sum()
        
        # Calculate attribution for each regime
        for regime, performance in regime_performance.items():
            # Portfolio return in regime
            portfolio_regime_return = performance.total_return
            
            # Benchmark return in regime (or zero if no benchmark)
            benchmark_regime_return = benchmark_regime_performance.get(regime, 0)
            
            # Attribution is excess return
            regime_attribution[regime] = portfolio_regime_return - benchmark_regime_return
        
        return regime_attribution
    
    def _calculate_regime_timing_alpha(
        self,
        returns: pd.Series,
        regimes: pd.Series,
        regime_performance: Dict[str, RegimePerformanceMetrics]
    ) -> float:
        """Calculate alpha from regime timing ability"""
        
        # Simple regime timing alpha calculation
        # This measures if the strategy performs better in regimes it allocates more to
        
        total_alpha = 0.0
        
        try:
            # Calculate average return by regime
            regime_avg_returns = {}
            for regime, performance in regime_performance.items():
                if performance.periods_in_regime > 0:
                    regime_avg_returns[regime] = performance.total_return / performance.periods_in_regime
            
            # Calculate timing alpha as weighted performance vs equal-weight performance
            if len(regime_avg_returns) > 1:
                equal_weight_return = np.mean(list(regime_avg_returns.values()))
                
                # Weight by actual time spent in each regime
                total_periods = sum(p.periods_in_regime for p in regime_performance.values())
                weighted_return = sum(
                    (p.periods_in_regime / total_periods) * regime_avg_returns.get(regime, 0)
                    for regime, p in regime_performance.items()
                    if regime in regime_avg_returns
                )
                
                total_alpha = weighted_return - equal_weight_return
            
        except Exception as e:
            logger.warning(f"Error calculating regime timing alpha: {str(e)}")
            total_alpha = 0.0
        
        return total_alpha
    
    def _analyze_performance_by_similarity(
        self,
        returns: pd.Series,
        similarity_scores: Optional[pd.Series]
    ) -> Dict[float, float]:
        """Analyze performance by regime similarity thresholds"""
        
        similarity_analysis = {}
        
        if similarity_scores is None:
            # Return empty analysis if no similarity scores
            return {threshold: 0.0 for threshold in self.similarity_thresholds}
        
        for threshold in self.similarity_thresholds:
            try:
                # Get periods where similarity is above threshold
                high_similarity_mask = similarity_scores >= threshold
                high_similarity_returns = returns[high_similarity_mask]
                
                if len(high_similarity_returns) > 0:
                    # Calculate performance for high similarity periods
                    high_similarity_performance = high_similarity_returns.sum()
                    similarity_analysis[threshold] = high_similarity_performance
                else:
                    similarity_analysis[threshold] = 0.0
                    
            except Exception as e:
                logger.warning(f"Error analyzing similarity threshold {threshold}: {str(e)}")
                similarity_analysis[threshold] = 0.0
        
        return similarity_analysis
    
    def generate_regime_attribution_report(
        self,
        attribution_result: RegimeAttributionResult,
        output_path: Optional[str] = None
    ) -> str:
        """Generate detailed regime attribution report"""
        
        report_lines = []
        
        # Header
        report_lines.append("REGIME-BASED PERFORMANCE ATTRIBUTION REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Attribution Period: {attribution_result.attribution_period[0].strftime('%Y-%m-%d')} to {attribution_result.attribution_period[1].strftime('%Y-%m-%d')}")
        report_lines.append(f"Total Portfolio Return: {attribution_result.total_portfolio_return:.3f}")
        if attribution_result.benchmark_return is not None:
            report_lines.append(f"Benchmark Return: {attribution_result.benchmark_return:.3f}")
        report_lines.append("")
        
        # Regime Performance Summary
        report_lines.append("REGIME PERFORMANCE SUMMARY")
        report_lines.append("-" * 40)
        for regime, performance in attribution_result.regime_performance.items():
            report_lines.append(f"Regime: {regime}")
            report_lines.append(f"  Total Return: {performance.total_return:.3f}")
            report_lines.append(f"  Annualized Return: {performance.annualized_return:.3f}")
            report_lines.append(f"  Sharpe Ratio: {performance.sharpe_ratio:.3f}")
            report_lines.append(f"  Max Drawdown: {performance.max_drawdown:.3f}")
            report_lines.append(f"  Periods: {performance.periods_in_regime}")
            report_lines.append("")
        
        # Attribution Analysis
        report_lines.append("ATTRIBUTION ANALYSIS")
        report_lines.append("-" * 40)
        for regime, attribution in attribution_result.regime_attribution.items():
            report_lines.append(f"{regime}: {attribution:.3f}")
        report_lines.append(f"Transition Attribution: {attribution_result.transition_attribution:.3f}")
        report_lines.append(f"Regime Timing Alpha: {attribution_result.regime_timing_alpha:.3f}")
        report_lines.append(f"Unexplained Alpha: {attribution_result.unexplained_alpha:.3f}")
        report_lines.append("")
        
        # Similarity Analysis
        if attribution_result.regime_similarity_analysis:
            report_lines.append("SIMILARITY THRESHOLD ANALYSIS")
            report_lines.append("-" * 40)
            for threshold, performance in attribution_result.regime_similarity_analysis.items():
                report_lines.append(f"Similarity >= {threshold}: {performance:.3f}")
            report_lines.append("")
        
        # Transition Analysis
        if attribution_result.transition_performance:
            report_lines.append("REGIME TRANSITION ANALYSIS")
            report_lines.append("-" * 40)
            for transition in attribution_result.transition_performance:
                report_lines.append(f"{transition.from_regime} → {transition.to_regime}: {transition.transition_impact:.3f}")
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        # Save report if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_content)
            logger.info(f"📄 Regime attribution report saved to {output_path}")
        
        return report_content