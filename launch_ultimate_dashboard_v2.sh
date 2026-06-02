#!/bin/bash
# launch_ultimate_dashboard_v2.sh — Northstar V3 Ultimate Dashboard V2
# Usage: ./launch_ultimate_dashboard_v2.sh [--port PORT]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source .env.options 2>/dev/null || true
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null

PORT="${1:-8504}"
if [[ "$1" == "--port" ]]; then PORT="$2"; shift 2; fi

echo "=============================================="
echo "🚀 Northstar V3 Ultimate Dashboard V2"
echo "=============================================="
echo ""
echo "Starting ultimate dashboard V2 on port $PORT..."
echo "Access at: http://localhost:$PORT"
echo ""
echo "Features:"
echo "  ✓ 210 visualizations across 9 tabs"
echo "  ✓ READABLE metrics (42px font, proper spacing)"
echo "  ✓ PROPER timeframes (FII starts from actual data)"
echo "  ✓ Credit Ratings Activity (NEW)"
echo "  ✓ RBI rates (only changing rates shown)"
echo "  ✓ Inflation with target line (enhanced)"
echo "  ✓ Macro Correlations (3-4x LARGER - 1600x1600px)"
echo "  ✓ Portfolio (5-10 NEW visualizations)"
echo "  ✓ Alpha OS (COMPLETELY BUILT - 15 viz)"
echo "  ✓ Options (10-15 NEW with explanations)"
echo "  ✓ System Health (enhanced)"
echo "  ✓ Every section: 5-10 additional graphs"
echo ""
echo "ALL VISUALIZATIONS USE REAL DATA"
echo "=============================================="
echo ""

streamlit run src/dashboard/ultimate_dashboard_v2.py \
    --server.port "$PORT" \
    --server.address localhost \
    --server.runOnSave true \
    --theme.base dark
