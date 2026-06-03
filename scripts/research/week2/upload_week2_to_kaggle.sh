#!/bin/bash
set -euo pipefail

EXPORT_DIR="${1:-$HOME/Desktop/northstar_kaggle_data_v2}"
DATASET_NAME="northstar-v4-week2"

KAGGLE_CMD=()
if command -v kaggle >/dev/null 2>&1; then
    KAGGLE_CMD=(kaggle)
elif [ -x "/Library/Frameworks/Python.framework/Versions/3.13/bin/kaggle" ]; then
    KAGGLE_CMD=(/Library/Frameworks/Python.framework/Versions/3.13/bin/kaggle)
elif [ -x "/usr/local/bin/kaggle" ]; then
    KAGGLE_CMD=(/usr/local/bin/kaggle)
elif python3 - <<'PY' >/dev/null 2>&1
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec("kaggle") is not None else 1)
PY
then
    KAGGLE_CMD=(python3 -m kaggle)
else
    echo "ERROR: Kaggle CLI not found."
    echo "Install it with: python3 -m pip install kaggle"
    echo "Or add the kaggle executable to your PATH."
    exit 1
fi

KAGGLE_USERNAME_VALUE="${KAGGLE_USERNAME:-}"
if [ -z "$KAGGLE_USERNAME_VALUE" ] && [ -f "$HOME/.kaggle/kaggle.json" ]; then
    KAGGLE_USERNAME_VALUE="$(python3 - <<'PY'
import json
from pathlib import Path

path = Path.home() / ".kaggle" / "kaggle.json"
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
print(str(payload.get("username", "")).strip())
PY
)"
fi

if [ -z "$KAGGLE_USERNAME_VALUE" ]; then
    KAGGLE_USERNAME_VALUE="$(python3 - <<'PY'
import importlib.util

if importlib.util.find_spec("kaggle") is None:
    raise SystemExit(0)

try:
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()

    username = ""
    if hasattr(api, "get_config_value"):
        try:
            username = api.get_config_value("username") or ""
        except Exception:
            username = ""
    if not username:
        username = str((getattr(api, "config_values", {}) or {}).get("username", "")).strip()
    print(username)
except Exception:
    pass
PY
)"
fi

if [ -z "$KAGGLE_USERNAME_VALUE" ]; then
    echo "ERROR: Could not determine Kaggle username."
    echo "Set KAGGLE_USERNAME, place kaggle.json in ~/.kaggle/kaggle.json,"
    echo "or ensure the Kaggle OAuth/access token can be introspected online."
    exit 1
fi

echo "Northstar Week 2 — Kaggle Upload"
echo "================================="
echo "Kaggle command: ${KAGGLE_CMD[*]}"
echo "Kaggle username: $KAGGLE_USERNAME_VALUE"

for f in northstar_features_v2.parquet northstar_features_reduced.parquet \
          northstar_walk_forward_splits.json northstar_regime_labels.parquet; do
    if [ ! -f "$EXPORT_DIR/$f" ]; then
        echo "ERROR: Missing $EXPORT_DIR/$f"
        echo "Run build_new_factors.py and build_reduced_feature_set.py first"
        exit 1
    fi
done

if [ ! -f "$EXPORT_DIR/northstar_factor_metadata_v2.json" ]; then
    echo "ERROR: Missing $EXPORT_DIR/northstar_factor_metadata_v2.json"
    echo "Run build_new_factors.py first"
    exit 1
fi

if [ ! -f "$EXPORT_DIR/northstar_features_reduced_metadata.json" ]; then
    echo "ERROR: Missing $EXPORT_DIR/northstar_features_reduced_metadata.json"
    echo "Run build_reduced_feature_set.py first"
    exit 1
fi

if [ "${NORTHSTAR_ALLOW_UNREADY:-0}" != "1" ]; then
    python3 - <<'PY' "$EXPORT_DIR"
import json
import sys
from pathlib import Path

export_dir = Path(sys.argv[1])
factor_meta = json.loads((export_dir / "northstar_factor_metadata_v2.json").read_text())
ready = bool(factor_meta.get("ready_for_kaggle", False))
dataset_audit = dict(factor_meta.get("dataset_audit", {}) or {})
split_audit = dict(factor_meta.get("split_audit", {}) or {})
power_audit = dict(factor_meta.get("power_audit", {}) or {})

if not ready:
    print("ERROR: Week-2 export is not marked ready for Kaggle.")
    print(f"  dataset_audit: {dataset_audit}")
    print(f"  split_audit:   {split_audit}")
    print(f"  power_audit:   {power_audit}")
    print("Set NORTHSTAR_ALLOW_UNREADY=1 only if you intentionally want to override the readiness gate.")
    raise SystemExit(1)
PY
fi

cp notebooks/kaggle_sprint/shared/sprint_utils.py "$EXPORT_DIR/sprint_utils.py"
cp notebooks/kaggle_v4_validation/utils/northstar_kaggle_utils.py "$EXPORT_DIR/northstar_kaggle_utils.py"
mkdir -p "$EXPORT_DIR/week2_scripts" "$EXPORT_DIR/week2_notebooks"
cp scripts/research/week2/build_new_factors.py "$EXPORT_DIR/week2_scripts/"
cp scripts/research/week2/build_reduced_feature_set.py "$EXPORT_DIR/week2_scripts/"
cp scripts/research/week2/day6_deployment_diagnosis.py "$EXPORT_DIR/week2_scripts/"
cp scripts/research/week2/upload_week2_to_kaggle.sh "$EXPORT_DIR/week2_scripts/"
cp notebooks/kaggle_sprint/week2/*.ipynb "$EXPORT_DIR/week2_notebooks/"

cat > "$EXPORT_DIR/dataset-metadata.json" << EOF
{
  "title": "Northstar V4 Week 2 Validation Data",
  "id": "$KAGGLE_USERNAME_VALUE/northstar-v4-week2",
  "licenses": [{"name": "other"}],
  "isPrivate": true
}
EOF

echo "Files to upload:"
ls -lh "$EXPORT_DIR"

if "${KAGGLE_CMD[@]}" datasets list --mine 2>/dev/null | grep -q "$DATASET_NAME"; then
    echo "Updating existing dataset..."
    "${KAGGLE_CMD[@]}" datasets version -p "$EXPORT_DIR" -m "Week 2: new factors, reduced feature set $(date +%Y-%m-%d)" --dir-mode zip
else
    echo "Creating new dataset..."
    "${KAGGLE_CMD[@]}" datasets create -p "$EXPORT_DIR" --dir-mode zip
fi

echo "Upload complete."
echo "Dataset: $DATASET_NAME"
