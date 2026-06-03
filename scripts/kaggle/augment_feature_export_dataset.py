#!/usr/bin/env python3
"""Augment the Kaggle feature export with locally recoverable and public-source fields.

This script is intentionally standalone so it can be run before packaging a new
Kaggle dataset version without touching the existing export builder.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import math
import re
import shutil
import subprocess
import sys
import time
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import fitz
import numpy as np
import pandas as pd
import requests
import urllib3
import yfinance as yf
from bs4 import BeautifulSoup
from pypdf import PdfReader
from urllib3.exceptions import InsecureRequestWarning

urllib3.disable_warnings(InsecureRequestWarning)
warnings.filterwarnings("ignore", category=FutureWarning, module="pandas")
fitz.TOOLS.mupdf_display_errors(False)
fitz.TOOLS.mupdf_display_warnings(False)
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("PyPDF2").setLevel(logging.ERROR)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors.gap9_academic_factors import Gap9AcademicFactors


DEFAULT_EXPORT_ROOT = (
    PROJECT_ROOT
    / "tmp"
    / "kaggle_uploads"
    / "northstar_v3_feature_export_robust_20260405"
)
DEFAULT_FEATURE_EXPORT = DEFAULT_EXPORT_ROOT / "northstar_features.parquet"
DEFAULT_METADATA_EXPORT = DEFAULT_EXPORT_ROOT / "northstar_metadata.parquet"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "tmp" / "feature_export_augmentation_20260408"
DEFAULT_START_DATE = "2019-01-01"
DEFAULT_BSE_ARCHIVE_RAW_MB = 192
DEFAULT_BSE_RAW_CACHE_POLICY = "text_failures_only"
BSE_RAW_CACHE_POLICIES = ("all", "text_failures_only", "none")
EXPORT_SUPPORT_FILES = (
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
    "plan_signal_audit.json",
    "feature_unit_registry.json",
    "merged_chunk_export_manifest.json",
    "weekly_export_manifest.json",
)

TARGET_FIELDS = [
    "earnings_quality_ratio",
    "earnings_quality_ratio_cs_z",
    "earnings_quality_ratio_cs_rank",
    "nim_4q_trend",
    "npa_net_4q",
    "provision_coverage",
    "credit_deposit_ratio",
    "loan_growth_yoy",
    "casa_ratio",
    "gnpa_yoy",
    "deal_TCV_qoq",
    "attrition_rate",
    "headcount_growth",
    "us_tech_index_4w",
    "order_backlog_growth",
    "govt_capex_qoq",
    "infra_spending_index",
    "power_sector_capex",
]

SECTOR_CONFIG = {
    "Financial Services": {
        "keywords": ("presentation", "transcript", "conference", "earnings", "investor", "outcome", "results"),
        "fields": [
            "nim_4q_trend",
            "npa_net_4q",
            "provision_coverage",
            "credit_deposit_ratio",
            "loan_growth_yoy",
            "casa_ratio",
            "gnpa_yoy",
        ],
    },
    "Information Technology": {
        "keywords": ("presentation", "transcript", "conference", "earnings", "investor", "outcome", "results"),
        "fields": ["deal_TCV_qoq", "attrition_rate", "headcount_growth"],
    },
    "Capital Goods": {
        "keywords": ("presentation", "transcript", "conference", "earnings", "investor", "outcome", "results"),
        "fields": ["order_backlog_growth"],
    },
}

MOSPI_UST = "MoSPI-8db534af-58d5-465a-9aa1-8c90f809bc28"
MONTH_NAME_TO_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _log(message: str) -> None:
    print(message, flush=True)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return int(path.stat().st_size)
    return int(sum(child.stat().st_size for child in path.rglob("*") if child.is_file()))


def _remove_empty_tree(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass
    try:
        path.rmdir()
    except OSError:
        pass


def _feature_count(frame: pd.DataFrame) -> int:
    return int(max(0, len(frame.columns) - 3))


def _rewrite_export_manifest(payload: dict[str, Any], *, export_root: Path, features: pd.DataFrame, metadata: pd.DataFrame) -> dict[str, Any]:
    updated = dict(payload or {})
    updated["features_rows"] = int(len(features))
    updated["metadata_rows"] = int(len(metadata))
    updated["feature_count"] = _feature_count(features)
    updated["ticker_count"] = int(features["ticker"].nunique()) if "ticker" in features.columns else int(metadata["ticker"].nunique())
    if "date" in features.columns and not features.empty:
        date_series = pd.to_datetime(features["date"], errors="coerce").dropna()
        if not date_series.empty:
            updated["date_min"] = str(date_series.min().date())
            updated["date_max"] = str(date_series.max().date())
    if "target_weekly_return" in features.columns:
        updated["target_non_null_pct"] = float(pd.to_numeric(features["target_weekly_return"], errors="coerce").notna().mean())
    if "northstar_walk_forward_splits.json" in [p.name for p in export_root.iterdir() if p.is_file()]:
        try:
            updated["n_windows"] = int(len(_read_json(export_root / "northstar_walk_forward_splits.json")))
        except Exception:
            pass
    files = dict(updated.get("files") or {})
    files.update(
        {
            "features": str(export_root / "northstar_features.parquet"),
            "metadata": str(export_root / "northstar_metadata.parquet"),
        }
    )
    if (export_root / "northstar_walk_forward_splits.json").exists():
        files["splits"] = str(export_root / "northstar_walk_forward_splits.json")
    if (export_root / "northstar_regime_labels.parquet").exists():
        files["regimes"] = str(export_root / "northstar_regime_labels.parquet")
    updated["files"] = files
    if "output_dir" in updated:
        updated["output_dir"] = str(export_root)
    return updated


def _carry_forward_export_support_files(
    *,
    source_export_root: Path,
    output_root: Path,
    merged: pd.DataFrame,
    metadata: pd.DataFrame,
) -> dict[str, str]:
    copied: dict[str, str] = {}
    for name in EXPORT_SUPPORT_FILES:
        src = source_export_root / name
        if not src.exists():
            continue
        dest = output_root / name
        if src.suffix == ".json":
            payload = _read_json(src)
            if name in {"weekly_export_manifest.json", "merged_chunk_export_manifest.json"} and isinstance(payload, dict):
                payload = _rewrite_export_manifest(payload, export_root=output_root, features=merged, metadata=metadata)
            _write_json(dest, payload)
        else:
            shutil.copy2(src, dest)
        copied[name] = str(dest)
    return copied


def _as_naive_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp


def _extract_pdf_text_with_pypdf(payload: bytes) -> str:
    parts: list[str] = []
    reader = PdfReader(io.BytesIO(payload), strict=False)
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _extract_pdf_text_with_fitz(payload: bytes) -> str:
    parts: list[str] = []
    with fitz.open(stream=payload, filetype="pdf") as document:
        for page_number in range(document.page_count):
            try:
                page = document.load_page(page_number)
                text = page.get_text() or ""
            except Exception:
                text = ""
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _extract_pdf_text(payload: bytes, *, prefer_pypdf: bool = False) -> str:
    extractors = (
        [_extract_pdf_text_with_pypdf, _extract_pdf_text_with_fitz]
        if prefer_pypdf
        else [_extract_pdf_text_with_fitz, _extract_pdf_text_with_pypdf]
    )
    last_error: Exception | None = None
    for extractor in extractors:
        try:
            text = extractor(payload)
        except Exception as exc:
            last_error = exc
            continue
        if text.strip():
            return text
    if last_error is not None:
        raise last_error
    return ""


def _coerce_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float, np.number)) and not pd.isna(value):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    text = text.replace("(", "-").replace(")", "")
    text = text.replace("−", "-")
    text = text.replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _percent_point_change(series: pd.Series, periods: int = 4) -> pd.Series:
    return pd.to_numeric(series, errors="coerce") - pd.to_numeric(series, errors="coerce").shift(periods)


def _pct_change(series: pd.Series, periods: int = 1) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").replace(0.0, np.nan)
    return values.pct_change(periods=periods, fill_method=None).replace([np.inf, -np.inf], np.nan)


def _pct_change_sparse_observed(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    observed = values.dropna().replace(0.0, np.nan)
    if observed.empty:
        return pd.Series(np.nan, index=series.index, dtype=float)
    changes = observed.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    return changes.reindex(series.index)


def _suppress_middle_outliers(
    series: pd.Series,
    *,
    lower_ratio: float = 0.5,
    upper_ratio: float = 2.0,
) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").copy()
    observed = values.dropna()
    if len(observed) < 3:
        return values
    filtered = values.copy()
    observed_values = observed.to_numpy(dtype=float)
    observed_index = list(observed.index)
    for idx in range(1, len(observed_values) - 1):
        prev_value = observed_values[idx - 1]
        current_value = observed_values[idx]
        next_value = observed_values[idx + 1]
        neighbor_level = float(np.nanmedian([prev_value, next_value]))
        if not np.isfinite(neighbor_level) or neighbor_level <= 0:
            continue
        ratio = current_value / neighbor_level
        if ratio < lower_ratio or ratio > upper_ratio:
            filtered.loc[observed_index[idx]] = np.nan
    return filtered


def _overlay_columns(frame: pd.DataFrame, columns: list[str], suffix: str = "__incoming") -> pd.DataFrame:
    for column in columns:
        incoming = f"{column}{suffix}"
        if incoming not in frame.columns:
            continue
        if column in frame.columns:
            frame[column] = frame[incoming].combine_first(frame[column])
            frame = frame.drop(columns=[incoming])
        else:
            frame = frame.rename(columns={incoming: column})
    return frame


def _normalize_number_with_unit(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if not unit:
        return float(value)
    unit_key = unit.strip().lower()
    multipliers = {
        "bn": 1_000.0,
        "billion": 1_000.0,
        "mn": 1.0,
        "million": 1.0,
        "m": 1.0,
        "cr": 10.0,
        "crore": 10.0,
        "trn": 1_000_000.0,
        "tn": 1_000_000.0,
        "trillion": 1_000_000.0,
    }
    return float(value) * multipliers.get(unit_key, 1.0)


def _normalize_inr_crore(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if not unit:
        return float(value)
    unit_key = unit.strip().lower()
    multipliers = {
        "cr": 1.0,
        "crore": 1.0,
        "crores": 1.0,
        "bn": 100.0,
        "billion": 100.0,
        "mn": 0.1,
        "million": 0.1,
        "m": 0.1,
        "trn": 100_000.0,
        "tn": 100_000.0,
        "trillion": 100_000.0,
    }
    return float(value) * multipliers.get(unit_key, 1.0)


def _series_from_patterns(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            value = _coerce_numeric(match.group(1))
            if value is not None:
                return value
    return None


def _extract_named_row_values(text: str, label_patterns: list[str]) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    for label in label_patterns:
        pattern = (
            rf"{label}\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)\s+([0-9,]+(?:\.[0-9]+)?)"
            rf"(?:\s+([()\-0-9.%]+))?(?:\s+([()\-0-9.%]+))?"
        )
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            current = _coerce_numeric(match.group(1))
            prior = _coerce_numeric(match.group(2))
            prev_q = _coerce_numeric(match.group(3))
            yoy = _coerce_numeric(match.group(4))
            qoq = _coerce_numeric(match.group(5))
            return current, prior, prev_q, yoy, qoq
    return None, None, None, None, None


def _extract_percent_after_label(text: str, labels: list[str]) -> float | None:
    for label in labels:
        patterns = [
            rf"{label}[^0-9]{{0,60}}([0-9]+(?:\.[0-9]+)?)\s*%",
            rf"([0-9]+(?:\.[0-9]+)?)\s*%\s*{label}",
        ]
        for pattern in patterns:
            if pattern.startswith("([0-9]"):
                match = re.search(pattern, text, flags=re.IGNORECASE)
            else:
                constrained = rf"{label}[^\n0-9]{{0,20}}([0-9]+(?:\.[0-9]+)?)\s*%"
                match = re.search(constrained, text, flags=re.IGNORECASE)
            if match:
                return _coerce_numeric(match.group(1))
    return None


def _extract_it_metrics(text: str) -> dict[str, float | None]:
    attrition_value: float | None = None
    for match in re.finditer(r"(?:ltm\s+)?attrition(?:\s+rate)?[^0-9]{0,40}([0-9]+(?:\.[0-9]+)?)\s*%", text, flags=re.IGNORECASE):
        snippet = text[max(0, match.start() - 40) : min(len(text), match.end() + 80)].lower()
        if "declin" in snippet or "improv" in snippet or "up by" in snippet or "down by" in snippet:
            continue
        attrition_value = _coerce_numeric(match.group(1))
        break

    headcount_value = _series_from_patterns(
        text,
        [
            r"net\s+headcount\s+(?:increased|grew|rose).{0,80}?to\s+([0-9,]{5,})\s+employees",
            r"headcount(?:\s+number)?[^.\n]{0,120}?(?:stood at|was at|is at|is now at|now at|now over|to)\s+([0-9,]{5,})\b",
            r"over\s+([0-9,]{5,})\s+employees",
            r"([0-9,]{5,})\s+employees\s+worldwide",
            r"employee\s+count[^.\n]{0,80}?([0-9,]{5,})",
        ],
    )

    tcv_match = re.search(
        r"(?:large\s+deal\s+)?tcv[^$0-9]{0,40}(?:was|at|of|stood at)?[^$0-9]{0,20}\$?\s*([0-9]+(?:\.[0-9]+)?)\s*(bn|billion|mn|million|m)\b",
        text,
        flags=re.IGNORECASE,
    )
    tcv_value = None
    if tcv_match:
        tcv_value = _normalize_number_with_unit(_coerce_numeric(tcv_match.group(1)), tcv_match.group(2))

    return {
        "attrition_rate": attrition_value,
        "headcount_level": headcount_value,
        "deal_tcv_level_usd_mn": tcv_value,
    }


def _extract_cg_metrics(text: str) -> dict[str, float | None]:
    order_book_value = None
    patterns = [
        r"order\s+(?:book|backlog)[^₹\ninr0-9]{0,40}(?:₹|rs\.?|inr)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(trn|tn|bn|crores?|cr)?",
        r"order\s+(?:book|backlog)[^0-9\n]{0,40}([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(trn|tn|bn|crores?|cr)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = _normalize_inr_crore(_coerce_numeric(match.group(1)), match.group(2))
        if value is not None and value >= 100.0:
            order_book_value = value
            break
    return {"order_book_level_inr_cr": order_book_value}


def _extract_fs_metrics(text: str) -> dict[str, float | None]:
    current_adv, prior_adv, _prev_q_adv, yoy_adv, _qoq_adv = _extract_named_row_values(
        text,
        [r"net\s+advances", r"customer\s+assets\*?"],
    )
    current_dep, prior_dep, _prev_q_dep, _yoy_dep, _qoq_dep = _extract_named_row_values(text, [r"deposits"])
    nim = _extract_percent_after_label(text, [r"\bNIM\b"])
    nnpa = _extract_percent_after_label(text, [r"\bNNPA\b", r"net\s+npa"])
    gnpa = _extract_percent_after_label(text, [r"\bGNPA\b", r"gross\s+npa"])
    pcr = _extract_percent_after_label(text, [r"\bPCR\b", r"provision\s+coverage"])
    casa = _extract_percent_after_label(text, [r"casa(?:\s+ratio)?"])
    cd_ratio = _extract_percent_after_label(text, [r"cd\s+ratio", r"credit(?:-| )deposit\s+ratio"])

    if cd_ratio is None and current_adv and current_dep and current_dep != 0:
        cd_ratio = 100.0 * current_adv / current_dep

    loan_growth_yoy = yoy_adv
    if loan_growth_yoy is None and current_adv and prior_adv and prior_adv != 0:
        loan_growth_yoy = 100.0 * ((current_adv / prior_adv) - 1.0)

    return {
        "nim_level": nim,
        "npa_net_4q": nnpa,
        "gnpa_level": gnpa,
        "provision_coverage": pcr,
        "casa_ratio": casa,
        "credit_deposit_ratio": cd_ratio,
        "loan_growth_yoy": loan_growth_yoy,
        "advances_level": current_adv,
        "deposits_level": current_dep,
    }


def _merge_asof_by_ticker(
    features: pd.DataFrame,
    events: pd.DataFrame,
    columns: list[str],
    *,
    tolerance: pd.Timedelta | None = None,
) -> pd.DataFrame:
    if events.empty:
        return features
    base = features.sort_values(["ticker", "date"], kind="mergesort").copy()
    out = base
    event_cols = ["ticker", "date"] + columns
    rename_map = {column: f"{column}__incoming" for column in columns}
    events = (
        events[event_cols]
        .copy()
        .rename(columns=rename_map)
        .dropna(subset=["ticker", "date"])
        .sort_values(["ticker", "date"], kind="mergesort")
    )
    merged_parts: list[pd.DataFrame] = []
    for ticker, group in out.groupby("ticker", sort=False):
        event_group = events[events["ticker"] == ticker]
        if event_group.empty:
            merged_parts.append(group)
            continue
        merged = pd.merge_asof(
            group.sort_values("date", kind="mergesort"),
            event_group.sort_values("date", kind="mergesort"),
            on="date",
            by="ticker",
            direction="backward",
            tolerance=tolerance,
        )
        merged = _overlay_columns(merged, columns)
        merged_parts.append(merged)
    return pd.concat(merged_parts, axis=0, ignore_index=True)


def _merge_asof_macro(
    features: pd.DataFrame,
    series: pd.DataFrame,
    columns: list[str],
    *,
    tolerance: pd.Timedelta | None = None,
) -> pd.DataFrame:
    if series.empty:
        return features
    base = features.sort_values(["date", "ticker"], kind="mergesort").copy()
    rename_map = {column: f"{column}__incoming" for column in columns}
    right = (
        series[["date"] + columns]
        .copy()
        .rename(columns=rename_map)
        .dropna(subset=["date"])
        .sort_values("date", kind="mergesort")
        .drop_duplicates(subset=["date"], keep="last")
    )
    merged = pd.merge_asof(base, right, on="date", direction="backward", tolerance=tolerance)
    return _overlay_columns(merged, columns)


def _derive_eq_family(features: pd.DataFrame) -> pd.DataFrame:
    factor = Gap9AcademicFactors()
    work = features[["date", "ticker"]].copy()
    for column in [
        "operating_cash_flow",
        "cash_conversion",
        "cash_conversion_sector_z",
        "cash_conversion_cs_z",
        "net_income",
    ]:
        if column in features.columns:
            work[column] = pd.to_numeric(features[column], errors="coerce")

    work["_orig_order"] = np.arange(len(work), dtype=int)
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.sort_values(["ticker", "date", "_orig_order"], kind="mergesort")
    for column in ["operating_cash_flow", "cash_conversion", "cash_conversion_sector_z", "cash_conversion_cs_z", "net_income"]:
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce").groupby(work["ticker"], sort=False).ffill()

    work["earnings_quality_ratio"] = factor._compute_earnings_quality_ratio(work)
    if "val_earnings_quality_score_zscore" in features.columns:
        proxy = pd.to_numeric(features["val_earnings_quality_score_zscore"], errors="coerce")
        if proxy.notna().any():
            ratio = pd.to_numeric(work["earnings_quality_ratio"], errors="coerce")
            clean_ratio = ratio.replace([np.inf, -np.inf], np.nan)
            if clean_ratio.dropna().empty or clean_ratio.nunique(dropna=True) <= 1 or int((clean_ratio.fillna(0.0) != 0.0).sum()) == 0:
                work["earnings_quality_ratio"] = proxy.astype(float)
    work["earnings_quality_ratio_cs_z"] = factor._group_zscore(work["earnings_quality_ratio"], work["date"])
    work["earnings_quality_ratio_cs_rank"] = factor._group_rank_centered(work["earnings_quality_ratio"], work["date"])
    work = work.sort_values("_orig_order", kind="mergesort")
    return work[["date", "ticker", "earnings_quality_ratio", "earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank"]].reset_index(drop=True)


def _first_available_numeric(frame: pd.DataFrame, candidates: list[str]) -> pd.Series:
    series = pd.Series(np.nan, index=frame.index, dtype=float)
    for column in candidates:
        if column in frame.columns:
            current = pd.to_numeric(frame[column], errors="coerce")
            series = series.where(series.notna(), current)
    return series


def _mean_of_available(columns: list[pd.Series]) -> pd.Series:
    return pd.concat(columns, axis=1).mean(axis=1, skipna=True)


def _sparse_event_projection(
    series: pd.Series,
    *,
    lag_events: int = 4,
    std_window: int = 8,
    sign_window: int = 3,
) -> tuple[pd.Series, pd.Series]:
    full_index = series.index
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        empty = pd.Series(np.nan, index=full_index, dtype=float)
        return empty, empty

    is_new_event = values.ne(values.shift())
    event_values = values.loc[is_new_event].astype(float)
    if event_values.empty:
        empty = pd.Series(np.nan, index=full_index, dtype=float)
        return empty, empty

    lagged = event_values.shift(lag_events)
    rolling_std = event_values.rolling(std_window, min_periods=4).std()
    accel_events = (event_values - lagged) / rolling_std.replace(0.0, np.nan)
    direction_events = event_values.rolling(sign_window, min_periods=sign_window).apply(
        lambda x: 1.0 if float(np.sum(np.asarray(x) > 0.0)) >= 2.0 else -1.0,
        raw=True,
    )

    accel = pd.Series(np.nan, index=full_index, dtype=float)
    direction = pd.Series(np.nan, index=full_index, dtype=float)
    accel.loc[event_values.index] = accel_events.to_numpy(dtype=float)
    direction.loc[event_values.index] = direction_events.to_numpy(dtype=float)
    accel = accel.ffill()
    direction = direction.ffill()
    valid_mask = series.notna()
    accel.loc[~valid_mask] = np.nan
    direction.loc[~valid_mask] = np.nan
    return accel, direction


def _derive_revision_family(features: pd.DataFrame) -> pd.DataFrame:
    work = features[["date", "ticker"]].copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["_orig_order"] = np.arange(len(work), dtype=int)
    work = work.sort_values(["ticker", "date", "_orig_order"], kind="mergesort")

    eps_signal = _first_available_numeric(features, ["eps_sue", "eps_sue_decay"])
    rev_signal = _first_available_numeric(features, ["rev_sue", "rev_sue_decay"])
    work["__eps_signal"] = eps_signal.reindex(work.index)
    work["__rev_signal"] = rev_signal.reindex(work.index)

    work["__eps_revision_accel_raw"] = (
        work.groupby("ticker", sort=False)["__eps_signal"]
        .transform(lambda s: _sparse_event_projection(s)[0])
        .astype(float)
    )
    work["eps_revision_direction"] = (
        work.groupby("ticker", sort=False)["__eps_signal"]
        .transform(lambda s: _sparse_event_projection(s)[1])
        .astype(float)
    )
    work["__rev_revision_accel_raw"] = (
        work.groupby("ticker", sort=False)["__rev_signal"]
        .transform(lambda s: _sparse_event_projection(s)[0])
        .astype(float)
    )

    work["eps_revision_accel"] = Gap9AcademicFactors._group_zscore(work["__eps_revision_accel_raw"], work["date"])
    eps_revision_composite = _mean_of_available(
        [
            work["__eps_revision_accel_raw"],
            work["eps_revision_direction"],
            work["__eps_signal"],
        ]
    )
    rev_revision_composite = _mean_of_available(
        [
            work["__rev_revision_accel_raw"],
            work["__rev_signal"],
        ]
    )
    work["combined_revision_score"] = 0.6 * eps_revision_composite + 0.4 * rev_revision_composite
    work["combined_revision_score_cs_z"] = Gap9AcademicFactors._group_zscore(work["combined_revision_score"], work["date"])
    work["combined_revision_score_cs_rank"] = Gap9AcademicFactors._group_rank_centered(work["combined_revision_score"], work["date"])
    work = work.sort_values("_orig_order", kind="mergesort")
    return work[
        [
            "date",
            "ticker",
            "eps_revision_accel",
            "eps_revision_direction",
            "combined_revision_score",
            "combined_revision_score_cs_z",
            "combined_revision_score_cs_rank",
        ]
    ].reset_index(drop=True)


def _repair_quality_proxy_families(features: pd.DataFrame) -> pd.DataFrame:
    work = features.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    proxy_specs = {
        "earnings_quality_ratio": "val_earnings_quality_score_zscore",
        "accruals_ratio": "val_accruals_ratio_zscore",
    }

    def is_dead(column_name: str) -> bool:
        if column_name not in work.columns:
            return True
        numeric = pd.to_numeric(work[column_name], errors="coerce").replace([np.inf, -np.inf], np.nan)
        clean = numeric.dropna()
        if clean.empty:
            return True
        if clean.nunique(dropna=True) <= 1:
            return True
        return int((clean.abs() > 1e-9).sum()) == 0

    for family_name, proxy_name in proxy_specs.items():
        if proxy_name not in work.columns:
            continue
        proxy = pd.to_numeric(work[proxy_name], errors="coerce").replace([np.inf, -np.inf], np.nan)
        if proxy.dropna().empty:
            continue
        raw_col = family_name
        z_col = f"{family_name}_cs_z"
        rank_col = f"{family_name}_cs_rank"
        if is_dead(raw_col):
            work[raw_col] = proxy.astype(float)
        if is_dead(z_col):
            work[z_col] = proxy.astype(float)
        if is_dead(rank_col):
            work[rank_col] = Gap9AcademicFactors._group_rank_centered(pd.to_numeric(work[z_col], errors="coerce"), work["date"])
    return work


def _repair_revision_factor_family(features: pd.DataFrame) -> pd.DataFrame:
    work = features.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")

    def is_dead(column_name: str) -> bool:
        if column_name not in work.columns:
            return True
        numeric = pd.to_numeric(work[column_name], errors="coerce").replace([np.inf, -np.inf], np.nan)
        clean = numeric.dropna()
        if clean.empty:
            return True
        if clean.nunique(dropna=True) <= 1:
            return True
        return int((clean.abs() > 1e-9).sum()) == 0

    repair_targets = [
        "eps_revision_accel",
        "eps_revision_direction",
        "combined_revision_score",
        "combined_revision_score_cs_z",
        "combined_revision_score_cs_rank",
    ]
    if not any(is_dead(column_name) for column_name in repair_targets):
        return work

    derived = _derive_revision_family(work)
    work = work.merge(derived, on=["date", "ticker"], how="left", suffixes=("", "__derived"))
    for column_name in repair_targets:
        derived_name = f"{column_name}__derived"
        if derived_name not in work.columns:
            continue
        if is_dead(column_name):
            work[column_name] = pd.to_numeric(work[derived_name], errors="coerce")
        work = work.drop(columns=[derived_name])
    return work


def _load_sector_universe(metadata_export: Path, screener_metadata_path: Path) -> pd.DataFrame:
    meta = pd.read_parquet(metadata_export, columns=["ticker", "sector"]).drop_duplicates(["ticker", "sector"])
    screener_meta = pd.read_csv(screener_metadata_path)
    screener_meta["bse_code"] = screener_meta["bse_code"].astype("Int64")
    join = meta.merge(
        screener_meta[["ticker", "company_name", "bse_code"]],
        on="ticker",
        how="left",
        sort=False,
    )
    return join


class CachedSession:
    def __init__(self, cache_dir: Path):
        self.cache_dir = _ensure_dir(cache_dir)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
        verify: bool = True,
        timeout: int = 60,
        force: bool = False,
    ) -> str:
        path = self.cache_dir / cache_key if cache_key else None
        if path and path.exists() and not force:
            return path.read_text(encoding="utf-8", errors="ignore")
        response = self.session.get(url, params=params, headers=headers, timeout=timeout, verify=verify)
        response.raise_for_status()
        text = response.text
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return text

    def get_bytes(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
        verify: bool = True,
        timeout: int = 60,
        force: bool = False,
        allow_curl_fallback: bool = False,
    ) -> bytes:
        path = self.cache_dir / cache_key if cache_key else None
        if path and path.exists() and not force:
            return path.read_bytes()
        last_error: Exception | None = None
        payload: bytes | None = None
        for attempt in range(3):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=timeout, verify=verify)
                response.raise_for_status()
                payload = response.content
                break
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        if payload is None and allow_curl_fallback:
            payload = _curl_download_bytes(url, headers=headers, verify=verify, timeout=timeout)
        if payload is None:
            assert last_error is not None
            raise last_error
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        return payload

    def post_json(
        self,
        url: str,
        *,
        json_payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        cache_key: str | None = None,
        verify: bool = True,
        timeout: int = 60,
        force: bool = False,
    ) -> dict[str, Any]:
        path = self.cache_dir / cache_key if cache_key else None
        if path and path.exists() and not force:
            return json.loads(path.read_text(encoding="utf-8"))
        response = self.session.post(url, json=json_payload, headers=headers, timeout=timeout, verify=verify)
        response.raise_for_status()
        payload = response.json()
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload), encoding="utf-8")
        return payload


class CompactBseCache:
    def __init__(self, cache_dir: Path, *, max_archive_raw_bytes: int):
        self.cache_dir = _ensure_dir(cache_dir)
        self.archive_dir = self.cache_dir / "attachment_archives"
        self.db_path = self.cache_dir / "packed_cache.duckdb"
        self.max_archive_raw_bytes = int(max_archive_raw_bytes)
        self.conn = duckdb.connect(str(self.db_path))
        self._ensure_schema()

    def close(self) -> None:
        self.conn.close()

    def _ensure_schema(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS announcement_cache (
                cache_key VARCHAR PRIMARY KEY,
                payload_json VARCHAR
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attachment_text_cache (
                attachment_name VARCHAR PRIMARY KEY,
                text_payload VARCHAR
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attachment_archives (
                archive_name VARCHAR PRIMARY KEY,
                raw_bytes BIGINT,
                blob_count BIGINT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attachment_blob_store (
                sha256 VARCHAR PRIMARY KEY,
                archive_name VARCHAR,
                member_name VARCHAR,
                raw_size BIGINT
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS attachment_alias (
                attachment_name VARCHAR PRIMARY KEY,
                sha256 VARCHAR
            )
            """
        )

    def _replace_one(self, table: str, key_col: str, key_value: str, value_cols: list[str], values: list[Any]) -> None:
        self.conn.execute(f"DELETE FROM {table} WHERE {key_col} = ?", [key_value])
        placeholders = ", ".join(["?"] * (1 + len(value_cols)))
        columns = ", ".join([key_col, *value_cols])
        self.conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            [key_value, *values],
        )

    def get_announcement(self, cache_key: str) -> str | None:
        row = self.conn.execute(
            "SELECT payload_json FROM announcement_cache WHERE cache_key = ?",
            [str(cache_key)],
        ).fetchone()
        return str(row[0]) if row else None

    def put_announcement(self, cache_key: str, payload_json: str) -> None:
        self._replace_one("announcement_cache", "cache_key", str(cache_key), ["payload_json"], [str(payload_json)])

    def get_attachment_text(self, attachment_name: str) -> str | None:
        row = self.conn.execute(
            "SELECT text_payload FROM attachment_text_cache WHERE attachment_name = ?",
            [str(attachment_name)],
        ).fetchone()
        return str(row[0]) if row else None

    def put_attachment_text(self, attachment_name: str, text_payload: str) -> None:
        self._replace_one(
            "attachment_text_cache",
            "attachment_name",
            str(attachment_name),
            ["text_payload"],
            [str(text_payload)],
        )

    def attachment_text_is_nonempty(self, attachment_name: str) -> bool:
        row = self.conn.execute(
            """
            SELECT CASE
                WHEN length(trim(coalesce(text_payload, ''))) > 0 THEN TRUE
                ELSE FALSE
            END
            FROM attachment_text_cache
            WHERE attachment_name = ?
            """,
            [str(attachment_name)],
        ).fetchone()
        return bool(row[0]) if row else False

    def attachments_with_empty_text(self) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT attachment_name
            FROM attachment_text_cache
            WHERE length(trim(coalesce(text_payload, ''))) = 0
            ORDER BY attachment_name
            """
        ).fetchall()
        return [str(row[0]) for row in rows]

    def _next_archive_name(self) -> str:
        count = int(self.conn.execute("SELECT COUNT(*) FROM attachment_archives").fetchone()[0] or 0)
        return f"attachment_shard_{count + 1:05d}.zip"

    def _pick_archive_name(self, raw_size: int) -> str:
        row = self.conn.execute(
            "SELECT archive_name, raw_bytes FROM attachment_archives ORDER BY archive_name DESC LIMIT 1"
        ).fetchone()
        if row is None:
            archive_name = self._next_archive_name()
            self.conn.execute(
                "INSERT INTO attachment_archives (archive_name, raw_bytes, blob_count) VALUES (?, ?, ?)",
                [archive_name, 0, 0],
            )
            return archive_name
        archive_name = str(row[0])
        current_raw_bytes = int(row[1] or 0)
        if current_raw_bytes + int(raw_size) <= self.max_archive_raw_bytes:
            return archive_name
        archive_name = self._next_archive_name()
        self.conn.execute(
            "INSERT INTO attachment_archives (archive_name, raw_bytes, blob_count) VALUES (?, ?, ?)",
            [archive_name, 0, 0],
        )
        return archive_name

    def put_attachment_bytes(self, attachment_name: str, payload: bytes) -> None:
        payload = bytes(payload)
        sha256 = hashlib.sha256(payload).hexdigest()
        existing = self.conn.execute(
            "SELECT archive_name, member_name FROM attachment_blob_store WHERE sha256 = ?",
            [sha256],
        ).fetchone()
        if existing is None:
            _ensure_dir(self.archive_dir)
            archive_name = self._pick_archive_name(len(payload))
            member_name = f"{sha256}.pdf"
            archive_path = self.archive_dir / archive_name
            with zipfile.ZipFile(archive_path, mode="a", compression=zipfile.ZIP_LZMA) as handle:
                handle.writestr(member_name, payload)
            self.conn.execute(
                "INSERT INTO attachment_blob_store (sha256, archive_name, member_name, raw_size) VALUES (?, ?, ?, ?)",
                [sha256, archive_name, member_name, int(len(payload))],
            )
            self.conn.execute(
                "UPDATE attachment_archives SET raw_bytes = raw_bytes + ?, blob_count = blob_count + 1 WHERE archive_name = ?",
                [int(len(payload)), archive_name],
            )
        self._replace_one("attachment_alias", "attachment_name", str(attachment_name), ["sha256"], [sha256])

    def get_attachment_pointer(self, attachment_name: str) -> tuple[str, str] | None:
        row = self.conn.execute(
            """
            SELECT b.archive_name, b.member_name
            FROM attachment_alias a
            JOIN attachment_blob_store b
              ON a.sha256 = b.sha256
            WHERE a.attachment_name = ?
            """,
            [str(attachment_name)],
        ).fetchone()
        if row is None:
            return None
        return str(row[0]), str(row[1])

    def get_attachment_bytes(self, attachment_name: str) -> bytes | None:
        pointer = self.get_attachment_pointer(str(attachment_name))
        if pointer is None:
            return None
        archive_name, member_name = pointer
        archive_path = self.archive_dir / archive_name
        if not archive_path.exists():
            return None
        with zipfile.ZipFile(archive_path, mode="r") as handle:
            return handle.read(member_name)

    def clear_attachment_bytes(self) -> None:
        self.conn.execute("DELETE FROM attachment_alias")
        self.conn.execute("DELETE FROM attachment_blob_store")
        self.conn.execute("DELETE FROM attachment_archives")
        if self.archive_dir.exists():
            shutil.rmtree(self.archive_dir)

    def vacuum(self) -> None:
        self.conn.execute("CHECKPOINT")
        self.conn.execute("VACUUM")


def compact_bse_cache(
    cache_dir: Path,
    *,
    max_archive_raw_bytes: int,
    raw_cache_policy: str = DEFAULT_BSE_RAW_CACHE_POLICY,
    delete_loose_files: bool = True,
) -> dict[str, Any]:
    if raw_cache_policy not in BSE_RAW_CACHE_POLICIES:
        raise ValueError(f"unsupported_raw_cache_policy:{raw_cache_policy}")
    cache_dir = _ensure_dir(cache_dir)
    packed = CompactBseCache(cache_dir, max_archive_raw_bytes=max_archive_raw_bytes)
    before_size = _path_size(cache_dir)
    attachments_dir = cache_dir / "attachments"
    attachment_text_dir = cache_dir / "attachment_text"
    announcement_files = sorted(cache_dir.glob("ann_*.json"))
    attachment_files = sorted(attachments_dir.iterdir()) if attachments_dir.exists() else []
    text_files = sorted(attachment_text_dir.glob("*.txt")) if attachment_text_dir.exists() else []

    summary = {
        "cache_dir": str(cache_dir),
        "raw_cache_policy": raw_cache_policy,
        "before_bytes": before_size,
        "announcement_files_compacted": 0,
        "attachment_text_files_compacted": 0,
        "attachment_pdf_files_compacted": 0,
        "attachment_pdf_files_retained": 0,
    }

    for idx, path in enumerate(announcement_files, start=1):
        packed.put_announcement(path.name, path.read_text(encoding="utf-8"))
        if delete_loose_files:
            path.unlink()
        if idx % 500 == 0:
            _log(f"[compact] announcement cache {idx}/{len(announcement_files)}")
        summary["announcement_files_compacted"] += 1

    for idx, path in enumerate(text_files, start=1):
        attachment_name = path.name[:-4] if path.name.endswith(".txt") else path.name
        packed.put_attachment_text(attachment_name, path.read_text(encoding="utf-8", errors="ignore"))
        if delete_loose_files:
            path.unlink()
        if idx % 500 == 0:
            _log(f"[compact] attachment text cache {idx}/{len(text_files)}")
        summary["attachment_text_files_compacted"] += 1

    retained_payloads: dict[str, bytes] = {}
    if raw_cache_policy == "all":
        for idx, path in enumerate(attachment_files, start=1):
            if not path.is_file():
                continue
            packed.put_attachment_bytes(path.name, path.read_bytes())
            if delete_loose_files:
                path.unlink()
            if idx % 100 == 0:
                _log(f"[compact] attachment archive {idx}/{len(attachment_files)}")
            summary["attachment_pdf_files_compacted"] += 1
        summary["attachment_pdf_files_retained"] = summary["attachment_pdf_files_compacted"]
    else:
        retained_names = set(packed.attachments_with_empty_text()) if raw_cache_policy == "text_failures_only" else set()
        for attachment_name in sorted(retained_names):
            loose_path = attachments_dir / attachment_name
            payload: bytes | None = None
            if loose_path.exists():
                payload = loose_path.read_bytes()
            else:
                payload = packed.get_attachment_bytes(attachment_name)
            if payload is not None:
                retained_payloads[attachment_name] = payload
        packed.clear_attachment_bytes()
        for idx, path in enumerate(attachment_files, start=1):
            if not path.is_file():
                continue
            if path.name in retained_names and path.name not in retained_payloads:
                retained_payloads[path.name] = path.read_bytes()
            if delete_loose_files:
                path.unlink()
            if idx % 500 == 0:
                _log(f"[compact] attachment cleanup {idx}/{len(attachment_files)}")
            summary["attachment_pdf_files_compacted"] += 1
        for attachment_name, payload in retained_payloads.items():
            packed.put_attachment_bytes(attachment_name, payload)
        summary["attachment_pdf_files_retained"] = len(retained_payloads)

    packed.vacuum()
    packed.close()
    if delete_loose_files:
        _remove_empty_tree(attachments_dir)
        _remove_empty_tree(attachment_text_dir)
    after_size = _path_size(cache_dir)
    summary["after_bytes"] = after_size
    summary["bytes_saved"] = before_size - after_size
    return summary


class BseClient:
    def __init__(
        self,
        cache_dir: Path,
        *,
        max_archive_raw_bytes: int = DEFAULT_BSE_ARCHIVE_RAW_MB * 1024 * 1024,
        raw_cache_policy: str = DEFAULT_BSE_RAW_CACHE_POLICY,
    ):
        if raw_cache_policy not in BSE_RAW_CACHE_POLICIES:
            raise ValueError(f"unsupported_raw_cache_policy:{raw_cache_policy}")
        self.cache_dir = _ensure_dir(cache_dir)
        self.compact_cache = CompactBseCache(self.cache_dir, max_archive_raw_bytes=max_archive_raw_bytes)
        self.raw_cache_policy = raw_cache_policy
        self.session = requests.Session()
        self.headers = {
            "Referer": "https://www.bseindia.com/corporates/ann.html",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/javascript, */*",
            "X-Requested-With": "XMLHttpRequest",
        }
        self.pdf_headers = {
            "Referer": "https://www.bseindia.com/corporates/ann.html",
            "User-Agent": "Mozilla/5.0",
        }

    def fetch_announcements(
        self,
        scrip_code: int,
        category: str,
        start_date: pd.Timestamp,
        end_date: pd.Timestamp,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            params = {
                "strCat": category,
                "strPrevDate": start_date.strftime("%Y%m%d"),
                "strScrip": str(int(scrip_code)),
                "strSearch": "P",
                "strToDate": end_date.strftime("%Y%m%d"),
                "strType": "C",
                "pageno": str(page),
                "subcategory": "-1",
            }
            cache_name = (
                f"ann_{int(scrip_code)}_{category.lower().replace(' ', '_')}_"
                f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{page}.json"
            )
            cache_path = self.cache_dir / cache_name
            if cache_path.exists():
                raw = cache_path.read_text(encoding="utf-8")
                payload = json.loads(raw)
                self.compact_cache.put_announcement(cache_name, raw)
            else:
                cached_payload = self.compact_cache.get_announcement(cache_name)
                if cached_payload is not None:
                    payload = json.loads(cached_payload)
                else:
                    response = self.session.get(
                        "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w",
                        params=params,
                        headers=self.headers,
                        timeout=30,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    self.compact_cache.put_announcement(cache_name, json.dumps(payload))
                    time.sleep(0.15)
            page_rows = list(payload.get("Table") or [])
            if not page_rows:
                break
            rows.extend(page_rows)
            total_pages = int(page_rows[0].get("TotalPageCnt") or 1)
            page += 1
        return rows

    def attachment_bytes(self, row: dict[str, Any]) -> bytes:
        attachment = str(row.get("ATTACHMENTNAME") or "").strip()
        if not attachment:
            raise FileNotFoundError("missing_attachment_name")
        cached = self.cache_dir / "attachments" / attachment
        if cached.exists():
            return cached.read_bytes()
        compacted = self.compact_cache.get_attachment_bytes(attachment)
        if compacted is not None:
            return compacted
        prefer_hist = int(row.get("PDFFLAG") or 0) == 1
        candidates = [
            f"https://www.bseindia.com/xml-data/corpfiling/{'AttachHis' if prefer_hist else 'AttachLive'}/{attachment}",
            f"https://www.bseindia.com/xml-data/corpfiling/{'AttachLive' if prefer_hist else 'AttachHis'}/{attachment}",
        ]
        last_error: Exception | None = None
        for url in candidates:
            try:
                response = self.session.get(url, headers=self.pdf_headers, timeout=45)
                if response.status_code == 200 and "pdf" in str(response.headers.get("content-type", "")).lower():
                    if self.raw_cache_policy == "all":
                        self.compact_cache.put_attachment_bytes(attachment, response.content)
                    return response.content
            except Exception as exc:  # pragma: no cover - network variability
                last_error = exc
        if last_error is not None:
            raise last_error
        raise FileNotFoundError(f"unable_to_download_attachment:{attachment}")

    def attachment_text(self, row: dict[str, Any]) -> str:
        attachment = str(row.get("ATTACHMENTNAME") or "").strip()
        cached = self.cache_dir / "attachment_text" / f"{attachment}.txt"
        if cached.exists():
            text = cached.read_text(encoding="utf-8", errors="ignore")
            self.compact_cache.put_attachment_text(attachment, text)
            return text
        compacted = self.compact_cache.get_attachment_text(attachment)
        if compacted is not None:
            return compacted
        payload = self.attachment_bytes(row)
        try:
            text = _extract_pdf_text(payload, prefer_pypdf=True)
        except Exception as exc:
            _log(f"[warn] pdf text extraction failed for {attachment}: {exc}")
            text = ""
        self.compact_cache.put_attachment_text(attachment, text)
        if self.raw_cache_policy == "text_failures_only" and not text.strip():
            self.compact_cache.put_attachment_bytes(attachment, payload)
        return text


def _curl_download_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    verify: bool = True,
    timeout: int = 60,
) -> bytes:
    if shutil.which("curl") is None:
        raise RuntimeError("curl_not_available_for_fallback_download")
    command = [
        "curl",
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        str(timeout),
        "-A",
        "Mozilla/5.0",
    ]
    if not verify:
        command.append("--insecure")
    for key, value in (headers or {}).items():
        command.extend(["-H", f"{key}: {value}"])
    command.append(url)
    completed = subprocess.run(command, check=True, capture_output=True)
    return completed.stdout


def _bse_document_score(row: dict[str, Any]) -> int:
    raw_text = " ".join(
        str(row.get(key) or "")
        for key in ["NEWSSUB", "HEADLINE", "SUBCATNAME", "CATEGORYNAME", "ATTACHMENTNAME"]
    )
    text = " ".join(raw_text.lower().split())
    score = 0
    positive_phrases = {
        "investor presentation": 130,
        "earnings presentation": 125,
        "conference call transcript": 120,
        "earnings call transcript": 120,
        "analyst call transcript": 115,
        "transcript": 110,
        "presentation": 105,
        "factsheet": 95,
        "fact sheet": 95,
        "results update": 90,
        "result update": 90,
        "outcome of board meeting": 80,
        "outcome": 75,
        "earnings call": 65,
        "conference call": 60,
        "investor meet": 35,
        "analyst meet": 35,
    }
    negative_phrases = {
        "intimation": -120,
        "notice": -80,
        "schedule": -75,
        "audio recording": -40,
        "recording": -20,
        "newspaper publication": -60,
        "press release": -30,
        "trading window": -150,
    }
    for phrase, bonus in positive_phrases.items():
        if phrase in text:
            score += bonus
    for phrase, penalty in negative_phrases.items():
        if phrase in text:
            score += penalty
    if "results" in text or "quarter" in text or "q1" in text or "q2" in text or "q3" in text or "q4" in text:
        score += 15
    attachment = str(row.get("ATTACHMENTNAME") or "").lower()
    if attachment.endswith(".pdf"):
        score += 5
    return score


def _build_local_fs_features(features: pd.DataFrame) -> pd.DataFrame:
    quarterly = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "screener_fundamentals_quarterly.csv",
        parse_dates=["availability_date"],
    )
    quarterly = quarterly.dropna(subset=["ticker", "availability_date"]).copy()
    quarterly = quarterly.sort_values(["ticker", "availability_date"], kind="mergesort")
    grouped = quarterly.groupby("ticker", sort=False)
    quarterly["nim_4q_trend"] = grouped["financing_margin_pct"].transform(_percent_point_change)
    quarterly["npa_net_4q"] = pd.to_numeric(quarterly["net_npa_pct"], errors="coerce")
    quarterly["gnpa_yoy"] = grouped["gross_npa_pct"].transform(_percent_point_change)
    gross = pd.to_numeric(quarterly["gross_npa_pct"], errors="coerce").replace(0.0, np.nan)
    net = pd.to_numeric(quarterly["net_npa_pct"], errors="coerce")
    quarterly["provision_coverage"] = (1.0 - (net / gross)) * 100.0
    local = quarterly.rename(columns={"availability_date": "date"})[
        ["date", "ticker", "nim_4q_trend", "npa_net_4q", "gnpa_yoy", "provision_coverage"]
    ].copy()
    local["date"] = pd.to_datetime(local["date"], errors="coerce")
    return local.dropna(subset=["date", "ticker"]).reset_index(drop=True)


def _collect_bse_sector_events(
    universe: pd.DataFrame,
    *,
    sector_name: str,
    bse_client: BseClient,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    sector_rows = universe[(universe["sector"] == sector_name) & universe["bse_code"].notna()].copy()
    sector_rows["bse_code"] = sector_rows["bse_code"].astype(int)
    if sector_rows.empty:
        return pd.DataFrame()

    output_rows: list[dict[str, Any]] = []
    keywords = tuple(SECTOR_CONFIG[sector_name]["keywords"])
    total_tickers = int(len(sector_rows))
    for index, (_, row) in enumerate(sector_rows.iterrows(), start=1):
        ticker = str(row["ticker"])
        scrip = int(row["bse_code"])
        if index == 1 or index == total_tickers or index % 5 == 0:
            _log(f"[info] {sector_name}: ticker {index}/{total_tickers} {ticker}")
        try:
            result_rows = bse_client.fetch_announcements(scrip, "Result", start_date, end_date)
        except Exception as exc:  # pragma: no cover - network variability
            _log(f"[warn] result fetch failed for {ticker}: {exc}")
            continue
        if not result_rows:
            continue

        anchors = sorted(
            {
                _as_naive_timestamp(item["DT_TM"]).normalize()
                for item in result_rows
                if item.get("DT_TM")
            }
        )
        seen_attachment: set[str] = set()
        candidate_rows: list[dict[str, Any]] = []
        for anchor in anchors:
            window_start = max(anchor - pd.Timedelta(days=12), start_date)
            window_end = min(anchor + pd.Timedelta(days=20), end_date)
            try:
                updates = bse_client.fetch_announcements(scrip, "Company Update", window_start, window_end)
            except Exception as exc:  # pragma: no cover - network variability
                _log(f"[warn] company update fetch failed for {ticker} @ {anchor.date()}: {exc}")
                continue
            anchor_candidates: list[tuple[int, int, dict[str, Any]]] = []
            for item in updates:
                title = str(item.get("NEWSSUB") or "").lower()
                attachment = str(item.get("ATTACHMENTNAME") or "")
                if attachment in seen_attachment:
                    continue
                score = _bse_document_score(item)
                has_keyword = any(keyword in title for keyword in keywords)
                if not has_keyword and score < 70:
                    continue
                if score < 40:
                    continue
                distance_days = abs((_as_naive_timestamp(item["DT_TM"]).normalize() - anchor).days) if item.get("DT_TM") else 999
                anchor_candidates.append((score, distance_days, item))
            anchor_candidates.sort(key=lambda value: (-value[0], value[1], str(value[2].get("ATTACHMENTNAME") or "")))
            for score, _distance_days, item in anchor_candidates[:4]:
                attachment = str(item.get("ATTACHMENTNAME") or "")
                if attachment in seen_attachment:
                    continue
                item = dict(item)
                item["_document_score"] = score
                seen_attachment.add(attachment)
                candidate_rows.append(item)

        for item in candidate_rows:
            attachment = str(item.get("ATTACHMENTNAME") or "")
            try:
                text = bse_client.attachment_text(item)
            except Exception as exc:  # pragma: no cover - network variability
                _log(f"[warn] attachment read failed for {ticker} {attachment}: {exc}")
                continue
            event_date = _as_naive_timestamp(item["DT_TM"]).normalize()
            record: dict[str, Any] = {"ticker": ticker, "date": event_date, "attachment_name": attachment}
            if sector_name == "Financial Services":
                record.update(_extract_fs_metrics(text))
            elif sector_name == "Information Technology":
                record.update(_extract_it_metrics(text))
            elif sector_name == "Capital Goods":
                record.update(_extract_cg_metrics(text))
            if len(record) > 3:
                output_rows.append(record)

    events = pd.DataFrame(output_rows)
    if events.empty:
        return events
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    events = events.dropna(subset=["ticker", "date"]).sort_values(["ticker", "date"], kind="mergesort")

    if sector_name == "Financial Services":
        grouped = events.groupby("ticker", sort=False)
        if "nim_level" in events.columns:
            events["nim_4q_trend"] = grouped["nim_level"].transform(_percent_point_change)
        if "gnpa_level" in events.columns:
            events["gnpa_yoy"] = grouped["gnpa_level"].transform(_percent_point_change)
        if "provision_coverage" not in events.columns:
            events["provision_coverage"] = np.nan
        if "credit_deposit_ratio" not in events.columns:
            events["credit_deposit_ratio"] = np.nan
        if "loan_growth_yoy" not in events.columns:
            events["loan_growth_yoy"] = np.nan
        return events[
            [
                "ticker",
                "date",
                "nim_4q_trend",
                "npa_net_4q",
                "provision_coverage",
                "credit_deposit_ratio",
                "loan_growth_yoy",
                "casa_ratio",
                "gnpa_yoy",
            ]
        ].copy()

    if sector_name == "Information Technology":
        grouped = events.groupby("ticker", sort=False)
        if "headcount_level" in events.columns:
            events["headcount_growth"] = grouped["headcount_level"].transform(_pct_change_sparse_observed)
        if "deal_tcv_level_usd_mn" in events.columns:
            events["deal_TCV_qoq"] = grouped["deal_tcv_level_usd_mn"].transform(_pct_change)
        return events[["ticker", "date", "deal_TCV_qoq", "attrition_rate", "headcount_growth"]].copy()

    grouped = events.groupby("ticker", sort=False)
    if "order_book_level_inr_cr" in events.columns:
        cleaned_levels = grouped["order_book_level_inr_cr"].transform(_suppress_middle_outliers)
        events["order_backlog_growth"] = cleaned_levels.groupby(events["ticker"], sort=False).transform(_pct_change_sparse_observed)
    return events[["ticker", "date", "order_backlog_growth"]].copy()


def _discover_mospi_statement13_url(cache: CachedSession) -> str:
    headers = {
        "ust": MOSPI_UST,
        "content-type": "application/json",
        "origin": "https://www.mospi.gov.in",
        "referer": "https://www.mospi.gov.in/",
        "user-agent": "Mozilla/5.0",
    }
    payload = {
        "page_no": 1,
        "page_size": 10,
        "search_term": "Annual and Quarterly Estimates of GDP at constant prices",
        "sort_field": "published_year",
        "sort_order": "desc",
        "from_date": "",
        "to_date": "",
        "lang": "en",
        "publication_id": "",
        "data_source": "",
    }
    response = cache.post_json(
        "https://www.mospi.gov.in/api/publications-reports/get-web-publications-report-list",
        json_payload=payload,
        headers=headers,
        cache_key="mospi_publications_statement13.json",
    )
    items = list(response.get("data") or [])
    if not items:
        raise RuntimeError("mospi_statement13_not_found")
    path = str(((items[0] or {}).get("file_one") or {}).get("path") or "").strip("/")
    if not path:
        raise RuntimeError("mospi_statement13_missing_file_path")
    return f"https://www.mospi.gov.in/{path}"


def _build_infra_spending_index(cache: CachedSession) -> pd.DataFrame:
    workbook_url = _discover_mospi_statement13_url(cache)
    payload = cache.get_bytes(workbook_url, cache_key="mospi_statement13.xls")
    sheet = pd.read_excel(io.BytesIO(payload), sheet_name="Quarterly Constant", header=None)
    row_text = sheet.astype(str).fillna("").agg(" | ".join, axis=1)
    row_idx = row_text[
        row_text.str.contains("GFCF", case=False, na=False)
        | row_text.str.contains("Gross Fixed Capital Formation", case=False, na=False)
        | row_text.str.contains("सकल स्थायी पूंजी निर्माण", case=False, na=False)
    ].index
    if len(row_idx) == 0:
        raise RuntimeError("gfcf_row_not_found_in_mospi_workbook")
    target_row = int(row_idx[0])
    year_row = sheet.iloc[3].tolist()
    quarter_row = sheet.iloc[4].tolist()
    values_row = sheet.iloc[target_row].tolist()
    records: list[dict[str, Any]] = []
    current_year: str | None = None
    for col in range(1, len(values_row)):
        if pd.notna(year_row[col]):
            current_year = str(year_row[col]).strip()
        quarter = str(quarter_row[col]).strip() if pd.notna(quarter_row[col]) else ""
        raw_value = _coerce_numeric(values_row[col])
        if not current_year or quarter not in {"Q1", "Q2", "Q3", "Q4"} or raw_value is None:
            continue
        year_start = int(str(current_year).split("-")[0])
        month_map = {"Q1": 6, "Q2": 9, "Q3": 12, "Q4": 3}
        year_end = year_start if quarter != "Q4" else year_start + 1
        date = pd.Timestamp(year=year_end, month=month_map[quarter], day=1) + pd.offsets.MonthEnd(0)
        records.append({"date": date, "gfcf_constant": raw_value})
    frame = pd.DataFrame(records).sort_values("date", kind="mergesort").drop_duplicates("date")
    if frame.empty:
        raise RuntimeError("empty_mospi_gfcf_series")
    base_value = float(frame["gfcf_constant"].iloc[0])
    frame["infra_spending_index"] = 100.0 * frame["gfcf_constant"] / base_value
    return frame[["date", "infra_spending_index"]].reset_index(drop=True)


def _build_us_tech_index_4w() -> pd.DataFrame:
    data = yf.download("^NDX", period="10y", interval="1wk", progress=False, auto_adjust=True)
    if data is None or data.empty:
        raise RuntimeError("empty_ndx_download")
    if isinstance(data.columns, pd.MultiIndex):
        if "Close" in data.columns.get_level_values(0):
            series = data.xs("Close", axis=1, level=0).squeeze("columns")
        else:
            series = data.iloc[:, 0].squeeze("columns")
    else:
        close_col = "Close" if "Close" in data.columns else list(data.columns)[0]
        series = data[close_col]
    series = pd.to_numeric(series, errors="coerce")
    frame = pd.DataFrame({"date": pd.to_datetime(series.index).tz_localize(None), "close": series.to_numpy()})
    frame["us_tech_index_4w"] = frame["close"].pct_change(4)
    return frame[["date", "us_tech_index_4w"]].dropna(subset=["date"]).reset_index(drop=True)


def _discover_cga_summary_url(month: int, year: int) -> tuple[str, str]:
    fy_start = year if month >= 4 else year - 1
    fy_end = fy_start + 1
    fy_code = f"{str(fy_start)[-2:]}{str(fy_end)[-2:]}"
    summary_url = f"https://cga.nic.in/writereaddata/MonthAccount/{month}{year}/DATA{fy_code}.htm"
    return summary_url, fy_code


def _parse_cga_detail_table(html: str) -> pd.DataFrame:
    tables = pd.read_html(io.StringIO(html))
    monthly_tables: list[pd.DataFrame] = []
    for table in tables:
        first_col = table.iloc[:, 0].astype(str).str.lower()
        if first_col.isin([name.lower() for name in MONTH_NAME_TO_NUM]).sum() >= 3:
            monthly_tables.append(table.copy())
    if not monthly_tables:
        raise RuntimeError("cga_monthly_table_not_found")
    table = monthly_tables[-1].copy()
    table.columns = ["month", "current_monthly", "current_ytd", "prior_monthly", "prior_ytd"]
    table["month_name"] = table["month"].astype(str).str.replace(r"\s*\(prov\.?\)\s*", "", regex=True).str.strip()
    table = table[table["month_name"].str.lower().isin(MONTH_NAME_TO_NUM)].copy()
    for column in ["current_monthly", "current_ytd", "prior_monthly", "prior_ytd"]:
        table[column] = table[column].map(_coerce_numeric)
    table["month_num"] = table["month_name"].str.lower().map(MONTH_NAME_TO_NUM)
    return table[["month_name", "month_num", "current_monthly", "current_ytd", "prior_monthly", "prior_ytd"]].reset_index(drop=True)


def _build_govt_capex_qoq(cache: CachedSession, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    month_cursor = pd.Timestamp(year=start_date.year, month=start_date.month, day=1).replace(day=1)
    month_cursor = month_cursor + pd.offsets.MonthEnd(0)
    end_month = pd.Timestamp(year=end_date.year, month=end_date.month, day=1) + pd.offsets.MonthEnd(0)
    while month_cursor <= end_month:
        summary_url, fy_code = _discover_cga_summary_url(month_cursor.month, month_cursor.year)
        cache_key = f"cga_summary_{month_cursor.year}_{month_cursor.month:02d}.html"
        try:
            summary_html = cache.get_text(summary_url, cache_key=cache_key, verify=False, timeout=45)
        except Exception:
            month_cursor = month_cursor + pd.offsets.MonthEnd(1)
            continue
        soup = BeautifulSoup(summary_html, "html.parser")
        detail_href = None
        for anchor in soup.find_all("a", href=True):
            label = anchor.get_text(" ", strip=True).lower()
            href = str(anchor.get("href") or "").strip()
            if "capital expenditure" in label and "dtl" in href.lower():
                detail_href = href.split("#", 1)[0]
                break
        if not detail_href:
            month_cursor = month_cursor + pd.offsets.MonthEnd(1)
            continue
        detail_url = requests.compat.urljoin(summary_url, detail_href)
        detail_cache = f"cga_detail_{month_cursor.year}_{month_cursor.month:02d}.html"
        try:
            detail_html = cache.get_text(detail_url, cache_key=detail_cache, verify=False, timeout=45)
            parsed = _parse_cga_detail_table(detail_html)
        except Exception:
            month_cursor = month_cursor + pd.offsets.MonthEnd(1)
            continue
        target = parsed[parsed["month_num"] == month_cursor.month]
        if target.empty:
            month_cursor = month_cursor + pd.offsets.MonthEnd(1)
            continue
        current = target.iloc[0]
        frames.append(
            pd.DataFrame(
                {
                    "date": [month_cursor.normalize()],
                    "govt_capex_monthly": [current["current_monthly"]],
                    "govt_capex_ytd": [current["current_ytd"]],
                }
            )
        )
        month_cursor = month_cursor + pd.offsets.MonthEnd(1)

    monthly = pd.concat(frames, axis=0, ignore_index=True) if frames else pd.DataFrame(columns=["date", "govt_capex_monthly", "govt_capex_ytd"])
    if monthly.empty:
        return pd.DataFrame(columns=["date", "govt_capex_qoq"])
    monthly = monthly.sort_values("date", kind="mergesort").drop_duplicates("date")
    monthly["quarter"] = monthly["date"].dt.to_period("Q")
    quarterly = monthly.groupby("quarter", sort=True)["govt_capex_monthly"].sum().reset_index()
    quarterly["date"] = quarterly["quarter"].dt.end_time.dt.normalize()
    quarterly["govt_capex_qoq"] = quarterly["govt_capex_monthly"].pct_change()
    return quarterly[["date", "govt_capex_qoq"]].reset_index(drop=True)


def _build_power_sector_capex_series(cache: CachedSession) -> pd.DataFrame:
    # Exact official series still available in the 2019-20 annual report.
    report_url = "https://cea.nic.in/wp-content/uploads/annual_reports/2020/Annual_Report_2019_20.pdf"
    payload = cache.get_bytes(
        report_url,
        cache_key="cea_annual_report_2019_20.pdf",
        verify=False,
        timeout=120,
        allow_curl_fallback=True,
    )
    text = _extract_pdf_text(payload)
    pattern = re.compile(
        r"GRAND TOTAL SECTOR\s+WISE\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+).*?"
        r"\(i\)\s+THERMAL\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return pd.DataFrame(columns=["date", "power_sector_capex"])
    total_2017 = _coerce_numeric(match.group(1))
    total_2018 = _coerce_numeric(match.group(2))
    total_2019 = _coerce_numeric(match.group(3))
    rows = []
    for year, value in [(2018, total_2017), (2019, total_2018), (2020, total_2019)]:
        if value is not None:
            rows.append({"date": pd.Timestamp(year=year, month=3, day=31), "power_sector_capex": value})
    return pd.DataFrame(rows)


def _build_fill_rate_summary(frame: pd.DataFrame, fields: list[str]) -> dict[str, float]:
    summary: dict[str, float] = {}
    for field in fields:
        if field not in frame.columns:
            summary[field] = 0.0
            continue
        summary[field] = float(pd.to_numeric(frame[field], errors="coerce").notna().mean())
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Augment the feature export with public-source fields.")
    parser.add_argument("--feature-export", type=Path, default=DEFAULT_FEATURE_EXPORT)
    parser.add_argument("--metadata-export", type=Path, default=DEFAULT_METADATA_EXPORT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--max-tickers-per-sector", type=int, default=None)
    parser.add_argument("--skip-bse", action="store_true")
    parser.add_argument("--skip-macro", action="store_true")
    parser.add_argument("--skip-local-fs", action="store_true")
    parser.add_argument("--compact-bse-cache", action="store_true")
    parser.add_argument("--compact-only", action="store_true")
    parser.add_argument("--max-bse-archive-raw-mb", type=int, default=DEFAULT_BSE_ARCHIVE_RAW_MB)
    parser.add_argument(
        "--bse-raw-cache-policy",
        choices=BSE_RAW_CACHE_POLICIES,
        default=DEFAULT_BSE_RAW_CACHE_POLICY,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    feature_export = args.feature_export.expanduser().resolve()
    metadata_export = args.metadata_export.expanduser().resolve()
    source_export_root = feature_export.parent
    output_root = _ensure_dir(args.output_root.expanduser().resolve())
    component_root = _ensure_dir(output_root / "components")
    cache_root = _ensure_dir(output_root / "cache")
    bse_cache_root = _ensure_dir(cache_root / "bse")
    start_date = pd.Timestamp(args.start_date).normalize()
    end_date = _as_naive_timestamp(args.end_date).normalize() if args.end_date else pd.Timestamp.now().normalize()
    max_bse_archive_raw_bytes = int(args.max_bse_archive_raw_mb) * 1024 * 1024

    if args.compact_only:
        summary = compact_bse_cache(
            bse_cache_root,
            max_archive_raw_bytes=max_bse_archive_raw_bytes,
            raw_cache_policy=args.bse_raw_cache_policy,
            delete_loose_files=True,
        )
        _write_json(output_root / "bse_cache_compaction_summary.json", summary)
        _log(
            "[info] compacted bse cache "
            f"before={summary['before_bytes'] / 1024 / 1024 / 1024:.2f}GB "
            f"after={summary['after_bytes'] / 1024 / 1024 / 1024:.2f}GB "
            f"saved={summary['bytes_saved'] / 1024 / 1024 / 1024:.2f}GB"
        )
        return 0

    _log(f"[info] loading features from {feature_export}")
    features = pd.read_parquet(feature_export)
    features["date"] = pd.to_datetime(features["date"], errors="coerce")
    metadata_frame = pd.read_parquet(metadata_export)
    metadata_frame["date"] = pd.to_datetime(metadata_frame["date"], errors="coerce")
    _log(f"[info] feature rows={len(features)} tickers={features['ticker'].nunique()} dates={features['date'].min().date()}..{features['date'].max().date()}")

    eq_family = _derive_eq_family(features)
    eq_family.to_parquet(component_root / "eq_family.parquet", index=False)

    merged = features.copy()
    merged = merged.merge(eq_family, on=["date", "ticker"], how="left", sort=False)

    if not args.skip_local_fs:
        local_fs = _build_local_fs_features(features)
        local_fs.to_parquet(component_root / "fs_local_screener.parquet", index=False)
        merged = _merge_asof_by_ticker(
            merged,
            local_fs,
            ["nim_4q_trend", "npa_net_4q", "gnpa_yoy", "provision_coverage"],
            tolerance=pd.Timedelta(days=200),
        )
    else:
        local_fs = pd.DataFrame()

    universe = _load_sector_universe(metadata_export, PROJECT_ROOT / "data" / "processed" / "screener_metadata.csv")
    if args.max_tickers_per_sector:
        limited_parts: list[pd.DataFrame] = []
        for sector_name in SECTOR_CONFIG:
            sector_rows = universe[universe["sector"] == sector_name].head(int(args.max_tickers_per_sector))
            limited_parts.append(sector_rows)
        universe = pd.concat(limited_parts, axis=0, ignore_index=True)

    bse_results: dict[str, pd.DataFrame] = {}
    collection_errors: dict[str, str] = {}
    bse_client: BseClient | None = None
    if not args.skip_bse:
        bse_client = BseClient(
            bse_cache_root,
            max_archive_raw_bytes=max_bse_archive_raw_bytes,
            raw_cache_policy=args.bse_raw_cache_policy,
        )
        for sector_name in SECTOR_CONFIG:
            _log(f"[info] collecting BSE event features for {sector_name}")
            try:
                sector_events = _collect_bse_sector_events(
                    universe,
                    sector_name=sector_name,
                    bse_client=bse_client,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as exc:
                sector_events = pd.DataFrame()
                collection_errors[f"bse::{sector_name}"] = str(exc)
                _log(f"[warn] sector collection failed for {sector_name}: {exc}")
            bse_results[sector_name] = sector_events
            out_name = sector_name.lower().replace(" ", "_")
            sector_events.to_parquet(component_root / f"{out_name}_bse_events.parquet", index=False)
    else:
        for sector_name in SECTOR_CONFIG:
            bse_results[sector_name] = pd.DataFrame()

    fs_events = bse_results.get("Financial Services", pd.DataFrame())
    if not fs_events.empty:
        fs_events = fs_events.sort_values(["ticker", "date"], kind="mergesort")
        fs_overlay = fs_events.groupby(["ticker", "date"], sort=False).last().reset_index()
        for column in ["nim_4q_trend", "npa_net_4q", "provision_coverage", "credit_deposit_ratio", "loan_growth_yoy", "casa_ratio", "gnpa_yoy"]:
            if column not in fs_overlay.columns:
                fs_overlay[column] = np.nan
        merged = _merge_asof_by_ticker(
            merged,
            fs_overlay,
            ["nim_4q_trend", "npa_net_4q", "provision_coverage", "credit_deposit_ratio", "loan_growth_yoy", "casa_ratio", "gnpa_yoy"],
            tolerance=pd.Timedelta(days=200),
        )

    it_events = bse_results.get("Information Technology", pd.DataFrame())
    if not it_events.empty:
        it_overlay = it_events.groupby(["ticker", "date"], sort=False).last().reset_index()
        merged = _merge_asof_by_ticker(
            merged,
            it_overlay,
            ["deal_TCV_qoq", "attrition_rate", "headcount_growth"],
            tolerance=pd.Timedelta(days=200),
        )

    cg_events = bse_results.get("Capital Goods", pd.DataFrame())
    if not cg_events.empty:
        cg_overlay = cg_events.groupby(["ticker", "date"], sort=False).last().reset_index()
        merged = _merge_asof_by_ticker(
            merged,
            cg_overlay,
            ["order_backlog_growth"],
            tolerance=pd.Timedelta(days=200),
        )

    macro_results: dict[str, pd.DataFrame] = {}
    cache = CachedSession(cache_root / "macro")
    if not args.skip_macro:
        _log("[info] collecting macro series")
        macro_builders = {
            "us_tech_index_4w": {
                "builder": lambda: _build_us_tech_index_4w(),
                "tolerance": pd.Timedelta(days=14),
            },
            "infra_spending_index": {
                "builder": lambda: _build_infra_spending_index(cache),
                "tolerance": pd.Timedelta(days=120),
            },
            "govt_capex_qoq": {
                "builder": lambda: _build_govt_capex_qoq(cache, start_date, end_date),
                "tolerance": pd.Timedelta(days=120),
            },
            "power_sector_capex": {
                "builder": lambda: _build_power_sector_capex_series(cache),
                "tolerance": pd.Timedelta(days=400),
            },
        }
        for field_name, spec in macro_builders.items():
            try:
                frame = spec["builder"]()
            except Exception as exc:
                collection_errors[f"macro::{field_name}"] = str(exc)
                frame = pd.DataFrame(columns=["date", field_name])
                _log(f"[warn] macro collection failed for {field_name}: {exc}")
            frame.to_parquet(component_root / f"{field_name}.parquet", index=False)
            merged = _merge_asof_macro(merged, frame, [field_name], tolerance=spec["tolerance"])
            macro_results[field_name] = frame

    merged = _repair_quality_proxy_families(merged)
    merged = _repair_revision_factor_family(merged)
    merged = merged.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
    merged_path = output_root / "northstar_features_augmented.parquet"
    canonical_features_path = output_root / "northstar_features.parquet"
    canonical_metadata_path = output_root / "northstar_metadata.parquet"
    merged.to_parquet(merged_path, index=False)
    merged.to_parquet(canonical_features_path, index=False)
    metadata_frame.to_parquet(canonical_metadata_path, index=False)
    copied_support_files = _carry_forward_export_support_files(
        source_export_root=source_export_root,
        output_root=output_root,
        merged=merged,
        metadata=metadata_frame,
    )

    fill_rates = _build_fill_rate_summary(merged, TARGET_FIELDS)
    missing_everywhere = [field for field, fill_rate in fill_rates.items() if fill_rate <= 0.0]
    manifest = {
        "feature_export": str(feature_export),
        "metadata_export": str(metadata_export),
        "output_path": str(merged_path),
        "date_min": str(merged["date"].min().date()),
        "date_max": str(merged["date"].max().date()),
        "rows": int(len(merged)),
        "tickers": int(merged["ticker"].nunique()),
        "fill_rates": fill_rates,
        "hard_gaps": missing_everywhere,
        "collection_errors": collection_errors,
        "carried_forward_support_files": copied_support_files,
        "notes": {
            "power_sector_capex": "Exact official annual series is only recoverable from the 2019-20 CEA annual report in the current public archive path.",
            "provision_coverage": "Bank presentation values are preferred; local screener fallback uses 1 - NNPA/GNPA where direct PCR is unavailable.",
        },
    }
    if bse_client is not None:
        bse_client.compact_cache.close()
    if args.compact_bse_cache:
        summary = compact_bse_cache(
            bse_cache_root,
            max_archive_raw_bytes=max_bse_archive_raw_bytes,
            raw_cache_policy=args.bse_raw_cache_policy,
            delete_loose_files=True,
        )
        manifest["bse_cache_compaction"] = summary
        _write_json(output_root / "bse_cache_compaction_summary.json", summary)
    _write_json(output_root / "augmentation_manifest.json", manifest)

    _log("[info] fill rates")
    for field in TARGET_FIELDS:
        _log(f"  {field}: {fill_rates.get(field, 0.0):.4f}")
    _log(f"[info] wrote merged export to {merged_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
