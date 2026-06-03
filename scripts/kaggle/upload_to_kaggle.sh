#!/bin/bash
set -euo pipefail

EXPORT_DIR="${1:-$HOME/Desktop/northstar_kaggle_data}"
DATASET_NAME="northstar-v4-validation-data"
NOTEBOOKS_DIR="notebooks/kaggle_v4_validation"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UTILS_FILE="$PROJECT_ROOT/notebooks/kaggle_v4_validation/utils/northstar_kaggle_utils.py"
SPRINT_UTILS_FILE="$PROJECT_ROOT/notebooks/kaggle_sprint/shared/sprint_utils.py"
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGING_DIR"' EXIT

resolve_kaggle_bin() {
    if command -v kaggle >/dev/null 2>&1; then
        command -v kaggle
        return 0
    fi

    if [ -x "/Library/Frameworks/Python.framework/Versions/3.13/bin/kaggle" ]; then
        echo "/Library/Frameworks/Python.framework/Versions/3.13/bin/kaggle"
        return 0
    fi

    return 1
}

resolve_kaggle_username() {
    if [ -n "${KAGGLE_USERNAME:-}" ]; then
        printf '%s\n' "$KAGGLE_USERNAME"
        return 0
    fi

    python3 - <<'PY'
import contextlib
import io
import sys
from kaggle.api.kaggle_api_extended import KaggleApi

api = KaggleApi()
buffer = io.StringIO()
try:
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        api.authenticate()
except SystemExit:
    sys.exit(1)
username = api.get_config_value(api.CONFIG_NAME_USER)
if username:
    print(username)
    sys.exit(0)
sys.exit(1)
PY
}

echo "Northstar V4 - Kaggle Upload Helper"
echo "====================================="

KAGGLE_BIN="$(resolve_kaggle_bin || true)"
if [ -z "$KAGGLE_BIN" ]; then
    echo "ERROR: Could not find the Kaggle CLI executable."
    echo "Install it with: python3 -m pip install --upgrade kaggle"
    echo "Then either add it to PATH or re-run this script."
    exit 1
fi

if [ -f "$HOME/.kaggle/kaggle.json" ]; then
    chmod 600 "$HOME/.kaggle/kaggle.json"
fi
if [ -f "$HOME/.kaggle/access_token" ]; then
    chmod 600 "$HOME/.kaggle/access_token"
fi
if [ -f "$HOME/.kaggle/access_token.txt" ]; then
    chmod 600 "$HOME/.kaggle/access_token.txt"
fi

if [ ! -f "$HOME/.kaggle/kaggle.json" ] && [ -z "${KAGGLE_API_TOKEN:-}" ] \
   && [ ! -f "$HOME/.kaggle/access_token" ] && [ ! -f "$HOME/.kaggle/access_token.txt" ]; then
    echo "ERROR: No Kaggle credentials found."
    echo "Use one of these auth methods before running the upload:"
    echo "  1. Legacy API key file: ~/.kaggle/kaggle.json"
    echo "  2. Access token env var: export KAGGLE_API_TOKEN=..."
    echo "  3. Access token file: ~/.kaggle/access_token"
    exit 1
fi

if [ ! -d "$EXPORT_DIR" ]; then
    echo "ERROR: Export directory not found: $EXPORT_DIR"
    echo "Run first: python3 scripts/kaggle/export_kaggle_data.py --output-dir $EXPORT_DIR"
    exit 1
fi

for f in northstar_features.parquet northstar_walk_forward_splits.json northstar_regime_labels.parquet; do
    if [ ! -f "$EXPORT_DIR/$f" ]; then
        echo "ERROR: Missing required file: $EXPORT_DIR/$f"
        exit 1
    fi
done

echo "Export verification:"
python3 - <<'PY' "$EXPORT_DIR"
from pathlib import Path
import json
import pandas as pd
import sys

export_dir = Path(sys.argv[1]).expanduser().resolve()
manifest_path = export_dir / "northstar_export_manifest.json"
features_path = export_dir / "northstar_features.parquet"

if manifest_path.exists():
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(
            f"  manifest: rows={payload.get('n_rows')} "
            f"tickers={payload.get('n_tickers')} "
            f"date_range={payload.get('date_min')}..{payload.get('date_max')}"
        )
    except Exception as exc:
        print(f"  manifest: unreadable ({exc})")

frame = pd.read_parquet(features_path, columns=["date", "ticker"])
frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
print(
    f"  parquet: rows={len(frame)} "
    f"tickers={frame['ticker'].astype(str).nunique()} "
    f"date_range={frame['date'].min()}..{frame['date'].max()}"
)
PY

if [ ! -f "$UTILS_FILE" ]; then
    echo "ERROR: Shared utils file not found: $UTILS_FILE"
    exit 1
fi

if [ -f "$SPRINT_UTILS_FILE" ]; then
    echo "Sprint utils found: $SPRINT_UTILS_FILE"
else
    echo "WARNING: Sprint utils file not found yet: $SPRINT_UTILS_FILE"
fi

echo "Export directory: $EXPORT_DIR"
echo "Files:"
ls -lh "$EXPORT_DIR"

cp "$EXPORT_DIR"/northstar_features.parquet "$STAGING_DIR/"
cp "$EXPORT_DIR"/northstar_walk_forward_splits.json "$STAGING_DIR/"
cp "$EXPORT_DIR"/northstar_regime_labels.parquet "$STAGING_DIR/"
cp "$UTILS_FILE" "$STAGING_DIR/"
if [ -f "$SPRINT_UTILS_FILE" ]; then
    cp "$SPRINT_UTILS_FILE" "$STAGING_DIR/"
fi
if [ -f "$EXPORT_DIR/northstar_export_manifest.json" ]; then
    cp "$EXPORT_DIR/northstar_export_manifest.json" "$STAGING_DIR/"
fi

KAGGLE_USERNAME="$(resolve_kaggle_username 2>/dev/null | tail -n 1 | tr -d '\r')"
if [ -z "$KAGGLE_USERNAME" ]; then
    echo "ERROR: Could not determine your Kaggle username."
    echo "Set it explicitly and retry:"
    echo "  export KAGGLE_USERNAME=<your-kaggle-username>"
    exit 1
fi

cat > "$STAGING_DIR/dataset-metadata.json" << EOF
{
  "title": "Northstar V4 Validation Data",
  "id": "$KAGGLE_USERNAME/$DATASET_NAME",
  "licenses": [{"name": "other"}],
  "isPrivate": true
}
EOF

echo ""
echo "Uploading to Kaggle..."
if "$KAGGLE_BIN" datasets list --mine 2>/dev/null | grep -q "$DATASET_NAME"; then
    echo "Dataset exists - creating new version..."
    "$KAGGLE_BIN" datasets version -p "$STAGING_DIR" -m "Northstar V4 validation refresh $(date +%Y-%m-%d)" --dir-mode zip
else
    echo "Creating new dataset..."
    "$KAGGLE_BIN" datasets create -p "$STAGING_DIR" --dir-mode zip
fi

echo ""
echo "Upload complete."
echo ""
echo "Next steps:"
echo "1. Open Kaggle -> Code -> New Notebook."
echo "2. Upload notebooks/kaggle_sprint/unified/notebook_unified.ipynb"
echo "3. In the notebook: Add Data -> search '$DATASET_NAME' -> attach the private dataset."
echo "4. Settings -> Accelerator -> GPU T4 x2."
echo "5. Run the unified notebook end-to-end."
echo "6. After it finishes, click Save Version so the outputs are persisted."
echo ""
echo "Tip: the dataset upload also includes northstar_kaggle_utils.py at the dataset root,"
echo "and, when present, sprint_utils.py at the dataset root so the sprint notebooks"
echo "can import both helper modules without any manual file copying on Kaggle."
