#!/usr/bin/env python3
"""
Intelligence Narrative - Read-Only Contextual Explanations

This module defines the IntelligenceNarrative class that provides contextual
understanding without steering behavior.

CRITICAL DESIGN PRINCIPLES:
1. Narratives are read-only explanations
2. Must include differences, not just similarities
3. Must reference what engines did historically, not what they should do
4. Must include disclaimers
5. Cannot appear in live execution dashboards
"""

import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

class NarrativeType(Enum):
    """Types of intelligence narratives"""
    REGIME_ANALOG = "regime_analog"
    ENGINE_BEHAVIOR = "engine_behavior"
    MARKET_STRUCTURE = "market_structure"
    HISTORICAL_CONTEXT = "historical_context"
    STRESS_ANALYSIS = "stress_analysis"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"

@dataclass
class HistoricalOutcome:
    """Historical outcome data for narrative context"""
    period: str
    outcome_type: str  # e.g., "drawdown", "recovery", "volatility_expansion"
    magnitude: float
    duration_days: int
    recovery_time_days: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'period': self.period,
            'outcome_type': self.outcome_type,
            'magnitude': self.magnitude,
            'duration_days': self.duration_days,
            'recovery_time_days': self.recovery_time_days
        }

@dataclass
class IntelligenceNarrative:
    """
    Intelligence Narrative - Read-Only Contextual Explanation
    
    This class provides contextual understanding and historical perspective
    without providing trading instructions or steering behavior.
    """
    
    # Core identification
    narrative_id: str
    narrative_type: NarrativeType
    title: str
    
    # Narrative content
    summary: str
    timestamp: datetime
    
    # Comparative analysis (REQUIRED)
    key_similarities: List[str] = field(default_factory=list)
    key_differences: List[str] = field(default_factory=list)  # MUST include differences
    
    # Historical context
    historical_outcomes: Dict[str, Any] = field(default_factory=dict)
    comparable_periods: List[str] = field(default_factory=list)
    
    # Engine behavior context (HISTORICAL ONLY)
    engine_behavior_note: str = ""
    
    # Authority boundaries (CRITICAL)
    explicit_disclaimer: str = "This narrative is descriptive only and does not imply system action."
    
    # Metadata
    confidence: float = 0.8
    data_quality: float = 1.0
    sources: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate narrative constraints"""
        
        # Validate confidence bounds
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be between 0 and 1")
        
        # Validate data quality bounds
        if not (0.0 <= self.data_quality <= 1.0):
            raise ValueError(f"Data quality {self.data_quality} must be between 0 and 1")
        
        # Ensure differences are included (critical for balanced analysis)
        if not self.key_differences:
            raise ValueError("Key differences must be included for balanced analysis")
        
        # Validate content is descriptive (no imperatives)
        forbidden_words = ['should', 'must', 'will', 'recommend', 'suggest', 'advise']
        
        for content in [self.summary, self.engine_behavior_note]:
            content_lower = content.lower()
            for word in forbidden_words:
                if word in content_lower:
                    raise ValueError(f"Narrative content contains forbidden word: '{word}'")
        
        # Validate engine behavior note is historical
        if self.engine_behavior_note:
            historical_indicators = ['historically', 'previously', 'in the past', 'typically', 'usually']
            if not any(indicator in self.engine_behavior_note.lower() for indicator in historical_indicators):
                raise ValueError("Engine behavior note must reference historical behavior only")
        
        # Ensure disclaimer is present
        if not self.explicit_disclaimer:
            raise ValueError("Explicit disclaimer is required")
    
    def get_similarity_summary(self) -> str:
        """Get formatted summary of similarities"""
        
        if not self.key_similarities:
            return "No significant similarities identified"
        
        if len(self.key_similarities) <= 3:
            return "; ".join(self.key_similarities)
        else:
            return "; ".join(self.key_similarities[:3]) + f" (and {len(self.key_similarities)-3} others)"
    
    def get_difference_summary(self) -> str:
        """Get formatted summary of differences"""
        
        if not self.key_differences:
            return "No significant differences identified"
        
        if len(self.key_differences) <= 3:
            return "; ".join(self.key_differences)
        else:
            return "; ".join(self.key_differences[:3]) + f" (and {len(self.key_differences)-3} others)"
    
    def get_outcome_summary(self) -> str:
        """Get formatted summary of historical outcomes"""
        
        if not self.historical_outcomes:
            return "Historical outcomes not available"
        
        summary_parts = []
        
        if 'median_drawdown' in self.historical_outcomes:
            summary_parts.append(f"Median drawdown: {self.historical_outcomes['median_drawdown']}")
        
        if 'recovery_time' in self.historical_outcomes:
            summary_parts.append(f"Recovery time: {self.historical_outcomes['recovery_time']}")
        
        if 'volatility_expansion' in self.historical_outcomes:
            summary_parts.append(f"Volatility expansion: {self.historical_outcomes['volatility_expansion']}")
        
        return "; ".join(summary_parts) if summary_parts else "Outcomes varied significantly"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert narrative to dictionary for serialization"""
        
        return {
            'narrative_id': self.narrative_id,
            'narrative_type': self.narrative_type.value,
            'title': self.title,
            'summary': self.summary,
            'timestamp': self.timestamp.isoformat(),
            'key_similarities': self.key_similarities,
            'key_differences': self.key_differences,
            'similarity_summary': self.get_similarity_summary(),
            'difference_summary': self.get_difference_summary(),
            'historical_outcomes': self.historical_outcomes,
            'outcome_summary': self.get_outcome_summary(),
            'comparable_periods': self.comparable_periods,
            'engine_behavior_note': self.engine_behavior_note,
            'explicit_disclaimer': self.explicit_disclaimer,
            'confidence': self.confidence,
            'data_quality': self.data_quality,
            'sources': self.sources
        }
    
    def to_json(self) -> str:
        """Convert narrative to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_markdown(self) -> str:
        """Convert narrative to markdown format for reports"""
        
        md = f"# {self.title}\n\n"
        md += f"**Type:** {self.narrative_type.value.replace('_', ' ').title()}\n"
        md += f"**Generated:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
        md += f"**Confidence:** {self.confidence:.1%}\n\n"
        
        md += f"## Summary\n\n{self.summary}\n\n"
        
        if self.comparable_periods:
            md += f"**Comparable Periods:** {', '.join(self.comparable_periods)}\n\n"
        
        md += f"## Key Similarities\n\n"
        for similarity in self.key_similarities:
            md += f"- {similarity}\n"
        md += "\n"
        
        md += f"## Key Differences\n\n"
        for difference in self.key_differences:
            md += f"- {difference}\n"
        md += "\n"
        
        if self.historical_outcomes:
            md += f"## Historical Outcomes\n\n"
            md += f"{self.get_outcome_summary()}\n\n"
        
        if self.engine_behavior_note:
            md += f"## Engine Behavior Context\n\n"
            md += f"{self.engine_behavior_note}\n\n"
        
        md += f"## Disclaimer\n\n"
        md += f"*{self.explicit_disclaimer}*\n"
        
        return md
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntelligenceNarrative':
        """Create IntelligenceNarrative from dictionary"""
        
        return cls(
            narrative_id=data['narrative_id'],
            narrative_type=NarrativeType(data['narrative_type']),
            title=data['title'],
            summary=data['summary'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            key_similarities=data.get('key_similarities', []),
            key_differences=data.get('key_differences', []),
            historical_outcomes=data.get('historical_outcomes', {}),
            comparable_periods=data.get('comparable_periods', []),
            engine_behavior_note=data.get('engine_behavior_note', ''),
            explicit_disclaimer=data.get('explicit_disclaimer', 
                'This narrative is descriptive only and does not imply system action.'),
            confidence=data.get('confidence', 0.8),
            data_quality=data.get('data_quality', 1.0),
            sources=data.get('sources', [])
        )

class NarrativeFactory:
    """Factory for creating standardized intelligence narratives"""
    
    @staticmethod
    def create_regime_analog_narrative(
        current_regime: str,
        analog_periods: List[str],
        similarities: List[str],
        differences: List[str],
        historical_outcomes: Dict[str, Any]
    ) -> IntelligenceNarrative:
        """Create regime analog narrative"""
        
        title = f"Current Market Conditions vs {analog_periods[0] if analog_periods else 'Historical Periods'}"
        
        summary = f"The current {current_regime} regime configuration shows similarities to "
        if len(analog_periods) == 1:
            summary += f"{analog_periods[0]}"
        elif len(analog_periods) <= 3:
            summary += f"{', '.join(analog_periods[:-1])} and {analog_periods[-1]}"
        else:
            summary += f"{', '.join(analog_periods[:2])} and {len(analog_periods)-2} other periods"
        
        summary += " based on volatility, correlation, and market structure patterns."
        
        engine_note = ""
        if historical_outcomes.get('engine_behavior'):
            engine_note = f"In similar periods, {historical_outcomes['engine_behavior']}"
        
        return IntelligenceNarrative(
            narrative_id=f"REGIME_ANALOG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            narrative_type=NarrativeType.REGIME_ANALOG,
            title=title,
            summary=summary,
            timestamp=datetime.now(),
            key_similarities=similarities,
            key_differences=differences,
            historical_outcomes=historical_outcomes,
            comparable_periods=analog_periods,
            engine_behavior_note=engine_note,
            confidence=0.8
        )
    
    @staticmethod
    def create_stress_analysis_narrative(
        stress_level: str,
        stress_indicators: List[str],
        historical_precedents: List[str],
        typical_outcomes: Dict[str, Any]
    ) -> IntelligenceNarrative:
        """Create stress analysis narrative"""
        
        title = f"Market Stress Analysis - {stress_level.title()} Level"
        
        summary = f"Current market exhibits {stress_level} stress characteristics with "
        summary += f"{len(stress_indicators)} active stress indicators. "
        
        if historical_precedents:
            summary += f"This pattern resembles {', '.join(historical_precedents[:2])}"
            if len(historical_precedents) > 2:
                summary += f" and {len(historical_precedents)-2} other periods"
            summary += "."
        
        similarities = [f"Active stress indicator: {indicator}" for indicator in stress_indicators[:5]]
        
        differences = [
            "Current market structure differs from historical periods",
            "Liquidity conditions may vary from precedents",
            "Policy environment has evolved since historical examples"
        ]
        
        return IntelligenceNarrative(
            narrative_id=f"STRESS_ANALYSIS_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            narrative_type=NarrativeType.STRESS_ANALYSIS,
            title=title,
            summary=summary,
            timestamp=datetime.now(),
            key_similarities=similarities,
            key_differences=differences,
            historical_outcomes=typical_outcomes,
            comparable_periods=historical_precedents,
            confidence=0.75
        )
    
    @staticmethod
    def create_engine_behavior_narrative(
        engine_name: str,
        recent_performance: Dict[str, Any],
        historical_context: Dict[str, Any],
        regime_context: str
    ) -> IntelligenceNarrative:
        """Create engine behavior analysis narrative"""
        
        title = f"{engine_name} Engine Behavior Analysis"
        
        summary = f"The {engine_name} engine has exhibited behavior consistent with {regime_context} "
        summary += f"market conditions. Recent performance metrics align with historical patterns "
        summary += f"for similar market environments."
        
        similarities = []
        differences = []
        
        if recent_performance.get('return_pattern'):
            similarities.append(f"Return pattern: {recent_performance['return_pattern']}")
        
        if recent_performance.get('volatility_behavior'):
            similarities.append(f"Volatility behavior: {recent_performance['volatility_behavior']}")
        
        if historical_context.get('typical_differences'):
            differences.extend(historical_context['typical_differences'])
        else:
            differences = [
                "Current market microstructure differs from historical periods",
                "Regulatory environment has evolved",
                "Market participant composition has changed"
            ]
        
        engine_note = f"Historically, the {engine_name} engine typically "
        if historical_context.get('historical_behavior'):
            engine_note += historical_context['historical_behavior']
        else:
            engine_note += f"performed consistently during {regime_context} regimes"
        
        return IntelligenceNarrative(
            narrative_id=f"ENGINE_BEHAVIOR_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            narrative_type=NarrativeType.ENGINE_BEHAVIOR,
            title=title,
            summary=summary,
            timestamp=datetime.now(),
            key_similarities=similarities,
            key_differences=differences,
            historical_outcomes=historical_context,
            engine_behavior_note=engine_note,
            confidence=0.85
        )