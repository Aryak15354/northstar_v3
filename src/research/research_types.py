"""Core data contracts for research modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd


@dataclass
class ResearchDataset:
    """Canonical dataset object consumed by training and simulation modules."""

    X: np.ndarray
    y: np.ndarray
    feature_names: List[str]
    metadata: Dict[str, Any]
    index: pd.DatetimeIndex
    tickers: np.ndarray
    frame: pd.DataFrame
    # TFT-style split blocks (same row cardinality as X/y).
    static_features: np.ndarray | None = None
    known_dynamic_features: np.ndarray | None = None
    observed_dynamic_features: np.ndarray | None = None
    static_feature_names: List[str] = field(default_factory=list)
    known_dynamic_feature_names: List[str] = field(default_factory=list)
    observed_dynamic_feature_names: List[str] = field(default_factory=list)
    ticker_ids: np.ndarray | None = None
    sector_ids: np.ndarray | None = None


@dataclass
class ResearchWindowResult:
    """One walk-forward window result."""

    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    metrics: Dict[str, float]


@dataclass
class ModelRunResult:
    """Model-level aggregate result."""

    model_name: str
    params: Dict[str, Any]
    windows: List[ResearchWindowResult]
    aggregate_metrics: Dict[str, float]
