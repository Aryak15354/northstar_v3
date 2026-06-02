from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.intelligence.news_brain.news_signal_state import MarketIntelligenceState


@dataclass
class PositionRiskScore:
    symbol: str
    sector: str
    current_weight: float
    sector_impact_score: float
    exposure_score: float
    hedge_required: bool
    rebalance_required: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class PositionRiskScorer:
    def score_positions(
        self,
        market_intelligence: MarketIntelligenceState,
        positions: list[dict[str, Any]],
    ) -> list[PositionRiskScore]:
        scores: list[PositionRiskScore] = []
        for row in positions:
            symbol = _normalize_symbol(row.get("symbol", row.get("ticker", "")))
            sector = str(row.get("sector", row.get("Industry", "Diversified")) or "Diversified").strip()
            weight = float(row.get("weight", row.get("final_weight", row.get("exposure", 0.0))) or 0.0)
            weight_pct = weight * 100.0 if abs(weight) <= 1.0 else weight
            sector_impact = market_intelligence.sector_impacts.get(sector)
            impact_score = float(getattr(sector_impact, "impact_score", 0.0) or 0.0)
            # We normalize weight percentages back to a -1..+1 scoring band so a 5% position in a
            # severe -0.85 sector still becomes actionable without requiring unrealistic 30% weights.
            exposure_score = (weight_pct * impact_score) / 10.0
            scores.append(
                PositionRiskScore(
                    symbol=symbol,
                    sector=sector,
                    current_weight=weight,
                    sector_impact_score=impact_score,
                    exposure_score=float(exposure_score),
                    hedge_required=bool(getattr(sector_impact, "hedge_required", False)),
                    rebalance_required=bool(getattr(sector_impact, "rebalance_required", False)),
                    metadata={"raw_position": dict(row)},
                )
            )
        scores.sort(key=lambda item: item.exposure_score)
        return scores


def _normalize_symbol(value: Any) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()
