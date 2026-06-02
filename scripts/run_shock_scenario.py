#!/usr/bin/env python3
"""
Shock Scenario Runner — replay a historical or hypothetical shock and show what
the system would have done.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.news_brain.news_signal_state import (  # noqa: E402
    IVRegime,
    MarketIntelligenceState,
    ShockDirection,
    ShockSeverity,
    ShockType,
    iv_regime_from_vix,
)
from src.intelligence.news_brain.sector_impact_engine import SectorImpactEngine  # noqa: E402
from src.intelligence.shock_engine.position_risk_scorer import PositionRiskScorer  # noqa: E402
from src.intelligence.shock_engine.shock_knowledge_base import get_shock_profile  # noqa: E402
from src.intelligence.shock_engine.shock_response_engine import ShockResponseEngine  # noqa: E402
from src.options.strategy_library.strategy_executor import StrategyExecutor  # noqa: E402
from src.options.strategy_library.strategy_selector import StrategySelector  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a Northstar shock scenario")
    parser.add_argument(
        "--date",
        default=datetime.now().date().isoformat(),
        help="Historical or simulated date in YYYY-MM-DD format",
    )
    parser.add_argument("--shock", required=True, choices=[item.value for item in ShockType], help="Primary shock type")
    parser.add_argument("--severity", required=True, choices=[item.name for item in ShockSeverity], help="Shock severity")
    parser.add_argument("--crude_change_pct", type=float, default=0.0, help="Crude change percent for the scenario")
    parser.add_argument("--inr_change_pct", type=float, default=0.0, help="INR/USD change percent for the scenario")
    parser.add_argument("--vix_level", type=float, default=None, help="Optional India VIX override")
    parser.add_argument("--secondary-shock", dest="secondary_shock", choices=[item.value for item in ShockType], default=None)
    parser.add_argument("--portfolio", default="", help="Optional parquet/json portfolio path")
    return parser.parse_args()


def load_positions(portfolio_arg: str) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    if portfolio_arg:
        candidates.append((PROJECT_ROOT / portfolio_arg).resolve() if not Path(portfolio_arg).is_absolute() else Path(portfolio_arg))
    candidates.extend(
        [
            PROJECT_ROOT / "data" / "portfolio" / "current_positions.json",
            PROJECT_ROOT / "data" / "processed" / "portfolio_weights.parquet",
        ]
    )

    for path in candidates:
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("positions"), dict):
                rows = list(payload["positions"].values())
            elif isinstance(payload, list):
                rows = payload
            else:
                rows = []
            return [_normalize_position(row) for row in rows if isinstance(row, dict)]
        if path.suffix.lower() == ".parquet":
            frame = pd.read_parquet(path)
            rows = frame.to_dict(orient="records")
            return [_normalize_position(row) for row in rows if isinstance(row, dict)]
        if path.suffix.lower() == ".csv":
            frame = pd.read_csv(path)
            rows = frame.to_dict(orient="records")
            return [_normalize_position(row) for row in rows if isinstance(row, dict)]
    return []


def _normalize_position(row: dict[str, Any]) -> dict[str, Any]:
    symbol = _normalize_symbol(row.get("symbol", row.get("ticker", row.get("tradingsymbol", ""))))
    sector = str(
        row.get("sector", row.get("Industry", row.get("industry", row.get("sector_name", "Diversified"))))
        or "Diversified"
    ).strip()
    weight = row.get("weight", row.get("final_weight", row.get("exposure", 0.0)))
    try:
        weight_value = float(weight or 0.0)
    except Exception:
        weight_value = 0.0
    if weight_value > 1.0 and weight_value <= 100.0:
        weight_value /= 100.0

    normalized = dict(row)
    normalized["symbol"] = symbol
    normalized["ticker"] = symbol
    normalized["sector"] = sector
    normalized["weight"] = weight_value
    return normalized


def build_intelligence_state(args: argparse.Namespace) -> MarketIntelligenceState:
    as_of = datetime.fromisoformat(f"{args.date}T09:15:00")
    shock_type = ShockType(args.shock)
    severity = ShockSeverity[args.severity]
    secondary = ShockType(args.secondary_shock) if args.secondary_shock else None

    profile = get_shock_profile(shock_type.value)
    market_impact = float(profile.get("market_level_impact", 0.0) or 0.0)
    if market_impact > 0.0:
        direction = ShockDirection.BULLISH
    elif market_impact < 0.0:
        direction = ShockDirection.BEARISH
    else:
        direction = ShockDirection.NEUTRAL

    vix_level = float(args.vix_level) if args.vix_level is not None else _default_vix(severity)
    engine = SectorImpactEngine()
    sector_impacts = engine.compute(
        primary_shock_type=shock_type,
        secondary_shock_type=secondary,
        shock_severity=severity,
        shock_direction=direction,
        company_signals=[],
        market_signals=[],
        macro_signals=[],
    )

    state = MarketIntelligenceState(
        computed_at=as_of,
        primary_shock_type=shock_type,
        secondary_shock_type=secondary,
        shock_severity=severity,
        shock_direction=direction,
        shock_confidence=0.92 if shock_type != ShockType.NONE else 0.0,
        shock_detected_at=as_of if shock_type != ShockType.NONE else None,
        shock_description=f"Scenario replay for {shock_type.value}",
        rbi_stance="hawkish" if "rate_hike" in shock_type.value else "neutral",
        global_risk_appetite="risk_off" if direction == ShockDirection.BEARISH else "risk_on",
        crude_direction=ShockDirection.BEARISH if args.crude_change_pct > 0 else ShockDirection.BULLISH if args.crude_change_pct < 0 else ShockDirection.NEUTRAL,
        crude_change_pct=float(args.crude_change_pct or 0.0),
        inr_direction=ShockDirection.BEARISH if args.inr_change_pct < 0 else ShockDirection.BULLISH if args.inr_change_pct > 0 else ShockDirection.NEUTRAL,
        inr_change_pct=float(args.inr_change_pct or 0.0),
        vix_level=vix_level,
        iv_regime=iv_regime_from_vix(vix_level),
        sector_impacts=sector_impacts,
        requires_immediate_hedge=severity >= ShockSeverity.HIGH,
        requires_portfolio_rebalance=any(item.rebalance_required for item in sector_impacts.values()),
        options_opportunity_detected=any(item.opportunity_trade for item in sector_impacts.values()) or severity == ShockSeverity.NONE,
        sources_used=["shock_scenario_runner"],
        freshness_minutes=0.0,
        is_stale=False,
        available=True,
    )

    selector = StrategySelector({})
    state.selected_option_strategies = selector.select(
        state,
        current_iv_surface={
            "vix": vix_level,
            "iv_rank": selector.estimate_iv_rank(vix_level),
            "nifty_intraday_fall_pct": abs(market_impact) * 100.0,
        },
    )
    return state


def augment_positions_for_scenario(
    positions: list[dict[str, Any]],
    state: MarketIntelligenceState,
) -> tuple[list[dict[str, Any]], list[str]]:
    augmented = [dict(row) for row in positions]
    existing_symbols = {_normalize_symbol(row.get("symbol", row.get("ticker", ""))) for row in augmented}
    injected: list[str] = []

    negative_sector = min(
        state.sector_impacts.values(),
        key=lambda item: float(item.impact_score),
        default=None,
    )
    if negative_sector:
        for ticker in negative_sector.key_tickers_at_risk:
            symbol = _normalize_symbol(ticker)
            if not symbol or symbol in existing_symbols:
                continue
            augmented.append(
                {
                    "symbol": symbol,
                    "ticker": symbol,
                    "sector": negative_sector.sector,
                    "weight": 0.045,
                    "adv": 0.01,
                    "scenario_injected": True,
                }
            )
            existing_symbols.add(symbol)
            injected.append(symbol)
            break

    opportunity_underlying = None
    for item in state.selected_option_strategies:
        if str(item.get("strategy", "")) == "long_call":
            opportunity_underlying = _normalize_symbol(item.get("underlying", ""))
            break
    if opportunity_underlying and opportunity_underlying not in existing_symbols:
        beneficiary_sector_name = None
        for sector_name, impact in state.sector_impacts.items():
            if opportunity_underlying in {_normalize_symbol(ticker) for ticker in impact.key_tickers_to_benefit}:
                beneficiary_sector_name = sector_name
                break
        augmented.append(
            {
                "symbol": opportunity_underlying,
                "ticker": opportunity_underlying,
                "sector": beneficiary_sector_name or "Diversified",
                "weight": 0.020,
                "adv": 1.0,
                "scenario_injected": True,
            }
        )
        existing_symbols.add(opportunity_underlying)
        injected.append(opportunity_underlying)

    return augmented, injected


def print_sector_vector(state: MarketIntelligenceState) -> None:
    print("Sector Impact Vector")
    print("====================")
    for sector, impact in sorted(state.sector_impacts.items(), key=lambda item: item[0]):
        print(
            f"{sector:35s} "
            f"score={impact.impact_score:+.2f} "
            f"move={impact.estimated_sector_move_pct:+.2f}% "
            f"horizon={impact.time_horizon_days}d"
        )
    print()


def print_position_exposures(state: MarketIntelligenceState, positions: list[dict[str, Any]]) -> None:
    scorer = PositionRiskScorer()
    scores = scorer.score_positions(state, positions)
    print("Positions Ranked By Shock Exposure")
    print("==================================")
    for score in scores[:10]:
        print(
            f"{score.symbol:12s} sector={score.sector:30s} "
            f"weight={float(score.current_weight):.4f} "
            f"sector_score={score.sector_impact_score:+.2f} "
            f"exposure={score.exposure_score:+.3f}"
        )
    print()


def print_response_plan(state: MarketIntelligenceState, positions: list[dict[str, Any]]) -> None:
    engine = ShockResponseEngine({})
    plan = engine.evaluate(state, positions)

    print("Rebalance Instructions")
    print("======================")
    if not plan.rebalance_instructions:
        print("No rebalance instructions.")
    for item in plan.rebalance_instructions:
        print(
            f"{item.instruction_type.value:20s} {item.symbol:12s} urgency={item.urgency.value:9s} "
            f"delta={item.target_weight_change:+.4f} rationale={item.rationale}"
        )
    print()

    print("Options Instructions")
    print("====================")
    if not plan.options_instructions:
        print("No options instructions.")
    for item in plan.options_instructions:
        print(
            f"{item.strategy:22s} {item.underlying:12s} urgency={item.urgency.value:9s} "
            f"lots={item.sizing_lots:2d} rationale={item.rationale}"
        )
    print()

    baseline_drawdown = estimate_portfolio_drawdown_pct(positions, state.sector_impacts)
    protected_drawdown = estimate_post_brain_drawdown_pct(baseline_drawdown, plan.options_instructions)
    protection = baseline_drawdown - protected_drawdown

    print("Protection Estimate")
    print("===================")
    print(f"Without brain: {baseline_drawdown:+.2f}% expected portfolio move")
    print(f"With brain:    {protected_drawdown:+.2f}% expected portfolio move")
    print(f"Protection:    {protection:+.2f}% expected P&L improvement")
    print()


def print_selected_strategies(state: MarketIntelligenceState) -> None:
    print("Strategy Library Recommendations")
    print("================================")
    if not state.selected_option_strategies:
        print("No strategy recommendations.")
        print()
        return

    executor = StrategyExecutor()
    for item in state.selected_option_strategies:
        strategy = str(item.get("strategy", "") or "")
        underlying = str(item.get("underlying", "") or "")
        sizing_lots = int(item.get("sizing_lots", 1) or 1)
        allocation_pct = float(item.get("allocation_pct", 0.0) or 0.0)
        urgency = str(item.get("urgency", "normal") or "normal")
        objective = str(item.get("objective", "") or "")
        rationale = str(item.get("rationale", "") or "")
        print(
            f"{strategy:22s} {underlying:12s} urgency={urgency:9s} "
            f"alloc={allocation_pct:.2f}% lots={sizing_lots:2d} objective={objective}"
        )
        if rationale:
            print(f"  rationale: {rationale}")
        try:
            built = executor.build(
                strategy,
                underlying,
                spot_price=_spot_price_for_underlying(underlying),
                sizing_lots=sizing_lots,
                as_of_datetime=state.computed_at,
            )
            for leg in built["legs"]:
                print(
                    "  "
                    f"{leg['action']:4s} {leg['instrument_type']:7s} "
                    f"strike={leg['strike']:.2f} expiry={leg['expiry']} qty={leg['quantity']}"
                )
        except Exception as exc:
            print(f"  leg build failed: {exc}")
    print()


def estimate_portfolio_drawdown_pct(
    positions: list[dict[str, Any]],
    sector_impacts: dict[str, Any],
) -> float:
    total_move = 0.0
    for row in positions:
        sector = str(row.get("sector", "Diversified") or "Diversified")
        weight = float(row.get("weight", 0.0) or 0.0)
        impact = sector_impacts.get(sector)
        move_pct = float(getattr(impact, "estimated_sector_move_pct", 0.0) or 0.0)
        total_move += weight * move_pct
    return float(total_move)


def estimate_post_brain_drawdown_pct(
    baseline_drawdown_pct: float,
    option_instructions: list[Any],
) -> float:
    hedge_coverage = 0.0
    coverage_map = {
        "protective_put": 0.30,
        "bear_put_spread": 0.35,
        "ratio_put_spread": 0.40,
        "delta_hedge_synthetic": 0.60,
        "vix_spike_put_spread": 0.20,
        "long_strangle": 0.12,
        "long_straddle": 0.12,
        "long_call": 0.08,
        "bull_call_spread": 0.10,
    }
    for item in option_instructions:
        hedge_coverage += coverage_map.get(str(getattr(item, "strategy", "") or ""), 0.0)
    hedge_coverage = min(0.85, hedge_coverage)
    return float(baseline_drawdown_pct * (1.0 - hedge_coverage))


def _normalize_symbol(value: Any) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()


def _default_vix(severity: ShockSeverity) -> float:
    if severity >= ShockSeverity.EXTREME:
        return 32.0
    if severity >= ShockSeverity.SEVERE:
        return 24.0
    if severity >= ShockSeverity.HIGH:
        return 21.0
    if severity >= ShockSeverity.MODERATE:
        return 17.0
    return 14.0


def _spot_price_for_underlying(underlying: str) -> float:
    symbol = _normalize_symbol(underlying)
    default_map = {
        "NIFTY": 22500.0,
        "BANKNIFTY": 48000.0,
        "FINNIFTY": 22500.0,
        "ONGC": 285.0,
        "INDIGO": 4100.0,
        "RELIANCE": 2950.0,
        "TCS": 4100.0,
        "INFY": 1650.0,
        "HDFCBANK": 1500.0,
        "ICICIBANK": 1100.0,
        "SBIN": 780.0,
    }
    return float(default_map.get(symbol, 1000.0))


def main() -> int:
    args = parse_args()
    state = build_intelligence_state(args)
    positions = load_positions(args.portfolio)
    positions, injected = augment_positions_for_scenario(positions, state)

    print(f"Scenario Date: {args.date}")
    print(f"Shock: {state.primary_shock_type.value}")
    print(f"Severity: {state.shock_severity.name}")
    print(f"Direction: {state.shock_direction.value}")
    print(f"VIX Level: {state.vix_level:.2f} ({state.iv_regime.value})")
    print(f"Crude Change: {state.crude_change_pct:+.2f}%")
    print(f"INR Change: {state.inr_change_pct:+.2f}%")
    if injected:
        print(f"Representative scenario positions injected: {', '.join(injected)}")
    print()

    print_sector_vector(state)
    print_selected_strategies(state)
    print_position_exposures(state, positions)
    print_response_plan(state, positions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
