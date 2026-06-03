#!/bin/bash
# Run options engine with stocks included

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     OPTIONS ENGINE - WITH STOCKS                               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Top liquid stocks
STOCKS="RELIANCE,TCS,HDFCBANK,INFY,ICICIBANK,SBIN"
INDICES="NIFTY,BANKNIFTY,FINNIFTY"
ALL_UNDERLYINGS="$INDICES,$STOCKS"

echo "📊 Trading Underlyings:"
echo "   Indices: NIFTY, BANKNIFTY, FINNIFTY"
echo "   Stocks: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK, SBIN"
echo ""
echo "⚠️  This will fetch chains for 9 underlyings (takes longer)"
echo "⏱️  Expect 3-5 minutes per cycle"
echo ""

read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

echo ""
echo "🚀 Starting options engine with stocks..."
echo ""

python3 scripts/run_integrated_options_paper_engine.py \
    --mode continuous \
    --interval-minutes 5 \
    --underlyings "$ALL_UNDERLYINGS" \
    --aggressive \
    --no-start-fresh-today

echo ""
echo "✅ Engine stopped"
