#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf .pytest_cache .hypothesis logs/ci || true
rm -rf data/state data/processed/runtime data/diagnostics || true
rm -f data/runtime/portfolio_runtime.db || true

find . -type d -name '__pycache__' -prune -exec rm -rf {} + || true
find . -type d -name '.mypy_cache' -prune -exec rm -rf {} + || true

mkdir -p logs/ci
mkdir -p data/options/live
mkdir -p reports/system

find data/options/live -maxdepth 1 -type f \
  \( -name '*.lock' -o -name '*.pid' -o -name '*.json' -o -name '*.jsonl' -o -name '*.log' -o -name '*.sha256' \) \
  -delete || true
find data/options -maxdepth 1 -type f -name 'trade_ledger.parquet' -delete || true
find reports/system -maxdepth 1 -type f -name 'complete_system_run_*.json' -delete || true
