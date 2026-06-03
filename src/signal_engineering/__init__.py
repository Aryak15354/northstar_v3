"""
Signal Engineering System

A modular framework for systematic quantitative equity signal development
with rigorous point-in-time (PIT) compliance and leakage detection.

Key Components:
- Configuration management with XGBoost hyperparameters and phase gates
- PIT audit framework for timestamp validation and safety buffers
- Leakage test framework for automated future information detection
- Feature budget enforcement (N/5 rule)
- Regime-conditional modeling support

Target: Improve IC from 0.030 baseline to 0.047+ through 7 phased implementations.
"""

from .config import (
    XGBoostConfig,
    PITSafetyBuffers,
    FeatureBudgetConfig,
    PhaseGates,
    SignalEngineeringConfig
)

from .pit_audit import (
    PITAuditEntry,
    PITTimestampManager,
    PITAuditLog,
    create_pit_audit_entry
)

from .leakage_test import (
    LeakageTestResult,
    LeakageTest,
    run_leakage_test_suite
)

from .accruals_validator import (
    AccrualsValidator,
    run_validation_tests
)

__version__ = "1.0.0"

__all__ = [
    # Configuration
    "XGBoostConfig",
    "PITSafetyBuffers",
    "FeatureBudgetConfig",
    "PhaseGates",
    "SignalEngineeringConfig",
    
    # PIT Audit
    "PITAuditEntry",
    "PITTimestampManager",
    "PITAuditLog",
    "create_pit_audit_entry",
    
    # Leakage Testing
    "LeakageTestResult",
    "LeakageTest",
    "run_leakage_test_suite",
    
    # Accruals Validation
    "AccrualsValidator",
    "run_validation_tests",
]
