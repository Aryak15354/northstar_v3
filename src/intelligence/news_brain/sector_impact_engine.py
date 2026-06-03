from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from src.intelligence.news_brain.news_signal_state import (
    CompanySignal,
    MarketSignal,
    MacroSignal,
    NIFTY500_SECTORS,
    SectorImpact,
    ShockDirection,
    ShockSeverity,
    ShockType,
    direction_from_score,
    severity_from_move_pct,
)
from src.intelligence.shock_engine.shock_knowledge_base import get_shock_profile


BELLWETHER_PROPAGATION_RULES: dict[str, list[tuple[str, float]]] = {
    "HDFCBANK": [("Financial Services", 0.20)],
    "TCS": [("Information Technology", 0.25)],
    "INFY": [("Information Technology", 0.25)],
    "RELIANCE": [("Oil Gas & Consumable Fuels", 0.30)],
    "LT": [("Capital Goods", 0.15), ("Construction", 0.15)],
}


def _ticker_root(ticker: str) -> str:
    return str(ticker or "").replace(".NS", "").replace(".BO", "").strip().upper()


def _sign_from_direction(direction: ShockDirection) -> float:
    if direction == ShockDirection.BULLISH:
        return 1.0
    if direction == ShockDirection.BEARISH:
        return -1.0
    return 0.0


class SectorImpactEngine:
    def __init__(self) -> None:
        self._sectors = list(NIFTY500_SECTORS)

    def compute(
        self,
        primary_shock_type: ShockType,
        shock_severity: ShockSeverity,
        shock_direction: ShockDirection,
        company_signals: Iterable[CompanySignal] | None = None,
        market_signals: Iterable[MarketSignal] | None = None,
        macro_signals: Iterable[MacroSignal] | None = None,
        secondary_shock_type: ShockType | None = None,
    ) -> dict[str, SectorImpact]:
        company_signals = list(company_signals or [])
        market_signals = list(market_signals or [])
        macro_signals = list(macro_signals or [])

        primary_profile = get_shock_profile(primary_shock_type.value)
        secondary_profile = get_shock_profile(secondary_shock_type.value) if secondary_shock_type else None

        impacts: dict[str, SectorImpact] = {}
        rationale_parts: dict[str, list[str]] = defaultdict(list)

        for sector in self._sectors:
            base = dict(primary_profile["sector_impacts"][sector])
            score = float(base.get("score", 0.0) or 0.0)
            estimated_move = float(base.get("estimated_move_pct", 0.0) or 0.0)
            horizon = int(base.get("time_horizon_days", primary_profile.get("time_horizon_days", 5)) or 5)
            at_risk = list(base.get("at_risk", []) or [])
            beneficiaries = list(base.get("beneficiaries", []) or [])
            rationale = str(base.get("rationale", "") or "")
            if rationale:
                rationale_parts[sector].append(rationale)

            if secondary_profile is not None:
                secondary = dict(secondary_profile["sector_impacts"][sector])
                score += 0.55 * float(secondary.get("score", 0.0) or 0.0)
                estimated_move += 0.55 * float(secondary.get("estimated_move_pct", 0.0) or 0.0)
                horizon = max(horizon, int(secondary.get("time_horizon_days", secondary_profile.get("time_horizon_days", 5)) or 5))
                at_risk.extend(list(secondary.get("at_risk", []) or []))
                beneficiaries.extend(list(secondary.get("beneficiaries", []) or []))
                if secondary.get("rationale"):
                    rationale_parts[sector].append(str(secondary["rationale"]))

            impacts[sector] = SectorImpact(
                sector=sector,
                impact_score=score,
                direction=direction_from_score(score),
                severity=severity_from_move_pct(estimated_move),
                estimated_sector_move_pct=estimated_move,
                time_horizon_days=horizon,
                key_tickers_at_risk=list(dict.fromkeys(at_risk)),
                key_tickers_to_benefit=list(dict.fromkeys(beneficiaries)),
                rebalance_required=score <= -0.30,
                hedge_required=score <= -0.55,
                opportunity_trade=score >= 0.35,
                rationale="; ".join(dict.fromkeys(part for part in rationale_parts[sector] if part)),
            )

        self._apply_company_signal_adjustments(impacts, company_signals)
        self._apply_market_signal_adjustments(impacts, market_signals)
        self._apply_macro_signal_adjustments(impacts, macro_signals)
        self._normalize_final_impacts(impacts, shock_severity=shock_severity, shock_direction=shock_direction)
        return impacts

    def _apply_company_signal_adjustments(
        self,
        impacts: dict[str, SectorImpact],
        company_signals: list[CompanySignal],
    ) -> None:
        for signal in company_signals:
            sector = signal.sector if signal.sector in impacts else None
            if not sector:
                continue
            direction_sign = _sign_from_direction(signal.direction)
            base_adjustment = direction_sign * (0.04 + 0.03 * float(signal.severity.value)) * max(0.25, float(signal.confidence))
            impacts[sector].impact_score += base_adjustment
            impacts[sector].estimated_sector_move_pct += base_adjustment * 2.5
            if signal.direction == ShockDirection.BEARISH:
                impacts[sector].key_tickers_at_risk = list(dict.fromkeys([*impacts[sector].key_tickers_at_risk, _ticker_root(signal.ticker), *signal.related_tickers]))
            elif signal.direction == ShockDirection.BULLISH:
                impacts[sector].key_tickers_to_benefit = list(dict.fromkeys([*impacts[sector].key_tickers_to_benefit, _ticker_root(signal.ticker), *signal.related_tickers]))
            if signal.headline:
                impacts[sector].rationale = "; ".join(
                    filter(None, [impacts[sector].rationale, f"{_ticker_root(signal.ticker)}: {signal.headline}"])
                )

            ticker_rules = BELLWETHER_PROPAGATION_RULES.get(_ticker_root(signal.ticker), [])
            for propagated_sector, bump in ticker_rules:
                propagation = bump * direction_sign * max(0.30, float(signal.confidence))
                impacts[propagated_sector].impact_score += propagation
                impacts[propagated_sector].estimated_sector_move_pct += propagation * 2.5
                impacts[propagated_sector].rationale = "; ".join(
                    filter(None, [impacts[propagated_sector].rationale, f"Bellwether propagation from {_ticker_root(signal.ticker)}"])
                )

    def _apply_market_signal_adjustments(
        self,
        impacts: dict[str, SectorImpact],
        market_signals: list[MarketSignal],
    ) -> None:
        for signal in market_signals:
            adjustment = _sign_from_direction(signal.direction) * 0.06 * max(0.25, float(signal.confidence))
            sectors = signal.affected_sectors or list(impacts.keys())
            for sector in sectors:
                if sector not in impacts:
                    continue
                impacts[sector].impact_score += adjustment
                impacts[sector].estimated_sector_move_pct += adjustment * 1.75
                if signal.headline:
                    impacts[sector].rationale = "; ".join(filter(None, [impacts[sector].rationale, signal.headline]))

    def _apply_macro_signal_adjustments(
        self,
        impacts: dict[str, SectorImpact],
        macro_signals: list[MacroSignal],
    ) -> None:
        for signal in macro_signals:
            adjustment = _sign_from_direction(signal.direction) * 0.07 * max(0.30, float(signal.confidence))
            sectors = signal.affected_sectors or list(impacts.keys())
            for sector in sectors:
                if sector not in impacts:
                    continue
                impacts[sector].impact_score += adjustment
                impacts[sector].estimated_sector_move_pct += adjustment * 1.5
                if signal.headline:
                    impacts[sector].rationale = "; ".join(filter(None, [impacts[sector].rationale, signal.headline]))

    def _normalize_final_impacts(
        self,
        impacts: dict[str, SectorImpact],
        shock_severity: ShockSeverity,
        shock_direction: ShockDirection,
    ) -> None:
        del shock_severity, shock_direction
        for sector, impact in impacts.items():
            impact.impact_score = float(max(-1.0, min(1.0, impact.impact_score)))
            impact.direction = direction_from_score(impact.impact_score)
            impact.severity = severity_from_move_pct(impact.estimated_sector_move_pct)
            impact.rebalance_required = impact.impact_score <= -0.30
            impact.hedge_required = impact.impact_score <= -0.55
            impact.opportunity_trade = impact.impact_score >= 0.35
            impact.key_tickers_at_risk = list(dict.fromkeys(impact.key_tickers_at_risk))
            impact.key_tickers_to_benefit = list(dict.fromkeys(impact.key_tickers_to_benefit))
            impact.rationale = impact.rationale or f"Sector impact synthesized for {sector}"
