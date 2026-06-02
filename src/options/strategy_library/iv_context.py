from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.intelligence.news_brain.news_signal_state import IVRegime, iv_regime_from_vix


@dataclass
class IVContext:
    vix_level: float
    iv_rank: float
    iv_regime: IVRegime
    term_structure: str = "flat"
    nifty_intraday_fall_pct: float = 0.0


def estimate_iv_rank(vix_level: float) -> float:
    vix = float(vix_level or 0.0)
    if vix <= 12.0:
        return 15.0
    if vix <= 18.0:
        return 35.0
    if vix <= 25.0:
        return 60.0
    if vix <= 35.0:
        return 82.0
    return 95.0


def build_iv_context(current_iv_surface: dict[str, Any] | None) -> IVContext:
    surface = dict(current_iv_surface or {})
    vix_level = float(surface.get("vix", surface.get("vix_level", 0.0)) or 0.0)
    iv_rank = float(surface.get("iv_rank", estimate_iv_rank(vix_level)) or estimate_iv_rank(vix_level))
    return IVContext(
        vix_level=vix_level,
        iv_rank=iv_rank,
        iv_regime=iv_regime_from_vix(vix_level),
        term_structure=str(surface.get("iv_term_structure", surface.get("term_structure", "flat")) or "flat").lower(),
        nifty_intraday_fall_pct=float(surface.get("nifty_intraday_fall_pct", 0.0) or 0.0),
    )
