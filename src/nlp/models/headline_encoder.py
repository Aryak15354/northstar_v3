"""Shared sentence-embedding wrapper for headlines and narratives."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.nlp.models.model_registry import NLPModelRegistry

logger = logging.getLogger(__name__)


class HeadlineEncoder:
    """Encodes headlines into dense vectors with a deterministic fallback."""

    CACHE_VERSION = "v1"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        encoder_cfg = self._config.get("nlp", {}).get("models", {}).get("encoder", {})
        self._embedding_dim = int(encoder_cfg.get("embedding_dim", 384))
        self._cache_enabled = bool(encoder_cfg.get("cache_embeddings", True))
        self._cache_path = Path(encoder_cfg.get("cache_path", "data/nlp/cache/embeddings"))
        self._cache_path.mkdir(parents=True, exist_ok=True)
        self._model = None
        self._model_version = "hashing_fallback"
        self._registry = NLPModelRegistry(self._config)

    def encode_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self._embedding_dim), dtype=np.float32)
        vectors: list[np.ndarray] = []
        missing: list[tuple[int, str, Path]] = []
        for idx, text in enumerate(texts):
            cache_file = self._cache_file(text)
            if self._cache_enabled and cache_file.exists():
                vectors.append(np.load(cache_file))
            else:
                vectors.append(np.zeros(self._embedding_dim, dtype=np.float32))
                missing.append((idx, text, cache_file))

        if missing:
            new_vectors = self._encode_uncached([item[1] for item in missing])
            for (idx, _, cache_file), vector in zip(missing, new_vectors):
                vectors[idx] = vector
                if self._cache_enabled:
                    np.save(cache_file, vector)
        return np.vstack(vectors).astype(np.float32)

    def encode_single(self, text: str) -> np.ndarray:
        batch = self.encode_batch([text])
        return batch[0] if len(batch) else np.zeros(self._embedding_dim, dtype=np.float32)

    def similarity(self, left: str, right: str) -> float:
        left_vec = self.encode_single(left)
        right_vec = self.encode_single(right)
        denom = float(np.linalg.norm(left_vec) * np.linalg.norm(right_vec))
        if denom <= 0.0:
            return 0.0
        return float(np.dot(left_vec, right_vec) / denom)

    def _encode_uncached(self, texts: list[str]) -> list[np.ndarray]:
        try:
            self._load_model()
        except Exception as exc:
            logger.debug("Headline encoder model unavailable, using hashing fallback: %s", exc)
            return [self._hash_embedding(text) for text in texts]

        if self._model is None:
            return [self._hash_embedding(text) for text in texts]
        try:
            encoded = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True)
            self._model_version = "sentence_transformer"
            return [np.asarray(row, dtype=np.float32) for row in encoded]
        except Exception as exc:
            logger.warning("Sentence encoder inference failed, falling back to hashing: %s", exc)
            return [self._hash_embedding(text) for text in texts]

    def _load_model(self) -> None:
        if self._model is not None:
            return
        spec = self._registry.encoder_model()
        if spec.source != "local" and not bool(self._config.get("nlp", {}).get("models", {}).get("encoder", {}).get("allow_remote_download", False)):
            raise RuntimeError("local sentence-encoder weights not found")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is not installed") from exc
        self._model = SentenceTransformer(spec.path)
        self._model_version = spec.name

    def _cache_file(self, text: str) -> Path:
        digest = hashlib.md5(f"{self.CACHE_VERSION}:{text}".encode("utf-8")).hexdigest()
        return self._cache_path / f"{digest}.npy"

    def _hash_embedding(self, text: str) -> np.ndarray:
        vector = np.zeros(self._embedding_dim, dtype=np.float32)
        for token in str(text or "").lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._embedding_dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = float(np.linalg.norm(vector))
        if norm > 0.0:
            vector /= norm
        return vector
