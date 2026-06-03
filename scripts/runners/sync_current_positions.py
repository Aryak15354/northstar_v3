#!/usr/bin/env python3
"""
Sync portfolio and trade-awareness artifacts from canonical runtime sources.

Outputs:
- data/portfolio/current_positions.json
- data/processed/current_holdings.parquet
- data/processed/rebalance_trades.parquet
- data/processed/options_trade_history.parquet
- data/processed/portfolio_sentiment_watchlist.json
- data/processed/unified_portfolio.parquet

It also refreshes the canonical `portfolio` section in unified_state.json so the
dashboard and downstream operators stop reading stale or empty position state.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
from src.pnl.nav_calculator import NAVCalculator


WEIGHTS_PATH = PROJECT_ROOT / "data/processed/portfolio_weights.parquet"
PRICES_PATH = PROJECT_ROOT / "data/processed/prices.parquet"
RUNTIME_PATH = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
OPTIONS_DASHBOARD_PATH = PROJECT_ROOT / "data/options/live/options_dashboard_state.json"
PNL_PATH = PROJECT_ROOT / "data/portfolio/pnl_on_paper.parquet"
NAV_HISTORY_PATH = PROJECT_ROOT / "data/pnl/nav_history.parquet"
STATE_PATH = PROJECT_ROOT / "data/state/unified_state.json"
PORTFOLIO_ANALYTICS_PATH = PROJECT_ROOT / "data/processed/portfolio_analytics.json"
RUNTIME_DB_PATH = PROJECT_ROOT / "data/runtime/portfolio_runtime.db"
OPTIONS_TRADE_LEDGER_PATH = PROJECT_ROOT / "data/options/trade_ledger.parquet"
MASTER_LEDGER_PATH = PROJECT_ROOT / "data/pnl/master_ledger.parquet"

CURRENT_POSITIONS_JSON_PATH = PROJECT_ROOT / "data/portfolio/current_positions.json"
CURRENT_HOLDINGS_PATH = PROJECT_ROOT / "data/processed/current_holdings.parquet"
REBALANCE_TRADES_PATH = PROJECT_ROOT / "data/processed/rebalance_trades.parquet"
OPTIONS_TRADE_HISTORY_PATH = PROJECT_ROOT / "data/processed/options_trade_history.parquet"
PORTFOLIO_TRADE_BLOTTER_PATH = PROJECT_ROOT / "data/processed/portfolio_trade_blotter.parquet"
PORTFOLIO_SENTIMENT_WATCHLIST_PATH = PROJECT_ROOT / "data/processed/portfolio_sentiment_watchlist.json"
OPTIONS_RUNTIME_AUDIT_PATH = PROJECT_ROOT / "data/processed/options_runtime_audit.json"
UNIFIED_PORTFOLIO_PATH = PROJECT_ROOT / "data/processed/unified_portfolio.parquet"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        out = float(v)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _safe_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _safe_json_loads(value: Any, default: Any) -> Any:
    if isinstance(value, type(default)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return default
        return parsed if isinstance(parsed, type(default)) else default
    return default


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def _base_symbol(ticker: Any) -> str:
    raw = str(ticker or "").strip().upper()
    if raw.endswith(".NS"):
        raw = raw[:-3]
    return raw


def _canonical_total_value() -> float | None:
    min_meaningful_inr = 100_000.0
    state = _safe_json(STATE_PATH)
    if state:
        governor = state.get("governor_state") or {}
        pnl_state = state.get("pnl_state") or {}
        portfolio = state.get("portfolio") or {}
        for candidate in (
            governor.get("total_capital_inr"),
            pnl_state.get("current_nav_inr"),
            portfolio.get("total_value"),
        ):
            value = _safe_float(candidate, default=np.nan)
            if np.isfinite(value) and value >= min_meaningful_inr:
                return float(value)

    analytics = _safe_json(PORTFOLIO_ANALYTICS_PATH)
    if analytics:
        summary = analytics.get("portfolio_summary") or {}
        for candidate in (
            summary.get("total_capital_inr"),
            summary.get("portfolio_value"),
            summary.get("current_nav_inr"),
        ):
            value = _safe_float(candidate, default=np.nan)
            if np.isfinite(value) and value >= min_meaningful_inr:
                return float(value)
    return None


def _load_total_value(default_capital: float) -> float:
    canonical_value = _canonical_total_value()
    if canonical_value is not None:
        return float(canonical_value)

    runtime = _safe_json(RUNTIME_PATH)
    net_equity = _safe_float(runtime.get("net_equity"), default=np.nan)
    if np.isfinite(net_equity) and net_equity > 0 and net_equity >= default_capital * 0.25:
        return float(net_equity)

    if NAV_HISTORY_PATH.exists():
        try:
            nav_df = pd.read_parquet(NAV_HISTORY_PATH)
            if not nav_df.empty:
                latest = nav_df.iloc[-1]
                for candidate in ("nav_combined", "nav", "current_nav", "nav_per_unit"):
                    value = _safe_float(latest.get(candidate), default=np.nan)
                    if np.isfinite(value) and value >= 100_000.0:
                        return float(value)
        except Exception:
            pass

    if PNL_PATH.exists():
        try:
            pnl_df = pd.read_parquet(PNL_PATH)
            if not pnl_df.empty and "Equity" in pnl_df.columns:
                eq = pd.to_numeric(pnl_df["Equity"], errors="coerce").dropna()
                if not eq.empty and float(eq.iloc[-1]) > 0:
                    latest_equity = float(eq.iloc[-1])
                    if latest_equity <= 10.0:
                        return float(latest_equity * default_capital)
                    return latest_equity
        except Exception:
            pass

    return float(default_capital)


def _load_latest_prices() -> pd.DataFrame:
    if not PRICES_PATH.exists():
        return pd.DataFrame(columns=["ticker", "Close"])
    p = pd.read_parquet(PRICES_PATH)
    if p.empty or "ticker" not in p.columns:
        return pd.DataFrame(columns=["ticker", "Close"])
    date_col = "Date" if "Date" in p.columns else ("date" if "date" in p.columns else None)
    if date_col is None:
        return pd.DataFrame(columns=["ticker", "Close"])
    p[date_col] = pd.to_datetime(p[date_col], errors="coerce")
    p["Close"] = pd.to_numeric(p.get("Close"), errors="coerce")
    p = p.dropna(subset=["ticker", date_col, "Close"]).sort_values(date_col)
    if p.empty:
        return pd.DataFrame(columns=["ticker", "Close"])
    return p.groupby("ticker", as_index=False).tail(1)[["ticker", "Close"]]


def _load_daily_return_pct() -> float:
    if not PNL_PATH.exists():
        return 0.0
    try:
        pnl_df = pd.read_parquet(PNL_PATH)
        if pnl_df.empty:
            return 0.0
        if "Return" in pnl_df.columns:
            series = pd.to_numeric(pnl_df["Return"], errors="coerce").dropna()
            if not series.empty:
                return float(series.iloc[-1] * 100.0)
    except Exception:
        return 0.0
    return 0.0


def _load_weights_metadata() -> pd.DataFrame:
    if not WEIGHTS_PATH.exists():
        return pd.DataFrame(columns=["ticker", "Company Name", "Industry", "position_role"])
    try:
        wdf = pd.read_parquet(WEIGHTS_PATH)
    except Exception:
        return pd.DataFrame(columns=["ticker", "Company Name", "Industry", "position_role"])

    if wdf.empty:
        return pd.DataFrame(columns=["ticker", "Company Name", "Industry", "position_role"])
    if "ticker" not in wdf.columns:
        if "symbol" in wdf.columns:
            wdf["ticker"] = wdf["symbol"].astype(str)
        else:
            return pd.DataFrame(columns=["ticker", "Company Name", "Industry", "position_role"])

    out = wdf.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")
        out = out.sort_values("date", na_position="last")

    company_col = "Company Name" if "Company Name" in out.columns else ("company_name" if "company_name" in out.columns else None)
    industry_col = "Industry" if "Industry" in out.columns else ("sector" if "sector" in out.columns else None)
    role_col = "position_role" if "position_role" in out.columns else None

    out = out.groupby("ticker", as_index=False).tail(1).copy()
    out["Company Name"] = out[company_col].astype(str) if company_col is not None else out["ticker"].astype(str)
    out["Industry"] = out[industry_col].fillna("Unknown").astype(str) if industry_col is not None else "Unknown"
    out["position_role"] = out[role_col].fillna("Core").astype(str) if role_col is not None else "Core"
    return out[["ticker", "Company Name", "Industry", "position_role"]]


def _load_weights_frame() -> pd.DataFrame:
    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"Missing portfolio weights: {WEIGHTS_PATH}")

    wdf = pd.read_parquet(WEIGHTS_PATH)
    if wdf.empty:
        raise RuntimeError("portfolio_weights.parquet is empty")

    if "ticker" not in wdf.columns:
        if "symbol" in wdf.columns:
            wdf["ticker"] = wdf["symbol"].astype(str)
        else:
            raise RuntimeError("portfolio_weights missing ticker/symbol columns")

    if "weight" not in wdf.columns:
        if "final_weight" in wdf.columns:
            wdf["weight"] = pd.to_numeric(wdf["final_weight"], errors="coerce")
        elif "exposure" in wdf.columns:
            wdf["weight"] = pd.to_numeric(wdf["exposure"], errors="coerce")
        else:
            raise RuntimeError("portfolio_weights missing weight/final_weight/exposure columns")

    wdf["weight"] = pd.to_numeric(wdf["weight"], errors="coerce").fillna(0.0)
    wdf = wdf[wdf["weight"].abs() > 1e-9].copy()
    if wdf.empty:
        raise RuntimeError("No non-zero positions found in portfolio_weights")

    if "date" in wdf.columns:
        wdf["date"] = pd.to_datetime(wdf["date"], errors="coerce")
    return wdf


def _build_holdings_frame(wdf: pd.DataFrame, total_value: float) -> pd.DataFrame:
    prices = _load_latest_prices()
    working = wdf.copy()
    working["ticker"] = working["ticker"].astype(str)
    if not prices.empty:
        working = working.merge(prices, on="ticker", how="left")
    else:
        working["Close"] = np.nan

    working["current_price"] = pd.to_numeric(working.get("Close"), errors="coerce")
    working["market_value"] = pd.to_numeric(working["weight"], errors="coerce").clip(lower=0.0) * float(total_value)
    working["quantity"] = np.where(
        pd.to_numeric(working["current_price"], errors="coerce").fillna(0.0) > 0.0,
        working["market_value"] / pd.to_numeric(working["current_price"], errors="coerce").replace(0, np.nan),
        0.0,
    )
    working["avg_price"] = working["current_price"].fillna(0.0)
    working["symbol"] = working.get("symbol", working["ticker"]).astype(str)
    working["Company Name"] = working.get("Company Name", working["ticker"]).astype(str)
    working["Industry"] = working.get("Industry", working.get("sector", "Unknown")).fillna("Unknown")
    working["position_role"] = working.get("position_role", "Core").fillna("Core")
    working["ticker_base"] = working["ticker"].map(_base_symbol)
    working["weight"] = pd.to_numeric(working["weight"], errors="coerce").fillna(0.0)
    working = working.sort_values("weight", ascending=False).reset_index(drop=True)
    return working


def _load_runtime_holdings_frame() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    empty = pd.DataFrame(
        columns=[
            "ticker",
            "symbol",
            "quantity",
            "avg_price",
            "current_price",
            "market_value",
            "weight",
            "Company Name",
            "Industry",
            "position_role",
            "ticker_base",
        ]
    )
    if not RUNTIME_DB_PATH.exists():
        return empty, {"source": "weights", "reason": "runtime_db_missing"}

    con = sqlite3.connect(RUNTIME_DB_PATH)
    try:
        row = con.execute(
            """
            SELECT snapshot_id, event_id, state_json, created_at
            FROM portfolio_snapshots
            ORDER BY snapshot_id DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return empty, {"source": "weights", "reason": "runtime_snapshot_missing"}

    snapshot_id, event_id, state_json, created_at = row
    state = _safe_json_loads(state_json, {})
    holdings = state.get("holdings") if isinstance(state, dict) else {}
    if not isinstance(holdings, dict) or not holdings:
        return empty, {"source": "weights", "reason": "runtime_holdings_empty"}

    rows: list[dict[str, Any]] = []
    raw_holdings_count = int(len(holdings))
    option_holdings_count = 0
    equity_holdings_count = 0
    for ticker, position in holdings.items():
        if not isinstance(position, dict):
            continue
        instrument_type = str(position.get("instrument_type") or "equity").strip().lower()
        if instrument_type not in {"equity", "cash_equity"}:
            option_holdings_count += 1
            continue
        equity_holdings_count += 1
        quantity = _safe_float(position.get("quantity"))
        if abs(quantity) <= 1e-9:
            continue
        avg_price = _safe_float(position.get("avg_price"))
        last_price = _safe_float(position.get("last_price"), default=avg_price)
        rows.append(
            {
                "ticker": str(ticker),
                "symbol": str(ticker),
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": last_price if last_price > 0 else avg_price,
                "sector": str(position.get("sector") or "Unknown"),
                "strategy_id": str(position.get("strategy_id") or ""),
            }
        )

    if not rows:
        return empty, {
            "source": "runtime_snapshot",
            "reason": "runtime_holdings_filtered_empty",
            "snapshot_id": int(snapshot_id),
            "snapshot_event_id": int(event_id) if event_id is not None else None,
            "snapshot_created_at": str(created_at),
            "raw_holdings_count": raw_holdings_count,
            "option_holdings_count": int(option_holdings_count),
            "equity_holdings_count": int(equity_holdings_count),
            "allow_empty_positions": bool(raw_holdings_count > 0 and equity_holdings_count == 0),
        }

    holdings_df = pd.DataFrame(rows)
    prices = _load_latest_prices()
    if not prices.empty:
        holdings_df = holdings_df.merge(prices.rename(columns={"Close": "latest_close"}), on="ticker", how="left")
        holdings_df["current_price"] = pd.to_numeric(holdings_df.get("latest_close"), errors="coerce").fillna(
            pd.to_numeric(holdings_df.get("current_price"), errors="coerce")
        )
        holdings_df = holdings_df.drop(columns=["latest_close"])
    else:
        holdings_df["current_price"] = pd.to_numeric(holdings_df.get("current_price"), errors="coerce").fillna(0.0)

    metadata = _load_weights_metadata()
    if not metadata.empty:
        holdings_df = holdings_df.merge(metadata, on="ticker", how="left")

    holdings_df["market_value"] = pd.to_numeric(holdings_df["quantity"], errors="coerce").fillna(0.0) * pd.to_numeric(
        holdings_df["current_price"], errors="coerce"
    ).fillna(0.0)
    holdings_df["weight"] = 0.0
    if "Company Name" in holdings_df.columns:
        holdings_df["Company Name"] = holdings_df["Company Name"].fillna(holdings_df["ticker"])
    else:
        holdings_df["Company Name"] = holdings_df["ticker"]
    if "Industry" in holdings_df.columns:
        holdings_df["Industry"] = holdings_df["Industry"].fillna(holdings_df.get("sector", "Unknown"))
    else:
        holdings_df["Industry"] = holdings_df.get("sector", "Unknown")
    if "position_role" in holdings_df.columns:
        holdings_df["position_role"] = holdings_df["position_role"].fillna("Executed")
    else:
        holdings_df["position_role"] = "Executed"
    holdings_df["ticker_base"] = holdings_df["ticker"].map(_base_symbol)
    holdings_df = holdings_df.sort_values("market_value", ascending=False).reset_index(drop=True)

    return holdings_df, {
        "source": "runtime_snapshot",
        "snapshot_id": int(snapshot_id),
        "snapshot_event_id": int(event_id) if event_id is not None else None,
        "snapshot_created_at": str(created_at),
        "holdings_count": int(len(holdings_df)),
        "raw_holdings_count": raw_holdings_count,
        "option_holdings_count": int(option_holdings_count),
        "equity_holdings_count": int(equity_holdings_count),
    }


def _load_open_options_market_value(runtime_payload: Dict[str, Any]) -> float:
    total = 0.0
    for position in runtime_payload.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        total += _safe_float(position.get("current_value"))
    return float(total)


def _load_ledger_cash_position(default_capital: float) -> float | None:
    if not MASTER_LEDGER_PATH.exists():
        return None
    try:
        ledger_df = pd.read_parquet(MASTER_LEDGER_PATH)
    except Exception:
        return None
    if ledger_df.empty:
        return float(default_capital)
    has_explicit_funding = False
    if "entry_type" in ledger_df.columns:
        entry_types = ledger_df["entry_type"].astype(str).str.upper()
        has_explicit_funding = bool(
            entry_types.isin(
                NAVCalculator._CASH_IN_ENTRY_TYPES | NAVCalculator._CASH_OUT_ENTRY_TYPES
            ).any()
        )
    cash_flows = ledger_df.apply(NAVCalculator._cash_flow_for_entry, axis=1)
    base_capital = 0.0 if has_explicit_funding else float(default_capital)
    return float(base_capital + pd.to_numeric(cash_flows, errors="coerce").fillna(0.0).sum())


def _rebalance_batch_from_runtime(total_value: float) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if not RUNTIME_DB_PATH.exists():
        return pd.DataFrame(), {}

    con = sqlite3.connect(RUNTIME_DB_PATH)
    try:
        query = """
            select
                pe.event_id as event_id,
                pe.timestamp_utc as timestamp_utc,
                pe.trigger_reason_code as trigger_reason_code,
                pe.strategy_id as strategy_id,
                pe.payload_json as payload_json,
                pe.risk_override_flag as risk_override_flag,
                ef.symbol as ticker,
                ef.side as side,
                ef.filled_qty as filled_qty,
                ef.fill_price as fill_price,
                ef.fill_notional as fill_notional,
                ef.created_at as created_at
            from portfolio_events pe
            join execution_fills ef on ef.event_id = pe.event_id
            where pe.trigger_reason_code = 'rebalance.core.sync'
            order by pe.timestamp_utc desc
        """
        trades = pd.read_sql_query(query, con)
    finally:
        con.close()

    if trades.empty:
        return pd.DataFrame(), {}

    trades["timestamp_utc"] = pd.to_datetime(trades["timestamp_utc"], errors="coerce", utc=True)
    trades["created_at"] = pd.to_datetime(trades["created_at"], errors="coerce", utc=True)
    trades = trades.dropna(subset=["timestamp_utc"]).sort_values("timestamp_utc", ascending=False)
    latest_ts = trades["timestamp_utc"].max()
    cutoff = latest_ts - pd.Timedelta(minutes=5)
    batch = trades.loc[trades["timestamp_utc"] >= cutoff].copy()

    payloads = batch["payload_json"].map(lambda x: json.loads(x) if isinstance(x, str) and x.strip() else {})
    batch["rebalance_reason"] = payloads.map(lambda x: x.get("rebalance_reason", "core_equity_sync"))
    batch["lifecycle_action"] = payloads.map(lambda x: x.get("lifecycle_action", "adjust"))
    batch["sector"] = payloads.map(lambda x: x.get("sector", "Unknown"))
    batch["filled_qty"] = pd.to_numeric(batch["filled_qty"], errors="coerce").fillna(0.0)
    batch["fill_price"] = pd.to_numeric(batch["fill_price"], errors="coerce").fillna(0.0)
    batch["fill_notional"] = pd.to_numeric(batch["fill_notional"], errors="coerce").fillna(0.0)
    batch["turnover_pct"] = np.where(float(total_value) > 0.0, batch["fill_notional"] / float(total_value), 0.0)
    batch["side"] = batch["side"].astype(str).str.lower()
    batch["ticker_base"] = batch["ticker"].map(_base_symbol)

    summary = {
        "last_rebalance_at": latest_ts.isoformat(),
        "trade_count": int(len(batch)),
        "buy_count": int((batch["side"] == "buy").sum()),
        "sell_count": int((batch["side"] == "sell").sum()),
        "gross_notional": float(batch["fill_notional"].sum()),
        "turnover_pct": float(batch["fill_notional"].sum() / max(float(total_value), 1e-9)),
        "reasons": sorted({str(v) for v in batch["rebalance_reason"].dropna().unique()}),
    }
    return batch.reset_index(drop=True), summary


def _load_options_trade_ledger() -> pd.DataFrame:
    if not OPTIONS_TRADE_LEDGER_PATH.exists():
        return pd.DataFrame()
    try:
        ledger = pd.read_parquet(OPTIONS_TRADE_LEDGER_PATH)
    except Exception:
        return pd.DataFrame()
    if ledger.empty:
        return ledger
    if "timestamp" in ledger.columns:
        ledger["timestamp"] = pd.to_datetime(ledger["timestamp"], errors="coerce")
    return ledger.sort_values("timestamp", ascending=False, na_position="last").reset_index(drop=True)


def _runtime_positions_by_id(runtime_payload: Dict[str, Any], dashboard_payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    positions: Dict[str, Dict[str, Any]] = {}
    containers: Iterable[list[dict[str, Any]]] = [
        list(runtime_payload.get("open_positions") or []),
        list(runtime_payload.get("closed_positions") or []),
        list(dashboard_payload.get("active_positions") or []),
        list(dashboard_payload.get("closed_positions") or []),
    ]
    for rows in containers:
        for row in rows:
            if not isinstance(row, dict):
                continue
            position_id = str(row.get("position_id") or "").strip()
            if not position_id or position_id in positions:
                continue
            positions[position_id] = row
    return positions


def _repair_stale_option_lifecycle_from_ledger(
    ledger_df: pd.DataFrame,
    runtime_payload: Dict[str, Any],
) -> Dict[str, Any]:
    open_runtime_count = int(len(runtime_payload.get("open_positions") or []))
    closed_runtime_count = int(len(runtime_payload.get("closed_positions") or []))

    if not RUNTIME_DB_PATH.exists():
        return {
            "timestamp": _utc_now_iso(),
            "runtime_open_positions": open_runtime_count,
            "runtime_closed_positions": closed_runtime_count,
            "ledger_open_positions": 0,
            "ledger_closed_positions": 0,
            "repaired_stale_lifecycle_rows": 0,
            "remaining_open_lifecycle_rows": 0,
            "status": "runtime_db_missing",
        }

    if ledger_df.empty or "trade_id" not in ledger_df.columns:
        return {
            "timestamp": _utc_now_iso(),
            "runtime_open_positions": open_runtime_count,
            "runtime_closed_positions": closed_runtime_count,
            "ledger_open_positions": 0,
            "ledger_closed_positions": 0,
            "repaired_stale_lifecycle_rows": 0,
            "remaining_open_lifecycle_rows": 0,
            "status": "trade_ledger_missing",
        }

    ledger = ledger_df.copy()
    ledger["action"] = ledger.get("action", "").astype(str).str.lower()
    ledger["timestamp"] = pd.to_datetime(ledger.get("timestamp"), errors="coerce", utc=True)
    open_ledger = ledger[ledger["action"] == "open"].copy()
    close_ledger = ledger[ledger["action"] == "close"].copy()
    ledger_open_ids = set(open_ledger["trade_id"].astype(str)) - set(close_ledger["trade_id"].astype(str))

    con = sqlite3.connect(RUNTIME_DB_PATH)
    repaired = 0
    try:
        stale = pd.read_sql_query(
            """
            SELECT
                plc.id AS lifecycle_id,
                plc.position_key AS position_key,
                plc.strategy_id AS strategy_id,
                plc.open_reason AS open_reason,
                plc.created_at AS created_at,
                pe.timestamp_utc AS open_timestamp_utc,
                pe.payload_json AS open_payload_json
            FROM position_lifecycle_table plc
            JOIN portfolio_events pe ON pe.event_id = plc.open_event_id
            WHERE plc.close_event_id IS NULL
            ORDER BY plc.id ASC
            """,
            con,
        )
        duplicate_lifecycle_rows = 0
        if not stale.empty:
            stale["created_at_dt"] = pd.to_datetime(stale["created_at"], errors="coerce", utc=True)
            stale["open_reason_rank"] = np.where(
                stale["open_reason"].astype(str).str.startswith("proposal.runtime"),
                0,
                1,
            )
            stale = stale.sort_values(
                ["position_key", "open_reason_rank", "created_at_dt", "lifecycle_id"],
                ascending=[True, True, True, True],
                na_position="last",
            )
            stale["duplicate_rank"] = stale.groupby("position_key").cumcount()
            duplicate_rows = stale[stale["duplicate_rank"] > 0].copy()
            if not duplicate_rows.empty:
                con.executemany(
                    "DELETE FROM position_lifecycle_table WHERE id = ?",
                    [(int(v),) for v in duplicate_rows["lifecycle_id"].tolist()],
                )
                duplicate_lifecycle_rows = int(len(duplicate_rows))
                stale = stale[stale["duplicate_rank"] == 0].copy()
            stale = stale.drop(
                columns=["created_at_dt", "open_reason_rank", "duplicate_rank"],
                errors="ignore",
            )
        close_events = pd.read_sql_query(
            """
            SELECT
                event_id,
                proposal_id,
                trigger_reason_code,
                timestamp_utc
            FROM portfolio_events
            WHERE event_type = 'ORDER_FILLED'
              AND trigger_reason_code LIKE 'close.%'
            ORDER BY timestamp_utc ASC
            """,
            con,
        )
        if not close_events.empty:
            close_events["timestamp_utc"] = pd.to_datetime(close_events["timestamp_utc"], errors="coerce", utc=True)

        for row in stale.to_dict(orient="records"):
            strategy_id = str(row.get("strategy_id") or "").strip()
            if not strategy_id:
                continue
            open_payload = _safe_json_loads(row.get("open_payload_json"), {})
            instrument_plan = open_payload.get("instrument_plan") or {}
            underlying = str(
                open_payload.get("underlying_symbol")
                or instrument_plan.get("underlying_symbol")
                or ""
            ).strip().upper()
            open_ts = pd.to_datetime(row.get("open_timestamp_utc") or row.get("created_at"), errors="coerce", utc=True)

            candidates = open_ledger[open_ledger["strategy_type"].astype(str) == strategy_id].copy()
            if underlying:
                candidates = candidates[candidates["underlying"].astype(str).str.upper() == underlying]
            if candidates.empty:
                continue
            sort_cols = ["timestamp"]
            if pd.notna(open_ts):
                candidates["time_gap_seconds"] = (candidates["timestamp"] - open_ts).abs().dt.total_seconds()
                candidates = candidates[candidates["time_gap_seconds"] <= 300]
                sort_cols = ["time_gap_seconds", "timestamp"]
            if candidates.empty:
                continue
            candidates = candidates.sort_values(sort_cols, na_position="last")
            trade_id = str(candidates.iloc[0].get("trade_id") or "").strip()
            if not trade_id:
                continue

            close_rows = close_ledger[close_ledger["trade_id"].astype(str) == trade_id].sort_values("timestamp")
            if close_rows.empty:
                continue
            close_row = close_rows.iloc[-1]

            close_match = close_events[
                close_events["proposal_id"].astype(str).str.startswith(f"prop_close_{trade_id}_")
            ]
            if close_match.empty:
                continue
            close_event = close_match.sort_values("timestamp_utc").iloc[-1]
            close_ts = pd.to_datetime(close_event.get("timestamp_utc"), errors="coerce", utc=True)
            if pd.isna(close_ts):
                close_ts = pd.to_datetime(close_row.get("timestamp"), errors="coerce", utc=True)
            if pd.isna(close_ts):
                continue

            created_ts = pd.to_datetime(row.get("created_at"), errors="coerce", utc=True)
            if pd.isna(created_ts):
                created_ts = open_ts
            hold_days = 0.0
            if pd.notna(created_ts):
                hold_days = max(0.0, (close_ts - created_ts).total_seconds() / 86400.0)

            con.execute(
                """
                UPDATE position_lifecycle_table
                SET close_event_id = ?, close_reason = ?, hold_days = ?,
                    realized_pnl = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    int(close_event.get("event_id")),
                    str(close_event.get("trigger_reason_code") or "close.reconciled_from_ledger"),
                    float(hold_days),
                    _safe_float(close_row.get("gross_pnl"), default=_safe_float(close_row.get("net_pnl"))),
                    close_ts.isoformat(),
                    int(row.get("lifecycle_id")),
                ),
            )
            repaired += 1
        con.commit()
        remaining_open = int(
            pd.read_sql_query(
                "SELECT COUNT(*) AS open_count FROM position_lifecycle_table WHERE close_event_id IS NULL",
                con,
            )["open_count"].iloc[0]
        )
    finally:
        con.close()

    status = "ok"
    if int(remaining_open) != int(len(ledger_open_ids)) or int(open_runtime_count) != int(len(ledger_open_ids)):
        status = "mismatch"

    return {
        "timestamp": _utc_now_iso(),
        "runtime_open_positions": open_runtime_count,
        "runtime_closed_positions": closed_runtime_count,
        "ledger_open_positions": int(len(ledger_open_ids)),
        "ledger_closed_positions": int(close_ledger["trade_id"].nunique()),
        "deduplicated_open_lifecycle_rows": int(duplicate_lifecycle_rows),
        "repaired_stale_lifecycle_rows": int(repaired),
        "remaining_open_lifecycle_rows": int(remaining_open),
        "status": status,
    }


def _options_trade_history_fallback(runtime_payload: Dict[str, Any], dashboard_payload: Dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    source_rows: Iterable[Tuple[str, list[dict[str, Any]]]] = [
        ("closed", list(runtime_payload.get("closed_positions") or [])),
        ("open", list(runtime_payload.get("open_positions") or [])),
    ]
    if not runtime_payload.get("closed_positions") and dashboard_payload.get("closed_positions"):
        source_rows = [("closed", list(dashboard_payload.get("closed_positions") or [])), *source_rows]
    if not runtime_payload.get("open_positions") and dashboard_payload.get("active_positions"):
        source_rows = list(source_rows) + [("open", list(dashboard_payload.get("active_positions") or []))]

    for status, positions in source_rows:
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            metadata = pos.get("metadata") or {}
            hedging_state = metadata.get("hedging_state") or {}
            rows.append(
                {
                    "status": status,
                    "position_id": pos.get("position_id"),
                    "strategy_type": pos.get("strategy_type"),
                    "underlying": pos.get("underlying"),
                    "entry_time": pos.get("entry_time"),
                    "exit_time": pos.get("exit_time"),
                    "expiry": pos.get("expiry"),
                    "days_held": _safe_float(pos.get("days_held")),
                    "realized_pnl": _safe_float(pos.get("realized_pnl")),
                    "unrealized_pnl": _safe_float(pos.get("unrealized_pnl")),
                    "max_loss": _safe_float(pos.get("max_loss")),
                    "max_profit": _safe_float(pos.get("max_profit")),
                    "entry_credit_debit": _safe_float(pos.get("entry_credit_debit")),
                    "current_value": _safe_float(pos.get("current_value")),
                    "exit_reason": pos.get("exit_reason"),
                    "objective": metadata.get("objective") or hedging_state.get("objective"),
                    "reason": metadata.get("reason"),
                    "portfolio_objective": hedging_state.get("portfolio_objective"),
                    "hedge_intensity": _safe_float(hedging_state.get("hedge_intensity")),
                    "protected_weight": _safe_float(hedging_state.get("protected_weight")),
                    "protected_symbols_count": int(len(hedging_state.get("protected_symbols") or [])),
                    "delta": _safe_float((pos.get("greeks") or {}).get("delta")),
                    "gamma": _safe_float((pos.get("greeks") or {}).get("gamma")),
                    "theta": _safe_float((pos.get("greeks") or {}).get("theta")),
                    "vega": _safe_float((pos.get("greeks") or {}).get("vega")),
                    "legs_count": int(len(pos.get("legs") or [])),
                }
            )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    for col in ("entry_time", "exit_time", "expiry"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df.sort_values(["entry_time", "exit_time"], ascending=False, na_position="last").reset_index(drop=True)


def _options_trade_history(
    runtime_payload: Dict[str, Any],
    dashboard_payload: Dict[str, Any],
    ledger_df: pd.DataFrame,
) -> pd.DataFrame:
    if ledger_df.empty or "trade_id" not in ledger_df.columns:
        return _options_trade_history_fallback(runtime_payload, dashboard_payload)

    runtime_positions = _runtime_positions_by_id(runtime_payload, dashboard_payload)
    ledger = ledger_df.copy()
    ledger["action"] = ledger.get("action", "").astype(str).str.lower()
    ledger["timestamp"] = pd.to_datetime(ledger.get("timestamp"), errors="coerce")
    rows: list[dict[str, Any]] = []

    for trade_id, group in ledger.groupby("trade_id", sort=False):
        working = group.sort_values("timestamp", na_position="last")
        open_rows = working[working["action"] == "open"]
        close_rows = working[working["action"] == "close"]
        open_row = open_rows.iloc[0] if not open_rows.empty else None
        close_row = close_rows.iloc[-1] if not close_rows.empty else None
        anchor = close_row if close_row is not None else open_row
        if anchor is None:
            continue

        runtime_row = runtime_positions.get(str(trade_id), {})
        metadata = runtime_row.get("metadata") or {}
        hedging_state = metadata.get("hedging_state") or {}
        anchor_legs = _safe_json_loads(anchor.get("legs"), [])
        exit_greeks = _safe_json_loads(close_row.get("greeks_at_exit") if close_row is not None else None, {})
        entry_greeks = _safe_json_loads(anchor.get("greeks_at_entry"), {})
        greeks = exit_greeks or entry_greeks

        rows.append(
            {
                "status": "closed" if close_row is not None else "open",
                "position_id": str(trade_id),
                "strategy_type": anchor.get("strategy_type"),
                "underlying": anchor.get("underlying"),
                "entry_time": open_row.get("timestamp") if open_row is not None else pd.NaT,
                "exit_time": close_row.get("timestamp") if close_row is not None else pd.NaT,
                "expiry": anchor.get("expiry"),
                "days_held": _safe_float(close_row.get("days_held") if close_row is not None else open_row.get("days_held")),
                "realized_pnl": _safe_float(close_row.get("net_pnl") if close_row is not None else runtime_row.get("realized_pnl")),
                "gross_pnl": _safe_float(close_row.get("gross_pnl") if close_row is not None else runtime_row.get("realized_pnl")),
                "unrealized_pnl": _safe_float(runtime_row.get("unrealized_pnl")),
                "max_loss": _safe_float(anchor.get("max_loss")),
                "max_profit": _safe_float(anchor.get("max_profit")),
                "entry_credit_debit": _safe_float(anchor.get("entry_credit_debit")),
                "current_value": _safe_float(close_row.get("exit_value") if close_row is not None else runtime_row.get("current_value")),
                "exit_reason": close_row.get("exit_reason") if close_row is not None else runtime_row.get("exit_reason"),
                "objective": metadata.get("objective") or hedging_state.get("objective"),
                "reason": metadata.get("reason"),
                "portfolio_objective": hedging_state.get("portfolio_objective"),
                "hedge_intensity": _safe_float(hedging_state.get("hedge_intensity")),
                "protected_weight": _safe_float(hedging_state.get("protected_weight")),
                "protected_symbols_count": int(len(hedging_state.get("protected_symbols") or [])),
                "delta": _safe_float(greeks.get("delta")),
                "gamma": _safe_float(greeks.get("gamma")),
                "theta": _safe_float(greeks.get("theta")),
                "vega": _safe_float(greeks.get("vega")),
                "legs_count": int(len(anchor_legs)),
            }
        )

    if not rows:
        return _options_trade_history_fallback(runtime_payload, dashboard_payload)

    df = pd.DataFrame(rows)
    for col in ("entry_time", "exit_time", "expiry"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df.sort_values(["entry_time", "exit_time"], ascending=False, na_position="last").reset_index(drop=True)


def _portfolio_trade_blotter() -> pd.DataFrame:
    if not RUNTIME_DB_PATH.exists():
        return pd.DataFrame()

    con = sqlite3.connect(RUNTIME_DB_PATH)
    try:
        trades = pd.read_sql_query(
            """
            SELECT
                pe.event_id AS event_id,
                pe.timestamp_utc AS timestamp_utc,
                pe.event_type AS event_type,
                pe.proposal_id AS proposal_id,
                pe.trigger_reason_code AS trigger_reason_code,
                pe.strategy_id AS strategy_id,
                pe.origin AS origin,
                pe.runtime_scope AS runtime_scope,
                pe.payload_json AS payload_json,
                ef.symbol AS symbol,
                ef.side AS side,
                ef.filled_qty AS filled_qty,
                ef.fill_price AS fill_price,
                ef.fill_notional AS fill_notional,
                ef.created_at AS created_at
            FROM portfolio_events pe
            JOIN execution_fills ef ON ef.event_id = pe.event_id
            ORDER BY pe.timestamp_utc DESC
            """,
            con,
        )
    finally:
        con.close()

    if trades.empty:
        return trades

    trades["timestamp_utc"] = pd.to_datetime(trades["timestamp_utc"], errors="coerce", utc=True)
    trades["created_at"] = pd.to_datetime(trades["created_at"], errors="coerce", utc=True)
    payloads = trades["payload_json"].map(lambda value: _safe_json_loads(value, {}))
    instrument_plans = payloads.map(lambda payload: payload.get("instrument_plan") if isinstance(payload, dict) else {})
    trades["asset_class"] = np.where(trades["symbol"].astype(str).str.startswith("OPT::"), "options", "equity")
    trades["lifecycle_action"] = payloads.map(lambda payload: payload.get("lifecycle_action") or "")
    trades["objective"] = payloads.map(lambda payload: payload.get("objective") or "")
    trades["underlying_symbol"] = instrument_plans.map(lambda plan: plan.get("underlying_symbol") if isinstance(plan, dict) else "")
    trades["sector"] = payloads.map(lambda payload: payload.get("sector") or "")
    trades["rebalance_reason"] = payloads.map(lambda payload: payload.get("rebalance_reason") or "")
    core_sync_mask = (
        trades["strategy_id"].astype(str).eq("hedge_fund_core_book")
        | trades["trigger_reason_code"].astype(str).eq("rebalance.core.sync")
        | trades["rebalance_reason"].astype(str).eq("core_equity_sync")
    )
    if "origin" in trades.columns:
        trades["origin_raw"] = trades["origin"]
        trades.loc[core_sync_mask, "origin"] = "research"
    trades["execution_bucket"] = np.where(
        core_sync_mask,
        "core_book_rebalance",
        np.where(
            trades["asset_class"].astype(str).eq("options"),
            "options_overlay",
            "other",
        ),
    )
    return trades.reset_index(drop=True)


def _portfolio_sentiment_watchlist(
    holdings_df: pd.DataFrame,
    runtime_payload: Dict[str, Any],
    dashboard_payload: Dict[str, Any],
) -> Dict[str, Any]:
    overlay = (dashboard_payload.get("portfolio_overlay") or runtime_payload.get("portfolio_overlay") or {})
    sentiment_snapshot = overlay.get("sentiment_snapshot") or {}

    negative_names = {_base_symbol(item) for item in sentiment_snapshot.get("negative_trending_companies") or []}
    impact_rows = sentiment_snapshot.get("event_company_impacts") or []
    impact_map = {
        _base_symbol(row.get("ticker")): row
        for row in impact_rows
        if isinstance(row, dict) and row.get("ticker")
    }
    selected_rows = {
        _base_symbol(row.get("ticker")): row
        for row in overlay.get("selected_stock_rows") or []
        if isinstance(row, dict) and row.get("ticker")
    }

    protected_symbols = set()
    for pos in list(runtime_payload.get("open_positions") or []) + list(runtime_payload.get("closed_positions") or []):
        metadata = pos.get("metadata") or {}
        hedging_state = metadata.get("hedging_state") or {}
        protected_symbols.update({_base_symbol(item) for item in hedging_state.get("protected_symbols") or []})

    watch_rows: list[dict[str, Any]] = []
    for row in holdings_df.to_dict(orient="records"):
        base = _base_symbol(row.get("ticker"))
        impact = impact_map.get(base) or {}
        selected = selected_rows.get(base) or {}
        if base not in negative_names and not impact and not selected:
            continue
        watch_rows.append(
            {
                "ticker": row.get("ticker"),
                "symbol": row.get("symbol"),
                "company_name": row.get("Company Name"),
                "sector": row.get("Industry"),
                "weight": _safe_float(row.get("weight")),
                "market_value": _safe_float(row.get("market_value")),
                "position_role": row.get("position_role"),
                "objective": selected.get("objective"),
                "reason": selected.get("reason"),
                "sentiment_label": impact.get("impact_direction") or selected.get("sentiment_label"),
                "impact_score": _safe_float(impact.get("impact_score")),
                "hedged_or_protected": base in protected_symbols,
            }
        )

    watch_rows.sort(key=lambda item: (_safe_float(item.get("impact_score")), _safe_float(item.get("weight"))), reverse=True)
    return {
        "timestamp": _utc_now_iso(),
        "portfolio_objective": overlay.get("portfolio_objective"),
        "hedge_intensity": _safe_float(overlay.get("hedge_intensity")),
        "held_positions_total": int(len(holdings_df)),
        "held_positions_under_pressure": watch_rows,
        "negative_trending_company_total": int(len(negative_names)),
        "protected_symbol_count": int(len(protected_symbols)),
    }


def _refresh_unified_portfolio_artifact(holdings_df: pd.DataFrame, timestamp: str) -> pd.DataFrame:
    if holdings_df.empty:
        return holdings_df

    out = holdings_df.copy()
    out["date"] = pd.to_datetime(timestamp, errors="coerce").normalize()
    out["allocation_timestamp"] = timestamp
    out["final_weight"] = pd.to_numeric(out.get("final_weight", out.get("weight")), errors="coerce")
    out["suggested_weight"] = pd.to_numeric(out.get("suggested_weight", out.get("weight")), errors="coerce")
    out["sector"] = out.get("sector", out.get("Industry"))
    _atomic_write_parquet(out, UNIFIED_PORTFOLIO_PATH)
    return out


def _sync_portfolio_state(
    payload: Dict[str, Any],
    holdings_df: pd.DataFrame,
    runtime_payload: Dict[str, Any],
    rebalance_summary: Dict[str, Any],
) -> None:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass

    authority = StateAuthority(
        state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="current_positions_sync",
        allowed_sections=["portfolio", "capital", "pnl_state", "governor_state"],
        priority=WritePriority.RESEARCH,
    )

    max_weight = float(pd.to_numeric(holdings_df["weight"], errors="coerce").fillna(0.0).max()) if not holdings_df.empty else 0.0
    options_positions = {
        str(pos.get("position_id") or f"open_{idx}"): pos
        for idx, pos in enumerate(runtime_payload.get("open_positions") or [])
        if isinstance(pos, dict)
    }
    latest_ts = payload.get("timestamp")
    state_ts = pd.to_datetime(latest_ts, errors="coerce", utc=True)
    state_dt = state_ts.to_pydatetime() if not pd.isna(state_ts) else None
    current_total_value = _safe_float(payload.get("total_value"))
    governor_state = getattr(state, "governor_state", None)
    equity_fraction = _safe_float(getattr(governor_state, "equity_fraction", 0.0), 0.0)
    options_fraction = _safe_float(getattr(governor_state, "options_fraction", 0.0), 0.0)
    cash_fraction = _safe_float(getattr(governor_state, "cash_fraction", 0.0), 0.0)

    updates = [
        ("portfolio", "total_positions", int(len(holdings_df))),
        ("portfolio", "position_count", int(len(holdings_df))),
        ("portfolio", "long_positions", int(len(holdings_df))),
        ("portfolio", "short_positions", 0),
        ("portfolio", "total_exposure", _safe_float(payload.get("invested_value")) / max(_safe_float(payload.get("total_value")), 1e-9)),
        ("portfolio", "max_position", max_weight),
        ("portfolio", "largest_position_pct", max_weight),
        ("portfolio", "sector_exposure", payload.get("sector_allocation") or {}),
        ("portfolio", "sector_allocation", payload.get("sector_allocation") or {}),
        ("portfolio", "max_sector_exposure", max((payload.get("sector_allocation") or {}).values(), default=0.0)),
        ("portfolio", "positions", payload.get("positions") or {}),
        ("portfolio", "total_value", _safe_float(payload.get("total_value"))),
        ("portfolio", "cash", _safe_float(payload.get("cash"))),
        ("portfolio", "invested_value", _safe_float(payload.get("invested_value"))),
        ("portfolio", "total_pnl", _safe_float(((payload.get("performance") or {}).get("total_pnl"))),
        ),
        ("portfolio", "total_return_pct", _safe_float(((payload.get("performance") or {}).get("total_return_pct")))),
        ("portfolio", "daily_return_pct", _safe_float(((payload.get("performance") or {}).get("daily_return_pct")))),
        ("portfolio", "options_positions", options_positions),
        ("portfolio", "options_position_count", int(len(options_positions))),
        ("portfolio", "options_net_delta", _safe_float((runtime_payload.get("latest_cycle_diagnostics") or {}).get("portfolio_delta"))),
        ("portfolio", "options_net_gamma", _safe_float((runtime_payload.get("latest_cycle_diagnostics") or {}).get("portfolio_gamma"))),
        ("portfolio", "options_net_theta", _safe_float((runtime_payload.get("latest_cycle_diagnostics") or {}).get("portfolio_theta"))),
        ("portfolio", "options_net_vega", _safe_float((runtime_payload.get("latest_cycle_diagnostics") or {}).get("portfolio_vega"))),
        ("portfolio", "options_unrealized_pnl", _safe_float(runtime_payload.get("unrealized_pnl"))),
        ("portfolio", "options_system_mode", runtime_payload.get("current_mode") or "UNKNOWN"),
        ("portfolio", "last_updated", latest_ts),
        ("pnl_state", "current_nav_inr", current_total_value),
        ("pnl_state", "last_updated", state_dt),
        ("governor_state", "total_capital_inr", current_total_value),
        ("governor_state", "equity_budget_inr", current_total_value * equity_fraction),
        ("governor_state", "options_budget_inr", current_total_value * options_fraction),
        ("governor_state", "cash_reserve_inr", current_total_value * cash_fraction),
        ("governor_state", "last_intraday_check", state_dt),
    ]
    if rebalance_summary.get("last_rebalance_at"):
        updates.append(("capital", "last_rebalance", rebalance_summary["last_rebalance_at"]))

    state_updates = [
        StateUpdate(
            writer_id="current_positions_sync",
            section=section,
            field_path=field_path,
            new_value=value,
            priority=WritePriority.RESEARCH,
            source="SYSTEM",
            reason="Current positions and rebalance sync",
        )
        for section, field_path, value in updates
    ]
    authority.batch_update(state_updates)
    authority.checkpoint(force=True)


def build_current_positions(default_capital: float = 10_000_000.0) -> Tuple[Dict[str, Any], pd.DataFrame]:
    runtime_payload = _safe_json(RUNTIME_PATH)
    runtime_holdings_df, runtime_meta = _load_runtime_holdings_frame()

    if runtime_holdings_df.empty:
        reason = str(runtime_meta.get("reason") or "runtime_holdings_unavailable")
        options_only_runtime = bool(runtime_meta.get("allow_empty_positions"))
        if not options_only_runtime:
            open_options = list(runtime_payload.get("open_positions") or [])
            options_only_runtime = (
                reason == "runtime_holdings_filtered_empty"
                and len(open_options) > 0
            )
        if not options_only_runtime:
            raise RuntimeError(
                "Runtime holdings unavailable; refusing weights fallback "
                f"(reason={reason})"
            )

    holdings_df = runtime_holdings_df.copy()
    invested_value = float(pd.to_numeric(holdings_df["market_value"], errors="coerce").fillna(0.0).sum())
    options_market_value = _load_open_options_market_value(runtime_payload)
    ledger_cash = _load_ledger_cash_position(default_capital=default_capital)
    if ledger_cash is not None:
        cash = float(ledger_cash)
        total_value = float(cash + invested_value + options_market_value)
    else:
        total_value = _load_total_value(default_capital=default_capital)
        cash = float(max(0.0, total_value - invested_value - options_market_value))
    holdings_df["weight"] = np.where(
        float(total_value) > 0.0,
        pd.to_numeric(holdings_df["market_value"], errors="coerce").fillna(0.0) / float(total_value),
        0.0,
    )
    position_source = str(runtime_meta.get("source") or "runtime_snapshot")
    if holdings_df.empty and bool(runtime_meta.get("allow_empty_positions")):
        position_source = f"{position_source}_options_only"

    positions: Dict[str, Dict[str, Any]] = {}
    sector_allocation: Dict[str, float] = {}
    for row in holdings_df.to_dict(orient="records"):
        ticker = str(row.get("ticker"))
        sector = str(row.get("Industry") or "Unknown")
        weight = _safe_float(row.get("weight"))
        positions[ticker] = {
            "symbol": ticker,
            "quantity": _safe_float(row.get("quantity")),
            "avg_price": _safe_float(row.get("avg_price")),
            "current_price": _safe_float(row.get("current_price")),
            "market_value": _safe_float(row.get("market_value")),
            "unrealized_pnl": 0.0,
            "weight": weight,
            "sector": sector,
            "company_name": row.get("Company Name"),
            "position_role": row.get("position_role"),
        }
        sector_allocation[sector] = sector_allocation.get(sector, 0.0) + max(0.0, weight)

    daily_return_pct = _load_daily_return_pct()
    total_return_pct = 0.0
    if PNL_PATH.exists():
        try:
            pnl_df = pd.read_parquet(PNL_PATH)
            eq = pd.to_numeric(pnl_df.get("Equity"), errors="coerce").dropna()
            if len(eq) >= 2 and float(eq.iloc[0]) > 0:
                total_return_pct = float((eq.iloc[-1] / eq.iloc[0] - 1.0) * 100.0)
        except Exception:
            total_return_pct = 0.0

    snapshot_ts = _utc_now_iso()
    payload = {
        "timestamp": snapshot_ts,
        "updated_at": snapshot_ts,
        "total_value": total_value,
        "cash": cash,
        "invested_value": invested_value,
        "options_market_value": float(options_market_value),
        "positions_count": int(len(positions)),
        "gross_exposure": float(sum(max(0.0, _safe_float(pos.get("weight"))) for pos in positions.values())),
        "cash_pct": float(cash / total_value) if total_value > 0 else 0.0,
        "invested_pct": float(invested_value / total_value) if total_value > 0 else 0.0,
        "options_pct": float(options_market_value / total_value) if total_value > 0 else 0.0,
        "position_source": position_source,
        "positions": positions,
        "sector_allocation": sector_allocation,
        "performance": {
            "total_pnl": float(total_value - default_capital),
            "total_return_pct": total_return_pct,
            "daily_return_pct": daily_return_pct,
            "volatility_30d": 0.0,
            "sharpe_ratio": 0.0,
        },
    }
    if runtime_meta:
        payload["runtime_snapshot"] = runtime_meta
    return payload, holdings_df


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync current positions and dashboard-friendly history surfaces")
    p.add_argument("--default-capital", type=float, default=10_000_000.0)
    p.add_argument("--output", type=str, default=str(CURRENT_POSITIONS_JSON_PATH))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    payload, holdings_df = build_current_positions(default_capital=float(args.default_capital))

    runtime_payload = _safe_json(RUNTIME_PATH)
    dashboard_payload = _safe_json(OPTIONS_DASHBOARD_PATH)
    ledger_df = _load_options_trade_ledger()
    options_runtime_audit = _repair_stale_option_lifecycle_from_ledger(ledger_df, runtime_payload)
    rebalance_trades_df, rebalance_summary = _rebalance_batch_from_runtime(total_value=_safe_float(payload.get("total_value")))
    options_trade_history_df = _options_trade_history(runtime_payload, dashboard_payload, ledger_df)
    portfolio_trade_blotter_df = _portfolio_trade_blotter()
    watchlist_payload = _portfolio_sentiment_watchlist(holdings_df, runtime_payload, dashboard_payload)

    payload["last_rebalance"] = rebalance_summary
    payload["options_runtime_audit"] = options_runtime_audit
    payload["sentiment_watchlist_summary"] = {
        "held_positions_under_pressure": len(watchlist_payload.get("held_positions_under_pressure") or []),
        "portfolio_objective": watchlist_payload.get("portfolio_objective"),
        "hedge_intensity": watchlist_payload.get("hedge_intensity"),
    }
    latest_trade_timestamp = None
    if not portfolio_trade_blotter_df.empty and "timestamp_utc" in portfolio_trade_blotter_df.columns:
        latest_trade_ts = pd.to_datetime(portfolio_trade_blotter_df["timestamp_utc"], errors="coerce", utc=True).dropna()
        if not latest_trade_ts.empty:
            latest_trade_timestamp = latest_trade_ts.max().isoformat()
    payload["last_rebalance_timestamp"] = rebalance_summary.get("last_rebalance_at") if isinstance(rebalance_summary, dict) else None
    payload["latest_trade_timestamp"] = latest_trade_timestamp
    payload["summary"] = {
        "positions_count": int(payload.get("positions_count", 0)),
        "gross_exposure": _safe_float(payload.get("gross_exposure")),
        "invested_value": _safe_float(payload.get("invested_value")),
        "cash": _safe_float(payload.get("cash")),
        "invested_pct": _safe_float(payload.get("invested_pct")),
        "cash_pct": _safe_float(payload.get("cash_pct")),
        "last_rebalance_at": payload.get("last_rebalance_timestamp"),
        "latest_trade_timestamp": latest_trade_timestamp,
        "last_rebalance_trade_count": int(rebalance_summary.get("trade_count", 0)) if isinstance(rebalance_summary, dict) else 0,
    }

    out_path = Path(args.output)
    _atomic_write_json(out_path, payload)
    _atomic_write_parquet(holdings_df.drop(columns=[c for c in ["ticker_base"] if c in holdings_df.columns]), CURRENT_HOLDINGS_PATH)
    _atomic_write_json(PORTFOLIO_SENTIMENT_WATCHLIST_PATH, watchlist_payload)
    _atomic_write_json(OPTIONS_RUNTIME_AUDIT_PATH, options_runtime_audit)
    if not rebalance_trades_df.empty:
        _atomic_write_parquet(rebalance_trades_df.drop(columns=[c for c in ["ticker_base", "payload_json"] if c in rebalance_trades_df.columns]), REBALANCE_TRADES_PATH)
    if not options_trade_history_df.empty:
        _atomic_write_parquet(options_trade_history_df, OPTIONS_TRADE_HISTORY_PATH)
    if not portfolio_trade_blotter_df.empty:
        _atomic_write_parquet(portfolio_trade_blotter_df.drop(columns=[c for c in ["payload_json"] if c in portfolio_trade_blotter_df.columns]), PORTFOLIO_TRADE_BLOTTER_PATH)
    _refresh_unified_portfolio_artifact(holdings_df, payload["timestamp"])
    _sync_portfolio_state(payload, holdings_df, runtime_payload, rebalance_summary)

    summary = {
        "status": "ok",
        "output": str(out_path),
        "positions": len(payload.get("positions", {})),
        "total_value": payload.get("total_value"),
        "last_rebalance": rebalance_summary,
        "options_closed_positions": int(len(runtime_payload.get("closed_positions") or [])),
        "options_open_positions": int(len(runtime_payload.get("open_positions") or [])),
        "options_runtime_audit": options_runtime_audit,
        "portfolio_trade_blotter_rows": int(len(portfolio_trade_blotter_df)),
        "held_positions_under_pressure": int(len(watchlist_payload.get("held_positions_under_pressure") or [])),
        "timestamp": payload.get("timestamp"),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
