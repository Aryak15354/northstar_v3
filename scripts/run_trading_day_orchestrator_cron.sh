#!/bin/bash
# Cron-safe wrapper for the trading-day orchestrator.

set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/trading_day_orchestrator.log"
PYTHON_BIN="${NORTHSTAR_PYTHON_BIN:-python3}"

mkdir -p "${LOG_DIR}"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z %z')] cron wrapper: starting trading-day orchestrator"
  cd "${PROJECT_ROOT}"
  export NORTHSTAR_REQUIRE_UPSTOX_TOKEN=1
  . "${PROJECT_ROOT}/scripts/load_runtime_env.sh"

  exec "${PYTHON_BIN}" \
    "${PROJECT_ROOT}/scripts/run_trading_day_orchestrator.py" \
    --run-once-day \
    --start-fresh-today \
    --interval-minutes 5 \
    --runtime-sync-minutes 15 \
    --eod-v3-mode quick \
    --skip-options-backtest \
    "$@"
} >> "${LOG_FILE}" 2>&1
