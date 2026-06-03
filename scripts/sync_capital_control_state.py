#!/usr/bin/env python3
"""Sync PnL + governor control state into canonical unified state."""

from __future__ import annotations

import json
import sys
from dataclasses import fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
from src.intelligence.no_edge_detector import NoEdgeDetector
from src.pnl.pnl_state import PnLState
from src.portfolio.governor import PortfolioGovernor
from src.portfolio.governor_state import GovernorState


STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"
CURRENT_POSITIONS_PATH = PROJECT_ROOT / "data" / "portfolio" / "current_positions.json"
NAV_HISTORY_PATH = PROJECT_ROOT / "data" / "pnl" / "nav_history.parquet"
V3_PNL_PATH = PROJECT_ROOT / "data" / "processed" / "v3_centralized_pnl.json"


def _load_state() -> UnifiedState:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    if state.market.regime == "unknown":
        state.load_from_legacy_sources()
    return state


def _load_governor_config() -> dict[str, Any]:
    config = {"starting_capital_inr": 10_000_000, "portfolio_governor": {}}
    config_path = PROJECT_ROOT / "config" / "portfolio_governor_config.yaml"
    if config_path.exists():
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict):
            config["portfolio_governor"] = payload
            config["starting_capital_inr"] = payload.get("starting_capital_inr", config["starting_capital_inr"])
    return config


def _load_current_positions_payload() -> dict[str, Any]:
    if not CURRENT_POSITIONS_PATH.exists():
        return {}
    try:
        payload = json.loads(CURRENT_POSITIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_nav_row() -> dict[str, Any]:
    if not NAV_HISTORY_PATH.exists():
        return {}
    try:
        df = pd.read_parquet(NAV_HISTORY_PATH)
    except Exception:
        return {}
    if df.empty:
        return {}
    return dict(df.iloc[-1].to_dict())


def _load_pnl_state(current_positions: dict[str, Any]) -> PnLState:
    pnl_state = PnLState()

    nav_row = _latest_nav_row()
    nav_combined = pd.to_numeric(nav_row.get("nav_combined"), errors="coerce")
    nav_per_unit = pd.to_numeric(nav_row.get("nav_per_unit"), errors="coerce")
    drawdown = pd.to_numeric(nav_row.get("drawdown"), errors="coerce")
    max_drawdown = pd.to_numeric(nav_row.get("max_drawdown_to_date"), errors="coerce")
    costs_cum = pd.to_numeric(nav_row.get("transaction_costs_cumulative"), errors="coerce")

    current_total_value = pd.to_numeric(current_positions.get("total_value"), errors="coerce")
    pnl_state.current_nav_inr = float(
        current_total_value
        if pd.notna(current_total_value) and current_total_value > 0
        else (nav_combined if pd.notna(nav_combined) else 0.0)
    )
    pnl_state.current_nav_per_unit = float(nav_per_unit if pd.notna(nav_per_unit) else 0.0)
    pnl_state.current_drawdown_pct = float(drawdown * 100.0) if pd.notna(drawdown) else 0.0
    pnl_state.max_drawdown_to_date_pct = float(max_drawdown * 100.0) if pd.notna(max_drawdown) else 0.0
    if pd.notna(costs_cum) and pnl_state.current_nav_inr > 0:
        pnl_state.total_cost_drag_pct = float(costs_cum / pnl_state.current_nav_inr)

    if V3_PNL_PATH.exists():
        try:
            pnl_payload = json.loads(V3_PNL_PATH.read_text(encoding="utf-8"))
            aggregates = pnl_payload.get("aggregates", {}) if isinstance(pnl_payload, dict) else {}
            components = pnl_payload.get("components", {}) if isinstance(pnl_payload, dict) else {}
            options_live = components.get("options_live", {}) if isinstance(components, dict) else {}
            pnl_state.pnl_today_options_inr = float(options_live.get("realized_pnl_closed_positions", 0.0) or 0.0)
            pnl_state.pnl_ytd_inr = float(aggregates.get("combined_net_pnl_estimate", 0.0) or 0.0)
            pnl_state.net_pnl_today_inr = pnl_state.pnl_today_options_inr
        except Exception:
            pass

    pnl_state.fund_health = "WARNING" if pnl_state.current_drawdown_pct <= -8.0 else "ON_TRACK"
    pnl_state.last_reconciliation_status = "CLEAN"
    pnl_state.last_updated = datetime.utcnow()
    pnl_state.last_eod_processing = datetime.utcnow()
    return pnl_state


def _dataclass_leaf_updates(
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


def main() -> int:
    state = _load_state()
    current_positions = _load_current_positions_payload()
    pnl_state = _load_pnl_state(current_positions)
    state.pnl_state = pnl_state

    governor = PortfolioGovernor(config=_load_governor_config())
    structure = governor.compute_capital_structure(state)
    governor_state = GovernorState()
    governor_state.update_from_structure(structure)
    governor_state.caution_score = float(getattr(governor, "last_caution_score", 0.0))

    no_edge_state = NoEdgeDetector().get_current_state()
    effective_cap = min(
        float(no_edge_state.get("exposure_cap", 0.8) or 0.8),
        float(governor_state.equity_fraction or 0.0) or 1.0,
    )

    total_value = float(current_positions.get("total_value", 0.0) or 0.0)
    invested_value = float(current_positions.get("invested_value", 0.0) or 0.0)
    cash_value = float(current_positions.get("cash", 0.0) or 0.0)
    actual_allocated = (invested_value / total_value) if total_value > 0 else 0.0
    allocation_efficiency = (actual_allocated / effective_cap) if effective_cap > 1e-12 else 0.0

    authority = StateAuthority(
        state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="capital_control_sync",
        allowed_sections=["pnl_state", "governor_state", "capital"],
        priority=WritePriority.RESEARCH,
    )

    updates: list[StateUpdate] = []
    updates.extend(
        _dataclass_leaf_updates(
            writer_id="capital_control_sync",
            section="pnl_state",
            obj=pnl_state,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Canonical PnL state sync",
        )
    )
    updates.extend(
        _dataclass_leaf_updates(
            writer_id="capital_control_sync",
            section="governor_state",
            obj=governor_state,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Canonical governor state sync",
        )
    )
    updates.extend(
        [
            StateUpdate(
                writer_id="capital_control_sync",
                section="capital",
                field_path="total_capital",
                new_value=float(total_value),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="Capital control sync",
            ),
            StateUpdate(
                writer_id="capital_control_sync",
                section="capital",
                field_path="allocated_capital",
                new_value=float(actual_allocated),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="Capital control sync",
            ),
            StateUpdate(
                writer_id="capital_control_sync",
                section="capital",
                field_path="cash_buffer",
                new_value=float((cash_value / total_value) if total_value > 0 else 0.0),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="Capital control sync",
            ),
            StateUpdate(
                writer_id="capital_control_sync",
                section="capital",
                field_path="allocation_efficiency",
                new_value=float(max(0.0, allocation_efficiency)),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="Capital control sync",
            ),
            StateUpdate(
                writer_id="capital_control_sync",
                section="capital",
                field_path="last_rebalance",
                new_value=(
                    None
                    if not (current_positions.get("updated_at") or current_positions.get("timestamp"))
                    else (
                        lambda parsed: None if pd.isna(parsed) else parsed.to_pydatetime()
                    )(
                        pd.to_datetime(
                            current_positions.get("updated_at") or current_positions.get("timestamp"),
                            errors="coerce",
                        )
                    )
                ),
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason="Capital control sync",
            ),
        ]
    )

    applied = authority.batch_update(updates)
    if applied != len(updates):
        raise RuntimeError(f"capital_control_sync_incomplete:{applied}/{len(updates)}")
    authority.checkpoint(force=True)

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "current_nav_inr": float(pnl_state.current_nav_inr),
        "current_drawdown_pct": float(pnl_state.current_drawdown_pct),
        "governor_regime": governor_state.capital_structure_regime,
        "governor_equity_fraction": float(governor_state.equity_fraction),
        "no_edge_state": dict(no_edge_state),
        "effective_equity_cap": float(effective_cap),
        "actual_allocated_capital": float(actual_allocated),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
