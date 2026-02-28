
# TEMPORAL GUARD INTEGRATION GUIDE

## 1. Replace Direct Data Access

### BEFORE (Dangerous):
```python
# Direct CSV access
df = pd.read_csv('data/prices/RELIANCE.csv')
latest_price = df.iloc[-1]['Close']

# Direct yfinance access  
data = yf.download('RELIANCE.NS', start='2020-01-01')
```

### AFTER (Safe):
```python
from src.intelligence.temporal_guard import TemporalGuard

guard = TemporalGuard()
current_time = datetime(2024, 1, 15)  # Your simulation time

# Temporal-safe access
df = guard.get_data('RELIANCE.NS', current_time, 'prices')
if not df.empty:
    latest_price = df.iloc[-1]['Close']
```

## 2. Replace Signal Calculations

### BEFORE (Dangerous):
```python
def calculate_momentum(symbol):
    data = pd.read_csv(f'data/prices/{symbol}.csv')
    return data['Close'].pct_change(20).iloc[-1]
```

### AFTER (Safe):
```python
def calculate_momentum(symbol, current_time, guard):
    data = guard.get_data(symbol, current_time, 'prices')
    if len(data) < 21:
        return 0.0
    return data['Close'].pct_change(20).iloc[-1]
```

## 3. Replace Regime Detection

### BEFORE (Dangerous):
```python
def detect_regime():
    macro_data = pd.read_csv('data/macro/yields.csv')
    latest_yield = macro_data.iloc[-1]['10Y']
    return 'bull' if latest_yield < 6.0 else 'bear'
```

### AFTER (Safe):
```python
def detect_regime(current_time, guard):
    macro_data = guard.get_macro_data(current_time)
    latest_yield = macro_data.get('yields', {}).get('10Y', 6.0)
    return 'bull' if latest_yield < 6.0 else 'bear'
```

## 4. Add Scramble Tests

For every signal, add a scramble test:

```python
def test_my_signal():
    guard = TemporalGuard()
    
    def signal_function(data):
        # Your signal calculation here
        return calculate_my_signal(data)
    
    result = guard.run_scramble_test(
        'RELIANCE.NS', 
        datetime(2024, 1, 15),
        signal_function,
        iterations=10
    )
    
    assert result['passed'], "Signal has look-ahead bias!"
```

## 5. Integration Checklist

- [ ] Replace all pd.read_csv() with guard.get_data()
- [ ] Replace all yf.download() with guard.get_data()
- [ ] Replace all .iloc[-1] with temporal checks
- [ ] Add current_time parameter to all signal functions
- [ ] Add scramble tests for all signals
- [ ] Run full system test with temporal guard
- [ ] Measure Sharpe before/after (expect 30-70% drop if bias existed)

## 6. Critical Files to Update

1. src/intelligence/bayesian_engine.py
2. src/intelligence/valuation_engines.py  
3. src/portfolio/strategies.py
4. src/backtesting/backtest_engine.py
5. src/state/market_state.py

## 7. Testing Protocol

1. Run scramble tests on all signals
2. Compare Sharpe ratios before/after temporal protection
3. Verify no future data access in logs
4. Run walk-forward test with temporal guard enabled

Remember: If Sharpe drops significantly, that's GOOD - it means you found the lies.
