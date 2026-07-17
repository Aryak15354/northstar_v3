#!/bin/bash
# Poll a Kaggle kernel's status; on completion, pull output + print the tail of the log.
# Kaggle exposes no live-log API -- for live output use the web UI. This tells you
# liveness/exit without babysitting the browser.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
KERNEL="${1:-aryakghoshal/northstar-v3-build-feature-export}"
EVERY="${2:-120}"
OUT="tmp/kaggle_out/$(basename "$KERNEL")"
START=$(date +%s)
while true; do
  S=$(python3 -m kaggle kernels status "$KERNEL" 2>&1 | sed 's/.*status "//;s/".*//')
  EL=$(( ($(date +%s) - START) / 60 ))
  echo "[$(date +%H:%M:%S)] +${EL}m  $S"
  case "$S" in
    *COMPLETE*|*ERROR*|*CANCEL*)
      mkdir -p "$OUT"
      python3 -m kaggle kernels output "$KERNEL" -p "$OUT" >/dev/null 2>&1 || true
      echo "--- output in $OUT ---"; ls -la "$OUT" 2>/dev/null
      [ -f "$OUT/build_log.txt" ] && { echo "--- tail build_log.txt ---"; tail -40 "$OUT/build_log.txt"; }
      break;;
  esac
  sleep "$EVERY"
done
