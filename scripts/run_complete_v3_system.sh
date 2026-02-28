#!/bin/bash

# Complete V3 System Runner with Market and RBI Data Updates
# This script runs the full integrated v3 options paper engine with fresh data

set -e  # Exit on error

echo "=========================================="
echo "COMPLETE V3 SYSTEM - FULL UPDATE & RUN"
echo "=========================================="
echo ""
echo "This script will:"
echo "  1. Update RBI macro data"
echo "  2. Refresh Upstox token (if needed)"
echo "  3. Run integrated V3 options paper engine"
echo "  4. Start dashboard for monitoring"
echo ""

# Create necessary directories
mkdir -p logs
mkdir -p snapshots
mkdir -p data/macro/raw
mkdir -p data/macro/cleaned
mkdir -p data/options/live
mkdir -p data/options/chains_cache

# Check if .env.options exists
if [ ! -f ".env.options" ]; then
    echo "❌ Error: .env.options file not found"
    echo "Please create .env.options with your Upstox credentials"
    echo ""
    echo "Required variables:"
    echo "  UPSTOX_API_KEY=your_api_key"
    echo "  UPSTOX_API_SECRET=your_api_secret"
    echo "  UPSTOX_ACCESS_TOKEN=your_access_token"
    echo "  UPSTOX_REDIRECT_URI=http://localhost:8080"
    exit 1
fi

echo "✅ Environment check passed"
echo ""

# ==========================================
# STEP 1: Update RBI Macro Data
# ==========================================
echo "=========================================="
echo "STEP 1: Updating RBI Macro Data"
echo "=========================================="
echo ""

if python3 src/ingestion/rbi_daily_updater.py; then
    echo "✅ RBI data updated successfully"
else
    echo "⚠️  RBI data update had issues (continuing anyway)"
fi

echo ""

# ==========================================
# STEP 2: Check Upstox Token
# ==========================================
echo "=========================================="
echo "STEP 2: Checking Upstox Token"
echo "=========================================="
echo ""

# Check if token is set
if grep -q "UPSTOX_ACCESS_TOKEN=" .env.options; then
    TOKEN=$(grep "UPSTOX_ACCESS_TOKEN=" .env.options | cut -d'=' -f2)
    if [ -z "$TOKEN" ] || [ "$TOKEN" = "your_access_token" ]; then
        echo "⚠️  Upstox access token not configured"
        echo ""
        echo "To refresh your token, run:"
        echo "  python3 scripts/refresh_upstox_token.py"
        echo ""
        read -p "Do you want to refresh the token now? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 scripts/refresh_upstox_token.py
        else
            echo "⚠️  Continuing with existing token (may be expired)"
        fi
    else
        echo "✅ Upstox token found"
        
        # Test the token
        if python3 scripts/test_upstox_connection.py > /dev/null 2>&1; then
            echo "✅ Upstox token is valid"
        else
            echo "⚠️  Upstox token may be expired"
            echo ""
            read -p "Do you want to refresh the token now? (y/n) " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                python3 scripts/refresh_upstox_token.py
            fi
        fi
    fi
else
    echo "❌ UPSTOX_ACCESS_TOKEN not found in .env.options"
    echo ""
    echo "Run this to configure:"
    echo "  python3 scripts/refresh_upstox_token.py"
    exit 1
fi

echo ""

# ==========================================
# STEP 3: Run Integrated V3 Engine
# ==========================================
echo "=========================================="
echo "STEP 3: Starting Integrated V3 Engine"
echo "=========================================="
echo ""

# Check if already running
if [ -f "engine.pid" ]; then
    PID=$(cat engine.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "⚠️  Engine already running (PID: $PID)"
        echo ""
        read -p "Stop existing engine and restart? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill $PID 2>/dev/null || true
            sleep 2
            rm -f engine.pid
        else
            echo "Keeping existing engine running"
            exit 0
        fi
    else
        echo "Removing stale PID file..."
        rm -f engine.pid
    fi
fi

# Determine run mode
echo "Select run mode:"
echo "  1) Single cycle (run once and exit)"
echo "  2) Continuous (30 min intervals)"
echo "  3) Continuous (10 min intervals - aggressive)"
echo "  4) Continuous (5 min intervals - very aggressive)"
echo ""
read -p "Enter choice (1-4) [default: 2]: " MODE_CHOICE

case $MODE_CHOICE in
    1)
        MODE="single"
        INTERVAL=0
        AGGRESSIVE=""
        ;;
    3)
        MODE="continuous"
        INTERVAL=600
        AGGRESSIVE="--aggressive"
        ;;
    4)
        MODE="continuous"
        INTERVAL=300
        AGGRESSIVE="--aggressive"
        ;;
    *)
        MODE="continuous"
        INTERVAL=1800
        AGGRESSIVE=""
        ;;
esac

# Select underlyings
echo ""
echo "Select underlyings to trade:"
echo "  1) Indices only (NIFTY, BANKNIFTY, FINNIFTY)"
echo "  2) Indices + top stocks (RELIANCE, TCS, HDFCBANK, etc.)"
echo "  3) Custom list"
echo ""
read -p "Enter choice (1-3) [default: 1]: " UNDERLYING_CHOICE

case $UNDERLYING_CHOICE in
    2)
        UNDERLYINGS="NIFTY,BANKNIFTY,FINNIFTY,RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK"
        ;;
    3)
        read -p "Enter comma-separated underlyings: " UNDERLYINGS
        ;;
    *)
        UNDERLYINGS="NIFTY,BANKNIFTY,FINNIFTY"
        ;;
esac

echo ""
echo "Configuration:"
echo "  Mode: $MODE"
if [ "$MODE" = "continuous" ]; then
    echo "  Interval: $((INTERVAL / 60)) minutes"
fi
echo "  Underlyings: $UNDERLYINGS"
echo "  Aggressive: ${AGGRESSIVE:-No}"
echo ""

# Start the engine
if [ "$MODE" = "single" ]; then
    echo "Running single cycle..."
    python3 scripts/run_integrated_options_paper_engine.py \
        --mode single \
        --underlyings "$UNDERLYINGS" \
        --no-start-fresh-today \
        $AGGRESSIVE
    
    echo ""
    echo "✅ Single cycle complete"
    echo ""
    echo "Check results:"
    echo "  - Runtime state: data/options/live/options_runtime_state.json"
    echo "  - Dashboard state: data/options/live/options_dashboard_state.json"
    echo "  - Snapshots: snapshots/current_state.json"
    echo ""
    
else
    echo "Starting continuous engine in background..."
    python3 scripts/run_integrated_options_paper_engine.py \
        --mode continuous \
        --interval-seconds $INTERVAL \
        --underlyings "$UNDERLYINGS" \
        --market-hours-only \
        --no-start-fresh-today \
        $AGGRESSIVE \
        > logs/engine_console.log 2>&1 &
    
    ENGINE_PID=$!
    echo $ENGINE_PID > engine.pid
    
    # Wait a moment for engine to initialize
    sleep 3
    
    # Check if engine started successfully
    if ps -p $ENGINE_PID > /dev/null 2>&1; then
        echo "✅ Engine started (PID: $ENGINE_PID)"
        echo ""
        echo "Engine is running in background"
        echo "  - PID: $ENGINE_PID"
        echo "  - Logs: logs/engine_console.log"
        echo "  - Detailed logs: logs/options_integrated_engine.log"
        echo ""
        echo "To stop the engine:"
        echo "  kill $ENGINE_PID"
        echo ""
    else
        echo "❌ Engine failed to start"
        echo "Check logs/engine_console.log for details"
        exit 1
    fi
fi

# ==========================================
# STEP 4: Start Dashboard (Optional)
# ==========================================
if [ "$MODE" = "continuous" ]; then
    echo "=========================================="
    echo "STEP 4: Dashboard"
    echo "=========================================="
    echo ""
    echo "Would you like to start the dashboard?"
    echo "  (This will open in your browser at http://localhost:8501)"
    echo ""
    read -p "Start dashboard? (y/n) " -n 1 -r
    echo ""
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Starting dashboard..."
        echo "  (Press Ctrl+C to stop dashboard - engine will keep running)"
        echo ""
        sleep 2
        
        streamlit run dashboard/volatility_dashboard.py
        
        echo ""
        echo "Dashboard stopped"
        echo "Engine is still running in background (PID: $ENGINE_PID)"
    else
        echo ""
        echo "Dashboard not started"
        echo ""
        echo "To start dashboard later:"
        echo "  streamlit run dashboard/volatility_dashboard.py"
    fi
fi

echo ""
echo "=========================================="
echo "V3 SYSTEM RUNNING"
echo "=========================================="
echo ""
echo "System Status:"
echo "  ✅ RBI data updated"
echo "  ✅ Market data feed active"
echo "  ✅ V3 engine running"
echo ""
echo "Monitor the system:"
echo "  - Engine logs: tail -f logs/options_integrated_engine.log"
echo "  - Console logs: tail -f logs/engine_console.log"
echo "  - Current state: cat snapshots/current_state.json | jq"
echo "  - Dashboard state: cat data/options/live/options_dashboard_state.json | jq"
echo ""
echo "Useful commands:"
echo "  - Check status: python3 scripts/status.py"
echo "  - Health check: python3 scripts/health_check.py"
echo "  - Emergency stop: python3 scripts/emergency_reduce.py"
echo ""
