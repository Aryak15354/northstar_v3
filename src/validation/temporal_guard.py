"""
Temporal Guard - Absolute Prevention of Future Data Access

This is the cornerstone component that enforces point-in-time data integrity.
NO future data can leak into historical simulations under any circumstances.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import logging
from dataclasses import dataclass
from enum import Enum

class TemporalViolationType(Enum):
    FUTURE_DATA_ACCESS = "future_data_access"
    BACKWARD_TIME_TRAVEL = "backward_time_travel"
    INVALID_TIME_ADVANCEMENT = "invalid_time_advancement"
    DATA_TIMESTAMP_VIOLATION = "data_timestamp_violation"

@dataclass
class TemporalViolation:
    violation_type: TemporalViolationType
    requested_timestamp: datetime
    current_simulation_date: datetime
    context: str
    stack_trace: Optional[str] = None

class TemporalViolationError(Exception):
    """Raised when future data is accessed during simulation"""
    def __init__(self, violation: TemporalViolation):
        self.violation = violation
        message = (
            f"TEMPORAL VIOLATION: {violation.violation_type.value}\n"
            f"Requested: {violation.requested_timestamp}\n"
            f"Current simulation date: {violation.current_simulation_date}\n"
            f"Context: {violation.context}"
        )
        super().__init__(message)

class TemporalGuard:
    """
    Enforces absolute temporal integrity during walk-forward simulation.
    
    This component is the final arbiter of what data can be accessed at any point
    in the simulation. It maintains strict boundaries and prevents any form of
    look-ahead bias.
    """
    
    def __init__(self, simulation_start_date: datetime):
        self.simulation_start_date = simulation_start_date
        self.current_simulation_date = simulation_start_date
        self.data_cutoff_date = simulation_start_date
        
        # Violation tracking for audit
        self.violations_detected: List[TemporalViolation] = []
        self.access_log: List[Dict[str, Any]] = []
        
        # Configuration
        self.strict_mode = True  # No tolerance for any violations
        self.log_all_access = True  # Complete audit trail
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"TemporalGuard initialized for simulation starting {simulation_start_date}")
    
    def validate_data_access(self, data_timestamp: datetime, context: str = "unknown") -> bool:
        """
        Validates if data with given timestamp can be accessed.
        
        Args:
            data_timestamp: Timestamp of the data being accessed
            context: Description of what is trying to access the data
            
        Returns:
            True if access is allowed, False otherwise
            
        Raises:
            TemporalViolationError: If strict_mode is True and violation detected
        """
        # Log all access attempts for audit trail
        if self.log_all_access:
            self.access_log.append({
                'timestamp': datetime.now(),
                'data_timestamp': data_timestamp,
                'simulation_date': self.current_simulation_date,
                'context': context,
                'allowed': data_timestamp <= self.data_cutoff_date
            })
        
        # Check for temporal violation
        if data_timestamp > self.data_cutoff_date:
            violation = TemporalViolation(
                violation_type=TemporalViolationType.FUTURE_DATA_ACCESS,
                requested_timestamp=data_timestamp,
                current_simulation_date=self.current_simulation_date,
                context=context
            )
            
            self.violations_detected.append(violation)
            self.logger.error(f"Temporal violation detected: {violation}")
            
            if self.strict_mode:
                raise TemporalViolationError(violation)
            
            return False
        
        return True
    
    def advance_time(self, new_date: datetime, context: str = "time_advancement") -> None:
        """
        Advances simulation time and updates data availability.
        
        Args:
            new_date: New simulation date to advance to
            context: Context for this time advancement
            
        Raises:
            TemporalViolationError: If attempting to move backwards in time
        """
        if new_date < self.current_simulation_date:
            violation = TemporalViolation(
                violation_type=TemporalViolationType.BACKWARD_TIME_TRAVEL,
                requested_timestamp=new_date,
                current_simulation_date=self.current_simulation_date,
                context=context
            )
            
            self.violations_detected.append(violation)
            
            if self.strict_mode:
                raise TemporalViolationError(violation)
            return
        
        # Validate reasonable time advancement (no jumps > 1 year)
        if new_date - self.current_simulation_date > timedelta(days=365):
            violation = TemporalViolation(
                violation_type=TemporalViolationType.INVALID_TIME_ADVANCEMENT,
                requested_timestamp=new_date,
                current_simulation_date=self.current_simulation_date,
                context=f"Large time jump: {context}"
            )
            
            self.violations_detected.append(violation)
            self.logger.warning(f"Large time advancement detected: {violation}")
        
        # Update simulation state
        previous_date = self.current_simulation_date
        self.current_simulation_date = new_date
        self.data_cutoff_date = new_date
        
        self.logger.info(f"Time advanced from {previous_date} to {new_date} ({context})")
    
    def get_available_data_cutoff(self) -> datetime:
        """Returns the current data cutoff date"""
        return self.data_cutoff_date
    
    def get_current_simulation_date(self) -> datetime:
        """Returns the current simulation date"""
        return self.current_simulation_date
    
    def validate_timestamp_batch(self, timestamps: List[datetime], context: str = "batch_validation") -> Dict[datetime, bool]:
        """
        Validates multiple timestamps at once for efficiency.
        
        Args:
            timestamps: List of timestamps to validate
            context: Context for this batch validation
            
        Returns:
            Dictionary mapping timestamps to their validation results
        """
        results = {}
        
        for timestamp in timestamps:
            try:
                results[timestamp] = self.validate_data_access(timestamp, f"{context}_{timestamp}")
            except TemporalViolationError:
                results[timestamp] = False
        
        return results
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Returns summary of all temporal violations detected"""
        violation_counts = {}
        for violation in self.violations_detected:
            violation_type = violation.violation_type.value
            violation_counts[violation_type] = violation_counts.get(violation_type, 0) + 1
        
        return {
            'total_violations': len(self.violations_detected),
            'violation_types': violation_counts,
            'first_violation': self.violations_detected[0] if self.violations_detected else None,
            'last_violation': self.violations_detected[-1] if self.violations_detected else None,
            'simulation_start': self.simulation_start_date,
            'current_date': self.current_simulation_date
        }
    
    def reset_to_date(self, reset_date: datetime, context: str = "reset") -> None:
        """
        Resets simulation to a specific date (for testing purposes only).
        
        Args:
            reset_date: Date to reset simulation to
            context: Context for this reset
        """
        self.logger.warning(f"TEMPORAL RESET: Resetting simulation from {self.current_simulation_date} to {reset_date}")
        
        self.current_simulation_date = reset_date
        self.data_cutoff_date = reset_date
        
        # Clear violations that occurred after reset date
        self.violations_detected = [
            v for v in self.violations_detected 
            if v.current_simulation_date <= reset_date
        ]
    
    def create_checkpoint(self) -> Dict[str, Any]:
        """Creates a checkpoint of current temporal state"""
        return {
            'simulation_date': self.current_simulation_date,
            'data_cutoff': self.data_cutoff_date,
            'violations_count': len(self.violations_detected),
            'access_log_count': len(self.access_log)
        }
    
    def restore_checkpoint(self, checkpoint: Dict[str, Any]) -> None:
        """Restores temporal state from checkpoint"""
        self.current_simulation_date = checkpoint['simulation_date']
        self.data_cutoff_date = checkpoint['data_cutoff']
        
        # Truncate logs to checkpoint state
        violations_to_keep = checkpoint['violations_count']
        access_to_keep = checkpoint['access_log_count']
        
        self.violations_detected = self.violations_detected[:violations_to_keep]
        self.access_log = self.access_log[:access_to_keep]
        
        self.logger.info(f"Temporal state restored to checkpoint: {checkpoint}")


class DataDispatcher:
    """
    Dispatches data with temporal validation.
    
    All data access must go through this dispatcher to ensure temporal integrity.
    """
    
    def __init__(self, temporal_guard: TemporalGuard):
        self.temporal_guard = temporal_guard
        self.logger = logging.getLogger(__name__)
    
    def get_data_at_timestamp(self, data_source: str, timestamp: datetime, 
                            context: str = "data_request") -> Optional[Any]:
        """
        Retrieves data at specific timestamp with temporal validation.
        
        Args:
            data_source: Identifier for the data source
            timestamp: Timestamp of requested data
            context: Context for this data request
            
        Returns:
            Data if temporal validation passes, None otherwise
        """
        full_context = f"{context}::{data_source}"
        
        if not self.temporal_guard.validate_data_access(timestamp, full_context):
            self.logger.error(f"Data access denied for {data_source} at {timestamp}")
            return None
        
        # Here would be actual data retrieval logic
        # For now, we just validate the temporal access
        self.logger.debug(f"Data access granted for {data_source} at {timestamp}")
        return {"timestamp": timestamp, "source": data_source, "validated": True}
    
    def get_data_range(self, data_source: str, start_time: datetime, 
                      end_time: datetime, context: str = "range_request") -> Optional[List[Any]]:
        """
        Retrieves data range with temporal validation.
        
        Args:
            data_source: Identifier for the data source
            start_time: Start of time range
            end_time: End of time range (must be <= current simulation date)
            context: Context for this range request
            
        Returns:
            List of data if temporal validation passes, None otherwise
        """
        full_context = f"{context}::{data_source}::range"
        
        # Validate end time (most restrictive)
        if not self.temporal_guard.validate_data_access(end_time, full_context):
            self.logger.error(f"Data range access denied for {data_source} ending at {end_time}")
            return None
        
        # Here would be actual data range retrieval logic
        self.logger.debug(f"Data range access granted for {data_source} from {start_time} to {end_time}")
        return [{"timestamp": end_time, "source": data_source, "range": True}]


class TimeController:
    """
    Controls time advancement in the simulation.
    
    Ensures proper sequencing and validation of time progression.
    """
    
    def __init__(self, temporal_guard: TemporalGuard, start_date: datetime, end_date: datetime):
        self.temporal_guard = temporal_guard
        self.start_date = start_date
        self.end_date = end_date
        self.current_date = start_date
        
        self.logger = logging.getLogger(__name__)
    
    def get_next_trading_day(self, current_date: datetime) -> Optional[datetime]:
        """
        Gets the next trading day after current_date.
        
        Args:
            current_date: Current date
            
        Returns:
            Next trading day or None if past end_date
        """
        next_date = current_date + timedelta(days=1)
        
        # Skip weekends (basic implementation)
        while next_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            next_date += timedelta(days=1)
        
        if next_date > self.end_date:
            return None
        
        return next_date
    
    def advance_to_next_day(self) -> bool:
        """
        Advances simulation to next trading day.
        
        Returns:
            True if advancement successful, False if simulation complete
        """
        next_day = self.get_next_trading_day(self.current_date)
        
        if next_day is None:
            self.logger.info("Simulation complete - reached end date")
            return False
        
        self.temporal_guard.advance_time(next_day, "daily_advancement")
        self.current_date = next_day
        
        return True
    
    def get_simulation_progress(self) -> float:
        """Returns simulation progress as percentage (0.0 to 1.0)"""
        total_days = (self.end_date - self.start_date).days
        elapsed_days = (self.current_date - self.start_date).days
        
        return min(1.0, elapsed_days / total_days) if total_days > 0 else 1.0
    
    def get_remaining_days(self) -> int:
        """Returns number of trading days remaining in simulation"""
        remaining = 0
        test_date = self.current_date
        
        while test_date <= self.end_date:
            test_date = self.get_next_trading_day(test_date)
            if test_date is None:
                break
            remaining += 1
        
        return remaining