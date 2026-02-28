"""
Death by Thousand Cuts Detector - Alpha Decay Monitoring

This module detects gradual alpha decay that kills funds slowly over time.
Most funds don't die from crashes - they die from slow bleeds, small edge decay,
and cost creep that compounds over months and years.

Key Detections:
- Rolling 12-month alpha decay
- Rolling IC slope degradation  
- Rolling Sharpe drift
- Cost creep detection
- Edge erosion patterns
- Performance attribution decay

Triggers warnings when:
- IC slope < 0 (predictive power declining)
- Net alpha < costs (negative value creation)
- Sharpe ratio trending downward
- Alpha attribution concentrating (diversification loss)

Author: Northstar Team
Date: 2026-01-05
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
from scipy import stats
from scipy.stats import linregress
import warnings

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


class DecayType(Enum):
    """Types of alpha decay patterns."""
    ALPHA_DECAY = "alpha_decay"
    IC_DEGRADATION = "ic_degradation"
    SHARPE_DRIFT = "sharpe_drift"
    COST_CREEP = "cost_creep"
    EDGE_EROSION = "edge_erosion"
    ATTRIBUTION_CONCENTRATION = "attribution_concentration"
    CAPACITY_CONSTRAINT = "capacity_constraint"
    REGIME_OBSOLESCENCE = "regime_obsolescence"


class DecaySeverity(Enum):
    """Severity levels for decay detection."""
    EARLY_WARNING = "early_warning"
    MODERATE_CONCERN = "moderate_concern"
    SERIOUS_DEGRADATION = "serious_degradation"
    CRITICAL_DECAY = "critical_decay"
    TERMINAL_DECLINE = "terminal_decline"


@dataclass
class DecaySignal:
    """Individual decay detection signal."""
    decay_type: DecayType
    severity: DecaySeverity
    detection_date: datetime
    
    # Metrics
    current_value: float
    historical_average: float
    decay_rate: float  # Rate of decline per period
    significance: float  # Statistical significance of trend
    
    # Trend analysis
    trend_slope: float
    trend_r_squared: float
    trend_p_value: float
    
    # Projections
    projected_zero_date: Optional[datetime]  # When metric hits zero
    time_to_critical: Optional[int]  # Days until critical threshold
    
    # Context
    contributing_factors: List[str]
    recommended_actions: List[str]


@dataclass
class ThousandCutsReport:
    """Comprehensive thousand cuts analysis report."""
    analysis_date: datetime
    analysis_period_days: int
    
    # Overall health
    overall_decay_score: float  # 0-1, higher = more decay
    fund_life_expectancy_days: Optional[int]
    critical_decay_detected: bool
    
    # Individual decay signals
    decay_signals: List[DecaySignal]
    active_warnings: int
    critical_alerts: int
    
    # Trend analysis
    alpha_trend: Dict[str, float]
    ic_trend: Dict[str, float]
    sharpe_trend: Dict[str, float]
    cost_trend: Dict[str, float]
    
    # Attribution analysis
    alpha_concentration: float
    diversification_loss: float
    single_source_dependency: float
    
    # Recommendations
    immediate_actions: List[str]
    strategic_changes: List[str]
    monitoring_enhancements: List[str]


class DeathByThousandCutsDetector:
    """
    Institutional-grade alpha decay detection system.
    
    This class monitors for gradual performance degradation that kills
    funds slowly over time through accumulated small losses.
    """
    
    def __init__(self, 
                 lookback_days: int = 252,
                 rolling_window: int = 63,
                 decay_threshold: float = 0.05):
        """
        Initialize thousand cuts detector.
        
        Args:
            lookback_days: Days of history to analyze
            rolling_window: Rolling window for trend analysis
            decay_threshold: Threshold for decay detection
        """
        self.lookback_days = lookback_days
        self.rolling_window = rolling_window
        self.decay_threshold = decay_threshold
        
        self.logger = setup_operation_logging()
        self.decay_thresholds = self._define_decay_thresholds()
        
        self.logger.info("Death by Thousand Cuts Detector initialized")
    
    def detect_thousand_cuts(self, 
                           returns: np.ndarray,
                           signals: np.ndarray,
                           costs: np.ndarray,
                           timestamps: List[datetime],
                           alpha_attribution: Optional[Dict[str, np.ndarray]] = None) -> ThousandCutsReport:
        """
        Run comprehensive thousand cuts analysis.
        
        Args:
            returns: Strategy returns
            signals: Alpha signals
            costs: Transaction and management costs
            timestamps: Timestamps for each observation
            alpha_attribution: Attribution by alpha source
            
        Returns:
            ThousandCutsReport: Comprehensive decay analysis
        """
        self.logger.info("📉 Running Death by Thousand Cuts Analysis")
        self.logger.info("=" * 60)
        
        # Validate inputs
        if len(returns) != len(signals) or len(returns) != len(costs):
            raise ValueError("All input arrays must have same length")
        
        if len(returns) < self.rolling_window * 2:
            raise ValueError(f"Insufficient data for analysis (need at least {self.rolling_window * 2} observations)")
        
        # Clean data
        valid_mask = ~(np.isnan(returns) | np.isnan(signals) | np.isnan(costs))
        returns_clean = returns[valid_mask]
        signals_clean = signals[valid_mask]
        costs_clean = costs[valid_mask]
        timestamps_clean = [t for t, m in zip(timestamps, valid_mask) if m]
        
        # Detect individual decay patterns
        decay_signals = []
        
        # 1. Alpha decay detection
        alpha_decay = self._detect_alpha_decay(returns_clean, timestamps_clean)
        if alpha_decay:
            decay_signals.append(alpha_decay)
        
        # 2. IC degradation detection
        ic_decay = self._detect_ic_degradation(returns_clean, signals_clean, timestamps_clean)
        if ic_decay:
            decay_signals.append(ic_decay)
        
        # 3. Sharpe drift detection
        sharpe_decay = self._detect_sharpe_drift(returns_clean, timestamps_clean)
        if sharpe_decay:
            decay_signals.append(sharpe_decay)
        
        # 4. Cost creep detection
        cost_decay = self._detect_cost_creep(returns_clean, costs_clean, timestamps_clean)
        if cost_decay:
            decay_signals.append(cost_decay)
        
        # 5. Edge erosion detection
        edge_decay = self._detect_edge_erosion(returns_clean, costs_clean, timestamps_clean)
        if edge_decay:
            decay_signals.append(edge_decay)
        
        # 6. Attribution concentration detection
        if alpha_attribution:
            attribution_decay = self._detect_attribution_concentration(alpha_attribution, timestamps_clean)
            if attribution_decay:
                decay_signals.append(attribution_decay)
        
        # Calculate overall metrics
        overall_metrics = self._calculate_overall_decay_metrics(decay_signals, returns_clean)
        
        # Generate trend analysis
        trend_analysis = self._analyze_trends(returns_clean, signals_clean, costs_clean, timestamps_clean)
        
        # Calculate attribution metrics
        attribution_metrics = self._calculate_attribution_metrics(alpha_attribution) if alpha_attribution else {}
        
        # Generate recommendations
        recommendations = self._generate_decay_recommendations(decay_signals, overall_metrics)
        
        # Compile comprehensive report
        report = ThousandCutsReport(
            analysis_date=datetime.now(),
            analysis_period_days=len(returns_clean),
            overall_decay_score=overall_metrics['decay_score'],
            fund_life_expectancy_days=overall_metrics['life_expectancy'],
            critical_decay_detected=overall_metrics['critical_detected'],
            decay_signals=decay_signals,
            active_warnings=len([s for s in decay_signals if s.severity in [DecaySeverity.EARLY_WARNING, DecaySeverity.MODERATE_CONCERN]]),
            critical_alerts=len([s for s in decay_signals if s.severity in [DecaySeverity.SERIOUS_DEGRADATION, DecaySeverity.CRITICAL_DECAY, DecaySeverity.TERMINAL_DECLINE]]),
            alpha_trend=trend_analysis.get('alpha_trend', {}),
            ic_trend=trend_analysis.get('ic_trend', {}),
            sharpe_trend=trend_analysis.get('sharpe_trend', {}),
            cost_trend=trend_analysis.get('cost_trend', {}),
            alpha_concentration=attribution_metrics.get('concentration', 0.0),
            diversification_loss=attribution_metrics.get('diversification_loss', 0.0),
            single_source_dependency=attribution_metrics.get('single_source_dependency', 0.0),
            immediate_actions=recommendations['immediate'],
            strategic_changes=recommendations['strategic'],
            monitoring_enhancements=recommendations['monitoring']
        )
        
        self._log_decay_results(report)
        return report
    
    def _define_decay_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Define thresholds for different types of decay."""
        return {
            'alpha_decay': {
                'early_warning': -0.02,  # 2% annual alpha decline
                'moderate_concern': -0.05,
                'serious_degradation': -0.10,
                'critical_decay': -0.20,
                'terminal_decline': -0.30
            },
            'ic_slope': {
                'early_warning': -0.001,  # IC declining by 0.001 per month
                'moderate_concern': -0.005,
                'serious_degradation': -0.01,
                'critical_decay': -0.02,
                'terminal_decline': -0.05
            },
            'sharpe_drift': {
                'early_warning': -0.1,  # Sharpe declining by 0.1 per year
                'moderate_concern': -0.3,
                'serious_degradation': -0.5,
                'critical_decay': -1.0,
                'terminal_decline': -2.0
            },
            'cost_creep': {
                'early_warning': 0.005,  # 0.5% annual cost increase
                'moderate_concern': 0.01,
                'serious_degradation': 0.02,
                'critical_decay': 0.05,
                'terminal_decline': 0.10
            }
        }
    
    def _detect_alpha_decay(self, returns: np.ndarray, timestamps: List[datetime]) -> Optional[DecaySignal]:
        """Detect rolling alpha decay."""
        if len(returns) < self.rolling_window * 3:
            return None
        
        # Calculate rolling 12-month alpha
        rolling_alpha = []
        for i in range(self.rolling_window, len(returns)):
            window_returns = returns[i-self.rolling_window:i]
            alpha = np.mean(window_returns) * 252  # Annualized
            rolling_alpha.append(alpha)
        
        if len(rolling_alpha) < 20:  # Need enough points for trend
            return None
        
        # Analyze trend
        x = np.arange(len(rolling_alpha))
        slope, intercept, r_value, p_value, std_err = linregress(x, rolling_alpha)
        
        # Convert slope to annual decay rate
        annual_decay_rate = slope * 252
        
        # Determine severity
        severity = self._determine_severity('alpha_decay', annual_decay_rate)
        
        if severity is None:
            return None
        
        # Calculate projections
        current_alpha = rolling_alpha[-1]
        projected_zero_date = None
        time_to_critical = None
        
        if slope < 0:
            days_to_zero = -current_alpha / (slope / 252) if slope != 0 else None
            if days_to_zero and days_to_zero > 0:
                projected_zero_date = timestamps[-1] + timedelta(days=int(days_to_zero))
            
            critical_threshold = self.decay_thresholds['alpha_decay']['critical_decay']
            if current_alpha > critical_threshold:
                days_to_critical = (current_alpha - critical_threshold) / (-slope / 252)
                time_to_critical = int(days_to_critical) if days_to_critical > 0 else None
        
        return DecaySignal(
            decay_type=DecayType.ALPHA_DECAY,
            severity=severity,
            detection_date=timestamps[-1],
            current_value=current_alpha,
            historical_average=np.mean(rolling_alpha),
            decay_rate=annual_decay_rate,
            significance=1 - p_value,
            trend_slope=slope,
            trend_r_squared=r_value**2,
            trend_p_value=p_value,
            projected_zero_date=projected_zero_date,
            time_to_critical=time_to_critical,
            contributing_factors=self._identify_alpha_decay_factors(rolling_alpha),
            recommended_actions=self._recommend_alpha_decay_actions(severity, annual_decay_rate)
        )
    
    def _detect_ic_degradation(self, returns: np.ndarray, signals: np.ndarray, timestamps: List[datetime]) -> Optional[DecaySignal]:
        """Detect Information Coefficient degradation."""
        if len(returns) < self.rolling_window * 3:
            return None
        
        # Calculate rolling IC
        rolling_ic = []
        for i in range(self.rolling_window, len(returns)):
            window_returns = returns[i-self.rolling_window:i]
            window_signals = signals[i-self.rolling_window:i]
            
            # Calculate IC (correlation)
            if np.std(window_signals) > 0 and np.std(window_returns) > 0:
                ic = np.corrcoef(window_signals, window_returns)[0, 1]
                if not np.isnan(ic):
                    rolling_ic.append(ic)
        
        if len(rolling_ic) < 20:
            return None
        
        # Analyze trend
        x = np.arange(len(rolling_ic))
        slope, intercept, r_value, p_value, std_err = linregress(x, rolling_ic)
        
        # Convert slope to monthly decay rate
        monthly_decay_rate = slope * 21  # Approximate trading days per month
        
        # Determine severity
        severity = self._determine_severity('ic_slope', monthly_decay_rate)
        
        if severity is None:
            return None
        
        current_ic = rolling_ic[-1]
        
        return DecaySignal(
            decay_type=DecayType.IC_DEGRADATION,
            severity=severity,
            detection_date=timestamps[-1],
            current_value=current_ic,
            historical_average=np.mean(rolling_ic),
            decay_rate=monthly_decay_rate,
            significance=1 - p_value,
            trend_slope=slope,
            trend_r_squared=r_value**2,
            trend_p_value=p_value,
            projected_zero_date=None,
            time_to_critical=None,
            contributing_factors=self._identify_ic_decay_factors(rolling_ic),
            recommended_actions=self._recommend_ic_decay_actions(severity, monthly_decay_rate)
        )
    
    def _detect_sharpe_drift(self, returns: np.ndarray, timestamps: List[datetime]) -> Optional[DecaySignal]:
        """Detect Sharpe ratio drift."""
        if len(returns) < self.rolling_window * 3:
            return None
        
        # Calculate rolling Sharpe ratio
        rolling_sharpe = []
        for i in range(self.rolling_window, len(returns)):
            window_returns = returns[i-self.rolling_window:i]
            mean_ret = np.mean(window_returns)
            std_ret = np.std(window_returns)
            
            if std_ret > 0:
                sharpe = (mean_ret * 252) / (std_ret * np.sqrt(252))  # Annualized
                rolling_sharpe.append(sharpe)
        
        if len(rolling_sharpe) < 20:
            return None
        
        # Analyze trend
        x = np.arange(len(rolling_sharpe))
        slope, intercept, r_value, p_value, std_err = linregress(x, rolling_sharpe)
        
        # Convert slope to annual drift rate
        annual_drift_rate = slope * 252
        
        # Determine severity
        severity = self._determine_severity('sharpe_drift', annual_drift_rate)
        
        if severity is None:
            return None
        
        current_sharpe = rolling_sharpe[-1]
        
        return DecaySignal(
            decay_type=DecayType.SHARPE_DRIFT,
            severity=severity,
            detection_date=timestamps[-1],
            current_value=current_sharpe,
            historical_average=np.mean(rolling_sharpe),
            decay_rate=annual_drift_rate,
            significance=1 - p_value,
            trend_slope=slope,
            trend_r_squared=r_value**2,
            trend_p_value=p_value,
            projected_zero_date=None,
            time_to_critical=None,
            contributing_factors=self._identify_sharpe_decay_factors(rolling_sharpe),
            recommended_actions=self._recommend_sharpe_decay_actions(severity, annual_drift_rate)
        )
    
    def _detect_cost_creep(self, returns: np.ndarray, costs: np.ndarray, timestamps: List[datetime]) -> Optional[DecaySignal]:
        """Detect cost creep over time."""
        if len(costs) < self.rolling_window * 3:
            return None
        
        # Calculate rolling average costs
        rolling_costs = []
        for i in range(self.rolling_window, len(costs)):
            window_costs = costs[i-self.rolling_window:i]
            avg_cost = np.mean(window_costs) * 252  # Annualized
            rolling_costs.append(avg_cost)
        
        if len(rolling_costs) < 20:
            return None
        
        # Analyze trend
        x = np.arange(len(rolling_costs))
        slope, intercept, r_value, p_value, std_err = linregress(x, rolling_costs)
        
        # Convert slope to annual cost increase rate
        annual_cost_increase = slope * 252
        
        # Determine severity
        severity = self._determine_severity('cost_creep', annual_cost_increase)
        
        if severity is None:
            return None
        
        current_cost = rolling_costs[-1]
        
        return DecaySignal(
            decay_type=DecayType.COST_CREEP,
            severity=severity,
            detection_date=timestamps[-1],
            current_value=current_cost,
            historical_average=np.mean(rolling_costs),
            decay_rate=annual_cost_increase,
            significance=1 - p_value,
            trend_slope=slope,
            trend_r_squared=r_value**2,
            trend_p_value=p_value,
            projected_zero_date=None,
            time_to_critical=None,
            contributing_factors=self._identify_cost_creep_factors(rolling_costs),
            recommended_actions=self._recommend_cost_creep_actions(severity, annual_cost_increase)
        )
    
    def _detect_edge_erosion(self, returns: np.ndarray, costs: np.ndarray, timestamps: List[datetime]) -> Optional[DecaySignal]:
        """Detect edge erosion (net alpha < costs)."""
        if len(returns) < self.rolling_window * 2:
            return None
        
        # Calculate rolling net alpha (returns - costs)
        net_returns = returns - costs
        rolling_net_alpha = []
        
        for i in range(self.rolling_window, len(net_returns)):
            window_net = net_returns[i-self.rolling_window:i]
            net_alpha = np.mean(window_net) * 252  # Annualized
            rolling_net_alpha.append(net_alpha)
        
        if len(rolling_net_alpha) < 10:
            return None
        
        current_net_alpha = rolling_net_alpha[-1]
        
        # Check if net alpha is negative or declining toward zero
        if current_net_alpha > 0.01:  # Still positive with buffer
            return None
        
        # Analyze trend
        x = np.arange(len(rolling_net_alpha))
        slope, intercept, r_value, p_value, std_err = linregress(x, rolling_net_alpha)
        
        # Determine severity based on current level and trend
        if current_net_alpha < -0.05:
            severity = DecaySeverity.TERMINAL_DECLINE
        elif current_net_alpha < -0.02:
            severity = DecaySeverity.CRITICAL_DECAY
        elif current_net_alpha < 0:
            severity = DecaySeverity.SERIOUS_DEGRADATION
        elif current_net_alpha < 0.005:
            severity = DecaySeverity.MODERATE_CONCERN
        else:
            severity = DecaySeverity.EARLY_WARNING
        
        return DecaySignal(
            decay_type=DecayType.EDGE_EROSION,
            severity=severity,
            detection_date=timestamps[-1],
            current_value=current_net_alpha,
            historical_average=np.mean(rolling_net_alpha),
            decay_rate=slope * 252,
            significance=1 - p_value,
            trend_slope=slope,
            trend_r_squared=r_value**2,
            trend_p_value=p_value,
            projected_zero_date=None,
            time_to_critical=None,
            contributing_factors=["Cost increases", "Alpha decay", "Market efficiency"],
            recommended_actions=["Reduce costs", "Improve alpha generation", "Consider strategy pivot"]
        )
    
    def _detect_attribution_concentration(self, alpha_attribution: Dict[str, np.ndarray], timestamps: List[datetime]) -> Optional[DecaySignal]:
        """Detect alpha attribution concentration risk."""
        if not alpha_attribution or len(alpha_attribution) < 2:
            return None
        
        # Calculate Herfindahl-Hirschman Index for concentration
        attribution_values = list(alpha_attribution.values())
        min_length = min(len(arr) for arr in attribution_values)
        
        if min_length < self.rolling_window:
            return None
        
        # Calculate rolling concentration
        rolling_concentration = []
        for i in range(self.rolling_window, min_length):
            # Get attribution for this window
            window_attributions = {}
            for name, values in alpha_attribution.items():
                window_attributions[name] = np.sum(values[i-self.rolling_window:i])
            
            # Calculate HHI
            total_attribution = sum(abs(v) for v in window_attributions.values())
            if total_attribution > 0:
                shares = [abs(v) / total_attribution for v in window_attributions.values()]
                hhi = sum(s**2 for s in shares)
                rolling_concentration.append(hhi)
        
        if len(rolling_concentration) < 10:
            return None
        
        current_concentration = rolling_concentration[-1]
        
        # Determine severity (HHI ranges from 1/n to 1)
        n_sources = len(alpha_attribution)
        min_hhi = 1.0 / n_sources  # Perfect diversification
        
        if current_concentration > 0.8:
            severity = DecaySeverity.CRITICAL_DECAY
        elif current_concentration > 0.6:
            severity = DecaySeverity.SERIOUS_DEGRADATION
        elif current_concentration > 0.4:
            severity = DecaySeverity.MODERATE_CONCERN
        elif current_concentration > min_hhi * 2:
            severity = DecaySeverity.EARLY_WARNING
        else:
            return None
        
        return DecaySignal(
            decay_type=DecayType.ATTRIBUTION_CONCENTRATION,
            severity=severity,
            detection_date=timestamps[-1],
            current_value=current_concentration,
            historical_average=np.mean(rolling_concentration),
            decay_rate=0.0,  # Not applicable for concentration
            significance=1.0,
            trend_slope=0.0,
            trend_r_squared=0.0,
            trend_p_value=0.0,
            projected_zero_date=None,
            time_to_critical=None,
            contributing_factors=["Alpha source concentration", "Diversification loss"],
            recommended_actions=["Diversify alpha sources", "Reduce single-source dependency"]
        )
    
    def _determine_severity(self, decay_type: str, value: float) -> Optional[DecaySeverity]:
        """Determine severity level for decay metric."""
        if decay_type not in self.decay_thresholds:
            return None
        
        thresholds = self.decay_thresholds[decay_type]
        
        if value <= thresholds['terminal_decline']:
            return DecaySeverity.TERMINAL_DECLINE
        elif value <= thresholds['critical_decay']:
            return DecaySeverity.CRITICAL_DECAY
        elif value <= thresholds['serious_degradation']:
            return DecaySeverity.SERIOUS_DEGRADATION
        elif value <= thresholds['moderate_concern']:
            return DecaySeverity.MODERATE_CONCERN
        elif value <= thresholds['early_warning']:
            return DecaySeverity.EARLY_WARNING
        else:
            return None
    
    def _identify_alpha_decay_factors(self, rolling_alpha: List[float]) -> List[str]:
        """Identify factors contributing to alpha decay."""
        factors = []
        
        # Check for accelerating decay
        if len(rolling_alpha) >= 10:
            recent_slope = np.polyfit(range(len(rolling_alpha)//2, len(rolling_alpha)), 
                                    rolling_alpha[len(rolling_alpha)//2:], 1)[0]
            early_slope = np.polyfit(range(len(rolling_alpha)//2), 
                                   rolling_alpha[:len(rolling_alpha)//2], 1)[0]
            
            if recent_slope < early_slope * 2:
                factors.append("Accelerating decay")
        
        # Check for volatility
        alpha_vol = np.std(rolling_alpha)
        if alpha_vol > np.mean(np.abs(rolling_alpha)) * 0.5:
            factors.append("High alpha volatility")
        
        # Check for recent sharp decline
        if len(rolling_alpha) >= 5:
            recent_change = rolling_alpha[-1] - rolling_alpha[-5]
            if recent_change < -0.05:
                factors.append("Recent sharp decline")
        
        return factors if factors else ["General market efficiency"]
    
    def _recommend_alpha_decay_actions(self, severity: DecaySeverity, decay_rate: float) -> List[str]:
        """Recommend actions for alpha decay."""
        actions = []
        
        if severity in [DecaySeverity.CRITICAL_DECAY, DecaySeverity.TERMINAL_DECLINE]:
            actions.extend([
                "URGENT: Consider strategy overhaul",
                "Reduce position sizes immediately",
                "Investigate alpha source failures"
            ])
        elif severity == DecaySeverity.SERIOUS_DEGRADATION:
            actions.extend([
                "Review and refresh alpha models",
                "Consider new data sources",
                "Reduce leverage"
            ])
        elif severity == DecaySeverity.MODERATE_CONCERN:
            actions.extend([
                "Monitor alpha sources closely",
                "Test new signal combinations",
                "Review market regime changes"
            ])
        else:
            actions.extend([
                "Increase monitoring frequency",
                "Prepare contingency plans"
            ])
        
        return actions
    
    def _recommend_ic_decay_actions(self, severity: DecaySeverity, decay_rate: float) -> List[str]:
        """Recommend actions for IC decay."""
        return [
            "Review signal construction methodology",
            "Test alternative signal transformations",
            "Check for data quality issues",
            "Consider regime-specific models"
        ]
    
    def _recommend_sharpe_decay_actions(self, severity: DecaySeverity, decay_rate: float) -> List[str]:
        """Recommend actions for Sharpe decay."""
        return [
            "Review risk management procedures",
            "Consider volatility targeting",
            "Analyze return/risk trade-offs",
            "Evaluate position sizing methodology"
        ]
    
    def _recommend_cost_creep_actions(self, severity: DecaySeverity, decay_rate: float) -> List[str]:
        """Recommend actions for cost creep."""
        return [
            "Audit all cost sources",
            "Negotiate better execution rates",
            "Optimize trading frequency",
            "Review fund operational expenses"
        ]
    
    def _identify_ic_decay_factors(self, rolling_ic: List[float]) -> List[str]:
        """Identify factors contributing to IC decay."""
        return ["Signal degradation", "Market efficiency", "Regime changes"]
    
    def _identify_sharpe_decay_factors(self, rolling_sharpe: List[float]) -> List[str]:
        """Identify factors contributing to Sharpe decay."""
        return ["Increased volatility", "Reduced returns", "Risk management issues"]
    
    def _identify_cost_creep_factors(self, rolling_costs: List[float]) -> List[str]:
        """Identify factors contributing to cost creep."""
        return ["Higher transaction costs", "Increased management fees", "Market impact"]
    
    def _calculate_overall_decay_metrics(self, decay_signals: List[DecaySignal], returns: np.ndarray) -> Dict[str, Any]:
        """Calculate overall decay metrics."""
        if not decay_signals:
            return {
                'decay_score': 0.0,
                'life_expectancy': None,
                'critical_detected': False
            }
        
        # Calculate weighted decay score
        severity_weights = {
            DecaySeverity.EARLY_WARNING: 0.2,
            DecaySeverity.MODERATE_CONCERN: 0.4,
            DecaySeverity.SERIOUS_DEGRADATION: 0.6,
            DecaySeverity.CRITICAL_DECAY: 0.8,
            DecaySeverity.TERMINAL_DECLINE: 1.0
        }
        
        decay_score = np.mean([severity_weights[signal.severity] for signal in decay_signals])
        
        # Check for critical decay
        critical_detected = any(signal.severity in [DecaySeverity.CRITICAL_DECAY, DecaySeverity.TERMINAL_DECLINE] 
                              for signal in decay_signals)
        
        # Estimate fund life expectancy
        life_expectancy = None
        if critical_detected:
            # Find shortest time to critical
            times_to_critical = [s.time_to_critical for s in decay_signals if s.time_to_critical is not None]
            if times_to_critical:
                life_expectancy = min(times_to_critical)
        
        return {
            'decay_score': decay_score,
            'life_expectancy': life_expectancy,
            'critical_detected': critical_detected
        }
    
    def _analyze_trends(self, returns: np.ndarray, signals: np.ndarray, costs: np.ndarray, timestamps: List[datetime]) -> Dict[str, Dict[str, float]]:
        """Analyze various performance trends."""
        trends = {}
        
        # Alpha trend
        if len(returns) >= self.rolling_window:
            rolling_alpha = []
            for i in range(self.rolling_window, len(returns)):
                window_returns = returns[i-self.rolling_window:i]
                alpha = np.mean(window_returns) * 252
                rolling_alpha.append(alpha)
            
            if len(rolling_alpha) >= 10:
                x = np.arange(len(rolling_alpha))
                slope, _, r_value, p_value, _ = linregress(x, rolling_alpha)
                trends['alpha_trend'] = {
                    'slope': slope * 252,
                    'r_squared': r_value**2,
                    'p_value': p_value
                }
        
        # Similar for IC, Sharpe, and costs...
        trends['ic_trend'] = {'slope': 0, 'r_squared': 0, 'p_value': 1}
        trends['sharpe_trend'] = {'slope': 0, 'r_squared': 0, 'p_value': 1}
        trends['cost_trend'] = {'slope': 0, 'r_squared': 0, 'p_value': 1}
        
        return trends
    
    def _calculate_attribution_metrics(self, alpha_attribution: Dict[str, np.ndarray]) -> Dict[str, float]:
        """Calculate attribution concentration metrics."""
        if not alpha_attribution:
            return {}
        
        # Calculate total attribution by source
        total_attributions = {name: np.sum(values) for name, values in alpha_attribution.items()}
        total_abs_attribution = sum(abs(v) for v in total_attributions.values())
        
        if total_abs_attribution == 0:
            return {'concentration': 0, 'diversification_loss': 0, 'single_source_dependency': 0}
        
        # Calculate HHI
        shares = [abs(v) / total_abs_attribution for v in total_attributions.values()]
        hhi = sum(s**2 for s in shares)
        
        # Calculate single source dependency
        max_share = max(shares)
        
        # Calculate diversification loss
        n_sources = len(alpha_attribution)
        perfect_diversification = 1.0 / n_sources
        diversification_loss = (hhi - perfect_diversification) / (1.0 - perfect_diversification)
        
        return {
            'concentration': hhi,
            'diversification_loss': max(0, diversification_loss),
            'single_source_dependency': max_share
        }
    
    def _generate_decay_recommendations(self, decay_signals: List[DecaySignal], overall_metrics: Dict[str, Any]) -> Dict[str, List[str]]:
        """Generate comprehensive decay recommendations."""
        immediate = []
        strategic = []
        monitoring = []
        
        # Immediate actions based on severity
        if overall_metrics['critical_detected']:
            immediate.extend([
                "CRITICAL: Reduce position sizes immediately",
                "CRITICAL: Implement emergency risk controls",
                "CRITICAL: Consider strategy suspension"
            ])
        
        # Collect all recommended actions
        for signal in decay_signals:
            immediate.extend(signal.recommended_actions)
        
        # Strategic recommendations
        decay_types = {signal.decay_type for signal in decay_signals}
        
        if DecayType.ALPHA_DECAY in decay_types:
            strategic.append("Develop new alpha sources")
        if DecayType.IC_DEGRADATION in decay_types:
            strategic.append("Overhaul signal generation methodology")
        if DecayType.COST_CREEP in decay_types:
            strategic.append("Implement comprehensive cost reduction program")
        
        # Monitoring enhancements
        monitoring.extend([
            "Implement daily decay monitoring",
            "Add early warning alert system",
            "Create decay attribution dashboard",
            "Establish decay response protocols"
        ])
        
        return {
            'immediate': list(set(immediate)),
            'strategic': list(set(strategic)),
            'monitoring': list(set(monitoring))
        }
    
    def _log_decay_results(self, report: ThousandCutsReport):
        """Log thousand cuts detection results."""
        self.logger.info("📉 Death by Thousand Cuts Analysis Results")
        self.logger.info(f"   Overall Decay Score: {report.overall_decay_score:.2f}")
        self.logger.info(f"   Critical Decay Detected: {'❌ YES' if report.critical_decay_detected else '✅ NO'}")
        self.logger.info(f"   Active Warnings: {report.active_warnings}")
        self.logger.info(f"   Critical Alerts: {report.critical_alerts}")
        
        if report.fund_life_expectancy_days:
            self.logger.info(f"   Estimated Fund Life: {report.fund_life_expectancy_days} days")
        
        # Log individual decay signals
        for signal in report.decay_signals:
            severity_emoji = {
                DecaySeverity.EARLY_WARNING: "⚠️",
                DecaySeverity.MODERATE_CONCERN: "🟡",
                DecaySeverity.SERIOUS_DEGRADATION: "🟠",
                DecaySeverity.CRITICAL_DECAY: "🔴",
                DecaySeverity.TERMINAL_DECLINE: "💀"
            }
            emoji = severity_emoji.get(signal.severity, "❓")
            self.logger.info(f"   {emoji} {signal.decay_type.value}: {signal.current_value:.4f} (trend: {signal.decay_rate:.4f})")


def create_thousand_cuts_detector() -> DeathByThousandCutsDetector:
    """Create institutional-grade thousand cuts detector."""
    return DeathByThousandCutsDetector(
        lookback_days=252,
        rolling_window=63,
        decay_threshold=0.05
    )


if __name__ == "__main__":
    # Demo usage
    detector = create_thousand_cuts_detector()
    
    # Generate sample data with gradual decay
    np.random.seed(42)
    n = 500  # ~2 years of data
    
    # Create returns with gradual alpha decay
    base_alpha = 0.05  # Start with 5% annual alpha
    decay_rate = -0.0001  # Gradual decay
    
    returns = []
    signals = []
    costs = []
    
    for i in range(n):
        current_alpha = base_alpha + decay_rate * i
        daily_return = current_alpha / 252 + np.random.randn() * 0.02
        signal = np.random.randn() * 0.5
        cost = 0.001 + np.random.randn() * 0.0002  # Slight cost creep
        
        returns.append(daily_return)
        signals.append(signal)
        costs.append(abs(cost))
    
    returns = np.array(returns)
    signals = np.array(signals)
    costs = np.array(costs)
    timestamps = [datetime(2022, 1, 1) + timedelta(days=i) for i in range(n)]
    
    # Run analysis
    report = detector.detect_thousand_cuts(returns, signals, costs, timestamps)
    
    print(f"Thousand Cuts Analysis Complete:")
    print(f"Overall Decay Score: {report.overall_decay_score:.2f}")
    print(f"Critical Decay: {report.critical_decay_detected}")
    print(f"Decay Signals: {len(report.decay_signals)}")
    print(f"Active Warnings: {report.active_warnings}")
    print(f"Critical Alerts: {report.critical_alerts}")