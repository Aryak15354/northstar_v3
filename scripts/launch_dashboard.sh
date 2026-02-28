#!/bin/bash
# Launch Northstar Command Bridge Dashboard

echo "🧭 Launching Northstar Command Bridge..."
echo "=========================================="
echo ""
echo "Dashboard will open in your browser at:"
echo "http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the dashboard"
echo ""

streamlit run src/dashboard/northstar_command_bridge.py
