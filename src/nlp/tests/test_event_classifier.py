from src.nlp.models.event_classifier import EventClassifier


def test_event_classifier_rule_based_macro_rate_hike() -> None:
    result = EventClassifier().classify("RBI raises repo rate as inflation remains high")

    assert result.event_type == "macro_rate_hike"
    assert result.expected_direction == "negative"
    assert result.is_macro_event is True
    assert result.rule_based is True
