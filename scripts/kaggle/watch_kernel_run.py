#!/usr/bin/env python3
"""Watch a SPECIFIC Kaggle kernel run to completion, then pull its output.

Why not just poll `kernels status` (2026-07-17): right after a push, status
still reports the PREVIOUS run's terminal state (ERROR/COMPLETE) until the new
run is scheduled. A naive watcher exits on its first poll and downloads the old
output -- which reads exactly like the new run failing identically. That burned
two debug cycles chasing an already-fixed bug.

This anchors on `lastRunTime` for the exact ref: capture it before the push,
then a run is only "ours" once lastRunTime has ADVANCED past the baseline. Only
then is a terminal status meaningful.

Usage:
  # capture baseline BEFORE pushing:
  watch_kernel_run.py <ref> --baseline            -> prints lastRunTime
  # after pushing:
  watch_kernel_run.py <ref> --since "<baseline>" [--interval 300] [--timeout 43200]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

TERMINAL = ("COMPLETE", "ERROR", "CANCEL")


def _run(args: list[str]) -> str:
    return subprocess.run([sys.executable, "-m", "kaggle", *args],
                          capture_output=True, text=True).stdout


def last_run_time(ref: str) -> str | None:
    slug = ref.split("/")[-1]
    for line in _run(["kernels", "list", "-m", "-s", slug]).splitlines():
        if line.startswith(ref + " ") or line.startswith(ref + "\t"):
            m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)", line)
            if m:
                return m.group(1)
    return None


def status(ref: str) -> str:
    out = _run(["kernels", "status", ref])
    m = re.search(r'status "([^"]+)"', out)
    return m.group(1) if m else out.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--baseline", action="store_true", help="print current lastRunTime and exit")
    ap.add_argument("--since", help="baseline lastRunTime; wait for a run newer than this")
    ap.add_argument("--interval", type=int, default=300)
    ap.add_argument("--timeout", type=int, default=43200)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.baseline:
        print(last_run_time(a.ref) or "")
        return 0

    deadline = time.time() + a.timeout
    started = time.time()
    advanced = False
    while time.time() < deadline:
        lrt = last_run_time(a.ref)
        st = status(a.ref)
        mins = int((time.time() - started) / 60)
        if not advanced and a.since and lrt and lrt > a.since:
            advanced = True
            print(f"[+{mins}m] new run detected (lastRunTime {a.since} -> {lrt})", flush=True)
        state = "OURS" if (advanced or not a.since) else "stale-previous-run"
        print(f"[+{mins}m] {st}  lastRunTime={lrt}  [{state}]", flush=True)

        if any(t in st for t in TERMINAL) and (advanced or not a.since):
            outdir = Path(a.out or f"tmp/kaggle_out/{a.ref.split('/')[-1]}")
            outdir.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "kaggle", "kernels", "output", a.ref,
                            "-p", str(outdir), "--force"], capture_output=True, text=True)
            print(f"\nTERMINAL: {st}\noutput -> {outdir}", flush=True)
            log = outdir / "build_log.txt"
            if log.exists():
                print("\n--- build_log.txt (tail) ---")
                print("\n".join(log.read_text(errors="replace").splitlines()[-45:]))
            return 0 if "COMPLETE" in st else 1
        time.sleep(a.interval)

    print(f"TIMEOUT after {a.timeout}s")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
