# Options Trading System - User Guide

## Overview

The Options Trading System is an intelligent signal generation system for Indian index options (NIFTY and BANKNIFTY). It integrates with the Northstar v3 trading platform to provide regime-based strategy recommendations with comprehensive risk management.

**Important**: This is a **signal generation system only**. It does NOT execute trades automatically. All trades must be manually executed by the user through their broker's platform.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuration](#configuration)
3. [Understanding the Dashboard](#understanding-the-dashboard)
4. [Interpreting Signals](#interpreting-signals)
5. [Manual Trade Execution](#manual-trade-execution)
6. [Monitoring Positions](#monitoring-positions)
7. [Risk Management](#risk-management)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Upstox trading account with API access
- Northstar v3 system installed and configured
- Basic understanding of options trading

### Installation

The Options Trading System is already integrated with Northstar v3. No separate installation is required.

### First-Time Setup

1. **Obtain Upstox API Credentials**
   - Log in to your Upstox account
   - Navigate to API settings
   - Generate API key and secret
   - Note down your redirect URI

2. **Configure Environment Variables**
   ```bash
   export UPSTOX_API_KEY="your_api_key_here"
   export UPSTOX_API_SECRET="your_api_secret_here"
   export UPSTOX_REDIRECT_URI="your_redirect_uri_here"
   ```

3. **Update Configuration File**
   - Edit `config/options_trading.yaml`
   - Set your base capital
   - Review and adjust risk parameters if needed
   - Update event calendar with upcoming macro events

4. **Run Initial Test**
   ```bash
   python -m pytest tests/options/test_e2e_simple.py -v
   ```

---

## Configuration

### Main Configuration File

Location: `config/options_trading.yaml`

#### Key Settings

**Capital Settings**
```yaml
capital:
  base_capital: 100000  # Your starting capital in INR
  base_risk_pct: 0.01   # 1% risk per trade
  max_risk_pct: 0.015   # 1.5% maximum risk ceiling
```

**Regime Detection**
```yaml
regime_detection:
  iv_rank_lookback_days: 252  # 1 year of IV history
  vol_of_vol_threshold: 1.5   # Threshold for unstable volatility
  regime_persistence_days: 2  # Minimum days before trading
```

**Survival Rules**
```yaml
survival_rules:
  weekly_loss_limit_pct: 0.02  # 2% weekly loss limit
  portfolio_risk_cap_pct: 0.02 # 2% total portfolio risk
  trauma_loss_threshold: 0.80  # 80% of max loss triggers trauma
  max_trades_per_week: 2       # Maximum 2 trades per week
```

**Event Calendar**
```yaml
event_calendar:
  - event_type: "RBI_POLICY"
    dates:
      - "2026-02-07"
      - "2026-04-10"
    buffer_days: 2  # Block trading 2 days before event
```

### Environment Variables

Required environment variables:

```bash
# Upstox API Credentials
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_REDIRECT_URI=your_redirect_uri

# Optional: Logging Level
OPTIONS_LOG_LEVEL=INFO
```

---

## Understanding the Dashboard

### Accessing the Dashboard

1. Start the Northstar v3 dashboard:
   ```bash
   streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py
   ```

2. Navigate to the **Options Trading** panel

### Dashboard Sections

#### 1. Current Regime

Displays the current options market regime:

- **LOW_VOL_SELL**: IV rank > 70%, stable volatility → Iron Condor strategies
- **HIGH_VOL_SELL**: IV rank > 80%, elevated volatility → Calendar Spread strategies
- **RISING_VOL_BUY**: IV rank < 30%, expanding volatility → Long Straddle strategies
- **NEUTRAL**: No clear regime → No trading
- **CRASH_HEDGE**: Equity crisis → No short-vol trading

**Key Metrics**:
- IV Rank: Percentile rank of current IV (0-100%)
- IV Trend: Rising, falling, or stable
- Vol-of-Vol: Whether volatility is unstable
- Days in Regime: How long current regime has persisted
- Confidence: System confidence in regime classification (0-100%)

#### 2. Active Positions

Shows all open options positions:

| Field | Description |
|-------|-------------|
| Trade ID | Unique identifier |
| Strategy | IRON_CONDOR, CALENDAR_SPREAD, or LONG_STRADDLE |
| Entry Date | When position was opened |
| Days Held | Days since entry |
| Unrealized P&L | Current profit/loss |
| Max Loss | Maximum possible loss |
| Max Profit | Maximum possible profit |
| Exit Reason | Why position should be closed (if any) |

#### 3. Portfolio Greeks

Real-time portfolio-level Greeks:

- **Delta**: Directional exposure (-0.2 to +0.2 target)
- **Gamma**: Rate of delta change (monitor for escalation)
- **Theta**: Time decay (should be positive for short-vol)
- **Vega**: Volatility exposure (-0.3 to +0.1 target)

**Greek Safety Bands**:
- 🟢 Green: Within safe range
- 🟡 Yellow: Approaching limits
- 🔴 Red: Violation - close positions

#### 4. Trade History

Recent trade history with performance metrics:

- Win Rate: Percentage of profitable trades
- Average P&L: Mean profit/loss per trade
- Total P&L: Cumulative profit/loss
- Sharpe Ratio: Risk-adjusted returns
- Max Drawdown: Largest peak-to-trough decline

#### 5. Risk Metrics

Current risk status:

- **Weekly Risk Used**: Percentage of weekly loss limit used
- **Portfolio Risk**: Total risk across open positions
- **Capital Scaling**: Current risk per trade (adjusted for performance)
- **Kill Switch Status**: Whether any kill switches are active

#### 6. Next Trade Eligibility

Shows whether the system would approve a new trade:

- ✅ **Eligible**: All checks passed, ready to trade
- ❌ **Not Eligible**: One or more violations

**Common Rejection Reasons**:
- Regime not persistent (< 2 days)
- Weekly loss limit exceeded
- Portfolio risk cap exceeded
- Vol-of-vol elevated
- Macro event within 2 days
- Insufficient liquidity
- Expiry too close (< 5 days)

---

## Interpreting Signals

### Signal Generation Process

The system generates signals through this pipeline:

1. **Regime Detection** → Classifies current market regime
2. **Strategy Generation** → Creates appropriate strategy for regime
3. **Eligibility Validation** → Checks all risk and hygiene rules
4. **Signal Output** → Displays recommendation on dashboard

### When to Act on a Signal

✅ **Act on signal when**:
- Dashboard shows "Eligible" status
- Regime has persisted for 2+ days
- No kill switches are active
- You understand the strategy and risks
- You have time to monitor the position

❌ **Do NOT act on signal when**:
- Dashboard shows "Not Eligible"
- You don't understand the strategy
- You're unable to monitor positions
- Market conditions feel unusual
- You're emotionally compromised

### Signal Confidence Levels

The system provides confidence scores:

- **High (80-100%)**: Strong regime signal, favorable conditions
- **Medium (60-79%)**: Moderate confidence, acceptable conditions
- **Low (< 60%)**: Weak signal, consider skipping

**Best Practice**: Only trade signals with Medium or High confidence.

---

## Manual Trade Execution

### Step-by-Step Execution Process

#### 1. Review the Signal

- Check dashboard for "Eligible" status
- Review strategy details (strikes, expiries, quantities)
- Verify max loss and max profit
- Confirm you have sufficient capital

#### 2. Prepare for Execution

- Log in to your Upstox trading platform
- Navigate to options trading section
- Have the dashboard open for reference
- Note down all leg details

#### 3. Execute Each Leg

For an **Iron Condor** (4 legs):

1. **Sell Call Spread**:
   - Sell 1 lot of higher strike call (16-20 delta)
   - Buy 1 lot of even higher strike call (5-10 delta)

2. **Sell Put Spread**:
   - Sell 1 lot of higher strike put (16-20 delta)
   - Buy 1 lot of lower strike put (5-10 delta)

**Execution Tips**:
- Use limit orders, not market orders
- Execute all legs within 2-3 minutes
- Check bid-ask spreads before placing orders
- Verify lot sizes match system recommendation

#### 4. Record the Trade

After execution:
- Note actual entry prices for each leg
- Calculate actual net credit/debit
- Record trade ID from dashboard
- Set alerts for exit conditions

#### 5. Update System (if needed)

The system automatically tracks positions, but verify:
- Position appears in "Active Positions"
- Entry prices are correct
- Greeks are calculated

---

## Monitoring Positions

### Daily Monitoring Checklist

**Every Trading Day**:
1. Check dashboard for position updates
2. Review unrealized P&L
3. Monitor portfolio Greeks
4. Check for exit signals
5. Verify no kill switches activated

### Exit Conditions

The system will flag positions for exit when:

1. **Profit Target Hit** (55% of max profit)
   - Close position immediately
   - Lock in profits

2. **Stop Loss Hit** (40% of max loss)
   - Close position immediately
   - Limit losses

3. **2 Days Before Expiry**
   - Close position to avoid assignment risk
   - Even if profitable

4. **Regime Flip**
   - Market regime has changed
   - Close position as conditions no longer favorable

5. **Greek Violation**
   - Portfolio Greeks outside safety bands
   - Close positions to reduce exposure

### Exit Precedence

If multiple exit conditions trigger:
1. Stop Loss (highest priority)
2. Greek Violation
3. Expiry Proximity
4. Profit Target
5. Regime Flip

### Manual Exit Process

1. Check dashboard for exit reason
2. Log in to Upstox platform
3. Close all legs of the position
4. Use limit orders for better fills
5. Verify position closed on dashboard

---

## Risk Management

### Kill Switches

The system has multiple kill switches that halt trading:

#### 1. Weekly Loss Limit (2%)
- Tracks P&L from Monday 00:00 to Sunday 23:59 IST
- Halts trading if weekly loss ≥ 2% of capital
- Resets Monday 9:15 AM IST

**What to do**: Stop trading for the week, review what went wrong

#### 2. Portfolio Risk Cap (2%)
- Sums max losses across all open positions
- Blocks new trades if total risk > 2% of capital

**What to do**: Close some positions before opening new ones

#### 3. Trauma Rule
- Activates if single trade loses > 80% of max loss
- Blocks short-vol strategies for 2 weeks

**What to do**: Take a break, review risk management, only trade long-vol

#### 4. Tax Liquidity Check
- Calculates YTD tax liability (30% of profits)
- Halts trading if tax > cash buffer

**What to do**: Set aside cash for taxes, reduce position sizes

### Capital Scaling

The system automatically adjusts risk based on performance:

**Profit Scaling** (scales UP):
- +0.25% risk per 8% profit milestone
- Maximum 1.5% risk per trade

**Drawdown De-Scaling** (scales DOWN):
- -0.25% at 3% drawdown
- -0.50% at 5% drawdown

**Recovery Requirement**:
- Must reach previous high + 2 profitable trades
- Minimum 8 consecutive weeks before first scaling

### System Hygiene Rules

**Strategy Concentration Limit**:
- Maximum 2 consecutive trades of same strategy type
- 3rd consecutive trade blocked

**Success Cooling Period**:
- After 2 consecutive wins, skip next signal
- Exception: IV rank > 90% (extreme conditions)

---

## Troubleshooting

### Common Issues

#### Issue: "Regime not persistent" rejection

**Cause**: Regime has existed for < 2 days

**Solution**: Wait for regime to persist for 2+ days before trading

#### Issue: "Vol-of-vol elevated" rejection

**Cause**: Volatility is unstable (5-day std > 1.5× 20-day std)

**Solution**: Wait for volatility to stabilize, avoid short-vol strategies

#### Issue: "Insufficient liquidity" rejection

**Cause**: Bid-ask spread > 8% or bid quantity < 2× lot size

**Solution**: Choose more liquid strikes or wait for better liquidity

#### Issue: Dashboard not updating

**Cause**: Data fetch error or connection issue

**Solution**:
1. Check internet connection
2. Verify Upstox API credentials
3. Restart dashboard
4. Check logs: `logs/options_trading.log`

#### Issue: Position not showing on dashboard

**Cause**: Trade not recorded in system

**Solution**:
1. Check trade ledger: `data/options/trade_ledger.parquet`
2. Manually verify position in Upstox
3. Contact support if discrepancy persists

### Getting Help

**Log Files**:
- Main log: `logs/options_trading.log`
- Error log: `logs/errors/options_errors.log`

**Support Channels**:
- Check documentation: `docs/options/`
- Review design document: `.kiro/specs/options-trading-system/design.md`
- Run diagnostics: `python -m pytest tests/options/ -v`

---

## Best Practices

### Do's ✅

- Review dashboard daily during market hours
- Execute trades manually with limit orders
- Monitor positions throughout the day
- Close positions when exit signals trigger
- Keep detailed trade journal
- Update event calendar regularly
- Run tests after configuration changes
- Maintain cash buffer for taxes

### Don'ts ❌

- Don't ignore kill switches
- Don't override system rejections
- Don't trade without understanding strategy
- Don't use market orders
- Don't hold positions past expiry
- Don't trade during high-impact events
- Don't scale position sizes manually
- Don't trade when emotionally compromised

---

## Appendix

### Strategy Descriptions

**Iron Condor**:
- Sell OTM call spread + sell OTM put spread
- Net credit strategy
- Profits from range-bound movement
- Used in LOW_VOL_SELL regime

**Calendar Spread**:
- Sell near-term option + buy far-term option
- Same strike, different expiries
- Profits from time decay differential
- Used in HIGH_VOL_SELL regime

**Long Straddle**:
- Buy ATM call + buy ATM put
- Net debit strategy
- Profits from large moves in either direction
- Used in RISING_VOL_BUY regime

### Glossary

- **IV Rank**: Percentile rank of current IV over 252 days
- **Vol-of-Vol**: Volatility of volatility (stability measure)
- **Delta**: Directional exposure (positive = bullish, negative = bearish)
- **Theta**: Time decay (positive = earning decay, negative = paying decay)
- **Vega**: Volatility exposure (positive = long vol, negative = short vol)
- **Gamma**: Rate of delta change (risk of position becoming directional)
- **Kill Switch**: Automatic trading halt due to risk condition
- **Regime**: Market environment classification for strategy selection

---

**Version**: 1.0  
**Last Updated**: 2026-02-10  
**System**: Northstar v3 Options Trading Module
