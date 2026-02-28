# AlphaOS 60–90 Day Hardening Runbook

Start date: 2026-02-17  
Target 60-day checkpoint: 2026-04-17  
Target 90-day checkpoint: 2026-05-18

## Daily pre-open checklist
1. Manually refresh `UPSTOX_ACCESS_TOKEN` in `.env.options` (required).
2. Start runtime and verify canonical artifacts are fresh:
   - `data/processed/capital_allocations.json`
   - `data/processed/regime_intelligence_feed.json`
   - `data/options/live/options_dashboard_state.json`
3. Confirm `alpha_os` mode and safety state in dashboard JSON:
   - `alpha_os.mode`
   - `alpha_os.diagnostics.drift`
   - `alpha_os.diagnostics.survival_core`
   - `alpha_os.diagnostics.shadow_divergence_index`

## Daily post-close checklist
1. Review fallback tier usage and reason codes.
2. Review drift flags and severity.
3. Review survival-core activation and lock-new-risk behavior.
4. Archive metrics snapshot to `reports/alpha_os/`.

## Weekly cadence
1. Run walk-forward harness:
   - `python3 scripts/run_walk_forward_validation.py`
2. Validate thresholds:
   - fallback rate <= 5%
   - no halted cycles
   - survival-core activates in crisis windows
3. No parameter changes unless hard invariant is broken.

## Monthly cadence
1. Run HMM trainer (monthly only):
   - `python3 scripts/train_regime_hmm.py`
2. If gates fail, model remains frozen by design (`retrain skipped`).

## Hard rollback triggers
1. Drift severity `high` for 3+ consecutive cycles.
2. Fallback tier 4 > 8% for 3 consecutive trading days.
3. Any cycle halt or safety invariant breach.

## Enforce-mode ramp (after stable shadow period)
1. Week 1: 10% sizing influence.
2. Week 2: 25% sizing influence.
3. Week 3–4: 50% sizing influence only if all gates are green.
