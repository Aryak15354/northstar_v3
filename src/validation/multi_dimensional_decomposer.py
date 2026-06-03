"""
Multi-Dimensional Decomposer

Decomposes performance across multiple dimensions simultaneously:
- Regime × Component × Timeline attribution
- Calculates interaction effects and unexplained alpha
- Provides statistical significance testing for attribution
- Handles complex multi-factor attribution models

This decomposer enables institutional-grade performance analysis
by breaking down returns across all relevant dimensions.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
import logging
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from itertools import combinations
import warnings
warnings.filterwarnings('ignore')

from src.validation.regime_based_attribution_engine import RegimeBasedAttributionEngine
from src.validation.phase3_component_attribution import Phase3ComponentAttribution
from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class DimensionDefinition:
    """Definition of a dimension for multi-dimensional attribution"""
    dimension_name: str
    dimension_type: str  # 'categorical', 'continuous', 'binary'
    dimension_values: List[str]  # For categorical dimensions
    dimension_data: pd.Series

@dataclass
class MultiDimensionalFactor:
    """A factor in multi-dimensional attribution"""
    factor_name: str
    factor_dimensions: List[str]  # Which dimensions this factor spans
    factor_coefficient: float
    factor_contribution: float
    factor_significance: float
    factor_confidence_interval: Tuple[float, float]

@dataclass
class InteractionTerm:
    """Interaction term between multiple dimensions"""
    interaction_name: str
    interacting_dimensions: List[str]
    interaction_coefficient: float
    interaction_contribution: float
    interaction_significance: float
    interaction_description: str

@dataclass
class MultiDimensionalDecompositionResult:
    """Complete multi-dimensional decomposition result"""
    decomposition_period: Tuple[datetime, datetime]
    total_return: float
    benchmark_return: Optional[float]
    dimensions: Dict[str, DimensionDefinition]
    main_effects: Dict[str, MultiDimensionalFactor]
    interaction_effects: List[InteractionTerm]
    model_r_squared: float
    model_adjusted_r_squared: float
    unexplained_alpha: float
    statistical_significance: Dict[str, float]
    dimension_importance: Dict[str, float]  # Relative importance of each dimension

class MultiDimensionalDecomposer:
    """
    Multi-Dimensional Performance Decomposer
    
    Decomposes performance across multiple dimensions simultaneously,
    handling complex interactions and providing statistical significance testing.
    """
    
    def __init__(self):
        self.name = "Multi-Dimensional Decomposer"
        self.version = "1.0"
        
        # Initialize sub-engines
        self.regime_attribution_engine = RegimeBasedAttributionEngine()
        self.component_attribution_engine = Phase3ComponentAttribution()
        
        # Decomposition parameters
        self.min_decomposition_periods = 20  # Minimum periods for decomposition
        self.significance_level = 0.05  # For statistical significance testing
        self.max_interaction_order = 2  # Maximum order of interactions to consider
        self.regularization_alpha = 0.01  # For regularized regression
        
        logger.info(f"🔀 {self.name} v{self.version} initialized")
        logger.info(f"💡 Max interaction order: {self.max_interaction_order}")
    
    def decompose_performance_multi_dimensional(
        self,
        portfolio_returns: pd.Series,
        dimensions: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series] = None,
        timeline_dimension: Optional[str] = None
    ) -> MultiDimensionalDecompositionResult:
        """
        Decompose performance across multiple dimensions simultaneously
        
        Args:
            portfolio_returns: Portfolio returns time series
            dimensions: Dictionary of dimension data (regime, component signals, etc.)
            benchmark_returns: Optional benchmark returns
            timeline_dimension: Optional timeline dimension name
            
        Returns:
            Complete multi-dimensional decomposition result
        """
        logger.info(f"🔀 {self.name} - Multi-Dimensional Performance Decomposition")
        logger.info(f"📊 Portfolio periods: {len(portfolio_returns)}")
        logger.info(f"🎯 Dimensions: {list(dimensions.keys())}")
        
        # Prepare dimensions
        dimension_definitions = self._prepare_dimensions(dimensions, portfolio_returns.index)
        
        # Align all data
        aligned_data = self._align_multi_dimensional_data(
            portfolio_returns, dimension_definitions, benchmark_returns
        )
        
        # Build feature matrix
        feature_matrix, feature_names = self._build_feature_matrix(
            aligned_data['dimensions']
        )
        
        # Calculate main effects
        main_effects = self._calculate_main_effects(
            aligned_data['returns'], feature_matrix, feature_names, dimension_definitions
        )
        
        # Calculate interaction effects
        interaction_effects = self._calculate_interaction_effects(
            aligned_data['returns'], feature_matrix, feature_names, dimension_definitions
        )
        
        # Fit complete model
        model_results = self._fit_complete_model(
            aligned_data['returns'], feature_matrix, feature_names
        )
        
        # Calculate dimension importance
        dimension_importance = self._calculate_dimension_importance(
            main_effects, interaction_effects, dimension_definitions
        )
        
        # Calculate statistical significance
        statistical_significance = self._calculate_statistical_significance(
            aligned_data['returns'], feature_matrix, feature_names
        )
        
        # Calculate unexplained alpha
        total_explained = sum(effect.factor_contribution for effect in main_effects.values())
        total_explained += sum(effect.interaction_contribution for effect in interaction_effects)
        
        total_return = aligned_data['returns'].sum()
        benchmark_return = aligned_data.get('benchmark', pd.Series([0])).sum()
        unexplained_alpha = total_return - benchmark_return - total_explained
        
        decomposition_result = MultiDimensionalDecompositionResult(
            decomposition_period=(aligned_data['returns'].index[0], aligned_data['returns'].index[-1]),
            total_return=total_return,
            benchmark_return=benchmark_return if benchmark_returns is not None else None,
            dimensions=dimension_definitions,
            main_effects=main_effects,
            interaction_effects=interaction_effects,
            model_r_squared=model_results['r_squared'],
            model_adjusted_r_squared=model_results['adjusted_r_squared'],
            unexplained_alpha=unexplained_alpha,
            statistical_significance=statistical_significance,
            dimension_importance=dimension_importance
        )
        
        logger.info(f"✅ Multi-dimensional decomposition completed")
        logger.info(f"📈 Total return: {total_return:.3f}")
        logger.info(f"📊 Model R²: {model_results['r_squared']:.3f}")
        logger.info(f"🎯 Main effects: {len(main_effects)}")
        logger.info(f"🔗 Interaction effects: {len(interaction_effects)}")
        logger.info(f"❓ Unexplained alpha: {unexplained_alpha:.3f}")
        
        return decomposition_result
    
    def _prepare_dimensions(
        self,
        dimensions: Dict[str, pd.Series],
        index: pd.Index
    ) -> Dict[str, DimensionDefinition]:
        """Prepare dimension definitions from raw dimension data"""
        
        dimension_definitions = {}
        
        for dim_name, dim_data in dimensions.items():
            # Align dimension data to returns index
            aligned_dim_data = dim_data.reindex(index, method='ffill')
            
            # Determine dimension type
            if aligned_dim_data.dtype == 'bool':
                dim_type = 'binary'
                dim_values = ['False', 'True']
            elif pd.api.types.is_numeric_dtype(aligned_dim_data):
                dim_type = 'continuous'
                dim_values = []
            else:
                dim_type = 'categorical'
                dim_values = aligned_dim_data.dropna().unique().tolist()
            
            dimension_definitions[dim_name] = DimensionDefinition(
                dimension_name=dim_name,
                dimension_type=dim_type,
                dimension_values=dim_values,
                dimension_data=aligned_dim_data
            )
        
        return dimension_definitions
    
    def _align_multi_dimensional_data(
        self,
        portfolio_returns: pd.Series,
        dimension_definitions: Dict[str, DimensionDefinition],
        benchmark_returns: Optional[pd.Series]
    ) -> Dict[str, Any]:
        """Align all multi-dimensional data"""
        
        aligned_data = {'returns': portfolio_returns.copy()}
        
        # Align dimensions
        aligned_dimensions = {}
        for dim_name, dim_def in dimension_definitions.items():
            aligned_dimensions[dim_name] = dim_def.dimension_data
        
        aligned_data['dimensions'] = aligned_dimensions
        
        # Align benchmark if provided
        if benchmark_returns is not None:
            aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index, method='ffill')
            aligned_data['benchmark'] = aligned_benchmark.fillna(0)
        
        # Remove periods with missing dimension data
        valid_mask = pd.Series(True, index=portfolio_returns.index)
        for dim_name, dim_data in aligned_dimensions.items():
            valid_mask &= dim_data.notna()
        
        # Apply valid mask
        for key in aligned_data:
            if key == 'dimensions':
                for dim_name in aligned_data[key]:
                    aligned_data[key][dim_name] = aligned_data[key][dim_name][valid_mask]
            else:
                aligned_data[key] = aligned_data[key][valid_mask]
        
        return aligned_data
    
    def _build_feature_matrix(
        self,
        dimensions: Dict[str, pd.Series]
    ) -> Tuple[pd.DataFrame, List[str]]:
        """Build feature matrix from dimensions"""
        
        features = []
        feature_names = []
        
        for dim_name, dim_data in dimensions.items():
            if dim_data.dtype == 'bool':
                # Binary dimension
                features.append(dim_data.astype(float))
                feature_names.append(f"{dim_name}_binary")
                
            elif pd.api.types.is_numeric_dtype(dim_data):
                # Continuous dimension - normalize
                normalized_data = (dim_data - dim_data.mean()) / dim_data.std()
                features.append(normalized_data.fillna(0))
                feature_names.append(f"{dim_name}_continuous")
                
            else:
                # Categorical dimension - one-hot encode
                encoded_data = pd.get_dummies(dim_data, prefix=dim_name)
                for col in encoded_data.columns:
                    features.append(encoded_data[col])
                    feature_names.append(col)
        
        if not features:
            raise ValueError("No valid features created from dimensions")
        
        feature_matrix = pd.concat(features, axis=1)
        feature_matrix.columns = feature_names
        
        return feature_matrix, feature_names
    
    def _calculate_main_effects(
        self,
        returns: pd.Series,
        feature_matrix: pd.DataFrame,
        feature_names: List[str],
        dimension_definitions: Dict[str, DimensionDefinition]
    ) -> Dict[str, MultiDimensionalFactor]:
        """Calculate main effects for each dimension"""
        
        main_effects = {}
        
        # Group features by dimension
        dimension_features = {}
        for feature_name in feature_names:
            for dim_name in dimension_definitions.keys():
                if feature_name.startswith(dim_name):
                    if dim_name not in dimension_features:
                        dimension_features[dim_name] = []
                    dimension_features[dim_name].append(feature_name)
                    break
        
        # Calculate main effect for each dimension
        for dim_name, dim_features in dimension_features.items():
            try:
                # Extract features for this dimension
                X = feature_matrix[dim_features]
                y = returns
                
                if len(X) < self.min_decomposition_periods:
                    continue
                
                # Fit regression model
                model = LinearRegression()
                model.fit(X, y)
                
                # Calculate contribution
                predicted_returns = model.predict(X)
                contribution = predicted_returns.sum()
                
                # Calculate average coefficient (for multi-feature dimensions)
                avg_coefficient = np.mean(model.coef_)
                
                # Simple significance test (t-statistic approximation)
                residuals = y - predicted_returns
                mse = np.mean(residuals ** 2)
                se = np.sqrt(mse / len(X))
                t_stat = abs(avg_coefficient) / (se + 1e-8)
                significance = 1 - stats.t.cdf(t_stat, len(X) - len(dim_features) - 1)
                
                # Confidence interval (simplified)
                margin_error = 1.96 * se  # 95% CI
                confidence_interval = (avg_coefficient - margin_error, avg_coefficient + margin_error)
                
                main_effects[dim_name] = MultiDimensionalFactor(
                    factor_name=dim_name,
                    factor_dimensions=[dim_name],
                    factor_coefficient=avg_coefficient,
                    factor_contribution=contribution,
                    factor_significance=significance,
                    factor_confidence_interval=confidence_interval
                )
                
            except Exception as e:
                logger.warning(f"Error calculating main effect for {dim_name}: {str(e)}")
                continue
        
        return main_effects
    
    def _calculate_interaction_effects(
        self,
        returns: pd.Series,
        feature_matrix: pd.DataFrame,
        feature_names: List[str],
        dimension_definitions: Dict[str, DimensionDefinition]
    ) -> List[InteractionTerm]:
        """Calculate interaction effects between dimensions"""
        
        interaction_effects = []
        
        # Get dimension names
        dimension_names = list(dimension_definitions.keys())
        
        # Calculate pairwise interactions (order 2)
        for dim1, dim2 in combinations(dimension_names, 2):
            try:
                # Get features for each dimension
                dim1_features = [f for f in feature_names if f.startswith(dim1)]
                dim2_features = [f for f in feature_names if f.startswith(dim2)]
                
                if not dim1_features or not dim2_features:
                    continue
                
                # Create interaction terms (simplified - use first feature from each dimension)
                feature1 = feature_matrix[dim1_features[0]]
                feature2 = feature_matrix[dim2_features[0]]
                interaction_term = feature1 * feature2
                
                # Regression with main effects and interaction
                X = pd.DataFrame({
                    'main1': feature1,
                    'main2': feature2,
                    'interaction': interaction_term
                })
                y = returns
                
                if len(X) < self.min_decomposition_periods:
                    continue
                
                model = LinearRegression()
                model.fit(X, y)
                
                # Extract interaction coefficient and contribution
                interaction_coef = model.coef_[2]
                interaction_contribution = (interaction_term * interaction_coef).sum()
                
                # Significance test
                predicted = model.predict(X)
                residuals = y - predicted
                mse = np.mean(residuals ** 2)
                se = np.sqrt(mse / len(X))
                t_stat = abs(interaction_coef) / (se + 1e-8)
                significance = 1 - stats.t.cdf(t_stat, len(X) - 4)
                
                # Describe interaction
                if interaction_coef > 0:
                    description = f"{dim1} and {dim2} have positive synergy"
                else:
                    description = f"{dim1} and {dim2} have negative interaction"
                
                interaction_effects.append(InteractionTerm(
                    interaction_name=f"{dim1}_x_{dim2}",
                    interacting_dimensions=[dim1, dim2],
                    interaction_coefficient=interaction_coef,
                    interaction_contribution=interaction_contribution,
                    interaction_significance=significance,
                    interaction_description=description
                ))
                
            except Exception as e:
                logger.warning(f"Error calculating interaction between {dim1} and {dim2}: {str(e)}")
                continue
        
        return interaction_effects
    
    def _fit_complete_model(
        self,
        returns: pd.Series,
        feature_matrix: pd.DataFrame,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Fit complete multi-dimensional model"""
        
        try:
            X = feature_matrix
            y = returns
            
            if len(X) < self.min_decomposition_periods:
                return {'r_squared': 0.0, 'adjusted_r_squared': 0.0}
            
            # Fit model
            model = LinearRegression()
            model.fit(X, y)
            
            # Calculate R-squared
            r_squared = model.score(X, y)
            
            # Calculate adjusted R-squared
            n = len(X)
            p = X.shape[1]
            adjusted_r_squared = 1 - (1 - r_squared) * (n - 1) / (n - p - 1)
            
            return {
                'r_squared': max(0.0, r_squared),
                'adjusted_r_squared': max(0.0, adjusted_r_squared)
            }
            
        except Exception as e:
            logger.warning(f"Error fitting complete model: {str(e)}")
            return {'r_squared': 0.0, 'adjusted_r_squared': 0.0}
    
    def _calculate_dimension_importance(
        self,
        main_effects: Dict[str, MultiDimensionalFactor],
        interaction_effects: List[InteractionTerm],
        dimension_definitions: Dict[str, DimensionDefinition]
    ) -> Dict[str, float]:
        """Calculate relative importance of each dimension"""
        
        dimension_importance = {}
        
        # Calculate total contribution
        total_contribution = 0.0
        
        # Add main effects
        for effect in main_effects.values():
            total_contribution += abs(effect.factor_contribution)
        
        # Add interaction effects
        for interaction in interaction_effects:
            total_contribution += abs(interaction.interaction_contribution)
        
        if total_contribution == 0:
            return {dim_name: 0.0 for dim_name in dimension_definitions.keys()}
        
        # Calculate importance for each dimension
        for dim_name in dimension_definitions.keys():
            importance = 0.0
            
            # Add main effect contribution
            if dim_name in main_effects:
                importance += abs(main_effects[dim_name].factor_contribution)
            
            # Add interaction effect contributions
            for interaction in interaction_effects:
                if dim_name in interaction.interacting_dimensions:
                    # Split interaction contribution among participating dimensions
                    importance += abs(interaction.interaction_contribution) / len(interaction.interacting_dimensions)
            
            # Normalize to percentage
            dimension_importance[dim_name] = importance / total_contribution
        
        return dimension_importance
    
    def _calculate_statistical_significance(
        self,
        returns: pd.Series,
        feature_matrix: pd.DataFrame,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Calculate statistical significance for each feature"""
        
        statistical_significance = {}
        
        try:
            X = feature_matrix
            y = returns
            
            if len(X) < self.min_decomposition_periods:
                return {name: 1.0 for name in feature_names}  # Not significant
            
            # Fit model
            model = LinearRegression()
            model.fit(X, y)
            
            # Calculate significance for each feature
            predicted = model.predict(X)
            residuals = y - predicted
            mse = np.mean(residuals ** 2)
            
            for i, feature_name in enumerate(feature_names):
                try:
                    coef = model.coef_[i]
                    se = np.sqrt(mse / len(X))  # Simplified standard error
                    t_stat = abs(coef) / (se + 1e-8)
                    p_value = 2 * (1 - stats.t.cdf(t_stat, len(X) - len(feature_names) - 1))
                    statistical_significance[feature_name] = p_value
                except:
                    statistical_significance[feature_name] = 1.0
            
        except Exception as e:
            logger.warning(f"Error calculating statistical significance: {str(e)}")
            statistical_significance = {name: 1.0 for name in feature_names}
        
        return statistical_significance
    
    def generate_multi_dimensional_report(
        self,
        decomposition_result: MultiDimensionalDecompositionResult,
        output_path: Optional[str] = None
    ) -> str:
        """Generate detailed multi-dimensional decomposition report"""
        
        report_lines = []
        
        # Header
        report_lines.append("MULTI-DIMENSIONAL PERFORMANCE DECOMPOSITION REPORT")
        report_lines.append("=" * 70)
        report_lines.append(f"Decomposition Period: {decomposition_result.decomposition_period[0].strftime('%Y-%m-%d')} to {decomposition_result.decomposition_period[1].strftime('%Y-%m-%d')}")
        report_lines.append(f"Total Return: {decomposition_result.total_return:.3f}")
        if decomposition_result.benchmark_return is not None:
            report_lines.append(f"Benchmark Return: {decomposition_result.benchmark_return:.3f}")
        report_lines.append(f"Model R²: {decomposition_result.model_r_squared:.3f}")
        report_lines.append(f"Adjusted R²: {decomposition_result.model_adjusted_r_squared:.3f}")
        report_lines.append("")
        
        # Dimensions
        report_lines.append("DIMENSIONS ANALYZED")
        report_lines.append("-" * 40)
        for dim_name, dim_def in decomposition_result.dimensions.items():
            report_lines.append(f"{dim_name}: {dim_def.dimension_type}")
            if dim_def.dimension_values:
                report_lines.append(f"  Values: {', '.join(map(str, dim_def.dimension_values[:5]))}")
        report_lines.append("")
        
        # Main Effects
        report_lines.append("MAIN EFFECTS")
        report_lines.append("-" * 40)
        for factor_name, factor in decomposition_result.main_effects.items():
            report_lines.append(f"Factor: {factor_name}")
            report_lines.append(f"  Contribution: {factor.factor_contribution:.3f}")
            report_lines.append(f"  Coefficient: {factor.factor_coefficient:.3f}")
            report_lines.append(f"  Significance: {factor.factor_significance:.3f}")
            report_lines.append("")
        
        # Interaction Effects
        if decomposition_result.interaction_effects:
            report_lines.append("INTERACTION EFFECTS")
            report_lines.append("-" * 40)
            for interaction in decomposition_result.interaction_effects:
                report_lines.append(f"Interaction: {interaction.interaction_name}")
                report_lines.append(f"  Dimensions: {' × '.join(interaction.interacting_dimensions)}")
                report_lines.append(f"  Contribution: {interaction.interaction_contribution:.3f}")
                report_lines.append(f"  Significance: {interaction.interaction_significance:.3f}")
                report_lines.append(f"  Description: {interaction.interaction_description}")
                report_lines.append("")
        
        # Dimension Importance
        report_lines.append("DIMENSION IMPORTANCE")
        report_lines.append("-" * 40)
        sorted_importance = sorted(
            decomposition_result.dimension_importance.items(),
            key=lambda x: x[1], reverse=True
        )
        for dim_name, importance in sorted_importance:
            report_lines.append(f"{dim_name}: {importance:.1%}")
        report_lines.append("")
        
        # Summary
        report_lines.append("DECOMPOSITION SUMMARY")
        report_lines.append("-" * 40)
        total_main_effects = sum(
            abs(effect.factor_contribution) for effect in decomposition_result.main_effects.values()
        )
        total_interactions = sum(
            abs(effect.interaction_contribution) for effect in decomposition_result.interaction_effects
        )
        
        report_lines.append(f"Total Main Effects: {total_main_effects:.3f}")
        report_lines.append(f"Total Interaction Effects: {total_interactions:.3f}")
        report_lines.append(f"Unexplained Alpha: {decomposition_result.unexplained_alpha:.3f}")
        report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        # Save report if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_content)
            logger.info(f"📄 Multi-dimensional decomposition report saved to {output_path}")
        
        return report_content