# Alpha Autopsy System Requirements

## Introduction

The Alpha Autopsy System performs surgical diagnosis on failed walk-forward validations to identify exactly what is destroying performance. This is not about backtesting or optimization - this is forensic analysis to separate signal from noise and identify which components deserve to live or die.

## Glossary

- **Alpha_Autopsy_System**: The forensic analysis engine that dissects walk-forward failures
- **Specialist_PnL_Analyzer**: Component that tracks profit/loss by individual specialists
- **Regime_Loss_Analyzer**: Component that identifies when losses occurred relative to regime changes
- **Timing_Analyzer**: Component that determines if losses are from late entry/exit or wrong signals
- **Cost_Attribution_Engine**: Component that breaks down total loss into specific cost components
- **Stability_Analyzer**: Component that measures performance variance across multiple runs
- **Forensic_Reporter**: Component that generates actionable diagnostic reports

## Requirements

### Requirement 1: Specialist Performance Forensics

**User Story:** As a quant researcher, I want to see PnL attribution by specialist, so that I can identify which alpha engines are bleeding capital.

#### Acceptance Criteria

1. WHEN analyzing walk-forward results, THE Specialist_PnL_Analyzer SHALL decompose total PnL by Momentum, Value, Quality, and Macro specialists
2. WHEN a specialist shows negative PnL, THE System SHALL calculate the specialist's contribution to total loss
3. WHEN multiple specialists are analyzed, THE System SHALL rank them by PnL contribution from worst to best
4. THE System SHALL track each specialist's hit rate, average win/loss, and Sharpe ratio independently
5. WHEN a specialist consistently loses money, THE System SHALL flag it for potential elimination

### Requirement 2: Regime-Based Loss Analysis

**User Story:** As a portfolio manager, I want to see when losses occurred relative to market regimes, so that I can identify regime transition failures.

#### Acceptance Criteria

1. WHEN analyzing drawdowns, THE Regime_Loss_Analyzer SHALL overlay loss periods with regime classifications
2. WHEN regime transitions occur, THE System SHALL measure performance in the 20 days before and after transitions
3. WHEN losses cluster around regime changes, THE System SHALL flag regime detection lag as a failure mode
4. THE System SHALL calculate PnL by regime type (Expansion, Recession, Crisis, Recovery)
5. WHEN a regime consistently produces losses, THE System SHALL identify it as a problem regime

### Requirement 3: Timing vs Selection Analysis

**User Story:** As a systematic trader, I want to know if losses come from bad timing or bad stock selection, so that I can fix the right problem.

#### Acceptance Criteria

1. WHEN analyzing trades, THE Timing_Analyzer SHALL separate timing losses from selection losses
2. WHEN regime changes occur, THE System SHALL measure if we enter too late or exit too late
3. WHEN positions are held, THE System SHALL track if individual stock selection is profitable net of timing
4. THE System SHALL calculate "perfect timing" PnL vs actual PnL to isolate timing drag
5. WHEN timing losses exceed selection losses, THE System SHALL flag regime detection as the primary issue

### Requirement 4: Cost Attribution Breakdown

**User Story:** As a fund manager, I want to see exactly how much each cost component is destroying returns, so that I can prioritize cost reduction efforts.

#### Acceptance Criteria

1. WHEN calculating total loss, THE Cost_Attribution_Engine SHALL break it down into: Gross Alpha, Slippage, Market Impact, Turnover Costs, Borrow Costs, and Crowding Penalties
2. WHEN transaction costs are high, THE System SHALL identify the primary cost driver
3. WHEN turnover is excessive, THE System SHALL calculate the cost per regime change
4. THE System SHALL compare gross alpha to net alpha to show the impact of all costs combined
5. WHEN costs exceed gross alpha, THE System SHALL flag the strategy as "cost-dominated"

### Requirement 5: Multi-Run Stability Analysis

**User Story:** As a risk manager, I want to measure performance stability across multiple identical runs, so that I can assess if the strategy has reliable edge or is just gambling.

#### Acceptance Criteria

1. WHEN multiple walk-forward runs are available, THE Stability_Analyzer SHALL calculate the distribution of final NAV values
2. WHEN the NAV distribution is wide, THE System SHALL flag the strategy as "unstable under perturbation"
3. WHEN runs show heavy downside tail, THE System SHALL calculate the probability of severe losses
4. THE System SHALL compute the coefficient of variation across runs to measure stability
5. WHEN stability is poor, THE System SHALL recommend increasing signal strength before parameter optimization

### Requirement 6: Forensic Reporting and Recommendations

**User Story:** As a portfolio manager, I want actionable recommendations based on the forensic analysis, so that I know exactly what to fix next.

#### Acceptance Criteria

1. WHEN analysis is complete, THE Forensic_Reporter SHALL generate a ranked list of failure modes
2. WHEN a specialist is bleeding, THE System SHALL recommend elimination or redesign
3. WHEN regime timing is poor, THE System SHALL recommend regime detection improvements
4. WHEN costs dominate, THE System SHALL recommend specific turnover reduction strategies
5. THE System SHALL provide a "kill list" of components that should be eliminated and a "fix list" of components that should be improved

### Requirement 7: Historical Walk-Forward Integration

**User Story:** As a researcher, I want to analyze multiple historical walk-forward results, so that I can identify consistent failure patterns across different time periods.

#### Acceptance Criteria

1. WHEN multiple sealed walk-forward results exist, THE System SHALL load and analyze all of them
2. WHEN analyzing historical results, THE System SHALL identify consistent failure patterns across time periods
3. WHEN a specialist fails in multiple periods, THE System SHALL flag it as systematically flawed
4. THE System SHALL track how failure modes evolve over different market conditions
5. WHEN patterns are identified, THE System SHALL recommend structural changes to prevent recurring failures

### Requirement 8: Real-Time Forensic Monitoring

**User Story:** As a live trader, I want real-time forensic analysis during live trading, so that I can detect failure modes as they develop.

#### Acceptance Criteria

1. WHEN live trading is active, THE System SHALL continuously monitor specialist performance
2. WHEN a specialist starts bleeding in real-time, THE System SHALL alert immediately
3. WHEN regime transitions occur, THE System SHALL monitor timing performance in real-time
4. THE System SHALL track rolling cost attribution to detect when costs start dominating
5. WHEN failure modes are detected, THE System SHALL recommend immediate defensive actions

## Notes

This system is designed to perform "alpha autopsy" - forensic analysis that tells us exactly what killed performance. It's not about optimization or curve fitting - it's about surgical diagnosis to separate what works from what doesn't.

The goal is to answer the three critical questions:
1. Which specialist is bleeding?
2. When did the losses occur?
3. Are we late or wrong?

Only with this forensic analysis can we make the hard decisions about what to kill and what to keep.