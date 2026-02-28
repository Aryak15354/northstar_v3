#!/bin/bash
# Quick test script to verify options integration

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     OPTIONS INTEGRATION TEST                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Test 1: Check files exist
echo "📁 Test 1: Checking required files..."
files=(
    "scripts/run_integrated_options_paper_engine.py"
    "scripts/refresh_upstox_token.py"
    "START_OPTIONS_SYSTEM.sh"
    "config/options_trading.yaml"
    ".env.options"
)

all_exist=true
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (missing)"
        all_exist=false
    fi
done

if [ "$all_exist" = false ]; then
    echo ""
    echo "❌ Some required files are missing"
    exit 1
fi

echo ""
echo "📦 Test 2: Checking Python syntax..."
python3 -m py_compile scripts/run_integrated_options_paper_engine.py
if [ $? -eq 0 ]; then
    echo "  ✅ Main engine compiles"
else
    echo "  ❌ Main engine has syntax errors"
    exit 1
fi

python3 -m py_compile scripts/refresh_upstox_token.py
if [ $? -eq 0 ]; then
    echo "  ✅ Token refresh script compiles"
else
    echo "  ❌ Token refresh script has syntax errors"
    exit 1
fi

echo ""
echo "🔧 Test 3: Checking command-line arguments..."
python3 scripts/run_integrated_options_paper_engine.py --help > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ Help command works"
else
    echo "  ❌ Help command failed"
    exit 1
fi

# Check for both interval parameters
if python3 scripts/run_integrated_options_paper_engine.py --help 2>&1 | grep -q "interval-minutes"; then
    echo "  ✅ --interval-minutes parameter exists"
else
    echo "  ❌ --interval-minutes parameter missing"
    exit 1
fi

if python3 scripts/run_integrated_options_paper_engine.py --help 2>&1 | grep -q "interval-seconds"; then
    echo "  ✅ --interval-seconds parameter exists"
else
    echo "  ❌ --interval-seconds parameter missing"
    exit 1
fi

echo ""
echo "📂 Test 4: Checking data directories..."
mkdir -p data/options/chains_cache data/dashboard
if [ -d "data/options" ]; then
    echo "  ✅ data/options/ exists"
else
    echo "  ❌ data/options/ missing"
    exit 1
fi

if [ -d "data/options/chains_cache" ]; then
    echo "  ✅ data/options/chains_cache/ exists"
else
    echo "  ❌ data/options/chains_cache/ missing"
    exit 1
fi

echo ""
echo "🔐 Test 5: Checking configuration..."
if grep -q "UPSTOX_API_KEY" .env.options; then
    echo "  ✅ UPSTOX_API_KEY found in .env.options"
else
    echo "  ⚠️  UPSTOX_API_KEY not set (you'll need to configure this)"
fi

if grep -q "UPSTOX_API_SECRET" .env.options; then
    echo "  ✅ UPSTOX_API_SECRET found in .env.options"
else
    echo "  ⚠️  UPSTOX_API_SECRET not set (you'll need to configure this)"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     TEST RESULTS                                               ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ All critical tests passed!"
echo ""
echo "📋 Next Steps:"
echo "  1. Configure your Upstox credentials in .env.options"
echo "  2. Run: python scripts/refresh_upstox_token.py"
echo "  3. Start trading: ./START_OPTIONS_SYSTEM.sh"
echo ""
echo "📚 Documentation:"
echo "  - Integration Guide: docs/OPTIONS_V3_INTEGRATION_GUIDE.md"
echo "  - Quick Start: INTEGRATION_SUMMARY.md"
echo "  - Checklist: READY_TO_TRADE_CHECKLIST.md"
echo ""
