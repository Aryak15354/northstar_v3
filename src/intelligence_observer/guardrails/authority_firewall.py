#!/usr/bin/env python3
"""
Authority Firewall - Prevents Intelligence Observer from Gaining Decision Authority

This module implements the critical authority firewall that ensures the Intelligence
Observer can never influence system decisions, override risk controls, or gain
any form of decision-making authority.

CRITICAL DESIGN PRINCIPLE:
The Observer may become arbitrarily intelligent, but it may never become brave.
Bravery is already encoded in your engines.
"""

import sys
import importlib
import inspect
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass
from enum import Enum
import logging

class ViolationType(Enum):
    """Types of authority violations"""
    FORBIDDEN_IMPORT = "forbidden_import"
    WRITE_ACCESS_ATTEMPT = "write_access_attempt"
    DECISION_INFLUENCE = "decision_influence"
    PARAMETER_MODIFICATION = "parameter_modification"
    EXECUTION_INTERFERENCE = "execution_interference"
    RISK_OVERRIDE_ATTEMPT = "risk_override_attempt"

@dataclass
class AuthorityViolation:
    """Authority violation record"""
    violation_type: ViolationType
    timestamp: datetime
    module_name: str
    function_name: str
    attempted_action: str
    stack_trace: str
    severity: str = "HIGH"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'violation_type': self.violation_type.value,
            'timestamp': self.timestamp.isoformat(),
            'module_name': self.module_name,
            'function_name': self.function_name,
            'attempted_action': self.attempted_action,
            'stack_trace': self.stack_trace,
            'severity': self.severity
        }

class AuthorityFirewall:
    """
    Authority Firewall - Prevents Intelligence Observer from Gaining Decision Authority
    
    This firewall ensures the Observer remains in a read-only, advisory capacity
    and can never influence system decisions or override risk controls.
    """
    
    def __init__(self):
        self.name = "Intelligence Observer Authority Firewall"
        self.version = "1.0.0"
        
        # Forbidden modules - Observer cannot import these
        self.forbidden_modules = {
            'src.portfolio.portfolio_governor',
            'src.risk.emergency_brake',
            'src.intelligence.dual_engine_coordinator',
            'src.intelligence.crisis_engine',
            'src.intelligence.trend_engine',
            'src.cohesion.risk_authority',
            'src.core.state',  # No direct state modification
            'src.execution',
            'src.live',
            'src.portfolio.strategies'
        }
        
        # Forbidden functions - Observer cannot call these
        self.forbidden_functions = {
            'set_exposure',
            'modify_position',
            'override_risk_limit',
            'activate_engine',
            'deactivate_engine',
            'force_rebalance',
            'emergency_stop',
            'update_parameters',
            'set_regime',
            'modify_allocation',
            'trigger_execution',
            'place_order',
            'cancel_order'
        }
        
        # Forbidden attributes - Observer cannot access these
        self.forbidden_attributes = {
            'current_positions',
            'live_pnl',
            'real_time_exposure',
            'active_orders',
            'execution_queue',
            'risk_overrides',
            'emergency_state'
        }
        
        # Violation tracking
        self.violations: List[AuthorityViolation] = []
        self.violation_count = 0
        self.observer_suspended = False
        
        # Logging
        self.logger = logging.getLogger(f"{self.name}")
        
        print(f"🔒 {self.name} v{self.version} - Authority Boundaries Enforced")
        print(f"🚫 Forbidden modules: {len(self.forbidden_modules)}")
        print(f"🚫 Forbidden functions: {len(self.forbidden_functions)}")
    
    def check_import_attempt(self, module_name: str) -> bool:
        """
        Check if module import is allowed for Observer
        
        Args:
            module_name: Name of module being imported
            
        Returns:
            bool: True if import is allowed, False if forbidden
        """
        
        # Check against forbidden modules
        for forbidden in self.forbidden_modules:
            if module_name.startswith(forbidden) or forbidden in module_name:
                self._record_violation(
                    ViolationType.FORBIDDEN_IMPORT,
                    module_name,
                    'import',
                    f"Attempted to import forbidden module: {module_name}"
                )
                return False
        
        return True
    
    def check_function_call(self, function_name: str, module_name: str = "") -> bool:
        """
        Check if function call is allowed for Observer
        
        Args:
            function_name: Name of function being called
            module_name: Module containing the function
            
        Returns:
            bool: True if call is allowed, False if forbidden
        """
        
        # Check against forbidden functions
        if function_name in self.forbidden_functions:
            self._record_violation(
                ViolationType.DECISION_INFLUENCE,
                module_name,
                function_name,
                f"Attempted to call forbidden function: {function_name}"
            )
            return False
        
        # Check for write operations
        write_indicators = ['set_', 'update_', 'modify_', 'change_', 'override_', 'force_']
        if any(function_name.startswith(indicator) for indicator in write_indicators):
            self._record_violation(
                ViolationType.WRITE_ACCESS_ATTEMPT,
                module_name,
                function_name,
                f"Attempted write operation: {function_name}"
            )
            return False
        
        return True
    
    def check_attribute_access(self, attribute_name: str, access_type: str = "read") -> bool:
        """
        Check if attribute access is allowed for Observer
        
        Args:
            attribute_name: Name of attribute being accessed
            access_type: Type of access ("read" or "write")
            
        Returns:
            bool: True if access is allowed, False if forbidden
        """
        
        # All write access is forbidden
        if access_type == "write":
            self._record_violation(
                ViolationType.WRITE_ACCESS_ATTEMPT,
                "unknown",
                "attribute_write",
                f"Attempted to write attribute: {attribute_name}"
            )
            return False
        
        # Check against forbidden attributes
        if attribute_name in self.forbidden_attributes:
            self._record_violation(
                ViolationType.EXECUTION_INTERFERENCE,
                "unknown",
                "attribute_read",
                f"Attempted to read forbidden attribute: {attribute_name}"
            )
            return False
        
        return True
    
    def validate_observer_output(self, output: Any) -> bool:
        """
        Validate that Observer output contains no decision commands
        
        Args:
            output: Observer output to validate
            
        Returns:
            bool: True if output is valid, False if contains forbidden content
        """
        
        if isinstance(output, dict):
            return self._validate_dict_output(output)
        elif isinstance(output, str):
            return self._validate_string_output(output)
        elif hasattr(output, 'to_dict'):
            return self._validate_dict_output(output.to_dict())
        
        return True
    
    def _validate_dict_output(self, output_dict: Dict[str, Any]) -> bool:
        """Validate dictionary output for forbidden content"""
        
        # Check for forbidden keys
        forbidden_keys = {
            'trade_signal', 'position_change', 'exposure_change',
            'engine_override', 'risk_override', 'execution_command'
        }
        
        for key in output_dict.keys():
            if key in forbidden_keys:
                self._record_violation(
                    ViolationType.DECISION_INFLUENCE,
                    "observer_output",
                    "output_validation",
                    f"Output contains forbidden key: {key}"
                )
                return False
        
        # Recursively check nested dictionaries
        for value in output_dict.values():
            if isinstance(value, dict):
                if not self._validate_dict_output(value):
                    return False
            elif isinstance(value, str):
                if not self._validate_string_output(value):
                    return False
        
        return True
    
    def _validate_string_output(self, output_string: str) -> bool:
        """Validate string output for forbidden content"""
        
        # Check for imperative language
        forbidden_phrases = [
            'should trade', 'must buy', 'must sell', 'should enter',
            'should exit', 'increase position', 'reduce position',
            'activate engine', 'override risk', 'force rebalance'
        ]
        
        output_lower = output_string.lower()
        
        for phrase in forbidden_phrases:
            if phrase in output_lower:
                self._record_violation(
                    ViolationType.DECISION_INFLUENCE,
                    "observer_output",
                    "string_validation",
                    f"Output contains forbidden phrase: {phrase}"
                )
                return False
        
        return True
    
    def _record_violation(self, violation_type: ViolationType, module_name: str, 
                         function_name: str, attempted_action: str):
        """Record an authority violation"""
        
        # Get stack trace
        import traceback
        stack_trace = traceback.format_stack()
        
        violation = AuthorityViolation(
            violation_type=violation_type,
            timestamp=datetime.now(),
            module_name=module_name,
            function_name=function_name,
            attempted_action=attempted_action,
            stack_trace=''.join(stack_trace[-5:])  # Last 5 stack frames
        )
        
        self.violations.append(violation)
        self.violation_count += 1
        
        # Log violation
        self.logger.error(f"AUTHORITY VIOLATION: {violation_type.value}")
        self.logger.error(f"Module: {module_name}, Function: {function_name}")
        self.logger.error(f"Action: {attempted_action}")
        
        print(f"🚨 AUTHORITY VIOLATION DETECTED")
        print(f"   Type: {violation_type.value}")
        print(f"   Action: {attempted_action}")
        print(f"   Count: {self.violation_count}")
        
        # Check if Observer should be suspended
        if self.violation_count >= 3:
            self._suspend_observer()
    
    def _suspend_observer(self):
        """Suspend Observer due to repeated violations"""
        
        self.observer_suspended = True
        
        self.logger.critical("INTELLIGENCE OBSERVER SUSPENDED - Multiple authority violations")
        print(f"🚨 INTELLIGENCE OBSERVER SUSPENDED")
        print(f"   Reason: {self.violation_count} authority violations")
        print(f"   System continues trading unaffected")
        
        # In a real implementation, this would disable the Observer
        # while allowing the trading system to continue normally
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Get summary of authority violations"""
        
        violation_types = {}
        for violation in self.violations:
            vtype = violation.violation_type.value
            violation_types[vtype] = violation_types.get(vtype, 0) + 1
        
        return {
            'total_violations': self.violation_count,
            'observer_suspended': self.observer_suspended,
            'violations_by_type': violation_types,
            'recent_violations': [v.to_dict() for v in self.violations[-5:]],
            'last_violation': self.violations[-1].to_dict() if self.violations else None
        }
    
    def reset_violations(self, authorization_code: str = ""):
        """Reset violation count (requires authorization)"""
        
        # In production, this would require proper authorization
        if authorization_code == "NORTHSTAR_ADMIN_RESET":
            self.violations.clear()
            self.violation_count = 0
            self.observer_suspended = False
            
            self.logger.info("Authority violations reset by administrator")
            print("🔄 Authority violations reset")
        else:
            print("❌ Unauthorized reset attempt")

class ObserverImportHook:
    """
    Import hook to monitor Observer module imports
    
    This hook intercepts import attempts and validates them against
    the authority firewall rules.
    """
    
    def __init__(self, firewall: AuthorityFirewall):
        self.firewall = firewall
        self.original_import = __builtins__['__import__']
    
    def __call__(self, name, globals=None, locals=None, fromlist=(), level=0):
        """Custom import function with authority checking"""
        
        # Check if this is an Observer module attempting import
        if globals and 'intelligence_observer' in str(globals.get('__name__', '')):
            if not self.firewall.check_import_attempt(name):
                raise ImportError(f"Authority Firewall: Import of {name} forbidden for Observer")
        
        # Proceed with normal import
        return self.original_import(name, globals, locals, fromlist, level)
    
    def install(self):
        """Install the import hook"""
        __builtins__['__import__'] = self
    
    def uninstall(self):
        """Uninstall the import hook"""
        __builtins__['__import__'] = self.original_import

# Global firewall instance
_authority_firewall = None

def get_authority_firewall() -> AuthorityFirewall:
    """Get the global authority firewall instance"""
    global _authority_firewall
    
    if _authority_firewall is None:
        _authority_firewall = AuthorityFirewall()
    
    return _authority_firewall

def install_authority_firewall():
    """Install the authority firewall and import hook"""
    
    firewall = get_authority_firewall()
    import_hook = ObserverImportHook(firewall)
    import_hook.install()
    
    print("🔒 Authority Firewall installed and active")
    return firewall

def check_observer_authority(func: Callable) -> Callable:
    """
    Decorator to check Observer authority for function calls
    
    This decorator can be applied to sensitive functions to ensure
    the Observer cannot call them.
    """
    
    def wrapper(*args, **kwargs):
        # Get calling module
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get('__name__', 'unknown')
        
        # Check if called from Observer
        if 'intelligence_observer' in module_name:
            firewall = get_authority_firewall()
            if not firewall.check_function_call(func.__name__, module_name):
                raise PermissionError(f"Authority Firewall: Observer cannot call {func.__name__}")
        
        return func(*args, **kwargs)
    
    return wrapper