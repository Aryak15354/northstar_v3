#!/usr/bin/env bash
# Run the focused Northstar Run 7 suite after Run 6 diagnostics.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLAN_DIR="${SCRIPT_DIR}/plan_2026_05_18_production"
RUN3_DIR="${SCRIPT_DIR}/run3_experiment_scripts"
SEQ_DIR_CODE="${SCRIPT_DIR}/sequence_experiments"

FEATURE_DATA_DIR="${FEATURE_DATA_DIR:-/kaggle/input/datasets/aryakghoshal/northstar-v3-feature-export-complete}"
SEQUENCE_DATA_DIR="${SEQUENCE_DATA_DIR:-/kaggle/input/datasets/aryakghoshal/northstar-v3-sequence-export-complete}"
OUTPUT_ROOT="${OUTPUT_ROOT:-/kaggle/working/northstar_run7_focused_results}"
LOG_DIR="${LOG_DIR:-/kaggle/working/northstar_run7_focused_logs}"
AUTOSAVE_ARCHIVE="${AUTOSAVE_ARCHIVE:-/kaggle/working/northstar_run7_focused_latest.tar.gz}"
FINAL_ARCHIVE="${FINAL_ARCHIVE:-/kaggle/working/northstar_run7_focused_final.tar.gz}"
AUTOSAVE_KAGGLE_DATASET_ID="${AUTOSAVE_KAGGLE_DATASET_ID:-}"

MAX_WINDOWS_ARG=()
if [[ -n "${MAX_WINDOWS:-}" ]]; then
  MAX_WINDOWS_ARG=(--max-windows "${MAX_WINDOWS}")
fi

SEQ_EXTRA_ARGS=()
if [[ "${SEQ_AMP:-1}" == "1" ]]; then SEQ_EXTRA_ARGS+=(--amp); fi
if [[ "${SEQ_SINGLE_GPU:-0}" == "1" ]]; then SEQ_EXTRA_ARGS+=(--single-gpu); fi
if [[ -n "${SEQ_NUM_WORKERS:-}" ]]; then SEQ_EXTRA_ARGS+=(--num-workers "${SEQ_NUM_WORKERS}"); fi
if [[ "${SEQ_INCLUDE_MASK:-0}" == "1" ]]; then SEQ_EXTRA_ARGS+=(--include-mask); fi
if [[ -n "${SEQ_MAX_TRAIN_SAMPLES:-}" ]]; then SEQ_EXTRA_ARGS+=(--max-train-samples "${SEQ_MAX_TRAIN_SAMPLES}"); fi
if [[ -n "${SEQ_MAX_TEST_SAMPLES:-}" ]]; then SEQ_EXTRA_ARGS+=(--max-test-samples "${SEQ_MAX_TEST_SAMPLES}"); fi

mkdir -p "${OUTPUT_ROOT}" "${LOG_DIR}"
STATUS_CSV="${OUTPUT_ROOT}/run_status.csv"
printf 'experiment,status,started_at,finished_at,log_file,output_dir\n' > "${STATUS_CSV}"

autosave_archive() {
  local archive_path="$1"
  local parent
  parent="$(dirname "${OUTPUT_ROOT}")"
  if [[ "${parent}" == "$(dirname "${LOG_DIR}")" ]]; then
    tar -czf "${archive_path}" -C "${parent}" "$(basename "${OUTPUT_ROOT}")" "$(basename "${LOG_DIR}")" 2>/dev/null || true
  fi
  [[ -f "${archive_path}" ]] && printf 'AUTOSAVED archive: %s\n' "${archive_path}"
}

autosave_kaggle_dataset() {
  [[ -z "${AUTOSAVE_KAGGLE_DATASET_ID}" ]] && return 0
  command -v kaggle >/dev/null 2>&1 || return 0
  local staging="/kaggle/working/northstar_run7_focused_autosave"
  local title
  title="$(printf '%s' "${AUTOSAVE_KAGGLE_DATASET_ID}" | awk -F/ '{print $2}')"
  rm -rf "${staging}" 2>/dev/null || true
  mkdir -p "${staging}"
  cp "${FINAL_ARCHIVE}" "${staging}/northstar_run7_focused_final.tar.gz" 2>/dev/null || true
  cp "${AUTOSAVE_ARCHIVE}" "${staging}/northstar_run7_focused_latest.tar.gz" 2>/dev/null || true
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
    kaggle datasets version -p "${staging}" -m "Northstar Run 7 focused autosave" --dir-mode zip || true
  else
    kaggle datasets create -p "${staging}" --dir-mode zip || true
  fi
}

run_job() {
  local name="$1"; local out_dir="$2"; shift 2
  local log_file="${LOG_DIR}/${name}.log"
  local started finished status
  started="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  mkdir -p "${out_dir}"
  printf '\n============================================================\nRUNNING %s\nLOG     %s\nOUTPUT  %s\n============================================================\n' "${name}" "${log_file}" "${out_dir}"
  "$@" 2>&1 | tee "${log_file}"
  status="${PIPESTATUS[0]}"
  finished="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  printf '%s,%s,%s,%s,%s,%s\n' "${name}" "${status}" "${started}" "${finished}" "${log_file}" "${out_dir}" >> "${STATUS_CSV}"
  autosave_archive "${AUTOSAVE_ARCHIVE}"
  [[ "${status}" -ne 0 ]] && printf 'WARNING: %s exited with status %s. Continuing.\n' "${name}" "${status}"
}

printf 'Northstar Run 7 focused suite\n'
printf 'Feature data : %s\n' "${FEATURE_DATA_DIR}"
printf 'Sequence data: %s\n' "${SEQUENCE_DATA_DIR}"
printf 'Output root  : %s\n' "${OUTPUT_ROOT}"
printf 'Log dir      : %s\n' "${LOG_DIR}"
printf 'Seq AMP      : %s\n' "${SEQ_AMP:-1}"
printf 'Seq workers  : %s\n' "${SEQ_NUM_WORKERS:-2}"
printf 'Experiments  : EXP-09 EXP-10 EXP-12 EXP-13 EXP-14 EXP-19 EXP-21 EXP-23\n'

[[ ! -f "${FEATURE_DATA_DIR}/northstar_features.parquet" ]] && { echo "FATAL: feature dataset missing"; exit 2; }
[[ ! -f "${SEQUENCE_DATA_DIR}/sequence_walk_forward_splits.json" ]] && { echo "FATAL: sequence dataset missing"; exit 2; }

python "${SCRIPT_DIR}/run4_preflight.py" \
  --feature-dir "${FEATURE_DATA_DIR}" \
  --sequence-dir "${SEQUENCE_DATA_DIR}" \
  --code-dir "${SCRIPT_DIR}" \
  ${REQUIRE_CUDA:+--require-cuda} || exit 2

run_job "EXP-09_multifamily_gate" "${OUTPUT_ROOT}/exp_09" python "${PLAN_DIR}/run_experiment.py" EXP-09 --data-dir "${FEATURE_DATA_DIR}" --output-dir "${OUTPUT_ROOT}/exp_09" --feature-policy full "${MAX_WINDOWS_ARG[@]}"
run_job "EXP-10_row_subsample_family_gate" "${OUTPUT_ROOT}/exp_10" python "${RUN3_DIR}/exp_10_run3_l2_ic_screen.py" --data-dir "${FEATURE_DATA_DIR}" --output-dir "${OUTPUT_ROOT}/exp_10" "${MAX_WINDOWS_ARG[@]}"
run_job "EXP-12_train_window_length" "${OUTPUT_ROOT}/exp_12" python "${RUN3_DIR}/exp_12_run3_train_window_length.py" --data-dir "${FEATURE_DATA_DIR}" --output-dir "${OUTPUT_ROOT}/exp_12" "${MAX_WINDOWS_ARG[@]}"
run_job "EXP-13_financial_services" "${OUTPUT_ROOT}/exp_13" python "${RUN3_DIR}/exp_13_run3_financial_services.py" --data-dir "${FEATURE_DATA_DIR}" --output-dir "${OUTPUT_ROOT}/exp_13" "${MAX_WINDOWS_ARG[@]}"
run_job "EXP-14_it_export_universe" "${OUTPUT_ROOT}/exp_14" python "${RUN3_DIR}/exp_14_run3_it_fx.py" --data-dir "${FEATURE_DATA_DIR}" --output-dir "${OUTPUT_ROOT}/exp_14" "${MAX_WINDOWS_ARG[@]}"
run_job "EXP-19_regime_routing" "${OUTPUT_ROOT}/exp_19" python "${RUN3_DIR}/exp_19_run3_regime_routing.py" --data-dir "${FEATURE_DATA_DIR}" --output-dir "${OUTPUT_ROOT}/exp_19" "${MAX_WINDOWS_ARG[@]}"

for exp_id in EXP-21 EXP-23; do
  lower="$(printf '%s' "${exp_id}" | tr '[:upper:]' '[:lower:]')"
  run_job "${exp_id}_sequence_model" "${OUTPUT_ROOT}/${lower}" \
    python "${SEQ_DIR_CODE}/run_sequence_experiment.py" "${exp_id}" \
      --sequence-dir "${SEQUENCE_DATA_DIR}" \
      --output-dir "${OUTPUT_ROOT}/sequence_models" \
      --epochs "${SEQ_EPOCHS:-8}" \
      --batch-size "${SEQ_BATCH_SIZE:-1024}" \
      ${SEQ_ALLOW_CPU:+--allow-cpu} \
      "${MAX_WINDOWS_ARG[@]}" \
      "${SEQ_EXTRA_ARGS[@]}"
done

printf '\nDONE. Status file: %s\n' "${STATUS_CSV}"
autosave_archive "${FINAL_ARCHIVE}"
printf 'Final archive: %s\n' "${FINAL_ARCHIVE}"
autosave_kaggle_dataset
