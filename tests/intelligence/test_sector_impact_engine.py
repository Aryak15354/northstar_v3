from src.intelligence.news_brain.news_signal_state import ShockSeverity, ShockType
from tests.intelligence.helpers import build_state, make_company_signal


def test_sector_impact_oil_spike():
    state = build_state(ShockType.OIL_PRICE_SPIKE, shock_severity=ShockSeverity.HIGH)
    assert state.sector_impacts["Services"].impact_score < -0.80


def test_sector_impact_it_inr():
    state = build_state(ShockType.INR_DEPRECIATION, shock_severity=ShockSeverity.HIGH)
    assert state.sector_impacts["Information Technology"].impact_score > 0.70


def test_sector_impact_rate_hike():
    state = build_state(ShockType.RATE_HIKE_RBI, shock_severity=ShockSeverity.MODERATE)
    assert state.sector_impacts["Realty"].impact_score < -0.80
    assert state.sector_impacts["Financial Services"].impact_score < -0.35


def test_no_shock_is_neutral():
    state = build_state(ShockType.NONE, shock_severity=ShockSeverity.NONE)
    assert all(abs(item.impact_score) < 1e-9 for item in state.sector_impacts.values())


def test_bellwether_propagation_hits_financials():
    signal = make_company_signal(
        ticker="HDFCBANK",
        sector="Financial Services",
        headline="HDFCBANK faces unexpected asset quality pressure",
        is_bellwether=True,
    )
    state = build_state(
        ShockType.NONE,
        shock_severity=ShockSeverity.NONE,
        company_signals=[signal],
    )
    assert state.sector_impacts["Financial Services"].impact_score < 0.0

