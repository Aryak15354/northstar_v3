# Design Document: System Integrity Repair

## Overview

This design addresses critical architectural flaws in Northstar V3's state management system. The current implementation has three competing sources of truth (Market Brain, Portfolio Governor, Unified State Manager) that produce contradictory outputs. This design establishes a single-source-of-truth architecture with proper bounds checking, meaningful health metrics, and atomic state operations.

## Architecture

### Current Problems

1. **Multiple Sources of Truth**: Market Brain, Portfolio Governor, and Unified State Manager each maintain their own state
2. **Unbounded Calculations**: Exposure can reach 3387% due to division by near-zero values
3. **Cosmetic Health Metrics**: System Health (80%) contradicts Market Health (0%)
4. **State Inconsistency**: Within a single run, regime flips from "late-expansion" to "unknown"
5. **Ignored Risk Limits**: Portfolio Governor forces 90% exposure regardless of market brain limits

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Canonical State Files                     │
│  (Single Source of Truth - File System)                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  data/processed/market_state.parquet                        │
│    - date, regime, risk_on, allowed_exposure, stress_score  │
│                                                              │
│  data/processed/portfolio_weights.parquet                   │
│    - date, symbol, weight, exposure                         │
│                                                              │
│  data/processed/risk_state.parquet                          │
│    - date, volatility, correlation, var                     │
│                                                              │
│  data/processed/exposure_history.parquet                    │
│    - date, allowed_exposure, actual_exposure                │
│                                                              │
│  data/processed/portfolio_analytics.json                    │
│    - drawdown, sharpe, returns, benchmark_comparison        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ Read Only
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Market Brain │    │  Portfolio   │    │   Unified    │
│              │    │  Governor    │    │    State     │
│  (Writer)    │    │  (Reader +   │    │   Manager    │
│              │    │   Writer)    │    │  (Reader)    │
└──────────────┘    └──────────────┘    └──────────────┘
```

**Key Principles:**
- Market Brain writes market_state.parquet (only writer)
- Portfolio Governor reads market_state, writes portfolio_weights
- Unified State Manager only reads, never writes
- All writes are atomic (temp file + rename)
- All calculations have hard bounds

## Components and Interfaces

### 1. State File Manager

**Purpose**: Provide atomic read/write operations for canonical state files

**Interface**:
```python
class StateFileManager:
    def read_market_state(self) -> pd.DataFrame
    def write_market_state(self, state: pd.DataFrame) -> None
    def read_portfolio_weights(self) -> pd.DataFrame
    def write_portfolio_weights(self, weights: pd.DataFrame) -> None
    def read_risk_state(self) -> pd.DataFrame
    def write_risk_state(self, risk: pd.DataFrame) -> None
    def validate_state_consistency(self) -> ValidationResult
```

**Implementation Details**:
- All writes use temp file + atomic rename pattern
- File locking prevents concurrent writes
- Schema validation before commit
- Automatic backup of previous state

### 2. Bounded Exposure Calculator

**Purpose**: Calculate exposure with mathematical guarantees

**Interface**:
```python
class BoundedExposureCalculator:
    def calculate_allowed_exposure(
        self, 
        risk_on: float, 
        stress_score: float,
        regime: str
    ) -> BoundedExposure
```

**Implementation Details**:
```python
@dataclass
class BoundedExposure:
    value: float  # Always in [0.0, 1.0]
    raw_value: float  # Unbounded calculation result
    was_bounded: bool  # True if bounds were applied
    bound_reason: Optional[str]  # Why it was bounded

def calculate_allowed_exposure(self, risk_on, stress_score, regime):
    # Raw calculation (may be unbounded)
    raw = self._raw_calculation(risk_on, stress_score, regime)
    
    # Handle special cases
    if math.isnan(raw):
        return BoundedExposure(0.0, raw, True, "NaN detected")
    if math.isinf(raw):
        return BoundedExposure(1.0, raw, True, "Infinity detected")
    
    # Apply bounds
    bounded = max(0.0, min(1.0, raw))
    was_bounded = (bounded != raw)
    reason = None
    if was_bounded:
        if raw < 0.0:
            reason = f"Negative value {raw:.4f} bounded to 0.0"
        else:
            reason = f"Excessive value {raw:.4f} bounded to 1.0"
    
    return BoundedExposure(bounded, raw, was_bounded, reason)
```

### 3. Meaningful Health Calculator

**Purpose**: Calculate health metrics that reflect actual system state

**Interface**:
```python
class HealthCalculator:
    def calculate_system_health(self) -> HealthMetrics
    
@dataclass
class HealthMetrics:
    overall_health: float  # [0.0, 1.0]
    data_freshness: float  # [0.0, 1.0]
    market_consistency: float  # [0.0, 1.0]
    portfolio_stability: float  # [0.0, 1.0]
    components: Dict[str, Any]  # Detailed breakdown
```

**Implementation Details**:
```python
def calculate_system_health(self):
    # Data Freshness (40% weight)
    market_state_age = self._get_file_age('market_state.parquet')
    portfolio_age = self._get_file_age('portfolio_weights.parquet')
    max_age_minutes = 60  # Threshold
    
    freshness = 1.0 - min(1.0, max(market_state_age, portfolio_age) / max_age_minutes)
    
    # Market Consistency (30% weight)
    market_state = self.state_manager.read_market_state()
    portfolio = self.state_manager.read_portfolio_weights()
    
    # Check if portfolio exposure aligns with market allowed_exposure
    allowed = market_state['allowed_exposure'].iloc[-1]
    actual = portfolio['exposure'].sum()
    consistency = 1.0 - min(1.0, abs(allowed - actual) / max(allowed, 0.01))
    
    # Portfolio Stability (30% weight)
    # Check recent weight changes
    recent_changes = self._calculate_recent_turnover(days=5)
    stability = 1.0 - min(1.0, recent_changes / 0.5)  # 50% turnover = 0 stability
    
    # Weighted combination
    overall = 0.4 * freshness + 0.3 * consistency + 0.3 * stability
    
    return HealthMetrics(
        overall_health=overall,
        data_freshness=freshness,
        market_consistency=consistency,
        portfolio_stability=stability,
        components={
            'market_state_age_minutes': market_state_age,
            'portfolio_age_minutes': portfolio_age,
            'allowed_exposure': allowed,
            'actual_exposure': actual,
            'recent_turnover': recent_changes
        }
    )
```

### 4. Aligned Portfolio Governor

**Purpose**: Construct portfolios that respect market brain exposure limits

**Interface**:
```python
class AlignedPortfolioGovernor:
    def construct_portfolio(
        self,
        signals: pd.DataFrame,
        market_state: pd.DataFrame
    ) -> Portfolio
```

**Implementation Details**:
```python
def construct_portfolio(self, signals, market_state):
    # Read allowed exposure from market brain
    allowed_exposure = market_state['allowed_exposure'].iloc[-1]
    
    # Calculate risk-scaled exposure based on portfolio risk
    portfolio_vol = self._estimate_portfolio_volatility(signals)
    target_vol = 0.15  # 15% annualized
    risk_scaled_exposure = min(1.0, target_vol / max(portfolio_vol, 0.01))
    
    # Take the minimum (most conservative)
    final_exposure = min(allowed_exposure, risk_scaled_exposure)
    
    # Log the decision
    logger.info(
        f"Exposure decision: "
        f"allowed={allowed_exposure:.1%}, "
        f"risk_scaled={risk_scaled_exposure:.1%}, "
        f"final={final_exposure:.1%}"
    )
    
    # Construct portfolio with final exposure
    weights = self._optimize_weights(signals, final_exposure)
    
    return Portfolio(weights=weights, exposure=final_exposure)
```

### 5. Read-Only Unified State Manager

**Purpose**: Provide consistent view of system state without recomputation

**Interface**:
```python
class ReadOnlyUnifiedStateManager:
    def get_current_state(self) -> SystemState
    def validate_consistency(self) -> List[str]  # Returns inconsistencies
```

**Implementation Details**:
```python
def get_current_state(self):
    # Simply read from canonical files
    market = self.file_manager.read_market_state()
    portfolio = self.file_manager.read_portfolio_weights()
    risk = self.file_manager.read_risk_state()
    
    # Validate consistency
    inconsistencies = self.validate_consistency()
    if inconsistencies:
        logger.warning(f"State inconsistencies detected: {inconsistencies}")
    
    return SystemState(
        market_state=market.iloc[-1].to_dict(),
        portfolio_weights=portfolio.to_dict('records'),
        risk_state=risk.iloc[-1].to_dict(),
        is_consistent=(len(inconsistencies) == 0),
        inconsistencies=inconsistencies
    )

def validate_consistency(self):
    issues = []
    
    market = self.file_manager.read_market_state()
    portfolio = self.file_manager.read_portfolio_weights()
    
    # Check date alignment
    market_date = market['date'].iloc[-1]
    portfolio_date = portfolio['date'].iloc[-1]
    if market_date != portfolio_date:
        issues.append(f"Date mismatch: market={market_date}, portfolio={portfolio_date}")
    
    # Check exposure alignment
    allowed = market['allowed_exposure'].iloc[-1]
    actual = portfolio['exposure'].sum()
    if abs(allowed - actual) > 0.05:  # 5% tolerance
        issues.append(f"Exposure mismatch: allowed={allowed:.1%}, actual={actual:.1%}")
    
    return issues
```

## Data Models

### Market State Schema
```python
market_state_schema = {
    'date': 'datetime64[ns]',
    'regime': 'str',  # One of: early-expansion, late-expansion, early-contraction, late-contraction
    'risk_on': 'float64',  # [0.0, 1.0]
    'allowed_exposure': 'float64',  # [0.0, 1.0]
    'stress_score': 'float64'  # [0.0, 1.0]
}
```

### Portfolio Weights Schema
```python
portfolio_weights_schema = {
    'date': 'datetime64[ns]',
    'symbol': 'str',
    'weight': 'float64',  # [-1.0, 1.0] (negative for shorts)
    'exposure': 'float64'  # Contribution to total exposure
}
```

### Exposure History Schema
```python
exposure_history_schema = {
    'date': 'datetime64[ns]',
    'allowed_exposure': 'float64',  # From market brain
    'actual_exposure': 'float64',  # From portfolio
    'risk_scaled_exposure': 'float64',  # From risk calculation
    'regime': 'str',
    'stress_score': 'float64'
}
```

### Portfolio Analytics Schema
```json
{
  "as_of_date": "2025-01-16",
  "portfolio_metrics": {
    "total_return": 0.15,
    "sharpe_ratio": 1.2,
    "max_drawdown": -0.08,
    "current_drawdown": -0.02,
    "volatility": 0.12
  },
  "benchmark_metrics": {
    "total_return": 0.10,
    "max_drawdown": -0.15,
    "current_drawdown": -0.05,
    "volatility": 0.18
  },
  "relative_performance": {
    "excess_return": 0.05,
    "information_ratio": 0.8,
    "tracking_error": 0.06
  }
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Acceptance Criteria Testing Prework

1.1 THE System SHALL maintain market state in exactly one canonical location
  Thoughts: This is about system architecture - we can test that only one file exists and all reads go to it
  Testable: yes - property

1.2 WHEN any component needs market state, THE System SHALL read from the canonical market state file
  Thoughts: We can instrument reads and verify they all target the same file path
  Testable: yes - property

2.1 WHEN calculating allowed exposure, THE System SHALL enforce a minimum bound of 0.0
  Thoughts: For any input, the output should be >= 0.0
  Testable: yes - property

2.2 WHEN calculating allowed exposure, THE System SHALL enforce a maximum bound of 1.0
  Thoughts: For any input, the output should be <= 1.0
  Testable: yes - property

2.3 IF a calculation produces NaN, THE System SHALL replace it with 0.0
  Thoughts: We can inject NaN values and verify replacement
  Testable: yes - property

3.1 THE System SHALL calculate health as a weighted combination
  Thoughts: For any component scores, the formula should be applied correctly
  Testable: yes - property

3.5 IF any component score is zero, THE System SHALL report overall health below 50%
  Thoughts: For any inputs where one component is 0, output should be < 0.5
  Testable: yes - property

4.1 THE Unified_State_Manager SHALL read from canonical data files
  Thoughts: We can verify all reads target the correct file paths
  Testable: yes - property

4.3 THE Unified_State_Manager SHALL NOT recompute or override canonical state values
  Thoughts: We can verify that values returned match file contents exactly
  Testable: yes - property

5.3 THE Portfolio_Governor SHALL set final_exposure to the minimum of allowed_exposure and risk_scaled_exposure
  Thoughts: For any two exposure values, final should equal their minimum
  Testable: yes - property

7.1 THE System SHALL maintain a time series of allowed_exposure
  Thoughts: After any exposure calculation, history should contain that value
  Testable: yes - property

8.1 THE System SHALL calculate portfolio drawdown as percentage decline from peak equity
  Thoughts: For any equity curve, drawdown formula should be applied correctly
  Testable: yes - property

10.1 WHEN writing state files, THE System SHALL write to temporary files first
  Thoughts: We can verify write operations create temp files before final files
  Testable: yes - property

10.2 WHEN temporary write completes, THE System SHALL atomically rename to canonical location
  Thoughts: This is a round-trip property - write then read should return same data
  Testable: yes - property

### Property Reflection

After reviewing all testable properties:

- Properties 2.1 and 2.2 can be combined into "Exposure bounds property"
- Properties 4.1 and 4.3 can be combined into "State manager read-only property"
- Properties 10.1 and 10.2 can be combined into "Atomic write property"

### Correctness Properties

**Property 1: Exposure Bounds**
*For any* risk_on, stress_score, and regime values, the calculated allowed_exposure must be in the range [0.0, 1.0], with NaN mapped to 0.0 and infinity mapped to 1.0
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

**Property 2: Health Calculation Formula**
*For any* data_freshness, market_consistency, and portfolio_stability scores in [0.0, 1.0], the overall health must equal 0.4 * data_freshness + 0.3 * market_consistency + 0.3 * portfolio_stability
**Validates: Requirements 3.1**

**Property 3: Zero Component Health Threshold**
*For any* component scores where at least one component equals 0.0, the overall health must be less than 0.5
**Validates: Requirements 3.5**

**Property 4: State Manager Read-Only**
*For any* canonical state file, when the Unified State Manager reads it, the returned values must exactly match the file contents without modification
**Validates: Requirements 4.1, 4.3**

**Property 5: Exposure Minimum Selection**
*For any* allowed_exposure and risk_scaled_exposure values, the Portfolio Governor's final_exposure must equal min(allowed_exposure, risk_scaled_exposure)
**Validates: Requirements 5.3**

**Property 6: Exposure History Append**
*For any* exposure calculation, the exposure_history file must contain a new row with that calculation's timestamp and values
**Validates: Requirements 7.1, 7.2**

**Property 7: Drawdown Calculation**
*For any* equity time series, the drawdown at time t must equal (equity[t] - max(equity[0:t])) / max(equity[0:t])
**Validates: Requirements 8.1**

**Property 8: Atomic Write Round-Trip**
*For any* state data written to a canonical file, immediately reading that file must return data equal to what was written
**Validates: Requirements 10.1, 10.2, 10.5**

**Property 9: Single Market State File**
*For any* system execution, there must exist exactly one market_state.parquet file at the canonical location
**Validates: Requirements 1.1**

**Property 10: Canonical File Reads**
*For any* component reading market state, the file path accessed must be the canonical market_state.parquet location
**Validates: Requirements 1.2**

## Error Handling

### Exposure Calculation Errors
- **NaN Detection**: Log warning, replace with 0.0, continue
- **Infinity Detection**: Log warning, replace with 1.0, continue
- **Division by Zero**: Catch, log, return 0.0

### File Operation Errors
- **Missing File**: Log error, return error state, do not start system
- **Corrupt File**: Log error, attempt to restore from backup, alert operator
- **Write Failure**: Log error, leave previous state intact, retry with exponential backoff
- **Lock Timeout**: Log warning, wait and retry up to 3 times, then fail

### State Inconsistency Errors
- **Date Mismatch**: Log warning, use most recent consistent state
- **Exposure Mismatch**: Log warning, trust market brain value, adjust portfolio
- **Schema Violation**: Log error, reject write, alert operator

## Testing Strategy

### Unit Tests
- Test BoundedExposureCalculator with edge cases (NaN, infinity, negative, >1.0)
- Test HealthCalculator with various component score combinations
- Test StateFileManager atomic write operations
- Test AlignedPortfolioGovernor exposure selection logic
- Test file locking behavior under concurrent access

### Property-Based Tests
Each property test will run 100 iterations with randomized inputs:

1. **Exposure Bounds Property**: Generate random risk_on, stress_score, regime → verify output in [0.0, 1.0]
2. **Health Formula Property**: Generate random component scores → verify weighted sum formula
3. **Zero Component Property**: Generate scores with at least one zero → verify health < 0.5
4. **Read-Only Property**: Write random state, read via StateManager → verify exact match
5. **Minimum Selection Property**: Generate random exposure pairs → verify min selection
6. **History Append Property**: Perform exposure calculation → verify history contains new row
7. **Drawdown Property**: Generate random equity curves → verify drawdown formula
8. **Atomic Write Property**: Write random data → immediately read → verify equality
9. **Single File Property**: Run system → verify exactly one market_state file exists
10. **Canonical Reads Property**: Instrument file access → verify all reads target canonical path

### Integration Tests
- Test full system startup with state validation
- Test market brain → portfolio governor → state manager flow
- Test exposure history accumulation over multiple days
- Test state recovery from backup after corruption
- Test concurrent access from multiple components

### Stress Tests
- Test with 10,000 rapid state updates
- Test with intentionally corrupted state files
- Test with missing state files
- Test with extremely large exposure values (1e10)
- Test with extremely small exposure values (1e-10)
