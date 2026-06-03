from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import clamp, confidence_from_spread, f, infer_market_cap, variance_from_bounds


class TransactionFamilyEngine:
    """
    Transaction-oriented valuation family:
    - Precedent transaction style value using sector EV/EBITDA + control premium
    - LBO implied entry value from target IRR
    """

    def __init__(self, control_premium: float = 0.20, lbo_target_irr: float = 0.20, hold_years: int = 5) -> None:
        self.control_premium = float(control_premium)
        self.lbo_target_irr = float(lbo_target_irr)
        self.hold_years = int(max(3, hold_years))

    @staticmethod
    def _sector_medians(df: pd.DataFrame) -> pd.DataFrame:
        work = df.copy()
        work["ev_ebitda"] = pd.to_numeric(work.get("ev_ebitda"), errors="coerce")
        med = (
            work.dropna(subset=["Industry", "ev_ebitda"])
            .query("ev_ebitda > 0")
            .groupby("Industry", as_index=False)["ev_ebitda"]
            .median()
            .rename(columns={"ev_ebitda": "sector_ev_ebitda_median"})
        )
        return med

    def run(self, core_df: pd.DataFrame) -> pd.DataFrame:
        med = self._sector_medians(core_df)
        base = core_df.merge(med, on="Industry", how="left")
        rows: list[dict[str, Any]] = []
        for _, row in base.iterrows():
            ticker = row.get("ticker")
            market_cap = infer_market_cap(row)
            ebitda = f(row.get("ebitda_ttm"), np.nan)
            debt = max(0.0, f(row.get("total_debt"), 0.0))
            cash = max(0.0, f(row.get("cash_and_equivalents"), 0.0))
            growth = clamp(f(row.get("revenue_growth"), 0.02), -0.05, 0.18)

            sector_multiple = f(row.get("sector_ev_ebitda_median"), np.nan)
            if not np.isfinite(sector_multiple) or sector_multiple <= 0:
                sector_multiple = clamp(f(row.get("ev_ebitda"), 10.0), 4.0, 24.0)

            if not np.isfinite(ebitda) or ebitda <= 0:
                rows.append(
                    {
                        "ticker": ticker,
                        "transaction_value": np.nan,
                        "transaction_gap": np.nan,
                        "transaction_variance": 1.0,
                        "transaction_confidence": 0.20,
                        "lbo_value": np.nan,
                        "lbo_gap": np.nan,
                        "lbo_variance": 1.0,
                        "lbo_confidence": 0.20,
                    }
                )
                continue

            tx_multiple = sector_multiple * (1.0 + self.control_premium)
            tx_ev = ebitda * tx_multiple
            tx_equity = tx_ev - debt + cash

            tx_low = tx_equity * 0.86
            tx_high = tx_equity * 1.14
            tx_var = variance_from_bounds(tx_low, tx_high)
            tx_spread = (tx_high - tx_low) / max(abs(tx_equity), 1.0)
            tx_conf = confidence_from_spread(tx_spread, base=0.66)
            tx_gap = np.nan
            if np.isfinite(market_cap) and market_cap > 0:
                tx_gap = clamp((tx_equity - market_cap) / market_cap, -2.0, 2.0)

            # LBO implied entry valuation.
            exit_multiple = clamp(sector_multiple * 0.95, 4.0, 22.0)
            projected_ebitda = ebitda * ((1.0 + max(growth, 0.0)) ** self.hold_years)
            exit_ev = projected_ebitda * exit_multiple
            entry_ev = exit_ev / ((1.0 + self.lbo_target_irr) ** self.hold_years)
            lbo_equity = entry_ev - debt + cash
            lbo_low = lbo_equity * 0.84
            lbo_high = lbo_equity * 1.16
            lbo_var = variance_from_bounds(lbo_low, lbo_high)
            lbo_spread = (lbo_high - lbo_low) / max(abs(lbo_equity), 1.0)
            lbo_conf = confidence_from_spread(lbo_spread, base=0.62)
            lbo_gap = np.nan
            if np.isfinite(market_cap) and market_cap > 0:
                lbo_gap = clamp((lbo_equity - market_cap) / market_cap, -2.0, 2.0)

            rows.append(
                {
                    "ticker": ticker,
                    "transaction_value": tx_equity,
                    "transaction_gap": tx_gap,
                    "transaction_variance": tx_var,
                    "transaction_confidence": tx_conf,
                    "lbo_value": lbo_equity,
                    "lbo_gap": lbo_gap,
                    "lbo_variance": lbo_var,
                    "lbo_confidence": lbo_conf,
                }
            )
        return pd.DataFrame(rows)

