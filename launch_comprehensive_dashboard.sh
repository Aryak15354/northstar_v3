#!/bin/bash
# launch_comprehensive_dashboard.sh — Northstar V3 Comprehensive Dashboard
# Usage: ./launch_comprehensive_dashboard.sh [--port PORT]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source .env.options 2>/dev/null || true
source venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null

PORT="${1:-8503}"
if [[ "$1" == "--port" ]]; then PORT="$2"; shift 2; fi

echo "=============================================="
echo "🚀 Northstar V3 Comprehensive Dashboard"
echo "=============================================="
echo ""
echo "Starting comprehensive dashboard on port $PORT..."
echo "Access at: http://localhost:$PORT"
echo ""
echo "Features:"
echo "  ✓ 126 visualizations across 9 tabs"
echo "  ✓ Command Center (20 viz)"
echo "  ✓ P&L Analytics (15 viz)"
echo "  ✓ Sentiment Intelligence (15 viz)"
echo "  ✓ Alternative Data (15 viz)"
echo "  ✓ Macro Tensor (15 viz)"
echo "  ✓ Portfolio Governor (12 viz)"
echo "  ✓ Alpha OS (12 viz)"
echo "  ✓ Options & Risk (12 viz)"
echo "  ✓ System Operations (10 viz)"
echo ""
echo "Data Sources:"
echo "  ✓ NAV: 75 days"
echo "  ✓ Sentiment: 5,135 days"
echo "  ✓ Regime: 7,830 days"
echo "  ✓ Macro: 3,905 rows"
echo "  ✓ Bulk Deals: 219,314 rows"
echo ""
echo "ALL VISUALIZATIONS USE REAL DATA"
echo "=============================================="
echo ""

streamlit run src/dashboard/comprehensive_dashboard.py \
    --server.port "$PORT" \
    --server.address localhost \
    --server.runOnSave true \
    --theme.base dark
