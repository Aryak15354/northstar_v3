#!/bin/bash

# Quick Market and RBI Data Update Script
# Updates all data sources without starting the engine

set -e

echo "=========================================="
echo "MARKET & RBI DATA UPDATE"
echo "=========================================="
echo ""

# Create necessary directories
mkdir -p logs
mkdir -p data/macro/raw
mkdir -p data/macro/cleaned
mkdir -p data/options/chains_cache

# ==========================================
# Step 1: Force market update first (yfinance)
# ==========================================
echo "📈 Updating market data (yfinance)..."
echo ""
if python3 src/ingestion/integrated_data_pipeline.py --market-only --force-market; then
    echo ""
    echo "✅ Market data updated successfully"
else
    echo ""
    echo "⚠️  Market data update completed with warnings"
fi

echo ""

# ==========================================
# Step 2: Force RBI pipeline
# ==========================================
echo "📊 Updating RBI Macro Data..."
echo ""
if python3 src/ingestion/rbi_daily_updater.py --force; then
    echo ""
    echo "✅ RBI data updated successfully"
else
    echo ""
    echo "⚠️  RBI data update completed with warnings"
fi

echo ""

# ==========================================
# Step 3: Recompute integrated market state
# ==========================================
echo "🧠 Recomputing integrated market state..."
echo ""
if python3 src/ingestion/integrated_data_pipeline.py --integrate-only; then
    echo "✅ Market state integration complete"
else
    echo "⚠️  Market state integration completed with warnings"
fi

echo ""

# ==========================================
# Summary
# ==========================================
echo "=========================================="
echo "DATA UPDATE COMPLETE"
echo "=========================================="
echo ""

# Check RBI data files
RBI_FILES=$(find data/macro/raw -name "*.csv" 2>/dev/null | wc -l | tr -d ' ')
echo "📁 RBI Data Status:"
echo "   CSV files: $RBI_FILES"

if [ -f "data/macro/cleaned/macro_cleaned.parquet" ]; then
    echo "   Cleaned data: ✅"
else
    echo "   Cleaned data: ⚠️  Not found"
fi

echo ""
echo "✅ Data update complete"
echo ""
echo "Next steps:"
echo "  - Run full system: ./scripts/run_complete_v3_system.sh"
echo "  - Run single cycle: python3 scripts/run_integrated_options_paper_engine.py --mode single"
echo ""
