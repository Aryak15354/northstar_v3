#!/bin/bash
# Launch the canonical Northstar V3 integrated dashboard

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📊 Launching Northstar V3 Canonical Dashboard..."
echo "==============================================="
echo ""
echo "Dashboard will open at:"
echo "http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo ""

python3 -m streamlit run src/dashboard/app.py --server.port 8501 --server.address localhost
