"""Assemble the OptionsOrgan's candidate + holdings inputs from real v3 output.

This is the integration seam that lets the options organ run off the v3 stack's
actual conclusions rather than injected test data:

  directional_score  <- v3 daily scorer (northstar_score, cross-sectionally
                        standardized to [-1, 1]); this is v3's "is this company
                        strong or weak" verdict.
  situation_score    <- for HELD equities: a blend of the directional score and
                        the recent news/sentiment trend (company_sentiment_daily).
                        Negative = deteriorating (weak score AND/OR bad news) ->
                        the organ will propose a hedge instead of a sell.
  spot / realized_vol<- canonical equity prices (last close; annualized vol of
                        daily returns).
  regime             <- the scorer's regime tag (falls back to market_state).

News (the "why it's tanking" the operator cares about) enters through the
sentiment surprise term, and the design leaves a `news_overlay` hook so the
standalone NIL layer can later sharpen situation scores with event-level
signals.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("options.candidate_builder")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCORES_PATH = PROJECT_ROOT / "data" / "processed" / "scores.parquet"
SENTIMENT_PATH = PROJECT_ROOT / "data" / "canonical" / "sentiment" / "company_sentiment_daily.parquet"
POSITIONS_PATH = PROJECT_ROOT / "data" / "portfolio" / "current_positions.json"
BULK_DEALS_PATH = PROJECT_ROOT / "data" / "processed" / "alternative" / "bulk_deals_nse_all.parquet"


def _std_to_unit(series: pd.Series) -> pd.Series:
    """Cross-sectional standardize then squash to [-1, 1] via tanh. Robust to
    whatever raw scale the score column is on."""
    x = pd.to_numeric(series, errors="coerce")
    mu, sd = x.mean(), x.std(ddof=0)
    if not np.isfinite(sd) or sd < 1e-9:
        return pd.Series(0.0, index=series.index)
    return np.tanh((x - mu) / sd)


def _price_summary(prices_legacy: pd.DataFrame, window: int = 30) -> Dict[str, Tuple[float, float]]:
    """Single-pass per-ticker (last_close, realized_vol). Avoids O(N_tickers x
    N_rows) repeated filtering of the 2M+ row price panel."""
    out: Dict[str, Tuple[float, float]] = {}
    if prices_legacy is None or prices_legacy.empty or "ticker" not in prices_legacy.columns:
        return out
    if "Close" not in prices_legacy.columns or "Date" not in prices_legacy.columns:
        return out
    df = prices_legacy[["ticker", "Date", "Close"]].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.dropna(subset=["ticker", "Date", "Close"]).sort_values(["ticker", "Date"])
    for tk, grp in df.groupby("ticker", sort=False):
        closes = grp["Close"].tail(window + 1)
        last_close = float(closes.iloc[-1]) if len(closes) else 0.0
        if len(closes) >= 5:
            rets = np.log(closes / closes.shift(1)).dropna()
            vol = float(rets.std() * np.sqrt(252))
            vol = float(np.clip(vol, 0.05, 1.5)) if np.isfinite(vol) else 0.25
        else:
            vol = 0.25
        out[str(tk)] = (last_close, vol)
    return out


class CandidateBuilder:
    def __init__(
        self,
        scores_path: Path = SCORES_PATH,
        sentiment_path: Path = SENTIMENT_PATH,
        positions_path: Path = POSITIONS_PATH,
        bulk_deals_path: Path = BULK_DEALS_PATH,
        *,
        news_overlay: Optional[Any] = None,   # seam for the NIL news layer
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.scores_path = Path(scores_path)
        self.sentiment_path = Path(sentiment_path)
        self.positions_path = Path(positions_path)
        self.bulk_deals_path = Path(bulk_deals_path)
        self.news_overlay = news_overlay
        self.log = log or logger

    # ---- loaders (all defensive) ----
    def _load_scores(self) -> pd.DataFrame:
        if not self.scores_path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_parquet(self.scores_path)
        except Exception:
            return pd.DataFrame()
        return df if "ticker" in df.columns else pd.DataFrame()

    def _latest_sentiment(self) -> Dict[str, float]:
        """Most-recent per-ticker sentiment trend: polarity + surprise (negative
        = deteriorating news). Returns {ticker: news_score in [-1, 1]}."""
        if not self.sentiment_path.exists():
            return {}
        try:
            df = pd.read_parquet(self.sentiment_path)
        except Exception:
            return {}
        if df.empty or "ticker" not in df.columns:
            return {}
        date_col = "availability_date" if "availability_date" in df.columns else "date"
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        # 10-business-day trailing mean of polarity+surprise per ticker.
        cutoff = df[date_col].max() - pd.Timedelta(days=14)
        recent = df[df[date_col] >= cutoff]
        out: Dict[str, float] = {}
        pol = pd.to_numeric(recent.get("sentiment_polarity"), errors="coerce")
        sur = pd.to_numeric(recent.get("sentiment_surprise"), errors="coerce")
        recent = recent.assign(_news=(pol.fillna(0.0) * 0.6 + sur.fillna(0.0) * 0.4))
        for tk, grp in recent.groupby("ticker"):
            val = float(grp["_news"].mean())
            out[str(tk)] = float(np.clip(val, -1.0, 1.0)) if np.isfinite(val) else 0.0
        return out

    def _latest_smart_money(self) -> Dict[str, float]:
        """Net institutional bulk-deal pressure per ticker over a trailing
        10-day window: (buy value - sell value) / total value, in [-1, 1].
        Heavy net institutional buying is a real, independent signal that
        alternative-data desks track alongside price/sentiment — this was
        gathered (bulk_deals_nse_all.parquet, refreshed daily) but never fed
        into the options organ's conviction score before."""
        if not self.bulk_deals_path.exists():
            return {}
        try:
            df = pd.read_parquet(self.bulk_deals_path)
        except Exception:
            return {}
        if df.empty or "date" not in df.columns:
            return {}
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        cutoff = df["date"].max() - pd.Timedelta(days=10)
        recent = df[df["date"] >= cutoff].copy()
        ticker_col = "nse_ticker" if "nse_ticker" in recent.columns else "symbol"
        if ticker_col not in recent.columns:
            return {}
        recent["value"] = pd.to_numeric(recent.get("quantity"), errors="coerce") * pd.to_numeric(recent.get("price"), errors="coerce")
        recent = recent.dropna(subset=["value"])
        is_buy = recent.get("deal_type", "").astype(str).str.upper().str.startswith("B")
        recent["signed"] = np.where(is_buy, recent["value"], -recent["value"])
        out: Dict[str, float] = {}
        for tk, grp in recent.groupby(ticker_col):
            total = grp["value"].sum()
            if total <= 0:
                continue
            score = float(grp["signed"].sum() / total)
            out[str(tk)] = float(np.clip(score, -1.0, 1.0))
        return out

    def _load_prices(self) -> pd.DataFrame:
        try:
            from src.data.price_access import read_prices_legacy
            return read_prices_legacy()
        except Exception:
            return pd.DataFrame()

    def _load_holdings_raw(self) -> Dict[str, Dict[str, Any]]:
        if not self.positions_path.exists():
            return {}
        try:
            payload = json.loads(self.positions_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        positions = payload.get("positions") if isinstance(payload, dict) else None
        return positions if isinstance(positions, dict) else {}

    # ---- assembly ----
    def build(self, *, regime_fallback: str = "unknown") -> Tuple[str, Dict[str, Dict], Dict[str, Dict]]:
        scores = self._load_scores()
        if scores.empty:
            self.log.warning("CandidateBuilder: no v3 scores available; empty candidate set")
            return regime_fallback, {}, {}

        # Directional score per ticker (v3 verdict), + regime.
        score_col = next((c for c in ["northstar_score", "final_score", "score", "model_score"]
                          if c in scores.columns), None)
        scores = scores.copy()
        scores["dir_unit"] = _std_to_unit(scores[score_col]) if score_col else 0.0
        regime = str(scores["regime"].dropna().iloc[0]) if "regime" in scores.columns and scores["regime"].notna().any() else regime_fallback

        sentiment = self._latest_sentiment()
        news = self.news_overlay.scores() if self.news_overlay is not None else {}
        smart_money = self._latest_smart_money()
        price_summary = _price_summary(self._load_prices())  # {ticker: (last_close, realized_vol)}

        candidates: Dict[str, Dict[str, Any]] = {}
        for row in scores.itertuples(index=False):
            tk = str(getattr(row, "ticker"))
            spot, rvol = price_summary.get(tk, (0.0, 0.25))
            if spot <= 0:
                continue
            dir_score = float(getattr(row, "dir_unit"))
            news_score = float(news.get(tk, sentiment.get(tk, 0.0)))
            smart_score = float(smart_money.get(tk, 0.0))
            # v3 factor score remains dominant; news and smart-money flow are
            # corroborating/contrarian tilts, not primary drivers.
            blended = 0.65 * dir_score + 0.20 * news_score + 0.15 * smart_score
            candidates[tk] = {
                "spot": spot,
                "directional_score": round(float(np.clip(blended, -1.0, 1.0)), 4),
                "realized_vol": rvol,
                "news_score": round(news_score, 4),
                "smart_money_score": round(smart_score, 4),
                "reason": self._reason(dir_score, news_score, regime, smart_score=smart_score),
            }

        # Holdings: only equities we actually hold; situation = directional+news.
        holdings: Dict[str, Dict[str, Any]] = {}
        for tk, pos in self._load_holdings_raw().items():
            if not isinstance(pos, dict):
                continue
            qty = float(pos.get("quantity") or pos.get("qty") or 0.0)
            if qty <= 0:
                continue
            cand = candidates.get(str(tk), {})
            spot = float(cand.get("spot") or pos.get("avg_cost") or pos.get("avg_price") or 0.0)
            if spot <= 0:
                continue
            dir_score = float(cand.get("directional_score", 0.0))
            news_score = float(cand.get("news_score", 0.0))
            situation = float(np.clip(0.5 * dir_score + 0.5 * news_score, -1.0, 1.0))
            holdings[str(tk)] = {
                "spot": spot,
                "quantity": qty,
                "situation_score": round(situation, 4),
                "realized_vol": cand.get("realized_vol", 0.25),
                "sector": pos.get("sector", ""),
                "reason": self._reason(dir_score, news_score, regime, held=True),
            }

        self.log.info(
            "CandidateBuilder: %d candidates, %d holdings, regime=%s", len(candidates), len(holdings), regime
        )
        return regime, candidates, holdings

    @staticmethod
    def _reason(dir_score: float, news_score: float, regime: str, held: bool = False, smart_score: float = 0.0) -> str:
        bits = []
        if dir_score <= -0.2:
            bits.append("weak v3 factor score")
        elif dir_score >= 0.2:
            bits.append("strong v3 factor score")
        if news_score <= -0.2:
            bits.append("deteriorating news/sentiment")
        elif news_score >= 0.2:
            bits.append("improving news/sentiment")
        if smart_score <= -0.3:
            bits.append("heavy institutional selling (bulk deals)")
        elif smart_score >= 0.3:
            bits.append("heavy institutional buying (bulk deals)")
        if not bits:
            bits.append("neutral v3 read")
        prefix = "Held equity: " if held else ""
        return f"{prefix}{', '.join(bits)} ({regime} regime)"
