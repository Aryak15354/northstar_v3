#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_CONFIG="${1:-config/research_policy.yaml}"
OUT_ROOT="${ROADMAP_OUT_ROOT:-data/results/research/reports/roadmap}"
PHASE="phase2"
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
  --max-windows 6
  --train-periods 504
  --valid-periods 63
  --test-periods 63
  --step-periods 42
  --dataset-max-rows 200000
  --dataset-lookback-days 3650
  --disable-macro-features
  --target-horizon-days 5
)

run_exp ex02_universe_100 "${COMMON[@]}" --dataset-max-tickers 100
run_exp ex02_universe_150 "${COMMON[@]}" --dataset-max-tickers 150
run_exp ex03_sector_information_technology "${COMMON[@]}" --dataset-max-tickers 150 --sector-filter "it"

python3 scripts/research_roadmap_gate.py \
  --mode phase-basic \
  --phase "${PHASE}" \
  --output-dir "${PHASE_DIR}" \
  --results-glob "ex*.json"

echo "phase=${PHASE}"
echo "output_dir=${PHASE_DIR}"
