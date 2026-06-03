# Options Trading System

Institutional-grade options trading system integrated with Northstar v3.

## Features

- **Live Options Data**: Upstox API integration for real-time option chains, Greeks, and IV
- **Regime Detection**: Automatic classification of market conditions (LOW_VOL_SELL, HIGH_VOL_SELL, RISING_VOL_BUY, etc.)
- **Strategy Generation**: Automated generation of Iron Condors, Calendar Spreads, and Long Straddles
- **Risk Management**: Multi-layer risk controls including capital scaling, survival rules, and Greek monitoring
- **Tax-Aware P&L**: Accurate post-tax P&L calculation for India VDA regime (30% flat tax)
- **Dashboard Integration**: Real-time monitoring via Streamlit dashboard
- **Immutable Audit Trail**: Append-only trade ledger for compliance

## Architecture

```
src/options/
├── __init__.py
├── config_loader.py          # Configuration management
├── upstox_adapter.py          # Upstox API integration (Task 2)
├── regime_detector.py         # Market regime detection (Task 4)
├── strategy_generator.py      # Strategy generation (Task 5)
├── eligibility_validator.py   # Trade eligibility rules (Task 7)
├── capital_scaling.py         # Dynamic risk adjustment (Task 8)
├── survival_rules.py          # Circuit breakers (Task 10)
├── position_manager.py        # Position tracking (Task 11)
├── pnl_tracker.py             # Tax-aware P&L (Task 13)
├── trade_ledger.py            # Immutable audit trail (Task 14)
└── dashboard/                 # Dashboard components (Task 18)
```

## Configuration

Configuration is loaded from:
1. `config/options_trading.yaml` - Main configuration file
2. `.env.options` - Upstox API credentials (never commit!)

### Environment Variables

```bash
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=your_access_token
```

### Key Configuration Sections

- **capital**: Base capital, risk percentages
- **upstox**: API credentials and endpoints
- **strategies**: Strategy parameters (Iron Condor, Calendar, Straddle)
- **regime_detection**: IV rank thresholds, vol-of-vol checks
- **eligibility**: Liquidity, expiry, event calendar rules
- **capital_scaling**: Profit/drawdown scaling rules
- **survival_rules**: Kill switches, frequency limits
- **exit_rules**: Profit targets, stop losses, Greek bands
- **costs**: Brokerage, exchange charges, tax rates
- **event_calendar**: Macro events (RBI, CPI, WPI, Budget)

## Usage

### Load Configuration

```python
from src.options.config_loader import get_config

config = get_config()
print(f"Base capital: ₹{config.capital.base_capital:,.0f}")
print(f"Allowed strategies: {config.strategies.allowed}")
```

### Test Configuration

```bash
python src/options/config_loader.py
```

## Safety Features

### 4 Critical Gaps Addressed

1. **Vol-of-Vol Check**: Blocks short-vol if IV volatility elevated
2. **Event Calendar**: Blocks short-vol 2 days before macro events
3. **Lot Size Validation**: Rejects fractional lot trades
4. **Liquidity Depth**: Requires bid_qty ≥ 2 × lot_size

### Kill Switches

- **Weekly Loss Limit**: Halt if weekly loss ≥ 2% capital
- **Trauma Rule**: Block short-vol for 2 weeks after 80% max loss
- **Portfolio Risk Cap**: Total open risk ≤ 2% capital
- **Tax Liquidity**: Halt if YTD tax > cash buffer

### Capital Scaling

- **Profit Scaling**: +0.25% risk per 8% net profit milestone
- **Drawdown De-Scaling**: -0.25% at 3% DD, -0.50% at 5% DD
- **Time Requirement**: No scaling before 8 weeks live
- **Hard Ceiling**: Max 1.5% risk per trade (never exceeded)

## Integration with Northstar v3

- **UnifiedState**: Options positions and metrics stored in state
- **RiskCoordinator**: Options risk validators added to hierarchy
- **Dashboard**: New OptionsPanel component
- **Event Bus**: Options events published to existing bus
- **Audit Trail**: Options trades logged to immutable ledger

## Testing

```bash
# Run all options tests
pytest tests/options/

# Run property-based tests only
pytest tests/options/ -m property

# Run specific test file
pytest tests/options/test_config_loader.py
```

## Data Storage

- **Trade Ledger**: `data/options/trade_ledger.parquet` (append-only)
- **Regime History**: `data/options/regime_history.parquet`
- **IV History**: `data/options/iv_history.parquet`
- **Position Snapshots**: `data/options/position_snapshots.parquet`

## Logging

Logs are written to:
- `logs/options_trading.log` - General logs
- `logs/options_errors.log` - Error logs only
- `logs/options_decisions.log` - Decision audit trail (JSON format)

## Development Status

- [x] Task 1: Infrastructure setup
- [ ] Task 2: Upstox adapter
- [ ] Task 4: Regime detection
- [ ] Task 5: Strategy generation
- [ ] Task 7: Eligibility validation
- [ ] Task 8: Capital scaling
- [ ] Task 10: Survival rules
- [ ] Task 11: Position management
- [ ] Task 13: Tax-aware P&L
- [ ] Task 14: Trade ledger
- [ ] Task 18: Dashboard integration

## Security

**CRITICAL**: Never commit credentials to version control!

- `.env.options` is in `.gitignore`
- Use `.env.options.template` as a template
- Rotate access tokens regularly (Upstox tokens expire daily)

## Support

For questions or issues, refer to:
- Design document: `.kiro/specs/options-trading-system/design.md`
- Requirements: `.kiro/specs/options-trading-system/requirements.md`
- Tasks: `.kiro/specs/options-trading-system/tasks.md`
