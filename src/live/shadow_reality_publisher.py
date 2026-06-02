"""Publish canonical shadow-reality artifacts from live shadow trading outputs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ShadowRealityRefreshResult:
    success: bool
    latest_date: Optional[str]
    refreshed_dates: List[str]
    shadow_state_path: str
    shadow_positions_path: str
    shadow_execution_log_path: str
    reason: str = ""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _date_from_filename(path: Path, prefix: str) -> Optional[str]:
    stem = path.stem
    if not stem.startswith(prefix):
        return None
    return stem[len(prefix) :]


def _list_artifacts_by_date(directory: Path, prefix: str) -> Dict[str, Path]:
    files: Dict[str, Path] = {}
    if not directory.exists():
        return files
    for path in sorted(directory.glob(f"{prefix}*.json")):
        date_key = _date_from_filename(path, prefix)
        if date_key:
            files[date_key] = path
    return files


def _normalize_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    normalized = parsed.dt.strftime("%Y-%m-%d")
    return normalized.where(normalized.notna(), series.astype(str))


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _fallback_timestamp_from_paths(*paths: Optional[Path]) -> str:
    existing = [path for path in paths if path is not None and path.exists()]
    if existing:
        latest_mtime = max(path.stat().st_mtime for path in existing)
        return datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def _upsert_frame(
    path: Path,
    incoming: pd.DataFrame,
    *,
    key_column: str = "date",
    preserve_existing: bool = True,
) -> None:
    if incoming.empty:
        return

    _ensure_parent(path)

    if preserve_existing and path.exists():
        try:
            existing = pd.read_parquet(path)
        except Exception as exc:
            logger.warning("Failed to read existing shadow artifact %s: %s", path, exc)
            existing = pd.DataFrame()
    else:
        existing = pd.DataFrame()

    if not existing.empty and key_column in existing.columns and key_column in incoming.columns:
        incoming_keys = set(_normalize_date_series(incoming[key_column]).tolist())
        existing_keys = _normalize_date_series(existing[key_column])
        existing = existing.loc[~existing_keys.isin(incoming_keys)].copy()

    all_columns = list(dict.fromkeys([*existing.columns.tolist(), *incoming.columns.tolist()]))
    if all_columns:
        existing = existing.reindex(columns=all_columns)
        incoming = incoming.reindex(columns=all_columns)

    combined = pd.concat([existing, incoming], ignore_index=True)

    if "timestamp" in combined.columns:
        combined = combined.assign(_sort_ts=pd.to_datetime(combined["timestamp"], errors="coerce"))
    if key_column in combined.columns:
        combined = combined.assign(_sort_date=pd.to_datetime(combined[key_column], errors="coerce"))
    sort_cols = [col for col in ["_sort_date", "_sort_ts"] if col in combined.columns]
    if sort_cols:
        combined = combined.sort_values(sort_cols).drop(columns=sort_cols)

    if key_column in combined.columns:
        combined[key_column] = _normalize_date_series(combined[key_column])
    elif "date" in combined.columns:
        combined["date"] = _normalize_date_series(combined["date"])

    combined.to_parquet(path, index=False)


def _build_shadow_position_rows(
    date_str: str,
    positions_payload: Dict[str, Any],
    *,
    positions_path: Optional[Path] = None,
) -> pd.DataFrame:
    timestamp = positions_payload.get("timestamp") or _fallback_timestamp_from_paths(positions_path)
    parsed_ts = pd.to_datetime(timestamp, errors="coerce", utc=True)
    if pd.isna(parsed_ts):
        parsed_ts = pd.Timestamp.utcnow()
    parsed_ts = parsed_ts.tz_convert("UTC").tz_localize(None)

    positions = positions_payload.get("positions", {}) or {}
    rows: List[Dict[str, Any]] = []
    for ticker, payload in positions.items():
        if not isinstance(payload, dict):
            continue
        quantity = _safe_float(payload.get("quantity", payload.get("shares", 0.0)))
        price = _safe_float(payload.get("price", payload.get("avg_price", 0.0)))
        market_value = _safe_float(payload.get("market_value"), quantity * price)
        rows.append(
            {
                "date": date_str,
                "timestamp": parsed_ts,
                "ticker": str(ticker),
                "shares": quantity,
                "quantity": quantity,
                "avg_price": _safe_float(payload.get("avg_price"), price),
                "market_value": market_value,
                "unrealized_pnl": _safe_float(payload.get("unrealized_pnl"), 0.0),
                "weight": _safe_float(payload.get("weight"), 0.0),
                "source": "daily_shadow_trader",
            }
        )
    return pd.DataFrame(rows)


def _decision_count(decisions_payload: Dict[str, Any]) -> int:
    decisions = decisions_payload.get("decisions", [])
    return len(decisions) if isinstance(decisions, list) else 0


def _extract_tracking_summary(
    pnl_payload: Dict[str, Any],
    decisions_payload: Dict[str, Any],
) -> Dict[str, Any]:
    tracking = pnl_payload.get("tracking_summary")
    if isinstance(tracking, dict):
        return dict(tracking)

    decisions = decisions_payload.get("decisions", [])
    if isinstance(decisions, list):
        for item in decisions:
            if not isinstance(item, dict):
                continue
            if str(item.get("type", "") or "") == "shadow_tracking_summary":
                return dict(item)

    fallback: Dict[str, Any] = {}
    for field in [
        "shadow_execution_mode",
        "target_position_overlap",
        "target_total_weight_drift",
        "target_max_weight_drift",
        "target_extra_positions_count",
        "target_missing_positions_count",
        "target_quantity_mismatch_count",
        "tracking_limit_breach",
        "exact_target_match",
    ]:
        if field in pnl_payload:
            fallback[field] = pnl_payload.get(field)
    return fallback


def _extract_proposals_executed(decisions_payload: Dict[str, Any]) -> int:
    decisions = decisions_payload.get("decisions", [])
    if not isinstance(decisions, list):
        return 0
    total = 0
    for item in decisions:
        if not isinstance(item, dict):
            continue
        total += int(_safe_float(item.get("prs_proposals_executed"), 0.0))
    return total


def _build_shadow_state_row(
    date_str: str,
    positions_payload: Dict[str, Any],
    pnl_payload: Dict[str, Any],
    decisions_payload: Dict[str, Any],
    target_payload: Dict[str, Any],
    *,
    positions_path: Path,
    pnl_path: Path,
    decisions_path: Optional[Path],
    target_path: Optional[Path],
) -> Dict[str, Any]:
    positions = positions_payload.get("positions", {}) or {}
    tracking_summary = _extract_tracking_summary(pnl_payload, decisions_payload)
    market_values = []
    for payload in positions.values():
        if not isinstance(payload, dict):
            continue
        quantity = _safe_float(payload.get("quantity", payload.get("shares", 0.0)))
        price = _safe_float(payload.get("price", payload.get("avg_price", 0.0)))
        market_values.append(_safe_float(payload.get("market_value"), quantity * price))

    total_position_value = _safe_float(pnl_payload.get("total_position_value"), sum(market_values))
    cash = _safe_float(pnl_payload.get("cash"), 0.0)
    portfolio_value = _safe_float(pnl_payload.get("portfolio_value"), total_position_value + cash)
    if portfolio_value <= 0.0 and total_position_value > 0.0:
        portfolio_value = total_position_value + cash
    total_exposure = total_position_value / portfolio_value if portfolio_value > 0.0 else 0.0

    timestamp = (
        positions_payload.get("timestamp")
        or pnl_payload.get("timestamp")
        or decisions_payload.get("timestamp")
        or _fallback_timestamp_from_paths(positions_path, pnl_path, decisions_path)
    )

    return {
        "date": date_str,
        "timestamp": str(timestamp),
        "nav": portfolio_value,
        "shadow_nav": portfolio_value,
        "cash": cash,
        "total_position_value": total_position_value,
        "total_exposure": total_exposure,
        "n_positions": int(len(positions)),
        "daily_return": _safe_float(pnl_payload.get("daily_return"), 0.0),
        "daily_pnl": _safe_float(pnl_payload.get("daily_pnl"), 0.0),
        "cumulative_pnl": _safe_float(pnl_payload.get("cumulative_pnl"), 0.0),
        "weights_date": pnl_payload.get("weights_date"),
        "price_date": pnl_payload.get("price_date"),
        "prev_price_date": pnl_payload.get("prev_price_date"),
        "execution_quality": 1.0,
        "reality_consistency": 1.0,
        "consistency_score": 1.0,
        "decision_count": int(_decision_count(decisions_payload)),
        "prs_proposals_executed": int(_extract_proposals_executed(decisions_payload)),
        "target_positions_count": int(len(target_payload.get("target_positions", {}) or {})),
        "target_snapshot_date": str(target_payload.get("weights_date") or date_str),
        "target_positions_json": json.dumps(target_payload.get("target_positions", {}) or {}, sort_keys=True),
        "execution_mode": str(
            tracking_summary.get("execution_mode")
            or tracking_summary.get("shadow_execution_mode")
            or pnl_payload.get("shadow_execution_mode")
            or "unknown"
        ),
        "tracking_status": str(tracking_summary.get("status", "unknown") or "unknown"),
        "tracking_breach": bool(tracking_summary.get("breach", tracking_summary.get("tracking_limit_breach", False))),
        "target_position_overlap": _safe_float(
            tracking_summary.get("target_position_overlap", pnl_payload.get("target_position_overlap")),
            0.0,
        ),
        "target_total_weight_drift": _safe_float(
            tracking_summary.get("total_weight_drift", pnl_payload.get("target_total_weight_drift")),
            0.0,
        ),
        "target_max_weight_drift": _safe_float(
            tracking_summary.get("max_symbol_weight_drift", pnl_payload.get("target_max_weight_drift")),
            0.0,
        ),
        "target_extra_positions_count": int(
            _safe_float(
                tracking_summary.get("extra_positions_count", pnl_payload.get("target_extra_positions_count")),
                0.0,
            )
        ),
        "target_missing_positions_count": int(
            _safe_float(
                tracking_summary.get(
                    "missing_target_positions_count",
                    pnl_payload.get("target_missing_positions_count"),
                ),
                0.0,
            )
        ),
        "target_quantity_mismatch_count": int(
            _safe_float(
                tracking_summary.get(
                    "quantity_mismatch_count",
                    pnl_payload.get("target_quantity_mismatch_count"),
                ),
                0.0,
            )
        ),
        "exact_target_match": bool(tracking_summary.get("exact_target_match", pnl_payload.get("exact_target_match", False))),
        "tracking_reasons_json": json.dumps(tracking_summary.get("reasons", []) or [], sort_keys=True),
        "unresolved_symbols_json": json.dumps(tracking_summary.get("unresolved_symbols", []) or [], sort_keys=True),
        "source_engine": "daily_shadow_trader",
        "positions_source_path": str(positions_path),
        "pnl_source_path": str(pnl_path),
        "decisions_source_path": str(decisions_path) if decisions_path else None,
        "target_source_path": str(target_path) if target_path else None,
    }


def _build_execution_log_row(
    date_str: str,
    positions_payload: Dict[str, Any],
    pnl_payload: Dict[str, Any],
    decisions_payload: Dict[str, Any],
    target_payload: Dict[str, Any],
    *,
    positions_path: Path,
    pnl_path: Path,
    decisions_path: Optional[Path],
    target_path: Optional[Path],
) -> Dict[str, Any]:
    tracking_summary = _extract_tracking_summary(pnl_payload, decisions_payload)
    timestamp = (
        decisions_payload.get("timestamp")
        or positions_payload.get("timestamp")
        or pnl_payload.get("timestamp")
        or _fallback_timestamp_from_paths(decisions_path, positions_path, pnl_path)
    )
    return {
        "date": date_str,
        "timestamp": str(timestamp),
        "source_engine": "daily_shadow_trader",
        "positions_path": str(positions_path),
        "pnl_path": str(pnl_path),
        "decisions_path": str(decisions_path) if decisions_path else None,
        "positions_count": int(len(positions_payload.get("positions", {}) or {})),
        "portfolio_value": _safe_float(pnl_payload.get("portfolio_value"), 0.0),
        "cash": _safe_float(pnl_payload.get("cash"), 0.0),
        "total_position_value": _safe_float(pnl_payload.get("total_position_value"), 0.0),
        "daily_return": _safe_float(pnl_payload.get("daily_return"), 0.0),
        "daily_pnl": _safe_float(pnl_payload.get("daily_pnl"), 0.0),
        "cumulative_pnl": _safe_float(pnl_payload.get("cumulative_pnl"), 0.0),
        "decision_count": int(_decision_count(decisions_payload)),
        "prs_proposals_executed": int(_extract_proposals_executed(decisions_payload)),
        "target_positions_count": int(len(target_payload.get("target_positions", {}) or {})),
        "execution_mode": str(
            tracking_summary.get("execution_mode")
            or tracking_summary.get("shadow_execution_mode")
            or pnl_payload.get("shadow_execution_mode")
            or "unknown"
        ),
        "tracking_breach": bool(tracking_summary.get("breach", tracking_summary.get("tracking_limit_breach", False))),
        "target_path": str(target_path) if target_path else None,
        "decisions_json": json.dumps(decisions_payload, default=str, sort_keys=True),
    }


def _existing_timestamp_map(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        existing = pd.read_parquet(path)
    except Exception:
        return {}
    if existing.empty or "date" not in existing.columns or "timestamp" not in existing.columns:
        return {}
    keys = _normalize_date_series(existing["date"])
    return {
        str(date_key): str(timestamp)
        for date_key, timestamp in zip(keys.tolist(), existing["timestamp"].astype(str).tolist())
        if str(date_key)
    }


def _existing_row_map(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        existing = pd.read_parquet(path)
    except Exception:
        return {}
    if existing.empty or "date" not in existing.columns:
        return {}
    existing = existing.copy()
    existing["__date_key__"] = _normalize_date_series(existing["date"])
    row_map: Dict[str, Dict[str, Any]] = {}
    for record in existing.to_dict("records"):
        date_key = str(record.pop("__date_key__", ""))
        if date_key:
            row_map[date_key] = record
    return row_map


def _sorted_intersection(left: Iterable[str], right: Iterable[str]) -> List[str]:
    return sorted(set(left) & set(right))


def _infer_target_payload_from_weights(
    date_str: str,
    *,
    weights_path: str = "data/processed/portfolio_weights.parquet",
) -> tuple[Dict[str, Any], Optional[Path]]:
    path = Path(weights_path)
    if not path.exists():
        return {}, None
    try:
        weights_df = pd.read_parquet(path)
    except Exception as exc:
        logger.warning("Failed to read portfolio weights for target inference: %s", exc)
        return {}, None
    if weights_df.empty:
        return {}, None

    date_col = "date" if "date" in weights_df.columns else ("Date" if "Date" in weights_df.columns else None)
    ticker_col = "ticker" if "ticker" in weights_df.columns else ("symbol" if "symbol" in weights_df.columns else None)
    weight_col = "weight" if "weight" in weights_df.columns else ("final_weight" if "final_weight" in weights_df.columns else None)
    if date_col is None or ticker_col is None or weight_col is None:
        return {}, None

    weights_df[date_col] = pd.to_datetime(weights_df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    snapshot = weights_df.loc[weights_df[date_col] == date_str].copy()
    if snapshot.empty:
        return {}, None

    snapshot[ticker_col] = snapshot[ticker_col].astype(str).str.strip()
    snapshot[weight_col] = pd.to_numeric(snapshot[weight_col], errors="coerce").fillna(0.0)
    snapshot = snapshot.loc[(snapshot[ticker_col] != "") & (snapshot[weight_col] > 0.0)]
    if snapshot.empty:
        return {}, None

    target_positions = {
        str(row[ticker_col]): {"weight": float(row[weight_col])}
        for _, row in snapshot.iterrows()
    }
    payload = {
        "date": date_str,
        "timestamp": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "weights_date": date_str,
        "target_positions": target_positions,
    }
    return payload, path


def refresh_shadow_reality_from_live_artifacts(
    *,
    live_data_directory: str = "data/live/shadow_trading",
    reality_directory: str = "data/shadow_reality",
    shadow_positions_path: str = "data/execution/shadow_positions.parquet",
    shadow_state_current_path: str = "data/processed/shadow_state_current.json",
    target_date: Optional[str] = None,
) -> ShadowRealityRefreshResult:
    """Backfill canonical shadow-reality artifacts from live shadow JSONs."""

    live_dir = Path(live_data_directory)
    positions_dir = live_dir / "positions"
    pnl_dir = live_dir / "pnl"
    decisions_dir = live_dir / "decisions"
    targets_dir = live_dir / "targets"
    reality_dir = Path(reality_directory)
    state_path = reality_dir / "shadow_portfolio_state.parquet"
    log_path = reality_dir / "shadow_execution_log.parquet"
    metadata_path = reality_dir / "shadow_metadata.json"
    shadow_positions = Path(shadow_positions_path)
    shadow_state_current = Path(shadow_state_current_path)

    positions_by_date = _list_artifacts_by_date(positions_dir, "positions_")
    pnl_by_date = _list_artifacts_by_date(pnl_dir, "pnl_")
    decisions_by_date = _list_artifacts_by_date(decisions_dir, "decisions_")
    targets_by_date = _list_artifacts_by_date(targets_dir, "targets_")

    candidate_dates = _sorted_intersection(positions_by_date.keys(), pnl_by_date.keys())
    if target_date:
        candidate_dates = [date for date in candidate_dates if date == target_date]

    if not candidate_dates:
        return ShadowRealityRefreshResult(
            success=False,
            latest_date=None,
            refreshed_dates=[],
            shadow_state_path=str(state_path),
            shadow_positions_path=str(shadow_positions),
            shadow_execution_log_path=str(log_path),
            reason="no_live_shadow_artifacts",
        )

    existing_timestamps = _existing_timestamp_map(state_path)
    existing_rows = _existing_row_map(state_path)
    state_rows: List[Dict[str, Any]] = []
    log_rows: List[Dict[str, Any]] = []
    latest_positions_frame = pd.DataFrame()
    latest_payload: Dict[str, Any] = {}
    refreshed_dates: List[str] = []
    latest_date = candidate_dates[-1]

    for date_str in candidate_dates:
        positions_path = positions_by_date[date_str]
        pnl_path = pnl_by_date[date_str]
        decisions_path = decisions_by_date.get(date_str)
        target_path = targets_by_date.get(date_str)

        positions_payload = _load_json(positions_path)
        pnl_payload = _load_json(pnl_path)
        decisions_payload = _load_json(decisions_path) if decisions_path and decisions_path.exists() else {}
        target_payload = _load_json(target_path) if target_path and target_path.exists() else {}
        if not target_payload:
            target_payload, inferred_target_path = _infer_target_payload_from_weights(date_str)
            if inferred_target_path is not None:
                target_path = inferred_target_path

        state_row = _build_shadow_state_row(
            date_str,
            positions_payload,
            pnl_payload,
            decisions_payload,
            target_payload,
            positions_path=positions_path,
            pnl_path=pnl_path,
            decisions_path=decisions_path,
            target_path=target_path,
        )
        existing_row = existing_rows.get(date_str, {})
        target_fields_missing = bool(
            target_payload
            and (
                not existing_row.get("target_positions_json")
                or not existing_row.get("target_snapshot_date")
                or int(_safe_float(existing_row.get("target_positions_count"), 0.0)) <= 0
            )
        )
        if existing_timestamps.get(date_str) != str(state_row["timestamp"]) or target_fields_missing:
            state_rows.append(state_row)
            refreshed_dates.append(date_str)

        log_rows.append(
            _build_execution_log_row(
                date_str,
                positions_payload,
                pnl_payload,
                decisions_payload,
                target_payload,
                positions_path=positions_path,
                pnl_path=pnl_path,
                decisions_path=decisions_path,
                target_path=target_path,
            )
        )

        if date_str == latest_date:
            latest_positions_frame = _build_shadow_position_rows(
                date_str,
                positions_payload,
                positions_path=positions_path,
            )
            latest_payload = {
                "date": date_str,
                "timestamp": state_row["timestamp"],
                "nav": state_row["nav"],
                "cash": state_row["cash"],
                "total_position_value": state_row["total_position_value"],
                "total_exposure": state_row["total_exposure"],
                "positions": positions_payload.get("positions", {}) or {},
                "target_positions": target_payload.get("target_positions", {}) or {},
                "decision_count": state_row["decision_count"],
                "prs_proposals_executed": state_row["prs_proposals_executed"],
                "source_engine": "daily_shadow_trader",
                "target_snapshot_date": state_row["target_snapshot_date"],
                "execution_mode": state_row["execution_mode"],
                "tracking_status": state_row["tracking_status"],
                "tracking_breach": state_row["tracking_breach"],
                "target_position_overlap": state_row["target_position_overlap"],
                "target_total_weight_drift": state_row["target_total_weight_drift"],
                "target_max_weight_drift": state_row["target_max_weight_drift"],
                "target_extra_positions_count": state_row["target_extra_positions_count"],
                "target_missing_positions_count": state_row["target_missing_positions_count"],
                "target_quantity_mismatch_count": state_row["target_quantity_mismatch_count"],
                "exact_target_match": state_row["exact_target_match"],
            }

    if state_rows:
        _upsert_frame(state_path, pd.DataFrame(state_rows), key_column="date")
    if log_rows:
        _upsert_frame(
            log_path,
            pd.DataFrame(log_rows),
            key_column="date",
            preserve_existing=False,
        )

    if not latest_positions_frame.empty:
        _ensure_parent(shadow_positions)
        latest_positions_frame.to_parquet(shadow_positions, index=False)

    if latest_payload:
        _ensure_parent(shadow_state_current)
        shadow_state_current.write_text(
            json.dumps(latest_payload, indent=2, default=str),
            encoding="utf-8",
        )

    _ensure_parent(metadata_path)
    metadata = {
        "published_at": datetime.now(timezone.utc).isoformat(),
        "publisher": "shadow_reality_publisher",
        "source_engine": "daily_shadow_trader",
        "live_data_directory": str(live_dir),
        "shadow_state_path": str(state_path),
        "shadow_positions_path": str(shadow_positions),
        "shadow_execution_log_path": str(log_path),
        "shadow_state_current_path": str(shadow_state_current),
        "latest_trading_date": latest_date,
        "candidate_dates": candidate_dates,
        "refreshed_dates": refreshed_dates,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")

    return ShadowRealityRefreshResult(
        success=True,
        latest_date=latest_date,
        refreshed_dates=refreshed_dates,
        shadow_state_path=str(state_path),
        shadow_positions_path=str(shadow_positions),
        shadow_execution_log_path=str(log_path),
        reason="ok",
    )
