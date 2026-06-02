"""
Capital Policy Module for Northstar V2

Handles auto de-scaling, capital ladder symmetry, and tier management.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)


class CapitalTier(Enum):
    """Capital allocation tiers"""
    TIER_1 = 1  # Base tier
    TIER_2 = 2  # 2x base
    TIER_3 = 3  # 3x base
    TIER_4 = 4  # 4x base
    TIER_5 = 5  # 5x base (maximum)


class ScalingDirection(Enum):
    """Scaling direction"""
    UP = "up"
    DOWN = "down"
    MAINTAIN = "maintain"


class CapitalPolicyManager:
    """Manages capital allocation tiers and scaling policies"""
    
    def __init__(self, base_capital: float = 100000.0):
        self.base_capital = base_capital
        self.current_tier = CapitalTier.TIER_1
        self.tier_history = []
        self.last_scaling_action = None
        self.scaling_cooldown = timedelta(days=7)  # Minimum time between scaling actions
        
        # De-scaling triggers
        self.descaling_triggers = {
            'drawdown_threshold': 0.15,      # 15% drawdown
            'survival_frequency_threshold': 5, # 5+ survival mode activations
            'drift_duration_threshold': 300   # 5+ hours of high drift
        }
        
        # Scaling up requirements (more stringent)
        self.scaling_requirements = {
            'min_stability_days': 14,        # 14 days of stable operation
            'max_drawdown_period': 0.05,     # Max 5% drawdown in stability period
            'min_sharpe_ratio': 1.5,         # Minimum Sharpe ratio
            'governance_mode_free_days': 7   # Days without governance constraints
        }
    
    def get_tier_capital(self, tier: CapitalTier) -> float:
        """Get capital allocation for a tier"""
        return self.base_capital * tier.value
    
    def get_current_capital(self, options_capital_budget_inr: float | None = None) -> float:
        """Get current tier capital allocation
        
        Args:
            options_capital_budget_inr: Optional budget from Portfolio Governor.
                                       If provided, this overrides the tier-based capital.
        """
        if options_capital_budget_inr is not None:
            print(f"   💰 Options Capital Budget from Governor: ₹{options_capital_budget_inr:,.0f}")
            return float(options_capital_budget_inr)
        
        return self.get_tier_capital(self.current_tier)
    
    def evaluate_descaling_triggers(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if auto de-scaling should be triggered"""
        evaluation = {
            'timestamp': datetime.now().isoformat(),
            'current_tier': self.current_tier.value,
            'should_descale': False,
            'triggers_met': [],
            'target_tier': None,
            'cooldown_active': False,
            'recommendations': []
        }
        evaluation['cooldown_active'] = self._is_scaling_cooldown_active()
        
        # Check drawdown trigger
        current_drawdown = system_state.get('current_drawdown', 0.0)
        if current_drawdown > self.descaling_triggers['drawdown_threshold']:
            evaluation['triggers_met'].append({
                'trigger': 'drawdown_excessive',
                'value': current_drawdown,
                'threshold': self.descaling_triggers['drawdown_threshold'],
                'description': f"Drawdown {current_drawdown:.1%} > {self.descaling_triggers['drawdown_threshold']:.1%}"
            })
        
        # Check survival mode frequency
        survival_activations = system_state.get('survival_mode_activations_recent', 0)
        if survival_activations >= self.descaling_triggers['survival_frequency_threshold']:
            evaluation['triggers_met'].append({
                'trigger': 'survival_frequency_high',
                'value': survival_activations,
                'threshold': self.descaling_triggers['survival_frequency_threshold'],
                'description': f"Survival mode activated {survival_activations} times"
            })
        
        # Check sustained drift
        high_drift_duration = system_state.get('high_drift_duration_minutes', 0)
        if high_drift_duration >= self.descaling_triggers['drift_duration_threshold']:
            evaluation['triggers_met'].append({
                'trigger': 'drift_sustained',
                'value': high_drift_duration,
                'threshold': self.descaling_triggers['drift_duration_threshold'],
                'description': f"High drift sustained for {high_drift_duration} minutes"
            })
        
        # Determine if de-scaling should occur
        if evaluation['triggers_met'] and self.current_tier.value > 1:
            evaluation['should_descale'] = True
            evaluation['target_tier'] = max(1, self.current_tier.value - 1)
            evaluation['recommendations'].append(
                f"Reduce capital tier from {self.current_tier.value} to {evaluation['target_tier']}"
            )
        
        return evaluation
    
    def evaluate_scaling_requirements(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if scaling up is allowed"""
        evaluation = {
            'timestamp': datetime.now().isoformat(),
            'current_tier': self.current_tier.value,
            'can_scale_up': False,
            'requirements_met': [],
            'requirements_failed': [],
            'target_tier': None,
            'cooldown_active': False
        }
        
        # Check cooldown
        if self._is_scaling_cooldown_active():
            evaluation['cooldown_active'] = True
            evaluation['requirements_failed'].append("Scaling cooldown active")
            return evaluation
        
        # Check if already at maximum tier
        if self.current_tier == CapitalTier.TIER_5:
            evaluation['requirements_failed'].append("Already at maximum tier")
            return evaluation
        
        # Check governance mode constraints
        current_mode = system_state.get('current_mode', 'normal_operation')
        if current_mode != 'normal_operation':
            evaluation['requirements_failed'].append(f"System in {current_mode} mode")
            return evaluation
        
        # Check stability period
        stability_days = system_state.get('days_since_last_incident', 0)
        if stability_days >= self.scaling_requirements['min_stability_days']:
            evaluation['requirements_met'].append({
                'requirement': 'stability_period',
                'value': stability_days,
                'threshold': self.scaling_requirements['min_stability_days'],
                'description': f"Stable for {stability_days} days"
            })
        else:
            evaluation['requirements_failed'].append(
                f"Stability period: {stability_days}/{self.scaling_requirements['min_stability_days']} days"
            )
        
        # Check drawdown during stability period
        max_drawdown_period = system_state.get('max_drawdown_stability_period', 0.0)
        if max_drawdown_period <= self.scaling_requirements['max_drawdown_period']:
            evaluation['requirements_met'].append({
                'requirement': 'drawdown_limit',
                'value': max_drawdown_period,
                'threshold': self.scaling_requirements['max_drawdown_period'],
                'description': f"Max drawdown {max_drawdown_period:.1%} in stability period"
            })
        else:
            evaluation['requirements_failed'].append(
                f"Drawdown too high: {max_drawdown_period:.1%} > {self.scaling_requirements['max_drawdown_period']:.1%}"
            )
        
        # Check performance metrics
        sharpe_ratio = system_state.get('sharpe_ratio_recent', 0.0)
        if sharpe_ratio >= self.scaling_requirements['min_sharpe_ratio']:
            evaluation['requirements_met'].append({
                'requirement': 'performance',
                'value': sharpe_ratio,
                'threshold': self.scaling_requirements['min_sharpe_ratio'],
                'description': f"Sharpe ratio {sharpe_ratio:.2f}"
            })
        else:
            evaluation['requirements_failed'].append(
                f"Performance insufficient: Sharpe {sharpe_ratio:.2f} < {self.scaling_requirements['min_sharpe_ratio']}"
            )
        
        # Check governance-free period
        governance_free_days = system_state.get('days_without_governance_constraints', 0)
        if governance_free_days >= self.scaling_requirements['governance_mode_free_days']:
            evaluation['requirements_met'].append({
                'requirement': 'governance_free',
                'value': governance_free_days,
                'threshold': self.scaling_requirements['governance_mode_free_days'],
                'description': f"Governance-free for {governance_free_days} days"
            })
        else:
            evaluation['requirements_failed'].append(
                f"Governance constraints too recent: {governance_free_days}/{self.scaling_requirements['governance_mode_free_days']} days"
            )
        
        # Determine if scaling up is allowed
        if not evaluation['requirements_failed'] and len(evaluation['requirements_met']) >= 4:
            evaluation['can_scale_up'] = True
            evaluation['target_tier'] = min(5, self.current_tier.value + 1)
        
        return evaluation
    
    def execute_tier_change(self, new_tier: int, reason: str, 
                          operator_override: bool = False) -> Dict[str, Any]:
        """Execute capital tier change"""
        if new_tier < 1 or new_tier > 5:
            raise ValueError(f"Invalid tier: {new_tier}. Must be 1-5.")
        
        old_tier = self.current_tier
        new_tier_enum = CapitalTier(new_tier)
        
        if old_tier == new_tier_enum:
            return {
                'changed': False,
                'reason': 'No change needed',
                'current_tier': old_tier.value
            }
        
        # Record tier change
        tier_change_record = {
            'timestamp': datetime.now().isoformat(),
            'from_tier': old_tier.value,
            'to_tier': new_tier,
            'from_capital': self.get_tier_capital(old_tier),
            'to_capital': self.get_tier_capital(new_tier_enum),
            'reason': reason,
            'operator_override': operator_override,
            'scaling_direction': 'up' if new_tier > old_tier.value else 'down'
        }
        
        # Update current tier
        self.current_tier = new_tier_enum
        self.tier_history.append(tier_change_record)
        self.last_scaling_action = datetime.now()
        
        logger.warning(f"Capital tier changed: {old_tier.value} → {new_tier} | "
                      f"Capital: ₹{tier_change_record['from_capital']:,.0f} → "
                      f"₹{tier_change_record['to_capital']:,.0f} | Reason: {reason}")
        
        return {
            'changed': True,
            'from_tier': old_tier.value,
            'to_tier': new_tier,
            'from_capital': tier_change_record['from_capital'],
            'to_capital': tier_change_record['to_capital'],
            'reason': reason,
            'operator_override': operator_override,
            'tier_change_record': tier_change_record
        }
    
    def _is_scaling_cooldown_active(self) -> bool:
        """Check if scaling cooldown is active"""
        if self.last_scaling_action is None:
            return False
        
        return datetime.now() - self.last_scaling_action < self.scaling_cooldown
    
    def get_scaling_recommendation(self, system_state: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive scaling recommendation"""
        recommendation = {
            'timestamp': datetime.now().isoformat(),
            'current_tier': self.current_tier.value,
            'current_capital': self.get_current_capital(),
            'recommendation': ScalingDirection.MAINTAIN.value,
            'target_tier': None,
            'confidence': 'low',
            'reasons': [],
            'next_review_date': None
        }
        
        # Check de-scaling triggers
        descaling_eval = self.evaluate_descaling_triggers(system_state)
        if descaling_eval['should_descale']:
            recommendation.update({
                'recommendation': ScalingDirection.DOWN.value,
                'target_tier': descaling_eval['target_tier'],
                'confidence': 'high',
                'reasons': [trigger['description'] for trigger in descaling_eval['triggers_met']]
            })
            return recommendation
        
        # Check scaling up requirements
        scaling_eval = self.evaluate_scaling_requirements(system_state)
        if scaling_eval['can_scale_up']:
            recommendation.update({
                'recommendation': ScalingDirection.UP.value,
                'target_tier': scaling_eval['target_tier'],
                'confidence': 'medium',
                'reasons': [req['description'] for req in scaling_eval['requirements_met']]
            })
        elif scaling_eval['requirements_failed']:
            # Provide guidance on what's needed for scaling up
            recommendation['reasons'] = scaling_eval['requirements_failed']
            
            # Estimate next review date based on requirements
            days_needed = max(
                self.scaling_requirements['min_stability_days'] - system_state.get('days_since_last_incident', 0),
                self.scaling_requirements['governance_mode_free_days'] - system_state.get('days_without_governance_constraints', 0),
                0
            )
            
            if days_needed > 0:
                next_review = datetime.now() + timedelta(days=days_needed)
                recommendation['next_review_date'] = next_review.isoformat()
        
        return recommendation
    
    def get_tier_status(self) -> Dict[str, Any]:
        """Get current tier status and history"""
        return {
            'current_tier': self.current_tier.value,
            'current_capital': self.get_current_capital(),
            'base_capital': self.base_capital,
            'last_scaling_action': self.last_scaling_action.isoformat() if self.last_scaling_action else None,
            'cooldown_active': self._is_scaling_cooldown_active(),
            'cooldown_expires': (self.last_scaling_action + self.scaling_cooldown).isoformat() if self.last_scaling_action else None,
            'tier_changes_count': len(self.tier_history),
            'recent_changes': self.tier_history[-5:] if self.tier_history else []
        }
    
    def update_policy_parameters(self, new_params: Dict[str, Any]) -> None:
        """Update policy parameters"""
        if 'descaling_triggers' in new_params:
            self.descaling_triggers.update(new_params['descaling_triggers'])
        
        if 'scaling_requirements' in new_params:
            self.scaling_requirements.update(new_params['scaling_requirements'])
        
        if 'scaling_cooldown_days' in new_params:
            self.scaling_cooldown = timedelta(days=new_params['scaling_cooldown_days'])
        
        logger.info(f"Capital policy parameters updated: {new_params}")
    
    def simulate_tier_impact(self, target_tier: int, current_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simulate impact of tier change on current positions"""
        current_capital = self.get_current_capital()
        target_capital = self.get_tier_capital(CapitalTier(target_tier))
        capital_ratio = target_capital / current_capital
        
        simulation = {
            'current_tier': self.current_tier.value,
            'target_tier': target_tier,
            'current_capital': current_capital,
            'target_capital': target_capital,
            'capital_ratio': capital_ratio,
            'scaling_direction': 'up' if target_tier > self.current_tier.value else 'down',
            'position_adjustments': []
        }
        
        # Simulate position adjustments
        for position in current_positions:
            current_size = position.get('size', 0)
            adjusted_size = current_size * capital_ratio
            
            adjustment = {
                'position_id': position.get('position_id'),
                'underlying': position.get('underlying'),
                'current_size': current_size,
                'adjusted_size': adjusted_size,
                'size_change': adjusted_size - current_size,
                'size_change_pct': (adjusted_size - current_size) / current_size * 100 if current_size != 0 else 0
            }
            
            simulation['position_adjustments'].append(adjustment)
        
        return simulation
