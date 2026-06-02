from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace

from src.integration.alpha_os_adapter import AlphaOSAdapter
from src.volatility.alpha_os_types import AlphaOSContext


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        enabled=True,
        shadow_mode=True,
        enforce_mode=False,
        write_legacy_artifacts=True,
        canonical_state_max_age_seconds=600,
        hmm_model_path="data/models/regime_hmm_latest.pkl",
        hmm_retrain_interval_days=30,
        hmm_min_samples=260,
        hmm_transition_smoothing=0.02,
        meta_regret_half_life_days=20,
        meta_hysteresis_relative_change=0.10,
        meta_max_weight_shift_per_cycle=0.15,
        meta_min_gross_exposure_floor=0.25,
    )


def _write_canonical_artifacts(project_root) -> None:
    cap = project_root / "data/processed/capital_allocations.json"
    reg = project_root / "data/processed/regime_intelligence_feed.json"
    cap.parent.mkdir(parents=True, exist_ok=True)
    cap.write_text(json.dumps({"strategy_allocations": {"legacy_core": 0.5}, "timestamp": _now_iso()}))
    reg.write_text(json.dumps({"regime": "neutral", "timestamp": _now_iso()}))


def _context(project_root, canonical_state) -> AlphaOSContext:
    return AlphaOSContext(
        timestamp=_now_iso(),
        cycle_id="1",
        canonical_state=canonical_state,
        canonical_sources={},
        current_positions=[],
        current_weights={"legacy_core": 0.5},
        current_gross_exposure=0.5,
        current_net_exposure=0.5,
        current_drawdown=0.0,
        max_gross_cap=1.0,
        max_net_cap=0.5,
        risk_veto_active=False,
        risk_veto_reasons=[],
        additional_inputs={},
    )


def test_adapter_blocks_when_contract_keys_missing(tmp_path) -> None:
    _write_canonical_artifacts(tmp_path)
    adapter = AlphaOSAdapter(project_root=tmp_path, config=_config())
    state = {
        "timestamp": _now_iso(),
        "portfolio_greeks": {},
        "weekly_risk_usage": {},
        "portfolio_risk_usage": {},
        # "options_cycle" intentionally missing
    }
    intent = adapter.evaluate_cycle(_context(tmp_path, state))
    assert intent.mode == "blocked_contract_violation"
    assert "adapter_contract_blocked" in intent.reason_codes


def test_adapter_blocks_when_artifacts_stale(tmp_path) -> None:
    _write_canonical_artifacts(tmp_path)
    stale_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(tmp_path / "data/processed/capital_allocations.json", (stale_epoch, stale_epoch))
    os.utime(tmp_path / "data/processed/regime_intelligence_feed.json", (stale_epoch, stale_epoch))

    adapter = AlphaOSAdapter(project_root=tmp_path, config=_config())
    state = {
        "timestamp": _now_iso(),
        "portfolio_greeks": {},
        "weekly_risk_usage": {},
        "portfolio_risk_usage": {},
        "options_cycle": {},
    }
    intent = adapter.evaluate_cycle(_context(tmp_path, state))
    assert intent.mode == "blocked_contract_violation"
    assert any("stale_canonical_artifact" in code for code in intent.reason_codes)


def test_adapter_runs_with_canonical_inputs_only(tmp_path) -> None:
    _write_canonical_artifacts(tmp_path)
    adapter = AlphaOSAdapter(project_root=tmp_path, config=_config())
    state = {
        "timestamp": _now_iso(),
        "portfolio_greeks": {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0},
        "weekly_risk_usage": {"trades_used": 0, "trades_limit": 2},
        "portfolio_risk_usage": {"risk_pct": 0.1},
        "options_cycle": {},
        "closed_positions": [],
        "regime_metrics": {"iv_rank": 0.5},
    }
    intent = adapter.evaluate_cycle(_context(tmp_path, state))
    assert intent.mode in {"shadow", "enforce", "disabled"}
    assert intent.mode != "blocked_contract_violation"
    assert "drift" in intent.diagnostics
    assert "survival_core" in intent.diagnostics
    assert "shadow_divergence_index" in intent.diagnostics


def test_returns_by_strategy_filters_short_regime_flip_churn(tmp_path) -> None:
    _write_canonical_artifacts(tmp_path)
    adapter = AlphaOSAdapter(project_root=tmp_path, config=_config())

    returns = adapter._returns_by_strategy(
        [
            {
                "strategy_type": "bear_put_spread",
                "realized_pnl": -1200.0,
                "max_loss": 4000.0,
                "exit_reason": "regime_flip",
                "hold_duration_minutes": 5.0,
            },
            {
                "strategy_type": "bear_put_spread",
                "realized_pnl": 800.0,
                "max_loss": 4000.0,
                "exit_reason": "target_hit",
                "hold_duration_minutes": 90.0,
            },
        ]
    )

    assert returns == {"bear_put_spread": [0.2]}
