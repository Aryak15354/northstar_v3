#!/usr/bin/env python3
"""
Build cohesive alpha feed (real-data-first) for macro-edge integration.

Inputs:
- data/processed/scores.parquet
- data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet (optional)
- data/alpha/latest_alpha_results.json (optional positional overlay)
- data/sentiment/v3/company_sentiment_trends.parquet (optional sentiment overlay)

Outputs:
- data/processed/cohesive_alpha_feed.parquet
- data/processed/cohesive_alpha_feed.csv
- data/processed/cohesive_alpha_feed_metadata.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.sentiment.context_loader import load_company_sentiment_scores


def _zscore(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    mu = float(x.mean()) if np.isfinite(x.mean()) else 0.0
    sigma = float(x.std()) if np.isfinite(x.std()) else 0.0
    if sigma <= 1e-12:
        return pd.Series(np.zeros(len(x)), index=x.index, dtype=float)
    return (x - mu) / sigma


def _load_scores(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required score source: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"Score source is empty: {path}")
    if "ticker" not in df.columns:
        raise ValueError(f"Score source must contain ticker column: {path}")
    candidates = ["northstar_score", "final_score", "score", "raw_score"]
    score_col = next((c for c in candidates if c in df.columns), None)
    if score_col is None:
        raise ValueError(
            f"Score source has no supported score column ({candidates}): {path}"
        )
    out = df[["ticker", score_col]].copy()
    out = out.rename(columns={score_col: "northstar_score"})
    out["ticker"] = out["ticker"].astype(str).str.strip()
    out["northstar_score"] = pd.to_numeric(out["northstar_score"], errors="coerce")
    out = out.dropna(subset=["ticker", "northstar_score"]).drop_duplicates("ticker", keep="last")
    if out.empty:
        raise ValueError(f"No valid rows in score source after cleanup: {path}")
    return out


def _load_macro_conditioned_snapshot(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    if df.empty:
        return None
    if "asset_id" not in df.columns:
        return None
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        latest_date = df["date"].max()
        if pd.notna(latest_date):
            df = df[df["date"] == latest_date].copy()
    col = None
    for c in ["signal_composite_regime", "signal_composite_equal"]:
        if c in df.columns:
            col = c
            break
    if col is None:
        return None
    out = df[["asset_id", col]].copy()
    out = out.rename(columns={"asset_id": "ticker", col: "macro_conditioned_score"})
    out["ticker"] = out["ticker"].astype(str).str.strip()
    out["macro_conditioned_score"] = pd.to_numeric(out["macro_conditioned_score"], errors="coerce")
    out = out.dropna(subset=["ticker", "macro_conditioned_score"]).drop_duplicates("ticker", keep="last")
    return out if not out.empty else None


def _load_institutional_positions(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return None
    positions = payload.get("positions") or {}
    if not isinstance(positions, dict) or not positions:
        return None
    out = pd.DataFrame(
        {"ticker": list(positions.keys()), "institutional_position": list(positions.values())}
    )
    out["ticker"] = out["ticker"].astype(str).str.strip()
    out["institutional_position"] = pd.to_numeric(out["institutional_position"], errors="coerce")
    out = out.dropna(subset=["ticker", "institutional_position"]).drop_duplicates("ticker", keep="last")
    return out if not out.empty else None


def _load_sentiment_overlay(path: Path) -> Optional[pd.DataFrame]:
    """
    Load ticker-level sentiment overlay for cross-system alpha conditioning.
    """
    # Prefer canonical shared loader (handles schema variants and signal construction).
    try:
        sentiment_df = load_company_sentiment_scores(
            project_root=Path.cwd(),
            top_companies_limit=4000,
        )
        if isinstance(sentiment_df, pd.DataFrame) and not sentiment_df.empty:
            out = sentiment_df[["ticker", "sentiment_signal"]].copy()
            out["ticker"] = out["ticker"].astype(str).str.strip()
            out["sentiment_signal"] = pd.to_numeric(out["sentiment_signal"], errors="coerce")
            out = out.dropna(subset=["ticker", "sentiment_signal"]).drop_duplicates("ticker", keep="last")
            if not out.empty:
                return out
    except Exception:
        pass

    # Fallback for custom path users (keeps backward compatibility).
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if not isinstance(df, pd.DataFrame) or df.empty or "ticker" not in df.columns:
        return None
    out = df.copy()
    out["ticker"] = out["ticker"].astype(str).str.replace(".NS", "", regex=False).str.strip().str.upper()
    if "signed_sentiment_intensity" in out.columns:
        signal = pd.to_numeric(out["signed_sentiment_intensity"], errors="coerce")
    elif "sentiment_score" in out.columns:
        signal = pd.to_numeric(out["sentiment_score"], errors="coerce")
    else:
        return None
    out["sentiment_signal"] = signal
    out = out.dropna(subset=["ticker", "sentiment_signal"]).drop_duplicates("ticker", keep="last")
    if out.empty:
        return None
    return out[["ticker", "sentiment_signal"]]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build cohesive alpha feed")
    p.add_argument("--scores", type=str, default="data/processed/scores.parquet")
    p.add_argument(
        "--macro-conditioned",
        type=str,
        default="data/processed/macro_conditioned_alpha/latest_macro_conditioned_signal_snapshot.parquet",
    )
    p.add_argument("--institutional-json", type=str, default="data/alpha/latest_alpha_results.json")
    p.add_argument("--sentiment-company-trends", type=str, default="data/sentiment/v3/company_sentiment_trends.parquet")
    p.add_argument("--output", type=str, default="data/processed/cohesive_alpha_feed.parquet")
    p.add_argument("--northstar-weight", type=float, default=0.55)
    p.add_argument("--macro-weight", type=float, default=0.35)
    p.add_argument("--institutional-weight", type=float, default=0.10)
    p.add_argument("--sentiment-weight", type=float, default=0.10)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scores = _load_scores(Path(args.scores))
    merged = scores.copy()

    macro_cond = _load_macro_conditioned_snapshot(Path(args.macro_conditioned))
    if macro_cond is not None:
        merged = merged.merge(macro_cond, on="ticker", how="left")

    inst = _load_institutional_positions(Path(args.institutional_json))
    if inst is not None:
        merged = merged.merge(inst, on="ticker", how="left")

    sentiment = _load_sentiment_overlay(Path(args.sentiment_company_trends))
    if sentiment is not None:
        merged = merged.merge(sentiment, on="ticker", how="left")

    merged["northstar_z"] = _zscore(merged["northstar_score"])
    if "macro_conditioned_score" in merged.columns:
        merged["macro_conditioned_z"] = _zscore(merged["macro_conditioned_score"])
    else:
        merged["macro_conditioned_z"] = np.nan
    if "institutional_position" in merged.columns:
        merged["institutional_position_z"] = _zscore(merged["institutional_position"])
    else:
        merged["institutional_position_z"] = np.nan
    if "sentiment_signal" in merged.columns:
        merged["sentiment_z"] = _zscore(merged["sentiment_signal"])
    else:
        merged["sentiment_z"] = np.nan

    available_weight_sum = (
        float(args.northstar_weight)
        + (float(args.macro_weight) if merged["macro_conditioned_z"].notna().any() else 0.0)
        + (float(args.institutional_weight) if merged["institutional_position_z"].notna().any() else 0.0)
        + (float(args.sentiment_weight) if merged["sentiment_z"].notna().any() else 0.0)
    )
    if available_weight_sum <= 0:
        raise RuntimeError("No alpha sources available to build cohesive feed")

    w_north = float(args.northstar_weight) / available_weight_sum
    w_macro = (
        float(args.macro_weight) / available_weight_sum
        if merged["macro_conditioned_z"].notna().any()
        else 0.0
    )
    w_inst = (
        float(args.institutional_weight) / available_weight_sum
        if merged["institutional_position_z"].notna().any()
        else 0.0
    )
    w_sentiment = (
        float(args.sentiment_weight) / available_weight_sum
        if merged["sentiment_z"].notna().any()
        else 0.0
    )

    merged["cohesive_alpha_score"] = (
        w_north * merged["northstar_z"].fillna(0.0)
        + w_macro * merged["macro_conditioned_z"].fillna(0.0)
        + w_inst * merged["institutional_position_z"].fillna(0.0)
        + w_sentiment * merged["sentiment_z"].fillna(0.0)
    )

    merged["cohesive_alpha_rank"] = merged["cohesive_alpha_score"].rank(ascending=False, method="average")
    merged["as_of"] = pd.Timestamp.utcnow()
    merged = merged.sort_values("cohesive_alpha_score", ascending=False).reset_index(drop=True)

    merged.to_parquet(out_path, index=False)
    merged.to_csv(out_path.with_suffix(".csv"), index=False)

    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "inputs": {
            "scores": str(Path(args.scores)),
            "macro_conditioned": str(Path(args.macro_conditioned)),
            "institutional_json": str(Path(args.institutional_json)),
            "sentiment_company_trends": str(Path(args.sentiment_company_trends)),
        },
        "rows": int(len(merged)),
        "weights_effective": {
            "northstar": w_north,
            "macro_conditioned": w_macro,
            "institutional_position": w_inst,
            "sentiment": w_sentiment,
        },
        "coverage": {
            "northstar_non_null": int(merged["northstar_score"].notna().sum()),
            "macro_conditioned_non_null": int(merged["macro_conditioned_z"].notna().sum()),
            "institutional_position_non_null": int(merged["institutional_position_z"].notna().sum()),
            "sentiment_non_null": int(merged["sentiment_z"].notna().sum()),
        },
    }
    (out_path.parent / "cohesive_alpha_feed_metadata.json").write_text(json.dumps(metadata, indent=2))

    print("✅ Cohesive alpha feed generated")
    print(f"   Output: {out_path}")
    print(f"   Rows: {len(merged)}")
    print(
        "   Effective weights:",
        (
            f"northstar={w_north:.2f}, macro={w_macro:.2f}, "
            f"institutional={w_inst:.2f}, sentiment={w_sentiment:.2f}"
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
