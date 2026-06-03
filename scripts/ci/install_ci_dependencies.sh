#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"

"$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
"$PYTHON_BIN" -m pip install -r requirements.txt
"$PYTHON_BIN" -m pip install pytest ruff packaging PyYAML hypothesis
"$PYTHON_BIN" - <<'PY'
import pytest
import yaml

print("ci dependencies ready")
print(f"pytest={getattr(pytest, '__version__', 'unknown')}")
print(f"yaml={getattr(yaml, '__version__', 'unknown')}")
PY
