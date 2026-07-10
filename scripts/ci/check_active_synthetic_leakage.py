#!/usr/bin/env python3
"""Reject synthetic/mock data generation in active runtime code."""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ACTIVE_FILES = (
    "scripts/run_complete_v3_system.py",
    "scripts/northstar_v3_unified.py",
    "scripts/system_status_report.py",
    "scripts/eod_rebalance_with_pnl.py",
    "scripts/force_market_update.py",
    "src/orchestrator/master_orchestrator.py",
    "src/ingestion/market_loader.py",
    "src/data/price_access.py",
    "src/dashboard/v3_data_hub.py",
    "src/backtesting/backtest_engine.py",
    "src/live/daily_shadow_trader.py",
    # --- Extended 2026-07 to the full VERIFIED-LIVE money path. The audit found
    # the old 11-file list left the entire daily scoring/valuation/portfolio/
    # options/pnl chain outside the no-synthetic gate, so fabrication there would
    # pass CI trivially. Every file below was confirmed free of np.random / mock
    # in production code; this pins that so any NEW fabrication on the money path
    # fails CI. (A full src/-wide scan additionally surfaces dormant fabrication
    # in unscheduled market_brain organs — tracked separately for quarantine.)
    # data + ingestion + canonical build
    "src/data/loaders.py",
    "src/data/price_sanitizer.py",
    "scripts/build_canonical_training_datasets.py",
    # scoring
    "src/scoring/daily_scorer.py",
    "src/scoring/northstar_model.py",
    "scripts/runners/generate_daily_scorer_scores.py",
    # processing engines
    "src/processing/valuation_engine.py",
    "src/processing/risk_engine.py",
    "src/processing/technical_engine.py",
    "src/processing/price_processor.py",
    "src/processing/fundamental_processor.py",
    # intelligence valuation stack
    "src/intelligence/valuation_engines.py",
    # portfolio + pnl
    "src/portfolio/paper_portfolio_engine.py",
    "src/portfolio/portfolio_governor.py",
    "src/portfolio/governor.py",
    "src/portfolio/strategies.py",
    "src/pnl/indian_cost_model.py",
    "src/pnl/equity_tax_lots.py",
    "src/pnl/ledger.py",
    "src/pnl/nav_calculator.py",
    "scripts/run_paper_fund.py",
    # options money path
    "src/options/options_organ.py",
    "src/options/candidate_builder.py",
    "src/options/position_manager.py",
    "src/options/strategy_generator.py",
    "src/options/black_scholes.py",
    # signals feeding live scores
    "src/signals/bulk_deals.py",
    "src/signals/credit_ratings.py",
    "src/signals/sentiment_overlay.py",
    # daily refresh orchestration
    "scripts/runners/refresh_v3_artifacts.py",
)

FORBIDDEN_IMPORTS = {
    "unittest.mock",
    "faker",
}
FORBIDDEN_CALL_NAMES = {
    "MagicMock",
    "Mock",
    "Faker",
}
FORBIDDEN_ATTR_ROOTS = {
    ("np", "random"),
    ("numpy", "random"),
    ("random", "random"),
    ("random", "normalvariate"),
    ("random", "uniform"),
    ("random", "randint"),
    ("random", "choice"),
}


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def main() -> int:
    findings: list[dict[str, object]] = []
    for rel in ACTIVE_FILES:
        path = ROOT / rel
        if not path.exists():
            findings.append({"file": rel, "error": "missing_active_file"})
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS or alias.name.startswith("faker."):
                        findings.append({"file": rel, "line": node.lineno, "import": alias.name})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in FORBIDDEN_IMPORTS or module.startswith("faker."):
                    findings.append({"file": rel, "line": node.lineno, "import": module})
            elif isinstance(node, ast.Call):
                name = _dotted_name(node.func)
                if not name:
                    continue
                parts = tuple(name.split("."))
                if parts[-1] in FORBIDDEN_CALL_NAMES:
                    findings.append({"file": rel, "line": node.lineno, "call": name})
                if len(parts) >= 2 and (parts[0], parts[1]) in FORBIDDEN_ATTR_ROOTS:
                    findings.append({"file": rel, "line": node.lineno, "call": name})

    print(json.dumps({"check": "active_synthetic_leakage", "count": len(findings), "findings": findings[:200]}, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
