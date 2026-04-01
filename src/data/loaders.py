"""Canonical data loaders for Northstar live + research paths."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


DEFAULT_POLICY_PATH = "config/research_policy.yaml"


def _resolve_policy_path(config_path: str | None = None) -> Path:
    return Path(config_path or os.getenv("NS_POLICY_CONFIG", DEFAULT_POLICY_PATH)).expanduser()


def _load_policy(config_path: str | None = None) -> tuple[dict[str, Any], Path]:
    path = _resolve_policy_path(config_path)
    if not path.exists():
        return {}, path
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return (payload if isinstance(payload, dict) else {}), path


def _resolve_data_path(raw: str, policy_path: Path) -> Path:
    p = Path(str(raw))
    if p.is_absolute():
        return p
    # Most Northstar configs live under <repo>/config/*.yaml.
    # Resolve relative artifact paths against repo root when possible.
    if policy_path.parent.name.lower() == "config":
        return (policy_path.parent.parent / p).resolve()
    return (policy_path.parent / p).resolve()


def _historical_dataset_cfg(policy: dict[str, Any]) -> dict[str, Any]:
    hr = policy.get("historical_research", {})
    if not isinstance(hr, dict):
        return {}
    ds = hr.get("dataset", {})
    return ds if isinstance(ds, dict) else {}


def _historical_cfg(policy: dict[str, Any]) -> dict[str, Any]:
    hr = policy.get("historical_research", {})
    return hr if isinstance(hr, dict) else {}


def _read_required_parquet(path: str, label: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{label}_artifact_missing:{p}")
    df = pd.read_parquet(p)
    if df is None or df.empty:
        raise ValueError(f"{label}_artifact_empty:{p}")
    return df


def _canonicalize_prices(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    rename_map: dict[str, str] = {}
    if "Ticker" in df.columns and "ticker" not in df.columns:
        rename_map["Ticker"] = "ticker"
    if "Timestamp" in df.columns and "timestamp" not in df.columns:
        rename_map["Timestamp"] = "timestamp"
    if not rename_map:
        return df
    return df.rename(columns=rename_map)


def load_prices(config_path: str | None = None) -> pd.DataFrame:
    policy, policy_path = _load_policy(config_path)
    ds = _historical_dataset_cfg(policy)
    path = str(ds.get("prices_path", "data/processed/prices.parquet"))
    return _canonicalize_prices(_read_required_parquet(str(_resolve_data_path(path, policy_path)), "prices"))


def load_fundamentals(config_path: str | None = None) -> pd.DataFrame:
    policy, policy_path = _load_policy(config_path)
    ds = _historical_dataset_cfg(policy)
    path = str(ds.get("fundamentals_path", "data/processed/fundamentals.parquet"))
    return _read_required_parquet(str(_resolve_data_path(path, policy_path)), "fundamentals")


def load_macro(config_path: str | None = None) -> pd.DataFrame:
    policy, policy_path = _load_policy(config_path)
    ds = _historical_dataset_cfg(policy)
    path = str(ds.get("macro_features_path", "data/processed/macro/macro_regime_features.parquet"))
    return _read_required_parquet(str(_resolve_data_path(path, policy_path)), "macro")


def load_sentiment(config_path: str | None = None, *, prefer_legacy: bool = False) -> pd.DataFrame:
    policy, policy_path = _load_policy(config_path)
    ds = _historical_dataset_cfg(policy)
    if prefer_legacy:
        raw = policy.get("sentiment_path") or ds.get("sentiment_path")
    else:
        raw = ds.get("sentiment_path") or policy.get("sentiment_path")
    path = str(raw or "data/processed/sentiment/ticker_sentiment_daily.parquet")
    return _read_required_parquet(str(_resolve_data_path(path, policy_path)), "sentiment")


def load_regime_labels(config_path: str | None = None) -> pd.DataFrame:
    policy, policy_path = _load_policy(config_path)
    hr = _historical_cfg(policy)
    path = str(hr.get("regime_labels_path", "data/processed/regime_labels.parquet"))
    return _read_required_parquet(str(_resolve_data_path(path, policy_path)), "regime_labels")
