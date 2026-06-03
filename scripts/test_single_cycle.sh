#!/bin/bash
# Quick test script to run a single cycle and see full output

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     SINGLE CYCLE TEST - FULL OUTPUT                            ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if underlyings specified
UNDERLYINGS="${1:-NIFTY}"

echo "🎯 Testing with: $UNDERLYINGS"
echo "⏱️  This may take 1-2 minutes (fetching option chains)..."
echo ""

# Run single cycle with full output
python3 scripts/run_integrated_options_paper_engine.py \
    --mode single \
    --underlyings "$UNDERLYINGS" \
    --aggressive

EXIT_CODE=$?

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     TEST COMPLETE                                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Cycle completed successfully!"
    echo ""
    echo "📊 Check results:"
    echo "   python scripts/monitor_options.py"
    echo ""
    echo "📁 Data files:"
    echo "   data/options/positions_state.json"
    echo "   data/options/capital_scaling_state.json"
    echo "   data/options/trade_ledger.parquet (if trades executed)"
else
    echo "❌ Cycle failed with exit code: $EXIT_CODE"
    echo ""
    echo "💡 Common issues:"
    echo "   - Token expired: python scripts/refresh_upstox_token.py"
    echo "   - API unavailable: Check internet connection"
    echo "   - Outside market hours: Normal, will use cached data"
fi

echo ""
