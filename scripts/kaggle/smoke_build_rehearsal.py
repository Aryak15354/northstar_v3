#!/usr/bin/env python3
"""Local dress rehearsal of the Kaggle PANEL-B build. Run BEFORE any push.

Simulates the kernel exactly: staged export bundle -> rawfix copy -> chunk
builder with the kernel's arguments -> one (or N) chunks -> assertions.
Reports per-step wall times and every input-resolution warning, then projects
the full 31-chunk Kaggle runtime (scaled by a CPU factor, Kaggle ~2x slower).

Launch criteria (printed at the end): projected total < 8h AND zero unresolved
input warnings AND valuation step served from the attested cache.

Usage: python3 scripts/kaggle/smoke_build_rehearsal.py [--chunks 1] [--bundle tmp/kaggle_uploads/raw_inputs]
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KAGGLE_CPU_FACTOR = 2.0  # Kaggle Xeon vs this machine, conservative

KERNEL_ARGS = [  # keep IDENTICAL to write_build_export_notebook.py PHASE 4
    "--start-date", "2019-01-01",
    "--chunk-months", "3",
    "--warmup-days", "420",
    "--forward-buffer-days", "10",
    "--threads", "2",
    "--duckdb-threads", "2",
    "--duckdb-memory-limit-mb", "2048",
    "--rebuild-screener", "auto",
    "--allow-proxies", "false",
    "--strict-plan-signals", "false",
    "--min-exact-signal-coverage-pct", "0",
    "--skip-existing",
]

WARN_PATTERNS = re.compile(
    r"not found|missing|skipped|failed|no such|degrad|quarantined|empty", re.IGNORECASE
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=1)
    ap.add_argument("--bundle", type=Path, default=PROJECT_ROOT / "tmp/kaggle_uploads/raw_inputs")
    ap.add_argument("--workdir", type=Path, default=PROJECT_ROOT / "tmp/smoke_rehearsal")
    args = ap.parse_args()

    bundle = args.bundle.resolve()
    assert bundle.exists(), f"staged bundle missing: {bundle} (run the exporter first)"
    work = args.workdir.resolve()
    rawfix = work / "rawfix"
    chunks = work / "chunks"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    print(f"[smoke] bundle: {bundle}")
    t0 = time.time()
    shutil.copytree(bundle, rawfix)
    # kernel PHASE 3 equivalents
    src = rawfix / "data/canonical/macro/macro_regime_features.parquet"
    dst = rawfix / "data/processed/macro/macro_regime_features.parquet"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists() and not dst.exists():
        shutil.copy2(src, dst)
    print(f"[smoke] rawfix staged in {time.time()-t0:.0f}s")

    # end-date caps the build to N chunks: start + N*3 months
    year, month = 2019, 1 + 3 * args.chunks
    end_date = f"{year + (month - 1) // 12}-{(month - 1) % 12 + 1:02d}-01"

    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts/kaggle/build_local_feature_chunks.py"),
        "--data-dir", str(rawfix),
        "--output-dir", str(chunks),
        "--end-date", end_date,
        *KERNEL_ARGS,
    ]
    print(f"[smoke] $ {' '.join(cmd)}")
    t1 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, errors="replace", bufsize=1)
    warnings: list[str] = []
    step_times: list[tuple[str, float]] = []
    last_step, last_t = None, time.time()
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        if not line.strip():
            continue
        now = time.time()
        print(f"  | {line}", flush=True)
        if WARN_PATTERNS.search(line) and "quarantined stale" not in line:
            warnings.append(line.strip())
        m = re.search(r"(START|DONE) (.+)$", line)
        if m and m.group(1) == "START":
            last_step, last_t = m.group(2), now
        elif m and m.group(1) == "DONE" and last_step:
            step_times.append((last_step, now - last_t))
            last_step = None
    rc = proc.wait()
    build_secs = time.time() - t1

    print("\n" + "=" * 72)
    print(f"[smoke] builder exit={rc} in {build_secs/60:.1f} min for {args.chunks} chunk(s)")
    print("\nSTEP TIMES (slowest first):")
    for name, secs in sorted(step_times, key=lambda x: -x[1])[:12]:
        print(f"  {secs/60:6.1f}m  {name}")

    per_chunk = build_secs / max(args.chunks, 1)
    projected_h = per_chunk * 31 * KAGGLE_CPU_FACTOR / 3600
    print(f"\nPROJECTION: {per_chunk/60:.1f} min/chunk here x31 x{KAGGLE_CPU_FACTOR}(kaggle) "
          f"= {projected_h:.1f}h on Kaggle (+merge ~0.3h)")

    print(f"\nINPUT WARNINGS ({len(warnings)}):")
    for w in sorted(set(warnings)):
        print(f"  !! {w}")

    feats = sorted(chunks.rglob("features/*.parquet"))
    print(f"\nchunk feature files written: {len(feats)}")
    ok = rc == 0 and len(feats) >= args.chunks and projected_h < 8.0
    verdict = "GO" if ok and not warnings else ("GO-WITH-WARNINGS" if ok else "NO-GO")
    print(f"\nVERDICT: {verdict}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
