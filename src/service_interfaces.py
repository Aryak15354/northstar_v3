"""
Backward-compatible service interface exports.

Legacy modules import interfaces from `src.service_interfaces`.
The canonical implementations now live under `src.cohesion.service_interfaces`.
"""

from src.cohesion.service_interfaces import *  # noqa: F401,F403

