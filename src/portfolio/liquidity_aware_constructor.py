#!/usr/bin/env python3
"""
Liquidity-aware portfolio construction.

Builds executable portfolios by combining ADV constraints, stress reductions,
and explicit cash buffering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import numpy as np

from src.intelligence.adv_database import ADVDatabase, LiquidityTier
from src.intelligence.position_governor import PositionGovernor


@dataclass
class LiquidityConstructionResult:
    """Result payload for liquidity-aware construction."""

    weights: Dict[str, float]
    cash_weight: float
    rejected_positions: Dict[str, str]
    capped_positions: Dict[str, float]
    redistributed_weight: float
    market_stress_applied: bool


class LiquidityAwarePortfolioConstructor:
    """
    Construct portfolios that remain executable under liquidity constraints.

    Guarantees:
    - All symbols are checked for ADV before final construction.
    - Symbols below minimum ADV threshold are rejected.
    - 20% minimum cash buffer by default.
    - Optional 50% stress reduction.
    """

    def __init__(
        self,
        adv_database: ADVDatabase,
        position_governor: PositionGovernor,
        min_cash_buffer: float = 0.20,
        stress_reduction_factor: float = 0.50,
    ) -> None:
        self.adv_database = adv_database
        self.position_governor = position_governor
        self.min_cash_buffer = float(min_cash_buffer)
        self.stress_reduction_factor = float(stress_reduction_factor)

    def construct_portfolio(
        self,
        target_weights: Dict[str, float],
        portfolio_value: float,
        *,
        market_stress: bool = False,
        as_of_date: Optional[datetime] = None,
    ) -> LiquidityConstructionResult:
        """Apply liquidity constraints and return executable portfolio weights."""

        symbols = list(target_weights.keys())
        adv_map = self.adv_database.get_adv_for_symbols(symbols, as_of_date=as_of_date)

        rejected: Dict[str, str] = {}
        prefiltered: Dict[str, float] = {}
        for symbol, weight in target_weights.items():
            adv = adv_map.get(symbol)
            if adv is None:
                rejected[symbol] = "no_adv_data"
                continue
            if adv.liquidity_tier == LiquidityTier.MICRO_CAP:
                rejected[symbol] = "adv_below_minimum"
                continue
            prefiltered[symbol] = float(weight)

        constrained = self.position_governor.apply_liquidity_constraints(
            prefiltered,
            portfolio_value=portfolio_value,
            as_of_date=as_of_date,
        )

        capped: Dict[str, float] = {}
        for symbol, old_w in prefiltered.items():
            new_w = float(constrained.get(symbol, 0.0))
            if abs(new_w) + 1e-12 < abs(old_w):
                capped[symbol] = old_w - new_w

        if market_stress:
            constrained = {
                s: float(w) * self.stress_reduction_factor
                for s, w in constrained.items()
            }

        # Keep long-only gross within available invested capital budget.
        long_weights = {s: max(0.0, float(w)) for s, w in constrained.items()}
        gross_long = float(sum(long_weights.values()))
        max_invested = max(0.0, 1.0 - self.min_cash_buffer)

        redistributed = 0.0
        if gross_long > max_invested and gross_long > 0:
            scale = max_invested / gross_long
            for s in long_weights:
                before = long_weights[s]
                long_weights[s] = before * scale
            redistributed = gross_long - max_invested
        elif gross_long < max_invested:
            # Redistribute spare capacity to most liquid names that survived.
            spare = max_invested - gross_long
            liquid_rank = sorted(
                [s for s in long_weights.keys()],
                key=lambda sym: float(getattr(adv_map.get(sym), "adv_21d", 0.0)),
                reverse=True,
            )
            if liquid_rank:
                total_rank = sum(range(1, len(liquid_rank) + 1))
                for i, sym in enumerate(liquid_rank, start=1):
                    # Heavier boost to more liquid names.
                    add = spare * (len(liquid_rank) - i + 1) / total_rank
                    long_weights[sym] += add
                redistributed = spare

        cash_weight = float(max(0.0, 1.0 - sum(long_weights.values())))
        if cash_weight < self.min_cash_buffer:
            deficit = self.min_cash_buffer - cash_weight
            total = sum(long_weights.values())
            if total > 0:
                shrink = max(0.0, (total - deficit) / total)
                for s in long_weights:
                    long_weights[s] *= shrink
            cash_weight = float(max(0.0, 1.0 - sum(long_weights.values())))

        clean_weights = {
            s: float(np.clip(w, 0.0, 1.0))
            for s, w in long_weights.items()
            if w > 1e-9
        }
        clean_weights["CASH"] = cash_weight

        return LiquidityConstructionResult(
            weights=clean_weights,
            cash_weight=cash_weight,
            rejected_positions=rejected,
            capped_positions=capped,
            redistributed_weight=float(max(0.0, redistributed)),
            market_stress_applied=bool(market_stress),
        )

