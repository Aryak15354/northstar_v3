"""Research package for Northstar governed offline intelligence."""

from .research_engine import ResearchEngine
from .research_controller import ResearchController
from .dataset_manager import DatasetManager
from .feature_factory import FeatureFactory

__all__ = [
    "ResearchEngine",
    "ResearchController",
    "DatasetManager",
    "FeatureFactory",
]

__version__ = "2.4.0"
