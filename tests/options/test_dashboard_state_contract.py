from __future__ import annotations

import json

from src.options.dashboard_state_contract import missing_dashboard_fields, normalize_dashboard_state
from src.options.state_io import StateIOManager


def test_normalize_dashboard_state_repairs_legacy_payload() -> None:
    runtime = {
        "timestamp": "2026-03-14T16:45:59.160377+05:30",
        "schema_version": "2.1.0",
        "continuity_mode": True,
        "recovery_mode": False,
        "base_capital": 500000.0,
        "net_equity": 513517.58,
        "risk_cap_value": 51351.75,
        "risk_remaining": 40000.0,
        "portfolio_risk_cap_pct": 0.10,
        "last_trade_eligibility": {"signal_generated": True, "rejected": False},
        "last_kill_switch": {"active": False, "reason": ""},
        "open_positions": [],
        "iv_history": {"NIFTY": [{"timestamp": "2026-03-14T16:30:51.348611+05:30", "iv": 0.25}]},
    }
    legacy_dashboard = {
        "timestamp": "2026-03-14T17:21:15.941120",
        "active_positions": [
            {
                "position_id": "REAL_WIPRO_0",
                "underlying": "WIPRO",
                "strike": 155.0,
                "iv": 0.54,
                "delta": -0.0187,
                "gamma": 0.002,
                "vega": 0.0194,
                "theta": -0.0312,
            }
        ],
        "portfolio_greeks": {" exposure          ": 0.6},
        "data_sources": {"option_chains": True},
    }

    normalized = normalize_dashboard_state(legacy_dashboard, runtime)

    assert normalized["schema_version"] == "2.1.0"
    assert normalized["net_equity"] == runtime["net_equity"]
    assert normalized["risk_remaining"] == runtime["risk_remaining"]
    assert normalized["trade_eligibility"]["signal_generated"] is True
    assert normalized["portfolio_greeks"]["exposure"] == 0.6
    assert normalized["active_positions"][0]["greeks"]["delta"] == legacy_dashboard["active_positions"][0]["delta"]
    assert missing_dashboard_fields(normalized) == []


def test_state_io_manager_writes_canonical_dashboard_state(tmp_path) -> None:
    live_dir = tmp_path / "live"
    live_dir.mkdir(parents=True)
    runtime = {
        "timestamp": "2026-03-14T16:45:59.160377+05:30",
        "schema_version": "2.1.0",
        "continuity_mode": True,
        "recovery_mode": False,
        "base_capital": 500000.0,
        "net_equity": 513517.58,
        "risk_cap_value": 51351.75,
        "risk_remaining": 40000.0,
        "open_positions": [{"symbol": "NIFTY", "delta": 0.25, "quantity": 2}],
        "last_trade_eligibility": {"signal_generated": True},
    }
    (live_dir / "options_runtime_state.json").write_text(json.dumps(runtime), encoding="utf-8")

    legacy_dashboard = {
        "timestamp": "2026-03-14T17:21:15.941120",
        "portfolio_greeks": {" exposure          ": 0.6},
    }

    manager = StateIOManager(live_dir)
    assert manager.write_dashboard_state(legacy_dashboard) is True

    written = json.loads((live_dir / "options_dashboard_state.json").read_text(encoding="utf-8"))
    assert written["schema_version"] == "2.1.0"
    assert written["net_equity"] == runtime["net_equity"]
    assert written["risk_remaining"] == runtime["risk_remaining"]
    assert written["trade_eligibility"]["signal_generated"] is True
    assert missing_dashboard_fields(written) == []
