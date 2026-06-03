#!/usr/bin/env python3
"""
Violation Handler - Manages Authority Violations and Observer Suspension

This module handles authority violations and manages Observer suspension
when violations exceed acceptable thresholds.
"""

from datetime import datetime
from typing import Dict, List, Any
import logging

class ViolationHandler:
    """Handles authority violations and Observer suspension"""
    
    def __init__(self):
        self.name = "Violation Handler"
        self.version = "1.0.0"
        
        self.violation_threshold = 3
        self.violations: List[Dict[str, Any]] = []
        self.observer_suspended = False
        
    def record_violation(self, violation_type: str, details: Dict[str, Any]):
        """Record an authority violation"""
        
        violation = {
            'timestamp': datetime.now().isoformat(),
            'type': violation_type,
            'details': details,
            'violation_id': len(self.violations) + 1
        }
        
        self.violations.append(violation)
        
        # Check if suspension is needed
        if len(self.violations) >= self.violation_threshold:
            self._suspend_observer()
    
    def _suspend_observer(self):
        """Suspend Observer due to violations"""
        
        self.observer_suspended = True
        
        print(f"🚨 INTELLIGENCE OBSERVER SUSPENDED")
        print(f"   Reason: {len(self.violations)} authority violations")
        print(f"   System continues trading unaffected")
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Get violation summary"""
        
        return {
            'total_violations': len(self.violations),
            'observer_suspended': self.observer_suspended,
            'recent_violations': self.violations[-5:] if self.violations else [],
            'violation_threshold': self.violation_threshold
        }