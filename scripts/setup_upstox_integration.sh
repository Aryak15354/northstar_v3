#!/bin/bash
# Setup script for Upstox integration with Unified Volatility Engine

set -e

echo "=========================================="
echo "Upstox Integration Setup"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env.options ]; then
    echo -e "${YELLOW}Creating .env.options file...${NC}"
    cp .env.options.template .env.options
    echo -e "${GREEN}✓ Created .env.options${NC}"
else
    echo -e "${GREEN}✓ .env.options already exists${NC}"
fi

# Prompt for Upstox credentials
echo ""
echo "Please provide your Upstox API credentials:"
echo "(You can get these from https://account.upstox.com/developer/apps)"
echo ""

read -p "Upstox API Key: " UPSTOX_API_KEY
read -p "Upstox API Secret: " UPSTOX_API_SECRET
read -p "Upstox Access Token (today's token): " UPSTOX_ACCESS_TOKEN

# Update .env file
echo ""
echo -e "${YELLOW}Updating .env.options...${NC}"

# Use sed to update or add credentials
if grep -q "UPSTOX_API_KEY=" .env.options; then
    sed -i.bak "s/UPSTOX_API_KEY=.*/UPSTOX_API_KEY=$UPSTOX_API_KEY/" .env.options
else
    echo "UPSTOX_API_KEY=$UPSTOX_API_KEY" >> .env.options
fi

if grep -q "UPSTOX_API_SECRET=" .env.options; then
    sed -i.bak "s/UPSTOX_API_SECRET=.*/UPSTOX_API_SECRET=$UPSTOX_API_SECRET/" .env.options
else
    echo "UPSTOX_API_SECRET=$UPSTOX_API_SECRET" >> .env.options
fi

if grep -q "UPSTOX_ACCESS_TOKEN=" .env.options; then
    sed -i.bak "s/UPSTOX_ACCESS_TOKEN=.*/UPSTOX_ACCESS_TOKEN=$UPSTOX_ACCESS_TOKEN/" .env.options
else
    echo "UPSTOX_ACCESS_TOKEN=$UPSTOX_ACCESS_TOKEN" >> .env.options
fi

# Remove backup file
rm -f .env.options.bak

echo -e "${GREEN}✓ Credentials saved to .env.options${NC}"

# Export environment variables
export UPSTOX_API_KEY
export UPSTOX_API_SECRET
export UPSTOX_ACCESS_TOKEN

# Create necessary directories
echo ""
echo -e "${YELLOW}Creating directories...${NC}"

mkdir -p snapshots
mkdir -p logs
mkdir -p reports
mkdir -p backups
mkdir -p audit

echo -e "${GREEN}✓ Directories created${NC}"

# Test connection
echo ""
echo -e "${YELLOW}Testing Upstox API connection...${NC}"

# Run the comprehensive connection test
python3 scripts/test_upstox_connection.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Upstox API connection successful${NC}"
else
    echo -e "${RED}✗ Upstox API connection failed${NC}"
    echo "Please check your credentials and try again"
    exit 1
fi

# Run integration tests
echo ""
echo -e "${YELLOW}Running integration tests...${NC}"
echo ""

python3 scripts/test_real_data_integration.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=========================================="
    echo "✓ Setup Complete!"
    echo "==========================================${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Review configuration: config/production_upstox.yaml"
    echo "2. Start the engine: python scripts/start_engine.py --config config/production_upstox.yaml"
    echo "3. Launch dashboard: streamlit run src/dashboard/app.py"
    echo ""
    echo "Important notes:"
    echo "- Upstox access tokens expire daily - update UPSTOX_ACCESS_TOKEN in .env.options daily"
    echo "- Start with paper trading mode (set paper_trading.enabled: true in config)"
    echo "- Monitor logs in logs/volatility_engine.log"
    echo ""
else
    echo ""
    echo -e "${RED}=========================================="
    echo "✗ Setup Failed"
    echo "==========================================${NC}"
    echo ""
    echo "Please check the error messages above and try again"
    exit 1
fi
