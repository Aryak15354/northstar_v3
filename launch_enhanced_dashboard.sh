#!/bin/bash
# launch_enhanced_dashboard.sh — Northstar V3 Enhanced Dashboard
# Usage: ./launch_enhanced_dashboard.sh [--port PORT]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source .env.options 2>/dev/null || true
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null

PORT="${1:-8502}"
if [[ "$1" == "--port" ]]; then PORT="$2"; shift 2; fi

echo "=============================================="
echo "🚀 Northstar V3 Enhanced Dashboard"
echo "=============================================="
echo ""
echo "Starting enhanced dashboard on port $PORT..."
echo "Access at: http://localhost:$PORT"
echo ""
echo "Features:"
echo "  ✓ Command Center with real-time metrics"
echo "  ✓ Intelligence & Regime Analysis"
echo "  ✓ Portfolio Governor View"
echo "  ✓ Performance & Attribution"
echo "  ✓ Options System"
echo "  ✓ System Operations"
echo ""
echo "ALL VISUALIZATIONS USE REAL DATA"
echo "=============================================="
echo ""

streamlit run src/dashboard/enhanced_dashboard.py \
    --server.port "$PORT" \
    --server.address localhost \
    --server.runOnSave true \
    --theme.base dark
