from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.intelligence.news_brain.news_signal_state import MarketIntelligenceState, ShockDirection, ShockSeverity, ShockType
from src.intelligence.shock_engine.position_risk_scorer import PositionRiskScorer
from src.intelligence.shock_engine.rebalance_instruction import (
    InstructionType,
    InstructionUrgency,
    OptionsInstruction,
    RebalanceInstruction,
    ShockResponsePlan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ShockResponseEngine:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = self._load_config(config)
        self.position_risk_scorer = PositionRiskScorer()

    def evaluate(
        self,
        intelligence_state: MarketIntelligenceState,
        current_positions: list[dict[str, Any]],
    ) -> ShockResponsePlan:
        return ShockResponsePlan(
            rebalance_instructions=self.get_rebalance_instructions(intelligence_state, current_positions),
            options_instructions=self.get_options_instructions(intelligence_state, current_positions),
        )

    def get_rebalance_instructions(
        self,
        intelligence_state: MarketIntelligenceState,
        current_positions: list[dict[str, Any]],
    ) -> list[RebalanceInstruction]:
        if intelligence_state.primary_shock_type == ShockType.NONE:
            return []

        reduction_factor = self._reduction_factor(intelligence_state.shock_severity)
        scores = self.position_risk_scorer.score_positions(intelligence_state, current_positions)
        instructions: list[RebalanceInstruction] = []
        for score in scores:
            if score.exposure_score >= -0.30:
                continue
            raw = dict(score.metadata.get("raw_position", {}))
            max_reducible = self._max_reducible_quantity(raw)
            target_reduction = float(score.current_weight) * abs(float(score.exposure_score)) * reduction_factor
            urgency = self._urgency_from_severity(intelligence_state.shock_severity)
            instructions.append(
                RebalanceInstruction(
                    instruction_type=InstructionType.REDUCE_EQUITY,
                    symbol=score.symbol,
                    sector=score.sector,
                    urgency=urgency,
                    current_weight=float(score.current_weight),
                    target_weight_change=-float(target_reduction),
                    max_reducible_quantity=max_reducible,
                    rationale=f"Shock exposure {score.exposure_score:.2f} from {score.sector} sector impact {score.sector_impact_score:.2f}",
                    metadata={"shock_type": intelligence_state.primary_shock_type.value},
                )
            )

            if target_reduction > max_reducible and (score.hedge_required or intelligence_state.shock_severity >= ShockSeverity.HIGH):
                instructions.append(
                    RebalanceInstruction(
                        instruction_type=InstructionType.HEDGE_WITH_OPTIONS,
                        symbol=score.symbol,
                        sector=score.sector,
                        urgency=InstructionUrgency.IMMEDIATE if intelligence_state.shock_severity >= ShockSeverity.SEVERE else urgency,
                        current_weight=float(score.current_weight),
                        target_weight_change=0.0,
                        max_reducible_quantity=max_reducible,
                        rationale=f"Position cannot be reduced fully within ADV limits; add options hedge on {score.symbol}",
                        metadata={"recommended_hedge": "protective_put"},
                    )
                )

        beneficiary_increases = self._beneficiary_increase_instructions(intelligence_state, current_positions)
        instructions.extend(beneficiary_increases)
        return instructions

    def get_options_instructions(
        self,
        intelligence_state: MarketIntelligenceState,
        current_positions: list[dict[str, Any]],
    ) -> list[OptionsInstruction]:
        if intelligence_state.primary_shock_type == ShockType.NONE or intelligence_state.shock_severity == ShockSeverity.NONE:
            return []
        del current_positions
        try:
            from src.options.strategy_library.strategy_selector import StrategySelector
        except Exception:
            return []

        selector = StrategySelector(self.config)
        selected = selector.select(
            intelligence_state,
            current_iv_surface={
                "vix": intelligence_state.vix_level,
                "iv_rank": selector.estimate_iv_rank(intelligence_state.vix_level),
                "nifty_intraday_fall_pct": intelligence_state.sector_impacts.get("Financial Services", None).estimated_sector_move_pct if intelligence_state.sector_impacts.get("Financial Services") else 0.0,
            },
        )
        instructions: list[OptionsInstruction] = []
        for item in selected:
            instructions.append(
                OptionsInstruction(
                    strategy=str(item.get("strategy")),
                    underlying=str(item.get("underlying")),
                    objective=str(item.get("objective", "shock_response")),
                    urgency=self._parse_urgency(item.get("urgency")),
                    sizing_lots=int(item.get("sizing_lots", 1) or 1),
                    rationale=str(item.get("rationale", "") or ""),
                    metadata=dict(item),
                )
            )
        return instructions

    def _beneficiary_increase_instructions(
        self,
        intelligence_state: MarketIntelligenceState,
        current_positions: list[dict[str, Any]],
    ) -> list[RebalanceInstruction]:
        holdings = {_normalize_symbol(row.get("symbol", row.get("ticker", ""))): dict(row) for row in current_positions}
        instructions: list[RebalanceInstruction] = []
        for sector, impact in intelligence_state.sector_impacts.items():
            if impact.impact_score < 0.35 and not impact.key_tickers_to_benefit:
                continue
            for ticker in impact.key_tickers_to_benefit[:2]:
                symbol = _normalize_symbol(ticker)
                if symbol not in holdings:
                    continue
                current_weight = float(holdings[symbol].get("weight", holdings[symbol].get("final_weight", 0.0)) or 0.0)
                beneficiary_lift = 0.15 if impact.impact_score >= 0.35 else 0.10
                instructions.append(
                    RebalanceInstruction(
                        instruction_type=InstructionType.INCREASE_EQUITY,
                        symbol=symbol,
                        sector=sector,
                        urgency=InstructionUrgency.MEDIUM if intelligence_state.shock_direction != ShockDirection.BEARISH else InstructionUrgency.HIGH,
                        current_weight=current_weight,
                        target_weight_change=max(0.0025, current_weight * beneficiary_lift),
                        max_reducible_quantity=0.0,
                        rationale=(
                            f"{symbol} is a listed beneficiary of {intelligence_state.primary_shock_type.value}"
                            if impact.impact_score >= 0.0
                            else f"{symbol} is an explicit beneficiary despite mixed sector impact during {intelligence_state.primary_shock_type.value}"
                        ),
                        metadata={
                            "beneficiary_sector_score": impact.impact_score,
                            "sector_mixed_beneficiary": bool(impact.impact_score < 0.35),
                        },
                    )
                )
        return instructions

    def _load_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        merged = dict(config or {})
        config_path = PROJECT_ROOT / "config" / "intelligence_brain.yaml"
        if config_path.exists():
            file_cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            merged = _deep_merge(dict(file_cfg), merged)
        return merged

    def _reduction_factor(self, severity: ShockSeverity) -> float:
        mapping = self.config.get("shock_response", {}).get("rebalance", {}) or {}
        if severity >= ShockSeverity.SEVERE:
            return float(mapping.get("reduction_factor_severe", 0.75))
        if severity >= ShockSeverity.HIGH:
            return float(mapping.get("reduction_factor_high", 0.50))
        return float(mapping.get("reduction_factor_moderate", 0.30))

    def _max_reducible_quantity(self, position: dict[str, Any]) -> float:
        adv_cap = float(self.config.get("shock_response", {}).get("rebalance", {}).get("max_daily_adv_pct", 10.0) or 10.0) / 100.0
        adv_candidates = [
            position.get("avg_daily_volume"),
            position.get("average_daily_volume"),
            position.get("adv"),
            position.get("adv_value"),
            position.get("average_daily_value"),
        ]
        for candidate in adv_candidates:
            try:
                adv = float(candidate or 0.0)
            except Exception:
                adv = 0.0
            if adv > 0.0:
                return adv * adv_cap
        market_value = float(position.get("market_value", 0.0) or 0.0)
        quantity = float(position.get("quantity", 0.0) or 0.0)
        if market_value > 0.0:
            return market_value * adv_cap
        if quantity > 0.0:
            return quantity * adv_cap
        weight = float(position.get("weight", position.get("final_weight", 0.0)) or 0.0)
        return max(0.0, weight * adv_cap)

    @staticmethod
    def _urgency_from_severity(severity: ShockSeverity) -> InstructionUrgency:
        if severity >= ShockSeverity.SEVERE:
            return InstructionUrgency.IMMEDIATE
        if severity >= ShockSeverity.HIGH:
            return InstructionUrgency.HIGH
        if severity >= ShockSeverity.MODERATE:
            return InstructionUrgency.MEDIUM
        return InstructionUrgency.LOW

    @staticmethod
    def _parse_urgency(value: Any) -> InstructionUrgency:
        try:
            return InstructionUrgency(str(value or "medium"))
        except Exception:
            return InstructionUrgency.MEDIUM


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_symbol(value: Any) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()
