# Implementation Tasks - Capacity Engine

## Overview

This document outlines the implementation tasks for the Capacity Engine - the system that transforms NorthStar from an unconstrained research prototype into a capital-realistic fund engine that can answer: "How much AUM can this safely run?"

The implementation follows the institutional transformation pattern established in TIER 1, building on the Signal Quality Gate, Position Inertia System, and Regime-Locked Capital Allocator.

---

## Task 1: ADV-Scaled Position Governor

**Priority**: HIGH  
**Estimated Effort**: 3-4 hours  
**Dependencies**: None  

### Objective
Implement liquidity-constrained position sizing that prevents unrealistic positions exceeding daily trading volume limits.

### Implementation Steps

1. **Create ADV Database Interface**
   - File: `src/intelligence/adv_database.py`
   - Implement rolling ADV calculations (21-day, 63-day windows)
   - Support multiple data sources (market data feeds, historical files)
   - Handle missing/stale data gracefully

2. **Build Position Governor Core**
   - File: `src/intelligence/position_governor.py`
   - Implement α × ADV position limits by asset class
   - Create liquidity tier classification (Large/Mid/Small cap)
   - Add position rejection logic for insufficient liquidity

3. **Integration with Existing Systems**
   - Integrate with Signal Quality Gate for pre-filtering
   - Connect to Regime-Locked Capital Allocator for capital limits
   - Add to walk-forward validation pipeline

### Acceptance Criteria
- [ ] Position values never exceed α × ADV limits
- [ ] Positions rejected when ADV < $1M daily
- [ ] Different α factors applied by asset class (3% equity, 1% small-cap, 5% large-cap)
- [ ] Rolling 21-day ADV updates automatically
- [ ] Integration tests pass with existing institutional components

### Validation
- Property test: All positions ≤ α × ADV across random portfolios
- Unit test: ADV calculation accuracy vs known benchmarks
- Integration test: End-to-end position sizing with real market data

---

## Task 2: Market Impact Model

**Priority**: HIGH  
**Estimated Effort**: 4-5 hours  
**Dependencies**: Task 1 (ADV Database)  

### Objective
Implement realistic execution cost modeling using square-root market impact formula to replace mid-market fantasy pricing.

### Implementation Steps

1. **Core Impact Model**
   - File: `src/execution/market_impact_model.py`
   - Implement square-root formula: impact = k × σ × √(order_size/ADV)
   - Dynamic k-factor based on market conditions (0.1-0.3 range)
   - Enhanced penalties for orders >10% ADV

2. **Execution Price Calculator**
   - Calculate realistic fill prices: fill_price = mid_price × (1 + sign(order) × impact)
   - Track cumulative impact for multiple orders in same symbol
   - Apply bid-ask spread modeling by liquidity tier

3. **Market Regime Integration**
   - Connect to regime detection for stress multipliers (2x impact in crisis)
   - Seasonal impact adjustments (higher costs in Q1, lower in Q2-Q3)
   - Volatility-adjusted impact calculations

### Acceptance Criteria
- [ ] Impact increases monotonically with order size
- [ ] Orders >10% ADV receive enhanced impact penalty
- [ ] k-factor adjusts based on market conditions
- [ ] Fill prices reflect realistic execution costs
- [ ] Cumulative impact tracking across multiple orders

### Validation
- Property test: Market impact monotonicity across order sizes
- Benchmark test: Impact model vs academic literature (Almgren-Chriss)
- Historical test: Validate impact costs against known execution data

---

## Task 3: Crowding Penalty System

**Priority**: MEDIUM  
**Estimated Effort**: 3-4 hours  
**Dependencies**: None  

### Objective
Implement anti-correlation system that penalizes strategies overlapping with ETF flows, forcing differentiated alpha discovery.

### Implementation Steps

1. **ETF Correlation Engine**
   - File: `src/intelligence/crowding_penalty_system.py`
   - Calculate rolling 63-day correlation with major factor ETFs
   - Track momentum (MTUM, VMOT), quality (QUAL, JQUA), value (VLUE, VMVL), size (IWM, VB)
   - Implement correlation threshold detection (>0.7 triggers penalty)

2. **Penalty Application Logic**
   - Apply multiplicative penalties: penalty = 1 - 0.5 × (correlation - 0.7)
   - Handle multiple factor crowding with compound penalties
   - Maintain whitelist for differentiated signals exempt from analysis

3. **Factor Exposure Analysis**
   - Decompose portfolio into factor loadings
   - Generate crowding reports showing ETF overlap
   - Alert system for high correlation periods

### Acceptance Criteria
- [ ] Correlation >0.7 triggers 50% capital reduction
- [ ] Multiple crowded factors apply multiplicative penalties
- [ ] Rolling 63-day correlation updates automatically
- [ ] Whitelist exempts differentiated signals
- [ ] Factor exposure reports generated

### Validation
- Property test: Crowding penalty consistency across correlation levels
- Unit test: Factor decomposition accuracy
- Integration test: Penalty application in portfolio construction

---

## Task 4: Capacity Analysis Engine

**Priority**: HIGH  
**Estimated Effort**: 5-6 hours  
**Dependencies**: Tasks 1, 2, 3  

### Objective
Build systematic AUM testing engine that discovers strategy capacity limits through empirical analysis across $10M-$1B range.

### Implementation Steps

1. **Capacity Testing Framework**
   - File: `src/validation/capacity_analysis_engine.py`
   - Implement AUM sweep across test levels: $10M, $50M, $100M, $250M, $500M, $1B
   - Run walk-forward validation at each AUM level
   - Measure CAGR degradation vs baseline performance

2. **Capacity Metrics Calculator**
   - Track CAGR, Sharpe ratio, max drawdown by AUM level
   - Calculate implementation shortfall (theoretical vs actual performance)
   - Measure turnover increase due to liquidity constraints
   - Identify capacity knee where performance drops >20%

3. **Capacity Reporting System**
   - Generate capacity curves (CAGR vs AUM, Sharpe vs AUM)
   - Create capacity reports with maximum recommended AUM
   - Stress-test capacity under adverse market conditions
   - Export results for institutional due diligence

### Acceptance Criteria
- [ ] AUM sweep tests $10M to $1B systematically
- [ ] CAGR degradation measured vs baseline
- [ ] Capacity knee identified (>20% performance drop)
- [ ] Capacity curves generated and exported
- [ ] Stress-adjusted capacity recommendations provided

### Validation
- Property test: Capacity degradation (CAGR stable or decreasing with AUM)
- Benchmark test: Capacity limits vs academic fund literature
- Stress test: Capacity validation under 2008, 2020, 2022 conditions

---

## Task 5: Liquidity-Aware Portfolio Construction

**Priority**: MEDIUM  
**Estimated Effort**: 3-4 hours  
**Dependencies**: Task 1 (Position Governor)  

### Objective
Implement portfolio construction that automatically sizes positions for liquidity and redistributes capital when constraints bind.

### Implementation Steps

1. **Liquidity-Aware Constructor**
   - File: `src/portfolio/liquidity_aware_constructor.py`
   - Query ADV for all target positions before construction
   - Redistribute capital from illiquid to liquid alternatives
   - Maintain minimum 20% cash buffer for liquidity management

2. **Dynamic Position Sizing**
   - Reduce position sizes by 50% during market stress
   - Reject positions in symbols with <$1M daily ADV
   - Apply position scaling based on liquidity tier classification

3. **Capital Reallocation Logic**
   - When liquidity constraints bind, find liquid substitutes
   - Preserve factor exposures while respecting liquidity limits
   - Generate liquidity constraint reports for analysis

### Acceptance Criteria
- [ ] ADV queried for all positions before construction
- [ ] Capital redistributed when liquidity insufficient
- [ ] 20% minimum cash buffer maintained
- [ ] 50% position reduction during market stress
- [ ] Positions <$1M ADV rejected automatically

### Validation
- Unit test: Capital redistribution logic accuracy
- Integration test: Portfolio construction with liquidity constraints
- Stress test: Portfolio behavior during liquidity crises

---

## Task 6: Dynamic Liquidity Monitoring

**Priority**: MEDIUM  
**Estimated Effort**: 2-3 hours  
**Dependencies**: Task 1 (ADV Database)  

### Objective
Implement real-time liquidity tracking that adjusts position limits automatically as market conditions change.

### Implementation Steps

1. **Liquidity Monitor Core**
   - File: `src/intelligence/liquidity_monitor.py`
   - Update ADV calculations daily using rolling windows
   - Detect ADV drops >30% for held positions
   - Classify symbols by liquidity tier with automatic updates

2. **Alert and Response System**
   - Trigger position size reduction when ADV drops significantly
   - Generate liquidity alerts for positions approaching limits
   - Adjust position limits when liquidity tier changes

3. **Monitoring Dashboard Integration**
   - Real-time liquidity utilization displays
   - Historical liquidity trend analysis
   - Liquidity constraint violation tracking

### Acceptance Criteria
- [ ] Daily ADV updates using rolling windows
- [ ] ADV drops >30% trigger position reduction
- [ ] Liquidity tier classification updates automatically
- [ ] Position limits adjust with tier changes
- [ ] Liquidity alerts generated for limit violations

### Validation
- Property test: Liquidity tier stability over time
- Unit test: ADV calculation and alert accuracy
- Integration test: Position limit adjustments

---

## Task 7: Capacity Stress Testing

**Priority**: MEDIUM  
**Estimated Effort**: 3-4 hours  
**Dependencies**: Task 4 (Capacity Analysis Engine)  

### Objective
Validate capacity limits under adverse market conditions to ensure AUM recommendations remain valid during stress periods.

### Implementation Steps

1. **Stress Testing Framework**
   - File: `src/validation/capacity_stress_tester.py`
   - Simulate 50% ADV reduction across all symbols
   - Test capacity during historical crisis periods (2008, 2020, 2022)
   - Measure maximum executable AUM under stress

2. **Stress Scenario Engine**
   - Implement multiple stress scenarios (liquidity crisis, market crash, volatility spike)
   - Apply stress conditions to capacity analysis
   - Generate stress-adjusted capacity recommendations

3. **Stress Reporting System**
   - Require capacity limits valid under 95th percentile stress
   - Generate stress test reports for risk management
   - Compare normal vs stress-adjusted capacity limits

### Acceptance Criteria
- [ ] 50% ADV reduction stress test implemented
- [ ] Historical crisis period testing (2008, 2020, 2022)
- [ ] Maximum executable AUM measured under stress
- [ ] 95th percentile stress scenario validation
- [ ] Stress-adjusted capacity recommendations generated

### Validation
- Property test: Stress capacity ≤ normal capacity
- Historical test: Stress scenarios vs actual crisis performance
- Benchmark test: Stress assumptions vs industry standards

---

## Task 8: Execution Reality Engine

**Priority**: MEDIUM  
**Estimated Effort**: 4-5 hours  
**Dependencies**: Task 2 (Market Impact Model)  

### Objective
Implement realistic execution simulation that models order splitting, TWAP execution, and bid-ask spreads for institutional-grade backtesting.

### Implementation Steps

1. **Order Splitting Logic**
   - File: `src/execution/execution_reality_engine.py`
   - Split orders >5% ADV across multiple days
   - Implement TWAP (Time-Weighted Average Price) execution
   - Model execution timing and market impact accumulation

2. **Bid-Ask Spread Modeling**
   - Apply spreads based on liquidity tier classification
   - Model spread widening during market stress (2x multiplier)
   - Track implementation shortfall vs theoretical performance

3. **Execution Cost Analysis**
   - Calculate total execution costs (impact + spread + timing)
   - Compare actual vs theoretical performance
   - Generate execution quality reports

### Acceptance Criteria
- [ ] Orders >5% ADV split across multiple days
- [ ] TWAP execution simulation implemented
- [ ] Bid-ask spreads modeled by liquidity tier
- [ ] 2x spread multiplier during market stress
- [ ] Implementation shortfall tracking vs theoretical

### Validation
- Property test: Execution costs exceed theoretical mid-market
- Unit test: Order splitting and TWAP accuracy
- Integration test: End-to-end execution simulation

---

## Task 9: Integration with Walk-Forward Engine

**Priority**: HIGH  
**Estimated Effort**: 2-3 hours  
**Dependencies**: All previous tasks  

### Objective
Integrate all Capacity Engine components into the existing walk-forward validation system for end-to-end capacity analysis.

### Implementation Steps

1. **Walk-Forward Integration**
   - File: `scripts/run_capacity_walk_forward.py`
   - Integrate Position Governor, Impact Model, Crowding Penalties
   - Add capacity analysis to existing validation pipeline
   - Maintain compatibility with institutional transformation components

2. **Capacity-Aware Validation**
   - Run walk-forward validation with capacity constraints
   - Generate capacity-constrained performance metrics
   - Compare constrained vs unconstrained results

3. **End-to-End Testing**
   - Validate complete capacity-aware system
   - Test integration with Signal Quality Gate, Position Inertia, Regime-Locked Allocator
   - Ensure institutional-grade variance control maintained

### Acceptance Criteria
- [ ] All capacity components integrated into walk-forward engine
- [ ] Capacity-constrained validation runs successfully
- [ ] Performance comparison (constrained vs unconstrained) generated
- [ ] Integration with existing institutional components maintained
- [ ] End-to-end system validation passes

### Validation
- Integration test: Complete capacity-aware walk-forward validation
- Performance test: Capacity system computational efficiency
- Regression test: Institutional transformation components still function

---

## Task 10: Capacity Discovery and Reporting

**Priority**: HIGH  
**Estimated Effort**: 2-3 hours  
**Dependencies**: Task 9 (Integration)  

### Objective
Run comprehensive capacity analysis to discover NorthStar's actual AUM limits and generate institutional-grade capacity reports.

### Implementation Steps

1. **Capacity Discovery Script**
   - File: `scripts/discover_northstar_capacity.py`
   - Run systematic capacity sweep across AUM levels
   - Identify capacity knee and maximum recommended AUM
   - Generate capacity curves and analysis reports

2. **Institutional Reporting**
   - Create capacity report for institutional investors
   - Include stress-adjusted capacity recommendations
   - Provide liquidity constraint analysis and crowding penalties
   - Export results in institutional formats (PDF, Excel)

3. **Capacity Monitoring Dashboard**
   - Add capacity metrics to NorthStar Command Bridge
   - Real-time capacity utilization tracking
   - Capacity limit alerts and warnings

### Acceptance Criteria
- [ ] Systematic capacity sweep completed across $10M-$1B
- [ ] Capacity knee identified and documented
- [ ] Maximum recommended AUM determined
- [ ] Institutional capacity report generated
- [ ] Capacity monitoring integrated into dashboard

### Validation
- Final test: Complete capacity analysis with real market data
- Report validation: Capacity recommendations vs industry benchmarks
- Dashboard test: Capacity monitoring functionality

---

## Implementation Priority and Timeline

### Phase 1: Core Capacity Infrastructure (Tasks 1-2)
**Timeline**: 1-2 days  
**Focus**: ADV-scaled position sizing and market impact modeling

### Phase 2: Advanced Capacity Features (Tasks 3-4)
**Timeline**: 1-2 days  
**Focus**: Crowding penalties and capacity analysis engine

### Phase 3: Portfolio Integration (Tasks 5-6)
**Timeline**: 1 day  
**Focus**: Liquidity-aware construction and monitoring

### Phase 4: Stress Testing and Execution (Tasks 7-8)
**Timeline**: 1 day  
**Focus**: Capacity validation under stress and execution reality

### Phase 5: System Integration (Tasks 9-10)
**Timeline**: 1 day  
**Focus**: Walk-forward integration and capacity discovery

**Total Estimated Timeline**: 5-6 days

---

## Success Criteria

### Technical Success
- [ ] All capacity components implemented and tested
- [ ] Integration with existing institutional transformation maintained
- [ ] Property tests pass for all capacity constraints
- [ ] End-to-end capacity analysis completes successfully

### Business Success
- [ ] NorthStar's maximum AUM capacity identified
- [ ] Capacity limits validated under stress conditions
- [ ] Institutional-grade capacity reports generated
- [ ] System ready for capital deployment with known limits

### Institutional Readiness
- [ ] Capital realism enforced through ADV constraints
- [ ] Market impact costs realistically modeled
- [ ] Crowding penalties prevent factor overlap
- [ ] Capacity analysis provides fund-ready AUM guidance

---

## Risk Mitigation

### Technical Risks
- **ADV Data Quality**: Implement robust data validation and fallback mechanisms
- **Performance Impact**: Optimize capacity calculations for real-time operation
- **Integration Complexity**: Maintain backward compatibility with existing systems

### Business Risks
- **Conservative Capacity**: Better to underestimate than overestimate capacity limits
- **Market Regime Changes**: Stress test capacity across multiple market conditions
- **Liquidity Assumptions**: Use conservative ADV estimates and safety margins

---

## Post-Implementation

### Monitoring and Maintenance
- Daily ADV updates and liquidity monitoring
- Monthly capacity utilization reports
- Quarterly capacity limit reviews and updates
- Annual stress testing and capacity revalidation

### Continuous Improvement
- Refine capacity models based on live trading experience
- Enhance crowding penalty system with new factor ETFs
- Optimize execution reality engine with actual execution data
- Expand capacity analysis to new asset classes and markets

---

*This completes the Capacity Engine specification and implementation plan. The system will transform NorthStar from "does this work?" to "how much money can this safely run?" - the critical question for institutional capital deployment.*