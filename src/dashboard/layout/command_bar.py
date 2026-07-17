#!/usr/bin/env python3
"""Bloomberg-style command line for the Northstar terminal.

Type a function code or a ticker and hit Enter:

    RELIANCE          -> Security viewer on RELIANCE
    TCS DES           -> same (explicit DES)
    MOV / MKT         -> Market page
    ECO / SENT        -> Sentiment & macro page
    PORT              -> Portfolio page
    RISK              -> Risk page
    OPT               -> Options page
    VAL / RES         -> Research page
    OS / ALPHA        -> Alpha OS page
    PERF / HP         -> Performance page
    HOME / OVR        -> Overview

The parse runs in the widget's on_change callback, which Streamlit executes
*before* the next script run — so it may safely set the tab-router and
security-viewer session state ahead of widget instantiation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.dashboard.layout.terminal_theme import TERM

PROJECT_ROOT = Path(__file__).resolve().parents[3]

CMD_KEY = "ns_command"
CMD_FEEDBACK_KEY = "ns_command_feedback"
TAB_STATE_KEY = "northstar_active_tab"  # mirrors tab_router.TAB_STATE_KEY
DES_TICKER_KEY = "des_ticker"           # mirrors sections.security.TICKER_STATE_KEY

_FUNCTION_MAP = {
    "HOME": "Overview", "OVR": "Overview", "TOP": "Overview",
    "PERF": "Performance", "HP": "Performance", "PNL": "Performance",
    "MOV": "Market", "MKT": "Market", "WEI": "Market",
    "ECO": "Sentiment", "SENT": "Sentiment", "NEWS": "Sentiment",
    "PORT": "Portfolio", "BOOK": "Portfolio",
    "RISK": "Risk", "RSK": "Risk",
    "OPT": "Options", "OMON": "Options",
    "VAL": "Research", "RES": "Research", "EQS": "Research",
    "OS": "Alpha OS", "ALPHA": "Alpha OS",
    "DES": "Security", "SEC": "Security",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _ticker_set() -> set[str]:
    p = PROJECT_ROOT / "data/processed/scores.parquet"
    if not p.exists():
        return set()
    try:
        return set(pd.read_parquet(p, columns=["ticker"])["ticker"].dropna().astype(str))
    except Exception:
        return set()


def _resolve_ticker(token: str, tickers: set[str]) -> str | None:
    cand = token.upper().replace(".NS", "") + ".NS"
    if cand in tickers:
        return cand
    # prefix match (unique)
    hits = [t for t in tickers if t.startswith(token.upper())]
    return hits[0] if len(hits) == 1 else None


def _execute_command() -> None:
    raw = (st.session_state.get(CMD_KEY) or "").strip()
    if not raw:
        return
    st.session_state[CMD_KEY] = ""  # clear the input like a real terminal
    tokens = raw.upper().split()
    tickers = _ticker_set()

    # "<TICKER> DES" or "DES <TICKER>" or bare "<TICKER>"
    func = next((t for t in tokens if t in _FUNCTION_MAP), None)
    tick = next((r for t in tokens if (r := _resolve_ticker(t, tickers))), None)

    if tick:
        st.session_state[DES_TICKER_KEY] = tick
        st.session_state[TAB_STATE_KEY] = "Security"
        st.session_state[CMD_FEEDBACK_KEY] = f"→ {tick.replace('.NS','')} DES"
        return
    if func:
        st.session_state[TAB_STATE_KEY] = _FUNCTION_MAP[func]
        st.session_state[CMD_FEEDBACK_KEY] = f"→ {_FUNCTION_MAP[func]}"
        return
    st.session_state[CMD_FEEDBACK_KEY] = f"unknown command: {raw[:24]}"


def render_command_bar() -> None:
    cols = st.columns([5, 2])
    with cols[0]:
        st.text_input(
            "Command",
            key=CMD_KEY,
            on_change=_execute_command,
            placeholder="⌘  RELIANCE · TCS DES · MOV · ECO · PORT · RISK · OPT · VAL · OS",
            label_visibility="collapsed",
        )
    with cols[1]:
        feedback = st.session_state.get(CMD_FEEDBACK_KEY, "")
        st.markdown(
            f'<div style="font-family:{TERM["mono"]};color:{TERM["amber"]};font-size:0.72rem;'
            f'padding-top:10px;">{feedback}</div>',
            unsafe_allow_html=True,
        )
