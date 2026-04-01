"""FinBERT sentiment scorer with cache and offline-safe fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    text: str
    positive_prob: float
    negative_prob: float
    neutral_prob: float
    predicted_label: str
    confidence: float
    polarity: float
    model_version: str
    from_cache: bool = False


class FinBERTScorer:
    """Runs FinBERT when available and falls back to a finance-aware heuristic model."""

    CACHE_VERSION = "v3"
    INDIA_MODEL_SANITY_CASES = (
        ("Infosys beats Q3 estimates, revenue rises 15%", "positive"),
        ("Promoter arrested for fraud allegation", "negative"),
        ("ONGC Q4 PAT surges 40% on higher crude realization", "positive"),
        ("Rate hike fears subside as RBI holds", "neutral_or_nonnegative"),
    )

    POSITIVE_TERMS = {
        "beat",
        "beats",
        "strong",
        "record",
        "surge",
        "surges",
        "surged",
        "rise",
        "rises",
        "rising",
        "profit",
        "growth",
        "approval",
        "approves",
        "approved",
        "wins",
        "win",
        "order",
        "buyback",
        "dividend",
        "cut",
        "cuts",
        "lower",
        "lowers",
        "eases",
        "ease",
        "capex",
        "acquisition",
        "inflow",
        "inflows",
        "realization",
        "pat",
    }
    NEGATIVE_TERMS = {
        "fraud",
        "scam",
        "probe",
        "probes",
        "investigation",
        "investigates",
        "miss",
        "misses",
        "missed",
        "fall",
        "falls",
        "fell",
        "drop",
        "drops",
        "decline",
        "declines",
        "down",
        "outflow",
        "outflows",
        "sell",
        "sells",
        "sold",
        "arrested",
        "raid",
        "pledge",
        "hike",
        "hikes",
        "raises",
        "raised",
        "inflation",
        "geopolitical",
        "blockade",
        "attack",
        "attacks",
        "war",
    }
    NEGATION_PHRASES = (
        "did not",
        "not",
        "no ",
        "unchanged",
        "holds",
        "holds rate",
        "holds repo",
        "subside",
        "subsides",
        "subsiding",
        "fears subside",
        "keeps repo rate unchanged",
    )

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self._config = config.get("nlp", {}).get("models", {}).get("sentiment", {})
        self._pipeline_cfg = config.get("nlp", {}).get("pipeline", {})
        self._model = None
        self._tokenizer = None
        self._device = self._resolve_device()
        self._model_version = "heuristic_finance_v1"
        self._cache_namespace_model_version = self._detect_cache_namespace_model_version()
        self._cache_path = Path("data/nlp/cache/scores")
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._cache_index_path = self._cache_path / "score_index.json"
        self._score_cache = self._load_cache_index()
        self._needs_flush = False

    def score_batch(self, texts: list[str]) -> list[SentimentScore]:
        if not texts:
            return []

        results: list[SentimentScore | None] = [None] * len(texts)
        uncached: list[str] = []
        uncached_positions: list[int] = []

        for idx, raw_text in enumerate(texts):
            text = str(raw_text or "").strip()
            key = self._cache_key(text)
            cached = self._score_cache.get(key)
            if cached is not None:
                results[idx] = SentimentScore(
                    text=text,
                    positive_prob=float(cached["pos"]),
                    negative_prob=float(cached["neg"]),
                    neutral_prob=float(cached["neu"]),
                    predicted_label=str(cached["label"]),
                    confidence=float(cached["conf"]),
                    polarity=float(cached["pol"]),
                    model_version=str(cached["model"]),
                    from_cache=True,
                )
            else:
                uncached.append(text)
                uncached_positions.append(idx)

        if uncached:
            fresh_scores = self._run_inference(uncached)
            for idx, score in zip(uncached_positions, fresh_scores):
                results[idx] = score
                self._score_cache[self._cache_key(score.text)] = {
                    "pos": score.positive_prob,
                    "neg": score.negative_prob,
                    "neu": score.neutral_prob,
                    "label": score.predicted_label,
                    "conf": score.confidence,
                    "pol": score.polarity,
                    "model": score.model_version,
                }
                self._needs_flush = True
        final_results = [item for item in results if item is not None]
        if self._needs_flush and len(uncached) >= 25:
            self.flush_cache()
        return final_results

    def score_single(self, text: str) -> SentimentScore:
        return self.score_batch([text])[0]

    def flush_cache(self) -> None:
        if not self._needs_flush:
            return
        self._cache_index_path.write_text(json.dumps(self._score_cache, indent=2), encoding="utf-8")
        self._needs_flush = False

    def _run_inference(self, texts: list[str]) -> list[SentimentScore]:
        try:
            self._load_model()
        except Exception as exc:
            self._model_version = "heuristic_finance_v1"
            self._cache_namespace_model_version = "heuristic_finance_v1"
            logger.info("FinBERT unavailable, using heuristic scorer: %s", exc)
            return [self._heuristic_score(text) for text in texts]

        if self._model is None or self._tokenizer is None:
            return [self._heuristic_score(text) for text in texts]

        return self._infer_with_loaded_model(texts)

    def _build_scores(self, texts: list[str], probs: np.ndarray) -> list[SentimentScore]:
        out: list[SentimentScore] = []
        for text, row in zip(texts, probs):
            label_probs = {
                "positive": float(row[0]) if len(row) > 0 else 0.0,
                "negative": float(row[1]) if len(row) > 1 else 0.0,
                "neutral": float(row[2]) if len(row) > 2 else 0.0,
            }
            predicted = max(label_probs, key=label_probs.get)
            confidence = float(label_probs[predicted])
            polarity = float(label_probs["positive"] - label_probs["negative"])
            if confidence < float(self._pipeline_cfg.get("min_confidence", 0.55)):
                predicted = "neutral"
                polarity = 0.0
                confidence = max(confidence, label_probs["neutral"])
            out.append(
                SentimentScore(
                    text=text,
                    positive_prob=label_probs["positive"],
                    negative_prob=label_probs["negative"],
                    neutral_prob=label_probs["neutral"],
                    predicted_label=predicted,
                    confidence=confidence,
                    polarity=polarity,
                    model_version=self._model_version,
                    from_cache=False,
                )
            )
        return out

    def _heuristic_score(self, text: str) -> SentimentScore:
        normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
        positive_hits = sum(term in normalized for term in self.POSITIVE_TERMS)
        negative_hits = sum(term in normalized for term in self.NEGATIVE_TERMS)
        negation_hits = sum(phrase in normalized for phrase in self.NEGATION_PHRASES)

        if "rate hike fears subside" in normalized or "keeps repo rate unchanged" in normalized:
            positive_hits += 1
            negative_hits = max(0, negative_hits - 2)
        if "not raise" in normalized or "did not raise" in normalized or "no rate hike" in normalized:
            negative_hits = max(0, negative_hits - 2)
        if "fraud" in normalized or "arrested" in normalized:
            negative_hits += 2
        if any(token in normalized for token in ("pat surges", "profit surges", "beats estimates", "record profit")):
            positive_hits += 2
        if any(token in normalized for token in ("earnings miss", "profit falls", "order loss", "pledge increase")):
            negative_hits += 2

        positive_score = max(0.0, positive_hits - 0.4 * negation_hits)
        negative_score = max(0.0, negative_hits - 0.8 * negation_hits)
        neutral_score = 1.0 + max(0.0, 1.5 - abs(positive_score - negative_score))

        total = positive_score + negative_score + neutral_score
        pos = positive_score / total if total else 0.0
        neg = negative_score / total if total else 0.0
        neu = neutral_score / total if total else 1.0
        label = max({"positive": pos, "negative": neg, "neutral": neu}, key={"positive": pos, "negative": neg, "neutral": neu}.get)
        confidence = max(pos, neg, neu)
        polarity = pos - neg
        if confidence < float(self._pipeline_cfg.get("min_confidence", 0.55)):
            label = "neutral"
            polarity = 0.0
        return SentimentScore(
            text=str(text or ""),
            positive_prob=float(pos),
            negative_prob=float(neg),
            neutral_prob=float(neu),
            predicted_label=label,
            confidence=float(confidence),
            polarity=float(polarity),
            model_version=self._model_version,
            from_cache=False,
        )

    def _load_model(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("transformers/torch not installed") from exc

        india_path = Path(self._config.get("india_finetuned_path", "data/nlp/models/finbert_india"))
        base_path = Path(self._config.get("local_path", "data/nlp/models/finbert_base"))
        model_path = None
        requested_model_version = None
        if bool(self._config.get("use_india_model_if_available", True)) and (india_path / "config.json").exists():
            model_path = str(india_path)
            requested_model_version = "finbert_india"
        elif (base_path / "config.json").exists():
            model_path = str(base_path)
            requested_model_version = "finbert_base"
        else:
            if not bool(self._config.get("allow_remote_download", False)):
                raise RuntimeError("local FinBERT weights not found")
            model_path = str(self._config.get("hf_model_id", "ProsusAI/finbert"))
            requested_model_version = "finbert_hf"

        self._load_transformer_artifacts(
            model_path=model_path,
            model_version=str(requested_model_version),
            auto_tokenizer_cls=AutoTokenizer,
            auto_model_cls=AutoModelForSequenceClassification,
            local_base_path=base_path,
        )

    def _load_transformer_artifacts(
        self,
        *,
        model_path: str,
        model_version: str,
        auto_tokenizer_cls: Any,
        auto_model_cls: Any,
        local_base_path: Path,
    ) -> None:
        import torch

        self._model_version = model_version
        if self._device == "cpu":
            thread_count = int(self._config.get("torch_num_threads", 0) or 0)
            if thread_count > 0:
                try:
                    torch.set_num_threads(thread_count)
                except Exception:
                    logger.debug("Could not set torch thread count", exc_info=True)

        self._tokenizer = auto_tokenizer_cls.from_pretrained(model_path)
        model_kwargs: dict[str, Any] = {}
        if bool(self._config.get("low_cpu_mem_usage", True)):
            model_kwargs["low_cpu_mem_usage"] = True
        try:
            self._model = auto_model_cls.from_pretrained(model_path, **model_kwargs)
        except TypeError:
            model_kwargs.pop("low_cpu_mem_usage", None)
            self._model = auto_model_cls.from_pretrained(model_path, **model_kwargs)
        self._model.eval()
        self._model.to(self._device)

        if self._model_version == "finbert_india" and bool(self._config.get("validate_india_model_on_load", True)):
            if not self._india_model_passes_sanity_gate():
                logger.warning("finbert_india failed sanity gate; falling back to finbert_base")
                self._model = None
                self._tokenizer = None
                if (local_base_path / "config.json").exists():
                    self._load_transformer_artifacts(
                        model_path=str(local_base_path),
                        model_version="finbert_base",
                        auto_tokenizer_cls=auto_tokenizer_cls,
                        auto_model_cls=auto_model_cls,
                        local_base_path=local_base_path,
                    )
                    return
                logger.warning("finbert_base not available; continuing with finbert_india despite failed sanity gate")

        if self._model_version == "finbert_hf":
            local_base_path.mkdir(parents=True, exist_ok=True)
            self._tokenizer.save_pretrained(str(local_base_path))
            self._model.save_pretrained(str(local_base_path))
        self._cache_namespace_model_version = self._model_version

    def _infer_with_loaded_model(self, texts: list[str]) -> list[SentimentScore]:
        try:
            import torch
        except ImportError:
            return [self._heuristic_score(text) for text in texts]

        batch_size = int(self._config.get("batch_size", 64))
        max_length = int(self._config.get("max_length", 512))
        outputs: list[SentimentScore] = []
        with torch.no_grad():
            for start in range(0, len(texts), batch_size):
                chunk = texts[start : start + batch_size]
                inputs = self._tokenizer(
                    chunk,
                    padding=True,
                    truncation=True,
                    max_length=max_length,
                    return_tensors="pt",
                )
                if hasattr(inputs, "to"):
                    inputs = inputs.to(self._device)
                logits = self._model(**inputs).logits
                probs = torch.softmax(logits, dim=-1).detach().cpu().numpy()
                outputs.extend(self._build_scores(chunk, probs))
        return outputs

    def _india_model_passes_sanity_gate(self) -> bool:
        scores = self._infer_with_loaded_model([text for text, _ in self.INDIA_MODEL_SANITY_CASES])
        passed = 0
        for score, (_, expectation) in zip(scores, self.INDIA_MODEL_SANITY_CASES):
            if expectation == "positive" and score.polarity > 0.2 and score.predicted_label == "positive":
                passed += 1
            elif expectation == "negative" and score.polarity < -0.2 and score.predicted_label == "negative":
                passed += 1
            elif expectation == "neutral_or_nonnegative" and score.polarity >= -0.1 and score.predicted_label != "negative":
                passed += 1
        return passed >= 3

    def _resolve_device(self) -> str:
        preferred = str(self._config.get("device", "auto"))
        if preferred != "auto":
            return preferred
        try:
            import torch
        except ImportError:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(
            f"{self.CACHE_VERSION}:{self._active_cache_namespace_model_version()}:{text}".encode("utf-8")
        ).hexdigest()

    def _active_cache_namespace_model_version(self) -> str:
        if self._model is not None and self._tokenizer is not None:
            return self._model_version
        return self._cache_namespace_model_version

    def _detect_cache_namespace_model_version(self) -> str:
        india_path = Path(self._config.get("india_finetuned_path", "data/nlp/models/finbert_india"))
        base_path = Path(self._config.get("local_path", "data/nlp/models/finbert_base"))
        if bool(self._config.get("use_india_model_if_available", True)) and (india_path / "config.json").exists():
            return "finbert_india"
        if (base_path / "config.json").exists():
            return "finbert_base"
        if bool(self._config.get("allow_remote_download", False)):
            return "finbert_hf"
        return "heuristic_finance_v1"

    def _load_cache_index(self) -> dict[str, dict[str, Any]]:
        if not self._cache_index_path.exists():
            return {}
        try:
            return json.loads(self._cache_index_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
