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


def _persist_scores(scored: pd.DataFrame, dt: pd.Timestamp) -> Path:
    out = scored.copy()
    out["score"] = pd.to_numeric(out.get("final_score"), errors="coerce").fillna(0.0)
    out["northstar_score"] = out["score"]
    out["date"] = pd.Timestamp(dt).normalize()
    if "Industry" not in out.columns:
        if "sector" in out.columns:
            out["Industry"] = out["sector"]
        else:
            out["Industry"] = "Unknown"

    keep_cols = [
        "ticker",
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
        "Industry",
    ]
    keep_cols = [c for c in keep_cols if c in out.columns]
    out = out[keep_cols].copy()
    out = out.sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)

    scores_path = REPO_ROOT / "data/processed/scores.parquet"
    scores_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(scores_path, index=False)

    history_dir = REPO_ROOT / "data/processed/score_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"scores_{pd.Timestamp(dt).strftime('%Y%m%d')}.parquet"
    out.to_parquet(history_path, index=False)
    return scores_path


def _load_sequence_payload(path: Path) -> tuple[object, pd.DataFrame]:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("sequence_scoring_requires_torch") from exc
    if not path.exists():
        raise FileNotFoundError(f"sequence_dataset_missing:{path}")
    payload = torch.load(path, map_location="cpu", weights_only=False)
    X = payload.get("X")
    meta = pd.DataFrame(payload.get("metadata", []))
    if X is None or meta.empty:
        raise ValueError("sequence_dataset_invalid_payload")
    if "date" not in meta.columns or "ticker" not in meta.columns:
        raise ValueError("sequence_dataset_metadata_requires_date_ticker")
    meta["date"] = pd.to_datetime(meta["date"], errors="coerce").dt.normalize()
    return X, meta


def _score_sequence_model(dt: pd.Timestamp, model_name: str, sequence_dataset_path: Path) -> pd.DataFrame:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("sequence_scoring_requires_torch") from exc

    model_key = str(model_name or "").strip().lower()
    if model_key not in {"transformer", "tcn"}:
        raise ValueError(f"unsupported_sequence_model:{model_key}")

    X_all, meta = _load_sequence_payload(sequence_dataset_path)
    target_date = pd.Timestamp(dt).normalize()

    mask = meta["date"] == target_date
    if not bool(mask.any()):
        prior_dates = meta.loc[meta["date"] <= target_date, "date"]
        if prior_dates.empty:
            raise ValueError(f"sequence_dataset_no_date_at_or_before:{target_date.date()}")
        use_date = pd.Timestamp(prior_dates.max()).normalize()
        mask = meta["date"] == use_date
    idx = np.where(mask.to_numpy(dtype=bool))[0]
    if len(idx) == 0:
        raise ValueError("sequence_dataset_empty_selection")

    x = X_all[idx]
    meta_sel = meta.iloc[idx].copy().reset_index(drop=True)

    if model_key == "transformer":
        from src.models.stock_transformer import StockTransformer

        ckpt_path = REPO_ROOT / "models/transformer/transformer_latest.pt"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"sequence_model_checkpoint_missing:{ckpt_path}")
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        model = StockTransformer(config=dict(ckpt.get("config", {}) or {}))
        model.load_state_dict(ckpt["state_dict"])
        model.eval()
        x_in = x.float()
    else:
        from src.models.stock_tcn import StockTCN

        ckpt_path = REPO_ROOT / "models/tcn/tcn_latest.pt"
        if not ckpt_path.exists():
            raise FileNotFoundError(f"sequence_model_checkpoint_missing:{ckpt_path}")
        ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        model = StockTCN(config=dict(ckpt.get("config", {}) or {}))
        model.load_state_dict(ckpt["state_dict"])
        model.eval()
        x_in = x.float().transpose(1, 2)

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    model = model.to(device)
    with torch.no_grad():
        pred = model(x_in.to(device)).detach().cpu().numpy().reshape(-1)

    out = pd.DataFrame(
        {
            "ticker": meta_sel["ticker"].astype(str).to_numpy(),
            "date": meta_sel["date"].to_numpy(),
            "regime": meta_sel.get("regime", pd.Series(["unknown"] * len(meta_sel))).astype(str).to_numpy(),
            "model_score": pred,
        }
    )
    out["final_score"] = pd.to_numeric(out["model_score"], errors="coerce").fillna(0.0)
    q = out["final_score"].rank(method="first", pct=True)
    out["quintile"] = np.ceil(q * 5.0).clip(1, 5).astype(int)
    top = out["quintile"].eq(5)
    n_top = int(top.sum())
    out["suggested_weight"] = 0.0
    if n_top > 0:
        out.loc[top, "suggested_weight"] = 1.0 / float(n_top)
    out["sentiment_multiplier"] = 1.0
    out["base_sentiment_multiplier"] = 1.0
    out["macro_multiplier"] = 1.0
    out = out.sort_values("final_score", ascending=False, kind="mergesort").reset_index(drop=True)
    return out


def _print_model_overlap(xgb: pd.DataFrame, tr: pd.DataFrame, tcn: pd.DataFrame) -> None:
    xgb_top = xgb.sort_values("final_score", ascending=False).head(20)
    tr_top = tr.sort_values("final_score", ascending=False).head(20)
    tcn_top = tcn.sort_values("final_score", ascending=False).head(20)

    print("TOP 20 SIDE-BY-SIDE (XGBOOST | TRANSFORMER | TCN):")
    print("Rank | XGBoost      | Transformer  | TCN")
    for i in range(20):
        a = str(xgb_top["ticker"].iloc[i]) if i < len(xgb_top) else ""
        b = str(tr_top["ticker"].iloc[i]) if i < len(tr_top) else ""
        c = str(tcn_top["ticker"].iloc[i]) if i < len(tcn_top) else ""
        print(f"{i+1:>4} | {a:<12} | {b:<12} | {c:<12}")

    overlap = set(xgb_top["ticker"].astype(str)).intersection(
        set(tr_top["ticker"].astype(str))
    ).intersection(set(tcn_top["ticker"].astype(str)))
    print("")
    print("TOP-20 INTERSECTION (all three models):")
    if not overlap:
        print("  None")
    else:
        for tk in sorted(overlap):
            print(f"  {tk}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Northstar v3 morning pipeline")
    p.add_argument("--date", type=str, default="today")
    p.add_argument("--config", type=str, default="config/research_policy.yaml")
    p.add_argument(
        "--model",
        type=str,
        default="xgboost",
        choices=["xgboost", "transformer", "tcn", "all"],
        help="Scoring model to run. 'all' compares XGBoost/Transformer/TCN side by side.",
    )
    p.add_argument(
        "--sequence-dataset",
        type=str,
        default="data/processed/sequence_dataset.pt",
        help="Sequence dataset path used for transformer/tcn morning scoring.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dt = _resolve_date(args.date)
    if pd.isna(dt):
        raise ValueError("invalid --date")

    if args.model in {"transformer", "tcn", "all"}:
        seq_path = Path(args.sequence_dataset)
        if args.model in {"transformer", "tcn"}:
            scored = _score_sequence_model(dt, args.model, seq_path)
            print(f"=== Northstar v3 Morning Pipeline - {dt.date()} ({args.model}) ===")
            print("")
            print("TOP 20 LONG POSITIONS:")
            print("Rank  Ticker         Score   Weight")
            top = scored.head(20)
            for i, (_, r) in enumerate(top.iterrows(), start=1):
                print(
                    f"{i:<5} {str(r['ticker']):<13} {float(r['final_score']):>6.3f}   "
                    f"{_fmt_pct(float(r['suggested_weight'])):>6}"
                )
            return 0

        cfg = _load_config(Path(args.config))
        cfg.setdefault("portfolio_mandate", "long_only")
        xgb = DailyScorer(cfg).score(dt)
        if xgb.empty:
            raise RuntimeError("xgboost_daily_scorer_empty")
        tr = _score_sequence_model(dt, "transformer", seq_path)
        tcn = _score_sequence_model(dt, "tcn", seq_path)
        print(f"=== Northstar v3 Morning Pipeline - {dt.date()} (all models) ===")
        print("")
        _print_model_overlap(xgb, tr, tcn)
        return 0

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
    persisted_scores = _persist_scores(work, dt)
    work["model_score"] = pd.to_numeric(work["model_score"], errors="coerce").fillna(0.0)
    work["sentiment_multiplier"] = pd.to_numeric(work["sentiment_multiplier"], errors="coerce").fillna(1.0)
    base_sent = work.get("base_sentiment_multiplier")
    if base_sent is None:
        base_sent = work["sentiment_multiplier"]
    work["base_sentiment_multiplier"] = pd.to_numeric(base_sent, errors="coerce").fillna(work["sentiment_multiplier"])
    macro_mult = work.get("macro_multiplier")
    if macro_mult is None:
        macro_mult = pd.Series(np.nan, index=work.index, dtype=float)
    work["macro_multiplier"] = pd.to_numeric(macro_mult, errors="coerce").fillna(
        work["sentiment_multiplier"] / work["base_sentiment_multiplier"].replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    work["final_score"] = pd.to_numeric(work["final_score"], errors="coerce").fillna(0.0)
    work["suggested_weight"] = pd.to_numeric(work["suggested_weight"], errors="coerce").fillna(0.0)
    sentiment_polarity = work.get("sentiment_polarity")
    if sentiment_polarity is None:
        sentiment_polarity = pd.Series(np.nan, index=work.index, dtype=float)
    work["sentiment_polarity"] = pd.to_numeric(sentiment_polarity, errors="coerce")
    sentiment_conviction = work.get("sentiment_conviction")
    if sentiment_conviction is None:
        sentiment_conviction = pd.Series(np.nan, index=work.index, dtype=float)
    work["sentiment_conviction"] = pd.to_numeric(sentiment_conviction, errors="coerce")
    news_volume = work.get("news_volume")
    if news_volume is None:
        news_volume = pd.Series(0.0, index=work.index, dtype=float)
    work["news_volume"] = pd.to_numeric(news_volume, errors="coerce").fillna(0.0)

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
    print(f"Scores artifact refreshed: {persisted_scores}")
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
