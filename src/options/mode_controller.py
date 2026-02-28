"""
Mode Controller for Northstar V2

Manages system mode state machine: normal -> governance_constrained -> survival_core -> recovery
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class SystemMode(Enum):
    """System operating modes"""
    NORMAL_OPERATION = "normal_operation"
    GOVERNANCE_CONSTRAINED = "governance_constrained"
    SURVIVAL_CORE = "survival_core"
    RECOVERY_MODE = "recovery_mode"


class RiskMode(Enum):
    """Risk management modes"""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class ModeController:
    """Controls system mode transitions and constraints"""
    
    def __init__(self):
        self.current_mode = SystemMode.NORMAL_OPERATION
        self.mode_history = []
        self.mode_entered_at = datetime.now()
        self.constraints_active = {}
        
        # Mode transition thresholds
        self.thresholds = {
            'governance_constrained': {
                'drift_elevated': True,
                'fallback_tier_gte': 2,
                'sdi_threshold': 0.4,
                'drawdown_threshold': 0.08
            },
            'survival_core': {
                'crisis_probability_high': True,
                'convexity_breach': True,
                'drawdown_threshold': 0.12,
                'gap_shock_trigger': True
            },
            'recovery_mode': {
                'corrupted_state': True,
                'wal_interrupted': True,
                'manual_trigger': True
            }
        }
    
    def evaluate_mode_transition(self, system_state: Dict[str, Any]) -> Tuple[SystemMode, List[str]]:
        """
        Evaluate if mode transition is needed
        
        Returns: (new_mode, reasons)
        """
        current_mode = self.current_mode
        reasons = []
        
        # Check for recovery mode triggers (highest priority)
        if self._check_recovery_triggers(system_state):
            reasons.append("State corruption or WAL interruption detected")
            return SystemMode.RECOVERY_MODE, reasons
        
        # Check for survival core triggers
        if self._check_survival_triggers(system_state):
            reasons.extend(self._get_survival_reasons(system_state))
            return SystemMode.SURVIVAL_CORE, reasons
        
        # Check for governance constrained triggers
        if self._check_governance_triggers(system_state):
            reasons.extend(self._get_governance_reasons(system_state))
            return SystemMode.GOVERNANCE_CONSTRAINED, reasons
        
        # Check if we can return to normal
        if current_mode != SystemMode.NORMAL_OPERATION:
            if self._check_normal_conditions(system_state):
                reasons.append("Conditions normalized")
                return SystemMode.NORMAL_OPERATION, reasons
        
        return current_mode, []
    
    def _check_recovery_triggers(self, system_state: Dict[str, Any]) -> bool:
        """Check if recovery mode should be triggered"""
        # State corruption
        integrity_status = system_state.get('integrity_status')
        if integrity_status == 'corrupted':
            return True
        
        # WAL interrupted operations
        interrupted_ops = system_state.get('interrupted_operations', [])
        if interrupted_ops:
            return True
        
        # Manual recovery trigger
        if system_state.get('manual_recovery_trigger', False):
            return True
        
        return False
    
    def _check_survival_triggers(self, system_state: Dict[str, Any]) -> bool:
        """Check if survival core mode should be triggered"""
        # Crisis probability high
        crisis_prob = system_state.get('crisis_probability', 0.0)
        if crisis_prob > 0.7:
            return True
        
        # Convexity breach
        if system_state.get('convexity_breach', False):
            return True
        
        # Severe drawdown
        drawdown = system_state.get('current_drawdown', 0.0)
        if drawdown > self.thresholds['survival_core']['drawdown_threshold']:
            return True
        
        # Gap shock trigger
        if system_state.get('gap_shock_detected', False):
            return True
        
        return False
    
    def _check_governance_triggers(self, system_state: Dict[str, Any]) -> bool:
        """Check if governance constrained mode should be triggered"""
        # Drift elevated
        drift_level = system_state.get('drift_level', 'normal')
        if drift_level in ['elevated', 'high']:
            return True
        
        # Fallback tier >= 2
        fallback_tier = system_state.get('fallback_tier', 0)
        if fallback_tier >= 2:
            return True
        
        # SDI > threshold
        sdi = system_state.get('sdi', 0.0)
        if sdi > self.thresholds['governance_constrained']['sdi_threshold']:
            return True
        
        # Moderate drawdown
        drawdown = system_state.get('current_drawdown', 0.0)
        if drawdown > self.thresholds['governance_constrained']['drawdown_threshold']:
            return True
        
        return False
    
    def _check_normal_conditions(self, system_state: Dict[str, Any]) -> bool:
        """Check if conditions allow return to normal operation"""
        # All triggers should be clear
        if self._check_recovery_triggers(system_state):
            return False
        if self._check_survival_triggers(system_state):
            return False
        if self._check_governance_triggers(system_state):
            return False
        
        # Additional stability requirements
        time_in_mode = datetime.now() - self.mode_entered_at
        min_stability_time = timedelta(minutes=15)  # Minimum time before returning to normal
        
        return time_in_mode >= min_stability_time
    
    def _get_survival_reasons(self, system_state: Dict[str, Any]) -> List[str]:
        """Get specific reasons for survival mode"""
        reasons = []
        
        if system_state.get('crisis_probability', 0.0) > 0.7:
            reasons.append(f"Crisis probability high: {system_state['crisis_probability']:.2f}")
        
        if system_state.get('convexity_breach', False):
            reasons.append("Convexity breach detected")
        
        drawdown = system_state.get('current_drawdown', 0.0)
        if drawdown > self.thresholds['survival_core']['drawdown_threshold']:
            reasons.append(f"Severe drawdown: {drawdown:.1%}")
        
        if system_state.get('gap_shock_detected', False):
            reasons.append("Gap shock detected")
        
        return reasons
    
    def _get_governance_reasons(self, system_state: Dict[str, Any]) -> List[str]:
        """Get specific reasons for governance constrained mode"""
        reasons = []
        
        drift_level = system_state.get('drift_level', 'normal')
        if drift_level in ['elevated', 'high']:
            reasons.append(f"Drift level: {drift_level}")
        
        fallback_tier = system_state.get('fallback_tier', 0)
        if fallback_tier >= 2:
            reasons.append(f"Fallback tier: {fallback_tier}")
        
        sdi = system_state.get('sdi', 0.0)
        if sdi > self.thresholds['governance_constrained']['sdi_threshold']:
            reasons.append(f"SDI elevated: {sdi:.2f}")
        
        drawdown = system_state.get('current_drawdown', 0.0)
        if drawdown > self.thresholds['governance_constrained']['drawdown_threshold']:
            reasons.append(f"Drawdown: {drawdown:.1%}")
        
        return reasons
    
    def transition_to_mode(self, new_mode: SystemMode, reasons: List[str]) -> Dict[str, Any]:
        """Execute mode transition"""
        old_mode = self.current_mode
        
        if old_mode == new_mode:
            return {'transitioned': False, 'mode': new_mode.value}
        
        # Record transition
        transition_record = {
            'timestamp': datetime.now().isoformat(),
            'from_mode': old_mode.value,
            'to_mode': new_mode.value,
            'reasons': reasons,
            'time_in_previous_mode': (datetime.now() - self.mode_entered_at).total_seconds()
        }
        
        self.mode_history.append(transition_record)
        
        # Update current mode
        self.current_mode = new_mode
        self.mode_entered_at = datetime.now()
        
        # Apply mode constraints
        self.constraints_active = self._get_mode_constraints(new_mode)
        
        logger.warning(f"Mode transition: {old_mode.value} → {new_mode.value} | Reasons: {reasons}")
        
        return {
            'transitioned': True,
            'from_mode': old_mode.value,
            'to_mode': new_mode.value,
            'reasons': reasons,
            'constraints': self.constraints_active,
            'transition_record': transition_record
        }
    
    def _get_mode_constraints(self, mode: SystemMode) -> Dict[str, Any]:
        """Get constraints for a given mode"""
        constraints = {
            'block_new_risk': False,
            'disable_research': False,
            'disable_scaling_up': False,
            'force_position_reduction': False,
            'increase_monitoring': False,
            'require_manual_approval': False
        }
        
        if mode == SystemMode.GOVERNANCE_CONSTRAINED:
            constraints.update({
                'disable_scaling_up': True,
                'increase_monitoring': True
            })
        
        elif mode == SystemMode.SURVIVAL_CORE:
            constraints.update({
                'block_new_risk': True,
                'disable_research': True,
                'disable_scaling_up': True,
                'force_position_reduction': True,
                'increase_monitoring': True
            })
        
        elif mode == SystemMode.RECOVERY_MODE:
            constraints.update({
                'block_new_risk': True,
                'disable_research': True,
                'disable_scaling_up': True,
                'require_manual_approval': True,
                'increase_monitoring': True
            })
        
        return constraints
    
    def is_action_allowed(self, action: str) -> Tuple[bool, Optional[str]]:
        """Check if an action is allowed in current mode"""
        constraints = self.constraints_active
        
        # Define action mappings
        action_constraints = {
            'open_new_position': 'block_new_risk',
            'scale_up_position': 'disable_scaling_up',
            'run_research': 'disable_research',
            'auto_parameter_update': 'require_manual_approval',
            'model_promotion': 'require_manual_approval'
        }
        
        constraint_key = action_constraints.get(action)
        if constraint_key and constraints.get(constraint_key, False):
            return False, f"Action blocked by {self.current_mode.value} mode"
        
        return True, None
    
    def get_mode_status(self) -> Dict[str, Any]:
        """Get current mode status"""
        time_in_mode = (datetime.now() - self.mode_entered_at).total_seconds()
        
        return {
            'current_mode': self.current_mode.value,
            'mode_entered_at': self.mode_entered_at.isoformat(),
            'time_in_mode_seconds': time_in_mode,
            'constraints_active': self.constraints_active,
            'transition_count': len(self.mode_history),
            'last_transition': self.mode_history[-1] if self.mode_history else None
        }
    
    def get_mode_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent mode transition history"""
        return self.mode_history[-limit:] if self.mode_history else []
    
    def force_mode_transition(self, target_mode: SystemMode, reason: str) -> Dict[str, Any]:
        """Force mode transition (for manual intervention)"""
        return self.transition_to_mode(target_mode, [f"Manual override: {reason}"])
    
    def update_thresholds(self, new_thresholds: Dict[str, Any]) -> None:
        """Update mode transition thresholds"""
        self.thresholds.update(new_thresholds)
        logger.info(f"Mode thresholds updated: {new_thresholds}")
    
    def evaluate_auto_descaling(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if auto de-scaling should be triggered"""
        descaling_report = {
            'should_descale': False,
            'current_tier': system_state.get('current_tier', 1),
            'target_tier': None,
            'triggers': [],
            'recommendations': []
        }
        
        current_tier = descaling_report['current_tier']
        
        # Check drawdown trigger
        drawdown = system_state.get('current_drawdown', 0.0)
        if drawdown > 0.15:  # 15% drawdown
            descaling_report['triggers'].append(f"Drawdown {drawdown:.1%} > 15%")
            descaling_report['should_descale'] = True
        
        # Check survival mode frequency
        survival_activations = system_state.get('survival_mode_activations_recent', 0)
        if survival_activations >= 5:
            descaling_report['triggers'].append(f"Survival mode activated {survival_activations} times")
            descaling_report['should_descale'] = True
        
        # Check sustained drift
        drift_duration = system_state.get('high_drift_duration_minutes', 0)
        if drift_duration >= 300:  # 5+ hours
            descaling_report['triggers'].append(f"High drift sustained for {drift_duration} minutes")
            descaling_report['should_descale'] = True
        
        # Determine target tier
        if descaling_report['should_descale'] and current_tier > 1:
            descaling_report['target_tier'] = max(1, current_tier - 1)
            descaling_report['recommendations'].append(
                f"Reduce tier from {current_tier} to {descaling_report['target_tier']}"
            )
        
        return descaling_report