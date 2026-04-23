"""Alpha Diagnostics Engine (ADE): advisory closed-loop diagnostics on top of PRS."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DiagnosticsPaths:
    runtime_db: str = "data/runtime/portfolio_runtime.db"
    diagnostics_db: str = "data/diagnostics/alpha_diagnostics.db"
    alpha_metrics_parquet: str = "data/diagnostics/alpha_metrics.parquet"
    strategy_metrics_parquet: str = "data/diagnostics/strategy_metrics.parquet"
    policy_recommendations_json: str = "data/diagnostics/policy_recommendations.json"


class AlphaDiagnosticsEngine:
    """Compute trade/strategy/portfolio diagnostics from runtime ledger truth."""

    def __init__(self, paths: DiagnosticsPaths | None = None):
        self.paths = paths or DiagnosticsPaths()
        Path(self.paths.diagnostics_db).parent.mkdir(parents=True, exist_ok=True)
        Path(self.paths.alpha_metrics_parquet).parent.mkdir(parents=True, exist_ok=True)
        runtime_db = Path(self.paths.runtime_db)
        runtime_db.parent.mkdir(parents=True, exist_ok=True)
        if runtime_db.exists():
            uri = f"file:{runtime_db}?mode=ro"
            self.runtime_conn = sqlite3.connect(uri, uri=True)
        else:
            # Best-effort fallback for bootstrap/smoke usage.
            self.runtime_conn = sqlite3.connect(self.paths.runtime_db)
        self.runtime_conn.row_factory = sqlite3.Row
        self.diag_conn = sqlite3.connect(self.paths.diagnostics_db)
        self.diag_conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        try:
            self.runtime_conn.close()
        except Exception:
            pass
        try:
            self.diag_conn.close()
        except Exception:
            pass

    def _init_schema(self) -> None:
        with self.diag_conn:
            self.diag_conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS trade_diagnostics (
                    trade_id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    open_event_id INTEGER NOT NULL,
                    close_event_id INTEGER NOT NULL,
                    hold_days REAL,
                    expected_edge REAL,
                    requested_notional REAL,
                    realized_pnl REAL,
                    capital_reserved REAL,
                    edge_realization_ratio REAL,
                    capital_efficiency_ratio REAL,
                    stress_drag_ratio REAL,
                    regime_at_entry TEXT,
                    regime_at_exit TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS strategy_diagnostics (
                    strategy_id TEXT PRIMARY KEY,
                    trade_count INTEGER NOT NULL,
                    avg_err REAL,
                    avg_cer REAL,
                    avg_sdr REAL,
                    starvation_ratio REAL,
                    rebalance_efficiency REAL,
                    sharpe REAL,
                    max_drawdown REAL,
                    stability_score REAL,
                    edge_decay REAL,
                    regime_sensitivity REAL,
                    certification_survival_ratio REAL,
                    last_updated TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS portfolio_diagnostics (
                    snapshot_ts TEXT PRIMARY KEY,
                    eqs REAL,
                    gross_exposure REAL,
                    net_exposure REAL,
                    portfolio_sharpe REAL,
                    stress_loss_ratio REAL,
                    reserve_utilization_equity REAL,
                    reserve_utilization_options REAL,
                    reserve_utilization_hedge REAL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS policy_recommendations (
                    recommendation_ts TEXT PRIMARY KEY,
                    recommendation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _safe_json_load(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        try:
            payload = json.loads(str(raw or "{}"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            out = float(v)
        except Exception:
            return float(default)
        if not np.isfinite(out):
            return float(default)
        return float(out)

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return float(max(lo, min(hi, x)))

    @staticmethod
    def _row_to_series(cur: sqlite3.Cursor) -> pd.DataFrame:
        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])

    def _runtime_table_exists(self, table_name: str) -> bool:
        row = self.runtime_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ? LIMIT 1",
            (str(table_name),),
        ).fetchone()
        return row is not None

    def _load_closed_positions(self) -> pd.DataFrame:
        if not self._runtime_table_exists("position_lifecycle_table"):
            return pd.DataFrame()
        cur = self.runtime_conn.execute(
            """
            SELECT
                plc.id AS lifecycle_id,
                plc.position_key,
                plc.strategy_id,
                plc.signal_id,
                plc.open_event_id,
                plc.close_event_id,
                plc.hold_days,
                plc.realized_pnl,
                plc.open_reason,
                plc.close_reason,
                oe.proposal_id AS open_proposal_id,
                ce.timestamp_utc AS close_timestamp_utc
            FROM position_lifecycle_table plc
            LEFT JOIN portfolio_events oe ON oe.event_id = plc.open_event_id
            LEFT JOIN portfolio_events ce ON ce.event_id = plc.close_event_id
            WHERE plc.close_event_id IS NOT NULL
            ORDER BY plc.close_event_id ASC
            """
        )
        return self._row_to_series(cur)

    def _load_stress_drag(self, open_event_id: int, close_event_id: int) -> float:
        if not self._runtime_table_exists("portfolio_stress_matrix"):
            return 0.0
        row = self.runtime_conn.execute(
            """
            SELECT MAX(risk_metric) AS max_risk_metric
            FROM portfolio_stress_matrix
            WHERE event_id BETWEEN ? AND ?
            """,
            (int(open_event_id), int(close_event_id)),
        ).fetchone()
        if row is None:
            return 0.0
        return self._safe_float(row["max_risk_metric"], 0.0)

    def _load_proposal_payload(self, proposal_id: str) -> Dict[str, Any]:
        if not self._runtime_table_exists("proposal_inbox"):
            return {}
        row = self.runtime_conn.execute(
            "SELECT proposal_json FROM proposal_inbox WHERE proposal_id = ?",
            (str(proposal_id),),
        ).fetchone()
        if row is None:
            return {}
        return self._safe_json_load(row["proposal_json"])

    def _load_regime_at_event(self, event_id: int) -> str:
        if not self._runtime_table_exists("portfolio_events"):
            return ""
        row = self.runtime_conn.execute(
            "SELECT payload_json FROM portfolio_events WHERE event_id = ?",
            (int(event_id),),
        ).fetchone()
        if row is None:
            return ""
        payload = self._safe_json_load(row["payload_json"])
        regime = payload.get("regime_context", {})
        if isinstance(regime, dict):
            return str(regime.get("regime", regime.get("state", "")) or "")
        return str(regime or "")

    def compute_trade_diagnostics(self) -> pd.DataFrame:
        trades = self._load_closed_positions()
        if trades.empty:
            out = pd.DataFrame(
                columns=[
                    "trade_id",
                    "strategy_id",
                    "signal_id",
                    "origin",
                    "open_event_id",
                    "close_event_id",
                    "hold_days",
                    "expected_edge",
                    "requested_notional",
                    "realized_pnl",
                    "capital_reserved",
                    "edge_realization_ratio",
                    "capital_efficiency_ratio",
                    "stress_drag_ratio",
                    "regime_at_entry",
                    "regime_at_exit",
                    "created_at",
                ]
            )
            out.to_parquet(self.paths.alpha_metrics_parquet, index=False)
            return out

        rows: List[Dict[str, Any]] = []
        now_iso = self._now_iso()
        for _, row in trades.iterrows():
            proposal_id = str(row.get("open_proposal_id", "") or "")
            proposal = self._load_proposal_payload(proposal_id)
            expected_edge = self._safe_float(proposal.get("expected_edge", 0.0))
            requested_notional = self._safe_float(proposal.get("requested_notional", 0.0))
            realized_pnl = self._safe_float(row.get("realized_pnl", 0.0))
            hold_days = max(0.0, self._safe_float(row.get("hold_days", 0.0)))
            expected_edge_notional = expected_edge * requested_notional
            if abs(expected_edge_notional) > 1e-12:
                err = self._clamp(realized_pnl / expected_edge_notional, -5.0, 5.0)
            else:
                err = 0.0
            if hold_days > 0.0 and requested_notional > 0.0:
                cer = realized_pnl / (requested_notional * hold_days)
            else:
                cer = 0.0
            sdr = self._load_stress_drag(int(row["open_event_id"]), int(row["close_event_id"]))
            regime_at_entry = self._load_regime_at_event(int(row["open_event_id"]))
            regime_at_exit = self._load_regime_at_event(int(row["close_event_id"]))
            rows.append(
                {
                    "trade_id": str(row.get("position_key", "") or row.get("lifecycle_id")),
                    "strategy_id": str(row.get("strategy_id", "") or ""),
                    "signal_id": str(row.get("signal_id", "") or ""),
                    "origin": str(proposal.get("origin", "")),
                    "open_event_id": int(row["open_event_id"]),
                    "close_event_id": int(row["close_event_id"]),
                    "hold_days": hold_days,
                    "expected_edge": expected_edge,
                    "requested_notional": requested_notional,
                    "realized_pnl": realized_pnl,
                    "capital_reserved": requested_notional,
                    "edge_realization_ratio": err,
                    "capital_efficiency_ratio": cer,
                    "stress_drag_ratio": sdr,
                    "regime_at_entry": regime_at_entry,
                    "regime_at_exit": regime_at_exit,
                    "created_at": now_iso,
                }
            )

        out = pd.DataFrame(rows)
        with self.diag_conn:
            self.diag_conn.execute("DELETE FROM trade_diagnostics")
            out.to_sql("trade_diagnostics", self.diag_conn, if_exists="append", index=False)
        out.to_parquet(self.paths.alpha_metrics_parquet, index=False)
        return out

    def _starvation_by_strategy(self) -> Dict[str, float]:
        if not self._runtime_table_exists("proposal_inbox"):
            return {}
        proposals = self._row_to_series(
            self.runtime_conn.execute(
                """
                SELECT proposal_id, proposal_json
                FROM proposal_inbox
                """
            )
        )
        if proposals.empty:
            return {}

        requested: Dict[str, float] = {}
        approved: Dict[str, float] = {}
        if self._runtime_table_exists("portfolio_events"):
            approved_rows = self._row_to_series(
                self.runtime_conn.execute(
                    """
                    SELECT proposal_id, payload_json
                    FROM portfolio_events
                    WHERE event_type = 'INTENT_APPROVED'
                    """
                )
            )
        else:
            approved_rows = pd.DataFrame()
        approved_map: Dict[str, float] = {}
        if not approved_rows.empty:
            for _, row in approved_rows.iterrows():
                payload = self._safe_json_load(row["payload_json"])
                approved_map[str(row["proposal_id"])] = self._safe_float(payload.get("approved_notional", 0.0))

        for _, row in proposals.iterrows():
            proposal = self._safe_json_load(row["proposal_json"])
            strategy = str(proposal.get("strategy_id", "") or "")
            req = self._safe_float(proposal.get("requested_notional", 0.0))
            ap = self._safe_float(approved_map.get(str(row["proposal_id"]), 0.0))
            requested[strategy] = requested.get(strategy, 0.0) + req
            approved[strategy] = approved.get(strategy, 0.0) + ap

        out: Dict[str, float] = {}
        for strategy, req in requested.items():
            app = approved.get(strategy, 0.0)
            if req <= 0.0:
                out[strategy] = 0.0
            else:
                out[strategy] = self._clamp(1.0 - (app / req), 0.0, 1.0)
        return out

    def _rebalance_efficiency_by_strategy(self) -> Dict[str, float]:
        if not self._runtime_table_exists("position_lifecycle_table"):
            return {}
        if not self._runtime_table_exists("execution_fills") or not self._runtime_table_exists("portfolio_events"):
            return {}
        pnl_rows = self._row_to_series(
            self.runtime_conn.execute(
                """
                SELECT strategy_id, SUM(COALESCE(realized_pnl, 0.0)) AS realized_pnl
                FROM position_lifecycle_table
                WHERE close_reason LIKE 'rebalance.%'
                GROUP BY strategy_id
                """
            )
        )
        cost_rows = self._row_to_series(
            self.runtime_conn.execute(
                """
                SELECT pe.strategy_id, SUM(COALESCE(ef.fill_notional, 0.0)) AS traded_notional
                FROM execution_fills ef
                JOIN portfolio_events pe ON pe.event_id = ef.event_id
                WHERE pe.trigger_reason_code LIKE 'rebalance.%'
                GROUP BY pe.strategy_id
                """
            )
        )
        pnl_map = {str(r["strategy_id"]): self._safe_float(r["realized_pnl"]) for _, r in pnl_rows.iterrows()} if not pnl_rows.empty else {}
        cost_map = {
            str(r["strategy_id"]): self._safe_float(r["traded_notional"]) * 0.0005
            for _, r in cost_rows.iterrows()
        } if not cost_rows.empty else {}
        out: Dict[str, float] = {}
        for strategy in set(pnl_map) | set(cost_map):
            pnl = self._safe_float(pnl_map.get(strategy, 0.0))
            cost = self._safe_float(cost_map.get(strategy, 0.0))
            out[strategy] = pnl / cost if cost > 0 else 0.0
        return out

    def _certification_survival_by_strategy(self) -> Dict[str, float]:
        if not self._runtime_table_exists("proposal_inbox"):
            return {}
        has_events = self._runtime_table_exists("portfolio_events")
        has_cert = self._runtime_table_exists("certification_snapshots")
        if has_events and has_cert:
            rows = self._row_to_series(
                self.runtime_conn.execute(
                    """
                    SELECT
                        p.proposal_json,
                        s.valid_until,
                        e.timestamp_utc AS approved_ts
                    FROM proposal_inbox p
                    LEFT JOIN certification_snapshots s
                      ON s.snapshot_hash = json_extract(p.proposal_json, '$.certification_snapshot_hash')
                    LEFT JOIN (
                        SELECT proposal_id, MIN(timestamp_utc) AS timestamp_utc
                        FROM portfolio_events
                        WHERE event_type = 'INTENT_APPROVED'
                        GROUP BY proposal_id
                    ) e
                      ON e.proposal_id = p.proposal_id
                    """
                )
            )
        else:
            rows = self._row_to_series(
                self.runtime_conn.execute(
                    """
                    SELECT proposal_json, '' AS valid_until, '' AS approved_ts
                    FROM proposal_inbox
                    """
                )
            )
        if rows.empty:
            return {}
        total: Dict[str, int] = {}
        survived: Dict[str, int] = {}
        for _, row in rows.iterrows():
            proposal = self._safe_json_load(row["proposal_json"])
            strategy = str(proposal.get("strategy_id", "") or "")
            total[strategy] = total.get(strategy, 0) + 1
            approved_ts = str(row.get("approved_ts", "") or "")
            valid_until = str(row.get("valid_until", "") or "")
            if approved_ts and valid_until and approved_ts <= valid_until:
                survived[strategy] = survived.get(strategy, 0) + 1
        out: Dict[str, float] = {}
        for strategy, n in total.items():
            out[strategy] = float(survived.get(strategy, 0)) / float(max(1, n))
        return out

    @staticmethod
    def _series_sharpe(values: pd.Series) -> float:
        arr = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
        if len(arr) < 2:
            return 0.0
        sd = float(np.std(arr, ddof=1))
        if sd <= 1e-12:
            return 0.0
        return float(np.mean(arr) / sd)

    def compute_strategy_diagnostics(self) -> pd.DataFrame:
        trades = self._row_to_series(self.diag_conn.execute("SELECT * FROM trade_diagnostics ORDER BY close_event_id ASC"))
        if trades.empty:
            out = pd.DataFrame(
                columns=[
                    "strategy_id",
                    "trade_count",
                    "avg_err",
                    "avg_cer",
                    "avg_sdr",
                    "starvation_ratio",
                    "rebalance_efficiency",
                    "sharpe",
                    "max_drawdown",
                    "stability_score",
                    "edge_decay",
                    "regime_sensitivity",
                    "certification_survival_ratio",
                    "last_updated",
                ]
            )
            out.to_parquet(self.paths.strategy_metrics_parquet, index=False)
            return out

        starvation = self._starvation_by_strategy()
        rebalance_eff = self._rebalance_efficiency_by_strategy()
        cert_survival = self._certification_survival_by_strategy()
        now_iso = self._now_iso()

        rows: List[Dict[str, Any]] = []
        for strategy, grp in trades.groupby("strategy_id", sort=True):
            g = grp.sort_values("close_event_id")
            err = pd.to_numeric(g["edge_realization_ratio"], errors="coerce").fillna(0.0)
            cer = pd.to_numeric(g["capital_efficiency_ratio"], errors="coerce").fillna(0.0)
            sdr = pd.to_numeric(g["stress_drag_ratio"], errors="coerce").fillna(0.0)
            pnl = pd.to_numeric(g["realized_pnl"], errors="coerce").fillna(0.0)
            curve = pnl.cumsum()
            dd = curve - curve.cummax()
            max_dd = float(abs(dd.min())) if len(dd) else 0.0
            sharpe = self._series_sharpe(pnl)

            if len(err) >= 2:
                x = np.arange(len(err), dtype=float)
                slope = float(np.polyfit(x, err.to_numpy(dtype=float), 1)[0])
            else:
                slope = 0.0

            regime_sharpes: List[float] = []
            for _, rg in g.groupby("regime_at_entry"):
                regime_sharpes.append(self._series_sharpe(pd.to_numeric(rg["realized_pnl"], errors="coerce").fillna(0.0)))
            if len(regime_sharpes) >= 2:
                mean_abs = abs(float(np.mean(regime_sharpes)))
                regime_sensitivity = float(np.std(regime_sharpes)) / max(1e-12, mean_abs)
            else:
                regime_sensitivity = 0.0

            if len(pnl) >= 6:
                windows = []
                window = min(20, max(6, len(pnl) // 2))
                arr = pnl.to_numpy(dtype=float)
                for i in range(window, len(arr) + 1):
                    segment = arr[i - window : i]
                    sd = float(np.std(segment, ddof=1)) if len(segment) > 1 else 0.0
                    windows.append(float(np.mean(segment) / sd) if sd > 1e-12 else 0.0)
                if len(windows) >= 2 and abs(float(np.mean(windows))) > 1e-9:
                    stability = 1.0 - (float(np.std(windows)) / abs(float(np.mean(windows))))
                else:
                    stability = 0.0
            else:
                stability = 0.0
            stability = self._clamp(stability, 0.0, 1.0)

            rows.append(
                {
                    "strategy_id": str(strategy),
                    "trade_count": int(len(g)),
                    "avg_err": float(err.mean()),
                    "avg_cer": float(cer.mean()),
                    "avg_sdr": float(sdr.mean()),
                    "starvation_ratio": float(starvation.get(str(strategy), 0.0)),
                    "rebalance_efficiency": float(rebalance_eff.get(str(strategy), 0.0)),
                    "sharpe": float(sharpe),
                    "max_drawdown": float(max_dd),
                    "stability_score": float(stability),
                    "edge_decay": float(slope),
                    "regime_sensitivity": float(regime_sensitivity),
                    "certification_survival_ratio": float(cert_survival.get(str(strategy), 0.0)),
                    "last_updated": now_iso,
                }
            )

        out = pd.DataFrame(rows).sort_values("strategy_id")
        with self.diag_conn:
            self.diag_conn.execute("DELETE FROM strategy_diagnostics")
            out.to_sql("strategy_diagnostics", self.diag_conn, if_exists="append", index=False)
        out.to_parquet(self.paths.strategy_metrics_parquet, index=False)
        return out

    def _latest_runtime_snapshot(self) -> Dict[str, Any]:
        if not self._runtime_table_exists("portfolio_snapshots"):
            return {}
        row = self.runtime_conn.execute(
            "SELECT state_json FROM portfolio_snapshots ORDER BY snapshot_id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return {}
        return self._safe_json_load(row["state_json"])

    def _reserve_utilization(self) -> Dict[str, float]:
        if not self._runtime_table_exists("portfolio_events"):
            return {"equity": 0.0, "options": 0.0, "hedge": 0.0}
        rows = self._row_to_series(
            self.runtime_conn.execute(
                """
                SELECT
                    origin,
                    SUM(COALESCE(json_extract(payload_json, '$.approved_notional'), 0.0)) AS approved_notional
                FROM portfolio_events
                WHERE event_type = 'INTENT_APPROVED'
                GROUP BY origin
                """
            )
        )
        if rows.empty:
            return {"equity": 0.0, "options": 0.0, "hedge": 0.0}
        total = float(pd.to_numeric(rows["approved_notional"], errors="coerce").fillna(0.0).sum())
        if total <= 0.0:
            return {"equity": 0.0, "options": 0.0, "hedge": 0.0}
        equity = 0.0
        options = 0.0
        hedge = 0.0
        for _, row in rows.iterrows():
            origin = str(row["origin"] or "")
            val = self._safe_float(row["approved_notional"], 0.0)
            if origin in {"options_alpha"}:
                options += val
            elif origin in {"options_hedge"}:
                hedge += val
            else:
                equity += val
        return {
            "equity": equity / total,
            "options": options / total,
            "hedge": hedge / total,
        }

    def compute_portfolio_diagnostics(self) -> pd.DataFrame:
        strategy = self._row_to_series(self.diag_conn.execute("SELECT * FROM strategy_diagnostics"))
        trades = self._row_to_series(self.diag_conn.execute("SELECT * FROM trade_diagnostics"))
        runtime = self._latest_runtime_snapshot()
        reserve_util = self._reserve_utilization()
        now_iso = self._now_iso()

        avg_err = self._safe_float(trades.get("edge_realization_ratio", pd.Series(dtype=float)).mean() if not trades.empty else 0.0)
        avg_cer = self._safe_float(trades.get("capital_efficiency_ratio", pd.Series(dtype=float)).mean() if not trades.empty else 0.0)
        avg_sdr = self._safe_float(trades.get("stress_drag_ratio", pd.Series(dtype=float)).mean() if not trades.empty else 0.0)
        avg_starvation = self._safe_float(strategy.get("starvation_ratio", pd.Series(dtype=float)).mean() if not strategy.empty else 0.0)

        norm_err = self._clamp(avg_err, 0.0, 1.0)
        norm_cer = self._clamp(avg_cer, 0.0, 1.0)
        norm_sdr = self._clamp(avg_sdr, 0.0, 1.0)
        norm_starvation = self._clamp(avg_starvation, 0.0, 1.0)
        eqs = (
            0.35 * norm_err
            + 0.30 * norm_cer
            + 0.20 * (1.0 - norm_sdr)
            + 0.15 * (1.0 - norm_starvation)
        )
        eqs = self._clamp(eqs, 0.0, 1.0)

        pnl = pd.to_numeric(trades.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        portfolio_sharpe = self._series_sharpe(pnl)

        out = pd.DataFrame(
            [
                {
                    "snapshot_ts": now_iso,
                    "eqs": float(eqs),
                    "gross_exposure": self._safe_float(runtime.get("gross_exposure", 0.0)),
                    "net_exposure": self._safe_float(runtime.get("net_exposure", 0.0)),
                    "portfolio_sharpe": float(portfolio_sharpe),
                    "stress_loss_ratio": float(avg_sdr),
                    "reserve_utilization_equity": float(reserve_util["equity"]),
                    "reserve_utilization_options": float(reserve_util["options"]),
                    "reserve_utilization_hedge": float(reserve_util["hedge"]),
                    "created_at": now_iso,
                }
            ]
        )
        with self.diag_conn:
            out.to_sql("portfolio_diagnostics", self.diag_conn, if_exists="append", index=False)

        recommendations = self._build_policy_recommendations(strategy, out.iloc[0].to_dict())
        with self.diag_conn:
            self.diag_conn.execute(
                """
                INSERT OR REPLACE INTO policy_recommendations (
                    recommendation_ts, recommendation_json, created_at
                ) VALUES (?, ?, ?)
                """,
                (now_iso, json.dumps(recommendations, sort_keys=True), now_iso),
            )
        Path(self.paths.policy_recommendations_json).write_text(
            json.dumps(recommendations, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return out

    def _build_policy_recommendations(
        self,
        strategy_df: pd.DataFrame,
        portfolio_row: Dict[str, Any],
    ) -> Dict[str, Any]:
        reserve_adj = {"equity_alpha": 0.0, "options_alpha": 0.0, "hedge": 0.0}
        strategy_cap_adjustment: Dict[str, float] = {}
        rebalance_adj: Dict[str, float] = {}
        ttl_adj_days = 0

        if not strategy_df.empty:
            cer_mean = self._safe_float(pd.to_numeric(strategy_df["avg_cer"], errors="coerce").fillna(0.0).mean())
            for _, row in strategy_df.iterrows():
                sid = str(row["strategy_id"])
                err = self._safe_float(row.get("avg_err", 0.0))
                cer = self._safe_float(row.get("avg_cer", 0.0))
                starvation = self._safe_float(row.get("starvation_ratio", 0.0))
                edge_decay = self._safe_float(row.get("edge_decay", 0.0))
                if starvation > 0.40 and err > 1.0 and cer > cer_mean:
                    strategy_cap_adjustment[sid] = 0.05
                elif err < 0.60 or edge_decay < -0.02:
                    strategy_cap_adjustment[sid] = -0.05

                reb_eff = self._safe_float(row.get("rebalance_efficiency", 0.0))
                if reb_eff < 1.0:
                    rebalance_adj["rule.volatility_shock"] = 0.05

            options_score = self._safe_float(
                pd.to_numeric(
                    strategy_df[strategy_df["strategy_id"].str.contains("option", case=False, na=False)]["avg_cer"],
                    errors="coerce",
                ).fillna(0.0).mean()
            )
            equity_score = self._safe_float(
                pd.to_numeric(
                    strategy_df[~strategy_df["strategy_id"].str.contains("option", case=False, na=False)]["avg_cer"],
                    errors="coerce",
                ).fillna(0.0).mean()
            )
            if options_score > equity_score + 0.01:
                reserve_adj["options_alpha"] = 0.05
                reserve_adj["equity_alpha"] = -0.05
            elif equity_score > options_score + 0.01:
                reserve_adj["options_alpha"] = -0.05
                reserve_adj["equity_alpha"] = 0.05

            cert_survival = self._safe_float(
                pd.to_numeric(strategy_df["certification_survival_ratio"], errors="coerce").fillna(0.0).mean()
            )
            if cert_survival < 0.50:
                ttl_adj_days = +5
            elif cert_survival > 0.90:
                ttl_adj_days = -5

        return {
            "generated_at": self._now_iso(),
            "advisory_only": True,
            "portfolio_eqs": float(self._safe_float(portfolio_row.get("eqs", 0.0))),
            "reserve_adjustment": reserve_adj,
            "strategy_cap_adjustment": strategy_cap_adjustment,
            "rebalance_threshold_adjustment": rebalance_adj,
            "certification_ttl_adjustment_days": int(ttl_adj_days),
        }
