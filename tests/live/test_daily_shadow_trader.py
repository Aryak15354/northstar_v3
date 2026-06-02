from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.live.daily_shadow_trader import DailyShadowTrader


def _build_trader(tmp_path: Path) -> DailyShadowTrader:
    return DailyShadowTrader(
        initial_capital=1_000_000,
        data_directory=str(tmp_path / "shadow_live"),
        execution_mode="exact_target",
        prs_db_path=str(tmp_path / "daily_shadow_runtime.db"),
        prs_materialized_dir=str(tmp_path / "materialized"),
    )


def test_exact_reconcile_positions_matches_target(tmp_path: Path) -> None:
    trader = _build_trader(tmp_path)
    try:
        prices = pd.Series(
            {
                "ABB.NS": 100.0,
                "ASHOKLEY.NS": 50.0,
                "BANKINDIA.NS": 80.0,
            }
        )
        first_target = {
            "ABB.NS": {"quantity": 10.0, "price": 100.0, "weight": 0.5},
            "ASHOKLEY.NS": {"quantity": 20.0, "price": 50.0, "weight": 0.5},
        }
        adjustments, unresolved = trader._reconcile_positions_exact(first_target, prices)
        first_positions = trader._sync_positions_from_prs(prices)
        first_summary = trader._compute_tracking_summary(
            first_target,
            first_positions,
            unresolved_symbols=unresolved,
        )

        assert adjustments == 2
        assert unresolved == []
        assert first_summary["breach"] is False
        assert first_summary["exact_target_match"] is True
        assert set(first_positions.keys()) == {"ABB.NS", "ASHOKLEY.NS"}

        second_target = {
            "ABB.NS": {"quantity": 5.0, "price": 100.0, "weight": 0.3846153846},
            "BANKINDIA.NS": {"quantity": 10.0, "price": 80.0, "weight": 0.6153846154},
        }
        adjustments_2, unresolved_2 = trader._reconcile_positions_exact(second_target, prices)
        second_positions = trader._sync_positions_from_prs(prices)
        second_summary = trader._compute_tracking_summary(
            second_target,
            second_positions,
            unresolved_symbols=unresolved_2,
        )

        assert adjustments_2 == 3
        assert unresolved_2 == []
        assert set(second_positions.keys()) == {"ABB.NS", "BANKINDIA.NS"}
        assert second_positions["ABB.NS"]["quantity"] == 5.0
        assert second_positions["BANKINDIA.NS"]["quantity"] == 10.0
        assert second_summary["breach"] is False
        assert second_summary["exact_target_match"] is True
        assert second_summary["target_position_overlap"] == 1.0
    finally:
        trader.prs.close()


def test_tracking_summary_flags_unresolved_and_extra_positions(tmp_path: Path) -> None:
    trader = _build_trader(tmp_path)
    try:
        target_positions = {
            "ABB.NS": {"quantity": 10.0, "price": 100.0, "weight": 1.0},
        }
        actual_positions = {
            "ASHOKLEY.NS": {"quantity": 5.0, "price": 50.0, "weight": 1.0},
        }
        summary = trader._compute_tracking_summary(
            target_positions,
            actual_positions,
            unresolved_symbols=["ABB.NS"],
        )

        assert summary["breach"] is True
        assert summary["exact_target_match"] is False
        assert summary["missing_target_positions_count"] == 1
        assert summary["extra_positions_count"] == 1
        assert summary["quantity_mismatch_count"] == 2
        assert any("unresolved_prices=ABB.NS" in reason for reason in summary["reasons"])
    finally:
        trader.prs.close()
