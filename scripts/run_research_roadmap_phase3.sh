#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_CONFIG="${1:-config/research_policy.yaml}"
OUT_ROOT="${ROADMAP_OUT_ROOT:-data/results/research/reports/roadmap}"
PHASE="phase3"
PHASE_DIR="${OUT_ROOT}/${PHASE}"
mkdir -p "${PHASE_DIR}"

run_exp () {
  local name="$1"; shift
  local out_json="${PHASE_DIR}/${name}.json"
  local out_log="${PHASE_DIR}/${name}.log"
  echo "=== ${PHASE}:${name} ==="
  python3 scripts/run_regime_ic_split.py "$@" --output-json "${out_json}" 2>&1 | tee "${out_log}"
}

if [[ "${ROADMAP_SKIP_PREFLIGHT:-0}" != "1" ]]; then
  python3 scripts/research_roadmap_gate.py \
    --mode preflight \
    --phase "${PHASE}" \
    --base-config "${BASE_CONFIG}" \
    --output-dir "${PHASE_DIR}"
fi

COMMON=(
  --base-config "${BASE_CONFIG}"
  --model xgboost
  --max-cpu-cores 1
  --max-blas-threads 1
  --max-windows 8
  --train-periods 504
  --valid-periods 63
  --test-periods 63
  --step-periods 42
  --dataset-max-rows 200000
  --dataset-lookback-days 4200
  --disable-macro-features
  --target-horizon-days 5
)

# Universe scaling diagnostics used by phase3 gate.
run_exp ex02_universe_100 "${COMMON[@]}" --dataset-max-tickers 100
run_exp ex02_universe_150 "${COMMON[@]}" --dataset-max-tickers 150

# Hard OOS diagnostics (2020-01-01 to 2024-12-31).
run_exp ex08_hard_oos_2020_2024 \
  "${COMMON[@]}" \
  --dataset-max-rows 0 \
  --dataset-lookback-days 6500 \
  --dataset-max-tickers 150 \
  --holdout-train-end-date "2019-12-31" \
  --holdout-test-start-date "2020-01-01" \
  --holdout-test-end-date "2024-12-31" \
  --holdout-valid-periods 63 \
  --holdout-min-train-periods 252

# phase3_gate.json ownership rule:
# This file is written exclusively by this phase-3 runner upon actual metric evaluation.
python3 scripts/research_roadmap_gate.py \
  --mode phase3 \
  --output-dir "${PHASE_DIR}"

echo "phase=${PHASE}"
echo "output_dir=${PHASE_DIR}"
echo "phase3_gate=${PHASE_DIR}/phase3_gate.json"
