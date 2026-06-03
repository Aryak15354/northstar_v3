#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

SCHEMA_VERSION = "2.1.0"
REQUIRED_DASHBOARD_FIELDS = ("timestamp", "schema_version", "net_equity", "risk_remaining")


def _as_dict(payload: Any) -> Dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _as_list(payload: Any) -> list[Any]:
    return payload if isinstance(payload, list) else []


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in [None, "", "None", "nan", "NaN"]:
            return default
        return float(value)
    except Exception:
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in [None, ""]:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_iso(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value
    try:
        if hasattr(value, "isoformat"):
            return value.isoformat()
    except Exception:
        pass
    return datetime.now().isoformat()


def _iter_iv_history(runtime_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    iv_history = _as_dict(runtime_payload.get("iv_history"))
    rows: list[dict[str, Any]] = []
    for underlying, points in iv_history.items():
        if not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, dict):
                continue
            rows.append(
                {
                    "timestamp": _to_iso(point.get("timestamp")),
                    "underlying": str(underlying),
                    "iv": _to_float(point.get("iv")),
                }
            )
    return rows


def _extract_position_greeks(position: Mapping[str, Any]) -> Dict[str, float]:
    nested = _as_dict(position.get("greeks"))
    return {
        "delta": _to_float(position.get("delta", nested.get("delta"))),
        "gamma": _to_float(position.get("gamma", nested.get("gamma"))),
        "theta": _to_float(position.get("theta", nested.get("theta"))),
        "vega": _to_float(position.get("vega", nested.get("vega"))),
    }


def _normalize_positions(positions: Iterable[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(positions):
        if not isinstance(raw, dict):
            continue
        greeks = _extract_position_greeks(raw)
        quantity = _to_float(raw.get("quantity", raw.get("lots", 1.0)), default=1.0)
        normalized.append(
            {
                "position_id": str(raw.get("position_id") or raw.get("trade_id") or raw.get("symbol") or raw.get("underlying") or f"position_{idx}"),
                "underlying": str(raw.get("underlying") or raw.get("symbol") or ""),
                "strategy_type": raw.get("strategy_type"),
                "quantity": quantity,
                "lots": quantity,
                "strike": raw.get("strike"),
                "expiry": raw.get("expiry"),
                "source": raw.get("source"),
                "entry_time": raw.get("entry_time"),
                "current_value": _to_float(raw.get("current_value")),
                "unrealized_pnl": _to_float(raw.get("unrealized_pnl")),
                **greeks,
                "greeks": greeks,
            }
        )
    return normalized


def _aggregate_greeks(positions: Iterable[dict[str, Any]], existing: Mapping[str, Any]) -> Dict[str, float]:
    clean_existing = {}
    for key, value in _as_dict(existing).items():
        normalized_key = str(key).strip().lower()
        if normalized_key in {"delta", "gamma", "theta", "vega", "exposure"}:
            clean_existing[normalized_key] = _to_float(value)

    if clean_existing:
        for greek in ("delta", "gamma", "theta", "vega", "exposure"):
            clean_existing.setdefault(greek, 0.0)
        return clean_existing

    totals = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    exposure = 0.0
    for position in positions:
        quantity = _to_float(position.get("quantity", 1.0), default=1.0)
        for greek in totals:
            totals[greek] += _to_float(position.get(greek)) * quantity
        exposure += abs(_to_float(position.get("current_value")))
    totals["exposure"] = exposure
    return totals


def normalize_dashboard_state(
    dashboard_state: Mapping[str, Any] | None,
    runtime_state: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    dashboard = dict(_as_dict(dashboard_state))
    runtime = dict(_as_dict(runtime_state))

    positions = _normalize_positions(
        dashboard.get("active_positions")
        or runtime.get("active_positions")
        or runtime.get("open_positions")
        or []
    )
    portfolio_greeks = _aggregate_greeks(positions, _as_dict(dashboard.get("portfolio_greeks")))

    risk_cap_value = _to_float(runtime.get("risk_cap_value"))
    risk_remaining = _to_float(runtime.get("risk_remaining"))
    risk_used = max(0.0, risk_cap_value - risk_remaining)
    net_equity = _to_float(runtime.get("net_equity"), default=_to_float(dashboard.get("net_equity")))
    base_capital = _to_float(runtime.get("base_capital"))
    portfolio_risk_cap_pct = _to_float(runtime.get("portfolio_risk_cap_pct"))

    normalized = dict(dashboard)
    normalized.update(
        {
            "timestamp": _to_iso(dashboard.get("timestamp") or runtime.get("timestamp")),
            "schema_version": str(dashboard.get("schema_version") or runtime.get("schema_version") or SCHEMA_VERSION),
            "continuity_mode": _to_bool(runtime.get("continuity_mode"), default=True),
            "recovery_mode": _to_bool(runtime.get("recovery_mode"), default=False),
            "base_capital": base_capital,
            "net_equity": net_equity,
            "risk_cap_value": risk_cap_value,
            "risk_remaining": risk_remaining,
            "realized_net_pnl": _to_float(runtime.get("realized_net_pnl")),
            "unrealized_pnl": _to_float(runtime.get("unrealized_pnl")),
            "active_positions": positions,
            "portfolio_greeks": portfolio_greeks,
            "portfolio_risk_usage": _as_dict(runtime.get("portfolio_risk_usage"))
            or {
                "total_risk": risk_used,
                "risk_cap": risk_cap_value,
                "risk_pct": (risk_used / net_equity) if net_equity > 0 else 0.0,
                "risk_cap_pct": portfolio_risk_cap_pct,
            },
            "weekly_risk_usage": _as_dict(runtime.get("weekly_risk_usage"))
            or {
                "risk_used": risk_used,
                "risk_limit": risk_cap_value,
            },
            "trade_eligibility": _as_dict(dashboard.get("trade_eligibility"))
            or _as_dict(runtime.get("trade_eligibility"))
            or _as_dict(runtime.get("last_trade_eligibility")),
            "kill_switch_status": _as_dict(dashboard.get("kill_switch_status"))
            or _as_dict(runtime.get("last_kill_switch")),
            "iv_surface": _as_list(dashboard.get("iv_surface")) or _iter_iv_history(runtime),
            "greeks_history": _as_list(dashboard.get("greeks_history")) or _as_list(runtime.get("greeks_history")),
            "market_snapshot": _as_dict(dashboard.get("market_snapshot")) or _as_dict(dashboard.get("market_state")) or _as_dict(runtime.get("market_snapshot")),
            "market_state": _as_dict(dashboard.get("market_state")) or _as_dict(runtime.get("market_snapshot")),
            "data_sources": _as_dict(dashboard.get("data_sources")),
            "data_quality": dashboard.get("data_quality") or "REAL_DATA_ONLY",
            "current_regime": dashboard.get("current_regime")
            or (_as_list(runtime.get("regime_history"))[-1].get("routed_regime") if _as_list(runtime.get("regime_history")) else None)
            or dashboard.get("system_status")
            or runtime.get("current_mode"),
            "last_reconciled_at": runtime.get("last_reconciled_at"),
        }
    )
    return normalized


def load_json_file(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def missing_dashboard_fields(payload: Mapping[str, Any] | None) -> list[str]:
    state = _as_dict(payload)
    return [field for field in REQUIRED_DASHBOARD_FIELDS if field not in state]
