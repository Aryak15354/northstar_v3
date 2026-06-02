"""
Integrated data pipeline compatibility surface for the cohesion package.

The original module drifted out of the live package, but the validation suite,
sample data sources, and system-integration tests still rely on its interfaces.
This implementation restores those interfaces with deterministic behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

import pandas as pd

from src.cohesion.configuration_manager import ValidationError, ValidationResult, ValidationSeverity
from src.cohesion.unified_state_manager import AuthorityLevel, UnifiedStateManager


class DataSourcePriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class ProcessingStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class DataSourceType(Enum):
    MARKET_DATA = "market_data"
    MACRO_DATA = "macro_data"
    FUNDAMENTAL_DATA = "fundamental_data"
    ALTERNATIVE_DATA = "alternative_data"


@dataclass
class DataSourceConfig:
    name: str
    source_type: DataSourceType
    priority: DataSourcePriority
    dependencies: List[str]
    schema_name: str
    freshness_threshold: timedelta
    retry_config: Dict[str, Any]
    quality_gates: List[str]

    def __post_init__(self):
        self.dependencies = list(self.dependencies or [])
        self.retry_config = dict(self.retry_config or {"max_retries": 3, "backoff_factor": 1.0, "initial_delay": 0.0})
        self.quality_gates = list(self.quality_gates or [])


@dataclass
class ProcessingResult:
    success: bool
    data: Optional[pd.DataFrame]
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    processing_time: float

    def __post_init__(self):
        self.errors = list(self.errors or [])
        self.warnings = list(self.warnings or [])
        self.metadata = dict(self.metadata or {})


@dataclass
class DataConflict:
    field: str
    conflicting_sources: List[str]
    conflicting_values: List[Any]
    source_priorities: List[DataSourcePriority]
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_method: Optional[str] = None


class IDataSource(Protocol):
    def get_name(self) -> str: ...
    def get_data(self, query: Dict[str, Any]) -> ProcessingResult: ...
    def validate_connection(self) -> bool: ...
    def get_last_update(self) -> Optional[datetime]: ...


class DependencyGraph:
    def __init__(self):
        self.nodes: Dict[str, DataSourceConfig] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_node(self, config: DataSourceConfig):
        self.nodes[config.name] = config
        self.edges[config.name] = list(config.dependencies)

    def get_processing_order(self) -> List[str]:
        in_degree = {node: 0 for node in self.nodes}
        for node, dependencies in self.edges.items():
            for dependency in dependencies:
                if dependency in in_degree:
                    in_degree[node] += 1
        queue = [node for node, degree in in_degree.items() if degree == 0]
        ordered: List[str] = []
        while queue:
            node = queue.pop(0)
            ordered.append(node)
            for other_node, dependencies in self.edges.items():
                if node in dependencies:
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)
        if len(ordered) != len(self.nodes):
            raise ValueError("Circular dependency detected in data pipeline")
        return ordered


class RetryManager:
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.0, initial_delay: float = 0.0):
        self.max_retries = int(max_retries)
        self.backoff_factor = float(backoff_factor)
        self.initial_delay = float(initial_delay)

    def execute_with_retry(self, operation, operation_name: str) -> ProcessingResult:
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
        return ProcessingResult(
            success=False,
            data=None,
            errors=[f"{operation_name} failed after {self.max_retries + 1} attempts: {last_error}"],
            warnings=[],
            metadata={"retry_attempts": self.max_retries + 1},
            processing_time=0.0,
        )


class IntegratedDataPipeline:
    """Cohesion-layer pipeline with dependency ordering and conflict resolution."""

    def __init__(self, config_manager=None, state_manager: Optional[UnifiedStateManager] = None, schema_validator=None):
        self.config_manager = config_manager
        self.state_manager = state_manager or UnifiedStateManager()
        self.schema_validator = schema_validator
        self.data_sources: Dict[str, IDataSource] = {}
        self.source_configs: Dict[str, DataSourceConfig] = {}
        self.processing_status: Dict[str, ProcessingStatus] = {}
        self.processing_results: Dict[str, ProcessingResult] = {}
        self.data_conflicts: List[DataConflict] = []
        self.dependency_graph = DependencyGraph()

    def register_data_source(self, name: str, source: IDataSource, config: DataSourceConfig):
        self.data_sources[name] = source
        self.source_configs[name] = config
        self.processing_status[name] = ProcessingStatus.PENDING
        self.dependency_graph.add_node(config)

    def process_data_pipeline(self, force_refresh: bool = False) -> ProcessingResult:
        del force_refresh
        successes = 0
        warnings: List[str] = []
        errors: List[str] = []

        for source_name in self.dependency_graph.get_processing_order():
            source = self.data_sources[source_name]
            config = self.source_configs[source_name]
            self.processing_status[source_name] = ProcessingStatus.PROCESSING
            retry_manager = RetryManager(**config.retry_config)
            result = retry_manager.execute_with_retry(lambda: source.get_data({}), source_name)
            self.processing_results[source_name] = result
            self.processing_status[source_name] = ProcessingStatus.COMPLETED if result.success else ProcessingStatus.FAILED
            if result.success:
                successes += 1
            else:
                errors.extend(result.errors)
            warnings.extend(result.warnings)

        self.state_manager.update_state(
            "intelligence",
            {
                "data_pipeline_last_run": datetime.now(),
                "data_pipeline_successful_sources": successes,
            },
            AuthorityLevel.INTELLIGENCE,
            reason="Integrated data pipeline run",
        )

        return ProcessingResult(
            success=successes > 0 and not errors,
            data=None,
            errors=errors,
            warnings=warnings,
            metadata={
                "successful_sources": successes,
                "registered_sources": len(self.data_sources),
            },
            processing_time=0.0,
        )

    def process_pipeline(self, force_refresh: bool = False) -> ProcessingResult:
        return self.process_data_pipeline(force_refresh=force_refresh)

    def get_data(self, source_name: str, as_of: Optional[datetime] = None) -> pd.DataFrame:
        del as_of
        result = self.processing_results.get(source_name)
        if result and result.success and isinstance(result.data, pd.DataFrame):
            return result.data.copy()
        return pd.DataFrame()

    def validate_pipeline(self) -> ValidationResult:
        errors: List[ValidationError] = []
        for name, config in self.source_configs.items():
            for dependency in config.dependencies:
                if dependency not in self.source_configs:
                    errors.append(
                        ValidationError(
                            code="MISSING_DEPENDENCY",
                            message=f"Missing dependency '{dependency}' for source '{name}'",
                            field=name,
                            value=dependency,
                            severity=ValidationSeverity.HIGH,
                            timestamp=datetime.now(),
                        )
                    )
        return ValidationResult(is_valid=not errors, errors=errors, warnings=[], metadata={})

    def validate_data_lineage(self) -> ValidationResult:
        errors: List[ValidationError] = []
        try:
            order = self.dependency_graph.get_processing_order()
        except ValueError as exc:
            errors.append(
                ValidationError(
                    code="CIRCULAR_DEPENDENCY",
                    message=str(exc),
                    field="dependency_graph",
                    value=None,
                    severity=ValidationSeverity.CRITICAL,
                    timestamp=datetime.now(),
                )
            )
            order = []

        if not order and self.source_configs:
            errors.append(
                ValidationError(
                    code="EMPTY_PROCESSING_ORDER",
                    message="No processing order could be determined",
                    field="dependency_graph",
                    value=None,
                    severity=ValidationSeverity.HIGH,
                    timestamp=datetime.now(),
                )
            )

        return ValidationResult(
            is_valid=not errors,
            errors=errors,
            warnings=[],
            metadata={"processing_order": order},
        )

    def _resolve_data_conflicts(self, results: Dict[str, ProcessingResult]) -> int:
        self.data_conflicts.clear()
        successful = {
            source: result.data
            for source, result in results.items()
            if result.success and isinstance(result.data, pd.DataFrame) and result.data is not None
        }
        if len(successful) < 2:
            return 0

        common_columns = set.intersection(*(set(df.columns) for df in successful.values()))
        conflicts_resolved = 0

        for column in sorted(common_columns):
            values: List[Any] = []
            sources: List[str] = []
            priorities: List[DataSourcePriority] = []
            for source_name, df in successful.items():
                if df.empty:
                    continue
                raw_value = df.iloc[0][column]
                value = raw_value.item() if hasattr(raw_value, "item") else raw_value
                values.append(value)
                sources.append(source_name)
                config = self.source_configs.get(source_name) or self.dependency_graph.nodes.get(source_name)
                priorities.append(config.priority if config else DataSourcePriority.LOW)

            if len(values) < 2:
                continue

            comparable = [repr(value) for value in values]
            if len(set(comparable)) <= 1:
                continue

            winner_idx = min(range(len(priorities)), key=lambda idx: priorities[idx].value)
            self.data_conflicts.append(
                DataConflict(
                    field=column,
                    conflicting_sources=sources,
                    conflicting_values=values,
                    source_priorities=priorities,
                    resolution=sources[winner_idx],
                    resolved_at=datetime.now(),
                    resolution_method="priority_order",
                )
            )
            conflicts_resolved += 1

        return conflicts_resolved

    def get_pipeline_status(self) -> Dict[str, Any]:
        lineage_result = self.validate_data_lineage()
        return {
            "timestamp": datetime.now().isoformat(),
            "registered_sources": len(self.data_sources),
            "processing_status": {name: status.value for name, status in self.processing_status.items()},
            "lineage_valid": bool(lineage_result.is_valid),
        }
