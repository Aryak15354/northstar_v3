"""SQLite event store for PRS authoritative runtime truth."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .contracts import CertificationSnapshot, ExecutionEvent
from .hash_utils import canonical_json_dumps


class RuntimeEventStore:
    def __init__(
        self,
        db_path: str,
        *,
        read_only: bool = False,
        writer_name: str = "runtime_writer",
    ):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self.read_only = bool(read_only)
        self.writer_name = str(writer_name or "runtime_writer")
        self._writer_lock_handle: Any = None
        self._writer_lock_path = self.db_path.with_suffix(f"{self.db_path.suffix}.writer.lock")

        if self.read_only:
            uri = f"file:{self.db_path}?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._harden_db_permissions()
        self._initialize_schema()
        self._ensure_schema_compat()
        self._bootstrap_runtime_control()
        self._acquire_writer_lock()

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(timezone.utc)

    @classmethod
    def _utcnow_iso(cls) -> str:
        return cls._utcnow().isoformat()

    @staticmethod
    def _coerce_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _parse_iso_utc(cls, raw: Any) -> datetime:
        dt = datetime.fromisoformat(str(raw))
        return cls._coerce_utc(dt)

    def _harden_db_permissions(self) -> None:
        """
        Harden DB file permissions to owner read/write only.

        This does not prevent same-user writes from rogue code, but materially
        reduces accidental cross-process mutation surface and supports PRS-only
        operating discipline.
        """
        try:
            if self.db_path.parent.exists():
                os.chmod(self.db_path.parent, 0o700)
            # Ensure file exists before chmod.
            if not self.db_path.exists():
                self.db_path.touch()
            os.chmod(self.db_path, 0o600)
        except Exception:
            # Permission hardening is best effort only.
            pass

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
        self._release_writer_lock()

    def _acquire_writer_lock(self) -> None:
        if self.read_only:
            return
        try:
            import fcntl  # type: ignore
        except Exception:
            # Non-POSIX platforms: best-effort only.
            return

        self._writer_lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self._writer_lock_path, "a+", encoding="utf-8")
        try:
            os.chmod(self._writer_lock_path, 0o600)
        except Exception:
            pass
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except Exception as exc:
            handle.close()
            raise RuntimeError(
                f"runtime_write_lock_unavailable db={self.db_path} writer={self.writer_name}"
            ) from exc
        self._writer_lock_handle = handle

        now = self._utcnow_iso()
        owner_payload = canonical_json_dumps(
            {
                "writer_name": self.writer_name,
                "pid": os.getpid(),
                "lock_file": str(self._writer_lock_path),
                "acquired_at": now,
            }
        )
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_control (key, value_json, updated_at)
                VALUES ('mutation_owner', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (owner_payload, now),
            )

    def _release_writer_lock(self) -> None:
        handle = self._writer_lock_handle
        if handle is None:
            return
        try:
            import fcntl  # type: ignore

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            handle.close()
        except Exception:
            pass
        self._writer_lock_handle = None

    def _require_write_authority(self) -> None:
        if self.read_only:
            raise PermissionError(
                f"runtime_store_read_only db={self.db_path} writer={self.writer_name}"
            )

    def _initialize_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA synchronous=NORMAL;

                CREATE TABLE IF NOT EXISTS certification_snapshots (
                    snapshot_hash TEXT PRIMARY KEY,
                    snapshot_json TEXT NOT NULL,
                    model_hash TEXT NOT NULL,
                    param_hash TEXT NOT NULL,
                    feature_hash TEXT NOT NULL,
                    data_revision_hash TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    drift_guard_version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    valid_until TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS proposal_inbox (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    denial_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS portfolio_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence_no INTEGER NOT NULL,
                    timestamp_utc TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    parent_event_id INTEGER,
                    trigger_reason_code TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    certification_snapshot_hash TEXT NOT NULL,
                    risk_override_flag INTEGER NOT NULL,
                    decision_mode TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    allocator_decision_id TEXT NOT NULL,
                    budget_decision_id TEXT NOT NULL,
                    liquidity_decision_id TEXT NOT NULL,
                    operator_id TEXT NOT NULL DEFAULT '',
                    runtime_scope TEXT NOT NULL DEFAULT 'live',
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_portfolio_events_proposal ON portfolio_events(proposal_id, sequence_no);
                CREATE INDEX IF NOT EXISTS idx_portfolio_events_type_time ON portfolio_events(event_type, timestamp_utc);

                CREATE TABLE IF NOT EXISTS execution_fills (
                    fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    proposal_id TEXT NOT NULL,
                    symbol TEXT,
                    side TEXT,
                    filled_qty REAL,
                    fill_price REAL,
                    fill_notional REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES portfolio_events(event_id)
                );

                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    state_hash TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_event ON portfolio_snapshots(event_id);

                CREATE TABLE IF NOT EXISTS portfolio_stress_matrix (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    scenario_id TEXT NOT NULL,
                    pnl_impact REAL NOT NULL,
                    risk_metric REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES portfolio_events(event_id)
                );

                CREATE TABLE IF NOT EXISTS position_lifecycle_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_key TEXT NOT NULL,
                    open_event_id INTEGER,
                    close_event_id INTEGER,
                    open_reason TEXT,
                    close_reason TEXT,
                    hold_days REAL,
                    max_adverse_excursion REAL,
                    max_favorable_excursion REAL,
                    realized_pnl REAL,
                    strategy_id TEXT,
                    signal_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_position_lifecycle_key ON position_lifecycle_table(position_key);

                CREATE TABLE IF NOT EXISTS truth_drift_incidents (
                    incident_id TEXT PRIMARY KEY,
                    timestamp_utc TEXT NOT NULL,
                    live_state_hash TEXT NOT NULL,
                    shadow_state_hash TEXT NOT NULL,
                    derived_view_hash TEXT NOT NULL,
                    breach_count INTEGER NOT NULL,
                    escalated_freeze INTEGER NOT NULL,
                    details_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runtime_control (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def _table_columns(self, table_name: str) -> set[str]:
        try:
            rows = self._conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        except Exception:
            return set()
        out: set[str] = set()
        for row in rows:
            try:
                out.add(str(row["name"]))
            except Exception:
                continue
        return out

    def _ensure_schema_compat(self) -> None:
        cols = self._table_columns("portfolio_events")
        with self._conn:
            if "operator_id" not in cols:
                self._conn.execute("ALTER TABLE portfolio_events ADD COLUMN operator_id TEXT NOT NULL DEFAULT ''")
            if "runtime_scope" not in cols:
                self._conn.execute(
                    "ALTER TABLE portfolio_events ADD COLUMN runtime_scope TEXT NOT NULL DEFAULT 'live'"
                )

    def _bootstrap_runtime_control(self) -> None:
        now = self._utcnow_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_control (key, value_json, updated_at)
                VALUES ('global_freeze', ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (
                    canonical_json_dumps(
                        {"is_frozen": False, "reason": "", "updated_by": "bootstrap"}
                    ),
                    now,
                ),
            )
            self._conn.execute(
                """
                INSERT INTO runtime_control (key, value_json, updated_at)
                VALUES ('runtime_state', ?, ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (
                    canonical_json_dumps(
                        {"state": "ACTIVE", "updated_by": "bootstrap", "updated_at": now}
                    ),
                    now,
                ),
            )

    def get_runtime_freeze_state(self) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT value_json FROM runtime_control WHERE key = 'global_freeze'"
        ).fetchone()
        if row is None:
            return {"is_frozen": False, "reason": "", "updated_by": ""}
        try:
            import json

            payload = json.loads(str(row["value_json"] or "{}"))
            if isinstance(payload, dict):
                return {
                    "is_frozen": bool(payload.get("is_frozen", False)),
                    "reason": str(payload.get("reason", "") or ""),
                    "updated_by": str(payload.get("updated_by", "") or ""),
                    "updated_at": str(payload.get("updated_at", "") or ""),
                }
        except Exception:
            pass
        return {"is_frozen": False, "reason": "", "updated_by": ""}

    def set_runtime_freeze_state(
        self, is_frozen: bool, reason: str, updated_by: str = "runtime"
    ) -> None:
        self._require_write_authority()
        now = self._utcnow_iso()
        payload = {
            "is_frozen": bool(is_frozen),
            "reason": str(reason or ""),
            "updated_by": str(updated_by or "runtime"),
            "updated_at": now,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_control (key, value_json, updated_at)
                VALUES ('global_freeze', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (canonical_json_dumps(payload), now),
            )

    def get_runtime_state(self) -> str:
        row = self._conn.execute(
            "SELECT value_json FROM runtime_control WHERE key = 'runtime_state'"
        ).fetchone()
        if row is None:
            return "ACTIVE"
        try:
            import json

            payload = json.loads(str(row["value_json"] or "{}"))
            return str(payload.get("state", "ACTIVE") or "ACTIVE").upper()
        except Exception:
            return "ACTIVE"

    def set_runtime_state(self, state: str, updated_by: str = "runtime") -> None:
        self._require_write_authority()
        now = self._utcnow_iso()
        payload = {
            "state": str(state or "ACTIVE").upper(),
            "updated_by": str(updated_by or "runtime"),
            "updated_at": now,
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_control (key, value_json, updated_at)
                VALUES ('runtime_state', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (canonical_json_dumps(payload), now),
            )

    def get_runtime_control_json(self, key: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT value_json FROM runtime_control WHERE key = ?",
            (str(key),),
        ).fetchone()
        if row is None:
            return dict(default or {})
        try:
            import json

            payload = json.loads(str(row["value_json"] or "{}"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return dict(default or {})

    def set_runtime_control_json(self, key: str, payload: Dict[str, Any]) -> None:
        self._require_write_authority()
        now = self._utcnow_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO runtime_control (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
                """,
                (str(key), canonical_json_dumps(dict(payload or {})), now),
            )

    @staticmethod
    def open_read_only_connection(db_path: str) -> sqlite3.Connection:
        """
        Read-only connection helper for dashboards and analytics consumers.
        """
        uri = f"file:{Path(db_path)}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def insert_certification_snapshot(self, snapshot: CertificationSnapshot) -> None:
        self._require_write_authority()
        payload = snapshot.to_dict()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO certification_snapshots (
                    snapshot_hash, snapshot_json, model_hash, param_hash, feature_hash,
                    data_revision_hash, config_hash, drift_guard_version, created_at, valid_until
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.snapshot_hash,
                    canonical_json_dumps(payload),
                    snapshot.model_hash,
                    snapshot.param_hash,
                    snapshot.feature_hash,
                    snapshot.data_revision_hash,
                    snapshot.config_hash,
                    snapshot.drift_guard_version,
                    snapshot.created_at.isoformat(),
                    snapshot.valid_until.isoformat(),
                ),
            )

    def get_certification_snapshot(self, snapshot_hash: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM certification_snapshots WHERE snapshot_hash = ?",
            (str(snapshot_hash),),
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def upsert_proposal(self, proposal_id: str, proposal_json: Dict[str, Any], status: str, denial_reason: str = "") -> None:
        self._require_write_authority()
        now = self._utcnow_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO proposal_inbox (proposal_id, proposal_json, status, denial_reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    proposal_json=excluded.proposal_json,
                    status=excluded.status,
                    denial_reason=excluded.denial_reason,
                    updated_at=excluded.updated_at
                """,
                (
                    str(proposal_id),
                    canonical_json_dumps(proposal_json),
                    str(status),
                    str(denial_reason or ""),
                    now,
                    now,
                ),
            )

    def update_proposal_status(self, proposal_id: str, status: str, denial_reason: str = "") -> None:
        self._require_write_authority()
        now = self._utcnow_iso()
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE proposal_inbox
                SET status = ?, denial_reason = ?, updated_at = ?
                WHERE proposal_id = ?
                """,
                (str(status), str(denial_reason or ""), now, str(proposal_id)),
            )

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            """
            SELECT proposal_json, status, denial_reason, created_at, updated_at
            FROM proposal_inbox
            WHERE proposal_id = ?
            """,
            (str(proposal_id),),
        ).fetchone()
        if row is None:
            return None
        try:
            import json

            proposal = json.loads(str(row["proposal_json"] or "{}"))
        except Exception:
            proposal = {}
        if not isinstance(proposal, dict):
            proposal = {}
        proposal["status"] = str(row["status"] or "")
        proposal["denial_reason"] = str(row["denial_reason"] or "")
        proposal["created_at"] = str(row["created_at"] or "")
        proposal["updated_at"] = str(row["updated_at"] or "")
        return proposal

    def latest_intent_approval(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            """
            SELECT event_id, payload_json, timestamp_utc
            FROM portfolio_events
            WHERE proposal_id = ? AND event_type = 'INTENT_APPROVED'
            ORDER BY event_id DESC
            LIMIT 1
            """,
            (str(proposal_id),),
        ).fetchone()
        if row is None:
            return None
        try:
            import json

            payload = json.loads(str(row["payload_json"] or "{}"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "event_id": int(row["event_id"] or 0),
            "payload": payload,
            "timestamp_utc": str(row["timestamp_utc"] or ""),
        }

    def _next_sequence_no(self, proposal_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(sequence_no), 0) AS mx FROM portfolio_events WHERE proposal_id = ?",
            (str(proposal_id),),
        ).fetchone()
        return int((row["mx"] if row else 0) or 0) + 1

    def append_event(self, event: ExecutionEvent) -> int:
        self._require_write_authority()
        with self._lock, self._conn:
            seq_no = int(event.sequence_no or self._next_sequence_no(event.proposal_id))
            cur = self._conn.execute(
                """
                INSERT INTO portfolio_events (
                    sequence_no, timestamp_utc, event_type, proposal_id, parent_event_id,
                    trigger_reason_code, strategy_id, signal_id, certification_snapshot_hash,
                    risk_override_flag, decision_mode, origin, allocator_decision_id,
                    budget_decision_id, liquidity_decision_id, operator_id, runtime_scope, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    seq_no,
                    event.timestamp_utc.isoformat(),
                    event.event_type.value,
                    event.proposal_id,
                    event.parent_event_id,
                    event.trigger_reason_code,
                    event.strategy_id,
                    event.signal_id,
                    event.certification_snapshot_hash,
                    int(bool(event.risk_override_flag)),
                    event.decision_mode.value,
                    event.origin.value,
                    event.allocator_decision_id,
                    event.budget_decision_id,
                    event.liquidity_decision_id,
                    str(event.operator_id or ""),
                    str(event.runtime_scope or "live"),
                    canonical_json_dumps(event.payload),
                ),
            )
            event_id = int(cur.lastrowid)
            self._maybe_insert_fill(event_id, event)
            self._update_position_lifecycle(event_id, event)
            return event_id

    def _maybe_insert_fill(self, event_id: int, event: ExecutionEvent) -> None:
        if event.event_type.value not in {"ORDER_PARTIAL", "ORDER_FILLED", "POSITION_ADJUSTED"}:
            return
        payload = dict(event.payload or {})
        qty = float(payload.get("filled_qty", payload.get("quantity", 0.0)) or 0.0)
        price = float(payload.get("fill_price", payload.get("price", 0.0)) or 0.0)
        if qty <= 0.0 or price <= 0.0:
            return
        self._conn.execute(
            """
            INSERT INTO execution_fills (
                event_id, proposal_id, symbol, side, filled_qty, fill_price, fill_notional, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event.proposal_id,
                str(payload.get("symbol", "") or ""),
                str(payload.get("side", "") or ""),
                qty,
                price,
                qty * price,
                self._utcnow_iso(),
            ),
        )

    def _update_position_lifecycle(self, event_id: int, event: ExecutionEvent) -> None:
        payload = dict(event.payload or {})
        action = str(payload.get("lifecycle_action", "") or "").strip().lower()
        if action not in {"open", "close"}:
            return
        key = str(payload.get("position_key", "") or "").strip()
        if not key:
            key = f"{event.strategy_id}:{event.signal_id}"
        now = self._utcnow_iso()

        if action == "open":
            existing = self._conn.execute(
                """
                SELECT id
                FROM position_lifecycle_table
                WHERE position_key = ? AND close_event_id IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (key,),
            ).fetchone()
            if existing is not None:
                self._conn.execute(
                    """
                    UPDATE position_lifecycle_table
                    SET updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        int(existing["id"]),
                    ),
                )
                return
            self._conn.execute(
                """
                INSERT INTO position_lifecycle_table (
                    position_key, open_event_id, close_event_id, open_reason, close_reason,
                    hold_days, max_adverse_excursion, max_favorable_excursion, realized_pnl,
                    strategy_id, signal_id, created_at, updated_at
                ) VALUES (?, ?, NULL, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?)
                """,
                (
                    key,
                    event_id,
                    event.trigger_reason_code,
                    event.strategy_id,
                    event.signal_id,
                    now,
                    now,
                ),
            )
            return

        row = self._conn.execute(
            """
            SELECT id, created_at
            FROM position_lifecycle_table
            WHERE position_key = ? AND close_event_id IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (key,),
        ).fetchone()
        if row is None:
            return

        created = self._parse_iso_utc(row["created_at"])
        hold_days = max(0.0, (self._utcnow() - created).total_seconds() / 86400.0)
        self._conn.execute(
            """
            UPDATE position_lifecycle_table
            SET close_event_id = ?, close_reason = ?, hold_days = ?,
                max_adverse_excursion = ?, max_favorable_excursion = ?,
                realized_pnl = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                event_id,
                event.trigger_reason_code,
                hold_days,
                float(payload.get("max_adverse_excursion", 0.0) or 0.0),
                float(payload.get("max_favorable_excursion", 0.0) or 0.0),
                float(payload.get("realized_pnl", 0.0) or 0.0),
                now,
                int(row["id"]),
            ),
        )

    def append_snapshot(self, event_id: int, snapshot: Dict[str, Any], state_hash: str) -> None:
        self._require_write_authority()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO portfolio_snapshots (event_id, state_hash, state_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (int(event_id), str(state_hash), canonical_json_dumps(snapshot), self._utcnow_iso()),
            )

    def latest_snapshot(self) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT event_id, state_hash, state_json, created_at FROM portfolio_snapshots ORDER BY snapshot_id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def append_stress_matrix(self, event_id: int, scenarios: List[Dict[str, Any]]) -> None:
        if not scenarios:
            return
        self._require_write_authority()
        now = self._utcnow_iso()
        with self._lock, self._conn:
            self._conn.executemany(
                """
                INSERT INTO portfolio_stress_matrix (event_id, scenario_id, pnl_impact, risk_metric, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        int(event_id),
                        str(s.get("scenario_id", "") or ""),
                        float(s.get("pnl_impact", 0.0) or 0.0),
                        float(s.get("risk_metric", 0.0) or 0.0),
                        canonical_json_dumps(dict(s.get("payload", {}) or {})),
                        now,
                    )
                    for s in scenarios
                ],
            )

    def append_truth_drift_incident(self, incident: Dict[str, Any]) -> None:
        self._require_write_authority()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO truth_drift_incidents (
                    incident_id, timestamp_utc, live_state_hash, shadow_state_hash,
                    derived_view_hash, breach_count, escalated_freeze, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(incident.get("incident_id", "")),
                    str(incident.get("timestamp_utc", self._utcnow_iso())),
                    str(incident.get("live_state_hash", "")),
                    str(incident.get("shadow_state_hash", "")),
                    str(incident.get("derived_view_hash", "")),
                    int(incident.get("breach_count", 0) or 0),
                    int(bool(incident.get("escalated_freeze", False))),
                    canonical_json_dumps(dict(incident.get("details", {}) or {})),
                ),
            )

    def list_events(self, since_event_id: int = 0, to_event_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if to_event_id is None:
            rows = self._conn.execute(
                "SELECT * FROM portfolio_events WHERE event_id > ? ORDER BY event_id ASC",
                (int(since_event_id),),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM portfolio_events
                WHERE event_id > ? AND event_id <= ?
                ORDER BY event_id ASC
                """,
                (int(since_event_id), int(to_event_id)),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_event_id(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(event_id), 0) AS mx FROM portfolio_events").fetchone()
        return int((row["mx"] if row else 0) or 0)

    def count_open_fills_since(self, start_ts_utc_iso: str) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM portfolio_events
            WHERE event_type = 'ORDER_FILLED'
              AND timestamp_utc >= ?
              AND json_extract(payload_json, '$.lifecycle_action') = 'open'
            """,
            (str(start_ts_utc_iso),),
        ).fetchone()
        return int((row["c"] if row else 0) or 0)
