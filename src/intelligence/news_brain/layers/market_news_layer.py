from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.nlp.pipeline.realtime_scorer import RealtimeScorer
from src.intelligence.news_brain.news_signal_state import (
    IVRegime,
    MarketSignal,
    ShockDirection,
    ShockSeverity,
    iv_regime_from_vix,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class MarketNewsLayer:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._root_config = dict(config or {})
        brain_cfg = dict(self._root_config.get("news_brain", self._root_config) or {})
        cfg = dict(brain_cfg.get("market_layer", {}) or {})
        self.fii_outflow_threshold_crores = float(cfg.get("fii_outflow_threshold_crores", 3000.0))
        self.fii_high_severity_crores = float(cfg.get("fii_high_severity_crores", 8000.0))
        self.breadth_stress_threshold = float(cfg.get("breadth_stress_threshold", 0.30))
        self.news_lookback_days = int(cfg.get("fresh_news_lookback_days", 2))
        self._realtime: RealtimeScorer | None = None

    def run(self, as_of_datetime: datetime) -> dict[str, Any]:
        context = {
            "market_signals": [],
            "vix_level": 0.0,
            "iv_regime": IVRegime.NORMAL,
            "fii_net_crores": 0.0,
            "dii_net_crores": 0.0,
            "breadth_pct": 50.0,
            "crude_change_pct": 0.0,
            "inr_change_pct": 0.0,
            "latest_data_at": None,
        }

        market_state_path = PROJECT_ROOT / "data" / "processed" / "market_state.parquet"
        if not market_state_path.exists():
            return context

        df = pd.read_parquet(market_state_path)
        if df.empty:
            return context

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df[df["date"] <= pd.Timestamp(as_of_datetime)]
        if df.empty:
            return context
        latest = df.sort_values("date").iloc[-1]
        latest_dt = pd.Timestamp(latest.get("date", as_of_datetime)).to_pydatetime()

        vix_level = self._infer_vix_level(latest)
        breadth_pct = float(pd.to_numeric(latest.get("breadth_pct", 50.0), errors="coerce") or 50.0)
        fii_net_crores = self._load_fii_net_crores(as_of_datetime)
        dii_net_crores = self._load_dii_net_crores(as_of_datetime)
        crude_change_pct = float(pd.to_numeric(latest.get("crude_price_change_pct", 0.0), errors="coerce") or 0.0)
        inr_change_pct = float(pd.to_numeric(latest.get("inr_change_pct", 0.0), errors="coerce") or 0.0)

        signals: list[MarketSignal] = []
        signals.extend(self._load_market_news_signals(as_of_datetime))
        if fii_net_crores <= -self.fii_outflow_threshold_crores:
            severity = ShockSeverity.HIGH if fii_net_crores <= -self.fii_high_severity_crores else ShockSeverity.MODERATE
            signals.append(
                MarketSignal(
                    signal_type="fii_outflow",
                    direction=ShockDirection.BEARISH,
                    severity=severity,
                    headline=f"FII net sell {abs(fii_net_crores):,.0f} crores",
                    source="market_flows",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.80 if severity >= ShockSeverity.HIGH else 0.68,
                    estimated_nifty_move_pct=-2.2 if severity >= ShockSeverity.HIGH else -1.0,
                    affected_sectors=["Financial Services", "Information Technology", "Metals & Mining"],
                    fii_net_flow_crores=fii_net_crores,
                    dii_net_flow_crores=dii_net_crores,
                )
            )

        if breadth_pct / 100.0 <= self.breadth_stress_threshold:
            signals.append(
                MarketSignal(
                    signal_type="broad_market_stress",
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.MODERATE,
                    headline=f"Market breadth weak at {breadth_pct:.1f}%",
                    source="market_state",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.62,
                    estimated_nifty_move_pct=-0.8,
                    affected_sectors=[],
                    fii_net_flow_crores=fii_net_crores,
                    dii_net_flow_crores=dii_net_crores,
                )
            )

        if crude_change_pct >= 5.0:
            signals.append(
                MarketSignal(
                    signal_type="oil_price_spike",
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.SEVERE if crude_change_pct >= 15.0 else ShockSeverity.HIGH,
                    headline=f"Crude move {crude_change_pct:+.1f}%",
                    source="market_state",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.78,
                    estimated_nifty_move_pct=-1.4 if crude_change_pct < 15.0 else -3.0,
                    affected_sectors=["Services", "Chemicals", "Automobile and Auto Components"],
                    fii_net_flow_crores=fii_net_crores,
                    dii_net_flow_crores=dii_net_crores,
                )
            )

        if inr_change_pct <= -1.5:
            signals.append(
                MarketSignal(
                    signal_type="inr_depreciation",
                    direction=ShockDirection.MIXED,
                    severity=ShockSeverity.HIGH,
                    headline=f"INR move {inr_change_pct:+.1f}%",
                    source="market_state",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.75,
                    estimated_nifty_move_pct=-1.0,
                    affected_sectors=["Information Technology", "Oil Gas & Consumable Fuels", "Services"],
                    fii_net_flow_crores=fii_net_crores,
                    dii_net_flow_crores=dii_net_crores,
                )
            )

        context.update(
            {
                "market_signals": self._dedupe_signals(signals),
                "vix_level": vix_level,
                "iv_regime": iv_regime_from_vix(vix_level),
                "fii_net_crores": fii_net_crores,
                "dii_net_crores": dii_net_crores,
                "breadth_pct": breadth_pct,
                "crude_change_pct": crude_change_pct,
                "inr_change_pct": inr_change_pct,
                "latest_data_at": max(
                    [latest_dt, *[signal.availability_date for signal in signals if getattr(signal, "availability_date", None)]],
                    default=latest_dt,
                ),
            }
        )
        return context

    def _load_market_news_signals(self, as_of_datetime: datetime) -> list[MarketSignal]:
        path = PROJECT_ROOT / "data" / "canonical" / "news" / "market_news_history.parquet"
        if not path.exists():
            return []
        df = pd.read_parquet(path, columns=["headline", "source", "date", "availability_date"])
        if df.empty:
            return []
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["availability_date"] = pd.to_datetime(df["availability_date"], errors="coerce")
        as_of_ts = pd.Timestamp(as_of_datetime).tz_localize(None) if pd.Timestamp(as_of_datetime).tzinfo else pd.Timestamp(as_of_datetime)
        eligible = df[df["availability_date"] <= as_of_ts].copy()
        if eligible.empty:
            return []
        latest_availability = eligible["availability_date"].max()
        recent = eligible[eligible["availability_date"] >= latest_availability - pd.Timedelta(days=self.news_lookback_days)].copy()
        scorer = self._get_realtime()
        signals: list[MarketSignal] = []
        for _, row in recent.iterrows():
            headline = str(row.get("headline", "") or "").strip()
            if len(headline) < 10:
                continue
            nlp = scorer.score_single(
                headline=headline,
                published_at=pd.Timestamp(row["date"]).to_pydatetime(),
                source=str(row.get("source", "market_news") or "market_news"),
            )
            if nlp is None or nlp.conviction < 0.55:
                continue
            if not (nlp.is_market_moving or (nlp.event and nlp.event.is_macro_event)):
                continue
            direction = self._direction_from_polarity(nlp.polarity)
            severity = self._severity_from_result(abs(nlp.polarity), nlp.conviction, nlp.event.materiality if nlp.event else "low")
            signals.append(
                MarketSignal(
                    signal_type=nlp.event.event_type if nlp.event else "market_news",
                    direction=direction,
                    severity=severity,
                    headline=headline,
                    source=str(row.get("source", "market_news") or "market_news"),
                    published_at=pd.Timestamp(row["date"]).to_pydatetime(),
                    availability_date=nlp.availability_date or pd.Timestamp(row["availability_date"]).to_pydatetime(),
                    confidence=float(nlp.conviction),
                    estimated_nifty_move_pct=round(abs(float(nlp.polarity)) * float(nlp.conviction) * 2.5, 2)
                    * (-1.0 if direction == ShockDirection.BEARISH else 1.0),
                    affected_sectors=[],
                )
            )
        return signals

    def _load_fii_net_crores(self, as_of_datetime: datetime) -> float:
        path = PROJECT_ROOT / "data" / "raw" / "shared" / "alternative" / "fii_dii_flows.csv"
        if not path.exists():
            return 0.0
        df = pd.read_csv(path)
        if df.empty:
            return 0.0
        date_col = next((col for col in df.columns if "date" in col.lower()), None)
        fii_col = next((col for col in df.columns if "fii" in col.lower() and "net" in col.lower()), None)
        if not date_col or not fii_col:
            return 0.0
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df[date_col] <= pd.Timestamp(as_of_datetime)]
        if df.empty:
            return 0.0
        return float(pd.to_numeric(df.sort_values(date_col).iloc[-1].get(fii_col), errors="coerce") or 0.0)

    def _load_dii_net_crores(self, as_of_datetime: datetime) -> float:
        path = PROJECT_ROOT / "data" / "raw" / "shared" / "alternative" / "fii_dii_flows.csv"
        if not path.exists():
            return 0.0
        df = pd.read_csv(path)
        if df.empty:
            return 0.0
        date_col = next((col for col in df.columns if "date" in col.lower()), None)
        dii_col = next((col for col in df.columns if "dii" in col.lower() and "net" in col.lower()), None)
        if not date_col or not dii_col:
            return 0.0
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[df[date_col] <= pd.Timestamp(as_of_datetime)]
        if df.empty:
            return 0.0
        return float(pd.to_numeric(df.sort_values(date_col).iloc[-1].get(dii_col), errors="coerce") or 0.0)

    @staticmethod
    def _infer_vix_level(row: pd.Series) -> float:
        for key in ["india_vix", "vix", "india_vix_close"]:
            value = pd.to_numeric(row.get(key), errors="coerce")
            if pd.notna(value):
                return float(value)
        volatility_regime = str(row.get("volatility_regime", "") or "").strip().lower()
        if volatility_regime in {"low", "low_vol"}:
            return 12.5
        if volatility_regime in {"elevated", "medium"}:
            return 20.0
        if volatility_regime in {"high", "crisis"}:
            return 28.0 if volatility_regime == "high" else 36.0
        return 15.5

    def _get_realtime(self) -> RealtimeScorer:
        if self._realtime is None:
            self._realtime = RealtimeScorer(self._root_config)
        return self._realtime

    @staticmethod
    def _direction_from_polarity(polarity: float) -> ShockDirection:
        if polarity <= -0.05:
            return ShockDirection.BEARISH
        if polarity >= 0.05:
            return ShockDirection.BULLISH
        return ShockDirection.NEUTRAL

    @staticmethod
    def _severity_from_result(magnitude: float, conviction: float, materiality: str) -> ShockSeverity:
        score = float(magnitude) * max(float(conviction), 0.25)
        if materiality == "high":
            score += 0.20
        if score >= 0.60:
            return ShockSeverity.HIGH
        if score >= 0.35:
            return ShockSeverity.MODERATE
        return ShockSeverity.LOW

    @staticmethod
    def _dedupe_signals(signals: list[MarketSignal]) -> list[MarketSignal]:
        deduped: dict[tuple[str, str], MarketSignal] = {}
        for signal in signals:
            key = (signal.signal_type, signal.headline)
            current = deduped.get(key)
            if current is None or (signal.severity.value, signal.confidence) > (current.severity.value, current.confidence):
                deduped[key] = signal
        return list(deduped.values())
