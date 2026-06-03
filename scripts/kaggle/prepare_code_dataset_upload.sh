#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

DATASET_ID="${1:-${KAGGLE_USERNAME:-}/northstar-v3-code}"
BUNDLE_NAME="${2:-northstar_v3_code_bundle.zip}"
UPLOAD_DIR="${3:-$PROJECT_ROOT/tmp/kaggle_uploads/code_dataset}"
DATASET_TITLE="${4:-Northstar V3 Code}"

if [[ -z "$DATASET_ID" || "$DATASET_ID" == "/northstar-v3-code" ]]; then
  echo "ERROR: dataset id is required."
  echo "Usage: bash scripts/kaggle/prepare_code_dataset_upload.sh <owner/dataset-slug> [bundle-name] [upload-dir] [title]"
  exit 1
fi

mkdir -p "$UPLOAD_DIR"
rm -rf "$UPLOAD_DIR"
mkdir -p "$UPLOAD_DIR"

echo "Preparing Kaggle code dataset upload folder"
echo "=========================================="
echo "Dataset id:   $DATASET_ID"
echo "Bundle name:  $BUNDLE_NAME"
echo "Upload dir:   $UPLOAD_DIR"
echo "Dataset title:$DATASET_TITLE"
echo

bash "$PROJECT_ROOT/scripts/kaggle/upload_code_dataset.sh" "$BUNDLE_NAME"

unzip -o "$PROJECT_ROOT/dist/kaggle/$BUNDLE_NAME" -d "$UPLOAD_DIR" >/dev/null

cat > "$UPLOAD_DIR/dataset-metadata.json" <<EOF
{
  "title": "$DATASET_TITLE",
  "id": "$DATASET_ID",
  "licenses": [{"name": "other"}],
  "isPrivate": true
}
EOF

echo "Prepared files:"
find "$UPLOAD_DIR" -maxdepth 2 -type f | sort
echo
echo "Next command if Kaggle auth is configured:"
echo "kaggle datasets version -p $UPLOAD_DIR -m \"$(basename "$BUNDLE_NAME" .zip) update\""
