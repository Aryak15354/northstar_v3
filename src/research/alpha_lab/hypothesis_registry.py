"""Alpha Lab hypothesis contracts and registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List


ModelFactory = Callable[[Dict[str, Any]], Any]


@dataclass(frozen=True)
class AlphaHypothesis:
    name: str
    model_factory: ModelFactory
    parameter_grid: Dict[str, List[Any]] = field(default_factory=dict)
    tags: Dict[str, Any] = field(default_factory=dict)


class HypothesisRegistry:
    def __init__(self) -> None:
        self._items: Dict[str, AlphaHypothesis] = {}

    def register(self, hypothesis: AlphaHypothesis) -> None:
        self._items[str(hypothesis.name)] = hypothesis

    def get(self, name: str) -> AlphaHypothesis | None:
        return self._items.get(str(name))

    def list(self) -> List[AlphaHypothesis]:
        return [self._items[k] for k in sorted(self._items)]

    def extend(self, hypotheses: Iterable[AlphaHypothesis]) -> None:
        for h in hypotheses:
            self.register(h)

