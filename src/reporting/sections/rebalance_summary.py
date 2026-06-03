"""Weekly rebalance execution summary."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta

import pandas as pd

from src.reporting.common import (
    PROJECT_ROOT,
    SectionResult,
    load_current_positions_frame,
    money_text,
    pct_text,
    read_json_candidates,
    render_note,
    unavailable_section,
)
from src.reporting.renderers.html_renderer import HTMLRenderer, render_metric_grid, render_table


SECTION_NAME = "rebalance_summary"
SECTION_TITLE = "Rebalance Execution Summary"


def build_section(report_date: date) -> SectionResult:
    try:
        db_path = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
        if not db_path.exists():
            raise FileNotFoundError("Runtime DB missing")

        con = sqlite3.connect(db_path)
        query = """
            select
                pe.event_id,
                pe.timestamp_utc,
                pe.trigger_reason_code,
                pe.strategy_id,
                ef.symbol,
                ef.side,
                ef.filled_qty,
                ef.fill_price,
                ef.fill_notional,
                pe.payload_json,
                pe.risk_override_flag
            from portfolio_events pe
            join execution_fills ef on ef.event_id = pe.event_id
            where pe.trigger_reason_code = 'rebalance.core.sync'
            order by pe.timestamp_utc desc
        """
        events = pd.read_sql_query(query, con)
        con.close()
        if events.empty:
            raise KeyError("No canonical rebalance.core.sync events found in runtime DB")

        events["timestamp_utc"] = pd.to_datetime(events["timestamp_utc"], errors="coerce", utc=True)
        latest_ts = events["timestamp_utc"].max()
        cutoff = latest_ts - pd.Timedelta(minutes=5)
        rebalance = events.loc[events["timestamp_utc"] >= cutoff].copy()
        rebalance["payload_json"] = rebalance["payload_json"].map(lambda x: json.loads(x) if isinstance(x, str) and x.strip() else {})
        rebalance["lifecycle_action"] = rebalance["payload_json"].map(lambda x: x.get("lifecycle_action", "adjust"))
        rebalance["Action"] = rebalance["lifecycle_action"].str.upper()
        rebalance["Ticker"] = rebalance["symbol"].astype(str)
        rebalance["Qty"] = rebalance["filled_qty"].map(lambda x: f"{float(x):,.2f}")
        rebalance["Price"] = rebalance["fill_price"].map(lambda x: money_text(x, digits=2, prefix="Rs "))
        rebalance["Notional"] = rebalance["fill_notional"].map(lambda x: money_text(x, digits=0, prefix="Rs "))
        rebalance["Side"] = rebalance["side"].str.upper()

        positions = load_current_positions_frame()
        total_value = float(positions["market_value"].sum()) if "market_value" in positions.columns else 0.0
        turnover = float(rebalance["fill_notional"].sum()) / max(total_value, 1e-9)
        override_count = int(rebalance["risk_override_flag"].fillna(0).astype(int).sum())
        unified_state = read_json_candidates(["data/state/unified_state.json"])
        avg_slippage = unified_state.get("pnl_state", {}).get("avg_slippage_bps_30d")

        metrics = render_metric_grid(
            [
                ("Rebalance timestamp", str(latest_ts), "Latest core sync batch"),
                ("Trades in batch", str(len(rebalance)), None),
                ("Approx turnover", pct_text(turnover, digits=1), "Gross traded notional / live book"),
                ("Avg slippage", f"{float(avg_slippage):.1f} bps" if avg_slippage is not None else "N/A", "From canonical pnl_state"),
                ("Overrides", str(override_count), "Risk override flags in batch"),
            ]
        )

        trade_table = rebalance[["Ticker", "Action", "Side", "Qty", "Price", "Notional", "strategy_id", "trigger_reason_code"]].rename(
            columns={"strategy_id": "Strategy", "trigger_reason_code": "Trigger"}
        )
        summary = f"Latest slow-rebalance batch executed {len(rebalance)} canonical fills at {latest_ts}."
        body = metrics + render_table(trade_table)
        body += render_note("This section is sourced from the runtime DB and immutable execution fills because a standalone rebalance_log parquet is not currently produced.")
        return SectionResult(
            name=SECTION_NAME,
            title=SECTION_TITLE,
            status="warn" if override_count > 0 else "ok",
            badge="ALERT" if override_count > 0 else "OK",
            summary=summary,
            body_html=body,
        )
    except (FileNotFoundError, KeyError) as exc:
        return unavailable_section(SECTION_TITLE, str(exc), name=SECTION_NAME)
    except Exception as exc:
        return unavailable_section(SECTION_TITLE, f"Unexpected error: {exc}", name=SECTION_NAME)


if __name__ == "__main__":
    print(HTMLRenderer(title=SECTION_TITLE).render_section(build_section(date.today())))
