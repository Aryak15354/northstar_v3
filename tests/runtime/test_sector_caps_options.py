from datetime import datetime, timezone

from src.runtime.contracts import CapitalDecision, DecisionMode, ProposalOrigin, TradeProposal
from src.runtime.risk_budget import RiskBudgetConfig, RiskBudgetManager
from src.runtime.state import Holding, PortfolioState


def _approved_capital_decision(notional: float) -> CapitalDecision:
    return CapitalDecision(
        decision_id="cap_test",
        is_approved=True,
        approved_notional=float(notional),
        reserve_pool="options",
        reserve_impact={},
        sizing_rationale={},
        denial_reason="",
    )


def _proposal(origin: ProposalOrigin, *, sector: str, underlying: str) -> TradeProposal:
    return TradeProposal(
        proposal_id=f"prop_{origin.value}_{underlying}",
        origin=origin,
        strategy_id="long_straddle",
        signal_id=f"sig_{underlying}",
        alpha_type="overlay",
        expected_edge=0.1,
        risk_score=0.02,
        regime_context={},
        instrument_plan={
            "symbol": f"OPT::{underlying}::TEST",
            "underlying_symbol": underlying,
            "side": "buy",
            "price": 100.0,
            "quantity": 100.0,
            "direction": 1.0,
            "instrument_type": "option",
            "sector": sector,
        },
        requested_notional=10_000.0,
        certification_snapshot_hash="cert",
        decision_mode=DecisionMode.AUTO,
        trigger_reason_code="test",
        risk_override_flag=False,
        created_at=datetime.now(timezone.utc),
    )


def test_portfolio_state_excludes_broad_index_hedges_from_sector_allocation():
    state = PortfolioState.initialize(482_241.0)
    state.holdings["OPT::NIFTY::TEST"] = Holding(
        symbol="OPT::NIFTY::TEST",
        instrument_type="option",
        quantity=172.0,
        avg_price=103.25,
        last_price=103.25,
        sector="financial services",
        strategy_id="bear_put_spread",
        origin="options_hedge",
    )

    snapshot = state.to_snapshot().to_dict()

    assert snapshot["sector_allocation"] == {}


def test_portfolio_state_keeps_sector_specific_option_alpha_in_sector_allocation():
    state = PortfolioState.initialize(490_000.0)
    state.holdings["OPT::SBIN::TEST"] = Holding(
        symbol="OPT::SBIN::TEST",
        instrument_type="option",
        quantity=100.0,
        avg_price=50.0,
        last_price=50.0,
        sector="financial services",
        strategy_id="long_straddle",
        origin="options_alpha",
    )

    snapshot = state.to_snapshot().to_dict()

    assert snapshot["sector_allocation"] == {"financial services": 1.0}


def test_risk_budget_skips_sector_cap_for_broad_index_option_hedges():
    manager = RiskBudgetManager(
        RiskBudgetConfig(
            sector_caps={"financial services": 0.30},
            gross_cap_ratio=10.0,
            net_cap_ratio=10.0,
            vol_adjusted_cap_ratio=10.0,
            per_strategy_cap_ratio=10.0,
            per_origin_cap_ratio=10.0,
            stress_loss_cap_ratio=10.0,
        )
    )
    decision = manager.check(
        _approved_capital_decision(15_000.0),
        _proposal(ProposalOrigin.OPTIONS_HEDGE, sector="financial services", underlying="NIFTY"),
        portfolio_snapshot={
            "net_liquidation_value": 500_000.0,
            "gross_exposure": 17_759.0,
            "net_exposure": 17_759.0,
            "sector_allocation": {"financial services": 1.0},
        },
        risk_snapshot={},
    )

    assert decision.is_approved is True
    assert decision.denial_reason == ""


def test_risk_budget_keeps_sector_cap_for_sector_specific_option_alpha():
    manager = RiskBudgetManager(
        RiskBudgetConfig(
            sector_caps={"financial services": 0.30},
            gross_cap_ratio=10.0,
            net_cap_ratio=10.0,
            vol_adjusted_cap_ratio=10.0,
            per_strategy_cap_ratio=10.0,
            per_origin_cap_ratio=10.0,
            stress_loss_cap_ratio=10.0,
        )
    )
    decision = manager.check(
        _approved_capital_decision(10_000.0),
        _proposal(ProposalOrigin.OPTIONS_ALPHA, sector="financial services", underlying="SBIN"),
        portfolio_snapshot={
            "net_liquidation_value": 500_000.0,
            "gross_exposure": 17_759.0,
            "net_exposure": 17_759.0,
            "sector_allocation": {"financial services": 1.0},
        },
        risk_snapshot={},
    )

    assert decision.is_approved is False
    assert decision.denial_reason == "risk.sector_cap_breach"
