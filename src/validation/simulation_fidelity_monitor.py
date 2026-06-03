"""
Simulation Fidelity Monitor

Maintains consistency score for each simulation run and detects unrealistic market behavior.
Provides detailed diagnostic information for inconsistencies and tracks which Phase 3 
components are affected by inconsistencies.

This monitor validates:
- Simulation consistency scores across runs
- Detection of unrealistic market behavior patterns
- Diagnostic information for inconsistencies
- Phase 3 component impact tracking
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from scipy import stats
import logging
import warnings

from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class ConsistencyScore:
    """Consistency score for a simulation run"""
    overall_score: float
    correlation_score: float
    volatility_score: float
    distribution_score: float
    regime_score: float
    temporal_score: float
    timestamp: datetime

@dataclass
class UnrealisticBehaviorDetection:
    """Detection of unrealistic market behavior"""
    behavior_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    affected_assets: List[str]
    detection_timestamp: datetime
    statistical_evidence: Dict[str, float]

@dataclass
class Phase3ComponentImpact:
    """Impact assessment on Phase 3 components"""
    component_name: str
    impact_severity: str  # 'none', 'low', 'medium', 'high', 'critical'
    impact_description: str
    affected_functionality: List[str]
    recommended_actions: List[str]

@dataclass
class DiagnosticInformation:
    """Detailed diagnostic information for inconsistencies"""
    inconsistency_type: str
    root_cause_analysis: str
    statistical_tests: Dict[str, Any]
    data_quality_issues: List[str]
    model_parameter_issues: List[str]
    temporal_issues: List[str]
    recommendations: List[str]

@dataclass
class SimulationFidelityResult:
    """Complete simulation fidelity monitoring result"""
    simulation_id: str
    monitoring_timestamp: datetime
    simulation_period: Tuple[datetime, datetime]
    consistency_score: ConsistencyScore
    unrealistic_behaviors: List[UnrealisticBehaviorDetection]
    phase3_component_impacts: List[Phase3ComponentImpact]
    diagnostic_information: DiagnosticInformation
    overall_fidelity_rating: str  # 'excellent', 'good', 'acceptable', 'poor', 'unacceptable'
    simulation_approved: bool

class SimulationFidelityMonitor:
    """
    Monitors simulation fidelity and detects unrealistic market behavior
    
    Maintains consistency scores for each simulation run and provides detailed
    diagnostics when inconsistencies are detected.
    """
    
    def __init__(self):
        # Fidelity thresholds
        self.fidelity_thresholds = {
            'excellent': 0.90,
            'good': 0.80,
            'acceptable': 0.70,
            'poor': 0.60,
            'unacceptable': 0.50
        }
        
        # Consistency score weights
        self.consistency_weights = {
            'correlation': 0.20,
            'volatility': 0.25,
            'distribution': 0.20,
            'regime': 0.20,
            'temporal': 0.15
        }
        
        # Unrealistic behavior detection thresholds
        self.behavior_thresholds = {
            'extreme_correlation': 0.99,
            'zero_volatility': 0.001,
            'extreme_volatility': 2.0,
            'impossible_returns': 0.50,  # 50% single-day return
            'regime_instability': 0.10,  # regime changes more than 10% of time
            'temporal_inconsistency': 0.05
        }
        
        # Phase 3 component monitoring
        self.phase3_components = [
            'regime_memory_system',
            'simple_tailwind_engine', 
            'no_edge_detector',
            'anticipatory_capital_allocator'
        ]
        
        # Historical consistency tracking
        self.consistency_history = []
        
    def monitor_simulation_fidelity(
        self,
        simulation_id: str,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame,
        simulation_period: Tuple[datetime, datetime],
        phase3_signals: Optional[Dict[str, pd.Series]] = None
    ) -> SimulationFidelityResult:
        """
        Monitor simulation fidelity and detect inconsistencies
        
        Args:
            simulation_id: Unique identifier for simulation run
            simulation_data: Simulated market data
            historical_reference: Historical data for comparison
            simulation_period: Period being simulated
            phase3_signals: Phase 3 component signals for impact assessment
            
        Returns:
            Complete simulation fidelity monitoring result
        """
        logger.info(f"Monitoring simulation fidelity for {simulation_id}")
        
        try:
            # Calculate consistency score
            consistency_score = self._calculate_consistency_score(
                simulation_data, historical_reference
            )
            
            # Detect unrealistic behaviors
            unrealistic_behaviors = self._detect_unrealistic_behaviors(
                simulation_data, historical_reference
            )
            
            # Assess Phase 3 component impacts
            phase3_impacts = self._assess_phase3_component_impacts(
                simulation_data, unrealistic_behaviors, phase3_signals
            )
            
            # Generate diagnostic information
            diagnostic_info = self._generate_diagnostic_information(
                simulation_data, historical_reference, unrealistic_behaviors, consistency_score
            )
            
            # Determine overall fidelity rating
            fidelity_rating = self._determine_fidelity_rating(
                consistency_score, unrealistic_behaviors, phase3_impacts
            )
            
            # Determine if simulation is approved
            simulation_approved = self._determine_simulation_approval(
                fidelity_rating, unrealistic_behaviors, phase3_impacts
            )
            
            # Store consistency history
            self.consistency_history.append(consistency_score)
            
            result = SimulationFidelityResult(
                simulation_id=simulation_id,
                monitoring_timestamp=datetime.now(),
                simulation_period=simulation_period,
                consistency_score=consistency_score,
                unrealistic_behaviors=unrealistic_behaviors,
                phase3_component_impacts=phase3_impacts,
                diagnostic_information=diagnostic_info,
                overall_fidelity_rating=fidelity_rating,
                simulation_approved=simulation_approved
            )
            
            logger.info(f"Simulation fidelity monitoring completed. Rating: {fidelity_rating}, Approved: {simulation_approved}")
            return result
            
        except Exception as e:
            logger.error(f"Simulation fidelity monitoring failed: {str(e)}")
            raise
    
    def _calculate_consistency_score(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> ConsistencyScore:
        """Calculate comprehensive consistency score"""
        
        # Calculate individual component scores
        correlation_score = self._calculate_correlation_consistency(simulation_data, historical_reference)
        volatility_score = self._calculate_volatility_consistency(simulation_data, historical_reference)
        distribution_score = self._calculate_distribution_consistency(simulation_data, historical_reference)
        regime_score = self._calculate_regime_consistency(simulation_data, historical_reference)
        temporal_score = self._calculate_temporal_consistency(simulation_data, historical_reference)
        
        # Calculate weighted overall score
        overall_score = (
            self.consistency_weights['correlation'] * correlation_score +
            self.consistency_weights['volatility'] * volatility_score +
            self.consistency_weights['distribution'] * distribution_score +
            self.consistency_weights['regime'] * regime_score +
            self.consistency_weights['temporal'] * temporal_score
        )
        
        return ConsistencyScore(
            overall_score=overall_score,
            correlation_score=correlation_score,
            volatility_score=volatility_score,
            distribution_score=distribution_score,
            regime_score=regime_score,
            temporal_score=temporal_score,
            timestamp=datetime.now()
        )
    
    def _calculate_correlation_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> float:
        """Calculate correlation structure consistency"""
        
        try:
            # Extract numeric columns
            sim_numeric = simulation_data.select_dtypes(include=[np.number]).dropna()
            hist_numeric = historical_reference.select_dtypes(include=[np.number]).dropna()
            
            if sim_numeric.empty or hist_numeric.empty:
                return 0.0
            
            # Find common columns
            common_cols = list(set(sim_numeric.columns) & set(hist_numeric.columns))
            if len(common_cols) < 2:
                return 0.0
            
            # Calculate correlation matrices
            sim_corr = sim_numeric[common_cols].corr()
            hist_corr = hist_numeric[common_cols].corr()
            
            # Calculate Frobenius norm difference
            diff_matrix = sim_corr - hist_corr
            frobenius_norm = np.linalg.norm(diff_matrix.values, 'fro')
            hist_norm = np.linalg.norm(hist_corr.values, 'fro')
            
            if hist_norm == 0:
                return 1.0 if frobenius_norm == 0 else 0.0
            
            consistency = max(0.0, 1.0 - frobenius_norm / hist_norm)
            return consistency
            
        except Exception as e:
            logger.warning(f"Correlation consistency calculation failed: {str(e)}")
            return 0.0
    
    def _calculate_volatility_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> float:
        """Calculate volatility pattern consistency"""
        
        try:
            # Calculate returns
            sim_returns = self._calculate_returns(simulation_data)
            hist_returns = self._calculate_returns(historical_reference)
            
            if sim_returns.empty or hist_returns.empty:
                return 0.0
            
            # Calculate rolling volatilities
            window = min(20, len(sim_returns) // 4, len(hist_returns) // 4)
            if window < 5:
                return 0.0
            
            consistencies = []
            common_cols = set(sim_returns.columns) & set(hist_returns.columns)
            
            for col in common_cols:
                sim_vol = sim_returns[col].rolling(window=window).std().dropna()
                hist_vol = hist_returns[col].rolling(window=window).std().dropna()
                
                if len(sim_vol) > 10 and len(hist_vol) > 10:
                    # Use Kolmogorov-Smirnov test
                    ks_stat, p_value = stats.ks_2samp(sim_vol, hist_vol)
                    consistency = 1.0 - ks_stat
                    consistencies.append(consistency)
            
            return np.mean(consistencies) if consistencies else 0.0
            
        except Exception as e:
            logger.warning(f"Volatility consistency calculation failed: {str(e)}")
            return 0.0
    
    def _calculate_distribution_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> float:
        """Calculate statistical distribution consistency"""
        
        try:
            sim_numeric = simulation_data.select_dtypes(include=[np.number]).dropna()
            hist_numeric = historical_reference.select_dtypes(include=[np.number]).dropna()
            
            if sim_numeric.empty or hist_numeric.empty:
                return 0.0
            
            consistencies = []
            common_cols = set(sim_numeric.columns) & set(hist_numeric.columns)
            
            for col in common_cols:
                sim_series = sim_numeric[col].dropna()
                hist_series = hist_numeric[col].dropna()
                
                if len(sim_series) > 30 and len(hist_series) > 30:
                    # Kolmogorov-Smirnov test for distribution similarity
                    ks_stat, p_value = stats.ks_2samp(sim_series, hist_series)
                    consistency = 1.0 - ks_stat
                    consistencies.append(consistency)
            
            return np.mean(consistencies) if consistencies else 0.0
            
        except Exception as e:
            logger.warning(f"Distribution consistency calculation failed: {str(e)}")
            return 0.0
    
    def _calculate_regime_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> float:
        """Calculate regime classification consistency"""
        
        try:
            # Extract regime data
            sim_regimes = simulation_data.get('regime_classification', pd.Series())
            hist_regimes = historical_reference.get('regime_classification', pd.Series())
            
            if sim_regimes.empty or hist_regimes.empty:
                return 0.0
            
            # Compare regime distributions
            sim_regime_dist = sim_regimes.value_counts(normalize=True)
            hist_regime_dist = hist_regimes.value_counts(normalize=True)
            
            # Calculate distribution similarity
            common_regimes = set(sim_regime_dist.index) & set(hist_regime_dist.index)
            if not common_regimes:
                return 0.0
            
            consistency_scores = []
            for regime in common_regimes:
                sim_freq = sim_regime_dist.get(regime, 0)
                hist_freq = hist_regime_dist.get(regime, 0)
                
                if hist_freq > 0:
                    freq_consistency = 1.0 - abs(sim_freq - hist_freq) / hist_freq
                    consistency_scores.append(max(0.0, freq_consistency))
            
            return np.mean(consistency_scores) if consistency_scores else 0.0
            
        except Exception as e:
            logger.warning(f"Regime consistency calculation failed: {str(e)}")
            return 0.0
    
    def _calculate_temporal_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> float:
        """Calculate temporal pattern consistency"""
        
        try:
            # Check for temporal patterns like autocorrelation
            sim_numeric = simulation_data.select_dtypes(include=[np.number]).dropna()
            hist_numeric = historical_reference.select_dtypes(include=[np.number]).dropna()
            
            if sim_numeric.empty or hist_numeric.empty:
                return 0.0
            
            consistencies = []
            common_cols = set(sim_numeric.columns) & set(hist_numeric.columns)
            
            for col in common_cols:
                sim_series = sim_numeric[col].dropna()
                hist_series = hist_numeric[col].dropna()
                
                if len(sim_series) > 50 and len(hist_series) > 50:
                    # Calculate autocorrelation at lag 1
                    sim_autocorr = sim_series.autocorr(lag=1)
                    hist_autocorr = hist_series.autocorr(lag=1)
                    
                    if not (np.isnan(sim_autocorr) or np.isnan(hist_autocorr)):
                        autocorr_diff = abs(sim_autocorr - hist_autocorr)
                        consistency = max(0.0, 1.0 - autocorr_diff)
                        consistencies.append(consistency)
            
            return np.mean(consistencies) if consistencies else 0.0
            
        except Exception as e:
            logger.warning(f"Temporal consistency calculation failed: {str(e)}")
            return 0.0
    
    def _calculate_returns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate returns from price-like data"""
        numeric_data = data.select_dtypes(include=[np.number]).dropna()
        
        # Look for price-like columns
        price_cols = []
        for col in numeric_data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['price', 'value', 'level', 'index']):
                price_cols.append(col)
        
        if not price_cols:
            # Use first few numeric columns as proxy
            price_cols = numeric_data.columns[:min(5, len(numeric_data.columns))]
        
        returns = pd.DataFrame(index=numeric_data.index)
        for col in price_cols:
            if len(numeric_data[col].dropna()) > 1:
                returns[f'{col}_return'] = numeric_data[col].pct_change()
        
        return returns.dropna()
    
    def _detect_unrealistic_behaviors(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> List[UnrealisticBehaviorDetection]:
        """Detect unrealistic market behaviors in simulation"""
        
        behaviors = []
        
        # Check for extreme correlations
        behaviors.extend(self._detect_extreme_correlations(simulation_data))
        
        # Check for unrealistic volatility
        behaviors.extend(self._detect_unrealistic_volatility(simulation_data, historical_reference))
        
        # Check for impossible returns
        behaviors.extend(self._detect_impossible_returns(simulation_data))
        
        # Check for regime instability
        behaviors.extend(self._detect_regime_instability(simulation_data))
        
        # Check for temporal inconsistencies
        behaviors.extend(self._detect_temporal_inconsistencies(simulation_data))
        
        return behaviors
    
    def _detect_extreme_correlations(self, data: pd.DataFrame) -> List[UnrealisticBehaviorDetection]:
        """Detect extreme correlation values"""
        behaviors = []
        
        try:
            numeric_data = data.select_dtypes(include=[np.number]).dropna()
            if len(numeric_data.columns) < 2:
                return behaviors
            
            corr_matrix = numeric_data.corr()
            
            # Check for correlations above threshold
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    corr_val = abs(corr_matrix.iloc[i, j])
                    
                    if corr_val > self.behavior_thresholds['extreme_correlation']:
                        behaviors.append(UnrealisticBehaviorDetection(
                            behavior_type='extreme_correlation',
                            severity='high' if corr_val > 0.995 else 'medium',
                            description=f"Extreme correlation {corr_val:.3f} between {corr_matrix.columns[i]} and {corr_matrix.columns[j]}",
                            affected_assets=[corr_matrix.columns[i], corr_matrix.columns[j]],
                            detection_timestamp=datetime.now(),
                            statistical_evidence={'correlation_value': corr_val}
                        ))
        
        except Exception as e:
            logger.warning(f"Extreme correlation detection failed: {str(e)}")
        
        return behaviors
    
    def _detect_unrealistic_volatility(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> List[UnrealisticBehaviorDetection]:
        """Detect unrealistic volatility patterns"""
        behaviors = []
        
        try:
            sim_returns = self._calculate_returns(simulation_data)
            hist_returns = self._calculate_returns(historical_reference)
            
            if sim_returns.empty:
                return behaviors
            
            for col in sim_returns.columns:
                sim_vol = sim_returns[col].std()
                
                # Check for zero volatility
                if sim_vol < self.behavior_thresholds['zero_volatility']:
                    behaviors.append(UnrealisticBehaviorDetection(
                        behavior_type='zero_volatility',
                        severity='high',
                        description=f"Near-zero volatility {sim_vol:.6f} in {col}",
                        affected_assets=[col],
                        detection_timestamp=datetime.now(),
                        statistical_evidence={'volatility': sim_vol}
                    ))
                
                # Check for extreme volatility
                elif sim_vol > self.behavior_thresholds['extreme_volatility']:
                    behaviors.append(UnrealisticBehaviorDetection(
                        behavior_type='extreme_volatility',
                        severity='high',
                        description=f"Extreme volatility {sim_vol:.3f} in {col}",
                        affected_assets=[col],
                        detection_timestamp=datetime.now(),
                        statistical_evidence={'volatility': sim_vol}
                    ))
                
                # Compare to historical volatility if available
                elif col in hist_returns.columns:
                    hist_vol = hist_returns[col].std()
                    if hist_vol > 0 and sim_vol / hist_vol > 5.0:
                        behaviors.append(UnrealisticBehaviorDetection(
                            behavior_type='volatility_mismatch',
                            severity='medium',
                            description=f"Volatility {sim_vol:.3f} is {sim_vol/hist_vol:.1f}x historical volatility {hist_vol:.3f} in {col}",
                            affected_assets=[col],
                            detection_timestamp=datetime.now(),
                            statistical_evidence={'sim_volatility': sim_vol, 'hist_volatility': hist_vol, 'ratio': sim_vol/hist_vol}
                        ))
        
        except Exception as e:
            logger.warning(f"Unrealistic volatility detection failed: {str(e)}")
        
        return behaviors
    
    def _detect_impossible_returns(self, data: pd.DataFrame) -> List[UnrealisticBehaviorDetection]:
        """Detect impossible return values"""
        behaviors = []
        
        try:
            returns = self._calculate_returns(data)
            
            for col in returns.columns:
                max_return = returns[col].max()
                min_return = returns[col].min()
                
                # Check for extreme positive returns
                if max_return > self.behavior_thresholds['impossible_returns']:
                    behaviors.append(UnrealisticBehaviorDetection(
                        behavior_type='impossible_return',
                        severity='critical',
                        description=f"Impossible positive return {max_return:.3f} in {col}",
                        affected_assets=[col],
                        detection_timestamp=datetime.now(),
                        statistical_evidence={'max_return': max_return}
                    ))
                
                # Check for extreme negative returns
                if min_return < -self.behavior_thresholds['impossible_returns']:
                    behaviors.append(UnrealisticBehaviorDetection(
                        behavior_type='impossible_return',
                        severity='critical',
                        description=f"Impossible negative return {min_return:.3f} in {col}",
                        affected_assets=[col],
                        detection_timestamp=datetime.now(),
                        statistical_evidence={'min_return': min_return}
                    ))
        
        except Exception as e:
            logger.warning(f"Impossible returns detection failed: {str(e)}")
        
        return behaviors
    
    def _detect_regime_instability(self, data: pd.DataFrame) -> List[UnrealisticBehaviorDetection]:
        """Detect regime classification instability"""
        behaviors = []
        
        try:
            regimes = data.get('regime_classification', pd.Series())
            if regimes.empty:
                return behaviors
            
            # Calculate regime change frequency
            regime_changes = (regimes != regimes.shift(1)).sum()
            total_periods = len(regimes)
            
            if total_periods > 0:
                change_rate = regime_changes / total_periods
                
                if change_rate > self.behavior_thresholds['regime_instability']:
                    behaviors.append(UnrealisticBehaviorDetection(
                        behavior_type='regime_instability',
                        severity='high' if change_rate > 0.20 else 'medium',
                        description=f"Regime changes {change_rate:.3f} of the time (threshold: {self.behavior_thresholds['regime_instability']:.3f})",
                        affected_assets=['regime_classification'],
                        detection_timestamp=datetime.now(),
                        statistical_evidence={'change_rate': change_rate, 'total_changes': regime_changes, 'total_periods': total_periods}
                    ))
        
        except Exception as e:
            logger.warning(f"Regime instability detection failed: {str(e)}")
        
        return behaviors
    
    def _detect_temporal_inconsistencies(self, data: pd.DataFrame) -> List[UnrealisticBehaviorDetection]:
        """Detect temporal inconsistencies in data"""
        behaviors = []
        
        try:
            # Check for missing timestamps or irregular spacing
            if hasattr(data.index, 'to_pydatetime'):
                timestamps = pd.to_datetime(data.index)
                
                # Check for duplicate timestamps
                duplicates = timestamps.duplicated().sum()
                if duplicates > 0:
                    behaviors.append(UnrealisticBehaviorDetection(
                        behavior_type='temporal_inconsistency',
                        severity='medium',
                        description=f"Found {duplicates} duplicate timestamps",
                        affected_assets=['timestamps'],
                        detection_timestamp=datetime.now(),
                        statistical_evidence={'duplicate_count': duplicates}
                    ))
                
                # Check for irregular spacing (simplified)
                if len(timestamps) > 2:
                    time_diffs = timestamps.diff().dropna()
                    if len(time_diffs) > 0:
                        median_diff = time_diffs.median()
                        irregular_count = (abs(time_diffs - median_diff) > median_diff * 2).sum()
                        irregular_rate = irregular_count / len(time_diffs)
                        
                        if irregular_rate > self.behavior_thresholds['temporal_inconsistency']:
                            behaviors.append(UnrealisticBehaviorDetection(
                                behavior_type='temporal_inconsistency',
                                severity='low',
                                description=f"Irregular timestamp spacing in {irregular_rate:.3f} of periods",
                                affected_assets=['timestamps'],
                                detection_timestamp=datetime.now(),
                                statistical_evidence={'irregular_rate': irregular_rate, 'median_diff': str(median_diff)}
                            ))
        
        except Exception as e:
            logger.warning(f"Temporal inconsistency detection failed: {str(e)}")
        
        return behaviors
    
    def _assess_phase3_component_impacts(
        self,
        simulation_data: pd.DataFrame,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        phase3_signals: Optional[Dict[str, pd.Series]]
    ) -> List[Phase3ComponentImpact]:
        """Assess impact of inconsistencies on Phase 3 components"""
        
        impacts = []
        
        # Assess impact on each Phase 3 component
        for component in self.phase3_components:
            impact = self._assess_component_impact(
                component, simulation_data, unrealistic_behaviors, phase3_signals
            )
            if impact:
                impacts.append(impact)
        
        return impacts
    
    def _assess_component_impact(
        self,
        component_name: str,
        simulation_data: pd.DataFrame,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        phase3_signals: Optional[Dict[str, pd.Series]]
    ) -> Optional[Phase3ComponentImpact]:
        """Assess impact on specific Phase 3 component"""
        
        try:
            # Component-specific impact assessment
            if component_name == 'regime_memory_system':
                return self._assess_regime_memory_impact(unrealistic_behaviors, simulation_data)
            elif component_name == 'simple_tailwind_engine':
                return self._assess_tailwind_engine_impact(unrealistic_behaviors, simulation_data)
            elif component_name == 'no_edge_detector':
                return self._assess_no_edge_detector_impact(unrealistic_behaviors, simulation_data)
            elif component_name == 'anticipatory_capital_allocator':
                return self._assess_capital_allocator_impact(unrealistic_behaviors, simulation_data)
            
            return None
            
        except Exception as e:
            logger.warning(f"Component impact assessment failed for {component_name}: {str(e)}")
            return None
    
    def _assess_regime_memory_impact(
        self,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        simulation_data: pd.DataFrame
    ) -> Optional[Phase3ComponentImpact]:
        """Assess impact on regime memory system"""
        
        # Check for behaviors that would affect regime memory
        relevant_behaviors = [
            b for b in unrealistic_behaviors 
            if b.behavior_type in ['extreme_correlation', 'regime_instability', 'volatility_mismatch']
        ]
        
        if not relevant_behaviors:
            return None
        
        # Determine impact severity
        critical_behaviors = [b for b in relevant_behaviors if b.severity == 'critical']
        high_behaviors = [b for b in relevant_behaviors if b.severity == 'high']
        
        if critical_behaviors:
            severity = 'critical'
            description = f"Critical inconsistencies detected that would severely impact regime similarity calculations"
        elif len(high_behaviors) > 2:
            severity = 'high'
            description = f"Multiple high-severity inconsistencies detected that would impact regime memory accuracy"
        elif high_behaviors:
            severity = 'medium'
            description = f"High-severity inconsistencies detected that may affect regime memory performance"
        else:
            severity = 'low'
            description = f"Minor inconsistencies detected that could slightly affect regime memory"
        
        affected_functionality = []
        recommendations = []
        
        for behavior in relevant_behaviors:
            if behavior.behavior_type == 'extreme_correlation':
                affected_functionality.append('regime_similarity_calculation')
                recommendations.append('Review correlation structure in simulation model')
            elif behavior.behavior_type == 'regime_instability':
                affected_functionality.append('regime_classification_stability')
                recommendations.append('Stabilize regime classification parameters')
            elif behavior.behavior_type == 'volatility_mismatch':
                affected_functionality.append('regime_volatility_patterns')
                recommendations.append('Calibrate volatility model to historical patterns')
        
        return Phase3ComponentImpact(
            component_name='regime_memory_system',
            impact_severity=severity,
            impact_description=description,
            affected_functionality=list(set(affected_functionality)),
            recommended_actions=list(set(recommendations))
        )
    
    def _assess_tailwind_engine_impact(
        self,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        simulation_data: pd.DataFrame
    ) -> Optional[Phase3ComponentImpact]:
        """Assess impact on tailwind engine"""
        
        # Check for behaviors that would affect tailwind calculations
        relevant_behaviors = [
            b for b in unrealistic_behaviors 
            if b.behavior_type in ['extreme_correlation', 'impossible_return', 'volatility_mismatch']
        ]
        
        if not relevant_behaviors:
            return None
        
        # Determine impact severity based on behavior types and counts
        critical_behaviors = [b for b in relevant_behaviors if b.severity == 'critical']
        
        if critical_behaviors:
            severity = 'high'
            description = f"Critical market behaviors detected that would invalidate tailwind calculations"
        elif len(relevant_behaviors) > 3:
            severity = 'medium'
            description = f"Multiple inconsistencies detected that could affect tailwind accuracy"
        else:
            severity = 'low'
            description = f"Minor inconsistencies detected that may slightly affect tailwind calculations"
        
        affected_functionality = ['sharpe_ratio_calculation', 'regime_weighting']
        recommendations = ['Validate performance calculation inputs', 'Review regime-strategy relationships']
        
        return Phase3ComponentImpact(
            component_name='simple_tailwind_engine',
            impact_severity=severity,
            impact_description=description,
            affected_functionality=affected_functionality,
            recommended_actions=recommendations
        )
    
    def _assess_no_edge_detector_impact(
        self,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        simulation_data: pd.DataFrame
    ) -> Optional[Phase3ComponentImpact]:
        """Assess impact on NO_EDGE detector"""
        
        # Check for behaviors that would affect NO_EDGE detection
        relevant_behaviors = [
            b for b in unrealistic_behaviors 
            if b.behavior_type in ['zero_volatility', 'extreme_volatility', 'regime_instability']
        ]
        
        if not relevant_behaviors:
            return None
        
        # NO_EDGE detector is designed to handle edge cases, so impact may be lower
        high_behaviors = [b for b in relevant_behaviors if b.severity in ['critical', 'high']]
        
        if len(high_behaviors) > 2:
            severity = 'medium'
            description = f"Multiple severe inconsistencies that could affect NO_EDGE detection accuracy"
        elif high_behaviors:
            severity = 'low'
            description = f"Some inconsistencies detected that may affect NO_EDGE trigger sensitivity"
        else:
            severity = 'none'
            description = f"Minor inconsistencies that should not significantly affect NO_EDGE detection"
        
        if severity == 'none':
            return None
        
        affected_functionality = ['edge_case_detection', 'exposure_capping']
        recommendations = ['Validate edge case detection thresholds', 'Review exposure capping triggers']
        
        return Phase3ComponentImpact(
            component_name='no_edge_detector',
            impact_severity=severity,
            impact_description=description,
            affected_functionality=affected_functionality,
            recommended_actions=recommendations
        )
    
    def _assess_capital_allocator_impact(
        self,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        simulation_data: pd.DataFrame
    ) -> Optional[Phase3ComponentImpact]:
        """Assess impact on anticipatory capital allocator"""
        
        # Capital allocator depends on all other components, so any significant issues affect it
        relevant_behaviors = unrealistic_behaviors
        
        if not relevant_behaviors:
            return None
        
        critical_behaviors = [b for b in relevant_behaviors if b.severity == 'critical']
        high_behaviors = [b for b in relevant_behaviors if b.severity == 'high']
        
        if critical_behaviors:
            severity = 'high'
            description = f"Critical inconsistencies detected that would significantly impact allocation decisions"
        elif len(high_behaviors) > 1:
            severity = 'medium'
            description = f"Multiple high-severity issues that could affect allocation quality"
        elif high_behaviors:
            severity = 'low'
            description = f"Some issues detected that may slightly affect allocation decisions"
        else:
            severity = 'none'
            description = f"Minor issues that should not significantly affect allocations"
        
        if severity == 'none':
            return None
        
        affected_functionality = ['allocation_calculation', 'anticipatory_positioning']
        recommendations = ['Validate all input components', 'Review allocation decision logic']
        
        return Phase3ComponentImpact(
            component_name='anticipatory_capital_allocator',
            impact_severity=severity,
            impact_description=description,
            affected_functionality=affected_functionality,
            recommended_actions=recommendations
        )
    
    def _generate_diagnostic_information(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        consistency_score: ConsistencyScore
    ) -> DiagnosticInformation:
        """Generate detailed diagnostic information"""
        
        # Identify primary inconsistency type
        if unrealistic_behaviors:
            primary_behavior = max(unrealistic_behaviors, key=lambda x: {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(x.severity, 0))
            inconsistency_type = primary_behavior.behavior_type
        else:
            inconsistency_type = 'low_consistency_score'
        
        # Root cause analysis
        root_cause = self._perform_root_cause_analysis(
            simulation_data, historical_reference, unrealistic_behaviors, consistency_score
        )
        
        # Statistical tests
        statistical_tests = self._perform_diagnostic_statistical_tests(
            simulation_data, historical_reference
        )
        
        # Identify issues
        data_quality_issues = self._identify_data_quality_issues(simulation_data)
        model_parameter_issues = self._identify_model_parameter_issues(unrealistic_behaviors)
        temporal_issues = self._identify_temporal_issues(simulation_data)
        
        # Generate recommendations
        recommendations = self._generate_diagnostic_recommendations(
            inconsistency_type, unrealistic_behaviors, consistency_score
        )
        
        return DiagnosticInformation(
            inconsistency_type=inconsistency_type,
            root_cause_analysis=root_cause,
            statistical_tests=statistical_tests,
            data_quality_issues=data_quality_issues,
            model_parameter_issues=model_parameter_issues,
            temporal_issues=temporal_issues,
            recommendations=recommendations
        )
    
    def _perform_root_cause_analysis(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        consistency_score: ConsistencyScore
    ) -> str:
        """Perform root cause analysis of inconsistencies"""
        
        causes = []
        
        # Analyze consistency scores
        if consistency_score.correlation_score < 0.60:
            causes.append("Poor correlation structure preservation")
        if consistency_score.volatility_score < 0.60:
            causes.append("Volatility patterns not matching historical characteristics")
        if consistency_score.distribution_score < 0.60:
            causes.append("Statistical distributions significantly different from historical")
        if consistency_score.regime_score < 0.60:
            causes.append("Regime classifications inconsistent with historical patterns")
        if consistency_score.temporal_score < 0.60:
            causes.append("Temporal patterns not preserved in simulation")
        
        # Analyze unrealistic behaviors
        behavior_types = [b.behavior_type for b in unrealistic_behaviors]
        if 'extreme_correlation' in behavior_types:
            causes.append("Correlation model producing unrealistic correlation values")
        if 'impossible_return' in behavior_types:
            causes.append("Return generation model producing impossible values")
        if 'regime_instability' in behavior_types:
            causes.append("Regime classification model too unstable")
        
        if not causes:
            causes.append("Multiple minor inconsistencies accumulating to reduce overall fidelity")
        
        return "; ".join(causes)
    
    def _perform_diagnostic_statistical_tests(
        self,
        simulation_data: pd.DataFrame,
        historical_reference: pd.DataFrame
    ) -> Dict[str, Any]:
        """Perform statistical tests for diagnostics"""
        
        tests = {}
        
        try:
            # Basic statistical comparisons
            sim_numeric = simulation_data.select_dtypes(include=[np.number]).dropna()
            hist_numeric = historical_reference.select_dtypes(include=[np.number]).dropna()
            
            if not sim_numeric.empty and not hist_numeric.empty:
                common_cols = list(set(sim_numeric.columns) & set(hist_numeric.columns))
                
                if common_cols:
                    # Kolmogorov-Smirnov tests
                    ks_results = {}
                    for col in common_cols[:5]:  # Limit to first 5 columns
                        try:
                            ks_stat, p_value = stats.ks_2samp(sim_numeric[col], hist_numeric[col])
                            ks_results[col] = {'statistic': ks_stat, 'p_value': p_value}
                        except:
                            continue
                    
                    tests['kolmogorov_smirnov'] = ks_results
                    
                    # Basic descriptive statistics comparison
                    sim_stats = sim_numeric[common_cols].describe()
                    hist_stats = hist_numeric[common_cols].describe()
                    
                    tests['descriptive_stats'] = {
                        'simulation': sim_stats.to_dict(),
                        'historical': hist_stats.to_dict()
                    }
        
        except Exception as e:
            tests['error'] = f"Statistical tests failed: {str(e)}"
        
        return tests
    
    def _identify_data_quality_issues(self, data: pd.DataFrame) -> List[str]:
        """Identify data quality issues"""
        issues = []
        
        # Check for missing data
        missing_pct = data.isnull().sum().sum() / (len(data) * len(data.columns))
        if missing_pct > 0.05:
            issues.append(f"High missing data rate: {missing_pct:.2%}")
        
        # Check for duplicate rows
        duplicates = data.duplicated().sum()
        if duplicates > 0:
            issues.append(f"Found {duplicates} duplicate rows")
        
        # Check for constant columns
        numeric_data = data.select_dtypes(include=[np.number])
        for col in numeric_data.columns:
            if numeric_data[col].nunique() <= 1:
                issues.append(f"Column {col} has constant values")
        
        return issues
    
    def _identify_model_parameter_issues(self, unrealistic_behaviors: List[UnrealisticBehaviorDetection]) -> List[str]:
        """Identify model parameter issues"""
        issues = []
        
        behavior_types = [b.behavior_type for b in unrealistic_behaviors]
        
        if 'extreme_correlation' in behavior_types:
            issues.append("Correlation model parameters may be miscalibrated")
        if 'extreme_volatility' in behavior_types:
            issues.append("Volatility model parameters may be too aggressive")
        if 'impossible_return' in behavior_types:
            issues.append("Return generation model lacks proper bounds")
        if 'regime_instability' in behavior_types:
            issues.append("Regime model parameters may be too sensitive")
        
        return issues
    
    def _identify_temporal_issues(self, data: pd.DataFrame) -> List[str]:
        """Identify temporal issues"""
        issues = []
        
        # Check index type and regularity
        if not isinstance(data.index, pd.DatetimeIndex):
            issues.append("Data index is not datetime-based")
        else:
            # Check for irregular spacing
            if len(data) > 2:
                time_diffs = data.index.to_series().diff().dropna()
                if time_diffs.nunique() > len(time_diffs) * 0.1:  # More than 10% unique differences
                    issues.append("Irregular timestamp spacing detected")
        
        return issues
    
    def _generate_diagnostic_recommendations(
        self,
        inconsistency_type: str,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        consistency_score: ConsistencyScore
    ) -> List[str]:
        """Generate diagnostic recommendations"""
        
        recommendations = []
        
        # Type-specific recommendations
        if inconsistency_type == 'extreme_correlation':
            recommendations.append("Review and recalibrate correlation model parameters")
            recommendations.append("Implement correlation bounds checking")
        elif inconsistency_type == 'impossible_return':
            recommendations.append("Implement return bounds in simulation model")
            recommendations.append("Review return generation methodology")
        elif inconsistency_type == 'regime_instability':
            recommendations.append("Increase regime classification stability parameters")
            recommendations.append("Review regime transition logic")
        
        # Score-based recommendations
        if consistency_score.overall_score < 0.70:
            recommendations.append("Consider recalibrating entire simulation model")
            recommendations.append("Increase validation against historical data")
        
        # Behavior-based recommendations
        critical_behaviors = [b for b in unrealistic_behaviors if b.severity == 'critical']
        if critical_behaviors:
            recommendations.append("Address critical inconsistencies before using simulation results")
        
        if not recommendations:
            recommendations.append("Monitor simulation fidelity in future runs")
        
        return recommendations
    
    def _determine_fidelity_rating(
        self,
        consistency_score: ConsistencyScore,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        phase3_impacts: List[Phase3ComponentImpact]
    ) -> str:
        """Determine overall fidelity rating"""
        
        # Start with consistency score rating
        score = consistency_score.overall_score
        
        if score >= self.fidelity_thresholds['excellent']:
            base_rating = 'excellent'
        elif score >= self.fidelity_thresholds['good']:
            base_rating = 'good'
        elif score >= self.fidelity_thresholds['acceptable']:
            base_rating = 'acceptable'
        elif score >= self.fidelity_thresholds['poor']:
            base_rating = 'poor'
        else:
            base_rating = 'unacceptable'
        
        # Downgrade based on unrealistic behaviors
        critical_behaviors = [b for b in unrealistic_behaviors if b.severity == 'critical']
        high_behaviors = [b for b in unrealistic_behaviors if b.severity == 'high']
        
        if critical_behaviors:
            if base_rating in ['excellent', 'good']:
                base_rating = 'poor'
            elif base_rating == 'acceptable':
                base_rating = 'unacceptable'
        elif len(high_behaviors) > 2:
            if base_rating == 'excellent':
                base_rating = 'good'
            elif base_rating == 'good':
                base_rating = 'acceptable'
        
        # Downgrade based on Phase 3 component impacts
        critical_impacts = [i for i in phase3_impacts if i.impact_severity == 'critical']
        high_impacts = [i for i in phase3_impacts if i.impact_severity == 'high']
        
        if critical_impacts:
            base_rating = 'unacceptable'
        elif len(high_impacts) > 1:
            if base_rating in ['excellent', 'good']:
                base_rating = 'acceptable'
        
        return base_rating
    
    def _determine_simulation_approval(
        self,
        fidelity_rating: str,
        unrealistic_behaviors: List[UnrealisticBehaviorDetection],
        phase3_impacts: List[Phase3ComponentImpact]
    ) -> bool:
        """Determine if simulation is approved for use"""
        
        # Automatic rejection criteria
        if fidelity_rating == 'unacceptable':
            return False
        
        # Check for critical issues
        critical_behaviors = [b for b in unrealistic_behaviors if b.severity == 'critical']
        critical_impacts = [i for i in phase3_impacts if i.impact_severity == 'critical']
        
        if critical_behaviors or critical_impacts:
            return False
        
        # Approve based on rating
        return fidelity_rating in ['excellent', 'good', 'acceptable']
    
    def get_consistency_history(self) -> List[ConsistencyScore]:
        """Get historical consistency scores"""
        return self.consistency_history.copy()
    
    def get_fidelity_trends(self) -> Dict[str, List[float]]:
        """Get fidelity trends over time"""
        if not self.consistency_history:
            return {}
        
        return {
            'overall_scores': [score.overall_score for score in self.consistency_history],
            'correlation_scores': [score.correlation_score for score in self.consistency_history],
            'volatility_scores': [score.volatility_score for score in self.consistency_history],
            'distribution_scores': [score.distribution_score for score in self.consistency_history],
            'regime_scores': [score.regime_score for score in self.consistency_history],
            'temporal_scores': [score.temporal_score for score in self.consistency_history]
        }