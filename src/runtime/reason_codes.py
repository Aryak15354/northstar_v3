"""Canonical reason code dictionary for runtime decisions and events."""

from __future__ import annotations

REASON_CODE_VERSION = "v1"

REASON_CODES = {
    "proposal.runtime.default": "Default runtime proposal reason.",
    "certification.missing_snapshot": "Certification snapshot hash not found.",
    "certification.ttl_expired": "Certification snapshot TTL expired.",
    "certification.context_mismatch": "Certification context hash mismatch.",
    "certification.feature_drift_breach": "Feature drift breach invalidated certification.",
    "capital.reserve_unavailable": "Requested notional exceeds reserve pool capacity.",
    "capital.request_non_positive": "Requested notional is non-positive.",
    "capital.phase3_deterministic_fail": "Phase 3 deterministic qualification failed for this proposal.",
    "capital.phase3_monte_carlo_fail": "Phase 3 Monte Carlo stability qualification failed for this proposal.",
    "capital.phase3_reject": "Phase 3 deployment qualification rejected this proposal.",
    "risk.gross_cap_breach": "Projected gross exposure breaches cap.",
    "risk.net_cap_breach": "Projected net exposure breaches cap.",
    "risk.sector_cap_breach": "Projected sector exposure breaches cap.",
    "risk.vol_adjusted_cap_breach": "Projected vol-adjusted exposure breaches cap.",
    "risk.strategy_cap_breach": "Projected strategy exposure breaches cap.",
    "risk.origin_cap_breach": "Projected origin exposure breaches cap.",
    "risk.stress_cap_breach": "Projected stress risk breaches cap.",
    "risk.freeze_active": "Runtime is globally frozen; only close_only orders are allowed.",
    "risk.runtime_frozen_close_only": "Runtime state is FROZEN and proposal is not close_only.",
    "risk.post_fill_budget_breach": "Post-fill realized exposure breached approved risk budget.",
    "risk.phase3_capacity_breach": "Live strategy notional breached Phase 3 capacity envelope.",
    "risk.phase3_live_sharpe_breach": "Live rolling Sharpe breached Phase 3 Monte Carlo floor.",
    "risk.phase3_live_drawdown_breach": "Live drawdown breached Phase 3 stress envelope.",
    "risk.phase6_capacity_breach": "Phase 6 mortality monitor detected live notional beyond qualified capacity.",
    "risk.phase6_drawdown_tail_breach": "Phase 6 mortality monitor detected drawdown beyond structural tail envelope.",
    "risk.phase6_critical_regret": "Phase 6 mortality monitor detected persistent critical regret.",
    "risk.phase6_posterior_collapse": "Phase 6 mortality monitor detected posterior edge confidence collapse.",
    "risk.phase6_shadow_mode": "Strategy is in Phase 6 shadow mode; new open risk is blocked.",
    "risk.phase6_alpha_frozen": "Strategy is frozen by Phase 6 mortality controller.",
    "risk.phase6_retired": "Strategy is retired by Phase 6 mortality controller.",
    "risk.options_missing_greeks": "Options proposal is missing required Greeks in strict mode.",
    "liquidity.adv_participation_breach": "Order ADV participation exceeds threshold.",
    "liquidity.spread_breach": "Order spread exceeds threshold.",
    "liquidity.depth_breach": "Order depth is insufficient.",
    "liquidity.slippage_breach": "Estimated slippage exceeds threshold.",
    "rebalance.regime_shift": "Regime transition triggered rebalance.",
    "rebalance.volatility_shock": "Volatility percentile shock triggered rebalance.",
    "rebalance.drawdown_breach": "Drawdown threshold triggered rebalance.",
    "rebalance.correlation_spike": "Correlation spike triggered rebalance.",
    "rebalance.signal_entropy_collapse": "Signal entropy collapse triggered rebalance.",
    "rebalance.risk_budget_breach": "Risk budget breach triggered rebalance.",
    "runtime.truth_drift": "Live/shadow/derived truth drift detected.",
}


def is_known_reason_code(code: str) -> bool:
    return str(code or "") in REASON_CODES
