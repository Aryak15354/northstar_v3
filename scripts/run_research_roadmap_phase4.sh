#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_CONFIG="${1:-config/research_policy.yaml}"
OUT_ROOT="${ROADMAP_OUT_ROOT:-reports/research/roadmap}"
PHASE="phase4"
PHASE_DIR="${OUT_ROOT}/${PHASE}"
PHASE3_GATE_PATH="${ROADMAP_PHASE3_GATE_PATH:-${OUT_ROOT}/phase3/phase3_gate.json}"
REGIME_EXPOSURE_SCALE="${ROADMAP_REGIME_EXPOSURE_SCALE:-low_vol|downtrend:0.05,default:1.0}"
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

PHASE3_STATUS="$(python3 - "${PHASE3_GATE_PATH}" <<'PY'
import json
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
if not p.exists():
    print("MISSING")
    raise SystemExit(0)
try:
    payload = json.loads(p.read_text() or "{}")
except Exception:
    print("INVALID")
    raise SystemExit(0)
print(str(payload.get("status", "MISSING")).upper())
PY
)"

if [[ "${PHASE3_STATUS}" != "PASS" ]]; then
  set +e
  python3 scripts/research_roadmap_gate.py \
    --mode phase4 \
    --output-dir "${PHASE_DIR}" \
    --phase3-gate-path "${PHASE3_GATE_PATH}" \
    --results-glob "ex4*.json"
  gate_rc=$?
  set -e
  if [[ ${gate_rc} -ne 3 ]]; then
    echo "Phase4 block-path expected rc=3 but got rc=${gate_rc}" >&2
  fi
  echo "phase4 blocked_by_phase3_gate status=${PHASE3_STATUS}"
  exit 3
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
  --dataset-max-tickers 150
  --dataset-lookback-days 4200
  --disable-macro-features
  --target-horizon-days 5
  --regime-exposure-scale "${REGIME_EXPOSURE_SCALE}"
)

if [[ "${ROADMAP_SKIP_EXPERIMENTS:-0}" != "1" ]]; then
  run_exp ex41_signal_combo_quality_momentum \
    "${COMMON[@]}" \
    --feature-include-patterns "roe,operating_margin,mom_20d,res_mom_20d"

  run_exp ex42_liquidity_top_bucket \
    "${COMMON[@]}" \
    --liquidity-bucket top

  run_exp ex43_liquidity_mid_bucket \
    "${COMMON[@]}" \
    --liquidity-bucket mid

  run_exp ex44_liquidity_bottom_bucket \
    "${COMMON[@]}" \
    --liquidity-bucket bottom
fi

python3 scripts/research_roadmap_gate.py \
  --mode phase4 \
  --output-dir "${PHASE_DIR}" \
  --phase3-gate-path "${PHASE3_GATE_PATH}" \
  --results-glob "ex4*.json"

echo "phase=${PHASE}"
echo "output_dir=${PHASE_DIR}"
echo "phase3_gate_path=${PHASE3_GATE_PATH}"
