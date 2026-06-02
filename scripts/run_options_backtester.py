#!/usr/bin/env python3
"""
Lightweight options backtester for dashboard integration.

Design goals:
- Works directly on offline option-chain history (Upstox universe artifacts)
- Produces deterministic artifacts consumed by the options dashboard
- Uses a transparent rule-set (hedge / income / opportunity tilt)
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNDERLYINGS = "NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN"


@dataclass
class BacktestConfig:
    underlyings: List[str]
    start_date: Optional[pd.Timestamp]
    end_date: Optional[pd.Timestamp]
    min_dte: int
    max_dte: int
    hold_days: int
    stop_loss_pct: float
    take_profit_pct: float
    transaction_cost_pct: float
    output_dir: Path


def _load_chain(symbol: str) -> pd.DataFrame:
    path = PROJECT_ROOT / "data/options/historical" / f"{symbol.lower()}_option_chains.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    elif "timestamp" in df.columns:
        df["date"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.floor("D")
    else:
        return pd.DataFrame()
    df = df.dropna(subset=["date"])
    if df.empty:
        return pd.DataFrame()

    if "expiry" not in df.columns:
        return pd.DataFrame()
    df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce")
    df = df.dropna(subset=["expiry"])
    if df.empty:
        return pd.DataFrame()

    df["option_type"] = df.get("option_type", "").astype(str).str.upper()
    df["strike"] = pd.to_numeric(df.get("strike"), errors="coerce")
    df["underlying_price"] = pd.to_numeric(df.get("underlying_price"), errors="coerce")
    if "premium" in df.columns:
        df["premium"] = pd.to_numeric(df["premium"], errors="coerce")
    else:
        ltp = pd.to_numeric(df.get("ltp"), errors="coerce")
        bid = pd.to_numeric(df.get("bid"), errors="coerce")
        ask = pd.to_numeric(df.get("ask"), errors="coerce")
        df["premium"] = ltp.where(ltp > 0, (bid + ask) / 2.0)
    df["iv"] = pd.to_numeric(df.get("iv"), errors="coerce")
    df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce").fillna(0.0)
    if "days_to_expiry" in df.columns:
        df["days_to_expiry"] = pd.to_numeric(df["days_to_expiry"], errors="coerce")
    else:
        df["days_to_expiry"] = (df["expiry"] - df["date"]).dt.days
    return df.dropna(subset=["strike", "premium", "underlying_price", "days_to_expiry"])


def _pick_leg(day: pd.DataFrame, strike: float, option_type: str) -> Optional[pd.Series]:
    sub = day[(day["option_type"] == option_type) & (day["strike"] == strike)]
    if sub.empty:
        return None
    sub = sub.sort_values(["volume", "premium"], ascending=[False, False])
    return sub.iloc[0]


def _build_daily_atm_series(
    df: pd.DataFrame,
    min_dte: int,
    max_dte: int,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    if df.empty:
        return pd.DataFrame()

    for trade_date in sorted(df["date"].dt.floor("D").unique()):
        day = df[df["date"].dt.floor("D") == trade_date].copy()
        if day.empty:
            continue
        day = day[(day["days_to_expiry"] >= min_dte) & (day["days_to_expiry"] <= max_dte)]
        if day.empty:
            continue

        expiry = day.sort_values("days_to_expiry").iloc[0]["expiry"]
        day = day[day["expiry"] == expiry].copy()
        if day.empty:
            continue

        spot = float(day["underlying_price"].median())
        strikes = day["strike"].dropna().unique().tolist()
        if not strikes:
            continue
        atm = min(strikes, key=lambda x: abs(float(x) - spot))

        ce = _pick_leg(day, strike=float(atm), option_type="CE")
        pe = _pick_leg(day, strike=float(atm), option_type="PE")
        if ce is None or pe is None:
            continue

        ce_p = float(ce.get("premium", 0.0) or 0.0)
        pe_p = float(pe.get("premium", 0.0) or 0.0)
        if ce_p <= 0 or pe_p <= 0:
            continue

        iv_vals = [
            float(v) for v in [ce.get("iv"), pe.get("iv")] if pd.notna(v)
        ]
        rows.append(
            {
                "date": pd.Timestamp(trade_date).floor("D"),
                "expiry": pd.to_datetime(expiry, errors="coerce"),
                "spot": spot,
                "atm_strike": float(atm),
                "ce_premium": ce_p,
                "pe_premium": pe_p,
                "straddle_premium": ce_p + pe_p,
                "iv": float(np.mean(iv_vals)) if iv_vals else np.nan,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    out["ret_1d"] = out["spot"].pct_change()
    out["ret_3d"] = out["spot"].pct_change(3)
    out["iv_rank"] = (
        out["iv"]
        .rolling(42, min_periods=8)
        .apply(lambda x: float((x <= x.iloc[-1]).mean()), raw=False)
    )
    out["iv_rank"] = out["iv_rank"].fillna(0.5)
    return out


def _generate_trades(
    symbol: str,
    series: pd.DataFrame,
    hold_days: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    transaction_cost_pct: float,
) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    if series.empty:
        return trades

    i = 5
    n = len(series)
    while i < n - 1:
        row = series.iloc[i]
        ret3 = float(row.get("ret_3d", 0.0) or 0.0)
        iv_rank = float(row.get("iv_rank", 0.5) or 0.5)
        entry_price = float(row.get("straddle_premium", 0.0) or 0.0)
        if entry_price <= 0:
            i += 1
            continue

        strategy = None
        side = None
        signal_reason = None
        if ret3 <= -0.018 or (ret3 <= -0.010 and iv_rank <= 0.45):
            strategy = "long_straddle"
            side = "LONG_VOL"
            signal_reason = "portfolio_hedge_downside_or_shock"
        elif iv_rank >= 0.78 and abs(ret3) <= 0.012:
            strategy = "short_straddle"
            side = "SHORT_VOL"
            signal_reason = "income_surface_high_iv_rangebound"

        if strategy is None:
            i += 1
            continue

        entry_date = pd.to_datetime(row["date"], errors="coerce")
        expiry = pd.to_datetime(row["expiry"], errors="coerce")
        if pd.isna(entry_date) or pd.isna(expiry):
            i += 1
            continue

        max_exit_date = min(
            entry_date + timedelta(days=max(1, int(hold_days))),
            expiry - timedelta(days=2),
            pd.to_datetime(series.iloc[-1]["date"], errors="coerce"),
        )
        if pd.isna(max_exit_date) or max_exit_date <= entry_date:
            i += 1
            continue

        window = series.iloc[i + 1 :].copy()
        window = window[pd.to_datetime(window["date"], errors="coerce") <= max_exit_date]
        if window.empty:
            i += 1
            continue

        exit_idx = int(window.index[-1])
        exit_reason = "time_exit"
        exit_price = float(series.loc[exit_idx, "straddle_premium"])

        for idx in window.index:
            px = float(series.loc[idx, "straddle_premium"])
            gross_pnl = (px - entry_price) if side == "LONG_VOL" else (entry_price - px)
            ret = gross_pnl / max(1e-9, entry_price)
            if ret <= -abs(stop_loss_pct):
                exit_idx = int(idx)
                exit_price = px
                exit_reason = "stop_loss"
                break
            if ret >= abs(take_profit_pct):
                exit_idx = int(idx)
                exit_price = px
                exit_reason = "take_profit"
                break

        exit_row = series.loc[exit_idx]
        gross_pnl = (exit_price - entry_price) if side == "LONG_VOL" else (entry_price - exit_price)
        costs = transaction_cost_pct * (entry_price + exit_price)
        net_pnl = gross_pnl - costs
        ret_pct = net_pnl / max(1e-9, entry_price)
        days_held = int((pd.to_datetime(exit_row["date"]) - entry_date).days)

        trades.append(
            {
                "underlying": symbol,
                "strategy": strategy,
                "side": side,
                "signal_reason": signal_reason,
                "entry_time": entry_date,
                "exit_time": pd.to_datetime(exit_row["date"]),
                "expiry": expiry,
                "days_held": max(1, days_held),
                "entry_spot": float(row.get("spot", np.nan)),
                "exit_spot": float(exit_row.get("spot", np.nan)),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_pnl": gross_pnl,
                "costs": costs,
                "net_pnl": net_pnl,
                "return_pct": ret_pct,
                "entry_iv_rank": iv_rank,
                "entry_ret_3d": ret3,
                "exit_reason": exit_reason,
            }
        )
        i = exit_idx + 1

    return trades


def _build_equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["timestamp", "equity", "cumulative_pnl"])
    t = trades.copy()
    t["exit_time"] = pd.to_datetime(t["exit_time"], errors="coerce")
    t = t.dropna(subset=["exit_time"]).sort_values("exit_time")
    t["net_pnl"] = pd.to_numeric(t["net_pnl"], errors="coerce").fillna(0.0)
    t["cumulative_pnl"] = t["net_pnl"].cumsum()
    t["equity"] = 500_000.0 + t["cumulative_pnl"]
    return t[["exit_time", "equity", "cumulative_pnl"]].rename(columns={"exit_time": "timestamp"})


def _summarize(trades: pd.DataFrame) -> Dict[str, Any]:
    if trades.empty:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "avg_return_pct": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "sharpe_like": 0.0,
        }

    pnl = pd.to_numeric(trades["net_pnl"], errors="coerce").fillna(0.0)
    rets = pd.to_numeric(trades["return_pct"], errors="coerce").fillna(0.0)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]

    equity = 500_000.0 + pnl.cumsum()
    hwm = equity.cummax()
    dd = ((equity - hwm) / hwm).fillna(0.0)

    sharpe_like = 0.0
    if rets.std(ddof=1) > 1e-9:
        sharpe_like = float(np.sqrt(252.0) * rets.mean() / rets.std(ddof=1))

    return {
        "total_trades": int(len(trades)),
        "win_rate": float((pnl > 0).mean()),
        "net_pnl": float(pnl.sum()),
        "avg_return_pct": float(rets.mean()),
        "profit_factor": float(wins.sum() / abs(losses.sum())) if not losses.empty else float("inf"),
        "max_drawdown_pct": float(dd.min()),
        "sharpe_like": sharpe_like,
    }


def _write_outputs(
    cfg: BacktestConfig,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    summary: Dict[str, Any],
) -> None:
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    trade_latest = cfg.output_dir / "options_backtest_trades_latest.parquet"
    equity_latest = cfg.output_dir / "options_backtest_equity_latest.parquet"
    summary_latest = cfg.output_dir / "options_backtest_summary_latest.json"
    trade_ts = cfg.output_dir / f"options_backtest_trades_{stamp}.parquet"
    equity_ts = cfg.output_dir / f"options_backtest_equity_{stamp}.parquet"
    summary_ts = cfg.output_dir / f"options_backtest_summary_{stamp}.json"

    trades.to_parquet(trade_latest, index=False)
    trades.to_parquet(trade_ts, index=False)
    equity.to_parquet(equity_latest, index=False)
    equity.to_parquet(equity_ts, index=False)

    payload = {
        **summary,
        "generated_at": datetime.now().isoformat(),
        "underlyings": cfg.underlyings,
        "start_date": str(cfg.start_date.date()) if cfg.start_date is not None else None,
        "end_date": str(cfg.end_date.date()) if cfg.end_date is not None else None,
        "hold_days": int(cfg.hold_days),
        "transaction_cost_pct": float(cfg.transaction_cost_pct),
    }
    summary_latest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary_ts.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline options backtester")
    parser.add_argument("--underlyings", type=str, default=DEFAULT_UNDERLYINGS)
    parser.add_argument("--start-date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="YYYY-MM-DD")
    parser.add_argument("--min-dte", type=int, default=7)
    parser.add_argument("--max-dte", type=int, default=45)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--stop-loss-pct", type=float, default=0.25)
    parser.add_argument("--take-profit-pct", type=float, default=0.35)
    parser.add_argument("--transaction-cost-pct", type=float, default=0.002)
    parser.add_argument("--output-dir", type=str, default="data/options/backtest_reports")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    underlyings = [u.strip().upper() for u in str(args.underlyings).split(",") if u.strip()]

    cfg = BacktestConfig(
        underlyings=underlyings,
        start_date=pd.to_datetime(args.start_date, errors="coerce") if args.start_date else None,
        end_date=pd.to_datetime(args.end_date, errors="coerce") if args.end_date else None,
        min_dte=max(1, int(args.min_dte)),
        max_dte=max(2, int(args.max_dte)),
        hold_days=max(1, int(args.hold_days)),
        stop_loss_pct=abs(float(args.stop_loss_pct)),
        take_profit_pct=abs(float(args.take_profit_pct)),
        transaction_cost_pct=max(0.0, float(args.transaction_cost_pct)),
        output_dir=(PROJECT_ROOT / args.output_dir).resolve(),
    )

    all_trades: List[Dict[str, Any]] = []
    for symbol in cfg.underlyings:
        chain = _load_chain(symbol)
        if chain.empty:
            continue
        if cfg.start_date is not None:
            chain = chain[chain["date"] >= cfg.start_date]
        if cfg.end_date is not None:
            chain = chain[chain["date"] <= cfg.end_date]
        if chain.empty:
            continue

        series = _build_daily_atm_series(chain, min_dte=cfg.min_dte, max_dte=cfg.max_dte)
        trades = _generate_trades(
            symbol=symbol,
            series=series,
            hold_days=cfg.hold_days,
            stop_loss_pct=cfg.stop_loss_pct,
            take_profit_pct=cfg.take_profit_pct,
            transaction_cost_pct=cfg.transaction_cost_pct,
        )
        all_trades.extend(trades)

    trades_df = pd.DataFrame(all_trades)
    if not trades_df.empty:
        trades_df = trades_df.sort_values("exit_time")
    equity_df = _build_equity_curve(trades_df)
    summary = _summarize(trades_df)

    _write_outputs(cfg=cfg, trades=trades_df, equity=equity_df, summary=summary)

    print(
        "Backtest complete | trades={trades} win_rate={win_rate:.1%} net_pnl={net:,.2f}".format(
            trades=int(summary["total_trades"]),
            win_rate=float(summary["win_rate"]),
            net=float(summary["net_pnl"]),
        )
    )
    print(f"Saved artifacts in: {cfg.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
