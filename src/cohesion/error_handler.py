"""
Comprehensive Error Handling System for Northstar V3 System Cohesion

This module implements the error handling system with fail-fast principles,
severity classification, automatic recovery, and error escalation.

Implements Properties 21-22 (E1-E2) from the design document.
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
import threading
import time
import json
import os
from collections import defaultdict, deque

from src.service_interfaces import IErrorHandler, ValidationResult

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """Error severity levels with escalation priorities"""
    CRITICAL = 1    # System integrity compromised - immediate termination
    HIGH = 2        # Data integrity issues - quarantine and alert
    MEDIUM = 3      # Performance degradation - log and monitor
    LOW = 4         # Minor issues - log for analysis

class ErrorCategory(Enum):
    """Error categories for classification"""
    DATA_CORRUPTION = "data_corruption"
    CONFIGURATION_ERROR = "configuration_error"
    COMPONENT_FAILURE = "component_failure"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    TEMPORAL_VIOLATION = "temporal_violation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPENDENCY_ERROR = "dependency_error"

class RecoveryStrategy(Enum):
    """Recovery strategies for different error types"""
    FAIL_FAST = "fail_fast"
    RETRY_EXPONENTIAL = "retry_exponential"
    QUARANTINE_DATA = "quarantine_data"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    ALERT_OPERATOR = "alert_operator"
    AUTOMATIC_RECOVERY = "automatic_recovery"

@dataclass
class SystemError:
    """Comprehensive error representation"""
    error_id: str
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    component: str
    timestamp: datetime
    context: Dict[str, Any]
    stack_trace: str
    recovery_strategy: RecoveryStrategy
    escalation_level: int = 0
    retry_count: int = 0
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None
    resolution_method: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            'error_id': self.error_id,
            'severity': self.severity.name,
            'category': self.category.value,
            'message': self.message,
            'component': self.component,
            'timestamp': self.timestamp.isoformat(),
            'context': self.context,
            'stack_trace': self.stack_trace,
            'recovery_strategy': self.recovery_strategy.value,
            'escalation_level': self.escalation_level,
            'retry_count': self.retry_count,
            'resolved': self.resolved,
            'resolution_timestamp': self.resolution_timestamp.isoformat() if self.resolution_timestamp else None,
            'resolution_method': self.resolution_method
        }

@dataclass
class ErrorPattern:
    """Error pattern for analysis"""
    pattern_id: str
    error_category: ErrorCategory
    component: str
    frequency: int
    first_occurrence: datetime
    last_occurrence: datetime
    average_resolution_time: float
    success_rate: float

@dataclass
class RecoveryAction:
    """Recovery action definition"""
    action_id: str
    name: str
    description: str
    strategy: RecoveryStrategy
    max_retries: int
    backoff_multiplier: float
    timeout_seconds: float
    success_callback: Optional[Callable] = None
    failure_callback: Optional[Callable] = None

class ErrorHandler(IErrorHandler):
    """
    Comprehensive error handling system.
    
    Implements Properties 21-22 (E1-E2):
    - Critical Error Fail-Fast (E1)
    - Error Escalation Consistency (E2)
    """
    
    def __init__(self, 
                 error_log_dir: str = "logs/errors",
                 max_error_history: int = 10000,
                 pattern_analysis_window: int = 3600):  # 1 hour
        self.error_log_dir = error_log_dir
        self.max_error_history = max_error_history
        self.pattern_analysis_window = pattern_analysis_window
        
        # Create error log directory
        os.makedirs(error_log_dir, exist_ok=True)
        
        # Error storage
        self.active_errors: Dict[str, SystemError] = {}
        self.error_history: deque = deque(maxlen=max_error_history)
        self.error_patterns: Dict[str, ErrorPattern] = {}
        
        # Recovery actions registry
        self.recovery_actions: Dict[RecoveryStrategy, RecoveryAction] = {}
        
        # Escalation configuration
        self.escalation_rules: Dict[ErrorSeverity, Dict[str, Any]] = {
            ErrorSeverity.CRITICAL: {
                'immediate_escalation': True,
                'max_escalation_level': 3,
                'escalation_timeout': 300,  # 5 minutes
                'requires_operator': True
            },
            ErrorSeverity.HIGH: {
                'immediate_escalation': False,
                'max_escalation_level': 2,
                'escalation_timeout': 900,  # 15 minutes
                'requires_operator': True
            },
            ErrorSeverity.MEDIUM: {
                'immediate_escalation': False,
                'max_escalation_level': 1,
                'escalation_timeout': 3600,  # 1 hour
                'requires_operator': False
            },
            ErrorSeverity.LOW: {
                'immediate_escalation': False,
                'max_escalation_level': 0,
                'escalation_timeout': 86400,  # 24 hours
                'requires_operator': False
            }
        }
        
        # Subscribers for error notifications
        self.error_subscribers: Dict[ErrorSeverity, List[Callable]] = defaultdict(list)
        
        # Thread safety
        self._lock = threading.Lock()
        self._error_counter = 0
        
        # Background processing
        self._running = True
        self._background_thread = threading.Thread(target=self._background_processor, daemon=True)
        self._background_thread.start()
        
        # Initialize recovery actions
        self._initialize_recovery_actions()
        
        logger.info("Error handler initialized")
    
    def _initialize_recovery_actions(self):
        """Initialize standard recovery actions"""
        self.recovery_actions = {
            RecoveryStrategy.FAIL_FAST: RecoveryAction(
                action_id="fail_fast",
                name="Fail Fast",
                description="Immediately terminate system on critical errors",
                strategy=RecoveryStrategy.FAIL_FAST,
                max_retries=0,
                backoff_multiplier=0.0,
                timeout_seconds=0.0
            ),
            RecoveryStrategy.RETRY_EXPONENTIAL: RecoveryAction(
                action_id="retry_exponential",
                name="Exponential Backoff Retry",
                description="Retry with exponential backoff for transient failures",
                strategy=RecoveryStrategy.RETRY_EXPONENTIAL,
                max_retries=5,
                backoff_multiplier=2.0,
                timeout_seconds=300.0
            ),
            RecoveryStrategy.QUARANTINE_DATA: RecoveryAction(
                action_id="quarantine_data",
                name="Data Quarantine",
                description="Quarantine corrupted data and alert operators",
                strategy=RecoveryStrategy.QUARANTINE_DATA,
                max_retries=0,
                backoff_multiplier=0.0,
                timeout_seconds=60.0
            ),
            RecoveryStrategy.GRACEFUL_DEGRADATION: RecoveryAction(
                action_id="graceful_degradation",
                name="Graceful Degradation",
                description="Reduce functionality while maintaining core operations",
                strategy=RecoveryStrategy.GRACEFUL_DEGRADATION,
                max_retries=3,
                backoff_multiplier=1.5,
                timeout_seconds=120.0
            ),
            RecoveryStrategy.ALERT_OPERATOR: RecoveryAction(
                action_id="alert_operator",
                name="Operator Alert",
                description="Alert human operators for manual intervention",
                strategy=RecoveryStrategy.ALERT_OPERATOR,
                max_retries=0,
                backoff_multiplier=0.0,
                timeout_seconds=30.0
            ),
            RecoveryStrategy.AUTOMATIC_RECOVERY: RecoveryAction(
                action_id="automatic_recovery",
                name="Automatic Recovery",
                description="Attempt automatic recovery procedures",
                strategy=RecoveryStrategy.AUTOMATIC_RECOVERY,
                max_retries=3,
                backoff_multiplier=1.0,
                timeout_seconds=180.0
            )
        }
    
    def handle_error(self, 
                    error: Exception, 
                    component: str,
                    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                    category: ErrorCategory = ErrorCategory.COMPONENT_FAILURE,
                    context: Optional[Dict[str, Any]] = None,
                    recovery_strategy: Optional[RecoveryStrategy] = None) -> SystemError:
        """
        Handle system error with comprehensive processing.
        
        Implements Property 21: Critical Error Fail-Fast (E1)
        """
        with self._lock:
            self._error_counter += 1
            error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._error_counter:04d}"
            
            # Determine recovery strategy if not provided
            if recovery_strategy is None:
                recovery_strategy = self._determine_recovery_strategy(severity, category)
            
            # Create system error
            system_error = SystemError(
                error_id=error_id,
                severity=severity,
                category=category,
                message=str(error),
                component=component,
                timestamp=datetime.now(),
                context=context or {},
                stack_trace=traceback.format_exc(),
                recovery_strategy=recovery_strategy
            )
            
            # Store error
            self.active_errors[error_id] = system_error
            self.error_history.append(system_error)
            
            # Log error
            self._log_error(system_error)
            
            # Property 21: Critical Error Fail-Fast (E1)
            if severity == ErrorSeverity.CRITICAL:
                logger.critical(f"CRITICAL ERROR - FAILING FAST: {system_error.message}")
                self._execute_fail_fast(system_error)
                return system_error
            
            # Execute recovery strategy
            self._execute_recovery_strategy(system_error)
            
            # Property 22: Error Escalation Consistency (E2)
            self._handle_escalation(system_error)
            
            # Notify subscribers
            self._notify_error_subscribers(system_error)
            
            # Update error patterns
            self._update_error_patterns(system_error)
            
            logger.info(f"Error handled: {error_id} - {severity.name} - {category.value}")
            
            return system_error
    
    def _determine_recovery_strategy(self, 
                                   severity: ErrorSeverity, 
                                   category: ErrorCategory) -> RecoveryStrategy:
        """Determine appropriate recovery strategy"""
        
        # All critical errors should fail fast
        if severity == ErrorSeverity.CRITICAL:
            return RecoveryStrategy.FAIL_FAST
        
        strategy_map = {
            (ErrorSeverity.HIGH, ErrorCategory.DATA_CORRUPTION): RecoveryStrategy.QUARANTINE_DATA,
            (ErrorSeverity.HIGH, ErrorCategory.TEMPORAL_VIOLATION): RecoveryStrategy.QUARANTINE_DATA,
            (ErrorSeverity.HIGH, ErrorCategory.VALIDATION_ERROR): RecoveryStrategy.ALERT_OPERATOR,
            
            (ErrorSeverity.MEDIUM, ErrorCategory.NETWORK_ERROR): RecoveryStrategy.RETRY_EXPONENTIAL,
            (ErrorSeverity.MEDIUM, ErrorCategory.RESOURCE_EXHAUSTION): RecoveryStrategy.GRACEFUL_DEGRADATION,
            (ErrorSeverity.MEDIUM, ErrorCategory.DEPENDENCY_ERROR): RecoveryStrategy.AUTOMATIC_RECOVERY,
            
            (ErrorSeverity.LOW, ErrorCategory.VALIDATION_ERROR): RecoveryStrategy.AUTOMATIC_RECOVERY,
            (ErrorSeverity.LOW, ErrorCategory.NETWORK_ERROR): RecoveryStrategy.RETRY_EXPONENTIAL,
        }
        
        return strategy_map.get((severity, category), RecoveryStrategy.ALERT_OPERATOR)
    
    def _execute_fail_fast(self, error: SystemError):
        """
        Execute fail-fast behavior for critical errors.
        
        Implements Property 21: Critical Error Fail-Fast (E1)
        """
        # Log critical error details
        critical_log = {
            'error_id': error.error_id,
            'message': error.message,
            'component': error.component,
            'timestamp': error.timestamp.isoformat(),
            'context': error.context,
            'stack_trace': error.stack_trace
        }
        
        # Write critical error to dedicated file
        critical_file = os.path.join(self.error_log_dir, f"CRITICAL_{error.error_id}.json")
        with open(critical_file, 'w') as f:
            json.dump(critical_log, f, indent=2)
        
        # Alert all critical error subscribers immediately
        for callback in self.error_subscribers[ErrorSeverity.CRITICAL]:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in critical error callback: {e}")
        
        # Mark system as terminated
        error.resolved = False
        error.resolution_method = "SYSTEM_TERMINATED"
        
        # In a real system, this would trigger system shutdown
        # For testing, we'll raise a specific exception
        raise SystemExit(f"CRITICAL ERROR - SYSTEM TERMINATED: {error.message}")
    
    def _execute_recovery_strategy(self, error: SystemError):
        """Execute the recovery strategy for the error"""
        strategy = error.recovery_strategy
        action = self.recovery_actions.get(strategy)
        
        if not action:
            logger.error(f"No recovery action defined for strategy: {strategy}")
            return
        
        logger.info(f"Executing recovery strategy: {strategy.value} for error {error.error_id}")
        
        if strategy == RecoveryStrategy.RETRY_EXPONENTIAL:
            self._execute_retry_strategy(error, action)
        elif strategy == RecoveryStrategy.QUARANTINE_DATA:
            self._execute_quarantine_strategy(error, action)
        elif strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
            self._execute_degradation_strategy(error, action)
        elif strategy == RecoveryStrategy.ALERT_OPERATOR:
            self._execute_alert_strategy(error, action)
        elif strategy == RecoveryStrategy.AUTOMATIC_RECOVERY:
            self._execute_automatic_recovery(error, action)
    
    def _execute_retry_strategy(self, error: SystemError, action: RecoveryAction):
        """Execute exponential backoff retry strategy"""
        if error.retry_count >= action.max_retries:
            logger.warning(f"Max retries exceeded for error {error.error_id}")
            error.recovery_strategy = RecoveryStrategy.ALERT_OPERATOR
            return
        
        # Calculate backoff delay
        delay = action.backoff_multiplier ** error.retry_count
        
        logger.info(f"Scheduling retry {error.retry_count + 1} for error {error.error_id} in {delay}s")
        
        # In a real system, this would schedule the retry
        # For now, we'll just increment the retry count
        error.retry_count += 1
    
    def _execute_quarantine_strategy(self, error: SystemError, action: RecoveryAction):
        """Execute data quarantine strategy"""
        quarantine_dir = os.path.join(self.error_log_dir, "quarantine")
        os.makedirs(quarantine_dir, exist_ok=True)
        
        quarantine_file = os.path.join(quarantine_dir, f"quarantine_{error.error_id}.json")
        
        quarantine_data = {
            'error_id': error.error_id,
            'timestamp': error.timestamp.isoformat(),
            'component': error.component,
            'context': error.context,
            'reason': error.message
        }
        
        with open(quarantine_file, 'w') as f:
            json.dump(quarantine_data, f, indent=2)
        
        logger.warning(f"Data quarantined for error {error.error_id}")
        
        # Alert operators
        self._alert_operators(error, f"Data quarantined: {error.message}")
    
    def _execute_degradation_strategy(self, error: SystemError, action: RecoveryAction):
        """Execute graceful degradation strategy"""
        logger.info(f"Initiating graceful degradation for error {error.error_id}")
        
        # In a real system, this would disable non-critical features
        degradation_info = {
            'error_id': error.error_id,
            'component': error.component,
            'degradation_level': 'partial',
            'timestamp': datetime.now().isoformat()
        }
        
        error.context['degradation_applied'] = degradation_info
        logger.info(f"Graceful degradation applied for component {error.component}")
    
    def _execute_alert_strategy(self, error: SystemError, action: RecoveryAction):
        """Execute operator alert strategy"""
        self._alert_operators(error, f"Manual intervention required: {error.message}")
    
    def _execute_automatic_recovery(self, error: SystemError, action: RecoveryAction):
        """Execute automatic recovery procedures"""
        logger.info(f"Attempting automatic recovery for error {error.error_id}")
        
        # In a real system, this would execute component-specific recovery
        recovery_success = self._attempt_component_recovery(error)
        
        if recovery_success:
            error.resolved = True
            error.resolution_timestamp = datetime.now()
            error.resolution_method = "automatic_recovery"
            logger.info(f"Automatic recovery successful for error {error.error_id}")
        else:
            logger.warning(f"Automatic recovery failed for error {error.error_id}")
            error.recovery_strategy = RecoveryStrategy.ALERT_OPERATOR
    
    def _attempt_component_recovery(self, error: SystemError) -> bool:
        """Attempt component-specific recovery"""
        # This is a placeholder for component-specific recovery logic
        # In a real system, this would call component-specific recovery methods
        
        component_recovery_map = {
            'data_pipeline': self._recover_data_pipeline,
            'state_manager': self._recover_state_manager,
            'intelligence_engine': self._recover_intelligence_engine,
            'risk_engine': self._recover_risk_engine
        }
        
        recovery_func = component_recovery_map.get(error.component)
        if recovery_func:
            try:
                return recovery_func(error)
            except Exception as e:
                logger.error(f"Component recovery failed: {e}")
                return False
        
        return False
    
    def _recover_data_pipeline(self, error: SystemError) -> bool:
        """Recover data pipeline component"""
        logger.info("Attempting data pipeline recovery")
        # Placeholder for data pipeline recovery logic
        return True
    
    def _recover_state_manager(self, error: SystemError) -> bool:
        """Recover state manager component"""
        logger.info("Attempting state manager recovery")
        # Placeholder for state manager recovery logic
        return True
    
    def _recover_intelligence_engine(self, error: SystemError) -> bool:
        """Recover intelligence engine component"""
        logger.info("Attempting intelligence engine recovery")
        # Placeholder for intelligence engine recovery logic
        return True
    
    def _recover_risk_engine(self, error: SystemError) -> bool:
        """Recover risk engine component"""
        logger.info("Attempting risk engine recovery")
        # Placeholder for risk engine recovery logic
        return True
    
    def _handle_escalation(self, error: SystemError):
        """
        Handle error escalation based on severity rules.
        
        Implements Property 22: Error Escalation Consistency (E2)
        """
        rules = self.escalation_rules.get(error.severity)
        if not rules:
            return
        
        # Check if immediate escalation is required
        if rules['immediate_escalation']:
            error.escalation_level = min(error.escalation_level + 1, rules['max_escalation_level'])
            logger.warning(f"Immediate escalation for error {error.error_id} to level {error.escalation_level}")
        
        # Check if escalation timeout has passed
        time_since_error = (datetime.now() - error.timestamp).total_seconds()
        if time_since_error > rules['escalation_timeout'] and error.escalation_level < rules['max_escalation_level']:
            error.escalation_level += 1
            logger.warning(f"Time-based escalation for error {error.error_id} to level {error.escalation_level}")
        
        # Alert operators if required
        if rules['requires_operator'] and error.escalation_level > 0:
            self._alert_operators(error, f"Escalated error requires attention: {error.message}")
    
    def _alert_operators(self, error: SystemError, message: str):
        """Alert human operators"""
        alert_data = {
            'error_id': error.error_id,
            'severity': error.severity.name,
            'component': error.component,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'escalation_level': error.escalation_level
        }
        
        # Write alert to file (in real system, would send to alerting system)
        alert_file = os.path.join(self.error_log_dir, f"alert_{error.error_id}.json")
        with open(alert_file, 'w') as f:
            json.dump(alert_data, f, indent=2)
        
        logger.warning(f"OPERATOR ALERT: {message}")
    
    def _notify_error_subscribers(self, error: SystemError):
        """Notify error subscribers"""
        subscribers = self.error_subscribers.get(error.severity, [])
        for callback in subscribers:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in subscriber callback: {e}")
    
    def _update_error_patterns(self, error: SystemError):
        """Update error patterns for analysis"""
        pattern_key = f"{error.category.value}_{error.component}"
        
        if pattern_key in self.error_patterns:
            pattern = self.error_patterns[pattern_key]
            pattern.frequency += 1
            pattern.last_occurrence = error.timestamp
        else:
            self.error_patterns[pattern_key] = ErrorPattern(
                pattern_id=pattern_key,
                error_category=error.category,
                component=error.component,
                frequency=1,
                first_occurrence=error.timestamp,
                last_occurrence=error.timestamp,
                average_resolution_time=0.0,
                success_rate=0.0
            )
    
    def _log_error(self, error: SystemError):
        """Log error to file"""
        log_file = os.path.join(self.error_log_dir, f"errors_{datetime.now().strftime('%Y%m%d')}.json")
        
        with open(log_file, 'a') as f:
            json.dump(error.to_dict(), f)
            f.write('\n')
    
    def _background_processor(self):
        """Background thread for error processing"""
        while self._running:
            try:
                self._process_pending_escalations()
                self._cleanup_resolved_errors()
                self._analyze_error_patterns()
                time.sleep(60)  # Process every minute
            except Exception as e:
                logger.error(f"Error in background processor: {e}")
    
    def _process_pending_escalations(self):
        """Process pending error escalations"""
        current_time = datetime.now()
        
        with self._lock:
            for error in self.active_errors.values():
                if error.resolved:
                    continue
                
                rules = self.escalation_rules.get(error.severity)
                if not rules:
                    continue
                
                time_since_error = (current_time - error.timestamp).total_seconds()
                if (time_since_error > rules['escalation_timeout'] and 
                    error.escalation_level < rules['max_escalation_level']):
                    
                    error.escalation_level += 1
                    logger.warning(f"Background escalation for error {error.error_id} to level {error.escalation_level}")
                    
                    if rules['requires_operator']:
                        self._alert_operators(error, f"Background escalated error: {error.message}")
    
    def _cleanup_resolved_errors(self):
        """Clean up resolved errors from active list"""
        with self._lock:
            resolved_errors = [error_id for error_id, error in self.active_errors.items() if error.resolved]
            for error_id in resolved_errors:
                del self.active_errors[error_id]
    
    def _analyze_error_patterns(self):
        """Analyze error patterns for insights"""
        current_time = datetime.now()
        window_start = current_time - timedelta(seconds=self.pattern_analysis_window)
        
        # Count recent errors by pattern
        recent_errors = defaultdict(int)
        for error in self.error_history:
            if error.timestamp >= window_start:
                pattern_key = f"{error.category.value}_{error.component}"
                recent_errors[pattern_key] += 1
        
        # Update pattern statistics
        for pattern_key, count in recent_errors.items():
            if pattern_key in self.error_patterns:
                pattern = self.error_patterns[pattern_key]
                # Simple moving average for frequency
                pattern.frequency = int((pattern.frequency + count) / 2)
    
    def subscribe_to_errors(self, severity: ErrorSeverity, callback: Callable[[SystemError], None]):
        """Subscribe to error notifications"""
        self.error_subscribers[severity].append(callback)
        logger.info(f"Subscribed to {severity.name} errors")
    
    def get_error_history(self, 
                         severity: Optional[ErrorSeverity] = None,
                         component: Optional[str] = None,
                         hours: int = 24) -> List[SystemError]:
        """Get error history with optional filtering"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        filtered_errors = []
        for error in self.error_history:
            if error.timestamp < cutoff_time:
                continue
            
            if severity and error.severity != severity:
                continue
            
            if component and error.component != component:
                continue
            
            filtered_errors.append(error)
        
        return filtered_errors
    
    def get_error_patterns(self) -> List[ErrorPattern]:
        """Get current error patterns"""
        return list(self.error_patterns.values())
    
    def resolve_error(self, error_id: str, resolution_method: str) -> bool:
        """Manually resolve an error"""
        with self._lock:
            if error_id in self.active_errors:
                error = self.active_errors[error_id]
                error.resolved = True
                error.resolution_timestamp = datetime.now()
                error.resolution_method = resolution_method
                
                logger.info(f"Error {error_id} resolved: {resolution_method}")
                return True
        
        return False
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get error handler health metrics"""
        with self._lock:
            active_critical = sum(1 for e in self.active_errors.values() if e.severity == ErrorSeverity.CRITICAL)
            active_high = sum(1 for e in self.active_errors.values() if e.severity == ErrorSeverity.HIGH)
            active_medium = sum(1 for e in self.active_errors.values() if e.severity == ErrorSeverity.MEDIUM)
            active_low = sum(1 for e in self.active_errors.values() if e.severity == ErrorSeverity.LOW)
            
            return {
                'healthy': active_critical == 0 and active_high < 5,
                'active_errors': len(self.active_errors),
                'active_critical': active_critical,
                'active_high': active_high,
                'active_medium': active_medium,
                'active_low': active_low,
                'total_errors_processed': len(self.error_history),
                'error_patterns': len(self.error_patterns),
                'message': f"Error handler: {len(self.active_errors)} active errors"
            }
    
    def initialize(self) -> bool:
        """Initialize the error handler"""
        try:
            logger.info("Error handler initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize error handler: {e}")
            return False
    
    def escalate_error(self, 
                      error: Exception, 
                      escalation_level: str) -> bool:
        """
        Escalate error to specified level.
        
        This method is called to escalate errors according to severity rules.
        """
        # Find the error in active errors
        for system_error in self.active_errors.values():
            if system_error.message == str(error):
                # Update escalation level
                try:
                    level = int(escalation_level)
                    max_level = self.escalation_rules[system_error.severity]['max_escalation_level']
                    system_error.escalation_level = min(level, max_level)
                    
                    logger.info(f"Error {system_error.error_id} escalated to level {system_error.escalation_level}")
                    
                    # Alert operators if required
                    rules = self.escalation_rules[system_error.severity]
                    if rules['requires_operator']:
                        self._alert_operators(system_error, f"Error escalated to level {escalation_level}")
                    
                    return True
                except (ValueError, KeyError) as e:
                    logger.error(f"Invalid escalation level {escalation_level}: {e}")
                    return False
        
        return False
    
    def should_fail_fast(self, error: Exception) -> bool:
        """
        Determine if error should trigger fail-fast behavior.
        
        Returns True for critical errors that should cause immediate system termination.
        """
        # This is a simple implementation - in practice, this might analyze
        # the error type, message, or context to determine criticality
        
        # Check if this is a known critical error pattern
        error_message = str(error).lower()
        
        critical_patterns = [
            'system integrity compromised',
            'data corruption detected',
            'critical configuration error',
            'security breach',
            'memory corruption',
            'stack overflow',
            'segmentation fault'
        ]
        
        for pattern in critical_patterns:
            if pattern in error_message:
                return True
        
        # Check error type
        critical_error_types = [
            SystemExit,
            MemoryError,
            KeyboardInterrupt
        ]
        
        if type(error) in critical_error_types:
            return True
        
        return False
    
    def shutdown(self) -> bool:
        """Shutdown the error handler"""
        self._running = False
        if self._background_thread.is_alive():
            self._background_thread.join(timeout=5)
        
        logger.info("Error handler shutdown")
        return True