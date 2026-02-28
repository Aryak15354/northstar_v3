# Probabilistic Forecasting Spine Spec

## ⚠️ START HERE: Task 0 is Mandatory

**DO NOT START IMPLEMENTATION WITHOUT COMPLETING TASK 0**

This spec contains a comprehensive plan for building an institutional-grade probabilistic forecasting framework. However, **70% of this infrastructure is premature if your signals are weak**.

### Critical First Step

Before building any infrastructure, you MUST complete:

**[Task 0: Signal Reality Audit](./TASK_0_README.md)**

Task 0 validates whether your signals contain enough predictive power to justify the complexity of this spec.

### Quick Start

1. Read [TASK_0_README.md](./TASK_0_README.md)
2. Run `python scripts/signal_reality_audit.py`
3. Review results and apply decision rules
4. If STOP: redesign signals (do not proceed)
5. If PROCEED: continue to Task 1 in [tasks.md](./tasks.md)

## Spec Overview

This spec defines a 6-layer probabilistic forecasting framework for Northstar:

1. **Signal Layer** - Orthogonal signals across 5 buckets
2. **Feature Engine** - Regime-aware feature contextualization
3. **Core Forecast Models** - Ridge, HAR, Logistic models
4. **Calibration Monitor** - Track forecast accuracy
5. **Decay Monitor** - Detect signal degradation
6. **Integration Layer** - Connect to existing Northstar components

## Documents

- **[requirements.md](./requirements.md)** - 25 comprehensive requirements
- **[design.md](./design.md)** - Architecture, interfaces, mathematical specifications
- **[tasks.md](./tasks.md)** - 19 implementation tasks (Task 0 is mandatory first)
- **[TASK_0_README.md](./TASK_0_README.md)** - Signal validation guide (START HERE)

## Key Principles

1. **Validate signals before building infrastructure** (Task 0)
2. **Forecast the right objects** (excess returns, volatility, tail risk, regime transitions)
3. **Stability over complexity** (ridge > deep learning)
4. **Proper calibration discipline** (IC monitoring, decay detection)
5. **Realistic performance expectations** (IC: 0.03-0.06, Sharpe: 1-1.8)

## Decision Rules

Based on Task 0 results:

| Mean IC | Action |
|---------|--------|
| < 0.015 | **STOP** - Redesign signals |
| 0.015-0.025 | Build minimal ridge only |
| > 0.025 & stable | Proceed with full spine |

## The Brutal Truth

A perfect forecasting spine on weak signals produces a perfectly engineered disappointment.

**Architecture doesn't create alpha. Signals do.**

## What Makes This Spec Different

This spec includes a **mandatory validation gate** (Task 0) that prevents premature engineering. Most forecasting projects fail because they build infrastructure before validating signal strength.

This spec forces you to answer the hard question first:

**Do your signals justify this complexity?**

If the answer is no, the spec tells you to STOP and redesign signals. This saves weeks of wasted engineering effort.

## Integration with Northstar

This forecasting spine integrates with existing Northstar components:

- **Market Brain** → provides regime probabilities
- **Forecast Engine** → outputs distributions
- **Capital Allocator** → converts distributions to weights
- **Portfolio Governor** → applies constraints
- **Risk Authority** → overrides based on tail risk

The design preserves your existing architecture while adding probabilistic forecasting capabilities.

## Performance Expectations

If built correctly on strong signals:

- Directional accuracy: 52-57%
- IC: 0.03-0.06
- Sharpe: 1-1.8
- Max drawdown: <20% (if risk layer works)

Anything beyond this is fantasy unless you have structural edge.

## Next Steps

1. **Read [TASK_0_README.md](./TASK_0_README.md)** ← START HERE
2. Run signal reality audit
3. Apply decision rules
4. If PROCEED: Open [tasks.md](./tasks.md) and start Task 1
5. If STOP: Redesign signals or pivot strategy

## Questions?

If Task 0 reveals weak signals, consider:

- Pivoting to volatility forecasting (often stronger than return forecasting)
- Focusing on regime timing instead of cross-sectional ranking
- Building allocator research instead of signal research
- Finding orthogonal data sources

**Remember:** Don't build the cathedral until you test the soil.

---

**Status:** Spec complete, ready for Task 0 validation

**Created:** 2026-02-15

**Last Updated:** 2026-02-15
