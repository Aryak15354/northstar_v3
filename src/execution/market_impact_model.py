#!/usr/bin/env python3
"""
Market impact model for capacity-aware execution realism.

Implements a square-root impact function:
    impact = k * sigma * sqrt(order_size / ADV)
with dynamic k-factor and enhanced penalties for large ADV participation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class MarketImpactConfig:
    """Configuration for square-root impact modeling."""

    base_k: float = 0.15
    min_k: float = 0.10
    max_k: float = 0.30
    large_order_threshold: float = 0.10
    large_order_penalty: float = 2.0
    crisis_multiplier: float = 2.0


class MarketImpactModel:
    """Square-root market impact model with cumulative impact tracking."""

    def __init__(self, config: MarketImpactConfig | None = None):
        self.config = config or MarketImpactConfig()
        self._cumulative_impact: Dict[str, float] = {}

    def calculate_k_factor(
        self,
        volatility: float,
        market_stress: float = 0.0,
        regime: str = "normal",
    ) -> float:
        """Calculate dynamic k-factor within configured bounds."""

        vol_adj = max(0.0, float(volatility) - 0.20)
        stress_adj = max(0.0, float(market_stress))
        k = self.config.base_k * (1.0 + 2.0 * vol_adj + stress_adj)
        if str(regime).lower() in {"crisis", "panic", "hostile"}:
            k *= self.config.crisis_multiplier
        return float(min(self.config.max_k, max(self.config.min_k, k)))

    def calculate_impact(
        self,
        order_size: float,
        adv: float,
        volatility: float,
        market_stress: float = 0.0,
        regime: str = "normal",
        symbol: str | None = None,
    ) -> float:
        """
        Calculate fractional price impact for an order.

        Returns value in decimal form (e.g. 0.003 = 30 bps).
        """

        adv_val = float(adv)
        if adv_val <= 0:
            raise ValueError("ADV must be positive")

        order_val = max(0.0, float(order_size))
        participation = order_val / adv_val
        sigma = max(1e-6, float(volatility))
        k = self.calculate_k_factor(volatility=sigma, market_stress=market_stress, regime=regime)

        impact = k * sigma * math.sqrt(participation)
        if participation > self.config.large_order_threshold:
            overflow = participation - self.config.large_order_threshold
            impact *= 1.0 + overflow * self.config.large_order_penalty

        impact = float(max(0.0, impact))

        if symbol:
            self._cumulative_impact[symbol] = self._cumulative_impact.get(symbol, 0.0) + impact

        return impact

    def calculate_fill_price(
        self,
        mid_price: float,
        side: str,
        order_size: float,
        adv: float,
        volatility: float,
        market_stress: float = 0.0,
        regime: str = "normal",
        symbol: str | None = None,
    ) -> Tuple[float, float]:
        """Calculate realistic fill price from mid price and impact."""

        mid = float(mid_price)
        if mid <= 0:
            raise ValueError("mid_price must be positive")

        impact = self.calculate_impact(
            order_size=order_size,
            adv=adv,
            volatility=volatility,
            market_stress=market_stress,
            regime=regime,
            symbol=symbol,
        )
        direction = 1.0 if str(side).lower() == "buy" else -1.0
        fill_price = mid * (1.0 + direction * impact)
        return float(fill_price), float(impact)

    def get_cumulative_impact(self, symbol: str) -> float:
        """Get cumulative recorded impact for a symbol."""
        return float(self._cumulative_impact.get(symbol, 0.0))

    def reset_cumulative_impact(self) -> None:
        """Reset cumulative impact tracking."""
        self._cumulative_impact.clear()

