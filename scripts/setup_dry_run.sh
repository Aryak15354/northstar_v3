#!/bin/bash

# Setup script for Options Trading Dry Run
# Creates necessary directories and checks dependencies

echo "=========================================="
echo "Options Trading System - Dry Run Setup"
echo "=========================================="
echo ""

# Create directories
echo "Creating directories..."
mkdir -p logs
mkdir -p data/dry_run
mkdir -p data/options
echo "✓ Directories created"
echo ""

# Check Python dependencies
echo "Checking Python dependencies..."

MISSING_DEPS=()

# Check each required package
python -c "import pandas" 2>/dev/null || MISSING_DEPS+=("pandas")
python -c "import numpy" 2>/dev/null || MISSING_DEPS+=("numpy")
python -c "import requests" 2>/dev/null || MISSING_DEPS+=("requests")
python -c "import pytz" 2>/dev/null || MISSING_DEPS+=("pytz")
python -c "import yaml" 2>/dev/null || MISSING_DEPS+=("pyyaml")

if [ ${#MISSING_DEPS[@]} -eq 0 ]; then
    echo "✓ All dependencies installed"
else
    echo "⚠️  Missing dependencies: ${MISSING_DEPS[*]}"
    echo ""
    echo "Install with:"
    echo "  pip install ${MISSING_DEPS[*]}"
    echo ""
    exit 1
fi

echo ""

# Check Upstox credentials
echo "Checking Upstox credentials..."

if [ -z "$UPSTOX_ACCESS_TOKEN" ]; then
    echo "⚠️  UPSTOX_ACCESS_TOKEN not set in environment"
    echo "   Using credentials from script (token expires daily)"
else
    echo "✓ UPSTOX_ACCESS_TOKEN found in environment"
fi

echo ""

# Display next steps
echo "=========================================="
echo "Setup Complete! ✅"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Test with single cycle:"
echo "   python scripts/dry_run_options_system.py --mode single --underlying NIFTY"
echo ""
echo "2. Start 14-day validation:"
echo "   python scripts/dry_run_options_system.py --mode continuous --duration 14 --interval 60 --underlying BOTH"
echo ""
echo "3. Monitor output in:"
echo "   - logs/dry_run.log (detailed log)"
echo "   - data/dry_run/cycle_results.csv (all cycles)"
echo "   - data/dry_run/signals.log (generated signals)"
echo ""
echo "4. Review guides:"
echo "   - docs/options/DRY_RUN_QUICK_START.md (quick reference)"
echo "   - docs/options/DRY_RUN_GUIDE.md (complete guide)"
echo ""
echo "⚠️  Remember: Access token expires daily!"
echo "   Generate new token from Upstox dashboard each day"
echo ""
echo "🚀 Ready to start dry run!"
echo ""
