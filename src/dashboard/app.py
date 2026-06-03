#!/usr/bin/env python3
"""
Northstar V3 Canonical Dashboard entrypoint.

Launch with:
    streamlit run src/dashboard/app.py
"""

from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.dashboard.integrated_dashboard import render_dashboard


st.set_page_config(
    page_title="Northstar V3 Canonical Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Northstar V3 Canonical Dashboard - real data only"},
)


def main() -> None:
    render_dashboard()


if __name__ == "__main__":
    main()
