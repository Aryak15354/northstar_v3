"""
Unified Data Ingestion Layer for Northstar V3

This module provides the single, authoritative gateway for all data access
in the entire system. Every module that needs data should import from here.

Key Features:
- Point-in-time (PIT) compliance enforcement
- Data freshness checking with staleness detection
- Standardized return types (DataFrame/Series)
- Structured logging with metadata
- LRU caching to avoid redundant disk reads

Usage:
    from src.ingestion import IngestionRegistry
    
    registry = IngestionRegistry(config)
    prices = registry.market.load(as_of_date=today, tickers=['RELIANCE', 'TCS'])
    fundamentals = registry.fundamentals.load_financials(as_of_date=today)
    macro = registry.macro.load_rbi_data(as_of_date=today)
"""

from .ingestion_registry import IngestionRegistry
from .base_loader import (
    PITViolationError,
    StaleDataError,
    StaleDataWarning,
    DataNotFoundError,
    DataSchemaError,
)

__all__ = [
    'IngestionRegistry',
    'PITViolationError',
    'StaleDataError',
    'StaleDataWarning',
    'DataNotFoundError',
    'DataSchemaError',
]
