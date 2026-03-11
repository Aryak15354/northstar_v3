#!/usr/bin/env python3
"""Run Northstar v3 morning regime-aware scoring pipeline."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.scoring.daily_scorer import DailyScorer


def _resolve_date(raw: str) -> pd.Timestamp:
    if str(raw).strip().lower() == "today":
        return pd.Timestamp.today().normalize()
    return pd.to_datetime(raw, errors="coerce").normalize()


def _load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}
    if isinstance(payload, dict) and isinstance(payload.get("historical_research"), dict):
        hr = dict(payload.get("historical_research") or {})
        out = {
            "dataset": dict(hr.get("dataset", {}) or {}),
            "trainer": {},
            "regime": {
                "regime_labels_path": str(hr.get("regime_labels_path", "data/processed/regime_labels.parquet")),
            },
            "sentiment_overlay": {
                "sentiment_path": str(hr.get("dataset", {}).get("sentiment_path", "data/processed/sentiment/ticker_sentiment_daily.parquet")),
                "market_sentiment_path": str(hr.get("dataset", {}).get("market_sentiment_path", "data/processed/sentiment/market_sentiment_daily.parquet")),
                "macro_regime_path": str(hr.get("dataset", {}).get("macro_features_path", "data/processed/macro/macro_regime_features.parquet")),
            },
            "portfolio_mandate": str(hr.get("portfolio_mandate", "long_only") or "long_only"),
        }
        return out
    return {}


def _fmt_pct(v: float) -> str:
    return f"{100.0 * float(v):.1f}%"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Northstar v3 morning pipeline")
    p.add_argument("--date", type=str, default="today")
    p.add_argument("--config", type=str, default="config/research_policy.yaml")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dt = _resolve_date(args.date)
    if pd.isna(dt):
        raise ValueError("invalid --date")

    cfg = _load_config(Path(args.config))
    cfg.setdefault("portfolio_mandate", "long_only")
    scorer = DailyScorer(cfg)
    scored = scorer.score(dt)
    info = scorer.get_last_info()

    regime = str(info.get("regime", "unknown") or "unknown")
    exposure = float(info.get("exposure_scale", 0.0) or 0.0)
    model_meta = dict(info.get("model_meta", {}) or {})

    print(f"=== Northstar v3 Morning Pipeline - {dt.date()} ===")
    print("")
    print(f"Current Regime: {regime}")
    print(f"Regime Exposure Scale: {exposure:.2f} ({'full deployment' if exposure >= 0.99 else 'scaled'})")
    print("")

    model_path = str(model_meta.get("model_path", "NA") or "NA")
    model_name = Path(model_path).name if model_path != "NA" else "NA"
    train_ic = model_meta.get("train_ic")
    oos_ic = model_meta.get("oos_ic")
    print(f"Model: {model_name}")
    print(f"Training IC for this regime: {float(train_ic):.4f}" if train_ic is not None else "Training IC for this regime: NA")
    print(f"OOS IC for this regime: {float(oos_ic):.4f}" if oos_ic is not None else "OOS IC for this regime: NA")
    print("")

    if scored.empty:
        print("No scored universe rows for this date.")
        return 0

    work = scored.copy()
    work["model_score"] = pd.to_numeric(work["model_score"], errors="coerce").fillna(0.0)
    work["sentiment_multiplier"] = pd.to_numeric(work["sentiment_multiplier"], errors="coerce").fillna(1.0)
    work["base_sentiment_multiplier"] = pd.to_numeric(work.get("base_sentiment_multiplier"), errors="coerce").fillna(
        work["sentiment_multiplier"]
    )
    work["macro_multiplier"] = pd.to_numeric(work.get("macro_multiplier"), errors="coerce").fillna(
        work["sentiment_multiplier"] / work["base_sentiment_multiplier"].replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    work["final_score"] = pd.to_numeric(work["final_score"], errors="coerce").fillna(0.0)
    work["suggested_weight"] = pd.to_numeric(work["suggested_weight"], errors="coerce").fillna(0.0)
    work["sentiment_polarity"] = pd.to_numeric(work.get("sentiment_polarity"), errors="coerce")
    work["sentiment_conviction"] = pd.to_numeric(work.get("sentiment_conviction"), errors="coerce")
    work["news_volume"] = pd.to_numeric(work.get("news_volume"), errors="coerce").fillna(0.0)

    sent_cov = float(work["sentiment_polarity"].notna().mean()) if len(work) else 0.0
    sent_nonzero = int((work["sentiment_polarity"].fillna(0.0).abs() > 1e-12).sum())
    neg_count = int((work["sentiment_polarity"].fillna(0.0) < -0.2).sum())
    distress_count = int((work["sentiment_polarity"].fillna(0.0) < -0.5).sum())
    print(
        f"Sentiment coverage: {100.0 * sent_cov:.1f}% | nonzero polarity: {sent_nonzero}/{len(work)} "
        f"| < -0.2: {neg_count} | < -0.5: {distress_count}"
    )
    sent_dist = work["base_sentiment_multiplier"].round(3).value_counts().sort_index()
    macro_dist = work["macro_multiplier"].round(3).value_counts().sort_index()
    print(f"Base sentiment multipliers: {sent_dist.to_dict()}")
    print(f"Macro multipliers: {macro_dist.to_dict()}")
    print("")

    longs = work[work["suggested_weight"] > 0].sort_values("final_score", ascending=False).head(20)
    print("TOP 20 LONG POSITIONS:")
    print("Rank  Ticker         Score   Sent    Macro   Final   Weight")
    for i, (_, r) in enumerate(longs.iterrows(), start=1):
        print(
            f"{i:<5} {str(r['ticker']):<13} {float(r['model_score']):>6.2f}   "
            f"{float(r['base_sentiment_multiplier']):>5.2f}   {float(r['macro_multiplier']):>5.2f}   "
            f"{float(r['final_score']):>6.2f}   {_fmt_pct(float(r['suggested_weight'])):>6}"
        )

    print("")
    print("BOTTOM 20 (avoid/short):")
    bottoms = work.sort_values("final_score", ascending=True).head(20)
    for i, (_, r) in enumerate(bottoms.iterrows(), start=1):
        print(
            f"{i:<5} {str(r['ticker']):<13} {float(r['model_score']):>6.2f}   "
            f"{float(r['base_sentiment_multiplier']):>5.2f}   {float(r['macro_multiplier']):>5.2f}   "
            f"{float(r['final_score']):>6.2f}   {_fmt_pct(float(r['suggested_weight'])):>6}"
        )

    print("")
    print("DISTRESS ALERTS (zeroed):")
    distress = work[(work.get("sentiment_override", False).fillna(False)) | (work["sentiment_multiplier"] <= 0.0)]
    if distress.empty:
        print("  None")
    else:
        for _, r in distress.iterrows():
            reason = str(r.get("override_reason", "distress"))
            print(f"  {str(r['ticker']):<13} {reason}")

    print("")
    print("Portfolio stats:")
    n_longs = int((work["suggested_weight"] > 0).sum())
    total_long = float(work.loc[work["suggested_weight"] > 0, "suggested_weight"].sum())
    if "sector" in work.columns and n_longs > 0:
        sec = (
            work.loc[work["suggested_weight"] > 0]
            .groupby("sector", as_index=False)["suggested_weight"]
            .sum()
            .sort_values("suggested_weight", ascending=False)
        )
        max_sec = float(sec["suggested_weight"].max()) if not sec.empty else 0.0
    else:
        max_sec = 0.0

    print(f"  Long positions: {n_longs}")
    print(f"  Total long weight: {_fmt_pct(total_long)}")
    compliant = "COMPLIANT" if max_sec <= 0.25 + 1e-12 else "BREACH"
    print(f"  Sector concentration: max {_fmt_pct(max_sec)} ({compliant})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
