"""Build per-stock sequence tensors for TCN/Transformer training."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

import numpy as np
import pandas as pd
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.data.loaders import load_fundamentals, load_prices, load_regime_labels

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = "config/research_policy.yaml"
DEFAULT_OUTPUT_PATH = "data/processed/sequence_dataset.pt"

PRICE_FEATURES = [
    "log_return_1d",
    "log_return_5d",
    "log_return_21d",
    "volume_zscore_21d",
    "high_low_range_pct",
]

TECHNICAL_FEATURES = [
    "rsi_14",
    "macd_signal",
    "bb_position",
    "atr_14_pct",
    "obv_zscore_21d",
    "adx_14",
    "cci_14",
    "mfi_14",
    "williams_r_14",
    "stoch_k_14",
    "ema_cross",
    "price_vs_52w",
]

FUNDAMENTAL_FEATURES = [
    "screener_roce_cs_z",
    "screener_opm_pct_cs_z",
    "screener_revenue_growth_1y_cs_z",
    "screener_pat_growth_1y_cs_z",
    "screener_cfo_to_pat_cs_z",
    "screener_promoter_pct_cs_z",
]

SENTIMENT_FEATURES = [
    "sentiment_5d_mean",
    "sentiment_shock",
]

REGIME_FEATURES = [
    "macro_expansion",
    "macro_contraction",
    "vol_high",
]

ALL_FEATURES = PRICE_FEATURES + TECHNICAL_FEATURES + FUNDAMENTAL_FEATURES + SENTIMENT_FEATURES + REGIME_FEATURES


@dataclass
class SequenceBuildResult:
    X: np.ndarray
    y: np.ndarray
    metadata: pd.DataFrame
    feature_names: list[str]
    seq_len: int


def _load_policy(config_path: str) -> dict[str, Any]:
    p = Path(config_path)
    if not p.exists():
        return {}
    payload = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _dataset_cfg(policy: dict[str, Any]) -> dict[str, Any]:
    hr = policy.get("historical_research", {})
    if not isinstance(hr, dict):
        return {}
    ds = hr.get("dataset", {})
    return ds if isinstance(ds, dict) else {}


def _normalize_date(frame: pd.DataFrame, candidates: Iterable[str]) -> pd.Series:
    for col in candidates:
        if col in frame.columns:
            return pd.to_datetime(frame[col], errors="coerce").dt.normalize()
    return pd.Series(pd.NaT, index=frame.index)


def _first_existing(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    for c in candidates:
        if c in frame.columns:
            return c
    return None


def _zscore_cross_section(series: pd.Series) -> pd.Series:
    v = pd.to_numeric(series, errors="coerce")
    mu = v.mean(skipna=True)
    sd = v.std(skipna=True)
    if not np.isfinite(sd) or float(sd) < 1e-12:
        return pd.Series(0.0, index=series.index, dtype=float)
    out = (v - mu) / sd
    out = out.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return out.astype(float)


def _ema(s: pd.Series, span: int) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").ewm(span=span, adjust=False, min_periods=span).mean()


def _rolling_zscore(s: pd.Series, window: int) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    mu = v.rolling(window, min_periods=max(5, window // 3)).mean()
    sd = v.rolling(window, min_periods=max(5, window // 3)).std()
    out = (v - mu) / (sd + 1e-12)
    return out.replace([np.inf, -np.inf], np.nan)


def _compute_technical_features(px: pd.DataFrame) -> pd.DataFrame:
    close = pd.to_numeric(px["close"], errors="coerce")
    high = pd.to_numeric(px["high"], errors="coerce")
    low = pd.to_numeric(px["low"], errors="coerce")
    vol = pd.to_numeric(px["volume"], errors="coerce")

    out = px.copy()

    out["log_return_1d"] = np.log(close / close.shift(1)).replace([np.inf, -np.inf], np.nan)
    out["log_return_5d"] = np.log(close / close.shift(5)).replace([np.inf, -np.inf], np.nan)
    out["log_return_21d"] = np.log(close / close.shift(21)).replace([np.inf, -np.inf], np.nan)
    out["volume_zscore_21d"] = _rolling_zscore(vol, 21)
    out["high_low_range_pct"] = ((high - low) / (close + 1e-12)).replace([np.inf, -np.inf], np.nan)

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta.clip(upper=0.0)).abs()
    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    out["rsi_14"] = (100.0 - (100.0 / (1.0 + rs))) / 100.0

    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    out["macd_signal"] = (macd - signal) / (close + 1e-12)

    bb_mid = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std()
    bb_upper = bb_mid + 2.0 * bb_std
    bb_lower = bb_mid - 2.0 * bb_std
    out["bb_position"] = ((close - bb_lower) / ((bb_upper - bb_lower) + 1e-12)).clip(0.0, 1.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = tr.rolling(14, min_periods=14).mean()
    out["atr_14_pct"] = atr14 / (close + 1e-12)

    direction = np.sign(delta.fillna(0.0))
    obv = (direction * vol.fillna(0.0)).cumsum()
    out["obv_zscore_21d"] = _rolling_zscore(obv, 21)

    plus_dm = (high.diff()).clip(lower=0.0)
    minus_dm = (-low.diff()).clip(lower=0.0)
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)
    tr14 = tr.rolling(14, min_periods=14).sum()
    plus_di = 100.0 * plus_dm.rolling(14, min_periods=14).sum() / (tr14 + 1e-12)
    minus_di = 100.0 * minus_dm.rolling(14, min_periods=14).sum() / (tr14 + 1e-12)
    dx = 100.0 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-12)
    out["adx_14"] = (dx.rolling(14, min_periods=14).mean() / 100.0).clip(0.0, 1.0)

    tp = (high + low + close) / 3.0
    tp_sma = tp.rolling(14, min_periods=14).mean()
    md = (tp - tp_sma).abs().rolling(14, min_periods=14).mean()
    out["cci_14"] = ((tp - tp_sma) / (0.015 * md + 1e-12)).clip(-400, 400) / 100.0

    raw_money_flow = tp * vol.fillna(0.0)
    positive_flow = raw_money_flow.where(tp > tp.shift(1), 0.0)
    negative_flow = raw_money_flow.where(tp < tp.shift(1), 0.0)
    pmf = positive_flow.rolling(14, min_periods=14).sum()
    nmf = negative_flow.rolling(14, min_periods=14).sum().abs()
    mfi = 100.0 - (100.0 / (1.0 + (pmf / (nmf + 1e-12))))
    out["mfi_14"] = (mfi / 100.0).clip(0.0, 1.0)

    hh14 = high.rolling(14, min_periods=14).max()
    ll14 = low.rolling(14, min_periods=14).min()
    wr = -100.0 * ((hh14 - close) / ((hh14 - ll14) + 1e-12))
    out["williams_r_14"] = (wr / 100.0).clip(-1.0, 0.0)

    out["stoch_k_14"] = ((close - ll14) / ((hh14 - ll14) + 1e-12)).clip(0.0, 1.0)

    ema9 = _ema(close, 9)
    ema21 = _ema(close, 21)
    out["ema_cross"] = (ema9 - ema21) / (close + 1e-12)

    out["price_vs_52w"] = close / (high.rolling(252, min_periods=60).max() + 1e-12)

    return out


def _prepare_prices(prices: pd.DataFrame) -> pd.DataFrame:
    px = prices.copy()
    px["date"] = _normalize_date(px, ["Date", "date", "timestamp"])
    px = px.dropna(subset=["date"]).copy()

    ticker_col = _first_existing(px, ["ticker", "Ticker", "symbol", "Symbol"])
    if ticker_col is None:
        raise ValueError("sequence_builder_missing_ticker_column_in_prices")
    px["ticker"] = px[ticker_col].astype(str).str.upper()

    open_col = _first_existing(px, ["Open", "open"])
    high_col = _first_existing(px, ["High", "high"])
    low_col = _first_existing(px, ["Low", "low"])
    close_col = _first_existing(px, ["Close", "close"])
    volume_col = _first_existing(px, ["Volume", "volume"])

    if close_col is None:
        raise ValueError("sequence_builder_missing_close_column")

    px["open"] = pd.to_numeric(px[open_col], errors="coerce") if open_col else np.nan
    px["high"] = pd.to_numeric(px[high_col], errors="coerce") if high_col else px["open"]
    px["low"] = pd.to_numeric(px[low_col], errors="coerce") if low_col else px["open"]
    px["close"] = pd.to_numeric(px[close_col], errors="coerce")
    px["volume"] = pd.to_numeric(px[volume_col], errors="coerce") if volume_col else 0.0

    px = px.dropna(subset=["ticker", "date", "close"]).copy()
    px = px.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)

    chunks: list[pd.DataFrame] = []
    for ticker, g in px.groupby("ticker", sort=False):
        if len(g) < 80:
            continue
        features = _compute_technical_features(g)
        chunks.append(features)

    out = pd.concat(chunks, axis=0, ignore_index=True) if chunks else pd.DataFrame(columns=px.columns)
    out = out.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    out["forward_return_5d"] = (
        out.groupby("ticker", sort=False)["close"].shift(-5) / (out["close"] + 1e-12)
    ) - 1.0
    return out


def _resolve_fundamental_column(frame: pd.DataFrame, candidates: list[str]) -> str | None:
    lc = {str(c).lower(): c for c in frame.columns}
    for cand in candidates:
        c = lc.get(str(cand).lower())
        if c is not None:
            return str(c)
    return None


def _prepare_fundamentals(fundamentals: pd.DataFrame) -> pd.DataFrame:
    if fundamentals is None or fundamentals.empty:
        cols = ["ticker", "availability_date"] + FUNDAMENTAL_FEATURES
        return pd.DataFrame(columns=cols)

    fd = fundamentals.copy()
    ticker_col = _first_existing(fd, ["ticker", "Ticker", "symbol", "Symbol"])
    if ticker_col is None:
        cols = ["ticker", "availability_date"] + FUNDAMENTAL_FEATURES
        return pd.DataFrame(columns=cols)

    fd["ticker"] = fd[ticker_col].astype(str).str.upper()

    if "availability_date" in fd.columns:
        avail = pd.to_datetime(fd["availability_date"], errors="coerce").dt.normalize()
    else:
        base_col = _first_existing(fd, ["period_end_date", "report_date", "date", "Date", "timestamp"])
        base = pd.to_datetime(fd[base_col], errors="coerce").dt.normalize() if base_col else pd.Series(pd.NaT, index=fd.index)
        avail = (base + pd.to_timedelta(60, unit="D")).dt.normalize()
    fd["availability_date"] = avail

    mapping = {
        "screener_roce_cs_z": ["screener_roce", "roce", "roce_pct", "return_on_capital_employed"],
        "screener_opm_pct_cs_z": ["screener_opm_pct", "opm", "opm_pct", "operating_margin"],
        "screener_revenue_growth_1y_cs_z": ["screener_revenue_growth_1y", "revenue_growth_1y", "sales_growth_1y", "revenue_growth"],
        "screener_pat_growth_1y_cs_z": ["screener_pat_growth_1y", "pat_growth_1y", "net_income_growth_1y", "profit_growth_1y"],
        "screener_cfo_to_pat_cs_z": ["screener_cfo_to_pat", "cfo_to_pat", "cashflow_to_profit", "operating_cash_flow_to_pat"],
        "screener_promoter_pct_cs_z": ["screener_promoter_pct", "promoter_pct", "promoter_holding_pct", "promoter_holding"],
    }

    keep = pd.DataFrame({
        "ticker": fd["ticker"],
        "availability_date": fd["availability_date"],
    })
    for out_col, candidates in mapping.items():
        src = _resolve_fundamental_column(fd, candidates)
        keep[out_col] = pd.to_numeric(fd[src], errors="coerce") if src else np.nan

    keep = keep.dropna(subset=["ticker", "availability_date"]).sort_values(["ticker", "availability_date"], kind="mergesort")
    return keep.reset_index(drop=True)


def _merge_fundamentals(panel: pd.DataFrame, fundamentals: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return panel
    out_chunks: list[pd.DataFrame] = []

    if fundamentals.empty:
        out = panel.copy()
        for col in FUNDAMENTAL_FEATURES:
            out[col] = 0.0
        return out

    for ticker, g in panel.groupby("ticker", sort=False):
        f = fundamentals[fundamentals["ticker"] == ticker]
        g = g.sort_values("date", kind="mergesort").copy()
        if f.empty:
            for col in FUNDAMENTAL_FEATURES:
                g[col] = np.nan
            out_chunks.append(g)
            continue
        f = f.sort_values("availability_date", kind="mergesort").copy()
        merged = pd.merge_asof(
            g,
            f,
            left_on="date",
            right_on="availability_date",
            direction="backward",
            suffixes=("", "_fund"),
        )
        if "ticker_y" in merged.columns:
            merged = merged.drop(columns=["ticker_y"])
        if "ticker_x" in merged.columns:
            merged = merged.rename(columns={"ticker_x": "ticker"})
        out_chunks.append(merged)

    out = pd.concat(out_chunks, axis=0, ignore_index=True)
    out = out.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)

    for col in FUNDAMENTAL_FEATURES:
        out[col] = out.groupby("date", sort=False)[col].transform(_zscore_cross_section).fillna(0.0)
    return out


def _prepare_sentiment(policy: dict[str, Any]) -> pd.DataFrame:
    ds = _dataset_cfg(policy)
    sentiment_path = str(ds.get("sentiment_path", "data/processed/sentiment/ticker_sentiment_daily.parquet"))
    p = Path(sentiment_path)
    if not p.exists() and not p.is_absolute():
        p = Path(".") / p
    if not p.exists():
        logger.warning("Sentiment source missing for sequence builder: %s", p)
        return pd.DataFrame(columns=["date", "ticker"] + SENTIMENT_FEATURES)

    news = pd.read_parquet(p)
    if news.empty:
        return pd.DataFrame(columns=["date", "ticker"] + SENTIMENT_FEATURES)

    date_col = _first_existing(news, ["date", "Date", "timestamp", "published_at"])
    ticker_col = _first_existing(news, ["ticker", "symbol", "Ticker", "Symbol"])
    if date_col is None or ticker_col is None:
        return pd.DataFrame(columns=["date", "ticker"] + SENTIMENT_FEATURES)

    work = news.copy()
    work["date"] = pd.to_datetime(work[date_col], errors="coerce").dt.normalize()
    work["ticker"] = work[ticker_col].astype(str).str.upper()

    if "sentiment_5d_mean" in work.columns and "sentiment_shock" in work.columns:
        out = work[["date", "ticker", "sentiment_5d_mean", "sentiment_shock"]].copy()
        out["sentiment_5d_mean"] = pd.to_numeric(out["sentiment_5d_mean"], errors="coerce")
        out["sentiment_shock"] = pd.to_numeric(out["sentiment_shock"], errors="coerce")
        out = out.dropna(subset=["date", "ticker"]).sort_values(["ticker", "date"], kind="mergesort")
        out["sentiment_5d_mean"] = out.groupby("ticker", sort=False)["sentiment_5d_mean"].shift(1)
        out["sentiment_shock"] = out.groupby("ticker", sort=False)["sentiment_shock"].shift(1)
        return out

    score_col = _first_existing(work, ["sentiment_score", "sentiment", "polarity"])
    if score_col is None:
        return pd.DataFrame(columns=["date", "ticker"] + SENTIMENT_FEATURES)

    work["sentiment_score"] = pd.to_numeric(work[score_col], errors="coerce")
    work = work.dropna(subset=["date", "ticker", "sentiment_score"])
    if work.empty:
        return pd.DataFrame(columns=["date", "ticker"] + SENTIMENT_FEATURES)

    daily = (
        work.groupby(["date", "ticker"], as_index=False)
        .agg(sentiment_daily_mean=("sentiment_score", "mean"))
        .sort_values(["ticker", "date"], kind="mergesort")
    )

    daily["sentiment_daily_mean"] = daily.groupby("ticker", sort=False)["sentiment_daily_mean"].shift(1)
    daily["sentiment_5d_mean"] = daily.groupby("ticker", sort=False)["sentiment_daily_mean"].transform(
        lambda x: x.rolling(5, min_periods=1).mean()
    )
    daily["sentiment_60d_mean"] = daily.groupby("ticker", sort=False)["sentiment_daily_mean"].transform(
        lambda x: x.rolling(60, min_periods=5).mean()
    )
    daily["sentiment_shock"] = daily["sentiment_5d_mean"] - daily["sentiment_60d_mean"]

    out = daily[["date", "ticker", "sentiment_5d_mean", "sentiment_shock"]].copy()
    return out


def _merge_sentiment(panel: pd.DataFrame, sentiment: pd.DataFrame) -> pd.DataFrame:
    if panel.empty:
        return panel
    if sentiment.empty:
        out = panel.copy()
        out["sentiment_5d_mean"] = 0.0
        out["sentiment_shock"] = 0.0
        return out

    out = panel.merge(sentiment, on=["date", "ticker"], how="left")
    out["sentiment_5d_mean"] = pd.to_numeric(out["sentiment_5d_mean"], errors="coerce")
    out["sentiment_shock"] = pd.to_numeric(out["sentiment_shock"], errors="coerce")
    out["sentiment_5d_mean"] = out.groupby("ticker", sort=False)["sentiment_5d_mean"].ffill().fillna(0.0)
    out["sentiment_shock"] = out.groupby("ticker", sort=False)["sentiment_shock"].ffill().fillna(0.0)
    return out


def _merge_regime_context(panel: pd.DataFrame, regime_labels: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if regime_labels is None or regime_labels.empty:
        out["regime"] = "unknown"
        out["macro_expansion"] = 0.0
        out["macro_contraction"] = 0.0
        out["vol_high"] = 0.0
        return out

    rg = regime_labels.copy()
    rg["date"] = _normalize_date(rg, ["date", "Date", "timestamp"])
    regime_col = _first_existing(rg, ["regime", "macro_regime_label", "market_regime"])
    if regime_col is None:
        out["regime"] = "unknown"
        out["macro_expansion"] = 0.0
        out["macro_contraction"] = 0.0
        out["vol_high"] = 0.0
        return out

    rg["regime"] = rg[regime_col].astype(str).str.lower()
    rg = rg.dropna(subset=["date"]).sort_values("date", kind="mergesort").drop_duplicates(subset=["date"], keep="last")

    out = out.merge(rg[["date", "regime"]], on="date", how="left")
    out["regime"] = out["regime"].fillna("unknown").astype(str)
    out["macro_expansion"] = out["regime"].str.contains("expansion", case=False, na=False).astype(float)
    out["macro_contraction"] = out["regime"].str.contains("contraction", case=False, na=False).astype(float)
    out["vol_high"] = out["regime"].str.contains("high_vol", case=False, na=False).astype(float)
    return out


def _normalize_sequence_window(window: np.ndarray) -> np.ndarray:
    mu = np.nanmean(window, axis=0)
    sd = np.nanstd(window, axis=0)
    mu = np.nan_to_num(mu, nan=0.0, posinf=0.0, neginf=0.0)
    sd = np.nan_to_num(sd, nan=1.0, posinf=1.0, neginf=1.0)
    sd = np.where(sd < 1e-8, 1.0, sd)
    out = (window - mu) / sd
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def _build_sequences_from_panel(panel: pd.DataFrame, seq_len: int) -> SequenceBuildResult:
    if panel.empty:
        raise ValueError("sequence_builder_empty_panel")

    work = panel.copy()
    work = work.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)

    X_rows: list[np.ndarray] = []
    y_rows: list[float] = []
    meta_rows: list[dict[str, Any]] = []

    tickers = sorted(work["ticker"].astype(str).unique().tolist())
    for i, ticker in enumerate(tickers, start=1):
        g = work[work["ticker"] == ticker].copy().sort_values("date", kind="mergesort")
        if len(g) < seq_len + 5:
            continue

        features = g[ALL_FEATURES].to_numpy(dtype=float)
        target = pd.to_numeric(g["forward_return_5d"], errors="coerce").to_numpy(dtype=float)
        dates = pd.to_datetime(g["date"], errors="coerce")
        regime_vals = g.get("regime", pd.Series(["unknown"] * len(g))).astype(str).to_numpy()

        for end_idx in range(seq_len - 1, len(g) - 5):
            y = target[end_idx]
            if not np.isfinite(y):
                continue
            w = features[end_idx - seq_len + 1 : end_idx + 1]
            if w.shape[0] != seq_len:
                continue
            x_norm = _normalize_sequence_window(w)
            X_rows.append(x_norm)
            y_rows.append(float(y))
            meta_rows.append(
                {
                    "ticker": str(ticker),
                    "date": pd.Timestamp(dates.iloc[end_idx]).strftime("%Y-%m-%d"),
                    "target_date": pd.Timestamp(dates.iloc[end_idx + 5]).strftime("%Y-%m-%d"),
                    "regime": str(regime_vals[end_idx]),
                }
            )

        if i % 50 == 0:
            logger.info("sequence_builder progress: %d/%d tickers processed", i, len(tickers))

    if not X_rows:
        raise ValueError("sequence_builder_no_samples_generated")

    X = np.stack(X_rows, axis=0).astype(np.float32)
    y = np.asarray(y_rows, dtype=np.float32)
    meta = pd.DataFrame(meta_rows)
    return SequenceBuildResult(X=X, y=y, metadata=meta, feature_names=list(ALL_FEATURES), seq_len=int(seq_len))


def build_sequence_dataset(config_path: str = DEFAULT_CONFIG_PATH, output_path: str = DEFAULT_OUTPUT_PATH) -> SequenceBuildResult:
    policy = _load_policy(config_path)
    seq_len = int(policy.get("sequence_lookback", 252) or 252)

    prices = load_prices(config_path=config_path)
    fundamentals = load_fundamentals(config_path=config_path)
    regime_labels = load_regime_labels(config_path=config_path)

    panel = _prepare_prices(prices)
    panel = _merge_fundamentals(panel, _prepare_fundamentals(fundamentals))
    panel = _merge_sentiment(panel, _prepare_sentiment(policy))
    panel = _merge_regime_context(panel, regime_labels)

    for col in ALL_FEATURES:
        if col not in panel.columns:
            panel[col] = 0.0
        panel[col] = pd.to_numeric(panel[col], errors="coerce").replace([np.inf, -np.inf], np.nan)

    panel[ALL_FEATURES] = panel[ALL_FEATURES].fillna(0.0)

    result = _build_sequences_from_panel(panel, seq_len=seq_len)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import torch
    except Exception as exc:
        raise RuntimeError("sequence_builder_requires_torch") from exc

    payload = {
        "X": torch.tensor(result.X, dtype=torch.float32),
        "y": torch.tensor(result.y, dtype=torch.float32),
        "metadata": result.metadata.to_dict(orient="records"),
        "feature_names": list(result.feature_names),
        "seq_len": int(result.seq_len),
    }
    torch.save(payload, out_path)

    logger.info(
        "Saved sequence dataset: path=%s samples=%d seq_len=%d features=%d",
        out_path,
        int(result.X.shape[0]),
        int(result.X.shape[1]),
        int(result.X.shape[2]),
    )
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build sequence dataset for Transformer/TCN")
    p.add_argument("--config", type=str, default=DEFAULT_CONFIG_PATH)
    p.add_argument("--output", type=str, default=DEFAULT_OUTPUT_PATH)
    p.add_argument("--log-level", type=str, default="INFO")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    _ = build_sequence_dataset(config_path=args.config, output_path=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
