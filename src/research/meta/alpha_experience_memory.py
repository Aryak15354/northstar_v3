"""Phase 7 memory store for research experiment outcomes."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class AlphaExperience:
    experiment_id: str
    family: str
    parameter_vector: Dict[str, Any]
    regime_features: Dict[str, Any]
    metrics: Dict[str, Any]
    durability_score: float
    timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": str(self.experiment_id),
            "family": str(self.family),
            "parameter_vector": dict(self.parameter_vector or {}),
            "regime_features": dict(self.regime_features or {}),
            "metrics": dict(self.metrics or {}),
            "durability_score": float(self.durability_score),
            "timestamp_utc": str(self.timestamp_utc),
        }


class AlphaExperienceMemory:
    def __init__(self, db_path: str = "data/research/alpha_experience_memory.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _score_from_payload(payload: Mapping[str, Any]) -> float:
        p = dict(payload or {})
        if "durability_score" in p:
            try:
                return float(max(0.0, min(1.0, float(p["durability_score"]))))
            except Exception:
                return 0.0

        wf = float(max(0.0, p.get("wf_sharpe", p.get("test_sharpe", 0.0)) or 0.0))
        surv = float(max(0.0, min(1.0, p.get("mc_survival", p.get("survival_probability", 0.0)) or 0.0)))
        longevity = float(max(0.0, min(1.0, p.get("phase6_longevity", p.get("longevity", 0.0)) or 0.0)))
        fragility = float(max(0.0, p.get("surface_fragility", p.get("fragility", 0.0)) or 0.0))
        if (wf + surv + longevity + fragility) <= 0.0:
            return 0.0
        wf_norm = float(min(1.0, wf / 2.0))
        score = (0.35 * wf_norm) + (0.35 * surv) + (0.30 * longevity)
        score = score / (1.0 + fragility)
        return float(max(0.0, min(1.0, score)))

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS alpha_experience_memory (
                    experiment_id TEXT PRIMARY KEY,
                    family TEXT NOT NULL,
                    parameter_json TEXT NOT NULL,
                    regime_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    durability_score REAL NOT NULL,
                    timestamp_utc TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_aem_family_time ON alpha_experience_memory(family, timestamp_utc);
                """
            )

    def append_experiments(self, experiments: Iterable[Mapping[str, Any]]) -> int:
        rows = list(experiments or [])
        if not rows:
            return 0
        now = self._now_iso()
        inserted = 0
        with self.conn:
            for item in rows:
                p = dict(item or {})
                experiment_id = str(p.get("experiment_id", "") or "")
                if not experiment_id:
                    experiment_id = f"exp_{abs(hash(json.dumps(p, sort_keys=True, default=str))) % (10**16)}"
                family = str(p.get("family", "unknown") or "unknown")
                params = dict(p.get("parameter_vector", p.get("params", {})) or {})
                regime = dict(p.get("regime_features", p.get("regime", {})) or {})
                metrics = dict(p.get("metrics", {}) or {})
                if not metrics:
                    metrics = {k: v for k, v in p.items() if k not in {"experiment_id", "family", "parameter_vector", "params", "regime_features", "regime", "timestamp_utc"}}
                durability = self._score_from_payload({**metrics, **p})
                ts = str(p.get("timestamp_utc", now) or now)
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO alpha_experience_memory (
                        experiment_id, family, parameter_json, regime_json, metrics_json,
                        durability_score, timestamp_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        experiment_id,
                        family,
                        json.dumps(params, sort_keys=True),
                        json.dumps(regime, sort_keys=True),
                        json.dumps(metrics, sort_keys=True),
                        float(durability),
                        ts,
                    ),
                )
                inserted += 1
        return int(inserted)

    def fetch_recent(self, *, limit: int = 5000) -> List[AlphaExperience]:
        lim = int(max(1, limit))
        rows = self.conn.execute(
            """
            SELECT experiment_id, family, parameter_json, regime_json, metrics_json,
                   durability_score, timestamp_utc
            FROM alpha_experience_memory
            ORDER BY timestamp_utc DESC
            LIMIT ?
            """,
            (lim,),
        ).fetchall()
        out: List[AlphaExperience] = []
        for row in rows:
            try:
                params = json.loads(str(row["parameter_json"] or "{}"))
            except Exception:
                params = {}
            try:
                regime = json.loads(str(row["regime_json"] or "{}"))
            except Exception:
                regime = {}
            try:
                metrics = json.loads(str(row["metrics_json"] or "{}"))
            except Exception:
                metrics = {}
            out.append(
                AlphaExperience(
                    experiment_id=str(row["experiment_id"]),
                    family=str(row["family"]),
                    parameter_vector=dict(params or {}),
                    regime_features=dict(regime or {}),
                    metrics=dict(metrics or {}),
                    durability_score=float(row["durability_score"] or 0.0),
                    timestamp_utc=str(row["timestamp_utc"]),
                )
            )
        return out

    def family_metrics(self, *, limit: int = 5000) -> Dict[str, Dict[str, float]]:
        rows = self.fetch_recent(limit=limit)
        buckets: Dict[str, List[float]] = {}
        fragility: Dict[str, List[float]] = {}
        for row in rows:
            fam = str(row.family)
            buckets.setdefault(fam, []).append(float(row.durability_score))
            frag = float(row.metrics.get("surface_fragility", row.metrics.get("fragility", 0.0)) or 0.0)
            fragility.setdefault(fam, []).append(float(max(0.0, frag)))

        out: Dict[str, Dict[str, float]] = {}
        for fam, vals in buckets.items():
            n = len(vals)
            if n == 0:
                continue
            avg = sum(vals) / float(n)
            var = sum((v - avg) ** 2 for v in vals) / float(max(1, n - 1))
            frag_vals = fragility.get(fam, [])
            frag_avg = (sum(frag_vals) / float(len(frag_vals))) if frag_vals else 0.0
            out[fam] = {
                "count": float(n),
                "durability_mean": float(avg),
                "durability_std": float(var ** 0.5),
                "fragility_mean": float(frag_avg),
            }
        return out
