#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

SOURCE_DIR="${1:-}"
DATASET_ID="${2:-${KAGGLE_USERNAME:-}/northstar-v3-feature-chunks}"
UPLOAD_DIR="${3:-$PROJECT_ROOT/tmp/kaggle_uploads/feature_chunk_dataset}"
DATASET_TITLE="${4:-Northstar V3 Feature Chunks}"

if [[ -z "$SOURCE_DIR" ]]; then
  echo "ERROR: source chunk directory is required."
  echo "Usage: bash scripts/kaggle/prepare_feature_chunk_dataset_upload.sh <chunk-output-dir> <owner/dataset-slug> [upload-dir] [title]"
  exit 1
fi

if [[ -z "$DATASET_ID" || "$DATASET_ID" == "/northstar-v3-feature-chunks" ]]; then
  echo "ERROR: dataset id is required."
  echo "Usage: bash scripts/kaggle/prepare_feature_chunk_dataset_upload.sh <chunk-output-dir> <owner/dataset-slug> [upload-dir] [title]"
  exit 1
fi

SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"

required_paths=(
  "local_chunked_dataset_manifest.json"
  "plan_signal_audit.json"
  "feature_unit_registry.json"
  "northstar_walk_forward_splits.json"
  "features_chunks"
  "metadata_chunks"
  "regime_chunks"
  "chunk_manifests"
)

for rel in "${required_paths[@]}"; do
  if [[ ! -e "$SOURCE_DIR/$rel" ]]; then
    echo "ERROR: missing required artifact: $SOURCE_DIR/$rel"
    exit 1
  fi
done

rm -rf "$UPLOAD_DIR"
mkdir -p "$UPLOAD_DIR"

link_or_copy_file() {
  local src="$1"
  local dst="$2"
  mkdir -p "$(dirname "$dst")"
  if ! ln "$src" "$dst" 2>/dev/null; then
    cp -p "$src" "$dst"
  fi
}

link_or_copy_tree() {
  local src_root="$1"
  local dst_root="$2"
  mkdir -p "$dst_root"
  while IFS= read -r -d '' src; do
    local rel="${src#"$src_root"/}"
    local dst="$dst_root/$rel"
    link_or_copy_file "$src" "$dst"
  done < <(find "$src_root" -type f -print0 | sort -z)
}

for file_name in \
  local_chunked_dataset_manifest.json \
  plan_signal_audit.json \
  feature_unit_registry.json \
  northstar_walk_forward_splits.json; do
  link_or_copy_file "$SOURCE_DIR/$file_name" "$UPLOAD_DIR/$file_name"
done

for dir_name in features_chunks metadata_chunks regime_chunks chunk_manifests; do
  link_or_copy_tree "$SOURCE_DIR/$dir_name" "$UPLOAD_DIR/$dir_name"
done

cat > "$UPLOAD_DIR/dataset-metadata.json" <<EOF
{
  "title": "$DATASET_TITLE",
  "id": "$DATASET_ID",
  "licenses": [{"name": "other"}],
  "isPrivate": true
}
EOF

echo "Prepared Kaggle feature chunk upload folder"
echo "==========================================="
echo "Source dir:   $SOURCE_DIR"
echo "Dataset id:   $DATASET_ID"
echo "Upload dir:   $UPLOAD_DIR"
echo "Dataset title:$DATASET_TITLE"
echo
echo "Files prepared:"
find "$UPLOAD_DIR" -maxdepth 2 -type f | sort
echo
echo "Next command if Kaggle auth is configured:"
echo "kaggle datasets version -p $UPLOAD_DIR -m \"feature chunk refresh $(date +%Y-%m-%d)\" --dir-mode zip"
