#!/usr/bin/env python3
"""
Day 6 Deployment Diagnosis
==========================
Traces the path from model score to actual deployed exposure.

The chain that must be tested:
Model score -> Score rank -> Kelly allocator -> Capital allocator ->
No-edge detector -> Governor capital structure -> Risk budget -> Actual position

Prior observation: mean exposure 4.84% when 20%+ was needed.
Hypothesis: one or more of the following is suppressing deployment:
1. No-edge detector is activated (IC estimates below threshold)
2. Recovery counter is dead (stuck in recovery mode indefinitely)
3. Convexity score veto (>0.5 collapses deployment to 0.3)
4. Governor in CAPITAL_PRESERVATION regime (reduces equity to 20%)
5. Risk budget gate denying proposals

This script does not modify state. It only inspects local files and runtime DBs.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, deque
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def recursive_matches(obj: Any, keywords: list[str]) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    queue = deque([([], obj)])
    while queue:
        path, current = queue.popleft()
        if isinstance(current, dict):
            for key, value in current.items():
                new_path = path + [str(key)]
                key_text = str(key).lower()
                if any(keyword in key_text for keyword in keywords):
                    found.append((".".join(new_path), value))
                queue.append((new_path, value))
        elif isinstance(current, list):
            for idx, value in enumerate(current[:50]):
                queue.append((path + [str(idx)], value))
    return found


def print_matches(label: str, matches: list[tuple[str, Any]], max_rows: int = 20) -> None:
    print(f"\n{label}:")
    if not matches:
        print("  no matching fields found")
        return
    for path, value in matches[:max_rows]:
        print(f"  {path}: {value}")
    if len(matches) > max_rows:
        print(f"  ... {len(matches) - max_rows} more")


def test_no_edge_detector() -> dict[str, Any]:
    state_paths = [
        PROJECT_ROOT / "data/state/unified_state.json",
        PROJECT_ROOT / "data/runtime/no_edge_state.json",
        PROJECT_ROOT / "data/state/intelligence_state.json",
    ]

    matches: list[tuple[str, Any]] = []
    no_edge_active = False
    for path in state_paths:
        payload = load_json(path)
        if payload is None:
            continue
        path_matches = recursive_matches(payload, ["no_edge", "edge", "ic", "signal"])
        if path_matches:
            print(f"\nFound state: {path}")
            print_matches("  no-edge related fields", path_matches)
        matches.extend(path_matches)
        for field_path, value in path_matches:
            text = str(value).lower()
            if "no_edge" in field_path.lower() and ("true" in text or "active" in text or "no_edge" == text):
                no_edge_active = True
            if field_path.lower().endswith("state") and "no_edge" in text:
                no_edge_active = True

    status = "FAIL" if no_edge_active else ("PASS" if matches else "UNKNOWN")
    note = "no-edge state appears active" if no_edge_active else ("signals found but not active" if matches else "no explicit no-edge state file")
    return {"status": status, "note": note}


def test_recovery_counter() -> dict[str, Any]:
    state_paths = [
        PROJECT_ROOT / "data/state/unified_state.json",
        PROJECT_ROOT / "data/runtime/recovery_state.json",
    ]

    matches: list[tuple[str, Any]] = []
    recovery_active = False
    for path in state_paths:
        payload = load_json(path)
        if payload is None:
            continue
        path_matches = recursive_matches(payload, ["recovery", "drawdown", "counter"])
        if path_matches:
            print(f"\nFound state: {path}")
            print_matches("  recovery-related fields", path_matches)
        matches.extend(path_matches)
        for field_path, value in path_matches:
            text = str(value).lower()
            if "recovery" in text and any(flag in text for flag in ["true", "mode", "active"]):
                recovery_active = True
            if field_path.lower().endswith("options_system_mode") and "recovery" in text:
                recovery_active = True

    status = "FAIL" if recovery_active else ("PASS" if matches else "UNKNOWN")
    note = "system still appears to be in recovery mode" if recovery_active else ("recovery fields present" if matches else "no explicit recovery counter file")
    return {"status": status, "note": note}


def test_governor_regime() -> dict[str, Any]:
    config_path = PROJECT_ROOT / "config/portfolio_governor_config.yaml"
    state_path = PROJECT_ROOT / "data/state/unified_state.json"

    active_regime = None
    equity_fraction = None
    allowed_exposure = None

    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        print("\nGovernor config:")
        for key in ["capital_structure", "regime", "equity_target", "regimes"]:
            if key in config:
                print(f"  {key}: {config[key]}")

    state = load_json(state_path) or {}
    governor_state = dict(state.get("governor_state", {}) or {})
    market_state = dict(state.get("market", {}) or {})
    if governor_state:
        active_regime = governor_state.get("capital_structure_regime")
        equity_fraction = governor_state.get("equity_fraction")
        allowed_exposure = market_state.get("allowed_exposure")
        print("\nGovernor runtime state:")
        print(f"  capital_structure_regime: {active_regime}")
        print(f"  equity_fraction: {equity_fraction}")
        print(f"  allowed_exposure: {allowed_exposure}")

    fail = str(active_regime).upper() == "CAPITAL_PRESERVATION" or (
        isinstance(equity_fraction, (float, int)) and float(equity_fraction) <= 0.20
    )
    status = "FAIL" if fail else ("PASS" if active_regime is not None else "UNKNOWN")
    note = (
        "governor capital structure is constraining equity deployment"
        if fail
        else f"regime={active_regime}, equity_fraction={equity_fraction}"
        if active_regime is not None
        else "governor runtime state unavailable"
    )
    return {"status": status, "note": note}


def test_risk_budget_gate() -> dict[str, Any]:
    db_path = PROJECT_ROOT / "data/runtime/portfolio_runtime.db"
    if not db_path.exists():
        print("\nRisk-budget DB missing.")
        return {"status": "UNKNOWN", "note": "portfolio_runtime.db not found"}

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"\nDatabase tables: {tables}")

        status_counts: Counter[str] = Counter()
        denial_reasons: Counter[str] = Counter()
        if "proposal_inbox" in tables:
            cursor.execute("SELECT status, denial_reason FROM proposal_inbox")
            for status, denial_reason in cursor.fetchall():
                status_counts[str(status or "UNKNOWN")] += 1
                if denial_reason:
                    denial_reasons[str(denial_reason)] += 1
            print(f"  proposal_inbox status counts: {dict(status_counts)}")
            if denial_reasons:
                print(f"  proposal_inbox denial reasons: {dict(denial_reasons)}")

        if "portfolio_events" in tables:
            cursor.execute(
                "SELECT event_type, decision_mode, budget_decision_id, liquidity_decision_id "
                "FROM portfolio_events ORDER BY sequence_no DESC LIMIT 20"
            )
            recent_events = cursor.fetchall()
            print("  recent portfolio_events:")
            for event_type, decision_mode, budget_decision_id, liquidity_decision_id in recent_events[:10]:
                print(
                    f"    {event_type} | mode={decision_mode} | "
                    f"budget={budget_decision_id} | liquidity={liquidity_decision_id}"
                )

        denied = sum(count for status, count in status_counts.items() if status.lower() in {"denied", "rejected"})
        pending = sum(count for status, count in status_counts.items() if status.lower() in {"pending", "queued"})
        total = sum(status_counts.values())
        denial_rate = denied / total if total else 0.0
        pending_rate = pending / total if total else 0.0

        if total == 0:
            return {"status": "UNKNOWN", "note": "no proposals logged"}
        if denial_rate > 0.30 or pending_rate > 0.50:
            return {
                "status": "FAIL",
                "note": f"proposal gate blocking flow (denial_rate={denial_rate:.0%}, pending_rate={pending_rate:.0%})",
            }
        return {
            "status": "PASS",
            "note": f"proposal flow healthy (statuses={dict(status_counts)})",
        }
    finally:
        conn.close()


def test_convexity_score() -> dict[str, Any]:
    state = load_json(PROJECT_ROOT / "data/state/unified_state.json") or {}
    matches = recursive_matches(state, ["convex", "caution"])
    print_matches("Convexity-related fields", matches)

    caution_score = None
    for field_path, value in matches:
        if field_path.endswith("caution_score"):
            try:
                caution_score = float(value)
            except Exception:
                caution_score = None

    convex_objective = any("convexity" in str(value).lower() for _, value in matches)
    fail = (caution_score is not None and caution_score > 0.5) or convex_objective
    status = "FAIL" if fail else ("PASS" if matches else "UNKNOWN")
    note = (
        f"convexity veto / defensive objective present (caution_score={caution_score})"
        if fail
        else f"caution_score={caution_score}"
        if matches
        else "no convexity fields found"
    )
    return {"status": status, "note": note}


def test_kelly_allocator() -> dict[str, Any]:
    state = load_json(PROJECT_ROOT / "data/state/unified_state.json") or {}
    market = dict(state.get("market", {}) or {})
    portfolio = dict(state.get("portfolio", {}) or {})
    governor_state = dict(state.get("governor_state", {}) or {})

    print("\nAllocator chain snapshot:")
    print(f"  market.allowed_exposure: {market.get('allowed_exposure')}")
    print(f"  governor_state.equity_fraction: {governor_state.get('equity_fraction')}")
    print(f"  portfolio.target_total_exposure: {portfolio.get('target_total_exposure')}")
    print(f"  portfolio.total_exposure: {portfolio.get('total_exposure')}")

    target_exposure = portfolio.get("target_total_exposure")
    if isinstance(target_exposure, (float, int)):
        target_exposure = float(target_exposure)
        status = "FAIL" if target_exposure < 0.20 else "PASS"
        note = (
            f"target_total_exposure={target_exposure:.2%} before hard caps"
            if status == "PASS"
            else f"target_total_exposure={target_exposure:.2%}, too low before deployment caps"
        )
        return {"status": status, "note": note}

    matches = recursive_matches(state, ["kelly", "gross", "weight", "exposure"])
    print_matches("Kelly-related fields", matches)
    return {"status": "UNKNOWN", "note": "no explicit Kelly allocator state found"}


def test_hot_load_strategy() -> dict[str, Any]:
    candidate_files = [
        PROJECT_ROOT / "data/state/unified_state.json",
        PROJECT_ROOT / "src/intelligence/intelligence_stack.py",
        PROJECT_ROOT / "src/core/state_authority.py",
    ]

    found_locations: list[str] = []
    for path in candidate_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "_hot_load_strategy" in text or "hot_load_strategy" in text:
            found_locations.append(str(path))

    if not found_locations:
        print("\nHot-load strategy wiring:")
        print("  no hot-load strategy references found in current state/runtime files")
        return {"status": "UNKNOWN", "note": "hot-load strategy wiring not materialized"}

    print("\nHot-load strategy wiring:")
    for location in found_locations:
        print(f"  found reference in: {location}")
    return {"status": "PASS", "note": f"hot-load references found in {len(found_locations)} location(s)"}


def print_diagnosis_summary(results: dict[str, dict[str, Any]]) -> None:
    print("\n" + "=" * 60)
    print("DEPLOYMENT DIAGNOSIS SUMMARY")
    print("=" * 60)
    for step, result in results.items():
        status = result.get("status", "UNKNOWN")
        note = result.get("note", "")
        print(f"  {step:<30} {status:<10} {note}")

    priority = [
        "No-edge detector",
        "Recovery counter",
        "Kelly allocator",
        "Governor regime",
        "Risk budget gate",
        "Convexity score",
        "Hot-load strategy",
    ]
    failed = [step for step in priority if results.get(step, {}).get("status") == "FAIL"]
    if failed:
        root = failed[0]
        print(f"\nMost likely root cause: {root}")
        print("Fix this first before investigating downstream suppressors.")
    else:
        print("\nAll steps show PASS or UNKNOWN.")
        print("Root cause may be hidden in thresholds or in runtime files not currently materialized.")


if __name__ == "__main__":
    print("Running deployment diagnosis...")
    print("=" * 60)

    results = {}

    print("\n[1/7] No-edge detector")
    results["No-edge detector"] = test_no_edge_detector()

    print("\n[2/7] Recovery counter")
    results["Recovery counter"] = test_recovery_counter()

    print("\n[3/7] Governor regime")
    results["Governor regime"] = test_governor_regime()

    print("\n[4/7] Risk budget gate")
    results["Risk budget gate"] = test_risk_budget_gate()

    print("\n[5/7] Convexity score")
    results["Convexity score"] = test_convexity_score()

    print("\n[6/7] Kelly allocator")
    results["Kelly allocator"] = test_kelly_allocator()

    print("\n[7/7] Hot-load strategy")
    results["Hot-load strategy"] = test_hot_load_strategy()

    print_diagnosis_summary(results)
    print("\nDiagnosis complete. Review output above for root cause.")
    print("Write findings to: data/research/experiments/week_2026_03_28/day6_diagnosis.md")
