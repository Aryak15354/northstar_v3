# Scoring Contract: Cross-Sectional Centering at Inference

All regime-specific model outputs MUST be cross-sectionally normalized at inference time before entering the overlay and allocation pipeline.

## Rule

- `DailyScorer` applies cross-sectional prediction normalization immediately after regime-model prediction and before any sentiment or macro overlay.
- The normalized score is stored in `model_score`.
- The pre-normalization output is preserved in `raw_model_score` for auditability.
- The default inference transform is `zscore`.

## Why

Regime models are trained for cross-sectional ranking. Their raw output distributions can drift by regime, so an absolute zero threshold is not stable across regimes. The allocator treats `final_score > 0` as deployable long exposure, which is only meaningful if the score distribution is centered.

Without centering, a regime-specific model can output an entirely negative cross-section even when its internal ranking remains useful. That causes silent underdeployment or full shutdown.

## Enforcement

- `src/scoring/daily_scorer.py` normalizes scores before overlays.
- `scripts/research/run_day2_clean_baseline.py` uses the same normalization contract for research walk-forwards.
- Any future scorer or replay path that consumes regime-model outputs must preserve this contract.

## Added

- Added: 2026-03-24
- Root cause identified during the Day 2 walk-forward audit of the Week of 2026-03-22 sprint.
