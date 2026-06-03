#!/usr/bin/env python3
"""Generate canonical live scores via DailyScorer.

This bridges live and research by deriving `data/processed/scores.parquet`
from `src.scoring.daily_scorer.DailyScorer` instead of `northstar_model`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
        return {
            "dataset": dict(hr.get("dataset", {}) or {}),
            "trainer": {},
            "regime": {
                "regime_labels_path": str(
                    hr.get("regime_labels_path", "data/processed/regime_labels.parquet")
                ),
            },
            "sentiment_overlay": {
                "sentiment_path": str(
                    hr.get("dataset", {}).get(
                        "sentiment_path",
                        "data/processed/sentiment/ticker_sentiment_daily.parquet",
                    )
                ),
                "market_sentiment_path": str(
                    hr.get("dataset", {}).get(
                        "market_sentiment_path",
                        "data/processed/sentiment/market_sentiment_daily.parquet",
                    )
                ),
                "macro_regime_path": str(
                    hr.get("dataset", {}).get(
                        "macro_features_path",
                        "data/processed/macro/macro_regime_features.parquet",
                    )
                ),
            },
            "portfolio_mandate": str(hr.get("portfolio_mandate", "long_only") or "long_only"),
        }
    return dict(payload) if isinstance(payload, dict) else {}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate scores.parquet from DailyScorer")
    p.add_argument("--date", type=str, default="today")
    p.add_argument("--config", type=str, default="config/research_policy.yaml")
    p.add_argument("--output", type=str, default="data/processed/scores.parquet")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dt = _resolve_date(args.date)
    if pd.isna(dt):
        raise ValueError("invalid --date")

    cfg = _load_config(REPO_ROOT / args.config)
    cfg.setdefault("portfolio_mandate", "long_only")

    scorer = DailyScorer(cfg)
    try:
        scored = scorer.score(dt)
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "DailyScorer failed to load model backend dependency "
            f"({exc}). Install the missing package in the runtime environment."
        ) from exc
    if scored.empty:
        raise RuntimeError("daily_scorer returned empty universe")

    out = scored.copy()
    if "ticker" not in out.columns:
        raise RuntimeError("daily_scorer output missing ticker column")

    out["score"] = pd.to_numeric(out.get("final_score"), errors="coerce").fillna(0.0)
    out["northstar_score"] = out["score"]
    out["date"] = pd.Timestamp(dt).normalize()
    if "Industry" not in out.columns:
        if "sector" in out.columns:
            out["Industry"] = out["sector"]
        else:
            out["Industry"] = "Unknown"
    if "Company Name" not in out.columns:
        out["Company Name"] = out["ticker"].astype(str)

    keep_cols = [
        "ticker",
        "Company Name",
        "Industry",
        "date",
        "northstar_score",
        "score",
        "final_score",
        "model_score",
        "regime",
        "sentiment_multiplier",
        "base_sentiment_multiplier",
        "macro_multiplier",
        "suggested_weight",
        "quintile",
        "sector",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols].copy()
    out = out.sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)

    out_path = REPO_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    history_dir = REPO_ROOT / "data" / "processed" / "score_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"scores_{pd.Timestamp(dt).strftime('%Y%m%d')}.parquet"
    out.to_parquet(history_path, index=False)

    print(
        f"DailyScorer scores generated: rows={len(out)} date={dt.date()} output={out_path} history={history_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
