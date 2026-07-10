"""Data access helpers for efficient local analytics."""

from .artifact_contracts import CONTRACTS, ArtifactContract, resolve_artifact, validate_all_contracts, validate_contract
from .price_access import canonical_price_path, read_prices_legacy
from .query_engine import DuckDBQueryEngine

__all__ = [
    "ArtifactContract",
    "CONTRACTS",
    "DuckDBQueryEngine",
    "canonical_price_path",
    "read_prices_legacy",
    "resolve_artifact",
    "validate_all_contracts",
    "validate_contract",
]
