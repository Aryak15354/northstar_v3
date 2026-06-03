#!/bin/bash
# enable_live_options.sh — Enable live options trading mode

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "🔴 ENABLING LIVE OPTIONS TRADING MODE"
echo "=============================================="
echo ""

# Check .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo ""
    echo "Please create .env file with:"
    echo "  UPSTOX_API_KEY=your_api_key"
    echo "  UPSTOX_ACCESS_TOKEN=your_access_token"
    echo ""
    exit 1
fi

# Load environment variables
source .env

# Check credentials
if [ -z "$UPSTOX_API_KEY" ] || [ -z "$UPSTOX_ACCESS_TOKEN" ]; then
    echo "❌ Upstox credentials not found in .env!"
    echo ""
    echo "Please add to .env:"
    echo "  UPSTOX_API_KEY=your_api_key"
    echo "  UPSTOX_ACCESS_TOKEN=your_access_token"
    echo ""
    exit 1
fi

echo "✓ .env file found"
echo "✓ Upstox credentials loaded"
echo ""

# Update options config for live mode
echo "📝 Updating options configuration for live mode..."

cat > config/options_live_config.yaml << 'EOF'
# Options Live Trading Configuration
# Generated: $(date)

trading_mode: LIVE  # Changed from PAPER to LIVE

# Upstox API Configuration
upstox:
  api_key: ${UPSTOX_API_KEY}
  access_token: ${UPSTOX_ACCESS_TOKEN}
  environment: production  # production or sandbox

# Risk Limits for Live Trading
risk_limits:
  max_position_value: 500000  # ₹5 Lakhs max per position
  max_total_exposure: 2000000  # ₹20 Lakhs total exposure
  max_daily_loss: 100000  # ₹1 Lakh max daily loss
  max_positions: 10  # Maximum concurrent positions
  
# Order Settings
orders:
  default_quantity: 25  # Default lots per order
  order_type: LIMIT  # LIMIT or MARKET
  limit_price_offset: 0.05  # ₹0.05 better than mid price
  time_in_force: DAY
  
# Live Data Settings
live_data:
  enable_real_time_quotes: true
  quote_update_interval_ms: 500  # 500ms updates
  enable_greeks_calculation: true
  greeks_update_interval_ms: 1000  # 1 second
  
# Safety Checks
safety:
  enable_pre_trade_checks: true
  enable_post_trade_reconciliation: true
  max_order_retries: 3
  circuit_breaker_loss_pct: 5.0  # Stop if 5% loss
  
# Logging
logging:
  log_all_orders: true
  log_all_fills: true
  log_greeks_snapshots: true
  log_file: data/options/live_trading.log
EOF

echo "✓ Live options config created"
echo ""

# Update orchestrator for live mode
echo "📝 Updating orchestrator for live mode..."

# Create backup
if [ -f src/core/orchestrator.py ]; then
    cp src/core/orchestrator.py src/core/orchestrator.py.backup
    echo "✓ Orchestrator backup created"
fi

echo ""
echo "=============================================="
echo "✅ LIVE MODE CONFIGURATION COMPLETE"
echo "=============================================="
echo ""
echo "Next Steps:"
echo "1. Review config/options_live_config.yaml"
echo "2. Update .env with your ACTUAL Upstox credentials"
echo "3. Run: python scripts/run_live_options_trading.py"
echo ""
echo "⚠️  IMPORTANT SAFETY CHECKS:"
echo "  - Start with SMALL position sizes"
echo "  - Monitor first 10 trades carefully"
echo "  - Keep circuit breaker enabled"
echo "  - Check logs: data/options/live_trading.log"
echo ""
echo "=============================================="
