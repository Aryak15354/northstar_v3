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
OUTDIR="data/results/research/regime_ic_runs/next_alpha_${RUN_TS}"
RPTDIR="data/results/research/reports/regime_ic/next_alpha_${RUN_TS}"
mkdir -p "${OUTDIR}" "${RPTDIR}"

python3 -m py_compile \
  scripts/run_regime_ic_split.py \
  scripts/generate_regime_ic_experiment_report.py \
  scripts/build_horizon_ensemble_metrics.py \
  src/research/training_pipeline.py \
  src/research/diagnostics/ic_diagnostics.py

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
  --max-keep-features 40
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

# 1-3 Horizon components for ensemble
run_exp e01_h5_base --target-horizon-days 5 --rebalance-frequency-days 5 --label-embargo-periods 5 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --portfolio-mode long_short
run_exp e02_h10_base --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --portfolio-mode long_short
run_exp e03_h30_base --target-horizon-days 30 --rebalance-frequency-days 30 --label-embargo-periods 30 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --portfolio-mode long_short

# 4-5 Volatility-scaled vs unscaled
run_exp e04_h10_vol_scaled --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --use-vol-scaling --portfolio-mode long_short
run_exp e05_h10_vol_unscaled --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --no-use-vol-scaling --portfolio-mode long_short

# 6 Turnover control
run_exp e06_h10_turnover_control --target-horizon-days 10 --rebalance-frequency-days 15 --label-embargo-periods 10 --long-short-quantile 0.15 --max-weight-per-asset 0.08 --portfolio-mode long_short

# 7 Signal standardization
run_exp e07_h10_pred_zscore --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --prediction-transform zscore --portfolio-mode long_short

# 8 Prediction neutralization (factor + sector)
run_exp e08_h10_pred_neutralized --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --prediction-sector-neutralize --prediction-neutralize-factors "vol_20d,mom_20d,ret_20d,close,shares_outstanding" --portfolio-mode long_short

# 9 Rank sharpening
run_exp e09_h10_rank_sharpen --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --prediction-transform rank_power --prediction-rank-power 1.5 --portfolio-mode long_short

# 10 Tanh sharpening
run_exp e10_h10_tanh_sharpen --target-horizon-days 10 --rebalance-frequency-days 10 --label-embargo-periods 10 --long-short-quantile 0.20 --max-weight-per-asset 0.10 --prediction-transform tanh --prediction-tanh-scale 3.0 --portfolio-mode long_short

# Horizon ensemble artifact from 1-3
if [[ -f "${OUTDIR}/e01_h5_base.json" && -f "${OUTDIR}/e02_h10_base.json" && -f "${OUTDIR}/e03_h30_base.json" ]]; then
  python3 scripts/build_horizon_ensemble_metrics.py \
    --h5-json "${OUTDIR}/e01_h5_base.json" \
    --h10-json "${OUTDIR}/e02_h10_base.json" \
    --h30-json "${OUTDIR}/e03_h30_base.json" \
    --weights "0.3,0.4,0.3" \
    --output-json "${RPTDIR}/horizon_ensemble_metrics.json" | tee "${RPTDIR}/horizon_ensemble_metrics.log"
fi

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
if [[ -f "${RPTDIR}/horizon_ensemble_metrics.json" ]]; then
  echo "HORIZON_ENSEMBLE_JSON=${RPTDIR}/horizon_ensemble_metrics.json"
fi
if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo "FAILED_EXPERIMENTS=${FAILED[*]}"
fi
sed -n '1,120p' "${RPTDIR}/regime_ic_experiment_report.md"
