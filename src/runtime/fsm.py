"""Deterministic execution finite state machine for proposal lifecycle."""

from __future__ import annotations

from typing import Dict, Iterable, Set

from .contracts import ExecutionEventType


class ExecutionFSM:
    """Replay-stable finite state machine for execution event sequencing."""

    _ALLOWED: Dict[str, Set[ExecutionEventType]] = {
        "NONE": {ExecutionEventType.INTENT_SUBMITTED},
        "INTENT_SUBMITTED": {
            ExecutionEventType.INTENT_APPROVED,
            ExecutionEventType.INTENT_REJECTED,
        },
        "INTENT_APPROVED": {
            ExecutionEventType.ORDER_SENT,
            ExecutionEventType.ORDER_CANCELLED,
        },
        "ORDER_SENT": {
            ExecutionEventType.ORDER_PARTIAL,
            ExecutionEventType.ORDER_FILLED,
            ExecutionEventType.ORDER_CANCELLED,
        },
        "ORDER_PARTIAL": {
            ExecutionEventType.ORDER_PARTIAL,
            ExecutionEventType.ORDER_FILLED,
            ExecutionEventType.ORDER_CANCELLED,
        },
        "ORDER_FILLED": {
            ExecutionEventType.RECONCILIATION_APPLIED,
            ExecutionEventType.POSITION_ADJUSTED,
            ExecutionEventType.CORPORATE_ACTION_APPLIED,
            ExecutionEventType.MARK_TO_MARKET,
        },
        "RECONCILIATION_APPLIED": {
            ExecutionEventType.POSITION_ADJUSTED,
            ExecutionEventType.CORPORATE_ACTION_APPLIED,
            ExecutionEventType.MARK_TO_MARKET,
        },
        "POSITION_ADJUSTED": {
            ExecutionEventType.RECONCILIATION_APPLIED,
            ExecutionEventType.CORPORATE_ACTION_APPLIED,
            ExecutionEventType.MARK_TO_MARKET,
        },
        "CORPORATE_ACTION_APPLIED": {
            ExecutionEventType.RECONCILIATION_APPLIED,
            ExecutionEventType.POSITION_ADJUSTED,
            ExecutionEventType.MARK_TO_MARKET,
        },
        "MARK_TO_MARKET": {
            ExecutionEventType.RECONCILIATION_APPLIED,
            ExecutionEventType.POSITION_ADJUSTED,
            ExecutionEventType.CORPORATE_ACTION_APPLIED,
            ExecutionEventType.MARK_TO_MARKET,
        },
        "INTENT_REJECTED": set(),
        "ORDER_CANCELLED": set(),
    }

    def __init__(self) -> None:
        self._states: Dict[str, str] = {}

    def state_for(self, proposal_id: str) -> str:
        return self._states.get(str(proposal_id), "NONE")

    def allowed_events(self, proposal_id: str) -> Iterable[ExecutionEventType]:
        return self._ALLOWED.get(self.state_for(proposal_id), set())

    def transition(self, proposal_id: str, event_type: ExecutionEventType) -> str:
        pid = str(proposal_id)
        current = self.state_for(pid)
        allowed = self._ALLOWED.get(current, set())
        if event_type not in allowed:
            raise ValueError(
                f"invalid_execution_transition proposal_id={pid} current={current} next={event_type.value}"
            )
        next_state = event_type.value
        self._states[pid] = next_state
        return next_state

    def force_set(self, proposal_id: str, state: str) -> None:
        self._states[str(proposal_id)] = str(state)
