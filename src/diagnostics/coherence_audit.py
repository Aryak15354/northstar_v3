#!/usr/bin/env python3
"""
Northstar V3 Coherence Audit

Checks calibration and coherence across macro (RBI), market (yfinance/indices),
valuations and scores pipelines. Produces a markdown report with findings.

Usage:
  python src/diagnostics/coherence_audit.py
"""
import os
import json
from datetime import datetime
import pandas as pd
import numpy as np

REPORTS_DIR = "reports"
MACRO_FACTORS_FILE = "data/macro/factors/macro_factors.parquet"
MACRO_SCORE_FILE = "data/macro/factors/macro_score.parquet"
MARKET_LIVE_FILE = "data/options/live/market_data_latest.json"
SCORES_FILE = "data/processed/scores.parquet"
PRICES_FILE = "data/processed/prices.parquet"

os.makedirs(REPORTS_DIR, exist_ok=True)


def pct_change(series, periods=1):
    try:
        return series.pct_change(periods)
    except Exception:
        return pd.Series(index=series.index, dtype=float)


def load_parquet(path):
    try:
        if os.path.exists(path):
            return pd.read_parquet(path)
    except Exception:
        pass
    return pd.DataFrame()


def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def summarize_series(name, s):
    s = s.dropna()
    if s.empty:
        return f"- **{name}**: no data\n"
    return (
        f"- **{name}**: n={len(s)}, mean={s.mean():.3f}, std={s.std():.3f}, "
        f"min={s.min():.3f}, max={s.max():.3f}\n"
    )


def audit_macro_consistency():
    findings = []
    macro = load_parquet(MACRO_SCORE_FILE)
    factors = load_parquet(MACRO_FACTORS_FILE)

    if not macro.empty:
        # Ensure datetime index
        if not isinstance(macro.index, pd.DatetimeIndex):
            if 'Date' in macro.columns:
                macro['Date'] = pd.to_datetime(macro['Date'], errors='coerce')
                macro = macro.set_index('Date')

        findings.append("## Macro Regime and Score")
        for col in [
            'MacroScore','Contrib_G','Contrib_I','Contrib_L','Contrib_S','TrueStress',
            'MarketStress_z','MarketBreadth','MarketParticipation'
        ]:
            if col in macro.columns:
                findings.append(summarize_series(col, macro[col]))
        # Check sign expectations
        signs_ok = []
        if {'Contrib_G','Contrib_I','Contrib_L','Contrib_S'}.issubset(macro.columns):
            signs_ok.append((macro['Contrib_G'].mean() >= macro['Contrib_G'].median() - 1e-9))  # growth positive bias
            signs_ok.append((macro['Contrib_I'].mean() <= macro['Contrib_I'].median() + 1e-9))  # inflation negative
            signs_ok.append((macro['Contrib_L'].mean() >= macro['Contrib_L'].median() - 1e-9))  # liquidity positive
            # Stress contribution should be negative on average
            signs_ok.append((macro['Contrib_S'].mean() <= macro['Contrib_S'].median() + 1e-9))
        if signs_ok and not all(signs_ok):
            findings.append("- ⚠️ Factor contribution signs look off vs expectations (G+, I-, L+, S-).\n")

        # Regime-breadth coherence (recent window)
        recent = macro.tail(26)
        if 'Regime' in recent.columns:
            breadth = recent.get('MarketBreadth')
            if breadth is not None and breadth.notna().any():
                boom_mask = recent['Regime'].str.lower() == 'boom'
                slowdown_mask = recent['Regime'].str.lower().isin(['slowdown','crisis'])
                if boom_mask.any() and breadth is not None:
                    mean_breadth_boom = breadth[boom_mask].mean()
                    if pd.notna(mean_breadth_boom) and mean_breadth_boom < 0.55:
                        findings.append("- ⚠️ Boom regime with weak breadth (<55%). Possible calibration gap.\n")
                if slowdown_mask.any() and breadth is not None:
                    mean_breadth_down = breadth[slowdown_mask].mean()
                    if pd.notna(mean_breadth_down) and mean_breadth_down > 0.60:
                        findings.append("- ⚠️ Slowdown/Crisis with strong breadth (>60%). Check gating logic.\n")
    else:
        findings.append("## Macro Regime and Score\n- ❌ No macro_score.parquet found\n")

    return "".join(findings)


def audit_market_alignment():
    findings = []
    live = load_json(MARKET_LIVE_FILE)
    findings.append("## Market Data Alignment (Indices)")
    if live and 'indices' in live:
        sectors = live['indices']
        changes = []
        for name, d in sectors.items():
            last = d.get('last_price', 0)
            chg = d.get('net_change', 0)
            if last:
                changes.append((name, (chg/last)*100))
        if changes:
            series = pd.Series({k:v for k,v in changes})
            findings.append(summarize_series("Sector Change % (snapshot)", series))
        else:
            findings.append("- ⚠️ No valid sector changes in live JSON\n")
    else:
        findings.append("- ⚠️ market_data_latest.json not found or empty\n")
    return "".join(findings)


def audit_scores_and_valuations():
    findings = []
    findings.append("## Scores and Valuations")
    scores = load_parquet(SCORES_FILE)
    if not scores.empty:
        # Detect broken constant scores
        if 'northstar_score' in scores.columns:
            ns = scores['northstar_score'].dropna()
            if len(ns) > 0 and ns.std() < 1e-6:
                findings.append("- ⚠️ northstar_score is constant. Consider switching to raw_score normalization.\n")
        # Distribution checks
        for col in ['northstar_score','raw_score','true_undervaluation']:
            if col in scores.columns:
                findings.append(summarize_series(col, scores[col]))
        # Basic rank sanity: top 1% vs bottom 1% gap
        if 'northstar_score' in scores.columns:
            q99 = scores['northstar_score'].quantile(0.99)
            q01 = scores['northstar_score'].quantile(0.01)
            if pd.notna(q99) and pd.notna(q01) and q99 - q01 < 5:
                findings.append("- ⚠️ Score dispersion very low (p99-p01 < 5). Check scaling.\n")
    else:
        findings.append("- ⚠️ scores.parquet missing or empty\n")

    # Price-return alignment if available
    prices = load_parquet(PRICES_FILE)
    if not prices.empty and 'Date' in prices.columns and 'ticker' in prices.columns and 'Close' in prices.columns:
        # Compute recent returns
        prices = prices.sort_values(['ticker','Date'])
        prices['ret_20d'] = prices.groupby('ticker')['Close'].pct_change(20)
        latest = prices.groupby('ticker').tail(1)[['ticker','ret_20d']]
        if not scores.empty and 'northstar_score' in scores.columns:
            merged = latest.merge(scores[['ticker','northstar_score']], on='ticker', how='inner').dropna()
            if not merged.empty:
                corr = merged['ret_20d'].corr(merged['northstar_score'])
                findings.append(f"- Correlation(20d return, northstar_score): {corr:.3f}\n")
    return "".join(findings)


def audit_summary():
    findings = []
    findings.append("# Northstar V3 Coherence Audit\n\n")
    findings.append(f"Generated: {datetime.now().isoformat()}\n\n")
    findings.append(audit_macro_consistency() + "\n")
    findings.append(audit_market_alignment() + "\n")
    findings.append(audit_scores_and_valuations() + "\n")

    # Key recommendations based on flags
    recommendations = []
    recommendations.append("## Recommendations\n")
    recommendations.append("- Validate MacroScore signs: G+, I-, L+, S-. If violated, revisit weights or z-scores.\n")
    recommendations.append("- Gate regimes with breadth/participation and market_stress_z (already supported). Review thresholds.\n")
    recommendations.append("- Normalize broken constant scores using raw_score percentiles.\n")
    recommendations.append("- Track coherence memory: persist recent contradictions (e.g., Expansion + weak breadth) and downweight conviction.\n")

    findings.append("".join(recommendations))
    return "".join(findings)


def main():
    report_text = audit_summary()
    out_file = os.path.join(REPORTS_DIR, f"coherence_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    with open(out_file, 'w') as f:
        f.write(report_text)
    print(f"✅ Coherence audit report written to: {out_file}")


if __name__ == "__main__":
    main()
