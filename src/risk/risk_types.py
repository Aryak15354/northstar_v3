from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True, slots=True)
class RiskState:
    current_equity: float
    peak_equity: float
    drawdown_pct: float
    current_portfolio_risk_pct: float
    weekly_trade_count: int
    event_block_active: bool = False
    kill_switch_active: bool = False
    in_flight_portfolio_risk_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class TradeProposal:
    symbol: str
    side: str
    quantity: float
    proposed_position_risk_pct: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RiskDecision:
    allowed: bool
    reason: str
    policy_hash: str
    equity_snapshot: float
    decision_ts: str
    decision_reason_code: str
    projected_portfolio_risk_pct: float
    metadata: Dict[str, Any] = field(default_factory=dict)
