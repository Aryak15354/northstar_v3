#!/usr/bin/env python3
"""Readable, live Kaggle notebook logging.

Why this exists
---------------
Kaggle's notebook runner captures cell output at the *Python* level (ipykernel
replaces sys.stdout). A child started with subprocess.run() inherits the raw OS
file descriptors and writes straight past that capture, so its output NEVER
reaches the kernel log -- the run looks dead from the first subprocess call
onward. run_streamed() pipes the child and re-emits every line through Python's
stdout, so it shows up live.

The heartbeat matters just as much: a quiet child is indistinguishable from a
hung one. HeartBeat prints liveness + RSS + elapsed even when nothing is logged.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

_T0 = time.monotonic()
_LOCK = threading.Lock()
_LOGFILE: object | None = None


def _elapsed(t0: float | None = None) -> str:
    s = int(time.monotonic() - (t0 if t0 is not None else _T0))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def _rss_gb() -> float:
    """Container RSS in GB (cgroup v2/v1, falls back to /proc/self)."""
    for p in ("/sys/fs/cgroup/memory.current",
              "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            return int(Path(p).read_text().strip()) / 1e9
        except Exception:
            continue
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1e6
    except Exception:
        pass
    return -1.0


def _disk_free_gb(path: str = "/kaggle") -> float:
    try:
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize / 1e9
    except Exception:
        return -1.0


def set_logfile(path) -> None:
    """Mirror all output to a file so the log survives as a run artifact."""
    global _LOGFILE
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _LOGFILE = p.open("a", buffering=1)
    say(f"log mirrored to {p}")


def emit(line: str) -> None:
    with _LOCK:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()
        if _LOGFILE is not None:
            try:
                _LOGFILE.write(line + "\n")
            except Exception:
                pass


def say(msg: str) -> None:
    emit(f"[+{_elapsed()}]   {msg}")


def banner(msg: str) -> None:
    emit("")
    emit("=" * 78)
    emit(f"[+{_elapsed()}] {msg}")
    emit("=" * 78)


class Phase:
    """Context manager marking one top-level step, with pass/fail + duration."""

    def __init__(self, n: int, total: int, name: str) -> None:
        self.n, self.total, self.name = n, total, name

    def __enter__(self):
        self.t0 = time.monotonic()
        emit("")
        emit(f"[+{_elapsed()}] >>> PHASE {self.n}/{self.total}  {self.name}")
        emit(f"            rss={_rss_gb():.1f}GB free={_disk_free_gb():.0f}GB")
        return self

    def __exit__(self, exc_type, exc, tb):
        dur = _elapsed(self.t0)
        if exc_type is None:
            emit(f"[+{_elapsed()}] <<< PHASE {self.n}/{self.total}  OK   ({dur})  {self.name}")
        else:
            emit(f"[+{_elapsed()}] <<< PHASE {self.n}/{self.total}  FAIL ({dur})  {self.name}")
            emit(f"            {exc_type.__name__}: {exc}")
        return False


class HeartBeat:
    """Prints a liveness line every `every` seconds while a child is quiet."""

    def __init__(self, every: int = 60) -> None:
        self.every = every
        self.last_line_at = time.monotonic()
        self._stop = threading.Event()
        self._t: threading.Thread | None = None
        self.lines = 0

    def note_line(self) -> None:
        self.last_line_at = time.monotonic()
        self.lines += 1

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            quiet = int(time.monotonic() - self.last_line_at)
            if quiet >= self.every:
                emit(f"[+{_elapsed()}] ... alive | rss={_rss_gb():.1f}GB "
                     f"free={_disk_free_gb():.0f}GB | {self.lines} lines | "
                     f"child quiet {quiet}s")

    def __enter__(self):
        self._t = threading.Thread(target=self._run, daemon=True)
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        if self._t:
            self._t.join(timeout=2)
        return False


def run_streamed(cmd, *, tag: str = "child", heartbeat: int = 60,
                 env: dict | None = None, check: bool = True) -> int:
    """Run cmd, streaming every child line into the Kaggle log live.

    This is the whole point of the module -- see the note at the top on why
    subprocess.run() output is invisible on Kaggle.
    """
    child_env = dict(os.environ)
    child_env["PYTHONUNBUFFERED"] = "1"   # no 8KB block buffering in the child
    if env:
        child_env.update(env)

    emit(f"[+{_elapsed()}]   $ {' '.join(str(c) for c in cmd)}")
    t0 = time.monotonic()
    proc = subprocess.Popen(
        [str(c) for c in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # StepProgress writes to stderr -- fold it in
        bufsize=1,
        text=True,
        errors="replace",
        env=child_env,
    )
    with HeartBeat(every=heartbeat) as hb:
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue
            hb.note_line()
            emit(f"[+{_elapsed()}] | {line}")
        rc = proc.wait()

    dur = _elapsed(t0)
    emit(f"[+{_elapsed()}]   {tag} exit={rc} after {dur} ({hb.lines} lines)")
    if check and rc != 0:
        raise SystemExit(f"{tag} FAILED rc={rc} after {dur}")
    return rc
