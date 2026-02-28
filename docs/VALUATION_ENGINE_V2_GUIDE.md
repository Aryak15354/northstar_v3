# Northstar Valuation Engine v2
## Institutional-Grade Valuation with Forensic Accounting & Buffett Principles

### Overview

The Valuation Engine v2 is a comprehensive, sector-aware valuation system that combines:

1. **Forensic Accounting Layer** - Detects earnings manipulation and accounting distortions
2. **Sector Intelligence** - Applies sector-specific valuation frameworks
3. **Buffett Module** - Implements Warren Buffett's value investing principles
4. **Intrinsic Value Core** - Conservative DCF with margin of safety

---

## Architecture

```
valuation_engine_v2/
│
├── core/                          # Financial normalization
│   ├── normalized_financials.py  # Accounting adjustments
│   ├── adjusted_metrics.py       # ROIC, FCF, Owner Earnings
│   └── sector_mapper.py           # Sector classification
│
├── forensic/                      # Earnings quality analysis
│   ├── earnings_quality.py       # Accrual ratio, cash conversion
│   ├── accounting_distortions.py # Revenue recognition, R&D
│   └── manipulation_flags.py     # Beneish M-Score, red flags
│
├── sector_models/                 # Sector-specific valuation
│   ├── financials_model.py       # P/B, ROE, NIM
│   ├── tech_model.py              # P/S, Rule of 40
│   ├── cyclicals_model.py         # Mid-cycle earnings
│   └── defensives_model.py        # Dividend yield, stability
│
├── intrinsic_value/               # DCF and intrinsic value
│   ├── owner_earnings.py          # Buffett's owner earnings
│   ├── dcf_engine.py              # Two-stage DCF
│   └── terminal_value.py          # Terminal value calculation
│
├── buffett_module/                # Value investing principles
│   ├── moat_score.py              # Economic moat assessment
│   ├── durability_score.py        # Business durability
│   └── capital_allocator_score.py # Management quality
│
└── composite/                     # Final scoring
    ├── valuation_score.py         # Sector-adjusted valuation
    ├── buffett_score.py           # Buffett quality score
    └── final_value_index.py       # Composite index
```

---

## Key Concepts

### 1. Accounting Normalization

Different sectors use different accounting treatments. The engine adjusts for:

#### Revenue Recognition
- **SaaS**: Deferred revenue smoothing
- **Construction**: Percentage-of-completion
- **Auto**: Dealer inventory stuffing
- **Pharma**: Milestone revenue spikes

#### R&D Treatment
```python
# Companies capitalizing R&D inflate earnings
Adjusted EBIT = Reported EBIT - Capitalized R&D + R&D Amortization
```

#### Lease Accounting (IFRS 16)
```python
# Include lease liabilities in enterprise value
EV = Market Cap + Debt + Lease Liabilities - Cash
```

#### Capex Split
```python
# Separate maintenance vs growth capex
Maintenance Capex ≈ Depreciation × Sector Ratio
Growth Capex = Total Capex - Maintenance Capex
```

### 2. Adjusted Metrics

#### ROIC (Return on Invested Capital)
```python
ROIC = NOPAT / Invested Capital

where:
NOPAT = Adjusted EBIT × (1 - Tax Rate)
Invested Capital = Equity + Debt - Excess Cash + Capitalized R&D
```

#### Owner Earnings (Buffett)
```python
Owner Earnings = Net Income
               + Depreciation & Amortization
               - Maintenance Capex
               - Working Capital Increase
               - One-Time Items
```

#### FCF Conversion
```python
FCF = Operating Cash Flow - Capex
FCF Conversion = FCF / Net Income

# Quality threshold: > 0.7
```

### 3. Forensic Accounting

#### Accrual Ratio (Sloan 1996)
```python
Accruals = (Net Income - Operating Cash Flow) / Total Assets

# Red flag: > 0.10
```

#### Beneish M-Score Components
- **DSRI**: Days Sales in Receivables Index (> 1.03 = red flag)
- **GMI**: Gross Margin Index (> 1.04 = deterioration)
- **AQI**: Asset Quality Index (> 1.04 = concern)
- **SGI**: Sales Growth Index (> 1.50 = aggressive)

#### Earnings Quality Score
```
Quality Score = 0.35 × Accrual Quality
              + 0.35 × Cash Conversion
              + 0.30 × Earnings Stability
              - Red Flag Penalty

Grades: A (80+), B (65+), C (50+), D (35+), F (<35)
```

### 4. Sector-Specific Valuation

#### Financials
```python
Primary Metrics: P/B, ROE, NIM, GNPA
Ignore: EV/EBITDA (not applicable)

Fair P/B = (ROE - g) / (Cost of Equity - g)
```

#### Technology
```python
Primary Metrics: P/S, EV/Revenue, Rule of 40, FCF Margin
Rule of 40 = Revenue Growth % + FCF Margin %

# Healthy: > 40
```

#### Cyclicals (Materials, Industrials, Energy)
```python
Use Mid-Cycle Earnings:
EBIT_mid = Median(EBIT_10Y)

Valuation: EV / EBIT_mid
```

#### Consumer (FMCG)
```python
Focus on:
- Brand power (pricing power)
- ROIC consistency (> 20%)
- Cash conversion
- Gross margin stability
```

### 5. Buffett Module

#### Economic Moat Assessment
```python
Moat Score = 0.40 × ROIC Consistency
           + 0.20 × Pricing Power
           + 0.15 × Switching Costs
           + 0.15 × Network Effects
           + 0.10 × Cost Advantage

Moat Width:
- Wide: Score ≥ 75, ROIC > 15% for 10+ years
- Narrow: Score ≥ 55, ROIC > 12% for 5+ years
- None: Below thresholds
```

#### Buffett's Rules

1. **Circle of Competence**: Avoid complex businesses
2. **Durable Moat**: ROIC > 15% for 10 years
3. **Earnings Consistency**: Positive earnings 10 years
4. **Low Leverage**: Debt/Equity reasonable, Interest Coverage > 5×
5. **Owner Earnings**: Use instead of EPS
6. **Margin of Safety**: Price < 70% of intrinsic value
7. **Management Quality**: Capital allocation discipline
8. **Avoid Commodities**: Low pricing power

### 6. Intrinsic Value (DCF)

#### Two-Stage DCF
```python
# Stage 1: Explicit forecast (5-10 years)
PV_Stage1 = Σ(Owner Earnings_t / (1 + r)^t)

# Stage 2: Terminal value
Terminal Value = Terminal CF × (1 + g) / (r - g)
PV_Terminal = Terminal Value / (1 + r)^n

Intrinsic Value = PV_Stage1 + PV_Terminal
```

#### Conservative Growth Assumptions
```python
Sustainable Growth = min(
    Historical Growth × 0.7,
    ROIC × Reinvestment Rate,
    GDP Growth Cap (6%),
    Industry Growth × 1.5
)

Terminal Growth:
- High ROIC (>20%): 5%
- Medium ROIC (15-20%): 4%
- Low ROIC (<15%): 3%
```

#### Margin of Safety
```python
MOS = (Intrinsic Value - Current Price) / Intrinsic Value

Required MOS: > 30%

Valuation Grades:
- A: MOS ≥ 40% (Excellent value)
- B: MOS ≥ 30% (Good value)
- C: MOS ≥ 20% (Fair value)
- D: MOS ≥ 0% (Fully valued)
- F: MOS < 0% (Overvalued)
```

---

## Usage Examples

### Example 1: Basic Valuation

```python
from src.valuation import (
    FinancialNormalizer,
    AdjustedMetricsCalculator,
    OwnerEarningsCalculator,
    DCFEngine
)

# 1. Normalize financials
normalizer = FinancialNormalizer()
adjusted = normalizer.normalize_financials(
    ticker='RELIANCE.NS',
    sector='Energy',
    revenue=500000,
    ebit=50000,
    # ... other parameters
)

# 2. Calculate adjusted metrics
metrics_calc = AdjustedMetricsCalculator()
metrics = metrics_calc.calculate_all_metrics(
    revenue=adjusted.adjusted_revenue,
    adjusted_ebit=adjusted.adjusted_ebit,
    # ... other parameters
)

# 3. Calculate owner earnings
oe_calc = OwnerEarningsCalculator()
owner_earnings = oe_calc.calculate_owner_earnings(
    net_income=40000,
    depreciation=10000,
    amortization=2000,
    total_capex=15000,
    # ... other parameters
)

# 4. DCF valuation
dcf = DCFEngine()
valuation = dcf.buffett_style_valuation(
    owner_earnings=owner_earnings.owner_earnings,
    roic_10y_avg=0.18,
    revenue_growth_5y=0.12,
    shares_outstanding=1000000,
    current_price=2500,
    quality_score=75
)

print(f"Intrinsic Value: ₹{valuation.intrinsic_value_per_share:.2f}")
print(f"Current Price: ₹{valuation.current_price:.2f}")
print(f"Margin of Safety: {valuation.margin_of_safety_pct:.1%}")
print(f"Grade: {valuation.valuation_grade}")
```

### Example 2: Forensic Analysis

```python
from src.valuation.forensic import EarningsQualityAnalyzer

analyzer = EarningsQualityAnalyzer()

quality = analyzer.analyze_earnings_quality(
    net_income=40000,
    operating_cash_flow=35000,
    total_assets=200000,
    receivables=30000,
    revenue=500000,
    # ... other parameters
)

print(f"Quality Score: {quality.overall_score:.1f}")
print(f"Grade: {quality.quality_grade}")
print(f"Red Flags: {len(quality.red_flags)}")
for flag in quality.red_flags:
    print(f"  - {flag}")
```

### Example 3: Moat Assessment

```python
from src.valuation.buffett_module import MoatScorer
import pandas as pd

moat_scorer = MoatScorer()

# Historical ROIC data
roic_history = pd.Series([0.18, 0.19, 0.17, 0.20, 0.19, 0.18, 0.21, 0.20, 0.19, 0.22])

moat = moat_scorer.assess_moat(
    roic_history=roic_history,
    gross_margin_history=pd.Series([0.65, 0.66, 0.67, 0.66, 0.68]),
    revenue_growth_history=pd.Series([0.15, 0.18, 0.16, 0.17, 0.19]),
    recurring_revenue_pct=0.80,
    customer_retention_rate=0.95,
)

print(f"Moat Width: {moat.moat_width}")
print(f"Moat Score: {moat.overall_score:.1f}")
print(f"Sources: {', '.join(moat.moat_sources)}")
```

---

## Integration with Northstar

### Composite Valuation Index

```python
Final Value Index = 0.4 × Sector-Adjusted Valuation Score
                  + 0.3 × Buffett Quality Score
                  + 0.2 × Intrinsic Value MOS
                  - 0.1 × Forensic Penalty

where:
- Sector-Adjusted Score: Uses appropriate metrics per sector
- Buffett Score: Moat + Durability + Capital Allocation
- Intrinsic MOS: Margin of safety from DCF
- Forensic Penalty: Earnings quality red flags
```

### Workflow

1. **Data Ingestion**: Load financial statements
2. **Normalization**: Adjust for accounting differences
3. **Forensic Analysis**: Check earnings quality
4. **Sector Mapping**: Classify and apply framework
5. **Metrics Calculation**: ROIC, Owner Earnings, FCF
6. **Moat Assessment**: Evaluate competitive advantages
7. **Intrinsic Value**: Conservative DCF
8. **Composite Score**: Weighted final index

---

## Sector-Specific Rules

### Financials
- **Use**: P/B, ROE, NIM, Asset Quality
- **Ignore**: EV/EBITDA, EV/EBIT
- **Focus**: Credit quality, loan growth, NIM stability

### Technology
- **Use**: P/S, Rule of 40, FCF Margin
- **Ignore**: P/B (intangibles)
- **Focus**: Revenue growth, gross margin, R&D efficiency

### Cyclicals
- **Use**: EV/EBIT_mid, P/B, ROIC
- **Ignore**: Current earnings (peak/trough)
- **Focus**: Mid-cycle margins, debt levels, capacity

### Consumer (FMCG)
- **Use**: P/E, EV/EBITDA, ROIC
- **Ignore**: None
- **Focus**: Brand power, pricing power, cash conversion

---

## Red Flags to Watch

### Accounting Red Flags
1. Receivables growing faster than revenue (DSRI > 1.03)
2. Gross margin deterioration (GMI > 1.04)
3. High accruals (> 10% of assets)
4. Poor cash conversion (FCF/NI < 0.7)
5. Frequent one-time items
6. Aggressive depreciation policies

### Business Red Flags
1. ROIC declining over time
2. Increasing leverage without ROIC improvement
3. Negative owner earnings
4. High customer concentration
5. Commodity business (no pricing power)
6. Complex business model (outside circle of competence)

---

## Best Practices

### 1. Always Use Sector Context
Don't compare P/E of a bank with a tech company. Use sector-appropriate metrics.

### 2. Prioritize Cash Over Earnings
Owner earnings and FCF are more reliable than accounting earnings.

### 3. Demand Margin of Safety
Never pay full intrinsic value. Require 30%+ discount.

### 4. Focus on Quality
High ROIC, low debt, consistent earnings > high growth.

### 5. Be Conservative
When in doubt, use lower growth, higher discount rate.

### 6. Check Forensics
Always run earnings quality analysis before valuation.

### 7. Understand the Business
If you can't explain the business model simply, don't invest.

---

## Performance Metrics

The valuation engine should be evaluated on:

1. **Accuracy**: Intrinsic value vs realized returns (3-5 years)
2. **Calibration**: MOS grades vs actual outcomes
3. **Red Flag Detection**: Catching accounting issues early
4. **Sector Appropriateness**: Using right metrics per sector

---

## Future Enhancements

1. **Bayesian Valuation**: Uncertainty bands around intrinsic value
2. **Stochastic DCF**: Monte Carlo simulation of growth/ROIC
3. **Regime Conditioning**: Adjust valuations for macro regime
4. **Value-Momentum Interaction**: Combine with technical signals
5. **Real Options**: Value of growth options, flexibility

---

## References

### Academic
- Sloan (1996): Accrual Ratio and Future Returns
- Beneish (1999): M-Score for Earnings Manipulation
- Piotroski (2000): F-Score for Value Investing

### Practitioner
- Warren Buffett: Berkshire Hathaway Letters
- Bruce Greenwald: Value Investing
- Aswath Damodaran: Valuation

---

## Support

For questions or issues:
- Documentation: `docs/VALUATION_ENGINE_V2_GUIDE.md`
- Examples: `examples/valuation_examples.py`
- Tests: `tests/test_valuation_*.py`
