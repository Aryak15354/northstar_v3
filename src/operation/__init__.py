"""
Northstar V3 Comprehensive Operation System

This module provides a complete framework for running, testing, and validating
the entire Northstar V3 trading system across multiple scenarios including
historical crisis periods, alpha generation validation, performance benchmarking,
and live operation readiness.
"""

__version__ = "1.0.0"
__author__ = "Northstar V3 Team"

from .operation_controller import OperationController
from .base_types import (
    OperationResult,
    CrisisValidationResult,
    AlphaValidationResult,
    SystemHealthStatus,
    OperationConfig
)

__all__ = [
    "OperationController",
    "OperationResult",
    "CrisisValidationResult", 
    "AlphaValidationResult",
    "SystemHealthStatus",
    "OperationConfig"
]