#!/bin/bash
# run_live_trading_system.sh — Master launcher for live trading

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "🚀 NORTHSTAR V3 LIVE TRADING SYSTEM"
echo "=============================================="
echo ""

# Check .env
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo ""
    echo "Create .env with:"
    echo "  UPSTOX_API_KEY=your_key"
    echo "  UPSTOX_ACCESS_TOKEN=your_token"
    exit 1
fi

source .env

if [ -z "$UPSTOX_API_KEY" ] || [ -z "$UPSTOX_ACCESS_TOKEN" ]; then
    echo "❌ Upstox credentials missing in .env!"
    exit 1
fi

echo "✓ .env loaded"
echo "✓ Upstox credentials found"
echo ""

# Enable live options mode
echo "📝 Enabling live options mode..."
bash scripts/enable_live_options.sh
echo ""

# Start dashboard in background
echo "📊 Starting canonical integrated dashboard..."
nohup streamlit run src/dashboard/app.py \
    --server.port 8504 \
    --server.address localhost \
    --server.headless true \
    --theme.base dark > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "✓ Dashboard started (PID: $DASHBOARD_PID)"
echo "  Access: http://localhost:8504"
echo ""

# Start 5-min sentiment updates in background
echo "🧠 Starting 5-minute sentiment updates..."
nohup python3 scripts/run_5min_sentiment_updates.py > logs/sentiment.log 2>&1 &
SENTIMENT_PID=$!
echo "✓ Sentiment updates started (PID: $SENTIMENT_PID)"
echo ""

# Start live options trading
echo "⚡ Starting live options trading..."
echo ""
echo "=============================================="
echo "⚠️  FINAL SAFETY CHECK"
echo "=============================================="
echo ""
echo "Live trading will start in 10 seconds..."
echo ""
echo "Press Ctrl+C NOW to cancel"
echo ""
sleep 10

python3 scripts/run_live_options_trading.py

# Cleanup on exit
echo ""
echo "=============================================="
echo "🛑 Shutting down..."
echo "=============================================="
kill $DASHBOARD_PID 2>/dev/null || true
kill $SENTIMENT_PID 2>/dev/null || true
echo "✓ All processes stopped"
