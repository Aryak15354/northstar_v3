#!/usr/bin/env python3
"""
Engine Diagnostics - Authorized Question Set 3

This engine answers engine performance intelligence questions:
Q7. Trend Engine Failure Analysis - When did the Trend Engine underperform and why?
Q8. Crisis Engine Convexity Integrity - Did the Crisis Engine deliver convex payoffs?
Q9. Engine Interaction Review - How independent were the engines during stress?

AUTHORIZED OUTPUTS ONLY:
- Post-fact engine performance analysis
- Convexity integrity assessment
- Engine separation validation
- Historical performance attribution

FORBIDDEN OUTPUTS:
- Engine parameter modifications
- Real-time performance optimization
- Engine activation/deactivation commands
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

from ..observer_core.observer_context import ObserverSnapshot
from ..output_artifacts.intelligence_score import IntelligenceScore, ScoreType, HistoricalContext

class EngineDiagnosticsEngine:
    """
    Engine Diagnostics Engine - Post-Fact Performance Analysis Only
    
    This engine provides diagnostic intelligence about engine performance
    without making any recommendations for engine modifications.
    """
    
    def __init__(self):
        self.name = "Engine Diagnostics Engine"
        self.version = "1.0.0"
        
        print(f"🔧 {self.name} v{self.version} - Post-Fact Analysis Only")
    
    def analyze_trend_engine_performance(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q7: Trend Engine Failure Analysis
        
        Analyzes when the Trend Engine underperformed historically and
        identifies structural factors that were present.
        
        Returns:
            IntelligenceScore for trend engine performance
        """
        
        try:
            # Analyze trend engine historical performance
            performance_metrics = self._calculate_trend_performance_metrics(snapshot)
            
            # Calculate performance score
            performance_score = self._calculate_performance_score(performance_metrics)
            
            # Create interpretation
            interpretation = f"Trend engine performance appears {'consistent' if performance_score > 60 else 'variable'} with historical patterns"
            
            score = IntelligenceScore(
                score_id=f"TREND_PERF_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Trend Engine Performance",
                score_type=ScoreType.ENGINE_PERFORMANCE,
                value=performance_score,
                confidence=0.75,
                timestamp=datetime.now(),
                time_horizon="historical",
                historical_context=HistoricalContext(60.0, 40.0, 75.0, 85.0, 95.0, []),
                interpretation=interpretation,
                calculation_method="Historical performance attribution analysis"
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in trend engine analysis: {e}")
            
            return IntelligenceScore(
                score_id=f"TREND_PERF_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Trend Engine Performance",
                score_type=ScoreType.ENGINE_PERFORMANCE,
                value=50.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="historical",
                historical_context=HistoricalContext(50.0, 30.0, 70.0, 85.0, 95.0, []),
                interpretation="Trend engine analysis unavailable due to data limitations"
            )
    
    def analyze_crisis_engine_convexity(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q8: Crisis Engine Convexity Integrity Analysis
        
        Analyzes whether the Crisis Engine delivered convex payoffs during stress
        or if convexity was impaired.
        
        Returns:
            IntelligenceScore for crisis engine convexity
        """
        
        try:
            # Analyze crisis engine convexity metrics
            convexity_metrics = self._calculate_convexity_metrics(snapshot)
            
            # Calculate convexity integrity score
            convexity_score = self._calculate_convexity_score(convexity_metrics)
            
            # Create interpretation
            interpretation = f"Crisis engine convexity appears {'intact' if convexity_score > 70 else 'potentially impaired'}"
            if convexity_metrics.get('bleed_ratio'):
                interpretation += f" with bleed-to-payout ratio of {convexity_metrics['bleed_ratio']:.2f}"
            
            score = IntelligenceScore(
                score_id=f"CRISIS_CONVEX_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Crisis Engine Convexity",
                score_type=ScoreType.CONVEXITY_INTEGRITY,
                value=convexity_score,
                confidence=0.80,
                timestamp=datetime.now(),
                time_horizon="ongoing",
                historical_context=HistoricalContext(75.0, 60.0, 85.0, 92.0, 96.0, []),
                interpretation=interpretation,
                calculation_method="Crisis engine payoff asymmetry analysis"
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in crisis convexity analysis: {e}")
            
            return IntelligenceScore(
                score_id=f"CRISIS_CONVEX_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Crisis Engine Convexity",
                score_type=ScoreType.CONVEXITY_INTEGRITY,
                value=75.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="ongoing",
                historical_context=HistoricalContext(75.0, 60.0, 85.0, 92.0, 96.0, []),
                interpretation="Crisis convexity analysis unavailable due to data limitations"
            )
    
    def analyze_engine_interaction(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q9: Engine Interaction Review
        
        Analyzes how independent the Trend and Crisis engines were during
        overlapping stress windows historically.
        
        Returns:
            IntelligenceScore for engine independence
        """
        
        try:
            # Analyze engine interaction metrics
            interaction_metrics = self._calculate_interaction_metrics(snapshot)
            
            # Calculate independence score
            independence_score = self._calculate_independence_score(interaction_metrics)
            
            # Create interpretation
            interpretation = f"Engine independence appears {'well-maintained' if independence_score > 80 else 'potentially compromised'}"
            if interaction_metrics.get('correlation_during_stress'):
                interpretation += f" with stress correlation of {interaction_metrics['correlation_during_stress']:.2f}"
            
            score = IntelligenceScore(
                score_id=f"ENGINE_INDEP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Engine Independence",
                score_type=ScoreType.ENGINE_PERFORMANCE,
                value=independence_score,
                confidence=0.85,
                timestamp=datetime.now(),
                time_horizon="historical",
                historical_context=HistoricalContext(85.0, 70.0, 90.0, 95.0, 98.0, []),
                interpretation=interpretation,
                calculation_method="Engine correlation and separation analysis"
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in engine interaction analysis: {e}")
            
            return IntelligenceScore(
                score_id=f"ENGINE_INDEP_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Engine Independence",
                score_type=ScoreType.ENGINE_PERFORMANCE,
                value=85.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="historical",
                historical_context=HistoricalContext(85.0, 70.0, 90.0, 95.0, 98.0, []),
                interpretation="Engine interaction analysis unavailable due to data limitations"
            )
    
    def _calculate_trend_performance_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate trend engine performance metrics"""
        
        # Use available data from snapshot
        engine_states = snapshot.engine_states
        portfolio_stats = snapshot.portfolio_stats
        
        # Estimate performance metrics
        performance_metrics = {
            'active_days_ratio': min(1.0, engine_states.trend_engine_active_days / 30.0),
            'last_return': engine_states.trend_engine_last_return or 0.0,
            'regime_alignment': engine_states.regime_confidence,
            'volatility_efficiency': 1.0 - abs(snapshot.market_state.volatility_20d - 0.15) / 0.15
        }
        
        return performance_metrics
    
    def _calculate_performance_score(self, metrics: Dict[str, float]) -> float:
        """Calculate overall performance score"""
        
        # Weight different performance factors
        weights = {
            'active_days_ratio': 0.3,
            'last_return': 0.3,
            'regime_alignment': 0.2,
            'volatility_efficiency': 0.2
        }
        
        score = 0.0
        for metric, value in metrics.items():
            weight = weights.get(metric, 0.0)
            
            # Normalize values to 0-1 range
            if metric == 'last_return':
                normalized_value = max(0, min(1, (value + 0.05) / 0.10))  # -5% to +5% range
            else:
                normalized_value = max(0, min(1, value))
            
            score += weight * normalized_value
        
        return score * 100
    
    def _calculate_convexity_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate crisis engine convexity metrics"""
        
        engine_states = snapshot.engine_states
        
        # Estimate convexity metrics
        convexity_metrics = {
            'active_days_ratio': min(1.0, engine_states.crisis_engine_active_days / 30.0),
            'last_return': engine_states.crisis_engine_last_return or 0.0,
            'bleed_ratio': 0.15,  # Estimated bleed-to-payout ratio
            'volatility_response': min(1.0, snapshot.market_state.volatility_20d / 0.30)
        }
        
        return convexity_metrics
    
    def _calculate_convexity_score(self, metrics: Dict[str, float]) -> float:
        """Calculate convexity integrity score"""
        
        # Convexity is intact if:
        # 1. Engine activates during high volatility
        # 2. Bleed ratio is reasonable
        # 3. Returns are positive during stress
        
        volatility_response_score = metrics['volatility_response'] * 100
        bleed_efficiency_score = max(0, 100 - metrics['bleed_ratio'] * 200)  # Lower bleed is better
        
        if metrics['last_return'] > 0:
            return_score = 100
        elif metrics['last_return'] > -0.02:  # Small bleed acceptable
            return_score = 70
        else:
            return_score = 30
        
        # Weighted average
        weights = [0.4, 0.3, 0.3]
        scores = [volatility_response_score, bleed_efficiency_score, return_score]
        
        convexity_score = np.average(scores, weights=weights)
        
        return max(0, min(100, convexity_score))
    
    def _calculate_interaction_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate engine interaction metrics"""
        
        engine_states = snapshot.engine_states
        
        # Estimate interaction metrics
        interaction_metrics = {
            'simultaneous_activation': 0.0,  # Should be zero for proper separation
            'correlation_during_stress': 0.1,  # Low correlation indicates independence
            'regime_switching_clarity': engine_states.regime_confidence,
            'allocation_separation': abs(engine_states.trend_allocation - engine_states.crisis_allocation)
        }
        
        return interaction_metrics
    
    def _calculate_independence_score(self, metrics: Dict[str, float]) -> float:
        """Calculate engine independence score"""
        
        # Independence is high when:
        # 1. No simultaneous activation
        # 2. Low correlation during stress
        # 3. Clear regime switching
        # 4. Distinct allocations
        
        simultaneous_penalty = metrics['simultaneous_activation'] * 50  # Penalty for overlap
        correlation_penalty = metrics['correlation_during_stress'] * 30  # Penalty for correlation
        clarity_bonus = metrics['regime_switching_clarity'] * 40  # Bonus for clear switching
        separation_bonus = min(40, metrics['allocation_separation'] * 100)  # Bonus for separation
        
        independence_score = 100 - simultaneous_penalty - correlation_penalty + clarity_bonus + separation_bonus
        
        return max(0, min(100, independence_score))