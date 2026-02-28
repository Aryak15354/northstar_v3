"""
Shadow Divergence Index (SDI) for AlphaOS vs legacy migration stability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional

import numpy as np


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SDIConfig:
    weight_w: float = 0.4
    weight_c: float = 0.2
    weight_s: float = 0.2
    weight_mu: float = 0.2
    inclusion_threshold: float = 0.01
    convexity_norm_scale: float = 0.20
    return_norm_scale: float = 0.10
    history_limit: int = 2000


class ShadowDivergenceIndex:
    def __init__(
        self,
        config: Optional[SDIConfig] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        self.config = config or SDIConfig()
        self.state_path = state_path
        self.history: list[dict] = []
        self._load_state()

    def update(
        self,
        *,
        alpha_weights: Mapping[str, float],
        legacy_weights: Mapping[str, float],
        alpha_convexity: float,
        legacy_convexity: float,
        alpha_expected_return: float,
        legacy_expected_return: float,
        regime_label: str,
    ) -> Dict[str, object]:
        a = self._normalize_weights(alpha_weights)
        l = self._normalize_weights(legacy_weights)

        keys = sorted(set(a.keys()) | set(l.keys()))
        dw = float(sum(abs(a.get(k, 0.0) - l.get(k, 0.0)) for k in keys))
        incl = self._inclusion_divergence(a, l)
        dc = float(abs(float(alpha_convexity) - float(legacy_convexity)))
        dmu = float(abs(float(alpha_expected_return) - float(legacy_expected_return)))

        dc_norm = float(np.tanh(dc / max(1e-8, float(self.config.convexity_norm_scale))))
        dmu_norm = float(np.tanh(dmu / max(1e-8, float(self.config.return_norm_scale))))
        sdi = (
            float(self.config.weight_w) * dw
            + float(self.config.weight_c) * dc_norm
            + float(self.config.weight_s) * incl
            + float(self.config.weight_mu) * dmu_norm
        )
        sdi = float(np.clip(sdi, 0.0, 1.0))

        band = "aligned"
        if sdi > 0.50:
            band = "migration_instability"
        elif sdi > 0.35:
            band = "structural_divergence"
        elif sdi > 0.15:
            band = "moderate_divergence"

        payload = {
            "timestamp": _utc_iso(),
            "regime": str(regime_label or "unknown"),
            "sdi": sdi,
            "band": band,
            "components": {
                "weight_divergence_l1": dw,
                "convexity_divergence_abs": dc,
                "strategy_inclusion_divergence": incl,
                "expected_return_divergence_abs": dmu,
            },
        }
        self.history.append(payload)
        self.history = self.history[-max(100, int(self.config.history_limit)) :]
        self._save_state()

        regime_stats = self.regime_stats()
        payload["regime_stats"] = regime_stats.get(str(regime_label or "unknown"), {})
        return payload

    def regime_stats(self) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        if not self.history:
            return out
        groups: Dict[str, list[float]] = {}
        for row in self.history:
            regime = str(row.get("regime", "unknown"))
            groups.setdefault(regime, []).append(float(row.get("sdi", 0.0) or 0.0))
        for regime, values in groups.items():
            vec = np.asarray(values, dtype=float)
            out[regime] = {
                "count": float(vec.size),
                "mean_sdi": float(np.mean(vec)),
                "p90_sdi": float(np.quantile(vec, 0.90)),
                "latest_sdi": float(vec[-1]),
            }
        return out

    def _normalize_weights(self, weights: Mapping[str, float]) -> Dict[str, float]:
        out = {str(k): float(v) for k, v in dict(weights).items()}
        gross = float(sum(abs(v) for v in out.values()))
        if gross <= 1e-12:
            return {k: 0.0 for k in out.keys()}
        return {k: float(v / gross) for k, v in out.items()}

    def _inclusion_divergence(self, alpha: Mapping[str, float], legacy: Mapping[str, float]) -> float:
        keys = sorted(set(alpha.keys()) | set(legacy.keys()))
        if not keys:
            return 0.0
        eps = float(self.config.inclusion_threshold)
        diffs = 0
        for k in keys:
            ia = abs(float(alpha.get(k, 0.0))) > eps
            il = abs(float(legacy.get(k, 0.0))) > eps
            diffs += int(ia != il)
        return float(diffs / len(keys))

    def _load_state(self) -> None:
        if self.state_path is None or not Path(self.state_path).exists():
            return
        try:
            payload = json.loads(Path(self.state_path).read_text())
            rows = payload.get("history", [])
            if isinstance(rows, list):
                self.history = [r for r in rows if isinstance(r, dict)]
            self.history = self.history[-max(100, int(self.config.history_limit)) :]
        except Exception:
            return

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        try:
            path = Path(self.state_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": _utc_iso(),
                "history": self.history[-max(100, int(self.config.history_limit)) :],
                "regime_stats": self.regime_stats(),
            }
            path.write_text(json.dumps(payload, indent=2))
        except Exception:
            return
