#!/bin/bash
# Automated Sentiment Data Backfill (Non-Interactive)
# Backfills 60+ days of historical sentiment data

set -e

LOG_FILE="logs/sentiment_backfill_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

echo "=========================================="
echo "SENTIMENT DATA BACKFILL - AUTOMATED"
echo "=========================================="
echo "Log: $LOG_FILE"
echo ""

{
    echo "Started: $(date)"
    echo ""
    
    echo "Step 1: Running historical sentiment pipeline (2020-2026)..."
    echo "=========================================="
    
    python scripts/run_daily_sentiment_pipeline.py \
        --include-news-builder \
        --news-start-year 2020 \
        --news-end-year 2026 \
        --news-sources "nse,rss" \
        --news-workers 4 \
        --news-resume \
        --news-sentiment-model "auto" 2>&1
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Historical pipeline failed"
        exit 1
    fi
    
    echo ""
    echo "Step 2: Running current date update..."
    echo "=========================================="
    
    python scripts/run_daily_sentiment_pipeline.py --date today 2>&1
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Current date update failed"
        exit 1
    fi
    
    echo ""
    echo "Step 3: Validating backfill..."
    echo "=========================================="
    
    python scripts/test_sentiment_ingestion.py 2>&1
    
    if [ $? -ne 0 ]; then
        echo "WARNING: Validation found issues"
    fi
    
    echo ""
    echo "Completed: $(date)"
    echo "=========================================="
    echo "✓ BACKFILL COMPLETE"
    echo "=========================================="
    
} 2>&1 | tee "$LOG_FILE"

echo ""
echo "Full log saved to: $LOG_FILE"
