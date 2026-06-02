#!/bin/bash
# Quick verification script for Gap 3 robust implementation
# Run this to verify all integrations are working

echo "=================================="
echo "GAP 3 QUICK VERIFICATION"
echo "=================================="
echo ""

# Run comprehensive tests
echo "Running comprehensive test suite..."
python scripts/test_gap3_robust_integrations.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=================================="
    echo "✓ ALL TESTS PASSED"
    echo "=================================="
    echo ""
    echo "Gap 3 is 100% robust:"
    echo "  ✓ Kalman filter extended with GST/power"
    echo "  ✓ Valuation engine using live credit spreads"
    echo "  ✓ Risk controller blocking high-pledge trades"
    echo ""
    echo "Run 'python scripts/validate_gap3_robust_complete.py' for detailed flow demonstration"
else
    echo ""
    echo "=================================="
    echo "✗ SOME TESTS FAILED"
    echo "=================================="
    echo "Review errors above"
    exit 1
fi
