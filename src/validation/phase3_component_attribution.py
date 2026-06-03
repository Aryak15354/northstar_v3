"""
Phase 3 Component Attribution Engine

Attributes performance to specific Phase 3 components:
- Regime Memory System contribution
- Simple Tailwind Engine contribution  
- NO_EDGE Detector contribution
- Anticipatory Capital Allocator contribution

Measures interaction effects between components and tracks
component-specific alpha generation over time.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import logging
from scipy import stats
from sklearn.linear_model import LinearRegression

from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector
from src.intelligence.anticipatory_capital_allocator import AnticipatoryCapitalAllocator
from src.utils.data_standards import validate_schema, standardize_dataframe

logger = logging.getLogger(__name__)

@dataclass
class ComponentContribution:
    """Performance contribution from a specific Phase 3 component"""
    component_name: str
    total_contribution: float
    annualized_contribution: float
    contribution_volatility: float
    contribution_sharpe: float
    positive_contribution_periods: int
    negative_contribution_periods: int
    average_positive_contribution: float
    average_negative_contribution: float
    contribution_consistency: float  # Consistency of contribution over time

@dataclass
class ComponentInteractionEffect:
    """Interaction effect between Phase 3 components"""
    component_1: str
    component_2: str
    interaction_strength: float
    interaction_contribution: float
    interaction_significance: float  # Statistical significance
    interaction_description: str

@dataclass
class Phase3ComponentAttributionResult:
    """Complete Phase 3 component attribution result"""
    attribution_period: Tuple[datetime, datetime]
    total_portfolio_return: float
    benchmark_return: Optional[float]
    component_contributions: Dict[str, ComponentContribution]
    interaction_effects: List[ComponentInteractionEffect]
    unexplained_alpha: float
    component_timing_alpha: float  # Alpha from component timing
    attribution_r_squared: float  # How much of returns explained by components
    component_correlation_matrix: pd.DataFrame

class Phase3ComponentAttribution:
    """
    Phase 3 Component Attribution Engine
    
    Decomposes portfolio performance by individual Phase 3 components,
    measuring each component's contribution to overall performance.
    """
    
    def __init__(self):
        self.name = "Phase 3 Component Attribution Engine"
        self.version = "1.0"
        
        # Component names for attribution
        self.component_names = [
            'regime_memory_system',
            'simple_tailwind_engine', 
            'no_edge_detector',
            'anticipatory_capital_allocator'
        ]
        
        # Attribution parameters
        self.min_attribution_periods = 10  # Minimum periods for attribution
        self.significance_level = 0.05  # For statistical significance testing
        self.rolling_window_days = 30  # Rolling window for component analysis
        
        logger.info(f"🧩 {self.name} v{self.version} initialized")
        logger.info(f"💡 Components: {', '.join(self.component_names)}")
    
    def calculate_phase3_component_attribution(
        self,
        portfolio_returns: pd.Series,
        phase3_signals: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series] = None
    ) -> Phase3ComponentAttributionResult:
        """
        Attribute performance to Phase 3 components
        
        Args:
            portfolio_returns: Portfolio returns time series
            phase3_signals: Dictionary of Phase 3 component signals
            benchmark_returns: Optional benchmark returns for comparison
            
        Returns:
            Complete Phase 3 component attribution analysis
        """
        logger.info(f"🧩 {self.name} - Calculating Phase 3 Component Attribution")
        logger.info(f"📊 Portfolio periods: {len(portfolio_returns)}")
        logger.info(f"🧠 Available signals: {list(phase3_signals.keys())}")
        
        # Align data
        aligned_data = self._align_component_data(
            portfolio_returns, phase3_signals, benchmark_returns
        )
        
        # Calculate component contributions
        component_contributions = self._calculate_component_contributions(
            aligned_data['returns'], aligned_data['signals']
        )
        
        # Calculate interaction effects
        interaction_effects = self._calculate_interaction_effects(
            aligned_data['returns'], aligned_data['signals']
        )
        
        # Calculate component timing alpha
        component_timing_alpha = self._calculate_component_timing_alpha(
            aligned_data['returns'], aligned_data['signals']
        )
        
        # Calculate attribution R-squared
        attribution_r_squared = self._calculate_attribution_r_squared(
            aligned_data['returns'], aligned_data['signals']
        )
        
        # Calculate component correlation matrix
        component_correlation_matrix = self._calculate_component_correlations(
            aligned_data['signals']
        )
        
        # Calculate unexplained alpha
        total_component_contribution = sum(
            contrib.total_contribution for contrib in component_contributions.values()
        )
        total_interaction_contribution = sum(
            effect.interaction_contribution for effect in interaction_effects
        )
        
        total_return = aligned_data['returns'].sum()
        benchmark_return = aligned_data.get('benchmark', pd.Series([0])).sum()
        
        unexplained_alpha = (
            total_return - benchmark_return - 
            total_component_contribution - total_interaction_contribution
        )
        
        attribution_result = Phase3ComponentAttributionResult(
            attribution_period=(aligned_data['returns'].index[0], aligned_data['returns'].index[-1]),
            total_portfolio_return=total_return,
            benchmark_return=benchmark_return if benchmark_returns is not None else None,
            component_contributions=component_contributions,
            interaction_effects=interaction_effects,
            unexplained_alpha=unexplained_alpha,
            component_timing_alpha=component_timing_alpha,
            attribution_r_squared=attribution_r_squared,
            component_correlation_matrix=component_correlation_matrix
        )
        
        logger.info(f"✅ Phase 3 component attribution completed")
        logger.info(f"📈 Total return: {total_return:.3f}")
        logger.info(f"🧩 Component contributions: {total_component_contribution:.3f}")
        logger.info(f"🔗 Interaction effects: {total_interaction_contribution:.3f}")
        logger.info(f"❓ Unexplained alpha: {unexplained_alpha:.3f}")
        logger.info(f"📊 Attribution R²: {attribution_r_squared:.3f}")
        
        return attribution_result
    
    def _align_component_data(
        self,
        portfolio_returns: pd.Series,
        phase3_signals: Dict[str, pd.Series],
        benchmark_returns: Optional[pd.Series]
    ) -> Dict[str, Any]:
        """Align portfolio returns with Phase 3 component signals"""
        
        # Start with portfolio returns as base
        aligned_data = {'returns': portfolio_returns.copy()}
        
        # Align Phase 3 signals
        aligned_signals = {}
        for signal_name, signal_data in phase3_signals.items():
            aligned_signal = signal_data.reindex(portfolio_returns.index, method='ffill')
            aligned_signals[signal_name] = aligned_signal
        
        aligned_data['signals'] = aligned_signals
        
        # Align benchmark if provided
        if benchmark_returns is not None:
            aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index, method='ffill')
            aligned_data['benchmark'] = aligned_benchmark.fillna(0)
        
        # Remove periods with insufficient signal data
        valid_mask = pd.Series(True, index=portfolio_returns.index)
        for signal_name, signal_data in aligned_signals.items():
            valid_mask &= signal_data.notna()
        
        # Apply valid mask to all data
        for key in aligned_data:
            if key == 'signals':
                for signal_name in aligned_data[key]:
                    aligned_data[key][signal_name] = aligned_data[key][signal_name][valid_mask]
            else:
                aligned_data[key] = aligned_data[key][valid_mask]
        
        return aligned_data
    
    def _calculate_component_contributions(
        self,
        returns: pd.Series,
        signals: Dict[str, pd.Series]
    ) -> Dict[str, ComponentContribution]:
        """Calculate contribution of each Phase 3 component"""
        
        component_contributions = {}
        
        for component_name in self.component_names:
            # Find relevant signals for this component
            component_signals = self._get_component_signals(component_name, signals)
            
            if not component_signals:
                logger.warning(f"No signals found for component {component_name}")
                continue
            
            # Calculate component contribution using regression analysis
            contribution = self._calculate_single_component_contribution(
                returns, component_signals, component_name
            )
            
            component_contributions[component_name] = contribution
        
        return component_contributions
    
    def _get_component_signals(
        self,
        component_name: str,
        signals: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """Get signals relevant to a specific component"""
        
        component_signal_mapping = {
            'regime_memory_system': [
                'regime_classification', 'regime_similarity_score', 
                'regime_confidence', 'regime_transition_signal'
            ],
            'simple_tailwind_engine': [
                'tailwind_scores', 'tailwind_momentum', 
                'tailwind_strength', 'strategy_tailwinds'
            ],
            'no_edge_detector': [
                'no_edge_state', 'no_edge_confidence', 
                'edge_strength', 'risk_reduction_signal'
            ],
            'anticipatory_capital_allocator': [
                'anticipatory_allocation', 'allocation_confidence',
                'position_changes', 'anticipatory_signals'
            ]
        }
        
        relevant_signal_names = component_signal_mapping.get(component_name, [])
        component_signals = {}
        
        for signal_name in relevant_signal_names:
            if signal_name in signals:
                component_signals[signal_name] = signals[signal_name]
        
        # If no exact matches, try partial matches
        if not component_signals:
            for signal_name, signal_data in signals.items():
                if any(keyword in signal_name.lower() for keyword in component_name.split('_')):
                    component_signals[signal_name] = signal_data
        
        return component_signals
    
    def _calculate_single_component_contribution(
        self,
        returns: pd.Series,
        component_signals: Dict[str, pd.Series],
        component_name: str
    ) -> ComponentContribution:
        """Calculate contribution of a single component using regression"""
        
        if len(component_signals) == 0:
            # Return zero contribution if no signals
            return ComponentContribution(
                component_name=component_name,
                total_contribution=0.0,
                annualized_contribution=0.0,
                contribution_volatility=0.0,
                contribution_sharpe=0.0,
                positive_contribution_periods=0,
                negative_contribution_periods=0,
                average_positive_contribution=0.0,
                average_negative_contribution=0.0,
                contribution_consistency=0.0
            )
        
        try:
            # Prepare regression data
            X_data = []
            for signal_name, signal_data in component_signals.items():
                # Handle different signal types
                if signal_data.dtype == 'bool':
                    X_data.append(signal_data.astype(float))
                elif pd.api.types.is_numeric_dtype(signal_data):
                    # Normalize numeric signals
                    normalized_signal = (signal_data - signal_data.mean()) / signal_data.std()
                    X_data.append(normalized_signal.fillna(0))
                else:
                    # Handle categorical signals (like regime classifications)
                    encoded_signal = pd.get_dummies(signal_data, prefix=signal_name)
                    for col in encoded_signal.columns:
                        X_data.append(encoded_signal[col])
            
            if not X_data:
                raise ValueError("No valid signals for regression")
            
            X = pd.concat(X_data, axis=1).fillna(0)
            y = returns
            
            # Ensure we have enough data
            if len(X) < self.min_attribution_periods:
                raise ValueError(f"Insufficient data: {len(X)} < {self.min_attribution_periods}")
            
            # Fit regression model
            model = LinearRegression()
            model.fit(X, y)
            
            # Calculate predicted contributions
            predicted_returns = model.predict(X)
            contribution_series = pd.Series(predicted_returns, index=returns.index)
            
            # Calculate contribution metrics
            total_contribution = contribution_series.sum()
            annualized_contribution = (1 + contribution_series.mean()) ** 252 - 1
            contribution_volatility = contribution_series.std() * np.sqrt(252)
            contribution_sharpe = (
                annualized_contribution / contribution_volatility 
                if contribution_volatility > 0 else 0
            )
            
            # Positive/negative contribution analysis
            positive_contributions = contribution_series[contribution_series > 0]
            negative_contributions = contribution_series[contribution_series < 0]
            
            positive_periods = len(positive_contributions)
            negative_periods = len(negative_contributions)
            avg_positive = positive_contributions.mean() if positive_periods > 0 else 0
            avg_negative = negative_contributions.mean() if negative_periods > 0 else 0
            
            # Contribution consistency (inverse of coefficient of variation)
            contribution_consistency = (
                1 / (contribution_series.std() / abs(contribution_series.mean()))
                if contribution_series.mean() != 0 and contribution_series.std() > 0
                else 0
            )
            
            return ComponentContribution(
                component_name=component_name,
                total_contribution=total_contribution,
                annualized_contribution=annualized_contribution,
                contribution_volatility=contribution_volatility,
                contribution_sharpe=contribution_sharpe,
                positive_contribution_periods=positive_periods,
                negative_contribution_periods=negative_periods,
                average_positive_contribution=avg_positive,
                average_negative_contribution=avg_negative,
                contribution_consistency=contribution_consistency
            )
            
        except Exception as e:
            logger.warning(f"Error calculating contribution for {component_name}: {str(e)}")
            return ComponentContribution(
                component_name=component_name,
                total_contribution=0.0,
                annualized_contribution=0.0,
                contribution_volatility=0.0,
                contribution_sharpe=0.0,
                positive_contribution_periods=0,
                negative_contribution_periods=0,
                average_positive_contribution=0.0,
                average_negative_contribution=0.0,
                contribution_consistency=0.0
            )
    
    def _calculate_interaction_effects(
        self,
        returns: pd.Series,
        signals: Dict[str, pd.Series]
    ) -> List[ComponentInteractionEffect]:
        """Calculate interaction effects between Phase 3 components"""
        
        interaction_effects = []
        
        # Get component signal groups
        component_signal_groups = {}
        for component_name in self.component_names:
            component_signals = self._get_component_signals(component_name, signals)
            if component_signals:
                # Create composite signal for component
                composite_signal = self._create_composite_signal(component_signals)
                component_signal_groups[component_name] = composite_signal
        
        # Calculate pairwise interactions
        component_names = list(component_signal_groups.keys())
        for i in range(len(component_names)):
            for j in range(i + 1, len(component_names)):
                component_1 = component_names[i]
                component_2 = component_names[j]
                
                signal_1 = component_signal_groups[component_1]
                signal_2 = component_signal_groups[component_2]
                
                interaction_effect = self._calculate_pairwise_interaction(
                    returns, signal_1, signal_2, component_1, component_2
                )
                
                if interaction_effect:
                    interaction_effects.append(interaction_effect)
        
        return interaction_effects
    
    def _create_composite_signal(self, component_signals: Dict[str, pd.Series]) -> pd.Series:
        """Create composite signal from multiple component signals"""
        
        if len(component_signals) == 1:
            return list(component_signals.values())[0]
        
        # Simple approach: average of normalized signals
        normalized_signals = []
        for signal_name, signal_data in component_signals.items():
            if pd.api.types.is_numeric_dtype(signal_data):
                normalized = (signal_data - signal_data.mean()) / signal_data.std()
                normalized_signals.append(normalized.fillna(0))
            elif signal_data.dtype == 'bool':
                normalized_signals.append(signal_data.astype(float))
        
        if normalized_signals:
            composite = pd.concat(normalized_signals, axis=1).mean(axis=1)
            return composite
        else:
            # Return zeros if no valid signals
            return pd.Series(0, index=list(component_signals.values())[0].index)
    
    def _calculate_pairwise_interaction(
        self,
        returns: pd.Series,
        signal_1: pd.Series,
        signal_2: pd.Series,
        component_1: str,
        component_2: str
    ) -> Optional[ComponentInteractionEffect]:
        """Calculate interaction effect between two components"""
        
        try:
            # Create interaction term
            interaction_term = signal_1 * signal_2
            
            # Regression with main effects and interaction
            X = pd.DataFrame({
                'signal_1': signal_1,
                'signal_2': signal_2,
                'interaction': interaction_term
            }).fillna(0)
            
            y = returns
            
            if len(X) < self.min_attribution_periods:
                return None
            
            # Fit model
            model = LinearRegression()
            model.fit(X, y)
            
            # Extract interaction coefficient
            interaction_coef = model.coef_[2]  # Third coefficient is interaction
            
            # Calculate interaction contribution
            interaction_contribution = (interaction_term * interaction_coef).sum()
            
            # Calculate interaction strength (correlation between signals)
            interaction_strength = signal_1.corr(signal_2)
            
            # Statistical significance (simplified)
            interaction_significance = abs(interaction_coef) / (interaction_term.std() + 1e-8)
            
            # Describe interaction
            if interaction_coef > 0:
                description = f"{component_1} and {component_2} work synergistically"
            else:
                description = f"{component_1} and {component_2} work antagonistically"
            
            return ComponentInteractionEffect(
                component_1=component_1,
                component_2=component_2,
                interaction_strength=interaction_strength,
                interaction_contribution=interaction_contribution,
                interaction_significance=interaction_significance,
                interaction_description=description
            )
            
        except Exception as e:
            logger.warning(f"Error calculating interaction between {component_1} and {component_2}: {str(e)}")
            return None
    
    def _calculate_component_timing_alpha(
        self,
        returns: pd.Series,
        signals: Dict[str, pd.Series]
    ) -> float:
        """Calculate alpha from component timing ability"""
        
        # Simple timing alpha: correlation between signal changes and subsequent returns
        timing_alpha = 0.0
        
        try:
            for signal_name, signal_data in signals.items():
                if pd.api.types.is_numeric_dtype(signal_data):
                    # Calculate signal changes
                    signal_changes = signal_data.diff()
                    
                    # Calculate forward returns (next period)
                    forward_returns = returns.shift(-1)
                    
                    # Calculate correlation
                    correlation = signal_changes.corr(forward_returns)
                    
                    if not pd.isna(correlation):
                        timing_alpha += correlation * 0.01  # Scale down contribution
            
        except Exception as e:
            logger.warning(f"Error calculating component timing alpha: {str(e)}")
            timing_alpha = 0.0
        
        return timing_alpha
    
    def _calculate_attribution_r_squared(
        self,
        returns: pd.Series,
        signals: Dict[str, pd.Series]
    ) -> float:
        """Calculate R-squared of attribution model"""
        
        try:
            # Prepare all signals for regression
            X_data = []
            for signal_name, signal_data in signals.items():
                if pd.api.types.is_numeric_dtype(signal_data):
                    normalized_signal = (signal_data - signal_data.mean()) / signal_data.std()
                    X_data.append(normalized_signal.fillna(0))
                elif signal_data.dtype == 'bool':
                    X_data.append(signal_data.astype(float))
            
            if not X_data:
                return 0.0
            
            X = pd.concat(X_data, axis=1).fillna(0)
            y = returns
            
            if len(X) < self.min_attribution_periods:
                return 0.0
            
            # Fit model and calculate R-squared
            model = LinearRegression()
            model.fit(X, y)
            r_squared = model.score(X, y)
            
            return max(0.0, r_squared)  # Ensure non-negative
            
        except Exception as e:
            logger.warning(f"Error calculating attribution R-squared: {str(e)}")
            return 0.0
    
    def _calculate_component_correlations(
        self,
        signals: Dict[str, pd.Series]
    ) -> pd.DataFrame:
        """Calculate correlation matrix between component signals"""
        
        try:
            # Prepare numeric signals
            numeric_signals = {}
            for signal_name, signal_data in signals.items():
                if pd.api.types.is_numeric_dtype(signal_data):
                    numeric_signals[signal_name] = signal_data
                elif signal_data.dtype == 'bool':
                    numeric_signals[signal_name] = signal_data.astype(float)
            
            if not numeric_signals:
                return pd.DataFrame()
            
            # Create correlation matrix
            signal_df = pd.DataFrame(numeric_signals)
            correlation_matrix = signal_df.corr()
            
            return correlation_matrix
            
        except Exception as e:
            logger.warning(f"Error calculating component correlations: {str(e)}")
            return pd.DataFrame()
    
    def generate_component_attribution_report(
        self,
        attribution_result: Phase3ComponentAttributionResult,
        output_path: Optional[str] = None
    ) -> str:
        """Generate detailed component attribution report"""
        
        report_lines = []
        
        # Header
        report_lines.append("PHASE 3 COMPONENT ATTRIBUTION REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Attribution Period: {attribution_result.attribution_period[0].strftime('%Y-%m-%d')} to {attribution_result.attribution_period[1].strftime('%Y-%m-%d')}")
        report_lines.append(f"Total Portfolio Return: {attribution_result.total_portfolio_return:.3f}")
        if attribution_result.benchmark_return is not None:
            report_lines.append(f"Benchmark Return: {attribution_result.benchmark_return:.3f}")
        report_lines.append(f"Attribution R²: {attribution_result.attribution_r_squared:.3f}")
        report_lines.append("")
        
        # Component Contributions
        report_lines.append("COMPONENT CONTRIBUTIONS")
        report_lines.append("-" * 40)
        for component_name, contribution in attribution_result.component_contributions.items():
            report_lines.append(f"Component: {component_name}")
            report_lines.append(f"  Total Contribution: {contribution.total_contribution:.3f}")
            report_lines.append(f"  Annualized Contribution: {contribution.annualized_contribution:.3f}")
            report_lines.append(f"  Contribution Sharpe: {contribution.contribution_sharpe:.3f}")
            report_lines.append(f"  Positive Periods: {contribution.positive_contribution_periods}")
            report_lines.append(f"  Negative Periods: {contribution.negative_contribution_periods}")
            report_lines.append(f"  Consistency: {contribution.contribution_consistency:.3f}")
            report_lines.append("")
        
        # Interaction Effects
        if attribution_result.interaction_effects:
            report_lines.append("COMPONENT INTERACTION EFFECTS")
            report_lines.append("-" * 40)
            for interaction in attribution_result.interaction_effects:
                report_lines.append(f"{interaction.component_1} × {interaction.component_2}")
                report_lines.append(f"  Interaction Strength: {interaction.interaction_strength:.3f}")
                report_lines.append(f"  Interaction Contribution: {interaction.interaction_contribution:.3f}")
                report_lines.append(f"  Description: {interaction.interaction_description}")
                report_lines.append("")
        
        # Summary
        report_lines.append("ATTRIBUTION SUMMARY")
        report_lines.append("-" * 40)
        total_component_contribution = sum(
            contrib.total_contribution for contrib in attribution_result.component_contributions.values()
        )
        total_interaction_contribution = sum(
            effect.interaction_contribution for effect in attribution_result.interaction_effects
        )
        
        report_lines.append(f"Total Component Contribution: {total_component_contribution:.3f}")
        report_lines.append(f"Total Interaction Contribution: {total_interaction_contribution:.3f}")
        report_lines.append(f"Component Timing Alpha: {attribution_result.component_timing_alpha:.3f}")
        report_lines.append(f"Unexplained Alpha: {attribution_result.unexplained_alpha:.3f}")
        report_lines.append("")
        
        # Component Correlations
        if not attribution_result.component_correlation_matrix.empty:
            report_lines.append("COMPONENT SIGNAL CORRELATIONS")
            report_lines.append("-" * 40)
            report_lines.append(attribution_result.component_correlation_matrix.to_string())
            report_lines.append("")
        
        report_content = "\n".join(report_lines)
        
        # Save report if path provided
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report_content)
            logger.info(f"📄 Component attribution report saved to {output_path}")
        
        return report_content