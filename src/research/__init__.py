"""Research package for Northstar governed offline intelligence."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "ResearchEngine",
    "ResearchController",
    "DatasetManager",
    "FeatureFactory",
]

__version__ = "2.4.0"

_EXPORTS = {
    "ResearchEngine": ".research_engine",
    "ResearchController": ".research_controller",
    "DatasetManager": ".dataset_manager",
    "FeatureFactory": ".feature_factory",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
