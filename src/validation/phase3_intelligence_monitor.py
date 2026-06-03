"""
Phase 3 Intelligence Monitor

Real-time monitoring system for Phase 3 intelligence components:
- Regime classification and confidence tracking
- Tailwind changes and momentum monitoring  
- NO_EDGE state duration and frequency tracking
- Anticipatory positioning lead times and accuracy

This monitor provides real-time visibility into the effectiveness of Phase 3
anticipatory intelligence components, enabling operational confidence and
performance optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import deque, defaultdict
import numpy as np
import pandas as pd

from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector
from src.intelligence.anticipatory_capital_allocator import AnticipatoryCapitalAllocator
from src.core.events import EventBus
from src.core.state import UnifiedState

logger = logging.getLogger(__name__)

@dataclass
class RegimeMonitoringState:
    """Current regime monitoring state"""
    current_regime: Optional[str] = None
    confidence_score: float = 0.0
    similarity_score: float = 0.0
    regime_duration: int = 0  # periods in current regime
    last_transition: Optional[datetime] = None
    transition_frequency: float = 0.0  # transitions per period
    confidence_history: deque = field(default_factory=lambda: deque(maxlen=100))
    regime_history: deque = field(default_factory=lambda: deque(maxlen=50))

@dataclass
class TailwindMonitoringState:
    """Current tailwind monitoring state"""
    current_tailwinds: Dict[str, float] = field(default_factory=dict)
    tailwind_momentum: Dict[str, float] = field(default_factory=dict)
    tailwind_changes: Dict[str, float] = field(default_factory=dict)
    significant_changes: List[Tuple[str, float, float]] = field(default_factory=list)  # (component, old, new)
    momentum_history: Dict[str, deque] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=50)))
    change_frequency: float = 0.0  # significant changes per period

@dataclass
class NoEdgeMonitoringState:
    """Current NO_EDGE monitoring state"""
    is_no_edge: bool = False
    no_edge_duration: int = 0  # periods in NO_EDGE state
    no_edge_frequency: float = 0.0  # NO_EDGE activations per period
    last_activation: Optional[datetime] = None
    last_deactivation: Optional[datetime] = None
    activation_triggers: List[str] = field(default_factory=list)
    activation_history: deque = field(default_factory=lambda: deque(maxlen=100))
    trigger_frequency: Dict[str, int] = field(default_factory=dict)

@dataclass
class AnticipatoryMonitoringState:
    """Current anticipatory positioning monitoring state"""
    current_positions: Dict[str, float] = field(default_factory=dict)
    position_changes: Dict[str, float] = field(default_factory=dict)
    lead_times: Dict[str, int] = field(default_factory=dict)  # periods ahead of market
    accuracy_scores: Dict[str, float] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    positioning_history: deque = field(default_factory=lambda: deque(maxlen=100))
    accuracy_history: deque = field(default_factory=lambda: deque(maxlen=50))

@dataclass
class Phase3IntelligenceSnapshot:
    """Complete snapshot of Phase 3 intelligence state"""
    timestamp: datetime
    regime_state: RegimeMonitoringState
    tailwind_state: TailwindMonitoringState
    no_edge_state: NoEdgeMonitoringState
    anticipatory_state: AnticipatoryMonitoringState
    overall_health_score: float = 0.0
    anomaly_flags: List[str] = field(default_factory=list)

class Phase3IntelligenceMonitor:
    """
    Real-time monitor for Phase 3 intelligence effectiveness
    
    Tracks:
    - Regime classification confidence and transitions
    - Tailwind momentum and significant changes
    - NO_EDGE state activations and triggers
    - Anticipatory positioning accuracy and lead times
    """
    
    def __init__(self, 
                 regime_memory: RegimeMemorySystem,
                 tailwind_engine: SimpleTailwindEngine,
                 no_edge_detector: NoEdgeDetector,
                 anticipatory_allocator: AnticipatoryCapitalAllocator,
                 event_bus: EventBus,
                 unified_state: UnifiedState,
                 monitoring_window: int = 100):
        """
        Initialize Phase 3 intelligence monitor
        
        Args:
            regime_memory: Phase 3 regime memory system
            tailwind_engine: Phase 3 tailwind engine
            no_edge_detector: Phase 3 NO_EDGE detector
            anticipatory_allocator: Phase 3 anticipatory allocator
            event_bus: System event bus
            unified_state: System unified state
            monitoring_window: Number of periods to track in history
        """
        self.regime_memory = regime_memory
        self.tailwind_engine = tailwind_engine
        self.no_edge_detector = no_edge_detector
        self.anticipatory_allocator = anticipatory_allocator
        self.event_bus = event_bus
        self.unified_state = unified_state
        self.monitoring_window = monitoring_window
        
        # Initialize monitoring states
        self.regime_state = RegimeMonitoringState()
        self.tailwind_state = TailwindMonitoringState()
        self.no_edge_state = NoEdgeMonitoringState()
        self.anticipatory_state = AnticipatoryMonitoringState()
        
        # Historical snapshots
        self.snapshots: deque = deque(maxlen=monitoring_window)
        
        # Anomaly detection thresholds
        self.confidence_threshold = 0.3  # Below this is concerning
        self.change_threshold = 0.1  # Above this is significant change
        self.frequency_threshold = 0.2  # Above this is high frequency
        
        # Performance tracking
        self.total_periods = 0
        self.regime_transitions = 0
        self.no_edge_activations = 0
        self.significant_tailwind_changes = 0
        
        logger.info("Phase3IntelligenceMonitor initialized")
    
    def update_monitoring_state(self, market_data: pd.DataFrame) -> Phase3IntelligenceSnapshot:
        """
        Update monitoring state with latest market data
        
        Args:
            market_data: Latest market data
            
        Returns:
            Complete intelligence snapshot
        """
        try:
            timestamp = datetime.now()
            self.total_periods += 1
            
            # Update regime monitoring
            self._update_regime_monitoring(market_data)
            
            # Update tailwind monitoring
            self._update_tailwind_monitoring(market_data)
            
            # Update NO_EDGE monitoring
            self._update_no_edge_monitoring(market_data)
            
            # Update anticipatory monitoring
            self._update_anticipatory_monitoring(market_data)
            
            # Calculate overall health score
            health_score = self._calculate_health_score()
            
            # Detect anomalies
            anomaly_flags = self._detect_anomalies()
            
            # Create snapshot
            snapshot = Phase3IntelligenceSnapshot(
                timestamp=timestamp,
                regime_state=self.regime_state,
                tailwind_state=self.tailwind_state,
                no_edge_state=self.no_edge_state,
                anticipatory_state=self.anticipatory_state,
                overall_health_score=health_score,
                anomaly_flags=anomaly_flags
            )
            
            # Store snapshot
            self.snapshots.append(snapshot)
            
            # Emit monitoring event
            self.event_bus.emit('phase3_intelligence_updated', {
                'snapshot': snapshot,
                'health_score': health_score,
                'anomalies': anomaly_flags
            })
            
            logger.debug(f"Phase 3 intelligence monitoring updated - Health: {health_score:.3f}")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error updating Phase 3 intelligence monitoring: {e}")
            raise
    
    def _update_regime_monitoring(self, market_data: pd.DataFrame):
        """Update regime monitoring state"""
        try:
            # Get current regime classification
            regime_result = self.regime_memory.classify_current_regime(market_data)
            
            if regime_result:
                current_regime = regime_result.get('regime_name')
                confidence = regime_result.get('confidence', 0.0)
                similarity = regime_result.get('similarity_score', 0.0)
                
                # Check for regime transition
                if (self.regime_state.current_regime and 
                    self.regime_state.current_regime != current_regime):
                    self.regime_transitions += 1
                    self.regime_state.last_transition = datetime.now()
                    self.regime_state.regime_duration = 0
                else:
                    self.regime_state.regime_duration += 1
                
                # Update state
                self.regime_state.current_regime = current_regime
                self.regime_state.confidence_score = confidence
                self.regime_state.similarity_score = similarity
                
                # Update histories
                self.regime_state.confidence_history.append(confidence)
                self.regime_state.regime_history.append(current_regime)
                
                # Calculate transition frequency
                if self.total_periods > 0:
                    self.regime_state.transition_frequency = self.regime_transitions / self.total_periods
                    
        except Exception as e:
            logger.warning(f"Error updating regime monitoring: {e}")
    
    def _update_tailwind_monitoring(self, market_data: pd.DataFrame):
        """Update tailwind monitoring state"""
        try:
            # Get current tailwinds
            tailwinds = self.tailwind_engine.calculate_tailwinds(market_data)
            
            if tailwinds:
                # Calculate changes from previous
                previous_tailwinds = self.tailwind_state.current_tailwinds.copy()
                
                for component, value in tailwinds.items():
                    # Calculate change
                    previous_value = previous_tailwinds.get(component, value)
                    change = value - previous_value
                    self.tailwind_state.tailwind_changes[component] = change
                    
                    # Check for significant change
                    if abs(change) > self.change_threshold:
                        self.tailwind_state.significant_changes.append(
                            (component, previous_value, value)
                        )
                        self.significant_tailwind_changes += 1
                    
                    # Calculate momentum (rate of change)
                    momentum_history = self.tailwind_state.momentum_history[component]
                    momentum_history.append(change)
                    
                    if len(momentum_history) >= 2:
                        recent_changes = list(momentum_history)[-5:]  # Last 5 periods
                        momentum = np.mean(recent_changes) if recent_changes else 0.0
                        self.tailwind_state.tailwind_momentum[component] = momentum
                
                # Update current tailwinds
                self.tailwind_state.current_tailwinds = tailwinds
                
                # Calculate change frequency
                if self.total_periods > 0:
                    self.tailwind_state.change_frequency = (
                        self.significant_tailwind_changes / self.total_periods
                    )
                    
        except Exception as e:
            logger.warning(f"Error updating tailwind monitoring: {e}")
    
    def _update_no_edge_monitoring(self, market_data: pd.DataFrame):
        """Update NO_EDGE monitoring state"""
        try:
            # Get current NO_EDGE state
            no_edge_result = self.no_edge_detector.detect_no_edge_state(market_data)
            
            if no_edge_result:
                is_no_edge = no_edge_result.get('is_no_edge', False)
                triggers = no_edge_result.get('triggers', [])
                
                # Check for state change
                if is_no_edge and not self.no_edge_state.is_no_edge:
                    # Entering NO_EDGE state
                    self.no_edge_activations += 1
                    self.no_edge_state.last_activation = datetime.now()
                    self.no_edge_state.no_edge_duration = 1
                    self.no_edge_state.activation_triggers = triggers
                    
                    # Update trigger frequency
                    for trigger in triggers:
                        self.no_edge_state.trigger_frequency[trigger] = (
                            self.no_edge_state.trigger_frequency.get(trigger, 0) + 1
                        )
                        
                elif not is_no_edge and self.no_edge_state.is_no_edge:
                    # Exiting NO_EDGE state
                    self.no_edge_state.last_deactivation = datetime.now()
                    self.no_edge_state.no_edge_duration = 0
                    
                elif is_no_edge:
                    # Continuing in NO_EDGE state
                    self.no_edge_state.no_edge_duration += 1
                
                # Update state
                self.no_edge_state.is_no_edge = is_no_edge
                self.no_edge_state.activation_history.append(is_no_edge)
                
                # Calculate activation frequency
                if self.total_periods > 0:
                    self.no_edge_state.no_edge_frequency = (
                        self.no_edge_activations / self.total_periods
                    )
                    
        except Exception as e:
            logger.warning(f"Error updating NO_EDGE monitoring: {e}")
    
    def _update_anticipatory_monitoring(self, market_data: pd.DataFrame):
        """Update anticipatory positioning monitoring state"""
        try:
            # Get current anticipatory allocations
            allocations = self.anticipatory_allocator.get_current_allocations()
            
            if allocations:
                # Calculate position changes
                previous_positions = self.anticipatory_state.current_positions.copy()
                
                for asset, allocation in allocations.items():
                    previous_allocation = previous_positions.get(asset, 0.0)
                    change = allocation - previous_allocation
                    self.anticipatory_state.position_changes[asset] = change
                
                # Update current positions
                self.anticipatory_state.current_positions = allocations
                
                # Get confidence scores if available
                confidence_scores = getattr(self.anticipatory_allocator, 'confidence_scores', {})
                self.anticipatory_state.confidence_scores = confidence_scores
                
                # Store positioning history
                self.anticipatory_state.positioning_history.append({
                    'timestamp': datetime.now(),
                    'positions': allocations.copy(),
                    'confidence': confidence_scores.copy()
                })
                
                # Calculate accuracy scores (simplified - would need actual performance data)
                # This is a placeholder for more sophisticated accuracy calculation
                for asset in allocations:
                    # Placeholder accuracy calculation
                    recent_confidence = confidence_scores.get(asset, 0.5)
                    self.anticipatory_state.accuracy_scores[asset] = recent_confidence
                
                # Update accuracy history
                if self.anticipatory_state.accuracy_scores:
                    avg_accuracy = np.mean(list(self.anticipatory_state.accuracy_scores.values()))
                    self.anticipatory_state.accuracy_history.append(avg_accuracy)
                    
        except Exception as e:
            logger.warning(f"Error updating anticipatory monitoring: {e}")
    
    def _calculate_health_score(self) -> float:
        """Calculate overall Phase 3 intelligence health score"""
        try:
            scores = []
            
            # Regime health (confidence and stability)
            if self.regime_state.confidence_score > 0:
                regime_score = min(self.regime_state.confidence_score * 2, 1.0)  # Scale up confidence
                scores.append(regime_score)
            
            # Tailwind health (momentum consistency)
            if self.tailwind_state.tailwind_momentum:
                momentum_values = list(self.tailwind_state.tailwind_momentum.values())
                momentum_consistency = 1.0 - min(np.std(momentum_values), 1.0)  # Lower std = higher score
                scores.append(momentum_consistency)
            
            # NO_EDGE health (appropriate frequency)
            no_edge_score = 1.0
            if self.no_edge_state.no_edge_frequency > self.frequency_threshold:
                no_edge_score = max(0.0, 1.0 - self.no_edge_state.no_edge_frequency)
            scores.append(no_edge_score)
            
            # Anticipatory health (confidence and accuracy)
            if self.anticipatory_state.confidence_scores:
                avg_confidence = np.mean(list(self.anticipatory_state.confidence_scores.values()))
                scores.append(avg_confidence)
            
            # Overall health is weighted average
            if scores:
                return np.mean(scores)
            else:
                return 0.5  # Neutral score if no data
                
        except Exception as e:
            logger.warning(f"Error calculating health score: {e}")
            return 0.0
    
    def _detect_anomalies(self) -> List[str]:
        """Detect anomalies in Phase 3 intelligence"""
        anomalies = []
        
        try:
            # Low regime confidence
            if self.regime_state.confidence_score < self.confidence_threshold:
                anomalies.append(f"Low regime confidence: {self.regime_state.confidence_score:.3f}")
            
            # High regime transition frequency
            if self.regime_state.transition_frequency > self.frequency_threshold:
                anomalies.append(f"High regime transition frequency: {self.regime_state.transition_frequency:.3f}")
            
            # High tailwind change frequency
            if self.tailwind_state.change_frequency > self.frequency_threshold:
                anomalies.append(f"High tailwind change frequency: {self.tailwind_state.change_frequency:.3f}")
            
            # Extended NO_EDGE duration
            if self.no_edge_state.no_edge_duration > 10:  # More than 10 periods
                anomalies.append(f"Extended NO_EDGE duration: {self.no_edge_state.no_edge_duration} periods")
            
            # Low anticipatory confidence
            if self.anticipatory_state.confidence_scores:
                avg_confidence = np.mean(list(self.anticipatory_state.confidence_scores.values()))
                if avg_confidence < self.confidence_threshold:
                    anomalies.append(f"Low anticipatory confidence: {avg_confidence:.3f}")
            
        except Exception as e:
            logger.warning(f"Error detecting anomalies: {e}")
        
        return anomalies
    
    def get_current_snapshot(self) -> Optional[Phase3IntelligenceSnapshot]:
        """Get the most recent intelligence snapshot"""
        return self.snapshots[-1] if self.snapshots else None
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get comprehensive monitoring summary"""
        try:
            current_snapshot = self.get_current_snapshot()
            
            if not current_snapshot:
                return {"status": "no_data"}
            
            # Calculate trend indicators
            regime_confidence_trend = self._calculate_trend(
                list(self.regime_state.confidence_history)
            )
            
            health_trend = self._calculate_trend([
                s.overall_health_score for s in list(self.snapshots)[-10:]
            ])
            
            return {
                "status": "active",
                "timestamp": current_snapshot.timestamp,
                "overall_health": current_snapshot.overall_health_score,
                "health_trend": health_trend,
                "regime": {
                    "current": self.regime_state.current_regime,
                    "confidence": self.regime_state.confidence_score,
                    "confidence_trend": regime_confidence_trend,
                    "duration": self.regime_state.regime_duration,
                    "transition_frequency": self.regime_state.transition_frequency
                },
                "tailwinds": {
                    "current": dict(self.tailwind_state.current_tailwinds),
                    "momentum": dict(self.tailwind_state.tailwind_momentum),
                    "change_frequency": self.tailwind_state.change_frequency,
                    "recent_changes": len(self.tailwind_state.significant_changes)
                },
                "no_edge": {
                    "active": self.no_edge_state.is_no_edge,
                    "duration": self.no_edge_state.no_edge_duration,
                    "frequency": self.no_edge_state.no_edge_frequency,
                    "triggers": dict(self.no_edge_state.trigger_frequency)
                },
                "anticipatory": {
                    "positions": dict(self.anticipatory_state.current_positions),
                    "confidence": dict(self.anticipatory_state.confidence_scores),
                    "accuracy": dict(self.anticipatory_state.accuracy_scores)
                },
                "anomalies": current_snapshot.anomaly_flags,
                "total_periods": self.total_periods
            }
            
        except Exception as e:
            logger.error(f"Error generating monitoring summary: {e}")
            return {"status": "error", "error": str(e)}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from recent values"""
        if len(values) < 3:
            return "insufficient_data"
        
        recent = values[-5:]  # Last 5 values
        if len(recent) < 2:
            return "insufficient_data"
        
        # Simple linear trend
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]
        
        if slope > 0.01:
            return "improving"
        elif slope < -0.01:
            return "declining"
        else:
            return "stable"
    
    def reset_monitoring(self):
        """Reset monitoring state (for testing)"""
        self.regime_state = RegimeMonitoringState()
        self.tailwind_state = TailwindMonitoringState()
        self.no_edge_state = NoEdgeMonitoringState()
        self.anticipatory_state = AnticipatoryMonitoringState()
        self.snapshots.clear()
        self.total_periods = 0
        self.regime_transitions = 0
        self.no_edge_activations = 0
        self.significant_tailwind_changes = 0
        
        logger.info("Phase 3 intelligence monitoring reset")