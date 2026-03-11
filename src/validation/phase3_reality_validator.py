"""
Phase 3 Reality Validator

Validates that Phase 3 components maintain statistical consistency with historical patterns
and that simulations accurately reflect market reality.

This validator ensures:
- Phase 3 regime classifications match historical patterns
- Simulated tailwind patterns match historical distributions  
- NO_EDGE triggers occur at appropriate frequencies
- Anticipatory signals maintain proper lead-lag relationships
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from scipy import stats
import logging

from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector
from src.intelligence.anticipatory_capital_allocator import AnticipatoryCapitalAllocator
from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class RegimeConsistencyResult:
    """Results of regime classification consistency validation"""
    regime_frequency_match: float
    regime_duration_match: float
    regime_transition_match: float
    similarity_score_stability: float
    overall_consistency: float
    inconsistencies: List[str]

@dataclass
class TailwindConsistencyResult:
    """Results of tailwind pattern consistency validation"""
    distribution_match: float
    correlation_structure_match: float
    persistence_pattern_match: float
    regime_relationship_match: float
    overall_consistency: float
    inconsistencies: List[str]

@dataclass
class NoEdgeConsistencyResult:
    """Results of NO_EDGE trigger consistency validation"""
    trigger_frequency_match: float
    trigger_duration_match: float
    trigger_condition_match: float
    recovery_pattern_match: float
    overall_consistency: float
    inconsistencies: List[str]

@dataclass
class AnticipatoryConsistencyResult:
    """Results of anticipatory signal consistency validation"""
    signal_timing_match: float
    lead_lag_relationship_match: float
    signal_strength_match: float
    accuracy_pattern_match: float
    overall_consistency: float
    inconsistencies: List[str]

@dataclass
class Phase3RealityValidationResult:
    """Complete Phase 3 reality consistency validation result"""
    validation_timestamp: datetime
    validation_period: Tuple[datetime, datetime]
    regime_consistency: RegimeConsistencyResult
    tailwind_consistency: TailwindConsistencyResult
    no_edge_consistency: NoEdgeConsistencyResult
    anticipatory_consistency: AnticipatoryConsistencyResult
    overall_reality_consistency: float
    critical_inconsistencies: List[str]
    recommendations: List[str]
    
    @property
    def regime_memory_accuracy(self) -> float:
        """Convenience property for regime memory accuracy"""
        return self.regime_consistency.overall_consistency
    
    @property
    def tailwind_calculation_accuracy(self) -> float:
        """Convenience property for tailwind calculation accuracy"""
        return self.tailwind_consistency.overall_consistency
    
    @property
    def no_edge_detection_precision(self) -> float:
        """Convenience property for NO_EDGE detection precision"""
        return self.no_edge_consistency.overall_consistency
    
    @property
    def anticipatory_positioning_accuracy(self) -> float:
        """Convenience property for anticipatory positioning accuracy"""
        return self.anticipatory_consistency.overall_consistency
    
    @property
    def overall_consistency_score(self) -> float:
        """Convenience property for overall consistency score"""
        return self.overall_reality_consistency

class Phase3RealityValidator:
    """
    Validates Phase 3 components maintain reality consistency
    
    Ensures simulated Phase 3 behavior matches historical patterns and
    maintains statistical consistency across different scenarios.
    """
    
    def __init__(self):
        self.regime_memory = RegimeMemorySystem()
        self.tailwind_engine = SimpleTailwindEngine()
        self.no_edge_detector = NoEdgeDetector()
        self.anticipatory_allocator = AnticipatoryCapitalAllocator()
        
        # Historical consistency thresholds
        self.consistency_thresholds = {
            'regime_frequency': 0.85,
            'regime_duration': 0.80,
            'regime_transition': 0.75,
            'tailwind_distribution': 0.85,
            'tailwind_correlation': 0.80,
            'no_edge_frequency': 0.90,
            'no_edge_duration': 0.85,
            'anticipatory_timing': 0.80,
            'anticipatory_accuracy': 0.75
        }
        
        # Statistical test significance level
        self.significance_level = 0.05

    @staticmethod
    def _clip01(value: float) -> float:
        """Return a finite score in [0, 1]."""
        try:
            v = float(value)
        except Exception:
            return 0.0
        if np.isnan(v) or np.isinf(v):
            return 0.0
        return float(np.clip(v, 0.0, 1.0))
        
    def validate_phase3_reality_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame,
        validation_period: Tuple[datetime, datetime],
        phase3_signals: Optional[Dict[str, pd.Series]] = None
    ) -> Phase3RealityValidationResult:
        """
        Validate Phase 3 components maintain reality consistency
        
        Args:
            simulation_data: Simulated market data with Phase 3 signals
            historical_data: Historical market data for comparison
            validation_period: Period being validated
            
        Returns:
            Complete validation result with consistency scores
        """
        logger.info(f"Starting Phase 3 reality consistency validation for period {validation_period}")
        
        try:
            # Validate regime consistency
            regime_result = self._validate_regime_consistency(
                simulation_data, historical_data
            )
            
            # Validate tailwind consistency
            tailwind_result = self._validate_tailwind_consistency(
                simulation_data, historical_data
            )
            
            # Validate NO_EDGE consistency
            no_edge_result = self._validate_no_edge_consistency(
                simulation_data, historical_data
            )
            
            # Validate anticipatory signal consistency
            anticipatory_result = self._validate_anticipatory_consistency(
                simulation_data, historical_data
            )
            
            # Calculate overall consistency
            overall_consistency = self._clip01(self._calculate_overall_consistency(
                regime_result, tailwind_result, no_edge_result, anticipatory_result
            ))
            
            # Identify critical inconsistencies
            critical_inconsistencies = self._identify_critical_inconsistencies(
                regime_result, tailwind_result, no_edge_result, anticipatory_result
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                regime_result, tailwind_result, no_edge_result, anticipatory_result
            )
            
            result = Phase3RealityValidationResult(
                validation_timestamp=datetime.now(),
                validation_period=validation_period,
                regime_consistency=regime_result,
                tailwind_consistency=tailwind_result,
                no_edge_consistency=no_edge_result,
                anticipatory_consistency=anticipatory_result,
                overall_reality_consistency=overall_consistency,
                critical_inconsistencies=critical_inconsistencies,
                recommendations=recommendations
            )
            
            logger.info(f"Phase 3 reality validation completed. Overall consistency: {overall_consistency:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Phase 3 reality validation failed: {str(e)}")
            raise
    
    def _validate_regime_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> RegimeConsistencyResult:
        """Validate regime classification consistency"""
        
        # Extract regime data
        sim_regimes = simulation_data.get('regime_classification', pd.Series())
        hist_regimes = historical_data.get('regime_classification', pd.Series())
        
        if sim_regimes.empty or hist_regimes.empty:
            logger.warning("Missing regime classification data")
            return RegimeConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Missing regime data"])
        
        inconsistencies = []
        
        # Check regime frequency distribution
        sim_freq = sim_regimes.value_counts(normalize=True)
        hist_freq = hist_regimes.value_counts(normalize=True)
        
        # Align frequencies for comparison
        all_regimes = set(sim_freq.index) | set(hist_freq.index)
        sim_freq_aligned = pd.Series([sim_freq.get(r, 0.0) for r in all_regimes], index=all_regimes)
        hist_freq_aligned = pd.Series([hist_freq.get(r, 0.0) for r in all_regimes], index=all_regimes)
        
        # Chi-square test for frequency distribution
        try:
            # Primary score is normalized absolute-frequency distance.
            # Identical distributions score 1.0, maximally different score 0.0.
            freq_distance = float(np.abs(sim_freq_aligned - hist_freq_aligned).sum() / 2.0)
            freq_match = max(0.0, 1.0 - freq_distance)

            # If statistical evidence indicates a meaningful mismatch, cap the score.
            _, p_value = stats.chisquare(
                sim_freq_aligned * len(sim_regimes),
                hist_freq_aligned * len(hist_regimes)
            )
            if p_value <= self.significance_level:
                freq_match = min(freq_match, 0.5)
        except:
            freq_match = 0.0
            inconsistencies.append("Regime frequency distribution test failed")
        
        # Check regime duration patterns
        sim_durations = self._calculate_regime_durations(sim_regimes)
        hist_durations = self._calculate_regime_durations(hist_regimes)
        
        duration_match = self._compare_duration_distributions(sim_durations, hist_durations)
        if duration_match < self.consistency_thresholds['regime_duration']:
            inconsistencies.append("Regime duration patterns inconsistent")
        
        # Check regime transition patterns
        sim_transitions = self._calculate_regime_transitions(sim_regimes)
        hist_transitions = self._calculate_regime_transitions(hist_regimes)
        
        transition_match = self._compare_transition_matrices(sim_transitions, hist_transitions)
        if transition_match < self.consistency_thresholds['regime_transition']:
            inconsistencies.append("Regime transition patterns inconsistent")
        
        # Check regime similarity score stability
        sim_similarity = simulation_data.get('regime_similarity_score', pd.Series())
        hist_similarity = historical_data.get('regime_similarity_score', pd.Series())
        
        if not sim_similarity.empty and not hist_similarity.empty:
            similarity_stability = self._compare_similarity_stability(sim_similarity, hist_similarity)
        else:
            similarity_stability = 0.0
            inconsistencies.append("Missing regime similarity scores")
        
        freq_match = self._clip01(freq_match)
        duration_match = self._clip01(duration_match)
        transition_match = self._clip01(transition_match)
        similarity_stability = self._clip01(similarity_stability)

        # Calculate overall regime consistency
        overall_consistency = self._clip01(
            np.mean([freq_match, duration_match, transition_match, similarity_stability])
        )
        
        return RegimeConsistencyResult(
            regime_frequency_match=freq_match,
            regime_duration_match=duration_match,
            regime_transition_match=transition_match,
            similarity_score_stability=similarity_stability,
            overall_consistency=overall_consistency,
            inconsistencies=inconsistencies
        )
    
    def _validate_tailwind_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> TailwindConsistencyResult:
        """Validate tailwind pattern consistency"""
        
        # Extract tailwind data
        sim_tailwinds = self._extract_tailwind_data(simulation_data)
        hist_tailwinds = self._extract_tailwind_data(historical_data)
        
        if sim_tailwinds.empty or hist_tailwinds.empty:
            logger.warning("Missing tailwind data")
            return TailwindConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Missing tailwind data"])
        
        inconsistencies = []
        
        # Check tailwind distribution consistency
        distribution_match = self._compare_tailwind_distributions(sim_tailwinds, hist_tailwinds)
        if distribution_match < self.consistency_thresholds['tailwind_distribution']:
            inconsistencies.append("Tailwind distributions inconsistent")
        
        # Check correlation structure consistency
        correlation_match = self._compare_tailwind_correlations(sim_tailwinds, hist_tailwinds)
        if correlation_match < self.consistency_thresholds['tailwind_correlation']:
            inconsistencies.append("Tailwind correlation structure inconsistent")
        
        # Check persistence patterns
        sim_persistence = self._calculate_tailwind_persistence(sim_tailwinds)
        hist_persistence = self._calculate_tailwind_persistence(hist_tailwinds)
        persistence_match = self._compare_persistence_patterns(sim_persistence, hist_persistence)
        
        # Check regime-tailwind relationships
        sim_regimes = simulation_data.get('regime_classification', pd.Series())
        hist_regimes = historical_data.get('regime_classification', pd.Series())
        
        if not sim_regimes.empty and not hist_regimes.empty:
            regime_relationship_match = self._compare_regime_tailwind_relationships(
                sim_tailwinds, sim_regimes, hist_tailwinds, hist_regimes
            )
        else:
            regime_relationship_match = 0.0
            inconsistencies.append("Missing regime data for tailwind relationship validation")
        
        distribution_match = self._clip01(distribution_match)
        correlation_match = self._clip01(correlation_match)
        persistence_match = self._clip01(persistence_match)
        regime_relationship_match = self._clip01(regime_relationship_match)

        # Calculate overall tailwind consistency
        overall_consistency = self._clip01(np.mean([
            distribution_match, correlation_match, persistence_match, regime_relationship_match
        ]))
        
        return TailwindConsistencyResult(
            distribution_match=distribution_match,
            correlation_structure_match=correlation_match,
            persistence_pattern_match=persistence_match,
            regime_relationship_match=regime_relationship_match,
            overall_consistency=overall_consistency,
            inconsistencies=inconsistencies
        )
    
    def _validate_no_edge_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> NoEdgeConsistencyResult:
        """Validate NO_EDGE trigger consistency"""
        
        # Extract NO_EDGE data
        sim_no_edge = simulation_data.get('no_edge_state', pd.Series(dtype=bool))
        hist_no_edge = historical_data.get('no_edge_state', pd.Series(dtype=bool))
        
        if sim_no_edge.empty or hist_no_edge.empty:
            logger.warning("Missing NO_EDGE state data")
            return NoEdgeConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Missing NO_EDGE data"])
        
        inconsistencies = []
        
        # Check trigger frequency
        sim_frequency = sim_no_edge.mean()
        hist_frequency = hist_no_edge.mean()
        
        freq_diff = abs(sim_frequency - hist_frequency)
        # Penalize large frequency divergence more aggressively to avoid
        # overstating consistency when simulation saturates to always-on/off.
        # The tighter denominator ensures large absolute drifts (e.g. always-on
        # simulation vs moderate historical trigger rate) are scored as clearly
        # inconsistent.
        freq_match = max(0.0, 1.0 - freq_diff / max(hist_frequency * 0.8, 0.01))
        
        if freq_match < self.consistency_thresholds['no_edge_frequency']:
            inconsistencies.append(f"NO_EDGE frequency mismatch: sim={sim_frequency:.3f}, hist={hist_frequency:.3f}")
        
        # Check trigger duration patterns
        sim_durations = self._calculate_no_edge_durations(sim_no_edge)
        hist_durations = self._calculate_no_edge_durations(hist_no_edge)
        
        duration_match = self._compare_duration_distributions(sim_durations, hist_durations)
        if duration_match < self.consistency_thresholds['no_edge_duration']:
            inconsistencies.append("NO_EDGE duration patterns inconsistent")
        
        # Check trigger conditions
        sim_conditions = simulation_data.get('no_edge_reasons', pd.Series())
        hist_conditions = historical_data.get('no_edge_reasons', pd.Series())
        
        if not sim_conditions.empty and not hist_conditions.empty:
            condition_match = self._compare_no_edge_conditions(sim_conditions, hist_conditions)
        else:
            condition_match = 0.0
            inconsistencies.append("Missing NO_EDGE trigger condition data")
        
        # Check recovery patterns
        recovery_match = self._compare_no_edge_recovery_patterns(sim_no_edge, hist_no_edge)
        
        freq_match = self._clip01(freq_match)
        duration_match = self._clip01(duration_match)
        condition_match = self._clip01(condition_match)
        recovery_match = self._clip01(recovery_match)

        # Calculate overall NO_EDGE consistency
        overall_consistency = self._clip01(
            np.mean([freq_match, duration_match, condition_match, recovery_match])
        )
        
        return NoEdgeConsistencyResult(
            trigger_frequency_match=freq_match,
            trigger_duration_match=duration_match,
            trigger_condition_match=condition_match,
            recovery_pattern_match=recovery_match,
            overall_consistency=overall_consistency,
            inconsistencies=inconsistencies
        )
    
    def _validate_anticipatory_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> AnticipatoryConsistencyResult:
        """Validate anticipatory signal consistency"""
        
        # Extract anticipatory signal data
        sim_signals = self._extract_anticipatory_signals(simulation_data)
        hist_signals = self._extract_anticipatory_signals(historical_data)
        
        if sim_signals.empty or hist_signals.empty:
            logger.warning("Missing anticipatory signal data")
            return AnticipatoryConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Missing anticipatory data"])
        
        inconsistencies = []
        
        # Check signal timing patterns
        timing_match = self._compare_signal_timing_patterns(sim_signals, hist_signals)
        if timing_match < self.consistency_thresholds['anticipatory_timing']:
            inconsistencies.append("Anticipatory signal timing patterns inconsistent")
        
        # Check lead-lag relationships
        lead_lag_match = self._compare_lead_lag_relationships(
            sim_signals, simulation_data, hist_signals, historical_data
        )
        
        # Check signal strength distributions
        strength_match = self._compare_signal_strength_distributions(sim_signals, hist_signals)
        
        # Check accuracy patterns
        accuracy_match = self._compare_anticipatory_accuracy_patterns(
            sim_signals, simulation_data, hist_signals, historical_data
        )
        if accuracy_match < self.consistency_thresholds['anticipatory_accuracy']:
            inconsistencies.append("Anticipatory accuracy patterns inconsistent")
        
        timing_match = self._clip01(timing_match)
        lead_lag_match = self._clip01(lead_lag_match)
        strength_match = self._clip01(strength_match)
        accuracy_match = self._clip01(accuracy_match)

        # Calculate overall anticipatory consistency
        overall_consistency = self._clip01(
            np.mean([timing_match, lead_lag_match, strength_match, accuracy_match])
        )
        
        return AnticipatoryConsistencyResult(
            signal_timing_match=timing_match,
            lead_lag_relationship_match=lead_lag_match,
            signal_strength_match=strength_match,
            accuracy_pattern_match=accuracy_match,
            overall_consistency=overall_consistency,
            inconsistencies=inconsistencies
        )
    
    def _calculate_regime_durations(self, regime_series: pd.Series) -> List[int]:
        """Calculate regime duration statistics"""
        if regime_series.empty:
            return []
        
        durations = []
        current_regime = regime_series.iloc[0]
        current_duration = 1
        
        for regime in regime_series.iloc[1:]:
            if regime == current_regime:
                current_duration += 1
            else:
                durations.append(current_duration)
                current_regime = regime
                current_duration = 1
        
        durations.append(current_duration)
        return durations
    
    def _calculate_regime_transitions(self, regime_series: pd.Series) -> pd.DataFrame:
        """Calculate regime transition matrix"""
        if regime_series.empty or len(regime_series) < 2:
            return pd.DataFrame()
        
        transitions = []
        for i in range(len(regime_series) - 1):
            transitions.append((regime_series.iloc[i], regime_series.iloc[i + 1]))
        
        transition_df = pd.DataFrame(transitions, columns=['from_regime', 'to_regime'])
        transition_matrix = pd.crosstab(
            transition_df['from_regime'], 
            transition_df['to_regime'], 
            normalize='index'
        )
        
        return transition_matrix
    
    def _compare_duration_distributions(self, sim_durations: List[int], hist_durations: List[int]) -> float:
        """Compare duration distributions using statistical tests"""
        if not sim_durations and not hist_durations:
            return 1.0
        if not sim_durations or not hist_durations:
            return 0.0
        
        try:
            # Use Kolmogorov-Smirnov test for distribution comparison
            ks_stat, p_value = stats.ks_2samp(sim_durations, hist_durations)
            return 1.0 - ks_stat if p_value > self.significance_level else 0.5
        except:
            return 0.0
    
    def _compare_transition_matrices(self, sim_matrix: pd.DataFrame, hist_matrix: pd.DataFrame) -> float:
        """Compare regime transition matrices"""
        if sim_matrix.empty or hist_matrix.empty:
            return 0.0
        
        # Align matrices
        all_regimes = set(sim_matrix.index) | set(sim_matrix.columns) | \
                     set(hist_matrix.index) | set(hist_matrix.columns)
        
        sim_aligned = sim_matrix.reindex(index=all_regimes, columns=all_regimes, fill_value=0.0)
        hist_aligned = hist_matrix.reindex(index=all_regimes, columns=all_regimes, fill_value=0.0)
        
        # Calculate Frobenius norm of difference
        diff_norm = np.linalg.norm(sim_aligned.values - hist_aligned.values, 'fro')
        max_norm = np.linalg.norm(hist_aligned.values, 'fro')
        
        if max_norm == 0:
            return 1.0 if diff_norm == 0 else 0.0
        
        return max(0.0, 1.0 - diff_norm / max_norm)
    
    def _compare_similarity_stability(self, sim_similarity: pd.Series, hist_similarity: pd.Series) -> float:
        """Compare regime similarity score stability"""
        if sim_similarity.empty or hist_similarity.empty:
            return 0.0
        
        # Compare variance and mean
        sim_var = sim_similarity.var()
        hist_var = hist_similarity.var()
        sim_mean = sim_similarity.mean()
        hist_mean = hist_similarity.mean()
        
        var_match = 1.0 - abs(sim_var - hist_var) / max(hist_var, 0.01)
        mean_match = 1.0 - abs(sim_mean - hist_mean) / max(hist_mean, 0.01)
        
        return self._clip01(np.mean([var_match, mean_match]))
    
    def _extract_tailwind_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract tailwind data from dataset"""
        tailwind_cols = [col for col in data.columns if 'tailwind' in col.lower()]
        if tailwind_cols:
            return data[tailwind_cols].dropna()
        return pd.DataFrame()
    
    def _compare_tailwind_distributions(self, sim_tailwinds: pd.DataFrame, hist_tailwinds: pd.DataFrame) -> float:
        """Compare tailwind distributions"""
        if sim_tailwinds.empty or hist_tailwinds.empty:
            return 0.0
        
        # Compare each tailwind component
        common_cols = set(sim_tailwinds.columns) & set(hist_tailwinds.columns)
        if not common_cols:
            return 0.0
        
        matches = []
        for col in common_cols:
            try:
                ks_stat, p_value = stats.ks_2samp(sim_tailwinds[col], hist_tailwinds[col])
                match = 1.0 - ks_stat if p_value > self.significance_level else 0.5
                matches.append(match)
            except:
                matches.append(0.0)
        
        return np.mean(matches) if matches else 0.0
    
    def _compare_tailwind_correlations(self, sim_tailwinds: pd.DataFrame, hist_tailwinds: pd.DataFrame) -> float:
        """Compare tailwind correlation structures"""
        if sim_tailwinds.empty or hist_tailwinds.empty:
            return 0.0
        
        common_cols = sorted(set(sim_tailwinds.columns) & set(hist_tailwinds.columns))
        if not common_cols:
            return 0.0
        if len(common_cols) == 1:
            aligned = pd.concat([
                sim_tailwinds[common_cols[0]].rename("sim"),
                hist_tailwinds[common_cols[0]].rename("hist"),
            ], axis=1).dropna()
            if aligned.empty:
                return 0.0
            return 1.0 if np.allclose(aligned["sim"].values, aligned["hist"].values, atol=1e-12) else 0.5
        
        try:
            sim_corr = sim_tailwinds[common_cols].corr()
            hist_corr = hist_tailwinds[common_cols].corr()
            
            # Calculate correlation between correlation matrices
            sim_corr_flat = sim_corr.values[np.triu_indices_from(sim_corr.values, k=1)]
            hist_corr_flat = hist_corr.values[np.triu_indices_from(hist_corr.values, k=1)]
            
            if len(sim_corr_flat) == 0:
                return 1.0

            sim_corr_flat = np.nan_to_num(sim_corr_flat, nan=0.0, posinf=0.0, neginf=0.0)
            hist_corr_flat = np.nan_to_num(hist_corr_flat, nan=0.0, posinf=0.0, neginf=0.0)

            if np.allclose(sim_corr_flat, hist_corr_flat, atol=1e-12):
                return 1.0

            if np.std(sim_corr_flat) <= 1e-12 or np.std(hist_corr_flat) <= 1e-12:
                mean_abs_diff = float(np.mean(np.abs(sim_corr_flat - hist_corr_flat)))
                return max(0.0, 1.0 - mean_abs_diff / 2.0)

            correlation = np.corrcoef(sim_corr_flat, hist_corr_flat)[0, 1]
            if np.isnan(correlation) or np.isinf(correlation):
                mean_abs_diff = float(np.mean(np.abs(sim_corr_flat - hist_corr_flat)))
                return max(0.0, 1.0 - mean_abs_diff / 2.0)
            return float(max(0.0, correlation))
        except:
            return 0.0
    
    def _calculate_tailwind_persistence(self, tailwinds: pd.DataFrame) -> Dict[str, float]:
        """Calculate tailwind persistence patterns"""
        persistence = {}
        
        for col in tailwinds.columns:
            series = tailwinds[col].dropna()
            if len(series) > 1:
                # Calculate autocorrelation at lag 1
                try:
                    autocorr = series.autocorr(lag=1)
                    persistence[col] = autocorr if not np.isnan(autocorr) else 0.0
                except:
                    persistence[col] = 0.0
            else:
                persistence[col] = 0.0
        
        return persistence
    
    def _compare_persistence_patterns(self, sim_persistence: Dict[str, float], hist_persistence: Dict[str, float]) -> float:
        """Compare tailwind persistence patterns"""
        common_keys = set(sim_persistence.keys()) & set(hist_persistence.keys())
        if not common_keys:
            return 0.0
        
        matches = []
        for key in common_keys:
            sim_val = float(np.nan_to_num(sim_persistence[key], nan=0.0, posinf=0.0, neginf=0.0))
            hist_val = float(np.nan_to_num(hist_persistence[key], nan=0.0, posinf=0.0, neginf=0.0))
            diff = abs(sim_val - hist_val)
            match = max(0.0, 1.0 - diff)
            matches.append(match)
        
        return np.mean(matches) if matches else 0.0
    
    def _compare_regime_tailwind_relationships(
        self,
        sim_tailwinds: pd.DataFrame,
        sim_regimes: pd.Series,
        hist_tailwinds: pd.DataFrame,
        hist_regimes: pd.Series
    ) -> float:
        """Compare regime-tailwind relationships"""
        
        # Align data by index
        sim_aligned = pd.concat([sim_tailwinds, sim_regimes.rename('regime')], axis=1).dropna()
        hist_aligned = pd.concat([hist_tailwinds, hist_regimes.rename('regime')], axis=1).dropna()
        
        if sim_aligned.empty or hist_aligned.empty:
            return 0.0
        
        # Compare mean tailwinds by regime
        common_regimes = set(sim_aligned['regime']) & set(hist_aligned['regime'])
        common_tailwinds = set(sim_tailwinds.columns) & set(hist_tailwinds.columns)
        
        if not common_regimes or not common_tailwinds:
            return 0.0
        
        matches = []
        for regime in common_regimes:
            sim_regime_data = sim_aligned[sim_aligned['regime'] == regime]
            hist_regime_data = hist_aligned[hist_aligned['regime'] == regime]
            
            for tailwind in common_tailwinds:
                if tailwind in sim_regime_data.columns and tailwind in hist_regime_data.columns:
                    sim_mean = sim_regime_data[tailwind].mean()
                    hist_mean = hist_regime_data[tailwind].mean()
                    
                    if not (np.isnan(sim_mean) or np.isnan(hist_mean)):
                        diff = abs(sim_mean - hist_mean)
                        match = max(0.0, 1.0 - diff / max(abs(hist_mean), 0.01))
                        matches.append(match)
        
        return np.mean(matches) if matches else 0.0
    
    def _calculate_no_edge_durations(self, no_edge_series: pd.Series) -> List[int]:
        """Calculate NO_EDGE state durations"""
        if no_edge_series.empty:
            return []
        
        durations = []
        in_no_edge = False
        current_duration = 0
        
        for state in no_edge_series:
            if state:  # In NO_EDGE state
                if in_no_edge:
                    current_duration += 1
                else:
                    in_no_edge = True
                    current_duration = 1
            else:  # Not in NO_EDGE state
                if in_no_edge:
                    durations.append(current_duration)
                    in_no_edge = False
                    current_duration = 0
        
        # Handle case where series ends in NO_EDGE state
        if in_no_edge:
            durations.append(current_duration)
        
        return durations
    
    def _compare_no_edge_conditions(self, sim_conditions: pd.Series, hist_conditions: pd.Series) -> float:
        """Compare NO_EDGE trigger conditions"""
        if sim_conditions.empty or hist_conditions.empty:
            return 0.0
        
        # Compare frequency of different trigger conditions
        sim_freq = sim_conditions.value_counts(normalize=True)
        hist_freq = hist_conditions.value_counts(normalize=True)
        
        # Align frequencies
        all_conditions = set(sim_freq.index) | set(hist_freq.index)
        sim_aligned = pd.Series([sim_freq.get(c, 0.0) for c in all_conditions], index=all_conditions)
        hist_aligned = pd.Series([hist_freq.get(c, 0.0) for c in all_conditions], index=all_conditions)
        
        # Calculate similarity
        diff = np.sum(np.abs(sim_aligned - hist_aligned))
        return max(0.0, 1.0 - diff / 2.0)  # Normalize by maximum possible difference
    
    def _compare_no_edge_recovery_patterns(self, sim_no_edge: pd.Series, hist_no_edge: pd.Series) -> float:
        """Compare NO_EDGE recovery patterns"""
        # Calculate time to recovery after NO_EDGE episodes
        sim_recovery = self._calculate_recovery_times(sim_no_edge)
        hist_recovery = self._calculate_recovery_times(hist_no_edge)
        
        if not sim_recovery and not hist_recovery:
            return 1.0
        if not sim_recovery or not hist_recovery:
            return 0.0
        
        return self._compare_duration_distributions(sim_recovery, hist_recovery)
    
    def _calculate_recovery_times(self, no_edge_series: pd.Series) -> List[int]:
        """Calculate recovery times after NO_EDGE episodes"""
        recovery_times = []
        in_no_edge = False
        recovery_count = 0
        
        for state in no_edge_series:
            if state:  # In NO_EDGE state
                in_no_edge = True
                recovery_count = 0
            else:  # Not in NO_EDGE state
                if in_no_edge:
                    recovery_count += 1
                else:
                    if recovery_count > 0:
                        recovery_times.append(recovery_count)
                        recovery_count = 0
        
        return recovery_times
    
    def _extract_anticipatory_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract anticipatory signal data"""
        signal_cols = [col for col in data.columns if 'anticipatory' in col.lower() or 'signal' in col.lower()]
        if signal_cols:
            return data[signal_cols].dropna()
        return pd.DataFrame()
    
    def _compare_signal_timing_patterns(self, sim_signals: pd.DataFrame, hist_signals: pd.DataFrame) -> float:
        """Compare anticipatory signal timing patterns"""
        if sim_signals.empty or hist_signals.empty:
            return 0.0
        
        # Compare signal generation frequency
        sim_freq = (sim_signals != 0).mean().mean()
        hist_freq = (hist_signals != 0).mean().mean()
        
        freq_diff = abs(sim_freq - hist_freq)
        return max(0.0, 1.0 - freq_diff / max(hist_freq, 0.01))
    
    def _compare_lead_lag_relationships(
        self,
        sim_signals: pd.DataFrame,
        sim_data: pd.DataFrame,
        hist_signals: pd.DataFrame,
        hist_data: pd.DataFrame
    ) -> float:
        """Compare lead-lag relationships between signals and outcomes"""
        # This is a simplified implementation
        # In practice, would analyze cross-correlations at different lags
        
        if sim_signals.empty or hist_signals.empty:
            return 0.0

        common_cols = sorted(set(sim_signals.columns) & set(hist_signals.columns))
        if not common_cols:
            return 0.0

        # If common signal series are effectively identical, lead-lag consistency is perfect.
        sim_common = sim_signals[common_cols].copy()
        hist_common = hist_signals[common_cols].copy()
        aligned = pd.concat(
            [sim_common.add_prefix("sim_"), hist_common.add_prefix("hist_")],
            axis=1
        ).dropna()
        if not aligned.empty:
            sim_vals = aligned[[f"sim_{c}" for c in common_cols]].values
            hist_vals = aligned[[f"hist_{c}" for c in common_cols]].values
            if np.allclose(sim_vals, hist_vals, atol=1e-12):
                return 1.0
        
        # Compare signal persistence patterns as proxy for lead-lag relationships
        sim_persistence = {}
        hist_persistence = {}
        
        for col in common_cols:
            sim_series = sim_signals[col].dropna()
            hist_series = hist_signals[col].dropna()

            if len(sim_series) > 1 and len(hist_series) > 1:
                try:
                    sim_autocorr = sim_series.autocorr(lag=1)
                    hist_autocorr = hist_series.autocorr(lag=1)
                    sim_persistence[col] = float(np.nan_to_num(sim_autocorr, nan=0.0, posinf=0.0, neginf=0.0))
                    hist_persistence[col] = float(np.nan_to_num(hist_autocorr, nan=0.0, posinf=0.0, neginf=0.0))
                except:
                    sim_persistence[col] = 0.0
                    hist_persistence[col] = 0.0
        
        return self._compare_persistence_patterns(sim_persistence, hist_persistence)
    
    def _compare_signal_strength_distributions(self, sim_signals: pd.DataFrame, hist_signals: pd.DataFrame) -> float:
        """Compare anticipatory signal strength distributions"""
        if sim_signals.empty or hist_signals.empty:
            return 0.0
        
        common_cols = set(sim_signals.columns) & set(hist_signals.columns)
        if not common_cols:
            return 0.0
        
        matches = []
        for col in common_cols:
            try:
                ks_stat, p_value = stats.ks_2samp(sim_signals[col], hist_signals[col])
                match = 1.0 - ks_stat if p_value > self.significance_level else 0.5
                matches.append(match)
            except:
                matches.append(0.0)
        
        return np.mean(matches) if matches else 0.0
    
    def _compare_anticipatory_accuracy_patterns(
        self,
        sim_signals: pd.DataFrame,
        sim_data: pd.DataFrame,
        hist_signals: pd.DataFrame,
        hist_data: pd.DataFrame
    ) -> float:
        """Compare anticipatory signal accuracy patterns"""
        # Simplified implementation - would need actual accuracy metrics
        # For now, compare signal volatility as proxy for accuracy consistency
        
        if sim_signals.empty or hist_signals.empty:
            return 0.0
        
        common_cols = set(sim_signals.columns) & set(hist_signals.columns)
        if not common_cols:
            return 0.0
        
        matches = []
        for col in common_cols:
            sim_vol = sim_signals[col].std()
            hist_vol = hist_signals[col].std()

            if np.isnan(sim_vol) or np.isnan(hist_vol):
                continue

            # If both are effectively constant, treat as a strong match.
            if sim_vol <= 1e-12 and hist_vol <= 1e-12:
                matches.append(1.0)
                continue

            if hist_vol > 1e-12:
                vol_diff = abs(sim_vol - hist_vol)
                match = max(0.0, 1.0 - vol_diff / hist_vol)
                matches.append(match)
            else:
                # Historical constant but simulated varying: weak match.
                matches.append(0.5 if sim_vol <= 1e-12 else 0.0)
        
        return np.mean(matches) if matches else 0.0
    
    def _calculate_overall_consistency(
        self,
        regime_result: RegimeConsistencyResult,
        tailwind_result: TailwindConsistencyResult,
        no_edge_result: NoEdgeConsistencyResult,
        anticipatory_result: AnticipatoryConsistencyResult
    ) -> float:
        """Calculate overall Phase 3 reality consistency score"""
        
        # Weight components based on importance
        weights = {
            'regime': 0.30,
            'tailwind': 0.25,
            'no_edge': 0.25,
            'anticipatory': 0.20
        }
        
        weighted_score = (
            weights['regime'] * regime_result.overall_consistency +
            weights['tailwind'] * tailwind_result.overall_consistency +
            weights['no_edge'] * no_edge_result.overall_consistency +
            weights['anticipatory'] * anticipatory_result.overall_consistency
        )
        
        return self._clip01(weighted_score)
    
    def _identify_critical_inconsistencies(
        self,
        regime_result: RegimeConsistencyResult,
        tailwind_result: TailwindConsistencyResult,
        no_edge_result: NoEdgeConsistencyResult,
        anticipatory_result: AnticipatoryConsistencyResult
    ) -> List[str]:
        """Identify critical inconsistencies requiring attention"""
        
        critical_inconsistencies = []
        
        # Check for critical regime inconsistencies
        if regime_result.overall_consistency < 0.70:
            critical_inconsistencies.extend([
                f"Critical regime consistency failure: {regime_result.overall_consistency:.3f}"
            ])
            critical_inconsistencies.extend(regime_result.inconsistencies)
        
        # Check for critical tailwind inconsistencies
        if tailwind_result.overall_consistency < 0.70:
            critical_inconsistencies.extend([
                f"Critical tailwind consistency failure: {tailwind_result.overall_consistency:.3f}"
            ])
            critical_inconsistencies.extend(tailwind_result.inconsistencies)
        
        # Check for critical NO_EDGE inconsistencies
        if no_edge_result.overall_consistency < 0.70:
            critical_inconsistencies.extend([
                f"Critical NO_EDGE consistency failure: {no_edge_result.overall_consistency:.3f}"
            ])
            critical_inconsistencies.extend(no_edge_result.inconsistencies)
        
        # Check for critical anticipatory inconsistencies
        if anticipatory_result.overall_consistency < 0.70:
            critical_inconsistencies.extend([
                f"Critical anticipatory consistency failure: {anticipatory_result.overall_consistency:.3f}"
            ])
            critical_inconsistencies.extend(anticipatory_result.inconsistencies)
        
        return critical_inconsistencies
    
    def _generate_recommendations(
        self,
        regime_result: RegimeConsistencyResult,
        tailwind_result: TailwindConsistencyResult,
        no_edge_result: NoEdgeConsistencyResult,
        anticipatory_result: AnticipatoryConsistencyResult
    ) -> List[str]:
        """Generate recommendations for improving consistency"""
        
        recommendations = []
        
        # Regime recommendations
        if regime_result.regime_frequency_match < 0.80:
            recommendations.append("Adjust regime classification parameters to match historical frequencies")
        
        if regime_result.regime_duration_match < 0.80:
            recommendations.append("Review regime persistence parameters to match historical durations")
        
        if regime_result.regime_transition_match < 0.75:
            recommendations.append("Calibrate regime transition probabilities using historical data")
        
        # Tailwind recommendations
        if tailwind_result.distribution_match < 0.80:
            recommendations.append("Recalibrate tailwind calculation parameters to match historical distributions")
        
        if tailwind_result.correlation_structure_match < 0.75:
            recommendations.append("Review tailwind correlation model to preserve historical relationships")
        
        # NO_EDGE recommendations
        if no_edge_result.trigger_frequency_match < 0.85:
            recommendations.append("Adjust NO_EDGE trigger thresholds to match historical frequency")
        
        if no_edge_result.trigger_duration_match < 0.80:
            recommendations.append("Review NO_EDGE exit conditions to match historical recovery patterns")
        
        # Anticipatory recommendations
        if anticipatory_result.signal_timing_match < 0.75:
            recommendations.append("Calibrate anticipatory signal timing to match historical patterns")
        
        if anticipatory_result.accuracy_pattern_match < 0.70:
            recommendations.append("Review anticipatory signal accuracy metrics and validation methods")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Phase 3 reality consistency is acceptable - continue monitoring")
        
        return recommendations
