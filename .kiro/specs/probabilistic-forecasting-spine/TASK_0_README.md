# Task 0: Signal Reality Audit (MANDATORY)

## ⚠️ CRITICAL: This Task Must Pass Before Any Infrastructure Is Built

**DO NOT START TASK 1 WITHOUT COMPLETING THIS TASK**

## Why Task 0 Exists

The probabilistic forecasting spine (Tasks 1-19) is a sophisticated, institutional-grade forecasting framework. However, **70% of this infrastructure is premature if your signals are weak**.

Building a perfect forecasting spine on weak signals produces a perfectly engineered disappointment.

## What Task 0 Does

Task 0 validates whether your signals contain enough predictive power to justify the complexity of the full forecasting spine. It answers ONE critical question:

**What is your true rolling out-of-sample IC?**

If that number is below ~0.02, most of the planned infrastructure is overkill.

## The Brutal Truth

You may have built:
- A 9/10 risk engine ✓
- An 8/10 allocator ✓
- A 10/10 system architecture ✓

On top of:
- A 4/10 signal layer ✗

This mismatch creates frustration. Architecture doesn't create alpha. Signals do.

## Decision Rules

Task 0 applies strict validation rules:

| Condition | Action |
|-----------|--------|
| Mean IC < 0.015 | **STOP** - Redesign signals |
| Mean IC 0.015-0.025 | Build minimal ridge only (skip Bayesian) |
| Mean IC > 0.025 & stable | Proceed with full spine |
| Crisis IC flips sign | Add regime modeling (if IC > 0.03) or STOP |
| Stability ratio < 0.5 | **STOP** - Signals too unstable |

## What Task 0 Measures

For each candidate signal, Task 0 computes:

1. **Rolling IC** (Information Coefficient)
   - Mean IC
   - IC standard deviation
   - % positive months
   - Stability ratio = Mean IC / Std IC

2. **Regime-Conditional IC**
   - IC in low-vol regime
   - IC in high-vol regime
   - IC in crisis regime
   - Does IC flip sign across regimes?

3. **Crisis-Period IC**
   - IC during 2008 financial crisis
   - IC during 2020 COVID crash
   - Does signal survive extreme conditions?

4. **IC Decay Curve**
   - IC at 5-day, 10-day, 20-day, 60-day horizons
   - IC half-life
   - Forecast horizon alignment

5. **Long-Short Decile Sharpe**
   - Rank assets by signal into deciles
   - Long top decile, short bottom decile
   - Equal weight, no optimizer
   - Raw signal ranking power

## How to Run Task 0

### Step 1: Prepare Your Data

Edit `scripts/signal_reality_audit.py` and implement:

```python
def load_sample_data() -> pd.DataFrame:
    """Load your market data."""
    df = pd.read_csv('data/market/your_data.csv', parse_dates=['date'])
    return df
```

Expected format:
- `date`: datetime
- `asset_id`: str
- `price`: float
- `volume`: float
- [other features for signals]

### Step 2: Define Your Signals

Edit `scripts/signal_reality_audit.py` and implement:

```python
def compute_candidate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Compute your top 5 candidate signals."""
    
    # 1. Momentum
    df['signal_momentum_1m'] = df.groupby('asset_id')['price'].transform(
        lambda x: np.log(x / x.shift(21))
    )
    
    # 2. Valuation (requires fundamental data)
    df['signal_pe_ratio'] = df['price'] / df['earnings_per_share']
    
    # 3. Quality (requires fundamental data)
    df['signal_roe'] = df['net_income'] / df['shareholders_equity']
    
    # 4. Liquidity
    df['signal_illiquidity'] = ...
    
    # 5. Macro
    df['signal_market_beta'] = ...
    
    return df
```

### Step 3: Run the Audit

```bash
python scripts/signal_reality_audit.py
```

### Step 4: Review Results

The script generates:
- `reports/signal_audit/signal_audit_report.json` - Detailed metrics
- `reports/signal_audit/ic_time_series.png` - IC over time
- `reports/signal_audit/ic_by_regime.png` - IC by market regime
- `reports/signal_audit/ic_decay.png` - IC decay curves

### Step 5: Apply Decision Rules

The script automatically applies decision rules and prints:

```
DECISION: [STOP | PROCEED_MINIMAL | PROCEED_FULL]
REASON: [explanation]
```

## What to Do Based on Results

### If Decision = STOP

**DO NOT PROCEED TO TASK 1**

Your signals are too weak to justify building forecasting infrastructure. Instead:

1. **Redesign signals**
   - Find orthogonal data sources
   - Reduce prediction horizon
   - Switch to relative instead of absolute prediction

2. **Pivot to volatility forecasting**
   - Volatility is often easier to forecast than returns
   - Your options engine needs volatility forecasts anyway

3. **Focus on regime timing**
   - Instead of cross-sectional ranking
   - Regime detection is already strong in Northstar

4. **Build allocator research**
   - Instead of signal research
   - Improve portfolio construction with existing signals

### If Decision = PROCEED_MINIMAL

Proceed with **minimal ridge regression only**:
- Skip Bayesian hierarchical models (Task 17)
- Skip complex regime interactions
- Focus on simple, stable models
- Build monitoring infrastructure (Tasks 7-8)

### If Decision = PROCEED_FULL

Proceed with full probabilistic forecasting spine:
- All tasks 1-19 are justified
- Bayesian extensions make sense
- Regime modeling adds value
- Full monitoring and stress testing warranted

## The Mature Quant Approach

Professional funds follow this sequence:

1. ✓ Discover signal
2. ✓ Prove raw predictive power ← **YOU ARE HERE (Task 0)**
3. Add shrinkage (ridge regression)
4. Add regime conditioning
5. Add portfolio layer
6. Add monitoring

You are currently trying to build steps 3-6 before fully validating step 2.

## Key Insight

**Engineering complexity should scale with signal strength, not with architectural ambition.**

If your IC is 0.01, you don't need:
- Hierarchical Bayesian modeling
- Regime interaction features
- Tail probability calibration
- Crisis stress harnesses

You need better signals.

## Questions?

If Task 0 reveals weak signals, ask yourself:

1. **Do I have the right data?**
   - Fundamental data for valuation/quality signals?
   - High-frequency data for microstructure signals?
   - Alternative data sources?

2. **Am I forecasting the right thing?**
   - Returns are barely predictable
   - Volatility is more forecastable
   - Dispersion is even more forecastable

3. **Is my horizon aligned?**
   - 10-day horizon may be too short or too long
   - IC decay curve reveals optimal horizon

4. **Should I pivot strategy?**
   - From return forecasting to volatility forecasting
   - From cross-sectional to time-series
   - From directional to relative value

## Final Warning

If you skip Task 0 and proceed directly to Task 1, you risk:

- Building 2,000+ lines of forecasting infrastructure
- Spending weeks on implementation
- Achieving perfect engineering
- Discovering your signals have IC = 0.01
- Realizing 70% of the work was premature

**Don't build the cathedral until you test the soil.**

---

**Next Steps:**
1. Run Task 0
2. Review results honestly
3. Apply decision rules
4. If STOP: redesign signals
5. If PROCEED: continue to Task 1

**Remember:** A perfect forecasting spine on weak signals produces a perfectly engineered disappointment.
