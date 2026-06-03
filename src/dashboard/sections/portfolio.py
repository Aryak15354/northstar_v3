from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.sections.shared import render_visual_section


def _holdings_frame(bundle: dict) -> pd.DataFrame:
    holdings = bundle.get("current_holdings")
    if isinstance(holdings, pd.DataFrame) and not holdings.empty:
        return holdings.copy()

    payload = bundle.get("current_positions") or {}
    positions = payload.get("positions") or {}
    if isinstance(positions, dict) and positions:
        rows = []
        for ticker, row in positions.items():
            record = {"ticker": ticker}
            if isinstance(row, dict):
                record.update(row)
            rows.append(record)
        return pd.DataFrame(rows)
    return pd.DataFrame()


def _render_live_holdings(bundle: dict) -> None:
    payload = bundle.get("current_positions") or {}
    holdings = _holdings_frame(bundle)

    st.subheader("Live Hedge Fund Holdings")
    if holdings.empty:
        st.info("No live holdings snapshot is available yet.")
        return

    total_value = float(payload.get("total_value", 0.0) or 0.0)
    cash = float(payload.get("cash", 0.0) or 0.0)
    invested = float(payload.get("invested_value", 0.0) or 0.0)
    last_sync = payload.get("updated_at") or payload.get("timestamp", "unknown")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Positions", f"{len(holdings):,d}")
    col2.metric("Invested", f"Rs {invested:,.0f}")
    col3.metric("Cash", f"Rs {cash:,.0f}")
    col4.metric("Total Value", f"Rs {total_value:,.0f}")
    st.caption(f"Latest holdings sync: `{last_sync}`")

    table = holdings.copy()
    keep = [col for col in ["ticker", "Company Name", "Industry", "position_role", "weight", "market_value", "quantity", "current_price"] if col in table.columns]
    if keep:
        table = table[keep].copy()
    rename_map = {
        "Company Name": "Company",
        "Industry": "Sector",
        "position_role": "Role",
        "weight": "Weight",
        "market_value": "Market Value",
        "quantity": "Quantity",
        "current_price": "Price",
    }
    table = table.rename(columns=rename_map).sort_values("Weight", ascending=False)
    st.dataframe(table.head(50), width="stretch", hide_index=True)


def _render_rebalance_history(bundle: dict) -> None:
    payload = bundle.get("current_positions") or {}
    rebalance = bundle.get("rebalance_trades")
    summary = payload.get("last_rebalance") or {}

    st.subheader("Latest Rebalance")
    if not isinstance(rebalance, pd.DataFrame) or rebalance.empty:
        st.info("No canonical rebalance trade batch is currently available.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Trades", f"{int(summary.get('trade_count', len(rebalance))):,d}")
    col2.metric("Buys", f"{int(summary.get('buy_count', 0)):,d}")
    col3.metric("Sells", f"{int(summary.get('sell_count', 0)):,d}")
    col4.metric("Turnover", f"{float(summary.get('turnover_pct', 0.0) or 0.0):.1%}")
    st.caption(f"Last rebalance at `{summary.get('last_rebalance_at', 'unknown')}`")

    table = rebalance.copy()
    keep = [col for col in ["timestamp_utc", "ticker", "side", "filled_qty", "fill_price", "fill_notional", "sector", "rebalance_reason"] if col in table.columns]
    table = table[keep].copy()
    table = table.rename(
        columns={
            "timestamp_utc": "Timestamp",
            "ticker": "Ticker",
            "side": "Side",
            "filled_qty": "Qty",
            "fill_price": "Price",
            "fill_notional": "Notional",
            "sector": "Sector",
            "rebalance_reason": "Reason",
        }
    )
    st.dataframe(table.head(50), width="stretch", hide_index=True)


def _render_sentiment_watchlist(bundle: dict) -> None:
    watchlist = bundle.get("portfolio_sentiment_watchlist") or {}
    rows = watchlist.get("held_positions_under_pressure") or []

    st.subheader("Held Names Under Live Sentiment Pressure")
    if not rows:
        st.info("No currently-held names are flagged by the live sentiment watchlist.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Flagged Holdings", f"{len(rows):,d}")
    col2.metric("Hedge Intensity", f"{float(watchlist.get('hedge_intensity', 0.0) or 0.0):.2f}")
    col3.metric("Protected Symbols", f"{int(watchlist.get('protected_symbol_count', 0) or 0):,d}")
    st.caption(f"Portfolio objective: `{watchlist.get('portfolio_objective', 'unknown')}`")

    table = pd.DataFrame(rows)
    keep = [col for col in ["ticker", "sector", "weight", "market_value", "objective", "reason", "sentiment_label", "impact_score", "hedged_or_protected"] if col in table.columns]
    table = table[keep].copy().rename(
        columns={
            "ticker": "Ticker",
            "sector": "Sector",
            "weight": "Weight",
            "market_value": "Market Value",
            "objective": "Objective",
            "reason": "Reason",
            "sentiment_label": "Sentiment",
            "impact_score": "Impact",
            "hedged_or_protected": "Protected",
        }
    )
    st.dataframe(table, width="stretch", hide_index=True)


def _render_trade_blotter(bundle: dict) -> None:
    blotter = bundle.get("portfolio_trade_blotter")

    st.subheader("Recent Trade Blotter")
    if not isinstance(blotter, pd.DataFrame) or blotter.empty:
        st.info("No canonical trade blotter is available yet.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Fills", f"{len(blotter):,d}")
    col2.metric("Equity Fills", f"{int((blotter.get('asset_class') == 'equity').sum()):,d}" if "asset_class" in blotter.columns else "0")
    col3.metric("Options Fills", f"{int((blotter.get('asset_class') == 'options').sum()):,d}" if "asset_class" in blotter.columns else "0")

    table = blotter.copy()
    keep = [
        col
        for col in [
            "timestamp_utc",
            "asset_class",
            "symbol",
            "side",
            "filled_qty",
            "fill_price",
            "fill_notional",
            "strategy_id",
            "origin",
            "trigger_reason_code",
            "underlying_symbol",
            "rebalance_reason",
        ]
        if col in table.columns
    ]
    if keep:
        table = table[keep].copy()
    table = table.rename(
        columns={
            "timestamp_utc": "Timestamp",
            "asset_class": "Asset Class",
            "symbol": "Symbol",
            "side": "Side",
            "filled_qty": "Qty",
            "fill_price": "Price",
            "fill_notional": "Notional",
            "strategy_id": "Strategy",
            "origin": "Origin",
            "trigger_reason_code": "Reason",
            "underlying_symbol": "Underlying",
            "rebalance_reason": "Rebalance Reason",
        }
    )
    st.dataframe(table.head(100), width="stretch", hide_index=True)


def render(bundle: dict) -> tuple[int, int]:
    rendered, total = render_visual_section(
        "Portfolio",
        bundle,
        "Current book, governor budgets, role mix, sector concentration, and allocation engine outputs.",
    )
    _render_live_holdings(bundle)
    _render_rebalance_history(bundle)
    _render_sentiment_watchlist(bundle)
    _render_trade_blotter(bundle)
    return rendered, total
