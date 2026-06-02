# Upstox Integration Guide

## Overview

This guide explains how to integrate the Unified Volatility Engine with Upstox API for live trading in Indian markets (NSE/BSE).

## Prerequisites

1. **Upstox Account**: Active Upstox trading account
2. **API Access**: Upstox API credentials (API Key, API Secret)
3. **Access Token**: Daily access token (expires at 3:30 AM IST)
4. **Python 3.8+**: With all dependencies installed

## Quick Start

### 1. Get Upstox API Credentials

1. Log in to [Upstox Developer Console](https://account.upstox.com/developer/apps)
2. Create a new app or use existing app
3. Note down:
   - API Key
   - API Secret
4. Generate access token (valid for 1 day)

### 2. Run Setup Script

```bash
chmod +x scripts/setup_upstox_integration.sh
./scripts/setup_upstox_integration.sh
```

The script will:
- Prompt for your Upstox credentials
- Save credentials to `.env.options`
- Test API connection
- Run integration tests
- Create necessary directories

### 3. Configure System

Edit `config/production_upstox.yaml` to customize:
- Capital allocation
- Position limits
- Risk thresholds
- Trading hours
- Strategy allocation

### 4. Start Trading

```bash
# Paper trading mode (recommended first)
python scripts/start_engine.py --config config/production_upstox.yaml --paper-trading

# Live trading mode (after testing)
python scripts/start_engine.py --config config/production_upstox.yaml
```

### 5. Launch Dashboard

```bash
streamlit run src/dashboard/app.py
```

Access at: http://localhost:8501

## Components

### 1. Market Data Feed (`src/volatility/market_data_feed.py`)

Provides real-time market data:
- Underlying prices (NIFTY, BANKNIFTY, FINNIFTY, stocks)
- Option chains with Greeks
- IV surface construction
- Data quality validation

**Usage:**
```python
from src.volatility.market_data_feed import create_market_data_feed

feed = create_market_data_feed(access_token)

# Get underlying price
nifty_price = feed.get_underlying_price("NIFTY")

# Get option chain
expiry = date(2026, 2, 13)
options = feed.get_option_chain("NIFTY", expiry)

# Get ATM options
atm_options = feed.get_atm_options("NIFTY", expiry, num_strikes=5)

# Get IV surface
expiries = feed.get_next_expiries("NIFTY", 3)
iv_surface = feed.get_iv_surface("NIFTY", expiries)
```

### 2. Broker Execution Interface (`src/volatility/broker_execution.py`)

Handles order execution:
- Order placement (MARKET, LIMIT, STOP LOSS)
- Order modification and cancellation
- Position tracking
- Execution quality monitoring

**Usage:**
```python
from src.volatility.broker_execution import (
    BrokerExecutionInterface, OrderSide, OrderType, ProductType
)

broker = BrokerExecutionInterface(api_key, api_secret, access_token)

# Place limit order
order = broker.place_order(
    instrument_key="NSE_FO|12345",
    quantity=50,
    side=OrderSide.BUY,
    order_type=OrderType.LIMIT,
    price=100.50,
    product_type=ProductType.CARRYFORWARD
)

# Check order status
status = broker.get_order_status(order.order_id)

# Get positions
positions = broker.get_positions()

# Get execution metrics
metrics = broker.get_execution_metrics()
```

### 3. Configuration (`config/production_upstox.yaml`)

Production configuration with:
- Upstox API endpoints
- Capital allocation (₹10 lakh default)
- Position limits (scaled for Indian markets)
- Greeks limits (in INR)
- Risk thresholds (VaR, CVaR, drawdown)
- Regime-conditional adjustments
- Execution parameters (NSE-specific)
- Trading hours (IST)
- Strategy allocation

## API Endpoints

### Upstox API v2/v3

1. **Option Chain**: `/v2/option/chain`
   - Complete option chain with market data
   - Greeks (delta, gamma, theta, vega, IV)
   - Bid/ask prices and quantities
   - OI and OI change

2. **Option Greeks**: `/v3/market-quote/option-greek`
   - Real-time Greek updates
   - Up to 50 instruments per request

3. **Market Quote**: `/v2/market-quote/quotes`
   - Underlying prices
   - Index quotes

4. **Place Order**: `/v2/order/place`
   - Order placement
   - Supports MARKET, LIMIT, SL, SL-M

5. **Order Book**: `/v2/order/retrieve-all`
   - All orders for the day

6. **Positions**: `/v2/portfolio/short-term-positions`
   - Current F&O positions

## Rate Limits

- **1 request per second** (configurable)
- **50 instruments per request** (for Greeks API)
- Exponential backoff on rate limit errors

## Data Flow

```
Upstox API
    ↓
Market Data Feed
    ↓
State Engine (UnifiedState)
    ↓
Strategy Generator
    ↓
Risk Authority (validation)
    ↓
Broker Execution Interface
    ↓
Upstox API (order placement)
```

## Trading Hours (IST)

- **Pre-market**: 09:00 - 09:15
- **Market Open**: 09:15
- **Trading Start**: 09:30 (15 min buffer)
- **Trading End**: 15:00 (30 min buffer)
- **Market Close**: 15:30
- **Post-market**: 15:30 - 16:00

## Expiry Days

- **NIFTY**: Thursday (weekly)
- **BANKNIFTY**: Wednesday (weekly)
- **FINNIFTY**: Tuesday (weekly)
- **Monthly**: Last Thursday of month

## Position Limits

### Default Limits (₹10 lakh capital)

- **Per underlying**: 50 contracts
- **Total portfolio**: 200 contracts
- **Max concentration**: 25% per underlying
- **Max position value**: ₹2 lakh
- **Max portfolio value**: ₹8 lakh

### Index-Specific Limits

- **NIFTY**: 20 lots (lot size = 50)
- **BANKNIFTY**: 10 lots (lot size = 15)
- **FINNIFTY**: 15 lots (lot size = 40)

## Risk Management

### Risk Thresholds (₹10 lakh capital)

- **VaR 95%**: ₹30,000
- **VaR 99%**: ₹60,000
- **CVaR 95%**: ₹45,000
- **Max Drawdown**: 12%
- **Max Daily Loss**: ₹15,000
- **Max Position Loss**: ₹5,000
- **Stop Loss**: 50% per position
- **Portfolio Stop Loss**: 10%

### Greeks Limits

- **Delta**: ±500
- **Gamma**: 250
- **Vega**: 5,000 (₹ per 1% IV change)
- **Theta**: -300 (₹ per day)

### Regime-Conditional Adjustments

**Crisis (VIX > 30)**:
- Position multiplier: 0.4x
- Short vol: Disabled
- Max leverage: 1.0x

**High Vol (VIX 20-30)**:
- Position multiplier: 0.7x
- Short vol: Enabled
- Max leverage: 1.3x

**Low Vol (VIX < 15)**:
- Position multiplier: 1.0x
- Short vol: Enabled
- Max leverage: 1.5x

## Execution Quality

### Metrics Tracked

- **Fill Rate**: % of orders filled
- **Rejection Rate**: % of orders rejected
- **Average Slippage**: Actual vs expected price
- **Execution Time**: Order placement to fill
- **Venue Performance**: By exchange

### Quality Controls

- **Max bid-ask spread**: 5%
- **Min OI**: 1,000 contracts
- **Min volume**: 100 contracts
- **Max slippage**: 1%
- **Retry on rejection**: Up to 3 times

## Paper Trading Mode

Enable in config:
```yaml
paper_trading:
  enabled: true
  initial_capital: 1000000
  simulate_slippage: true
  slippage_bps: 5
  simulate_latency_ms: 100
```

Paper trading:
- Simulates order execution
- Tracks P&L
- No real orders placed
- Perfect for testing

## Daily Operations

### Morning Routine (Before 9:15 AM)

1. **Update Access Token**:
   ```bash
   # Edit .env.options
   UPSTOX_ACCESS_TOKEN=new_token_here
   ```

2. **Check System Health**:
   ```bash
   python scripts/health_check.py
   ```

3. **Review Configuration**:
   ```bash
   python scripts/validate_config.py config/production_upstox.yaml
   ```

4. **Start Engine**:
   ```bash
   python scripts/start_engine.py --config config/production_upstox.yaml
   ```

5. **Launch Dashboard**:
   ```bash
   streamlit run src/dashboard/app.py
   ```

### Intraday Monitoring

- Monitor dashboard for:
  - P&L tracking
  - Greeks utilization
  - Risk metrics
  - Position status
  - Alerts

- Check logs:
  ```bash
  tail -f logs/volatility_engine.log
  ```

### End of Day (After 3:30 PM)

1. **Generate Reports**:
   ```bash
   python scripts/generate_eod_reports.py
   ```

2. **Save State**:
   ```bash
   python scripts/save_state.py snapshots/eod_$(date +%Y%m%d).json
   ```

3. **Shutdown Engine**:
   ```bash
   python scripts/shutdown_engine.py
   ```

## Troubleshooting

### Token Expired

**Error**: `401 Unauthorized`

**Solution**:
1. Generate new access token from Upstox
2. Update `.env.options`
3. Restart engine

### Rate Limit Exceeded

**Error**: `429 Too Many Requests`

**Solution**:
- System automatically retries with exponential backoff
- Check `rate_limit_per_second` in config
- Reduce data refresh frequency

### Empty Option Chain

**Error**: Empty DataFrame returned

**Possible Causes**:
1. Invalid expiry date
2. Market closed
3. No liquidity
4. API issue

**Solution**:
- Check expiry date is valid
- Verify market hours
- Try different expiry
- Check Upstox API status

### Order Rejection

**Common Reasons**:
1. Insufficient margin
2. Invalid instrument key
3. Price out of range
4. Market closed
5. Risk limit breach

**Solution**:
- Check margin available
- Verify instrument key format
- Check price limits
- Verify trading hours
- Review risk limits

## Best Practices

### 1. Token Management

- Generate new token daily before market open
- Store securely in `.env.options`
- Never commit tokens to git
- Use environment variables

### 2. Risk Management

- Start with paper trading
- Use conservative limits initially
- Monitor Greeks continuously
- Respect stop losses
- Diversify across underlyings

### 3. Data Quality

- Validate option chain data
- Check bid-ask spreads
- Verify OI and volume
- Monitor IV levels
- Watch for stale data

### 4. Execution

- Use LIMIT orders (avoid MARKET)
- Check liquidity before trading
- Monitor slippage
- Stagger large orders
- Verify fills

### 5. Monitoring

- Watch dashboard continuously
- Set up alerts
- Review logs regularly
- Track performance metrics
- Document decisions

## Support

### Upstox Support

- **Website**: https://upstox.com/support
- **Email**: support@upstox.com
- **Phone**: 022-6130-8888
- **API Docs**: https://upstox.com/developer/api-documentation

### System Issues

- Check logs: `logs/volatility_engine.log`
- Run diagnostics: `python scripts/health_check.py`
- Review configuration: `config/production_upstox.yaml`
- Test connection: `python scripts/test_real_data_integration.py`

## Appendix

### A. Instrument Key Format

- **Index**: `NSE_INDEX|Nifty 50`
- **Stock**: `NSE_EQ|INE002A01018` (ISIN)
- **F&O**: `NSE_FO|12345` (instrument token)

### B. Order Types

- **MARKET**: Execute at best available price
- **LIMIT**: Execute at specified price or better
- **SL**: Stop loss order (trigger + limit price)
- **SL-M**: Stop loss market (trigger only)

### C. Product Types

- **INTRADAY (MIS)**: Intraday positions (squared off by EOD)
- **DELIVERY (CNC)**: Delivery positions (equity only)
- **CARRYFORWARD (NRML)**: F&O positions (can carry forward)

### D. Useful Links

- [Upstox API Documentation](https://upstox.com/developer/api-documentation)
- [NSE Option Chain](https://www.nseindia.com/option-chain)
- [India VIX](https://www.nseindia.com/products-services/indices-india-vix)
- [NSE Holidays](https://www.nseindia.com/regulations/trading-holidays)

---

**Last Updated**: 2026-02-11
**Version**: 1.0
