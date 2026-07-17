from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Iterable, Optional, Protocol

from src.risk.risk_policy import RiskPolicy
from src.risk.risk_types import RiskDecision, RiskState, TradeProposal
from src.alternative_data import RiskAlternativeBridge


class Clock(Protocol):
    def now(self) -> datetime:
        ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class RiskController:
    def __init__(self, policy: RiskPolicy, clock: Optional[Clock] = None, registry=None, config: dict = None):
        self.policy = policy
        self.clock = clock or SystemClock()
        
        # GAP 3: Initialize risk bridge for pledge-based checks
        self.risk_bridge = None
        self.use_alternative_risk = False
        if registry is not None:
            try:
                self.risk_bridge = RiskAlternativeBridge(registry, config or {})
                self.use_alternative_risk = True
                print("🟢 Alternative risk checks enabled in RiskController")
            except Exception as e:
                print(f"⚠️ Could not initialize alternative risk: {e}")

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
        
        # GAP 3: Check alternative risk (pledge, credit distress)
        if self.use_alternative_risk and hasattr(proposal, 'symbol'):
            alt_risk_check = self._check_alternative_risk(proposal, now)
            if not alt_risk_check['allowed']:
                return self._reject(
                    state,
                    alt_risk_check['reason'],
                    alt_risk_check['reason_code'],
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
    
    def _check_alternative_risk(self, proposal: TradeProposal, now: datetime) -> dict:
        """
        GAP 3: Check alternative risk factors (pledge, credit distress).
        
        Returns dict with 'allowed', 'reason', 'reason_code'
        """
        if self.risk_bridge is None:
            return {'allowed': True, 'reason': '', 'reason_code': ''}
        
        try:
            ticker = proposal.symbol  # Use symbol field from TradeProposal
            proposed_weight = float(proposal.proposed_position_risk_pct)
            
            # Get new position risk check from bridge
            risk_check = self.risk_bridge.get_new_position_risk_check(
                as_of_date=now,
                ticker=ticker,
                proposed_weight=proposed_weight
            )
            
            # Block if status is BLOCK
            if risk_check['status'] == 'BLOCK':
                return {
                    'allowed': False,
                    'reason': f"Alternative risk check failed: {risk_check['rationale']}",
                    'reason_code': 'ALTERNATIVE_RISK_BLOCK'
                }
            
            # Allow (with potential warning logged)
            if risk_check['status'] == 'WARN':
                print(f"⚠️ Alternative risk warning for {ticker}: {risk_check['rationale']}")
            
            return {'allowed': True, 'reason': '', 'reason_code': ''}
            
        except Exception as e:
            # Graceful degradation: allow trade if alternative risk check fails
            print(f"⚠️ Alternative risk check error: {e}")
            return {'allowed': True, 'reason': '', 'reason_code': ''}
