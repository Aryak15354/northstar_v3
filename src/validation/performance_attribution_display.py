"""
Performance Attribution Display

Real-time display system for Phase 3 performance attribution:
- Real-time performance attribution breakdown
- Phase 3 component contribution visualization
- Regime-based attribution analysis
- Confidence score and performance correlation tracking

This display provides institutional-grade performance attribution with
real-time updates and comprehensive Phase 3 intelligence integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from collections import deque, defaultdict
import numpy as np
import pandas as pd
import json

from src.validation.regime_based_attribution_engine import RegimeBasedAttributionEngine
from src.validation.phase3_component_attribution import Phase3ComponentAttribution
from src.validation.multi_dimensional_decomposer import MultiDimensionalDecomposer
from src.validation.phase3_intelligence_monitor import Phase3IntelligenceMonitor
from src.core.events import EventBus

logger = logging.getLogger(__name__)

@dataclass
class AttributionBreakdown:
    """Performance attribution breakdown"""
    total_return: float
    regime_attribution: Dict[str, float]
    component_attribution: Dict[str, float]
    interaction_effects: Dict[str, float]
    unexplained_alpha: float
    confidence_weighted_return: float
    attribution_quality_score: float

@dataclass
class RegimeContribution:
    """Regime-specific contribution data"""
    regime_name: str
    periods_active: int
    total_contribution: float
    average_contribution: float
    sharpe_ratio: float
    max_drawdown: float
    confidence_score: float
    transition_impact: float

@dataclass
class ComponentContribution:
    """Phase 3 component contribution data"""
    component_name: str
    total_contribution: float
    average_contribution: float
    contribution_volatility: float
    hit_rate: float
    confidence_correlation: float
    regime_consistency: float

@dataclass
class ConfidencePerformanceCorrelation:
    """Confidence score vs performance correlation analysis"""
    overall_correlation: float
    regime_correlations: Dict[str, float]
    component_correlations: Dict[str, float]
    confidence_buckets: Dict[str, Dict[str, float]]  # High/Medium/Low confidence performance
    predictive_power: float

@dataclass
class AttributionDisplaySnapshot:
    """Complete attribution display snapshot"""
    timestamp: datetime
    attribution_breakdown: AttributionBreakdown
    regime_contributions: List[RegimeContribution]
    component_contributions: List[ComponentContribution]
    confidence_correlation: ConfidencePerformanceCorrelation
    rolling_attribution: Dict[str, List[float]]  # Rolling attribution over time
    attribution_trends: Dict[str, str]  # Improving/Declining/Stable
    quality_metrics: Dict[str, float]

class PerformanceAttributionDisplay:
    """
    Real-time performance attribution display system
    
    Provides comprehensive attribution analysis:
    - Real-time attribution breakdown by regime and component
    - Confidence score correlation with performance
    - Attribution quality and trend analysis
    - Interactive visualization data preparation
    """
    
    def __init__(self,
                 regime_attribution_engine: RegimeBasedAttributionEngine,
                 component_attribution: Phase3ComponentAttribution,
                 multi_dimensional_decomposer: MultiDimensionalDecomposer,
                 intelligence_monitor: Phase3IntelligenceMonitor,
                 event_bus: EventBus,
                 display_window: int = 500):
        """
        Initialize performance attribution display
        
        Args:
            regime_attribution_engine: Regime-based attribution engine
            component_attribution: Phase 3 component attribution
            multi_dimensional_decomposer: Multi-dimensional decomposer
            intelligence_monitor: Phase 3 intelligence monitor
            event_bus: System event bus
            display_window: Number of periods to maintain in display history
        """
        self.regime_attribution_engine = regime_attribution_engine
        self.component_attribution = component_attribution
        self.multi_dimensional_decomposer = multi_dimensional_decomposer
        self.intelligence_monitor = intelligence_monitor
        self.event_bus = event_bus
        self.display_window = display_window
        
        # Display state
        self.attribution_history: deque = deque(maxlen=display_window)
        self.regime_performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=display_window))
        self.component_performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=display_window))
        self.confidence_performance_pairs: deque = deque(maxlen=display_window)
        
        # Rolling calculations
        self.rolling_windows = {
            'short': 20,   # 20 periods
            'medium': 60,  # 60 periods
            'long': 120    # 120 periods
        }
        
        # Quality thresholds
        self.attribution_quality_threshold = 0.7
        self.correlation_significance_threshold = 0.3
        self.trend_detection_periods = 30
        
        # Performance tracking
        self.total_updates = 0
        self.last_attribution_quality = 0.0
        
        logger.info("PerformanceAttributionDisplay initialized")
    
    def update_attribution_display(self, 
                                 portfolio_returns: pd.Series,
                                 market_data: pd.DataFrame) -> AttributionDisplaySnapshot:
        """
        Update attribution display with latest performance data
        
        Args:
            portfolio_returns: Portfolio return series
            market_data: Market data for attribution analysis
            
        Returns:
            Complete attribution display snapshot
        """
        try:
            timestamp = datetime.now()
            self.total_updates += 1
            
            # Get current intelligence state
            intelligence_snapshot = self.intelligence_monitor.get_current_snapshot()
            
            # Calculate attribution breakdown
            attribution_breakdown = self._calculate_attribution_breakdown(
                portfolio_returns, market_data, intelligence_snapshot
            )
            
            # Calculate regime contributions
            regime_contributions = self._calculate_regime_contributions(
                portfolio_returns, market_data, intelligence_snapshot
            )
            
            # Calculate component contributions
            component_contributions = self._calculate_component_contributions(
                portfolio_returns, market_data, intelligence_snapshot
            )
            
            # Calculate confidence-performance correlation
            confidence_correlation = self._calculate_confidence_correlation(
                portfolio_returns, intelligence_snapshot
            )
            
            # Calculate rolling attribution
            rolling_attribution = self._calculate_rolling_attribution()
            
            # Detect attribution trends
            attribution_trends = self._detect_attribution_trends()
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(attribution_breakdown)
            
            # Create display snapshot
            snapshot = AttributionDisplaySnapshot(
                timestamp=timestamp,
                attribution_breakdown=attribution_breakdown,
                regime_contributions=regime_contributions,
                component_contributions=component_contributions,
                confidence_correlation=confidence_correlation,
                rolling_attribution=rolling_attribution,
                attribution_trends=attribution_trends,
                quality_metrics=quality_metrics
            )
            
            # Store snapshot
            self.attribution_history.append(snapshot)
            
            # Update performance histories
            self._update_performance_histories(
                portfolio_returns, intelligence_snapshot, attribution_breakdown
            )
            
            # Emit display update event
            self.event_bus.emit('performance_attribution_display_updated', {
                'snapshot': snapshot,
                'quality_score': attribution_breakdown.attribution_quality_score,
                'trends': attribution_trends
            })
            
            logger.debug(f"Performance attribution display updated - "
                        f"Quality: {attribution_breakdown.attribution_quality_score:.3f}, "
                        f"Unexplained: {attribution_breakdown.unexplained_alpha:.3f}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error updating performance attribution display: {e}")
            raise
    
    def _calculate_attribution_breakdown(self, 
                                       portfolio_returns: pd.Series,
                                       market_data: pd.DataFrame,
                                       intelligence_snapshot: Optional[Any]) -> AttributionBreakdown:
        """Calculate comprehensive attribution breakdown"""
        try:
            # Get regime attribution
            regime_attribution = self.regime_attribution_engine.calculate_regime_attribution(
                portfolio_returns, market_data
            )
            
            # Get component attribution
            component_attribution = self.component_attribution.calculate_component_attribution(
                portfolio_returns, market_data
            )
            
            # Get multi-dimensional decomposition
            decomposition = self.multi_dimensional_decomposer.decompose_performance(
                portfolio_returns, market_data
            )
            
            # Calculate total return
            total_return = portfolio_returns.sum() if len(portfolio_returns) > 0 else 0.0
            
            # Extract attribution components
            regime_attr = regime_attribution.get('regime_contributions', {})
            component_attr = component_attribution.get('component_contributions', {})
            interaction_effects = decomposition.get('interaction_effects', {})
            unexplained_alpha = decomposition.get('unexplained_alpha', 0.0)
            
            # Calculate confidence-weighted return
            confidence_weighted_return = 0.0
            if intelligence_snapshot and intelligence_snapshot.anticipatory_state.confidence_scores:
                avg_confidence = np.mean(list(intelligence_snapshot.anticipatory_state.confidence_scores.values()))
                confidence_weighted_return = total_return * avg_confidence
            
            # Calculate attribution quality score
            explained_return = sum(regime_attr.values()) + sum(component_attr.values())
            attribution_quality_score = 1.0 - abs(unexplained_alpha) / max(abs(total_return), 0.001)
            attribution_quality_score = max(0.0, min(1.0, attribution_quality_score))
            
            return AttributionBreakdown(
                total_return=total_return,
                regime_attribution=regime_attr,
                component_attribution=component_attr,
                interaction_effects=interaction_effects,
                unexplained_alpha=unexplained_alpha,
                confidence_weighted_return=confidence_weighted_return,
                attribution_quality_score=attribution_quality_score
            )
            
        except Exception as e:
            logger.warning(f"Error calculating attribution breakdown: {e}")
            return AttributionBreakdown(
                total_return=0.0,
                regime_attribution={},
                component_attribution={},
                interaction_effects={},
                unexplained_alpha=0.0,
                confidence_weighted_return=0.0,
                attribution_quality_score=0.0
            )
    
    def _calculate_regime_contributions(self, 
                                     portfolio_returns: pd.Series,
                                     market_data: pd.DataFrame,
                                     intelligence_snapshot: Optional[Any]) -> List[RegimeContribution]:
        """Calculate detailed regime contributions"""
        try:
            contributions = []
            
            # Get regime attribution details
            regime_details = self.regime_attribution_engine.get_detailed_regime_analysis(
                portfolio_returns, market_data
            )
            
            for regime_name, details in regime_details.items():
                # Calculate regime-specific metrics
                regime_returns = details.get('returns', [])
                periods_active = len(regime_returns)
                
                if periods_active > 0:
                    total_contribution = sum(regime_returns)
                    average_contribution = total_contribution / periods_active
                    
                    # Calculate Sharpe ratio for regime
                    if len(regime_returns) > 1:
                        regime_volatility = np.std(regime_returns)
                        sharpe_ratio = average_contribution / regime_volatility if regime_volatility > 0 else 0.0
                    else:
                        sharpe_ratio = 0.0
                    
                    # Calculate max drawdown for regime
                    if len(regime_returns) > 1:
                        cumulative = np.cumsum(regime_returns)
                        peak = np.maximum.accumulate(cumulative)
                        drawdown = (cumulative - peak) / np.maximum(peak, 0.001)
                        max_drawdown = np.min(drawdown)
                    else:
                        max_drawdown = 0.0
                    
                    # Get confidence score
                    confidence_score = details.get('average_confidence', 0.0)
                    
                    # Calculate transition impact
                    transition_impact = details.get('transition_impact', 0.0)
                    
                    contribution = RegimeContribution(
                        regime_name=regime_name,
                        periods_active=periods_active,
                        total_contribution=total_contribution,
                        average_contribution=average_contribution,
                        sharpe_ratio=sharpe_ratio,
                        max_drawdown=max_drawdown,
                        confidence_score=confidence_score,
                        transition_impact=transition_impact
                    )
                    
                    contributions.append(contribution)
            
            # Sort by total contribution
            contributions.sort(key=lambda x: abs(x.total_contribution), reverse=True)
            
            return contributions
            
        except Exception as e:
            logger.warning(f"Error calculating regime contributions: {e}")
            return []
    
    def _calculate_component_contributions(self, 
                                        portfolio_returns: pd.Series,
                                        market_data: pd.DataFrame,
                                        intelligence_snapshot: Optional[Any]) -> List[ComponentContribution]:
        """Calculate detailed component contributions"""
        try:
            contributions = []
            
            # Get component attribution details
            component_details = self.component_attribution.get_detailed_component_analysis(
                portfolio_returns, market_data
            )
            
            for component_name, details in component_details.items():
                component_returns = details.get('returns', [])
                
                if len(component_returns) > 0:
                    total_contribution = sum(component_returns)
                    average_contribution = np.mean(component_returns)
                    contribution_volatility = np.std(component_returns) if len(component_returns) > 1 else 0.0
                    
                    # Calculate hit rate (positive contribution periods)
                    positive_periods = sum(1 for r in component_returns if r > 0)
                    hit_rate = positive_periods / len(component_returns)
                    
                    # Get confidence correlation
                    confidence_correlation = details.get('confidence_correlation', 0.0)
                    
                    # Calculate regime consistency
                    regime_consistency = details.get('regime_consistency', 0.0)
                    
                    contribution = ComponentContribution(
                        component_name=component_name,
                        total_contribution=total_contribution,
                        average_contribution=average_contribution,
                        contribution_volatility=contribution_volatility,
                        hit_rate=hit_rate,
                        confidence_correlation=confidence_correlation,
                        regime_consistency=regime_consistency
                    )
                    
                    contributions.append(contribution)
            
            # Sort by total contribution
            contributions.sort(key=lambda x: abs(x.total_contribution), reverse=True)
            
            return contributions
            
        except Exception as e:
            logger.warning(f"Error calculating component contributions: {e}")
            return []
    
    def _calculate_confidence_correlation(self, 
                                        portfolio_returns: pd.Series,
                                        intelligence_snapshot: Optional[Any]) -> ConfidencePerformanceCorrelation:
        """Calculate confidence score vs performance correlation"""
        try:
            # Store confidence-performance pairs
            if intelligence_snapshot and intelligence_snapshot.anticipatory_state.confidence_scores:
                avg_confidence = np.mean(list(intelligence_snapshot.anticipatory_state.confidence_scores.values()))
                current_return = portfolio_returns.iloc[-1] if len(portfolio_returns) > 0 else 0.0
                
                self.confidence_performance_pairs.append((avg_confidence, current_return))
            
            # Calculate overall correlation
            overall_correlation = 0.0
            if len(self.confidence_performance_pairs) >= 10:
                confidences, returns = zip(*self.confidence_performance_pairs)
                correlation_matrix = np.corrcoef(confidences, returns)
                overall_correlation = correlation_matrix[0, 1] if not np.isnan(correlation_matrix[0, 1]) else 0.0
            
            # Calculate regime-specific correlations (simplified)
            regime_correlations = {}
            current_regime = intelligence_snapshot.regime_state.current_regime if intelligence_snapshot else None
            if current_regime:
                regime_correlations[current_regime] = overall_correlation  # Simplified
            
            # Calculate component-specific correlations (simplified)
            component_correlations = {}
            if intelligence_snapshot and intelligence_snapshot.tailwind_state.current_tailwinds:
                for component in intelligence_snapshot.tailwind_state.current_tailwinds:
                    component_correlations[component] = overall_correlation * 0.8  # Simplified
            
            # Calculate confidence bucket performance
            confidence_buckets = self._calculate_confidence_buckets()
            
            # Calculate predictive power (simplified)
            predictive_power = abs(overall_correlation) if abs(overall_correlation) > self.correlation_significance_threshold else 0.0
            
            return ConfidencePerformanceCorrelation(
                overall_correlation=overall_correlation,
                regime_correlations=regime_correlations,
                component_correlations=component_correlations,
                confidence_buckets=confidence_buckets,
                predictive_power=predictive_power
            )
            
        except Exception as e:
            logger.warning(f"Error calculating confidence correlation: {e}")
            return ConfidencePerformanceCorrelation(
                overall_correlation=0.0,
                regime_correlations={},
                component_correlations={},
                confidence_buckets={},
                predictive_power=0.0
            )
    
    def _calculate_confidence_buckets(self) -> Dict[str, Dict[str, float]]:
        """Calculate performance by confidence buckets"""
        try:
            if len(self.confidence_performance_pairs) < 10:
                return {}
            
            # Separate into confidence buckets
            high_conf_returns = []
            medium_conf_returns = []
            low_conf_returns = []
            
            for confidence, return_val in self.confidence_performance_pairs:
                if confidence > 0.7:
                    high_conf_returns.append(return_val)
                elif confidence > 0.4:
                    medium_conf_returns.append(return_val)
                else:
                    low_conf_returns.append(return_val)
            
            buckets = {}
            
            for bucket_name, returns in [
                ('high', high_conf_returns),
                ('medium', medium_conf_returns),
                ('low', low_conf_returns)
            ]:
                if returns:
                    buckets[bucket_name] = {
                        'avg_return': np.mean(returns),
                        'volatility': np.std(returns),
                        'sharpe': np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0.0,
                        'hit_rate': sum(1 for r in returns if r > 0) / len(returns),
                        'count': len(returns)
                    }
            
            return buckets
            
        except Exception as e:
            logger.warning(f"Error calculating confidence buckets: {e}")
            return {}
    
    def _calculate_rolling_attribution(self) -> Dict[str, List[float]]:
        """Calculate rolling attribution over different time windows"""
        try:
            rolling_attribution = {}
            
            if len(self.attribution_history) < 10:
                return rolling_attribution
            
            # Calculate rolling attribution for each window
            for window_name, window_size in self.rolling_windows.items():
                recent_snapshots = list(self.attribution_history)[-window_size:]
                
                if len(recent_snapshots) >= 5:
                    # Aggregate regime attribution
                    regime_rolling = defaultdict(list)
                    component_rolling = defaultdict(list)
                    
                    for snapshot in recent_snapshots:
                        for regime, contribution in snapshot.attribution_breakdown.regime_attribution.items():
                            regime_rolling[f"regime_{regime}"].append(contribution)
                        
                        for component, contribution in snapshot.attribution_breakdown.component_attribution.items():
                            component_rolling[f"component_{component}"].append(contribution)
                    
                    # Calculate rolling averages
                    for regime, contributions in regime_rolling.items():
                        rolling_attribution[f"{window_name}_{regime}"] = [np.mean(contributions)]
                    
                    for component, contributions in component_rolling.items():
                        rolling_attribution[f"{window_name}_{component}"] = [np.mean(contributions)]
            
            return rolling_attribution
            
        except Exception as e:
            logger.warning(f"Error calculating rolling attribution: {e}")
            return {}
    
    def _detect_attribution_trends(self) -> Dict[str, str]:
        """Detect trends in attribution components"""
        try:
            trends = {}
            
            if len(self.attribution_history) < self.trend_detection_periods:
                return trends
            
            recent_snapshots = list(self.attribution_history)[-self.trend_detection_periods:]
            
            # Analyze regime attribution trends
            regime_trends = defaultdict(list)
            component_trends = defaultdict(list)
            
            for snapshot in recent_snapshots:
                for regime, contribution in snapshot.attribution_breakdown.regime_attribution.items():
                    regime_trends[regime].append(contribution)
                
                for component, contribution in snapshot.attribution_breakdown.component_attribution.items():
                    component_trends[component].append(contribution)
            
            # Calculate trends
            for regime, contributions in regime_trends.items():
                if len(contributions) >= 5:
                    trend = self._calculate_trend_direction(contributions)
                    trends[f"regime_{regime}"] = trend
            
            for component, contributions in component_trends.items():
                if len(contributions) >= 5:
                    trend = self._calculate_trend_direction(contributions)
                    trends[f"component_{component}"] = trend
            
            # Overall attribution quality trend
            quality_scores = [s.attribution_breakdown.attribution_quality_score for s in recent_snapshots]
            if quality_scores:
                trends['attribution_quality'] = self._calculate_trend_direction(quality_scores)
            
            return trends
            
        except Exception as e:
            logger.warning(f"Error detecting attribution trends: {e}")
            return {}
    
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """Calculate trend direction from values"""
        if len(values) < 3:
            return "insufficient_data"
        
        # Simple linear trend
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if slope > 0.001:
            return "improving"
        elif slope < -0.001:
            return "declining"
        else:
            return "stable"
    
    def _calculate_quality_metrics(self, attribution_breakdown: AttributionBreakdown) -> Dict[str, float]:
        """Calculate attribution quality metrics"""
        try:
            metrics = {}
            
            # Attribution coverage (how much is explained)
            total_explained = (sum(attribution_breakdown.regime_attribution.values()) + 
                             sum(attribution_breakdown.component_attribution.values()))
            
            if attribution_breakdown.total_return != 0:
                coverage = abs(total_explained) / abs(attribution_breakdown.total_return)
                metrics['attribution_coverage'] = min(1.0, coverage)
            else:
                metrics['attribution_coverage'] = 0.0
            
            # Attribution consistency (low unexplained alpha)
            if attribution_breakdown.total_return != 0:
                consistency = 1.0 - abs(attribution_breakdown.unexplained_alpha) / abs(attribution_breakdown.total_return)
                metrics['attribution_consistency'] = max(0.0, min(1.0, consistency))
            else:
                metrics['attribution_consistency'] = 1.0
            
            # Component balance (not dominated by single component)
            if attribution_breakdown.component_attribution:
                contributions = list(attribution_breakdown.component_attribution.values())
                max_contribution = max(abs(c) for c in contributions)
                total_contribution = sum(abs(c) for c in contributions)
                
                if total_contribution > 0:
                    balance = 1.0 - (max_contribution / total_contribution)
                    metrics['component_balance'] = balance
                else:
                    metrics['component_balance'] = 1.0
            else:
                metrics['component_balance'] = 0.0
            
            # Overall quality score
            metrics['overall_quality'] = attribution_breakdown.attribution_quality_score
            
            return metrics
            
        except Exception as e:
            logger.warning(f"Error calculating quality metrics: {e}")
            return {}
    
    def _update_performance_histories(self, 
                                    portfolio_returns: pd.Series,
                                    intelligence_snapshot: Optional[Any],
                                    attribution_breakdown: AttributionBreakdown):
        """Update performance history tracking"""
        try:
            # Update regime performance history
            if intelligence_snapshot and intelligence_snapshot.regime_state.current_regime:
                current_regime = intelligence_snapshot.regime_state.current_regime
                current_return = portfolio_returns.iloc[-1] if len(portfolio_returns) > 0 else 0.0
                self.regime_performance_history[current_regime].append(current_return)
            
            # Update component performance history
            for component, contribution in attribution_breakdown.component_attribution.items():
                self.component_performance_history[component].append(contribution)
            
        except Exception as e:
            logger.warning(f"Error updating performance histories: {e}")
    
    def get_attribution_summary(self) -> Dict[str, Any]:
        """Get comprehensive attribution summary"""
        try:
            current_snapshot = self.attribution_history[-1] if self.attribution_history else None
            
            if not current_snapshot:
                return {"status": "no_data"}
            
            # Calculate summary statistics
            total_regime_contribution = sum(current_snapshot.attribution_breakdown.regime_attribution.values())
            total_component_contribution = sum(current_snapshot.attribution_breakdown.component_attribution.values())
            
            # Top contributors
            top_regimes = sorted(
                current_snapshot.attribution_breakdown.regime_attribution.items(),
                key=lambda x: abs(x[1]), reverse=True
            )[:3]
            
            top_components = sorted(
                current_snapshot.attribution_breakdown.component_attribution.items(),
                key=lambda x: abs(x[1]), reverse=True
            )[:3]
            
            return {
                "status": "active",
                "timestamp": current_snapshot.timestamp,
                "attribution": {
                    "total_return": current_snapshot.attribution_breakdown.total_return,
                    "regime_contribution": total_regime_contribution,
                    "component_contribution": total_component_contribution,
                    "unexplained_alpha": current_snapshot.attribution_breakdown.unexplained_alpha,
                    "quality_score": current_snapshot.attribution_breakdown.attribution_quality_score,
                    "confidence_weighted_return": current_snapshot.attribution_breakdown.confidence_weighted_return
                },
                "top_contributors": {
                    "regimes": [{"name": name, "contribution": contrib} for name, contrib in top_regimes],
                    "components": [{"name": name, "contribution": contrib} for name, contrib in top_components]
                },
                "confidence_analysis": {
                    "overall_correlation": current_snapshot.confidence_correlation.overall_correlation,
                    "predictive_power": current_snapshot.confidence_correlation.predictive_power,
                    "confidence_buckets": current_snapshot.confidence_correlation.confidence_buckets
                },
                "quality_metrics": current_snapshot.quality_metrics,
                "trends": current_snapshot.attribution_trends,
                "regime_details": [
                    {
                        "name": contrib.regime_name,
                        "periods_active": contrib.periods_active,
                        "total_contribution": contrib.total_contribution,
                        "sharpe_ratio": contrib.sharpe_ratio,
                        "confidence": contrib.confidence_score
                    }
                    for contrib in current_snapshot.regime_contributions[:5]
                ],
                "component_details": [
                    {
                        "name": contrib.component_name,
                        "total_contribution": contrib.total_contribution,
                        "hit_rate": contrib.hit_rate,
                        "volatility": contrib.contribution_volatility,
                        "confidence_correlation": contrib.confidence_correlation
                    }
                    for contrib in current_snapshot.component_contributions[:5]
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating attribution summary: {e}")
            return {"status": "error", "error": str(e)}
    
    def export_attribution_data(self, format: str = 'json') -> Union[str, Dict[str, Any]]:
        """Export attribution data for external analysis"""
        try:
            data = {
                "metadata": {
                    "export_timestamp": datetime.now().isoformat(),
                    "total_snapshots": len(self.attribution_history),
                    "display_window": self.display_window
                },
                "current_attribution": self.get_attribution_summary(),
                "historical_attribution": [
                    {
                        "timestamp": snapshot.timestamp.isoformat(),
                        "total_return": snapshot.attribution_breakdown.total_return,
                        "regime_attribution": snapshot.attribution_breakdown.regime_attribution,
                        "component_attribution": snapshot.attribution_breakdown.component_attribution,
                        "quality_score": snapshot.attribution_breakdown.attribution_quality_score,
                        "unexplained_alpha": snapshot.attribution_breakdown.unexplained_alpha
                    }
                    for snapshot in list(self.attribution_history)[-100:]
                ],
                "performance_correlation": {
                    "confidence_performance_pairs": [
                        {"confidence": conf, "return": ret}
                        for conf, ret in list(self.confidence_performance_pairs)[-100:]
                    ]
                }
            }
            
            if format.lower() == 'json':
                return json.dumps(data, indent=2, default=str)
            else:
                return data
                
        except Exception as e:
            logger.error(f"Error exporting attribution data: {e}")
            return {"error": str(e)}
    
    def reset_display(self):
        """Reset display state (for testing)"""
        self.attribution_history.clear()
        self.regime_performance_history.clear()
        self.component_performance_history.clear()
        self.confidence_performance_pairs.clear()
        
        self.total_updates = 0
        self.last_attribution_quality = 0.0
        
        logger.info("Performance attribution display reset")