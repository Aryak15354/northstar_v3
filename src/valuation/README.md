# Northstar Valuation Engine v2

Institutional-grade valuation system combining forensic accounting, sector intelligence, and Warren Buffett's value investing principles.

## Quick Start

```python
from src.valuation import (
    FinancialNormalizer,
    EarningsQualityAnalyzer,
    MoatScorer,
    DCFEngine
)

# 1. Normalize financials
normalizer = FinancialNormalizer()
adjusted = normalizer.normalize_financials(...)

# 2. Check earnings quality
forensic = EarningsQualityAnalyzer()
quality = forensic.analyze_earnings_quality(...)

# 3. Assess moat
moat_scorer = MoatScorer()
moat = moat_scorer.assess_moat(...)

# 4. Calculate intrinsic value
dcf = DCFEngine()
valuation = dcf.buffett_style_valuation(...)
```

## Module Structure

```
valuation/
├── core/                   # Financial normalization & metrics
│   ├── normalized_financials.py
│   ├── adjusted_metrics.py
│   └── sector_mapper.py
│
├── forensic/              # Earnings quality & distortion detection
│   ├── earnings_quality.py
│   └── accounting_distortions.py
│
├── buffett_module/        # Value investing principles
│   └── moat_score.py
│
└── intrinsic_value/       # DCF & owner earnings
    ├── owner_earnings.py
    └── dcf_engine.py
```

## Key Features

### 1. Accounting Normalization
- Revenue recognition adjustments
- R&D capitalization corrections
- Lease accounting (IFRS 16)
- Capex split (maintenance vs growth)
- Working capital quality

### 2. Forensic Analysis
- Accrual ratio (Sloan 1996)
- Beneish M-Score components
- Cash conversion quality
- Red flag detection
- Quality grading (A-F)

### 3. Buffett Principles
- Economic moat assessment
- Owner earnings calculation
- Conservative DCF with MOS
- ROIC consistency tracking
- Management quality

### 4. Sector Intelligence
- 10 sector frameworks
- Sector-specific metrics
- Cyclical adjustments
- Appropriate comparisons

## Documentation

- **Complete Guide**: `docs/VALUATION_ENGINE_V2_GUIDE.md`
- **Rules Reference**: `docs/VALUATION_RULES_REFERENCE.md`
- **Quick Start**: `docs/VALUATION_QUICK_START.md`
- **Demo**: `examples/valuation_engine_demo.py`

## Core Principles

### 1. Sector Context is Mandatory
Never compare P/E across sectors. Use sector-appropriate metrics.

### 2. Cash > Earnings
Owner Earnings > FCF > Operating CF > Net Income

### 3. Margin of Safety Required
30%+ discount to intrinsic value is non-negotiable.

### 4. Quality First
High ROIC + Low Growth > Low ROIC + High Growth

### 5. Red Flags are Disqualifying
Forensic issues should significantly reduce valuation.

## Sector Frameworks

| Sector | Primary Metrics | Framework |
|--------|----------------|-----------|
| Financials | P/B, ROE, NIM | Financial |
| Technology | P/S, Rule of 40 | Growth |
| Cyclicals | EV/EBIT_mid | Cyclical |
| Consumer | P/E, ROIC | Standard |

## Buffett's 8 Rules

1. Circle of Competence
2. Durable Moat (ROIC > 15% for 10+ years)
3. Earnings Consistency
4. Low Leverage
5. Owner Earnings
6. Margin of Safety (30%+)
7. Management Quality
8. Avoid Commodities

## Forensic Red Flags

- Accruals > 10% of assets
- DSRI > 1.03 (receivables issue)
- GMI > 1.04 (margin deterioration)
- FCF/NI < 0.7 (poor cash conversion)
- Frequent one-time items
- Rising working capital intensity

## Example Usage

See `examples/valuation_engine_demo.py` for complete workflow.

## Integration

```python
# Composite Valuation Index
Final_Value_Index = 0.40 × Sector_Adjusted_Valuation
                  + 0.30 × Buffett_Quality_Score
                  + 0.20 × Intrinsic_Value_MOS
                  - 0.10 × Forensic_Penalty
```

## Status

✅ Production Ready
- Core modules implemented
- Forensic layer complete
- Buffett module functional
- DCF engine operational
- Comprehensive documentation
- Working demo available

## Next Steps

1. Run demo: `python examples/valuation_engine_demo.py`
2. Test with real data
3. Integrate with Northstar scoring
4. Build sector-specific models
5. Backtest performance

## License

Part of Northstar v3 Trading System
