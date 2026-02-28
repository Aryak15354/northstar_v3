"""
Property-Based Tests for State Transition Logger

Tests logging of state transitions, bound violations, health changes, and inconsistencies.
"""

import pytest
from hypothesis import given, strategies as st, settings
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil
import json

from src.cohesion.state_transition_logger import (
    StateTransitionLogger,
    get_transition_logger
)


class TestStateTransitionLoggerProperties:
    """Property-based tests for state transition logger"""
    
    def setup_method(self):
        """Create temporary directory for each test"""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir) / "logs"
        self.logger = StateTransitionLogger(str(self.log_dir))
    
    def teardown_method(self):
        """Clean up temporary directory"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    @settings(max_examples=100)
    @given(
        component=st.sampled_from(['market_state', 'portfolio', 'risk_state']),
        field=st.sampled_from(['regime', 'exposure', 'volatility']),
        prev_value=st.floats(min_value=0.0, max_value=1.0),
        new_value=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_property_state_transition_logged(
        self, component, field, prev_value, new_value
    ):
        """
        Property: State transitions are logged
        
        For any state transition, the log file should contain that transition.
        """
        # Log transition
        self.logger.log_state_transition(
            component=component,
            field=field,
            previous_value=prev_value,
            new_value=new_value
        )
        
        # Verify logged
        transitions = self.logger.get_recent_transitions(hours=1)
        
        assert len(transitions) > 0
        latest = transitions.iloc[0]
        assert latest['component'] == component
        assert latest['field'] == field
        assert float(latest['previous_value']) == pytest.approx(prev_value, abs=0.01)
        assert float(latest['new_value']) == pytest.approx(new_value, abs=0.01)
    
    @settings(max_examples=100)
    @given(
        unbounded=st.floats(min_value=1.1, max_value=10.0),
        bounded=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_property_bound_violation_logged(self, unbounded, bounded):
        """
        Property: Bound violations are logged
        
        For any bound violation, the log file should contain that violation.
        """
        # Log violation
        self.logger.log_bound_violation(
            calculation_type='allowed_exposure',
            unbounded_value=unbounded,
            bounded_value=bounded,
            bound_type='excessive',
            reason=f'Value {unbounded:.4f} exceeded maximum'
        )
        
        # Verify logged
        violations = self.logger.get_recent_violations(hours=1)
        
        assert len(violations) > 0
        latest = violations.iloc[0]
        assert latest['calculation_type'] == 'allowed_exposure'
        assert latest['unbounded_value'] == pytest.approx(unbounded, abs=0.01)
        assert latest['bounded_value'] == pytest.approx(bounded, abs=0.01)
        assert latest['bound_type'] == 'excessive'
    
    @settings(max_examples=100)
    @given(
        prev_health=st.floats(min_value=0.01, max_value=1.0),  # Avoid division by near-zero
        new_health=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_property_significant_health_change_logged(self, prev_health, new_health):
        """
        Property: Significant health changes (>10%) are logged
        
        For any health change >10%, the log file should contain that change.
        """
        # Calculate change percentage (same formula as logger)
        change_pct = abs((new_health - prev_health) / max(prev_health, 0.01)) * 100
        
        # Log health change
        self.logger.log_health_change(
            metric='overall_health',
            previous_value=prev_health,
            new_value=new_health,
            contributing_factors={'test': 'data'}
        )
        
        # Verify logged only if significant
        health_changes = self.logger.get_recent_health_changes(hours=1)
        
        if change_pct >= 10:
            assert len(health_changes) > 0, f"Expected health change to be logged (change={change_pct:.1f}%)"
            latest = health_changes.iloc[0]
            assert latest['metric'] == 'overall_health'
            assert latest['previous_value'] == pytest.approx(prev_health, abs=0.01)
            assert latest['new_value'] == pytest.approx(new_health, abs=0.01)
        # Note: We don't assert len == 0 for small changes because previous test runs
        # may have left significant changes in the file
    
    @settings(max_examples=100)
    @given(
        severity=st.sampled_from(['warning', 'error', 'critical']),
        allowed=st.floats(min_value=0.0, max_value=1.0),
        actual=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_property_inconsistency_logged(self, severity, allowed, actual):
        """
        Property: State inconsistencies are logged
        
        For any inconsistency, the log file should contain that inconsistency.
        """
        # Log inconsistency
        self.logger.log_inconsistency(
            inconsistency_type='exposure_mismatch',
            conflicting_values={
                'allowed_exposure': allowed,
                'actual_exposure': actual
            },
            severity=severity,
            description=f'Exposure mismatch: {allowed:.2f} vs {actual:.2f}'
        )
        
        # Verify logged
        inconsistencies = self.logger.get_recent_inconsistencies(hours=1)
        
        assert len(inconsistencies) > 0
        latest = inconsistencies.iloc[0]
        assert latest['inconsistency_type'] == 'exposure_mismatch'
        assert latest['severity'] == severity
        
        # Parse conflicting values
        values = json.loads(latest['conflicting_values'])
        assert values['allowed_exposure'] == pytest.approx(allowed, abs=0.01)
        assert values['actual_exposure'] == pytest.approx(actual, abs=0.01)
    
    def test_retention_policy_enforced(self):
        """
        Integration test: Retention policy removes old logs
        """
        # Log transition with old timestamp
        old_date = datetime.now() - timedelta(days=100)
        
        # Manually create old log entry
        old_row = pd.DataFrame([{
            'timestamp': old_date,
            'component': 'test',
            'field': 'test',
            'previous_value': '0.5',
            'new_value': '0.6',
            'change_magnitude': 0.2,
            'reason': 'test'
        }])
        old_row.to_parquet(self.logger.transitions_file, index=False)
        
        # Log new transition (should trigger cleanup)
        self.logger.log_state_transition(
            component='market_state',
            field='regime',
            previous_value='early-expansion',
            new_value='late-expansion'
        )
        
        # Verify old entry removed
        transitions = pd.read_parquet(self.logger.transitions_file)
        assert all(transitions['timestamp'] >= datetime.now() - timedelta(days=90))
    
    def test_multiple_transitions_accumulated(self):
        """
        Integration test: Multiple transitions are accumulated
        """
        # Log multiple transitions
        for i in range(5):
            self.logger.log_state_transition(
                component='market_state',
                field='allowed_exposure',
                previous_value=0.5 + i * 0.1,
                new_value=0.6 + i * 0.1
            )
        
        # Verify all logged
        transitions = self.logger.get_recent_transitions(hours=1)
        assert len(transitions) >= 5
    
    def test_diagnostic_report_generation(self):
        """
        Integration test: Diagnostic report includes all log types
        """
        # Log various events
        self.logger.log_state_transition(
            component='market_state',
            field='regime',
            previous_value='early-expansion',
            new_value='late-expansion'
        )
        
        self.logger.log_bound_violation(
            calculation_type='allowed_exposure',
            unbounded_value=2.5,
            bounded_value=1.0,
            bound_type='excessive',
            reason='Test violation'
        )
        
        self.logger.log_health_change(
            metric='overall_health',
            previous_value=0.8,
            new_value=0.5,
            contributing_factors={'test': 'data'}
        )
        
        self.logger.log_inconsistency(
            inconsistency_type='test',
            conflicting_values={'a': 1, 'b': 2},
            severity='warning',
            description='Test inconsistency'
        )
        
        # Generate report
        report = self.logger.generate_diagnostic_report(hours=1)
        
        # Verify report structure
        assert 'summary' in report
        assert report['summary']['total_transitions'] >= 1
        assert report['summary']['total_violations'] >= 1
        assert report['summary']['total_health_changes'] >= 1
        assert report['summary']['total_inconsistencies'] >= 1
    
    def test_change_magnitude_calculated_for_numeric_values(self):
        """
        Integration test: Change magnitude calculated for numeric transitions
        """
        # Log numeric transition
        self.logger.log_state_transition(
            component='market_state',
            field='allowed_exposure',
            previous_value=0.5,
            new_value=0.75
        )
        
        # Verify change magnitude calculated
        transitions = self.logger.get_recent_transitions(hours=1)
        latest = transitions.iloc[0]
        
        # Change magnitude should be (0.75 - 0.5) / 0.5 = 0.5
        assert latest['change_magnitude'] == pytest.approx(0.5, abs=0.01)
    
    def test_change_magnitude_none_for_string_values(self):
        """
        Integration test: Change magnitude is None for string transitions
        """
        # Log string transition
        self.logger.log_state_transition(
            component='market_state',
            field='regime',
            previous_value='early-expansion',
            new_value='late-expansion'
        )
        
        # Verify change magnitude is None
        transitions = self.logger.get_recent_transitions(hours=1)
        latest = transitions.iloc[0]
        
        assert pd.isna(latest['change_magnitude'])
    
    def test_global_logger_singleton(self):
        """
        Integration test: Global logger returns same instance
        """
        logger1 = get_transition_logger()
        logger2 = get_transition_logger()
        
        assert logger1 is logger2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
