#!/usr/bin/env bash
# Daily data-collection driver for Northstar V3.
#
# Runs the alternative-data scrapers (with the fixed resume semantics and run
# ledger), canonicalizes them, refreshes the announcements incrementally, and
# finishes with the freshness invariant check. Designed to be invoked by launchd
# (see deploy/launchd/) but safe to run by hand.
#
# Exit code is the freshness checker's: non-zero means an error-severity dataset
# is stale, which the daemon/monitor can alert on.
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 2

PY="${NORTHSTAR_PYTHON:-/usr/local/bin/python3}"
LOG_DIR="$PROJECT_ROOT/data/logs/collection"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d)"
LOG="$LOG_DIR/daily_${STAMP}.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== daily data collection start ==="

log "step 1/4: alternative-data collection (resume, 1D)"
"$PY" scripts/collect_all_alternative_data.py --start-year 2024 --end-year "$(date +%Y)" \
      --nse-period 1D --resume >>"$LOG" 2>&1
log "  collect rc=$?"

log "step 2/4: announcements incremental (last 3 days)"
"$PY" scripts/backfill_nse_announcements_history.py \
      --start "$(date -v-3d +%Y-%m-%d 2>/dev/null || date -d '3 days ago' +%Y-%m-%d)" \
      --end "$(date +%Y-%m-%d)" --window-days 3 >>"$LOG" 2>&1
log "  announcements rc=$?"

log "step 3/4: canonicalize alternative data"
"$PY" scripts/canonicalize_alternative_data.py >>"$LOG" 2>&1
log "  canonicalize rc=$?"

log "step 4/4: freshness invariant check"
"$PY" scripts/ci/check_data_freshness.py | tee -a "$LOG"
FRESH_RC=${PIPESTATUS[0]}
log "  freshness rc=$FRESH_RC"

log "=== daily data collection done (freshness_rc=$FRESH_RC) ==="
exit "$FRESH_RC"
