#!/usr/bin/env python3
"""Build Northstar V3 sequence tensors on Kaggle.

This script intentionally builds the heavy LSTM/GRU/TFT/iTransformer-ready
dataset from canonical raw inputs on Kaggle rather than on a small local Mac.
It includes prices, cross-asset macro, RBI/GST/power macro, news sentiment,
company sentiment, alternative events, fundamentals/static weekly features, and
walk-forward split metadata.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TARGET_COL = "target_weekly_return"
POST_INDAS_ANCHOR = pd.Timestamp("2021-04-01")
DEFAULT_LOOKBACK = 60
DEFAULT_SHARD_SIZE = 8192


def log(msg: str) -> None:
    print(msg, flush=True)


def json_safe(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if not np.isfinite(obj) else float(obj)
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    return obj


def resolve_dir(user_path: str | None, candidates: list[str], required: str) -> Path:
    if user_path:
        path = Path(user_path).expanduser().resolve()
        if (path / required).exists():
            return path
        raise FileNotFoundError(f"{required} not found in {path}")
    for raw in candidates:
        path = Path(raw)
        if (path / required).exists():
            return path.resolve()
    root = Path("/kaggle/input")
    if root.exists():
        for found in root.rglob(required):
            return found.parent.resolve()
    raise FileNotFoundError(f"Could not resolve directory containing {required}")


def read_parquet_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        log(f"  MISSING optional source: {path}")
        return pd.DataFrame()
    return pd.read_parquet(path)


def normalize_ticker(series: pd.Series) -> pd.Series:
    out = series.astype(str).str.strip()
    out = out.where(out.str.endswith(".NS"), out + ".NS")
    return out


def add_price_features(prices: pd.DataFrame) -> pd.DataFrame:
    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    prices["ticker"] = normalize_ticker(prices["ticker"])
    prices = prices.sort_values(["ticker", "date"], kind="mergesort")
    for col in ["open", "high", "low", "close", "volume"]:
        prices[col] = pd.to_numeric(prices[col], errors="coerce").astype("float32")
    g = prices.groupby("ticker", sort=False)
    prices["px_ret_1d"] = g["close"].pct_change()
    prices["px_logret_1d"] = np.log(prices["close"].clip(lower=1e-6)).groupby(prices["ticker"]).diff()
    prices["px_ret_5d"] = g["close"].pct_change(5)
    prices["px_ret_20d"] = g["close"].pct_change(20)
    prices["px_hl_range"] = (prices["high"] - prices["low"]) / prices["close"].replace(0, np.nan)
    prices["px_close_to_open"] = (prices["close"] - prices["open"]) / prices["open"].replace(0, np.nan)
    prices["px_volume_log"] = np.log1p(prices["volume"].clip(lower=0))
    vol_mean = g["volume"].transform(lambda s: s.rolling(20, min_periods=5).mean())
    vol_std = g["volume"].transform(lambda s: s.rolling(20, min_periods=5).std())
    prices["px_volume_z20"] = (prices["volume"] - vol_mean) / (vol_std + 1e-8)
    prices["px_volatility_5d"] = g["px_ret_1d"].transform(lambda s: s.rolling(5, min_periods=3).std())
    prices["px_volatility_20d"] = g["px_ret_1d"].transform(lambda s: s.rolling(20, min_periods=10).std())
    prices["px_dollar_volume_log"] = np.log1p((prices["close"] * prices["volume"]).clip(lower=0))
    keep = [
        "date",
        "ticker",
        "px_ret_1d",
        "px_logret_1d",
        "px_ret_5d",
        "px_ret_20d",
        "px_hl_range",
        "px_close_to_open",
        "px_volume_log",
        "px_volume_z20",
        "px_volatility_5d",
        "px_volatility_20d",
        "px_dollar_volume_log",
    ]
    return prices[keep]


def build_cross_asset_features(canonical_dir: Path) -> pd.DataFrame:
    path = canonical_dir / "macro" / "cross_asset_prices_daily.parquet"
    raw = read_parquet_if_exists(path)
    if raw.empty:
        return pd.DataFrame(columns=["date"])
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw["close"] = pd.to_numeric(raw.get("close"), errors="coerce")
    wanted = {
        "USDINR=X": "usd_inr",
        "CL=F": "crude",
        "GC=F": "gold",
        "HG=F": "copper",
        "HRC=F": "steel",
        "DX-Y.NYB": "dxy",
        "^TNX": "us10y",
    }
    raw = raw[raw["symbol"].isin(wanted)].copy()
    raw["name"] = raw["symbol"].map(wanted)
    wide = raw.pivot_table(index="date", columns="name", values="close", aggfunc="last").sort_index()
    out = pd.DataFrame(index=wide.index)
    for col in wide.columns:
        ret_1d = wide[col].pct_change(fill_method=None)
        out[f"xasset_{col}_ret_1d"] = ret_1d
        out[f"xasset_{col}_ret_5d"] = wide[col].pct_change(5, fill_method=None)
        out[f"xasset_{col}_vol_20d"] = ret_1d.rolling(20, min_periods=10).std()
    return out.reset_index()


def build_rbi_features(canonical_dir: Path) -> pd.DataFrame:
    raw = read_parquet_if_exists(canonical_dir / "macro" / "rbi_macro_wide.parquet")
    if raw.empty:
        return pd.DataFrame(columns=["date"])
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    keys = [
        "policy_repo_rate",
        "reverse_repo_rate",
        "standing_deposit_facility",
        "cash_reserve_ratio",
        "credit_deposit_ratio",
        "consumer_price_index",
        "foreign_exchange_reserves",
        "net_portfolio_investment",
        "rbi_s_reference_rate_inr_per_usd",
        "10_year_g_sec_yield",
        "nse_s_and_p_cnx_nifty",
    ]
    selected = ["date"]
    for col in raw.columns:
        low = col.lower()
        if any(k in low for k in keys) and pd.api.types.is_numeric_dtype(raw[col]):
            selected.append(col)
    selected = selected[:31]
    out = raw[selected].sort_values("date").copy()
    rename = {c: "rbi_" + c.split("__")[-1][:48] for c in selected if c != "date"}
    out = out.rename(columns=rename)
    return out


def build_monthly_macro_features(canonical_dir: Path) -> pd.DataFrame:
    frames = []
    for rel in [
        "macro/macro_regime_features.parquet",
        "macro/gst_ewaybill_market_monthly.parquet",
        "macro/cea_power_daily.parquet",
    ]:
        df = read_parquet_if_exists(canonical_dir / rel)
        if df.empty or "date" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        numeric = [c for c in df.columns if c != "date" and pd.api.types.is_numeric_dtype(df[c])]
        prefix = rel.split("/")[-1].replace(".parquet", "")
        part = df[["date"] + numeric].copy()
        part = part.rename(columns={c: f"{prefix}_{c}" for c in numeric})
        frames.append(part.groupby("date", as_index=False).mean(numeric_only=True))
    if not frames:
        return pd.DataFrame(columns=["date"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer", sort=False)
    return out.sort_values("date")


def build_sentiment_features(canonical_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    company = read_parquet_if_exists(canonical_dir / "sentiment" / "company_sentiment_daily.parquet")
    if not company.empty:
        company["date"] = pd.to_datetime(company.get("availability_date", company["date"])).dt.normalize()
        company["ticker"] = normalize_ticker(company["ticker"])
        numeric = [c for c in company.columns if pd.api.types.is_numeric_dtype(company[c])]
        company = company.groupby(["date", "ticker"], as_index=False)[numeric].mean()
        company = company.rename(columns={c: f"sent_company_{c}" for c in numeric})
        company = add_rolling_by_ticker(company, [c for c in company.columns if c.startswith("sent_company_")], [5, 20])
    else:
        company = pd.DataFrame(columns=["date", "ticker"])

    market = read_parquet_if_exists(canonical_dir / "sentiment" / "market_sentiment_daily.parquet")
    if not market.empty:
        market["date"] = pd.to_datetime(market.get("availability_date", market["date"])).dt.normalize()
        numeric = [c for c in market.columns if pd.api.types.is_numeric_dtype(market[c])]
        market = market.groupby("date", as_index=False)[numeric].mean()
        market = market.rename(columns={c: f"sent_market_{c}" for c in numeric})
    else:
        market = pd.DataFrame(columns=["date"])
    return company, market


def add_rolling_by_ticker(df: pd.DataFrame, cols: list[str], windows: list[int]) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.sort_values(["ticker", "date"], kind="mergesort").copy()
    g = df.groupby("ticker", sort=False)
    for col in cols:
        for window in windows:
            df[f"{col}_sum{window}d"] = g[col].transform(lambda s: s.rolling(window, min_periods=1).sum())
            df[f"{col}_mean{window}d"] = g[col].transform(lambda s: s.rolling(window, min_periods=1).mean())
    return df


def build_news_features(canonical_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    company = read_parquet_if_exists(canonical_dir / "news" / "company_news_history.parquet")
    if not company.empty:
        company["date"] = pd.to_datetime(company.get("availability_date", company["date"])).dt.normalize()
        company["ticker"] = normalize_ticker(company["ticker"])
        company["news_company_count"] = 1.0
        for col in ["sentiment_score", "sentiment_conviction"]:
            company[col] = pd.to_numeric(company.get(col), errors="coerce")
        company = company.groupby(["date", "ticker"], as_index=False).agg(
            news_company_count=("news_company_count", "sum"),
            news_company_sentiment_score=("sentiment_score", "mean"),
            news_company_sentiment_conviction=("sentiment_conviction", "mean"),
        )
        company = add_rolling_by_ticker(company, ["news_company_count", "news_company_sentiment_score"], [5, 20])
    else:
        company = pd.DataFrame(columns=["date", "ticker"])

    market = read_parquet_if_exists(canonical_dir / "news" / "market_news_history.parquet")
    if not market.empty:
        market["date"] = pd.to_datetime(market.get("availability_date", market["date"])).dt.normalize()
        market["news_market_count"] = 1.0
        market = market.groupby("date", as_index=False).agg(news_market_count=("news_market_count", "sum"))
    else:
        market = pd.DataFrame(columns=["date"])
    return company, market


def build_alternative_features(canonical_dir: Path) -> pd.DataFrame:
    frames = []
    events = read_parquet_if_exists(canonical_dir / "alternative" / "nse_alternative_events.parquet")
    if not events.empty:
        events["date"] = pd.to_datetime(events.get("availability_date", events.get("event_date"))).dt.normalize()
        events["ticker"] = normalize_ticker(events["ticker"])
        events["alt_event_count"] = 1.0
        events["signal_strength"] = pd.to_numeric(events.get("signal_strength"), errors="coerce")
        agg = events.groupby(["date", "ticker"], as_index=False).agg(
            alt_event_count=("alt_event_count", "sum"),
            alt_signal_strength_sum=("signal_strength", "sum"),
            alt_signal_strength_mean=("signal_strength", "mean"),
        )
        frames.append(agg)

    bulk = read_parquet_if_exists(canonical_dir / "alternative" / "bulk_deals_nse_all.parquet")
    if not bulk.empty:
        bulk["date"] = pd.to_datetime(bulk.get("availability_date", bulk["date"])).dt.normalize()
        bulk["ticker"] = normalize_ticker(bulk.get("nse_ticker", bulk.get("symbol")))
        bulk["bulk_deal_count"] = 1.0
        bulk["signed_notional"] = pd.to_numeric(bulk.get("signed_notional"), errors="coerce")
        frames.append(
            bulk.groupby(["date", "ticker"], as_index=False).agg(
                bulk_deal_count=("bulk_deal_count", "sum"),
                bulk_signed_notional_sum=("signed_notional", "sum"),
            )
        )

    ann = read_parquet_if_exists(canonical_dir / "alternative" / "announcements_all.parquet")
    if not ann.empty:
        ann["date"] = pd.to_datetime(ann.get("availability_date", ann["date"])).dt.normalize()
        ann["ticker"] = normalize_ticker(ann.get("nse_ticker", ann.get("symbol")))
        ann["announcement_count"] = 1.0
        frames.append(ann.groupby(["date", "ticker"], as_index=False).agg(announcement_count=("announcement_count", "sum")))

    pledge = read_parquet_if_exists(canonical_dir / "alternative" / "promoter_pledge_all.parquet")
    if not pledge.empty:
        pledge["date"] = pd.to_datetime(pledge.get("availability_date", pledge["date"])).dt.normalize()
        pledge["ticker"] = normalize_ticker(pledge["nse_ticker"])
        keep = ["date", "ticker"] + [c for c in ["pledge_pct", "pledge_value_cr", "total_promoter_holding_pct"] if c in pledge.columns]
        frames.append(pledge[keep].groupby(["date", "ticker"], as_index=False).last())

    ratings = read_parquet_if_exists(canonical_dir / "alternative" / "credit_ratings_nse_all.parquet")
    if not ratings.empty:
        ratings["date"] = pd.to_datetime(ratings.get("availability_date", ratings["date"])).dt.normalize()
        ratings["ticker"] = normalize_ticker(ratings["nse_ticker"])
        keep = ["date", "ticker"] + [c for c in ["rating_numeric"] if c in ratings.columns]
        frames.append(ratings[keep].groupby(["date", "ticker"], as_index=False).last())

    if not frames:
        return pd.DataFrame(columns=["date", "ticker"])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on=["date", "ticker"], how="outer", sort=False)
    numeric = [c for c in out.columns if c not in {"date", "ticker"} and pd.api.types.is_numeric_dtype(out[c])]
    out = add_rolling_by_ticker(out, numeric, [5, 20])
    return out


def build_daily_panel(canonical_dir: Path, tickers: list[str]) -> tuple[pd.DataFrame, list[str]]:
    log("Loading and featurising daily prices...")
    prices = pd.read_parquet(canonical_dir / "prices" / "equity_prices_daily.parquet")
    prices["ticker"] = normalize_ticker(prices["ticker"])
    prices = prices[prices["ticker"].isin(tickers)].copy()
    panel = add_price_features(prices)

    company_sent, market_sent = build_sentiment_features(canonical_dir)
    company_news, market_news = build_news_features(canonical_dir)
    alt = build_alternative_features(canonical_dir)
    xasset = build_cross_asset_features(canonical_dir)
    rbi = build_rbi_features(canonical_dir)
    macro = build_monthly_macro_features(canonical_dir)

    log("Merging sequence feature groups...")
    for frame in [company_sent, company_news, alt]:
        if not frame.empty:
            panel = panel.merge(frame, on=["date", "ticker"], how="left", sort=False)
    for frame in [market_sent, market_news, xasset, rbi, macro]:
        if not frame.empty:
            panel = panel.merge(frame, on="date", how="left", sort=False)

    panel = panel.sort_values(["ticker", "date"], kind="mergesort")
    feature_cols = [c for c in panel.columns if c not in {"date", "ticker"} and pd.api.types.is_numeric_dtype(panel[c])]

    # Event/count features are zero when absent; continuous sparse sources are forward-filled.
    zero_cols = [c for c in feature_cols if any(k in c for k in ["count", "sum", "notional", "news_", "alt_"])]
    ffill_cols = [c for c in feature_cols if c not in set(zero_cols)]
    if ffill_cols:
        panel[ffill_cols] = panel.groupby("ticker", sort=False)[ffill_cols].ffill()
    if zero_cols:
        panel[zero_cols] = panel[zero_cols].fillna(0.0)
    panel[feature_cols] = panel[feature_cols].replace([np.inf, -np.inf], np.nan)
    return panel, feature_cols


def build_static_features(feature_dir: Path, samples: pd.DataFrame) -> pd.DataFrame:
    weekly = pd.read_parquet(feature_dir / "northstar_features.parquet")
    weekly["date"] = pd.to_datetime(weekly["date"]).dt.normalize()
    weekly["ticker"] = normalize_ticker(weekly["ticker"])
    numeric = [c for c in weekly.columns if c not in {"date", "ticker", TARGET_COL} and pd.api.types.is_numeric_dtype(weekly[c])]
    out = samples[["sample_id", "date", "ticker"]].merge(weekly[["date", "ticker"] + numeric], on=["date", "ticker"], how="left", sort=False)
    return out


def write_shards(
    panel: pd.DataFrame,
    feature_cols: list[str],
    samples: pd.DataFrame,
    out_dir: Path,
    *,
    lookback: int,
    shard_size: int,
    compress: bool,
) -> dict[str, Any]:
    shard_dir = out_dir / "sequence_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    panel = panel.sort_values(["ticker", "date"], kind="mergesort")
    ticker_arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for ticker, group in panel.groupby("ticker", sort=False):
        dates = pd.to_datetime(group["date"]).to_numpy(dtype="datetime64[ns]")
        values = group[feature_cols].to_numpy(dtype="float32", copy=True)
        ticker_arrays[str(ticker)] = (dates, values)

    kept_rows = []
    shard_meta = []
    X_buf: list[np.ndarray] = []
    M_buf: list[np.ndarray] = []
    y_buf: list[float] = []
    idx_buf: list[int] = []

    def flush(shard_id: int) -> None:
        if not X_buf:
            return
        X = np.stack(X_buf).astype("float32")
        M = np.stack(M_buf).astype("uint8")
        y = np.asarray(y_buf, dtype="float32")
        idx = np.asarray(idx_buf, dtype="int64")
        path = shard_dir / f"seq_shard_{shard_id:04d}.npz"
        if compress:
            np.savez_compressed(path, X_temporal=X, X_mask=M, y=y, sample_id=idx)
        else:
            np.savez(path, X_temporal=X, X_mask=M, y=y, sample_id=idx)
        shard_meta.append({"shard": path.name, "rows": int(len(y)), "x_shape": list(X.shape)})
        X_buf.clear()
        M_buf.clear()
        y_buf.clear()
        idx_buf.clear()

    shard_id = 0
    for row in samples.itertuples(index=False):
        ticker = str(row.ticker)
        if ticker not in ticker_arrays:
            continue
        dates, values = ticker_arrays[ticker]
        pos = int(np.searchsorted(dates, np.datetime64(pd.Timestamp(row.date)), side="right")) - 1
        start = pos - lookback + 1
        if start < 0:
            continue
        window = values[start : pos + 1]
        if window.shape[0] != lookback:
            continue
        mask = np.isfinite(window).astype("uint8")
        window = np.nan_to_num(window, nan=0.0, posinf=0.0, neginf=0.0).astype("float32")
        X_buf.append(window)
        M_buf.append(mask)
        y_buf.append(float(row.target))
        idx_buf.append(int(row.sample_id))
        kept_rows.append(row._asdict())
        if len(y_buf) >= shard_size:
            flush(shard_id)
            shard_id += 1
    flush(shard_id)
    kept = pd.DataFrame(kept_rows)
    kept.to_parquet(out_dir / "sample_index.parquet", index=False)
    return {"samples_kept": int(len(kept)), "shards": shard_meta}


def build_splits(feature_dir: Path, sample_index: pd.DataFrame, out_dir: Path) -> list[dict[str, Any]]:
    raw = json.loads((feature_dir / "northstar_walk_forward_splits.json").read_text())
    windows = raw.get("windows", raw) if isinstance(raw, dict) else raw
    available_ids = set(sample_index["sample_id"].astype(int).tolist())
    rows = []
    for i, split in enumerate(windows, start=1):
        train_start = max(pd.Timestamp(split["test_start"]) - pd.Timedelta(weeks=104), POST_INDAS_ANCHOR)
        train_end = pd.Timestamp(split["train_end"])
        test_start = pd.Timestamp(split["test_start"])
        test_end = pd.Timestamp(split["test_end"])
        train_ids = sample_index.loc[(sample_index["date"] >= train_start) & (sample_index["date"] <= train_end), "sample_id"].astype(int).tolist()
        test_ids = sample_index.loc[(sample_index["date"] >= test_start) & (sample_index["date"] <= test_end), "sample_id"].astype(int).tolist()
        train_ids = [x for x in train_ids if x in available_ids]
        test_ids = [x for x in test_ids if x in available_ids]
        if not train_ids or not test_ids:
            continue
        rows.append(
            {
                "window_id": len(rows) + 1,
                "source_window_id": split.get("window_id", i),
                "train_start": str(train_start.date()),
                "train_end": str(train_end.date()),
                "test_start": str(test_start.date()),
                "test_end": str(test_end.date()),
                "train_sample_ids": train_ids,
                "test_sample_ids": test_ids,
                "train_samples": len(train_ids),
                "test_samples": len(test_ids),
            }
        )
    (out_dir / "sequence_walk_forward_splits.json").write_text(json.dumps(json_safe({"windows": rows}), indent=2), encoding="utf-8")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-dir", default=None)
    parser.add_argument("--feature-dir", default=None)
    parser.add_argument("--output-dir", default="/kaggle/working/northstar_v3_sequence_export")
    parser.add_argument("--lookback", type=int, default=DEFAULT_LOOKBACK)
    parser.add_argument("--shard-size", type=int, default=DEFAULT_SHARD_SIZE)
    parser.add_argument("--max-tickers", type=int, default=None)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--no-compress", action="store_true")
    args = parser.parse_args()

    canonical_dir = resolve_dir(
        args.canonical_dir,
        [
            "/kaggle/input/datasets/aryakghoshal/northstar-v3-canonical-raw/canonical",
            "/kaggle/input/northstar-v3-canonical-raw/canonical",
            "data/canonical",
        ],
        "prices/equity_prices_daily.parquet",
    )
    feature_dir = resolve_dir(
        args.feature_dir,
        [
            "/kaggle/input/datasets/aryakghoshal/northstar-v3-feature-export-fixed",
            "/kaggle/input/northstar-v3-feature-export-fixed",
            "tmp/kaggle_uploads/northstar_v3_feature_export_fixed_20260519",
        ],
        "northstar_features.parquet",
    )
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    weekly = pd.read_parquet(feature_dir / "northstar_features.parquet", columns=["date", "ticker", TARGET_COL])
    weekly["date"] = pd.to_datetime(weekly["date"]).dt.normalize()
    weekly["ticker"] = normalize_ticker(weekly["ticker"])
    weekly = weekly[(weekly["date"] >= POST_INDAS_ANCHOR) & weekly[TARGET_COL].notna()].copy()
    tickers = sorted(weekly["ticker"].unique().tolist())
    if args.max_tickers:
        tickers = tickers[: args.max_tickers]
        weekly = weekly[weekly["ticker"].isin(tickers)].copy()
    weekly = weekly.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
    weekly["sample_id"] = np.arange(len(weekly), dtype=np.int64)
    weekly = weekly.rename(columns={TARGET_COL: "target"})
    if args.max_samples:
        weekly = weekly.head(args.max_samples).copy()

    log("\nNORTHSTAR V3 SEQUENCE EXPORT BUILDER")
    log(f"  Canonical dir: {canonical_dir}")
    log(f"  Feature dir  : {feature_dir}")
    log(f"  Output dir   : {out_dir}")
    log(f"  Tickers      : {len(tickers)}")
    log(f"  Candidate samples: {len(weekly):,}")
    log(f"  Lookback days: {args.lookback}")

    panel, temporal_features = build_daily_panel(canonical_dir, tickers)
    log(f"  Daily panel shape: {panel.shape}")
    log(f"  Temporal features: {len(temporal_features)}")

    shard_info = write_shards(
        panel,
        temporal_features,
        weekly,
        out_dir,
        lookback=args.lookback,
        shard_size=args.shard_size,
        compress=not args.no_compress,
    )
    sample_index = pd.read_parquet(out_dir / "sample_index.parquet")
    static = build_static_features(feature_dir, sample_index)
    static.to_parquet(out_dir / "static_features.parquet", index=False)
    splits = build_splits(feature_dir, sample_index, out_dir)

    feature_registry = {
        "temporal_features": temporal_features,
        "static_feature_count": int(static.shape[1] - 3),
        "target": "forward 5-day return from fixed weekly feature export",
        "lookback_days": int(args.lookback),
        "groups": {
            "prices": [c for c in temporal_features if c.startswith("px_")],
            "cross_asset_macro": [c for c in temporal_features if c.startswith("xasset_")],
            "rbi_macro": [c for c in temporal_features if c.startswith("rbi_")],
            "sentiment": [c for c in temporal_features if c.startswith("sent_") or c.startswith("news_")],
            "alternative": [c for c in temporal_features if c.startswith("alt_") or c.startswith("bulk_") or c.startswith("announcement") or c in {"pledge_pct", "pledge_value_cr", "rating_numeric"}],
        },
    }
    (out_dir / "sequence_feature_registry.json").write_text(json.dumps(json_safe(feature_registry), indent=2), encoding="utf-8")

    manifest = {
        "dataset_name": "northstar_v3_sequence_export",
        "created_in": "kaggle_or_local_builder",
        "canonical_dir": str(canonical_dir),
        "feature_dir": str(feature_dir),
        "candidate_samples": int(len(weekly)),
        "samples_kept": shard_info["samples_kept"],
        "tickers": int(sample_index["ticker"].nunique()) if len(sample_index) else 0,
        "date_min": sample_index["date"].min() if len(sample_index) else None,
        "date_max": sample_index["date"].max() if len(sample_index) else None,
        "lookback_days": int(args.lookback),
        "temporal_feature_count": int(len(temporal_features)),
        "static_feature_count": int(static.shape[1] - 3),
        "shards": shard_info["shards"],
        "split_windows": len(splits),
    }
    (out_dir / "sequence_export_manifest.json").write_text(json.dumps(json_safe(manifest), indent=2), encoding="utf-8")
    dataset_metadata = {
        "title": "Northstar V3 Sequence Export",
        "id": "aryakghoshal/northstar-v3-sequence-export",
        "licenses": [{"name": "other"}],
        "isPrivate": True,
    }
    (out_dir / "dataset-metadata.json").write_text(json.dumps(dataset_metadata, indent=2), encoding="utf-8")
    log("\nBUILD COMPLETE")
    log(json.dumps(json_safe(manifest), indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
