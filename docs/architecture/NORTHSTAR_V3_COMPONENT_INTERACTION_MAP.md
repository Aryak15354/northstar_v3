# 🧭 NORTHSTAR V3 - DETAILED COMPONENT INTERACTION MAP

**Complete System Component Relationships & Data Flow**

---

## 📊 SYSTEM COMPONENTS BY CATEGORY

### **DATA COLLECTION LAYER**

| Component | File | Purpose | Input | Output | Schedule |
|-----------|------|---------|-------|--------|----------|
| EOD Options Pipeline | `eod_options_pipeline.py` | Collect NIFTY options data | Upstox API | `data/options/live/market_data_latest.json` | Daily 3:35 PM IST |
| RBI Scraper | `rbi_scraper_fixed.py` | Collect RBI macro data | RBI Website | `data/macro/raw/*.csv` | Weekly |
| Integrated Pipeline | `src/ingestion/integrated_data_pipeline.py` | Coordinate data collection | Both above | `data/processed/` | Daily |
| Price Fetcher | `src/ingestion/price_fetcher.py` | Collect stock prices | yfinance | `data/raw/prices_daily/` | Daily |
| Financials Fetcher | `src/ingestion/financials_fetcher.py` | Collect financial statements | External APIs | `data/raw/financials/` | Quarterly |

### **DATA PROCESSING LAYER**

| Component | File | Purpose | Input | Output | Frequency |
|-----------|------|---------|-------|--------|-----------|
| Macro Cleaner | `src/preprocessing/macro_cleaner.py` | Clean macro data | RBI raw data | `data/macro/factors/macro_score.parquet` | Daily |
| Price Processor | `src/processing/price_processor.py` | Process price data | Raw prices | `data/processed/prices.parquet` | Daily |
| Fundamental Processor | `src/processing/fundamental_processor.py` | Process financials | Raw financials | `data/processed/fundamentals.parquet` | Quarterly |
| Market Regime | `src/processing/market_regime.py` | Calculate regime metrics | Market data | `data/processed/market_regime.parquet` | Daily |
| Sector Rotation | `src/processing/sector_rotation.py` | Analyze sector flows | Sector data | `data/processed/sector_rotation.parquet` | Daily |
| Volatility Engine | `src/processing/volatility_engine.py` | Calculate volatility | Price data | `data/processed/volatility_state.parquet` | Daily |
| Technical Engine | `src/processing/technical_engine.py` | Calculate technicals | Price data | `data/processed/technicals.parquet` | Daily |
| Valuation Engine | `src/processing/valuation_engine.py` | Calculate valuations | Fundamentals | `data/processed/valuation.parquet` | Daily |

### **STATE MANAGEMENT LAYER**

| Component | File | Purpose | Input | Output | Frequency |
|-----------|------|---------|-------|--------|-----------|
| Market State Spine | `src/state/market_state.py` | Central market state | All processing | `data/processed/market_state.parquet` | Daily |
| Data Confidence | `src/state/data_confidence.py` | Data quality metrics | All data | `data/processed/data_confidence.parquet` | Daily |
| Market Brain State | `src/intelligence/market_brain/` | Brain state | Market data | `data/processed/market_brain_state.json` | Daily |

### **INTELLIGENCE LAYER**

| Component | File | Purpose | Input | Output | Frequency |
|-----------|------|---------|-------|--------|-----------|
| Intelligence Stack | `src/intelligence/intelligence_stack.py` | Master intelligence | Market state | `data/intelligence/intelligence_state.json` | Daily |
| Valuation Engines | `src/intelligence/valuation_engines.py` | 4 valuation models | Fundamentals | Valuation scores | Daily |
| Confidence Engine | `src/intelligence/confidence_engine.py` | Confidence weighting | Data quality | Confidence weights | Daily |
| Bayesian Engine | `src/intelligence/bayesian_engine.py` | Signal fusion | All signals | Fused beliefs | Daily |
| Narrative Engine | `src/intelligence/narrative_engine.py` | 5 jurors narrative | Market data | Market narrative | Daily |
| Memory Engine | `src/intelligence/memory_engine.py` | Learning system | Trade outcomes | Adaptive weights | Daily |
| Market Brain | `src/intelligence/market_brain/brain_orchestrator.py` | Market intelligence | Market data | Pulse, survival | Daily |
| Strategy Intelligence | `src/intelligence/strategy_intelligence.py` | Strategy learning | Strategy outcomes | Strategy beliefs | Daily |

### **PORTFOLIO MANAGEMENT LAYER**

| Component | File | Purpose | Input | Output | Frequency |
|-----------|------|---------|-------|--------|-----------|
| Strategy System | `src/portfolio/strategies.py` | Generate strategies | Scores, signals | Strategy portfolios | Daily |
| Backtest Engine | `src/backtesting/backtest_engine.py` | Backtest strategies | Historical data | Strategy performance | Daily |
| Capital Allocator | `src/intelligence/capital_allocator.py` | Allocate capital | Strategy perf | Allocation weights | Daily |
| Portfolio Governor | `src/portfolio/portfolio_governor.py` | Construct portfolio | All above | Final portfolio | Daily |
| Macro Risk Controller | `src/portfolio/macro_risk_controller.py` | Macro risk overlay | Market state | Risk-adjusted weights | Daily |

### **RISK MANAGEMENT LAYER**

| Component | File | Purpose | Input | Output | Frequency |
|-----------|------|---------|-------|--------|-----------|
| Emergency Brake | `src/risk/emergency_brake.py` | System-level risk | System state | Emergency protocols | Real-time |
| Portfolio Kill Switches | `src/risk/portfolio_kill_switches.py` | Portfolio-level risk | Portfolio state | Kill switch triggers | Real-time |
| Portfolio Risk Controller | `src/risk/portfolio_risk_controller.py` | Position-level risk | Holdings | Risk adjustments | Real-time |
| Survival Instincts | `src/intelligence/market_brain/survival_instincts.py` | Adaptive risk | System stress | Exposure multipliers | Real-time |

### **ORCHESTRATION LAYER**

| Component | File | Purpose | Input | Output | Frequency |
|-----------|------|---------|-------|--------|-----------|
| System Orchestrator | `src/orchestrator/system_orchestrator.py` | Coordinate systems | All components | Execution log | Daily |
| Market Brain Orchestrator | `src/intelligence/market_brain/brain_orchestrator.py` | Coordinate brain | Market data | Brain state | Daily |
| Update All Systems | `update_all_systems.py` | Master update script | All sources | All outputs | Daily |

### **USER INTERFACE LAYER**

| Component | File | Purpose | Input | Output | Type |
|-----------|------|---------|-------|--------|------|
| Trading Desk | `northstar_trading_desk.py` | Bloomberg-style UI | Market state | Dashboard | Streamlit |
| Professional Dashboard | `northstar_professional.py` | Intelligence UI | Intelligence state | Dashboard | Streamlit |
| Intelligence Organism | `northstar_intelligence_organism.py` | 4-plane UI | All state | Dashboard | Streamlit |
| React Terminal | `northstar-terminal/` | Professional terminal | API data | Dashboard | React |
| API Server | `src/api/server.py` | Data API | All state | REST endpoints | FastAPI |

---

## 🔄 DATA FLOW DIAGRAMS

### **FLOW 1: Daily Data Collection & Processing**

```
┌─────────────────────────────────────────────────────────────┐
│                    DAILY DATA FLOW                          │
└─────────────────────────────────────────────────────────────┘

3:35 PM IST
    ↓
eod_options_pipeline.py
    ↓
data/options/live/market_data_latest.json
    ↓
integrated_data_pipeline.py
    ↓
┌─────────────────────────────────────────────────────────────┐
│              DATA PROCESSING PIPELINE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Market Data → Price Processor → prices.parquet             │
│  RBI Data → Macro Cleaner → macro_score.parquet             │
│  Prices → Technical Engine → technicals.parquet             │
│  Prices → Volatility Engine → volatility_state.parquet      │
│  Fundamentals → Valuation Engine → valuation.parquet        │
│  Sectors → Sector Rotation → sector_rotation.parquet        │
│  Market Data → Market Regime → market_regime.parquet        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
Market State Spine (market_state.py)
    ↓
data/processed/market_state.parquet
    ↓
[Feeds all downstream systems]
```

### **FLOW 2: Intelligence Generation**

```
┌─────────────────────────────────────────────────────────────┐
│              INTELLIGENCE GENERATION FLOW                   │
└─────────────────────────────────────────────────────────────┘

Market State Spine
    ↓
┌─────────────────────────────────────────────────────────────┐
│           INTELLIGENCE STACK (intelligence_stack.py)        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Detect Market Regime                                    │
│  2. Run 4-Engine Valuation Analysis                         │
│  3. Apply Confidence Weighting                              │
│  4. Generate Market Narrative (5 Jurors)                    │
│  5. Resolve Contradictions (Bayesian)                       │
│  6. Apply Memory & Learning                                 │
│  7. Synthesize Final Beliefs                                │
│  8. Generate Actions                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
data/intelligence/intelligence_state.json
    ↓
[Feeds portfolio construction]

PARALLEL: Market Brain
    ↓
┌─────────────────────────────────────────────────────────────┐
│        MARKET BRAIN ORCHESTRATOR (brain_orchestrator.py)    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Build Market Tensor                                     │
│  2. Analyze Causal Graph                                    │
│  3. Compress Regime Memory                                  │
│  4. Detect Market Pulse                                     │
│  5. Monitor Survival Instincts                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
data/processed/market_brain_state.json
    ↓
[Feeds portfolio construction & risk management]
```

### **FLOW 3: Portfolio Construction**

```
┌─────────────────────────────────────────────────────────────┐
│           PORTFOLIO CONSTRUCTION FLOW                       │
└─────────────────────────────────────────────────────────────┘

Intelligence State + Market Brain State
    ↓
Strategy System (strategies.py)
    ↓
Generate 6+ Strategy Portfolios
    ↓
Backtest Engine (backtest_engine.py)
    ↓
Strategy Performance Metrics
    ↓
Capital Allocator (capital_allocator.py)
    ↓
Allocation Weights per Strategy
    ↓
Portfolio Governor (portfolio_governor.py)
    ↓
Blend Strategies + Apply Constraints
    ↓
Macro Risk Controller (macro_risk_controller.py)
    ↓
Apply Macro Overlay
    ↓
Final Portfolio Weights
    ↓
data/processed/portfolio_weights.parquet
    ↓
[Feeds risk management & dashboards]
```

### **FLOW 4: Risk Management**

```
┌─────────────────────────────────────────────────────────────┐
│              RISK MANAGEMENT FLOW                           │
└─────────────────────────────────────────────────────────────┘

Portfolio State + Market State
    ↓
┌─────────────────────────────────────────────────────────────┐
│           RISK MONITORING (Real-time)                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Emergency Brake (emergency_brake.py)                       │
│    ↓ Monitors system health                                 │
│    ↓ Triggers emergency protocols                           │
│                                                              │
│  Portfolio Kill Switches (portfolio_kill_switches.py)       │
│    ↓ Monitors position-level risk                           │
│    ↓ Triggers position exits                                │
│                                                              │
│  Portfolio Risk Controller (portfolio_risk_controller.py)   │
│    ↓ Monitors sector exposure                               │
│    ↓ Adjusts weights                                        │
│                                                              │
│  Survival Instincts (survival_instincts.py)                 │
│    ↓ Monitors system stress                                 │
│    ↓ Adjusts exposure multipliers                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
Risk-Adjusted Portfolio
    ↓
[Feeds dashboards & execution]
```

### **FLOW 5: Dashboard Rendering**

```
┌─────────────────────────────────────────────────────────────┐
│              DASHBOARD RENDERING FLOW                       │
└─────────────────────────────────────────────────────────────┘

Unified State (All components)
    ↓
Dashboard Snapshot Builder (build_dashboard_snapshot.py)
    ↓
data/processed/cache/dashboard_snapshot.parquet
    ↓
┌─────────────────────────────────────────────────────────────┐
│           DASHBOARD IMPLEMENTATIONS                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Trading Desk (northstar_trading_desk.py)                   │
│    ↓ Bloomberg-style interface                              │
│    ↓ Real-time risk monitoring                              │
│                                                              │
│  Professional Dashboard (northstar_professional.py)         │
│    ↓ Intelligence-focused interface                         │
│    ↓ AI insights and narratives                             │
│                                                              │
│  Intelligence Organism (northstar_intelligence_organism.py) │
│    ↓ 4-plane command center                                 │
│    ↓ Advanced AI visualization                              │
│                                                              │
│  React Terminal (northstar-terminal/)                       │
│    ↓ Professional trading terminal                          │
│    ↓ D3.js visualizations                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
    ↓
User Interface
```

---

## 🔗 COMPONENT DEPENDENCY GRAPH

### **Dependency Levels**

```
LEVEL 0: Data Sources
    ├── Upstox API
    ├── RBI Website
    ├── yfinance
    └── External APIs

LEVEL 1: Data Collection
    ├── eod_options_pipeline.py
    ├── rbi_scraper_fixed.py
    ├── price_fetcher.py
    └── financials_fetcher.py

LEVEL 2: Data Processing
    ├── macro_cleaner.py
    ├── price_processor.py
    ├── technical_engine.py
    ├── volatility_engine.py
    ├── valuation_engine.py
    ├── market_regime.py
    └── sector_rotation.py

LEVEL 3: State Management
    ├── market_state.py
    ├── data_confidence.py
    └── market_brain_state.py

LEVEL 4: Intelligence
    ├── intelligence_stack.py
    ├── market_brain_orchestrator.py
    ├── strategy_intelligence.py
    └── capital_allocator.py

LEVEL 5: Portfolio Management
    ├── strategy_system.py
    ├── backtest_engine.py
    ├── portfolio_governor.py
    └── macro_risk_controller.py

LEVEL 6: Risk Management
    ├── emergency_brake.py
    ├── portfolio_kill_switches.py
    ├── portfolio_risk_controller.py
    └── survival_instincts.py

LEVEL 7: Orchestration
    ├── system_orchestrator.py
    ├── market_brain_orchestrator.py
    └── update_all_systems.py

LEVEL 8: User Interface
    ├── northstar_trading_desk.py
    ├── northstar_professional.py
    ├── northstar_intelligence_organism.py
    ├── northstar-terminal/
    └── api_server.py
```

### **Critical Dependencies**

```
Market State Spine is depended on by:
    ├── Intelligence Stack
    ├── Market Brain
    ├── Strategy System
    ├── Capital Allocator
    ├── Portfolio Governor
    ├── Risk Controllers
    └── All Dashboards

Intelligence State is depended on by:
    ├── Capital Allocator
    ├── Portfolio Governor
    ├── Risk Controllers
    └── All Dashboards

Portfolio State is depended on by:
    ├── Risk Controllers
    ├── Dashboards
    └── Execution Systems
```

---

## 🎯 COMPONENT INTERACTION PATTERNS

### **Pattern 1: Sequential Processing**

```
Data Collection → Data Processing → State Management → Intelligence → Portfolio → Risk → UI
```

**Components**: All data-driven components follow this pattern

### **Pattern 2: Parallel Intelligence**

```
Market State → Intelligence Stack (parallel)
            → Market Brain (parallel)
            → Strategy Intelligence (parallel)
```

**Components**: Three intelligence systems run in parallel

### **Pattern 3: Feedback Loops**

```
Portfolio → Risk Management → Exposure Adjustment → Portfolio Governor → Portfolio
```

**Components**: Risk management feeds back to portfolio construction

### **Pattern 4: State Propagation**

```
Market State Spine → All Downstream Systems
```

**Components**: Market State Spine is the central hub

---

## 📈 SYSTEM STATISTICS

### **Component Count**
- **Data Collection**: 5 components
- **Data Processing**: 8 components
- **State Management**: 3 components
- **Intelligence**: 8 components
- **Portfolio Management**: 4 components
- **Risk Management**: 4 components
- **Orchestration**: 3 components
- **User Interface**: 5 components
- **Total**: 40+ components

### **Data Files Generated**
- **Parquet Files**: 20+
- **JSON Files**: 10+
- **CSV Files**: 5+
- **Total**: 35+ data files

### **Execution Frequency**
- **Real-time**: 4 components (Risk management)
- **Daily**: 25+ components
- **Weekly**: 2 components (RBI scraper)
- **Quarterly**: 1 component (Financials)
- **On-demand**: 5+ components

---

## 🔍 COMPONENT INTERACTION EXAMPLES

### **Example 1: Daily Update Sequence**

```
1. 3:35 PM IST: eod_options_pipeline.py collects market data
2. 3:40 PM IST: integrated_data_pipeline.py processes data
3. 3:45 PM IST: market_state.py computes market state
4. 3:50 PM IST: intelligence_stack.py generates intelligence
5. 3:55 PM IST: market_brain_orchestrator.py generates brain state
6. 4:00 PM IST: strategy_system.py generates strategies
7. 4:05 PM IST: backtest_engine.py backtests strategies
8. 4:10 PM IST: capital_allocator.py allocates capital
9. 4:15 PM IST: portfolio_governor.py constructs portfolio
10. 4:20 PM IST: risk_controllers.py adjust for risk
11. 4:25 PM IST: dashboards render updated state
```

### **Example 2: Real-time Risk Management**

```
1. Portfolio State Changes
2. Emergency Brake monitors system health
3. If stress detected:
   a. Survival Instincts adjusts exposure multiplier
   b. Portfolio Kill Switches triggers position exits
   c. Portfolio Risk Controller adjusts weights
   d. Market State Spine updates allowed exposure
   e. Dashboards alert user
```

### **Example 3: Intelligence Generation**

```
1. Market State Spine provides market context
2. Intelligence Stack:
   a. Detects market regime
   b. Runs 4 valuation engines
   c. Applies confidence weighting
   d. Generates 5-juror narrative
   e. Resolves contradictions
   f. Synthesizes beliefs
3. Market Brain:
   a. Builds market tensor
   b. Analyzes causal relationships
   c. Detects market pulse
   d. Monitors survival
4. Strategy Intelligence:
   a. Tracks strategy performance
   b. Updates strategy beliefs
   c. Calculates strategy regret
5. Unified beliefs feed portfolio construction
```

---

## 🎯 CONCLUSION

Northstar V3 has **40+ components** organized in **8 layers** with **complex interdependencies**. While each component is sophisticated, the system lacks:

1. **Unified entry point** - 8 separate entry points
2. **Unified orchestration** - 2 separate orchestrators
3. **Unified intelligence** - 3 separate intelligence systems
4. **Unified state** - 3 separate state systems
5. **Unified data flow** - Multiple fragmented flows
6. **Unified UI** - 4 separate implementations

**Unification will consolidate these 40+ components into a coherent system with clear data flow, unified state, and coordinated execution.**

---

*Component Interaction Map Complete*
