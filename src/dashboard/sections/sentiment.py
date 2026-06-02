#!/usr/bin/env python3
from __future__ import annotations

from src.dashboard.sections.shared import render_visual_section


def render(bundle: dict) -> tuple[int, int]:
    return render_visual_section("Sentiment", bundle, "Market sentiment, company coverage, and NSE-focused alternative-data surfaces.")
