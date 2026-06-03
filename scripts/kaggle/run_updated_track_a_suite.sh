#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." 2>/dev/null && pwd || pwd)"
RUNNER=""

for candidate in \
  "$SCRIPT_DIR/run_updated_track_a_experiments.py" \
  "$SCRIPT_DIR/../kaggle/run_updated_track_a_experiments.py" \
  "$ROOT_DIR/scripts/kaggle/run_updated_track_a_experiments.py"
do
  if [[ -f "$candidate" ]]; then
    RUNNER="$candidate"
    break
  fi
done

if [[ -z "$RUNNER" ]]; then
  echo "Could not locate run_updated_track_a_experiments.py next to this wrapper or in scripts/kaggle." >&2
  exit 1
fi

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Usage: $0 <data-dir> [smoke|full] [output-root]" >&2
  exit 1
fi

DATA_DIR="$1"
PROFILE="${2:-full}"
if [[ $# -ge 3 ]]; then
  OUTPUT_ROOT="$3"
elif [[ -d /kaggle/working ]]; then
  OUTPUT_ROOT="/kaggle/working/updated_track_a_experiments"
else
  OUTPUT_ROOT="$ROOT_DIR/tmp/updated_track_a_experiments"
fi

required_files=(
  "northstar_features.parquet"
  "northstar_walk_forward_splits.json"
  "northstar_regime_labels.parquet"
)

for filename in "${required_files[@]}"; do
  if [[ ! -f "$DATA_DIR/$filename" ]]; then
    echo "Missing required export file: $DATA_DIR/$filename" >&2
    exit 1
  fi
done

if [[ "$PROFILE" != "smoke" && "$PROFILE" != "full" ]]; then
  echo "Profile must be either 'smoke' or 'full'." >&2
  exit 1
fi

echo "Running updated Track A suite"
echo "data_dir=$DATA_DIR"
echo "profile=$PROFILE"
echo "output_root=$OUTPUT_ROOT"

python3 "$RUNNER" \
  --data-dir "$DATA_DIR" \
  --output-root "$OUTPUT_ROOT" \
  --experiment tree_baseline \
  --profile "$PROFILE"

python3 "$RUNNER" \
  --data-dir "$DATA_DIR" \
  --output-root "$OUTPUT_ROOT" \
  --experiment tree_reduced \
  --profile "$PROFILE"

python3 "$RUNNER" \
  --data-dir "$DATA_DIR" \
  --output-root "$OUTPUT_ROOT" \
  --experiment sequence_reduced \
  --profile "$PROFILE"

echo "Updated Track A suite finished."
