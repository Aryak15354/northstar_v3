#!/usr/bin/env python3
"""
Intelligence Alert - Rate-Limited, Non-Actionable Attention Signals

This module defines the IntelligenceAlert class that provides attention signals
while maintaining strict authority boundaries and rate limiting.

CRITICAL DESIGN PRINCIPLES:
1. Alerts are interruptions, not instructions
2. Rate-limited with cooldown periods
3. Severity ≠ urgency (no HIGH → action mapping)
4. Must include explicitly_not_recommended actions
5. May not reference portfolio actions
6. May not trigger workflows
"""

import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

class AlertType(Enum):
    """Types of intelligence alerts"""
    INFORMATIONAL = "informational"
    MONITORING = "monitoring"
    ANALYTICAL = "analytical"
    STRUCTURAL = "structural"

class AlertSeverity(Enum):
    """Alert severity levels (NOT urgency levels)"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"  # High severity ≠ immediate action required

@dataclass
class AlertCooldown:
    """Alert cooldown configuration"""
    alert_type: str
    cooldown_hours: float
    last_emission: Optional[datetime] = None
    
    def is_cooled_down(self) -> bool:
        """Check if alert has cooled down"""
        if self.last_emission is None:
            return True
        
        elapsed = datetime.now() - self.last_emission
        return elapsed.total_seconds() / 3600 >= self.cooldown_hours
    
    def update_emission(self):
        """Update last emission time"""
        self.last_emission = datetime.now()

@dataclass
class IntelligenceAlert:
    """
    Intelligence Alert - Rate-Limited, Non-Actionable Attention Signal
    
    This class represents an intelligence alert that raises attention
    without triggering action or providing trading instructions.
    """
    
    # Core identification
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    
    # Alert content
    message: str
    timestamp: datetime
    
    # Supporting evidence
    supporting_scores: Dict[str, float] = field(default_factory=dict)
    historical_precedents: List[str] = field(default_factory=list)
    
    # Response guidance (NON-BINDING)
    recommended_response: str = "Increase monitoring vigilance"
    
    # Authority boundaries (CRITICAL)
    explicitly_not_recommended: List[str] = field(default_factory=lambda: [
        "reduce_exposure",
        "activate_crisis_engine",
        "override_system",
        "force_rebalance",
        "modify_risk_limits",
        "switch_engines",
        "increase_position_size",
        "exit_positions"
    ])
    
    # Rate limiting
    cooldown_period_hours: float = 168.0  # 1 week default
    
    # Metadata
    confidence: float = 0.8
    data_quality: float = 1.0
    false_alarm_rate: Optional[float] = None
    
    def __post_init__(self):
        """Validate alert constraints"""
        
        # Validate confidence bounds
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be between 0 and 1")
        
        # Validate data quality bounds
        if not (0.0 <= self.data_quality <= 1.0):
            raise ValueError(f"Data quality {self.data_quality} must be between 0 and 1")
        
        # Validate cooldown period
        if self.cooldown_period_hours <= 0:
            raise ValueError(f"Cooldown period {self.cooldown_period_hours} must be positive")
        
        # Validate message is descriptive (no imperatives)
        forbidden_words = ['must', 'should', 'will', 'do', 'enter', 'exit', 'buy', 'sell']
        message_lower = self.message.lower()
        
        for word in forbidden_words:
            if word in message_lower:
                raise ValueError(f"Alert message contains forbidden imperative word: '{word}'")
        
        # Validate recommended response is non-binding
        response_lower = self.recommended_response.lower()
        action_words = ['trade', 'buy', 'sell', 'enter', 'exit', 'rebalance']
        
        for word in action_words:
            if word in response_lower:
                raise ValueError(f"Recommended response contains forbidden action word: '{word}'")
        
        # Ensure explicitly_not_recommended list is not empty
        if not self.explicitly_not_recommended:
            raise ValueError("Explicitly not recommended actions list cannot be empty")
    
    def get_severity_description(self) -> str:
        """Get human-readable severity description"""
        
        severity_descriptions = {
            AlertSeverity.LOW: "Low severity - routine monitoring",
            AlertSeverity.MEDIUM: "Medium severity - increased attention",
            AlertSeverity.HIGH: "High severity - careful observation (not immediate action)"
        }
        
        return severity_descriptions.get(self.severity, "Unknown severity")
    
    def get_precedent_summary(self) -> str:
        """Get summary of historical precedents"""
        
        if not self.historical_precedents:
            return "No clear historical precedents identified"
        
        if len(self.historical_precedents) == 1:
            return f"Similar to {self.historical_precedents[0]}"
        elif len(self.historical_precedents) <= 3:
            return f"Similar to {', '.join(self.historical_precedents)}"
        else:
            return f"Similar to {', '.join(self.historical_precedents[:2])} and {len(self.historical_precedents)-2} other periods"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization"""
        
        return {
            'alert_id': self.alert_id,
            'alert_type': self.alert_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'supporting_scores': self.supporting_scores,
            'historical_precedents': self.historical_precedents,
            'precedent_summary': self.get_precedent_summary(),
            'recommended_response': self.recommended_response,
            'explicitly_not_recommended': self.explicitly_not_recommended,
            'cooldown_period_hours': self.cooldown_period_hours,
            'confidence': self.confidence,
            'data_quality': self.data_quality,
            'false_alarm_rate': self.false_alarm_rate,
            'severity_description': self.get_severity_description()
        }
    
    def to_json(self) -> str:
        """Convert alert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IntelligenceAlert':
        """Create IntelligenceAlert from dictionary"""
        
        return cls(
            alert_id=data['alert_id'],
            alert_type=AlertType(data['alert_type']),
            severity=AlertSeverity(data['severity']),
            message=data['message'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            supporting_scores=data.get('supporting_scores', {}),
            historical_precedents=data.get('historical_precedents', []),
            recommended_response=data.get('recommended_response', 'Increase monitoring vigilance'),
            explicitly_not_recommended=data.get('explicitly_not_recommended', []),
            cooldown_period_hours=data.get('cooldown_period_hours', 168.0),
            confidence=data.get('confidence', 0.8),
            data_quality=data.get('data_quality', 1.0),
            false_alarm_rate=data.get('false_alarm_rate')
        )

class AlertManager:
    """Manages alert rate limiting and cooldown periods"""
    
    def __init__(self):
        self.cooldowns: Dict[str, AlertCooldown] = {}
        self.emission_history: List[Dict[str, Any]] = []
        
        # Default cooldown periods by alert type
        self.default_cooldowns = {
            'stress_clustering': 24.0,      # 24 hours
            'regime_transition': 48.0,      # 48 hours  
            'false_calm_warning': 72.0,     # 72 hours
            'convexity_degradation': 168.0, # 1 week
            'behavioral_drift': 336.0       # 2 weeks
        }
    
    def can_emit_alert(self, alert_type: str, alert_subtype: str = "") -> bool:
        """Check if alert can be emitted (not in cooldown)"""
        
        cooldown_key = f"{alert_type}_{alert_subtype}" if alert_subtype else alert_type
        
        if cooldown_key not in self.cooldowns:
            # Create new cooldown tracker
            cooldown_hours = self.default_cooldowns.get(alert_type, 168.0)
            self.cooldowns[cooldown_key] = AlertCooldown(
                alert_type=cooldown_key,
                cooldown_hours=cooldown_hours
            )
        
        return self.cooldowns[cooldown_key].is_cooled_down()
    
    def emit_alert(self, alert: IntelligenceAlert) -> bool:
        """Emit alert if not in cooldown period"""
        
        alert_key = f"{alert.alert_type.value}_{alert.alert_id.split('_')[0]}"
        
        if not self.can_emit_alert(alert.alert_type.value, alert.alert_id.split('_')[0]):
            return False
        
        # Update cooldown
        if alert_key in self.cooldowns:
            self.cooldowns[alert_key].update_emission()
        
        # Log emission
        self.emission_history.append({
            'alert_id': alert.alert_id,
            'alert_type': alert.alert_type.value,
            'severity': alert.severity.value,
            'timestamp': alert.timestamp.isoformat(),
            'message': alert.message
        })
        
        # Keep only recent history
        cutoff_time = datetime.now() - timedelta(days=30)
        self.emission_history = [
            h for h in self.emission_history 
            if datetime.fromisoformat(h['timestamp']) > cutoff_time
        ]
        
        return True
    
    def get_emission_stats(self) -> Dict[str, Any]:
        """Get alert emission statistics"""
        
        recent_alerts = [
            h for h in self.emission_history
            if datetime.fromisoformat(h['timestamp']) > datetime.now() - timedelta(days=7)
        ]
        
        return {
            'total_alerts_7d': len(recent_alerts),
            'alerts_by_type': {
                alert_type: len([a for a in recent_alerts if a['alert_type'] == alert_type])
                for alert_type in set(a['alert_type'] for a in recent_alerts)
            },
            'active_cooldowns': len([c for c in self.cooldowns.values() if not c.is_cooled_down()]),
            'last_alert': self.emission_history[-1] if self.emission_history else None
        }

class AlertFactory:
    """Factory for creating standardized intelligence alerts"""
    
    @staticmethod
    def create_stress_clustering_alert(
        stress_score: float,
        active_indicators: List[str],
        historical_precedents: List[str]
    ) -> IntelligenceAlert:
        """Create stress clustering alert"""
        
        severity = AlertSeverity.HIGH if stress_score > 80 else AlertSeverity.MEDIUM
        
        message = f"Stress indicators are clustering above historical baseline (score: {stress_score:.0f})"
        if active_indicators:
            message += f". Active indicators: {', '.join(active_indicators[:3])}"
        
        return IntelligenceAlert(
            alert_id=f"STRESS_CLUSTER_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            alert_type=AlertType.MONITORING,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            supporting_scores={'stress_clustering_index': stress_score},
            historical_precedents=historical_precedents,
            recommended_response="Monitor stress indicators and prepare for potential volatility",
            cooldown_period_hours=24.0,
            confidence=0.85
        )
    
    @staticmethod
    def create_false_calm_alert(
        false_calm_score: float,
        volatility_compression: float,
        historical_precedents: List[str]
    ) -> IntelligenceAlert:
        """Create false calm detection alert"""
        
        severity = AlertSeverity.MEDIUM
        
        message = f"Current conditions resemble historical 'false calm' patterns (score: {false_calm_score:.0f})"
        if volatility_compression > 0.5:
            message += f" with significant volatility compression ({volatility_compression:.1f}x)"
        
        return IntelligenceAlert(
            alert_id=f"FALSE_CALM_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            alert_type=AlertType.ANALYTICAL,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            supporting_scores={
                'false_calm_likelihood': false_calm_score,
                'volatility_compression': volatility_compression
            },
            historical_precedents=historical_precedents,
            recommended_response="Maintain heightened awareness of potential volatility expansion",
            cooldown_period_hours=72.0,
            confidence=0.75
        )
    
    @staticmethod
    def create_behavioral_drift_alert(
        drift_score: float,
        drift_components: List[str]
    ) -> IntelligenceAlert:
        """Create behavioral drift alert"""
        
        severity = AlertSeverity.HIGH if drift_score > 70 else AlertSeverity.MEDIUM
        
        message = f"System behavioral drift detected (score: {drift_score:.0f})"
        if drift_components:
            message += f". Affected components: {', '.join(drift_components[:2])}"
        
        return IntelligenceAlert(
            alert_id=f"BEHAVIORAL_DRIFT_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            alert_type=AlertType.STRUCTURAL,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            supporting_scores={'behavioral_drift_index': drift_score},
            historical_precedents=[],
            recommended_response="Review system integrity and investigate drift causes",
            cooldown_period_hours=336.0,  # 2 weeks
            confidence=0.90
        )