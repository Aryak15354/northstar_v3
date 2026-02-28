# System Hygiene Rules Implementation

## Overview

Implemented system hygiene rules to prevent overtrading and revenge trading through disciplined constraints on strategy selection and trade frequency.

## Implementation Details

### File: `src/options/system_hygiene.py`

**Class: `SystemHygieneRules`**

Core responsibilities:
- Enforce strategy concentration limits
- Enforce success cooling periods
- Track recent trade history
- Provide hygiene check results

### Key Features

1. **Strategy Concentration Limit**
   - Tracks last 2 trades
   - Rejects 3rd consecutive trade of same strategy type
   - Prevents fixation on single strategy
   - Promotes strategy diversity

2. **Success Cooling Period**
   - Tracks last 2 trades
   - Pauses trading after 2 consecutive wins
   - Exception: Allows trading if IV rank extreme (>90% or <10%)
   - Prevents overconfidence and revenge trading

3. **Trade History Tracking**
   - Efficient deque-based storage (max 10 trades)
   - Tracks: trade_id, timestamp, strategy_type, regime, profitability, P&L
   - Provides summary statistics

4. **Hygiene Check Results**
   - Clear allowed/blocked status
   - Detailed reason codes
   - Human-readable explanations

### Rules Logic

#### Strategy Concentration

```python
# Rule: No 3rd consecutive trade of same strategy
Last 2 trades: [iron_condor, iron_condor]
Proposed: iron_condor
Result: BLOCKED (would be 3rd consecutive)

Last 2 trades: [iron_condor, calendar_spread]
Proposed: iron_condor
Result: ALLOWED (diversity maintained)
```

#### Success Cooling

```python
# Rule: Pause after 2 consecutive wins (unless IV extreme)
Last 2 trades: [WIN, WIN]
IV Rank: 75%
Result: BLOCKED (cooling period active)

Last 2 trades: [WIN, WIN]
IV Rank: 92% (>90%)
Result: ALLOWED (IV extreme high - exception)

Last 2 trades: [WIN, LOSS]
IV Rank: 75%
Result: ALLOWED (not all wins)
```

### Data Models

**TradeRecord**:
```python
@dataclass
class TradeRecord:
    trade_id: str
    timestamp: datetime
    strategy_type: str
    regime: Regime
    was_profitable: bool
    net_pnl: float
```

**HygieneCheckResult**:
```python
@dataclass
class HygieneCheckResult:
    allowed: bool
    reason: str
    details: str
```

## Testing

### File: `tests/options/test_system_hygiene.py`

**Test Coverage: 15 tests, all passing**

1. `test_initial_state` - Empty history allows all
2. `test_strategy_concentration_allowed` - Diverse strategies allowed
3. `test_strategy_concentration_blocked` - 3rd consecutive blocked
4. `test_strategy_concentration_resets_with_different_strategy` - Counter resets
5. `test_success_cooling_not_triggered_with_losses` - Losses prevent cooling
6. `test_success_cooling_triggered` - 2 wins trigger cooling
7. `test_success_cooling_bypassed_extreme_high_iv` - High IV exception
8. `test_success_cooling_bypassed_extreme_low_iv` - Low IV exception
9. `test_success_cooling_not_bypassed_moderate_iv` - Moderate IV blocked
10. `test_check_all_hygiene_rules_pass` - All checks pass
11. `test_check_all_hygiene_rules_fail_concentration` - Concentration fails
12. `test_check_all_hygiene_rules_fail_cooling` - Cooling fails
13. `test_get_recent_trades_summary` - Summary statistics
14. `test_consecutive_wins_count` - Win streak tracking
15. `test_reset` - History reset

**Test Results**: ✅ 15/15 passed

## Usage Example

```python
from src.options.system_hygiene import SystemHygieneRules
from src.options.regime_detector import Regime

# Initialize hygiene rules
hygiene = SystemHygieneRules(
    concentration_lookback=2,
    cooling_lookback=2,
    iv_rank_extreme_threshold=0.90,
    iv_rank_extreme_low=0.10
)

# Add completed trades
hygiene.add_trade(
    trade_id="T1",
    timestamp=datetime.now(),
    strategy_type="iron_condor",
    regime=Regime.LOW_VOL_SELL,
    was_profitable=True,
    net_pnl=1000.0
)

# Check if new trade allowed
result = hygiene.check_all_hygiene_rules(
    proposed_strategy_type="iron_condor",
    iv_rank=0.75
)

if result.allowed:
    print("Trade allowed")
else:
    print(f"Trade blocked: {result.reason}")
    print(f"Details: {result.details}")

# Get summary
summary = hygiene.get_recent_trades_summary()
print(f"Win rate: {summary['win_rate']:.1%}")
print(f"Consecutive wins: {summary['consecutive_wins']}")
```

## Integration Points

1. **Signal Generation**: Check hygiene before generating signals
2. **Trade Ledger**: Add trades to hygiene tracker on close
3. **Dashboard**: Display hygiene status and recent trades
4. **Risk System**: Hygiene checks as part of trade approval

## Philosophy

These rules enforce **discipline over activity**:

1. **Concentration Limit**: Prevents fixation on single strategy
   - Forces strategy diversity
   - Reduces correlation risk
   - Prevents "hammer looking for nails" syndrome

2. **Cooling Period**: Prevents overconfidence after wins
   - Enforces pause after success
   - Reduces revenge trading
   - Allows IV extreme exceptions (rare opportunities)

The system is designed to **not die in options** through selectivity, not activity.

## Benefits

1. **Prevents Overtrading**: Hard limits on consecutive same-strategy trades
2. **Reduces Emotional Trading**: Cooling period after wins
3. **Maintains Discipline**: Systematic rules, not discretion
4. **Allows Exceptions**: IV extreme conditions bypass cooling
5. **Trackable**: Full audit trail of hygiene decisions

## Configuration

Default parameters (tunable):
- `concentration_lookback`: 2 trades
- `cooling_lookback`: 2 trades
- `iv_rank_extreme_threshold`: 90% (high)
- `iv_rank_extreme_low`: 10% (low)

These can be adjusted based on trading style and market conditions.

## Next Steps

- Task 17: V3 Risk System Integration (RiskCoordinator, Event Bus)
- Task 18: Dashboard Integration (OptionsPanel, OptionsObserver)
- Task 19: Backtesting Support

## Status

✅ **Task 15 Complete**: System hygiene rules fully implemented and tested

Both concentration limits and cooling periods working as designed with comprehensive test coverage.
