#!/bin/bash

echo "🎯 LAUNCHING ULTIMATE NORTHSTAR V3 DASHBOARD"
echo "============================================================"
echo "🌟 ULTIMATE FEATURES:"
echo "   📊 Comprehensive time-series analysis with 365 days of data"
echo "   🔥 Functional stress testing with persistent result storage"
echo "   🚶 Advanced walk-forward validation with detailed analysis"
echo "   📈 Extensive charts, graphs, and visualizations"
echo "   🧠 Machine learning insights and model performance"
echo "   ⚖️ Advanced risk analysis with VaR, correlation, liquidity"
echo "   🏢 Sector evolution tracking and allocation changes"
echo "   🎯 Market regime analysis and transition probabilities"
echo "   🔬 Multi-factor analysis and attribution"
echo "   📊 Performance attribution and optimization insights"
echo "   🎛️ Interactive validation system with comparison tools"
echo "============================================================"
echo "🌐 Dashboard will be available at: http://localhost:8514"
echo "🛑 Press Ctrl+C to stop the dashboard"
echo "============================================================"

# Navigate to project root
cd "$(dirname "$0")/.."

# Launch the ultimate dashboard
python -m streamlit run src/dashboard/ultimate_northstar_dashboard.py --server.port 8514 --server.headless true --browser.gatherUsageStats false