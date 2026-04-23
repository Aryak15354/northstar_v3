#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf .pytest_cache .hypothesis logs/ci || true
rm -rf data/state || true

find . -type d -name '__pycache__' -prune -exec rm -rf {} + || true
find . -type d -name '.mypy_cache' -prune -exec rm -rf {} + || true

mkdir -p logs/ci
mkdir -p data/options/live
mkdir -p data/options
mkdir -p data/runtime
mkdir -p data/processed
mkdir -p data/diagnostics

find data/options/live -maxdepth 1 -type f \( -name '*.lock' -o -name '*.pid' \) -delete || true
rm -f data/options/live/gate_code_freeze_baseline.json || true
rm -f data/options/live/runtime_gate_ci_bootstrap.json || true
rm -f data/options/live/options_runtime_state.json || true
rm -f data/options/live/options_dashboard_state.json || true
rm -f data/options/live/governance_events.parquet || true
rm -f data/options/live/northstar_daemon_status.json || true
rm -f data/options/live/full_gate_runner_status.json || true
rm -f data/options/live/write_journal.log || true
rm -f data/options/live/market_data_latest.json || true
rm -f data/options/trade_ledger.parquet || true
rm -f data/runtime/portfolio_runtime.db || true
rm -f data/runtime/portfolio_runtime.db.writer.lock || true
rm -f data/processed/test_count_baseline.json || true
rm -f data/diagnostics/alpha_diagnostics.db || true
rm -f data/diagnostics/alpha_metrics.parquet || true
rm -f data/diagnostics/strategy_metrics.parquet || true
rm -f data/diagnostics/policy_recommendations.json || true
