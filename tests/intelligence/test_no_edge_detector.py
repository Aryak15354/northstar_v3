from __future__ import annotations

import pandas as pd

from src.intelligence.no_edge_detector import NoEdgeDetector


def test_select_live_tailwind_rows_uses_current_regime_snapshot(tmp_path):
    detector = NoEdgeDetector()

    market_state_path = tmp_path / "market_state.parquet"
    tailwinds_path = tmp_path / "strategy_tailwinds.parquet"

    pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-03-19"),
                "regime": "late-expansion",
            }
        ]
    ).to_parquet(market_state_path, index=False)

    pd.DataFrame(
        [
            {"strategy_id": "northstar", "strategy_family": "composite", "regime": "boom", "tailwind_score": 0.94, "as_of_date": pd.Timestamp("2026-03-19")},
            {"strategy_id": "northstar", "strategy_family": "composite", "regime": "late-expansion", "tailwind_score": 1.08, "as_of_date": pd.Timestamp("2026-03-19")},
            {"strategy_id": "ownership_accumulation", "strategy_family": "ownership", "regime": "boom", "tailwind_score": 0.91, "as_of_date": pd.Timestamp("2026-03-19")},
            {"strategy_id": "ownership_accumulation", "strategy_family": "ownership", "regime": "late-expansion", "tailwind_score": 1.11, "as_of_date": pd.Timestamp("2026-03-19")},
        ]
    ).to_parquet(tailwinds_path, index=False)

    detector.paths["market_state"] = str(market_state_path)
    detector.paths["strategy_tailwinds"] = str(tailwinds_path)

    live_rows = detector._select_live_tailwind_rows(pd.read_parquet(tailwinds_path))
    assert set(live_rows["strategy"].tolist()) == {"northstar", "ownership_accumulation"}
    assert set(live_rows["regime"].astype(str).str.lower().tolist()) == {"late-expansion"}
    assert (pd.to_numeric(live_rows["combined_score"], errors="coerce") >= 1.03).all()
