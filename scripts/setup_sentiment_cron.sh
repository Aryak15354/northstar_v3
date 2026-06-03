#!/bin/bash
# Setup cron job for daily sentiment processing
# Run this script to install the cron job

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "SENTIMENT CRON JOB SETUP"
echo "=========================================="
echo ""
echo "This will add a daily cron job to process sentiment data"
echo "Schedule: 6:30 AM IST daily (after market close data is available)"
echo ""

# Create the cron command
CRON_CMD="30 6 * * * cd $PROJECT_ROOT && /usr/bin/python3 $PROJECT_ROOT/scripts/run_daily_sentiment_pipeline.py --date today >> $PROJECT_ROOT/logs/sentiment_cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_daily_sentiment_pipeline.py"; then
    echo "⚠️  Sentiment cron job already exists"
    echo ""
    echo "Current cron jobs:"
    crontab -l | grep "run_daily_sentiment_pipeline.py"
    echo ""
    read -p "Replace existing job? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    
    # Remove old job
    crontab -l | grep -v "run_daily_sentiment_pipeline.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo ""
echo "✅ Cron job installed successfully!"
echo ""
echo "Schedule: Daily at 6:30 AM IST"
echo "Command: $CRON_CMD"
echo ""
echo "To view all cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove this cron job:"
echo "  crontab -l | grep -v 'run_daily_sentiment_pipeline.py' | crontab -"
echo ""
echo "Logs will be written to: $PROJECT_ROOT/logs/sentiment_cron.log"
echo ""
