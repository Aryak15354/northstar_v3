from __future__ import annotations

from src.nlp.models.event_classifier import EventClassifier


def test_earnings_beat_detected():
    clf = EventClassifier({})
    result = clf.classify("Q3 net profit rises 25%, beats estimates")
    assert result.event_type == "earnings_beat"


def test_rate_hike_detected():
    clf = EventClassifier({})
    result = clf.classify("RBI raises repo rate by 25 basis points")
    assert result.event_type == "macro_rate_hike"


def test_rate_hike_negation():
    clf = EventClassifier({})
    result = clf.classify("RBI keeps repo rate unchanged")
    assert result.event_type != "macro_rate_hike"


def test_fraud_detected():
    clf = EventClassifier({})
    result = clf.classify("SEBI probes company for accounting irregularities")
    assert result.event_type == "fraud_allegation"


def test_order_win_detected():
    clf = EventClassifier({})
    result = clf.classify("L&T bags Rs 2,500 crore order from NHAI")
    assert result.event_type == "order_win"


def test_macro_geopolitical():
    clf = EventClassifier({})
    result = clf.classify("Strait of Hormuz blockade disrupts tanker routes")
    assert result.event_type == "macro_geopolitical"


def test_fii_outflow_realistic_phrasing():
    clf = EventClassifier({})
    result = clf.classify("FII net sellers pull Rs 6,500 crore from equities")
    assert result.event_type == "macro_fii_outflow"


def test_rule_based_high_confidence():
    clf = EventClassifier({})
    result = clf.classify("Q3 net profit rises 25%, beats estimates")
    assert result.confidence >= 0.85


def test_unknown_event_handled():
    clf = EventClassifier({})
    result = clf.classify("Board to meet next week for routine matters")
    assert result.event_type in {"neutral_corporate", "unknown"}
