#!/usr/bin/env python3
"""
Reset options strategy posteriors after system-caused rapid-close losses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


POSTERIORS_PATH = Path("data/processed/alpha_os_strategy_posteriors.parquet")
OPTIONS_STRATEGIES = {
    'bear_put_spread',
    'long_straddle',
    'long_strangle',
    'long_call',
    'long_put',
    'bull_call_spread',
}


def main() -> int:
    if not POSTERIORS_PATH.exists():
        print(f"Posteriors file not found: {POSTERIORS_PATH}")
        return 1

    df = pd.read_parquet(POSTERIORS_PATH)
    if df.empty or "strategy_name" not in df.columns:
        print("Posterior file is empty or missing strategy_name")
        return 1

    reset_count = 0
    for strategy in sorted(OPTIONS_STRATEGIES):
        strategy_rows = df[df["strategy_name"] == strategy]
        if strategy_rows.empty:
            continue
        latest_ts = strategy_rows["timestamp"].max() if "timestamp" in strategy_rows.columns else None
        mask = df["strategy_name"].eq(strategy)
        if latest_ts is not None:
            mask &= df["timestamp"].eq(latest_ts)

        old_values = df.loc[mask, "posterior_mean"].tolist()
        df.loc[mask, "posterior_mean"] = 0.0
        if "posterior_variance" in df.columns:
            df.loc[mask, "posterior_variance"] = 0.01
        print(f"Reset {strategy}: {old_values} -> 0.0")
        reset_count += int(mask.sum())

    if reset_count == 0:
        print("No options posterior rows found to reset")
        return 0

    df.to_parquet(POSTERIORS_PATH, index=False)
    print(f"Reset {reset_count} posterior rows to neutral in {POSTERIORS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
