"""Sequence utilities for time-series models (LSTM/TCN/Transformer)."""

from __future__ import annotations

from typing import Tuple

import numpy as np


def create_sequences(X: np.ndarray, y: np.ndarray, lookback: int) -> Tuple[np.ndarray, np.ndarray]:
    """Create rolling lookback sequences.

    Returns:
        X_seq: [n_samples, lookback, n_features]
        y_seq: [n_samples]
    """
    if lookback <= 1:
        return np.asarray(X), np.asarray(y)

    X = np.asarray(X)
    y = np.asarray(y)

    if X.ndim != 2:
        raise ValueError("X must be 2D for sequence building")
    if len(X) != len(y):
        raise ValueError("X and y length mismatch")
    if len(X) <= lookback:
        return np.empty((0, lookback, X.shape[1]), dtype=float), np.empty((0,), dtype=float)

    X_seq = []
    y_seq = []
    for i in range(lookback, len(X)):
        X_seq.append(X[i - lookback : i])
        y_seq.append(y[i])
    return np.asarray(X_seq), np.asarray(y_seq)
