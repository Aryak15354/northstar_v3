#!/usr/bin/env python3
"""Modern end-to-end daily runner for Northstar V3 Gaps 1-7."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cohesion.state_file_manager import StateFileManager
from src.core.state import UnifiedState
from src.ingestion import IngestionRegistry
from src.sentiment.sentiment_regime import SentimentRegimeClassifier
from src.sentiment.sentiment_state import compute_sentiment_state

try:
    from src.alternative_data.alternative_pipeline_runner import AlternativePipelineRunner
    from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
    from src.core.state_bridges.runtime_bridge import RuntimeStateBridge
    from src.core.state_bridges.shadow_bridge import ShadowStateBridge
    from src.live.shadow_reality_publisher import refresh_shadow_reality_from_live_artifacts
    from src.portfolio.governor import PortfolioGovernor
    from src.portfolio.governor_state import GovernorState
except Exception:
    # CI quick mode only needs market refresh helpers from this module.
    AlternativePipelineRunner = None
    StateAuthority = None
    StateUpdate = None
    WritePriority = None
    RuntimeStateBridge = None
    ShadowStateBridge = None
    refresh_shadow_reality_from_live_artifacts = None
    PortfolioGovernor = None
    GovernorState = None

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    name: str
    required: bool
    status: str
    summary: str
    command: Optional[str]
    started_at: str
    finished_at: str
    duration_seconds: float
    returncode: Optional[int]
    log_path: Optional[str]


def _ci_gate_mode() -> bool:
    raw = str(os.getenv("NORTHSTAR_CI_GATE", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def resolve_date(raw: str) -> pd.Timestamp:
    if str(raw).strip().lower() == "today":
        return pd.Timestamp.today().normalize()
    value = pd.to_datetime(raw, errors="coerce")
    if pd.isna(value):
        raise ValueError(f"invalid --date: {raw}")
    return pd.Timestamp(value).normalize()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def check_market_data_freshness(max_age_hours: float = 4.0) -> dict[str, Any]:
    """Abort the intelligence stack if all canonical market-refresh artifacts are stale."""
    candidate_paths = [
        PROJECT_ROOT / "data" / "processed" / "market_state.parquet",
        PROJECT_ROOT / "data" / "options" / "live" / "market_data_latest.json",
        PROJECT_ROOT / "data" / "processed" / "prices.parquet",
    ]
    existing_paths = [path for path in candidate_paths if path.exists()]
    if not existing_paths:
        raise FileNotFoundError(
            "No canonical market data artifacts found. Checked: "
            + ", ".join(str(path) for path in candidate_paths)
        )

    freshest_path = max(existing_paths, key=lambda path: path.stat().st_mtime)
    file_age_hours = max((time.time() - freshest_path.stat().st_mtime) / 3600.0, 0.0)
    india_tz = timezone(timedelta(hours=5, minutes=30))
    now_ist = datetime.now(india_tz)
    is_market_hours = dtime(9, 0) <= now_ist.time() <= dtime(16, 0)
    if is_market_hours and file_age_hours > max_age_hours:
        print(
            f"CRITICAL: Market data is {file_age_hours:.1f} hours old during market hours. "
            "Aborting pipeline to prevent decisions on stale data. "
            "Run the market refresh pipeline first."
        )
        raise SystemExit(1)
    if (not is_market_hours) and file_age_hours > 14.0:
        return {
            "status": "warning",
            "freshest_artifact": str(freshest_path),
            "checked_artifacts": [str(path) for path in existing_paths],
            "file_age_hours": round(file_age_hours, 3),
            "max_age_hours": float(max_age_hours),
            "message": (
                f"Market data is {file_age_hours:.1f} hours old outside market hours. "
                "Refresh before next open."
            ),
        }

    return {
        "status": "fresh",
        "freshest_artifact": str(freshest_path),
        "checked_artifacts": [str(path) for path in existing_paths],
        "file_age_hours": round(file_age_hours, 3),
        "max_age_hours": float(max_age_hours),
    }


def tail_text(path: Path, max_lines: int = 12) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def deep_merge(base: dict, extra: dict) -> dict:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_system_config() -> dict:
    config: dict = {}

    ingestion_path = PROJECT_ROOT / "config" / "ingestion_config.yaml"
    if ingestion_path.exists():
        payload = yaml.safe_load(ingestion_path.read_text()) or {}
        if isinstance(payload, dict):
            config = deep_merge(config, payload)

    pnl_path = PROJECT_ROOT / "config" / "pnl_config.yaml"
    if pnl_path.exists():
        payload = yaml.safe_load(pnl_path.read_text()) or {}
        if isinstance(payload, dict):
            config = deep_merge(config, payload)

    governor_path = PROJECT_ROOT / "config" / "portfolio_governor_config.yaml"
    if governor_path.exists():
        payload = yaml.safe_load(governor_path.read_text()) or {}
        if isinstance(payload, dict):
            config["portfolio_governor"] = payload
            if "starting_capital_inr" in payload:
                config["starting_capital_inr"] = payload["starting_capital_inr"]

    sentiment_path = PROJECT_ROOT / "config" / "sentiment_config.yaml"
    if sentiment_path.exists():
        payload = yaml.safe_load(sentiment_path.read_text()) or {}
        if isinstance(payload, dict):
            config = deep_merge(config, payload)

    nlp_path = PROJECT_ROOT / "config" / "nlp_config.yaml"
    if nlp_path.exists():
        payload = yaml.safe_load(nlp_path.read_text()) or {}
        if isinstance(payload, dict):
            config = deep_merge(config, payload)

    valuation_path = PROJECT_ROOT / "config" / "valuation_config.yaml"
    if valuation_path.exists():
        payload = yaml.safe_load(valuation_path.read_text()) or {}
        if isinstance(payload, dict):
            config = deep_merge(config, payload)

    config.setdefault("starting_capital_inr", 10_000_000)
    return config


def dataclass_leaf_updates(
    *,
    writer_id: str,
    section: str,
    obj: Any,
    priority: WritePriority,
    source: str,
    reason: str,
) -> list[StateUpdate]:
    if not is_dataclass(obj):
        raise TypeError(f"expected dataclass for section {section}")

    updates: list[StateUpdate] = []

    def walk(value: Any, prefix: str = "") -> None:
        for field_meta in fields(value):
            field_name = field_meta.name
            field_value = getattr(value, field_name)
            field_path = f"{prefix}.{field_name}" if prefix else field_name
            if is_dataclass(field_value):
                walk(field_value, field_path)
            else:
                updates.append(
                    StateUpdate(
                        writer_id=writer_id,
                        section=section,
                        field_path=field_path,
                        new_value=field_value,
                        priority=priority,
                        source=source,
                        reason=reason,
                    )
                )

    walk(obj)
    return updates


def health_snapshot_to_updates(
    *,
    writer_id: str,
    snapshot: Dict[str, Dict[str, Any]],
    intelligence_active: bool,
    portfolio_active: bool,
) -> list[StateUpdate]:
    total = len(snapshot)
    fresh = sum(1 for item in snapshot.values() if bool(item.get("is_fresh")))
    available = sum(1 for item in snapshot.values() if str(item.get("status", "")).lower() not in {"error", "unavailable"})

    data_source_criticality = {
        "market_data": 1.0,
        "sentiment": 0.9,
        "macro_data": 0.8,
        "fundamentals": 0.7,
        "alternative_data": 0.5,
    }

    freshness_values: list[float] = []
    for item in snapshot.values():
        raw_last_updated = item.get("last_updated")
        if raw_last_updated in (None, "", "None"):
            continue
        parsed = pd.to_datetime(raw_last_updated, errors="coerce")
        if pd.notna(parsed):
            age_hours = max((pd.Timestamp.utcnow().tz_localize(None) - pd.Timestamp(parsed).tz_localize(None)).total_seconds() / 3600.0, 0.0)
            freshness_values.append(float(age_hours))

    worst_freshness_hours = max(freshness_values) if freshness_values else 0.0
    fresh_ratio = (fresh / total) if total else 0.0
    availability_ratio = (available / total) if total else 0.0
    total_weight = sum(data_source_criticality.values())
    achieved_weight = 0.0
    for source_name, criticality in data_source_criticality.items():
        item = snapshot.get(source_name, {})
        if bool(item.get("is_fresh")):
            achieved_weight += criticality
        elif str(item.get("status", "")).lower() not in {"error", "unavailable"}:
            achieved_weight += criticality * 0.5

    overall_health_score = (achieved_weight / total_weight) if total_weight else 0.0
    critical_sources_fresh = all(
        bool(snapshot.get(source_name, {}).get("is_fresh"))
        for source_name, criticality in data_source_criticality.items()
        if criticality >= 1.0
    )

    if overall_health_score >= 0.85 and critical_sources_fresh:
        health_status = "healthy"
    elif overall_health_score >= 0.60 or critical_sources_fresh:
        health_status = "degraded"
    else:
        health_status = "critical"

    fields_to_write = {
        "overall_health_score": float(overall_health_score),
        "health_status": health_status,
        "data_fresh": fresh == total and total > 0,
        "data_freshness_hours": float(worst_freshness_hours),
        "component_availability": float(availability_ratio),
        "components_healthy": int(fresh),
        "total_components": int(total),
        "portfolio_active": bool(portfolio_active),
        "intelligence_active": bool(intelligence_active),
        "last_updated": datetime.now(),
    }

    return [
        StateUpdate(
            writer_id=writer_id,
            section="health",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Complete V3 system health sync",
        )
        for field_path, value in fields_to_write.items()
    ]


def load_pnl_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "last_updated": datetime.now(),
    }

    nav_path = PROJECT_ROOT / "data" / "pnl" / "nav_history.parquet"
    if nav_path.exists():
        try:
            nav_df = pd.read_parquet(nav_path)
        except Exception:
            nav_df = pd.DataFrame()
        if not nav_df.empty:
            date_col = next((col for col in nav_df.columns if col.lower() == "date"), None)
            if date_col:
                nav_df[date_col] = pd.to_datetime(nav_df[date_col], errors="coerce")
                nav_df = nav_df.sort_values(date_col, kind="mergesort")
            latest = nav_df.iloc[-1]
            nav_value = latest.get("nav_combined", latest.get("nav", 0.0))
            nav_per_unit = latest.get("nav_per_unit", 0.0)
            drawdown = latest.get("drawdown", latest.get("drawdown_pct", 0.0))
            drawdown_pct = float(drawdown) * 100.0 if pd.notna(drawdown) else 0.0

            snapshot.update(
                {
                    "current_nav_inr": float(pd.to_numeric(nav_value, errors="coerce") or 0.0),
                    "current_nav_per_unit": float(pd.to_numeric(nav_per_unit, errors="coerce") or 0.0),
                    "current_drawdown_pct": float(drawdown_pct),
                    "last_eod_processing": latest.get(date_col) if date_col else None,
                }
            )

    recon_path = PROJECT_ROOT / "data" / "pnl" / "reconciliation_log.parquet"
    if recon_path.exists():
        try:
            recon_df = pd.read_parquet(recon_path)
        except Exception:
            recon_df = pd.DataFrame()
        if not recon_df.empty:
            date_col = next((col for col in recon_df.columns if "date" in col.lower() or "computed" in col.lower()), None)
            if date_col:
                recon_df[date_col] = pd.to_datetime(recon_df[date_col], errors="coerce")
                recon_df = recon_df.sort_values(date_col, kind="mergesort")
            latest = recon_df.iloc[-1]
            status = latest.get("overall_status", latest.get("status", "UNKNOWN"))
            snapshot["last_reconciliation_status"] = str(status)
            if date_col:
                snapshot["last_reconciliation_date"] = latest.get(date_col)

    return snapshot


def _ratio_value(value: Any, default: float = 0.0) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return float(default)
    ratio = float(numeric)
    return float(max(0.0, min(1.0, ratio)))


def _validate_exposure_field(value: Any, field_name: str, default: float = 0.0) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return float(default)
    ratio = float(numeric)
    if ratio > 1.5:
        raise ValueError(
            f"Exposure field '{field_name}' = {ratio}. "
            "All exposure values must be decimal ratios (0.0 to 1.0), not percentage points."
        )
    return float(max(0.0, min(1.0, ratio)))


def _maybe_migrate_legacy_exposure_columns(
    df: pd.DataFrame,
    *,
    source_name: str,
    columns: tuple[str, ...] = ("allowed_exposure", "ai_allowed_exposure"),
) -> tuple[pd.DataFrame, list[str]]:
    if df.empty:
        return df, []

    working = df.copy()
    migrated_columns: list[str] = []
    for column in columns:
        if column not in working.columns:
            continue
        numeric = pd.to_numeric(working[column], errors="coerce")
        legacy_mask = numeric > 1.5
        if not legacy_mask.any():
            continue
        legacy_max = float(numeric[legacy_mask].max())
        if legacy_max > 100.0:
            raise ValueError(
                f"Exposure field '{column}' in {source_name} = {legacy_max}. "
                "Legacy percentage-point migration only supports values up to 100.0."
            )
        working.loc[legacy_mask, column] = numeric.loc[legacy_mask] / 100.0
        migrated_columns.append(column)

    if migrated_columns:
        logger.warning(
            "Migrated legacy exposure columns in %s: %s",
            source_name,
            ", ".join(migrated_columns),
        )
    return working, migrated_columns


def _numeric_value(value: Any, default: float = 0.0) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return float(default)
    return float(numeric)


def _naive_timestamp(value: Any) -> Optional[pd.Timestamp]:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        return ts.tz_convert(None)
    return ts


def load_core_state_payload() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {
        "market": {},
        "macro": {},
        "regime": {},
        "beliefs": {},
    }

    market_state_path = PROJECT_ROOT / "data" / "processed" / "market_state.parquet"
    if market_state_path.exists():
        try:
            market_df = pd.read_parquet(market_state_path)
        except Exception:
            market_df = pd.DataFrame()
        if not market_df.empty:
            market_df, migrated_columns = _maybe_migrate_legacy_exposure_columns(
                market_df,
                source_name=str(market_state_path),
                columns=("allowed_exposure",),
            )
            if migrated_columns:
                market_df.to_parquet(market_state_path, index=False)
        if not market_df.empty:
            latest = market_df.iloc[-1]
            updated_at = pd.to_datetime(latest.get("date"), errors="coerce")
            updated_at = (
                pd.Timestamp(updated_at).to_pydatetime()
                if pd.notna(updated_at)
                else datetime.now()
            )
            payload["market"] = {
                "regime": str(latest.get("regime", "unknown") or "unknown"),
                "risk_on_probability": _ratio_value(
                    latest.get("risk_on_probability", latest.get("risk_on", 0.5)),
                    0.5,
                ),
                "allowed_exposure": _validate_exposure_field(
                    latest.get("allowed_exposure", 0.35),
                    "allowed_exposure",
                    0.35,
                ),
                "volatility_regime": str(latest.get("volatility_regime", "normal") or "normal"),
                "market_stress": _numeric_value(latest.get("stress_score", latest.get("stress_level", 0.0)), 0.0),
                "breadth_pct": _numeric_value(latest.get("breadth_pct", 50.0), 50.0),
                "participation_score": _numeric_value(latest.get("participation_score", 0.5), 0.5),
                "correlation": _numeric_value(latest.get("correlation", 0.5), 0.5),
                "last_updated": updated_at,
                "pulse_intensity": _numeric_value(latest.get("pulse_intensity", 0.0), 0.0),
                "market_phase": str(latest.get("market_phase", "neutral") or "neutral"),
                "pulse_risk_level": str(latest.get("pulse_risk_level", "low") or "low"),
                "regime_similarity": _numeric_value(latest.get("regime_similarity", 0.0), 0.0),
                "brain_regime": str(latest.get("regime_name", latest.get("regime", "Unknown")) or "Unknown"),
            }
            payload["macro"] = {
                "liquidity_conditions": str(latest.get("liquidity_state", "normal") or "normal"),
                "policy_stance": str(latest.get("macro_regime", "neutral") or "neutral"),
                "macro_score": _numeric_value(latest.get("macro_score", 0.0), 0.0),
                "last_updated": updated_at,
            }
            payload["regime"] = {
                "current_regime": str(latest.get("regime_name", latest.get("regime", "unknown")) or "unknown"),
                "regime_confidence": _numeric_value(latest.get("confidence", 0.5), 0.5),
                "historical_similarity": _numeric_value(latest.get("regime_similarity", 0.0), 0.0),
                "last_updated": updated_at,
            }

    intelligent_market_state_path = PROJECT_ROOT / "data" / "processed" / "intelligent_market_state.parquet"
    if intelligent_market_state_path.exists():
        try:
            intelligent_df = pd.read_parquet(intelligent_market_state_path)
        except Exception:
            intelligent_df = pd.DataFrame()
        if not intelligent_df.empty:
            intelligent_df, migrated_columns = _maybe_migrate_legacy_exposure_columns(
                intelligent_df,
                source_name=str(intelligent_market_state_path),
            )
            if migrated_columns:
                intelligent_df.to_parquet(intelligent_market_state_path, index=False)

    intelligence_state_path = PROJECT_ROOT / "data" / "intelligence" / "intelligence_state.json"
    if intelligence_state_path.exists():
        try:
            intelligence_payload = json.loads(intelligence_state_path.read_text(encoding="utf-8"))
            beliefs = intelligence_payload.get("beliefs") or {}
            conviction_levels = beliefs.get("conviction_levels") or {}
            timestamp = pd.to_datetime(intelligence_payload.get("timestamp"), errors="coerce")
            updated_at = (
                pd.Timestamp(timestamp).to_pydatetime()
                if pd.notna(timestamp)
                else datetime.now()
            )
            payload["beliefs"] = {
                "valuation_conviction": _numeric_value((beliefs.get("valuation_beliefs") or {}).get("conviction", 0.0), 0.0),
                "market_conviction": _numeric_value((beliefs.get("market_beliefs") or {}).get("conviction", 0.0), 0.0),
                "strategy_conviction": _numeric_value(conviction_levels.get("strategy", conviction_levels.get("overall", 0.0)), 0.0),
                "narrative_conviction": _numeric_value((beliefs.get("narrative_beliefs") or {}).get("conviction", 0.0), 0.0),
                "unified_conviction": _numeric_value(conviction_levels.get("overall", 0.0), 0.0),
                "last_updated": updated_at,
            }
        except Exception:
            pass

    return payload


def load_equity_portfolio_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {}

    weights_path = PROJECT_ROOT / "data" / "processed" / "portfolio_weights.parquet"
    analytics_path = PROJECT_ROOT / "data" / "processed" / "portfolio_analytics.json"

    weights_df = pd.DataFrame()
    if weights_path.exists():
        try:
            weights_df = pd.read_parquet(weights_path)
        except Exception:
            weights_df = pd.DataFrame()

    if not weights_df.empty:
        symbol_col = "symbol" if "symbol" in weights_df.columns else ("ticker" if "ticker" in weights_df.columns else None)
        weight_col = "final_weight" if "final_weight" in weights_df.columns else ("weight" if "weight" in weights_df.columns else None)
        if weight_col:
            weights_df[weight_col] = pd.to_numeric(weights_df[weight_col], errors="coerce").fillna(0.0)
            snapshot.update(
                {
                    "total_positions": int(len(weights_df)),
                    "total_exposure": float(weights_df[weight_col].sum()),
                    "max_position": float(weights_df[weight_col].max() if len(weights_df) else 0.0),
                    "long_positions": int((weights_df[weight_col] > 0).sum()),
                    "short_positions": int((weights_df[weight_col] < 0).sum()),
                    "position_count": int(len(weights_df)),
                    "largest_position_pct": float(weights_df[weight_col].max() if len(weights_df) else 0.0),
                    "positions": {
                        str(row.get(symbol_col) or row.get("ticker") or f"equity_{idx}"): row
                        for idx, row in enumerate(weights_df.to_dict("records"))
                    },
                }
            )
            if "timestamp" in weights_df.columns:
                latest_ts = pd.to_datetime(weights_df["timestamp"], errors="coerce").dropna()
                if not latest_ts.empty:
                    snapshot["last_updated"] = pd.Timestamp(latest_ts.max()).to_pydatetime()

    if analytics_path.exists():
        try:
            analytics_payload = json.loads(analytics_path.read_text(encoding="utf-8"))
            summary = analytics_payload.get("portfolio_summary") or {}
            sector_allocation = analytics_payload.get("sector_allocation") or {}
            snapshot.update(
                {
                    "total_positions": int(summary.get("total_positions", summary.get("n_positions", snapshot.get("total_positions", 0)))),
                    "total_exposure": float(summary.get("total_exposure", snapshot.get("total_exposure", 0.0))),
                    "largest_position_pct": float(summary.get("largest_position", snapshot.get("largest_position_pct", 0.0))),
                    "cash": float(summary.get("cash_level", summary.get("cash", snapshot.get("cash", 0.0)))),
                    "sector_exposure": sector_allocation,
                    "sector_allocation": sector_allocation,
                }
            )
            analytics_ts = pd.to_datetime(analytics_payload.get("timestamp"), errors="coerce")
            if pd.notna(analytics_ts):
                snapshot["last_updated"] = pd.Timestamp(analytics_ts).to_pydatetime()
        except Exception:
            pass

    return snapshot


def _normalize_symbol_key(value: Any) -> str:
    symbol = str(value or "").strip().upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        symbol = symbol.rsplit(".", 1)[0]
    return symbol


def _portfolio_target_updates(snapshot: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "positions": "target_positions",
        "total_positions": "target_total_positions",
        "position_count": "target_position_count",
        "total_exposure": "target_total_exposure",
        "max_position": "target_max_position",
        "largest_position_pct": "target_largest_position_pct",
        "long_positions": "target_long_positions",
        "short_positions": "target_short_positions",
        "sector_exposure": "target_sector_exposure",
        "sector_allocation": "target_sector_allocation",
        "last_updated": "target_last_updated",
    }
    return {
        target_field: snapshot[source_field]
        for source_field, target_field in mapping.items()
        if source_field in snapshot
    }


def _build_live_equity_rows(
    live_positions: dict[str, Any],
    target_snapshot: dict[str, Any],
    total_portfolio_value: float,
) -> list[dict[str, Any]]:
    if not isinstance(live_positions, dict):
        return []

    target_positions = {
        _normalize_symbol_key(symbol): dict(payload or {})
        for symbol, payload in dict(target_snapshot.get("positions", {}) or {}).items()
    }
    denominator = float(total_portfolio_value or 0.0)
    if denominator <= 0.0:
        denominator = float(
            sum(float((payload or {}).get("market_value", 0.0) or 0.0) for payload in live_positions.values())
        )

    rows: list[dict[str, Any]] = []
    for symbol, payload in live_positions.items():
        row = dict(target_positions.get(_normalize_symbol_key(symbol), {}))
        row.update(dict(payload or {}))
        market_value = float(row.get("market_value", 0.0) or 0.0)
        if denominator > 0.0:
            row["weight"] = market_value / denominator
        row.setdefault("symbol", str(symbol))
        row.setdefault("ticker", str(symbol))
        row.setdefault("Industry", row.get("sector", "Unknown"))
        rows.append(row)
    return rows


def _maybe_refresh_shadow_reality(logger: logging.Logger) -> Optional[Dict[str, Any]]:
    """Self-heal canonical shadow artifacts from live shadow trading outputs."""
    try:
        refresh_result = refresh_shadow_reality_from_live_artifacts()
    except Exception as exc:
        logger.warning("Shadow reality refresh failed: %s", exc)
        return None

    if not refresh_result.success:
        logger.info("Shadow reality refresh skipped: %s", refresh_result.reason)
        return None

    logger.info(
        "Shadow reality refresh complete: latest_date=%s refreshed_dates=%s",
        refresh_result.latest_date,
        refresh_result.refreshed_dates,
    )
    return {
        "latest_date": refresh_result.latest_date,
        "refreshed_dates": refresh_result.refreshed_dates,
        "shadow_state_path": refresh_result.shadow_state_path,
        "shadow_positions_path": refresh_result.shadow_positions_path,
        "shadow_execution_log_path": refresh_result.shadow_execution_log_path,
    }


def _write_urgent_shock_flag(market_intelligence_state: Any) -> dict[str, Any] | None:
    if market_intelligence_state is None or not getattr(market_intelligence_state, "available", False):
        return None
    if getattr(market_intelligence_state, "shock_severity").value < 3:
        return None

    payload = {
        "shock_type": market_intelligence_state.primary_shock_type.value,
        "severity": market_intelligence_state.shock_severity.name,
        "shock_direction": market_intelligence_state.shock_direction.value,
        "shock_confidence": float(getattr(market_intelligence_state, "shock_confidence", 0.0) or 0.0),
        "requires_immediate_hedge": bool(getattr(market_intelligence_state, "requires_immediate_hedge", False)),
        "written_at": datetime.now().isoformat(),
    }
    flag_path = PROJECT_ROOT / "data" / "intelligence" / "urgent_shock_flag.json"
    flag_path.parent.mkdir(parents=True, exist_ok=True)
    flag_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _write_shock_rebalance_instructions(
    config: dict[str, Any],
    market_intelligence_state: Any,
    current_positions: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if market_intelligence_state is None or not getattr(market_intelligence_state, "available", False):
        return None
    if not bool(getattr(market_intelligence_state, "requires_portfolio_rebalance", False)):
        return None

    try:
        from src.intelligence.shock_engine.shock_response_engine import ShockResponseEngine

        engine = ShockResponseEngine(config)
        plan = engine.evaluate(market_intelligence_state, current_positions)
    except Exception:
        logger.exception("Shock response engine failed while writing rebalance instructions")
        return None

    if not plan.rebalance_instructions and not plan.options_instructions:
        return None

    payload = {
        "generated_at": datetime.now().isoformat(),
        "shock_type": market_intelligence_state.primary_shock_type.value,
        "shock_severity": market_intelligence_state.shock_severity.name,
        "shock_direction": market_intelligence_state.shock_direction.value,
        "rebalance_instructions": [asdict(item) for item in plan.rebalance_instructions],
        "options_instructions": [asdict(item) for item in plan.options_instructions],
    }
    instructions_path = PROJECT_ROOT / "data" / "intelligence" / "shock_rebalance_instructions.json"
    instructions_path.parent.mkdir(parents=True, exist_ok=True)
    instructions_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def _compute_weight_entropy(weights: Dict[str, float]) -> float:
    usable = [abs(float(value)) for value in weights.values() if pd.notna(value) and abs(float(value)) > 0.0]
    total = sum(usable)
    if total <= 0.0:
        return 0.0
    entropy = 0.0
    for value in usable:
        probability = value / total
        entropy -= probability * math.log(probability)
    return float(entropy)


def load_alpha_os_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "last_updated": datetime.now(),
        "strategy_weights": {},
    }

    try:
        from src.alpha_os.strategy_registry import StrategyRegistry, StrategyStatus

        registry = StrategyRegistry()
        active = registry.get_by_status(StrategyStatus.ACTIVE)
        probation = registry.get_by_status(StrategyStatus.PROBATION)
        candidate = registry.get_by_status(StrategyStatus.CANDIDATE)

        snapshot.update(
            {
                "active_strategy_count": int(len(active)),
                "probation_strategy_count": int(len(probation)),
                "candidate_strategy_count": int(len(candidate)),
                "redundancy_issues": int(
                    sum(
                        1
                        for record in registry.strategies.values()
                        if getattr(record.status, "value", str(record.status)) == "REDUNDANT"
                        or bool(getattr(record, "redundant_with", None))
                    )
                ),
            }
        )

        active_icirs = [float(record.validation_icir) for record in active if pd.notna(record.validation_icir)]
        if active_icirs:
            snapshot["avg_active_icir"] = float(sum(active_icirs) / len(active_icirs))

        weakest_candidates = []
        for record in active + probation:
            live_ic = record.current_live_ic if record.current_live_ic is not None else record.validation_icir
            weakest_candidates.append((float(live_ic or 0.0), record.strategy_id))
        if weakest_candidates:
            weakest_candidates.sort(key=lambda item: item[0])
            snapshot["weakest_strategy_live_ic"] = float(weakest_candidates[0][0])
            snapshot["weakest_strategy_id"] = weakest_candidates[0][1]

        event_dates = {
            "last_promotion_date": [],
            "last_retirement_date": [],
            "last_probation_date": [],
        }
        status_key_map = {
            "ACTIVE": "last_promotion_date",
            "RETIRED": "last_retirement_date",
            "PROBATION": "last_probation_date",
        }
        for record in registry.strategies.values():
            for event in record.status_change_log:
                event_time = pd.to_datetime(event.get("timestamp"), errors="coerce")
                if pd.isna(event_time):
                    continue
                target_key = status_key_map.get(str(event.get("to_status", "")).upper())
                if target_key:
                    event_dates[target_key].append(pd.Timestamp(event_time).to_pydatetime())

        for field_name, values in event_dates.items():
            if values:
                snapshot[field_name] = max(values)
    except Exception:
        pass

    posterior_path = PROJECT_ROOT / "data" / "processed" / "alpha_os_strategy_posteriors.parquet"
    runtime_path = PROJECT_ROOT / "data" / "options" / "live" / "options_runtime_state.json"

    weights: Dict[str, float] = {}
    posterior_weights: Dict[str, float] = {}
    runtime_weights: Dict[str, float] = {}
    posterior_ts: Optional[pd.Timestamp] = None
    runtime_ts: Optional[pd.Timestamp] = None
    if posterior_path.exists():
        try:
            posterior_df = pd.read_parquet(posterior_path)
            if not posterior_df.empty and {"timestamp", "strategy_name", "final_weight"}.issubset(posterior_df.columns):
                posterior_df["timestamp"] = pd.to_datetime(posterior_df["timestamp"], errors="coerce")
                latest_ts = posterior_df["timestamp"].dropna().max()
                latest_df = posterior_df.loc[posterior_df["timestamp"] == latest_ts]
                posterior_weights = {
                    str(row["strategy_name"]): float(row["final_weight"])
                    for _, row in latest_df.iterrows()
                    if abs(float(row["final_weight"])) > 0.0
                }
                posterior_ts = _naive_timestamp(latest_ts)
        except Exception:
            posterior_weights = {}
            posterior_ts = None

    if runtime_path.exists():
        try:
            runtime_payload = json.loads(runtime_path.read_text(encoding="utf-8"))
            runtime_weights_raw = ((runtime_payload.get("alpha_os_last_intent") or {}).get("strategy_weights") or {})
            runtime_weights = {str(key): float(value) for key, value in runtime_weights_raw.items()}
            runtime_ts = _naive_timestamp(runtime_payload.get("timestamp"))
        except Exception:
            runtime_weights = {}
            runtime_ts = None

    runtime_is_meaningfully_newer = (
        runtime_ts is not None and (
            posterior_ts is None or runtime_ts >= posterior_ts + pd.Timedelta(hours=6)
        )
    )
    if runtime_is_meaningfully_newer:
        weights = runtime_weights
        snapshot["last_updated"] = runtime_ts.to_pydatetime()
    elif posterior_weights:
        weights = posterior_weights
        if posterior_ts is not None:
            snapshot["last_updated"] = posterior_ts.to_pydatetime()
    elif runtime_weights or runtime_ts is not None:
        weights = runtime_weights
        if runtime_ts is not None:
            snapshot["last_updated"] = runtime_ts.to_pydatetime()

    snapshot["strategy_weights"] = weights
    snapshot["tribunal_entropy"] = _compute_weight_entropy(weights)
    return snapshot


def load_options_runtime_snapshot() -> tuple[dict[str, Any], dict[str, Any]]:
    portfolio_snapshot: dict[str, Any] = {}
    risk_snapshot: dict[str, Any] = {}

    runtime_path = PROJECT_ROOT / "data" / "options" / "live" / "options_runtime_state.json"
    dashboard_path = PROJECT_ROOT / "data" / "options" / "live" / "options_dashboard_state.json"

    runtime_payload: dict[str, Any] = {}
    dashboard_payload: dict[str, Any] = {}
    try:
        if runtime_path.exists():
            runtime_payload = json.loads(runtime_path.read_text(encoding="utf-8"))
    except Exception:
        runtime_payload = {}

    try:
        if dashboard_path.exists():
            dashboard_payload = json.loads(dashboard_path.read_text(encoding="utf-8"))
    except Exception:
        dashboard_payload = {}

    active_positions = dashboard_payload.get("active_positions") or runtime_payload.get("open_positions") or []
    positions = {
        str(position.get("position_id") or position.get("symbol") or position.get("underlying") or f"options_{idx}"): position
        for idx, position in enumerate(active_positions)
        if isinstance(position, dict)
    }

    def _aggregate_greek(name: str) -> float:
        total = 0.0
        for position in positions.values():
            quantity = float(position.get("quantity") or position.get("lots") or 1.0)
            greek_value = float(position.get(name) or 0.0)
            total += greek_value * quantity
        return float(total)

    risk_cap_value = float(runtime_payload.get("risk_cap_value") or 0.0)
    risk_remaining = float(runtime_payload.get("risk_remaining") or 0.0)
    margin_utilization = 0.0
    if risk_cap_value > 0.0:
        margin_utilization = max(0.0, min(1.0, 1.0 - (risk_remaining / risk_cap_value)))

    portfolio_snapshot.update(
        {
            "options_positions": positions,
            "options_position_count": int(len(positions)),
            "options_net_delta": _aggregate_greek("delta"),
            "options_net_gamma": _aggregate_greek("gamma"),
            "options_net_vega": _aggregate_greek("vega"),
            "options_net_theta": _aggregate_greek("theta"),
            "options_premium_at_risk": float(max(risk_cap_value - risk_remaining, 0.0)),
            "options_notional_deployed": float(runtime_payload.get("net_equity") or runtime_payload.get("base_capital") or 0.0),
            "options_unrealized_pnl": float(runtime_payload.get("unrealized_pnl") or 0.0),
            "options_system_mode": str(runtime_payload.get("current_mode") or "UNKNOWN").upper(),
        }
    )

    risk_snapshot.update(
        {
            "options_delta_exposure_inr": abs(portfolio_snapshot["options_net_delta"]),
            "options_vega_exposure_inr": abs(portfolio_snapshot["options_net_vega"]),
            "options_margin_utilization": float(margin_utilization),
            "options_max_loss_scenario": float(risk_cap_value),
            "options_trading_suspended": bool(runtime_payload.get("block_new_risk") or runtime_payload.get("last_kill_switch")),
        }
    )

    return portfolio_snapshot, risk_snapshot


def normalize_loaded_state(state: UnifiedState) -> None:
    """Repair persisted snapshot fields that older loaders left as strings."""
    governor_datetime_fields = ["last_morning_decision", "last_intraday_check"]
    for field_name in governor_datetime_fields:
        raw_value = getattr(state.governor_state, field_name, None)
        if isinstance(raw_value, str) and raw_value.strip():
            parsed = pd.to_datetime(raw_value, errors="coerce")
            if pd.notna(parsed):
                setattr(state.governor_state, field_name, pd.Timestamp(parsed).to_pydatetime())


def materialize_processed_risk_state(state: UnifiedState) -> str:
    """Refresh the legacy processed risk snapshot from canonical unified state."""
    risk_status = getattr(state.risk.status, "value", str(state.risk.status))
    now = pd.Timestamp.now().normalize()

    risk_df = pd.DataFrame(
        [
            {
                "date": now,
                "volatility": float(pd.to_numeric(getattr(state.market, "market_stress", 0.0), errors="coerce") or 0.0),
                "correlation": float(pd.to_numeric(getattr(state.market, "correlation", 0.0), errors="coerce") or 0.0),
                "var": float(pd.to_numeric(getattr(state.risk, "overall_risk_level", 0.0), errors="coerce") or 0.0),
                "risk_status": risk_status,
                "system_stress": float(pd.to_numeric(getattr(state.risk, "system_stress", 0.0), errors="coerce") or 0.0),
                "overall_risk_level": float(pd.to_numeric(getattr(state.risk, "overall_risk_level", 0.0), errors="coerce") or 0.0),
                "exposure_multiplier": float(pd.to_numeric(getattr(state.risk, "exposure_multiplier", 1.0), errors="coerce") or 1.0),
                "emergency_brake_active": bool(getattr(state.risk, "emergency_brake_active", False)),
                "options_margin_utilization": float(
                    pd.to_numeric(getattr(state.risk, "options_margin_utilization", 0.0), errors="coerce") or 0.0
                ),
            }
        ]
    )

    manager = StateFileManager()
    manager.write_risk_state(risk_df)
    return str(manager.RISK_STATE_PATH)


def sync_canonical_state(args: argparse.Namespace, run_dir: Path) -> dict[str, Any]:
    config = load_system_config()
    as_of = resolve_date(args.date).to_pydatetime()

    try:
        from src.nlp.pipeline.batch_scorer import BatchHistoricalScorer

        scorer = BatchHistoricalScorer(config)
        scorer.score_incremental(
            since_date=as_of.date(),
            company_output_path="data/canonical/sentiment/company_sentiment_daily.parquet",
            market_output_path="data/canonical/sentiment/market_sentiment_daily.parquet",
        )
        logger.info("Incremental NLP sentiment refresh complete for %s", as_of.date())
    except Exception as exc:
        logger.error("Incremental NLP sentiment refresh failed: %s", exc)

    state = UnifiedState()
    state_path = PROJECT_ROOT / "data" / "state" / "unified_state.json"
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as handle:
                state.load_snapshot(json.load(handle))
        except Exception:
            pass
    normalize_loaded_state(state)

    authority = StateAuthority(
        state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(state_path),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="complete_v3_runner",
        allowed_sections=[
            "market",
            "macro",
            "regime",
            "beliefs",
            "sentiment",
            "alternative_data",
            "intelligence_state",
            "health",
            "governor_state",
            "pnl_state",
            "alpha_os",
            "portfolio",
            "risk",
        ],
        priority=WritePriority.RESEARCH,
    )

    registry = IngestionRegistry(config)
    health_snapshot = registry.health_check(as_of)
    lineage_snapshot = registry.get_data_lineage_report(as_of)
    core_state_payload = load_core_state_payload()
    equity_portfolio_payload = load_equity_portfolio_snapshot()

    for section_name in ("market", "macro", "regime", "beliefs"):
        updates = [
            StateUpdate(
                writer_id="complete_v3_runner",
                section=section_name,
                field_path=field_path,
                new_value=value,
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="Complete V3 core state sync",
            )
            for field_path, value in core_state_payload.get(section_name, {}).items()
        ]
        if updates:
            applied = authority.batch_update(updates)
            if applied != len(updates):
                raise RuntimeError(f"{section_name}_state_sync_incomplete:{applied}/{len(updates)}")

    classifier = SentimentRegimeClassifier(config)
    sentiment_state = compute_sentiment_state(
        registry=registry,
        as_of_date=as_of,
        sentiment_regime_classifier=classifier,
        market_state=state.market,
    )

    alternative_runner = AlternativePipelineRunner(config)
    alternative_pipeline = alternative_runner.run(as_of, force=False)
    alternative_state = alternative_runner._last_processed_state or alternative_runner.compute_alternative_state(as_of)
    alpha_os_payload = load_alpha_os_snapshot()
    options_portfolio_payload, options_risk_payload = load_options_runtime_snapshot()

    pnl_payload = load_pnl_snapshot()
    pnl_updates = [
        StateUpdate(
            writer_id="complete_v3_runner",
            section="pnl_state",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Complete V3 P&L snapshot sync",
        )
        for field_path, value in pnl_payload.items()
    ]
    if pnl_updates:
        applied = authority.batch_update(pnl_updates)
        if applied != len(pnl_updates):
            raise RuntimeError(f"pnl_state_sync_incomplete:{applied}/{len(pnl_updates)}")

    alpha_os_updates = [
        StateUpdate(
            writer_id="complete_v3_runner",
            section="alpha_os",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Complete V3 Alpha OS snapshot sync",
        )
        for field_path, value in alpha_os_payload.items()
    ]
    if alpha_os_updates:
        applied = authority.batch_update(alpha_os_updates)
        if applied != len(alpha_os_updates):
            raise RuntimeError(f"alpha_os_state_sync_incomplete:{applied}/{len(alpha_os_updates)}")

    sentiment_updates = dataclass_leaf_updates(
        writer_id="complete_v3_runner",
        section="sentiment",
        obj=sentiment_state,
        priority=WritePriority.RESEARCH,
        source="SYSTEM",
        reason="Complete V3 sentiment state sync",
    )
    applied = authority.batch_update(sentiment_updates)
    if applied != len(sentiment_updates):
        raise RuntimeError(f"sentiment_state_sync_incomplete:{applied}/{len(sentiment_updates)}")

    alternative_updates = dataclass_leaf_updates(
        writer_id="complete_v3_runner",
        section="alternative_data",
        obj=alternative_state,
        priority=WritePriority.RESEARCH,
        source="SYSTEM",
        reason="Complete V3 alternative state sync",
    )
    applied = authority.batch_update(alternative_updates)
    if applied != len(alternative_updates):
        raise RuntimeError(f"alternative_state_sync_incomplete:{applied}/{len(alternative_updates)}")

    from src.intelligence.news_brain.news_brain import NewsBrain
    from src.intelligence.news_brain.news_signal_state import intelligence_state_to_dict

    runtime_sync = None
    runtime_db_path = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
    if runtime_db_path.exists():
        runtime_bridge = RuntimeStateBridge(
            db_path=str(runtime_db_path),
            state_authority=authority,
            json_path=str(PROJECT_ROOT / "data" / "portfolio" / "current_positions.json"),
        )
        runtime_sync = runtime_bridge.sync_to_unified_state()
        runtime_bridge.sync_to_json_checkpoint()

    news_brain = NewsBrain(config)
    intelligence_as_of = datetime.now()
    market_intelligence_state = news_brain.run_cycle(as_of_datetime=intelligence_as_of)
    intelligence_updates: list[StateUpdate] = []
    if market_intelligence_state and getattr(market_intelligence_state, "available", False):
        intelligence_payload = intelligence_state_to_dict(market_intelligence_state)
        intelligence_updates = [
            StateUpdate(
                writer_id="complete_v3_runner",
                section="intelligence_state",
                field_path=field_path,
                new_value=value,
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason=(
                    f"News brain sync shock={market_intelligence_state.primary_shock_type.value} "
                    f"severity={market_intelligence_state.shock_severity.name}"
                ),
            )
            for field_path, value in intelligence_payload.items()
        ]
        if intelligence_updates:
            applied = authority.batch_update(intelligence_updates)
            if applied != len(intelligence_updates):
                raise RuntimeError(f"intelligence_state_sync_incomplete:{applied}/{len(intelligence_updates)}")

        live_equity_rows = _build_live_equity_rows(
            authority.state.portfolio.positions or {},
            equity_portfolio_payload,
            float(getattr(authority.state.portfolio, "total_value", 0.0) or 0.0),
        )
        if market_intelligence_state.is_stale:
            logger.warning(
                "News brain state persisted but marked stale (freshness_minutes=%.1f); "
                "skipping urgent hedge and rebalance outputs",
                float(getattr(market_intelligence_state, "freshness_minutes", 0.0) or 0.0),
            )
        else:
            urgent_flag = _write_urgent_shock_flag(market_intelligence_state)
            if urgent_flag:
                logger.warning(
                    "Urgent shock flag written: %s severity=%s confidence=%.2f",
                    urgent_flag["shock_type"],
                    urgent_flag["severity"],
                    urgent_flag["shock_confidence"],
                )

            shock_instructions = _write_shock_rebalance_instructions(
                config,
                market_intelligence_state,
                live_equity_rows,
            )
            if shock_instructions:
                logger.warning(
                    "Shock rebalance instructions written: %s rebalance / %s options",
                    len(shock_instructions["rebalance_instructions"]),
                    len(shock_instructions["options_instructions"]),
                )

    shadow_sync = _maybe_refresh_shadow_reality(logger)
    shadow_path = PROJECT_ROOT / "data" / "shadow_reality" / "shadow_portfolio_state.parquet"
    if shadow_path.exists():
        shadow_bridge = ShadowStateBridge(str(shadow_path), authority)
        shadow_bridge.push_shadow_state()
        if shadow_sync is None:
            shadow_sync = {"shadow_state_path": str(shadow_path)}
        shadow_sync["last_sync"] = datetime.utcnow().isoformat()

    equity_portfolio_updates = [
        StateUpdate(
            writer_id="complete_v3_runner",
            section="portfolio",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Complete V3 equity portfolio sync",
        )
        for field_path, value in _portfolio_target_updates(equity_portfolio_payload).items()
    ]
    if equity_portfolio_updates:
        authority.batch_update(equity_portfolio_updates)

    options_portfolio_updates = [
        StateUpdate(
            writer_id="complete_v3_runner",
            section="portfolio",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Complete V3 options portfolio sync",
        )
        for field_path, value in options_portfolio_payload.items()
    ]
    if options_portfolio_updates:
        authority.batch_update(options_portfolio_updates)

    options_risk_updates = [
        StateUpdate(
            writer_id="complete_v3_runner",
            section="risk",
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Complete V3 options risk sync",
        )
        for field_path, value in options_risk_payload.items()
    ]
    if options_risk_updates:
        authority.batch_update(options_risk_updates)

    intelligence_active = bool(
        sentiment_state.is_fresh
        and alternative_state.any_source_fresh
        and market_intelligence_state.available
        and not market_intelligence_state.is_stale
    )
    portfolio_active = bool(
        equity_portfolio_payload.get("total_exposure", 0.0)
        or options_portfolio_payload.get("options_position_count", 0)
        or (runtime_sync and runtime_sync.success)
    )
    health_updates = health_snapshot_to_updates(
        writer_id="complete_v3_runner",
        snapshot=health_snapshot,
        intelligence_active=intelligence_active,
        portfolio_active=portfolio_active,
    )
    applied = authority.batch_update(health_updates)
    if applied != len(health_updates):
        raise RuntimeError(f"health_state_sync_incomplete:{applied}/{len(health_updates)}")

    # Canonical sync has just refreshed the in-memory state from authoritative sources.
    # Clear the stale marker inherited from the previously persisted snapshot so the
    # governor can recompute on the fresh canonical view.
    state._state_is_stale = False
    state._state_age_hours = 0.0

    governor = PortfolioGovernor(config=config)
    structure = governor.compute_capital_structure(state)
    if structure is None:
        raise RuntimeError("governor_compute_returned_none_after_canonical_refresh")
    governor_state = GovernorState()
    governor_state.update_from_structure(structure)
    governor_state.caution_score = float(getattr(governor, "last_caution_score", 0.0))

    governor_updates = dataclass_leaf_updates(
        writer_id="complete_v3_runner",
        section="governor_state",
        obj=governor_state,
        priority=WritePriority.RESEARCH,
        source="SYSTEM",
        reason="Complete V3 governor state sync",
    )
    applied = authority.batch_update(governor_updates)
    if applied != len(governor_updates):
        raise RuntimeError(f"governor_state_sync_incomplete:{applied}/{len(governor_updates)}")

    authority.checkpoint(force=True)
    processed_risk_state_path = materialize_processed_risk_state(state)

    snapshot_path = run_dir / "canonical_state_snapshot.json"
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(state.get_state_dict(), handle, indent=2, default=str)

    return {
        "sentiment_pipeline_status": "FRESH" if sentiment_state.is_fresh else "STALE",
        "sentiment_regime": getattr(sentiment_state.market_sentiment_regime, "value", str(sentiment_state.market_sentiment_regime)),
        "sentiment_is_fresh": bool(sentiment_state.is_fresh),
        "sentiment_companies_covered": int(sentiment_state.companies_with_coverage),
        "alternative_pipeline_status": alternative_pipeline.status,
        "alternative_regime": getattr(alternative_state.economic_activity_regime, "value", str(alternative_state.economic_activity_regime)),
        "alternative_all_sources_fresh": bool(alternative_state.all_sources_fresh),
        "news_brain_available": bool(market_intelligence_state.available),
        "news_brain_shock_type": market_intelligence_state.primary_shock_type.value,
        "news_brain_shock_severity": market_intelligence_state.shock_severity.name,
        "news_brain_requires_hedge": bool(market_intelligence_state.requires_immediate_hedge),
        "governor_regime": structure.capital_structure_regime.value,
        "equity_budget_inr": float(structure.equity_budget_inr),
        "options_budget_inr": float(structure.options_budget_inr),
        "cash_reserve_inr": float(structure.cash_reserve_inr),
        "alpha_os_active_strategy_count": int(alpha_os_payload.get("active_strategy_count", 0)),
        "alpha_os_weight_count": int(len(alpha_os_payload.get("strategy_weights", {}))),
        "market_regime": str(state.market.regime),
        "market_allowed_exposure": float(state.market.allowed_exposure),
        "macro_regime": str(getattr(state.macro, "policy_stance", "neutral")),
        "equity_total_exposure": float(equity_portfolio_payload.get("total_exposure", 0.0)),
        "options_position_count": int(options_portfolio_payload.get("options_position_count", 0)),
        "options_system_mode": str(options_portfolio_payload.get("options_system_mode", "UNKNOWN")),
        "state_path": str(state_path),
        "processed_risk_state_path": processed_risk_state_path,
        "snapshot_path": str(snapshot_path),
        "runtime_sync": asdict(runtime_sync) if runtime_sync is not None else None,
        "shadow_sync": shadow_sync,
        "health_snapshot": health_snapshot,
        "lineage_snapshot": lineage_snapshot,
    }


def run_function_stage(
    *,
    name: str,
    required: bool,
    func: Callable[[], dict[str, Any]],
    run_dir: Path,
) -> tuple[StageResult, dict[str, Any]]:
    started_at = datetime.now()
    log_path = run_dir / "logs" / f"{slugify(name)}.log"
    payload: dict[str, Any] = {}
    try:
        payload = func()
        with open(log_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        status = "PASS"
        summary = payload.get("governor_regime") or payload.get("sentiment_pipeline_status") or "completed"
        returncode = 0
    except Exception as exc:
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write(f"{type(exc).__name__}: {exc}\n\n")
            handle.write(traceback.format_exc())
        status = "FAIL"
        summary = str(exc)
        returncode = 1
    finished_at = datetime.now()
    result = StageResult(
        name=name,
        required=required,
        status=status,
        summary=summary,
        command=None,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_seconds=(finished_at - started_at).total_seconds(),
        returncode=returncode,
        log_path=str(log_path),
    )
    return result, payload


def run_command_stage(
    *,
    name: str,
    description: str,
    command: list[str],
    required: bool,
    run_dir: Path,
    dry_run: bool,
    timeout_seconds: Optional[int] = None,
) -> StageResult:
    started_at = datetime.now()
    log_path = run_dir / "logs" / f"{slugify(name)}.log"
    command_text = " ".join(command)

    print(f"\n=== {name} ===")
    print(description)
    print(command_text)

    if dry_run:
        finished_at = datetime.now()
        return StageResult(
            name=name,
            required=required,
            status="SKIPPED",
            summary="dry-run",
            command=command_text,
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            duration_seconds=(finished_at - started_at).total_seconds(),
            returncode=None,
            log_path=str(log_path),
        )

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write(f"$ {command_text}\n\n")
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                env={**os.environ, "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED", "1")},
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            rc = int(completed.returncode)
            status = "PASS" if rc == 0 else "FAIL"
        except subprocess.TimeoutExpired:
            handle.write("\n[runner] stage timed out\n")
            rc = 124
            status = "FAIL"

    finished_at = datetime.now()
    tail = tail_text(log_path)
    summary = "completed" if status == "PASS" else (tail.splitlines()[-1] if tail else "failed")

    print(f"[{name}] {status} ({(finished_at - started_at).total_seconds():.1f}s)")
    print(f"[{name}] log: {log_path}")

    return StageResult(
        name=name,
        required=required,
        status=status,
        summary=summary,
        command=command_text,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        duration_seconds=(finished_at - started_at).total_seconds(),
        returncode=rc,
        log_path=str(log_path),
    )


def proof_commands(proof_level: str) -> list[tuple[str, str, list[str]]]:
    commands = [
        ("Gap 1 Proof", "Validate unified ingestion layer", [sys.executable, "scripts/verify_gap1_fixes.py"]),
        ("Gap 2 Proof", "Validate sentiment integration", [sys.executable, "scripts/validate_gap2_complete.py"]),
        ("Gap 3 Proof", "Validate alternative data integration", [sys.executable, "scripts/validate_gap3_robust_complete.py"]),
        ("Gap 4 Proof", "Validate Alpha OS robustness", [sys.executable, "scripts/test_gap4_robust.py"]),
        ("Gap 5 Proof", "Validate unified P&L ledger", [sys.executable, "scripts/validate_gap5_complete.py"]),
        ("Gap 6 Proof", "Validate Portfolio Governor", [sys.executable, "scripts/validate_gap6_complete.py"]),
        ("Gap 7 Proof", "Validate state authority hard cutover", [sys.executable, "scripts/validate_gap7_complete.py"]),
    ]

    if proof_level == "full":
        commands.extend(
            [
                ("Gap 3 Integration", "Run alternative pipeline integration test", [sys.executable, "scripts/test_alternative_pipeline_runner.py"]),
                ("Gap 5 Integration", "Run Gap 5 end-to-end test", [sys.executable, "scripts/test_gap5_end_to_end.py"]),
                ("Gap 6 Integration", "Run Gap 6 integration test", [sys.executable, "scripts/test_gap6_integration.py"]),
                ("Gap 7 Integration", "Run Gap 7 integration test", [sys.executable, "scripts/test_gap7_integration.py"]),
            ]
        )

    return commands


def stage_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    # Operator-facing --quick should actually be quick. The previous behavior only
    # honored it behind a CI env flag, which caused post-close runs to fall into
    # heavyweight research/backtest stages unexpectedly.
    ci_gate_quick = bool(args.quick)

    if args.dashboard_only:
        return [
            {
                "type": "command",
                "name": "Dashboard",
                "description": "Launch dashboard only",
                "command": ["bash", "scripts/launch_dashboard.sh"],
                "required": True,
            }
        ]

    stages: list[dict[str, Any]] = [
        {
            "type": "command",
            "name": "Market Refresh",
            "description": "Refresh prices, indices, market state, and canonical market sections",
            "command": [sys.executable, "scripts/force_market_update.py"],
            "required": True,
            "timeout_seconds": 7200,
        }
    ]

    if ci_gate_quick and _ci_gate_mode():
        stages.append(
            {
                "type": "function",
                "name": "Market Data Freshness",
                "description": "Block downstream runtime validation when refreshed market data is stale",
                "required": True,
                "func": lambda: check_market_data_freshness(max_age_hours=4.0),
            }
        )
        return stages

    stages.append(
        {
            "type": "command",
            "name": "RBI Macro",
            "description": "Run RBI daily updater",
            "command": [sys.executable, "src/ingestion/rbi_daily_updater.py"],
            "required": True,
            "timeout_seconds": 5400,
        }
    )

    macro_cmd = [sys.executable, "scripts/collect_macro_daily.py"]
    if args.force_gst:
        macro_cmd.append("--force-gst")
    stages.append(
        {
            "type": "command",
            "name": "Macro Features",
            "description": "Refresh macro features from CEA/GST inputs",
            "command": macro_cmd,
            "required": True,
            "timeout_seconds": 5400,
        }
    )

    if not args.quick:
        alt_cmd = [
            sys.executable,
            "scripts/daily_alternative_data_pipeline.py",
            "--start-year",
            str(args.alt_start_year),
            "--end-year",
            str(args.alt_end_year),
        ]
        alt_cmd.append("--resume")
        if args.include_announcements:
            alt_cmd.append("--include-announcements")
        alt_cmd.extend(["--nse-period", "1D"])
        stages.append(
            {
                "type": "command",
                "name": "Alternative Data",
                "description": "Refresh NSE-first alternative datasets and sync canonical alternative state",
                "command": alt_cmd,
                "required": True,
                "timeout_seconds": 10800,
            }
        )

        screener_cmd = [
            sys.executable,
            "scripts/scrape_screener_financials.py",
            "--resume",
        ]
        if args.screener_max_tickers > 0:
            screener_cmd.extend(["--max-tickers", str(args.screener_max_tickers)])
        stages.append(
            {
                "type": "command",
                "name": "Screener Scrape",
                "description": "Refresh Screener fundamentals",
                "command": screener_cmd,
                "required": True,
                "timeout_seconds": 21600,
            }
        )

    stages.append(
        {
            "type": "command",
            "name": "Screener Processing",
            "description": "Normalize raw Screener artifacts into processed datasets",
            "command": [sys.executable, "scripts/load_screener_to_pipeline.py"],
            "required": True,
            "timeout_seconds": 1800,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Valuation Scores",
            "description": "Warm the Screener-backed valuation feature cache before research dataset assembly",
            "command": [sys.executable, "scripts/compute_valuation_scores.py", "--date", args.date],
            "required": True,
            "timeout_seconds": 3600,
        }
    )

    sentiment_cmd = [sys.executable, "scripts/run_daily_sentiment_pipeline.py", "--date", args.date]
    if not args.quick:
        sentiment_cmd.append("--include-news-builder")
        sentiment_cmd.extend(["--news-sources", args.news_sources])
        if args.news_max_tickers > 0:
            sentiment_cmd.extend(["--news-max-tickers", str(args.news_max_tickers)])
        if args.news_max_months > 0:
            sentiment_cmd.extend(["--news-max-months", str(args.news_max_months)])
    stages.append(
        {
            "type": "command",
            "name": "News And Sentiment",
            "description": "Refresh news inputs and export processed sentiment artifacts",
            "command": sentiment_cmd,
            "required": True,
            "timeout_seconds": 10800,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Canonical Datasets",
            "description": "Build canonical cross-source training datasets and manifests from refreshed artifacts",
            "command": [sys.executable, "scripts/build_canonical_training_datasets.py"],
            "required": True,
            "timeout_seconds": 5400,
        }
    )

    stages.append(
        {
            "type": "function",
            "name": "Market Data Freshness",
            "description": "Block downstream intelligence stages when processed price data is stale",
            "required": True,
            "func": lambda: check_market_data_freshness(max_age_hours=4.0),
        }
    )

    if ci_gate_quick:
        return stages

    if not ci_gate_quick:
        stages.append(
            {
                "type": "command",
                "name": "Research Surface",
                "description": "Run one operator-triggered research cycle to refresh research opportunity artifacts",
                "command": [sys.executable, "scripts/run_research_worker.py", "--once", "--manual-run"],
                "required": True,
                "timeout_seconds": 10800,
            }
        )

        stages.append(
            {
                "type": "command",
                "name": "Strategy Backtests",
                "description": "Rebuild point-in-time strategy backtests across live and research families",
                "command": [sys.executable, "src/backtesting/backtest_engine.py"],
                "required": True,
                "timeout_seconds": 10800,
            }
        )

        stages.append(
            {
                "type": "command",
                "name": "Strategy Beliefs",
                "description": "Refresh Bayesian strategy beliefs from the latest backtest evidence",
                "command": [sys.executable, "src/intelligence/strategy_beliefs.py"],
                "required": True,
                "timeout_seconds": 3600,
            }
        )

        stages.append(
            {
                "type": "command",
                "name": "Strategy Regret",
                "description": "Refresh regret and missed-opportunity diagnostics across active strategies",
                "command": [sys.executable, "src/intelligence/strategy_regret.py"],
                "required": True,
                "timeout_seconds": 3600,
            }
        )

        stages.append(
            {
                "type": "command",
                "name": "Strategy Tailwinds",
                "description": "Recompute strategy tailwinds from refreshed regimes and performance",
                "command": [sys.executable, "src/intelligence/simple_tailwind_engine.py"],
                "required": True,
                "timeout_seconds": 3600,
            }
        )

    stages.append(
        {
            "type": "command",
            "name": "Capital Allocator",
            "description": "Refresh canonical strategy capital allocations from the latest market and belief surfaces",
            "command": [sys.executable, "src/intelligence/capital_allocator.py"],
            "required": True,
            "timeout_seconds": 1800,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Live Scores",
            "description": "Persist canonical live score surface from the daily scorer and archive the date snapshot",
            "command": [sys.executable, "scripts/runners/generate_daily_scorer_scores.py", "--date", args.date, "--config", "config/research_policy.yaml"],
            "required": True,
            "timeout_seconds": 3600,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Opportunity Surface",
            "description": "Refresh the portfolio opportunity surface from current scores and valuation state",
            "command": [sys.executable, "src/processing/opportunity_surface.py"],
            "required": True,
            "timeout_seconds": 1800,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Portfolio Construction",
            "description": "Refresh canonical portfolio weights and analytics for downstream options/runtime systems",
            "command": [sys.executable, "src/portfolio/portfolio_governor.py"],
            "required": True,
            "timeout_seconds": 3600,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Current Positions Sync",
            "description": "Materialize the hedge-fund equity book into current_positions.json from canonical portfolio state",
            "command": [sys.executable, "scripts/runners/sync_current_positions.py"],
            "required": True,
            "timeout_seconds": 900,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Runtime Book Sync",
            "description": "Synchronize the live hedge-fund core book and options sleeve into the canonical PRS runtime ledger",
            "command": [sys.executable, "scripts/runners/sync_live_books_to_runtime.py"],
            "required": True,
            "timeout_seconds": 900,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Runtime Accounting",
            "description": "Refresh immutable ledgers, NAV, reconciliation, and runtime DB accounting controls",
            "command": [sys.executable, "scripts/runners/refresh_runtime_accounting.py"],
            "required": True,
            "timeout_seconds": 1800,
        }
    )

    stages.append(
        {
            "type": "command",
            "name": "Strategy Surface Sync",
            "description": "Rebuild canonical strategy catalog, tailwinds, intelligence state, and registry views",
            "command": [sys.executable, "scripts/sync_canonical_strategy_surfaces.py"],
            "required": True,
            "timeout_seconds": 1800,
        }
    )

    stages.append(
        {
            "type": "function",
            "name": "Canonical State Sync",
            "description": "Push refreshed sentiment, alternative, P&L, health, and governor state into UnifiedState",
            "required": True,
            "func": lambda: sync_canonical_state(args, CURRENT_RUN_DIR),
        }
    )

    if args.data_only:
        return stages

    stages.extend(
        [
            {
                "type": "command",
                "name": "Preopen Checks",
                "description": "Run pre-market readiness checks",
                "command": [sys.executable, "scripts/preopen_checks.py"],
                "required": not args.quick,
                "timeout_seconds": 1800,
            },
            {
                "type": "command",
                "name": "Morning Pipeline",
                "description": "Run the morning regime-aware scoring pipeline",
                "command": [sys.executable, "scripts/run_morning_pipeline.py", "--date", args.date],
                "required": True,
                "timeout_seconds": 3600,
            },
        ]
    )

    if args.proof_level != "none":
        for name, description, command in proof_commands(args.proof_level):
            stages.append(
                {
                    "type": "command",
                    "name": name,
                    "description": description,
                    "command": command,
                    "required": True,
                    "timeout_seconds": 3600,
                }
            )

    return stages


def build_markdown_report(
    *,
    args: argparse.Namespace,
    run_id: str,
    overall_status: str,
    stage_results: list[StageResult],
    state_summary: dict[str, Any],
) -> str:
    lines = [
        f"# Complete V3 System Run",
        "",
        f"- Run ID: `{run_id}`",
        f"- Date: `{args.date}`",
        f"- Mode: `{'dashboard-only' if args.dashboard_only else 'data-only' if args.data_only else 'full'}`",
        f"- Quick: `{args.quick}`",
        f"- Proof Level: `{args.proof_level}`",
        f"- Overall Status: `{overall_status}`",
        "",
        "## Stage Summary",
        "",
        "| Stage | Status | Required | Duration (s) | Summary |",
        "| --- | --- | --- | ---: | --- |",
    ]

    for result in stage_results:
        lines.append(
            f"| {result.name} | {result.status} | {result.required} | {result.duration_seconds:.1f} | {result.summary.replace('|', '/')} |"
        )

    if state_summary:
        health_snapshot = state_summary.get("health_snapshot", {})
        lines.extend(
            [
                "",
                "## Canonical State",
                "",
                f"- Sentiment regime: `{state_summary.get('sentiment_regime', 'NA')}`",
                f"- Sentiment fresh: `{state_summary.get('sentiment_is_fresh', False)}`",
                f"- Companies with sentiment coverage: `{state_summary.get('sentiment_companies_covered', 0)}`",
                f"- Alternative regime: `{state_summary.get('alternative_regime', 'NA')}`",
                f"- All alternative sources fresh: `{state_summary.get('alternative_all_sources_fresh', False)}`",
                f"- Governor regime: `{state_summary.get('governor_regime', 'NA')}`",
                f"- Equity budget: `₹{state_summary.get('equity_budget_inr', 0.0):,.0f}`",
                f"- Options budget: `₹{state_summary.get('options_budget_inr', 0.0):,.0f}`",
                f"- Cash reserve: `₹{state_summary.get('cash_reserve_inr', 0.0):,.0f}`",
                f"- Unified state path: `{state_summary.get('state_path', 'NA')}`",
                "",
                "## Data Health",
                "",
            ]
        )
        for source_name, snapshot in health_snapshot.items():
            status = snapshot.get("status", "unknown")
            fresh = snapshot.get("is_fresh", False)
            warning = snapshot.get("warning")
            detail = f"{status}, fresh={fresh}"
            if warning:
                detail += f", warning={warning}"
            lines.append(f"- {source_name}: `{detail}`")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete Northstar V3 daily system.")
    parser.add_argument("--date", type=str, default="today")
    parser.add_argument("--quick", action="store_true", help="Skip the heaviest raw scrapes and reuse existing processed surfaces.")
    parser.add_argument("--data-only", action="store_true", help="Refresh data and sync canonical state only.")
    parser.add_argument("--dashboard-only", action="store_true", help="Launch the dashboard and exit.")
    parser.add_argument(
        "--proof-level",
        choices=["none", "standard", "full"],
        default="standard",
        help="How much Gap 1-7 proof to run after refresh.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the execution plan without running stages.")
    parser.add_argument("--force-gst", action="store_true", help="Force GST refresh even before the 15th of the month.")
    parser.add_argument("--include-announcements", action="store_true", help="Deprecated no-op. NSE announcements now run in the standard alternative refresh.")
    parser.add_argument("--alt-start-year", type=int, default=2024)
    parser.add_argument("--alt-end-year", type=int, default=datetime.now().year)
    parser.add_argument("--screener-max-tickers", type=int, default=0)
    parser.add_argument("--news-sources", type=str, default="nse,rss")
    parser.add_argument("--news-max-tickers", type=int, default=0)
    parser.add_argument("--news-max-months", type=int, default=0)
    return parser.parse_args()


CURRENT_RUN_DIR: Path


def main() -> int:
    global CURRENT_RUN_DIR

    args = parse_args()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    CURRENT_RUN_DIR = PROJECT_ROOT / "data" / "operations" / "complete_v3_runs" / run_id
    (CURRENT_RUN_DIR / "logs").mkdir(parents=True, exist_ok=True)

    print("=" * 88)
    print("NORTHSTAR V3 COMPLETE SYSTEM")
    print("=" * 88)
    print(f"Run ID: {run_id}")
    print(f"Date: {args.date}")
    print(f"Quick Mode: {args.quick}")
    print(f"Proof Level: {args.proof_level}")
    print(f"Artifacts: {CURRENT_RUN_DIR}")

    stages = stage_plan(args)
    if args.dry_run:
        print("\nPlanned stages:")
        for stage in stages:
            print(f"- {stage['name']}: {stage['description']}")
        return 0

    stage_results: list[StageResult] = []
    state_summary: dict[str, Any] = {}

    for stage in stages:
        if stage["type"] == "command":
            result = run_command_stage(
                name=stage["name"],
                description=stage["description"],
                command=stage["command"],
                required=bool(stage["required"]),
                run_dir=CURRENT_RUN_DIR,
                dry_run=args.dry_run,
                timeout_seconds=stage.get("timeout_seconds"),
            )
            stage_results.append(result)
            if result.status == "FAIL" and result.required:
                print(f"[runner] required stage failed: {result.name}")
        else:
            result, payload = run_function_stage(
                name=stage["name"],
                required=bool(stage["required"]),
                func=stage["func"],
                run_dir=CURRENT_RUN_DIR,
            )
            stage_results.append(result)
            if stage["name"] == "Canonical State Sync":
                state_summary = payload
            print(f"[{stage['name']}] {result.status} ({result.duration_seconds:.1f}s)")
            print(f"[{stage['name']}] log: {result.log_path}")

    failed_required = [result for result in stage_results if result.required and result.status == "FAIL"]
    failed_optional = [result for result in stage_results if not result.required and result.status == "FAIL"]
    overall_status = "PASS" if not failed_required else "FAIL"

    report = {
        "run_id": run_id,
        "started_at": stage_results[0].started_at if stage_results else datetime.now().isoformat(),
        "finished_at": datetime.now().isoformat(),
        "overall_status": overall_status,
        "arguments": vars(args),
        "failed_required_stage_count": len(failed_required),
        "failed_optional_stage_count": len(failed_optional),
        "stage_results": [asdict(result) for result in stage_results],
        "canonical_state": state_summary,
    }

    report_json = CURRENT_RUN_DIR / "run_report.json"
    report_md = CURRENT_RUN_DIR / "run_report.md"
    with open(report_json, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    report_md.write_text(
        build_markdown_report(
            args=args,
            run_id=run_id,
            overall_status=overall_status,
            stage_results=stage_results,
            state_summary=state_summary,
        ),
        encoding="utf-8",
    )

    latest_pointer = PROJECT_ROOT / "data" / "operations" / "complete_v3_runs" / "latest_run.json"
    with open(latest_pointer, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "run_id": run_id,
                "overall_status": overall_status,
                "report_json": str(report_json),
                "report_md": str(report_md),
            },
            handle,
            indent=2,
        )

    print("\n" + "=" * 88)
    print(f"OVERALL STATUS: {overall_status}")
    print(f"JSON report: {report_json}")
    print(f"Markdown report: {report_md}")
    if failed_required:
        print("Failed required stages:")
        for result in failed_required:
            print(f"- {result.name}: {result.summary}")
    print("=" * 88)

    return 0 if overall_status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
