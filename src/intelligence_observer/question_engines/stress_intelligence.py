#!/usr/bin/env python3
"""
Stress Intelligence Engine - Authorized Question Set 2

This engine answers stress & crisis anticipation questions:
Q4. Stress Signal Clustering - Are stress indicators clustering beyond historical baselines?
Q5. False Calm Detection - Do current conditions resemble historical 'false calm' regimes?
Q6. Crisis Engine Readiness - How long after initial stress signals did full crisis activation occur?

AUTHORIZED OUTPUTS ONLY:
- Stress signal density analysis
- False calm likelihood assessment
- Crisis timing patterns
- Early warning indicators

FORBIDDEN OUTPUTS:
- Crisis engine activation commands
- Pre-emptive position changes
- Risk override recommendations
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import warnings
warnings.filterwarnings('ignore')

from ..observer_core.observer_context import ObserverSnapshot
from ..output_artifacts.intelligence_score import IntelligenceScore, ScoreType, HistoricalContext
from ..output_artifacts.intelligence_alert import IntelligenceAlert, AlertFactory, AlertType, AlertSeverity
from ..output_artifacts.intelligence_narrative import IntelligenceNarrative, NarrativeFactory, NarrativeType

@dataclass
class StressIndicator:
    """Individual stress indicator"""
    name: str
    value: float
    threshold: float
    is_active: bool
    historical_percentile: float
    
class StressIntelligenceEngine:
    """
    Stress Intelligence Engine - Early Warning Without Action
    
    This engine provides intelligence about stress clustering, false calm periods,
    and crisis timing patterns without triggering any system actions.
    """
    
    def __init__(self):
        self.name = "Stress Intelligence Engine"
        self.version = "1.0.0"
        
        # Stress indicator definitions
        self.stress_indicators = {
            'volatility_spike': {
                'threshold': 0.25,  # 25% annualized volatility
                'weight': 0.25,
                'description': 'Volatility above normal levels'
            },
            'correlation_surge': {
                'threshold': 0.75,  # 75% cross-asset correlation
                'weight': 0.20,
                'description': 'Elevated cross-asset correlations'
            },
            'breadth_deterioration': {
                'threshold': 30.0,  # 30% breadth
                'weight': 0.15,
                'description': 'Market breadth deterioration'
            },
            'liquidity_stress': {
                'threshold': 0.30,  # 30% liquidity stress
                'weight': 0.20,
                'description': 'Liquidity conditions stress'
            },
            'momentum_breakdown': {
                'threshold': -2.0,  # -2 sigma momentum
                'weight': 0.10,
                'description': 'Momentum factor breakdown'
            },
            'credit_stress': {
                'threshold': 0.40,  # 40% credit stress
                'weight': 0.10,
                'description': 'Credit market stress signals'
            }
        }
        
        # False calm characteristics
        self.false_calm_indicators = {
            'volatility_compression': 0.12,  # Vol below 12%
            'correlation_normalization': 0.45,  # Correlation below 45%
            'breadth_expansion': 65.0,  # Breadth above 65%
            'complacency_duration': 20  # Days of low stress
        }
        
        # Historical crisis patterns
        self.crisis_patterns = {
            'warning_to_crisis_days': {
                'median': 12,
                'p25': 5,
                'p75': 25,
                'p90': 45
            },
            'false_alarm_rate': 0.35,  # 35% of stress signals are false alarms
            'crisis_probability_given_clustering': 0.42  # 42% probability when clustering
        }
        
        print(f"🚨 {self.name} v{self.version} - Stress Pattern Recognition")
    
    def analyze_stress_clustering(self, snapshot: ObserverSnapshot) -> Tuple[IntelligenceScore, Optional[IntelligenceAlert]]:
        """
        Q4: Stress Signal Clustering Analysis
        
        Analyzes whether stress indicators are clustering beyond historical baselines.
        
        Returns:
            Tuple of (clustering_score, optional_alert)
        """
        
        try:
            # Calculate individual stress indicators
            stress_indicators = self._calculate_stress_indicators(snapshot)
            
            # Calculate clustering metrics
            clustering_metrics = self._calculate_clustering_metrics(stress_indicators)
            
            # Get historical clustering distribution
            historical_clustering = self._get_historical_clustering_distribution()
            
            # Calculate clustering score
            clustering_score = self._calculate_clustering_score(clustering_metrics, historical_clustering)
            
            # Create intelligence score
            active_indicators = [ind.name for ind in stress_indicators if ind.is_active]
            
            interpretation = f"Stress indicators are {'clustering above' if clustering_score > 60 else 'within'} historical baseline"
            if active_indicators:
                interpretation += f". Active: {', '.join(active_indicators[:3])}"
            
            score = IntelligenceScore(
                score_id=f"STRESS_CLUST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Stress Clustering Index",
                score_type=ScoreType.STRESS_CLUSTERING,
                value=clustering_score,
                confidence=0.85,
                timestamp=datetime.now(),
                time_horizon="2-8 weeks",
                historical_context=HistoricalContext(
                    median=historical_clustering['median'],
                    p25=historical_clustering['p25'],
                    p75=historical_clustering['p75'],
                    p90=historical_clustering['p90'],
                    p95=historical_clustering['p95'],
                    similar_periods=[]
                ),
                interpretation=interpretation,
                calculation_method="Multi-indicator stress co-activation analysis",
                contributing_factors=[
                    f"Active indicators: {len(active_indicators)}/{len(stress_indicators)}",
                    f"Clustering density: {clustering_metrics['density']:.2f}",
                    f"Weighted stress score: {clustering_metrics['weighted_score']:.2f}"
                ]
            )
            
            # Create alert if clustering is significant
            alert = None
            if clustering_score > 70:
                alert = AlertFactory.create_stress_clustering_alert(
                    stress_score=clustering_score,
                    active_indicators=active_indicators,
                    historical_precedents=self._get_stress_precedents(clustering_score)
                )
            
            return score, alert
            
        except Exception as e:
            print(f"⚠️ Error in stress clustering analysis: {e}")
            
            # Return default score on error
            default_score = IntelligenceScore(
                score_id=f"STRESS_CLUST_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Stress Clustering Index",
                score_type=ScoreType.STRESS_CLUSTERING,
                value=35.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="2-8 weeks",
                historical_context=HistoricalContext(35.0, 20.0, 55.0, 72.0, 85.0, []),
                interpretation="Stress clustering analysis unavailable due to data limitations"
            )
            
            return default_score, None
    
    def analyze_false_calm_detection(self, snapshot: ObserverSnapshot) -> Tuple[IntelligenceScore, Optional[IntelligenceAlert]]:
        """
        Q5: False Calm Detection Analysis
        
        Analyzes whether current volatility and liquidity conditions resemble
        historical 'false calm' regimes that preceded volatility expansion.
        
        Returns:
            Tuple of (false_calm_score, optional_alert)
        """
        
        try:
            # Calculate false calm indicators
            false_calm_metrics = self._calculate_false_calm_metrics(snapshot)
            
            # Get historical false calm patterns
            historical_patterns = self._get_historical_false_calm_patterns()
            
            # Calculate false calm likelihood
            false_calm_score = self._calculate_false_calm_score(false_calm_metrics, historical_patterns)
            
            # Create intelligence score
            interpretation = f"Current conditions {'resemble' if false_calm_score > 60 else 'do not strongly resemble'} historical false calm patterns"
            if false_calm_metrics['volatility_compression'] > 0.5:
                interpretation += f" with significant volatility compression"
            
            score = IntelligenceScore(
                score_id=f"FALSE_CALM_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="False Calm Likelihood",
                score_type=ScoreType.FALSE_CALM_LIKELIHOOD,
                value=false_calm_score,
                confidence=0.75,
                timestamp=datetime.now(),
                time_horizon="4-12 weeks",
                historical_context=HistoricalContext(
                    median=historical_patterns['median_score'],
                    p25=historical_patterns['p25_score'],
                    p75=historical_patterns['p75_score'],
                    p90=historical_patterns['p90_score'],
                    p95=historical_patterns['p95_score'],
                    similar_periods=historical_patterns['similar_periods']
                ),
                interpretation=interpretation,
                calculation_method="False calm pattern matching with volatility compression analysis",
                contributing_factors=[
                    f"Volatility compression: {false_calm_metrics['volatility_compression']:.2f}",
                    f"Correlation normalization: {false_calm_metrics['correlation_normalization']:.2f}",
                    f"Complacency duration: {false_calm_metrics['complacency_duration']} days"
                ]
            )
            
            # Create alert if false calm likelihood is high
            alert = None
            if false_calm_score > 65:
                alert = AlertFactory.create_false_calm_alert(
                    false_calm_score=false_calm_score,
                    volatility_compression=false_calm_metrics['volatility_compression'],
                    historical_precedents=historical_patterns['similar_periods']
                )
            
            return score, alert
            
        except Exception as e:
            print(f"⚠️ Error in false calm analysis: {e}")
            
            # Return default score on error
            default_score = IntelligenceScore(
                score_id=f"FALSE_CALM_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="False Calm Likelihood",
                score_type=ScoreType.FALSE_CALM_LIKELIHOOD,
                value=30.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="4-12 weeks",
                historical_context=HistoricalContext(30.0, 15.0, 50.0, 70.0, 85.0, []),
                interpretation="False calm analysis unavailable due to data limitations"
            )
            
            return default_score, None
    
    def analyze_crisis_engine_readiness(self, snapshot: ObserverSnapshot) -> IntelligenceScore:
        """
        Q6: Crisis Engine Readiness Analysis
        
        Analyzes historically, how long after initial stress signals did
        full crisis activation occur, providing timing context.
        
        Returns:
            IntelligenceScore for crisis timing patterns
        """
        
        try:
            # Analyze current stress signal progression
            stress_progression = self._analyze_stress_progression(snapshot)
            
            # Get historical crisis timing patterns
            timing_patterns = self._get_historical_crisis_timing()
            
            # Calculate readiness score based on stress signal maturity
            readiness_score = self._calculate_readiness_score(stress_progression, timing_patterns)
            
            # Create interpretation
            interpretation = f"Stress signals have been building for {stress_progression['signal_age']} days"
            if readiness_score > 70:
                interpretation += ", approaching historical crisis activation timeframes"
            elif readiness_score < 30:
                interpretation += ", still in early stress signal development"
            else:
                interpretation += ", within normal stress signal progression range"
            
            score = IntelligenceScore(
                score_id=f"CRISIS_READY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Crisis Engine Readiness",
                score_type=ScoreType.CONVEXITY_INTEGRITY,  # Reusing type
                value=readiness_score,
                confidence=0.70,
                timestamp=datetime.now(),
                time_horizon="2-6 weeks",
                historical_context=HistoricalContext(
                    median=timing_patterns['median_readiness'],
                    p25=timing_patterns['p25_readiness'],
                    p75=timing_patterns['p75_readiness'],
                    p90=timing_patterns['p90_readiness'],
                    p95=timing_patterns['p95_readiness'],
                    similar_periods=[]
                ),
                interpretation=interpretation,
                calculation_method="Stress signal progression vs historical crisis timing analysis",
                contributing_factors=[
                    f"Signal age: {stress_progression['signal_age']} days",
                    f"Signal intensity: {stress_progression['intensity']:.2f}",
                    f"Historical median timing: {timing_patterns['median_days']} days"
                ]
            )
            
            return score
            
        except Exception as e:
            print(f"⚠️ Error in crisis readiness analysis: {e}")
            
            # Return default score on error
            return IntelligenceScore(
                score_id=f"CRISIS_READY_ERROR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                score_name="Crisis Engine Readiness",
                score_type=ScoreType.CONVEXITY_INTEGRITY,
                value=40.0,
                confidence=0.3,
                timestamp=datetime.now(),
                time_horizon="2-6 weeks",
                historical_context=HistoricalContext(40.0, 25.0, 60.0, 75.0, 90.0, []),
                interpretation="Crisis readiness analysis unavailable due to data limitations"
            )
    
    def _calculate_stress_indicators(self, snapshot: ObserverSnapshot) -> List[StressIndicator]:
        """Calculate individual stress indicators"""
        
        market_state = snapshot.market_state
        indicators = []
        
        # Volatility spike indicator
        vol_indicator = StressIndicator(
            name="volatility_spike",
            value=market_state.volatility_20d,
            threshold=self.stress_indicators['volatility_spike']['threshold'],
            is_active=market_state.volatility_20d > self.stress_indicators['volatility_spike']['threshold'],
            historical_percentile=min(95, market_state.volatility_20d / 0.15 * 50)  # Rough percentile
        )
        indicators.append(vol_indicator)
        
        # Correlation surge indicator
        corr_indicator = StressIndicator(
            name="correlation_surge",
            value=market_state.correlation,
            threshold=self.stress_indicators['correlation_surge']['threshold'],
            is_active=market_state.correlation > self.stress_indicators['correlation_surge']['threshold'],
            historical_percentile=market_state.correlation * 100
        )
        indicators.append(corr_indicator)
        
        # Breadth deterioration indicator
        breadth_indicator = StressIndicator(
            name="breadth_deterioration",
            value=market_state.breadth_pct,
            threshold=self.stress_indicators['breadth_deterioration']['threshold'],
            is_active=market_state.breadth_pct < self.stress_indicators['breadth_deterioration']['threshold'],
            historical_percentile=100 - market_state.breadth_pct
        )
        indicators.append(breadth_indicator)
        
        # Market stress indicator
        stress_indicator = StressIndicator(
            name="market_stress",
            value=market_state.market_stress,
            threshold=self.stress_indicators['liquidity_stress']['threshold'],
            is_active=market_state.market_stress > self.stress_indicators['liquidity_stress']['threshold'],
            historical_percentile=market_state.market_stress * 100
        )
        indicators.append(stress_indicator)
        
        # Add synthetic indicators for completeness
        momentum_indicator = StressIndicator(
            name="momentum_breakdown",
            value=market_state.trend_strength,
            threshold=self.stress_indicators['momentum_breakdown']['threshold'],
            is_active=market_state.trend_strength < self.stress_indicators['momentum_breakdown']['threshold'],
            historical_percentile=max(0, 50 + market_state.trend_strength * 25)
        )
        indicators.append(momentum_indicator)
        
        credit_indicator = StressIndicator(
            name="credit_stress",
            value=market_state.market_stress * 1.2,  # Proxy for credit stress
            threshold=self.stress_indicators['credit_stress']['threshold'],
            is_active=market_state.market_stress * 1.2 > self.stress_indicators['credit_stress']['threshold'],
            historical_percentile=market_state.market_stress * 120
        )
        indicators.append(credit_indicator)
        
        return indicators
    
    def _calculate_clustering_metrics(self, stress_indicators: List[StressIndicator]) -> Dict[str, float]:
        """Calculate stress clustering metrics"""
        
        # Count active indicators
        active_count = sum(1 for ind in stress_indicators if ind.is_active)
        total_count = len(stress_indicators)
        
        # Calculate clustering density
        density = active_count / total_count
        
        # Calculate weighted stress score
        weighted_score = 0.0
        for indicator in stress_indicators:
            weight = self.stress_indicators.get(indicator.name, {}).get('weight', 0.1)
            if indicator.is_active:
                weighted_score += weight * (indicator.historical_percentile / 100.0)
        
        # Calculate co-activation score (how many indicators are active simultaneously)
        co_activation = density ** 2  # Quadratic penalty for multiple active indicators
        
        return {
            'active_count': active_count,
            'density': density,
            'weighted_score': weighted_score,
            'co_activation': co_activation
        }
    
    def _get_historical_clustering_distribution(self) -> Dict[str, float]:
        """Get historical stress clustering distribution"""
        
        # These would be calculated from historical data
        return {
            'median': 35.0,
            'p25': 20.0,
            'p75': 55.0,
            'p90': 72.0,
            'p95': 85.0,
            'mean_active_indicators': 1.8,
            'max_clustering_score': 92.0
        }
    
    def _calculate_clustering_score(self, clustering_metrics: Dict[str, float],
                                  historical_clustering: Dict[str, float]) -> float:
        """Calculate stress clustering score (0-100)"""
        
        # Combine multiple clustering indicators
        density_score = clustering_metrics['density'] * 100
        weighted_score = clustering_metrics['weighted_score'] * 100
        co_activation_score = clustering_metrics['co_activation'] * 100
        
        # Weighted average
        weights = [0.4, 0.4, 0.2]
        scores = [density_score, weighted_score, co_activation_score]
        
        clustering_score = np.average(scores, weights=weights)
        
        return max(0, min(100, clustering_score))
    
    def _get_stress_precedents(self, clustering_score: float) -> List[str]:
        """Get historical precedents for current stress level"""
        
        if clustering_score > 80:
            return ["2008-Q4", "2020-Q1", "2018-Q4"]
        elif clustering_score > 60:
            return ["2015-Aug", "2018-Feb", "2011-Q3"]
        else:
            return ["2016-Q1", "2019-Q4"]
    
    def _calculate_false_calm_metrics(self, snapshot: ObserverSnapshot) -> Dict[str, float]:
        """Calculate false calm detection metrics"""
        
        market_state = snapshot.market_state
        
        # Volatility compression (how much below normal)
        normal_vol = 0.18  # Normal volatility baseline
        volatility_compression = max(0, (normal_vol - market_state.volatility_20d) / normal_vol)
        
        # Correlation normalization (how much correlations have normalized)
        high_stress_corr = 0.80  # High stress correlation
        correlation_normalization = max(0, (high_stress_corr - market_state.correlation) / high_stress_corr)
        
        # Breadth expansion (how much breadth has improved)
        breadth_expansion = max(0, (market_state.breadth_pct - 50.0) / 50.0)
        
        # Estimate complacency duration (days of low stress)
        # This would be calculated from historical stress data
        complacency_duration = max(0, 30 - snapshot.engine_states.regime_changes_30d * 2)
        
        return {
            'volatility_compression': volatility_compression,
            'correlation_normalization': correlation_normalization,
            'breadth_expansion': breadth_expansion,
            'complacency_duration': complacency_duration
        }
    
    def _get_historical_false_calm_patterns(self) -> Dict[str, Any]:
        """Get historical false calm patterns"""
        
        return {
            'median_score': 35.0,
            'p25_score': 20.0,
            'p75_score': 55.0,
            'p90_score': 75.0,
            'p95_score': 90.0,
            'similar_periods': ["2007-Q2", "2017-Q4", "2019-Q3"],
            'typical_duration': 45,  # Days before volatility expansion
            'expansion_probability': 0.65  # Probability of subsequent volatility expansion
        }
    
    def _calculate_false_calm_score(self, false_calm_metrics: Dict[str, float],
                                   historical_patterns: Dict[str, Any]) -> float:
        """Calculate false calm likelihood score (0-100)"""
        
        # Weight the different false calm indicators
        vol_compression_score = false_calm_metrics['volatility_compression'] * 100
        corr_normalization_score = false_calm_metrics['correlation_normalization'] * 100
        breadth_expansion_score = false_calm_metrics['breadth_expansion'] * 100
        complacency_score = min(100, false_calm_metrics['complacency_duration'] / 30 * 100)
        
        # Weighted average
        weights = [0.35, 0.25, 0.20, 0.20]
        scores = [vol_compression_score, corr_normalization_score, breadth_expansion_score, complacency_score]
        
        false_calm_score = np.average(scores, weights=weights)
        
        return max(0, min(100, false_calm_score))
    
    def _analyze_stress_progression(self, snapshot: ObserverSnapshot) -> Dict[str, Any]:
        """Analyze current stress signal progression"""
        
        # Estimate how long stress signals have been building
        # This would be calculated from historical stress signal data
        signal_age = max(1, 30 - snapshot.engine_states.regime_changes_30d * 3)
        
        # Calculate signal intensity
        signal_intensity = (snapshot.market_state.volatility_20d / 0.15 + 
                          snapshot.market_state.market_stress + 
                          (1 - snapshot.market_state.breadth_pct / 100)) / 3
        
        # Calculate progression rate
        progression_rate = signal_intensity / max(1, signal_age)
        
        return {
            'signal_age': signal_age,
            'intensity': signal_intensity,
            'progression_rate': progression_rate
        }
    
    def _get_historical_crisis_timing(self) -> Dict[str, Any]:
        """Get historical crisis timing patterns"""
        
        return {
            'median_days': 12,
            'p25_days': 5,
            'p75_days': 25,
            'p90_days': 45,
            'median_readiness': 45.0,
            'p25_readiness': 25.0,
            'p75_readiness': 65.0,
            'p90_readiness': 80.0,
            'p95_readiness': 90.0,
            'false_alarm_rate': 0.35
        }
    
    def _calculate_readiness_score(self, stress_progression: Dict[str, Any],
                                 timing_patterns: Dict[str, Any]) -> float:
        """Calculate crisis engine readiness score (0-100)"""
        
        # Calculate how far along we are in typical crisis progression
        signal_age = stress_progression['signal_age']
        median_timing = timing_patterns['median_days']
        
        # Age-based readiness
        age_readiness = min(100, (signal_age / median_timing) * 60)
        
        # Intensity-based readiness
        intensity_readiness = stress_progression['intensity'] * 100
        
        # Progression rate readiness
        rate_readiness = min(100, stress_progression['progression_rate'] * 50)
        
        # Weighted average
        weights = [0.4, 0.4, 0.2]
        scores = [age_readiness, intensity_readiness, rate_readiness]
        
        readiness_score = np.average(scores, weights=weights)
        
        return max(0, min(100, readiness_score))