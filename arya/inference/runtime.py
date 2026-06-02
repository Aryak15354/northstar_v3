"""Drop-in `.complete()` runtime wrapper for Arya."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import torch
from tokenizers import Tokenizer


@dataclass(frozen=True)
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    cached: bool = False
    cost_usd: float = 0.0


class AryaRuntime:
    def __init__(self, model: Any, tokeniser_path: str | Path | Tokenizer, device: str | None = None):
        self._model = model
        self._tokeniser = (
            tokeniser_path
            if isinstance(tokeniser_path, Tokenizer)
            else Tokenizer.from_file(str(tokeniser_path))
        )
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        if hasattr(self._model, "to"):
            self._model.to(self._device)
        if hasattr(self._model, "eval"):
            self._model.eval()
        self._cache: dict[str, LLMResponse] = {}
        self.session_calls = 0
        self.session_cost_usd = 0.0

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 512,
        temperature: float = 0.2,
    ) -> LLMResponse:
        cache_key = hashlib.md5(
            f"{system}|{user}|{max_tokens}|{temperature}".encode("utf-8")
        ).hexdigest()
        if cache_key in self._cache:
            return replace(self._cache[cache_key], cached=True)

        prompt = f"<|system|>\n{system}\n<|user|>\n{user}\n<|assistant|>\n"
        input_ids = self._tokeniser.encode(prompt).ids
        input_tensor = torch.tensor([input_ids], dtype=torch.long, device=self._device)
        eos_id = self._tokeniser.token_to_id("<|eos|>")

        start = time.time()
        with torch.no_grad():
            output_tensor = self._model.generate(
                input_tensor,
                max_new_tokens=max_tokens,
                temperature=temperature,
                eos_token_id=eos_id,
            )
        latency_ms = (time.time() - start) * 1000

        new_ids = output_tensor[0, len(input_ids) :].detach().cpu().tolist()
        if eos_id is not None and eos_id in new_ids:
            new_ids = new_ids[: new_ids.index(eos_id)]
        content = self._tokeniser.decode(new_ids)
        response = LLMResponse(
            content=content,
            input_tokens=len(input_ids),
            output_tokens=len(new_ids),
            latency_ms=latency_ms,
        )
        self._cache[cache_key] = response
        self.session_calls += 1
        return response

