"""Persistence store for Alpha Lab fold and promotion artifacts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


class AlphaLabStore:
    def __init__(self, db_path: str = "data/diagnostics/alpha_diagnostics.db"):
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

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS alpha_lab_fold_results (
                    hypothesis_name TEXT NOT NULL,
                    parameter_hash TEXT NOT NULL,
                    fold_id INTEGER NOT NULL,
                    train_sharpe REAL,
                    test_sharpe REAL,
                    max_dd REAL,
                    turnover REAL,
                    stress_drag REAL,
                    stability_score REAL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (hypothesis_name, parameter_hash, fold_id)
                );

                CREATE TABLE IF NOT EXISTS alpha_lab_robustness_results (
                    hypothesis_name TEXT NOT NULL,
                    parameter_hash TEXT NOT NULL,
                    robustness_score REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (hypothesis_name, parameter_hash)
                );

                CREATE TABLE IF NOT EXISTS alpha_lab_promotions (
                    promotion_id TEXT PRIMARY KEY,
                    hypothesis_name TEXT NOT NULL,
                    parameter_hash TEXT NOT NULL,
                    promoted INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alpha_lab_surface_results (
                    hypothesis_name TEXT NOT NULL,
                    parameter_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    reject_reason TEXT NOT NULL,
                    train_sharpe REAL,
                    test_sharpe REAL,
                    shrunk_train_sharpe REAL,
                    gradient_norm REAL,
                    curvature REAL,
                    neighbor_stability REAL,
                    surface_variance_ratio REAL,
                    plateau_width INTEGER,
                    drift REAL,
                    regime_variance REAL,
                    weighted_regime_score REAL,
                    perturbation_drop REAL,
                    noise_robustness_score REAL,
                    neighbor_collapse REAL,
                    regime_tag TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (hypothesis_name, parameter_hash)
                );
                """
            )

    def write_fold_rows(
        self,
        *,
        hypothesis_name: str,
        parameter_hash: str,
        rows: Iterable[Dict[str, Any]],
    ) -> None:
        now = self._now_iso()
        with self.conn:
            for row in rows:
                payload = dict(row or {})
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO alpha_lab_fold_results (
                        hypothesis_name, parameter_hash, fold_id, train_sharpe, test_sharpe,
                        max_dd, turnover, stress_drag, stability_score, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(hypothesis_name),
                        str(parameter_hash),
                        int(payload.get("fold_id", 0) or 0),
                        float(payload.get("train_sharpe", 0.0) or 0.0),
                        float(payload.get("test_sharpe", 0.0) or 0.0),
                        float(payload.get("max_dd", 0.0) or 0.0),
                        float(payload.get("turnover", 0.0) or 0.0),
                        float(payload.get("stress_drag", 0.0) or 0.0),
                        float(payload.get("stability_score", 0.0) or 0.0),
                        json.dumps(payload, sort_keys=True),
                        now,
                    ),
                )

    def write_robustness(
        self,
        *,
        hypothesis_name: str,
        parameter_hash: str,
        robustness_payload: Dict[str, Any],
    ) -> None:
        now = self._now_iso()
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO alpha_lab_robustness_results (
                    hypothesis_name, parameter_hash, robustness_score, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(hypothesis_name),
                    str(parameter_hash),
                    float(robustness_payload.get("robustness_score", 0.0) or 0.0),
                    json.dumps(dict(robustness_payload or {}), sort_keys=True),
                    now,
                ),
            )

    def write_promotion(
        self,
        *,
        promotion_id: str,
        hypothesis_name: str,
        parameter_hash: str,
        promoted: bool,
        reason: str,
        payload: Dict[str, Any],
    ) -> None:
        now = self._now_iso()
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO alpha_lab_promotions (
                    promotion_id, hypothesis_name, parameter_hash, promoted, reason, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(promotion_id),
                    str(hypothesis_name),
                    str(parameter_hash),
                    int(bool(promoted)),
                    str(reason or ""),
                    json.dumps(dict(payload or {}), sort_keys=True),
                    now,
                ),
            )

    def write_surface_result(
        self,
        *,
        hypothesis_name: str,
        parameter_hash: str,
        surface_payload: Dict[str, Any],
    ) -> None:
        payload = dict(surface_payload or {})
        now = self._now_iso()
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO alpha_lab_surface_results (
                    hypothesis_name, parameter_hash, status, reject_reason,
                    train_sharpe, test_sharpe, shrunk_train_sharpe,
                    gradient_norm, curvature, neighbor_stability, surface_variance_ratio,
                    plateau_width, drift, regime_variance, weighted_regime_score,
                    perturbation_drop, noise_robustness_score, neighbor_collapse, regime_tag,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(hypothesis_name),
                    str(parameter_hash),
                    str(payload.get("status", "unknown")),
                    str(payload.get("reject_reason", "")),
                    float(payload.get("train_sharpe", 0.0) or 0.0),
                    float(payload.get("test_sharpe", 0.0) or 0.0),
                    float(payload.get("shrunk_train_sharpe", 0.0) or 0.0),
                    float(payload.get("gradient_norm", 0.0) or 0.0),
                    float(payload.get("curvature", 0.0) or 0.0),
                    float(payload.get("neighbor_stability", 0.0) or 0.0),
                    float(payload.get("surface_variance_ratio", 0.0) or 0.0),
                    int(payload.get("plateau_width", 0) or 0),
                    float(payload.get("drift", 0.0) or 0.0),
                    float(payload.get("regime_variance", 0.0) or 0.0),
                    float(payload.get("weighted_regime_score", 0.0) or 0.0),
                    float(payload.get("perturbation_drop", 0.0) or 0.0),
                    float(payload.get("noise_robustness_score", 0.0) or 0.0),
                    float(payload.get("neighbor_collapse", 0.0) or 0.0),
                    str(payload.get("regime_tag", "unknown")),
                    json.dumps(payload, sort_keys=True),
                    now,
                ),
            )

    def fetch_fold_rows(self, hypothesis_name: str, parameter_hash: str) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT payload_json
            FROM alpha_lab_fold_results
            WHERE hypothesis_name = ? AND parameter_hash = ?
            ORDER BY fold_id ASC
            """,
            (str(hypothesis_name), str(parameter_hash)),
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload_json"] or "{}"))
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                out.append(payload)
        return out
