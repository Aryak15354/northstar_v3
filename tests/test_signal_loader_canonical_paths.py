from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.intelligence.capital_allocator import CapitalAllocator
from src.signals.signal_loader import AlternativeDataLoader


def test_signal_loader_reads_live_nse_file_names(tmp_path: Path) -> None:
    alt_dir = tmp_path / "alternative"
    alt_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "nse_ticker": ["AAA.NS"],
            "deal_type": ["BUY"],
            "quantity": [1000.0],
            "price": [10.0],
            "client_name": ["GLOBAL MUTUAL FUND"],
            "company_name": ["AAA Ltd"],
        }
    ).to_csv(alt_dir / "bulk_deals_nse_all.csv", index=False)

    pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "nse_ticker": ["AAA.NS"],
            "new_rating": ["AA+"],
            "action_type": ["Upgrade"],
            "outlook": ["Positive"],
            "agency": ["ICRA"],
            "company_name": ["AAA Ltd"],
        }
    ).to_csv(alt_dir / "credit_ratings_nse_all.csv", index=False)

    pd.DataFrame(
        {
            "date": [pd.Timestamp("2023-12-31")],
            "nse_ticker": ["AAA.NS"],
            "pledge_pct": [35.0],
        }
    ).to_csv(alt_dir / "promoter_pledge_all.csv", index=False)

    pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "nse_ticker": ["AAA.NS"],
            "category": ["Order Win"],
            "headline": ["AAA wins order worth Rs 50 crore"],
            "announcement_text": ["Order win announced"],
        }
    ).to_csv(alt_dir / "announcements_all.csv", index=False)

    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-03")],
            "ticker": ["AAA.NS"],
            "market_cap": [100_000.0],
        }
    )

    loader = AlternativeDataLoader({"alternative_data_path": str(alt_dir)})
    out = loader.get_features_as_of_frame(frame)

    assert float(out.loc[0, "bulk_net_volume_5d"]) > 0.0
    assert float(out.loc[0, "rating_numeric"]) == 9.0
    assert float(out.loc[0, "order_win_flag_30d"]) == 1.0


def test_capital_allocator_normalizes_alpha_os_tailwind_schema() -> None:
    allocator = CapitalAllocator()
    tailwind_df = pd.DataFrame(
        {
            "strategy_id": ["strategy_recommendations_1"],
            "strategy_family": ["COMPOSITE"],
            "regime": ["bull_optimistic_expansion"],
            "tailwind_score": [0.03],
            "n_observations": [20],
            "as_of_date": [pd.Timestamp("2026-03-13")],
        }
    )

    normalized = allocator._normalize_tailwind_frame(tailwind_df)
    resolved = allocator._resolve_tailwind_for_strategy("quality_tilt", normalized)

    assert "__default__" in normalized
    assert normalized["__default__"]["combined_score"] == 1.03
    assert resolved["combined_score"] == 1.03
