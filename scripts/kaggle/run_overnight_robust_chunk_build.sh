#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

OUTPUT_DIR="${1:-${ROOT_DIR}/tmp/northstar_v3_chunk_build_robust_$(date +%Y%m%d_%H%M%S)}"
MERGED_DIR="${2:-${OUTPUT_DIR}_merged}"
LOG_DIR="${OUTPUT_DIR}/logs"

START_DATE="${START_DATE:-2019-01-01}"
END_DATE="${END_DATE:-2026-03-27}"
CHUNK_MONTHS="${CHUNK_MONTHS:-3}"
WARMUP_DAYS="${WARMUP_DAYS:-420}"
FORWARD_BUFFER_DAYS="${FORWARD_BUFFER_DAYS:-10}"
THREADS="${THREADS:-2}"
DUCKDB_THREADS="${DUCKDB_THREADS:-1}"
DUCKDB_MEMORY_LIMIT_MB="${DUCKDB_MEMORY_LIMIT_MB:-768}"
REBUILD_SCREENER="${REBUILD_SCREENER:-false}"
ALLOW_PROXIES="${ALLOW_PROXIES:-false}"
STRICT_PLAN_SIGNALS="${STRICT_PLAN_SIGNALS:-true}"
MIN_EXACT_SIGNAL_COVERAGE_PCT="${MIN_EXACT_SIGNAL_COVERAGE_PCT:-90}"
TRAIN_WEEKS="${TRAIN_WEEKS:-104}"
TEST_WEEKS="${TEST_WEEKS:-13}"
STEP_WEEKS="${STEP_WEEKS:-13}"
TARGET_WINDOWS="${TARGET_WINDOWS:-20}"

if (( WARMUP_DAYS > 35 )); then
  DEFAULT_STAGE_LOOKBACK_DAYS="${WARMUP_DAYS}"
else
  DEFAULT_STAGE_LOOKBACK_DAYS="35"
fi
STAGE_LOOKBACK_DAYS="${STAGE_LOOKBACK_DAYS:-${DEFAULT_STAGE_LOOKBACK_DAYS}}"
STAGE_START_DATE="${STAGE_START_DATE:-$(
  START_DATE="${START_DATE}" STAGE_LOOKBACK_DAYS="${STAGE_LOOKBACK_DAYS}" python3 -c \
    'import datetime as dt, os; start = dt.date.fromisoformat(os.environ["START_DATE"]); lookback = int(os.environ["STAGE_LOOKBACK_DAYS"]); print((start - dt.timedelta(days=lookback)).isoformat())'
)}"

mkdir -p "${LOG_DIR}"

echo "[overnight-build] root=${ROOT_DIR}"
echo "[overnight-build] output_dir=${OUTPUT_DIR}"
echo "[overnight-build] merged_dir=${MERGED_DIR}"
echo "[overnight-build] logs=${LOG_DIR}"
echo "[overnight-build] stage_start_date=${STAGE_START_DATE}"
echo "[overnight-build] stage_lookback_days=${STAGE_LOOKBACK_DAYS}"

python3 scripts/stage_plan_signal_market_data.py \
  --start-date "${STAGE_START_DATE}" \
  --end-date "${END_DATE}" \
  2>&1 | tee "${LOG_DIR}/stage_plan_signal_market_data.log"

python3 scripts/kaggle/build_local_feature_chunks.py \
  --output-dir "${OUTPUT_DIR}" \
  --start-date "${START_DATE}" \
  --end-date "${END_DATE}" \
  --chunk-months "${CHUNK_MONTHS}" \
  --warmup-days "${WARMUP_DAYS}" \
  --forward-buffer-days "${FORWARD_BUFFER_DAYS}" \
  --threads "${THREADS}" \
  --duckdb-threads "${DUCKDB_THREADS}" \
  --duckdb-memory-limit-mb "${DUCKDB_MEMORY_LIMIT_MB}" \
  --rebuild-screener "${REBUILD_SCREENER}" \
  --allow-proxies "${ALLOW_PROXIES}" \
  --strict-plan-signals "${STRICT_PLAN_SIGNALS}" \
  --min-exact-signal-coverage-pct "${MIN_EXACT_SIGNAL_COVERAGE_PCT}" \
  --train-weeks "${TRAIN_WEEKS}" \
  --test-weeks "${TEST_WEEKS}" \
  --step-weeks "${STEP_WEEKS}" \
  --target-windows "${TARGET_WINDOWS}" \
  2>&1 | tee "${LOG_DIR}/build_local_feature_chunks.log"

python3 scripts/kaggle/merge_chunked_feature_dataset.py \
  --chunk-root "${OUTPUT_DIR}" \
  --output-dir "${MERGED_DIR}" \
  2>&1 | tee "${LOG_DIR}/merge_chunked_feature_dataset.log"

echo "[overnight-build] complete"
echo "[overnight-build] chunk_bundle=${OUTPUT_DIR}"
echo "[overnight-build] merged_export=${MERGED_DIR}"
