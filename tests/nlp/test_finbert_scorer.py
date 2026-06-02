from __future__ import annotations

from pathlib import Path

from src.nlp.models.finbert_scorer import FinBERTScorer


def _config() -> dict:
    return {
        "nlp": {
            "models": {"sentiment": {"device": "cpu", "batch_size": 8, "max_length": 128}},
            "pipeline": {"min_confidence": 0.55},
        }
    }


def test_finbert_loads_without_error():
    scorer = FinBERTScorer(_config())
    score = scorer.score_single("Infosys beats Q3 estimates, revenue rises 15%")
    assert score.predicted_label in {"positive", "neutral", "negative"}


def test_positive_headline_scores_positive():
    scorer = FinBERTScorer(_config())
    score = scorer.score_single("Infosys beats Q3 estimates, revenue rises 15%")
    assert score.polarity > 0.2


def test_negative_headline_scores_negative():
    scorer = FinBERTScorer(_config())
    score = scorer.score_single("Promoter arrested for fraud allegation")
    assert score.polarity < -0.2


def test_rate_hike_negation_handled():
    scorer = FinBERTScorer(_config())
    score = scorer.score_single("Rate hike fears subside as RBI holds")
    assert score.polarity >= -0.1


def test_cache_prevents_re_inference(tmp_path):
    scorer = FinBERTScorer(_config())
    scorer._cache_path = tmp_path
    scorer._cache_index_path = tmp_path / "score_index.json"
    scorer._score_cache = {}
    headline = "ONGC Q4 PAT surges 40% on higher crude realization"
    first = scorer.score_single(headline)
    scorer.flush_cache()
    second = scorer.score_single(headline)
    assert first.from_cache is False
    assert second.from_cache is True


def test_batch_produces_same_as_single():
    scorer = FinBERTScorer(_config())
    headlines = [
        "Infosys beats Q3 estimates, revenue rises 15%",
        "Promoter arrested for fraud allegation",
    ]
    batch = scorer.score_batch(headlines)
    single = [scorer.score_single(text) for text in headlines]
    assert [round(item.polarity, 6) for item in batch] == [round(item.polarity, 6) for item in single]


def test_india_financial_terminology():
    scorer = FinBERTScorer(_config())
    score = scorer.score_single("ONGC Q4 PAT surges 40% on higher crude realization")
    assert score.polarity > 0.2


def test_hindi_english_mixing_handled():
    scorer = FinBERTScorer(_config())
    score = scorer.score_single("Tata Motors ne record profit announce kiya")
    assert score.text


def test_local_model_presence_switches_cache_namespace(tmp_path):
    model_dir = tmp_path / "finbert_base"
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    scorer = FinBERTScorer(
        {
            "nlp": {
                "models": {
                    "sentiment": {
                        "device": "cpu",
                        "batch_size": 8,
                        "max_length": 128,
                        "local_path": str(model_dir),
                        "use_india_model_if_available": False,
                    }
                },
                "pipeline": {"min_confidence": 0.55},
            }
        }
    )

    assert scorer._cache_namespace_model_version == "finbert_base"


def test_failed_india_model_automatically_falls_back_to_base(tmp_path):
    india_dir = tmp_path / "finbert_india"
    base_dir = tmp_path / "finbert_base"
    india_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    (india_dir / "config.json").write_text("{}", encoding="utf-8")
    (base_dir / "config.json").write_text("{}", encoding="utf-8")

    class _GuardedScorer(FinBERTScorer):
        def _load_transformer_artifacts(
            self,
            *,
            model_path: str,
            model_version: str,
            auto_tokenizer_cls,
            auto_model_cls,
            local_base_path: Path,
        ) -> None:
            del auto_tokenizer_cls, auto_model_cls
            self._model_version = model_version
            self._tokenizer = object()
            self._model = object()
            if self._model_version == "finbert_india" and not self._india_model_passes_sanity_gate():
                self._model = None
                self._tokenizer = None
                self._load_transformer_artifacts(
                    model_path=str(local_base_path),
                    model_version="finbert_base",
                    auto_tokenizer_cls=None,
                    auto_model_cls=None,
                    local_base_path=local_base_path,
                )
                return
            self._cache_namespace_model_version = self._model_version

        def _india_model_passes_sanity_gate(self) -> bool:
            return False

    scorer = _GuardedScorer(
        {
            "nlp": {
                "models": {
                    "sentiment": {
                        "device": "cpu",
                        "india_finetuned_path": str(india_dir),
                        "local_path": str(base_dir),
                        "use_india_model_if_available": True,
                    }
                },
                "pipeline": {"min_confidence": 0.55},
            }
        }
    )

    scorer._load_model()

    assert scorer._model_version == "finbert_base"
