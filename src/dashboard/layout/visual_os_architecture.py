from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class LayerDefinition:
    layer_id: str
    title: str
    mode_scope: str  # live|research|both
    description: str
    sla_contract: str
    visual_budget: str


LAYER_DEFINITIONS: Tuple[LayerDefinition, ...] = (
    LayerDefinition(
        layer_id="L0",
        title="System Control Strip",
        mode_scope="both",
        description="Global state banner: strict mode, freeze state, policy lock, freshness posture.",
        sla_contract="No chart render; state-only indicators.",
        visual_budget="0 charts",
    ),
    LayerDefinition(
        layer_id="L1",
        title="Executive Live Surface",
        mode_scope="live",
        description="Immediate decision surfaces for market, portfolio, risk, narrative, and system health.",
        sla_contract="Contract-managed charts; expired charts blocked in live mode.",
        visual_budget="8-12 surfaces",
    ),
    LayerDefinition(
        layer_id="L2",
        title="Tactical Drill-Down",
        mode_scope="both",
        description="Operational drill-down tabs for deeper context and diagnostics.",
        sla_contract="Contract-managed where available; stale warns allowed.",
        visual_budget="25-35 surfaces",
    ),
    LayerDefinition(
        layer_id="L3",
        title="Research Lab",
        mode_scope="research",
        description="Heavy exploratory and advanced intelligence workbench.",
        sla_contract="Collapsed by default; non-blocking research rendering.",
        visual_budget="40-45 emissions (collapsed)",
    ),
)


LIVE_DEPTH_OPTIONS: Tuple[str, ...] = (
    "Executive Control Surface",
    "Tactical Drill-Down",
)


RESEARCH_DEPTH_OPTIONS: Tuple[str, ...] = (
    "Tactical Research",
    "Research Lab",
)


EMISSION_TARGETS: Dict[str, int] = {
    "baseline": 174,
    "wave_1": 150,
    "wave_2": 120,
    "wave_3": 100,
    "wave_4": 90,
}

