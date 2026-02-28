#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

rm -rf .pytest_cache .hypothesis logs/ci || true
rm -rf data/state || true

find . -type d -name '__pycache__' -prune -exec rm -rf {} + || true
find . -type d -name '.mypy_cache' -prune -exec rm -rf {} + || true

mkdir -p logs/ci
mkdir -p data/options/live

find data/options/live -maxdepth 1 -type f \( -name '*.lock' -o -name '*.pid' \) -delete || true
