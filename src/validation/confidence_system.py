#!/usr/bin/env python3
"""
Confidence System - Phase 5: Infrastructure Layer
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

class ConfidenceType(Enum):
    REGIME_DETECTION = "regime_detection"
    STRATEGY_TAILWINDS = "strategy_tailwinds"
    ALLOCATION_DECISIONS = "allocation_decisions"

class ConfidenceLevel(Enum):
    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"

@dataclass
class BeliefConfidence:
    timestamp: datetime
    output_type: ConfidenceType
    output_value: Any
    confidence_score: float
    confidence_sources: Dict[str, float]
    confidence_level: ConfidenceLevel
    uncertainty_factors: List[str]
    data_freshness_hours: float
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['timestamp'] = result['timestamp'].isoformat()
        result['output_type'] = result['output_type'].value
        result['confidence_level'] = result['confidence_level'].value
        if not isinstance(result['output_value'], (str, int, float, bool, type(None))):
            result['output_value'] = str(result['output_value'])
        return result
    
    def validate(self) -> List[str]:
        errors = []
        if not (0.0 <= self.confidence_score <= 1.0):
            errors.append(f"Confidence score {self.confidence_score} outside bounds [0.0, 1.0]")
        if not isinstance(self.confidence_sources, dict):
            errors.append("Confidence sources must be a dictionary")
        else:
            for source, value in self.confidence_sources.items():
                if not (0.0 <= float(value) <= 1.0):
                    errors.append(f"Source confidence {source}={value} outside bounds [0.0, 1.0]")
        if not isinstance(self.uncertainty_factors, list):
            errors.append("Uncertainty factors must be a list")
        if self.data_freshness_hours < 0:
            errors.append("Data freshness hours cannot be negative")
        return errors

@dataclass
class ConfidenceThresholds:
    exposure_reduction_threshold: float = 0.5
    no_edge_threshold: float = 0.3
    narrative_uncertainty_threshold: float = 0.6
    data_freshness_max_hours: float = 24.0

    def validate(self) -> List[str]:
        errors = []
        if not (0.0 <= self.exposure_reduction_threshold <= 1.0):
            errors.append(
                f"exposure_reduction_threshold {self.exposure_reduction_threshold} outside bounds [0.0, 1.0]"
            )
        if not (0.0 <= self.no_edge_threshold <= 1.0):
            errors.append(
                f"no_edge_threshold {self.no_edge_threshold} outside bounds [0.0, 1.0]"
            )
        if not (0.0 <= self.narrative_uncertainty_threshold <= 1.0):
            errors.append(
                f"narrative_uncertainty_threshold {self.narrative_uncertainty_threshold} outside bounds [0.0, 1.0]"
            )
        if self.data_freshness_max_hours <= 0:
            errors.append("Data freshness max hours must be positive")
        return errors

class ConfidenceSystem:
    def __init__(self, base_dir: str = "data/intelligence", thresholds=None):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.thresholds = thresholds or ConfidenceThresholds()
        self.current_confidences = {}
        self.confidence_history = []
        self.risk_coordinator = None
        print("🎯 Confidence System initialized")
    
    def compute_regime_confidence(self, regime_similarity: float, similarity_dispersion: float, regime_stability_days: int = 30) -> float:
        similarity_confidence = min(regime_similarity, 1.0)
        dispersion_penalty = min(similarity_dispersion * 2.0, 0.3)
        dispersion_confidence = max(0.0, 1.0 - dispersion_penalty)
        stability_bonus = min(regime_stability_days / 60.0, 0.2)
        stability_confidence = min(1.0, 0.8 + stability_bonus)
        
        regime_confidence = (
            0.5 * similarity_confidence +
            0.3 * dispersion_confidence +
            0.2 * stability_confidence
        )
        return max(0.0, min(1.0, regime_confidence))
    
    def compute_tailwind_confidence(self, beta_drift_consistency: float, signal_strength: float, data_coverage: float) -> float:
        consistency_confidence = min(beta_drift_consistency, 1.0)
        strength_confidence = min(signal_strength, 1.0)
        coverage_confidence = min(data_coverage, 1.0)
        
        tailwind_confidence = (
            0.4 * consistency_confidence +
            0.4 * strength_confidence +
            0.2 * coverage_confidence
        )
        return max(0.0, min(1.0, tailwind_confidence))
    
    def compute_allocation_confidence(self, regime_confidence: float, tailwind_confidence: float, data_freshness_hours: float) -> float:
        base_confidence = (regime_confidence + tailwind_confidence) / 2.0
        freshness_penalty = min(data_freshness_hours / self.thresholds.data_freshness_max_hours, 1.0)
        freshness_confidence = max(0.0, 1.0 - freshness_penalty)
        allocation_confidence = base_confidence * freshness_confidence
        return max(0.0, min(1.0, allocation_confidence))
    
    def _classify_confidence_level(self, confidence_score: float) -> ConfidenceLevel:
        if confidence_score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def update_belief_confidence(self, output_type: str, output_value: Any, confidence_score: float, confidence_sources: Dict[str, float], data_freshness_hours: float = 0.0) -> BeliefConfidence:
        print(f"🎯 Updating belief confidence: {output_type}")
        
        confidence_type = ConfidenceType(output_type)
        confidence_level = self._classify_confidence_level(confidence_score)
        uncertainty_factors = [
            f"Low {k.replace('_', ' ')} ({v:.2f})"
            for k, v in confidence_sources.items()
            if v < 0.5
        ]
        
        belief_confidence = BeliefConfidence(
            timestamp=datetime.now(),
            output_type=confidence_type,
            output_value=output_value,
            confidence_score=confidence_score,
            confidence_sources=confidence_sources,
            confidence_level=confidence_level,
            uncertainty_factors=uncertainty_factors,
            data_freshness_hours=data_freshness_hours
        )
        
        self.current_confidences[output_type] = belief_confidence
        self.confidence_history.append(belief_confidence)

        # Persist confidence history for schema/audit checks.
        try:
            parquet_file = os.path.join(self.base_dir, "belief_confidence.parquet")
            new_row = pd.DataFrame([belief_confidence.to_dict()])
            new_row['timestamp'] = pd.to_datetime(new_row['timestamp'])

            if os.path.exists(parquet_file):
                existing = pd.read_parquet(parquet_file)
                combined = pd.concat([existing, new_row], ignore_index=True)
            else:
                combined = new_row

            combined.to_parquet(parquet_file, index=False)
        except Exception:
            # Keep runtime robust in restricted environments.
            pass

        # Trigger risk-side confidence controls when available.
        if self.risk_coordinator is not None:
            reason = f"Low confidence in {output_type} ({confidence_score:.3f})"
            confidence_factors = confidence_sources

            if confidence_score < self.thresholds.no_edge_threshold:
                if hasattr(self.risk_coordinator, "enter_no_edge_state"):
                    self.risk_coordinator.enter_no_edge_state(
                        reason=reason,
                        confidence_factors=confidence_factors
                    )
            elif confidence_score < self.thresholds.exposure_reduction_threshold:
                # Scale exposure down linearly and cap at 60% as institutional guardrail.
                reduction_ratio = confidence_score / max(self.thresholds.exposure_reduction_threshold, 1e-9)
                new_exposure = max(0.0, min(0.6, 0.6 * reduction_ratio))

                if hasattr(self.risk_coordinator, "suggest_exposure_reduction"):
                    self.risk_coordinator.suggest_exposure_reduction(
                        new_exposure=new_exposure,
                        reason=reason,
                        confidence_factors=confidence_factors
                    )
        
        return belief_confidence
    
    def should_add_uncertainty_language(self, output_type: str) -> Tuple[bool, str]:
        if output_type not in self.current_confidences:
            return True, "Insufficient data for confidence assessment"
        
        belief_confidence = self.current_confidences[output_type]
        
        if belief_confidence.confidence_score < self.thresholds.narrative_uncertainty_threshold:
            if belief_confidence.confidence_level == ConfidenceLevel.VERY_HIGH:
                return False, "Very high confidence - strong conviction"
            elif belief_confidence.confidence_level == ConfidenceLevel.HIGH:
                return False, "High confidence - good conviction"
            elif belief_confidence.confidence_level == ConfidenceLevel.MEDIUM:
                return True, "Medium confidence - moderate uncertainty"
            elif belief_confidence.confidence_level == ConfidenceLevel.LOW:
                return True, "Low confidence - significant uncertainty"
            else:
                return True, "Very low confidence - high uncertainty, defensive positioning recommended"
        
        return False, ""
    
    def get_confidence_summary(self) -> Dict[str, Any]:
        summary = {
            'timestamp': datetime.now().isoformat(),
            'current_confidences': {},
            'overall_confidence': 0.0,
            'exposure_reduction_needed': False,
            'no_edge_state': False,
            'uncertainty_narrative_needed': False
        }
        
        if not self.current_confidences:
            summary['overall_confidence'] = 0.0
            summary['no_edge_state'] = True
            return summary
        
        confidence_scores = []
        for output_type, belief_confidence in self.current_confidences.items():
            summary['current_confidences'][output_type] = {
                'confidence_score': belief_confidence.confidence_score,
                'confidence_level': belief_confidence.confidence_level.value,
                'uncertainty_factors': belief_confidence.uncertainty_factors,
                'data_freshness_hours': belief_confidence.data_freshness_hours
            }
            confidence_scores.append(belief_confidence.confidence_score)
        
        summary['overall_confidence'] = np.mean(confidence_scores)
        summary['no_edge_state'] = summary['overall_confidence'] < self.thresholds.no_edge_threshold
        summary['exposure_reduction_needed'] = summary['overall_confidence'] < self.thresholds.exposure_reduction_threshold
        summary['uncertainty_narrative_needed'] = summary['overall_confidence'] < self.thresholds.narrative_uncertainty_threshold
        
        return summary

def main():
    print("🎯 CONFIDENCE SYSTEM - DEMONSTRATION")
    confidence = ConfidenceSystem(base_dir="data/test_confidence")
    
    regime_confidence = confidence.compute_regime_confidence(
        regime_similarity=0.85,
        similarity_dispersion=0.15,
        regime_stability_days=45
    )
    print(f"Regime confidence: {regime_confidence:.3f}")
    
    confidence.update_belief_confidence(
        output_type="regime_detection",
        output_value="late_expansion",
        confidence_score=regime_confidence,
        confidence_sources={"regime_similarity": 0.85, "stability": 0.75},
        data_freshness_hours=2.5
    )
    
    summary = confidence.get_confidence_summary()
    print(f"Overall confidence: {summary['overall_confidence']:.3f}")
    print("✅ Confidence System demonstration complete")

if __name__ == "__main__":
    main()
