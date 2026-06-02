#!/bin/bash
# Northstar V3 Options System - Quick Start
# This script helps you start the integrated options trading system

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     NORTHSTAR V3 OPTIONS SYSTEM - QUICK START                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if .env.options exists
if [ ! -f ".env.options" ]; then
    echo "❌ ERROR: .env.options file not found"
    echo ""
    echo "Please create .env.options with your Upstox credentials:"
    echo "  cp .env.options.template .env.options"
    echo "  # Then edit .env.options with your API keys"
    exit 1
fi

# Check if token needs refresh
echo "🔍 Checking Upstox token status..."
if grep -q "UPSTOX_ACCESS_TOKEN=your_access_token_here" .env.options || \
   grep -q "UPSTOX_ACCESS_TOKEN=$" .env.options; then
    echo "⚠️  No valid access token found"
    echo ""
    echo "You need to refresh your Upstox token first."
    echo "Run: python scripts/refresh_upstox_token.py"
    echo ""
    read -p "Would you like to refresh the token now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python3 scripts/refresh_upstox_token.py
    else
        echo "❌ Cannot proceed without valid token"
        exit 1
    fi
fi

echo "✅ Token check passed"
echo ""

# Ask user what they want to do
echo "What would you like to do?"
echo ""
echo "1) Run canonical V3 refresh + dashboard"
echo "2) Run options engine only (standalone)"
echo "3) Run options engine in aggressive mode"
echo "4) Launch volatility dashboard only"
echo "5) Check system status"
echo "6) Refresh Upstox token"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting canonical V3 refresh..."
        echo "   This includes:"
        echo "   - Canonical data + state refresh"
        echo "   - Canonical dashboard launch"
        echo "   - Options engine remains a separate launcher"
        echo ""
        python3 scripts/run_complete_v3_system.py --quick
        if [ $? -eq 0 ]; then
            ./launch_dashboard.sh --port 8517
        fi
        ;;
    2)
        echo ""
        echo "🚀 Starting options engine (conservative mode)..."
        echo ""
        python3 scripts/run_integrated_options_paper_engine.py \
            --mode continuous \
            --interval-minutes 5 \
            --underlyings NIFTY,BANKNIFTY,FINNIFTY \
            --market-hours-only \
            --no-start-fresh-today  # Changed to use persistence
        ;;
    3)
        echo ""
        echo "🚀 Starting options engine (AGGRESSIVE mode)..."
        echo "   ⚠️  This will trade more frequently!"
        echo ""
        python3 scripts/run_integrated_options_paper_engine.py \
            --mode continuous \
            --interval-minutes 5 \
            --underlyings NIFTY,BANKNIFTY,FINNIFTY \
            --aggressive \
            --no-start-fresh-today  # Changed to use persistence
        ;;
    4)
        echo ""
        echo "🚀 Launching canonical dashboard..."
        echo "   Visit: http://localhost:8501"
        echo ""
        ./launch_dashboard.sh --port 8501
        ;;
    5)
        echo ""
        echo "📊 System Status:"
        echo "════════════════════════════════════════════════════════════"
        python3 scripts/status.py
        echo ""
        echo "🏥 Health Check:"
        echo "════════════════════════════════════════════════════════════"
        python3 scripts/health_check.py
        ;;
    6)
        echo ""
        echo "🔑 Refreshing Upstox token..."
        python3 scripts/refresh_upstox_token.py
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Done!"
