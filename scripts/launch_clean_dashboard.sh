#!/bin/bash

echo "🎯 LAUNCHING CLEAN NORTHSTAR V3 DASHBOARD"
echo "=================================================="
echo "🌐 Dashboard will be available at: http://localhost:8513"
echo "🛑 Press Ctrl+C to stop the dashboard"
echo "=================================================="

# Navigate to project root
cd "$(dirname "$0")/.."

# Launch the clean dashboard
python -m streamlit run src/dashboard/clean_northstar_dashboard.py --server.port 8513 --server.headless true --browser.gatherUsageStats false