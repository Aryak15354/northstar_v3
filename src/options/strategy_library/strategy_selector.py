from __future__ import annotations

from typing import Any

from src.intelligence.news_brain.news_signal_state import MarketIntelligenceState, SectorImpact, ShockDirection, ShockSeverity, ShockType
from src.options.strategy_library.iv_context import IVContext, build_iv_context, estimate_iv_rank
from src.options.strategy_library.strategy_definitions import OPTION_STRATEGIES


SECTOR_INDEX_MAP = {
    "Financial Services": "BANKNIFTY",
    "Information Technology": "NIFTYIT",
    "Healthcare": "NIFTYPHARMA",
    "Oil Gas & Consumable Fuels": "NIFTYENERGY",
    "Automobile and Auto Components": "NIFTYAUTO",
    "Metals & Mining": "NIFTYMETAL",
    "Fast Moving Consumer Goods": "NIFTYFMCG",
    "Realty": "NIFTYREALTY",
}


class StrategySelector:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = dict(config or {})
        library_cfg = self.config.get("strategy_library", {}) or {}
        sizing_cfg = library_cfg.get("position_sizing", {}) or {}
        self.max_concurrent_strategies = int(library_cfg.get("max_concurrent_strategies", 5) or 5)
        self.max_per_strategy_pct = float(sizing_cfg.get("max_per_strategy_pct", 2.0) or 2.0)
        self.max_total_options_pct = float(sizing_cfg.get("max_total_options_pct", 8.0) or 8.0)

    @staticmethod
    def estimate_iv_rank(vix_level: float) -> float:
        return estimate_iv_rank(vix_level)

    def select(
        self,
        intelligence_state: MarketIntelligenceState,
        current_iv_surface: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        iv_context = build_iv_context(current_iv_surface)
        candidates = self._candidate_strategies(intelligence_state, iv_context)

        scored: list[dict[str, Any]] = []
        for strategy_name in candidates:
            strategy_def = OPTION_STRATEGIES.get(strategy_name)
            if not strategy_def:
                continue
            if not self._trigger_match(strategy_def, intelligence_state.primary_shock_type):
                continue
            if not self._entry_conditions_match(strategy_def, intelligence_state, iv_context):
                continue
            underlying = self._choose_underlying(strategy_name, intelligence_state)
            score = self._score(strategy_name, strategy_def, intelligence_state, iv_context, underlying)
            scored.append(
                {
                    "strategy": strategy_name,
                    "underlying": underlying,
                    "score": float(score),
                    "objective": self._objective_for_strategy(strategy_name, intelligence_state),
                    "rationale": self._rationale(strategy_name, intelligence_state, underlying),
                    "urgency": self._urgency(intelligence_state, strategy_name),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        top = scored[: min(3, self.max_concurrent_strategies)]
        top = self._ensure_opportunity_mix(top, scored, intelligence_state)

        remaining = self.max_total_options_pct
        for item in top:
            allocation_pct = min(self.max_per_strategy_pct, remaining)
            item["allocation_pct"] = float(max(0.0, allocation_pct))
            item["sizing_lots"] = self._sizing_lots(item["strategy"], item["underlying"], intelligence_state, allocation_pct)
            item["entry_window_minutes"] = 30 if item["urgency"] in {"high", "immediate"} else 90
            remaining = max(0.0, remaining - allocation_pct)
        return top

    def _ensure_opportunity_mix(
        self,
        top: list[dict[str, Any]],
        scored: list[dict[str, Any]],
        intelligence_state: MarketIntelligenceState,
    ) -> list[dict[str, Any]]:
        if intelligence_state.primary_shock_type == ShockType.NONE or intelligence_state.shock_severity < ShockSeverity.HIGH:
            return top
        if any(item.get("objective") == "shock_opportunity" for item in top):
            return top

        best_opportunity = next((item for item in scored if item.get("objective") == "shock_opportunity"), None)
        if best_opportunity is None:
            return top

        core_systemic_hedges = {
            "bear_put_spread",
            "ratio_put_spread",
            "vix_spike_put_spread",
            "delta_hedge_synthetic",
        }
        replacement_pool = [item for item in top if item.get("objective") != "shock_hedge"]
        if not replacement_pool:
            replacement_pool = [item for item in top if str(item.get("strategy")) not in core_systemic_hedges]
        replace_target = replacement_pool[-1] if replacement_pool else top[-1] if top else None
        if replace_target is None:
            return [best_opportunity]

        replaced = []
        for item in top:
            if item is replace_target:
                replaced.append(best_opportunity)
            else:
                replaced.append(item)

        deduped: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for item in replaced:
            key = (str(item.get("strategy")), str(item.get("underlying")))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(item)
        deduped.sort(key=lambda item: item["score"], reverse=True)
        return deduped[: min(3, self.max_concurrent_strategies)]

    def _candidate_strategies(self, intelligence_state: MarketIntelligenceState, iv_context: IVContext) -> list[str]:
        shock = intelligence_state.primary_shock_type
        severity = intelligence_state.shock_severity
        direction = intelligence_state.shock_direction

        if severity == ShockSeverity.NONE or shock == ShockType.NONE:
            return ["covered_call", "iron_condor", "put_write_cash_secured", "diagonal_spread"]

        candidates: list[str] = []
        if severity >= ShockSeverity.SEVERE:
            candidates.extend(["ratio_put_spread", "vix_spike_put_spread", "delta_hedge_synthetic"])
        elif severity >= ShockSeverity.HIGH:
            candidates.extend(["bear_put_spread", "protective_put"])
        elif severity >= ShockSeverity.MODERATE:
            candidates.extend(["bear_put_spread", "protective_put"])

        shock_map = {
            ShockType.OIL_PRICE_SPIKE: ["bear_put_spread", "protective_put", "long_call"],
            ShockType.OIL_SUPPLY_DISRUPTION: ["bear_put_spread", "ratio_put_spread", "long_call", "long_strangle"],
            ShockType.GEOPOLITICAL_CONFLICT: ["ratio_put_spread", "long_call", "calendar_spread_iv", "long_strangle"],
            ShockType.FII_OUTFLOW: ["bear_put_spread", "long_strangle", "protective_put"],
            ShockType.CHINA_SLOWDOWN: ["bear_put_spread", "protective_put", "long_call"],
            ShockType.RATE_HIKE_RBI: ["bear_put_spread", "collar", "protective_put"],
            ShockType.RATE_HIKE_FED: ["bear_put_spread", "protective_put", "long_strangle"],
            ShockType.INR_DEPRECIATION: ["long_call", "bull_call_spread", "diagonal_spread"],
            ShockType.RATE_CUT_RBI: ["bull_call_spread", "long_call", "call_backspread"],
            ShockType.CAPEX_CYCLE_ACCELERATION: ["bull_call_spread", "call_backspread", "diagonal_spread"],
            ShockType.BUDGET_POSITIVE: ["bull_call_spread", "call_backspread", "diagonal_spread"],
            ShockType.BANKING_STRESS: ["vix_spike_put_spread", "bear_put_spread", "long_straddle"],
            ShockType.GLOBAL_RECESSION: ["ratio_put_spread", "bear_put_spread", "vix_spike_put_spread", "long_strangle"],
            ShockType.MONSOON_NORMAL: ["bull_call_spread", "naked_put_aggressive"],
            ShockType.FII_INFLOW: ["call_backspread", "bull_call_spread", "naked_put_aggressive"],
        }
        candidates.extend(shock_map.get(shock, []))

        if direction == ShockDirection.BULLISH:
            candidates.extend(["bull_call_spread", "long_call"])
        elif direction == ShockDirection.BEARISH:
            candidates.extend(["bear_put_spread", "protective_put"])

        if iv_context.vix_level > 25.0 and intelligence_state.shock_direction == ShockDirection.BEARISH:
            candidates.append("vix_spike_put_spread")
        if iv_context.iv_rank < 30.0 and severity >= ShockSeverity.MODERATE:
            candidates.append("long_straddle")
        if iv_context.iv_rank > 70.0 and severity == ShockSeverity.NONE:
            candidates.append("iron_butterfly")

        ordered: list[str] = []
        for name in candidates:
            if name not in ordered:
                ordered.append(name)
        return ordered

    def _trigger_match(self, strategy_def: dict[str, Any], shock_type: ShockType) -> bool:
        triggers = list(strategy_def.get("shock_triggers", []) or [])
        if not triggers:
            return shock_type == ShockType.NONE
        return shock_type.value in triggers or "post_resolution" in triggers

    def _entry_conditions_match(
        self,
        strategy_def: dict[str, Any],
        intelligence_state: MarketIntelligenceState,
        iv_context: IVContext,
    ) -> bool:
        entry = strategy_def.get("entry_conditions", {}) or {}
        min_severity = str(entry.get("min_shock_severity", "NONE") or "NONE").upper()
        if intelligence_state.shock_severity.value < ShockSeverity[min_severity].value:
            return False

        max_iv_rank = entry.get("max_iv_rank")
        if max_iv_rank is not None and iv_context.iv_rank > float(max_iv_rank):
            return False
        min_iv_rank = entry.get("min_iv_rank")
        if min_iv_rank is not None and iv_context.iv_rank < float(min_iv_rank):
            return False
        min_vix_level = entry.get("min_vix_level") or entry.get("vix_level_min")
        if min_vix_level is not None and iv_context.vix_level < float(min_vix_level):
            return False
        min_fall = entry.get("min_nifty_intraday_fall_pct")
        if min_fall is not None and abs(float(iv_context.nifty_intraday_fall_pct)) < float(min_fall):
            return False
        iv_term = str(entry.get("iv_term_structure", "") or "").lower()
        if iv_term and iv_term != iv_context.term_structure:
            return False
        max_shock_severity = entry.get("max_shock_severity")
        if max_shock_severity is not None and intelligence_state.shock_severity.value > ShockSeverity[str(max_shock_severity).upper()].value:
            return False
        return True

    def _choose_underlying(self, strategy_name: str, intelligence_state: MarketIntelligenceState) -> str:
        negative_sector = self._top_sector(intelligence_state, positive=False)
        positive_sector = self._top_sector(intelligence_state, positive=True)
        if strategy_name in {"bear_put_spread", "ratio_put_spread", "vix_spike_put_spread", "long_straddle", "long_strangle", "iron_condor", "iron_butterfly"}:
            if intelligence_state.primary_shock_type == ShockType.RATE_HIKE_RBI:
                return "BANKNIFTY"
            return SECTOR_INDEX_MAP.get(negative_sector.sector, "NIFTY") if negative_sector else "NIFTY"
        if strategy_name in {"protective_put", "collar"}:
            if negative_sector:
                if negative_sector.key_tickers_at_risk:
                    return negative_sector.key_tickers_at_risk[0]
                return SECTOR_INDEX_MAP.get(negative_sector.sector, "NIFTY")
            return "NIFTY"
        if strategy_name in {"long_call", "bull_call_spread", "call_backspread", "diagonal_spread", "naked_put_aggressive", "put_write_cash_secured", "covered_call"}:
            preferred_beneficiary = self._preferred_beneficiary_underlying(intelligence_state)
            if preferred_beneficiary:
                return preferred_beneficiary
            if positive_sector and positive_sector.key_tickers_to_benefit:
                return positive_sector.key_tickers_to_benefit[0]
            if positive_sector:
                return SECTOR_INDEX_MAP.get(positive_sector.sector, "NIFTY")
            return "NIFTY"
        if strategy_name == "delta_hedge_synthetic":
            return "NIFTY"
        return "NIFTY"

    def _preferred_beneficiary_underlying(self, intelligence_state: MarketIntelligenceState) -> str | None:
        sector_priority_map = {
            ShockType.OIL_PRICE_SPIKE: ["Oil Gas & Consumable Fuels", "Information Technology"],
            ShockType.OIL_SUPPLY_DISRUPTION: ["Oil Gas & Consumable Fuels", "Information Technology"],
            ShockType.GEOPOLITICAL_CONFLICT: ["Capital Goods", "Information Technology"],
            ShockType.INR_DEPRECIATION: ["Information Technology", "Healthcare"],
            ShockType.RATE_CUT_RBI: ["Realty", "Financial Services", "Automobile and Auto Components"],
            ShockType.CAPEX_CYCLE_ACCELERATION: ["Capital Goods", "Construction", "Construction Materials"],
            ShockType.BUDGET_POSITIVE: ["Capital Goods", "Construction", "Financial Services"],
            ShockType.FII_INFLOW: ["Financial Services", "Capital Goods", "Information Technology"],
            ShockType.MONSOON_NORMAL: ["Fast Moving Consumer Goods", "Automobile and Auto Components"],
        }
        for sector_name in sector_priority_map.get(intelligence_state.primary_shock_type, []):
            impact = intelligence_state.sector_impacts.get(sector_name)
            if not impact:
                continue
            if impact.key_tickers_to_benefit:
                return impact.key_tickers_to_benefit[0]
            if impact.impact_score > 0.10:
                mapped = SECTOR_INDEX_MAP.get(sector_name)
                if mapped:
                    return mapped
        return None

    def _top_sector(self, intelligence_state: MarketIntelligenceState, positive: bool) -> SectorImpact | None:
        impacts = list(intelligence_state.sector_impacts.values())
        if not impacts:
            return None
        sorted_impacts = sorted(impacts, key=lambda item: item.impact_score, reverse=positive)
        if positive:
            return next((impact for impact in sorted_impacts if impact.impact_score > 0.10), None)
        return next((impact for impact in sorted_impacts if impact.impact_score < -0.10), None)

    def _score(
        self,
        strategy_name: str,
        strategy_def: dict[str, Any],
        intelligence_state: MarketIntelligenceState,
        iv_context: IVContext,
        underlying: str,
    ) -> float:
        urgency = 1.2 if intelligence_state.shock_severity >= ShockSeverity.SEVERE else 1.0
        if intelligence_state.shock_severity == ShockSeverity.NONE:
            urgency = 0.8
        confidence = max(0.2, float(intelligence_state.shock_confidence))
        iv_suitability = self._iv_suitability(strategy_name, iv_context)
        beneficiary_bonus = 0.0
        if strategy_name in {"long_call", "bull_call_spread", "call_backspread", "diagonal_spread"}:
            sector = self._top_sector(intelligence_state, positive=True)
            beneficiary_bonus = max(0.0, float(sector.impact_score)) if sector else 0.0
            preferred_beneficiary = self._preferred_beneficiary_underlying(intelligence_state)
            if preferred_beneficiary and str(preferred_beneficiary).upper() == str(underlying).upper():
                beneficiary_bonus = max(beneficiary_bonus, 0.50)
            if strategy_name == "long_call" and intelligence_state.primary_shock_type in {
                ShockType.OIL_PRICE_SPIKE,
                ShockType.OIL_SUPPLY_DISRUPTION,
                ShockType.GEOPOLITICAL_CONFLICT,
            }:
                beneficiary_bonus += 0.20
        if strategy_name in {"protective_put", "bear_put_spread", "ratio_put_spread"}:
            sector = self._top_sector(intelligence_state, positive=False)
            beneficiary_bonus = abs(min(0.0, float(sector.impact_score))) if sector else 0.0
        index_bonus = 0.12 if underlying in {"NIFTY", "BANKNIFTY"} else 0.0
        sell_group_penalty = 0.25 if strategy_def.get("group") == "income" and intelligence_state.shock_severity != ShockSeverity.NONE else 0.0
        systemic_protection_penalty = 0.0
        if strategy_name == "protective_put" and intelligence_state.shock_severity >= ShockSeverity.SEVERE:
            if intelligence_state.primary_shock_type in {
                ShockType.OIL_SUPPLY_DISRUPTION,
                ShockType.GEOPOLITICAL_CONFLICT,
                ShockType.GLOBAL_RECESSION,
                ShockType.UNKNOWN_HIGH_MAGNITUDE,
            }:
                systemic_protection_penalty = 0.25
        return urgency * confidence * (0.85 + iv_suitability + beneficiary_bonus + index_bonus) - sell_group_penalty - systemic_protection_penalty

    def _iv_suitability(self, strategy_name: str, iv_context: IVContext) -> float:
        iv_rank = float(iv_context.iv_rank)
        vix = float(iv_context.vix_level)
        if strategy_name == "protective_put":
            return 0.35 if iv_rank < 50 else (-0.30 if iv_rank > 70 else 0.10)
        if strategy_name == "bear_put_spread":
            return 0.40 if 40 <= iv_rank <= 80 else 0.15
        if strategy_name == "ratio_put_spread":
            return 0.55 if iv_rank > 60 else -0.10
        if strategy_name == "long_straddle":
            return 0.55 if iv_rank < 30 else (-0.70 if iv_rank > 50 else -0.15)
        if strategy_name == "long_strangle":
            return 0.45 if iv_rank < 35 else (-0.55 if iv_rank > 50 else -0.10)
        if strategy_name == "calendar_spread_iv":
            return 0.50 if iv_rank > 65 and iv_context.term_structure == "inverted" else -0.35
        if strategy_name == "vix_spike_put_spread":
            return 0.65 if vix > 25 else -0.45
        if strategy_name == "iron_condor":
            return 0.40 if iv_rank > 45 else -0.40
        if strategy_name == "covered_call":
            return 0.30 if 40 <= iv_rank <= 65 else -0.15
        if strategy_name == "bull_call_spread":
            return 0.35 if 30 <= iv_rank <= 70 else 0.05
        return 0.20

    def _objective_for_strategy(self, strategy_name: str, intelligence_state: MarketIntelligenceState) -> str:
        if strategy_name in {"bear_put_spread", "ratio_put_spread", "protective_put", "collar", "delta_hedge_synthetic"}:
            return "shock_hedge"
        if strategy_name in {"long_call", "bull_call_spread", "call_backspread", "diagonal_spread", "naked_put_aggressive"}:
            return "shock_opportunity"
        if strategy_name in {"long_straddle", "long_strangle", "calendar_spread_iv", "vix_spike_put_spread", "iron_butterfly"}:
            return "volatility_expression"
        if intelligence_state.shock_severity == ShockSeverity.NONE:
            return "income_harvest"
        return "overlay"

    def _rationale(self, strategy_name: str, intelligence_state: MarketIntelligenceState, underlying: str) -> str:
        if strategy_name == "long_call":
            sector = self._top_sector(intelligence_state, positive=True)
            if sector:
                return f"{sector.sector} scores {sector.impact_score:+.2f}; {underlying} is a listed beneficiary"
        if strategy_name in {"bear_put_spread", "ratio_put_spread", "vix_spike_put_spread"}:
            return f"{intelligence_state.primary_shock_type.value} {intelligence_state.shock_severity.name} severity with bearish market impact"
        return f"{intelligence_state.primary_shock_type.value} with {intelligence_state.shock_direction.value} bias on {underlying}"

    def _urgency(self, intelligence_state: MarketIntelligenceState, strategy_name: str) -> str:
        if strategy_name == "vix_spike_put_spread":
            return "immediate"
        if intelligence_state.shock_severity >= ShockSeverity.SEVERE:
            return "immediate"
        if intelligence_state.shock_severity >= ShockSeverity.HIGH:
            return "high"
        if intelligence_state.shock_severity >= ShockSeverity.MODERATE:
            return "medium"
        return "low"

    def _sizing_lots(self, strategy_name: str, underlying: str, intelligence_state: MarketIntelligenceState, allocation_pct: float) -> int:
        base = 1
        if underlying in {"NIFTY", "BANKNIFTY"}:
            base = 2
        if strategy_name == "vix_spike_put_spread":
            base = 5 if intelligence_state.shock_severity == ShockSeverity.SEVERE else 8
        elif strategy_name == "ratio_put_spread":
            base = 2
        elif strategy_name == "bear_put_spread" and intelligence_state.shock_severity >= ShockSeverity.HIGH:
            base = 3
        scale = max(1, int(round(max(1.0, allocation_pct / max(0.5, self.max_per_strategy_pct) * base))))
        return max(1, scale)
