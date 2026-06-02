#!/usr/bin/env python3
from __future__ import annotations

import streamlit as st


def render_placeholder_card(title: str, reason: str, metadata: str = "") -> None:
    meta_html = f'<div class="ns-visual-meta">{metadata}</div>' if metadata else ""
    st.markdown(
        f"""
        <div class="ns-visual-card ns-placeholder-card">
            <div class="ns-visual-title">{title}</div>
            {meta_html}
            <div class="ns-placeholder-title">Data Unavailable</div>
            <div class="ns-placeholder-body">{reason}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="ns-section-shell">
            <div class="ns-section-title">{title}</div>
            <div class="ns-section-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
