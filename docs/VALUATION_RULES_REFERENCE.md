# Valuation Engine v2 - Complete Rules Reference

## Part I: Institutional Robust Valuation Engine Rules

### A. Accounting Subtlety Rules (Non-Negotiable)

#### 1. Revenue Recognition Differences

**Rule**: Compare revenue growth only within same revenue model

**Sector-Specific Treatments**:
- **SaaS**: Subscription smoothing, check deferred revenue changes
- **Infrastructure**: Percentage-of-completion, milestone-based
- **Automotive**: Watch for dealer inventory stuffing
- **Pharma**: Milestone revenue spikes, USFDA approval timing
- **Banks**: Interest income timing, fee recognition

**Red Flags**:
- Receivables growing faster than revenue
- Abnormal deferred revenue decreases
- Revenue concentration in quarter-end

**Adjustment**:
```python
if receivables_days > sector_threshold * 1.5:
    adjusted_revenue = revenue * (sector_threshold / receivables_days)
```

#### 2. EBITDA Is Not Comparable Across Sectors

**Rule**: Prefer EBIT over EBITDA, track capitalized expenses separately

**Distortions by Sector**:
- **Telecom**: Excludes spectrum acquisition costs
- **Tech**: Capitalizes R&D (inflates EBITDA)
- **Manufacturing**: Capitalizes maintenance (should be expensed)
- **Infrastructure**: Includes government subsidies

**Adjustment**:
```python
# Normalize to operating margin
normalized_margin = EBIT / Revenue
# Compare within sector only
```

#### 3. Capitalized vs Expensed R&D

**Rule**: Reconstruct "Adjusted EBIT" by expensing capitalized R&D

**Problem**: Companies capitalizing R&D inflate earnings

**Adjustment**:
```python
Adjusted_EBIT = Reported_EBIT - Capitalized_RD + RD_Amortization
Adjusted_ROIC = (Adjusted_EBIT × (1 - Tax)) / (Invested_Capital + Capitalized_RD)
```

**Sectors Affected**: Technology, Pharmaceuticals, Automotive

#### 4. Depreciation Policy Differences

**Rule**: Compare depreciation as % of gross PP&E, flag outliers

**Normal Ranges by Sector**:
- Technology: 15-25%
- Industrials: 8-15%
- Utilities: 4-8%
- Consumer: 10-18%

**Red Flag**: Depreciation rate outside sector range by >30%

**Check**:
```python
depreciation_rate = Depreciation / Gross_PPE
if depreciation_rate < sector_low * 0.7:
    flag = "Conservative depreciation - earnings may be understated"
elif depreciation_rate > sector_high * 1.3:
    flag = "Aggressive depreciation - earnings may be overstated"
```

#### 5. Working Capital Manipulation

**Rule**: Compute cash conversion cycle, penalize rising WC intensity

**Red Flags**:
- Receivables growing faster than revenue
- Inventory days increasing
- Payables stretched artificially

**Metrics**:
```python
Receivables_Days = (Receivables / Revenue) × 365
Inventory_Days = (Inventory / COGS) × 365
Payables_Days = (Payables / COGS) × 365

Cash_Conversion_Cycle = Receivables_Days + Inventory_Days - Payables_Days

# Sector benchmarks
Tech: 30 days
Consumer: 45 days
Industrials: 60 days
Healthcare: 50 days
```

#### 6. Lease Accounting Differences (IFRS 16)

**Rule**: Include lease liabilities in enterprise value, use EBITDAR where relevant

**Impact**: Retail, airlines, restaurants look more levered post-IFRS 16

**Adjustment**:
```python
EV_Adjusted = Market_Cap + Debt + Lease_Liabilities - Cash

# For comparability
EBITDAR = EBITDA + Rent_Expense
EV / EBITDAR  # Use for asset-light businesses
```

#### 7. Financial Sector Is Completely Different

**Rule**: Separate financial valuation engine entirely

**For Banks**:
- **Ignore**: EV/EBITDA, EV/EBIT (meaningless)
- **Use**: P/B, ROE, NIM, Asset Quality
- **Focus**: Loan growth, credit quality, GNPA/NNPA trends

**Valuation**:
```python
Fair_PB = (ROE - g) / (Cost_of_Equity - g)

# Key metrics
NIM = (Interest_Income - Interest_Expense) / Earning_Assets
GNPA_Ratio = Gross_NPAs / Gross_Advances
ROE = Net_Income / Equity
```

#### 8. Cyclical Industries

**Rule**: Use mid-cycle earnings, avoid peak/trough multiples

**Sectors**: Steel, cement, commodities, chemicals, oil & gas

**Approach**:
```python
# Use 10-year history
EBIT_mid = median(EBIT_10Y)  # or trimmed mean

# Valuation
EV / EBIT_mid  # Not current EBIT

# Through-cycle margins
Margin_mid = median(EBIT_Margin_10Y)
```

**Warning**: Earnings peak = dangerous time to buy

#### 9. One-Off Items

**Rule**: Strip exceptional items, use adjusted net income, track 5-year normalized earnings

**Common One-Offs**:
- Restructuring charges
- Impairment charges
- Gain/loss on asset sales
- Litigation settlements
- Tax adjustments
- Forex gains/losses (if non-operating)

**Adjustment**:
```python
Adjusted_NI = Reported_NI - One_Time_Items
Normalized_NI = mean(Adjusted_NI_5Y)
```

#### 10. Free Cash Flow Quality

**Rule**: FCF must be positive over cycle, avoid earnings without cash

**Metrics**:
```python
FCF = Operating_Cash_Flow - Capex
FCF_Conversion = FCF / Net_Income

# Quality thresholds
Excellent: FCF_Conversion > 1.0
Good: FCF_Conversion > 0.8
Acceptable: FCF_Conversion > 0.7
Poor: FCF_Conversion < 0.7
Red Flag: FCF_Conversion < 0.5 persistently
```

**Track**: 5-year cumulative FCF vs cumulative earnings

---

### B. Sector-Specific Valuation Frameworks

#### Financials Template

**Primary Metrics**:
- P/B (Price to Book)
- ROE vs Cost of Equity spread
- NIM (Net Interest Margin) stability
- Loan growth vs credit cost
- GNPA/NNPA trends

**Scoring**:
```python
Score = 0.30 × ROE_Stability
      + 0.20 × NIM_Stability
      + 0.20 × GNPA_Trend
      + 0.30 × PB_Discount_vs_Fair
```

**Fair Value**:
```python
Fair_PB = (ROE - g) / (COE - g)
where:
  ROE = sustainable return on equity
  g = long-term growth rate
  COE = cost of equity
```

#### Technology / SaaS Template

**Primary Metrics**:
- Revenue CAGR
- FCF Margin
- R&D Efficiency
- Rule of 40
- Gross Margin

**Scoring**:
```python
Score = 0.25 × Revenue_CAGR
      + 0.25 × FCF_Margin
      + 0.20 × RD_Efficiency
      + 0.20 × Rule_of_40
      + 0.10 × Dilution_Risk

Rule_of_40 = Revenue_Growth_% + FCF_Margin_%
# Healthy: > 40
```

**Red Flags**:
- Gross margin declining
- R&D > 30% of revenue without path to profitability
- High dilution (>5% annually)

#### FMCG / Consumer Template

**Primary Metrics**:
- Gross margin stability
- ROIC 10-year average
- Brand power (pricing power proxy)
- Cash conversion
- Low capex intensity

**Scoring**:
```python
Score = 0.30 × Gross_Margin_Stability
      + 0.25 × ROIC_10Y
      + 0.20 × Pricing_Power
      + 0.15 × Cash_Conversion
      + 0.10 × Capex_Intensity_Inverse
```

**Quality Indicators**:
- Gross margin > 50%
- ROIC > 20% consistently
- Capex < 3% of revenue
- Pricing power (price increases without volume loss)

#### Cyclicals Template (Industrials, Materials, Energy)

**Primary Metrics**:
- Mid-cycle margin
- Debt ratio
- Capacity utilization
- EV / EBIT_mid
- Order book visibility

**Scoring**:
```python
Score = 0.30 × Mid_Cycle_Margin
      + 0.25 × Debt_Safety
      + 0.20 × Capacity_Utilization
      + 0.15 × Order_Book_Visibility
      + 0.10 × Cost_Position
```

**Valuation**:
```python
# Never use current earnings at peak/trough
EBIT_mid = median(EBIT_10Y)
Fair_EV = EBIT_mid × Sector_Multiple
```

---

## Part II: Warren Buffett Module Rules

### Buffett Rule 1: Circle of Competence

**Principle**: Avoid businesses you don't understand

**Implementation**:
```python
# Flag complex businesses
red_flags = [
    'Complex derivatives exposure',
    'Crypto/blockchain primary business',
    'Highly leveraged financial engineering',
    'Business model requires constant innovation',
    'Technology changes rapidly'
]
```

**Test**: Can you explain the business model in 2 sentences?

### Buffett Rule 2: Durable Moat

**Principle**: Sustainable competitive advantage

**Quantifiable Proxies**:
```python
Moat_Score = 0.40 × ROIC_Consistency
           + 0.20 × Pricing_Power
           + 0.15 × Switching_Costs
           + 0.15 × Network_Effects
           + 0.10 × Cost_Advantage
```

**ROIC Consistency**:
- Wide Moat: ROIC > 15% for 10+ years
- Narrow Moat: ROIC > 12% for 7+ years
- No Moat: Below thresholds

**Pricing Power Indicators**:
- Stable/expanding gross margins
- Revenue growth without margin compression
- Price increases without volume loss

### Buffett Rule 3: Earnings Consistency

**Principle**: Predictable, stable earnings

**Requirements**:
- Positive earnings for 10 consecutive years
- No earnings volatility spikes (CV < 0.3)
- No accounting restatements
- No frequent one-time items

**Metric**:
```python
Earnings_Volatility = std(Earnings_10Y) / mean(Earnings_10Y)

Excellent: CV < 0.15
Good: CV < 0.25
Acceptable: CV < 0.35
Poor: CV > 0.35
```

### Buffett Rule 4: Low Leverage

**Principle**: Conservative capital structure

**Thresholds**:
```python
# Debt ratios
Debt_to_Equity < 0.5  # Excellent
Debt_to_Equity < 1.0  # Good
Debt_to_Equity < 2.0  # Acceptable (sector-dependent)

# Interest coverage
Interest_Coverage = EBIT / Interest_Expense
Required: > 5×
Comfortable: > 10×
```

**Exceptions**: Utilities, regulated industries (higher leverage acceptable)

### Buffett Rule 5: Owner Earnings

**Principle**: Use owner earnings instead of EPS

**Formula**:
```python
Owner_Earnings = Net_Income
               + Depreciation
               + Amortization
               - Maintenance_Capex
               - Working_Capital_Increase
               - One_Time_Items
```

**Maintenance Capex Estimation**:
```python
# Sector-specific ratios
Utilities: Maintenance = 1.0 × Depreciation
Industrials: Maintenance = 0.9 × Depreciation
Technology: Maintenance = 0.6 × Depreciation
Consumer: Maintenance = 0.75 × Depreciation
```

### Buffett Rule 6: Margin of Safety

**Principle**: Never pay full intrinsic value

**Requirements**:
```python
Margin_of_Safety = (Intrinsic_Value - Price) / Intrinsic_Value

Required: MOS > 30%
Comfortable: MOS > 40%
Excellent: MOS > 50%
```

**Intrinsic Value Calculation**:
```python
# Two-stage DCF
Stage1_PV = Σ(Owner_Earnings_t / (1 + r)^t)  # Years 1-10
Terminal_Value = Terminal_OE × (1 + g) / (r - g)
Terminal_PV = Terminal_Value / (1 + r)^10

Intrinsic_Value = Stage1_PV + Terminal_PV
```

**Conservative Assumptions**:
- Growth: min(Historical × 0.7, ROIC × Reinvestment, GDP Cap)
- Terminal Growth: 3-5% (based on ROIC)
- Discount Rate: 10-13% (quality-adjusted)

### Buffett Rule 7: Management Quality

**Principle**: Capital allocation discipline

**Quantitative Proxies**:
```python
# Good capital allocation
- Buybacks at low valuations (P/B < 1.5)
- Dividends sustainable (payout < 60%)
- No frequent equity dilution
- No empire building (avoid bad acquisitions)
- ROIC on reinvested capital > WACC

# Red flags
- Buybacks at peak valuations
- Debt-funded dividends
- Frequent equity raises
- Serial acquirers with declining ROIC
```

### Buffett Rule 8: Avoid Commodity Businesses

**Principle**: No pricing power = no moat

**Characteristics to Avoid**:
- Low pricing power
- Cyclical margin swings
- High capital intensity
- Undifferentiated products
- Compete on price only

**Flag Commodities**:
```python
commodity_indicators = [
    'Gross margin < 20%',
    'Margin volatility > 30%',
    'Capex > 15% of revenue',
    'ROIC < 10%',
    'No brand differentiation'
]
```

---

## Part III: Forensic Accounting Penalty Layer

### 1. Accrual Ratio (Sloan 1996)

**Formula**:
```python
Accruals = (Net_Income - Operating_Cash_Flow) / Total_Assets
```

**Thresholds**:
- Excellent: < 0.05
- Good: < 0.08
- Acceptable: < 0.10
- Red Flag: > 0.10
- Severe: > 0.15

**Penalty**:
```python
if abs(Accruals) > 0.10:
    Penalty += 10 points
if abs(Accruals) > 0.15:
    Penalty += 20 points
```

### 2. Beneish M-Score Components

**DSRI (Days Sales in Receivables Index)**:
```python
DSRI = (Receivables_t / Sales_t) / (Receivables_t-1 / Sales_t-1)

Red Flag: DSRI > 1.03
```

**GMI (Gross Margin Index)**:
```python
GMI = Gross_Margin_t-1 / Gross_Margin_t

Red Flag: GMI > 1.04  # Margin deterioration
```

**AQI (Asset Quality Index)**:
```python
AQI = Asset_Quality_t / Asset_Quality_t-1
where Asset_Quality = (Current_Assets + PPE) / Total_Assets

Red Flag: AQI > 1.04
```

**SGI (Sales Growth Index)**:
```python
SGI = Sales_t / Sales_t-1

Red Flag: SGI > 1.50  # Aggressive growth
```

### 3. Earnings Stability Score

**Coefficient of Variation**:
```python
CV = std(Earnings_10Y) / mean(Earnings_10Y)

Excellent: CV < 0.15
Good: CV < 0.25
Acceptable: CV < 0.35
Poor: CV > 0.50
```

### 4. Capital Allocation Red Flags

**Dilution**:
```python
Annual_Dilution = (Shares_t - Shares_t-1) / Shares_t-1

Red Flag: > 5% annually
Severe: > 10% annually
```

**Buyback Timing**:
```python
if Buybacks_at_High_Valuation:  # P/B > 3 or P/E > 25
    Red_Flag = "Poor capital allocation"
```

**Debt-Funded Dividends**:
```python
if Dividends > FCF and Debt_Increasing:
    Red_Flag = "Unsustainable dividends"
```

### 5. Forensic Penalty Score

**Formula**:
```python
Forensic_Penalty = w1 × Accrual_Risk
                 + w2 × Manipulation_Risk
                 + w3 × Stability_Risk
                 + w4 × Capital_Allocation_Risk

where:
w1 = 0.35  # Accruals most important
w2 = 0.30  # Beneish components
w3 = 0.20  # Earnings stability
w4 = 0.15  # Management quality
```

**Application**:
```python
Adjusted_Valuation_Score = Raw_Score × (1 - Forensic_Penalty)
```

---

## Part IV: Final Composite Index

### Formula

```python
Final_Value_Index = 0.40 × Sector_Adjusted_Valuation_Score
                  + 0.30 × Buffett_Quality_Score
                  + 0.20 × Intrinsic_Value_MOS
                  - 0.10 × Forensic_Penalty
```

### Component Breakdown

**Sector-Adjusted Valuation (40%)**:
- Uses appropriate metrics per sector
- Normalized within sector
- Accounts for cyclicality

**Buffett Quality Score (30%)**:
- Moat assessment (40%)
- Durability (30%)
- Capital allocation (30%)

**Intrinsic Value MOS (20%)**:
- From conservative DCF
- Requires 30%+ margin of safety
- Quality-adjusted discount rate

**Forensic Penalty (10%)**:
- Earnings quality issues
- Accounting red flags
- Management concerns

### Interpretation

**Score Ranges**:
- 80-100: Excellent value + quality
- 65-80: Good value + quality
- 50-65: Fair value
- 35-50: Fully valued
- 0-35: Overvalued or poor quality

**Action Thresholds**:
- > 75: Strong buy
- 60-75: Buy
- 45-60: Hold
- 30-45: Reduce
- < 30: Sell

---

## Part V: Critical Implementation Notes

### 1. Sector Context is Mandatory

Never compare across sectors without adjustment. A P/E of 15 means different things for:
- Banks (expensive)
- Tech (cheap)
- Utilities (fair)

### 2. Cash > Earnings

Always prioritize:
1. Owner Earnings
2. Free Cash Flow
3. Operating Cash Flow
4. Net Income (least reliable)

### 3. Conservative Bias

When uncertain:
- Use lower growth rate
- Use higher discount rate
- Require higher margin of safety
- Assume mid-cycle earnings for cyclicals

### 4. Quality First

Prefer:
- High ROIC + Low Growth
- Over Low ROIC + High Growth

### 5. Red Flags are Disqualifying

Any of these should significantly reduce score:
- Persistent negative FCF
- Accruals > 15%
- Multiple Beneish red flags
- Declining ROIC with increasing leverage
- Frequent restatements

### 6. Moat is Everything

Without a moat:
- Growth is temporary
- Returns revert to cost of capital
- Valuation premium unjustified

### 7. Margin of Safety is Non-Negotiable

Never invest without 30%+ MOS, regardless of quality.

---

## Quick Reference Checklist

### Before Valuing Any Company:

- [ ] Understand the business model (2-sentence test)
- [ ] Identify sector and appropriate framework
- [ ] Check for accounting red flags
- [ ] Verify earnings quality (accruals, cash conversion)
- [ ] Assess moat (ROIC history)
- [ ] Calculate owner earnings
- [ ] Run conservative DCF
- [ ] Verify 30%+ margin of safety
- [ ] Check management quality
- [ ] Review forensic penalty
- [ ] Calculate composite score

### Red Flags Checklist:

- [ ] Receivables > Revenue growth
- [ ] Accruals > 10%
- [ ] FCF Conversion < 0.7
- [ ] ROIC declining
- [ ] Leverage increasing
- [ ] Frequent one-time items
- [ ] Gross margin declining
- [ ] Complex business model
- [ ] Commodity characteristics
- [ ] Poor capital allocation

---

This completes the comprehensive rules reference for the Valuation Engine v2.
