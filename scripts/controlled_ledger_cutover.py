#!/usr/bin/env python3
"""Controlled ledger cutover/archive for strict underlying attribution gating.

Purpose:
- Preserve full historical ledger in archive.
- Build a clean canonical ledger for live gating (strict audit should pass).
- Avoid breaking recovery by refusing unsafe cutovers by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
LIVE_DIR = PROJECT_ROOT / "data/options/live"
LEDGER_PATH = PROJECT_ROOT / "data/options/trade_ledger.parquet"
RUNTIME_PATH = LIVE_DIR / "options_runtime_state.json"
ARCHIVE_DIR = PROJECT_ROOT / "data/options/archive/ledger_cutovers"
REPORT_PATH = LIVE_DIR / "ledger_cutover_report.json"
HISTORY_PATH = ARCHIVE_DIR / "ledger_cutover_history.ndjson"

GENERIC_UNDERLYING_TOKENS = {
    "NSE",
    "NSE_EQ",
    "NSE_FO",
    "NSE_INDEX",
    "NFO",
    "BSE",
    "BSE_EQ",
    "BSE_FO",
    "UNKNOWN",
}
_TRADE_ID_TS_RE = re.compile(r"^POS_(\d{8})_(\d{6})_")


def _now_iso() -> str:
    return datetime.now().isoformat()


def _norm_underlying(value: Any) -> str:
    return str(value or "").strip().upper()


def _read_runtime_open_ids(runtime_path: Path) -> Set[str]:
    if not runtime_path.exists():
        return set()
    try:
        payload = json.loads(runtime_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return set()
        open_positions = payload.get("open_positions", [])
        if not isinstance(open_positions, list):
            return set()
        ids: Set[str] = set()
        for row in open_positions:
            if not isinstance(row, dict):
                continue
            pid = str(row.get("position_id") or "").strip()
            if pid:
                ids.add(pid)
        return ids
    except Exception:
        return set()


def _open_trade_ids(df: pd.DataFrame) -> Set[str]:
    if df.empty:
        return set()
    action = df["action"].astype(str).str.lower()
    open_ids = {
        str(x).strip()
        for x in df.loc[action == "open", "trade_id"].astype(str).tolist()
        if str(x).strip()
    }
    close_ids = {
        str(x).strip()
        for x in df.loc[action == "close", "trade_id"].astype(str).tolist()
        if str(x).strip()
    }
    return {x for x in open_ids if x not in close_ids}


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


def _sanitize_timestamps(df: pd.DataFrame) -> tuple[pd.DataFrame, Dict[str, int]]:
    if "timestamp" not in df.columns or df.empty:
        return df, {"null_before": 0, "inferred_from_trade_id": 0, "fallback_now": 0, "null_after": 0}

    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    null_before_mask = out["timestamp"].isna()
    null_before = int(null_before_mask.sum())

    inferred_count = 0
    if null_before > 0 and "trade_id" in out.columns:
        inferred = out.loc[null_before_mask, "trade_id"].apply(_infer_timestamp_from_trade_id)
        inferred_valid = inferred.notna()
        inferred_count = int(inferred_valid.sum())
        if inferred_count > 0:
            out.loc[null_before_mask, "timestamp"] = inferred.values
        null_before_mask = out["timestamp"].isna()

    fallback_count = int(null_before_mask.sum())
    if fallback_count > 0:
        out.loc[null_before_mask, "timestamp"] = pd.Timestamp.now()

    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    null_after = int(out["timestamp"].isna().sum())
    return out, {
        "null_before": null_before,
        "inferred_from_trade_id": inferred_count,
        "fallback_now": fallback_count,
        "null_after": null_after,
    }


def _audit_df(df: pd.DataFrame) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "total_rows": int(len(df)),
        "generic_underlying_rows": 0,
        "generic_underlying_ratio": 0.0,
        "by_underlying": {},
    }
    if df.empty:
        return report

    underlying = df.get("underlying", pd.Series(dtype=str)).astype(str).map(_norm_underlying)
    counts = underlying.value_counts(dropna=False)
    generic_mask = underlying.isin(GENERIC_UNDERLYING_TOKENS)
    generic_rows = int(generic_mask.sum())
    total_rows = int(len(df))
    report["generic_underlying_rows"] = generic_rows
    report["generic_underlying_ratio"] = float(generic_rows / total_rows) if total_rows else 0.0
    report["by_underlying"] = {str(k): int(v) for k, v in counts.items()}
    return report


def _build_cutover_plan(df: pd.DataFrame, runtime_open_ids: Set[str]) -> Dict[str, Any]:
    if df.empty:
        blocked_by: List[str] = []
        if runtime_open_ids:
            blocked_by.append("runtime_open_positions_not_represented_after_cutover")
        return {
            "can_execute_safely": len(blocked_by) == 0,
            "reason": "ledger_empty" if len(blocked_by) == 0 else "blocked",
            "before": _audit_df(df),
            "after": _audit_df(df),
            "contaminated_trade_ids": [],
            "runtime_open_ids": sorted(runtime_open_ids),
            "runtime_open_missing_after_cutover": sorted(runtime_open_ids),
            "blocked_by": blocked_by,
        }

    working = df.copy()
    working["underlying_norm"] = working["underlying"].astype(str).map(_norm_underlying)
    generic_mask = working["underlying_norm"].isin(GENERIC_UNDERLYING_TOKENS)

    contaminated_trade_ids = sorted(
        {
            str(x).strip()
            for x in working.loc[generic_mask, "trade_id"].astype(str).tolist()
            if str(x).strip()
        }
    )
    contaminated_set = set(contaminated_trade_ids)

    # Safety strategy: remove whole trade lifecycles if any row is contaminated.
    clean_df = working.loc[
        ~working["trade_id"].astype(str).isin(contaminated_set)
    ].drop(columns=["underlying_norm"], errors="ignore")

    before_open_only = _open_trade_ids(df)
    after_open_only = _open_trade_ids(clean_df)
    contaminated_open_only = sorted(before_open_only.intersection(contaminated_set))
    runtime_open_missing_after = sorted(runtime_open_ids - after_open_only)

    blocked_by: List[str] = []
    if contaminated_open_only:
        blocked_by.append("contaminated_open_trades_present")
    if runtime_open_missing_after:
        blocked_by.append("runtime_open_positions_not_represented_after_cutover")

    plan = {
        "can_execute_safely": len(blocked_by) == 0,
        "reason": "ok" if len(blocked_by) == 0 else "blocked",
        "before": _audit_df(df),
        "after": _audit_df(clean_df),
        "rows_removed": int(len(df) - len(clean_df)),
        "trade_ids_removed": int(len(contaminated_trade_ids)),
        "contaminated_trade_ids": contaminated_trade_ids,
        "contaminated_open_trade_ids": contaminated_open_only,
        "runtime_open_ids": sorted(runtime_open_ids),
        "runtime_open_missing_after_cutover": runtime_open_missing_after,
        "open_trade_ids_before": sorted(before_open_only),
        "open_trade_ids_after": sorted(after_open_only),
        "blocked_by": blocked_by,
    }
    return plan


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _fsync_parent_dir(path: Path) -> None:
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
    except Exception:
        return
    try:
        os.fsync(dir_fd)
    except Exception:
        pass
    finally:
        os.close(dir_fd)


def _write_parquet_atomic(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    try:
        with open(tmp, "rb") as handle:
            os.fsync(handle.fileno())
    except Exception:
        pass
    tmp.replace(path)
    _fsync_parent_dir(path)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _append_ndjson(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _archive_artifacts(
    original_df: pd.DataFrame,
    contaminated_df: pd.DataFrame,
    archive_dir: Path,
    cutover_id: str,
) -> Dict[str, str]:
    archive_dir.mkdir(parents=True, exist_ok=True)
    full_archive = archive_dir / f"trade_ledger_pre_cutover_{cutover_id}.parquet"
    contaminated_archive = archive_dir / f"trade_ledger_removed_rows_{cutover_id}.parquet"
    _write_parquet_atomic(full_archive, original_df)
    if not contaminated_df.empty:
        _write_parquet_atomic(contaminated_archive, contaminated_df)
    return {
        "full_archive_path": str(full_archive),
        "full_archive_sha256": _sha256(full_archive),
        "contaminated_rows_archive_path": str(contaminated_archive) if not contaminated_df.empty else None,
        "contaminated_rows_archive_sha256": _sha256(contaminated_archive) if not contaminated_df.empty else None,
    }


def execute_cutover(args: argparse.Namespace) -> int:
    from src.options.state_io import ProcessLock
    from src.options.state_recovery import StateRecoveryManager

    report: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "mode": "execute" if args.execute else "dry_run",
        "ledger_path": str(args.ledger_path),
        "archive_dir": str(args.archive_dir),
        "strict_target": True,
        "status": "started",
    }

    if not args.ledger_path.exists():
        report["status"] = "failed"
        report["error"] = f"ledger_missing:{args.ledger_path}"
        _write_json(args.report_path, report)
        print(json.dumps(report, indent=2))
        return 1

    lock = None
    if args.execute or args.require_lock_for_dry_run:
        lock = ProcessLock(args.lock_path)
        if not lock.acquire(timeout=float(args.lock_timeout_seconds)):
            report["status"] = "failed"
            report["error"] = "engine_lock_unavailable"
            _write_json(args.report_path, report)
            print(json.dumps(report, indent=2))
            return 2

    try:
        df = pd.read_parquet(args.ledger_path)
        runtime_open_ids = _read_runtime_open_ids(args.runtime_path)
        plan = _build_cutover_plan(df, runtime_open_ids)
        report["plan"] = plan
        report["precheck_strict_pass"] = int(plan.get("after", {}).get("generic_underlying_rows", 0)) == 0

        # Precondition blockers (enforced only on execute).
        blockers = list(plan.get("blocked_by", []))
        if not args.execute:
            report["status"] = "dry_run_complete"
            report["would_block_on_execute"] = blockers
            _write_json(args.report_path, report)
            print(json.dumps(report, indent=2))
            return 0

        if "contaminated_open_trades_present" in blockers and not args.allow_contaminated_open_trades:
            report["status"] = "blocked"
            report["error"] = "contaminated_open_trades_present"
            _write_json(args.report_path, report)
            print(json.dumps(report, indent=2))
            return 3
        runtime_mismatch = "runtime_open_positions_not_represented_after_cutover" in blockers
        if runtime_mismatch and not args.allow_runtime_open_mismatch and not args.rebuild_runtime:
            report["status"] = "blocked"
            report["error"] = "runtime_open_positions_not_represented_after_cutover"
            report["hint"] = "rerun with --rebuild-runtime or --allow-runtime-open-mismatch"
            _write_json(args.report_path, report)
            print(json.dumps(report, indent=2))
            return 4

        cutover_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        contaminated_trade_ids = set(plan.get("contaminated_trade_ids", []))
        contaminated_df = df.loc[df["trade_id"].astype(str).isin(contaminated_trade_ids)].copy()
        clean_df = df.loc[~df["trade_id"].astype(str).isin(contaminated_trade_ids)].copy()
        clean_df, ts_fix = _sanitize_timestamps(clean_df)
        report["timestamp_sanitation"] = ts_fix

        archive_paths = _archive_artifacts(
            original_df=df,
            contaminated_df=contaminated_df,
            archive_dir=args.archive_dir,
            cutover_id=cutover_id,
        )
        report["cutover_id"] = cutover_id
        report["archives"] = archive_paths

        # Write canonical clean ledger atomically via temp + replace.
        pre_cutover_sha = _sha256(args.ledger_path)
        _write_parquet_atomic(args.ledger_path, clean_df)
        post_cutover_sha = _sha256(args.ledger_path)

        after_df = pd.read_parquet(args.ledger_path)
        after_audit = _audit_df(after_df)
        report["post_cutover_audit"] = after_audit
        report["strict_pass"] = int(after_audit.get("generic_underlying_rows", 0)) == 0
        report["ledger_checksums"] = {
            "before_cutover": pre_cutover_sha,
            "after_cutover": post_cutover_sha,
        }

        if not report["strict_pass"]:
            report["status"] = "failed"
            report["error"] = "strict_audit_failed_after_cutover"
            _write_json(args.report_path, report)
            print(json.dumps(report, indent=2))
            return 5

        if args.rebuild_runtime:
            recovery = StateRecoveryManager(args.runtime_path.parent)
            base_capital = 100000.0
            try:
                if args.runtime_path.exists():
                    runtime_payload = json.loads(args.runtime_path.read_text(encoding="utf-8"))
                    if isinstance(runtime_payload, dict):
                        base_capital = float(runtime_payload.get("base_capital", base_capital) or base_capital)
            except Exception:
                pass
            recovery_report = recovery.rebuild_from_ledger(
                recovery_mode=False,
                base_capital=base_capital,
                portfolio_risk_cap_pct=float(args.portfolio_risk_cap_pct),
            )
            report["recovery_report"] = recovery_report

        report["status"] = "completed"
        report["completed_at"] = _now_iso()
        _write_json(args.report_path, report)
        _append_ndjson(HISTORY_PATH, report)
        print(json.dumps(report, indent=2))
        return 0
    finally:
        if lock is not None:
            lock.release()


def rollback_from_archive(args: argparse.Namespace) -> int:
    from src.options.state_io import ProcessLock

    report: Dict[str, Any] = {
        "timestamp": _now_iso(),
        "mode": "rollback",
        "status": "started",
        "archive_path": str(args.rollback_from),
    }

    if not args.rollback_from.exists():
        report["status"] = "failed"
        report["error"] = f"archive_missing:{args.rollback_from}"
        _write_json(args.report_path, report)
        print(json.dumps(report, indent=2))
        return 1

    lock = ProcessLock(args.lock_path)
    if not lock.acquire(timeout=float(args.lock_timeout_seconds)):
        report["status"] = "failed"
        report["error"] = "engine_lock_unavailable"
        _write_json(args.report_path, report)
        print(json.dumps(report, indent=2))
        return 2

    try:
        archived = pd.read_parquet(args.rollback_from)
        pre_rollback_sha = _sha256(args.ledger_path)
        _write_parquet_atomic(args.ledger_path, archived)
        post_rollback_sha = _sha256(args.ledger_path)
        report["status"] = "completed"
        report["rows_restored"] = int(len(archived))
        report["ledger_checksums"] = {
            "before_rollback": pre_rollback_sha,
            "after_rollback": post_rollback_sha,
            "archive_source": _sha256(args.rollback_from),
        }
        report["completed_at"] = _now_iso()
        _write_json(args.report_path, report)
        _append_ndjson(HISTORY_PATH, report)
        print(json.dumps(report, indent=2))
        return 0
    finally:
        lock.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Controlled ledger cutover/archive for strict gating")
    parser.add_argument("--ledger-path", type=Path, default=LEDGER_PATH)
    parser.add_argument("--runtime-path", type=Path, default=RUNTIME_PATH)
    parser.add_argument("--archive-dir", type=Path, default=ARCHIVE_DIR)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH)
    parser.add_argument("--lock-path", type=Path, default=LIVE_DIR / "options_engine.lock")
    parser.add_argument("--lock-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--portfolio-risk-cap-pct", type=float, default=0.10)

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply cutover. Default is dry-run preview only.",
    )
    parser.add_argument(
        "--require-lock-for-dry-run",
        action="store_true",
        help="Acquire options engine lock even for read-only dry-runs.",
    )
    parser.add_argument(
        "--rebuild-runtime",
        action="store_true",
        help="Rebuild runtime from cutover ledger after success.",
    )
    parser.add_argument(
        "--allow-contaminated-open-trades",
        action="store_true",
        help="Allow cutover even if contaminated trade IDs are still open.",
    )
    parser.add_argument(
        "--allow-runtime-open-mismatch",
        action="store_true",
        help="Allow cutover even if runtime open positions are not represented in post-cutover ledger.",
    )
    parser.add_argument(
        "--rollback-from",
        type=Path,
        default=None,
        help="Rollback canonical ledger from a previous archive parquet path.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.rollback_from:
        return rollback_from_archive(args)
    return execute_cutover(args)


if __name__ == "__main__":
    raise SystemExit(main())
