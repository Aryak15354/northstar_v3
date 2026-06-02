from __future__ import annotations

from src.intelligence.news_brain.news_signal_state import ShockDirection, ShockSeverity, ShockType
from src.intelligence.news_brain.shock_classifier import NLPShockClassifier
from tests.intelligence.helpers import make_macro_signal


def test_replaces_keyword_classifier_interface():
    classifier = NLPShockClassifier({})
    result = classifier.classify_from_signals(macro_signals=[], market_signals=[])
    assert isinstance(result, tuple)
    assert len(result) == 4


def test_oil_shock_detected_via_nlp():
    classifier = NLPShockClassifier({})
    shock_type, confidence, direction = classifier.classify_single_headline("Tanker routes obstructed near Gulf shipping lane")
    assert shock_type == ShockType.OIL_SUPPLY_DISRUPTION
    assert direction == ShockDirection.BEARISH
    assert confidence > 0.5


def test_rate_hike_detected_via_nlp():
    classifier = NLPShockClassifier({})
    shock_type, confidence, direction = classifier.classify_single_headline("Central bank tightens monetary policy")
    assert shock_type == ShockType.RATE_HIKE_RBI
    assert direction == ShockDirection.BEARISH
    assert confidence > 0.5


def test_quantitative_triggers_override_nlp():
    classifier = NLPShockClassifier({})
    shock_type, severity, direction, confidence = classifier.classify_from_signals(
        macro_signals=[],
        market_signals=[],
        crude_change_pct=16.0,
    )
    assert shock_type == ShockType.OIL_SUPPLY_DISRUPTION
    assert severity == ShockSeverity.EXTREME
    assert direction == ShockDirection.BEARISH
    assert confidence >= 0.9


def test_negation_handled():
    classifier = NLPShockClassifier({})
    shock_type, confidence, direction = classifier.classify_single_headline("Rate hike fears subside as RBI holds")
    assert shock_type == ShockType.NONE
    assert direction == ShockDirection.NEUTRAL


def test_fii_outflow_detected_via_nlp():
    classifier = NLPShockClassifier({})
    shock_type, confidence, direction = classifier.classify_single_headline(
        "FII net sellers pull Rs 6,500 crore from equities"
    )
    assert shock_type == ShockType.FII_OUTFLOW
    assert direction == ShockDirection.BEARISH
    assert confidence > 0.5


def test_macro_signal_geopolitical_headline_maps_to_conflict():
    classifier = NLPShockClassifier({})
    signal = make_macro_signal(
        signal_type="macro_news",
        shock_type=ShockType.NONE,
        direction=ShockDirection.BEARISH,
        severity=ShockSeverity.HIGH,
        headline="Israel launches airstrike on Iran nuclear facility as conflict escalates",
    )
    shock_type, severity, direction, confidence = classifier.classify_from_signals(macro_signals=[signal], market_signals=[])
    assert shock_type == ShockType.GEOPOLITICAL_CONFLICT
    assert severity >= ShockSeverity.HIGH
    assert direction == ShockDirection.BEARISH
    assert confidence > 0.5
