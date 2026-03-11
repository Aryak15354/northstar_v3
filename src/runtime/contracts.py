"""Canonical runtime contracts for the Portfolio Runtime Service (PRS)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ProposalOrigin(str, Enum):
    RESEARCH = "research"
    BACKTEST = "backtest"
    WALK_FORWARD = "walk_forward"
    SHADOW = "shadow"
    ALPHA_OS = "alpha_os"
    OPTIONS_ALPHA = "options_alpha"
    OPTIONS_HEDGE = "options_hedge"
    MANUAL = "manual"


class DecisionMode(str, Enum):
    AUTO = "auto"
    DISCRETIONARY = "discretionary"


class RuntimeState(str, Enum):
    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"


class ExecutionEventType(str, Enum):
    INTENT_SUBMITTED = "INTENT_SUBMITTED"
    INTENT_APPROVED = "INTENT_APPROVED"
    INTENT_REJECTED = "INTENT_REJECTED"
    ORDER_SENT = "ORDER_SENT"
    ORDER_PARTIAL = "ORDER_PARTIAL"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    RECONCILIATION_APPLIED = "RECONCILIATION_APPLIED"
    POSITION_ADJUSTED = "POSITION_ADJUSTED"
    CORPORATE_ACTION_APPLIED = "CORPORATE_ACTION_APPLIED"
    MARK_TO_MARKET = "MARK_TO_MARKET"


@dataclass(frozen=True)
class TradeProposal:
    proposal_id: str
    origin: ProposalOrigin
    strategy_id: str
    signal_id: str
    alpha_type: str
    expected_edge: float
    risk_score: float
    regime_context: Dict[str, Any]
    instrument_plan: Dict[str, Any]
    requested_notional: float
    certification_snapshot_hash: str
    decision_mode: DecisionMode = DecisionMode.AUTO
    trigger_reason_code: str = "proposal.runtime.default"
    risk_override_flag: bool = False
    operator_id: str = ""
    runtime_scope: str = "live"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["origin"] = str(self.origin.value)
        out["decision_mode"] = str(self.decision_mode.value)
        out["created_at"] = self.created_at.isoformat()
        return out


@dataclass(frozen=True)
class CertificationSnapshot:
    snapshot_hash: str
    model_hash: str
    param_hash: str
    feature_hash: str
    data_revision_hash: str
    config_hash: str
    created_at: datetime
    valid_until: datetime
    drift_guard_version: str = "v1"

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["created_at"] = self.created_at.isoformat()
        out["valid_until"] = self.valid_until.isoformat()
        return out


@dataclass(frozen=True)
class CertificationCheckResult:
    is_valid: bool
    reason: str
    snapshot_hash: str


@dataclass(frozen=True)
class CapitalDecision:
    decision_id: str
    is_approved: bool
    approved_notional: float
    reserve_pool: str
    reserve_impact: Dict[str, float]
    sizing_rationale: Dict[str, Any] = field(default_factory=dict)
    denial_reason: str = ""


@dataclass(frozen=True)
class BudgetDecision:
    decision_id: str
    is_approved: bool
    approved_notional: float
    denial_reason: str = ""
    cap_observations: Dict[str, Any] = field(default_factory=dict)
    post_fill_guard_required: bool = True


@dataclass(frozen=True)
class LiquidityDecision:
    decision_id: str
    is_approved: bool
    denial_reason: str = ""
    observations: Dict[str, Any] = field(default_factory=dict)
    min_fill_feasible: bool = True


@dataclass(frozen=True)
class ProposalReceipt:
    proposal_id: str
    submitted_event_id: int
    status: str


@dataclass(frozen=True)
class ExecutionEvent:
    event_type: ExecutionEventType
    proposal_id: str
    sequence_no: int
    timestamp_utc: datetime
    trigger_reason_code: str
    strategy_id: str
    signal_id: str
    certification_snapshot_hash: str
    risk_override_flag: bool
    decision_mode: DecisionMode
    origin: ProposalOrigin
    allocator_decision_id: str
    budget_decision_id: str
    liquidity_decision_id: str
    operator_id: str = ""
    runtime_scope: str = "live"
    payload: Dict[str, Any] = field(default_factory=dict)
    parent_event_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["event_type"] = self.event_type.value
        out["decision_mode"] = self.decision_mode.value
        out["origin"] = self.origin.value
        out["timestamp_utc"] = self.timestamp_utc.isoformat()
        return out


@dataclass(frozen=True)
class RebalanceTriggerDecision:
    rule_id: str
    trigger_reason_code: str
    input_hash: str
    threshold_values: Dict[str, float]
    decision: bool


@dataclass(frozen=True)
class StressScenarioResult:
    scenario_id: str
    pnl_impact: float
    risk_metric: float
    payload: Dict[str, Any]


@dataclass(frozen=True)
class PortfolioStateSnapshot:
    timestamp_utc: datetime
    cash: float
    net_liquidation_value: float
    gross_exposure: float
    net_exposure: float
    beta: float
    sector_allocation: Dict[str, float]
    regime_context: Dict[str, Any]
    hedging_state: Dict[str, Any]
    transaction_history: List[int]
    unrealized_pnl: float
    realized_pnl: float
    net_delta: float
    net_gamma: float
    net_vega: float
    net_theta: float
    net_rho: float
    holdings: Dict[str, Dict[str, Any]]
    last_rebalance_reason: str
    state_hash: str
    source_event_id: int = 0

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["timestamp_utc"] = self.timestamp_utc.isoformat()
        return out


@dataclass(frozen=True)
class ExecutionResult:
    proposal_id: str
    approved: bool
    status: str
    denial_reason: str = ""
    event_ids: List[int] = field(default_factory=list)
    capital_decision_id: str = ""
    budget_decision_id: str = ""
    liquidity_decision_id: str = ""
    stress_matrix: List[StressScenarioResult] = field(default_factory=list)
    rebalance_triggers: List[RebalanceTriggerDecision] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "approved": bool(self.approved),
            "status": self.status,
            "denial_reason": self.denial_reason,
            "event_ids": list(self.event_ids),
            "capital_decision_id": self.capital_decision_id,
            "budget_decision_id": self.budget_decision_id,
            "liquidity_decision_id": self.liquidity_decision_id,
            "stress_matrix": [asdict(s) for s in self.stress_matrix],
            "rebalance_triggers": [asdict(t) for t in self.rebalance_triggers],
        }


@dataclass(frozen=True)
class TruthDriftIncident:
    incident_id: str
    timestamp_utc: datetime
    live_state_hash: str
    shadow_state_hash: str
    derived_view_hash: str
    breach_count: int
    escalated_freeze: bool
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["timestamp_utc"] = self.timestamp_utc.isoformat()
        return out
