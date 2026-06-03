#!/bin/bash
# Backfill Sentiment Data for Northstar V3
# Run this once to build historical sentiment database

set -e

echo "=========================================="
echo "SENTIMENT DATA BACKFILL"
echo "=========================================="
echo ""
echo "This will:"
echo "  1. Process historical news from 2020-2026"
echo "  2. Generate sentiment scores"
echo "  3. Export to data/sentiment/v3/"
echo ""
echo "Estimated time: 1-2 hours"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1: Running historical sentiment pipeline..."
echo "=========================================="

python scripts/run_daily_sentiment_pipeline.py \
    --include-news-builder \
    --news-start-year 2020 \
    --news-end-year 2026 \
    --news-sources "nse,rss" \
    --news-workers 4 \
    --news-resume \
    --news-sentiment-model "auto"

if [ $? -ne 0 ]; then
    echo "ERROR: Historical pipeline failed"
    exit 1
fi

echo ""
echo "Step 2: Running current date update..."
echo "=========================================="

python scripts/run_daily_sentiment_pipeline.py --date today

if [ $? -ne 0 ]; then
    echo "ERROR: Current date update failed"
    exit 1
fi

echo ""
echo "Step 3: Validating backfill..."
echo "=========================================="

python scripts/test_sentiment_ingestion.py

if [ $? -ne 0 ]; then
    echo "WARNING: Validation found issues - review output above"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ BACKFILL COMPLETE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Review validation results above"
echo "  2. If all tests pass, add to START_LIVE_SYSTEM.sh"
echo "  3. Schedule daily runs via cron"
echo ""
