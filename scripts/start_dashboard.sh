#!/bin/bash

# Start the integrated volatility dashboard
echo "🚀 Starting Unified Volatility Engine Dashboard..."
echo "📊 Integrated with Options System v3"
echo ""

# Check if options system data is available
if [ -f "data/options/live/options_dashboard_state.json" ]; then
    echo "✅ Options system data found"
    echo "📈 Latest data: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" data/options/live/options_dashboard_state.json)"
else
    echo "⚠️  Options system data not found"
    echo "💡 Make sure the options system is running first"
fi

echo ""
echo "🌐 Starting Streamlit dashboard..."
echo "📍 Dashboard will be available at: http://localhost:8501"
echo ""

# Start the dashboard
streamlit run dashboard/volatility_dashboard.py --server.port 8501 --server.headless false