#!/usr/bin/env python3
"""Resumable progress manifest: one row per (source, identifier, quarter_label) unit of work, with
status in {pending, done, empty, failed} and a retry count. Atomic writes (write-tmp-then-replace),
so a killed process never corrupts the manifest -- re-running `run_scrape.py` picks up exactly where
it left off, skipping every unit already marked done/empty and retrying only failed units (up to a
cap).
"""
from __future__ import annotations

import csv
import time
from pathlib import Path
from threading import Lock

FIELDS = ["source", "identifier", "quarter_label", "status", "attempts", "last_attempt_ts", "note"]


class Checkpoint:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._rows: dict[tuple[str, str, str], dict] = {}
        self._load()

    def _key(self, source: str, identifier: str, quarter_label: str) -> tuple[str, str, str]:
        return (source, str(identifier).upper(), quarter_label)

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                k = self._key(row["source"], row["identifier"], row["quarter_label"])
                self._rows[k] = row

    def _flush(self) -> None:
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            for row in self._rows.values():
                w.writerow(row)
        tmp.replace(self.path)

    def status(self, source: str, identifier: str, quarter_label: str) -> str | None:
        row = self._rows.get(self._key(source, identifier, quarter_label))
        return row["status"] if row else None

    def should_attempt(self, source: str, identifier: str, quarter_label: str,
                       max_retries: int = 3) -> bool:
        row = self._rows.get(self._key(source, identifier, quarter_label))
        if row is None:
            return True
        if row["status"] in ("done", "empty"):
            return False
        if row["status"] == "failed" and int(row["attempts"]) >= max_retries:
            return False
        return True

    def record(self, source: str, identifier: str, quarter_label: str, status: str,
              note: str = "") -> None:
        with self._lock:
            k = self._key(source, identifier, quarter_label)
            prev = self._rows.get(k)
            attempts = int(prev["attempts"]) + 1 if prev else 1
            self._rows[k] = dict(source=source, identifier=str(identifier).upper(),
                                 quarter_label=quarter_label, status=status,
                                 attempts=str(attempts), last_attempt_ts=str(time.time()),
                                 note=note[:200])
            self._flush()

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in self._rows.values():
            out[row["status"]] = out.get(row["status"], 0) + 1
        out["total"] = len(self._rows)
        return out
