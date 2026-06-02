#!/bin/bash
# start_live_trading.sh - canonical launcher for the integrated V3 live stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "=============================================="
echo "NORTHSTAR V3 - CANONICAL LIVE STACK"
echo "=============================================="
echo ""

export NORTHSTAR_REQUIRE_UPSTOX_TOKEN=1
# shellcheck disable=SC1091
source "$PROJECT_ROOT/scripts/load_runtime_env.sh"
echo "Loaded credentials from ${NORTHSTAR_ENV_FILE}"

mkdir -p logs

LOOP_INTERVAL_MINUTES="${NORTHSTAR_LOOP_INTERVAL_MINUTES:-15}"
RUNTIME_SYNC_MINUTES="${NORTHSTAR_RUNTIME_SYNC_MINUTES:-15}"
DEFAULT_STALE_MINUTES="$("$PYTHON_BIN" -c 'import sys; interval = float(sys.argv[1]); print(max(interval * 2.0, interval + 10.0, 15.0))' "$LOOP_INTERVAL_MINUTES")"
STALE_MINUTES="${NORTHSTAR_STALE_MINUTES:-$DEFAULT_STALE_MINUTES}"
OPTIONS_SCAN_TICKERS="${OPTIONS_MAX_DYNAMIC_UNDERLYINGS:-180}"
OPTIONS_EXECUTION_CANDIDATES="${OPTIONS_SENTIMENT_EXECUTION_CANDIDATES:-36}"
OPTIONS_EXPLICIT_HEDGE_MODE="${OPTIONS_EXPLICIT_HEDGE_MODE:-0}"
START_FRESH_TODAY="${NORTHSTAR_START_FRESH_TODAY:-0}"
START_FRESH_NORMALIZED="$(printf '%s' "$START_FRESH_TODAY" | tr '[:upper:]' '[:lower:]')"

export OPTIONS_MAX_DYNAMIC_UNDERLYINGS="$OPTIONS_SCAN_TICKERS"
export OPTIONS_SENTIMENT_EXECUTION_CANDIDATES="$OPTIONS_EXECUTION_CANDIDATES"
export OPTIONS_EXPLICIT_HEDGE_MODE="$OPTIONS_EXPLICIT_HEDGE_MODE"

START_FRESH_FLAG="--no-start-fresh-today"
case "$START_FRESH_NORMALIZED" in
  1|true|yes|on)
    START_FRESH_FLAG="--start-fresh-today"
    ;;
esac

echo "Loop cadence: ${LOOP_INTERVAL_MINUTES} minutes"
echo "Runtime sync cadence: ${RUNTIME_SYNC_MINUTES} minutes"
echo "Stale threshold: ${STALE_MINUTES} minutes"
echo "Normal-mode scan target: ${OPTIONS_SCAN_TICKERS} tickers"
echo "Sentiment execution shortlist: ${OPTIONS_EXECUTION_CANDIDATES} tickers"
echo "Explicit hedge mode: $( [ "$OPTIONS_EXPLICIT_HEDGE_MODE" = "1" ] && echo enabled || echo disabled )"
echo "Interday persistence: $( [ "$START_FRESH_FLAG" = "--no-start-fresh-today" ] && echo enabled || echo disabled )"
echo ""

echo "Stopping older launcher processes..."
pkill -f "run_trading_day_orchestrator.py" 2>/dev/null || true
pkill -f "run_integrated_options_paper_engine.py" 2>/dev/null || true
pkill -f "run_live_options_trading.py" 2>/dev/null || true
pkill -f "run_live_engine.py" 2>/dev/null || true
pkill -f "run_5min_market_updates.py" 2>/dev/null || true
pkill -f "run_ns_uso_sentiment_loop.py" 2>/dev/null || true
pkill -f "run_5min_sentiment_updates.py" 2>/dev/null || true
pkill -f "northstar_v3_ultimate_integrated_dashboard.py" 2>/dev/null || true
pkill -f "src/dashboard/app.py" 2>/dev/null || true
sleep 2

echo "Starting canonical dashboard..."
nohup env STREAMLIT_SERVER_FILE_WATCHER_TYPE=none "$PYTHON_BIN" -m streamlit run \
  src/dashboard/app.py \
  --server.port 8517 \
  --server.address 127.0.0.1 \
  --server.headless true \
  > logs/dashboard_8517.log 2>&1 &
DASHBOARD_PID=$!
echo "$DASHBOARD_PID" > logs/dashboard.pid

echo "Starting trading-day orchestrator..."
nohup "$PYTHON_BIN" scripts/run_trading_day_orchestrator.py \
  --run-once-day \
  "$START_FRESH_FLAG" \
  --interval-minutes "$LOOP_INTERVAL_MINUTES" \
  --runtime-sync-minutes "$RUNTIME_SYNC_MINUTES" \
  --market-stale-minutes "$STALE_MINUTES" \
  --options-stale-minutes "$STALE_MINUTES" \
  --sentiment-stale-minutes "$STALE_MINUTES" \
  --eod-v3-mode quick \
  --skip-options-backtest \
  > logs/trading_day_orchestrator.log 2>&1 &
ORCH_PID=$!
echo "$ORCH_PID" > logs/trading_day_orchestrator.pid

echo ""
echo "Dashboard PID: $DASHBOARD_PID"
echo "Orchestrator PID: $ORCH_PID"
echo "Dashboard: http://127.0.0.1:8517"
echo "Python: $PYTHON_BIN"
echo "Logs:"
echo "  logs/dashboard_8517.log"
echo "  logs/trading_day_orchestrator.log"
echo ""
echo "To stop: bash scripts/stop_live_trading.sh"
