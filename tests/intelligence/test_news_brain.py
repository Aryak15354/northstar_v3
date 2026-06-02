from datetime import datetime, timedelta

from src.intelligence.news_brain.news_brain import NewsBrain
from src.intelligence.news_brain.news_signal_state import ShockDirection, ShockSeverity, ShockType
from tests.intelligence.helpers import make_macro_signal


def test_news_brain_detects_oil_disruption_and_selects_beneficiary_call(monkeypatch):
    brain = NewsBrain({})
    monkeypatch.setattr(brain.company_layer, "run", lambda as_of: [])
    monkeypatch.setattr(
        brain.market_layer,
        "run",
        lambda as_of: {
            "market_signals": [],
            "vix_level": 24.0,
            "fii_net_crores": 0.0,
        },
    )
    monkeypatch.setattr(
        brain.macro_layer,
        "run",
        lambda as_of: {
            "macro_signals": [
                make_macro_signal(
                    signal_type="macro_news",
                    shock_type=ShockType.OIL_SUPPLY_DISRUPTION,
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.SEVERE,
                    headline="Strait of Hormuz blockade disrupts tanker movement",
                    estimated_nifty_move_pct=-4.0,
                    crude_price_change_pct=15.0,
                    inr_usd_change_pct=-1.8,
                )
            ],
            "rbi_stance": "neutral",
            "global_risk_appetite": "risk_off",
            "crude_change_pct": 15.0,
            "inr_change_pct": -1.8,
        },
    )
    monkeypatch.setattr(brain, "_write_snapshot", lambda state: None)

    state = brain.run_cycle()
    assert state.primary_shock_type == ShockType.OIL_SUPPLY_DISRUPTION
    assert state.sector_impacts["Services"].impact_score <= -0.85
    selected = {(item["strategy"], item["underlying"]) for item in state.selected_option_strategies}
    assert ("bear_put_spread", "NIFTY") in selected
    assert ("long_call", "ONGC") in selected


def test_news_brain_uses_income_strategies_when_no_shock(monkeypatch):
    brain = NewsBrain({})
    monkeypatch.setattr(brain.company_layer, "run", lambda as_of: [])
    monkeypatch.setattr(brain.market_layer, "run", lambda as_of: {"market_signals": [], "vix_level": 17.0, "fii_net_crores": 0.0})
    monkeypatch.setattr(
        brain.macro_layer,
        "run",
        lambda as_of: {
            "macro_signals": [],
            "rbi_stance": "neutral",
            "global_risk_appetite": "neutral",
            "crude_change_pct": 0.0,
            "inr_change_pct": 0.0,
        },
    )
    monkeypatch.setattr(brain, "_write_snapshot", lambda state: None)

    state = brain.run_cycle()
    assert state.primary_shock_type == ShockType.NONE
    assert state.requires_immediate_hedge is False
    strategy_names = {item["strategy"] for item in state.selected_option_strategies}
    assert "covered_call" in strategy_names


def test_news_brain_uses_source_aware_freshness(monkeypatch):
    brain = NewsBrain({})
    now = datetime.now()

    monkeypatch.setattr(brain.company_layer, "run", lambda as_of: [])
    monkeypatch.setattr(
        brain.market_layer,
        "run",
        lambda as_of: {
            "market_signals": [],
            "vix_level": 18.0,
            "fii_net_crores": 0.0,
            "latest_data_at": now - timedelta(hours=2),
        },
    )
    monkeypatch.setattr(
        brain.macro_layer,
        "run",
        lambda as_of: {
            "macro_signals": [],
            "rbi_stance": "neutral",
            "global_risk_appetite": "neutral",
            "crude_change_pct": 0.0,
            "inr_change_pct": 0.0,
            "latest_data_at": now - timedelta(days=10),
        },
    )
    monkeypatch.setattr(brain, "_write_snapshot", lambda state: None)

    state = brain.run_cycle(as_of_datetime=now)

    assert state.available is True
    assert state.is_stale is False
