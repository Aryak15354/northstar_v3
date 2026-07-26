#!/usr/bin/env python3
"""Raw-response disk cache. Every fetch writes its raw bytes here BEFORE any parsing is attempted --
if the parser has a bug (or the endpoint shape differs from what was assumed), the fix is a re-parse
of what's already on disk, never a re-scrape. This is the single most important property for a
37,000-request job: parsing bugs are cheap to fix; re-hitting the exchange is not.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CACHE_ROOT = REPO / "data/raw/exchanges/shareholding_pattern_scrape"


def cache_path(source: str, identifier: str, quarter_label: str, ext: str = "json") -> Path:
    """source: 'nse' or 'bse'. identifier: NSE symbol or BSE scripcode."""
    safe_id = str(identifier).strip().upper().replace("/", "_")
    return CACHE_ROOT / source / safe_id / f"{quarter_label}.{ext}"


def is_cached(source: str, identifier: str, quarter_label: str, ext: str = "json") -> bool:
    p = cache_path(source, identifier, quarter_label, ext)
    return p.exists() and p.stat().st_size > 0


def write_raw(source: str, identifier: str, quarter_label: str, content: bytes,
             *, ext: str = "json", meta: dict | None = None) -> Path:
    p = cache_path(source, identifier, quarter_label, ext)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(p)  # atomic on POSIX -- a killed process never leaves a half-written cache entry
    if meta is not None:
        meta_path = p.with_suffix(p.suffix + ".meta.json")
        meta_full = dict(meta, cached_at=time.time())
        meta_path.write_text(json.dumps(meta_full, indent=2, default=str))
    return p


def read_raw(source: str, identifier: str, quarter_label: str, ext: str = "json") -> bytes | None:
    p = cache_path(source, identifier, quarter_label, ext)
    return p.read_bytes() if p.exists() else None


def iter_cached(source: str):
    """Yield (identifier, quarter_label, path) for every cached raw response of a given source."""
    root = CACHE_ROOT / source
    if not root.exists():
        return
    for id_dir in sorted(root.iterdir()):
        if not id_dir.is_dir():
            continue
        for f in sorted(id_dir.glob("*.json")):
            if f.name.endswith(".meta.json"):
                continue
            yield id_dir.name, f.stem, f
        for f in sorted(id_dir.glob("*.csv")):
            yield id_dir.name, f.stem, f
