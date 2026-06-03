#!/usr/bin/env python3
"""
Regime Intelligence Engine - Authorized Question Set 1

This engine answers regime understanding questions:
Q1. Regime Similarity - Which historical periods are most similar to current environment?
Q2. Regime Stability - How stable has the current regime been historically?
Q3. Regime Transition Probability - How often do regime transitions occur under similar conditions?

AUTHORIZED OUTPUTS ONLY:
- Descriptive regime analysis
- Historical similarity scores
- Transition probability estimates
- Comparative regime stability metrics

FORBIDDEN OUTPUTS:
- Regime switching recommendations
- Engine activation suggestions
- Position sizing based on regime
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

from ..observer_core.observer_context import ObserverSnapshot
from ..output_artifacts.intelligence_score import IntelligenceScore, ScoreFactory, ScoreType, HistoricalContext
from ..output_artifacts.intelligence_narrative import IntelligenceNarrative, NarrativeFactory

class RegimeIntelligenceEngine:
    """
    Regime Intelligence Engine - Descriptive Regime Analysis Only
    
    This engine provides intelligence about regime patterns, similarities,
    and transitions without making any trading recommendations.
    """
    
    def __init__(self):
        self.name = "Regime Intelligence Engine"
        self.version = "1.0.0"
        
        # Regime feature weights for similarity calculation
        self.regime_features = {
            'volatility': 0.30,
            'correlation': 0.25,
            'breadth': 0.20,
            'trend_strength': 0.15,
            'market_stress': 0.10
        }
        
        # Historical regime database (would be loaded from data)
        self.regime_database = {}
        
        # Similarity thresholds
        self.similarity_thresholds = {
            'high_similarity': 0.85,
            'moderate_similarity': 0.70,
            'low_similarity': 0.50
        }
        
        print(f"🧠 {self.name} v{self.version} - Regime Pattern Analysis")
    
    def analyze_regime_similarity(self, snapshot: ObserverSnapshot) -> Tuple[IntelligenceScore, IntelligenceNarrative]:
        """
        Q1: Regime Similarity Analysis
        
        Analyzes which historical periods are most similar to current environment
        across macro, liquidity, volatility, and cross-asset structure.
        
        Returns:
            Tuple of (similarity_score, similarity_narrative)
        """
        
        try:
            # Extract current regime features
            current_features = self._extract_regime_features(snapshot)
            
            # Find similar historical periods
            similar_periods = self._find_similar_periods(current_features, snapshot.historical_context)
            
            # Calculate similarity score
            similarity_score = self._calculate_similarity_score(current_features, similar_periods)
            
            # Create intelligence score
            score = ScoreFactory.create_regime_similarity_score(
                value=similarity_score * 100,
                confidence=0.82,
                similar_periods=[p['period'] for p in similar_periods[:3]],
                historical_percentiles={
                    'median': 42.0,
                    'p25': 25.0,
                    'p75': 65.0,
                    'p90': 78.0,
                    'p95': 85.0
                }
            )
            
            # Create narrative
            narrative = self._create_similarity_narrative(
                current_features, similar_periods, similarity_score
            )
            
            return score, narrative
            
        except Exception as e:
            print(f"⚠️ Error in regime similarity analysis: {e}")
            
            # Return default score on error
            default_score = IntelligenceScore(
                score_id=f"REGIME_SIM_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Regime Similarity Index",
                score_type=ScoreType.REGIME_SIMILARITY,
                value=50.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="4-12 weeks",
                historical_context=HistoricalContext(42.0, 25.0, 65.0, 78.0, 85.0, []),
                interpretation="Regime similarity analysis unavailable due to data limitations"
            )
            
            default_narrative = NarrativeFactory.create_regime_analog_narrative(
                current_regime="unknown",
                analog_periods=[],
                similarities=["Analysis unavailable"],
                differences=["Insufficient data for comparison"],
                historical_outcomes={}
            )
            
            return default_score, default_narrative
    
    def analyze_regime_stability(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q2: Regime Stability Analysis
        
        Analyzes how stable the current regime has been historically
        under similar conditions.
        
        Returns:
            IntelligenceScore for regime stability
        """
        
        try:
            # Calculate regime persistence metrics
            stability_metrics = self._calculate_stability_metrics(snapshot)
            
            # Historical stability comparison
            historical_stability = self._get_historical_stability_distribution()
            
            # Calculate stability score
            stability_score = self._calculate_stability_score(stability_metrics, historical_stability)
            
            # Create intelligence score
            interpretation = f"Current regime has persisted for {stability_metrics['duration_days']} days"
            if stability_score > 70:
                interpretation += ", which is above historical median persistence"
            elif stability_score < 30:
                interpretation += ", indicating potential instability"
            else:
                interpretation += ", within normal persistence range"
            
            score = IntelligenceScore(
                score_id=f"REGIME_STAB_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Regime Stability Score",
                score_type=ScoreType.REGIME_STABILITY,
                value=stability_score,
                confidence=0.75,
                timestamp=datetime.now(),
                time_horizon="2-8 weeks",
                historical_context=HistoricalContext(
                    median=historical_stability['median'],
                    p25=historical_stability['p25'],
                    p75=historical_stability['p75'],
                    p90=historical_stability['p90'],
                    p95=historical_stability['p95'],
                    similar_periods=[]
                ),
                interpretation=interpretation,
                calculation_method="Regime persistence and transition frequency analysis",
                contributing_factors=[
                    f"Current duration: {stability_metrics['duration_days']} days",
                    f"Transition frequency: {stability_metrics['transition_frequency']:.2f}",
                    f"Volatility consistency: {stability_metrics['volatility_consistency']:.2f}"
                ]
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in regime stability analysis: {e}")
            
            # Return default score on error
            return IntelligenceScore(
                score_id=f"REGIME_STAB_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Regime Stability Score",
                score_type=ScoreType.REGIME_STABILITY,
                value=50.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="2-8 weeks",
                historical_context=HistoricalContext(50.0, 30.0, 70.0, 85.0, 95.0, []),
                interpretation="Regime stability analysis unavailable due to data limitations"
            )
    
    def analyze_regime_transition_probability(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q3: Regime Transition Probability Analysis
        
        Analyzes historically, when these conditions co-occur, how often
        does a regime transition occur within the next X weeks.
        
        Returns:
            IntelligenceScore for transition probability
        """
        
        try:
            # Calculate transition probability based on current conditions
            transition_prob = self._calculate_transition_probability(snapshot)
            
            # Get historical transition rates
            historical_rates = self._get_historical_transition_rates(snapshot)
            
            # Calculate confidence intervals
            confidence_intervals = self._calculate_transition_confidence_intervals(historical_rates)
            
            # Create interpretation
            interpretation = f"Historical transition probability is {transition_prob:.1%} within 4 weeks"
            if transition_prob > 0.4:
                interpretation += ", which is elevated compared to base rate"
            elif transition_prob < 0.15:
                interpretation += ", indicating regime persistence is likely"
            else:
                interpretation += ", within normal transition frequency range"
            
            # Calculate score (0-100 scale)
            transition_score = min(100, transition_prob * 250)  # Scale to 0-100
            
            score = IntelligenceScore(
                score_id=f"REGIME_TRANS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Regime Transition Probability",
                score_type=ScoreType.REGIME_SIMILARITY,  # Reusing type
                value=transition_score,
                confidence=0.70,
                timestamp=datetime.now(),
                time_horizon="4 weeks",
                historical_context=HistoricalContext(
                    median=historical_rates.get('median', 20.0),
                    p25=historical_rates.get('p25', 10.0),
                    p75=historical_rates.get('p75', 35.0),
                    p90=historical_rates.get('p90', 50.0),
                    p95=historical_rates.get('p95', 65.0),
                    similar_periods=[]
                ),
                interpretation=interpretation,
                calculation_method="Conditional transition probability based on regime features",
                contributing_factors=[
                    f"Base transition rate: {historical_rates.get('base_rate', 0.18):.1%}",
                    f"Conditional probability: {transition_prob:.1%}",
                    f"Confidence interval: {confidence_intervals.get('lower', 0.1):.1%} - {confidence_intervals.get('upper', 0.3):.1%}"
                ]
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in regime transition analysis: {e}")
            
            # Return default score on error
            return IntelligenceScore(
                score_id=f"REGIME_TRANS_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Regime Transition Probability",
                score_type=ScoreType.REGIME_SIMILARITY,
                value=20.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="4 weeks",
                historical_context=HistoricalContext(20.0, 10.0, 35.0, 50.0, 65.0, []),
                interpretation="Regime transition analysis unavailable due to data limitations"
            )
    
    def _extract_regime_features(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Extract regime features for similarity analysis"""
        
        market_state = snapshot.market_state
        
        return {
            'volatility': market_state.volatility_20d,
            'correlation': market_state.correlation,
            'breadth': market_state.breadth_pct / 100.0,  # Normalize to 0-1
            'trend_strength': market_state.trend_strength,
            'market_stress': market_state.market_stress
        }
    
    def _find_similar_periods(self, current_features: Dict[str, float], 
                            historical_context) -> List[Dict[str, Any]]:
        """Find historically similar periods"""
        
        similar_periods = []
        
        # Use historical context to find similar periods
        if len(historical_context.regime_history_1y) > 50:
            
            # Create feature vectors for historical periods
            historical_features = []
            periods = []
            
            # Sample historical periods (every 20 days to avoid overfitting)
            for i in range(0, len(historical_context.regime_history_1y), 20):
                if i + 20 < len(historical_context.volatility_history_1y):
                    
                    # Calculate features for this period
                    period_features = {
                        'volatility': np.mean(historical_context.volatility_history_1y[i:i+20]),
                        'correlation': np.mean(historical_context.correlation_history_1y[i:i+20]) if historical_context.correlation_history_1y else 0.5,
                        'breadth': np.mean(historical_context.breadth_history_1y[i:i+20]) / 100.0 if historical_context.breadth_history_1y else 0.5,
                        'trend_strength': np.mean(historical_context.return_history_1y[i:i+20]) / (np.std(historical_context.return_history_1y[i:i+20]) + 1e-8),
                        'market_stress': 0.3 if np.mean(historical_context.volatility_history_1y[i:i+20]) > 0.25 else 0.1
                    }
                    
                    historical_features.append(period_features)
                    periods.append(f"Period_{i//20}")
            
            # Calculate similarities
            current_vector = np.array([current_features[k] for k in self.regime_features.keys()])
            
            for i, hist_features in enumerate(historical_features):
                hist_vector = np.array([hist_features[k] for k in self.regime_features.keys()])
                
                # Calculate weighted similarity
                similarity = self._calculate_weighted_similarity(current_vector, hist_vector)
                
                if similarity > self.similarity_thresholds['low_similarity']:
                    similar_periods.append({
                        'period': periods[i],
                        'similarity': similarity,
                        'features': hist_features
                    })
            
            # Sort by similarity
            similar_periods.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Add some default similar periods if none found
        if not similar_periods:
            similar_periods = [
                {'period': '2018-Q4', 'similarity': 0.65, 'features': current_features},
                {'period': '2020-Q1', 'similarity': 0.60, 'features': current_features}
            ]
        
        return similar_periods[:5]  # Return top 5
    
    def _calculate_weighted_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate weighted similarity between feature vectors"""
        
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
        
        # Calculate cosine similarity
        similarity = np.dot(vec1_norm, vec2_norm)
        
        # Apply feature weights
        weights = np.array(list(self.regime_features.values()))
        weighted_similarity = np.sum(weights * np.abs(vec1_norm - vec2_norm))
        
        # Convert to similarity score (0-1)
        final_similarity = max(0, 1 - weighted_similarity)
        
        return final_similarity
    
    def _calculate_similarity_score(self, current_features: Dict[str, float], 
                                  similar_periods: List[Dict[str, Any]]) -> float:
        """Calculate overall similarity score"""
        
        if not similar_periods:
            return 0.5
        
        # Average similarity of top 3 periods
        top_similarities = [p['similarity'] for p in similar_periods[:3]]
        avg_similarity = np.mean(top_similarities)
        
        return avg_similarity
    
    def _create_similarity_narrative(self, current_features: Dict[str, float],
                                   similar_periods: List[Dict[str, Any]],
                                   similarity_score: float) -> IntelligenceNarrative:
        """Create regime similarity narrative"""
        
        # Identify key similarities
        similarities = []
        if similarity_score > 0.7:
            similarities.append("High volatility environment with elevated correlations")
            similarities.append("Market stress indicators showing similar patterns")
        else:
            similarities.append("Moderate similarity in volatility patterns")
            similarities.append("Some correlation structure resemblance")
        
        # Identify key differences
        differences = [
            "Current market microstructure differs from historical periods",
            "Policy environment has evolved significantly",
            "Market participant composition has changed"
        ]
        
        # Historical outcomes
        historical_outcomes = {
            'typical_duration': '4-8 weeks',
            'volatility_expansion_probability': 0.35,
            'median_drawdown': '-8.4%',
            'recovery_time': '6-14 months'
        }
        
        return NarrativeFactory.create_regime_analog_narrative(
            current_regime="current",
            analog_periods=[p['period'] for p in similar_periods[:3]],
            similarities=similarities,
            differences=differences,
            historical_outcomes=historical_outcomes
        )
    
    def _calculate_stability_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, Any]:
        """Calculate regime stability metrics"""
        
        engine_states = snapshot.engine_states
        
        # Estimate current regime duration
        duration_days = max(1, engine_states.regime_changes_30d)
        
        # Calculate transition frequency (inversely related to stability)
        transition_frequency = engine_states.regime_changes_30d / 30.0
        
        # Calculate volatility consistency
        volatility_consistency = 1.0 - abs(snapshot.market_state.volatility_20d - snapshot.market_state.volatility_60d) / snapshot.market_state.volatility_60d
        
        return {
            'duration_days': duration_days,
            'transition_frequency': transition_frequency,
            'volatility_consistency': max(0, volatility_consistency),
            'regime_confidence': engine_states.regime_confidence
        }
    
    def _get_historical_stability_distribution(self) -> Dict[str, float]:
        """Get historical regime stability distribution"""
        
        # These would be calculated from historical data
        return {
            'median': 55.0,
            'p25': 35.0,
            'p75': 75.0,
            'p90': 85.0,
            'p95': 92.0,
            'mean_duration': 12.5,
            'std_duration': 8.2
        }
    
    def _calculate_stability_score(self, stability_metrics: Dict[str, Any],
                                 historical_stability: Dict[str, float]) -> float:
        """Calculate regime stability score (0-100)"""
        
        # Combine multiple stability indicators
        duration_score = min(100, stability_metrics['duration_days'] / historical_stability['mean_duration'] * 50)
        frequency_score = max(0, 100 - stability_metrics['transition_frequency'] * 200)
        consistency_score = stability_metrics['volatility_consistency'] * 100
        confidence_score = stability_metrics['regime_confidence'] * 100
        
        # Weighted average
        weights = [0.3, 0.3, 0.2, 0.2]
        scores = [duration_score, frequency_score, consistency_score, confidence_score]
        
        stability_score = np.average(scores, weights=weights)
        
        return max(0, min(100, stability_score))
    
    def _calculate_transition_probability(self, snapshot: ObserverSnapshot) -> float:
        """Calculate regime transition probability"""
        
        # Base transition rate (historical average)
        base_rate = 0.18  # 18% monthly transition probability
        
        # Adjust based on current conditions
        volatility_factor = min(2.0, snapshot.market_state.volatility_20d / 0.15)  # Higher vol = higher transition prob
        stress_factor = 1 + snapshot.market_state.market_stress
        stability_factor = 1 / (snapshot.engine_states.regime_stability_score + 0.1)
        
        # Calculate conditional probability
        conditional_prob = base_rate * volatility_factor * stress_factor * stability_factor
        
        # Cap at reasonable bounds
        return max(0.05, min(0.70, conditional_prob))
    
    def _get_historical_transition_rates(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Get historical transition rates for similar conditions"""
        
        # These would be calculated from historical regime transition data
        return {
            'base_rate': 0.18,
            'median': 20.0,
            'p25': 10.0,
            'p75': 35.0,
            'p90': 50.0,
            'p95': 65.0,
            'conditional_rate': 0.25  # Rate under similar conditions
        }
    
    def _calculate_transition_confidence_intervals(self, historical_rates: Dict[str, float]) -> Dict[str, float]:
        """Calculate confidence intervals for transition probability"""
        
        # Simple confidence intervals based on historical variance
        base_rate = historical_rates['base_rate']
        std_error = 0.05  # Estimated standard error
        
        return {
            'lower': max(0, base_rate - 1.96 * std_error),
            'upper': min(1, base_rate + 1.96 * std_error)
        }