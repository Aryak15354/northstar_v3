# 🚀 NORTHSTAR V3 - UNIFICATION ROADMAP & IMPLEMENTATION GUIDE

**Step-by-Step Plan to Transform Fragmented System into Unified Operating System**

---

## 📋 EXECUTIVE SUMMARY

Northstar V3 consists of **40+ components** across **8 layers** that operate as **separate organisms** rather than **one unified system**. This roadmap provides a **concrete, phased approach** to unify them into a **single coherent investment operating system**.

**Key Principle**: We're not building new functionality—we're **orchestrating existing components** into a unified whole.

---

## 🎯 UNIFICATION OBJECTIVES

### **Objective 1: Single Entry Point**
- **Current**: 8 separate entry points (northstar_trading_desk.py, northstar_professional.py, etc.)
- **Target**: 1 unified entry point (northstar_v3_unified.py)
- **Benefit**: Simplified system initialization and mode selection

### **Objective 2: Unified Orchestration**
- **Current**: 2 separate orchestrators (System, Market Brain)
- **Target**: 1 Master Orchestrator coordinating all subsystems
- **Benefit**: Coordinated execution and clear sequencing

### **Objective 3: Unified Intelligence**
- **Current**: 3 separate intelligence systems (Stack, Brain, Strategy)
- **Target**: 1 Unified Intelligence Engine with shared beliefs
- **Benefit**: Coherent market understanding and decision-making

### **Objective 4: Unified Data Pipeline**
- **Current**: 3 separate data collection entry points
- **Target**: 1 Data Pipeline Coordinator
- **Benefit**: Consistent data flow and validation

### **Objective 5: Unified Portfolio Management**
- **Current**: 3 separate portfolio systems (Strategy, Governor, Allocator)
- **Target**: 1 Portfolio Construction Pipeline
- **Benefit**: Clear portfolio construction flow

### **Objective 6: Unified Risk Management**
- **Current**: 4 separate risk systems
- **Target**: 1 Unified Risk Framework
- **Benefit**: Integrated risk controls

### **Objective 7: Unified State Management**
- **Current**: 3 separate state systems
- **Target**: 1 Unified State Model
- **Benefit**: Single source of truth

### **Objective 8: Unified User Interface**
- **Current**: 4 separate UI implementations
- **Target**: 1 Unified Terminal with multiple views
- **Benefit**: Consistent user experience

---

## 📅 IMPLEMENTATION ROADMAP

### **PHASE 1: FOUNDATION (Week 1-2)**

#### **1.1 Create Unified Entry Point**

**File**: `northstar_v3_unified.py`

```python
#!/usr/bin/env python3
"""
🧭 NORTHSTAR V3 - UNIFIED ENTRY POINT
Single entry point for all Northstar V3 operations
"""

import argparse
import sys
from src.orchestrator.master_orchestrator import MasterOrchestrator

def main():
    parser = argparse.ArgumentParser(description='Northstar V3 Unified System')
    parser.add_argument('--mode', choices=['live', 'backtest', 'dashboard', 'update'], 
                       default='dashboard', help='Operation mode')
    parser.add_argument('--dashboard', choices=['trading-desk', 'professional', 'intelligence', 'unified'],
                       default='unified', help='Dashboard type')
    parser.add_argument('--quick', action='store_true', help='Quick update (skip full brain)')
    
    args = parser.parse_args()
    
    # Initialize Master Orchestrator
    orchestrator = MasterOrchestrator()
    
    # Execute based on mode
    if args.mode == 'live':
        orchestrator.run_live_trading()
    elif args.mode == 'backtest':
        orchestrator.run_backtest()
    elif args.mode == 'dashboard':
        orchestrator.run_dashboard(args.dashboard)
    elif args.mode == 'update':
        orchestrator.run_system_update(quick=args.quick)

if __name__ == "__main__":
    main()
```

**Usage**:
```bash
python northstar_v3_unified.py --mode dashboard --dashboard unified
python northstar_v3_unified.py --mode update --quick
python northstar_v3_unified.py --mode live
```

#### **1.2 Create Master Orchestrator**

**File**: `src/orchestrator/master_orchestrator.py`

```python
class MasterOrchestrator:
    """
    Master Orchestrator - Coordinates all Northstar V3 subsystems
    
    Responsibilities:
    - Initialize all subsystems
    - Coordinate execution sequencing
    - Manage state propagation
    - Handle error recovery
    """
    
    def __init__(self):
        self.system_orchestrator = SystemOrchestrator()
        self.market_brain_orchestrator = MarketBrainOrchestrator()
        self.data_pipeline_coordinator = DataPipelineCoordinator()
        self.intelligence_coordinator = IntelligenceCoordinator()
        self.portfolio_coordinator = PortfolioCoordinator()
        self.risk_coordinator = RiskCoordinator()
        self.state_manager = UnifiedStateManager()
    
    def run_system_update(self, quick=False):
        """Run complete system update"""
        # 1. Collect data
        self.data_pipeline_coordinator.collect_data()
        
        # 2. Process data
        self.data_pipeline_coordinator.process_data()
        
        # 3. Update market state
        self.state_manager.update_market_state()
        
        # 4. Generate intelligence
        if not quick:
            self.intelligence_coordinator.generate_intelligence()
        else:
            self.intelligence_coordinator.quick_update()
        
        # 5. Construct portfolio
        self.portfolio_coordinator.construct_portfolio()
        
        # 6. Apply risk management
        self.risk_coordinator.apply_risk_management()
        
        # 7. Update dashboards
        self.state_manager.build_dashboard_snapshot()
    
    def run_dashboard(self, dashboard_type='unified'):
        """Launch dashboard"""
        # Ensure system is up to date
        self.run_system_update(quick=True)
        
        # Launch appropriate dashboard
        if dashboard_type == 'unified':
            from src.dashboard.unified_terminal import UnifiedTerminal
            terminal = UnifiedTerminal()
            terminal.run()
        # ... other dashboard types
```

#### **1.3 Create Unified State Manager**

**File**: `src/state/unified_state_manager.py`

```python
class UnifiedStateManager:
    """
    Unified State Manager - Single source of truth for all system state
    
    Manages:
    - Market state
    - Intelligence state
    - Portfolio state
    - Risk state
    """
    
    def __init__(self):
        self.market_state = {}
        self.intelligence_state = {}
        self.portfolio_state = {}
        self.risk_state = {}
        self.state_file = 'data/processed/unified_state.json'
    
    def get_unified_state(self):
        """Get complete unified state"""
        return {
            'market': self.market_state,
            'intelligence': self.intelligence_state,
            'portfolio': self.portfolio_state,
            'risk': self.risk_state,
            'timestamp': datetime.now().isoformat()
        }
    
    def update_market_state(self):
        """Update market state from Market State Spine"""
        # Load from market_state.parquet
        # Merge with Market Brain state
        # Store in unified state
        pass
    
    def update_intelligence_state(self):
        """Update intelligence state from all intelligence systems"""
        # Merge Intelligence Stack beliefs
        # Merge Market Brain intelligence
        # Merge Strategy Intelligence
        # Store in unified state
        pass
    
    def update_portfolio_state(self):
        """Update portfolio state"""
        # Load portfolio weights
        # Load strategy allocations
        # Load performance metrics
        # Store in unified state
        pass
    
    def update_risk_state(self):
        """Update risk state"""
        # Load emergency brake status
        # Load kill switch status
        # Load survival mode
        # Store in unified state
        pass
    
    def build_dashboard_snapshot(self):
        """Build unified snapshot for all dashboards"""
        snapshot = self.get_unified_state()
        # Save to parquet for fast loading
        # Save to JSON for debugging
        pass
```

**Deliverables for Phase 1**:
- ✅ `northstar_v3_unified.py` - Single entry point
- ✅ `src/orchestrator/master_orchestrator.py` - Master orchestrator
- ✅ `src/state/unified_state_manager.py` - Unified state manager
- ✅ Documentation of unified architecture

---

### **PHASE 2: DATA PIPELINE UNIFICATION (Week 3)**

#### **2.1 Create Data Pipeline Coordinator**

**File**: `src/ingestion/data_pipeline_coordinator.py`

```python
class DataPipelineCoordinator:
    """
    Unified Data Pipeline Coordinator
    
    Coordinates:
    - Market data collection (EOD Options)
    - Macro data collection (RBI Scraper)
    - Data validation
    - Data transformation
    - Market State Spine feeding
    """
    
    def __init__(self):
        self.market_collector = MarketDataCollector()
        self.macro_collector = MacroDataCollector()
        self.validator = DataValidator()
        self.transformer = DataTransformer()
    
    def collect_data(self):
        """Collect all data sources"""
        print("📊 Collecting market data...")
        market_data = self.market_collector.collect()
        
        print("🏦 Collecting macro data...")
        macro_data = self.macro_collector.collect()
        
        return market_data, macro_data
    
    def validate_data(self, market_data, macro_data):
        """Validate collected data"""
        print("✓ Validating data...")
        
        market_valid = self.validator.validate_market_data(market_data)
        macro_valid = self.validator.validate_macro_data(macro_data)
        
        return market_valid and macro_valid
    
    def process_data(self):
        """Process all data"""
        # Collect
        market_data, macro_data = self.collect_data()
        
        # Validate
        if not self.validate_data(market_data, macro_data):
            raise Exception("Data validation failed")
        
        # Transform
        print("🔄 Transforming data...")
        processed = self.transformer.transform(market_data, macro_data)
        
        # Feed to Market State Spine
        print("🧠 Feeding Market State Spine...")
        self.feed_market_state_spine(processed)
    
    def feed_market_state_spine(self, processed_data):
        """Feed processed data to Market State Spine"""
        # Market State Spine reads this data
        # and computes unified market state
        pass
```

#### **2.2 Consolidate Data Collection**

**Changes**:
- `eod_options_pipeline.py` → Called by `DataPipelineCoordinator`
- `rbi_scraper_fixed.py` → Called by `DataPipelineCoordinator`
- `integrated_data_pipeline.py` → Merged into `DataPipelineCoordinator`

**Deliverables for Phase 2**:
- ✅ `src/ingestion/data_pipeline_coordinator.py` - Unified coordinator
- ✅ Consolidated data collection logic
- ✅ Unified data validation
- ✅ Single data flow to Market State Spine

---

### **PHASE 3: INTELLIGENCE UNIFICATION (Week 4-5)**

#### **3.1 Create Unified Intelligence Engine**

**File**: `src/intelligence/unified_intelligence_engine.py`

```python
class UnifiedIntelligenceEngine:
    """
    Unified Intelligence Engine
    
    Coordinates:
    - Market Intelligence (Market Brain)
    - Valuation Intelligence (Intelligence Stack)
    - Strategy Intelligence (Strategy System)
    - Unified Belief System
    """
    
    def __init__(self):
        self.market_brain = MarketBrainOrchestrator()
        self.intelligence_stack = IntelligenceStack()
        self.strategy_intelligence = StrategyIntelligence()
        self.belief_system = UnifiedBeliefSystem()
    
    def generate_intelligence(self):
        """Generate complete unified intelligence"""
        print("🧠 Generating unified intelligence...")
        
        # 1. Market Intelligence
        print("1️⃣ Market Intelligence...")
        market_beliefs = self.market_brain.generate_intelligence()
        
        # 2. Valuation Intelligence
        print("2️⃣ Valuation Intelligence...")
        valuation_beliefs = self.intelligence_stack.generate_intelligence()
        
        # 3. Strategy Intelligence
        print("3️⃣ Strategy Intelligence...")
        strategy_beliefs = self.strategy_intelligence.generate_intelligence()
        
        # 4. Merge into Unified Beliefs
        print("4️⃣ Merging into unified beliefs...")
        unified_beliefs = self.belief_system.merge_beliefs(
            market_beliefs,
            valuation_beliefs,
            strategy_beliefs
        )
        
        return unified_beliefs
    
    def quick_update(self):
        """Quick intelligence update (pulse only)"""
        # Update market pulse only
        # Skip full brain computation
        pass
```

#### **3.2 Create Unified Belief System**

**File**: `src/intelligence/unified_belief_system.py`

```python
class UnifiedBeliefSystem:
    """
    Unified Belief System - Single source of truth for all beliefs
    
    Manages:
    - Market beliefs (regime, risk-on probability, etc.)
    - Valuation beliefs (undervaluation scores, confidence)
    - Strategy beliefs (skill, regret, conviction)
    """
    
    def __init__(self):
        self.beliefs = {
            'market': {},
            'valuation': {},
            'strategy': {}
        }
    
    def merge_beliefs(self, market_beliefs, valuation_beliefs, strategy_beliefs):
        """Merge all beliefs into unified system"""
        self.beliefs['market'] = market_beliefs
        self.beliefs['valuation'] = valuation_beliefs
        self.beliefs['strategy'] = strategy_beliefs
        
        # Compute unified conviction
        unified_conviction = self.compute_unified_conviction()
        
        return {
            'beliefs': self.beliefs,
            'conviction': unified_conviction,
            'timestamp': datetime.now().isoformat()
        }
    
    def compute_unified_conviction(self):
        """Compute overall system conviction"""
        # Combine market, valuation, and strategy conviction
        # Weight by importance
        # Return unified conviction score
        pass
```

**Deliverables for Phase 3**:
- ✅ `src/intelligence/unified_intelligence_engine.py` - Unified coordinator
- ✅ `src/intelligence/unified_belief_system.py` - Unified beliefs
- ✅ Merged intelligence generation logic
- ✅ Unified belief propagation

---

### **PHASE 4: PORTFOLIO UNIFICATION (Week 6)**

#### **4.1 Create Portfolio Construction Pipeline**

**File**: `src/portfolio/portfolio_construction_pipeline.py`

```python
class PortfolioConstructionPipeline:
    """
    Unified Portfolio Construction Pipeline
    
    Coordinates:
    - Strategy generation
    - Strategy backtesting
    - Capital allocation
    - Portfolio blending
    - Risk adjustment
    """
    
    def __init__(self):
        self.strategy_system = StrategySystem()
        self.backtest_engine = BacktestEngine()
        self.capital_allocator = CapitalAllocator()
        self.portfolio_governor = PortfolioGovernor()
        self.risk_controller = MacroRiskController()
    
    def construct_portfolio(self):
        """Construct final portfolio"""
        print("🎯 Constructing portfolio...")
        
        # 1. Generate strategies
        print("1️⃣ Generating strategies...")
        strategies = self.strategy_system.generate_all_strategies()
        
        # 2. Backtest strategies
        print("2️⃣ Backtesting strategies...")
        strategy_performance = self.backtest_engine.backtest_all(strategies)
        
        # 3. Allocate capital
        print("3️⃣ Allocating capital...")
        allocations = self.capital_allocator.allocate_capital(strategy_performance)
        
        # 4. Blend strategies
        print("4️⃣ Blending strategies...")
        blended_portfolio = self.portfolio_governor.blend_strategies(
            strategies,
            allocations
        )
        
        # 5. Apply risk adjustment
        print("5️⃣ Applying risk adjustment...")
        final_portfolio = self.risk_controller.apply_macro_overlay(blended_portfolio)
        
        return final_portfolio
```

**Deliverables for Phase 4**:
- ✅ `src/portfolio/portfolio_construction_pipeline.py` - Unified pipeline
- ✅ Clear portfolio construction flow
- ✅ Unified portfolio output

---

### **PHASE 5: RISK MANAGEMENT UNIFICATION (Week 7)**

#### **5.1 Create Unified Risk Framework**

**File**: `src/risk/unified_risk_framework.py`

```python
class UnifiedRiskFramework:
    """
    Unified Risk Framework
    
    Coordinates:
    - System-level risk (Emergency Brake)
    - Portfolio-level risk (Kill Switches)
    - Position-level risk (Risk Controller)
    - Adaptive risk (Survival Instincts)
    """
    
    def __init__(self):
        self.emergency_brake = EmergencyBrake()
        self.kill_switches = PortfolioKillSwitches()
        self.risk_controller = PortfolioRiskController()
        self.survival_instincts = SurvivalInstincts()
    
    def apply_risk_management(self, portfolio):
        """Apply unified risk management"""
        print("🛡️ Applying risk management...")
        
        # 1. System-level risk check
        print("1️⃣ System-level risk check...")
        if self.emergency_brake.should_trigger():
            return self.emergency_brake.execute_protocol()
        
        # 2. Portfolio-level risk check
        print("2️⃣ Portfolio-level risk check...")
        if self.kill_switches.should_trigger(portfolio):
            portfolio = self.kill_switches.execute_exits(portfolio)
        
        # 3. Position-level risk adjustment
        print("3️⃣ Position-level risk adjustment...")
        portfolio = self.risk_controller.adjust_positions(portfolio)
        
        # 4. Adaptive risk adjustment
        print("4️⃣ Adaptive risk adjustment...")
        portfolio = self.survival_instincts.apply_survival_mode(portfolio)
        
        return portfolio
```

**Deliverables for Phase 5**:
- ✅ `src/risk/unified_risk_framework.py` - Unified framework
- ✅ Coordinated risk management
- ✅ Clear risk control hierarchy

---

### **PHASE 6: STATE MANAGEMENT UNIFICATION (Week 8)**

#### **6.1 Enhance Unified State Manager**

**Enhancements to Phase 1 State Manager**:

```python
class UnifiedStateManager:
    """Enhanced Unified State Manager"""
    
    def __init__(self):
        # ... existing code ...
        self.state_history = []
        self.state_file = 'data/processed/unified_state.json'
        self.state_parquet = 'data/processed/unified_state.parquet'
    
    def update_all_state(self):
        """Update all state components"""
        self.update_market_state()
        self.update_intelligence_state()
        self.update_portfolio_state()
        self.update_risk_state()
        self.save_state()
    
    def save_state(self):
        """Save unified state"""
        state = self.get_unified_state()
        
        # Save to JSON
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        # Save to Parquet
        df = pd.DataFrame([state])
        df.to_parquet(self.state_parquet, index=False)
        
        # Keep history
        self.state_history.append(state)
    
    def get_state_for_dashboard(self):
        """Get state formatted for dashboard"""
        state = self.get_unified_state()
        return self.format_for_dashboard(state)
```

**Deliverables for Phase 6**:
- ✅ Enhanced Unified State Manager
- ✅ State persistence and history
- ✅ Dashboard-formatted state

---

### **PHASE 7: USER INTERFACE UNIFICATION (Week 9)**

#### **7.1 Create Unified Terminal**

**File**: `src/dashboard/unified_terminal.py`

```python
class UnifiedTerminal:
    """
    Unified Terminal - Single UI with multiple views
    
    Views:
    - War Room (Operations)
    - Portfolio Command (Holdings)
    - Intelligence Organism (Strategy)
    """
    
    def __init__(self):
        self.state_manager = UnifiedStateManager()
        self.war_room = WarRoomView()
        self.portfolio_command = PortfolioCommandView()
        self.intelligence_organism = IntelligenceOrganismView()
    
    def run(self):
        """Run unified terminal"""
        st.set_page_config(layout="wide", page_title="Northstar V3 Unified Terminal")
        
        # Global status bar
        self.render_global_status_bar()
        
        # View selection
        view = st.sidebar.radio("Select View", 
                               ["War Room", "Portfolio Command", "Intelligence Organism"])
        
        # Render selected view
        if view == "War Room":
            self.war_room.render(self.state_manager.get_unified_state())
        elif view == "Portfolio Command":
            self.portfolio_command.render(self.state_manager.get_unified_state())
        elif view == "Intelligence Organism":
            self.intelligence_organism.render(self.state_manager.get_unified_state())
    
    def render_global_status_bar(self):
        """Render global status bar"""
        state = self.state_manager.get_unified_state()
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        
        with col1:
            st.metric("REGIME", state['market'].get('regime', 'N/A'))
        with col2:
            st.metric("RISK", f"{state['market'].get('stress', 0):.1%}")
        with col3:
            st.metric("EXPOSURE", f"{state['portfolio'].get('exposure', 0):.1%}")
        with col4:
            st.metric("DD", f"{state['portfolio'].get('drawdown', 0):.1%}")
        with col5:
            st.metric("VOL", f"{state['market'].get('volatility', 0):.1%}")
        with col6:
            st.metric("LIQUIDITY", state['market'].get('liquidity', 'N/A'))
        with col7:
            st.metric("AI CONVICTION", f"{state['intelligence'].get('conviction', 0):.1%}")
```

**Deliverables for Phase 7**:
- ✅ `src/dashboard/unified_terminal.py` - Unified terminal
- ✅ Consolidated UI logic
- ✅ Shared data layer
- ✅ Multiple views from single state

---

### **PHASE 8: INTEGRATION & TESTING (Week 10)**

#### **8.1 Integration Testing**

```python
class IntegrationTests:
    """Integration tests for unified system"""
    
    def test_data_flow(self):
        """Test complete data flow"""
        # Data collection → Processing → State → Intelligence → Portfolio → Risk
        pass
    
    def test_state_consistency(self):
        """Test state consistency across all components"""
        # Verify all components read from unified state
        pass
    
    def test_orchestration(self):
        """Test master orchestrator"""
        # Verify correct sequencing
        pass
    
    def test_ui_rendering(self):
        """Test UI rendering"""
        # Verify all views render correctly
        pass
```

#### **8.2 Performance Testing**

```python
class PerformanceTests:
    """Performance tests for unified system"""
    
    def test_update_speed(self):
        """Test system update speed"""
        # Should complete in < 5 minutes
        pass
    
    def test_dashboard_load_time(self):
        """Test dashboard load time"""
        # Should load in < 2 seconds
        pass
    
    def test_memory_usage(self):
        """Test memory usage"""
        # Should use < 2GB RAM
        pass
```

**Deliverables for Phase 8**:
- ✅ Integration tests
- ✅ Performance tests
- ✅ System validation
- ✅ Production readiness certificate

---

## 📊 UNIFICATION BENEFITS

### **Operational Benefits**
- ✅ **Single entry point** instead of 8
- ✅ **Unified data flow** instead of fragmented
- ✅ **Coordinated execution** instead of parallel
- ✅ **Consistent state** across all systems
- ✅ **Simplified debugging** and monitoring

### **Architectural Benefits**
- ✅ **Clear dependencies** instead of implicit
- ✅ **Unified data model** instead of scattered
- ✅ **Coordinated intelligence** instead of separate
- ✅ **Integrated risk management** instead of fragmented
- ✅ **Coherent system** instead of collection of scripts

### **Performance Benefits**
- ✅ **Reduced redundant computation**
- ✅ **Optimized data flow**
- ✅ **Faster decision-making**
- ✅ **Better resource utilization**
- ✅ **Improved scalability**

### **Maintenance Benefits**
- ✅ **Easier to understand** system flow
- ✅ **Simpler to add** new features
- ✅ **Faster to debug** issues
- ✅ **Easier to test** components
- ✅ **Better code organization**

---

## 🎯 SUCCESS CRITERIA

### **Phase 1 Success**
- ✅ Single entry point works
- ✅ Master orchestrator coordinates subsystems
- ✅ Unified state manager maintains state

### **Phase 2 Success**
- ✅ Data collection is coordinated
- ✅ Data validation is unified
- ✅ Market State Spine receives consistent data

### **Phase 3 Success**
- ✅ Intelligence systems are coordinated
- ✅ Beliefs are unified
- ✅ Conviction is computed correctly

### **Phase 4 Success**
- ✅ Portfolio construction is sequential
- ✅ Capital allocation is clear
- ✅ Final portfolio is correct

### **Phase 5 Success**
- ✅ Risk management is coordinated
- ✅ Risk controls are hierarchical
- ✅ Emergency protocols work

### **Phase 6 Success**
- ✅ State is unified
- ✅ State is persistent
- ✅ State is accessible

### **Phase 7 Success**
- ✅ UI is unified
- ✅ All views work
- ✅ Data is consistent

### **Phase 8 Success**
- ✅ All tests pass
- ✅ Performance is acceptable
- ✅ System is production-ready

---

## 📈 TIMELINE

```
Week 1-2:   Foundation (Entry Point, Master Orchestrator, State Manager)
Week 3:     Data Pipeline Unification
Week 4-5:   Intelligence Unification
Week 6:     Portfolio Unification
Week 7:     Risk Management Unification
Week 8:     State Management Enhancement
Week 9:     User Interface Unification
Week 10:    Integration & Testing

Total: 10 weeks to complete unification
```

---

## 🎉 FINAL STATE

After unification, Northstar V3 will be:

```
┌─────────────────────────────────────────────────────────────┐
│         NORTHSTAR V3 - UNIFIED OPERATING SYSTEM             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  northstar_v3_unified.py (Single Entry Point)               │
│         ↓                                                    │
│  Master Orchestrator                                        │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Data Pipeline Coordinator                           │   │
│  │ Intelligence Coordinator                            │   │
│  │ Portfolio Coordinator                               │   │
│  │ Risk Coordinator                                    │   │
│  │ State Manager                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│         ↓                                                    │
│  Unified State (Single Source of Truth)                     │
│         ↓                                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Unified Terminal                                    │   │
│  │ ├─ War Room                                         │   │
│  │ ├─ Portfolio Command                                │   │
│  │ └─ Intelligence Organism                            │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**One coherent investment operating system.**

---

*Unification Roadmap Complete - Ready for Implementation*
