#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

export NORTHSTAR_STRICT_MODE="${NORTHSTAR_STRICT_MODE:-1}"
export NORTHSTAR_CI_GATE="${NORTHSTAR_CI_GATE:-1}"
export RISK_RANDOM_SEED="${RISK_RANDOM_SEED:-42}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-42}"
export TZ="${TZ:-UTC}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

bash scripts/ci/clean_ci_runtime_state.sh

run_cmd() {
  local name="$1"
  shift
  local log_file="logs/ci/runtime_gate_${name}.log"
  echo "[runtime-gate] Running ${name}: $*"
  set +e
  "$@" >"$log_file" 2>&1
  local rc=$?
  set -e
  cat "$log_file"
  if [[ $rc -ne 0 ]]; then
    echo "[runtime-gate] ${name} failed with exit code ${rc}"
    exit "$rc"
  fi
}

run_cmd bootstrap "$PYTHON_BIN" scripts/ci/bootstrap_runtime_gate_state.py
run_cmd health "$PYTHON_BIN" run.py --mode health --verbose
run_cmd update "$PYTHON_BIN" run.py --mode update --quick --verbose
run_cmd dashboard "$PYTHON_BIN" run.py --mode dashboard --dashboard brain --verbose
run_cmd ade "$PYTHON_BIN" scripts/run_alpha_diagnostics.py --runtime-db data/runtime/portfolio_runtime.db --diagnostics-db data/diagnostics/alpha_diagnostics.db
run_cmd replay "$PYTHON_BIN" -c "from src.runtime import PortfolioRuntimeService; prs=PortfolioRuntimeService(db_path='data/runtime/portfolio_runtime.db', materialized_output_dir='data/processed/runtime'); out=prs.replay(); prs.close(); import json,sys; print(json.dumps(out)); sys.exit(0 if out.get('deterministic_match', True) else 1)"

"$PYTHON_BIN" scripts/ci/check_strict_log_patterns.py --log-dir logs/ci
