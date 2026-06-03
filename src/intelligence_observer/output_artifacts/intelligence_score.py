#!/usr/bin/env python3
"""
Intelligence Score - Bounded, Non-Imperative Quantitative Intelligence

This module defines the IntelligenceScore class that provides quantitative
intelligence outputs while maintaining strict authority boundaries.

CRITICAL DESIGN PRINCIPLES:
1. All scores are bounded (0-100)
2. Directionality is always "neutral" (never bullish/bearish)
3. Interpretation is descriptive only
4. Forbidden actions are explicitly listed
5. No 1:1 mapping to system triggers
"""

import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

class ScoreType(Enum):
    """Types of intelligence scores"""
    REGIME_SIMILARITY = "regime_similarity"
    REGIME_STABILITY = "regime_stability"
    STRESS_CLUSTERING = "stress_clustering"
    FALSE_CALM_LIKELIHOOD = "false_calm_likelihood"
    CONVEXITY_INTEGRITY = "convexity_integrity"
    BEHAVIORAL_DRIFT = "behavioral_drift"
    ENGINE_PERFORMANCE = "engine_performance"
    PORTFOLIO_CONCENTRATION = "portfolio_concentration"
    LIQUIDITY_FRAGILITY = "liquidity_fragility"

@dataclass
class HistoricalContext:
    """Historical context for score interpretation"""
    median: float
    p25: float
    p75: float
    p90: float
    p95: float
    similar_periods: List[str]
    
    def __post_init__(self):
        """Validate percentiles are ordered correctly"""
        assert self.p25 <= self.median <= self.p75 <= self.p90 <= self.p95

@dataclass
class IntelligenceScore:
    """
    Intelligence Score - Bounded, Non-Imperative Quantitative Intelligence
    
    This class represents a single intelligence score that provides
    quantitative insight while maintaining strict authority boundaries.
    """
    
    # Core identification
    score_id: str
    score_name: str
    score_type: ScoreType
    
    # Score value (MUST be bounded 0-100)
    value: float
    confidence: float
    
    # Temporal context
    timestamp: datetime
    time_horizon: str  # e.g., "4-12 weeks", "1-3 months"
    
    # Historical context
    historical_context: HistoricalContext
    
    # Interpretation (DESCRIPTIVE ONLY)
    interpretation: str
    
    # Authority boundaries (CRITICAL)
    forbidden_actions: List[str] = field(default_factory=lambda: [
        "change_exposure",
        "switch_engine", 
        "modify_thresholds",
        "override_risk_limits",
        "force_rebalance",
        "activate_crisis_mode",
        "increase_position_size",
        "reduce_position_size"
    ])
    
    # Metadata
    data_quality: float = 1.0
    calculation_method: str = ""
    contributing_factors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate score constraints"""
        
        # Validate score bounds
        if not (0.0 <= self.value <= 100.0):
            raise ValueError(f"Score value {self.value} must be between 0 and 100")
        
        # Validate confidence bounds
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be between 0 and 1")
        
        # Validate data quality bounds
        if not (0.0 <= self.data_quality <= 1.0):
            raise ValueError(f"Data quality {self.data_quality} must be between 0 and 1")
        
        # Validate interpretation is descriptive (no imperatives)
        forbidden_words = ['should', 'must', 'will', 'do', 'enter', 'exit', 'increase', 'reduce']
        interpretation_lower = self.interpretation.lower()
        
        for word in forbidden_words:
            if word in interpretation_lower:
                raise ValueError(f"Interpretation contains forbidden imperative word: '{word}'")
        
        # Ensure forbidden actions list is not empty
        if not self.forbidden_actions:
            raise ValueError("Forbidden actions list cannot be empty")
    
    def get_percentile_rank(self) -> str:
        """Get percentile rank description"""
        
        if self.value >= self.historical_context.p95:
            return "95th percentile (extremely high)"
        elif self.value >= self.historical_context.p90:
            return "90th percentile (very high)"
        elif self.value >= self.historical_context.p75:
            return "75th percentile (high)"
        elif self.value >= self.historical_context.median:
            return "above median"
        elif self.value >= self.historical_context.p25:
            return "below median"
        else:
            return "25th percentile (low)"
    
    def get_relative_description(self) -> str:
        """Get relative description vs historical context"""
        
        if self.value > self.historical_context.p90:
            return f"significantly elevated (vs median {self.historical_context.median:.0f})"
        elif self.value > self.historical_context.p75:
            return f"moderately elevated (vs median {self.historical_context.median:.0f})"
        elif self.value > self.historical_context.median:
            return f"slightly above median ({self.historical_context.median:.0f})"
        elif self.value > self.historical_context.p25:
            return f"slightly below median ({self.historical_context.median:.0f})"
        else:
            return f"significantly below median ({self.historical_context.median:.0f})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert score to dictionary for serialization"""
        
        return {
            'score_id': self.score_id,
            'score_name': self.score_name,
            'score_type': self.score_type.value,
            'value': self.value,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'time_horizon': self.time_horizon,
            'historical_context': {
                'median': self.historical_context.median,
                'p25': self.historical_context.p25,
                'p75': self.historical_context.p75,
                'p90': self.historical_context.p90,
                'p95': self.historical_context.p95,
                'similar_periods': self.historical_context.similar_periods
            },
            'interpretation': self.interpretation,
            'percentile_rank': self.get_percentile_rank(),
            'relative_description': self.get_relative_description(),
            'forbidden_actions': self.forbidden_actions,
            'data_quality': self.data_quality,
            'calculation_method': self.calculation_method,
            'contributing_factors': self.contributing_factors
        }
    
    def to_json(self) -> str:
        """Convert score to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntelligenceScore':
        """Create IntelligenceScore from dictionary"""
        
        historical_context = HistoricalContext(
            median=data['historical_context']['median'],
            p25=data['historical_context']['p25'],
            p75=data['historical_context']['p75'],
            p90=data['historical_context']['p90'],
            p95=data['historical_context']['p95'],
            similar_periods=data['historical_context']['similar_periods']
        )
        
        return cls(
            score_id=data['score_id'],
            score_name=data['score_name'],
            score_type=ScoreType(data['score_type']),
            value=data['value'],
            confidence=data['confidence'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            time_horizon=data['time_horizon'],
            historical_context=historical_context,
            interpretation=data['interpretation'],
            forbidden_actions=data.get('forbidden_actions', []),
            data_quality=data.get('data_quality', 1.0),
            calculation_method=data.get('calculation_method', ''),
            contributing_factors=data.get('contributing_factors', [])
        )

class ScoreFactory:
    """Factory for creating standardized intelligence scores"""
    
    @staticmethod
    def create_regime_similarity_score(
        value: float,
        confidence: float,
        similar_periods: List[str],
        historical_percentiles: Dict[str, float]
    ) -> IntelligenceScore:
        """Create regime similarity score"""
        
        historical_context = HistoricalContext(
            median=historical_percentiles.get('median', 42.0),
            p25=historical_percentiles.get('p25', 25.0),
            p75=historical_percentiles.get('p75', 65.0),
            p90=historical_percentiles.get('p90', 78.0),
            p95=historical_percentiles.get('p95', 85.0),
            similar_periods=similar_periods
        )
        
        interpretation = f"Current conditions resemble historically {'unstable' if value > 70 else 'stable'} regimes"
        if similar_periods:
            interpretation += f", particularly {', '.join(similar_periods[:2])}"
        
        return IntelligenceScore(
            score_id=f"REGIME_SIM_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            score_name="Regime Similarity Index",
            score_type=ScoreType.REGIME_SIMILARITY,
            value=value,
            confidence=confidence,
            timestamp=datetime.now(),
            time_horizon="4-12 weeks",
            historical_context=historical_context,
            interpretation=interpretation,
            calculation_method="Multi-dimensional regime embedding similarity"
        )
    
    @staticmethod
    def create_stress_clustering_score(
        value: float,
        confidence: float,
        active_indicators: List[str],
        historical_percentiles: Dict[str, float]
    ) -> IntelligenceScore:
        """Create stress clustering score"""
        
        historical_context = HistoricalContext(
            median=historical_percentiles.get('median', 35.0),
            p25=historical_percentiles.get('p25', 20.0),
            p75=historical_percentiles.get('p75', 55.0),
            p90=historical_percentiles.get('p90', 72.0),
            p95=historical_percentiles.get('p95', 85.0),
            similar_periods=[]
        )
        
        interpretation = f"Stress indicators are {'clustering above' if value > 60 else 'within'} historical baseline"
        if active_indicators:
            interpretation += f". Active: {', '.join(active_indicators[:3])}"
        
        return IntelligenceScore(
            score_id=f"STRESS_CLUST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            score_name="Stress Clustering Index",
            score_type=ScoreType.STRESS_CLUSTERING,
            value=value,
            confidence=confidence,
            timestamp=datetime.now(),
            time_horizon="2-8 weeks",
            historical_context=historical_context,
            interpretation=interpretation,
            contributing_factors=active_indicators,
            calculation_method="Multi-indicator stress co-activation analysis"
        )
    
    @staticmethod
    def create_convexity_integrity_score(
        value: float,
        confidence: float,
        bleed_ratio: float,
        historical_percentiles: Dict[str, float]
    ) -> IntelligenceScore:
        """Create convexity integrity score"""
        
        historical_context = HistoricalContext(
            median=historical_percentiles.get('median', 75.0),
            p25=historical_percentiles.get('p25', 60.0),
            p75=historical_percentiles.get('p75', 85.0),
            p90=historical_percentiles.get('p90', 92.0),
            p95=historical_percentiles.get('p95', 96.0),
            similar_periods=[]
        )
        
        interpretation = f"Crisis convexity appears {'intact' if value > 70 else 'potentially impaired'}"
        if bleed_ratio > 0:
            interpretation += f" with bleed-to-payout ratio of {bleed_ratio:.2f}"
        
        return IntelligenceScore(
            score_id=f"CONVEX_INT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            score_name="Convexity Integrity Score",
            score_type=ScoreType.CONVEXITY_INTEGRITY,
            value=value,
            confidence=confidence,
            timestamp=datetime.now(),
            time_horizon="ongoing",
            historical_context=historical_context,
            interpretation=interpretation,
            calculation_method="Crisis engine payoff asymmetry analysis"
        )