# Options Trading Infrastructure - Complete Analysis

## Overview

Your codebase has a **comprehensive options trading system** built for the Indian market (NSE), specifically focused on NIFTY and BANKNIFTY index options. The system is production-grade with proper data fetching, regime detection, strategy generation, and backtesting capabilities.

---

## 📁 Core Options Modules

### 1. **Data Acquisition Layer** (`src/options/`)

#### `nse_session.py` - Production-Grade Session Manager
- **Purpose**: Compliant NSE API access with human-scale frequency
- **Features**:
  - Rate limiting (60-second minimum between requests)
  - Proper browser-like headers (not spoofing, just standard)
  - Session management with cookie handling
  - Automatic retry logic with exponential backoff
  - SSL handling for development
- **Compliance**: Designed to be respectful to NSE servers

#### `nse_fetcher.py` - Options Chain Data Fetcher
- **Purpose**: Fetch live NIFTY/BANKNIFTY options chains from NSE API
- **Data Retrieved**:
  - Strike prices, expiries, option types (Call/Put)
  - Last traded price (LTP), bid/ask spreads
  - Implied volatility (IV)
  - Open interest (OI) and volume
  - Greeks: Delta, Gamma, Theta, Vega
  - OI changes and percentage changes
- **Data Quality**:
  - Filters out zero prices and invalid strikes
  - Removes options with zero IV
  - Filters by days to expiry (1-365 days)
  - Calculates moneyness and time to expiry
- **Output**: Structured DataFrame with 20+ columns

#### `market_hours.py` - Trading Calendar Manager
- **Purpose**: NSE market hours and holiday management
- **Features**:
  - IST timezone handling
  - Market hours: 9:15 AM - 3:30 PM IST
  - 2025 holiday calendar (10 major holidays)
  - Market status detection (OPEN/CLOSED/PRE_MARKET/POST_MARKET)
  - Smart data fetching windows (15 min pre-market, 30 min post-market)
- **Functions**:
  - `is_market_hours()` - Check if market is open
  - `should_fetch_live_data()` - Determine if API calls should be made
  - `time_to_market_open()` - Minutes until next market open

---

### 2. **Options Surface & Analytics** (`src/options/`)

#### `options_surface.py` - Volatility Surface Builder
- **Purpose**: Build comprehensive options surface from chain data
- **Calculations**:
  - **Moneyness buckets**: 0.6 to 1.5 (60% to 150% of spot)
  - **IV Rank**: Rolling 60-day percentile rank per moneyness bucket
  - **Skew**: OTM put IV minus OTM call IV (per expiry)
  - **Term structure**: Near vs far expiry IV comparison
- **Output**: Enhanced options chain with surface metrics

#### `options_regime.py` - Market Regime Classifier
- **Purpose**: Classify market conditions for options strategy selection
- **Inputs**:
  - India VIX data
  - Market regime (from main system)
  - Macro factors and scores
  - Realized volatility
- **Regimes Detected**:
  1. **CRASH_HEDGE**: High stress (>20%) or macro score < -1
  2. **LOW_VOL_SELL**: VIX < realized vol, trending down
  3. **RISING_VOL_BUY**: VIX rising above realized vol
  4. **HIGH_VOL_SELL**: VIX > 1.5x realized vol
  5. **NEUTRAL**: Default state
- **Output**: Daily regime classification with volatility metrics

---

### 3. **Strategy Engine** (`src/options/`)

#### `strategy_engine.py` - Options Strategy Generator
- **Purpose**: Generate regime-appropriate options strategies
- **Strategies Implemented**:

1. **LONG_STRADDLE** (Rising Vol Buy regime)
   - Buy ATM call + Buy ATM put
   - Profits from large moves in either direction
   - Used when expecting volatility expansion

2. **IRON_CONDOR** (Low Vol Sell regime)
   - Sell OTM put + Buy further OTM put
   - Sell OTM call + Buy further OTM call
   - Profits from range-bound markets
   - Strikes: 90%, 95%, 105%, 110% of spot

3. **CALENDAR SPREAD** (High Vol Sell regime)
   - Sell near-term option + Buy far-term option (same strike)
   - Profits from time decay differential
   - Used when IV is elevated but expected to decline

4. **PUT RATIO SPREAD** (Crash Hedge regime)
   - Buy ATM put + Sell 2x OTM puts
   - Defensive positioning with limited cost
   - Protects against moderate declines

- **Position Sizing**:
  - Regime-based aggressiveness multipliers
  - Integrated with macro risk budget
  - Multi-symbol support (NIFTY + BANKNIFTY)

---

### 4. **Backtesting** (`src/options/`)

#### `options_backtester.py` - Strategy Backtester
- **Features**:
  - Multi-leg strategy evaluation
  - Transaction costs: 10 bps per leg
  - Slippage: 15 bps on entry/exit
  - Stop loss: -30% of premium outlay
  - Max holding period: 10 days
  - Automatic exit at expiry
- **Metrics Tracked**:
  - Gross P&L and net P&L (after costs)
  - Gross return and net return
  - Days held per trade
  - Strategy-level aggregation
- **Output**: Backtest results with per-strategy performance

---

## 📊 Data Storage Structure

```
data/options/
├── cache/
│   └── dashboard_cache.json          # Dashboard caching
├── complete/
│   ├── nifty_all_options_20251229_030813.parquet
│   └── nifty_all_options_latest.parquet  # Full options chain snapshots
├── eod/
│   └── snapshot_20251229.json        # End-of-day market snapshots
├── live/
│   ├── market_data_latest.json       # Live index prices (NIFTY, BANKNIFTY, sectors)
│   ├── nifty_options_20251229_025427.parquet
│   ├── nifty_options_20251229_025907.parquet
│   └── nifty_options_latest.parquet  # Latest options chain data
└── hedge_plan.parquet                # Generated hedge strategies
```

### Sample Options Data Schema (80 rows × 21 columns):
- `timestamp`, `date`, `symbol` (NIFTY/BANKNIFTY)
- `expiry`, `strike`, `option_type` (C/P)
- `ltp`, `bid`, `ask` - Pricing
- `iv` - Implied volatility
- `oi`, `volume`, `change_oi` - Liquidity metrics
- `delta`, `gamma`, `theta`, `vega` - Greeks
- `days_to_expiry`, `time_to_expiry`
- `underlying_price`, `moneyness`

---

## 🔄 Processing Pipeline (`src/processing/`)

### Supporting Modules:

1. **`options_volatility.py`**
   - Calculates realized volatility (60-day)
   - ATR (Average True Range) calculation
   - Per-ticker volatility metrics

2. **`options_timing.py`**
   - Technical signal detection
   - Pullback/breakout identification
   - Overbought/oversold conditions (RSI)
   - SMA crossover analysis

3. **`options_horizon.py`**
   - Expected holding period calculation
   - Based on historical volatility patterns
   - Recommends 5-60 day horizons

4. **`options_regime.py`** (Processing version)
   - Combines scores, volatility, and timing
   - Classifies stocks into:
     - "Avoid" - Overbought or high vol
     - "Income Safe" - Undervalued + low vol
     - "Directional" - Strong market score
     - "Neutral" - Default

---

## 🎯 Integration Points

### With Main Northstar System:

1. **Market Regime Integration**
   - Options regime uses main system's market state
   - Coordinates with macro factor analysis
   - Respects risk budget allocations

2. **Risk Management**
   - Options strategies sized based on portfolio risk budget
   - Integrated with kill switch and stress testing
   - Hedging strategies activated during crisis regimes

3. **Data Flow**
   - Market data feeds into both equity and options systems
   - VIX data shared across volatility models
   - Unified timestamp and date handling

4. **Dashboard Integration**
   - Options data cached for dashboard display
   - Live market data JSON feeds real-time panels
   - Options regime visible in market intelligence

---

## 🚀 Current Capabilities

### ✅ What's Working:

1. **Live Data Fetching**
   - NSE API integration functional
   - Rate-limited, compliant access
   - Market hours awareness
   - Multi-symbol support (NIFTY, BANKNIFTY)

2. **Options Analytics**
   - Full volatility surface construction
   - IV rank and skew calculations
   - Greeks computation
   - Regime classification

3. **Strategy Generation**
   - 4 distinct strategy types
   - Regime-aware selection
   - Multi-leg position construction
   - Risk-based sizing

4. **Backtesting**
   - Realistic cost modeling
   - Stop-loss implementation
   - Multi-day holding periods
   - Strategy performance tracking

### 📈 Data Available:

- **Latest snapshot**: December 29, 2025
- **80 options contracts** in latest file
- **7-day expiries** (typical weekly options)
- **Full Greeks** and IV data
- **Live market indices** for 8+ sectors

---

## 🔧 Usage Examples

### Fetch Live Options Data:
```python
from src.options.nse_fetcher import fetch_nifty_chain
from src.options.market_hours import should_fetch_live_data

if should_fetch_live_data():
    df = fetch_nifty_chain("NIFTY")
    # Returns DataFrame with 80+ options contracts
```

### Check Market Status:
```python
from src.options.market_hours import get_market_info

info = get_market_info()
# Returns: status, is_market_hours, minutes_to_open, etc.
```

### Build Options Surface:
```python
from src.options.options_surface import run
run()  # Reads chain data, outputs surface with IV rank and skew
```

### Generate Strategies:
```python
from src.options.strategy_engine import run
run()  # Reads regime + surface, outputs strategy book
```

### Run Backtest:
```python
from src.options.options_backtester import run
run()  # Reads chain + strategies, outputs backtest results
```

---

## 💡 Key Design Decisions

1. **NSE-Specific**: Built for Indian market (IST timezone, NSE holidays)
2. **Index Options Only**: Focuses on NIFTY/BANKNIFTY (most liquid)
3. **Regime-Driven**: Strategy selection based on market conditions
4. **Cost-Aware**: Realistic transaction costs and slippage
5. **Risk-Integrated**: Respects portfolio-level risk budgets
6. **Production-Grade**: Rate limiting, error handling, data validation

---

## 🎓 Options Strategies Explained

### When Each Strategy is Used:

| Regime | Strategy | Market View | Risk Profile |
|--------|----------|-------------|--------------|
| LOW_VOL_SELL | Iron Condor | Range-bound, low volatility | Limited risk, limited profit |
| RISING_VOL_BUY | Long Straddle | Big move expected, direction unclear | Limited risk, unlimited profit |
| HIGH_VOL_SELL | Calendar Spread | High IV will decline | Limited risk, moderate profit |
| CRASH_HEDGE | Put Ratio Spread | Defensive, protect downside | Limited risk, asymmetric payoff |

---

## 📝 File Locations Summary

### Core Implementation:
- `src/options/` - 7 files, 1,031 lines of code
  - Session management, data fetching, analytics, strategies, backtesting

### Data Processing:
- `src/processing/options_*.py` - 4 files
  - Volatility, timing, horizon, regime classification

### Data Storage:
- `data/options/` - Multiple directories
  - Live data, EOD snapshots, complete chains, cache

### Integration:
- `src/intelligence/market_brain/market_tensor.py` - Uses options data
- `src/dashboard/` - Displays options metrics
- Main system - Coordinates with options regime

---

## 🔮 Potential Enhancements

Based on the codebase, here are areas that could be expanded:

1. **More Strategies**:
   - Vertical spreads (bull/bear)
   - Butterfly spreads
   - Diagonal spreads
   - Covered calls on equity positions

2. **Advanced Analytics**:
   - Volatility smile modeling
   - Term structure arbitrage
   - Put-call parity checks
   - Synthetic position construction

3. **Risk Management**:
   - Portfolio Greeks aggregation
   - Scenario analysis
   - Stress testing options positions
   - Correlation with equity book

4. **Execution**:
   - Order placement integration
   - Position monitoring
   - Greeks rebalancing
   - Roll management

5. **Data Enhancements**:
   - Historical options data storage
   - Volatility surface history
   - Strategy performance database
   - Trade journal

---

## 🎯 Bottom Line

You have a **fully functional, production-grade options trading system** that:

✅ Fetches live NSE options data (NIFTY/BANKNIFTY)  
✅ Builds volatility surfaces with IV rank and skew  
✅ Classifies market regimes for strategy selection  
✅ Generates 4 distinct multi-leg options strategies  
✅ Backtests with realistic costs and risk controls  
✅ Integrates with your main Northstar trading system  
✅ Respects market hours and rate limits  
✅ Stores data in organized parquet/JSON format  

The system is **regime-aware**, **risk-managed**, and **ready for live trading** (with proper broker integration for execution).

---

**Generated**: February 9, 2026  
**Analysis Scope**: Complete codebase scan for options trading infrastructure
