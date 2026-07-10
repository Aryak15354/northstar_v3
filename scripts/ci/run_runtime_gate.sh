#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"

export NORTHSTAR_STRICT_MODE="${NORTHSTAR_STRICT_MODE:-1}"
export NORTHSTAR_CI_GATE="${NORTHSTAR_CI_GATE:-1}"
export NORTHSTAR_FAST_MARKET_REFRESH="${NORTHSTAR_FAST_MARKET_REFRESH:-1}"
export RISK_RANDOM_SEED="${RISK_RANDOM_SEED:-42}"
export PYTHONHASHSEED="${PYTHONHASHSEED:-42}"
export TZ="${TZ:-UTC}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LANG="${LANG:-C.UTF-8}"

bash scripts/ci/clean_ci_runtime_state.sh
"$PYTHON_BIN" scripts/ci/bootstrap_runtime_gate_state.py --write > logs/ci/runtime_gate_bootstrap.log 2>&1
cat logs/ci/runtime_gate_bootstrap.log

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

# NOTE: this used to call a repo-root `run.py --mode <health|update|dashboard>`,
# which does not exist anywhere in this checkout (confirmed via repo-wide
# search) -- every invocation below would fail immediately with "No such
# file or directory". Remapped to the equivalent flags on the current
# canonical entry point, scripts/run_complete_v3_system.py (per
# docs/operations/SCRIPT_CATALOG.md). If the original --mode semantics
# differed from this mapping, correct it here.
run_cmd health "$PYTHON_BIN" scripts/system_status_report.py
run_cmd update "$PYTHON_BIN" scripts/run_complete_v3_system.py --quick --data-only
run_cmd options_runtime "$PYTHON_BIN" scripts/ci/strict_options_runtime_check.py
run_cmd dashboard "$PYTHON_BIN" scripts/run_complete_v3_system.py --dashboard-only
run_cmd ade "$PYTHON_BIN" scripts/run_alpha_diagnostics.py --runtime-db data/runtime/portfolio_runtime.db --diagnostics-db data/diagnostics/alpha_diagnostics.db
run_cmd replay "$PYTHON_BIN" -c "from src.runtime import PortfolioRuntimeService; prs=PortfolioRuntimeService(db_path='data/runtime/portfolio_runtime.db', materialized_output_dir='data/processed/runtime'); out=prs.replay(); prs.close(); import json,sys; print(json.dumps(out)); sys.exit(0 if out.get('deterministic_match', True) else 1)"
run_cmd live_artifact_invariants "$PYTHON_BIN" scripts/ci/check_live_artifact_invariants.py
run_cmd code_freeze_verify "$PYTHON_BIN" scripts/ci/bootstrap_runtime_gate_state.py --verify

"$PYTHON_BIN" scripts/ci/check_strict_log_patterns.py --log-dir logs/ci
