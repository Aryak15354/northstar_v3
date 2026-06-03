from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Callable, Iterable, Optional

from src.risk.risk_controller import RiskController
from src.risk.risk_types import RiskDecision, RiskState, TradeProposal


ExecutionHandler = Callable[[TradeProposal, RiskDecision], dict]


class ExecutionGateway:
    """Only authority allowed to submit execution requests.

    `authorize` evaluates risk and returns a RiskDecision.
    `execute_trade` requires an approved RiskDecision and enforces freeze policy.
    """

    def __init__(self, risk_controller: RiskController, execution_handler: ExecutionHandler):
        self.risk_controller = risk_controller
        self.execution_handler = execution_handler
        self._risk_state_lock = RLock()
        self._in_flight_risk_pct = 0.0

    def authorize(
        self,
        proposal: TradeProposal,
        state: RiskState,
        open_positions: Optional[Iterable[object]] = None,
        event_calendar_dates: Optional[Iterable[object]] = None,
    ) -> RiskDecision:
        if self._is_trading_frozen():
            return RiskDecision(
                allowed=False,
                reason="Trading is frozen",
                policy_hash=self.risk_controller.policy.policy_hash,
                equity_snapshot=float(state.current_equity),
                decision_ts=self.risk_controller.clock.now().isoformat(),
                decision_reason_code="TRADING_FROZEN",
                projected_portfolio_risk_pct=float(state.current_portfolio_risk_pct),
                metadata={"freeze": self._freeze_state()},
            )

        with self._risk_state_lock:
            effective_state = RiskState(
                current_equity=state.current_equity,
                peak_equity=state.peak_equity,
                drawdown_pct=state.drawdown_pct,
                current_portfolio_risk_pct=state.current_portfolio_risk_pct,
                weekly_trade_count=state.weekly_trade_count,
                event_block_active=state.event_block_active,
                kill_switch_active=state.kill_switch_active,
                in_flight_portfolio_risk_pct=self._in_flight_risk_pct,
            )
            decision = self.risk_controller.evaluate_trade(
                proposal=proposal,
                state=effective_state,
                open_positions=open_positions,
                event_calendar_dates=event_calendar_dates,
            )
            if decision.allowed:
                self._in_flight_risk_pct += max(0.0, float(proposal.proposed_position_risk_pct))
            return decision

    def execute_trade(self, proposal: TradeProposal, decision: RiskDecision) -> dict:
        if not isinstance(decision, RiskDecision):
            raise RuntimeError("Trade not risk-evaluated: decision type invalid")
        if not decision.allowed:
            raise RuntimeError(
                f"Trade blocked by risk controller: {decision.decision_reason_code} {decision.reason}"
            )
        if self._is_trading_frozen():
            raise RuntimeError("Trading is frozen and execution is blocked")

        result = self.execution_handler(proposal, decision)

        with self._risk_state_lock:
            self._in_flight_risk_pct = max(
                0.0,
                self._in_flight_risk_pct - max(0.0, float(proposal.proposed_position_risk_pct)),
            )

        return {
            "status": "submitted",
            "symbol": proposal.symbol,
            "decision_reason_code": decision.decision_reason_code,
            "policy_hash": decision.policy_hash,
            "equity_snapshot": decision.equity_snapshot,
            "execution_result": result,
        }

    def _is_trading_frozen(self) -> bool:
        env_freeze = str(os.getenv("NORTHSTAR_TRADING_FREEZE", "0")).strip().lower()
        if env_freeze in {"1", "true", "yes", "on"}:
            return True
        freeze = self._freeze_state()
        return bool(freeze.get("freeze_active", False))

    def _freeze_state(self) -> dict:
        freeze_path = Path("data/processed/model_freeze_state.json")
        if not freeze_path.exists():
            return {}
        try:
            return json.loads(freeze_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
