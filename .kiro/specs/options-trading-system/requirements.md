# Options Trading System - Requirements

## Feature Overview
Build an institutional-grade options derivatives control system deeply integrated with Northstar v3's nervous system. This is not a "bolt-on" options trader - it's a first-class organ that thinks in regimes, enforces absolute risk authority, maintains temporal integrity, and leverages V3's intelligence stack for anticipatory edge. The system uses Upstox API for live options data and implements multi-layered survival rules with tax-aware P&L tracking.

**Core Philosophy**: Options don't trade - they survive. The power comes from knowing when NOT to trade, not from strategy sophistication.

## User Stories

### PHASE 1: V3 NERVOUS SYSTEM INTEGRATION (MANDATORY)

### US-V3-1: UnifiedState Integration (Brainstem)
**As a** options trading system  
**I want** to store all options state in UnifiedState  
**So that** options become a first-class citizen with temporal replay, audit trails, and risk override authority

**Acceptance Criteria:**
- V3-1.1: OptionsState slice added to UnifiedState with: options_regime, options_positions, portfolio_greeks, weekly_risk_usage, tax_liability, kill_switch_state
- V3-1.2: All options state changes flow through UnifiedState (no rogue state)
- V3-1.3: Options state participates in temporal snapshots and replay
- V3-1.4: State transitions are auditable and reversible
- V3-1.5: Options state accessible to RiskCoordinator for override authority

### US-V3-2: Temporal Guard Integration (Non-Negotiable)
**As a** options trading system  
**I want** all option chain fetches and regime decisions wrapped in TemporalGuard  
**So that** backtests are believable and live/backtest behavior is comparable

**Acceptance Criteria:**
- V3-2.1: TemporalGuard wraps: option chain fetches, IV history access, regime detection, MTM calculations
- V3-2.2: No lookahead IV or Greeks in backtests
- V3-2.3: Expiry dates validated against current timestamp
- V3-2.4: Historical data access enforces point-in-time consistency
- V3-2.5: Temporal violations logged as CRITICAL errors

### US-V3-3: Market Regime Correlation Control
**As a** options trading system  
**I want** to hard-gate strategies based on underlying equity regime  
**So that** correlation blow-ups during crises are prevented

**Acceptance Criteria:**
- V3-3.1: Read MarketState.regime from V3's existing market state
- V3-3.2: If equity regime = CRISIS → only allow Long Straddle/Hedge, block all short-vol
- V3-3.3: If equity regime = HIGH_STRESS → block short-vol, allow defined-risk only
- V3-3.4: If equity regime = NORMAL → full regime logic applies
- V3-3.5: If equity regime = LOW_VOL → allow condors with tighter bands
- V3-3.6: Regime correlation matrix logged for post-mortem analysis

### US-V3-4: Crisis Engine Integration (Survival Core)
**As a** options trading system  
**I want** to trigger forced exits and strategy bans when crisis patterns detected  
**So that** options positions exit before equity drawdowns show

**Acceptance Criteria:**
- V3-4.1: Subscribe to CrisisEngine events (shock_detected, crisis_probability_high)
- V3-4.2: On crisis probability > threshold → force-close all short-vol positions
- V3-4.3: On shock pattern detected → reduce position sizes by 50%
- V3-4.4: On correlation spike → block new short-vol for 48 hours
- V3-4.5: Crisis engine provides lead time before panic IV explodes

### US-V3-5: Pulse State Timing Filter (Unique Edge)
**As a** options trading system  
**I want** to use PulseState for micro-timing of entries/exits  
**So that** I avoid entries during pulse spikes and tighten exits during pulse hostility

**Acceptance Criteria:**
- V3-5.1: Read PulseState (intensity, phase, risk_level) from V3
- V3-5.2: Block entries if pulse intensity > 0.7 (market stress)
- V3-5.3: Tighten exit targets by 10% if pulse turns hostile
- V3-5.4: Delay selling vol if pulse is building (pre-expansion)
- V3-5.5: Pulse-based timing provides alpha beyond IV rank alone

### US-V3-6: Confidence & Belief State Position Sizing
**As a** options trading system  
**I want** to modulate position size based on epistemic certainty  
**So that** risk scales with confidence, not just capital

**Acceptance Criteria:**
- V3-6.1: Read ConfidenceState and BeliefState from V3
- V3-6.2: High IV + Low confidence → skip trade
- V3-6.3: Moderate IV + High confidence → trade at full size
- V3-6.4: Low IV + Medium confidence → trade at 50% size
- V3-6.5: Confidence-based sizing logged for performance attribution

### US-V3-7: Bayesian Capital Allocation (Multi-Strategy)
**As a** options trading system  
**I want** options to compete with equities for capital allocation  
**So that** capital flows to highest-edge strategies probabilistically

**Acceptance Criteria:**
- V3-7.1: Options treated as strategy sleeve in BayesianCapitalTribunal
- V3-7.2: Capital allocated based on: edge score, regret risk, recent performance
- V3-7.3: Options allocation reduced when regret rises
- V3-7.4: Prevents options from hijacking portfolio capital
- V3-7.5: Multi-strategy fund discipline enforced

### US-V3-8: Risk Coordinator Absolute Authority
**As a** options trading system  
**I want** RiskCoordinator to have veto power over all options trades  
**So that** system-level risk limits override strategy-level decisions

**Acceptance Criteria:**
- V3-8.1: OptionsRiskValidator registered in RiskCoordinator hierarchy
- V3-8.2: Options trades subject to: system kill switches, portfolio drawdown rules, volatility shock rules
- V3-8.3: RiskCoordinator can force-close options positions
- V3-8.4: Emergency brake applies to options (absolute authority)
- V3-8.5: Risk veto logged with reason for audit

### US-V3-9: Event Bus Integration (Audited Events)
**As a** options trading system  
**I want** all options actions published as events  
**So that** behavior is replayable, debuggable, and explainable

**Acceptance Criteria:**
- V3-9.1: Publish events: OPTIONS_REGIME_CHANGE, OPTIONS_TRADE_SIGNAL, OPTIONS_KILL_SWITCH, PORTFOLIO_GREEKS_BREACH
- V3-9.2: Events include: timestamp, regime, reason, metrics, decision_path
- V3-9.3: Events stored in immutable audit trail
- V3-9.4: Events enable post-mortem analysis
- V3-9.5: Dashboard subscribes to events for real-time updates

### US-V3-10: Validation Framework Integration (Edge Decay)
**As a** options trading system  
**I want** continuous monitoring of strategy edge decay  
**So that** silent edge erosion is detected and strategies paused

**Acceptance Criteria:**
- V3-10.1: SignalDecayMonitor tracks: IV edge decay, strategy redundancy, performance drift
- V3-10.2: NoEdgeDetector flags when edge score < threshold
- V3-10.3: RedundancyMonitor detects if multiple strategies behaving identically
- V3-10.4: Automatic pause when edge decays below acceptable level
- V3-10.5: Edge hygiene prevents slow death

### US-V3-11: Memory & Regime Similarity (Historical Intuition)
**As a** options trading system  
**I want** to compare current IV surface to historical regimes  
**So that** strategy aggressiveness adjusts based on regime memory

**Acceptance Criteria:**
- V3-11.1: RegimeMemorySystem stores: past crashes, vol compressions, event weeks
- V3-11.2: Current regime compared to historical similar regimes
- V3-11.3: If current regime similar to past crash → reduce aggressiveness
- V3-11.4: If current regime similar to past success → maintain aggressiveness
- V3-11.5: Memory-based adjustments logged for attribution

### PHASE 2: CORE OPTIONS FUNCTIONALITY

### US-1: Upstox Options Data Integration
**As a** system operator  
**I want** live options data from Upstox API  
**So that** I can access real bid/ask, Greeks, OI, and IV data for NIFTY and BANKNIFTY options

**Acceptance Criteria:**
- 1.1: System fetches option chains from Upstox API using provided credentials
- 1.2: Data includes: symbol, expiry, strike, option_type, bid, ask, ltp, iv, delta, gamma, theta, vega, oi, change_oi, volume, underlying_price
- 1.3: Data is normalized to match existing pipeline schema (parquet format)
- 1.4: Adapter pattern allows switching between data sources without changing downstream logic
- 1.5: API token refresh is handled automatically
- 1.6: Rate limiting and error handling for API calls

### US-2: Options Regime Detection
**As a** trading system  
**I want** to detect current options market regime  
**So that** I can select appropriate strategies for current conditions

**Acceptance Criteria:**
- 2.1: System classifies regime as: LOW_VOL_SELL, HIGH_VOL_SELL, RISING_VOL_BUY, NEUTRAL, CRASH_HEDGE
- 2.2: Regime detection uses IV rank, IV trend, skew, and underlying regime
- 2.3: Regime must persist ≥ 2 trading days before allowing trades
- 2.4: Regime changes trigger position review and potential exits
- 2.5: Volatility-of-volatility check: block short-vol if IV 5-day std > 1.5 × IV 20-day std

### US-3: Strategy Generation Engine
**As a** trading system  
**I want** to generate appropriate option strategies based on regime  
**So that** I can execute high-probability, defined-risk trades

**Acceptance Criteria:**
- 3.1: LOW_VOL_SELL regime generates Iron Condor strategies
- 3.2: HIGH_VOL_SELL regime generates Calendar Spread strategies
- 3.3: RISING_VOL_BUY regime generates Long Straddle strategies
- 3.4: Each strategy includes: strikes, max loss, max profit, net credit/debit, Greeks
- 3.5: Strategies respect lot size constraints (no fractional lots)
- 3.6: Premium adequacy rule: net credit ≥ 0.25 × max loss

### US-4: Trade Eligibility Validation
**As a** risk management system  
**I want** strict trade eligibility rules  
**So that** only high-quality trades are executed

**Acceptance Criteria:**
- 4.1: Regime persistence check (≥ 2 days)
- 4.2: IV rank thresholds: LOW_VOL_SELL (>70%), HIGH_VOL_SELL (>80%), RISING_VOL_BUY (<30%)
- 4.3: Liquidity check: bid-ask spread ≤ 8% of premium
- 4.4: Liquidity depth check: min bid_qty ≥ 2 × required lot size
- 4.5: Expiry hygiene: no new trades with < 5 days to expiry
- 4.6: Event calendar check: block short-vol within 2 days of macro events (RBI, CPI, WPI, Budget)
- 4.7: Vol-of-vol check: block short-vol if IV volatility is elevated
- 4.8: Late-cycle protection: reduce position size by 50% if LOW_VOL_SELL > 10 days

### US-5: Capital Scaling Rules
**As a** risk management system  
**I want** dynamic capital scaling based on performance  
**So that** risk adjusts appropriately to wins and losses

**Acceptance Criteria:**
- 5.1: Base capital = ₹5,00,000, base risk = 1.0% per trade
- 5.2: Profit scaling: +0.25% risk after 8% net profit milestone
- 5.3: Max risk ceiling: 1.5% per trade (never exceeded)
- 5.4: Drawdown de-scaling: -0.25% risk at 3% drawdown, 0.5% risk at 5% drawdown
- 5.5: Recovery condition: risk increases only after equity reaches previous high + 2 profitable trades
- 5.6: Time requirement: no scaling before 8 consecutive weeks of live trading

### US-6: Hard Survival Rules
**As a** risk management system  
**I want** circuit breakers that prevent catastrophic losses  
**So that** the system survives bad periods

**Acceptance Criteria:**
- 6.1: Weekly loss kill switch: halt trading if weekly loss ≥ 2% capital
- 6.2: Single-trade trauma rule: no short-vol for 2 weeks if any trade loses > 80% max loss
- 6.3: Portfolio risk cap: total open worst-case loss ≤ 2% capital
- 6.4: Tax reality check: halt if YTD tax payable > cash buffer
- 6.5: Max trades per week: 2 (hard limit)
- 6.6: No trading on Monday mornings or expiry days

### US-7: Position Management
**As a** trading system  
**I want** to track and manage open positions  
**So that** I can monitor risk and execute exits properly

**Acceptance Criteria:**
- 7.1: Position object tracks: strategy, regime, expiry, legs, max_loss, entry_time, Greeks
- 7.2: Daily mark-to-market using live option chain data
- 7.3: Exit rules: 55% profit target, 40% stop loss, 2 days before expiry, regime flip
- 7.4: Portfolio Greeks aggregation: delta, gamma, theta, vega
- 7.5: Greek safety bands: delta [-0.2, +0.2], theta positive, vega [-0.3, +0.1]
- 7.6: Immutable trade ledger (append-only parquet)

### US-8: Tax-Aware P&L Tracking
**As a** trading system  
**I want** accurate post-tax P&L calculation  
**So that** I understand true profitability

**Acceptance Criteria:**
- 8.1: Gross P&L calculation from entry to exit
- 8.2: Cost tracking: brokerage (₹20/leg), exchange charges (~0.1%), GST
- 8.3: Tax calculation: 30% flat on profits (India VDA regime)
- 8.4: Net P&L = Gross P&L - costs - tax
- 8.5: Trade rejection if expected net P&L < 1.5 × total costs
- 8.6: YTD tax liability tracking

### US-9: Dashboard Integration
**As a** system operator  
**I want** options trading integrated into the v3 dashboard  
**So that** I can monitor options positions alongside equity strategies

**Acceptance Criteria:**
- 9.1: New "Options Trading" panel in main dashboard
- 9.2: Live display: current regime, IV rank, active positions, portfolio Greeks
- 9.3: Position table: strategy, strikes, P&L (gross/net), days held, Greeks
- 9.4: Greek drift charts over time
- 9.5: Trade history with win rate, avg profit, max drawdown
- 9.6: Risk metrics: weekly risk used, capital scaling status, kill switch status
- 9.7: Next trade eligibility status with reasons if blocked

### US-10: System Hygiene Rules
**As a** trading system  
**I want** behavioral guardrails  
**So that** I avoid psychological trading mistakes

**Acceptance Criteria:**
- 10.1: Strategy concentration: max 2 consecutive trades of same strategy
- 10.2: Success cooling: skip next signal after 2 consecutive wins (unless IV extreme)
- 10.3: Boredom protection: 48h forced pause if manual override attempted
- 10.4: Monthly audit: automated report on trades taken vs skipped, net vs gross P&L, tax drag
- 10.5: Loss normalization: distinguish normal losses from system failures

### PHASE 3: ADVANCED STRATEGY INTELLIGENCE

### US-ADV-1: Volatility Compression Fade (Micro-Calendar)
**As a** strategy intelligence system  
**I want** to exploit IV term-structure mispricing  
**So that** I capture edge from near-term theta overpricing

**Acceptance Criteria:**
- ADV-1.1: Detect IV compression windows (IV rank 40-55%, vol-of-vol falling)
- ADV-1.2: Generate micro-calendar: sell near-term OTM, buy slightly longer same strike
- ADV-1.3: Target small debit/flat trade with positive theta
- ADV-1.4: Exit within 3-5 days (fast theta capture)
- ADV-1.5: Only trade when theta positive but flattening

### US-ADV-2: Gamma Trap Reversal (Dealer Positioning)
**As a** strategy intelligence system  
**I want** to exploit dealer gamma hedging flows  
**So that** I capture mean-reversion after false breakouts

**Acceptance Criteria:**
- ADV-2.1: Detect gamma spikes + OI divergence + failed range expansion
- ADV-2.2: Generate narrow debit spread after failed breakout
- ADV-2.3: Fast exit (1-2 days) - this is not directional trading
- ADV-2.4: Requires MarketBrain + Greeks engine integration
- ADV-2.5: Only trade when dealer positioning extreme

### US-ADV-3: Skew Harvest (Asymmetric Condor)
**As a** strategy intelligence system  
**I want** to tilt iron condor wings based on skew percentile  
**So that** I harvest persistent put skew overpricing

**Acceptance Criteria:**
- ADV-3.1: Measure skew percentile (OTM put IV - ATM IV) / ATM IV
- ADV-3.2: Generate asymmetric condor: wider downside protection, tighter upside
- ADV-3.3: Net credit still meets adequacy (≥ 0.25 × max loss)
- ADV-3.4: Dynamically adjust wing widths based on skew
- ADV-3.5: Improves IC expectancy 20-30% without extra risk

### US-ADV-4: Post-Event Volatility Drift
**As a** strategy intelligence system  
**I want** to capture uneven IV collapse after macro events  
**So that** I exploit mispriced strikes post-event

**Acceptance Criteria:**
- ADV-4.1: Enter 1 day after event (RBI, CPI, Budget)
- ADV-4.2: Generate calendar/diagonal where IV collapse fastest
- ADV-4.3: Only trade if IV drop > historical median
- ADV-4.4: Only trade if vol-of-vol normalized
- ADV-4.5: Clean alpha - not gambling on event outcome

### US-ADV-5: Theta Acceleration Window
**As a** strategy intelligence system  
**I want** to exploit non-linear theta acceleration near expiry  
**So that** I harvest micro-edge from expiry physics

**Acceptance Criteria:**
- ADV-5.1: Generate ultra-short defined risk spreads (3-4 days to expiry)
- ADV-5.2: Very tight exits (intraday if needed)
- ADV-5.3: Small size, high probability
- ADV-5.4: Only when: vol stable, no events, gamma under control
- ADV-5.5: Micro-harvesting, not YOLO

### US-ADV-6: Options Strategy Intelligence Organ
**As a** meta-strategy system  
**I want** to discover which strategy types have edge today  
**So that** only top 1-2 strategies are allowed per week

**Acceptance Criteria:**
- ADV-6.1: OptionsStrategyIntelligenceOrgan scores all strategies: edge_score, decay, risk_penalty
- ADV-6.2: Inputs from: RegimeMemory, SignalHealthMonitor, CrisisEngine, vol-of-vol, trade ledger
- ADV-6.3: Bayesian update on: net P&L (post-tax), drawdown pain, time-to-profit
- ADV-6.4: Penalizes: frequent exits, gamma stress, kill switch proximity
- ADV-6.5: Only top-ranked strategies allowed (adaptive filtering, not ML overfitting)

### US-ADV-7: Strategy Fatigue Detection
**As a** meta-strategy system  
**I want** to detect when a strategy wins often but expectancy decays  
**So that** silent edge erosion is caught before losses

**Acceptance Criteria:**
- ADV-7.1: Track per-strategy: win rate, avg profit, exit timing, Greek stress
- ADV-7.2: Detect if strategy exits earlier than usual (fatigue signal)
- ADV-7.3: Detect if expectancy decays despite wins
- ADV-7.4: Quietly de-rank fatigued strategies
- ADV-7.5: No human notices this in time - system must

### US-ADV-8: Regime-Strategy Memory
**As a** meta-strategy system  
**I want** to remember which strategies work in which regime conditions  
**So that** strategy selection uses historical context

**Acceptance Criteria:**
- ADV-8.1: Track: strategy type + regime + breadth + outcome
- ADV-8.2: Example: Iron Condors in LOW_VOL_SELL work ONLY when breadth > 55%
- ADV-8.3: If breadth < 45%, ICs quietly bleed (historical pattern)
- ADV-8.4: RegimeMemory already tracks this - just wire it
- ADV-8.5: Memory-based filtering prevents repeated mistakes

### US-ADV-9: Edge Silence Mode (Most Important)
**As a** meta-strategy system  
**I want** to do nothing when no strategy has edge  
**So that** forced action is eliminated (90% of trader failures)

**Acceptance Criteria:**
- ADV-9.1: If no strategy has edge_score > threshold → system does nothing
- ADV-9.2: If confidence < minimum → system does nothing
- ADV-9.3: Tax drag stays constant, risk stays bounded
- ADV-9.4: Upside comes from selectivity, not activity
- ADV-9.5: This is exactly how V3 beat crises - by not forcing action

### US-11: Configuration Management
**As a** system operator  
**I want** centralized configuration for options trading  
**So that** I can adjust parameters without code changes

**Acceptance Criteria:**
- 11.1: Config file: `config/options_trading.yaml`
- 11.2: Configurable: capital base, risk percentages, allowed strategies, exit rules, tax rates
- 11.3: Upstox credentials stored securely (environment variables)
- 11.4: Event calendar loaded from config (macro event dates)
- 11.5: Config validation on startup

### US-12: Backtesting and Simulation
**As a** system operator  
**I want** to backtest options strategies  
**So that** I can validate rules before live trading

**Acceptance Criteria:**
- 12.1: Historical option chain data support
- 12.2: Simulate 8-week trading periods with realistic conditions
- 12.3: Include all costs, taxes, and slippage
- 12.4: Report: win rate, net P&L, max drawdown, Greek violations
- 12.5: Stress test scenarios: vol expansion, calendar spread failure, consecutive losses

## Non-Functional Requirements

### NFR-1: Performance
- Option chain fetch and processing < 2 seconds
- Dashboard refresh rate: 5 seconds for live data
- Position MTM calculation < 500ms

### NFR-2: Reliability
- API retry logic with exponential backoff
- Graceful degradation if Upstox API unavailable
- Data validation at every pipeline stage

### NFR-3: Security
- API credentials never logged or exposed
- Trade ledger immutable (append-only)
- Audit trail for all risk rule violations

### NFR-4: Maintainability
- Adapter pattern for data sources
- Strategy pattern for option strategies
- Clear separation: data → regime → strategy → execution → tracking

### NFR-5: Observability
- Structured logging for all trades and decisions
- Metrics: API latency, regime changes, trade rejections
- Alerts: kill switch activation, Greek violations, API failures

## Out of Scope
- Automated order execution (manual execution only)
- Intraday trading or scalping
- Naked option selling
- Futures trading
- Multi-leg adjustments (roll, repair)
- Real-time streaming data (daily/hourly refresh sufficient)

## Dependencies
- Existing Northstar v3 system
- Upstox API access (credentials provided)
- Python libraries: requests, pandas, numpy, pyyaml
- Dashboard framework (Streamlit)

## Success Metrics
- System generates 1-2 trade signals per week
- Trade eligibility rejection rate > 80% (high selectivity)
- No kill switch activations in first 8 weeks
- Net P&L positive after 12 weeks (post-tax)
- Zero Greek safety band violations
- 100% trade ledger accuracy

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Upstox API downtime | High | Fallback to manual data entry, cache last known data |
| Token expiration | Medium | Automated refresh, alert on failure |
| Lot size constraints | Medium | Pre-trade validation, reject undersized trades |
| Event calendar outdated | High | Manual review monthly, conservative 3-day buffer |
| Tax law changes | High | Configurable tax rates, annual review |
| Overtrading temptation | Medium | Hard-coded frequency limits, boredom protection |
| V3 integration coupling | Medium | Graceful degradation if V3 components unavailable |
| Edge decay undetected | High | Continuous monitoring via SignalDecayMonitor |
| Correlation blow-up | Critical | Hard gates on equity regime, crisis engine integration |

## What Makes This System Unique

This is not an "options trading bot". This is an **institutional derivatives control system**. The uniqueness comes from:

### 🧠 Regime Thinking, Not Trade Thinking
- Market conditions dictate behavior, not P&L emotions
- Regime persistence enforced (2-day minimum)
- Regime memory informs aggressiveness
- Correlation regimes prevent blow-ups

### ⚠️ Risk Has Absolute Authority
- RiskCoordinator can veto any trade
- Emergency brake applies to options
- Kill switches have no override (except manual + 48h cooling)
- Portfolio risk caps enforced system-wide

### ⏳ Time Integrity is Enforced
- TemporalGuard prevents lookahead bias
- Backtests are believable
- Live and backtest behavior comparable
- Point-in-time consistency guaranteed

### 🧮 Capital is Probabilistic
- Bayesian allocation across strategies
- Options compete with equities for capital
- Confidence modulates position size
- Regret risk reduces allocation

### 🧾 Taxes are First-Class
- All P&L calculations post-tax
- Tax liability tracked YTD
- Minimum profitability filters
- Tax liquidity kill switch

### 📊 Greeks are Portfolio-Level
- Not per-trade Greeks
- Portfolio aggregation continuous
- Safety bands enforced
- Gamma escalation triggers exits

### 🧠 Memory Informs Behavior
- Regime similarity to past crashes
- Strategy performance by regime
- Edge decay detection
- Fatigue monitoring

### 🎯 Selectivity Over Activity
- Edge silence mode (do nothing when no edge)
- 80%+ rejection rate is success
- Forced action eliminated
- This is how V3 survived crises

## The Honest Truth

Most people trade options to make money.  
This system is built to **not die in options**.  
That's why it has a chance.

The power is not in the strategies (Iron Condor, Calendar, Straddle).  
The power is in the **nervous system integration**:
- Crisis engine gives lead time before IV explodes
- Pulse state provides micro-timing edge
- Confidence state prevents low-conviction trades
- Memory prevents repeated regime mistakes
- Edge decay detection stops silent death

This is institutional discipline, algorithmically enforced.

## Implementation Priority
1. **Phase 1 (V3 Integration - MANDATORY)**: UnifiedState integration, TemporalGuard wrapping, MarketState correlation control, RiskCoordinator authority
2. **Phase 2 (Core Options)**: Upstox adapter, regime detection, basic strategy generation (IC, Calendar, Straddle)
3. **Phase 3 (Risk & Survival)**: Trade eligibility, capital scaling, survival rules, kill switches
4. **Phase 4 (Tracking & Intelligence)**: Position management, tax-aware P&L, trade ledger, event bus
5. **Phase 5 (Dashboard & Observability)**: OptionsPanel, Greek monitoring, alerts, audit trails
6. **Phase 6 (Advanced Strategies)**: Micro-calendar, skew harvest, post-event drift, theta acceleration
7. **Phase 7 (Meta-Intelligence)**: OptionsStrategyIntelligenceOrgan, fatigue detection, edge silence mode
8. **Phase 8 (Validation)**: Backtesting, stress tests, walk-forward validation, 8-week simulation

**Critical Path**: V3 integration MUST come first. Without UnifiedState, TemporalGuard, and RiskCoordinator integration, the options system is just another retail trader - not an institutional organ.
