#!/bin/bash

# Start Live Volatility Trading System
# This script starts both the engine and dashboard

echo "=========================================="
echo "UNIFIED VOLATILITY ENGINE - LIVE SYSTEM"
echo "=========================================="
echo ""

# Check if .env.options exists
if [ ! -f ".env.options" ]; then
    echo "❌ Error: .env.options file not found"
    echo "Please create .env.options with your Upstox credentials"
    exit 1
fi

# Create necessary directories
mkdir -p logs
mkdir -p snapshots

echo "✅ Environment check passed"
echo ""

# Run ingestion layer health check
echo "Running data health check..."
python3 -c "
from src.ingestion import IngestionRegistry
from datetime import datetime
import sys

try:
    registry = IngestionRegistry()
    health = registry.health_check(datetime.now())
    
    critical_sources = ['market_data', 'fundamentals']
    optional_sources = ['sentiment', 'alternative_data']
    all_fresh = True
    
    for source in critical_sources:
        if source in health:
            status = health[source]
            if not status['is_fresh'] or status['status'] != 'available':
                print(f'❌ {source}: {status.get(\"warning\", \"not fresh\")}')
                all_fresh = False
    
    # Check optional sources (warn but don't fail)
    for source in optional_sources:
        if source in health:
            status = health[source]
            if not status['is_fresh'] or status['status'] != 'available':
                print(f'⚠️  {source}: {status.get(\"warning\", \"not fresh\")} (optional)')
            else:
                print(f'✅ {source}: fresh')
    
    if not all_fresh:
        print('\\n❌ Critical data sources are stale. Update data before starting.')
        print('Run: bash scripts/update_market_and_rbi_data.sh')
        sys.exit(1)
    else:
        print('✅ All critical data sources are fresh')
except Exception as e:
    print(f'⚠️  Health check failed: {e}')
    print('Continuing anyway...')
"

if [ $? -ne 0 ]; then
    echo ""
    echo "Data health check failed. Exiting."
    exit 1
fi

echo ""

# Check if already running
if [ -f "engine.pid" ]; then
    PID=$(cat engine.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Engine already running (PID: $PID)"
        echo "Stop it first with: kill $PID"
        exit 1
    else
        echo "Removing stale PID file..."
        rm engine.pid
    fi
fi

echo "Starting components..."
echo ""

# Start the live engine in background
echo "1. Starting live engine..."
python3 scripts/run_live_engine.py --interval 30 > logs/engine_console.log 2>&1 &
ENGINE_PID=$!

# Wait a moment for engine to initialize
sleep 3

# Check if engine started successfully
if ps -p $ENGINE_PID > /dev/null 2>&1; then
    echo "   ✅ Engine started (PID: $ENGINE_PID)"
else
    echo "   ❌ Engine failed to start"
    echo "   Check logs/engine_console.log for details"
    exit 1
fi

echo ""
echo "2. Starting dashboard..."
echo "   Dashboard will open in your browser at http://localhost:8501"
echo ""

# Start the dashboard (this will block)
./launch_dashboard.sh --port 8501

# If we get here, dashboard was stopped
echo ""
echo "Dashboard stopped. Stopping engine..."

# Stop the engine
if [ -f "engine.pid" ]; then
    PID=$(cat engine.pid)
    kill $PID 2>/dev/null
    echo "✅ Engine stopped"
fi

echo ""
echo "=========================================="
echo "System shutdown complete"
echo "=========================================="
