"""
Statistical Consistency Checker

Compares simulated vs historical market statistics to ensure Phase 3 components
maintain statistical consistency with empirical market characteristics.

This checker validates:
- Correlation structures remain within historical ranges
- Volatility patterns match empirical characteristics  
- Regime similarity calculations remain stable
- Statistical distributions are preserved across simulations
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from scipy import stats
from scipy.stats import kstest, anderson, jarque_bera
import logging
import warnings

from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class CorrelationConsistencyResult:
    """Results of correlation structure consistency check"""
    correlation_stability: float
    correlation_range_compliance: float
    correlation_structure_preservation: float
    eigenvalue_stability: float
    overall_correlation_consistency: float
    violations: List[str]

@dataclass
class VolatilityConsistencyResult:
    """Results of volatility pattern consistency check"""
    volatility_distribution_match: float
    volatility_clustering_preservation: float
    volatility_regime_relationship: float
    garch_pattern_consistency: float
    overall_volatility_consistency: float
    violations: List[str]

@dataclass
class DistributionConsistencyResult:
    """Results of statistical distribution consistency check"""
    normality_test_consistency: float
    tail_behavior_consistency: float
    skewness_consistency: float
    kurtosis_consistency: float
    overall_distribution_consistency: float
    violations: List[str]

@dataclass
class RegimeSimilarityStabilityResult:
    """Results of regime similarity calculation stability check"""
    similarity_score_stability: float
    similarity_ranking_stability: float
    similarity_threshold_stability: float
    similarity_calculation_robustness: float
    overall_similarity_stability: float
    violations: List[str]

@dataclass
class StatisticalConsistencyResult:
    """Complete statistical consistency validation result"""
    validation_timestamp: datetime
    validation_period: Tuple[datetime, datetime]
    correlation_consistency: CorrelationConsistencyResult
    volatility_consistency: VolatilityConsistencyResult
    distribution_consistency: DistributionConsistencyResult
    regime_similarity_stability: RegimeSimilarityStabilityResult
    overall_statistical_consistency: float
    critical_violations: List[str]
    recommendations: List[str]

class StatisticalConsistencyChecker:
    """
    Validates statistical consistency between simulated and historical market data
    
    Ensures that Phase 3 components maintain proper statistical characteristics
    and that simulations preserve empirical market properties.
    """
    
    def __init__(self):
        # Statistical test significance levels
        self.significance_level = 0.05
        self.critical_significance_level = 0.01
        
        # Consistency thresholds
        self.consistency_thresholds = {
            'correlation_stability': 0.85,
            'correlation_range': 0.80,
            'volatility_distribution': 0.80,
            'volatility_clustering': 0.75,
            'distribution_normality': 0.70,
            'tail_behavior': 0.75,
            'regime_similarity': 0.85,
            'similarity_ranking': 0.80
        }
        
        # Acceptable ranges for market statistics
        self.acceptable_ranges = {
            'correlation_bounds': (-0.95, 0.95),
            'volatility_bounds': (0.001, 1.0),
            'skewness_bounds': (-3.0, 3.0),
            'kurtosis_bounds': (1.0, 20.0),
            'similarity_bounds': (0.0, 1.0)
        }
        
    def check_statistical_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame,
        validation_period: Tuple[datetime, datetime]
    ) -> StatisticalConsistencyResult:
        """
        Perform comprehensive statistical consistency validation
        
        Args:
            simulation_data: Simulated market data with Phase 3 signals
            historical_data: Historical market data for comparison
            validation_period: Period being validated
            
        Returns:
            Complete statistical consistency validation result
        """
        logger.info(f"Starting statistical consistency check for period {validation_period}")
        
        try:
            # Check correlation structure consistency
            correlation_result = self._check_correlation_consistency(
                simulation_data, historical_data
            )
            
            # Check volatility pattern consistency
            volatility_result = self._check_volatility_consistency(
                simulation_data, historical_data
            )
            
            # Check statistical distribution consistency
            distribution_result = self._check_distribution_consistency(
                simulation_data, historical_data
            )
            
            # Check regime similarity stability
            similarity_result = self._check_regime_similarity_stability(
                simulation_data, historical_data
            )
            
            # Calculate overall consistency
            overall_consistency = self._calculate_overall_statistical_consistency(
                correlation_result, volatility_result, distribution_result, similarity_result
            )
            
            # Identify critical violations
            critical_violations = self._identify_critical_violations(
                correlation_result, volatility_result, distribution_result, similarity_result
            )
            
            # Generate recommendations
            recommendations = self._generate_statistical_recommendations(
                correlation_result, volatility_result, distribution_result, similarity_result
            )
            
            result = StatisticalConsistencyResult(
                validation_timestamp=datetime.now(),
                validation_period=validation_period,
                correlation_consistency=correlation_result,
                volatility_consistency=volatility_result,
                distribution_consistency=distribution_result,
                regime_similarity_stability=similarity_result,
                overall_statistical_consistency=overall_consistency,
                critical_violations=critical_violations,
                recommendations=recommendations
            )
            
            logger.info(f"Statistical consistency check completed. Overall consistency: {overall_consistency:.3f}")
            return result
            
        except Exception as e:
            logger.error(f"Statistical consistency check failed: {str(e)}")
            raise
    
    def _check_correlation_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> CorrelationConsistencyResult:
        """Check correlation structure consistency"""
        
        violations = []
        
        # Extract numeric columns for correlation analysis
        sim_numeric = self._extract_numeric_columns(simulation_data)
        hist_numeric = self._extract_numeric_columns(historical_data)
        
        if sim_numeric.empty or hist_numeric.empty:
            logger.warning("Insufficient numeric data for correlation analysis")
            return CorrelationConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Insufficient numeric data"])
        
        # Find common columns
        common_cols = list(set(sim_numeric.columns) & set(hist_numeric.columns))
        if len(common_cols) < 2:
            violations.append("Insufficient common columns for correlation analysis")
            return CorrelationConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, violations)
        
        # Calculate correlation matrices
        sim_corr = sim_numeric[common_cols].corr()
        hist_corr = hist_numeric[common_cols].corr()
        
        # Check correlation stability
        correlation_stability = self._calculate_correlation_stability(sim_corr, hist_corr)
        if correlation_stability < self.consistency_thresholds['correlation_stability']:
            violations.append(f"Correlation stability below threshold: {correlation_stability:.3f}")
        
        # Check correlation range compliance
        range_compliance = self._check_correlation_range_compliance(sim_corr, hist_corr)
        if range_compliance < self.consistency_thresholds['correlation_range']:
            violations.append(f"Correlation range compliance below threshold: {range_compliance:.3f}")
        
        # Check correlation structure preservation
        structure_preservation = self._check_correlation_structure_preservation(sim_corr, hist_corr)
        
        # Check eigenvalue stability (for PCA-like analysis)
        eigenvalue_stability = self._check_eigenvalue_stability(sim_corr, hist_corr)
        
        # Calculate overall correlation consistency
        overall_consistency = np.mean([
            correlation_stability, range_compliance, structure_preservation, eigenvalue_stability
        ])
        
        return CorrelationConsistencyResult(
            correlation_stability=correlation_stability,
            correlation_range_compliance=range_compliance,
            correlation_structure_preservation=structure_preservation,
            eigenvalue_stability=eigenvalue_stability,
            overall_correlation_consistency=overall_consistency,
            violations=violations
        )
    
    def _check_volatility_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> VolatilityConsistencyResult:
        """Check volatility pattern consistency"""
        
        violations = []
        
        # Calculate returns for volatility analysis
        sim_returns = self._calculate_returns(simulation_data)
        hist_returns = self._calculate_returns(historical_data)
        
        if sim_returns.empty or hist_returns.empty:
            logger.warning("Insufficient data for volatility analysis")
            return VolatilityConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Insufficient return data"])
        
        # Check volatility distribution match
        distribution_match = self._check_volatility_distribution_match(sim_returns, hist_returns)
        if distribution_match < self.consistency_thresholds['volatility_distribution']:
            violations.append(f"Volatility distribution mismatch: {distribution_match:.3f}")
        
        # Check volatility clustering preservation
        clustering_preservation = self._check_volatility_clustering(sim_returns, hist_returns)
        if clustering_preservation < self.consistency_thresholds['volatility_clustering']:
            violations.append(f"Volatility clustering not preserved: {clustering_preservation:.3f}")
        
        # Check volatility-regime relationship
        regime_relationship = self._check_volatility_regime_relationship(
            sim_returns, simulation_data, hist_returns, historical_data
        )
        
        # Check GARCH-like pattern consistency
        garch_consistency = self._check_garch_pattern_consistency(sim_returns, hist_returns)
        
        # Calculate overall volatility consistency
        overall_consistency = np.mean([
            distribution_match, clustering_preservation, regime_relationship, garch_consistency
        ])
        
        return VolatilityConsistencyResult(
            volatility_distribution_match=distribution_match,
            volatility_clustering_preservation=clustering_preservation,
            volatility_regime_relationship=regime_relationship,
            garch_pattern_consistency=garch_consistency,
            overall_volatility_consistency=overall_consistency,
            violations=violations
        )
    
    def _check_distribution_consistency(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> DistributionConsistencyResult:
        """Check statistical distribution consistency"""
        
        violations = []
        
        # Extract numeric data for distribution analysis
        sim_numeric = self._extract_numeric_columns(simulation_data)
        hist_numeric = self._extract_numeric_columns(historical_data)
        
        if sim_numeric.empty or hist_numeric.empty:
            logger.warning("Insufficient numeric data for distribution analysis")
            return DistributionConsistencyResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Insufficient numeric data"])
        
        # Check normality test consistency
        normality_consistency = self._check_normality_test_consistency(sim_numeric, hist_numeric)
        if normality_consistency < self.consistency_thresholds['distribution_normality']:
            violations.append(f"Normality test consistency below threshold: {normality_consistency:.3f}")
        
        # Check tail behavior consistency
        tail_consistency = self._check_tail_behavior_consistency(sim_numeric, hist_numeric)
        if tail_consistency < self.consistency_thresholds['tail_behavior']:
            violations.append(f"Tail behavior consistency below threshold: {tail_consistency:.3f}")
        
        # Check skewness consistency
        skewness_consistency = self._check_skewness_consistency(sim_numeric, hist_numeric)
        
        # Check kurtosis consistency
        kurtosis_consistency = self._check_kurtosis_consistency(sim_numeric, hist_numeric)
        
        # Calculate overall distribution consistency
        overall_consistency = np.mean([
            normality_consistency, tail_consistency, skewness_consistency, kurtosis_consistency
        ])
        
        return DistributionConsistencyResult(
            normality_test_consistency=normality_consistency,
            tail_behavior_consistency=tail_consistency,
            skewness_consistency=skewness_consistency,
            kurtosis_consistency=kurtosis_consistency,
            overall_distribution_consistency=overall_consistency,
            violations=violations
        )
    
    def _check_regime_similarity_stability(
        self,
        simulation_data: pd.DataFrame,
        historical_data: pd.DataFrame
    ) -> RegimeSimilarityStabilityResult:
        """Check regime similarity calculation stability"""
        
        violations = []
        
        # Extract regime similarity data
        sim_similarity = simulation_data.get('regime_similarity_score', pd.Series())
        hist_similarity = historical_data.get('regime_similarity_score', pd.Series())
        
        if sim_similarity.empty or hist_similarity.empty:
            logger.warning("Missing regime similarity data")
            return RegimeSimilarityStabilityResult(0.0, 0.0, 0.0, 0.0, 0.0, ["Missing similarity data"])
        
        # Check similarity score stability
        score_stability = self._check_similarity_score_stability(sim_similarity, hist_similarity)
        if score_stability < self.consistency_thresholds['regime_similarity']:
            violations.append(f"Regime similarity score instability: {score_stability:.3f}")
        
        # Check similarity ranking stability
        ranking_stability = self._check_similarity_ranking_stability(
            simulation_data, historical_data
        )
        if ranking_stability < self.consistency_thresholds['similarity_ranking']:
            violations.append(f"Similarity ranking instability: {ranking_stability:.3f}")
        
        # Check similarity threshold stability
        threshold_stability = self._check_similarity_threshold_stability(sim_similarity, hist_similarity)
        
        # Check calculation robustness
        calculation_robustness = self._check_similarity_calculation_robustness(
            sim_similarity, hist_similarity
        )
        
        # Calculate overall similarity stability
        overall_stability = np.mean([
            score_stability, ranking_stability, threshold_stability, calculation_robustness
        ])
        
        return RegimeSimilarityStabilityResult(
            similarity_score_stability=score_stability,
            similarity_ranking_stability=ranking_stability,
            similarity_threshold_stability=threshold_stability,
            similarity_calculation_robustness=calculation_robustness,
            overall_similarity_stability=overall_stability,
            violations=violations
        )
    
    def _extract_numeric_columns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract numeric columns suitable for statistical analysis"""
        numeric_data = data.select_dtypes(include=[np.number])
        
        # Remove columns with insufficient variance
        for col in numeric_data.columns:
            if numeric_data[col].var() < 1e-10:
                numeric_data = numeric_data.drop(col, axis=1)
        
        return numeric_data.dropna()
    
    def _calculate_returns(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate returns from price-like data"""
        numeric_data = self._extract_numeric_columns(data)
        
        # Look for price-like columns
        price_cols = []
        for col in numeric_data.columns:
            col_lower = col.lower()
            if any(keyword in col_lower for keyword in ['price', 'value', 'level', 'index']):
                price_cols.append(col)
        
        if not price_cols:
            # Use all numeric columns as proxy
            price_cols = numeric_data.columns[:min(5, len(numeric_data.columns))]
        
        returns = pd.DataFrame(index=numeric_data.index)
        for col in price_cols:
            if len(numeric_data[col].dropna()) > 1:
                returns[f'{col}_return'] = numeric_data[col].pct_change()
        
        return returns.dropna()
    
    def _calculate_correlation_stability(self, sim_corr: pd.DataFrame, hist_corr: pd.DataFrame) -> float:
        """Calculate correlation matrix stability"""
        if sim_corr.empty or hist_corr.empty:
            return 0.0
        
        # Align correlation matrices
        common_idx = sim_corr.index.intersection(hist_corr.index)
        common_cols = sim_corr.columns.intersection(hist_corr.columns)
        
        if len(common_idx) < 2 or len(common_cols) < 2:
            return 0.0
        
        sim_aligned = sim_corr.loc[common_idx, common_cols]
        hist_aligned = hist_corr.loc[common_idx, common_cols]
        
        # Calculate Frobenius norm of difference
        diff_matrix = sim_aligned - hist_aligned
        frobenius_norm = np.linalg.norm(diff_matrix.values, 'fro')
        
        # Normalize by historical correlation matrix norm
        hist_norm = np.linalg.norm(hist_aligned.values, 'fro')
        if hist_norm == 0:
            return 1.0 if frobenius_norm == 0 else 0.0
        
        stability = max(0.0, 1.0 - frobenius_norm / hist_norm)
        return stability
    
    def _check_correlation_range_compliance(self, sim_corr: pd.DataFrame, hist_corr: pd.DataFrame) -> float:
        """Check if correlations stay within acceptable ranges"""
        if sim_corr.empty or hist_corr.empty:
            return 0.0
        
        min_corr, max_corr = self.acceptable_ranges['correlation_bounds']
        
        # Check simulation correlations
        sim_values = sim_corr.values[np.triu_indices_from(sim_corr.values, k=1)]
        sim_violations = np.sum((sim_values < min_corr) | (sim_values > max_corr))
        
        # Check historical correlations for reference
        hist_values = hist_corr.values[np.triu_indices_from(hist_corr.values, k=1)]
        hist_violations = np.sum((hist_values < min_corr) | (hist_values > max_corr))
        
        total_correlations = len(sim_values)
        if total_correlations == 0:
            return 1.0
        
        # Calculate compliance rate
        sim_compliance = 1.0 - sim_violations / total_correlations
        hist_compliance = 1.0 - hist_violations / total_correlations
        
        # Return relative compliance
        if hist_compliance == 0:
            return 1.0 if sim_compliance == 0 else 0.0
        
        return min(1.0, sim_compliance / hist_compliance)
    
    def _check_correlation_structure_preservation(self, sim_corr: pd.DataFrame, hist_corr: pd.DataFrame) -> float:
        """Check if correlation structure is preserved"""
        if sim_corr.empty or hist_corr.empty:
            return 0.0
        
        # Align matrices
        common_idx = sim_corr.index.intersection(hist_corr.index)
        common_cols = sim_corr.columns.intersection(hist_corr.columns)
        
        if len(common_idx) < 2 or len(common_cols) < 2:
            return 0.0
        
        sim_aligned = sim_corr.loc[common_idx, common_cols]
        hist_aligned = hist_corr.loc[common_idx, common_cols]
        
        # Extract upper triangular correlations
        sim_values = sim_aligned.values[np.triu_indices_from(sim_aligned.values, k=1)]
        hist_values = hist_aligned.values[np.triu_indices_from(hist_aligned.values, k=1)]
        
        if len(sim_values) == 0:
            return 1.0
        
        # Calculate correlation between correlation vectors
        try:
            structure_correlation = np.corrcoef(sim_values, hist_values)[0, 1]
            return max(0.0, structure_correlation) if not np.isnan(structure_correlation) else 0.0
        except:
            return 0.0
    
    def _check_eigenvalue_stability(self, sim_corr: pd.DataFrame, hist_corr: pd.DataFrame) -> float:
        """Check eigenvalue stability of correlation matrices"""
        if sim_corr.empty or hist_corr.empty:
            return 0.0
        
        try:
            # Align matrices
            common_idx = sim_corr.index.intersection(hist_corr.index)
            common_cols = sim_corr.columns.intersection(hist_corr.columns)
            
            if len(common_idx) < 2 or len(common_cols) < 2:
                return 0.0
            
            sim_aligned = sim_corr.loc[common_idx, common_cols]
            hist_aligned = hist_corr.loc[common_idx, common_cols]
            
            # Calculate eigenvalues
            sim_eigenvals = np.linalg.eigvals(sim_aligned.values)
            hist_eigenvals = np.linalg.eigvals(hist_aligned.values)
            
            # Sort eigenvalues
            sim_eigenvals = np.sort(sim_eigenvals)[::-1]
            hist_eigenvals = np.sort(hist_eigenvals)[::-1]
            
            # Calculate stability as correlation between eigenvalue vectors
            eigenval_correlation = np.corrcoef(sim_eigenvals, hist_eigenvals)[0, 1]
            return max(0.0, eigenval_correlation) if not np.isnan(eigenval_correlation) else 0.0
            
        except:
            return 0.0
    
    def _check_volatility_distribution_match(self, sim_returns: pd.DataFrame, hist_returns: pd.DataFrame) -> float:
        """Check if volatility distributions match"""
        if sim_returns.empty or hist_returns.empty:
            return 0.0
        
        # Calculate volatilities (rolling standard deviation)
        window = min(20, len(sim_returns) // 4, len(hist_returns) // 4)
        if window < 5:
            return 0.0
        
        matches = []
        common_cols = set(sim_returns.columns) & set(hist_returns.columns)
        
        for col in common_cols:
            sim_vol = sim_returns[col].rolling(window=window).std().dropna()
            hist_vol = hist_returns[col].rolling(window=window).std().dropna()
            
            if len(sim_vol) > 10 and len(hist_vol) > 10:
                try:
                    # Use Kolmogorov-Smirnov test
                    ks_stat, p_value = stats.ks_2samp(sim_vol, hist_vol)
                    match = 1.0 - ks_stat if p_value > self.significance_level else 0.5
                    matches.append(match)
                except:
                    matches.append(0.0)
        
        return np.mean(matches) if matches else 0.0
    
    def _check_volatility_clustering(self, sim_returns: pd.DataFrame, hist_returns: pd.DataFrame) -> float:
        """Check if volatility clustering patterns are preserved"""
        if sim_returns.empty or hist_returns.empty:
            return 0.0
        
        matches = []
        common_cols = set(sim_returns.columns) & set(hist_returns.columns)
        
        for col in common_cols:
            sim_series = sim_returns[col].dropna()
            hist_series = hist_returns[col].dropna()
            
            if len(sim_series) > 20 and len(hist_series) > 20:
                # Calculate volatility clustering measure (autocorrelation of squared returns)
                sim_clustering = self._calculate_volatility_clustering_measure(sim_series)
                hist_clustering = self._calculate_volatility_clustering_measure(hist_series)
                
                if hist_clustering != 0:
                    clustering_match = 1.0 - abs(sim_clustering - hist_clustering) / abs(hist_clustering)
                    matches.append(max(0.0, clustering_match))
        
        return np.mean(matches) if matches else 0.0
    
    def _calculate_volatility_clustering_measure(self, returns: pd.Series) -> float:
        """Calculate volatility clustering measure"""
        try:
            squared_returns = returns ** 2
            autocorr = squared_returns.autocorr(lag=1)
            return autocorr if not np.isnan(autocorr) else 0.0
        except:
            return 0.0
    
    def _check_volatility_regime_relationship(
        self,
        sim_returns: pd.DataFrame,
        sim_data: pd.DataFrame,
        hist_returns: pd.DataFrame,
        hist_data: pd.DataFrame
    ) -> float:
        """Check if volatility-regime relationships are preserved"""
        
        # Extract regime data
        sim_regimes = sim_data.get('regime_classification', pd.Series())
        hist_regimes = hist_data.get('regime_classification', pd.Series())
        
        if sim_regimes.empty or hist_regimes.empty or sim_returns.empty or hist_returns.empty:
            return 0.0
        
        # Align data
        sim_aligned = pd.concat([sim_returns, sim_regimes.rename('regime')], axis=1).dropna()
        hist_aligned = pd.concat([hist_returns, hist_regimes.rename('regime')], axis=1).dropna()
        
        if sim_aligned.empty or hist_aligned.empty:
            return 0.0
        
        # Compare volatility by regime
        common_regimes = set(sim_aligned['regime']) & set(hist_aligned['regime'])
        common_return_cols = set(sim_returns.columns) & set(hist_returns.columns)
        
        if not common_regimes or not common_return_cols:
            return 0.0
        
        matches = []
        for regime in common_regimes:
            sim_regime_data = sim_aligned[sim_aligned['regime'] == regime]
            hist_regime_data = hist_aligned[hist_aligned['regime'] == regime]
            
            for col in common_return_cols:
                if col in sim_regime_data.columns and col in hist_regime_data.columns:
                    sim_vol = sim_regime_data[col].std()
                    hist_vol = hist_regime_data[col].std()
                    
                    if not (np.isnan(sim_vol) or np.isnan(hist_vol)) and hist_vol > 0:
                        vol_match = 1.0 - abs(sim_vol - hist_vol) / hist_vol
                        matches.append(max(0.0, vol_match))
        
        return np.mean(matches) if matches else 0.0
    
    def _check_garch_pattern_consistency(self, sim_returns: pd.DataFrame, hist_returns: pd.DataFrame) -> float:
        """Check GARCH-like pattern consistency (simplified)"""
        if sim_returns.empty or hist_returns.empty:
            return 0.0
        
        matches = []
        common_cols = set(sim_returns.columns) & set(hist_returns.columns)
        
        for col in common_cols:
            sim_series = sim_returns[col].dropna()
            hist_series = hist_returns[col].dropna()
            
            if len(sim_series) > 30 and len(hist_series) > 30:
                # Simple GARCH-like measure: autocorrelation of squared returns at multiple lags
                sim_garch_measure = self._calculate_garch_measure(sim_series)
                hist_garch_measure = self._calculate_garch_measure(hist_series)
                
                if hist_garch_measure != 0:
                    garch_match = 1.0 - abs(sim_garch_measure - hist_garch_measure) / abs(hist_garch_measure)
                    matches.append(max(0.0, garch_match))
        
        return np.mean(matches) if matches else 0.0
    
    def _calculate_garch_measure(self, returns: pd.Series) -> float:
        """Calculate simplified GARCH-like measure"""
        try:
            squared_returns = returns ** 2
            # Average autocorrelation at lags 1-5
            autocorrs = []
            for lag in range(1, 6):
                autocorr = squared_returns.autocorr(lag=lag)
                if not np.isnan(autocorr):
                    autocorrs.append(autocorr)
            
            return np.mean(autocorrs) if autocorrs else 0.0
        except:
            return 0.0
    
    def _check_normality_test_consistency(self, sim_data: pd.DataFrame, hist_data: pd.DataFrame) -> float:
        """Check consistency of normality test results"""
        if sim_data.empty or hist_data.empty:
            return 0.0
        
        matches = []
        common_cols = set(sim_data.columns) & set(hist_data.columns)
        
        for col in common_cols:
            sim_series = sim_data[col].dropna()
            hist_series = hist_data[col].dropna()
            
            if len(sim_series) > 20 and len(hist_series) > 20:
                # Jarque-Bera test for normality
                sim_jb_stat, sim_jb_p = jarque_bera(sim_series)
                hist_jb_stat, hist_jb_p = jarque_bera(hist_series)
                
                # Check if both reject or both accept normality
                sim_normal = sim_jb_p > self.significance_level
                hist_normal = hist_jb_p > self.significance_level
                
                match = 1.0 if sim_normal == hist_normal else 0.0
                matches.append(match)
        
        return np.mean(matches) if matches else 0.0
    
    def _check_tail_behavior_consistency(self, sim_data: pd.DataFrame, hist_data: pd.DataFrame) -> float:
        """Check tail behavior consistency"""
        if sim_data.empty or hist_data.empty:
            return 0.0
        
        matches = []
        common_cols = set(sim_data.columns) & set(hist_data.columns)
        
        for col in common_cols:
            sim_series = sim_data[col].dropna()
            hist_series = hist_data[col].dropna()
            
            if len(sim_series) > 50 and len(hist_series) > 50:
                # Compare extreme quantiles
                quantiles = [0.01, 0.05, 0.95, 0.99]
                tail_matches = []
                
                for q in quantiles:
                    sim_quantile = sim_series.quantile(q)
                    hist_quantile = hist_series.quantile(q)
                    
                    if hist_quantile != 0:
                        quantile_match = 1.0 - abs(sim_quantile - hist_quantile) / abs(hist_quantile)
                        tail_matches.append(max(0.0, quantile_match))
                
                if tail_matches:
                    matches.append(np.mean(tail_matches))
        
        return np.mean(matches) if matches else 0.0
    
    def _check_skewness_consistency(self, sim_data: pd.DataFrame, hist_data: pd.DataFrame) -> float:
        """Check skewness consistency"""
        if sim_data.empty or hist_data.empty:
            return 0.0
        
        matches = []
        common_cols = set(sim_data.columns) & set(hist_data.columns)
        
        for col in common_cols:
            sim_series = sim_data[col].dropna()
            hist_series = hist_data[col].dropna()
            
            if len(sim_series) > 20 and len(hist_series) > 20:
                try:
                    sim_skew = stats.skew(sim_series)
                    hist_skew = stats.skew(hist_series)
                    
                    if not (np.isnan(sim_skew) or np.isnan(hist_skew)):
                        skew_diff = abs(sim_skew - hist_skew)
                        # Normalize by acceptable skewness range
                        max_skew_diff = self.acceptable_ranges['skewness_bounds'][1] - self.acceptable_ranges['skewness_bounds'][0]
                        skew_match = max(0.0, 1.0 - skew_diff / max_skew_diff)
                        matches.append(skew_match)
                except:
                    matches.append(0.0)
        
        return np.mean(matches) if matches else 0.0
    
    def _check_kurtosis_consistency(self, sim_data: pd.DataFrame, hist_data: pd.DataFrame) -> float:
        """Check kurtosis consistency"""
        if sim_data.empty or hist_data.empty:
            return 0.0
        
        matches = []
        common_cols = set(sim_data.columns) & set(hist_data.columns)
        
        for col in common_cols:
            sim_series = sim_data[col].dropna()
            hist_series = hist_data[col].dropna()
            
            if len(sim_series) > 20 and len(hist_series) > 20:
                try:
                    sim_kurt = stats.kurtosis(sim_series)
                    hist_kurt = stats.kurtosis(hist_series)
                    
                    if not (np.isnan(sim_kurt) or np.isnan(hist_kurt)):
                        kurt_diff = abs(sim_kurt - hist_kurt)
                        # Normalize by acceptable kurtosis range
                        max_kurt_diff = self.acceptable_ranges['kurtosis_bounds'][1] - self.acceptable_ranges['kurtosis_bounds'][0]
                        kurt_match = max(0.0, 1.0 - kurt_diff / max_kurt_diff)
                        matches.append(kurt_match)
                except:
                    matches.append(0.0)
        
        return np.mean(matches) if matches else 0.0
    
    def _check_similarity_score_stability(self, sim_similarity: pd.Series, hist_similarity: pd.Series) -> float:
        """Check regime similarity score stability"""
        if sim_similarity.empty or hist_similarity.empty:
            return 0.0
        
        # Compare statistical properties of similarity scores
        sim_mean = sim_similarity.mean()
        hist_mean = hist_similarity.mean()
        sim_std = sim_similarity.std()
        hist_std = hist_similarity.std()
        
        if np.isnan(sim_mean) or np.isnan(hist_mean) or np.isnan(sim_std) or np.isnan(hist_std):
            return 0.0
        
        # Compare means
        mean_diff = abs(sim_mean - hist_mean)
        mean_match = max(0.0, 1.0 - mean_diff / max(hist_mean, 0.01))
        
        # Compare standard deviations
        std_diff = abs(sim_std - hist_std)
        std_match = max(0.0, 1.0 - std_diff / max(hist_std, 0.01))
        
        return np.mean([mean_match, std_match])
    
    def _check_similarity_ranking_stability(self, sim_data: pd.DataFrame, hist_data: pd.DataFrame) -> float:
        """Check similarity ranking stability"""
        # This is a simplified implementation
        # In practice, would compare rankings of similar periods
        
        sim_similarity = sim_data.get('regime_similarity_score', pd.Series())
        hist_similarity = hist_data.get('regime_similarity_score', pd.Series())
        
        if sim_similarity.empty or hist_similarity.empty:
            return 0.0
        
        # Compare ranking correlation (simplified)
        try:
            # Use Spearman correlation as proxy for ranking stability
            if len(sim_similarity) == len(hist_similarity):
                ranking_corr = stats.spearmanr(sim_similarity, hist_similarity)[0]
                return max(0.0, ranking_corr) if not np.isnan(ranking_corr) else 0.0
            else:
                # Compare quantile rankings
                sim_ranks = sim_similarity.rank(pct=True)
                hist_ranks = hist_similarity.rank(pct=True)
                
                # Compare distribution of ranks
                ks_stat, p_value = stats.ks_2samp(sim_ranks, hist_ranks)
                return 1.0 - ks_stat if p_value > self.significance_level else 0.5
        except:
            return 0.0
    
    def _check_similarity_threshold_stability(self, sim_similarity: pd.Series, hist_similarity: pd.Series) -> float:
        """Check similarity threshold stability"""
        if sim_similarity.empty or hist_similarity.empty:
            return 0.0
        
        # Check stability at different threshold levels
        thresholds = [0.3, 0.5, 0.7, 0.8, 0.9]
        threshold_matches = []
        
        for threshold in thresholds:
            sim_above = (sim_similarity > threshold).mean()
            hist_above = (hist_similarity > threshold).mean()
            
            if hist_above > 0:
                threshold_match = 1.0 - abs(sim_above - hist_above) / hist_above
                threshold_matches.append(max(0.0, threshold_match))
        
        return np.mean(threshold_matches) if threshold_matches else 0.0
    
    def _check_similarity_calculation_robustness(self, sim_similarity: pd.Series, hist_similarity: pd.Series) -> float:
        """Check similarity calculation robustness"""
        if sim_similarity.empty or hist_similarity.empty:
            return 0.0
        
        # Check for outliers and stability
        sim_outliers = self._detect_outliers(sim_similarity)
        hist_outliers = self._detect_outliers(hist_similarity)
        
        # Compare outlier rates
        sim_outlier_rate = sim_outliers.mean()
        hist_outlier_rate = hist_outliers.mean()
        
        outlier_match = 1.0 - abs(sim_outlier_rate - hist_outlier_rate)
        
        # Check for NaN/infinite values
        sim_invalid = sim_similarity.isna().mean()
        hist_invalid = hist_similarity.isna().mean()
        
        invalid_match = 1.0 - abs(sim_invalid - hist_invalid)
        
        return np.mean([outlier_match, invalid_match])
    
    def _detect_outliers(self, series: pd.Series) -> pd.Series:
        """Detect outliers using IQR method"""
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        return (series < lower_bound) | (series > upper_bound)
    
    def _calculate_overall_statistical_consistency(
        self,
        correlation_result: CorrelationConsistencyResult,
        volatility_result: VolatilityConsistencyResult,
        distribution_result: DistributionConsistencyResult,
        similarity_result: RegimeSimilarityStabilityResult
    ) -> float:
        """Calculate overall statistical consistency score"""
        
        # Weight components based on importance
        weights = {
            'correlation': 0.25,
            'volatility': 0.30,
            'distribution': 0.25,
            'similarity': 0.20
        }
        
        weighted_score = (
            weights['correlation'] * correlation_result.overall_correlation_consistency +
            weights['volatility'] * volatility_result.overall_volatility_consistency +
            weights['distribution'] * distribution_result.overall_distribution_consistency +
            weights['similarity'] * similarity_result.overall_similarity_stability
        )
        
        return weighted_score
    
    def _identify_critical_violations(
        self,
        correlation_result: CorrelationConsistencyResult,
        volatility_result: VolatilityConsistencyResult,
        distribution_result: DistributionConsistencyResult,
        similarity_result: RegimeSimilarityStabilityResult
    ) -> List[str]:
        """Identify critical statistical violations"""
        
        critical_violations = []
        
        # Check for critical correlation violations
        if correlation_result.overall_correlation_consistency < 0.60:
            critical_violations.append(f"Critical correlation consistency failure: {correlation_result.overall_correlation_consistency:.3f}")
            critical_violations.extend(correlation_result.violations)
        
        # Check for critical volatility violations
        if volatility_result.overall_volatility_consistency < 0.60:
            critical_violations.append(f"Critical volatility consistency failure: {volatility_result.overall_volatility_consistency:.3f}")
            critical_violations.extend(volatility_result.violations)
        
        # Check for critical distribution violations
        if distribution_result.overall_distribution_consistency < 0.60:
            critical_violations.append(f"Critical distribution consistency failure: {distribution_result.overall_distribution_consistency:.3f}")
            critical_violations.extend(distribution_result.violations)
        
        # Check for critical similarity violations
        if similarity_result.overall_similarity_stability < 0.60:
            critical_violations.append(f"Critical similarity stability failure: {similarity_result.overall_similarity_stability:.3f}")
            critical_violations.extend(similarity_result.violations)
        
        return critical_violations
    
    def _generate_statistical_recommendations(
        self,
        correlation_result: CorrelationConsistencyResult,
        volatility_result: VolatilityConsistencyResult,
        distribution_result: DistributionConsistencyResult,
        similarity_result: RegimeSimilarityStabilityResult
    ) -> List[str]:
        """Generate recommendations for improving statistical consistency"""
        
        recommendations = []
        
        # Correlation recommendations
        if correlation_result.correlation_stability < 0.80:
            recommendations.append("Review correlation model parameters to improve stability")
        
        if correlation_result.correlation_range_compliance < 0.80:
            recommendations.append("Implement correlation bounds checking to prevent unrealistic values")
        
        if correlation_result.eigenvalue_stability < 0.75:
            recommendations.append("Investigate correlation matrix conditioning and eigenvalue stability")
        
        # Volatility recommendations
        if volatility_result.volatility_distribution_match < 0.75:
            recommendations.append("Calibrate volatility model to match historical distributions")
        
        if volatility_result.volatility_clustering_preservation < 0.70:
            recommendations.append("Implement GARCH-like volatility clustering in simulation")
        
        if volatility_result.volatility_regime_relationship < 0.70:
            recommendations.append("Review volatility-regime relationship modeling")
        
        # Distribution recommendations
        if distribution_result.normality_test_consistency < 0.70:
            recommendations.append("Review distributional assumptions in simulation models")
        
        if distribution_result.tail_behavior_consistency < 0.70:
            recommendations.append("Implement proper tail behavior modeling for extreme events")
        
        # Similarity recommendations
        if similarity_result.similarity_score_stability < 0.80:
            recommendations.append("Stabilize regime similarity calculation parameters")
        
        if similarity_result.similarity_ranking_stability < 0.75:
            recommendations.append("Review regime similarity ranking methodology")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Statistical consistency is acceptable - continue monitoring")
        
        return recommendations