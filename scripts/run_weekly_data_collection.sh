#!/usr/bin/env bash
# Weekly data-collection driver for Northstar V3.
#
# Heavier jobs that don't need daily cadence: Screener fundamentals re-scrape
# (with the fixed freshness-gated resume so quarterly updates actually land) and
# an incremental NSE XBRL results pull for the financials universe (new filings
# only — cached XBRL is immutable and skipped).
set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 2

PY="${NORTHSTAR_PYTHON:-/usr/local/bin/python3}"
LOG_DIR="$PROJECT_ROOT/data/logs/collection"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%d)"
LOG="$LOG_DIR/weekly_${STAMP}.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== weekly data collection start ==="

log "step 1/3: Screener fundamentals (resume, freshness-gated)"
"$PY" scripts/scrape_screener_financials.py --resume --max-age-days 45 >>"$LOG" 2>&1
log "  screener rc=$?"

log "step 2/3: load Screener into pipeline"
"$PY" scripts/load_screener_to_pipeline.py >>"$LOG" 2>&1
log "  load rc=$?"

log "step 3/3: NSE XBRL results incremental (financials universe)"
"$PY" -m src.ingestion.xbrl_results_fetcher --universe-financials >>"$LOG" 2>&1
log "  xbrl rc=$?"

log "=== weekly data collection done ==="
