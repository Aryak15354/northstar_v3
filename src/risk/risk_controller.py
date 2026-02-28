from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Iterable, Optional, Protocol

from src.risk.risk_policy import RiskPolicy
from src.risk.risk_types import RiskDecision, RiskState, TradeProposal


class Clock(Protocol):
    def now(self) -> datetime:
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class RiskController:
    def __init__(self, policy: RiskPolicy, clock: Optional[Clock] = None):
        self.policy = policy
        self.clock = clock or SystemClock()

    def evaluate_trade(
        self,
        proposal: TradeProposal,
        state: RiskState,
        open_positions: Optional[Iterable[object]] = None,
        event_calendar_dates: Optional[Iterable[date]] = None,
    ) -> RiskDecision:
        """Central risk gate for all trade proposals.

        All percentages are decimals. This method is deterministic for a fixed
        `(proposal, state, policy, clock.now())` tuple.
        """

        _ = open_positions  # Reserved for richer position-aware checks.
        now = self.clock.now()

        if state.kill_switch_active:
            return self._reject(
                state,
                "Kill switch active",
                "KILL_SWITCH_ACTIVE",
                state.current_portfolio_risk_pct,
                now,
            )

        if self._is_stale_event_calendar(now, event_calendar_dates):
            if self.policy.strict_mode:
                return self._reject(
                    state,
                    "Event calendar stale in strict mode",
                    "EVENT_CALENDAR_STALE",
                    state.current_portfolio_risk_pct,
                    now,
                )

        if state.event_block_active:
            return self._reject(
                state,
                "Event block active",
                "EVENT_BLOCK_ACTIVE",
                state.current_portfolio_risk_pct,
                now,
            )

        if state.drawdown_pct > self.policy.max_drawdown_pct + self.policy.epsilon:
            return self._reject(
                state,
                "Max drawdown exceeded",
                "MAX_DRAWDOWN_EXCEEDED",
                state.current_portfolio_risk_pct,
                now,
            )

        if state.weekly_trade_count >= self.policy.weekly_trade_cap:
            return self._reject(
                state,
                "Weekly trade cap exceeded",
                "WEEKLY_TRADE_CAP_EXCEEDED",
                state.current_portfolio_risk_pct,
                now,
            )

        proposed_risk = float(proposal.proposed_position_risk_pct)
        if not (0.0 < proposed_risk < 1.0):
            return self._reject(
                state,
                "Invalid proposed position risk pct",
                "INVALID_POSITION_RISK_PCT",
                state.current_portfolio_risk_pct,
                now,
            )

        if proposed_risk > self.policy.max_position_risk_pct + self.policy.epsilon:
            return self._reject(
                state,
                "Position risk cap exceeded",
                "POSITION_RISK_CAP_EXCEEDED",
                state.current_portfolio_risk_pct,
                now,
            )

        projected_risk = (
            float(state.current_portfolio_risk_pct)
            + float(state.in_flight_portfolio_risk_pct)
            + proposed_risk
        )

        if projected_risk > self.policy.portfolio_risk_cap_pct + self.policy.epsilon:
            return self._reject(
                state,
                "Portfolio risk cap exceeded",
                "PORTFOLIO_RISK_CAP_EXCEEDED",
                projected_risk,
                now,
            )

        return self._approve(
            state,
            "Risk checks passed",
            "RISK_APPROVED",
            projected_risk,
            now,
            extra={
                "proposal": asdict(proposal),
                "policy": self.policy.as_dict(),
            },
        )

    def _is_stale_event_calendar(
        self,
        now: datetime,
        event_calendar_dates: Optional[Iterable[date]],
    ) -> bool:
        if not event_calendar_dates:
            return True
        max_date = max(event_calendar_dates)
        if isinstance(max_date, datetime):
            max_date = max_date.date()
        if not isinstance(max_date, date):
            return True
        age_days = (now.date() - max_date).days
        return age_days > self.policy.event_calendar_max_age_days

    def _approve(
        self,
        state: RiskState,
        reason: str,
        reason_code: str,
        projected_risk: float,
        now: datetime,
        extra: Optional[dict] = None,
    ) -> RiskDecision:
        return RiskDecision(
            allowed=True,
            reason=reason,
            policy_hash=self.policy.policy_hash,
            equity_snapshot=float(state.current_equity),
            decision_ts=now.isoformat(),
            decision_reason_code=reason_code,
            projected_portfolio_risk_pct=float(projected_risk),
            metadata=extra or {},
        )

    def _reject(
        self,
        state: RiskState,
        reason: str,
        reason_code: str,
        projected_risk: float,
        now: datetime,
    ) -> RiskDecision:
        return RiskDecision(
            allowed=False,
            reason=reason,
            policy_hash=self.policy.policy_hash,
            equity_snapshot=float(state.current_equity),
            decision_ts=now.isoformat(),
            decision_reason_code=reason_code,
            projected_portfolio_risk_pct=float(projected_risk),
            metadata={"policy": self.policy.as_dict()},
        )
