#!/usr/bin/env python3
"""
Execution reality engine.

Simulates order splitting, TWAP-style fills, spread costs, and implementation
shortfall against theoretical mid-market execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import math
import numpy as np

from src.execution.market_impact_model import MarketImpactModel


@dataclass
class ExecutionSlice:
    """One child fill in a split execution plan."""

    day_index: int
    notional: float
    fill_price: float
    impact: float
    spread_bps: float


@dataclass
class ExecutionResult:
    """Execution simulation output."""

    symbol: str
    side: str
    order_notional: float
    adv: float
    num_slices: int
    average_fill_price: float
    theoretical_mid_price: float
    implementation_shortfall: float
    total_cost: float
    slices: List[ExecutionSlice]


class ExecutionRealityEngine:
    """
    Institutional-style execution simulator.

    Rules:
    - Orders >5% ADV are split across multiple days.
    - TWAP simulation for split child orders.
    - Spread model by liquidity tier, doubled in stress regime.
    - Implementation shortfall tracked vs theoretical mid fill.
    """

    def __init__(self, impact_model: MarketImpactModel | None = None) -> None:
        self.impact_model = impact_model or MarketImpactModel()
        self.spread_bps_by_tier: Dict[str, float] = {
            "large_cap": 5.0,
            "mid_cap": 12.0,
            "small_cap": 30.0,
            "micro_cap": 60.0,
        }

    def split_order_across_days(self, order_notional: float, adv: float) -> int:
        """Return number of execution days for order splitting (>5% ADV)."""

        adv_val = float(adv)
        if adv_val <= 0:
            raise ValueError("ADV must be positive")
        participation = abs(float(order_notional)) / adv_val
        if participation <= 0.05:
            return 1
        return int(math.ceil(participation / 0.05))

    def _spread_bps(self, tier: str, market_stress: bool) -> float:
        base = self.spread_bps_by_tier.get(str(tier).lower(), 12.0)
        return float(base * (2.0 if market_stress else 1.0))

    def simulate_execution(
        self,
        *,
        symbol: str,
        side: str,
        order_notional: float,
        mid_price: float,
        adv: float,
        volatility: float,
        liquidity_tier: str = "mid_cap",
        market_stress: bool = False,
    ) -> ExecutionResult:
        """
        Simulate realistic execution with impact + spread + slicing.
        """

        side_norm = str(side).lower()
        if side_norm not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if float(mid_price) <= 0:
            raise ValueError("mid_price must be positive")

        slices_n = self.split_order_across_days(order_notional, adv)
        child_notional = float(order_notional) / slices_n
        spread_bps = self._spread_bps(liquidity_tier, market_stress)
        spread_fraction = spread_bps / 10000.0
        regime = "crisis" if market_stress else "normal"
        direction = 1.0 if side_norm == "buy" else -1.0

        fills: List[ExecutionSlice] = []
        fill_prices: List[float] = []
        for i in range(slices_n):
            fill_price, impact = self.impact_model.calculate_fill_price(
                mid_price=float(mid_price),
                side=side_norm,
                order_size=abs(child_notional),
                adv=float(adv),
                volatility=float(max(1e-6, volatility)),
                market_stress=1.0 if market_stress else 0.0,
                regime=regime,
                symbol=symbol,
            )
            # Half-spread slippage on each side, signed by direction.
            fill_price = fill_price * (1.0 + direction * spread_fraction / 2.0)
            fills.append(
                ExecutionSlice(
                    day_index=i,
                    notional=abs(child_notional),
                    fill_price=float(fill_price),
                    impact=float(impact),
                    spread_bps=float(spread_bps),
                )
            )
            fill_prices.append(float(fill_price))

        avg_fill = float(np.mean(fill_prices)) if fill_prices else float(mid_price)
        theoretical = float(mid_price)
        shortfall_per_unit = (avg_fill - theoretical) * direction
        implementation_shortfall = float(max(0.0, shortfall_per_unit))
        total_cost = float(implementation_shortfall * (abs(order_notional) / theoretical))

        return ExecutionResult(
            symbol=str(symbol),
            side=side_norm,
            order_notional=float(order_notional),
            adv=float(adv),
            num_slices=int(slices_n),
            average_fill_price=avg_fill,
            theoretical_mid_price=theoretical,
            implementation_shortfall=implementation_shortfall,
            total_cost=total_cost,
            slices=fills,
        )

