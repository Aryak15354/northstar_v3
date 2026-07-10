"""Cadence-aware data refresh scheduler.

Reads config/refresh_cadence.yaml and, for a given day, runs only the data
sources that are *due* for their cadence tier (daily / weekly / monthly /
quarterly), records the last successful run per source in
data/runtime/refresh_state.json, performs post-run storage hygiene (e.g. RBI
raw-xlsx pruning), and runs the canonical rebuild once at the end iff any
triggering source actually refreshed.

Design notes:
- "Due" is decided by comparing a cadence period-key (e.g. the ISO week for
  weekly sources) against the last successful key in state -- so a source runs
  at most once per period regardless of how often the scheduler is invoked.
- The manually generated Upstox token is checked for freshness (mtime of
  .env.options). A stale token only skips sources flagged requires_upstox and
  prints a loud banner; everything else still runs (decision: keep non-Upstox
  data flowing on days you forget the token).
- Everything is idempotent and merge-friendly: the underlying fetchers already
  --resume / merge into existing local data, so re-running is safe.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "refresh_cadence.yaml"
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "runtime" / "refresh_state.json"
DEFAULT_HOLIDAYS_PATH = PROJECT_ROOT / "config" / "nse_holidays.csv"

logger = logging.getLogger("ingestion.refresh_scheduler")


def _period_key(cadence: str, day: datetime) -> str:
    """A string that is constant within one cadence period and changes across periods."""
    cadence = (cadence or "").strip().lower()
    if cadence == "daily":
        return day.strftime("%Y-%m-%d")
    if cadence == "weekly":
        iso = day.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if cadence == "monthly":
        return day.strftime("%Y-%m")
    if cadence == "quarterly":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
    # Unknown cadence -> treat as daily so it at least runs and is visible.
    return day.strftime("%Y-%m-%d")


def _load_holidays(path: Path = DEFAULT_HOLIDAYS_PATH) -> set:
    """Load NSE trading holidays (YYYY-MM-DD) from config/nse_holidays.csv."""
    out: set = set()
    if not path.exists():
        return out
    try:
        import csv

        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                raw = (row.get("date") or "").strip()
                if not raw:
                    continue
                try:
                    out.add(datetime.strptime(raw, "%Y-%m-%d").date())
                except ValueError:
                    continue
    except Exception:
        return out
    return out


class RefreshScheduler:
    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG_PATH,
        state_path: Path = DEFAULT_STATE_PATH,
        repo_root: Path = PROJECT_ROOT,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.state_path = Path(state_path)
        self.repo_root = Path(repo_root)
        self.log = log or logger
        self.config = self._load_config()
        self.state = self._load_state()
        self.holidays = _load_holidays(self.repo_root / "config" / "nse_holidays.csv")

    def _is_trading_day(self, day: datetime) -> bool:
        """Mon-Fri and not an NSE holiday (config/nse_holidays.csv)."""
        return day.weekday() < 5 and day.date() not in self.holidays

    # ---- config / state ----
    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"refresh cadence config not found: {self.config_path}")
        payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict) or "sources" not in payload:
            raise ValueError(f"invalid refresh cadence config: {self.config_path}")
        return payload

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"sources": {}}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("sources"), dict):
                return data
        except Exception:
            self.log.warning("refresh_state.json unreadable; starting fresh")
        return {"sources": {}}

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_name(f"{self.state_path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(self.state, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.state_path)

    # ---- upstox token freshness ----
    def upstox_token_status(self, now: Optional[datetime] = None) -> Tuple[bool, str]:
        now = now or datetime.now()
        env_rel = str(self.config.get("upstox_env_file", ".env.options"))
        max_age_h = float(self.config.get("upstox_token_max_age_hours", 20) or 20)
        env_path = self.repo_root / env_rel
        if not env_path.exists():
            return False, f"Upstox env file {env_rel} not found -- generate a token."
        age_h = (now - datetime.fromtimestamp(env_path.stat().st_mtime)).total_seconds() / 3600.0
        if age_h > max_age_h:
            return (
                False,
                f"Upstox token is STALE ({age_h:.1f}h old > {max_age_h:.0f}h). "
                f"Run: python3 scripts/refresh_upstox_token.py",
            )
        return True, f"Upstox token fresh ({age_h:.1f}h old)."

    # ---- due-ness ----
    def _source_state(self, name: str) -> Dict[str, Any]:
        return self.state["sources"].get(name, {})

    def is_due(self, source: Dict[str, Any], as_of: datetime) -> Tuple[bool, str]:
        name = source["name"]
        cadence = str(source.get("cadence", "daily")).lower()
        if bool(source.get("trading_day_only", False)) and not self._is_trading_day(as_of):
            return False, "not a trading day (weekend/NSE holiday)"
        want_key = _period_key(cadence, as_of)
        have_key = self._source_state(name).get("last_period_key")
        if have_key == want_key:
            return False, f"already refreshed for {cadence} period {want_key}"
        return True, f"due for {cadence} period {want_key}"

    # ---- gap-safe lookback ----
    def _gap_days(self, name: str, spec: Dict[str, Any], as_of: datetime) -> int:
        """Days of history a 'fetch last N days' source must cover so nothing is
        missed since its last successful run. Uses the last success date from
        state; on first run (no prior success) uses first_run_days so a long
        gap since the system last updated is still fully backfilled."""
        buffer_days = int(spec.get("buffer_days", 5))
        min_days = int(spec.get("min_days", 30))
        first_run_days = int(spec.get("first_run_days", 90))
        last_key = self._source_state(name).get("last_period_key")
        last_date = None
        if last_key:
            try:
                last_date = datetime.strptime(str(last_key)[:10], "%Y-%m-%d").date()
            except ValueError:
                last_date = None
        if last_date is None:
            return max(min_days, first_run_days)
        gap = (as_of.date() - last_date).days + buffer_days
        return max(min_days, gap)

    def _apply_gap_lookback(self, source: Dict[str, Any], as_of: datetime) -> List[List[str]]:
        """Return the source's commands with its gap_lookback flag set to a value
        that covers the whole gap since last success (see _gap_days)."""
        commands = [list(c) for c in source.get("commands", [])]
        spec = source.get("gap_lookback")
        if not spec:
            return commands
        flag = str(spec.get("flag", "")).strip()
        if not flag:
            return commands
        value = str(self._gap_days(source["name"], spec, as_of))
        for cmd in commands:
            if flag in cmd:
                cmd[cmd.index(flag) + 1] = value
            else:
                cmd.extend([flag, value])
        self.log.info("  gap-fill: %s %s (covers gap since last success)", flag, value)
        return commands

    # ---- execution ----
    def _run_commands(self, commands: List[List[str]], env: Dict[str, str]) -> Tuple[bool, str]:
        for cmd in commands:
            argv = [str(a) for a in cmd]
            self.log.info("  $ %s", " ".join(argv))
            try:
                proc = subprocess.run(argv, cwd=str(self.repo_root), env=env, timeout=6 * 3600)
            except subprocess.TimeoutExpired:
                return False, f"timeout: {' '.join(argv)}"
            except Exception as exc:  # noqa: BLE001 - report and continue to next source
                return False, f"error running {' '.join(argv)}: {exc}"
            if proc.returncode != 0:
                return False, f"exit {proc.returncode}: {' '.join(argv)}"
        return True, "ok"

    def _mark_success(self, name: str, cadence: str, as_of: datetime) -> None:
        prior = self.state["sources"].get(name, {})
        self.state["sources"][name] = {
            "last_period_key": _period_key(cadence, as_of),
            "last_success_utc": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": 0,
            # keep last error for post-mortems even after recovery
            "last_error": prior.get("last_error"),
            "last_failure_utc": prior.get("last_failure_utc"),
        }
        self._save_state()

    def _mark_failure(self, name: str, error: str) -> None:
        """Persist failures so a broken feed is visible in state, not just in a
        stdout report nobody reads. The 2026-07-06 audit found equity_prices
        failing for months with zero trace in refresh_state.json (finding M3)."""
        entry = self.state["sources"].setdefault(name, {})
        entry["consecutive_failures"] = int(entry.get("consecutive_failures", 0) or 0) + 1
        entry["last_error"] = str(error)[:500]
        entry["last_failure_utc"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    # ---- storage hygiene ----
    def _prune(self, key: str) -> None:
        if key == "rbi_macro":
            self._prune_rbi_macro()

    def _prune_rbi_macro(self) -> None:
        """Delete raw RBI .xlsx (and .xlsx.backup_*) after processing, and prune
        the accumulating versioned '<name>_vN.csv' snapshots.

        Safety: a versioned CSV is deleted only if the un-versioned base file
        exists; for any stem that has NO base, the highest-numbered version is
        retained so we never delete the only copy of a dataset."""
        raw = self.repo_root / "data" / "macro" / "raw"
        if not raw.exists():
            return
        removed = 0

        # 1. Raw Excel downloads (re-downloadable; already processed to parquet/csv).
        for p in list(raw.iterdir()):
            if p.is_file() and (p.name.endswith(".xlsx") or ".xlsx.backup" in p.name or p.name.endswith(".xls")):
                try:
                    p.unlink(); removed += 1
                except Exception as exc:  # noqa: BLE001
                    self.log.warning("could not prune %s: %s", p, exc)

        # 2. Versioned CSV snapshots '<stem>_vN.csv'.
        version_re = re.compile(r"^(?P<stem>.+)_v(?P<num>\d+)\.csv$")
        by_stem: Dict[str, List[Tuple[int, Path]]] = {}
        for p in raw.iterdir():
            if not p.is_file():
                continue
            m = version_re.match(p.name)
            if m:
                by_stem.setdefault(m.group("stem"), []).append((int(m.group("num")), p))
        for stem, versions in by_stem.items():
            base_exists = (raw / f"{stem}.csv").exists()
            versions.sort(key=lambda t: t[0])  # ascending version
            # If no base, keep the highest version; otherwise all versioned copies go.
            keep = None if base_exists else versions[-1][1]
            for _, path in versions:
                if path == keep:
                    continue
                try:
                    path.unlink(); removed += 1
                except Exception as exc:  # noqa: BLE001
                    self.log.warning("could not prune %s: %s", path, exc)

        if removed:
            self.log.info("  pruned %d raw RBI/macro files from data/macro/raw", removed)

    # ---- top-level run ----
    def run(
        self,
        as_of: Optional[datetime] = None,
        dry_run: bool = False,
        force: bool = False,
        only: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        as_of = as_of or datetime.now()
        base_env = dict(os.environ)
        report: Dict[str, Any] = {
            "as_of": as_of.isoformat(),
            "dry_run": dry_run,
            "ran": [],
            "skipped": [],
            "failed": [],
            "canonical_rebuilt": False,
        }

        token_fresh, token_msg = self.upstox_token_status(as_of)
        report["upstox_token_fresh"] = token_fresh
        report["upstox_token_message"] = token_msg
        if not token_fresh:
            banner = "=" * 72
            self.log.warning("%s\n  UPSTOX TOKEN: %s\n%s", banner, token_msg, banner)
        else:
            self.log.info(token_msg)

        any_canonical_trigger = False
        for source in self.config.get("sources", []):
            name = source["name"]
            if only and name not in only:
                continue

            if force and (not only or name in only):
                due, why = True, "forced"
            else:
                due, why = self.is_due(source, as_of)
            if not due:
                report["skipped"].append({"name": name, "reason": why})
                continue

            if bool(source.get("requires_upstox", False)) and not token_fresh:
                report["skipped"].append({"name": name, "reason": "upstox token stale"})
                continue

            if dry_run:
                report["ran"].append({"name": name, "reason": why, "dry_run": True})
                if bool(source.get("triggers_canonical", False)):
                    any_canonical_trigger = True
                continue

            self.log.info("[refresh] %s -- %s", name, why)
            commands = self._apply_gap_lookback(source, as_of)
            ok, msg = self._run_commands(commands, base_env)
            if ok:
                self._mark_success(name, str(source.get("cadence", "daily")), as_of)
                if source.get("prune"):
                    self._prune(str(source["prune"]))
                report["ran"].append({"name": name})
                if bool(source.get("triggers_canonical", False)):
                    any_canonical_trigger = True
            else:
                self.log.error("[refresh] %s FAILED: %s", name, msg)
                self._mark_failure(name, msg)
                report["failed"].append({"name": name, "error": msg})

        # Downstream canonical rebuild -- once, only if something changed.
        downstream = self.config.get("downstream", {}).get("canonical_rebuild", {})
        if any_canonical_trigger and downstream.get("commands"):
            if dry_run:
                report["canonical_rebuilt"] = "would_run"
            else:
                self.log.info("[refresh] downstream canonical rebuild")
                ok, msg = self._run_commands(downstream["commands"], base_env)
                report["canonical_rebuilt"] = bool(ok)
                if ok:
                    # Record success so consecutive_failures resets. Without this
                    # the counter was monotonic — canonical_rebuild stayed marked
                    # "failing" in refresh_state.json forever after one failure,
                    # even across successful rebuilds (audit 2026-07 finding).
                    self._mark_success("canonical_rebuild", "daily", as_of)
                else:
                    self._mark_failure("canonical_rebuild", msg)
                    report["failed"].append({"name": "canonical_rebuild", "error": msg})

        return report
