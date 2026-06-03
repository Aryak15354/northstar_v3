"""Lightweight distributed execution helpers for laptop research jobs."""

from __future__ import annotations

from multiprocessing import Pool, cpu_count
from typing import Any, Callable, Iterable, List


def parallel_map(func: Callable[[Any], Any], jobs: Iterable[Any], n_workers: int | None = None) -> List[Any]:
    items = list(jobs)
    if not items:
        return []

    workers = int(n_workers) if n_workers is not None else max(1, cpu_count() - 2)
    workers = max(1, min(workers, len(items)))

    if workers <= 1:
        return [func(x) for x in items]

    with Pool(processes=workers) as pool:
        return pool.map(func, items)
