# Options Trading System - Implementation Log

## Overview

Building an institutional-grade options trading system integrated with Northstar v3. The system uses Upstox API for live options data and implements comprehensive risk management with tax-aware P&L tracking.

## Completed Tasks

### ✅ Task 1: Infrastructure Setup (Completed)

**Created:**
1. Directory structure:
   - `src/options/` - Core system modules
   - `tests/options/` - Test suite
   - `config/options/` - Configuration files
   - `data/options/` - Data storage

2. Configuration files:
   - `config/options_trading.yaml` - Main configuration (capital, strategies, risk rules, event calendar)
   - `config/options/logging_config.yaml` - Logging configuration
   - `.env.options` - Upstox API credentials (populated with user credentials)
   - `.env.options.template` - Template for credentials

3. Core modules:
   - `src/options/__init__.py` - Package initialization
   - `src/options/config_loader.py` - Configuration loader with validation
   - `src/options/README.md` - System documentation

4. Security:
   - `.gitignore` - Protects credentials and sensitive data
   - Environment variable substitution for API keys

**Validated:**
- Configuration loads successfully
- Environment variables are read correctly
- All directories created
- Upstox credentials configured:
  - API Key: your_upstox_api_key_here
  - API Secret: your_upstox_api_secret_here
  - Access Token: (configured, expires 2026-02-10)

**Key Configuration Highlights:**
- Base capital: ₹5,00,000
- Base risk: 1.0% per trade
- Max risk ceiling: 1.5%
- Allowed strategies: Iron Condor, Calendar Spread, Long Straddle
- Weekly loss limit: 2%
- Max trades per week: 2
- Tax rate: 30% (India VDA)
- Event calendar: RBI, CPI, WPI, Budget dates configured

## Next Steps

### Task 2: Upstox API Adapter
- Implement UpstoxAdapter class with OAuth
- Implement fetch_option_chain() using `/v2/option/chain` API
- Implement fetch_option_greeks() using `/v3/market-quote/option-greek` API
- Implement data normalization to parquet format
- Add rate limiting (1 req/sec)
- Write property tests for API completeness and normalization

### Task 4: Regime Detection Engine
- Implement RegimeDetector class
- Calculate IV percentile rank (252-day history)
- Calculate vol-of-vol (std(iv_5d) / std(iv_20d))
- Implement regime persistence tracking (2-day minimum)
- Integrate with equity crisis regime from Northstar v3
- Write property tests for regime classification

### Task 5: Strategy Generation Engine
- Implement StrategyGenerator class
- Generate Iron Condor strategies (LOW_VOL_SELL)
- Generate Calendar Spread strategies (HIGH_VOL_SELL)
- Generate Long Straddle strategies (RISING_VOL_BUY)
- Validate lot sizes (NIFTY: 50, BANKNIFTY: 15)
- Check premium adequacy (credit ≥ 0.25 × max loss)
- Write property tests for strategy validation

## System Architecture

```
Options Trading System
├── Data Layer (Upstox API)
├── Regime Detection (Market conditions)
├── Strategy Generation (Iron Condor, Calendar, Straddle)
├── Eligibility Validation (Liquidity, events, vol-of-vol)
├── Capital Scaling (Performance-based risk adjustment)
├── Survival Rules (Kill switches, circuit breakers)
├── Position Management (Tracking, MTM, Greeks)
├── P&L Tracking (Tax-aware, costs)
└── Dashboard Integration (Streamlit panels)
```

## Critical Safety Features

### 4 Gaps Addressed
1. **Vol-of-Vol Check**: Block short-vol if std(iv_5d) > 1.5 × std(iv_20d)
2. **Event Calendar**: Block short-vol 2 days before RBI/CPI/WPI/Budget
3. **Lot Size Validation**: Reject fractional lot trades
4. **Liquidity Depth**: Require bid_qty ≥ 2 × lot_size

### Kill Switches
- Weekly loss limit: 2% capital
- Trauma rule: Block short-vol for 2 weeks after 80% max loss
- Portfolio risk cap: Total open risk ≤ 2% capital
- Tax liquidity check: Halt if YTD tax > cash buffer

### Capital Scaling
- Profit scaling: +0.25% risk per 8% net profit
- Drawdown de-scaling: -0.25% at 3% DD, -0.50% at 5% DD
- Time requirement: No scaling before 8 weeks
- Hard ceiling: Max 1.5% risk per trade

## Testing Strategy

- **Unit Tests**: Specific examples and edge cases
- **Property Tests**: Universal correctness properties (hypothesis library)
- **Integration Tests**: End-to-end pipeline validation
- **Stress Tests**: Vol expansion, calendar failure, consecutive losses

## Data Storage

- **Trade Ledger**: `data/options/trade_ledger.parquet` (immutable, append-only)
- **Regime History**: `data/options/regime_history.parquet`
- **IV History**: `data/options/iv_history.parquet`
- **Position Snapshots**: `data/options/position_snapshots.parquet`

## Integration Points with Northstar v3

1. **UnifiedState**: Options positions and metrics
2. **RiskCoordinator**: Options risk validators
3. **Dashboard**: OptionsPanel component
4. **Event Bus**: Options events
5. **Audit Trail**: Trade logging

## Timeline

- **Phase 1 (Core)**: Tasks 1-6 - Data, regime, strategy (Current)
- **Phase 2 (Risk)**: Tasks 7-10 - Eligibility, scaling, survival
- **Phase 3 (Tracking)**: Tasks 11-14 - Positions, P&L, ledger
- **Phase 4 (Integration)**: Tasks 17-18 - Risk system, dashboard
- **Phase 5 (Validation)**: Tasks 19-21 - Backtesting, docs, deployment

### ✅ Task 2: Upstox API Adapter (Completed)

**Created:**
1. `src/options/upstox_adapter.py` - Complete Upstox API integration

**Features Implemented:**
- **UpstoxAdapter class** with full OAuth token management
- **Rate limiting**: 1 request/second with automatic throttling
- **fetch_option_chain()**: Fetches complete option chain using `/v2/option/chain` API
  - Returns bid/ask prices and quantities
  - Includes full Greeks (delta, gamma, theta, vega, IV)
  - Provides OI, OI change, volume
  - Handles nested JSON response (call_options/put_options)
- **fetch_option_greeks()**: Real-time Greek updates using `/v3/market-quote/option-greek` API
  - Supports up to 50 instruments per request
  - Lower latency for position monitoring
- **get_underlying_price()**: Fetches current NIFTY/BANKNIFTY price
- **Data normalization**: Converts Upstox format to parquet-compatible DataFrame
- **Data validation**: Removes invalid strikes, negative Greeks, zero OI
- **Error handling**: Exponential backoff, automatic retry (3 attempts)
- **Token refresh**: Placeholder for OAuth refresh flow

**Validation:**
- Bid <= Ask enforcement
- Gamma, Vega, IV >= 0
- Strike > 0
- OI > 0 (removes illiquid options)
- Bid_qty and ask_qty presence check

**API Endpoints Used:**
- `/v2/option/chain` - Complete option chain with market data
- `/v3/market-quote/option-greek` - Real-time Greek updates
- `/v2/market-quote/quotes` - Underlying price

**Data Schema:**
```
timestamp, symbol, expiry, strike, option_type, bid, ask, ltp,
bid_qty, ask_qty, volume, oi, prev_oi, change_oi, iv, delta,
gamma, theta, vega, underlying_price, days_to_expiry
```

### ✅ Task 3: Checkpoint - Upstox Adapter Verified (Completed)

**Verification Results:**
- ✓ Configuration loads successfully
- ✓ Adapter initializes correctly
- ✓ API authentication working (token valid)
- ✓ Real option data fetched successfully
- ✓ Data normalization working
- ✓ All quality checks passed

**Real Data Test:**
- Fetched 12 NIFTY option contracts for March 26, 2026 expiry
- Underlying price: ₹25,867.30
- 6 Call options + 6 Put options
- Strike range: 21,000 to 30,000
- All data validation checks passed
- Sample data saved to `data/options/sample_option_chain.parquet`

**Key Findings:**
- Upstox API returns data only for specific expiry dates
- Weekly expiries (Thursdays) and monthly expiries (last Thursday)
- Empty responses for dates without option contracts
- API rate limiting working correctly (1 req/sec)
- Token expires daily - needs manual refresh

## Status

- **Current Task**: Task 4 - Regime Detection Engine
- **Next Task**: Task 5 - Strategy Generation Engine
- **Overall Progress**: 3/21 tasks complete (14%)

---

*Last Updated: 2026-02-09*
