#!/bin/bash
# Northstar V3 Operations Startup Script
# Environment: development

set -e

echo "Starting Northstar V3 Operations (development)..."

# Set environment variables
export NORTHSTAR_ENV=development
export NORTHSTAR_CONFIG_DIR="deployment/development/config"
export NORTHSTAR_LOG_LEVEL=DEBUG

# Change to deployment directory
cd "deployment/development"

# Start system integration
echo "Starting system integration..."
python scripts/start_system_integration.py --environment development

# Verify system health
echo "Verifying system health..."
python scripts/run_comprehensive_system_validation.py --quick-check

# Start monitoring (if enabled)
if [ "True" = "True" ]; then
    echo "Starting real-time monitoring..."
    python scripts/start_monitoring.py --environment development
fi

echo "Northstar V3 Operations startup completed successfully!"
