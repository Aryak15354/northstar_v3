#!/bin/bash
# stop_live_trading.sh - stop the canonical integrated V3 live stack

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=============================================="
echo "STOPPING NORTHSTAR V3 LIVE STACK"
echo "=============================================="
echo ""

for pid_file in logs/dashboard.pid logs/trading_day_orchestrator.pid; do
  if [ -f "$pid_file" ]; then
    PID="$(cat "$pid_file")"
    if [ -n "$PID" ]; then
      echo "Stopping PID $PID from $pid_file"
      kill "$PID" 2>/dev/null || true
    fi
  fi
done

pkill -f "run_trading_day_orchestrator.py" 2>/dev/null || true
pkill -f "run_integrated_options_paper_engine.py" 2>/dev/null || true
pkill -f "run_live_options_trading.py" 2>/dev/null || true
pkill -f "run_live_engine.py" 2>/dev/null || true
pkill -f "run_5min_market_updates.py" 2>/dev/null || true
pkill -f "run_ns_uso_sentiment_loop.py" 2>/dev/null || true
pkill -f "run_5min_sentiment_updates.py" 2>/dev/null || true
pkill -f "northstar_v3_ultimate_integrated_dashboard.py" 2>/dev/null || true
pkill -f "src/dashboard/app.py" 2>/dev/null || true

rm -f logs/dashboard.pid logs/trading_day_orchestrator.pid

echo ""
echo "Live stack stopped."
echo "Logs remain in logs/."
