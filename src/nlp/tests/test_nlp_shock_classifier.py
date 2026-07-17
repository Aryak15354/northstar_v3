from src.nlp.models.event_classifier import EventClassifier


def test_event_classifier_identifies_geopolitical_macro_shock() -> None:
    result = EventClassifier().classify("Oil tanker route faces blockade after missile attack")

    assert result.event_type == "macro_geopolitical"
    assert result.expected_direction == "negative"
    assert result.materiality == "high"
