"""
State recovery and reconciliation for options runtime persistence.

Rebuilds canonical runtime state from immutable trade ledger entries when
runtime state is missing/corrupted or WAL indicates interrupted writes.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from src.options.runtime_guard import write_runtime_signature, verify_runtime_signature
from src.options.state_io import StateIOManager

logger = logging.getLogger(__name__)

_TRADE_ID_TS_RE = re.compile(r"^POS_(\d{8})_(\d{6})_")


REQUIRED_LEDGER_COLUMNS = {
    "trade_id",
    "timestamp",
    "action",
    "strategy_type",
    "regime_at_entry",
    "underlying",
    "expiry",
    "legs",
    "entry_credit_debit",
    "net_pnl",
}

REQUIRED_RUNTIME_FIELDS = {
    "schema_version",
    "continuity_mode",
    "base_capital",
    "realized_net_pnl",
    "unrealized_pnl",
    "net_equity",
    "week_start_equity",
    "risk_cap_value",
    "risk_remaining",
    "last_reconciled_at",
    "open_positions",
}


class StateRecoveryManager:
    """Manages recovery and reconciliation from immutable ledger records."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.ledger_path = base_path.parent / "trade_ledger.parquet"
        self.runtime_path = base_path / "options_runtime_state.json"
        self.recovery_report_path = base_path / "state_recovery_report.json"
        self.state_io = StateIOManager(base_path)

    def check_state_integrity(self) -> Dict[str, Any]:
        """Validate readability and minimum schema of runtime + ledger files."""
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "files_checked": {},
            "issues_found": [],
            "overall_status": "healthy",
        }

        # Runtime JSON
        if self.runtime_path.exists():
            try:
                payload = json.loads(self.runtime_path.read_text())
                if not isinstance(payload, dict):
                    raise ValueError("runtime payload must be object")
                missing_runtime_fields = sorted(
                    REQUIRED_RUNTIME_FIELDS - set(str(k) for k in payload.keys())
                )
                signature_report = verify_runtime_signature(self.runtime_path)
                report["files_checked"]["runtime_state"] = {
                    "exists": True,
                    "readable": True,
                    "schema_version": payload.get("schema_version"),
                    "timestamp": payload.get("timestamp"),
                    "missing_required_fields": missing_runtime_fields,
                    "signature": signature_report,
                }
                if missing_runtime_fields:
                    report["issues_found"].append(
                        f"runtime_state_missing_fields:{','.join(missing_runtime_fields)}"
                    )
                signature_status = str(signature_report.get("status", "")).lower()
                if signature_status == "mismatch":
                    report["issues_found"].append("runtime_signature_mismatch")
                elif signature_status in {"signature_error"}:
                    report["issues_found"].append("runtime_signature_error")
                elif signature_status in {"signature_missing"}:
                    report["issues_found"].append("runtime_signature_missing")
            except Exception as exc:
                report["files_checked"]["runtime_state"] = {
                    "exists": True,
                    "readable": False,
                    "error": str(exc),
                }
                report["issues_found"].append(f"runtime_state_corrupted:{exc}")
        else:
            report["files_checked"]["runtime_state"] = {"exists": False}
            report["issues_found"].append("runtime_state_missing")

        # Ledger parquet
        if self.ledger_path.exists():
            try:
                ledger = pd.read_parquet(self.ledger_path)
                cols = set(str(c) for c in ledger.columns)
                missing = sorted(REQUIRED_LEDGER_COLUMNS - cols)
                report["files_checked"]["trade_ledger"] = {
                    "exists": True,
                    "readable": True,
                    "row_count": int(len(ledger)),
                    "columns": sorted(cols),
                    "missing_required_columns": missing,
                }
                if missing:
                    report["issues_found"].append(
                        f"ledger_missing_columns:{','.join(missing)}"
                    )
            except Exception as exc:
                report["files_checked"]["trade_ledger"] = {
                    "exists": True,
                    "readable": False,
                    "error": str(exc),
                }
                report["issues_found"].append(f"trade_ledger_corrupted:{exc}")
        else:
            report["files_checked"]["trade_ledger"] = {"exists": False}
            report["issues_found"].append("trade_ledger_missing")

        if report["issues_found"]:
            severe = any(
                (
                    "corrupted" in issue
                    or "missing_columns" in issue
                    or "runtime_signature_mismatch" in issue
                    or "runtime_signature_error" in issue
                )
                for issue in report["issues_found"]
            )
            report["overall_status"] = "corrupted" if severe else "incomplete"

        return report

    def rebuild_from_ledger(
        self,
        recovery_mode: bool = False,
        base_capital: float = 100000.0,
        portfolio_risk_cap_pct: float = 0.10,
    ) -> Dict[str, Any]:
        """
        Rebuild runtime state from immutable ledger.

        Runtime equation:
            net_equity = base_capital + realized_net_pnl + unrealized_pnl
        """
        started_at = datetime.now()
        report: Dict[str, Any] = {
            "timestamp": started_at.isoformat(),
            "recovery_mode": bool(recovery_mode),
            "source": str(self.ledger_path),
            "status": "started",
            "errors": [],
            "warnings": [],
            "positions_rebuilt": 0,
            "closed_trades": 0,
            "realized_net_pnl": 0.0,
            "runtime_state_created": False,
        }

        try:
            if not self.ledger_path.exists():
                report["warnings"].append(f"ledger_missing:{self.ledger_path}")
                runtime_state = self._empty_runtime_state(
                    base_capital=base_capital,
                    recovery_mode=recovery_mode,
                    portfolio_risk_cap_pct=portfolio_risk_cap_pct,
                )
                self._write_runtime(runtime_state)
                report.update(
                    {
                        "status": "completed",
                        "runtime_state_created": True,
                        "closed_trades": 0,
                        "positions_rebuilt": 0,
                        "realized_net_pnl": 0.0,
                    }
                )
                self._write_report(report)
                return report

            ledger = pd.read_parquet(self.ledger_path)
            cols = set(str(c) for c in ledger.columns)
            missing = sorted(REQUIRED_LEDGER_COLUMNS - cols)
            if missing:
                raise ValueError(f"Ledger missing required columns: {missing}")

            if ledger.empty:
                runtime_state = self._empty_runtime_state(
                    base_capital=base_capital,
                    recovery_mode=recovery_mode,
                    portfolio_risk_cap_pct=portfolio_risk_cap_pct,
                )
                self._write_runtime(runtime_state)
                report.update(
                    {
                        "status": "completed",
                        "runtime_state_created": True,
                        "closed_trades": 0,
                        "positions_rebuilt": 0,
                        "realized_net_pnl": 0.0,
                    }
                )
                self._write_report(report)
                return report

            ledger = ledger.copy()
            ledger["timestamp"] = pd.to_datetime(ledger["timestamp"], errors="coerce")
            null_ts_mask = ledger["timestamp"].isna()
            null_ts_count = int(null_ts_mask.sum())
            inferred_ts_count = 0
            if null_ts_count > 0:
                inferred = ledger.loc[null_ts_mask, "trade_id"].apply(self._infer_timestamp_from_trade_id)
                inferred_valid = inferred.notna()
                inferred_ts_count = int(inferred_valid.sum())
                if inferred_ts_count > 0:
                    ledger.loc[null_ts_mask, "timestamp"] = inferred.values
                null_ts_mask = ledger["timestamp"].isna()

            unresolved_null_ts = int(null_ts_mask.sum())
            if unresolved_null_ts > 0:
                fallback_ts = pd.Timestamp.now()
                ledger.loc[null_ts_mask, "timestamp"] = fallback_ts
                report["warnings"].append(
                    f"timestamp_fallback_applied:{unresolved_null_ts}"
                )

            if null_ts_count > 0:
                report["warnings"].append(
                    f"timestamp_missing_rows:{null_ts_count}"
                )
            if inferred_ts_count > 0:
                report["warnings"].append(
                    f"timestamp_inferred_from_trade_id:{inferred_ts_count}"
                )

            ledger = ledger.sort_values("timestamp")

            open_ids = self._open_trade_ids(ledger)
            open_positions = self._rebuild_open_positions(ledger, open_ids)
            realized_net_pnl = float(
                pd.to_numeric(
                    ledger.loc[ledger["action"].astype(str).str.lower() == "close", "net_pnl"],
                    errors="coerce",
                ).fillna(0.0).sum()
            )

            estimated_open_risk = float(
                sum(abs(float(p.get("max_loss", 0.0) or 0.0)) for p in open_positions)
            )
            unrealized_pnl = 0.0
            net_equity = float(base_capital + realized_net_pnl + unrealized_pnl)
            risk_cap_value = float(max(0.0, net_equity * float(portfolio_risk_cap_pct)))
            risk_remaining = float(max(0.0, risk_cap_value - estimated_open_risk))

            runtime_state = {
                "schema_version": "2.1.0",
                "timestamp": datetime.now().isoformat(),
                "continuity_mode": True,
                "recovery_mode": bool(recovery_mode),
                "base_capital": float(base_capital),
                "portfolio_risk_cap_pct": float(portfolio_risk_cap_pct),
                "realized_net_pnl": float(realized_net_pnl),
                "unrealized_pnl": float(unrealized_pnl),
                "net_equity": float(net_equity),
                "week_start_equity": float(net_equity),
                "week_anchor_date": datetime.now().date().isoformat(),
                "risk_cap_value": float(risk_cap_value),
                "risk_remaining": float(risk_remaining),
                "last_reconciled_at": datetime.now().isoformat(),
                "current_mode": "recovery_mode" if recovery_mode else "normal_operation",
                "mode_constraints": {},
                "block_new_risk": bool(recovery_mode),
                "open_positions": open_positions,
                "closed_positions": [],
                "closed_positions_count": int((ledger["action"].astype(str).str.lower() == "close").sum()),
                "total_ledger_entries": int(len(ledger)),
                "cumulative_net_pnl": float(realized_net_pnl),
            }

            self._write_runtime(runtime_state)

            report.update(
                {
                    "status": "completed",
                    "runtime_state_created": True,
                    "positions_rebuilt": int(len(open_positions)),
                    "closed_trades": int(runtime_state["closed_positions_count"]),
                    "realized_net_pnl": float(realized_net_pnl),
                }
            )

        except Exception as exc:
            report["status"] = "failed"
            report["errors"].append(str(exc))
            logger.error("State rebuild failed: %s", exc, exc_info=True)

        self._write_report(report)
        return report

    def handle_interrupted_operations(
        self, interrupted_ops: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Summarize interrupted WAL operations and validate touched files."""
        actions: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "interrupted_operations": int(len(interrupted_ops or [])),
            "actions_taken": [],
            "manual_intervention_required": [],
        }

        for op in interrupted_ops or []:
            op_id = str(op.get("op_id") or "unknown")
            target_path = Path(str(op.get("target_path") or ""))
            if not str(target_path):
                actions["manual_intervention_required"].append(
                    {
                        "op_id": op_id,
                        "issue": "missing_target_path",
                        "recommendation": "run_full_reconciliation",
                    }
                )
                continue

            if not target_path.exists():
                actions["actions_taken"].append(
                    f"missing_target_marked_for_rebuild:{target_path}"
                )
                continue

            try:
                if target_path.suffix == ".json":
                    json.loads(target_path.read_text())
                elif target_path.suffix == ".parquet":
                    pd.read_parquet(target_path)
                actions["actions_taken"].append(f"validated_target:{target_path}")
            except Exception as exc:
                actions["manual_intervention_required"].append(
                    {
                        "op_id": op_id,
                        "target_path": str(target_path),
                        "issue": f"target_validation_failed:{exc}",
                        "recommendation": "archive_corrupt_file_then_rebuild",
                    }
                )

        return actions

    def _empty_runtime_state(
        self,
        base_capital: float,
        recovery_mode: bool,
        portfolio_risk_cap_pct: float,
    ) -> Dict[str, Any]:
        net_equity = float(base_capital)
        risk_cap_value = float(max(0.0, net_equity * float(portfolio_risk_cap_pct)))
        return {
            "schema_version": "2.1.0",
            "timestamp": datetime.now().isoformat(),
            "continuity_mode": True,
            "recovery_mode": bool(recovery_mode),
            "base_capital": float(base_capital),
            "portfolio_risk_cap_pct": float(portfolio_risk_cap_pct),
            "realized_net_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "net_equity": net_equity,
            "week_start_equity": net_equity,
            "week_anchor_date": datetime.now().date().isoformat(),
            "risk_cap_value": risk_cap_value,
            "risk_remaining": risk_cap_value,
            "last_reconciled_at": datetime.now().isoformat(),
            "current_mode": "recovery_mode" if recovery_mode else "normal_operation",
            "mode_constraints": {},
            "block_new_risk": bool(recovery_mode),
            "open_positions": [],
            "closed_positions": [],
            "closed_positions_count": 0,
            "total_ledger_entries": 0,
            "cumulative_net_pnl": 0.0,
        }

    @staticmethod
    def _infer_timestamp_from_trade_id(trade_id: Any) -> pd.Timestamp:
        text = str(trade_id or "").strip().upper()
        match = _TRADE_ID_TS_RE.match(text)
        if not match:
            return pd.NaT
        date_token = str(match.group(1))
        time_token = str(match.group(2))
        try:
            return pd.to_datetime(
                f"{date_token}{time_token}",
                format="%Y%m%d%H%M%S",
                errors="coerce",
            )
        except Exception:
            return pd.NaT

    @staticmethod
    def _open_trade_ids(ledger: pd.DataFrame) -> List[str]:
        action = ledger["action"].astype(str).str.lower()
        open_ids = {
            str(tid).strip()
            for tid in ledger.loc[action == "open", "trade_id"].tolist()
            if str(tid).strip() and str(tid).strip().lower() != "nan"
        }
        close_ids = {
            str(tid).strip()
            for tid in ledger.loc[action == "close", "trade_id"].tolist()
            if str(tid).strip() and str(tid).strip().lower() != "nan"
        }
        return sorted(tid for tid in open_ids if tid not in close_ids)

    def _rebuild_open_positions(
        self, ledger: pd.DataFrame, open_ids: List[str]
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not open_ids:
            return rows

        action = ledger["action"].astype(str).str.lower()
        open_entries = ledger.loc[action == "open"].copy()

        for trade_id in open_ids:
            group = open_entries.loc[open_entries["trade_id"].astype(str) == str(trade_id)]
            if group.empty:
                continue
            last = group.iloc[-1]

            legs = self._parse_legs(last.get("legs"))
            underlying = str(last.get("underlying") or "").strip().upper() or "UNKNOWN"
            entry_credit = float(last.get("entry_credit_debit") or 0.0)
            max_loss_raw = pd.to_numeric(last.get("max_loss"), errors="coerce")
            if pd.isna(max_loss_raw):
                max_loss_est = float(max(1.0, abs(entry_credit)))
            else:
                max_loss_est = float(max(1.0, abs(float(max_loss_raw))))
            max_profit_raw = pd.to_numeric(last.get("max_profit"), errors="coerce")
            max_profit_est = 0.0 if pd.isna(max_profit_raw) else float(max(0.0, float(max_profit_raw)))
            entry_ts = pd.to_datetime(last.get("timestamp"), errors="coerce")
            expiry_ts = pd.to_datetime(last.get("expiry"), errors="coerce")
            if pd.isna(entry_ts):
                entry_ts = pd.Timestamp.utcnow()
            if pd.isna(expiry_ts):
                expiry_ts = entry_ts

            row = {
                "position_id": str(trade_id),
                "strategy_type": str(last.get("strategy_type") or "unknown"),
                "underlying": underlying,
                "regime_at_entry": str(last.get("regime_at_entry") or "transition"),
                "legs": legs,
                "entry_time": entry_ts.to_pydatetime().isoformat(),
                "expiry": expiry_ts.date().isoformat(),
                "max_loss": max_loss_est,
                "max_profit": max_profit_est,
                "entry_credit_debit": entry_credit,
                "current_value": entry_credit,
                "unrealized_pnl": 0.0,
                "realized_pnl": None,
                "days_held": 0,
                "greeks": None,
                "entry_greeks": None,
                "exit_time": None,
                "exit_reason": None,
            }
            rows.append(row)

        return rows

    @staticmethod
    def _parse_legs(raw_legs: Any) -> List[Dict[str, Any]]:
        if raw_legs is None:
            return []

        legs_obj: Any = raw_legs
        if isinstance(raw_legs, str):
            try:
                legs_obj = json.loads(raw_legs)
            except Exception:
                return []

        if not isinstance(legs_obj, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for leg in legs_obj:
            if not isinstance(leg, dict):
                continue
            normalized.append(
                {
                    "symbol": str(leg.get("symbol") or ""),
                    "strike": float(leg.get("strike") or 0.0),
                    "option_type": str(leg.get("option_type") or ""),
                    "action": str(leg.get("action") or ""),
                    "quantity": int(leg.get("quantity") or 0),
                    "entry_premium": float(leg.get("entry_premium") or 0.0),
                    "current_premium": float(leg.get("current_premium") or 0.0),
                    "entry_iv": float(leg.get("entry_iv") or 0.0),
                    "current_iv": float(leg.get("current_iv") or 0.0),
                    "delta": float(leg.get("delta") or 0.0),
                    "gamma": float(leg.get("gamma") or 0.0),
                    "theta": float(leg.get("theta") or 0.0),
                    "vega": float(leg.get("vega") or 0.0),
                }
            )
        return normalized

    def _write_runtime(self, payload: Dict[str, Any]) -> None:
        if self.state_io.write_runtime_state(payload):
            return
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.runtime_path.with_suffix(f"{self.runtime_path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(self.runtime_path)
        try:
            dir_fd = os.open(str(self.runtime_path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass
        write_runtime_signature(self.runtime_path)

    def _write_report(self, payload: Dict[str, Any]) -> None:
        self.recovery_report_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.recovery_report_path.with_suffix(f"{self.recovery_report_path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(self.recovery_report_path)
        try:
            dir_fd = os.open(str(self.recovery_report_path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass
