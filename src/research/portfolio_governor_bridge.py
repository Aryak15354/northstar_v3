"""Bridge research allocations into portfolio governor-friendly structure."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


class PortfolioGovernorBridge:
    def __init__(self, out_path: str = "data/research/research_governor_bridge.json"):
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)

    def export_allocation_intent(self, best_model: str, confidence: float, notes: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "best_model": str(best_model),
            "confidence": float(confidence),
            "intent": "research_proposal_only",
            "notes": notes,
        }
        tmp = self.out_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str))
        tmp.replace(self.out_path)
        return payload
