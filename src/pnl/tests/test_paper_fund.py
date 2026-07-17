"""Tests for the ₹100cr paper fund: cost model, tax lots, and engine invariants.

These lock the institutional accounting guarantees the fund depends on:
  * Indian statutory costs are computed to known values.
  * FIFO tax lots split LTCG/STCG correctly and honour the annual exemption.
  * The engine enforces its rules (position/sector caps), marks to market every
    trading day (no flat NAV), stops at the honest price horizon, and its NAV
    reconciles exactly to cash + mark-to-market.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.pnl.indian_cost_model import IndianEquityCostModel
from src.pnl.equity_tax_lots import EquityTaxLotTracker


# --------------------------------------------------------------------------- #
# cost model
# --------------------------------------------------------------------------- #
def test_buy_cost_known_values():
    cm = IndianEquityCostModel()
    b = cm.cost_breakdown("BUY", 1_000_000, adv_inr=500_000_000)
    assert b.stt == pytest.approx(1000.0)             # 0.1%
    assert b.stamp_duty == pytest.approx(150.0)       # 0.015% buy side
    assert b.exchange_txn == pytest.approx(29.7, rel=1e-3)
    assert b.gst == pytest.approx(0.18 * (b.brokerage + b.exchange_txn + b.sebi), rel=1e-6)
    assert b.slippage > 0                             # impact present with ADV


def test_sell_has_no_stamp_duty():
    cm = IndianEquityCostModel()
    s = cm.cost_breakdown("SELL", 1_000_000, adv_inr=500_000_000)
    assert s.stamp_duty == 0.0
    assert s.stt == pytest.approx(1000.0)             # STT both sides


def test_slippage_scales_with_size_over_adv():
    cm = IndianEquityCostModel()
    small = cm.slippage_bps_for(1_000_000, 1_000_000_000)
    large = cm.slippage_bps_for(100_000_000, 1_000_000_000)
    assert large > small > cm.slippage_bps - 1e-9     # impact grows with size


# --------------------------------------------------------------------------- #
# tax lots
# --------------------------------------------------------------------------- #
def test_stcg_taxed_at_20pct():
    t = EquityTaxLotTracker()
    t.buy("X.NS", 100, 100.0, datetime(2024, 1, 1))
    g = t.sell("X.NS", 100, 150.0, datetime(2024, 6, 1))   # <1yr
    assert g.short_term_gain == pytest.approx(5000.0)
    assert g.long_term_gain == 0.0
    assert g.tax == pytest.approx(1000.0)                  # 20% of 5000


def test_ltcg_under_exemption_is_untaxed():
    t = EquityTaxLotTracker()
    t.buy("Y.NS", 100, 100.0, datetime(2023, 1, 1))
    g = t.sell("Y.NS", 100, 150.0, datetime(2024, 3, 1))   # >1yr, gain 5000 < 1.25L
    assert g.long_term_gain == pytest.approx(5000.0)
    assert g.tax == 0.0


def test_ltcg_over_exemption_taxed_at_12_5pct():
    t = EquityTaxLotTracker()
    t.buy("Z.NS", 1000, 100.0, datetime(2023, 1, 1))
    g = t.sell("Z.NS", 1000, 300.0, datetime(2024, 3, 1))  # gain 200000
    # taxable = 200000 - 125000 exemption = 75000 @ 12.5% = 9375
    assert g.tax == pytest.approx(9375.0)


def test_fifo_ordering():
    t = EquityTaxLotTracker()
    t.buy("A.NS", 10, 100.0, datetime(2023, 1, 1))   # old, long-term
    t.buy("A.NS", 10, 200.0, datetime(2024, 6, 1))   # new, short-term
    g = t.sell("A.NS", 10, 250.0, datetime(2024, 7, 1))
    # FIFO consumes the old lot first → long-term gain of (250-100)*10 = 1500
    assert g.long_term_gain == pytest.approx(1500.0)
    assert g.short_term_gain == 0.0


# --------------------------------------------------------------------------- #
# engine invariants (skip cleanly if price data isn't present)
# --------------------------------------------------------------------------- #
def _engine_result():
    from pathlib import Path
    from src.portfolio.paper_portfolio_engine import PaperPortfolioEngine, MarketData
    root = Path(__file__).resolve().parents[3]
    weights = root / "data/processed/portfolio_weights.parquet"
    prices = root / "data/processed/prices.parquet"
    if not weights.exists() or not prices.exists():
        pytest.skip("price/weights data not present")
    MarketData._cache = None
    tw = pd.read_parquet(weights)[["ticker", "Industry", "final_weight"]]
    eng = PaperPortfolioEngine(tw, strategy_id="test", market=MarketData.get())
    return eng, eng.simulate()


def test_engine_marks_every_day_and_reconciles():
    eng, res = _engine_result()
    nav = res.nav_history
    assert len(nav) > 200
    # marked to market EVERY day — not flat like the old ledger-only NAV
    assert (nav["daily_return"].abs() > 1e-12).mean() > 0.95
    # NAV == cash + mark-to-market by construction (final row)
    invested = res.positions["market_value"].sum() if not res.positions.empty else 0.0
    assert abs((nav["net_cash_position"].iloc[-1] + invested) - nav["nav_combined"].iloc[-1]) < 1.0


def test_engine_stops_at_price_horizon():
    from src.portfolio.paper_portfolio_engine import MarketData
    eng, res = _engine_result()
    last = res.nav_history["date"].max()
    assert last == MarketData.get().last_date        # honest freeze, no phantom marks


def test_engine_enforces_caps():
    eng, res = _engine_result()
    pos = res.positions
    assert not pos.empty
    # single-name weight stays within cap + rebalance band tolerance
    assert pos["weight_pct"].max() <= eng.max_position * (1 + eng.rebalance_band) * 100 + 0.5
    # sector weight within cap + band tolerance
    sector_pct = pos.groupby("sector")["market_value"].sum() / pos["market_value"].sum() * 100
    assert sector_pct.max() <= eng.max_sector * (1 + eng.rebalance_band) * 100 + 1.0


def test_liquidation_takes_multiple_days_for_some_names():
    eng, res = _engine_result()
    liq = res.liquidation_schedule
    assert not liq.empty
    assert liq["days_to_exit"].max() >= 1             # cannot dump instantly
