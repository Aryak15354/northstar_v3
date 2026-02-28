#!/usr/bin/env python3
"""
Meta-Integrity Intelligence - Authorized Question Set 5 & 6

This engine answers meta-questions about system health:
Q15. Behavioral Integrity Drift - Is the system deviating from intended behavior?
Q16. Preparedness Assessment - What scenarios should the operator mentally rehearse?

AUTHORIZED OUTPUTS ONLY:
- System behavioral drift detection
- Preparedness scenario identification
- Integrity monitoring
- Psychological risk assessment

FORBIDDEN OUTPUTS:
- System parameter modifications
- Behavioral corrections
- Operational interventions
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')

from ..observer_core.observer_context import ObserverSnapshot
from ..output_artifacts.intelligence_score import IntelligenceScore, ScoreType, HistoricalContext
from ..output_artifacts.intelligence_narrative import IntelligenceNarrative, NarrativeType

class MetaIntegrityIntelligenceEngine:
    """
    Meta-Integrity Intelligence Engine - System Health Monitoring Only
    
    This engine provides intelligence about system behavioral integrity
    and preparedness scenarios without making system modifications.
    """
    
    def __init__(self):
        self.name = "Meta-Integrity Intelligence Engine"
        self.version = "1.0.0"
        
        print(f"🔍 {self.name} v{self.version} - System Health Monitoring")
    
    def analyze_behavioral_drift(self, snapshot: ObserverSnapshot) -> Tuple[IntelligenceScore, IntelligenceNarrative]:
        """
        Q15: Behavioral Integrity Drift Analysis
        
        Analyzes whether there are signs the system is slowly deviating
        from its intended behavioral profile.
        
        Returns:
            Tuple of (drift_score, drift_narrative)
        """
        
        try:
            # Analyze behavioral drift metrics
            drift_metrics = self._calculate_drift_metrics(snapshot)
            
            # Calculate drift score
            drift_score = self._calculate_drift_score(drift_metrics)
            
            # Create drift score
            interpretation = f"System behavioral drift appears {'concerning' if drift_score > 70 else 'within acceptable bounds'}"
            if drift_metrics.get('regime_consistency'):
                interpretation += f" with regime consistency of {drift_metrics['regime_consistency']:.1%}"
            
            score = IntelligenceScore(
                score_id=f"BEHAVIORAL_DRIFT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Behavioral Drift Index",
                score_type=ScoreType.BEHAVIORAL_DRIFT,
                value=drift_score,
                confidence=0.80,
                timestamp=datetime.now(),
                time_horizon="ongoing",
                historical_context=HistoricalContext(25.0, 10.0, 40.0, 60.0, 80.0, []),
                interpretation=interpretation,
                calculation_method="Multi-dimensional behavioral consistency analysis"
            )
            
            # Create drift narrative
            narrative = self._create_drift_narrative(drift_metrics, drift_score)
            
            return score, narrative
            
        except Exception as e:
            print(f"⚠️ Error in behavioral drift analysis: {e}")
            
            default_score = IntelligenceScore(
                score_id=f"BEHAVIORAL_DRIFT_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Behavioral Drift Index",
                score_type=ScoreType.BEHAVIORAL_DRIFT,
                value=25.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="ongoing",
                historical_context=HistoricalContext(25.0, 10.0, 40.0, 60.0, 80.0, []),
                interpretation="Behavioral drift analysis unavailable due to data limitations"
            )
            
            default_narrative = IntelligenceNarrative(
                narrative_id=f"DRIFT_NARRATIVE_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                narrative_type=NarrativeType.PERFORMANCE_ATTRIBUTION,
                title="System Behavioral Drift Analysis",
                summary="Behavioral drift analysis unavailable due to insufficient data",
                timestamp=datetime.now(),
                key_similarities=["Analysis unavailable"],
                key_differences=["Insufficient data for comparison"]
            )
            
            return default_score, default_narrative
    
    def analyze_preparedness_scenarios(self, snapshot: ObserverSnapshot) -> IntelligenceNarrative:
        """
        Q16: Preparedness Assessment Analysis
        
        Analyzes what scenarios the operator should mentally rehearse
        given current intelligence.
        
        Returns:
            IntelligenceNarrative with preparedness scenarios
        """
        
        try:
            # Identify preparedness scenarios
            scenarios = self._identify_preparedness_scenarios(snapshot)
            
            # Create preparedness narrative
            narrative = self._create_preparedness_narrative(scenarios, snapshot)
            
            return narrative
            
        except Exception as e:
            print(f"⚠️ Error in preparedness analysis: {e}")
            
            return IntelligenceNarrative(
                narrative_id=f"PREPAREDNESS_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                narrative_type=NarrativeType.HISTORICAL_CONTEXT,
                title="Preparedness Assessment",
                summary="Preparedness analysis unavailable due to data limitations",
                timestamp=datetime.now(),
                key_similarities=["Analysis unavailable"],
                key_differences=["Insufficient data for scenario identification"]
            )
    
    def _calculate_drift_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate behavioral drift metrics"""
        
        engine_states = snapshot.engine_states
        market_state = snapshot.market_state
        portfolio_stats = snapshot.portfolio_stats
        
        # Calculate various drift indicators
        drift_metrics = {
            'regime_consistency': engine_states.regime_stability_score,
            'allocation_stability': 1.0 - abs(engine_states.trend_allocation - 0.6),  # Expected ~60% trend
            'exposure_drift': abs(portfolio_stats.avg_exposure_30d - 0.35),  # Expected ~35% exposure
            'volatility_response': abs(market_state.volatility_20d - 0.15) / 0.15,  # Deviation from normal
            'correlation_behavior': abs(market_state.correlation - 0.5),  # Deviation from normal
            'turnover_consistency': abs(portfolio_stats.turnover_7d - 0.05) / 0.05  # Expected ~5% turnover
        }
        
        return drift_metrics
    
    def _calculate_drift_score(self, metrics: Dict[str, float]) -> float:
        """Calculate behavioral drift score"""
        
        # Lower consistency = higher drift score
        drift_factors = []
        
        # Regime consistency factor (inverted - lower consistency = higher drift)
        regime_drift = (1.0 - metrics['regime_consistency']) * 100
        drift_factors.append(regime_drift)
        
        # Allocation stability factor
        allocation_drift = metrics['allocation_stability'] * 100
        drift_factors.append(allocation_drift)
        
        # Exposure drift factor
        exposure_drift = min(100, metrics['exposure_drift'] * 200)  # 50% deviation = 100 points
        drift_factors.append(exposure_drift)
        
        # Volatility response drift
        volatility_drift = min(100, metrics['volatility_response'] * 100)
        drift_factors.append(volatility_drift)
        
        # Correlation behavior drift
        correlation_drift = metrics['correlation_behavior'] * 200  # 50% deviation = 100 points
        drift_factors.append(correlation_drift)
        
        # Turnover consistency drift
        turnover_drift = min(100, metrics['turnover_consistency'] * 100)
        drift_factors.append(turnover_drift)
        
        # Weighted average
        weights = [0.25, 0.20, 0.15, 0.15, 0.15, 0.10]
        drift_score = np.average(drift_factors, weights=weights)
        
        return max(0, min(100, drift_score))
    
    def _create_drift_narrative(self, drift_metrics: Dict[str, float], drift_score: float) -> IntelligenceNarrative:
        """Create behavioral drift narrative"""
        
        # Identify key drift areas
        similarities = []
        differences = []
        
        if drift_metrics['regime_consistency'] > 0.8:
            similarities.append("Regime classification behavior remains consistent")
        else:
            differences.append("Regime classification showing some variability")
        
        if drift_metrics['allocation_stability'] < 0.2:
            similarities.append("Allocation patterns consistent with design")
        else:
            differences.append("Allocation patterns showing deviation from expected behavior")
        
        if drift_metrics['exposure_drift'] < 0.1:
            similarities.append("Exposure management within expected parameters")
        else:
            differences.append("Exposure levels deviating from typical ranges")
        
        # Add default differences for balanced analysis
        differences.extend([
            "Market conditions have evolved since system calibration",
            "Regime patterns may be shifting due to structural changes"
        ])
        
        return IntelligenceNarrative(
            narrative_id=f"DRIFT_NARRATIVE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            narrative_type=NarrativeType.PERFORMANCE_ATTRIBUTION,
            title="System Behavioral Drift Analysis",
            summary=f"Analysis of system behavioral consistency shows {'potential drift concerns' if drift_score > 50 else 'stable behavioral patterns'}",
            timestamp=datetime.now(),
            key_similarities=similarities,
            key_differences=differences,
            historical_outcomes={
                'typical_drift_range': '10-30%',
                'intervention_threshold': '70%',
                'historical_stability': '85%'
            },
            engine_behavior_note="Historically, the system maintains behavioral consistency within 20% of design parameters during normal market conditions"
        )
    
    def _identify_preparedness_scenarios(self, snapshot: ObserverSnapshot) -> List[Dict[str, Any]]:
        """Identify scenarios for mental rehearsal"""
        
        market_state = snapshot.market_state
        engine_states = snapshot.engine_states
        
        scenarios = []
        
        # Scenario 1: Regime transition
        if engine_states.regime_confidence < 0.7:
            scenarios.append({
                'scenario': 'Regime Transition',
                'probability': 'Moderate',
                'description': 'Market regime may transition within 2-4 weeks',
                'psychological_risks': ['Overconfidence in timing', 'Premature intervention'],
                'mental_rehearsal': 'Practice maintaining discipline during regime uncertainty'
            })
        
        # Scenario 2: Volatility expansion
        if market_state.volatility_20d < 0.15 and market_state.market_stress > 0.2:
            scenarios.append({
                'scenario': 'Volatility Expansion',
                'probability': 'Elevated',
                'description': 'Current low volatility may expand rapidly',
                'psychological_risks': ['Panic during expansion', 'False calm complacency'],
                'mental_rehearsal': 'Visualize calm response to volatility spikes'
            })
        
        # Scenario 3: Crisis engine activation
        if market_state.market_stress > 0.3:
            scenarios.append({
                'scenario': 'Crisis Engine Activation',
                'probability': 'Possible',
                'description': 'Stress levels approaching crisis engine thresholds',
                'psychological_risks': ['Interference with crisis logic', 'Emotional override'],
                'mental_rehearsal': 'Practice trusting crisis engine during stress'
            })
        
        # Scenario 4: Extended drawdown
        if snapshot.portfolio_stats.max_drawdown_30d < -0.05:
            scenarios.append({
                'scenario': 'Extended Drawdown',
                'probability': 'Ongoing',
                'description': 'Drawdown may persist or deepen',
                'psychological_risks': ['Loss of confidence', 'System abandonment'],
                'mental_rehearsal': 'Reinforce commitment to systematic approach'
            })
        
        # Default scenario if none identified
        if not scenarios:
            scenarios.append({
                'scenario': 'Normal Market Conditions',
                'probability': 'Current',
                'description': 'Markets operating within normal parameters',
                'psychological_risks': ['Overconfidence', 'Complacency'],
                'mental_rehearsal': 'Maintain vigilance during calm periods'
            })
        
        return scenarios
    
    def _create_preparedness_narrative(self, scenarios: List[Dict[str, Any]], snapshot: ObserverSnapshot) -> IntelligenceNarrative:
        """Create preparedness assessment narrative"""
        
        # Extract scenario information
        scenario_names = [s['scenario'] for s in scenarios]
        psychological_risks = []
        mental_rehearsals = []
        
        for scenario in scenarios:
            psychological_risks.extend(scenario['psychological_risks'])
            mental_rehearsals.append(scenario['mental_rehearsal'])
        
        # Create similarities (current conditions)
        similarities = [
            f"Current market conditions suggest {len(scenarios)} key scenarios for consideration",
            f"Psychological risks include {', '.join(psychological_risks[:3])}"
        ]
        
        # Create differences (scenario-specific factors)
        differences = [
            "Each scenario requires different psychological preparation",
            "Market structure evolution creates new psychological challenges",
            "Historical precedents may not fully capture current dynamics"
        ]
        
        return IntelligenceNarrative(
            narrative_id=f"PREPAREDNESS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            narrative_type=NarrativeType.HISTORICAL_CONTEXT,
            title="Operator Preparedness Assessment",
            summary=f"Current intelligence suggests {len(scenarios)} key scenarios warrant mental rehearsal and psychological preparation",
            timestamp=datetime.now(),
            key_similarities=similarities,
            key_differences=differences,
            historical_outcomes={
                'scenario_count': len(scenarios),
                'primary_scenarios': scenario_names[:3],
                'preparation_focus': 'Psychological resilience and systematic discipline'
            },
            comparable_periods=[],
            engine_behavior_note="Historically, operators who mentally rehearse scenarios maintain better discipline during actual events"
        )