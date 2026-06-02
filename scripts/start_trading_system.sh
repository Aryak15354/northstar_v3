#!/bin/bash
# Start the Unified Volatility Engine and Dashboard

echo "=========================================="
echo "Starting Unified Volatility Engine"
echo "=========================================="

# Check if .env.options exists
if [ ! -f .env.options ]; then
    echo "ERROR: .env.options not found"
    echo "Run: ./scripts/setup_upstox_integration.sh"
    exit 1
fi

# Load environment variables
export $(cat .env.options | grep -v '^#' | xargs)

echo ""
echo "Configuration:"
echo "  API Key: ${UPSTOX_API_KEY:0:20}..."
echo "  Mode: Paper Trading"
echo ""

# Start the engine in paper trading mode (background)
echo "Starting engine in paper trading mode..."
python3 scripts/start_engine.py --paper-trading &
ENGINE_PID=$!

echo "Engine started (PID: $ENGINE_PID)"
echo ""

# Wait a moment for engine to initialize
sleep 3

# Start the dashboard
echo "Starting dashboard..."
echo "Dashboard will be available at: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop both engine and dashboard"
echo ""

# Start dashboard (foreground)
python3 launch_dashboard.py --port 8501

# When dashboard stops, kill the engine
echo ""
echo "Stopping engine..."
kill $ENGINE_PID 2>/dev/null

echo "System stopped"
