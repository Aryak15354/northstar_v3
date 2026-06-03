#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class DashboardFilters:
    start_date: date | None = None
    end_date: date | None = None
    regimes: tuple[str, ...] = field(default_factory=tuple)
    strategies: tuple[str, ...] = field(default_factory=tuple)
    asset_classes: tuple[str, ...] = field(default_factory=tuple)
    show_manifest: bool = False
    auto_live_refresh: bool = True
