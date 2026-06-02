"""Arya, the Northstar finance LLM subsystem.

Arya is intentionally isolated from the main Northstar runtime.  The package
contains data, tokeniser, model, training, alignment, inference, bridge, and
evaluation modules that can be reused by future systems without importing the
trading stack.
"""

from arya.model.config import AryaConfig
from arya.model.transformer import Arya

__all__ = ["Arya", "AryaConfig"]

