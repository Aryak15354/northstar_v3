"""Progress-bar and resume checkpoint helpers for long-running collectors."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Iterable, Iterator, TypeVar


T = TypeVar("T")


try:  # pragma: no cover - optional dependency
    from tqdm.auto import tqdm as _tqdm  # type: ignore
except Exception:  # pragma: no cover
    _tqdm = None


class _SimpleBar:
    def __init__(self, total: int, desc: str, unit: str = "item"):
        self.total = int(max(0, total))
        self.desc = str(desc)
        self.unit = str(unit)
        self.count = 0

    def update(self, n: int = 1) -> None:
        self.count += int(n)
        total = max(self.total, 1)
        pct = min(100.0, 100.0 * float(self.count) / float(total))
        msg = f"\r[{self.desc}] {self.count}/{self.total} {self.unit}s ({pct:5.1f}%)"
        sys.stdout.write(msg)
        sys.stdout.flush()

    def close(self) -> None:
        if self.total > 0:
            sys.stdout.write("\n")
            sys.stdout.flush()


class Progress:
    def __init__(self, total: int, desc: str, unit: str = "item"):
        self._inner = _tqdm(total=total, desc=desc, unit=unit) if _tqdm is not None else _SimpleBar(total, desc, unit)

    def update(self, n: int = 1) -> None:
        self._inner.update(n)

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class ResumeState:
    """File-backed set of completed units with atomic writes."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.completed = self._load()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            payload = json.loads(self.path.read_text())
            vals = payload.get("completed", []) if isinstance(payload, dict) else []
            return {str(x) for x in vals}
        except Exception:
            return set()

    def has(self, key: str) -> bool:
        return str(key) in self.completed

    def mark(self, key: str) -> None:
        self.completed.add(str(key))
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"completed": sorted(self.completed)}
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        os.replace(tmp, self.path)


def iter_progress(items: Iterable[T], desc: str, unit: str = "item") -> Iterator[T]:
    seq = list(items)
    with Progress(total=len(seq), desc=desc, unit=unit) as p:
        for x in seq:
            yield x
            p.update(1)
