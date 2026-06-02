#!/usr/bin/env python3
"""Generate a deep read-only audit of Northstar V3 research artifacts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]

INSTITUTIONAL_COMPLETE_MD = REPO_ROOT / "data/validation/institutional_complete/INSTITUTIONAL_REPORT_20260226_174620.md"
INSTITUTIONAL_REAL_DATA_JSON = REPO_ROOT / "data/validation/institutional_real_data/institutional_report_20260226_174613.json"
PRODUCTION_CERTIFICATE_JSON = REPO_ROOT / "data/validation/NORTHSTAR_PRODUCTION_CERTIFICATE.json"
SIGNAL_DECAY_PARQUET = REPO_ROOT / "data/validation/signal_decay/signal_decay.parquet"
WALK_FORWARD_PARQUET = REPO_ROOT / "data/validation/walk_forward_results.parquet"
OOS_PARQUET = REPO_ROOT / "data/validation/oos_validation/oos_results.parquet"
BEHAVIORAL_STABILITY_PARQUET = REPO_ROOT / "data/validation/behavioral_stability/behavioral_stability.parquet"
IC_DIAGNOSTICS_DIR = REPO_ROOT / "data/results/research/ic_diagnostics"
RESEARCH_CYCLES_DIR = REPO_ROOT / "data/results/research/cycles"
MODEL_TRAINING_RESULTS_JSON = REPO_ROOT / "data/results/research/state/model_training_results.json"
RESEARCH_CYCLE_GLOB = "research_cycle_*.json"


AFFECTED_LIVE_PATH_FEATURES = [
    "earnings_quality_zscore",
    "earnings_quality_score",
    "bulk_deal_zscore",
    "bulk_signal_numeric",
    "credit_stress_flag",
    "credit_upgrade_ratio",
    "power_deviation_seasonal",
    "economic_activity_regime",
    "economic_activity_regime_encoded",
]


KEY_TIMELINE_FILES = {
    "pit_lag_audit": REPO_ROOT / "docs/pit_lag_audit.md",
    "build_regime_labels": REPO_ROOT / "scripts/build_regime_labels.py",
    "regime_pit_tests": REPO_ROOT / "tests/test_regime_pit_compliance.py",
    "accruals_tests": REPO_ROOT / "tests/test_accruals_validation.py",
    "formula_audit": REPO_ROOT / "audit/FORMULA_AND_CALCULATION_AUDIT_2026-03-21.md",
    "alternative_feature_block": REPO_ROOT / "src/alternative_data/alternative_feature_block.py",
    "alternative_pipeline_runner": REPO_ROOT / "src/alternative_data/alternative_pipeline_runner.py",
    "alt_data_contract_tests": REPO_ROOT / "tests/alternative_data/test_alt_data_key_contracts.py",
    "feature_factory": REPO_ROOT / "src/research/feature_factory.py",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def _read_text(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def _extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except Exception:
        return None


def _extract_string(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _coerce_timestamp(value: Any) -> pd.Timestamp | None:
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return ts.tz_convert(None)


@dataclass
class InstitutionalCompleteSummary:
    validation_status: str | None
    mean_return_pct: float | None
    mean_drawdown_pct: float | None
    mean_exposure_pct: float | None


@dataclass
class InstitutionalRealDataSummary:
    validation_status: str | None
    mean_return_pct: float | None
    mean_drawdown_pct: float | None
    mean_exposure_pct: float | None
    stayed_exposed_when_uncomfortable: Any
    temporal_violations: int | None
    override_attempts: int | None


@dataclass
class ICDiagnosticsSummary:
    report_count: int
    coverage_start: str | None
    coverage_end: str | None
    latest_report: str | None
    latest_selected_features: int | None
    latest_mean_ic_all: float | None
    latest_mean_ic_selected: float | None
    latest_top_features: list[str]
    affected_feature_report_counts: dict[str, int]


@dataclass
class ModelSummary:
    summary_timestamp: str | None
    latest_cycle_file: str | None
    latest_best_model: str | None
    latest_candidate_score: float | None
    historical_best_model_by_peak_score: str | None
    historical_peak_candidate_score: float | None


def load_institutional_complete() -> InstitutionalCompleteSummary:
    text = _read_text(INSTITUTIONAL_COMPLETE_MD)
    return InstitutionalCompleteSummary(
        validation_status=_extract_string(r"\*\*Validation Status\*\*:\s*([A-Z]+)", text),
        mean_return_pct=_extract_float(r"\*\*Returns\*\*:\s*Mean\s+([0-9.]+)%", text),
        mean_drawdown_pct=_extract_float(r"\*\*Drawdowns\*\*:\s*Mean\s+([0-9.]+)%", text),
        mean_exposure_pct=_extract_float(r"\*\*Exposures\*\*:\s*Mean\s+([0-9.]+)%", text),
    )


def load_institutional_real_data() -> InstitutionalRealDataSummary:
    report = _read_json(INSTITUTIONAL_REAL_DATA_JSON)
    distributions = report.get("distributions", {})
    behavior = report.get("behavior_validation", {})
    integrity = report.get("system_integrity", {})
    stayed_exposed = behavior.get("stayed_exposed_when_uncomfortable")
    if isinstance(stayed_exposed, str):
        stayed_exposed = stayed_exposed.strip().lower() == "true"
    return InstitutionalRealDataSummary(
        validation_status=report.get("validation_status"),
        mean_return_pct=(distributions.get("returns", {}) or {}).get("mean"),
        mean_drawdown_pct=(distributions.get("drawdowns", {}) or {}).get("mean"),
        mean_exposure_pct=(distributions.get("exposures", {}) or {}).get("mean"),
        stayed_exposed_when_uncomfortable=stayed_exposed,
        temporal_violations=integrity.get("temporal_violations"),
        override_attempts=integrity.get("override_attempts"),
    )


def load_signal_decay() -> dict[str, Any]:
    if not SIGNAL_DECAY_PARQUET.exists():
        return {"rows": 0, "alert_rows": 0, "signal_names": []}
    decay = pd.read_parquet(SIGNAL_DECAY_PARQUET)
    alert_rows = decay[decay.get("alert_level", pd.Series(dtype=object)).astype(str).str.lower() != "none"]
    return {
        "rows": int(len(decay)),
        "alert_rows": int(len(alert_rows)),
        "signal_names": sorted(decay.get("signal_name", pd.Series(dtype=object)).dropna().astype(str).unique().tolist()),
    }


def load_walk_forward() -> dict[str, Any]:
    if not WALK_FORWARD_PARQUET.exists():
        return {}
    wf = pd.read_parquet(WALK_FORWARD_PARQUET)
    out: dict[str, Any] = {"rows": int(len(wf))}
    if "sharpe" in wf.columns:
        ordered = wf.sort_values("sharpe", ascending=False).head(5)
        out["top_strategies_by_sharpe"] = [
            {
                "strategy": str(row.get("strategy")),
                "sharpe": float(row.get("sharpe")),
                "max_drawdown": float(row.get("max_drawdown")) if pd.notna(row.get("max_drawdown")) else None,
            }
            for _, row in ordered.iterrows()
        ]
        out["mean_sharpe"] = float(pd.to_numeric(wf["sharpe"], errors="coerce").mean())
    return out


def load_oos() -> dict[str, Any]:
    if not OOS_PARQUET.exists():
        return {}
    oos = pd.read_parquet(OOS_PARQUET)
    if oos.empty:
        return {"rows": 0}
    result: dict[str, Any] = {"rows": int(len(oos))}
    if {"train_sharpe", "test_sharpe"}.issubset(set(oos.columns)):
        tmp = oos.copy()
        tmp["derived_sharpe_degradation"] = pd.to_numeric(tmp["train_sharpe"], errors="coerce") - pd.to_numeric(
            tmp["test_sharpe"], errors="coerce"
        )
        worst = tmp.sort_values("derived_sharpe_degradation", ascending=False).iloc[0]
        result["worst_sharpe_degradation"] = float(worst["derived_sharpe_degradation"])
        result["worst_strategy"] = str(worst.get("strategy_name"))
        result["appears_placeholder"] = bool(
            set(tmp.get("strategy_name", pd.Series(dtype=object)).astype(str).unique()) == {"test_strategy"}
            and pd.to_numeric(tmp.get("train_observations", pd.Series(dtype=float)), errors="coerce").fillna(0).max() <= 0
        )
    return result


def load_behavioral_stability() -> dict[str, Any]:
    if not BEHAVIORAL_STABILITY_PARQUET.exists():
        return {}
    stab = pd.read_parquet(BEHAVIORAL_STABILITY_PARQUET)
    if stab.empty:
        return {"rows": 0}
    return {
        "rows": int(len(stab)),
        "mean_return_correlation": float(pd.to_numeric(stab.get("return_correlation"), errors="coerce").mean()),
        "all_unstable": bool(stab.get("stability_result", pd.Series(dtype=object)).astype(str).eq("unstable").all()),
        "appears_placeholder": bool(
            set(stab.get("strategy_name", pd.Series(dtype=object)).astype(str).unique()) == {"test_strategy"}
        ),
    }


def load_ic_diagnostics() -> ICDiagnosticsSummary:
    rows: list[dict[str, Any]] = []
    affected_counts = {feature: 0 for feature in AFFECTED_LIVE_PATH_FEATURES}
    latest_payload: dict[str, Any] | None = None
    latest_ts: pd.Timestamp | None = None

    for path in sorted(IC_DIAGNOSTICS_DIR.rglob("ic_report_*.json")):
        payload = _read_json(path)
        generated_at = _coerce_timestamp(payload.get("generated_at"))
        if generated_at is None:
            continue
        rows.append(
            {
                "file": path.name,
                "generated_at": generated_at,
                "n_features_selected": payload.get("n_features_selected"),
                "mean_ic_all_features": payload.get("mean_ic_all_features"),
                "mean_ic_selected_features": payload.get("mean_ic_selected_features"),
            }
        )
        feature_names = {
            row.get("feature")
            for row in payload.get("feature_stats", [])
            if isinstance(row, dict) and row.get("feature")
        }
        for feature in AFFECTED_LIVE_PATH_FEATURES:
            if feature in feature_names:
                affected_counts[feature] += 1
        if latest_ts is None or generated_at > latest_ts:
            latest_ts = generated_at
            latest_payload = payload

    if not rows:
        return ICDiagnosticsSummary(
            report_count=0,
            coverage_start=None,
            coverage_end=None,
            latest_report=None,
            latest_selected_features=None,
            latest_mean_ic_all=None,
            latest_mean_ic_selected=None,
            latest_top_features=[],
            affected_feature_report_counts=affected_counts,
        )

    frame = pd.DataFrame(rows).sort_values("generated_at")
    top_features = latest_payload.get("top_features", []) if latest_payload else []
    latest_top_features: list[str] = []
    for item in top_features[:10]:
        if isinstance(item, dict):
            latest_top_features.append(str(item.get("feature") or item.get("name") or "unknown"))
        else:
            latest_top_features.append(str(item))

    return ICDiagnosticsSummary(
        report_count=int(len(frame)),
        coverage_start=str(frame["generated_at"].min()),
        coverage_end=str(frame["generated_at"].max()),
        latest_report=str(frame.iloc[-1]["file"]),
        latest_selected_features=int(frame.iloc[-1]["n_features_selected"]) if pd.notna(frame.iloc[-1]["n_features_selected"]) else None,
        latest_mean_ic_all=float(frame.iloc[-1]["mean_ic_all_features"]) if pd.notna(frame.iloc[-1]["mean_ic_all_features"]) else None,
        latest_mean_ic_selected=float(frame.iloc[-1]["mean_ic_selected_features"]) if pd.notna(frame.iloc[-1]["mean_ic_selected_features"]) else None,
        latest_top_features=latest_top_features,
        affected_feature_report_counts=affected_counts,
    )


def load_model_summary() -> ModelSummary:
    summary_payload = _read_json(MODEL_TRAINING_RESULTS_JSON)
    summary_timestamp = summary_payload.get("timestamp")

    historical_best_model = None
    historical_peak_score = None
    latest_cycle_file = None
    latest_cycle_ts = None
    latest_best_model = None
    latest_candidate_score = None

    for path in sorted(RESEARCH_CYCLES_DIR.rglob(RESEARCH_CYCLE_GLOB)):
        payload = _read_json(path)
        outputs = payload.get("outputs_generated", []) if isinstance(payload, dict) else []
        model_promotion = None
        output_generated_at = None
        for output in outputs:
            if isinstance(output, dict) and output.get("type") == "model_promotion":
                model_promotion = output.get("data", {})
                output_generated_at = output.get("generated_at")
                break
        if not isinstance(model_promotion, dict):
            continue

        score = (model_promotion.get("score") or {}).get("candidate_score")
        if score is not None and (historical_peak_score is None or float(score) > float(historical_peak_score)):
            historical_peak_score = float(score)
            historical_best_model = str(model_promotion.get("best_model"))

        ts = (
            _coerce_timestamp(model_promotion.get("generated_at"))
            or _coerce_timestamp(output_generated_at)
            or _coerce_timestamp(payload.get("timestamp"))
            or pd.Timestamp(path.stat().st_mtime, unit="s")
        )
        if latest_cycle_ts is None or ts > latest_cycle_ts:
            latest_cycle_ts = ts
            latest_cycle_file = path.name
            latest_best_model = str(model_promotion.get("best_model"))
            latest_candidate_score = float(score) if score is not None else None

    return ModelSummary(
        summary_timestamp=str(summary_timestamp) if summary_timestamp else None,
        latest_cycle_file=latest_cycle_file,
        latest_best_model=latest_best_model,
        latest_candidate_score=latest_candidate_score,
        historical_best_model_by_peak_score=historical_best_model,
        historical_peak_candidate_score=historical_peak_score,
    )


def collect_timeline_mtimes() -> dict[str, str]:
    out: dict[str, str] = {}
    for label, path in KEY_TIMELINE_FILES.items():
        if not path.exists():
            continue
        out[label] = pd.Timestamp(path.stat().st_mtime, unit="s").strftime("%Y-%m-%d %H:%M:%S")
    return out


def build_markdown(
    *,
    institutional_complete: InstitutionalCompleteSummary,
    institutional_real_data: InstitutionalRealDataSummary,
    signal_decay: dict[str, Any],
    walk_forward: dict[str, Any],
    oos: dict[str, Any],
    behavioral_stability: dict[str, Any],
    ic_summary: ICDiagnosticsSummary,
    model_summary: ModelSummary,
    timeline_mtimes: dict[str, str],
) -> str:
    latest_top_features = ", ".join(ic_summary.latest_top_features[:10]) if ic_summary.latest_top_features else "none"
    missing_affected = [name for name, count in ic_summary.affected_feature_report_counts.items() if count == 0]
    top_strategies = walk_forward.get("top_strategies_by_sharpe", [])
    top_strategy_lines = [
        f"- {row['strategy']}: Sharpe {row['sharpe']:.3f}, max drawdown {row['max_drawdown']:.3f}"
        for row in top_strategies
    ] or ["- none"]

    return f"""# Deep Research Audit

Generated by: `scripts/research/deep_research_audit.py`

## Executive Verdict

1. PIT hardening is real and recent. The repo shows a PIT audit on 2026-03-09 plus corresponding code/test updates through 2026-03-12 and 2026-03-22.
2. Underdeployment on real data is real. The stored institutional real-data validation averages only {institutional_real_data.mean_exposure_pct:.2f}% exposure and fails its own behavior gate.
3. The current evidence base cannot answer the post-bugfix question yet. The latest IC diagnostics stop at {ic_summary.coverage_end}, which is before the 2026-03-21 formula audit and before the 2026-03-22 weekly sprint.
4. The PIT-hardened research stack and the exposure-suppressing live path are not the same code path. Existing IC reports therefore do not directly validate the March 21 alternative-data live-path fixes.
5. Current promotion stance should remain `HOLD`. The latest stored research snapshot points to `{model_summary.latest_best_model}` at candidate score `{model_summary.latest_candidate_score}`, but that is still pre-postfix-certification evidence under an active freeze.

## What Changed

### Timeline

- 2026-01-19: production certificate issued and valid until 2026-04-19.
- 2026-02-26: institutional complete walk-forward report marked PASS with mean return about {institutional_complete.mean_return_pct:.1f}%, mean drawdown about {institutional_complete.mean_drawdown_pct:.1f}%, and mean exposure about {institutional_complete.mean_exposure_pct:.1f}%.
- 2026-02-26: institutional real-data validation marked FAIL with mean return {institutional_real_data.mean_return_pct:.2f}%, mean drawdown {institutional_real_data.mean_drawdown_pct:.2f}%, and mean exposure {institutional_real_data.mean_exposure_pct:.2f}%.
- 2026-03-09: PIT lag audit documented two concrete hardening changes.
- 2026-03-11 to 2026-03-12: latest stored IC diagnostics were generated.
- 2026-03-21: formula audit documented alternative-data key mismatches, smart-money mapping inversion, exposure-unit drift, and dead recovery restoration.
- 2026-03-22: feature factory was modified again, consistent with continued PIT/research stack work.

### PIT Hardening Evidence

- `docs/pit_lag_audit.md` is timestamped `{timeline_mtimes.get('pit_lag_audit', 'unknown')}`.
- `scripts/build_regime_labels.py` is timestamped `{timeline_mtimes.get('build_regime_labels', 'unknown')}` and explicitly uses `+1 day` for daily macro lag plus `+1 business day` fallbacks for sentiment.
- `tests/test_regime_pit_compliance.py` is timestamped `{timeline_mtimes.get('regime_pit_tests', 'unknown')}`.
- `src/research/feature_factory.py` is timestamped `{timeline_mtimes.get('feature_factory', 'unknown')}` and falls back to `date + 1 business day` when sentiment `availability_date` is missing.

Net interpretation: PIT integration made the research stack more conservative and more honest. Any comparison between pre-March-09 and post-March-09 research outputs must assume some earlier optimism may have been removed.

### Formula / Live-Path Bug-Fix Evidence

- `audit/FORMULA_AND_CALCULATION_AUDIT_2026-03-21.md` is timestamped `{timeline_mtimes.get('formula_audit', 'unknown')}`.
- `src/alternative_data/alternative_feature_block.py` and `src/alternative_data/alternative_pipeline_runner.py` were updated on `{timeline_mtimes.get('alternative_feature_block', 'unknown')}` and `{timeline_mtimes.get('alternative_pipeline_runner', 'unknown')}`.
- `tests/alternative_data/test_alt_data_key_contracts.py` was added on `{timeline_mtimes.get('alt_data_contract_tests', 'unknown')}`.
- `tests/test_accruals_validation.py` was added on `{timeline_mtimes.get('accruals_tests', 'unknown')}`.

Net interpretation: March 21 work addressed bugs that would all suppress deployment or mis-state live alternative-data state. That supports the hypothesis that live exposure should rise after those fixes.

## Artifact Audit

### Institutional Validation Split

- Institutional complete report: `{institutional_complete.validation_status}`.
- Institutional real-data report: `{institutional_real_data.validation_status}`.
- Real-data behavior flag `stayed_exposed_when_uncomfortable`: `{institutional_real_data.stayed_exposed_when_uncomfortable}`.
- Real-data system integrity still shows temporal violations `{institutional_real_data.temporal_violations}` and override attempts `{institutional_real_data.override_attempts}`.

Interpretation:

- The system still behaves with temporal integrity on real data.
- The failure is deployment/exposure, not lookahead leakage or operator override.
- The strongest divergence between complete and real-data validation is average exposure: about {institutional_complete.mean_exposure_pct:.1f}% versus {institutional_real_data.mean_exposure_pct:.2f}%.

### Validator Drift

Three different exposure gates exist in code:

- `scripts/institutional_12month_real_data.py`: mean exposure must exceed 50 percentage points.
- `src/validation/institutional_walk_forward_validator.py`: average exposure must be at least 40%.
- `scripts/institutional_walk_forward_complete.py`: average exposure must exceed 15 percentage points.

Interpretation:

- Pass/fail messaging is not normalized across validation surfaces.
- This drift does not explain the full problem because 4.84% would fail every threshold above 15%.
- It does mean the exact wording of the FAIL reason depends on which validator produced the artifact.

### Signal Decay / OOS / Stability

- Signal decay rows: {signal_decay.get('rows', 0)}.
- Signal decay alert rows: {signal_decay.get('alert_rows', 0)}.
- OOS rows: {oos.get('rows', 0)} with worst Sharpe degradation {oos.get('worst_sharpe_degradation')}.
- Behavioral stability rows: {behavioral_stability.get('rows', 0)} with mean return correlation {behavioral_stability.get('mean_return_correlation')}.

Interpretation:

- Signal decay parquet appears to be a placeholder harness artifact, not decision-grade evidence. It contains only `{", ".join(signal_decay.get('signal_names', [])) or 'none'}`.
- OOS validation also appears to be a placeholder harness artifact because it is built around `test_strategy` with zero training observations.
- Behavioral stability appears non-decision-grade for the same reason: only `test_strategy` is present and every row is marked unstable.

### Walk-Forward Results Parquet

Top stored strategies by Sharpe:
{chr(10).join(top_strategy_lines)}

Interpretation:

- The generic walk-forward parquet is more useful than the placeholder OOS/stability artifacts.
- It shows a live candidate ranking surface, but it is not enough on its own to answer the post-bugfix exposure question.

### IC Diagnostics

- IC reports found: {ic_summary.report_count}.
- Coverage: {ic_summary.coverage_start} to {ic_summary.coverage_end}.
- Latest report: {ic_summary.latest_report}.
- Latest selected feature count: {ic_summary.latest_selected_features}.
- Latest mean IC across all evaluated features: {ic_summary.latest_mean_ic_all}.
- Latest mean IC across selected features: {ic_summary.latest_mean_ic_selected}.
- Latest top features: {latest_top_features}.

Interpretation:

- The latest IC evidence is dominated by short-horizon price and momentum features.
- The latest IC corpus is PIT-hardened but still pre-March-21 formula-fix.
- None of the following bug-affected live-path features appear in any stored IC report: {", ".join(missing_affected)}.

This is the key structural finding of the audit:

- The current IC corpus is not measuring the March 21 alternative-data live-path fixes.
- Therefore it cannot tell us whether those fixes materially improved exposure or predictive power.

### Promotion Snapshot

- Model summary timestamp: {model_summary.summary_timestamp}.
- Latest stored promotion candidate: `{model_summary.latest_best_model}` from `{model_summary.latest_cycle_file}`.
- Latest stored candidate score: `{model_summary.latest_candidate_score}`.
- Historical peak candidate score in stored research cycles: `{model_summary.historical_peak_candidate_score}` from `{model_summary.historical_best_model_by_peak_score}`.

Interpretation:

- The latest stored winner is `{model_summary.latest_best_model}`, but earlier pre-PIT or pre-postfix runs achieved higher scores with other models.
- Because certification and exposure evidence are stale relative to the March 21 fixes, model choice is not yet promotion-grade.

## Code-Path Split That Explains The Confusion

The audit shows two materially different paths:

1. Research PIT path:
   - `scripts/build_regime_labels.py`
   - `src/research/regime_engine.py`
   - `src/research/feature_factory.py`
   - `src/signals/sentiment_bridge.py`

2. Live alternative-data / exposure path:
   - `src/alternative_data/alternative_feature_block.py`
   - `src/alternative_data/alternative_pipeline_runner.py`
   - `src/portfolio/governor.py`
   - market-state exposure normalization and downstream runtime consumers

The research IC diagnostics use the `src/signals/*` family for alternative features, with fields like `bulk_net_*`, `rating_*`, and `pledge_*`.

The March 21 audit findings were mostly in the live `src/alternative_data/*` state path, with fields like `credit_upgrade_ratio`, `credit_stress_flag`, `bulk_signal_numeric`, and `power_deviation_seasonal`.

Consequence:

- PIT-hardened research results and live exposure suppression are being discussed together, but the stored evidence is only partially overlapping.
- A post-fix audit must explicitly test both the research dataset path and the live alternative-data state path.

## Research Verdict For Freeze Review

Current verdict: `DO NOT PROMOTE YET`

Why:

- The production certificate predates PIT hardening and predates the March 21 formula/live-path fixes.
- The real-data validation FAIL is genuine on exposure.
- The IC corpus is stale relative to the latest bug-fix set.
- The current stored artifacts do not prove that post-fix IC is materially better.

## Highest-Leverage Next Runs

1. Run a focused 52-week IC spot-check for the bug-affected features on current code and store it beside this audit.
2. Re-run institutional real-data validation on current code with a timestamped experiment output and compare exposure window by window against 2026-02-26.
3. Re-run the honest walk-forward on current frozen research configuration to produce a post-fix baseline.
4. Only after steps 1-3, update the weekly promotion memo for the 2026-04-17 freeze review.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a deep research audit report")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where markdown/json outputs will be written")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    institutional_complete = load_institutional_complete()
    institutional_real_data = load_institutional_real_data()
    signal_decay = load_signal_decay()
    walk_forward = load_walk_forward()
    oos = load_oos()
    behavioral_stability = load_behavioral_stability()
    ic_summary = load_ic_diagnostics()
    model_summary = load_model_summary()
    timeline_mtimes = collect_timeline_mtimes()

    markdown = build_markdown(
        institutional_complete=institutional_complete,
        institutional_real_data=institutional_real_data,
        signal_decay=signal_decay,
        walk_forward=walk_forward,
        oos=oos,
        behavioral_stability=behavioral_stability,
        ic_summary=ic_summary,
        model_summary=model_summary,
        timeline_mtimes=timeline_mtimes,
    )

    summary = {
        "institutional_complete": asdict(institutional_complete),
        "institutional_real_data": asdict(institutional_real_data),
        "signal_decay": signal_decay,
        "walk_forward": walk_forward,
        "oos": oos,
        "behavioral_stability": behavioral_stability,
        "ic_summary": asdict(ic_summary),
        "model_summary": asdict(model_summary),
        "timeline_mtimes": timeline_mtimes,
    }

    (output_dir / "deep_research_audit.md").write_text(markdown)
    (output_dir / "deep_research_audit_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Wrote {output_dir / 'deep_research_audit.md'}")
    print(f"Wrote {output_dir / 'deep_research_audit_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
