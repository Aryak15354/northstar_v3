#!/bin/bash

# Start the canonical dashboard surface
echo "🚀 Starting Northstar V3 Canonical Dashboard..."
echo "📊 Integrated with the current dashboard app surface"
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
python3 launch_dashboard.py --port 8501 --dev
