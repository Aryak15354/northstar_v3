"""Liquidity gate for ADV participation, spread, depth, and slippage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from uuid import uuid4

from .contracts import LiquidityDecision


@dataclass(frozen=True)
class LiquidityGateConfig:
    max_adv_participation: float = 0.10
    max_spread_bps: float = 120.0
    min_depth_multiple: float = 1.10
    max_slippage_bps: float = 75.0


class LiquidityGate:
    def __init__(self, config: LiquidityGateConfig | None = None):
        self.config = config or LiquidityGateConfig()

    def check(
        self,
        order_plan: Dict[str, Any],
        market_liquidity_snapshot: Dict[str, Any],
    ) -> LiquidityDecision:
        decision_id = f"liq_{uuid4().hex[:16]}"

        notional = float(order_plan.get("notional", 0.0) or 0.0)
        quantity = float(order_plan.get("quantity", 0.0) or 0.0)
        adv = float(market_liquidity_snapshot.get("adv_notional", 0.0) or 0.0)
        spread_bps = float(market_liquidity_snapshot.get("spread_bps", 0.0) or 0.0)
        depth_qty = float(market_liquidity_snapshot.get("depth_qty", 0.0) or 0.0)
        slippage_bps = float(market_liquidity_snapshot.get("estimated_slippage_bps", 0.0) or 0.0)

        participation = (notional / adv) if adv > 0 else 0.0
        depth_ok = True
        min_fill_feasible = True
        if quantity > 0:
            min_depth_required = quantity * float(self.config.min_depth_multiple)
            depth_ok = depth_qty >= min_depth_required
            min_fill_feasible = depth_qty >= max(1.0, quantity * 0.10)

        obs = {
            "notional": notional,
            "quantity": quantity,
            "adv_notional": adv,
            "adv_participation": participation,
            "spread_bps": spread_bps,
            "depth_qty": depth_qty,
            "estimated_slippage_bps": slippage_bps,
        }

        if adv > 0 and participation > float(self.config.max_adv_participation):
            return LiquidityDecision(decision_id, False, "liquidity.adv_participation_breach", obs, min_fill_feasible)
        if spread_bps > float(self.config.max_spread_bps):
            return LiquidityDecision(decision_id, False, "liquidity.spread_breach", obs, min_fill_feasible)
        if not depth_ok:
            return LiquidityDecision(decision_id, False, "liquidity.depth_breach", obs, min_fill_feasible)
        if slippage_bps > float(self.config.max_slippage_bps):
            return LiquidityDecision(decision_id, False, "liquidity.slippage_breach", obs, min_fill_feasible)

        return LiquidityDecision(decision_id, True, "", obs, min_fill_feasible)
