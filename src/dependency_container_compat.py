"""
Backward-compatible dependency container exports.

Legacy modules import DI primitives from `src.dependency_container_compat`.
The canonical implementations now live under `src.cohesion.dependency_container`.
"""

from src.cohesion.dependency_container import *  # noqa: F401,F403
