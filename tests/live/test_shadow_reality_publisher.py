from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority
from src.core.state_bridges.shadow_bridge import ShadowStateBridge
from src.live.shadow_reality_publisher import refresh_shadow_reality_from_live_artifacts


def _write_shadow_json_artifacts(base_dir: Path, date_str: str) -> None:
    positions_dir = base_dir / "positions"
    pnl_dir = base_dir / "pnl"
    decisions_dir = base_dir / "decisions"
    positions_dir.mkdir(parents=True, exist_ok=True)
    pnl_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    targets_dir = base_dir / "targets"
    targets_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()
    positions_payload = {
        "date": date_str,
        "timestamp": timestamp,
        "positions": {
            "ABB.NS": {"quantity": 10.0, "price": 100.0, "weight": 0.5},
            "ASHOKLEY.NS": {"quantity": 20.0, "price": 50.0, "weight": 0.5},
        },
    }
    pnl_payload = {
        "date": date_str,
        "timestamp": timestamp,
        "daily_return": 0.01,
        "daily_pnl": 20.0,
        "cumulative_pnl": 120.0,
        "total_position_value": 2000.0,
        "cash": 500.0,
        "portfolio_value": 2500.0,
        "weights_date": date_str,
        "price_date": date_str,
        "prev_price_date": date_str,
        "prs_mode": True,
        "shadow_execution_mode": "exact_target",
        "tracking_summary": {
            "execution_mode": "exact_target",
            "status": "pass",
            "breach": False,
            "target_position_overlap": 1.0,
            "total_weight_drift": 0.0,
            "max_symbol_weight_drift": 0.0,
            "extra_positions_count": 0,
            "missing_target_positions_count": 0,
            "quantity_mismatch_count": 0,
            "exact_target_match": True,
            "reasons": [],
            "unresolved_symbols": [],
        },
    }
    decisions_payload = {
        "date": date_str,
        "timestamp": timestamp,
        "decisions": [
            {
                "timestamp": timestamp,
                "type": "real_data_rebalance",
                "prs_proposals_executed": 2,
            }
        ],
    }
    targets_payload = {
        "date": date_str,
        "timestamp": timestamp,
        "weights_date": date_str,
        "target_positions": {
            "ABB.NS": {"weight": 0.5, "quantity": 10.0, "price": 100.0, "notional": 1000.0},
            "ASHOKLEY.NS": {"weight": 0.5, "quantity": 20.0, "price": 50.0, "notional": 1000.0},
        },
    }

    (positions_dir / f"positions_{date_str}.json").write_text(json.dumps(positions_payload), encoding="utf-8")
    (pnl_dir / f"pnl_{date_str}.json").write_text(json.dumps(pnl_payload), encoding="utf-8")
    (decisions_dir / f"decisions_{date_str}.json").write_text(json.dumps(decisions_payload), encoding="utf-8")
    (targets_dir / f"targets_{date_str}.json").write_text(json.dumps(targets_payload), encoding="utf-8")


def test_refresh_shadow_reality_materializes_canonical_files(tmp_path: Path) -> None:
    live_dir = tmp_path / "live_shadow"
    reality_dir = tmp_path / "shadow_reality"
    shadow_positions_path = tmp_path / "execution" / "shadow_positions.parquet"
    shadow_state_current_path = tmp_path / "processed" / "shadow_state_current.json"
    date_str = "2026-03-20"
    _write_shadow_json_artifacts(live_dir, date_str)

    result = refresh_shadow_reality_from_live_artifacts(
        live_data_directory=str(live_dir),
        reality_directory=str(reality_dir),
        shadow_positions_path=str(shadow_positions_path),
        shadow_state_current_path=str(shadow_state_current_path),
    )

    assert result.success is True
    assert result.latest_date == date_str
    assert date_str in result.refreshed_dates

    state_df = pd.read_parquet(reality_dir / "shadow_portfolio_state.parquet")
    assert not state_df.empty
    latest = state_df.iloc[-1]
    assert str(latest["date"])[:10] == date_str
    assert float(latest["shadow_nav"]) == 2500.0
    assert float(latest["total_exposure"]) == 0.8
    assert str(latest["execution_mode"]) == "exact_target"
    assert bool(latest["exact_target_match"]) is True
    assert float(latest["target_total_weight_drift"]) == 0.0

    positions_df = pd.read_parquet(shadow_positions_path)
    assert len(positions_df) == 2
    assert set(positions_df["ticker"].tolist()) == {"ABB.NS", "ASHOKLEY.NS"}

    shadow_state_current = json.loads(shadow_state_current_path.read_text(encoding="utf-8"))
    assert shadow_state_current["date"] == date_str
    assert shadow_state_current["positions"]["ABB.NS"]["quantity"] == 10.0
    assert shadow_state_current["execution_mode"] == "exact_target"
    assert shadow_state_current["exact_target_match"] is True


def test_shadow_bridge_uses_fresh_published_shadow_snapshot(tmp_path: Path) -> None:
    live_dir = tmp_path / "live_shadow"
    reality_dir = tmp_path / "shadow_reality"
    shadow_positions_path = tmp_path / "execution" / "shadow_positions.parquet"
    shadow_state_current_path = tmp_path / "processed" / "shadow_state_current.json"
    date_str = "2026-03-20"
    _write_shadow_json_artifacts(live_dir, date_str)

    refresh_shadow_reality_from_live_artifacts(
        live_data_directory=str(live_dir),
        reality_directory=str(reality_dir),
        shadow_positions_path=str(shadow_positions_path),
        shadow_state_current_path=str(shadow_state_current_path),
    )

    state = UnifiedState()
    state.portfolio.positions = {
        "ABB.NS": {"quantity": 10.0, "market_value": 1000.0},
        "ASHOKLEY.NS": {"quantity": 20.0, "market_value": 1000.0},
    }
    state.portfolio.total_value = 2500.0
    authority = StateAuthority(state, config={"dev_mode": True, "checkpoint_path": str(tmp_path / "state.json")})

    bridge = ShadowStateBridge(
        str(reality_dir / "shadow_portfolio_state.parquet"),
        authority,
        config={
            "max_shadow_age_days": 7,
            "shadow_positions_path": str(shadow_positions_path),
        },
    )
    bridge.push_shadow_state()

    assert authority.state.shadow_state.shadow_data_stale is False
    assert authority.state.shadow_state.comparison_available is True
    assert authority.state.shadow_state.comparison_mode == "positions"
    assert authority.state.shadow_state.live_shadow_position_overlap == 1.0


def test_refresh_shadow_reality_is_stable_when_source_json_has_no_timestamp(tmp_path: Path) -> None:
    live_dir = tmp_path / "live_shadow"
    reality_dir = tmp_path / "shadow_reality"
    shadow_positions_path = tmp_path / "execution" / "shadow_positions.parquet"
    shadow_state_current_path = tmp_path / "processed" / "shadow_state_current.json"
    date_str = "2026-01-18"
    _write_shadow_json_artifacts(live_dir, date_str)

    for artifact in [
        live_dir / "positions" / f"positions_{date_str}.json",
        live_dir / "pnl" / f"pnl_{date_str}.json",
        live_dir / "decisions" / f"decisions_{date_str}.json",
    ]:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        payload.pop("timestamp", None)
        artifact.write_text(json.dumps(payload), encoding="utf-8")

    first = refresh_shadow_reality_from_live_artifacts(
        live_data_directory=str(live_dir),
        reality_directory=str(reality_dir),
        shadow_positions_path=str(shadow_positions_path),
        shadow_state_current_path=str(shadow_state_current_path),
    )
    second = refresh_shadow_reality_from_live_artifacts(
        live_data_directory=str(live_dir),
        reality_directory=str(reality_dir),
        shadow_positions_path=str(shadow_positions_path),
        shadow_state_current_path=str(shadow_state_current_path),
    )

    assert first.success is True
    assert second.success is True
    assert second.refreshed_dates == []
