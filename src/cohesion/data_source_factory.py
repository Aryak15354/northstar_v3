"""
Concrete data source factory for cohesion dependency bootstrap.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.cohesion.service_interfaces import IDataSourceFactory, IDataSource, ValidationResult


logger = logging.getLogger(__name__)


class FileDataSource(IDataSource):
    """Simple file-backed data source for csv/parquet/json artifacts."""

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = Path(path)

    def read_data(self, query: Dict[str, Any] = None):
        if not self.path.exists():
            raise FileNotFoundError(f"Data source path does not exist: {self.path}")

        if self.path.suffix == ".parquet":
            return pd.read_parquet(self.path)
        if self.path.suffix == ".csv":
            return pd.read_csv(self.path)
        if self.path.suffix == ".json":
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                return pd.DataFrame(payload)
            if isinstance(payload, dict):
                return pd.DataFrame([payload])
            return pd.DataFrame({"value": [payload]})
        raise ValueError(f"Unsupported file source type for {self.path}")

    def get_schema(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"columns": [], "types": {}}
        df = self.read_data()
        return {
            "columns": list(df.columns),
            "types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        }

    def get_last_update(self):
        if not self.path.exists():
            return datetime.min
        return datetime.fromtimestamp(self.path.stat().st_mtime)

    def validate_connection(self) -> ValidationResult:
        errors = []
        warnings = []
        if not self.path.exists():
            errors.append(f"Path does not exist: {self.path}")
        return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)


class ApiDataSource(IDataSource):
    """Placeholder API data source that fails honestly until implemented."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    def read_data(self, query: Dict[str, Any] = None):
        raise NotImplementedError(f"API data source '{self.name}' is not implemented")

    def get_schema(self) -> Dict[str, Any]:
        return {"columns": [], "types": {}, "implemented": False}

    def get_last_update(self):
        return datetime.min

    def validate_connection(self) -> ValidationResult:
        return ValidationResult(
            is_valid=False,
            errors=[f"API data source '{self.name}' is not implemented"],
            warnings=[],
        )


class DataSourceFactory(IDataSourceFactory):
    """Create concrete data sources from simple config payloads."""

    def __init__(self):
        self.supported_types = ['csv', 'parquet', 'json', 'api']

    def create_data_source(self, source_type: str, config: Dict[str, Any]) -> IDataSource:
        source_type = str(source_type).lower()
        if source_type not in self.supported_types:
            raise ValueError(f"Unsupported source type: {source_type}")

        name = str(config.get("name") or config.get("path") or f"{source_type}_source")
        if source_type in {"csv", "parquet", "json"}:
            path = config.get("path")
            if not path:
                raise ValueError(f"Missing path for {source_type} data source")
            return FileDataSource(name=name, path=str(path))
        return ApiDataSource(name=name, config=config)

    def validate_config(self, source_type: str, config: Dict[str, Any]) -> ValidationResult:
        errors = []
        warnings = []

        source_type = str(source_type).lower()
        if source_type not in self.supported_types:
            errors.append(f"Unsupported source type: {source_type}")

        if source_type in {"csv", "parquet", "json"} and not config.get("path"):
            errors.append("Missing required 'path' field in config")
        if not config.get("name"):
            warnings.append("Missing optional 'name' field in config; factory will derive one")

        return ValidationResult(is_valid=not errors, errors=errors, warnings=warnings)
