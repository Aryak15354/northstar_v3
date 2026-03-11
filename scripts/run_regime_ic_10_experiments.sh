#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BASE_CONFIG="${1:-/tmp/research_policy_full_stack_postfix.yaml}"
if [[ ! -f "${BASE_CONFIG}" ]]; then
  echo "Missing base config: ${BASE_CONFIG}" >&2
  exit 1
fi

RUN_TS="$(date +%Y%m%d_%H%M%S)"
OUTDIR="data/research/regime_ic_runs/run_${RUN_TS}"
RPTDIR="data/research/reports/run_${RUN_TS}"
mkdir -p "${OUTDIR}" "${RPTDIR}"

python3 -m py_compile \
  scripts/run_regime_ic_split.py \
  scripts/generate_regime_ic_experiment_report.py \
  src/research/diagnostics/ic_diagnostics.py \
  src/research/walk_forward_validator.py \
  src/research/training_pipeline.py

COMMON=(
  --base-config "${BASE_CONFIG}"
  --model xgboost
  --max-cpu-cores 1
  --max-blas-threads 1
  --max-windows 10
  --train-periods 504
  --valid-periods 84
  --test-periods 84
  --step-periods 42
  --dataset-max-rows 180000
  --dataset-max-tickers 140
  --dataset-lookback-days 3600
  --prune-features-by-ic
  --ic-min-abs 0.01
  --ic-min-sign-consistency 0.55
  --transaction-cost-bps 25
  --sector-neutralize
)

declare -a FAILED=()
run_exp () {
  local NAME="$1"; shift
  local OUT_JSON="${OUTDIR}/${NAME}.json"
  local LOG_FILE="${OUTDIR}/${NAME}.log"
  if [[ -f "${OUT_JSON}" ]]; then
    echo "=== SKIP ${NAME} (exists) ==="
    return 0
  fi
  echo "=== RUN ${NAME} ==="
  if python3 scripts/run_regime_ic_split.py "${COMMON[@]}" "$@" --output-json "${OUT_JSON}" 2>&1 | tee "${LOG_FILE}"; then
    echo "=== DONE ${NAME} ==="
  else
    echo "=== FAIL ${NAME} ==="
    FAILED+=("${NAME}")
  fi
}

# E01 anchor
run_exp e01_anchor_h5_q20_ls \
  --target-horizon-days 5 \
  --rebalance-frequency-days 5 \
  --label-embargo-periods 5 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_short

# E02 decay h=1
run_exp e02_decay_h1_q20_ls \
  --target-horizon-days 1 \
  --rebalance-frequency-days 1 \
  --label-embargo-periods 1 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_short

# E03 decay h=3
run_exp e03_decay_h3_q20_ls \
  --target-horizon-days 3 \
  --rebalance-frequency-days 3 \
  --label-embargo-periods 3 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_short

# E04 decay h=10
run_exp e04_decay_h10_q20_ls \
  --target-horizon-days 10 \
  --rebalance-frequency-days 10 \
  --label-embargo-periods 10 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_short

# E05 decay h=20
run_exp e05_decay_h20_q20_ls \
  --target-horizon-days 20 \
  --rebalance-frequency-days 20 \
  --label-embargo-periods 20 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_short

# E06 decay h=30
run_exp e06_decay_h30_q20_ls \
  --target-horizon-days 30 \
  --rebalance-frequency-days 30 \
  --label-embargo-periods 30 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_short

# E07 magnitude filter q=30%
run_exp e07_mag_h10_q30_ls \
  --target-horizon-days 10 \
  --rebalance-frequency-days 10 \
  --label-embargo-periods 10 \
  --long-short-quantile 0.30 \
  --max-weight-per-asset 0.08 \
  --portfolio-mode long_short

# E08 magnitude filter q=10%
run_exp e08_mag_h10_q10_ls \
  --target-horizon-days 10 \
  --rebalance-frequency-days 10 \
  --label-embargo-periods 10 \
  --long-short-quantile 0.10 \
  --max-weight-per-asset 0.06 \
  --portfolio-mode long_short

# E09 long-only asymmetry
run_exp e09_asym_h10_q20_longonly \
  --target-horizon-days 10 \
  --rebalance-frequency-days 10 \
  --label-embargo-periods 10 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode long_only

# E10 short-only asymmetry
run_exp e10_asym_h10_q20_shortonly \
  --target-horizon-days 10 \
  --rebalance-frequency-days 10 \
  --label-embargo-periods 10 \
  --long-short-quantile 0.20 \
  --max-weight-per-asset 0.10 \
  --portfolio-mode short_only

python3 scripts/generate_regime_ic_experiment_report.py \
  --glob "${OUTDIR}/*.json" \
  --output-md "${RPTDIR}/regime_ic_experiment_report.md" \
  --output-csv "${RPTDIR}/regime_ic_experiment_summary.csv" \
  --output-regime-csv "${RPTDIR}/regime_ic_experiment_regime_rows.csv"

echo "RUN_TS=${RUN_TS}"
echo "OUTDIR=${OUTDIR}"
echo "REPORT_MD=${RPTDIR}/regime_ic_experiment_report.md"
echo "REPORT_CSV=${RPTDIR}/regime_ic_experiment_summary.csv"
echo "REPORT_REGIME_CSV=${RPTDIR}/regime_ic_experiment_regime_rows.csv"
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "FAILED_EXPERIMENTS=${FAILED[*]}"
fi
echo "Top of report:"
sed -n '1,120p' "${RPTDIR}/regime_ic_experiment_report.md"

