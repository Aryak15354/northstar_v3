#!/usr/bin/env python3
"""
🔥 CRISIS ENGINE CONVICTION CONTRACT

This contract governs the Crisis Engine with the same institutional discipline
as the Trend Engine. It exists to prevent emotional interference with crisis alpha.

CRITICAL PRINCIPLE:
Crisis alpha is paid for in advance through steady bleeding.
Any emotional override destroys more value than it protects.

This contract is FROZEN and NON-NEGOTIABLE.
"""

import hashlib
import json
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

class ConvictionViolationType(Enum):
    """Types of conviction violations"""
    EMOTIONAL_OVERRIDE = "EMOTIONAL_OVERRIDE"           # Turning off during bleed
    SIZE_REDUCTION = "SIZE_REDUCTION"                   # Reducing size due to discomfort
    PREMATURE_EXIT = "PREMATURE_EXIT"                   # Exiting before signal says to
    PARAMETER_DRIFT = "PARAMETER_DRIFT"                 # Changing frozen parameters
    REGIME_OVERRIDE = "REGIME_OVERRIDE"                 # Overriding regime classification
    OPTIMIZATION_ATTEMPT = "OPTIMIZATION_ATTEMPT"       # Trying to "improve" after crisis

@dataclass
class CrisisConvictionRules:
    """
    Frozen rules for Crisis Engine conviction - NO CHANGES ALLOWED
    
    These rules encode the psychological discipline required for crisis alpha.
    Any violation destroys the engine's effectiveness.
    """
    
    # RULE 1: ENGINE SEPARATION (ABSOLUTE)
    trend_engine_overlap_forbidden: bool = True
    crisis_signals_independent: bool = True
    no_cross_engine_hedging: bool = True
    
    # RULE 2: REGIME DISCIPLINE (ABSOLUTE)
    only_activate_in_hostile_regime: bool = True
    no_manual_regime_override: bool = True
    regime_classification_frozen: bool = True
    
    # RULE 3: BLEEDING TOLERANCE (PSYCHOLOGICAL)
    max_consecutive_bleed_months: int = 24          # Must tolerate 24 months of bleeding
    max_cumulative_bleed_tolerance: float = 0.15    # 15% cumulative loss before reset
    no_size_reduction_during_bleed: bool = True
    no_emotional_exits: bool = True
    
    # RULE 4: ACTIVATION DISCIPLINE (BEHAVIORAL)
    no_manual_activation: bool = True               # Only regime triggers activation
    no_discretionary_sizing: bool = True           # Only signal determines size
    no_narrative_override: bool = True             # Ignore market narratives
    
    # RULE 5: PARAMETER FREEZE (STRUCTURAL)
    volatility_thresholds_frozen: bool = True
    position_sizing_rules_frozen: bool = True
    exit_conditions_frozen: bool = True
    no_post_crisis_optimization: bool = True
    
    # RULE 6: PAYOFF PATIENCE (TEMPORAL)
    min_holding_period_days: int = 1               # No day-trading crisis positions
    max_holding_period_days: int = 90              # Force exit after 90 days max
    no_profit_taking_before_signal: bool = True
    
    # RULE 7: PERFORMANCE EVALUATION (PHILOSOPHICAL)
    evaluate_over_full_cycles: bool = True         # Judge over 3+ year periods
    ignore_annual_performance: bool = True         # Don't judge yearly results
    focus_on_crisis_capture: bool = True          # Success = capturing crisis alpha
    
    def to_hash(self) -> str:
        """Generate cryptographic hash of conviction rules"""
        rules_dict = asdict(self)
        rules_str = json.dumps(rules_dict, sort_keys=True)
        return hashlib.sha256(rules_str.encode()).hexdigest()

@dataclass
class ConvictionViolation:
    """Record of a conviction violation"""
    timestamp: datetime
    violation_type: ConvictionViolationType
    description: str
    severity: str  # "WARNING", "VIOLATION", "CRITICAL"
    context: Dict[str, Any]

class CrisisConvictionContract:
    """
    Crisis Engine Conviction Contract
    
    This contract enforces the psychological discipline required for crisis alpha.
    It monitors for emotional overrides and parameter drift that destroy convexity.
    """
    
    def __init__(self):
        self.name = "Crisis Engine Conviction Contract"
        self.version = "1.0.0"
        self.creation_date = datetime.now()
        
        # Frozen conviction rules
        self.rules = CrisisConvictionRules()
        self.rules_hash = self.rules.to_hash()
        
        # Violation tracking
        self.violations: List[ConvictionViolation] = []
        self.warning_count = 0
        self.violation_count = 0
        self.critical_count = 0
        
        # State tracking for violation detection
        self.last_regime_state = None
        self.last_position_size = 0.0
        self.consecutive_bleed_days = 0
        self.cumulative_bleed = 0.0
        self.last_parameter_hash = None
        
        print(f"🔥 {self.name} v{self.version}")
        print(f"🔒 Rules Hash: {self.rules_hash[:16]}...")
        print(f"⚠️  CONVICTION CONTRACT ACTIVE - Monitoring for violations")
    
    def validate_engine_action(self, action_type: str, current_state: Dict[str, Any], 
                              proposed_action: Dict[str, Any]) -> bool:
        """
        Validate that a proposed engine action follows conviction rules
        
        Returns True if action is allowed, False if it violates conviction.
        Records violations for audit trail.
        """
        
        violations_detected = []
        
        # Check each rule category
        violations_detected.extend(self._check_engine_separation(current_state, proposed_action))
        violations_detected.extend(self._check_regime_discipline(current_state, proposed_action))
        violations_detected.extend(self._check_bleeding_tolerance(current_state, proposed_action))
        violations_detected.extend(self._check_activation_discipline(current_state, proposed_action))
        violations_detected.extend(self._check_parameter_freeze(current_state, proposed_action))
        violations_detected.extend(self._check_payoff_patience(current_state, proposed_action))
        
        # Record any violations
        for violation in violations_detected:
            self._record_violation(violation)
        
        # Action is allowed only if no critical violations
        critical_violations = [v for v in violations_detected if v.severity == "CRITICAL"]
        return len(critical_violations) == 0
    
    def _check_engine_separation(self, current_state: Dict[str, Any], 
                                proposed_action: Dict[str, Any]) -> List[ConvictionViolation]:
        """Check Rule 1: Engine Separation"""
        violations = []
        
        # Check for trend engine overlap (would need trend engine state)
        if proposed_action.get('uses_trend_signals', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.EMOTIONAL_OVERRIDE,
                description="Crisis engine attempting to use trend signals",
                severity="CRITICAL",
                context={'action': proposed_action}
            ))
        
        # Check for cross-engine hedging
        if proposed_action.get('hedges_trend_engine', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.EMOTIONAL_OVERRIDE,
                description="Crisis engine attempting to hedge trend engine",
                severity="CRITICAL",
                context={'action': proposed_action}
            ))
        
        return violations
    
    def _check_regime_discipline(self, current_state: Dict[str, Any], 
                                proposed_action: Dict[str, Any]) -> List[ConvictionViolation]:
        """Check Rule 2: Regime Discipline"""
        violations = []
        
        # Check activation outside hostile regime
        regime = current_state.get('regime_state', 'DORMANT')
        position_size = proposed_action.get('crisis_allocation', 0.0)
        
        if position_size > 0 and regime == 'DORMANT':
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.REGIME_OVERRIDE,
                description=f"Crisis engine active in {regime} regime",
                severity="CRITICAL",
                context={'regime': regime, 'position_size': position_size}
            ))
        
        # Check manual regime override
        if proposed_action.get('manual_regime_override', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.REGIME_OVERRIDE,
                description="Manual regime override attempted",
                severity="CRITICAL",
                context={'action': proposed_action}
            ))
        
        return violations
    
    def _check_bleeding_tolerance(self, current_state: Dict[str, Any], 
                                 proposed_action: Dict[str, Any]) -> List[ConvictionViolation]:
        """Check Rule 3: Bleeding Tolerance"""
        violations = []
        
        # Update bleeding tracking
        current_pnl = current_state.get('daily_pnl', 0.0)
        if current_pnl < 0:
            self.consecutive_bleed_days += 1
            self.cumulative_bleed += abs(current_pnl)
        else:
            self.consecutive_bleed_days = 0
        
        # Check for size reduction during bleeding
        current_size = current_state.get('position_size', 0.0)
        proposed_size = proposed_action.get('crisis_allocation', 0.0)
        
        if (self.consecutive_bleed_days > 30 and 
            proposed_size < current_size and 
            current_state.get('regime_state') != 'DORMANT'):
            
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.SIZE_REDUCTION,
                description=f"Position size reduced during {self.consecutive_bleed_days} days of bleeding",
                severity="VIOLATION",
                context={'bleed_days': self.consecutive_bleed_days, 'size_change': proposed_size - current_size}
            ))
        
        # Check for emotional exit
        if (proposed_action.get('reason_for_exit') == 'emotional' or 
            proposed_action.get('manual_exit', False)):
            
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.EMOTIONAL_OVERRIDE,
                description="Emotional exit attempted during bleeding period",
                severity="CRITICAL",
                context={'consecutive_bleed_days': self.consecutive_bleed_days}
            ))
        
        return violations
    
    def _check_activation_discipline(self, current_state: Dict[str, Any], 
                                   proposed_action: Dict[str, Any]) -> List[ConvictionViolation]:
        """Check Rule 4: Activation Discipline"""
        violations = []
        
        # Check for manual activation
        if proposed_action.get('manual_activation', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.EMOTIONAL_OVERRIDE,
                description="Manual activation attempted",
                severity="CRITICAL",
                context={'action': proposed_action}
            ))
        
        # Check for discretionary sizing
        if proposed_action.get('discretionary_sizing', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.SIZE_REDUCTION,
                description="Discretionary position sizing attempted",
                severity="VIOLATION",
                context={'action': proposed_action}
            ))
        
        # Check for narrative override
        if proposed_action.get('narrative_based_decision', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.EMOTIONAL_OVERRIDE,
                description="Decision based on market narrative rather than signals",
                severity="WARNING",
                context={'narrative': proposed_action.get('narrative_reason')}
            ))
        
        return violations
    
    def _check_parameter_freeze(self, current_state: Dict[str, Any], 
                               proposed_action: Dict[str, Any]) -> List[ConvictionViolation]:
        """Check Rule 5: Parameter Freeze"""
        violations = []
        
        # Check for parameter changes
        current_params = proposed_action.get('engine_parameters', {})
        if current_params:
            param_hash = hashlib.sha256(json.dumps(current_params, sort_keys=True).encode()).hexdigest()
            
            if self.last_parameter_hash and param_hash != self.last_parameter_hash:
                violations.append(ConvictionViolation(
                    timestamp=datetime.now(),
                    violation_type=ConvictionViolationType.PARAMETER_DRIFT,
                    description="Engine parameters modified",
                    severity="CRITICAL",
                    context={'parameter_hash_change': True}
                ))
            
            self.last_parameter_hash = param_hash
        
        # Check for post-crisis optimization
        if proposed_action.get('post_crisis_optimization', False):
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.OPTIMIZATION_ATTEMPT,
                description="Post-crisis optimization attempted",
                severity="CRITICAL",
                context={'optimization_type': proposed_action.get('optimization_type')}
            ))
        
        return violations
    
    def _check_payoff_patience(self, current_state: Dict[str, Any], 
                              proposed_action: Dict[str, Any]) -> List[ConvictionViolation]:
        """Check Rule 6: Payoff Patience"""
        violations = []
        
        # Check for premature profit taking
        if (proposed_action.get('exit_reason') == 'profit_taking' and 
            not proposed_action.get('signal_based_exit', False)):
            
            violations.append(ConvictionViolation(
                timestamp=datetime.now(),
                violation_type=ConvictionViolationType.PREMATURE_EXIT,
                description="Profit taking without signal confirmation",
                severity="VIOLATION",
                context={'exit_reason': 'profit_taking'}
            ))
        
        return violations
    
    def _record_violation(self, violation: ConvictionViolation):
        """Record a conviction violation"""
        self.violations.append(violation)
        
        if violation.severity == "WARNING":
            self.warning_count += 1
        elif violation.severity == "VIOLATION":
            self.violation_count += 1
        elif violation.severity == "CRITICAL":
            self.critical_count += 1
        
        # Log violation
        print(f"🚨 CONVICTION VIOLATION: {violation.violation_type.value}")
        print(f"   Severity: {violation.severity}")
        print(f"   Description: {violation.description}")
        
        if violation.severity == "CRITICAL":
            print(f"   ❌ CRITICAL VIOLATION - Action blocked")
    
    def get_conviction_health(self) -> Dict[str, Any]:
        """Get conviction contract health metrics"""
        
        total_violations = len(self.violations)
        recent_violations = len([v for v in self.violations 
                               if (datetime.now() - v.timestamp).days <= 30])
        
        # Calculate conviction score (0-100)
        conviction_score = 100
        conviction_score -= self.critical_count * 25  # Critical violations hurt most
        conviction_score -= self.violation_count * 10
        conviction_score -= self.warning_count * 2
        conviction_score = max(0, conviction_score)
        
        return {
            'conviction_score': conviction_score,
            'total_violations': total_violations,
            'recent_violations_30d': recent_violations,
            'violation_breakdown': {
                'warnings': self.warning_count,
                'violations': self.violation_count,
                'critical': self.critical_count
            },
            'bleeding_tolerance': {
                'consecutive_bleed_days': self.consecutive_bleed_days,
                'cumulative_bleed': self.cumulative_bleed,
                'max_bleed_tolerance': self.rules.max_cumulative_bleed_tolerance
            },
            'rules_integrity': {
                'rules_hash': self.rules_hash,
                'rules_frozen': True,
                'contract_active': True
            }
        }
    
    def generate_conviction_report(self) -> str:
        """Generate human-readable conviction report"""
        
        health = self.get_conviction_health()
        
        report = f"""
🔥 CRISIS ENGINE CONVICTION REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CONVICTION SCORE: {health['conviction_score']}/100

VIOLATION SUMMARY:
- Warnings: {health['violation_breakdown']['warnings']}
- Violations: {health['violation_breakdown']['violations']}
- Critical: {health['violation_breakdown']['critical']}
- Total: {health['total_violations']}
- Recent (30d): {health['recent_violations_30d']}

BLEEDING TOLERANCE:
- Consecutive bleed days: {health['bleeding_tolerance']['consecutive_bleed_days']}
- Cumulative bleed: {health['bleeding_tolerance']['cumulative_bleed']:.2%}
- Max tolerance: {health['bleeding_tolerance']['max_bleed_tolerance']:.2%}

RULES INTEGRITY:
- Rules hash: {health['rules_integrity']['rules_hash'][:16]}...
- Rules frozen: {health['rules_integrity']['rules_frozen']}
- Contract active: {health['rules_integrity']['contract_active']}

RECENT VIOLATIONS:
"""
        
        recent_violations = [v for v in self.violations 
                           if (datetime.now() - v.timestamp).days <= 7]
        
        if recent_violations:
            for violation in recent_violations[-5:]:  # Last 5
                report += f"- {violation.timestamp.strftime('%Y-%m-%d')}: {violation.violation_type.value} ({violation.severity})\n"
        else:
            report += "- No recent violations\n"
        
        report += f"""
CONVICTION ASSESSMENT:
"""
        
        if health['conviction_score'] >= 90:
            report += "✅ EXCELLENT - Strong conviction discipline maintained\n"
        elif health['conviction_score'] >= 70:
            report += "⚠️  GOOD - Minor violations, monitor closely\n"
        elif health['conviction_score'] >= 50:
            report += "🚨 CONCERNING - Multiple violations, review discipline\n"
        else:
            report += "❌ CRITICAL - Conviction compromised, engine effectiveness destroyed\n"
        
        return report

def create_crisis_conviction_contract() -> CrisisConvictionContract:
    """Factory function to create crisis conviction contract"""
    return CrisisConvictionContract()

# Example usage
if __name__ == "__main__":
    # Create conviction contract
    contract = create_crisis_conviction_contract()
    
    # Test violation detection
    print("\n🧪 TESTING CONVICTION CONTRACT")
    print("=" * 50)
    
    # Test valid action
    current_state = {
        'regime_state': 'HOSTILE',
        'position_size': 0.05,
        'daily_pnl': -0.001
    }
    
    valid_action = {
        'crisis_allocation': 0.05,
        'signal_based': True
    }
    
    is_valid = contract.validate_engine_action('position_sizing', current_state, valid_action)
    print(f"Valid action allowed: {is_valid}")
    
    # Test invalid action (emotional override)
    invalid_action = {
        'crisis_allocation': 0.0,
        'manual_exit': True,
        'reason_for_exit': 'emotional'
    }
    
    is_valid = contract.validate_engine_action('exit', current_state, invalid_action)
    print(f"Invalid action allowed: {is_valid}")
    
    # Generate report
    print("\n📊 CONVICTION REPORT")
    print("=" * 50)
    print(contract.generate_conviction_report())