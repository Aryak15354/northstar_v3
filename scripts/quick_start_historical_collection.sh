#!/bin/bash

# Quick Start: Historical Option Chain Data Collection
# 
# This script helps you start collecting historical data with recommended settings.

set -e

echo "================================================================================"
echo "Historical Option Chain Data Collection - Quick Start"
echo "================================================================================"
echo ""

# Check if logs directory exists
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo "✓ Created logs directory"
fi

# Check if data directory exists
if [ ! -d "data/options/historical" ]; then
    mkdir -p data/options/historical
    echo "✓ Created data/options/historical directory"
fi

echo ""
echo "Select collection scope:"
echo ""
echo "1) Test Run (NIFTY, last 7 days) - ~5 minutes"
echo "2) Phase 1: All Indices (90 days) - ~3 hours"
echo "3) Phase 1: All Indices (1 year) - ~8 hours"
echo "4) Phase 2: Top 20 Stocks (90 days) - ~4 hours"
echo "5) Single Stock (specify symbol and days)"
echo "6) Custom (specify all parameters)"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo "Starting test run: NIFTY, last 7 days"
        echo "This will take approximately 5 minutes..."
        python scripts/collect_historical_option_chains.py \
            --days 7 \
            --underlying NIFTY
        ;;
    
    2)
        echo ""
        echo "Starting Phase 1: All 4 indices, 90 days"
        echo "This will take approximately 3 hours..."
        echo "You can monitor progress with: tail -f logs/historical_collection.log"
        echo ""
        read -p "Press Enter to start or Ctrl+C to cancel..."
        python scripts/collect_historical_option_chains.py \
            --days 90 \
            --underlying ALL_INDICES
        ;;
    
    3)
        echo ""
        echo "Starting Phase 1: All 4 indices, 1 year (252 days)"
        echo "This will take approximately 8 hours..."
        echo "You can monitor progress with: tail -f logs/historical_collection.log"
        echo ""
        read -p "Press Enter to start or Ctrl+C to cancel..."
        python scripts/collect_historical_option_chains.py \
            --days 252 \
            --underlying ALL_INDICES
        ;;
    
    4)
        echo ""
        echo "Starting Phase 2: Top 20 liquid stocks, 90 days"
        echo "This will take approximately 4 hours..."
        echo "You can monitor progress with: tail -f logs/historical_collection.log"
        echo ""
        read -p "Press Enter to start or Ctrl+C to cancel..."
        python scripts/collect_historical_option_chains.py \
            --days 90 \
            --underlying TOP_LIQUID_STOCKS
        ;;
    
    5)
        echo ""
        read -p "Enter stock symbol (e.g., RELIANCE): " symbol
        read -p "Enter number of days: " days
        echo ""
        echo "Starting collection: $symbol, last $days days"
        python scripts/collect_historical_option_chains.py \
            --days $days \
            --underlying $symbol
        ;;
    
    6)
        echo ""
        read -p "Enter underlying (e.g., NIFTY, ALL_INDICES, RELIANCE): " underlying
        read -p "Enter start date (YYYY-MM-DD) or leave blank for days: " start_date
        
        if [ -z "$start_date" ]; then
            read -p "Enter number of days: " days
            echo ""
            echo "Starting collection: $underlying, last $days days"
            python scripts/collect_historical_option_chains.py \
                --days $days \
                --underlying $underlying
        else
            read -p "Enter end date (YYYY-MM-DD) or leave blank for today: " end_date
            
            if [ -z "$end_date" ]; then
                echo ""
                echo "Starting collection: $underlying, from $start_date to today"
                python scripts/collect_historical_option_chains.py \
                    --start-date $start_date \
                    --underlying $underlying
            else
                echo ""
                echo "Starting collection: $underlying, from $start_date to $end_date"
                python scripts/collect_historical_option_chains.py \
                    --start-date $start_date \
                    --end-date $end_date \
                    --underlying $underlying
            fi
        fi
        ;;
    
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "Collection Complete!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "1. Validate data: python scripts/validate_historical_data.py --underlying <SYMBOL>"
echo "2. View summary: cat data/options/historical/<symbol>_summary.txt"
echo "3. Run backtest: python scripts/backtest_options_system.py --underlying <SYMBOL>"
echo ""
