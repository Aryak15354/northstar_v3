# Alpha Autopsy System Design

## Overview

The Alpha Autopsy System performs forensic analysis on failed walk-forward validations to identify exactly what is destroying performance. This is surgical diagnosis, not backtesting - we dissect the corpse to understand what killed it.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Alpha Autopsy System                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │ Sealed Results  │    │ System Hashes   │                │
│  │ Loader          │    │ Validator       │                │
│  └─────────────────┘    └─────────────────┘                │
│           │                       │                        │
│           └───────────┬───────────┘                        │
│                       │                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Forensic Analysis Engine                  │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │ Specialist PnL  │  │ Regime Loss     │              │ │
│  │  │ Analyzer        │  │ Analyzer        │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  │                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │ Timing          │  │ Cost Attribution│              │ │
│  │  │ Analyzer        │  │ Engine          │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  │                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │ Stability       │  │ Pattern         │              │ │
│  │  │ Analyzer        │  │ Detector        │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
│                       │                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Forensic Reporter                         │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │ Kill List       │  │ Fix List        │              │ │
│  │  │ Generator       │  │ Generator       │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  │                                                         │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │ Failure Mode    │  │ Recommendation  │              │ │
│  │  │ Ranker          │  │ Engine          │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Sealed Results Loader

**Purpose:** Load and validate cryptographically sealed walk-forward results

**Key Methods:**
- `load_sealed_results(file_path)` - Load sealed JSON results
- `validate_system_hash(results)` - Verify system hasn't been tampered with
- `extract_performance_data(results)` - Extract key performance metrics
- `load_multiple_runs(directory)` - Load multiple runs for stability analysis

**Data Structures:**
```python
class SealedResults:
    system_hash: str
    daily_nav: List[float]
    daily_costs: List[float]
    daily_regime: List[str]
    specialist_allocations: List[Dict]
    daily_trades: List[Dict]
    market_data: pd.DataFrame
    run_timestamp: str
    results_hash: str
```

### 2. Specialist PnL Analyzer

**Purpose:** Decompose total PnL by individual specialists to identify bleeding engines

**Key Methods:**
- `calculate_specialist_pnl(results)` - Calculate PnL by specialist
- `rank_specialists_by_performance()` - Rank from worst to best
- `identify_bleeding_specialists()` - Flag negative PnL specialists
- `calculate_specialist_metrics()` - Hit rate, Sharpe, etc.

**Analysis Output:**
```python
class SpecialistAnalysis:
    momentum_pnl: float
    value_pnl: float
    quality_pnl: float
    macro_pnl: float
    specialist_rankings: List[Tuple[str, float]]
    bleeding_specialists: List[str]
    specialist_metrics: Dict[str, Dict]
```

### 3. Regime Loss Analyzer

**Purpose:** Identify when losses occurred relative to regime changes

**Key Methods:**
- `overlay_losses_with_regimes(results)` - Map losses to regime periods
- `analyze_regime_transitions()` - Performance around transitions
- `calculate_regime_pnl()` - PnL by regime type
- `identify_problem_regimes()` - Flag consistently losing regimes

**Analysis Output:**
```python
class RegimeAnalysis:
    regime_pnl: Dict[str, float]
    transition_performance: Dict[str, float]
    problem_regimes: List[str]
    regime_timing_lag: Dict[str, int]  # Days late
    loss_clustering: Dict[str, List[date]]
```

### 4. Timing Analyzer

**Purpose:** Separate timing losses from selection losses

**Key Methods:**
- `calculate_perfect_timing_pnl()` - PnL with perfect regime timing
- `measure_regime_entry_lag()` - How late we enter regimes
- `measure_regime_exit_lag()` - How late we exit regimes
- `separate_timing_vs_selection()` - Decompose loss sources

**Analysis Output:**
```python
class TimingAnalysis:
    perfect_timing_pnl: float
    actual_pnl: float
    timing_drag: float
    selection_alpha: float
    entry_lag_days: Dict[str, int]
    exit_lag_days: Dict[str, int]
    timing_vs_selection_ratio: float
```

### 5. Cost Attribution Engine

**Purpose:** Break down total loss into specific cost components

**Key Methods:**
- `calculate_gross_alpha()` - Performance before all costs
- `attribute_transaction_costs()` - Slippage, market impact, etc.
- `calculate_turnover_costs()` - Cost per regime change
- `identify_primary_cost_driver()` - Biggest cost component

**Analysis Output:**
```python
class CostAnalysis:
    gross_alpha: float
    net_alpha: float
    slippage_cost: float
    market_impact_cost: float
    turnover_cost: float
    borrow_cost: float
    crowding_penalty: float
    primary_cost_driver: str
    cost_dominated: bool
```

### 6. Stability Analyzer

**Purpose:** Measure performance stability across multiple runs

**Key Methods:**
- `calculate_nav_distribution()` - Distribution of final NAV values
- `measure_stability_metrics()` - Coefficient of variation, etc.
- `detect_heavy_tails()` - Probability of severe losses
- `assess_edge_reliability()` - Is there consistent edge?

**Analysis Output:**
```python
class StabilityAnalysis:
    nav_distribution: Dict[str, float]  # mean, std, skew, kurtosis
    coefficient_of_variation: float
    downside_tail_probability: float
    edge_reliability_score: float
    stability_verdict: str  # "stable", "unstable", "gambling"
```

### 7. Forensic Reporter

**Purpose:** Generate actionable recommendations based on forensic analysis

**Key Methods:**
- `generate_kill_list()` - Components to eliminate
- `generate_fix_list()` - Components to improve
- `rank_failure_modes()` - Priority order for fixes
- `recommend_next_actions()` - Specific next steps

**Report Output:**
```python
class ForensicReport:
    kill_list: List[str]  # Components to eliminate
    fix_list: List[Tuple[str, str]]  # (component, fix_type)
    failure_mode_ranking: List[Tuple[str, float]]  # (mode, severity)
    primary_failure_mode: str
    recommended_actions: List[str]
    structural_changes_needed: List[str]
```

## Key Algorithms

### Specialist PnL Attribution

```python
def calculate_specialist_pnl(results):
    """
    Decompose total PnL by specialist allocation weights
    """
    specialist_pnl = {}
    
    for day, (nav_change, allocations) in enumerate(zip(nav_changes, specialist_allocations)):
        for specialist, weight in allocations.items():
            if specialist not in specialist_pnl:
                specialist_pnl[specialist] = 0
            
            # Attribute PnL proportionally to allocation weight
            specialist_pnl[specialist] += nav_change * weight
    
    return specialist_pnl
```

### Regime Transition Analysis

```python
def analyze_regime_transitions(results):
    """
    Measure performance around regime changes
    """
    transitions = detect_regime_changes(results.daily_regime)
    transition_performance = {}
    
    for transition_date, (old_regime, new_regime) in transitions.items():
        # Performance 20 days before and after transition
        pre_performance = calculate_performance(transition_date - 20, transition_date)
        post_performance = calculate_performance(transition_date, transition_date + 20)
        
        transition_key = f"{old_regime}_to_{new_regime}"
        transition_performance[transition_key] = {
            'pre_performance': pre_performance,
            'post_performance': post_performance,
            'transition_cost': pre_performance + post_performance
        }
    
    return transition_performance
```

### Cost Attribution Waterfall

```python
def calculate_cost_waterfall(results):
    """
    Break down total loss into component costs
    """
    # Start with gross returns (before any costs)
    gross_alpha = calculate_gross_alpha(results)
    
    # Subtract each cost component
    net_after_slippage = gross_alpha - calculate_slippage_cost(results)
    net_after_impact = net_after_slippage - calculate_market_impact_cost(results)
    net_after_turnover = net_after_impact - calculate_turnover_cost(results)
    net_after_borrow = net_after_turnover - calculate_borrow_cost(results)
    final_net = net_after_borrow - calculate_crowding_penalty(results)
    
    return {
        'gross_alpha': gross_alpha,
        'slippage_cost': gross_alpha - net_after_slippage,
        'market_impact_cost': net_after_slippage - net_after_impact,
        'turnover_cost': net_after_impact - net_after_turnover,
        'borrow_cost': net_after_turnover - net_after_borrow,
        'crowding_penalty': net_after_borrow - final_net,
        'final_net': final_net
    }
```

## Integration Points

### With Walk-Forward Engine
- Reads sealed results from `sealed_results.json`
- Validates system hashes from `system_freeze_hash.txt`
- Analyzes multiple runs from different executions

### With Institutional Alpha Engine
- Maps specialist allocations to performance
- Analyzes regime detection timing
- Evaluates signal strength vs noise

### With Shadow Fund Engine
- Analyzes transaction cost impact
- Evaluates execution timing
- Measures slippage and market impact

## Output Formats

### Forensic Analysis Report
```json
{
  "analysis_timestamp": "2026-01-04T10:30:00",
  "runs_analyzed": 3,
  "primary_failure_mode": "cost_dominated",
  "specialist_analysis": {
    "momentum": {"pnl": -15.2, "rank": 4, "verdict": "kill"},
    "value": {"pnl": -8.1, "rank": 3, "verdict": "fix"},
    "quality": {"pnl": 2.3, "rank": 1, "verdict": "keep"},
    "macro": {"pnl": -1.1, "rank": 2, "verdict": "fix"}
  },
  "regime_analysis": {
    "crisis_transitions": {"avg_loss": -12.5, "timing_lag": 15},
    "problem_regimes": ["crisis", "high_volatility"]
  },
  "cost_analysis": {
    "gross_alpha": 2.1,
    "total_costs": -40.1,
    "primary_cost_driver": "turnover_cost",
    "cost_dominated": true
  },
  "stability_analysis": {
    "coefficient_of_variation": 0.85,
    "verdict": "unstable",
    "edge_reliability": "low"
  },
  "recommendations": {
    "kill_list": ["momentum_specialist"],
    "fix_list": ["regime_detection_lag", "turnover_reduction"],
    "next_actions": [
      "Eliminate momentum specialist",
      "Reduce regime switching frequency",
      "Increase signal threshold for trades"
    ]
  }
}
```

## Success Metrics

1. **Diagnostic Accuracy**: Can identify the primary failure mode correctly
2. **Actionability**: Recommendations lead to measurable improvements
3. **Speed**: Complete forensic analysis in under 60 seconds
4. **Reliability**: Consistent diagnosis across multiple runs
5. **Completeness**: Covers all major failure modes (specialist, regime, timing, cost, stability)

## Implementation Priority

1. **Phase 1**: Sealed Results Loader + Specialist PnL Analyzer
2. **Phase 2**: Cost Attribution Engine + Stability Analyzer  
3. **Phase 3**: Regime Loss Analyzer + Timing Analyzer
4. **Phase 4**: Forensic Reporter + Pattern Detector
5. **Phase 5**: Real-time monitoring integration

This system will tell us exactly what killed the performance and what needs to be fixed. No lies, no hope - only evidence.