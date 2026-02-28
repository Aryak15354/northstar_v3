# Northstar V4 Cutover Runbook

## 1. Pre-Cutover
1. Freeze live trading (`NORTHSTAR_TRADING_FREEZE=1` and freeze-state artifact active).
2. Confirm all CI gates are green on stabilization branch.
3. Run strict shadow-delta workflow.

## 2. Pre-Merge Review
1. Verify `audit/V3_vs_V4_RUNTIME_DELTA.md` has no unexpected deltas.
2. Verify risk decisions include `policy_hash` and `equity_snapshot`.
3. Verify archive isolation gate pass.
4. Verify execution bypass check pass.

## 3. Cutover Execution
1. Merge stabilization branch to target branch.
2. Tag release baseline: `v4_stable_baseline`.
3. Enable branch protection with required CI gates:
   - `gate_static_integrity`
   - `gate_risk_safety`
   - `gate_runtime_integrity`
   - `gate_drift_detection`
   - `gate_risk_drift`
   - `gate_reachability_regression`
   - `gate_archive_isolation`
   - `ci_summary`
4. Disallow direct pushes to protected branch.

## 4. Post-Cutover Verification
1. Re-run strict 3-command runtime gate on protected branch head.
2. Re-run strict shadow-delta workflow.
3. Confirm no unexpected deltas after merge.

## 5. Unfreeze Protocol
1. Require explicit approval record.
2. Reference exact commit/tag for unfreeze.
3. Confirm CI green and shadow audit sign-off.
4. Apply unfreeze only through execution-governed pathway.

## 6. Rollback Policy
1. If any unexpected delta appears after cutover, re-enable freeze immediately.
2. Revert to prior tagged baseline if runtime integrity is compromised.
3. Re-open stabilization branch with incident findings attached.
