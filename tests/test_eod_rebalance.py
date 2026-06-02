from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from scripts import eod_rebalance_with_pnl as eod_mod


def test_load_current_positions_raises_when_sources_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        eod_mod.load_current_positions()


def test_load_eod_prices_raises_when_date_not_found(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    prices_path = Path("data/processed/prices.parquet")
    prices_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"Date": "2026-03-19", "ticker": "RELIANCE", "Close": 100.0},
        ]
    ).to_parquet(prices_path, index=False)

    with pytest.raises(ValueError):
        eod_mod.load_eod_prices(["RELIANCE"], datetime(2026, 3, 20))


def test_load_options_positions_returns_empty_dict_when_file_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert eod_mod.load_options_positions() == {}


def test_eod_dry_run_loads_real_inputs_without_empty_dicts(monkeypatch) -> None:
    class Dummy:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(eod_mod, "load_current_positions", lambda: {"RELIANCE": {"quantity": 10, "avg_cost": 100.0}})
    monkeypatch.setattr(eod_mod, "resolve_effective_rebalance_date", lambda tickers, requested_date: requested_date)
    monkeypatch.setattr(eod_mod, "load_eod_prices", lambda tickers, trade_date: {"RELIANCE": 110.0})
    monkeypatch.setattr(
        eod_mod,
        "load_options_positions",
        lambda: {"OPT1": {"underlying": "NIFTY", "entry_credit_debit": 10.0, "quantity": 1}},
    )
    monkeypatch.setattr(eod_mod, "load_options_eod_prices", lambda trade_date=None: {"OPT1": 12.0})
    monkeypatch.setattr(eod_mod, "UnifiedPnLLedger", Dummy)
    monkeypatch.setattr(eod_mod, "NAVCalculator", Dummy)
    monkeypatch.setattr(eod_mod, "PnLAttributor", Dummy)
    monkeypatch.setattr(eod_mod, "PnLReconciler", Dummy)
    monkeypatch.setattr(eod_mod, "ExecutionQualityMonitor", Dummy)
    monkeypatch.setattr(eod_mod, "PaperFundManager", Dummy)
    monkeypatch.setattr(eod_mod, "UnifiedState", Dummy)

    assert eod_mod.eod_rebalance_with_pnl(dry_run=True) is True
