"""Model selection helpers for the NLP stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    name: str
    path: str
    source: str
    hf_model_id: str | None = None
    available: bool = False


class NLPModelRegistry:
    """Resolves local-vs-remote model paths from the NLP configuration."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}

    def sentiment_model(self) -> ModelSpec:
        sentiment_cfg = self._config.get("nlp", {}).get("models", {}).get("sentiment", {})
        india_path = Path(sentiment_cfg.get("india_finetuned_path", "data/nlp/models/finbert_india"))
        base_path = Path(sentiment_cfg.get("local_path", "data/nlp/models/finbert_base"))
        hf_model_id = str(sentiment_cfg.get("hf_model_id", "ProsusAI/finbert"))
        use_india = bool(sentiment_cfg.get("use_india_model_if_available", True))

        if use_india and (india_path / "config.json").exists():
            return ModelSpec(
                name=str(sentiment_cfg.get("primary", "finbert_india")),
                path=str(india_path),
                source="local",
                hf_model_id=hf_model_id,
                available=True,
            )
        if (base_path / "config.json").exists():
            return ModelSpec(
                name=str(sentiment_cfg.get("fallback", "finbert_base")),
                path=str(base_path),
                source="local",
                hf_model_id=hf_model_id,
                available=True,
            )
        return ModelSpec(
            name=str(sentiment_cfg.get("fallback", "finbert_base")),
            path=hf_model_id,
            source="huggingface",
            hf_model_id=hf_model_id,
            available=False,
        )

    def ner_model(self) -> ModelSpec:
        ner_cfg = self._config.get("nlp", {}).get("models", {}).get("ner", {})
        local_path = Path(ner_cfg.get("local_path", "data/nlp/models/india_ner"))
        fallback = str(ner_cfg.get("fallback_ner", "dbmdz/bert-large-cased-finetuned-conll03-english"))
        if (local_path / "config.json").exists():
            return ModelSpec(name=str(ner_cfg.get("model", "india_ner")), path=str(local_path), source="local", available=True)
        return ModelSpec(name="fallback_ner", path=fallback, source="huggingface", hf_model_id=fallback, available=False)

    def event_model(self) -> ModelSpec:
        event_cfg = self._config.get("nlp", {}).get("models", {}).get("event_classifier", {})
        local_path = Path(event_cfg.get("local_path", "data/nlp/models/event_classifier"))
        if (local_path / "config.json").exists():
            return ModelSpec(name=str(event_cfg.get("model", "event_classifier")), path=str(local_path), source="local", available=True)
        return ModelSpec(name="zero_shot", path="facebook/bart-large-mnli", source="huggingface", hf_model_id="facebook/bart-large-mnli", available=False)

    def encoder_model(self) -> ModelSpec:
        encoder_cfg = self._config.get("nlp", {}).get("models", {}).get("encoder", {})
        local_path = Path(encoder_cfg.get("local_path", "data/nlp/models/sentence_encoder"))
        fallback = str(encoder_cfg.get("model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"))
        if (local_path / "config.json").exists():
            return ModelSpec(name="sentence_encoder", path=str(local_path), source="local", available=True)
        return ModelSpec(name="sentence_encoder", path=fallback, source="huggingface", hf_model_id=fallback, available=False)
