# 🧭 NORTHSTAR UNIFIED TERMINAL

**The Ultimate Hedge Fund Command Center**

Transform Northstar from "cool" into "unignorable" with a true hedge fund war room that combines all three dashboards into one synchronized terminal.

## 🎯 **WHAT IS THIS?**

The Unified Terminal is a Bloomberg-style command center that provides three mental states in one interface:

- **🟥 WAR ROOM** (Operations): "Are we safe right now?"
- **🟦 PORTFOLIO COMMAND** (Holdings): "What are we holding and why?"  
- **🧠 INTELLIGENCE ORGANISM** (Strategy): "What kind of world are we in?"

## 🚀 **QUICK START**

### Launch the Complete System
```bash
# Full system with auto-updating snapshots
python launch_unified_terminal.py

# Terminal only (no background scheduler)
python launch_unified_terminal.py --no-scheduler

# Build snapshot and exit
python launch_unified_terminal.py --build-only
```

### Check System Health
```bash
# Verify all dependencies and data structure
python launch_unified_terminal.py --check-only
```

## 🧠 **ARCHITECTURE**

### Data Nervous System
- **Single Snapshot**: All dashboards read from one cached file
- **5-minute Updates**: Automated snapshot builder keeps data fresh
- **Perfect Sync**: No race conditions or stale data

### Three Mental States
1. **War Room**: Real-time risk monitoring with gauges and alerts
2. **Portfolio Command**: Holdings analysis with capital allocation
3. **Intelligence Organism**: AI-powered market analysis and learning

## 📊 **GLOBAL STATUS BAR**

The nerve center shows 7 critical metrics at all times:
- **REGIME**: Market environment (Expansion/Crisis/etc.)
- **RISK**: Current volatility level
- **EXPOSURE**: Portfolio exposure vs allowed
- **DD**: Current drawdown
- **VOL**: Market volatility
- **LIQUIDITY**: Liquidity conditions
- **AI CONVICTION**: AI confidence level

## 🟥 **WAR ROOM FEATURES**

### Risk Gauges
- **Volatility Gauge**: Real-time market volatility
- **Drawdown Gauge**: Portfolio drawdown monitoring
- **Exposure Dial**: Current vs allowed exposure
- **Kill Switch Status**: System safety status

### Market Stress Monitor
- **Liquidity Pressure**: USD, yields, credit stress
- **Breadth Collapse**: % stocks above 50DMA
- **Correlation Spike**: Strategy correlation matrix
- **Overall Stress**: Combined stress indicators

### Live Execution
- **Recent Trades**: Trade count and turnover
- **Live PnL**: Real-time portfolio value
- **Slippage Monitor**: Execution quality

## 🟦 **PORTFOLIO COMMAND FEATURES**

### Capital Engine
- **Strategy Allocation Pie**: Capital distribution across strategies
- **Bayesian Skill Bar**: Average strategy skill level
- **Active Strategies**: Count of competing strategies

### Holdings Analysis
- **Top Holdings Table**: Current positions and weights
- **Holdings Visualization**: Bar chart of top positions
- **Sector Breakdown**: Portfolio sector allocation

### Performance Tracking
- **Portfolio Value**: Current equity value
- **20D Return**: Recent performance
- **Volatility**: Portfolio volatility
- **Max Drawdown**: Historical maximum drawdown
- **Equity Curve**: Visual performance chart

## 🧠 **INTELLIGENCE ORGANISM FEATURES**

### AI Narrative Engine
- **AI Status**: Active/dormant/error status
- **Regime Detection**: AI-detected market regime
- **Conviction Level**: AI confidence in analysis
- **Primary Action**: Main recommendation

### Key Market Forces
- **Macro Environment**: Current regime and score
- **Liquidity Conditions**: Tight/ample/neutral
- **AI Assessment**: High/medium/low conviction

### Strategy Evolution
- **Skill Evolution**: Strategy performance over time
- **Learning System**: AI health and adaptation status
- **Recent Insights**: Latest AI discoveries

## 🔧 **TECHNICAL DETAILS**

### Data Flow
```
Raw Data → Snapshot Builder → Unified Snapshot → Three Dashboard Views
```

### File Structure
```
data/processed/cache/dashboard_snapshot.parquet  # Single source of truth
src/dashboard/data_loader.py                     # Data loading functions
src/intelligence/build_dashboard_snapshot.py     # Snapshot builder
src/automation/snapshot_scheduler.py             # 5-minute scheduler
northstar_unified_terminal.py                    # Main terminal
launch_unified_terminal.py                       # Master launcher
```

### Caching Strategy
- **5-minute TTL**: Streamlit cache refreshes every 5 minutes
- **Background Updates**: Scheduler builds fresh snapshots
- **Instant Loading**: All data from single cached file

## 🎨 **DESIGN PHILOSOPHY**

### Visual Hierarchy
- **War Room**: Red/danger colors for risk monitoring
- **Portfolio**: Blue/corporate colors for analysis
- **Intelligence**: Green/sci-fi colors for AI thinking

### Information Density
- **War Room**: High density for quick scanning
- **Portfolio**: Medium density for detailed analysis  
- **Intelligence**: Low density for deep thinking

### Mental State Switching
You're not switching pages - you're switching mental states:
- **Operations**: "Keep us alive"
- **Management**: "Deploy capital wisely"
- **Strategy**: "Understand the world"

## 🏥 **HEALTH MONITORING**

The system continuously monitors its own health:
- **Data Age**: How fresh is the data?
- **Missing Files**: Are critical files present?
- **System Grade**: Overall health (A/B/C/D)
- **Component Status**: Which parts are working?

## 🚀 **WHAT MAKES THIS ELITE**

This terminal matches how real hedge funds think:

| Layer | Purpose | Color | Density |
|-------|---------|-------|---------|
| War Room | Survival | Red | High |
| Portfolio | Capital | Blue | Medium |
| Intelligence | Understanding | Green | Low |

Each layer uses different colors, chart types, and information density, but all share the same truth from the unified snapshot.

## 🎯 **NEXT STEPS**

The unified terminal is now ready for:
1. **Real-time Operations**: Monitor portfolio safety
2. **Capital Deployment**: Analyze holdings and allocation
3. **Strategic Planning**: Understand market dynamics
4. **System Evolution**: Learn and adapt over time

This is no longer just a dashboard - it's a complete hedge fund brain that thinks, learns, and adapts while providing multiple interfaces for different operational needs.

---

**Built like Bloomberg + Two Sigma + a war room.**