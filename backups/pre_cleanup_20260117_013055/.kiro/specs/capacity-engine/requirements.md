# Requirements Document - Capacity Engine

## Introduction

The Capacity Engine transforms NorthStar from an unconstrained system (assuming infinite liquidity) into a capital-realistic system that answers the critical question: "How much AUM can NorthStar run before it breaks?"

This addresses the fundamental issue where returns explode in some runs due to unrealistic liquidity assumptions. The engine enforces capital realism through ADV-scaled position sizing, market impact modeling, crowding penalties, and systematic capacity analysis.

## Glossary

- **ADV**: Average Daily Volume - the average daily traded value in currency units
- **Market_Impact**: Price movement caused by large orders relative to daily liquidity
- **Capacity**: Maximum AUM the strategy can manage before alpha degrades significantly
- **Crowding_Penalty**: Reduction in alpha when trading overlaps with ETFs/other quants
- **Position_Governor**: System component that enforces liquidity-based position limits
- **Impact_Model**: Mathematical model calculating execution price degradation

## Requirements

### Requirement 1: ADV-Scaled Position Sizing

**User Story:** As a portfolio manager, I want position sizes constrained by daily liquidity, so that the system cannot take unrealistic positions that would be impossible to execute.

#### Acceptance Criteria

1. WHEN calculating target position size, THE Position_Governor SHALL limit position value to α × ADV where α ≤ 5%
2. WHEN ADV data is unavailable for a symbol, THE Position_Governor SHALL reject the position entirely
3. WHEN target position exceeds liquidity limit, THE Position_Governor SHALL cap position at maximum allowable size
4. THE Position_Governor SHALL use rolling 21-day ADV to account for liquidity changes
5. THE Position_Governor SHALL apply different α values by asset class (3% equities, 1% small-cap, 5% large-cap)

### Requirement 2: Market Impact Modeling

**User Story:** As a risk manager, I want realistic execution costs that account for market impact, so that large orders reflect true execution prices rather than mid-market fantasies.

#### Acceptance Criteria

1. WHEN executing an order, THE Impact_Model SHALL calculate impact using square-root formula: impact = k × σ × √(order_size/ADV)
2. WHEN order size exceeds 10% of ADV, THE Impact_Model SHALL apply enhanced impact penalty
3. THE Impact_Model SHALL use k-factor between 0.1-0.3 based on market conditions
4. WHEN applying impact, THE Impact_Model SHALL adjust fill price: fill_price = mid_price × (1 + sign(order) × impact)
5. THE Impact_Model SHALL track cumulative impact across multiple orders in same symbol

### Requirement 3: Crowding Penalty System

**User Story:** As a strategy designer, I want penalties for trading crowded factors, so that the system is forced to find differentiated alpha rather than following ETF flows.

#### Acceptance Criteria

1. WHEN calculating position weights, THE Crowding_Penalty SHALL compute correlation with momentum/quality/value ETFs
2. WHEN factor correlation exceeds 0.7, THE Crowding_Penalty SHALL reduce capital allocation by 50% × (correlation - 0.7)
3. THE Crowding_Penalty SHALL track rolling 63-day correlation with major factor ETFs
4. WHEN multiple factors are crowded, THE Crowding_Penalty SHALL apply multiplicative penalties
5. THE Crowding_Penalty SHALL maintain whitelist of differentiated signals exempt from crowding analysis

### Requirement 4: Capacity Analysis Engine

**User Story:** As a fund manager, I want to know maximum deployable AUM, so that I can set realistic fundraising targets and avoid capacity constraints.

#### Acceptance Criteria

1. WHEN running capacity analysis, THE Capacity_Engine SHALL test AUM levels: $10M, $50M, $100M, $250M, $500M, $1B
2. FOR EACH AUM level, THE Capacity_Engine SHALL measure CAGR degradation vs baseline
3. THE Capacity_Engine SHALL identify capacity knee where CAGR drops >20% from peak
4. WHEN capacity limit reached, THE Capacity_Engine SHALL generate capacity report with maximum recommended AUM
5. THE Capacity_Engine SHALL plot capacity curve showing CAGR vs AUM and Sharpe vs AUM

### Requirement 5: Liquidity-Aware Portfolio Construction

**User Story:** As a portfolio constructor, I want positions automatically sized for liquidity, so that the portfolio is always executable in real markets.

#### Acceptance Criteria

1. WHEN constructing portfolio, THE Portfolio_Constructor SHALL query ADV for all target positions
2. WHEN insufficient liquidity exists, THE Portfolio_Constructor SHALL redistribute capital to liquid alternatives
3. THE Portfolio_Constructor SHALL maintain minimum 20% cash buffer for liquidity management
4. WHEN market stress detected, THE Portfolio_Constructor SHALL reduce position sizes by 50%
5. THE Portfolio_Constructor SHALL reject positions in symbols with <$1M daily ADV

### Requirement 6: Dynamic Liquidity Monitoring

**User Story:** As a risk monitor, I want real-time liquidity tracking, so that position limits adjust automatically as market conditions change.

#### Acceptance Criteria

1. THE Liquidity_Monitor SHALL update ADV calculations daily using rolling windows
2. WHEN ADV drops >30% for held position, THE Liquidity_Monitor SHALL trigger position size reduction
3. THE Liquidity_Monitor SHALL classify symbols by liquidity tier (Large: >$50M ADV, Mid: $5-50M, Small: $1-5M)
4. WHEN liquidity tier changes, THE Liquidity_Monitor SHALL adjust position limits accordingly
5. THE Liquidity_Monitor SHALL generate liquidity alerts for positions approaching limits

### Requirement 7: Capacity Stress Testing

**User Story:** As a stress tester, I want capacity validation under adverse conditions, so that AUM limits remain valid during market stress.

#### Acceptance Criteria

1. WHEN stress testing capacity, THE Stress_Tester SHALL simulate 50% ADV reduction across all symbols
2. THE Stress_Tester SHALL test capacity during 2008, 2020, and 2022 market conditions
3. WHEN stress conditions applied, THE Stress_Tester SHALL measure maximum executable AUM
4. THE Stress_Tester SHALL require capacity limits valid under 95th percentile stress scenarios
5. THE Stress_Tester SHALL generate stress-adjusted capacity recommendations

### Requirement 8: Execution Reality Engine

**User Story:** As an execution trader, I want realistic execution simulation, so that backtests reflect true trading costs and constraints.

#### Acceptance Criteria

1. THE Execution_Engine SHALL simulate order splitting for large positions (>5% ADV)
2. WHEN splitting orders, THE Execution_Engine SHALL apply TWAP execution over multiple days
3. THE Execution_Engine SHALL model bid-ask spreads based on symbol liquidity tier
4. WHEN executing in stressed markets, THE Execution_Engine SHALL apply 2x impact multiplier
5. THE Execution_Engine SHALL track implementation shortfall vs theoretical performance