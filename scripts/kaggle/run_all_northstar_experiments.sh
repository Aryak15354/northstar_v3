#!/usr/bin/env bash
# Run Northstar V3 Run 4 tabular and sequence experiments in one Kaggle cell.
# Every experiment gets a separate output folder and log file. The suite keeps
# going if one experiment fails, writes a status CSV, and autosaves archives.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAN_DIR="${SCRIPT_DIR}/plan_2026_05_18_production"
RUN3_DIR="${SCRIPT_DIR}/run3_experiment_scripts"
SEQ_DIR_CODE="${SCRIPT_DIR}/sequence_experiments"

resolve_dir() {
  local explicit="${1:-}"
  shift || true
  if [[ -n "${explicit}" && -e "${explicit}" ]]; then
    printf '%s\n' "${explicit}"
    return 0
  fi
  for candidate in "$@"; do
    if [[ -e "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
  printf '%s\n' "${explicit}"
}

FEATURE_DATA_DIR="$(resolve_dir "${FEATURE_DATA_DIR:-}" \
  "/kaggle/input/datasets/aryakghoshal/northstar-v3-feature-export-fixed" \
  "/kaggle/input/northstar-v3-feature-export-fixed")"

SEQUENCE_DATA_DIR="$(resolve_dir "${SEQUENCE_DATA_DIR:-}" \
  "/kaggle/input/datasets/aryakghoshal/northstar-v3-sequence-export" \
  "/kaggle/input/northstar-v3-sequence-export" \
  "/kaggle/working/northstar_v3_sequence_export")"

OUTPUT_ROOT="${OUTPUT_ROOT:-/kaggle/working/northstar_all_experiment_results}"
LOG_DIR="${LOG_DIR:-/kaggle/working/northstar_run_logs}"
AUTOSAVE_ARCHIVE="${AUTOSAVE_ARCHIVE:-/kaggle/working/northstar_run4_results_latest.tar.gz}"
FINAL_ARCHIVE="${FINAL_ARCHIVE:-/kaggle/working/northstar_run4_results_and_logs_final.tar.gz}"
AUTOSAVE_KAGGLE_DATASET_ID="${AUTOSAVE_KAGGLE_DATASET_ID:-}"
REQUIRE_SEQUENCE="${REQUIRE_SEQUENCE:-1}"
MAX_WINDOWS_ARG=()
if [[ -n "${MAX_WINDOWS:-}" ]]; then
  MAX_WINDOWS_ARG=(--max-windows "${MAX_WINDOWS}")
fi

SEQ_EXTRA_ARGS=()
if [[ -n "${SEQ_MAX_TRAIN_SAMPLES:-}" ]]; then
  SEQ_EXTRA_ARGS+=(--max-train-samples "${SEQ_MAX_TRAIN_SAMPLES}")
fi
if [[ -n "${SEQ_MAX_TEST_SAMPLES:-}" ]]; then
  SEQ_EXTRA_ARGS+=(--max-test-samples "${SEQ_MAX_TEST_SAMPLES}")
fi
if [[ "${SEQ_INCLUDE_MASK:-0}" == "1" ]]; then
  SEQ_EXTRA_ARGS+=(--include-mask)
fi

mkdir -p "${OUTPUT_ROOT}" "${LOG_DIR}"
STATUS_CSV="${OUTPUT_ROOT}/run_status.csv"
printf 'experiment,status,started_at,finished_at,log_file,output_dir\n' > "${STATUS_CSV}"

autosave_archive() {
  local archive_path="$1"
  local output_parent
  local output_base
  local log_parent
  local log_base
  output_parent="$(dirname "${OUTPUT_ROOT}")"
  output_base="$(basename "${OUTPUT_ROOT}")"
  log_parent="$(dirname "${LOG_DIR}")"
  log_base="$(basename "${LOG_DIR}")"
  if [[ "${output_parent}" == "${log_parent}" ]]; then
    tar -czf "${archive_path}" -C "${output_parent}" "${output_base}" "${log_base}" 2>/dev/null || true
  else
    local staging="/kaggle/working/northstar_autosave_staging"
    rm -rf "${staging}" 2>/dev/null || true
    mkdir -p "${staging}"
    cp -R "${OUTPUT_ROOT}" "${staging}/${output_base}" 2>/dev/null || true
    cp -R "${LOG_DIR}" "${staging}/${log_base}" 2>/dev/null || true
    tar -czf "${archive_path}" -C "${staging}" "${output_base}" "${log_base}" 2>/dev/null || true
  fi
  if [[ -f "${archive_path}" ]]; then
    printf 'AUTOSAVED archive: %s\n' "${archive_path}"
  fi
}

autosave_kaggle_dataset() {
  if [[ -z "${AUTOSAVE_KAGGLE_DATASET_ID}" ]]; then
    return 0
  fi
  if ! command -v kaggle >/dev/null 2>&1; then
    printf 'WARNING: kaggle CLI not available; skipping Kaggle dataset autosave.\n'
    return 0
  fi
  local staging="/kaggle/working/northstar_run4_kaggle_autosave"
  local title
  title="$(printf '%s' "${AUTOSAVE_KAGGLE_DATASET_ID}" | awk -F/ '{print $2}')"
  rm -rf "${staging}" 2>/dev/null || true
  mkdir -p "${staging}"
  cp "${FINAL_ARCHIVE}" "${staging}/northstar_run4_results_and_logs_final.tar.gz" 2>/dev/null || true
  cp "${AUTOSAVE_ARCHIVE}" "${staging}/northstar_run4_results_latest.tar.gz" 2>/dev/null || true
  cp "${STATUS_CSV}" "${staging}/run_status.csv" 2>/dev/null || true
  cat > "${staging}/dataset-metadata.json" <<EOF
{
  "title": "${title}",
  "id": "${AUTOSAVE_KAGGLE_DATASET_ID}",
  "licenses": [{"name": "other"}],
  "isPrivate": true
}
EOF
  if kaggle datasets files "${AUTOSAVE_KAGGLE_DATASET_ID}" >/dev/null 2>&1; then
    kaggle datasets version -p "${staging}" -m "Northstar Run 4 autosaved results" --dir-mode zip || true
  else
    kaggle datasets create -p "${staging}" --dir-mode zip || true
  fi
}

run_job() {
  local name="$1"
  local out_dir="$2"
  shift 2
  local log_file="${LOG_DIR}/${name}.log"
  local started
  local finished
  started="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  mkdir -p "${out_dir}"
  printf '\n============================================================\n'
  printf 'RUNNING %s\n' "${name}"
  printf 'LOG     %s\n' "${log_file}"
  printf 'OUTPUT  %s\n' "${out_dir}"
  printf '============================================================\n'
  "$@" 2>&1 | tee "${log_file}"
  local status="${PIPESTATUS[0]}"
  finished="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  printf '%s,%s,%s,%s,%s,%s\n' "${name}" "${status}" "${started}" "${finished}" "${log_file}" "${out_dir}" >> "${STATUS_CSV}"
  autosave_archive "${AUTOSAVE_ARCHIVE}"
  if [[ "${status}" -ne 0 ]]; then
    printf 'WARNING: %s exited with status %s. Continuing suite.\n' "${name}" "${status}"
  fi
}

printf 'Northstar V3 Run 4 suite\n'
printf 'Feature data : %s\n' "${FEATURE_DATA_DIR}"
printf 'Sequence data: %s\n' "${SEQUENCE_DATA_DIR}"
printf 'Output root  : %s\n' "${OUTPUT_ROOT}"
printf 'Log dir      : %s\n' "${LOG_DIR}"
printf 'Autosave     : %s\n' "${AUTOSAVE_ARCHIVE}"

if [[ ! -f "${FEATURE_DATA_DIR}/northstar_features.parquet" ]]; then
  printf 'FATAL: feature dataset not found at %s\n' "${FEATURE_DATA_DIR}"
  exit 2
fi

SEQUENCE_AVAILABLE=1
if [[ ! -f "${SEQUENCE_DATA_DIR}/sequence_walk_forward_splits.json" || ! -d "${SEQUENCE_DATA_DIR}/sequence_shards" ]]; then
  SEQUENCE_AVAILABLE=0
  printf 'WARNING: sequence dataset not found at %s\n' "${SEQUENCE_DATA_DIR}"
  printf 'Attach aryakghoshal/northstar-v3-sequence-export or set REQUIRE_SEQUENCE=0 to run tabular only.\n'
  if [[ "${REQUIRE_SEQUENCE}" == "1" ]]; then
    printf 'FATAL: sequence dataset is required for the full suite.\n'
    exit 2
  fi
fi

PREFLIGHT_ARGS=()
if [[ "${REQUIRE_CUDA:-1}" == "1" ]]; then
  PREFLIGHT_ARGS+=(--require-cuda)
fi
python "${SCRIPT_DIR}/run4_preflight.py" \
  --feature-dir "${FEATURE_DATA_DIR}" \
  --sequence-dir "${SEQUENCE_DATA_DIR}" \
  --code-dir "${SCRIPT_DIR}" \
  "${PREFLIGHT_ARGS[@]}" || exit 2

# Core tabular configuration sweep.
run_job "EXP-09_run4b_depthwise_min_leaf_sweep" "${OUTPUT_ROOT}/exp_09" \
  python "${PLAN_DIR}/run_experiment.py" EXP-09 \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_09" \
    --feature-policy full \
    "${MAX_WINDOWS_ARG[@]}"

# Modular tabular experiments EXP-10..EXP-19.
run_job "EXP-10_row_subsample_ic_screen" "${OUTPUT_ROOT}/exp_10" \
  python "${RUN3_DIR}/exp_10_run3_l2_ic_screen.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_10" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-11_closed_boosting_type" "${OUTPUT_ROOT}/exp_11" \
  python "${RUN3_DIR}/exp_11_run3_boosting_type.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_11" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-12_train_window_length" "${OUTPUT_ROOT}/exp_12" \
  python "${RUN3_DIR}/exp_12_run3_train_window_length.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_12" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-13_financial_services" "${OUTPUT_ROOT}/exp_13" \
  python "${RUN3_DIR}/exp_13_run3_financial_services.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_13" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-14_it_fx" "${OUTPUT_ROOT}/exp_14" \
  python "${RUN3_DIR}/exp_14_run3_it_fx.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_14" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-15_capital_goods" "${OUTPUT_ROOT}/exp_15" \
  python "${RUN3_DIR}/exp_15_run3_capital_goods.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_15" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-16_sector_blend" "${OUTPUT_ROOT}/exp_16" \
  python "${RUN3_DIR}/exp_16_run3_sector_blend.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_16" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-17_factor_regime_heatmap" "${OUTPUT_ROOT}/exp_17" \
  python "${RUN3_DIR}/exp_17_run3_factor_regime_heatmap.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_17" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-18_universal_diagnostics" "${OUTPUT_ROOT}/exp_18" \
  python "${RUN3_DIR}/exp_18_run3_universal_diagnostics.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_18" \
    "${MAX_WINDOWS_ARG[@]}"

run_job "EXP-19_regime_routing" "${OUTPUT_ROOT}/exp_19" \
  python "${RUN3_DIR}/exp_19_run3_regime_routing.py" \
    --data-dir "${FEATURE_DATA_DIR}" \
    --output-dir "${OUTPUT_ROOT}/exp_19" \
    "${MAX_WINDOWS_ARG[@]}"

# True sequence experiments on the new tensor export.
if [[ "${SEQUENCE_AVAILABLE}" == "1" ]]; then
  for exp_id in EXP-20 EXP-21 EXP-22 EXP-23; do
    lower="$(printf '%s' "${exp_id}" | tr '[:upper:]' '[:lower:]')"
    run_job "${exp_id}_sequence_model" "${OUTPUT_ROOT}/${lower}" \
      python "${SEQ_DIR_CODE}/run_sequence_experiment.py" "${exp_id}" \
        --sequence-dir "${SEQUENCE_DATA_DIR}" \
        --output-dir "${OUTPUT_ROOT}/sequence_models" \
        --epochs "${SEQ_EPOCHS:-8}" \
        --batch-size "${SEQ_BATCH_SIZE:-512}" \
        ${SEQ_ALLOW_CPU:+--allow-cpu} \
        "${MAX_WINDOWS_ARG[@]}" \
        "${SEQ_EXTRA_ARGS[@]}"
  done
else
  printf 'Skipping EXP-20..EXP-23 because sequence dataset is unavailable and REQUIRE_SEQUENCE=0.\n'
fi

# Lightweight diagnostics and validation experiments. Run 4 proper stops at
# EXP-24; EXP-25..27 are deliberately excluded unless RUN_EXTRA_DIAGNOSTICS=1.
DIAG_EXPERIMENTS=(EXP-24)
if [[ "${RUN_EXTRA_DIAGNOSTICS:-0}" == "1" ]]; then
  DIAG_EXPERIMENTS+=(EXP-25 EXP-26 EXP-27)
fi
for exp_id in "${DIAG_EXPERIMENTS[@]}"; do
  lower="$(printf '%s' "${exp_id}" | tr '[:upper:]' '[:lower:]')"
  run_job "${exp_id}_diagnostic" "${OUTPUT_ROOT}/${lower}" \
    python "${PLAN_DIR}/run_experiment.py" "${exp_id}" \
      --data-dir "${FEATURE_DATA_DIR}" \
      --output-dir "${OUTPUT_ROOT}/${lower}" \
      --feature-policy full \
      "${MAX_WINDOWS_ARG[@]}"
done

printf '\nDONE. Status file: %s\n' "${STATUS_CSV}"
printf 'Results root: %s\n' "${OUTPUT_ROOT}"
printf 'Logs root: %s\n' "${LOG_DIR}"
autosave_archive "${FINAL_ARCHIVE}"
printf 'Final archive: %s\n' "${FINAL_ARCHIVE}"
autosave_kaggle_dataset
