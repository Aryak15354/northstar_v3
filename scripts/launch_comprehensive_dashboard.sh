#!/bin/bash

echo "🎯 LAUNCHING COMPREHENSIVE NORTHSTAR V3 DASHBOARD"
echo "============================================================"
echo "🚀 Features:"
echo "   📊 Extensive time-series analysis with 365 days of data"
echo "   🧪 Functional stress testing with real result storage"
echo "   🚶 Walk-forward validation with period-by-period analysis"
echo "   📈 Comprehensive performance attribution over time"
echo "   🌊 Market regime analysis with transition probabilities"
echo "   📉 Detailed drawdown analysis and recovery tracking"
echo "   ⚖️ Risk metrics evolution and monitoring"
echo "   💼 Portfolio composition tracking with changes over time"
echo "   🏢 Sector analysis with performance time series"
echo "   📊 Interactive validation results comparison"
echo "============================================================"
echo "🌐 Dashboard will be available at: http://localhost:8514"
echo "🛑 Press Ctrl+C to stop the dashboard"
echo "============================================================"

# Navigate to project root
cd "$(dirname "$0")/.."

# Launch the comprehensive dashboard
python -m streamlit run src/dashboard/northstar_v3_comprehensive_dashboard.py --server.port 8514 --server.headless true --browser.gatherUsageStats false