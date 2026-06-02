from __future__ import annotations

import json
import sqlite3
import os
from datetime import datetime, timedelta, timezone

from src.runtime import (
    DecisionMode,
    PortfolioRuntimeService,
    ProposalOrigin,
    RuntimeState,
    TradeProposal,
    build_certification_snapshot,
)
from src.runtime.contracts import BudgetDecision, CapitalDecision
from src.runtime.hash_utils import canonical_hash, canonical_json_dumps
from src.runtime.rebalance_trigger import RebalanceTriggerEngine
from src.runtime.state import Holding, PortfolioState, state_hash_payload


def _make_prs(tmp_path):
    db = tmp_path / "portfolio_runtime.db"
    out = tmp_path / "derived"
    prs = PortfolioRuntimeService(db_path=str(db), materialized_output_dir=str(out), starting_cash=1000.0)
    snap = build_certification_snapshot(
        model_hash="m1",
        param_hash="p1",
        feature_hash="f1",
        data_revision_hash="d1",
        config_hash="c1",
        created_at=datetime.now(timezone.utc),
        ttl_days=30,
        drift_guard_version="v1",
    )
    prs.register_certification_snapshot(snap)
    context = {
        "model_hash": snap.model_hash,
        "param_hash": snap.param_hash,
        "feature_hash": snap.feature_hash,
        "data_revision_hash": snap.data_revision_hash,
        "config_hash": snap.config_hash,
        "drift_guard_version": snap.drift_guard_version,
    }
    return prs, snap, context


def test_capital_authority_limits_options_alpha(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)

    proposal = TradeProposal(
        proposal_id="prop_cap_1",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="short_strangle",
        signal_id="sig_cap_1",
        alpha_type="vol",
        expected_edge=0.2,
        risk_score=0.3,
        regime_context={"regime": "normal"},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 100.0,
            "sector": "financial services",
            "lifecycle_action": "open",
            "position_key": "cap_pos_1",
        },
        requested_notional=800.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )

    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 1_000_000.0,
            "spread_bps": 10.0,
            "depth_qty": 10_000.0,
            "estimated_slippage_bps": 5.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )

    assert res.approved
    snap_state = prs.get_portfolio_state()
    # options_alpha reserve defaults to 25% => <= 250 approved from 1000 NAV
    assert snap_state.gross_exposure <= 250.0 + 1e-6


def test_execution_lifecycle_intent_does_not_mutate_on_unfilled(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)

    proposal = TradeProposal(
        proposal_id="prop_lifecycle_1",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="long_straddle",
        signal_id="sig_lifecycle_1",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={"regime": "neutral"},
        instrument_plan={
            "symbol": "BANKNIFTY",
            "side": "buy",
            "price": 100.0,
            "quantity": 1.0,
            "sector": "financial services",
            "lifecycle_action": "open",
            "position_key": "life_pos_1",
        },
        requested_notional=100.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )

    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 1_000_000.0,
            "spread_bps": 2.0,
            "depth_qty": 1_000.0,
            "estimated_slippage_bps": 1.0,
        },
        risk_snapshot={"signal_entropy": 0.95, "risk_budget_ratio": 0.05},
        certification_context=ctx,
        auto_fill=False,
    )

    assert res.approved
    state = prs.get_portfolio_state()
    assert state.gross_exposure == 0.0
    assert state.cash == 1000.0


def test_certification_ttl_expiry_blocks_execution(tmp_path):
    db = tmp_path / "runtime_expiry.db"
    out = tmp_path / "derived_expiry"
    prs = PortfolioRuntimeService(db_path=str(db), materialized_output_dir=str(out), starting_cash=1000.0)

    stale = build_certification_snapshot(
        model_hash="m1",
        param_hash="p1",
        feature_hash="f1",
        data_revision_hash="d1",
        config_hash="c1",
        created_at=datetime.now(timezone.utc) - timedelta(days=40),
        ttl_days=30,
        drift_guard_version="v1",
    )
    prs.register_certification_snapshot(stale)

    proposal = TradeProposal(
        proposal_id="prop_expired_1",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="calendar_spread",
        signal_id="sig_expired_1",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={"symbol": "NIFTY", "side": "buy", "price": 10.0, "quantity": 1.0},
        requested_notional=10.0,
        certification_snapshot_hash=stale.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )

    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={"adv_notional": 10_000.0, "spread_bps": 1.0, "depth_qty": 100.0, "estimated_slippage_bps": 1.0},
        certification_context={
            "model_hash": stale.model_hash,
            "param_hash": stale.param_hash,
            "feature_hash": stale.feature_hash,
            "data_revision_hash": stale.data_revision_hash,
            "config_hash": stale.config_hash,
            "drift_guard_version": stale.drift_guard_version,
        },
    )

    assert not res.approved
    assert res.denial_reason == "certification.ttl_expired"


def test_rebalance_trigger_is_deterministic():
    engine = RebalanceTriggerEngine()
    portfolio = {
        "regime_transition_probability": 0.1,
        "drawdown_ratio": 0.09,
    }
    market = {
        "regime_transition_probability": 0.5,
        "vol_percentile_jump": 0.3,
        "correlation_spike": 0.2,
    }
    risk = {
        "signal_entropy": 0.2,
        "risk_budget_ratio": 1.1,
    }

    a = engine.evaluate(portfolio, market, risk)
    b = engine.evaluate(portfolio, market, risk)

    assert [x.__dict__ for x in a] == [x.__dict__ for x in b]


def test_truth_drift_monitor_detects_mismatch(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    proposal = TradeProposal(
        proposal_id="prop_drift_1",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="long_straddle",
        signal_id="sig_drift_1",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 5.0,
            "lifecycle_action": "open",
            "position_key": "drift_pos_1",
        },
        requested_notional=50.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    prs.process_proposal(
        proposal,
        market_liquidity_snapshot={"adv_notional": 100000.0, "spread_bps": 2.0, "depth_qty": 1000.0, "estimated_slippage_bps": 2.0},
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )

    incident = prs.run_truth_drift_check(shadow_state={"state_hash": "bad_hash"}, extra_derived_paths=[])
    assert incident is not None
    assert incident["breach_count"] >= 1


def test_portfolio_state_hash_ignores_snapshot_timestamp():
    state = PortfolioState.initialize(1000.0)
    state.holdings["NIFTY"] = Holding(
        symbol="NIFTY",
        instrument_type="option",
        quantity=2.0,
        avg_price=100.0,
        last_price=110.0,
        sector="financial services",
        strategy_id="s1",
        origin="options_alpha",
        greek_delta_per_unit=0.25,
    )
    state.realized_pnl = 5.0
    state.last_event_id = 7
    state._refresh_derived()

    snap_a = state.to_snapshot(timestamp=datetime(2026, 3, 19, 9, 0, tzinfo=timezone.utc))
    snap_b = state.to_snapshot(timestamp=datetime(2026, 3, 19, 15, 0, tzinfo=timezone.utc))

    assert snap_a.timestamp_utc != snap_b.timestamp_utc
    assert snap_a.state_hash == snap_b.state_hash


def test_replay_matches_legacy_snapshot_hash_payload(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    proposal = TradeProposal(
        proposal_id="prop_replay_legacy_1",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="legacy_replay",
        signal_id="sig_replay_legacy_1",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 5.0,
            "lifecycle_action": "open",
            "position_key": "legacy_replay_pos_1",
        },
        requested_notional=50.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 2.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )

    latest = prs.store.latest_snapshot()
    assert latest is not None
    latest_payload = json.loads(str(latest.get("state_json", "{}") or "{}"))
    legacy_hash = canonical_hash(
        {
            "timestamp_utc": latest_payload.get("timestamp_utc"),
            **state_hash_payload(latest_payload),
        }
    )
    latest_payload["state_hash"] = legacy_hash

    conn = sqlite3.connect(prs.store.db_path)
    with conn:
        conn.execute(
            """
            UPDATE portfolio_snapshots
            SET state_hash = ?, state_json = ?
            WHERE snapshot_id = (SELECT MAX(snapshot_id) FROM portfolio_snapshots)
            """,
            (legacy_hash, canonical_json_dumps(latest_payload)),
        )
    conn.close()

    replay = prs.replay()
    assert replay["deterministic_match"] is True


def test_replay_infers_starting_cash_and_latest_snapshot_boundary(tmp_path):
    db = tmp_path / "portfolio_runtime.db"
    out = tmp_path / "derived"
    prs, snap, ctx = _make_prs(tmp_path)

    filled = TradeProposal(
        proposal_id="prop_replay_boundary_fill",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="boundary_fill",
        signal_id="sig_boundary_fill",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 5.0,
            "lifecycle_action": "open",
            "position_key": "boundary_fill_pos",
        },
        requested_notional=50.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    prs.process_proposal(
        filled,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 2.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )

    prs.set_global_freeze(True, reason="test.freeze")
    rejected = TradeProposal(
        proposal_id="prop_replay_boundary_reject",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="boundary_reject",
        signal_id="sig_boundary_reject",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={"symbol": "BANKNIFTY", "side": "buy", "price": 10.0, "quantity": 1.0},
        requested_notional=10.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    res = prs.process_proposal(
        rejected,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 2.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )
    assert not res.approved
    prs.close()

    prs2 = PortfolioRuntimeService(db_path=str(db), materialized_output_dir=str(out), starting_cash=5000.0)
    replay = prs2.replay()
    assert replay["deterministic_match"] is True
    assert replay["inferred_starting_cash"] == 1000.0
    assert replay["replayed_to_event_id"] < max(
        int(row["event_id"]) for row in prs2.store.list_events(since_event_id=0)
    )
    prs2.close()


def test_runtime_freeze_blocks_open_allows_close_only(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    prs.set_global_freeze(True, reason="test.freeze")
    assert prs.runtime_state == RuntimeState.FROZEN

    open_proposal = TradeProposal(
        proposal_id="prop_freeze_open_1",
        origin=ProposalOrigin.SHADOW,
        strategy_id="shadow_open",
        signal_id="sig_freeze_open_1",
        alpha_type="directional",
        expected_edge=0.0,
        risk_score=0.1,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 10.0,
            "lifecycle_action": "open",
            "position_key": "freeze_open_1",
        },
        requested_notional=100.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    open_res = prs.process_proposal(
        open_proposal,
        market_liquidity_snapshot={"adv_notional": 100000.0, "spread_bps": 2.0, "depth_qty": 1000.0, "estimated_slippage_bps": 2.0},
        certification_context=ctx,
    )
    assert not open_res.approved
    assert open_res.denial_reason == "risk.runtime_frozen_close_only"

    close_only_proposal = TradeProposal(
        proposal_id="prop_freeze_close_1",
        origin=ProposalOrigin.SHADOW,
        strategy_id="shadow_close",
        signal_id="sig_freeze_close_1",
        alpha_type="closeout",
        expected_edge=0.0,
        risk_score=0.0,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "sell",
            "price": 10.0,
            "quantity": 5.0,
            "close_only": True,
            "lifecycle_action": "close",
            "position_key": "freeze_close_1",
        },
        requested_notional=50.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="close.manual",
    )
    close_res = prs.process_proposal(
        close_only_proposal,
        market_liquidity_snapshot={"adv_notional": 100000.0, "spread_bps": 2.0, "depth_qty": 1000.0, "estimated_slippage_bps": 2.0},
        certification_context=ctx,
    )
    assert close_res.approved


def test_phase3_capacity_breach_freezes_runtime(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)

    def _patched_capital_evaluate(proposal, portfolio_snapshot, budget_snapshot=None, risk_snapshot=None):
        return CapitalDecision(
            decision_id="cap_phase3_breach",
            is_approved=True,
            approved_notional=float(proposal.requested_notional),
            reserve_pool="equity_alpha",
            reserve_impact={},
            sizing_rationale={
                "advanced_models": {
                    "phase3": {
                        "phase3_status": "approved",
                        "deterministic": {
                            "capacity_limit_estimate": 20.0,
                            "stress_max_dd": 0.35,
                        },
                        "monte_carlo": {
                            "sharpe_p05": 0.10,
                        },
                    },
                    "phase3_min_history": 20,
                }
            },
        )

    prs.capital_allocator.evaluate = _patched_capital_evaluate
    proposal = TradeProposal(
        proposal_id="prop_phase3_capacity_1",
        origin=ProposalOrigin.SHADOW,
        strategy_id="phase3_capacity",
        signal_id="sig_phase3_capacity_1",
        alpha_type="directional",
        expected_edge=0.1,
        risk_score=0.1,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 10.0,
            "lifecycle_action": "open",
            "position_key": "phase3_capacity_1",
        },
        requested_notional=100.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={"adv_notional": 100000.0, "spread_bps": 2.0, "depth_qty": 1000.0, "estimated_slippage_bps": 2.0},
        certification_context=ctx,
    )
    assert not res.approved
    assert res.denial_reason == "risk.phase3_capacity_breach"
    assert prs.global_freeze is True
    assert prs.runtime_state == RuntimeState.FROZEN


def test_phase3_live_monitor_freezes_on_mark_to_market(tmp_path):
    prs, _, _ = _make_prs(tmp_path)
    prs._phase3_live_envelopes["phase3_mtm_case"] = {
        "phase3_status": "approved",
        "mc_sharpe_p05": 0.50,
        "stress_max_dd": 0.20,
        "capacity_limit_estimate": 0.0,
        "min_history": 5,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    prs._strategy_realized_returns = lambda strategy_id, max_points=256: ([-0.02] * 30 if strategy_id == "phase3_mtm_case" else [])

    out = prs.mark_to_market({"NIFTY": {"mark_price": 12.0}}, source="phase3_mtm_test")
    assert out["event_ids"]
    assert prs.global_freeze is True
    assert prs.freeze_reason == "risk.phase3_live_sharpe_breach"


def test_post_fill_budget_breach_generates_reconciliation_event(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    original_check = prs.risk_budget_manager.check
    call_count = {"n": 0}

    def _patched_check(capital_decision, proposal, portfolio_snapshot, risk_snapshot=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return original_check(capital_decision, proposal, portfolio_snapshot, risk_snapshot)
        return BudgetDecision(
            decision_id="post_budget_fail",
            is_approved=False,
            approved_notional=float(capital_decision.approved_notional),
            denial_reason="risk.gross_cap_breach",
            cap_observations={"patched": True},
        )

    prs.risk_budget_manager.check = _patched_check

    proposal = TradeProposal(
        proposal_id="prop_post_fill_1",
        origin=ProposalOrigin.OPTIONS_ALPHA,
        strategy_id="patched_post_fill",
        signal_id="sig_post_fill_1",
        alpha_type="vol",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 5.0,
            "lifecycle_action": "open",
            "position_key": "post_fill_1",
        },
        requested_notional=50.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    result = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 2.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )

    assert result.approved
    events = prs.latest_events()
    assert any(str(e.get("trigger_reason_code", "")) == "risk.post_fill_budget_breach" for e in events)


def test_mark_to_market_updates_prices_without_cash_mutation(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    proposal = TradeProposal(
        proposal_id="prop_mtm_open",
        origin=ProposalOrigin.SHADOW,
        strategy_id="mtm_case",
        signal_id="sig_mtm_open",
        alpha_type="directional",
        expected_edge=0.0,
        risk_score=0.1,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 5.0,
            "lifecycle_action": "open",
            "position_key": "mtm_pos_1",
            "instrument_type": "equity",
        },
        requested_notional=50.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 2.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )
    assert res.approved
    before = prs.get_portfolio_state().to_dict()
    before_cash = float(before.get("cash", 0.0))
    mtm_out = prs.mark_to_market({"NIFTY": {"mark_price": 12.0}}, source="test")
    assert mtm_out["event_ids"]
    after = prs.get_portfolio_state().to_dict()
    assert float(after.get("cash", 0.0)) == before_cash
    assert float(after["holdings"]["NIFTY"]["last_price"]) == 12.0


def test_strict_mode_blocks_option_without_greeks(tmp_path):
    prev = os.environ.get("NORTHSTAR_STRICT_MODE")
    os.environ["NORTHSTAR_STRICT_MODE"] = "1"
    try:
        prs, snap, ctx = _make_prs(tmp_path)
        proposal = TradeProposal(
            proposal_id="prop_opt_strict_1",
            origin=ProposalOrigin.OPTIONS_ALPHA,
            strategy_id="strict_options",
            signal_id="sig_opt_strict_1",
            alpha_type="vol",
            expected_edge=0.2,
            risk_score=0.3,
            regime_context={},
            instrument_plan={
                "symbol": "NIFTY",
                "side": "buy",
                "price": 100.0,
                "quantity": 1.0,
                "instrument_type": "option",
                "option_type": "call",
                "lifecycle_action": "open",
                "position_key": "strict_opt_pos_1",
            },
            requested_notional=100.0,
            certification_snapshot_hash=snap.snapshot_hash,
            decision_mode=DecisionMode.AUTO,
            trigger_reason_code="proposal.runtime.default",
        )
        res = prs.process_proposal(
            proposal,
            market_liquidity_snapshot={
                "adv_notional": 100000.0,
                "spread_bps": 2.0,
                "depth_qty": 1000.0,
                "estimated_slippage_bps": 2.0,
            },
            risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
            certification_context=ctx,
        )
        assert not res.approved
        assert res.denial_reason == "risk.options_missing_greeks"
    finally:
        if prev is None:
            os.environ.pop("NORTHSTAR_STRICT_MODE", None)
        else:
            os.environ["NORTHSTAR_STRICT_MODE"] = prev


def test_research_evolution_runs_once_per_day_and_persists_state(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    assert prs.research_evolution is not None
    calls = {"n": 0}
    original_run_cycle = prs.research_evolution.run_cycle

    def _wrapped_run_cycle(*args, **kwargs):
        calls["n"] += 1
        return original_run_cycle(*args, **kwargs)

    prs.research_evolution.run_cycle = _wrapped_run_cycle

    p1 = TradeProposal(
        proposal_id="prop_evo_1",
        origin=ProposalOrigin.SHADOW,
        strategy_id="evo_strategy",
        signal_id="sig_evo_1",
        alpha_type="directional",
        expected_edge=0.1,
        risk_score=0.1,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 2.0,
            "lifecycle_action": "open",
            "position_key": "evo_pos_1",
        },
        requested_notional=20.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
        runtime_scope="shadow",
    )
    p2 = TradeProposal(
        proposal_id="prop_evo_2",
        origin=ProposalOrigin.SHADOW,
        strategy_id="evo_strategy",
        signal_id="sig_evo_2",
        alpha_type="directional",
        expected_edge=0.1,
        risk_score=0.1,
        regime_context={},
        instrument_plan={
            "symbol": "BANKNIFTY",
            "side": "buy",
            "price": 20.0,
            "quantity": 1.0,
            "lifecycle_action": "open",
            "position_key": "evo_pos_2",
        },
        requested_notional=20.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
        runtime_scope="shadow",
    )
    r1 = prs.process_proposal(
        p1,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 1.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )
    r2 = prs.process_proposal(
        p2,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 1.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
    )
    assert r1.approved and r2.approved
    assert calls["n"] == 1

    regime_state = prs.store.get_runtime_control_json(prs._REGIME_STATE_CONTROL_KEY, {})
    param_state = prs.store.get_runtime_control_json(prs._PARAM_STATE_CONTROL_KEY, {})
    meta_state = prs.store.get_runtime_control_json(prs._EVOLUTION_META_CONTROL_KEY, {})
    assert regime_state
    assert param_state
    assert "shadow" in dict(meta_state.get("last_cycle_date_by_scope", {}) or {})

    db = str(tmp_path / "portfolio_runtime.db")
    out = str(tmp_path / "derived")
    prs.close()

    prs2 = PortfolioRuntimeService(db_path=db, materialized_output_dir=out, starting_cash=1000.0)
    try:
        assert prs2.regime_engine is not None
        assert prs2.parameter_engine is not None
        assert prs2._last_evolution_cycle_date_by_scope.get("shadow")
    finally:
        prs2.close()


def test_adaptive_size_multiplier_is_applied_before_capital_gate(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    assert prs.parameter_engine is not None
    prs.parameter_engine.current_parameters["size_multiplier"] = 0.50
    prs.parameter_engine.current_parameters["slippage_buffer_bps"] = 3.0
    prs.parameter_engine.current_parameters["aggressiveness_multiplier"] = 0.80

    proposal = TradeProposal(
        proposal_id="prop_adaptive_size_1",
        origin=ProposalOrigin.SHADOW,
        strategy_id="adaptive_size",
        signal_id="sig_adaptive_size_1",
        alpha_type="directional",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 20.0,
            "lifecycle_action": "open",
            "position_key": "adaptive_size_pos_1",
        },
        requested_notional=200.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )
    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 1.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
        auto_fill=False,
    )
    assert res.approved
    events = prs.latest_events()
    approved_events = [e for e in events if str(e.get("event_type", "")) == "INTENT_APPROVED"]
    assert approved_events
    payload = prs._payload_from_row(approved_events[-1])
    approved_notional = float(payload.get("approved_notional", 0.0) or 0.0)
    assert approved_notional <= 120.0
    adaptive_overrides = dict(payload.get("adaptive_overrides", {}) or {})
    assert adaptive_overrides.get("applied") is True
    assert float(adaptive_overrides.get("size_multiplier", 1.0)) == 0.5


def test_phase6_shadow_mode_blocks_open_proposals(tmp_path):
    prs, snap, ctx = _make_prs(tmp_path)
    prs._phase6_latest_decisions["phase6_shadow"] = {
        "state": "SHADOW",
        "capital_multiplier": 0.1,
    }

    proposal = TradeProposal(
        proposal_id="prop_phase6_shadow_1",
        origin=ProposalOrigin.SHADOW,
        strategy_id="phase6_shadow",
        signal_id="sig_phase6_shadow_1",
        alpha_type="directional",
        expected_edge=0.1,
        risk_score=0.2,
        regime_context={},
        instrument_plan={
            "symbol": "NIFTY",
            "side": "buy",
            "price": 10.0,
            "quantity": 10.0,
            "lifecycle_action": "open",
            "position_key": "phase6_shadow_pos_1",
        },
        requested_notional=100.0,
        certification_snapshot_hash=snap.snapshot_hash,
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="proposal.runtime.default",
    )

    res = prs.process_proposal(
        proposal,
        market_liquidity_snapshot={
            "adv_notional": 100000.0,
            "spread_bps": 2.0,
            "depth_qty": 1000.0,
            "estimated_slippage_bps": 1.0,
        },
        risk_snapshot={"signal_entropy": 0.9, "risk_budget_ratio": 0.1},
        certification_context=ctx,
        auto_fill=False,
    )
    assert not res.approved
    assert res.denial_reason == "risk.phase6_shadow_mode"


def test_phase6_capacity_breach_freezes_runtime_on_mark_to_market(tmp_path):
    prs, _snap, _ctx = _make_prs(tmp_path)
    prs._phase6_profiles["phase6_breach"] = {
        "strategy_id": "phase6_breach",
        "prior_mean": 0.01,
        "prior_variance": 0.05,
        "mc_sharpe_mean": 0.5,
        "mc_sharpe_std": 0.2,
        "mc_drawdown_mean": 0.1,
        "mc_drawdown_std": 0.05,
        "recovery_days_median": 15.0,
        "recovery_sigma": 0.25,
        "regime_sharpe_profile": {"state_1": 0.5},
        "regime_sigma": 0.2,
        "baseline_vol_cluster_acf1": 0.0,
        "baseline_skew": 0.0,
        "baseline_convexity": 0.0,
        "baseline_decay_lambda": 0.01,
        "capacity_limit_estimate": 10.0,
        "freeze_drawdown_limit": 0.9,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    prs._current_strategy_notional = lambda strategy_id: 25.0 if strategy_id == "phase6_breach" else 0.0
    prs._strategy_realized_returns = lambda strategy_id, max_points=256: ([0.001] * 40 if strategy_id == "phase6_breach" else [])

    out = prs.mark_to_market({"NIFTY": {"mark_price": 12.0}}, source="phase6_capacity_test")
    assert out["event_ids"]
    assert prs.global_freeze is True
    assert prs.freeze_reason == "risk.phase6_capacity_breach"
