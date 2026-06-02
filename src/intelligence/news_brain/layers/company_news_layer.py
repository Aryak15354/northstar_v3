from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.nlp.pipeline.realtime_scorer import RealtimeScorer
from src.intelligence.news_brain.news_signal_state import (
    CompanySignal,
    NIFTY500_SECTORS,
    ShockDirection,
    ShockSeverity,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class CompanyNewsLayer:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._root_config = dict(config or {})
        brain_cfg = dict(self._root_config.get("news_brain", self._root_config) or {})
        cfg = dict(brain_cfg.get("company_layer", {}) or {})
        self.negative_threshold = float(cfg.get("sentiment_negative_threshold", -0.30))
        self.positive_threshold = float(cfg.get("sentiment_positive_threshold", 0.30))
        self.conviction_threshold = float(cfg.get("sentiment_conviction_threshold", 0.60))
        self.news_lookback_days = int(cfg.get("fresh_news_lookback_days", 2))
        self.bellwether_tickers = {_normalize_symbol(ticker) for ticker in list(cfg.get("bellwether_tickers", []) or [])}
        self._sector_cache = self._build_sector_lookup()
        self._realtime: RealtimeScorer | None = None

    def run(self, as_of_datetime: datetime) -> list[CompanySignal]:
        signals = self._load_recent_headline_signals(as_of_datetime)
        signals.extend(self._load_sentiment_signals(as_of_datetime))
        signals.extend(self._load_announcement_signals(as_of_datetime))
        signals.sort(key=lambda item: (int(item.severity.value), float(item.confidence), abs(float(item.estimated_stock_move_pct))), reverse=True)
        deduped: dict[tuple[str, str], CompanySignal] = {}
        for signal in signals:
            key = (_normalize_symbol(signal.ticker), signal.signal_type)
            current = deduped.get(key)
            if current is None or (signal.severity.value, signal.confidence) > (current.severity.value, current.confidence):
                deduped[key] = signal
        return list(deduped.values())

    def _load_recent_headline_signals(self, as_of_datetime: datetime) -> list[CompanySignal]:
        news_path = PROJECT_ROOT / "data" / "canonical" / "news" / "company_news_history.parquet"
        if not news_path.exists():
            return []
        df = pd.read_parquet(news_path, columns=["ticker", "headline", "source", "date", "availability_date"])
        if df.empty:
            return []
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["availability_date"] = pd.to_datetime(df["availability_date"], errors="coerce")
        as_of_ts = pd.Timestamp(as_of_datetime).tz_localize(None) if pd.Timestamp(as_of_datetime).tzinfo else pd.Timestamp(as_of_datetime)
        eligible = df[df["availability_date"] <= as_of_ts].copy()
        if eligible.empty:
            return []
        latest_availability = eligible["availability_date"].max()
        window_start = latest_availability - pd.Timedelta(days=self.news_lookback_days)
        recent = eligible[eligible["availability_date"] >= window_start].copy()
        recent = recent.sort_values(["availability_date", "date"], ascending=[False, False], kind="mergesort")
        if recent.empty:
            return []

        scorer = self._get_realtime()
        signals: list[CompanySignal] = []
        for _, row in recent.iterrows():
            headline = str(row.get("headline", "") or "").strip()
            ticker = _normalize_symbol(row.get("ticker"))
            if len(headline) < 10:
                continue
            nlp_result = scorer.score_single(
                headline=headline,
                ticker=ticker,
                published_at=pd.Timestamp(row["date"]).to_pydatetime(),
                source=str(row.get("source", "company_news") or "company_news"),
            )
            if nlp_result is None or nlp_result.conviction < self.conviction_threshold:
                continue
            if abs(float(nlp_result.polarity)) < min(abs(self.negative_threshold), abs(self.positive_threshold)) and not nlp_result.is_market_moving:
                continue
            primary_ticker = _to_storage_ticker(nlp_result.resolved_tickers[0] if nlp_result.resolved_tickers else ticker)
            direction = self._map_direction(nlp_result.polarity)
            severity = self._map_severity(abs(nlp_result.polarity), nlp_result.conviction, nlp_result.event.materiality if nlp_result.event else "low")
            signals.append(
                CompanySignal(
                    ticker=primary_ticker,
                    sector=self._resolve_sector(primary_ticker),
                    signal_type=nlp_result.event.event_type if nlp_result.event else ("sentiment_negative" if direction == ShockDirection.BEARISH else "sentiment_positive"),
                    direction=direction,
                    severity=severity,
                    headline=headline,
                    source=str(row.get("source", "company_news") or "company_news"),
                    published_at=pd.Timestamp(row["date"]).to_pydatetime(),
                    availability_date=nlp_result.availability_date or pd.Timestamp(row["availability_date"]).to_pydatetime(),
                    confidence=float(nlp_result.conviction),
                    is_bellwether=_normalize_symbol(primary_ticker) in self.bellwether_tickers,
                    estimated_stock_move_pct=round(abs(float(nlp_result.polarity)) * float(nlp_result.conviction) * 6.0, 2)
                    * (-1.0 if direction == ShockDirection.BEARISH else 1.0),
                    related_tickers=[_to_storage_ticker(item) for item in nlp_result.resolved_tickers if _to_storage_ticker(item) != primary_ticker],
                )
            )
        return signals

    def _load_sentiment_signals(self, as_of_datetime: datetime) -> list[CompanySignal]:
        candidates = [
            PROJECT_ROOT / "data" / "canonical" / "sentiment" / "company_sentiment_daily.parquet",
            PROJECT_ROOT / "data" / "processed" / "sentiment" / "ticker_sentiment_daily.parquet",
        ]
        sentiment_path = next((path for path in candidates if path.exists()), None)
        if sentiment_path is None:
            return []
        df = pd.read_parquet(sentiment_path)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["availability_date"] = pd.to_datetime(df["availability_date"], errors="coerce")
        as_of_ts = pd.Timestamp(as_of_datetime).tz_localize(None) if pd.Timestamp(as_of_datetime).tzinfo else pd.Timestamp(as_of_datetime)
        df = df[df["availability_date"] <= as_of_ts]
        if df.empty:
            return []
        latest_date = df["date"].max()
        df = df[df["date"] == latest_date].copy()
        df["sentiment_polarity"] = pd.to_numeric(df["sentiment_polarity"], errors="coerce").fillna(0.0)
        df["sentiment_conviction"] = pd.to_numeric(df["sentiment_conviction"], errors="coerce").fillna(0.0)
        flagged = df[
            (df["sentiment_conviction"] >= self.conviction_threshold)
            & (
                (df["sentiment_polarity"] <= self.negative_threshold)
                | (df["sentiment_polarity"] >= self.positive_threshold)
            )
        ].copy()

        signals: list[CompanySignal] = []
        for _, row in flagged.iterrows():
            ticker = str(row.get("ticker", "") or "")
            symbol = _normalize_symbol(ticker)
            polarity = float(row.get("sentiment_polarity", 0.0) or 0.0)
            conviction = float(row.get("sentiment_conviction", 0.0) or 0.0)
            direction = ShockDirection.BEARISH if polarity < 0 else ShockDirection.BULLISH
            severity = _severity_from_intensity(abs(polarity) * conviction)
            signals.append(
                CompanySignal(
                    ticker=ticker,
                    sector=self._resolve_sector(symbol),
                    signal_type=str(
                        row.get(
                            "dominant_event_type",
                            "sentiment_negative" if direction == ShockDirection.BEARISH else "sentiment_positive",
                        )
                    ),
                    direction=direction,
                    severity=severity if conviction >= self.conviction_threshold else ShockSeverity.LOW,
                    headline=f"Sentiment {polarity:+.2f} with conviction {conviction:.2f}",
                    source=str(row.get("source", "sentiment_pipeline") or "sentiment_pipeline"),
                    published_at=pd.Timestamp(row.get("date")).to_pydatetime(),
                    availability_date=pd.Timestamp(row.get("availability_date")).to_pydatetime(),
                    confidence=min(0.99, max(0.30, conviction)),
                    is_bellwether=symbol in self.bellwether_tickers,
                    estimated_stock_move_pct=round(abs(polarity) * conviction * (7.5 if direction == ShockDirection.BEARISH else 6.0), 2) * (-1.0 if direction == ShockDirection.BEARISH else 1.0),
                    related_tickers=[],
                )
            )
        return signals

    def _load_announcement_signals(self, as_of_datetime: datetime) -> list[CompanySignal]:
        candidate_paths = [
            PROJECT_ROOT / "data" / "canonical" / "alternative" / "announcements_all.parquet",
            PROJECT_ROOT / "data" / "processed" / "alternative" / "announcements_all.parquet",
            PROJECT_ROOT / "data" / "processed" / "alternative" / "announcements_all.csv",
        ]
        path = next((candidate for candidate in candidate_paths if candidate.exists()), None)
        if path is None:
            return []

        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        else:
            df = pd.read_parquet(path)
        if df.empty:
            return []
        df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
        window_start = pd.Timestamp(as_of_datetime) - pd.Timedelta(days=7)
        df = df[(df["date"] >= window_start) & (df["date"] <= pd.Timestamp(as_of_datetime))]
        if df.empty:
            return []

        signals: list[CompanySignal] = []
        for _, row in df.iterrows():
            ticker = _normalize_symbol(row.get("nse_ticker", row.get("ticker", "")))
            if not ticker:
                continue
            category = str(row.get("category", "") or "").upper()
            headline = str(row.get("headline", "") or "").strip()
            direction = None
            signal_type = ""
            severity = ShockSeverity.LOW
            confidence = 0.55

            if "ORDER WIN" in category or "CAPACITY EXPANSION" in category:
                direction = ShockDirection.BULLISH
                signal_type = "order_win"
                severity = ShockSeverity.MODERATE
                confidence = 0.70
            elif "REGULATORY" in category or "SEBI" in category:
                direction = ShockDirection.BEARISH
                signal_type = "regulatory_negative"
                severity = ShockSeverity.MODERATE
                confidence = 0.75
            elif "EARNINGS" in category and "MISS" in headline.upper():
                direction = ShockDirection.BEARISH
                signal_type = "earnings_miss"
                severity = ShockSeverity.MODERATE
                confidence = 0.75
            elif "EARNINGS" in category and any(token in headline.upper() for token in ["BEAT", "STRONG", "RECORD"]):
                direction = ShockDirection.BULLISH
                signal_type = "earnings_beat"
                severity = ShockSeverity.MODERATE
                confidence = 0.75

            if direction is None:
                continue

            published_at = pd.Timestamp(row.get("date")).to_pydatetime()
            signals.append(
                CompanySignal(
                    ticker=f"{ticker}.NS",
                    sector=self._resolve_sector(ticker),
                    signal_type=signal_type,
                    direction=direction,
                    severity=severity,
                    headline=headline or signal_type.replace("_", " "),
                    source="nse_announcements",
                    published_at=published_at,
                    availability_date=published_at + timedelta(minutes=15),
                    confidence=confidence,
                    is_bellwether=ticker in self.bellwether_tickers,
                    estimated_stock_move_pct=(2.5 if direction == ShockDirection.BULLISH else -2.5),
                    related_tickers=[],
                )
            )
        return signals

    def _build_sector_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}

        portfolio_weights_path = PROJECT_ROOT / "data" / "processed" / "portfolio_weights.parquet"
        if portfolio_weights_path.exists():
            try:
                weights_df = pd.read_parquet(portfolio_weights_path)
                for _, row in weights_df.iterrows():
                    symbol = _normalize_symbol(row.get("ticker", row.get("symbol", "")))
                    sector = str(row.get("Industry", row.get("sector", "")) or "").strip()
                    if symbol and sector in NIFTY500_SECTORS:
                        lookup[symbol] = sector
            except Exception:
                pass

        ticker_master_path = PROJECT_ROOT / "data" / "canonical" / "reference" / "ticker_master.parquet"
        if ticker_master_path.exists():
            try:
                master_df = pd.read_parquet(ticker_master_path)
                for _, row in master_df.iterrows():
                    symbol = _normalize_symbol(row.get("symbol", row.get("ticker", "")))
                    sector = str(row.get("sector", row.get("Industry", "")) or "").strip()
                    if symbol and sector in NIFTY500_SECTORS:
                        lookup[symbol] = sector
            except Exception:
                pass

        current_positions_path = PROJECT_ROOT / "data" / "portfolio" / "current_positions.json"
        if current_positions_path.exists():
            try:
                payload = json.loads(current_positions_path.read_text(encoding="utf-8"))
                for symbol, row in dict(payload.get("positions", {}) or {}).items():
                    normalized = _normalize_symbol(symbol)
                    sector = str((row or {}).get("sector", "") or "").strip()
                    if normalized and sector in NIFTY500_SECTORS:
                        lookup[normalized] = sector
            except Exception:
                pass

        try:
            from src.options.stock_options_loader import get_stock_loader

            loader = get_stock_loader()
            for symbol in loader.get_all_symbols():
                try:
                    stock = loader.get_stock(symbol)
                except Exception:
                    stock = None
                sector = str(getattr(stock, "sector", "") or "").strip()
                if symbol and sector in NIFTY500_SECTORS:
                    lookup[_normalize_symbol(symbol)] = sector
        except Exception:
            pass

        return lookup

    def _resolve_sector(self, symbol: str) -> str:
        return self._sector_cache.get(symbol, "Diversified")

    def _get_realtime(self) -> RealtimeScorer:
        if self._realtime is None:
            self._realtime = RealtimeScorer(self._root_config)
        return self._realtime

    @staticmethod
    def _map_direction(polarity: float) -> ShockDirection:
        if polarity <= -0.05:
            return ShockDirection.BEARISH
        if polarity >= 0.05:
            return ShockDirection.BULLISH
        return ShockDirection.NEUTRAL

    @staticmethod
    def _map_severity(magnitude: float, conviction: float, materiality: str) -> ShockSeverity:
        score = float(magnitude) * max(float(conviction), 0.25)
        if materiality == "high":
            score += 0.15
        if score >= 0.55:
            return ShockSeverity.HIGH
        if score >= 0.30:
            return ShockSeverity.MODERATE
        return ShockSeverity.LOW


def _normalize_symbol(value: Any) -> str:
    return str(value or "").replace(".NS", "").replace(".BO", "").strip().upper()


def _to_storage_ticker(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith(".NS") or text.endswith(".BO"):
        return text
    if "." in text:
        return text
    return f"{_normalize_symbol(text)}.NS"


def _severity_from_intensity(intensity: float) -> ShockSeverity:
    if intensity >= 0.70:
        return ShockSeverity.HIGH
    if intensity >= 0.45:
        return ShockSeverity.MODERATE
    return ShockSeverity.LOW
