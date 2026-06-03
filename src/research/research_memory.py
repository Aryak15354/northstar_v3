"""Persistent research memory for survivor biasing and meta-learning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class ResearchMemory:
    def __init__(self, path: str = "data/results/research/state/research_memory.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(
                {
                    "model_stats": {},
                    "feature_stats": {},
                    "cycle_stats": {
                        "total_cycles": 0,
                        "accepted_candidates": 0,
                        "rejection_streak": 0,
                        "last_candidate_score": 0.0,
                        "adaptive_mutation_rate": 0.25,
                        "exploration_intensity": 0.5,
                        "last_updated": None,
                    },
                    "last_updated": None,
                }
            )

    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {
                "model_stats": {},
                "feature_stats": {},
                "cycle_stats": {
                    "total_cycles": 0,
                    "accepted_candidates": 0,
                    "rejection_streak": 0,
                    "last_candidate_score": 0.0,
                    "adaptive_mutation_rate": 0.25,
                    "exploration_intensity": 0.5,
                    "last_updated": None,
                },
                "last_updated": None,
            }

    def _write(self, payload: Dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str))
        tmp.replace(self.path)

    def update_model(self, model_name: str, metrics: Dict[str, float]) -> None:
        data = self._read()
        s = data.setdefault("model_stats", {}).setdefault(model_name, {"runs": 0, "avg_score": 0.0})
        runs = int(s.get("runs", 0)) + 1
        prev = float(s.get("avg_score", 0.0))
        score = float(metrics.get("stability_score", metrics.get("avg_sharpe", 0.0)))
        s["runs"] = runs
        s["avg_score"] = (prev * (runs - 1) + score) / runs
        data["last_updated"] = metrics.get("timestamp")
        self._write(data)

    def top_models(self, k: int = 5) -> list[tuple[str, float]]:
        data = self._read()
        rows = [
            (name, float(stats.get("avg_score", 0.0)))
            for name, stats in data.get("model_stats", {}).items()
        ]
        rows.sort(key=lambda x: x[1], reverse=True)
        return rows[: max(1, int(k))]

    def update_cycle(
        self,
        *,
        candidate_score: float,
        accepted: bool,
        errors_count: int = 0,
        timestamp: str | None = None,
    ) -> Dict[str, Any]:
        data = self._read()
        cs = data.setdefault("cycle_stats", {})
        total = int(cs.get("total_cycles", 0)) + 1
        accepted_count = int(cs.get("accepted_candidates", 0))
        rejection_streak = int(cs.get("rejection_streak", 0))
        mutation_rate = float(cs.get("adaptive_mutation_rate", 0.25))
        exploration = float(cs.get("exploration_intensity", 0.5))

        if accepted:
            accepted_count += 1
            rejection_streak = 0
            mutation_rate = max(0.10, mutation_rate * 0.90)
            exploration = max(0.25, exploration * 0.95)
        else:
            rejection_streak += 1
            mutation_rate = min(0.60, mutation_rate * 1.10)
            exploration = min(1.00, exploration + 0.03)

        if int(errors_count) > 0:
            exploration = min(1.00, exploration + 0.05)

        cs.update(
            {
                "total_cycles": total,
                "accepted_candidates": accepted_count,
                "rejection_streak": rejection_streak,
                "last_candidate_score": float(candidate_score),
                "adaptive_mutation_rate": float(mutation_rate),
                "exploration_intensity": float(exploration),
                "acceptance_rate": float(accepted_count / max(1, total)),
                "last_updated": timestamp,
            }
        )
        data["last_updated"] = timestamp
        self._write(data)
        return dict(cs)

    def awareness_snapshot(self) -> Dict[str, Any]:
        data = self._read()
        cs = dict(data.get("cycle_stats", {}))
        cs.setdefault("total_cycles", 0)
        cs.setdefault("accepted_candidates", 0)
        cs.setdefault("rejection_streak", 0)
        cs.setdefault("last_candidate_score", 0.0)
        cs.setdefault("adaptive_mutation_rate", 0.25)
        cs.setdefault("exploration_intensity", 0.5)
        cs.setdefault("acceptance_rate", 0.0)
        return cs
