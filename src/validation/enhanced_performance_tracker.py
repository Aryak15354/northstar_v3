"""
Enhanced Performance Tracker

Integrates Phase 4.5 Advanced Performance Attribution System with existing
V3 performance tracking infrastructure. Builds upon existing PerformanceTracker
with Phase 3 component attribution and institutional-grade reporting.

This enhanced tracker provides:
- Integration with existing V3 performance tracking
- Phase 3 component attribution tracking
- Regime-based performance analysis
- Multi-dimensional attribution
- Institutional reporting capabilities
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from pathlib import Path

# Import existing V3 performance tracking
from src.validation.performance_tracker import PerformanceTracker

# Import Phase 4.5 attribution engines
from src.validation.regime_based_attribution_engine import (
    RegimeBasedAttributionEngine, RegimeAttributionResult
)
from src.validation.phase3_component_attribution import (
    Phase3ComponentAttribution, Phase3ComponentAttributionResult
)
from src.validation.multi_dimensional_decomposer import (
    MultiDimensionalDecomposer, MultiDimensionalDecompositionResult
)
from src.validation.institutional_report_generator import (
    InstitutionalReportGenerator, InstitutionalReportConfig, InstitutionalReport
)

from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class EnhancedPerformanceMetrics:
    """Enhanced performance metrics with Phase 3 attribution"""
    # Basic metrics from existing tracker
    basic_metrics: Dict[str, float]
    
    # Phase 3 attribution metrics
    regime_attribution: Optional[RegimeAttributionResult]
    component_attribution: Optional[Phase3ComponentAttributionResult]
    multi_dimensional_attribution: Optional[MultiDimensionalDecompositionResult]
    
    # Enhanced metrics
    phase3_intelligence_score: float
    attribution_quality_score: float
    institutional_grade_rating: str
    
    # Tracking metadata
    tracking_period: Tuple[datetime, datetime]
    last_updated: datetime

@dataclass
class PerformanceTrackingConfig:
    """Configuration for enhanced performance tracking"""
    enable_regime_attribution: bool = True
    enable_component_attribution: bool = True
    enable_multi_dimensional_attribution: bool = True
    enable_institutional_reporting: bool = True
    attribution_frequency: str = "daily"  # daily, weekly, monthly
    reporting_frequency: str = "monthly"
    min_tracking_periods: int = 30
    benchmark_symbol: Optional[str] = None

class EnhancedPerformanceTracker(PerformanceTracker):
    """
    Enhanced Performance Tracker with Phase 3 Attribution
    
    Extends the existing V3 PerformanceTracker with advanced attribution
    capabilities and institutional-grade reporting.
    """
    
    def __init__(self, config: Optional[PerformanceTrackingConfig] = None):
        # Initialize parent class
        super().__init__()
        
        self.name = "Enhanced Performance Tracker"
        self.version = "2.0"
        
        # Configuration
        self.config = config or PerformanceTrackingConfig()
        
        # Initialize Phase 4.5 attribution engines
        self.regime_attribution_engine = RegimeBasedAttributionEngine()
        self.component_attribution_engine = Phase3ComponentAttribution()
        self.multi_dimensional_decomposer = MultiDimensionalDecomposer()
        self.institutional_report_generator = InstitutionalReportGenerator()
        
        # Enhanced tracking state
        self.enhanced_metrics_history: List[EnhancedPerformanceMetrics] = []
        self.attribution_cache: Dict[str, Any] = {}
        self.institutional_reports: Dict[str, InstitutionalReport] = {}
        
        # Integration paths
        self.enhanced_data_path = Path("data/performance/enhanced")
        self.enhanced_data_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📊 {self.name} v{self.version} initialized")
        logger.info(f"🔗 Enhanced with Phase 3 attribution capabilities")
        logger.info(f"💡 Configuration: {self.config}")
    
    def track_enhanced_performance(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        phase3_signals: Optional[Dict[str, pd.Series]] = None,
        force_update: bool = False
    ) -> EnhancedPerformanceMetrics:
        """
        Track performance with enhanced Phase 3 attribution
        
        Args:
            portfolio_returns: Portfolio returns time series
            benchmark_returns: Optional benchmark returns
            phase3_signals: Optional Phase 3 component signals
            force_update: Force recalculation even if cached
            
        Returns:
            Enhanced performance metrics with attribution
        """
        logger.info(f"📊 {self.name} - Tracking Enhanced Performance")
        logger.info(f"📈 Portfolio periods: {len(portfolio_returns)}")
        
        # Check minimum periods requirement
        if len(portfolio_returns) < self.config.min_tracking_periods:
            logger.warning(f"Insufficient data: {len(portfolio_returns)} < {self.config.min_tracking_periods}")
            return self._create_minimal_metrics(portfolio_returns)
        
        # Track basic performance using parent class
        basic_metrics = self._track_basic_performance(portfolio_returns, benchmark_returns)
        
        # Calculate Phase 3 attributions
        regime_attribution = None
        component_attribution = None
        multi_dimensional_attribution = None
        
        if phase3_signals:
            # Regime attribution
            if self.config.enable_regime_attribution and 'regime_classification' in phase3_signals:
                regime_attribution = self._calculate_regime_attribution(
                    portfolio_returns, phase3_signals, benchmark_returns
                )
            
            # Component attribution
            if self.config.enable_component_attribution:
                component_attribution = self._calculate_component_attribution(
                    portfolio_returns, phase3_signals, benchmark_returns
                )
            
            # Multi-dimensional attribution
            if self.config.enable_multi_dimensional_attribution:
                multi_dimensional_attribution = self._calculate_multi_dimensional_attribution(
                    portfolio_returns, phase3_signals, benchmark_returns
                )
        
        # Calculate enhanced metrics
        phase3_intelligence_score = self._calculate_phase3_intelligence_score(
            regime_attribution, component_attribution, multi_dimensional_attribution
        )
        
        attribution_quality_score = self._calculate_attribution_quality_score(
            regime_attribution, component_attribution, multi_dimensional_attribution
        )
        
        institutional_grade_rating = self._calculate_institutional_grade_rating(
            basic_metrics, phase3_intelligence_score, attribution_quality_score
        )
        
        # Create enhanced metrics
        enhanced_metrics = EnhancedPerformanceMetrics(
            basic_metrics=basic_metrics,
            regime_attribution=regime_attribution,
            component_attribution=component_attribution,
            multi_dimensional_attribution=multi_dimensional_attribution,
            phase3_intelligence_score=phase3_intelligence_score,
            attribution_quality_score=attribution_quality_score,
            institutional_grade_rating=institutional_grade_rating,
            tracking_period=(portfolio_returns.index[0], portfolio_returns.index[-1]),
            last_updated=datetime.now()
        )
        
        # Store in history
        self.enhanced_metrics_history.append(enhanced_metrics)
        
        # Save enhanced metrics
        self._save_enhanced_metrics(enhanced_metrics)
        
        logger.info(f"✅ Enhanced performance tracking completed")
        logger.info(f"🧠 Phase 3 Intelligence Score: {phase3_intelligence_score:.3f}")
        logger.info(f"📊 Attribution Quality Score: {attribution_quality_score:.3f}")
        logger.info(f"🏆 Institutional Grade: {institutional_grade_rating}")
        
        return enhanced_metrics
    
    def _track_basic_performance(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series]
    ) -> Dict[str, float]:
        """Track basic performance using parent class functionality"""
        
        try:
            # Use parent class methods for basic tracking
            # This maintains compatibility with existing V3 infrastructure
            
            basic_metrics = {}
            
            # Calculate basic return metrics
            total_return = (1 + portfolio_returns).prod() - 1
            annualized_return = (1 + portfolio_returns.mean()) ** 252 - 1
            volatility = portfolio_returns.std() * np.sqrt(252)
            sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
            
            # Drawdown analysis
            cumulative_returns = (1 + portfolio_returns).cumprod()
            running_max = cumulative_returns.expanding().max()
            drawdown = (cumulative_returns - running_max) / running_max
            max_drawdown = drawdown.min()
            
            basic_metrics.update({
                'total_return': total_return,
                'annualized_return': annualized_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'periods_tracked': len(portfolio_returns)
            })
            
            # Add benchmark-relative metrics if available
            if benchmark_returns is not None:
                excess_returns = portfolio_returns - benchmark_returns
                tracking_error = excess_returns.std() * np.sqrt(252)
                information_ratio = excess_returns.mean() * np.sqrt(252) / tracking_error if tracking_error > 0 else 0
                
                basic_metrics.update({
                    'tracking_error': tracking_error,
                    'information_ratio': information_ratio,
                    'benchmark_correlation': portfolio_returns.corr(benchmark_returns)
                })
            
            return basic_metrics
            
        except Exception as e:
            logger.error(f"Error in basic performance tracking: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_regime_attribution(
        self,
        portfolio_returns: pd.Series,
        phase3_signals: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series]
    ) -> Optional[RegimeAttributionResult]:
        """Calculate regime-based attribution"""
        
        try:
            if 'regime_classification' not in phase3_signals:
                return None
            
            regime_classification = phase3_signals['regime_classification']
            regime_similarity_scores = phase3_signals.get('regime_similarity_score')
            
            return self.regime_attribution_engine.calculate_regime_attribution(
                portfolio_returns, regime_classification, benchmark_returns, regime_similarity_scores
            )
            
        except Exception as e:
            logger.warning(f"Error in regime attribution: {str(e)}")
            return None
    
    def _calculate_component_attribution(
        self,
        portfolio_returns: pd.Series,
        phase3_signals: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series]
    ) -> Optional[Phase3ComponentAttributionResult]:
        """Calculate Phase 3 component attribution"""
        
        try:
            return self.component_attribution_engine.calculate_phase3_component_attribution(
                portfolio_returns, phase3_signals, benchmark_returns
            )
            
        except Exception as e:
            logger.warning(f"Error in component attribution: {str(e)}")
            return None
    
    def _calculate_multi_dimensional_attribution(
        self,
        portfolio_returns: pd.Series,
        phase3_signals: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series]
    ) -> Optional[MultiDimensionalDecompositionResult]:
        """Calculate multi-dimensional attribution"""
        
        try:
            # Prepare dimensions for multi-dimensional analysis
            dimensions = {}
            
            if 'regime_classification' in phase3_signals:
                dimensions['regime'] = phase3_signals['regime_classification']
            
            if 'tailwind_scores' in phase3_signals:
                dimensions['tailwinds'] = phase3_signals['tailwind_scores']
            
            if 'no_edge_state' in phase3_signals:
                dimensions['no_edge'] = phase3_signals['no_edge_state']
            
            if 'anticipatory_allocation' in phase3_signals:
                dimensions['anticipatory'] = phase3_signals['anticipatory_allocation']
            
            if not dimensions:
                return None
            
            return self.multi_dimensional_decomposer.decompose_performance_multi_dimensional(
                portfolio_returns, dimensions, benchmark_returns
            )
            
        except Exception as e:
            logger.warning(f"Error in multi-dimensional attribution: {str(e)}")
            return None
    
    def _calculate_phase3_intelligence_score(
        self,
        regime_attribution: Optional[RegimeAttributionResult],
        component_attribution: Optional[Phase3ComponentAttributionResult],
        multi_dimensional_attribution: Optional[MultiDimensionalDecompositionResult]
    ) -> float:
        """Calculate Phase 3 intelligence effectiveness score"""
        
        intelligence_score = 0.0
        
        try:
            # Score from regime attribution
            if regime_attribution:
                regime_timing_alpha = regime_attribution.regime_timing_alpha
                intelligence_score += min(abs(regime_timing_alpha) * 10, 0.3)  # Cap at 0.3
            
            # Score from component attribution
            if component_attribution:
                attribution_r_squared = component_attribution.attribution_r_squared
                intelligence_score += attribution_r_squared * 0.4  # Up to 0.4
            
            # Score from multi-dimensional attribution
            if multi_dimensional_attribution:
                model_r_squared = multi_dimensional_attribution.model_r_squared
                intelligence_score += model_r_squared * 0.3  # Up to 0.3
            
            # Normalize to 0-1 range
            intelligence_score = min(intelligence_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating Phase 3 intelligence score: {str(e)}")
            intelligence_score = 0.0
        
        return intelligence_score
    
    def _calculate_attribution_quality_score(
        self,
        regime_attribution: Optional[RegimeAttributionResult],
        component_attribution: Optional[Phase3ComponentAttributionResult],
        multi_dimensional_attribution: Optional[MultiDimensionalDecompositionResult]
    ) -> float:
        """Calculate attribution quality score"""
        
        quality_score = 0.0
        
        try:
            # Quality from regime attribution
            if regime_attribution:
                # Check if unexplained alpha is low (good attribution)
                total_return = regime_attribution.total_portfolio_return
                unexplained_ratio = abs(regime_attribution.unexplained_alpha) / (abs(total_return) + 1e-8)
                regime_quality = max(0, 1 - unexplained_ratio)
                quality_score += regime_quality * 0.3
            
            # Quality from component attribution
            if component_attribution:
                # R-squared indicates attribution quality
                quality_score += component_attribution.attribution_r_squared * 0.4
            
            # Quality from multi-dimensional attribution
            if multi_dimensional_attribution:
                # Adjusted R-squared indicates model quality
                quality_score += multi_dimensional_attribution.model_adjusted_r_squared * 0.3
            
            # Normalize to 0-1 range
            quality_score = min(quality_score, 1.0)
            
        except Exception as e:
            logger.warning(f"Error calculating attribution quality score: {str(e)}")
            quality_score = 0.0
        
        return quality_score
    
    def _calculate_institutional_grade_rating(
        self,
        basic_metrics: Dict[str, float],
        phase3_intelligence_score: float,
        attribution_quality_score: float
    ) -> str:
        """Calculate institutional grade rating"""
        
        try:
            # Performance criteria
            sharpe_ratio = basic_metrics.get('sharpe_ratio', 0)
            max_drawdown = basic_metrics.get('max_drawdown', 0)
            
            # Calculate composite score
            performance_score = 0.0
            
            # Sharpe ratio component (0-0.4)
            if sharpe_ratio > 2.0:
                performance_score += 0.4
            elif sharpe_ratio > 1.5:
                performance_score += 0.3
            elif sharpe_ratio > 1.0:
                performance_score += 0.2
            elif sharpe_ratio > 0.5:
                performance_score += 0.1
            
            # Drawdown component (0-0.2)
            if max_drawdown > -0.05:
                performance_score += 0.2
            elif max_drawdown > -0.10:
                performance_score += 0.15
            elif max_drawdown > -0.15:
                performance_score += 0.1
            elif max_drawdown > -0.20:
                performance_score += 0.05
            
            # Intelligence and attribution scores (0-0.4)
            intelligence_component = (phase3_intelligence_score + attribution_quality_score) / 2 * 0.4
            performance_score += intelligence_component
            
            # Determine rating
            if performance_score >= 0.8:
                return "AAA"
            elif performance_score >= 0.7:
                return "AA"
            elif performance_score >= 0.6:
                return "A"
            elif performance_score >= 0.5:
                return "BBB"
            elif performance_score >= 0.4:
                return "BB"
            elif performance_score >= 0.3:
                return "B"
            else:
                return "C"
                
        except Exception as e:
            logger.warning(f"Error calculating institutional grade: {str(e)}")
            return "NR"  # Not Rated
    
    def _create_minimal_metrics(self, portfolio_returns: pd.Series) -> EnhancedPerformanceMetrics:
        """Create minimal metrics when insufficient data"""
        
        basic_metrics = {
            'total_return': (1 + portfolio_returns).prod() - 1 if len(portfolio_returns) > 0 else 0,
            'periods_tracked': len(portfolio_returns),
            'insufficient_data': True
        }
        
        return EnhancedPerformanceMetrics(
            basic_metrics=basic_metrics,
            regime_attribution=None,
            component_attribution=None,
            multi_dimensional_attribution=None,
            phase3_intelligence_score=0.0,
            attribution_quality_score=0.0,
            institutional_grade_rating="NR",
            tracking_period=(
                portfolio_returns.index[0] if len(portfolio_returns) > 0 else datetime.now(),
                portfolio_returns.index[-1] if len(portfolio_returns) > 0 else datetime.now()
            ),
            last_updated=datetime.now()
        )
    
    def _save_enhanced_metrics(self, enhanced_metrics: EnhancedPerformanceMetrics) -> None:
        """Save enhanced metrics to storage"""
        
        try:
            # Save to JSON for easy access
            metrics_data = {
                'tracking_period': [
                    enhanced_metrics.tracking_period[0].isoformat(),
                    enhanced_metrics.tracking_period[1].isoformat()
                ],
                'last_updated': enhanced_metrics.last_updated.isoformat(),
                'basic_metrics': enhanced_metrics.basic_metrics,
                'phase3_intelligence_score': enhanced_metrics.phase3_intelligence_score,
                'attribution_quality_score': enhanced_metrics.attribution_quality_score,
                'institutional_grade_rating': enhanced_metrics.institutional_grade_rating
            }
            
            timestamp = enhanced_metrics.last_updated.strftime('%Y%m%d_%H%M%S')
            metrics_path = self.enhanced_data_path / f"enhanced_metrics_{timestamp}.json"
            
            import json
            with open(metrics_path, 'w') as f:
                json.dump(metrics_data, f, indent=2)
            
            logger.info(f"💾 Enhanced metrics saved to {metrics_path}")
            
        except Exception as e:
            logger.error(f"Error saving enhanced metrics: {str(e)}")
    
    def generate_institutional_report(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: pd.Series,
        phase3_signals: Dict[str, pd.Series],
        report_type: str = "tearsheet"
    ) -> Optional[InstitutionalReport]:
        """Generate institutional report using enhanced tracking data"""
        
        if not self.config.enable_institutional_reporting:
            logger.warning("Institutional reporting disabled in configuration")
            return None
        
        try:
            # Create report configuration
            report_config = InstitutionalReportConfig(
                report_type=report_type,
                report_period=(portfolio_returns.index[0], portfolio_returns.index[-1]),
                include_phase3_analysis=True,
                include_risk_analysis=True,
                include_compliance_section=True
            )
            
            # Generate report
            institutional_report = self.institutional_report_generator.generate_institutional_tearsheet(
                portfolio_returns, benchmark_returns, phase3_signals, report_config
            )
            
            # Store report
            self.institutional_reports[institutional_report.report_id] = institutional_report
            
            logger.info(f"📄 Institutional report generated: {institutional_report.report_id}")
            
            return institutional_report
            
        except Exception as e:
            logger.error(f"Error generating institutional report: {str(e)}")
            return None
    
    def get_latest_enhanced_metrics(self) -> Optional[EnhancedPerformanceMetrics]:
        """Get the latest enhanced performance metrics"""
        
        if not self.enhanced_metrics_history:
            return None
        
        return self.enhanced_metrics_history[-1]
    
    def get_enhanced_metrics_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[EnhancedPerformanceMetrics]:
        """Get enhanced metrics history for a date range"""
        
        if not start_date and not end_date:
            return self.enhanced_metrics_history
        
        filtered_metrics = []
        for metrics in self.enhanced_metrics_history:
            metrics_date = metrics.last_updated
            
            if start_date and metrics_date < start_date:
                continue
            if end_date and metrics_date > end_date:
                continue
                
            filtered_metrics.append(metrics)
        
        return filtered_metrics
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        
        latest_metrics = self.get_latest_enhanced_metrics()
        
        if not latest_metrics:
            return {'error': 'No enhanced metrics available'}
        
        summary = {
            'basic_performance': latest_metrics.basic_metrics,
            'phase3_intelligence_score': latest_metrics.phase3_intelligence_score,
            'attribution_quality_score': latest_metrics.attribution_quality_score,
            'institutional_grade_rating': latest_metrics.institutional_grade_rating,
            'tracking_period': latest_metrics.tracking_period,
            'last_updated': latest_metrics.last_updated,
            'attribution_available': {
                'regime_attribution': latest_metrics.regime_attribution is not None,
                'component_attribution': latest_metrics.component_attribution is not None,
                'multi_dimensional_attribution': latest_metrics.multi_dimensional_attribution is not None
            }
        }
        
        return summary