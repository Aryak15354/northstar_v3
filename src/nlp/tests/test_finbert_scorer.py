from src.nlp.models.finbert_scorer import FinBERTScorer


def test_finbert_scorer_offline_heuristic_positive() -> None:
    scorer = FinBERTScorer({"nlp": {"models": {"sentiment": {"allow_remote_download": False}}}})

    score = scorer.score_single("Infosys beats Q3 estimates as revenue rises 15 percent")

    assert score.predicted_label == "positive"
    assert score.polarity > 0
    assert score.model_version
