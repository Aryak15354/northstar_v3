"""Optional external research data contracts (announcement/index membership/estimates)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd


def _read_optional_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt"}:
        return pd.read_csv(path)
    return pd.DataFrame()


def _validate_required_any(columns: set[str], groups: list[list[str]]) -> list[list[str]]:
    missing_groups: list[list[str]] = []
    for group in groups:
        if not any(c in columns for c in group):
            missing_groups.append(group)
    return missing_groups


def _audit_dataset(
    *,
    key: str,
    path: Path,
    required_cols: Iterable[str],
    required_any_groups: list[list[str]] | None = None,
) -> Dict[str, Any]:
    if not path.exists():
        return {
            "key": key,
            "status": "missing_optional_data",
            "path": str(path),
            "exists": False,
            "row_count": 0,
            "missing_columns": list(required_cols),
            "missing_any_groups": list(required_any_groups or []),
        }

    try:
        df = _read_optional_table(path)
    except Exception as exc:
        return {
            "key": key,
            "status": "schema_invalid",
            "path": str(path),
            "exists": True,
            "row_count": 0,
            "error": f"read_error:{exc}",
            "missing_columns": list(required_cols),
            "missing_any_groups": list(required_any_groups or []),
        }

    cols = {str(c) for c in df.columns}
    missing = [c for c in required_cols if c not in cols]
    missing_any_groups = _validate_required_any(cols, list(required_any_groups or []))
    if missing or missing_any_groups:
        return {
            "key": key,
            "status": "schema_invalid",
            "path": str(path),
            "exists": True,
            "row_count": int(len(df)),
            "missing_columns": missing,
            "missing_any_groups": missing_any_groups,
        }
    return {
        "key": key,
        "status": "ok",
        "path": str(path),
        "exists": True,
        "row_count": int(len(df)),
        "missing_columns": [],
        "missing_any_groups": [],
    }


def audit_external_data_interfaces(*, project_root: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Audit optional external datasets used by advanced roadmap phases.

    These interfaces are intentionally non-blocking for Parts 1-3.
    """
    ext_cfg = dict(cfg.get("external_data", {}) or {})
    ann_path = project_root / str(ext_cfg.get("announcement_dates_path", "data/external/announcement_dates.parquet"))
    idx_path = project_root / str(ext_cfg.get("index_membership_path", "data/external/index_membership_history.parquet"))
    est_path = project_root / str(ext_cfg.get("analyst_estimates_path", "data/external/analyst_estimates.parquet"))

    audits = {
        "announcement_dates": _audit_dataset(
            key="announcement_dates",
            path=ann_path,
            required_cols=["ticker"],
            required_any_groups=[["announcement_date", "date", "announced_at"]],
        ),
        "index_membership": _audit_dataset(
            key="index_membership",
            path=idx_path,
            required_cols=["ticker"],
            required_any_groups=[["effective_date", "date", "start_date"], ["index_name", "index"]],
        ),
        "analyst_estimates": _audit_dataset(
            key="analyst_estimates",
            path=est_path,
            required_cols=["ticker"],
            required_any_groups=[["estimate_date", "date", "asof_date"], ["eps_estimate", "consensus_eps", "estimate_value"]],
        ),
    }

    statuses = {str(v.get("status", "unknown")) for v in audits.values()}
    if statuses == {"ok"}:
        overall = "ok"
    elif "schema_invalid" in statuses:
        overall = "schema_invalid"
    else:
        overall = "missing_optional_data"

    return {
        "status": overall,
        "datasets": audits,
    }

