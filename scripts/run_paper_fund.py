#!/usr/bin/env python3
"""
run_paper_fund.py — drive the ₹100cr paper fund and persist the ONE truth.

Rebuilds the fund's canonical accounting from the v3 target book:
  * marks positions to market daily to the last available price date,
  * books full Indian costs + realized LTCG/STCG,
  * enforces position/sector/cash caps and ADV-capped multi-day execution,

then writes the single source of truth:
  data/pnl/nav_history.parquet          (NAV time series — the honest curve)
  data/pnl/current_positions.parquet    (position book)
  data/pnl/master_ledger.parquet        (trade/cost/tax audit log)
  data/pnl/paper_fund_summary.json      (metrics, costs, liquidation schedule)
  data/pnl/liquidation_schedule.parquet
  data/state/unified_state.json         (portfolio + governor capital block)

Idempotent: backs up prior artifacts before overwriting. Re-running after the
daily refresh brings newer prices auto-extends the NAV (honest freeze + extend).

Usage:
  python3 scripts/run_paper_fund.py
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.paper_portfolio_engine import PaperPortfolioEngine, MarketData

PNL_DIR = PROJECT_ROOT / "data" / "pnl"
STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"
V3_WEIGHTS = PROJECT_ROOT / "data" / "processed" / "portfolio_weights.parquet"
WEEKLY_DIR = PROJECT_ROOT / "data" / "portfolio" / "weekly"


def _build_target_schedule() -> dict:
    """Point-in-time target history: {as_of_date -> weights_df}.

    Assembled from the weekly portfolio snapshots (the record of what the target
    ACTUALLY was each week) plus today's live weights as the most recent target.
    Feeding this to the engine makes nav_history.parquet an honest walk-forward
    curve instead of the previous look-ahead backfill that replayed TODAY's book
    across all past dates.
    """
    schedule: dict = {}
    if WEEKLY_DIR.exists():
        for snap in sorted(WEEKLY_DIR.glob("*.parquet")):
            ts = pd.to_datetime(snap.stem, errors="coerce")
            if pd.isna(ts):
                continue
            try:
                df = pd.read_parquet(snap)
            except Exception:
                continue
            if df.empty or "ticker" not in df.columns:
                continue
            wcol = next((c for c in ("weight", "final_weight", "w", "allocation") if c in df.columns), None)
            if wcol is None:
                continue
            keep = [c for c in ("ticker", "Industry", wcol) if c in df.columns]
            schedule[pd.Timestamp(ts).normalize()] = df[keep].rename(columns={wcol: "weight"})
    # Today's live target is the most recent point on the curve.
    if V3_WEIGHTS.exists():
        tw = pd.read_parquet(V3_WEIGHTS)
        if not tw.empty and "ticker" in tw.columns:
            schedule[pd.Timestamp.today().normalize()] = tw
    return schedule


def _backup(paths: list[Path]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = PNL_DIR / "backup_before_paper_fund"
    bdir.mkdir(parents=True, exist_ok=True)
    for p in paths:
        if p.exists():
            shutil.copy(p, bdir / f"{p.stem}_{stamp}{p.suffix}")


def _update_state(result, starting_capital: float) -> None:
    """Write the fund truth into unified_state.json (portfolio + governor capital)."""
    if not STATE_PATH.exists():
        return
    try:
        state = json.loads(STATE_PATH.read_text())
    except Exception:
        return
    nav = result.nav_history
    pos = result.positions
    final_nav = float(nav["nav_combined"].iloc[-1]) if not nav.empty else starting_capital
    cash = float(nav["net_cash_position"].iloc[-1]) if not nav.empty else starting_capital
    invested = float(pos["market_value"].sum()) if not pos.empty else 0.0
    sector_exp = (pos.groupby("sector")["market_value"].sum() / final_nav).to_dict() if not pos.empty else {}

    port = state.setdefault("portfolio", {})
    port.update({
        "total_value": final_nav,
        "cash": cash,
        "invested_value": invested,
        "position_count": int(len(pos)),
        "total_positions": int(len(pos)),
        "total_exposure": float(invested / final_nav) if final_nav else 0.0,
        "max_position": float(pos["weight_pct"].max() / 100.0) if not pos.empty else 0.0,
        "sector_exposure": {k: float(v) for k, v in sector_exp.items()},
        "max_sector_exposure": float(max(sector_exp.values())) if sector_exp else 0.0,
        "unrealized_pnl": float(pos["unrealized_pnl"].sum()) if not pos.empty else 0.0,
        "as_of_market_date": result.metrics.get("as_of"),
        "last_updated": datetime.now().isoformat(),
    })

    gov = state.setdefault("governor_state", {})
    eq_frac = float(gov.get("equity_fraction", 0.75))
    opt_frac = float(gov.get("options_fraction", 0.15))
    cash_frac = float(gov.get("cash_fraction", 0.10))
    gov.update({
        "total_capital_inr": final_nav,
        "equity_budget_inr": final_nav * eq_frac,
        "options_budget_inr": final_nav * opt_frac,
        "cash_reserve_inr": final_nav * cash_frac,
    })

    cap = state.setdefault("capital", {})
    cap.update({
        "total_capital": final_nav,
        "allocated_capital": invested,
        "allocation_efficiency": float(invested / final_nav) if final_nav else 0.0,
        "last_rebalance": result.metrics.get("as_of"),
    })

    STATE_PATH.write_text(json.dumps(state, indent=2, default=str))


def main() -> int:
    print("=" * 72)
    print("NORTHSTAR V3 PAPER FUND — rebuilding the one truth")
    print("=" * 72)

    if not V3_WEIGHTS.exists():
        print(f"✗ missing target weights: {V3_WEIGHTS}")
        return 1

    schedule = _build_target_schedule()
    if not schedule:
        print("✗ no target history (weekly snapshots + current weights both empty)")
        return 1

    market = MarketData.get()
    first_target = min(schedule)
    print(f"  price horizon: inception → {market.last_date.date()} (honest freeze)")
    print(f"  point-in-time target schedule: {len(schedule)} snapshots, "
          f"first real target {pd.Timestamp(first_target).date()}")

    # Pass the POINT-IN-TIME schedule (not a single static target replayed from
    # inception) so the NAV curve is an honest walk-forward record with costs.
    engine = PaperPortfolioEngine(strategy_id="v3", market=market, target_schedule=schedule)
    result = engine.simulate()

    nav = result.nav_history
    m = result.metrics
    print(f"  NAV: ₹{engine.starting_capital:,.0f} → ₹{m['final_nav']:,.0f}  "
          f"({m['total_return_pct']:+.1f}%, ann {m['annualized_return_pct']:+.1f}%, "
          f"Sharpe {m['sharpe']:.2f}, maxDD {m['max_drawdown_pct']:.1f}%)")
    print(f"  costs ₹{result.cost_summary['cumulative_costs']:,.0f} "
          f"({result.cost_summary['cost_drag_pct']:.2f}%) · "
          f"tax ₹{result.cost_summary['cumulative_tax']:,.0f} "
          f"({result.cost_summary['tax_drag_pct']:.2f}%) · {len(result.ledger)} trades")
    print(f"  holdings: {len(result.positions)} names · "
          f"liquidation {result.liquidation_schedule['days_to_exit'].min()}–"
          f"{result.liquidation_schedule['days_to_exit'].max()} days")

    # persist (backup first)
    PNL_DIR.mkdir(parents=True, exist_ok=True)
    _backup([PNL_DIR / "nav_history.parquet", PNL_DIR / "master_ledger.parquet",
             PNL_DIR / "current_positions.parquet"])

    nav.to_parquet(PNL_DIR / "nav_history.parquet", index=False)
    result.positions.to_parquet(PNL_DIR / "current_positions.parquet", index=False)
    result.ledger.to_parquet(PNL_DIR / "master_ledger.parquet", index=False)
    result.liquidation_schedule.to_parquet(PNL_DIR / "liquidation_schedule.parquet", index=False)
    (PNL_DIR / "paper_fund_summary.json").write_text(json.dumps({
        "metrics": m, "costs": result.cost_summary,
        "as_of": m.get("as_of"), "generated_at": datetime.now().isoformat(),
    }, indent=2, default=str))

    # Regenerate exposure_history FROM the one truth (daily equity exposure =
    # (NAV - cash) / NAV). The old artifact was a single stale row (audit M1).
    exposure = pd.DataFrame({
        "date": nav["date"],
        "actual_exposure": ((nav["nav_combined"] - nav["net_cash_position"]) / nav["nav_combined"]).clip(0, 1),
    })
    exp_path = PROJECT_ROOT / "data/processed/exposure_history.parquet"
    _backup([exp_path])
    exposure.to_parquet(exp_path, index=False)

    # Regenerate the legacy shadow-P&L series FROM the one truth so every
    # NAV/P&L surface in the dashboard agrees (no more four stale sources).
    shadow = pd.DataFrame({
        "date": nav["date"], "timestamp": nav["date"],
        "daily_return": nav["daily_return"], "daily_pnl": nav["nav_combined"].diff().fillna(0.0),
        "portfolio_value": nav["nav_combined"], "cash": nav["net_cash_position"],
    })
    shadow_path = PROJECT_ROOT / "data/processed/shadow_pnl_series.parquet"
    _backup([shadow_path])
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow.to_parquet(shadow_path, index=False)

    # Regenerate execution_quality.parquet as a REAL daily series from the
    # fund's own trades (each fill now carries its slippage_bps). The old
    # artifact was a single dead row from March, all zeros — the "Average
    # Slippage (bps)" chart legitimately had nothing to plot.
    if "slippage_bps" in result.ledger.columns and not result.ledger.empty:
        led = result.ledger.copy()
        led["trade_date"] = pd.to_datetime(led["trade_date"]).dt.normalize()
        led["slippage_inr"] = led["slippage_bps"] / 10_000.0 * led["notional"].abs()
        exec_quality = (led.groupby("trade_date")
                        .agg(avg_slippage_bps=("slippage_bps", "mean"),
                             total_slippage_inr=("slippage_inr", "sum"),
                             trade_count=("slippage_bps", "count"))
                        .reset_index().rename(columns={"trade_date": "date"}))
        exec_quality["implementation_shortfall_bps"] = exec_quality["avg_slippage_bps"]
        exec_quality["fill_rate"] = 1.0
        exec_quality["partial_fills"] = 0
        exec_quality["unfilled_count"] = 0
        exec_path = PNL_DIR / "execution_quality.parquet"
        _backup([exec_path])
        exec_quality.to_parquet(exec_path, index=False)
        print(f"  ✓ execution_quality regenerated: {len(exec_quality)} trading days, "
              f"avg slippage {exec_quality['avg_slippage_bps'].mean():.1f}bps")

    _update_state(result, engine.starting_capital)
    # NOTE: the benchmark is now owned by scripts/update_benchmark_nifty.py
    # (real ^NSEI levels, daily cadence). The old return-chaining consolidation
    # here silently INFLATED NIFTY (+21% vs the true -3%) by chaining a
    # rebased side series' returns — retired after the 2026-07-06 audit.
    print("  ✓ wrote nav_history, current_positions, master_ledger, summary, state")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
