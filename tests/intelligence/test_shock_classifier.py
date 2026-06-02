from src.intelligence.news_brain.shock_classifier import classify_shock, determine_shock_summary
from src.intelligence.news_brain.news_signal_state import ShockDirection, ShockSeverity, ShockType
from tests.intelligence.helpers import make_macro_signal


def test_oil_supply_disruption_keywords():
    signal = make_macro_signal(
        signal_type="macro_news",
        shock_type=ShockType.NONE,
        direction=ShockDirection.BEARISH,
        severity=ShockSeverity.SEVERE,
        headline="Strait of Hormuz blockade disrupts crude tanker supply routes",
        estimated_nifty_move_pct=-4.0,
        crude_price_change_pct=16.0,
    )
    shock_type, severity, direction, confidence = classify_shock(
        company_signals=[],
        market_signals=[],
        macro_signals=[signal],
        india_vix=24.0,
        crude_change_pct=16.0,
        inr_change_pct=-1.0,
        fii_net_crores=0.0,
    )
    assert shock_type == ShockType.OIL_SUPPLY_DISRUPTION
    assert severity >= ShockSeverity.SEVERE
    assert direction == ShockDirection.BEARISH
    assert confidence >= 0.70


def test_rate_hike_rbi_keywords():
    signal = make_macro_signal(
        signal_type="policy",
        shock_type=ShockType.RATE_HIKE_RBI,
        direction=ShockDirection.BEARISH,
        severity=ShockSeverity.MODERATE,
        headline="RBI MPC raises repo rate by 25bps in hawkish surprise",
        estimated_nifty_move_pct=-1.0,
    )
    shock_type, severity, direction, confidence = classify_shock(
        company_signals=[],
        market_signals=[],
        macro_signals=[signal],
        india_vix=16.0,
        crude_change_pct=0.0,
        inr_change_pct=0.2,
        fii_net_crores=0.0,
    )
    assert shock_type == ShockType.RATE_HIKE_RBI
    assert severity == ShockSeverity.MODERATE
    assert direction == ShockDirection.BEARISH
    assert confidence >= 0.65


def test_geopolitical_conflict():
    signal = make_macro_signal(
        signal_type="macro_news",
        shock_type=ShockType.NONE,
        direction=ShockDirection.BEARISH,
        severity=ShockSeverity.HIGH,
        headline="Israel launches airstrike on Iran nuclear facility as conflict escalates",
        estimated_nifty_move_pct=-2.5,
    )
    shock_type, severity, direction, confidence = classify_shock(
        company_signals=[],
        market_signals=[],
        macro_signals=[signal],
        india_vix=22.0,
        crude_change_pct=4.0,
        inr_change_pct=-0.8,
        fii_net_crores=-1200.0,
    )
    assert shock_type == ShockType.GEOPOLITICAL_CONFLICT
    assert severity >= ShockSeverity.HIGH
    assert direction == ShockDirection.BEARISH
    assert confidence >= 0.65


def test_no_shock_when_quiet():
    shock_type, severity, direction, confidence = classify_shock(
        company_signals=[],
        market_signals=[],
        macro_signals=[],
        india_vix=12.0,
        crude_change_pct=0.0,
        inr_change_pct=0.0,
        fii_net_crores=0.0,
    )
    assert shock_type == ShockType.NONE
    assert severity == ShockSeverity.NONE
    assert direction == ShockDirection.NEUTRAL
    assert confidence == 0.0


def test_compound_shock():
    oil_signal = make_macro_signal(
        signal_type="macro_news",
        shock_type=ShockType.NONE,
        direction=ShockDirection.BEARISH,
        severity=ShockSeverity.SEVERE,
        headline="Hormuz blockade sends crude sharply higher and disrupts supply route",
        estimated_nifty_move_pct=-4.0,
        crude_price_change_pct=18.0,
    )
    geo_signal = make_macro_signal(
        signal_type="macro_news",
        shock_type=ShockType.NONE,
        direction=ShockDirection.BEARISH,
        severity=ShockSeverity.HIGH,
        headline="Military airstrike escalates geopolitical conflict in the Gulf",
        estimated_nifty_move_pct=-2.5,
    )
    summary = determine_shock_summary(
        company_signals=[],
        market_signals=[],
        macro_signals=[oil_signal, geo_signal],
        india_vix=24.0,
        crude_change_pct=18.0,
        inr_change_pct=-1.6,
        fii_net_crores=0.0,
    )
    assert summary["primary_shock_type"] == ShockType.OIL_SUPPLY_DISRUPTION
    assert summary["secondary_shock_type"] == ShockType.GEOPOLITICAL_CONFLICT

