"""
State Transition Logger for System Integrity Repair

This module implements comprehensive logging of state transitions, exposure bound
violations, health metric changes, and state inconsistencies for diagnostic purposes.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import json

logger = logging.getLogger(__name__)


@dataclass
class StateTransition:
    """Record of a state transition"""
    timestamp: datetime
    component: str  # Which component changed
    field: str  # Which field changed
    previous_value: Any
    new_value: Any
    change_magnitude: Optional[float] = None
    reason: Optional[str] = None


@dataclass
class BoundViolation:
    """Record of an exposure bound violation"""
    timestamp: datetime
    calculation_type: str  # 'allowed_exposure', 'risk_scaled_exposure', etc.
    unbounded_value: float
    bounded_value: float
    bound_type: str  # 'NaN', 'infinity', 'negative', 'excessive'
    reason: str


@dataclass
class HealthChange:
    """Record of a significant health metric change"""
    timestamp: datetime
    metric: str  # 'overall_health', 'data_freshness', etc.
    previous_value: float
    new_value: float
    change_percent: float
    contributing_factors: Dict[str, Any]


@dataclass
class StateInconsistency:
    """Record of a state inconsistency"""
    timestamp: datetime
    inconsistency_type: str  # 'date_mismatch', 'exposure_mismatch', etc.
    conflicting_values: Dict[str, Any]
    severity: str  # 'warning', 'error', 'critical'
    description: str


class StateTransitionLogger:
    """
    Logs state transitions, bound violations, health changes, and inconsistencies
    
    Maintains structured logs for diagnostic purposes with 90-day retention.
    """
    
    def __init__(self, log_dir: str = "data/logs/state_transitions"):
        """
        Initialize state transition logger
        
        Args:
            log_dir: Directory for storing transition logs
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log file paths
        self.transitions_file = self.log_dir / "state_transitions.parquet"
        self.violations_file = self.log_dir / "bound_violations.parquet"
        self.health_changes_file = self.log_dir / "health_changes.parquet"
        self.inconsistencies_file = self.log_dir / "state_inconsistencies.parquet"
        
        # Retention policy
        self.retention_days = 90
    
    def log_state_transition(
        self,
        component: str,
        field: str,
        previous_value: Any,
        new_value: Any,
        reason: Optional[str] = None
    ) -> None:
        """
        Log a state transition
        
        Args:
            component: Component that changed (e.g., 'market_state', 'portfolio')
            field: Field that changed (e.g., 'regime', 'allowed_exposure')
            previous_value: Previous value
            new_value: New value
            reason: Optional reason for change
        """
        # Calculate change magnitude for numeric values
        change_magnitude = None
        if isinstance(previous_value, (int, float)) and isinstance(new_value, (int, float)):
            if previous_value != 0:
                change_magnitude = abs((new_value - previous_value) / previous_value)
            else:
                change_magnitude = abs(new_value)
        
        transition = StateTransition(
            timestamp=datetime.now(),
            component=component,
            field=field,
            previous_value=previous_value,
            new_value=new_value,
            change_magnitude=change_magnitude,
            reason=reason
        )
        
        self._append_transition(transition)
        
        logger.info(
            f"State transition: {component}.{field} "
            f"{previous_value} → {new_value}"
            + (f" ({reason})" if reason else "")
        )
    
    def log_bound_violation(
        self,
        calculation_type: str,
        unbounded_value: float,
        bounded_value: float,
        bound_type: str,
        reason: str
    ) -> None:
        """
        Log an exposure bound violation
        
        Args:
            calculation_type: Type of calculation (e.g., 'allowed_exposure')
            unbounded_value: Original unbounded value
            bounded_value: Value after bounding
            bound_type: Type of bound applied ('NaN', 'infinity', 'negative', 'excessive')
            reason: Detailed reason for bounding
        """
        violation = BoundViolation(
            timestamp=datetime.now(),
            calculation_type=calculation_type,
            unbounded_value=unbounded_value,
            bounded_value=bounded_value,
            bound_type=bound_type,
            reason=reason
        )
        
        self._append_violation(violation)
        
        logger.warning(
            f"Bound violation: {calculation_type} "
            f"{unbounded_value:.4f} → {bounded_value:.4f} "
            f"({bound_type}: {reason})"
        )
    
    def log_health_change(
        self,
        metric: str,
        previous_value: float,
        new_value: float,
        contributing_factors: Dict[str, Any]
    ) -> None:
        """
        Log a significant health metric change (>10%)
        
        Args:
            metric: Health metric name (e.g., 'overall_health')
            previous_value: Previous value
            new_value: New value
            contributing_factors: Factors contributing to change
        """
        change_percent = abs((new_value - previous_value) / max(previous_value, 0.01)) * 100
        
        # Only log if change is significant
        if change_percent < 10:
            return
        
        health_change = HealthChange(
            timestamp=datetime.now(),
            metric=metric,
            previous_value=previous_value,
            new_value=new_value,
            change_percent=change_percent,
            contributing_factors=contributing_factors
        )
        
        self._append_health_change(health_change)
        
        direction = "↑" if new_value > previous_value else "↓"
        logger.info(
            f"Health change: {metric} "
            f"{previous_value:.1%} → {new_value:.1%} "
            f"({direction}{change_percent:.1f}%)"
        )
    
    def log_inconsistency(
        self,
        inconsistency_type: str,
        conflicting_values: Dict[str, Any],
        severity: str,
        description: str
    ) -> None:
        """
        Log a state inconsistency
        
        Args:
            inconsistency_type: Type of inconsistency (e.g., 'date_mismatch')
            conflicting_values: Dictionary of conflicting values
            severity: Severity level ('warning', 'error', 'critical')
            description: Human-readable description
        """
        inconsistency = StateInconsistency(
            timestamp=datetime.now(),
            inconsistency_type=inconsistency_type,
            conflicting_values=conflicting_values,
            severity=severity,
            description=description
        )
        
        self._append_inconsistency(inconsistency)
        
        log_func = {
            'warning': logger.warning,
            'error': logger.error,
            'critical': logger.critical
        }.get(severity, logger.warning)
        
        log_func(
            f"State inconsistency ({severity}): {inconsistency_type} - {description}"
        )
    
    def _append_transition(self, transition: StateTransition) -> None:
        """Append transition to log file"""
        try:
            # Convert to DataFrame row
            row = pd.DataFrame([{
                'timestamp': transition.timestamp,
                'component': transition.component,
                'field': transition.field,
                'previous_value': str(transition.previous_value),
                'new_value': str(transition.new_value),
                'change_magnitude': transition.change_magnitude,
                'reason': transition.reason
            }])
            
            # Append to file
            if self.transitions_file.exists():
                existing = pd.read_parquet(self.transitions_file)
                combined = pd.concat([existing, row], ignore_index=True)
            else:
                combined = row
            
            # Apply retention policy
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            combined = combined[combined['timestamp'] >= cutoff]
            
            # Save
            combined.to_parquet(self.transitions_file, index=False)
            
        except Exception as e:
            logger.error(f"Failed to append transition: {e}")
    
    def _append_violation(self, violation: BoundViolation) -> None:
        """Append violation to log file"""
        try:
            row = pd.DataFrame([{
                'timestamp': violation.timestamp,
                'calculation_type': violation.calculation_type,
                'unbounded_value': violation.unbounded_value,
                'bounded_value': violation.bounded_value,
                'bound_type': violation.bound_type,
                'reason': violation.reason
            }])
            
            if self.violations_file.exists():
                existing = pd.read_parquet(self.violations_file)
                combined = pd.concat([existing, row], ignore_index=True)
            else:
                combined = row
            
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            combined = combined[combined['timestamp'] >= cutoff]
            
            combined.to_parquet(self.violations_file, index=False)
            
        except Exception as e:
            logger.error(f"Failed to append violation: {e}")
    
    def _append_health_change(self, health_change: HealthChange) -> None:
        """Append health change to log file"""
        try:
            row = pd.DataFrame([{
                'timestamp': health_change.timestamp,
                'metric': health_change.metric,
                'previous_value': health_change.previous_value,
                'new_value': health_change.new_value,
                'change_percent': health_change.change_percent,
                'contributing_factors': json.dumps(health_change.contributing_factors)
            }])
            
            if self.health_changes_file.exists():
                existing = pd.read_parquet(self.health_changes_file)
                combined = pd.concat([existing, row], ignore_index=True)
            else:
                combined = row
            
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            combined = combined[combined['timestamp'] >= cutoff]
            
            combined.to_parquet(self.health_changes_file, index=False)
            
        except Exception as e:
            logger.error(f"Failed to append health change: {e}")
    
    def _append_inconsistency(self, inconsistency: StateInconsistency) -> None:
        """Append inconsistency to log file"""
        try:
            row = pd.DataFrame([{
                'timestamp': inconsistency.timestamp,
                'inconsistency_type': inconsistency.inconsistency_type,
                'conflicting_values': json.dumps(inconsistency.conflicting_values),
                'severity': inconsistency.severity,
                'description': inconsistency.description
            }])
            
            if self.inconsistencies_file.exists():
                existing = pd.read_parquet(self.inconsistencies_file)
                combined = pd.concat([existing, row], ignore_index=True)
            else:
                combined = row
            
            cutoff = datetime.now() - timedelta(days=self.retention_days)
            combined = combined[combined['timestamp'] >= cutoff]
            
            combined.to_parquet(self.inconsistencies_file, index=False)
            
        except Exception as e:
            logger.error(f"Failed to append inconsistency: {e}")
    
    def get_recent_transitions(self, hours: int = 24) -> pd.DataFrame:
        """
        Get recent state transitions
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            DataFrame of recent transitions
        """
        if not self.transitions_file.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(self.transitions_file)
        cutoff = datetime.now() - timedelta(hours=hours)
        return df[df['timestamp'] >= cutoff].sort_values('timestamp', ascending=False)
    
    def get_recent_violations(self, hours: int = 24) -> pd.DataFrame:
        """
        Get recent bound violations
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            DataFrame of recent violations
        """
        if not self.violations_file.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(self.violations_file)
        cutoff = datetime.now() - timedelta(hours=hours)
        return df[df['timestamp'] >= cutoff].sort_values('timestamp', ascending=False)
    
    def get_recent_health_changes(self, hours: int = 24) -> pd.DataFrame:
        """
        Get recent health changes
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            DataFrame of recent health changes
        """
        if not self.health_changes_file.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(self.health_changes_file)
        cutoff = datetime.now() - timedelta(hours=hours)
        return df[df['timestamp'] >= cutoff].sort_values('timestamp', ascending=False)
    
    def get_recent_inconsistencies(self, hours: int = 24) -> pd.DataFrame:
        """
        Get recent inconsistencies
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            DataFrame of recent inconsistencies
        """
        if not self.inconsistencies_file.exists():
            return pd.DataFrame()
        
        df = pd.read_parquet(self.inconsistencies_file)
        cutoff = datetime.now() - timedelta(hours=hours)
        return df[df['timestamp'] >= cutoff].sort_values('timestamp', ascending=False)
    
    def generate_diagnostic_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate diagnostic report of recent activity
        
        Args:
            hours: Number of hours to include in report
        
        Returns:
            Dictionary with diagnostic information
        """
        transitions = self.get_recent_transitions(hours)
        violations = self.get_recent_violations(hours)
        health_changes = self.get_recent_health_changes(hours)
        inconsistencies = self.get_recent_inconsistencies(hours)
        
        report = {
            'period_hours': hours,
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_transitions': len(transitions),
                'total_violations': len(violations),
                'total_health_changes': len(health_changes),
                'total_inconsistencies': len(inconsistencies)
            },
            'transitions_by_component': transitions['component'].value_counts().to_dict() if len(transitions) > 0 else {},
            'violations_by_type': violations['bound_type'].value_counts().to_dict() if len(violations) > 0 else {},
            'health_changes_by_metric': health_changes['metric'].value_counts().to_dict() if len(health_changes) > 0 else {},
            'inconsistencies_by_severity': inconsistencies['severity'].value_counts().to_dict() if len(inconsistencies) > 0 else {},
            'recent_critical_issues': []
        }
        
        # Add critical issues
        if len(inconsistencies) > 0:
            critical = inconsistencies[inconsistencies['severity'] == 'critical']
            for _, row in critical.head(10).iterrows():
                report['recent_critical_issues'].append({
                    'timestamp': row['timestamp'].isoformat(),
                    'type': row['inconsistency_type'],
                    'description': row['description']
                })
        
        return report


# Global logger instance
_global_logger: Optional[StateTransitionLogger] = None


def get_transition_logger() -> StateTransitionLogger:
    """Get global state transition logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = StateTransitionLogger()
    return _global_logger


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    logger_instance = StateTransitionLogger()
    
    # Log some example transitions
    logger_instance.log_state_transition(
        component='market_state',
        field='regime',
        previous_value='early-expansion',
        new_value='late-expansion',
        reason='Momentum indicators crossed threshold'
    )
    
    logger_instance.log_bound_violation(
        calculation_type='allowed_exposure',
        unbounded_value=3.87,
        bounded_value=1.0,
        bound_type='excessive',
        reason='Division by near-zero volatility'
    )
    
    logger_instance.log_health_change(
        metric='overall_health',
        previous_value=0.85,
        new_value=0.62,
        contributing_factors={
            'data_freshness': 0.95,
            'market_consistency': 0.45,
            'portfolio_stability': 0.50
        }
    )
    
    logger_instance.log_inconsistency(
        inconsistency_type='exposure_mismatch',
        conflicting_values={
            'allowed_exposure': 0.60,
            'actual_exposure': 0.90
        },
        severity='warning',
        description='Portfolio exposure exceeds market brain limit'
    )
    
    # Generate report
    report = logger_instance.generate_diagnostic_report(hours=24)
    print("\nDiagnostic Report:")
    print(json.dumps(report, indent=2))
