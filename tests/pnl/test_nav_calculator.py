from __future__ import annotations

from datetime import datetime

import pandas as pd

from src.pnl.nav_calculator import NAVCalculator


class _StubLedger:
    def __init__(self, rows: list[dict]):
        self._df = pd.DataFrame(rows)

    def query(self, start_date=None, end_date=None):
        df = self._df.copy()
        if df.empty:
            return df
        if start_date is not None:
            df = df[df["trade_date"] >= start_date]
        if end_date is not None:
            df = df[df["trade_date"] <= end_date]
        return df


def _config(starting_capital: float = 1_000.0) -> dict:
    return {
        "pnl": {
            "nav": {
                "starting_capital_inr": starting_capital,
                "inception_date": "2026-01-01",
                "nav_unit_size": 100.0,
            }
        }
    }


def test_compute_daily_nav_keeps_starting_capital_as_cash_when_no_entries():
    calc = NAVCalculator(_StubLedger([]), _config())
    nav = calc.compute_daily_nav(
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 3),
    )

    assert nav["net_cash_position"].tolist() == [1_000.0, 1_000.0, 1_000.0]


def test_compute_daily_nav_reconstructs_cash_from_trade_flows():
    ledger = _StubLedger(
        [
            {
                "trade_date": datetime(2026, 1, 2, 10, 0, 0),
                "entry_type": "EQUITY_BUY",
                "book": "EQUITY",
                "quantity": 2.0,
                "price": 50.0,
                "notional": 100.0,
                "net_pnl": 0.0,
                "transaction_cost": -1.0,
            },
            {
                "trade_date": datetime(2026, 1, 3, 10, 0, 0),
                "entry_type": "EQUITY_MTM",
                "book": "EQUITY",
                "quantity": 0.0,
                "price": 110.0,
                "notional": 110.0,
                "net_pnl": 5.0,
                "transaction_cost": 0.0,
            },
            {
                "trade_date": datetime(2026, 1, 4, 10, 0, 0),
                "entry_type": "EQUITY_SELL",
                "book": "EQUITY",
                "quantity": -1.0,
                "price": 50.0,
                "notional": 50.0,
                "net_pnl": 10.0,
                "transaction_cost": -1.0,
            },
        ]
    )
    calc = NAVCalculator(ledger, _config())

    nav = calc.compute_daily_nav(
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 1, 4),
    )

    assert nav.loc[pd.Timestamp("2026-01-01"), "net_cash_position"] == 1_000.0
    assert nav.loc[pd.Timestamp("2026-01-02"), "net_cash_position"] == 899.0
    assert nav.loc[pd.Timestamp("2026-01-03"), "net_cash_position"] == 899.0
    assert nav.loc[pd.Timestamp("2026-01-04"), "net_cash_position"] == 948.0
