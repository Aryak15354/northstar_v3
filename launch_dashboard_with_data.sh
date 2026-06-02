#!/bin/bash

# Launch Dashboard with Fresh Data
# This script populates all data and launches the dashboard

echo "=========================================="
echo "NORTHSTAR V3 DASHBOARD LAUNCHER"
echo "=========================================="
echo ""

# Step 1: Populate data
echo "Step 1: Populating dashboard data..."
python3 scripts/populate_comprehensive_dashboard_data.py

if [ $? -ne 0 ]; then
    echo "Error: Data population failed"
    exit 1
fi

echo ""
echo "Step 2: Launching dashboard..."
echo ""

# Step 2: Launch dashboard
./launch_dashboard.sh "$@"
