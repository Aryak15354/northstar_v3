#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGING_DIR="$(mktemp -d)"
OUTPUT_DIR="${PROJECT_ROOT}/dist/kaggle"
BUNDLE_NAME="${1:-northstar_v3_code_bundle.zip}"
ZIP_PATH="${OUTPUT_DIR}/${BUNDLE_NAME}"

mkdir -p "${OUTPUT_DIR}"
trap 'rm -rf "${STAGING_DIR}"' EXIT

if [ -f "${ZIP_PATH}" ]; then
  rm -f "${ZIP_PATH}"
fi

copy_tree() {
  local src="$1"
  local dst="$2"
  if [ ! -d "${src}" ]; then
    return 0
  fi
  mkdir -p "$(dirname "${dst}")"
  cp -R "${src}" "${dst}"
}

echo "Northstar V3 - Kaggle code bundle"
echo "================================="
echo "Project root: ${PROJECT_ROOT}"

copy_tree "${PROJECT_ROOT}/configs" "${STAGING_DIR}/configs"
copy_tree "${PROJECT_ROOT}/src" "${STAGING_DIR}/src"
copy_tree "${PROJECT_ROOT}/scripts" "${STAGING_DIR}/scripts"
copy_tree "${PROJECT_ROOT}/notebooks/kaggle_sprint/shared" "${STAGING_DIR}/notebooks/kaggle_sprint/shared"
copy_tree "${PROJECT_ROOT}/data/canonical/reference/regimes" "${STAGING_DIR}/data/canonical/reference/regimes"

if [ -f "${PROJECT_ROOT}/requirements.txt" ]; then
  cp "${PROJECT_ROOT}/requirements.txt" "${STAGING_DIR}/requirements.txt"
fi
if [ -f "${PROJECT_ROOT}/README.md" ]; then
  cp "${PROJECT_ROOT}/README.md" "${STAGING_DIR}/README.md"
fi

python3 - <<'PY' "${STAGING_DIR}"
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
for folder in [root / "src" / "__pycache__", root / "scripts" / "__pycache__"]:
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
for path in root.rglob("__pycache__"):
    shutil.rmtree(path, ignore_errors=True)
cleanup_patterns = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.tmp",
    "*.swp",
    "*.swo",
    "*.orig",
    "*.rej",
    "*.bak*",
    "*.save*",
    "*~",
    ".DS_Store",
    "*.yamlES",
    "*.ymlES",
]
for pattern in cleanup_patterns:
    for path in root.rglob(pattern):
        path.unlink(missing_ok=True)
PY

(
  cd "${STAGING_DIR}"
  zip -qr "${ZIP_PATH}" .
)

SIZE_BYTES="$(stat -f%z "${ZIP_PATH}")"
SIZE_MB="$(python3 - <<'PY' "${SIZE_BYTES}"
import sys
size = int(sys.argv[1])
print(f"{size / (1024 * 1024):.2f}")
PY
)"

echo "Bundle written to: ${ZIP_PATH}"
echo "Bundle size: ${SIZE_MB} MB"
echo
echo "Included roots:"
echo "- configs/"
echo "- src/"
echo "- scripts/"
echo "- notebooks/kaggle_sprint/shared/"
echo "- data/canonical/reference/regimes/"
echo

python3 - <<'PY' "${ZIP_PATH}"
from pathlib import Path
import sys
import zipfile

bundle = Path(sys.argv[1]).resolve()
with zipfile.ZipFile(bundle) as zf:
    names = sorted(zf.namelist())
    print("Top-level entries:")
    for name in names[:25]:
        print(f"  {name}")
PY

python3 - <<'PY' "${ZIP_PATH}"
from pathlib import Path
import sys
bundle = Path(sys.argv[1]).resolve()
threshold_mb = 10.0
size_mb = bundle.stat().st_size / (1024 * 1024)
if size_mb > threshold_mb:
    print(f"WARNING: bundle exceeds {threshold_mb:.0f} MB target ({size_mb:.2f} MB).")
else:
    print(f"Bundle is within the 10 MB target ({size_mb:.2f} MB).")
PY

echo
echo "Next steps:"
echo "1. Upload the zip contents as the Kaggle code dataset layer."
echo "2. Re-upload only this bundle when configs/scripts/src change."
echo "3. Keep raw data and feature exports in separate Kaggle datasets."
