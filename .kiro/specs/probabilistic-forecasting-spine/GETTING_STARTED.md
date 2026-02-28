# Getting Started: Probabilistic Forecasting Spine

## The One Thing You Must Do First

**Run Task 0: Signal Reality Audit**

Everything else is conditional on Task 0 passing validation.

## Quick Start (5 minutes)

```bash
# 1. Read the Task 0 guide
cat .kiro/specs/probabilistic-forecasting-spine/TASK_0_README.md

# 2. Edit the audit script to load your data
vim scripts/signal_reality_audit.py
# Implement: load_sample_data() and compute_candidate_signals()

# 3. Run the audit
python scripts/signal_reality_audit.py

# 4. Review results
cat reports/signal_audit/signal_audit_report.json
open reports/signal_audit/ic_time_series.png
```

## What Happens Next?

### Scenario 1: Task 0 Says STOP

**DO NOT PROCEED TO TASK 1**

Your signals are too weak. Instead:

1. **Redesign signals**
   - Review signal construction logic
   - Add orthogonal data sources
   - Test different feature engineering approaches

2. **Pivot to volatility forecasting**
   - Volatility is easier to forecast than returns
   - Your options engine needs it anyway
   - IC for volatility is typically 2-3x higher

3. **Focus on regime timing**
   - Your regime detection is already strong
   - Time regime transitions instead of ranking stocks

4. **Improve allocator**
   - Better portfolio construction with existing signals
   - Risk management improvements
   - Position sizing optimization

### Scenario 2: Task 0 Says PROCEED_MINIMAL

Build minimal ridge regression only:

**Tasks to complete:**
- Task 1: Project structure
- Task 2: Signal layer (simplified)
- Task 3: Feature engine (basic)
- Task 5.1: Ridge regression only
- Task 7: Calibration monitor
- Task 9: Integration layer

**Tasks to skip:**
- Task 17: Bayesian hierarchical (overkill for IC < 0.025)
- Complex regime interactions
- Tail probability modeling (unless needed for risk)

### Scenario 3: Task 0 Says PROCEED_FULL

Proceed with full probabilistic forecasting spine:

**Complete all tasks 1-19 in order:**
- Follow [tasks.md](./tasks.md)
- Each task builds on previous work
- Checkpoints validate before proceeding
- Property-based tests ensure correctness

## The Decision Tree

```
Start
  │
  ├─ Run Task 0
  │
  ├─ Mean IC < 0.015?
  │   └─ YES → STOP, redesign signals
  │   └─ NO → Continue
  │
  ├─ Stability ratio < 0.5?
  │   └─ YES → STOP, signals too unstable
  │   └─ NO → Continue
  │
  ├─ Crisis IC flips sign?
  │   ├─ YES & IC < 0.03 → STOP
  │   ├─ YES & IC > 0.03 → Add regime modeling
  │   └─ NO → Continue
  │
  ├─ Mean IC < 0.025?
  │   └─ YES → PROCEED_MINIMAL (ridge only)
  │   └─ NO → PROCEED_FULL (all tasks)
```

## Common Mistakes to Avoid

### ❌ Mistake 1: Skipping Task 0

"I'll just build the infrastructure and test signals later."

**Result:** Weeks of engineering on weak signals. Perfect architecture, zero alpha.

### ❌ Mistake 2: Ignoring STOP Decision

"My IC is 0.01 but I'll build Bayesian hierarchical models anyway."

**Result:** Complexity amplifies noise. Overfitting. Unstable forecasts.

### ❌ Mistake 3: Building Everything at Once

"I'll implement all 19 tasks in parallel."

**Result:** No validation checkpoints. Hard to debug. Wasted effort.

### ❌ Mistake 4: Trusting In-Sample IC

"My in-sample IC is 0.08!"

**Result:** Out-of-sample IC is 0.01. Look-ahead bias. Overfitting.

## The Right Way

### ✓ Step 1: Validate Signals (Task 0)

- Rolling walk-forward IC
- No look-ahead bias
- Crisis period validation
- Honest out-of-sample metrics

### ✓ Step 2: Apply Decision Rules

- If STOP → redesign signals
- If PROCEED_MINIMAL → build simple models
- If PROCEED_FULL → build full spine

### ✓ Step 3: Incremental Implementation

- One task at a time
- Validate at checkpoints
- Property-based tests
- Integration tests

### ✓ Step 4: Monitor in Production

- Track IC drift
- Detect signal decay
- Calibration monitoring
- Crisis stress testing

## Key Insights

### Insight 1: Signal Strength Determines Complexity

| IC Range | Justified Complexity |
|----------|---------------------|
| < 0.015 | None (redesign signals) |
| 0.015-0.025 | Simple ridge regression |
| 0.025-0.040 | Ridge + regime awareness |
| > 0.040 | Full Bayesian hierarchy |

### Insight 2: Volatility > Returns

Volatility forecasting typically has:
- 2-3x higher IC than return forecasting
- More stable across regimes
- Better crisis survival
- Direct use in options pricing

If your return IC < 0.02, pivot to volatility.

### Insight 3: Architecture ≠ Alpha

You can have:
- Perfect engineering
- Clean architecture
- Comprehensive tests
- Production-grade monitoring

And still have zero alpha if signals are weak.

**Signals come first. Architecture comes second.**

## Resources

- **[TASK_0_README.md](./TASK_0_README.md)** - Detailed Task 0 guide
- **[requirements.md](./requirements.md)** - What the system must do
- **[design.md](./design.md)** - How the system works
- **[tasks.md](./tasks.md)** - Implementation steps
- **[README.md](./README.md)** - Spec overview

## Support

If Task 0 reveals weak signals and you're unsure what to do:

1. **Review IC by regime** - Does signal work in some regimes?
2. **Check IC decay** - Is horizon misaligned?
3. **Analyze crisis IC** - Does signal survive stress?
4. **Compare to volatility** - Is volatility forecasting stronger?
5. **Consider alternatives** - Regime timing? Dispersion trading?

## Final Checklist

Before starting Task 1:

- [ ] I have run Task 0
- [ ] I have reviewed the audit report
- [ ] I understand my mean IC
- [ ] I understand my stability ratio
- [ ] I have checked crisis IC
- [ ] I have applied decision rules
- [ ] Decision is PROCEED (not STOP)
- [ ] I know which tasks to complete (minimal vs. full)
- [ ] I have read the implementation plan
- [ ] I am ready to build incrementally

If all boxes are checked and decision is PROCEED, open [tasks.md](./tasks.md) and start Task 1.

If decision is STOP, do not proceed. Redesign signals first.

---

**Remember:** Don't build the cathedral until you test the soil.

**Good luck!**
