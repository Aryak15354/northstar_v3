from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import pytest

from scripts.run_complete_v3_system import _maybe_migrate_legacy_exposure_columns
from src.core.state import MarketState, UnifiedState
from src.core.state_authority import StateAuthority
from src.core.state_bridges.runtime_bridge import RuntimeStateBridge
from src.core.state_bridges.shadow_bridge import ShadowStateBridge
from src.portfolio.governor import PortfolioGovernor
from src.scoring.daily_scorer import DailyScorer


def _write_snapshot(path: Path, *, age_hours: float) -> None:
    snapshot = {
        "version": "2.0",
        "checkpoint_time": (datetime.now() - timedelta(hours=age_hours)).isoformat(),
        "timestamp": (datetime.now() - timedelta(hours=age_hours)).isoformat(),
        "market": {"regime": "BULL", "volatility_regime": "NORMAL_VOL"},
    }
    path.write_text(json.dumps(snapshot), encoding="utf-8")


def test_load_snapshot_marks_state_stale_when_older_than_threshold(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "unified_state.json"
    _write_snapshot(snapshot_path, age_hours=7.0)

    state = UnifiedState.load_snapshot_file(snapshot_path, max_age_hours=6.0)

    assert state._state_is_stale is True
    assert state._state_age_hours is not None
    assert state._state_age_hours >= 7.0 - 0.2


def test_load_snapshot_marks_state_fresh_within_threshold(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "unified_state.json"
    _write_snapshot(snapshot_path, age_hours=1.0)

    state = UnifiedState.load_snapshot_file(snapshot_path, max_age_hours=6.0)

    assert state._state_is_stale is False
    assert state._state_age_hours is not None
    assert state._state_age_hours < 6.0


def test_governor_returns_none_when_state_is_stale(tmp_path: Path) -> None:
    governor = PortfolioGovernor(config={"starting_capital_inr": 10_000_000}, data_dir=str(tmp_path))
    state = UnifiedState()
    state._state_is_stale = True
    state._state_age_hours = 7.0

    assert governor.compute_capital_structure(state) is None


def test_market_state_rejects_percentage_point_exposure_values() -> None:
    with pytest.raises(ValueError, match="decimal ratios"):
        MarketState(allowed_exposure=55.0)


def test_legacy_exposure_columns_are_migrated_to_ratios() -> None:
    df = pd.DataFrame(
        {
            "allowed_exposure": [55.0, 22.5],
            "ai_allowed_exposure": [65.0, 40.0],
        }
    )

    migrated, migrated_columns = _maybe_migrate_legacy_exposure_columns(
        df,
        source_name="test_market_state.parquet",
    )

    assert migrated_columns == ["allowed_exposure", "ai_allowed_exposure"]
    assert migrated["allowed_exposure"].tolist() == [0.55, 0.225]
    assert migrated["ai_allowed_exposure"].tolist() == [0.65, 0.4]


def test_scorer_warns_but_continues_when_state_is_stale(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    snapshot_path = tmp_path / "unified_state.json"
    _write_snapshot(snapshot_path, age_hours=7.0)

    scorer = DailyScorer(
        config={
            "state": {
                "snapshot_path": str(snapshot_path),
                "max_age_hours": 6.0,
            }
        }
    )

    monkeypatch.setattr(scorer.regime_engine, "get_regime_as_of", lambda dt: "BULL")
    monkeypatch.setattr(scorer.regime_engine, "get_exposure_scale", lambda regime: 1.0)
    monkeypatch.setattr(
        scorer,
        "_load_latest_universe_frame",
        lambda dt, regime=None: (
            pd.DataFrame({"ticker": ["AAA.NS"], "feature_1": [1.0]}),
            ["feature_1"],
        ),
    )
    monkeypatch.setattr(scorer.trainer, "predict", lambda frame, regime=None: np.array([0.42]))
    monkeypatch.setattr(
        scorer.overlay,
        "apply",
        lambda frame, as_of_date=None: pd.DataFrame(
            {
                "ticker": frame["ticker"].astype(str),
                "sentiment_multiplier": [1.0],
                "sentiment_override": [False],
                "override_reason": [None],
                "sentiment_polarity": [0.0],
                "sentiment_conviction": [0.0],
                "news_volume": [0.0],
            }
        ),
    )
    monkeypatch.setattr(
        scorer,
        "_build_weights",
        lambda frame, exposure_scale, mandate, apply_turnover=True: pd.Series([1.0], index=frame.index),
    )
    monkeypatch.setattr(scorer, "_save_prev_portfolio", lambda portfolio: None)

    with caplog.at_level(logging.WARNING):
        out = scorer.score("2026-03-20")

    assert not out.empty
    assert "[daily-scorer] unified state is stale" in caplog.text


def test_runtime_bridge_treats_target_book_as_structural_mismatch(tmp_path: Path) -> None:
    state = UnifiedState()
    authority = StateAuthority(state, config={"dev_mode": True, "checkpoint_path": str(tmp_path / "state.json")})
    bridge = RuntimeStateBridge(
        db_path=str(tmp_path / "missing.db"),
        state_authority=authority,
        config={"materialized_positions_path": str(tmp_path / "runtime_positions.parquet")},
    )

    discrepancies = bridge._compare_positions(
        {"ABB.NS": {"quantity": 10.0}},
        {"ABB.NS": {"weight": 0.05, "final_weight": 0.05, "Industry": "Capital Goods"}},
    )

    assert discrepancies == [
        "unified portfolio contains target-weight rows rather than live quantities; runtime bridge will reconcile"
    ]


def test_shadow_bridge_suppresses_stale_shadow_divergence_alert(tmp_path: Path) -> None:
    shadow_path = tmp_path / "shadow_portfolio_state.parquet"
    pd.DataFrame(
        [
            {
                "date": datetime.now() - timedelta(days=30),
                "timestamp": (datetime.now() - timedelta(days=30)).isoformat(),
                "total_exposure": 0.8,
                "n_positions": 7,
            }
        ]
    ).to_parquet(shadow_path, index=False)

    state = UnifiedState()
    state.portfolio.total_value = 10_000_000.0
    state.portfolio.invested_value = 2_500_000.0
    authority = StateAuthority(state, config={"dev_mode": True, "checkpoint_path": str(tmp_path / "state.json")})

    bridge = ShadowStateBridge(str(shadow_path), authority, config={"max_shadow_age_days": 7})
    bridge.push_shadow_state()

    assert authority.state.shadow_state.divergence_alert is False
    assert authority.state.shadow_state.shadow_data_stale is True
    assert authority.state.shadow_state.live_shadow_nav_divergence_pct == 0.0


def test_shadow_bridge_tracks_target_overlap_and_ignores_options(tmp_path: Path) -> None:
    shadow_path = tmp_path / "shadow_portfolio_state.parquet"
    pd.DataFrame(
        [
            {
                "date": datetime.now(),
                "timestamp": datetime.now().isoformat(),
                "nav": 1_000_000.0,
                "total_exposure": 0.8,
                "n_positions": 2,
                "execution_mode": "exact_target",
                "tracking_status": "pass",
                "tracking_breach": False,
                "target_total_weight_drift": 0.0,
                "target_max_weight_drift": 0.0,
                "target_quantity_mismatch_count": 0,
                "exact_target_match": True,
            }
        ]
    ).to_parquet(shadow_path, index=False)

    shadow_positions_path = tmp_path / "shadow_positions.parquet"
    pd.DataFrame(
        [
            {
                "timestamp": datetime.now(),
                "ticker": "ABB.NS",
                "shares": 10.0,
                "avg_price": 100.0,
                "market_value": 1_000.0,
                "unrealized_pnl": 0.0,
            },
            {
                "timestamp": datetime.now(),
                "ticker": "ASHOKLEY.NS",
                "shares": 20.0,
                "avg_price": 50.0,
                "market_value": 1_000.0,
                "unrealized_pnl": 0.0,
            },
        ]
    ).to_parquet(shadow_positions_path, index=False)

    state = UnifiedState()
    state.portfolio.total_value = 1_000_000.0
    state.portfolio.positions = {
        "ABB.NS": {"quantity": 10.0, "market_value": 1_000.0, "instrument_type": "equity"},
        "ASHOKLEY.NS": {"quantity": 20.0, "market_value": 1_000.0, "instrument_type": "equity"},
        "OPT::TEST_LONG_CALL": {"quantity": 1.0, "market_value": 500.0, "instrument_type": "option"},
    }
    state.portfolio.target_positions = {
        "ABB.NS": {"weight": 0.5},
        "ASHOKLEY.NS": {"weight": 0.3},
        "BANKINDIA.NS": {"weight": 0.2},
    }
    authority = StateAuthority(state, config={"dev_mode": True, "checkpoint_path": str(tmp_path / "state.json")})

    bridge = ShadowStateBridge(
        str(shadow_path),
        authority,
        config={"shadow_positions_path": str(shadow_positions_path)},
    )
    bridge.push_shadow_state()

    assert authority.state.shadow_state.live_shadow_position_overlap == 1.0
    assert authority.state.shadow_state.target_shadow_position_overlap == pytest.approx(2 / 3, rel=1e-9)
    assert authority.state.shadow_state.execution_mode == "exact_target"
    assert authority.state.shadow_state.tracking_breach is False
    assert authority.state.shadow_state.exact_target_match is True


def test_shadow_bridge_ignores_zero_sized_target_rows(tmp_path: Path) -> None:
    shadow_path = tmp_path / "shadow_portfolio_state.parquet"
    pd.DataFrame(
        [
            {
                "date": datetime.now(),
                "timestamp": datetime.now().isoformat(),
                "nav": 1_000_000.0,
                "total_exposure": 0.8,
                "n_positions": 1,
                "target_positions_json": json.dumps(
                    {
                        "ABB.NS": {"quantity": 10.0, "price": 100.0, "notional": 1_000.0},
                        "ASHOKLEY.NS": {"quantity": 0.0, "price": 0.0, "notional": 0.0},
                    }
                ),
            }
        ]
    ).to_parquet(shadow_path, index=False)

    shadow_positions_path = tmp_path / "shadow_positions.parquet"
    pd.DataFrame(
        [
            {
                "timestamp": datetime.now(),
                "ticker": "ABB.NS",
                "shares": 10.0,
                "avg_price": 100.0,
                "market_value": 1_000.0,
                "unrealized_pnl": 0.0,
            },
        ]
    ).to_parquet(shadow_positions_path, index=False)

    state = UnifiedState()
    state.portfolio.total_value = 1_000_000.0
    authority = StateAuthority(state, config={"dev_mode": True, "checkpoint_path": str(tmp_path / "state.json")})

    bridge = ShadowStateBridge(
        str(shadow_path),
        authority,
        config={"shadow_positions_path": str(shadow_positions_path)},
    )
    bridge.push_shadow_state()

    assert authority.state.shadow_state.target_shadow_position_overlap == 1.0
    assert authority.state.shadow_state.shadow_missing_target_positions_count == 0
