"""Bridge research outputs into capital allocator-compatible artifacts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


class CapitalAllocatorBridge:
    def __init__(self, out_path: str = "data/results/research/state/research_allocator_bridge.json"):
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)

    def export_health_scores(self, model_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Convert research model metrics into normalized health scores [0,1]."""
        scores = {}
        for model_name, payload in model_results.items():
            agg = payload.get("aggregate_metrics", {})
            sharpe = float(agg.get("avg_sharpe", 0.0))
            stability = float(agg.get("stability_score", 0.0))
            ic = float(agg.get("ic_mean", 0.0))
            health = max(0.0, min(1.0, 0.5 + 0.25 * sharpe + 0.20 * stability + 0.05 * ic))
            scores[model_name] = {
                "health_score": health,
                "sharpe": sharpe,
                "stability": stability,
                "ic": ic,
            }

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "health_scores": scores,
        }
        tmp = self.out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str))
        tmp.replace(self.out_path)
        return payload
