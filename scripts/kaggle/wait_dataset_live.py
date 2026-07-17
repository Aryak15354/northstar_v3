#!/usr/bin/env python3
"""Block until a Kaggle dataset's newest version is live, verified by content.

Why this exists (2026-07-17): waiting via
``kaggle datasets list -s <slug> | grep <timestamp-pattern>`` is unsafe on two
counts -- the search returns MANY datasets (a different row's timestamp can
satisfy the grep) and Kaggle's listing clock is not the local clock. A kernel
pushed against a still-processing version silently mounts the PREVIOUS version,
so the run looks legitimate while executing stale code. That cost a full smoke
cycle chasing a bug that was already fixed.

This checks the only thing that actually matters: does the live dataset contain
the expected content?

Usage:
  wait_dataset_live.py <owner/slug> --file <path-in-dataset> --contains <text>
  wait_dataset_live.py <owner/slug> --file <path> --contains <text> --timeout 1800
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def fetch(ref: str, dest: Path) -> bool:
    r = subprocess.run(
        [sys.executable, "-m", "kaggle", "datasets", "download", ref, "-p", str(dest), "--unzip", "-q"],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--file", required=True, help="path inside the dataset to inspect")
    ap.add_argument("--contains", required=True, help="text that must be present")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--interval", type=int, default=45)
    a = ap.parse_args()

    deadline = time.time() + a.timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            if fetch(a.ref, dest):
                target = dest / a.file
                if target.exists() and a.contains in target.read_text(errors="replace"):
                    print(f"LIVE: {a.ref} :: {a.file} contains {a.contains!r} (attempt {attempt})")
                    return 0
                state = "content not yet updated" if target.exists() else f"{a.file} absent"
                print(f"[{attempt}] {a.ref}: {state}; waiting {a.interval}s", flush=True)
            else:
                print(f"[{attempt}] {a.ref}: download failed; waiting {a.interval}s", flush=True)
        time.sleep(a.interval)

    print(f"TIMEOUT after {a.timeout}s: {a.ref} never served {a.contains!r} in {a.file}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
