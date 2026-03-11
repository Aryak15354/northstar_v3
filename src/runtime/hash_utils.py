"""Hashing helpers for deterministic runtime artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_dumps(payload: Any) -> str:
    """Serialize payload deterministically for hashing and replay stability."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def canonical_hash(payload: Any) -> str:
    raw = canonical_json_dumps(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
