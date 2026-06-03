#!/usr/bin/env bash
# Northstar daily local/host job runner.
# Cron schedule options:
# - If host timezone is UTC: 0 3 * * 1-5 /path/to/northstar_v3/scripts/run_daily_cron.sh
# - If host timezone is IST: 30 8 * * 1-5 /path/to/northstar_v3/scripts/run_daily_cron.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATE_IST="$(TZ=Asia/Kolkata date +%Y-%m-%d)"
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/daily_${DATE_IST}.log"

mkdir -p "$LOG_DIR"

log_line() {
  local msg="$1"
  printf "%s %s\n" "$(TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M:%S %Z')" "$msg" >> "$LOG_FILE"
}

trap 'rc=$?; if [[ $rc -ne 0 ]]; then log_line "=== FAILED (exit=$rc) ==="; fi; exit $rc' EXIT

cd "$PROJECT_ROOT"

if [[ ! -f "venv/bin/activate" ]]; then
  log_line "venv/bin/activate not found. Create local venv first."
  exit 1
fi

source venv/bin/activate

log_line "=== Northstar v3 Daily Run Start ==="
log_line "[1/2] Run morning pipeline"
python3 scripts/run_morning_pipeline.py --date today >> "$LOG_FILE" 2>&1

log_line "[2/2] Local run complete (manual S3 sync if needed)"

log_line "=== Northstar v3 Daily Run Done ==="
