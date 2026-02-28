# Valuation Engine v2 - Quick Start Guide

## What You Now Have

A comprehensive, institutional-grade valuation system with:

### 1. Forensic Accounting Layer ✅
- Detects earnings manipulation (Accrual Ratio, Beneish M-Score)
- Identifies accounting distortions (revenue recognition, R&D capitalization)
- Assesses earnings quality (cash conversion, stability)

### 2. Sector Intelligence ✅
- Maps companies to appropriate valuation frameworks
- Applies sector-specific metrics (Financials use P/B, Tech uses P/S, etc.)
- Handles cyclical industries with mid-cycle earnings

### 3. Buffett Module ✅
- Economic moat assessment (ROIC consistency, pricing power)
- Owner earnings calculation (true cash available to owners)
- Conservative DCF with margin of safety
- Management quality evaluation

### 4. Intrinsic Value Core ✅
- Two-stage DCF with conservative assumptions
- ROIC-based growth sustainability
- Quality-adjusted discount rates
- Sensitivity analysis

---

## Quick Start

### Run the Demo

```bash
python examples/valuation_engine_demo.py
```

This will show you:
1. Complete valuation of a tech company (SaaS)
2. Financial company valuation (Bank)
3. All the key metrics and assessments

### Basic Usage

```python
from src.valuation import (
    FinancialNormalizer,
    AdjustedMetricsCalculator,
    EarningsQualityAnalyzer,
    MoatScorer,
    OwnerEarningsCalculator,
    DCFEngine
)

# 1. Normalize financials (adjust for accounting differences)
normalizer = FinancialNormalizer()
adjusted = normalizer.normalize_financials(
    ticker='RELIANCE.NS',
    sector='Energy',
    revenue=500000,
    ebit=50000,
    # ... other parameters
)

# 2. Check earnings quality (forensic analysis)
forensic = EarningsQualityAnalyzer()
quality = forensic.analyze_earnings_quality(
    net_income=40000,
    operating_cash_flow=35000,
    total_assets=200000,
    # ... other parameters
)

# 3. Assess economic moat (Buffett principle)
moat_scorer = MoatScorer()
moat = moat_scorer.assess_moat(
    roic_history=roic_10y,
    gross_margin_history=margins_5y,
    # ... other parameters
)

# 4. Calculate intrinsic value (conservative DCF)
dcf = DCFEngine()
valuation = dcf.buffett_style_valuation(
    owner_earnings=owner_earnings,
    roic_10y_avg=0.18,
    revenue_growth_5y=0.12,
    shares_outstanding=1000000,
    current_price=2500,
    quality_score=75
)

print(f"Intrinsic Value: ₹{valuation.intrinsic_value_per_share:.2f}")
print(f"Margin of Safety: {valuation.margin_of_safety_pct:.1%}")
print(f"Grade: {valuation.valuation_grade}")
```

---

## Key Files Created

### Core Modules
- `src/valuation/core/normalized_financials.py` - Accounting adjustments
- `src/valuation/core/adjusted_metrics.py` - ROIC, FCF, Owner Earnings
- `src/valuation/core/sector_mapper.py` - Sector classification

### Forensic Layer
- `src/valuation/forensic/earnings_quality.py` - Earnings quality analysis
- `src/valuation/forensic/accounting_distortions.py` - Distortion detection

### Buffett Module
- `src/valuation/buffett_module/moat_score.py` - Economic moat assessment

### Intrinsic Value
- `src/valuation/intrinsic_value/owner_earnings.py` - Owner earnings calculator
- `src/valuation/intrinsic_value/dcf_engine.py` - Conservative DCF

### Documentation
- `docs/VALUATION_ENGINE_V2_GUIDE.md` - Complete guide (architecture, formulas, examples)
- `docs/VALUATION_RULES_REFERENCE.md` - All rules and thresholds
- `docs/VALUATION_QUICK_START.md` - This file

### Examples
- `examples/valuation_engine_demo.py` - Comprehensive demo

---

## Critical Rules to Remember

### 1. Sector Context is Mandatory
Never compare P/E across sectors. Use sector-appropriate metrics:
- **Financials**: P/B, ROE, NIM
- **Technology**: P/S, Rule of 40, FCF Margin
- **Cyclicals**: EV/EBIT_mid (mid-cycle earnings)
- **Consumer**: P/E, ROIC, Brand Power

### 2. Cash > Earnings
Priority order:
1. Owner Earnings (most reliable)
2. Free Cash Flow
3. Operating Cash Flow
4. Net Income (least reliable)

### 3. Margin of Safety is Non-Negotiable
- Required: 30%+ discount to intrinsic value
- Comfortable: 40%+ discount
- Never pay full intrinsic value

### 4. Quality First
Prefer: High ROIC + Low Growth
Over: Low ROIC + High Growth

### 5. Red Flags are Disqualifying
Any of these should significantly reduce score:
- Accruals > 10% of assets
- FCF Conversion < 0.7 persistently
- Multiple Beneish red flags
- Declining ROIC with increasing leverage

---

## Sector-Specific Quick Reference

### Financials (Banks, Insurance)
```python
# Use
P/B, ROE, NIM, GNPA/NNPA

# Ignore
EV/EBITDA, EV/EBIT (meaningless for banks)

# Fair Value
Fair_PB = (ROE - g) / (COE - g)
```

### Technology (SaaS, Software)
```python
# Use
P/S, Rule of 40, FCF Margin, Gross Margin

# Rule of 40
Rule_of_40 = Revenue_Growth_% + FCF_Margin_%
# Healthy: > 40

# Ignore
P/B (intangibles not captured)
```

### Cyclicals (Steel, Cement, Commodities)
```python
# Use
EV/EBIT_mid, P/B, ROIC

# Mid-Cycle Earnings
EBIT_mid = median(EBIT_10Y)

# Never use current earnings at peak/trough
```

### Consumer (FMCG)
```python
# Use
P/E, EV/EBITDA, ROIC, Brand Power

# Quality Indicators
- Gross Margin > 50%
- ROIC > 20% consistently
- Pricing Power (price increases without volume loss)
```

---

## Buffett's 8 Rules (Quick Checklist)

- [ ] **Circle of Competence**: Can you explain the business in 2 sentences?
- [ ] **Durable Moat**: ROIC > 15% for 10+ years?
- [ ] **Earnings Consistency**: Positive earnings for 10 years?
- [ ] **Low Leverage**: Debt/Equity < 1.0, Interest Coverage > 5×?
- [ ] **Owner Earnings**: Positive and growing?
- [ ] **Margin of Safety**: Price < 70% of intrinsic value?
- [ ] **Management Quality**: Good capital allocation?
- [ ] **Avoid Commodities**: Has pricing power?

---

## Forensic Red Flags (Quick Checklist)

- [ ] Receivables growing faster than revenue (DSRI > 1.03)
- [ ] High accruals (> 10% of assets)
- [ ] Poor cash conversion (FCF/NI < 0.7)
- [ ] Gross margin deterioration (GMI > 1.04)
- [ ] Frequent one-time items
- [ ] Rising inventory days
- [ ] Stretched payables
- [ ] R&D capitalization (tech companies)

---

## Integration with Northstar

### Composite Valuation Index

```python
Final_Value_Index = 0.40 × Sector_Adjusted_Valuation
                  + 0.30 × Buffett_Quality_Score
                  + 0.20 × Intrinsic_Value_MOS
                  - 0.10 × Forensic_Penalty
```

### Workflow

1. **Data Ingestion** → Load financial statements
2. **Normalization** → Adjust for accounting differences
3. **Forensic Analysis** → Check earnings quality
4. **Sector Mapping** → Classify and apply framework
5. **Metrics Calculation** → ROIC, Owner Earnings, FCF
6. **Moat Assessment** → Evaluate competitive advantages
7. **Intrinsic Value** → Conservative DCF
8. **Composite Score** → Weighted final index

---

## Next Steps

### 1. Test with Real Data
Run the demo with your actual company data:
```bash
python examples/valuation_engine_demo.py
```

### 2. Integrate with Existing System
Add valuation scores to your Northstar scoring model:
```python
from src.valuation import FinalValueIndexCalculator

# Calculate composite valuation index
value_index = calculator.calculate_final_index(
    sector_score=sector_valuation,
    buffett_score=moat_assessment,
    intrinsic_mos=dcf_margin_of_safety,
    forensic_penalty=earnings_quality_penalty
)
```

### 3. Build Sector Models
Complete the sector-specific models:
- `src/valuation/sector_models/financials_model.py`
- `src/valuation/sector_models/tech_model.py`
- `src/valuation/sector_models/cyclicals_model.py`
- `src/valuation/sector_models/defensives_model.py`

### 4. Add Remaining Modules
- `src/valuation/forensic/manipulation_flags.py`
- `src/valuation/intrinsic_value/terminal_value.py`
- `src/valuation/buffett_module/durability_score.py`
- `src/valuation/buffett_module/capital_allocator_score.py`
- `src/valuation/composite/valuation_score.py`
- `src/valuation/composite/buffett_score.py`
- `src/valuation/composite/final_value_index.py`

### 5. Backtest
Test the valuation engine on historical data:
- Does high MOS predict outperformance?
- Do forensic red flags predict underperformance?
- Does moat score correlate with long-term returns?

---

## Support & Resources

### Documentation
- **Complete Guide**: `docs/VALUATION_ENGINE_V2_GUIDE.md`
- **Rules Reference**: `docs/VALUATION_RULES_REFERENCE.md`
- **Quick Start**: `docs/VALUATION_QUICK_START.md` (this file)

### Examples
- **Demo Script**: `examples/valuation_engine_demo.py`

### Source Code
- **Core**: `src/valuation/core/`
- **Forensic**: `src/valuation/forensic/`
- **Buffett**: `src/valuation/buffett_module/`
- **Intrinsic Value**: `src/valuation/intrinsic_value/`

---

## Key Takeaways

### What Makes This Different

1. **Sector-Aware**: Different sectors need different metrics
2. **Forensic**: Detects accounting manipulation before valuation
3. **Conservative**: Buffett-style margin of safety required
4. **Quality-Focused**: Moat and durability matter more than growth
5. **Cash-Based**: Owner earnings > accounting earnings

### The Philosophy

> "Price is what you pay. Value is what you get." - Warren Buffett

This engine helps you:
- Understand what you're getting (intrinsic value)
- Ensure you're not overpaying (margin of safety)
- Avoid accounting tricks (forensic analysis)
- Focus on quality (moat assessment)

### Remember

- **Never** invest without understanding the business
- **Never** pay full intrinsic value
- **Always** check earnings quality
- **Always** require a moat
- **Always** use sector-appropriate metrics

---

## Quick Command Reference

```bash
# Run demo
python examples/valuation_engine_demo.py

# View documentation
cat docs/VALUATION_ENGINE_V2_GUIDE.md
cat docs/VALUATION_RULES_REFERENCE.md

# List modules
ls -la src/valuation/

# Check structure
tree src/valuation/
```

---

**You now have a complete, institutional-grade valuation engine that combines forensic accounting, sector intelligence, and Buffett's value investing principles.**

Start with the demo, then integrate with your existing Northstar system!
