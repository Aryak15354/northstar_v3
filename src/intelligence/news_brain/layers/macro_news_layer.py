from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from src.nlp.pipeline.realtime_scorer import RealtimeScorer
from src.intelligence.news_brain.news_signal_state import MacroSignal, ShockDirection, ShockSeverity, ShockType
from src.intelligence.news_brain.shock_classifier import EVENT_TYPE_TO_SHOCK
from src.intelligence.shock_engine.shock_knowledge_base import get_shock_profile


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class MacroNewsLayer:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._root_config = dict(config or {})
        brain_cfg = dict(self._root_config.get("news_brain", self._root_config) or {})
        cfg = dict(brain_cfg.get("macro_layer", {}) or {})
        self.crude_spike_threshold_pct = float(cfg.get("crude_spike_threshold_pct", 5.0))
        self.crude_disruption_threshold_pct = float(cfg.get("crude_disruption_threshold_pct", 15.0))
        self.inr_depreciation_threshold_pct = float(cfg.get("inr_depreciation_threshold_pct", 1.5))
        self.news_lookback_days = int(cfg.get("fresh_news_lookback_days", 2))
        self._realtime: RealtimeScorer | None = None

    def run(self, as_of_datetime: datetime) -> dict[str, Any]:
        context = {
            "macro_signals": [],
            "rbi_stance": "neutral",
            "global_risk_appetite": "neutral",
            "crude_change_pct": 0.0,
            "inr_change_pct": 0.0,
            "latest_data_at": None,
        }

        macro_path = PROJECT_ROOT / "data" / "macro" / "comprehensive_rbi_data.parquet"
        if not macro_path.exists():
            return context

        df = pd.read_parquet(macro_path)
        if df.empty:
            return context
        if isinstance(df.index, pd.DatetimeIndex):
            work = df[df.index <= pd.Timestamp(as_of_datetime)].copy()
            work = work.sort_index()
        else:
            work = df.copy()
        if work.empty:
            return context

        repo_series = self._series(work, ["weekly_core_Policy Repo Rate (%)", "daily_other_REPO RATE (OVERNIGHT)"])
        inr_series = self._series(work, ["daily_other_RBI'S REFERENCE RATE: INR PER USD", "monthly_core_Exchange Rate of Indian Rupee vis-à-vis US Dollar (Month End)"])
        gsec_series = self._series(work, ["weekly_core_10-Year G-Sec Yield (FBIL) (%)"])
        nifty_series = self._series(work, ["daily_other_NSE S&P CNX NIFTY"])

        signals: list[MacroSignal] = self._load_macro_news_signals(as_of_datetime)
        latest_dt = work.index.max().to_pydatetime() if isinstance(work.index, pd.DatetimeIndex) else as_of_datetime

        repo_rate = float(repo_series.iloc[-1]) if len(repo_series) else 0.0
        repo_prev = float(repo_series.iloc[-2]) if len(repo_series) >= 2 else repo_rate
        inr_ref = float(inr_series.iloc[-1]) if len(inr_series) else 0.0
        inr_prev = float(inr_series.iloc[-2]) if len(inr_series) >= 2 else inr_ref
        gsec = float(gsec_series.iloc[-1]) if len(gsec_series) else 0.0
        gsec_prev = float(gsec_series.iloc[-2]) if len(gsec_series) >= 2 else gsec
        nifty = float(nifty_series.iloc[-1]) if len(nifty_series) else 0.0
        nifty_prev = float(nifty_series.iloc[-2]) if len(nifty_series) >= 2 else nifty

        crude_change_pct = self._infer_crude_change(work, nifty, nifty_prev)
        inr_change_pct = ((inr_ref - inr_prev) / inr_prev * 100.0) if inr_prev else 0.0
        gsec_change_bps = (gsec - gsec_prev) * 100.0

        rbi_stance = "neutral"
        if repo_rate > repo_prev + 0.001:
            rbi_stance = "hawkish"
            signals.append(
                MacroSignal(
                    signal_type="rbi_rate_hike",
                    shock_type=ShockType.RATE_HIKE_RBI,
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.MODERATE,
                    headline=f"RBI repo rate increased to {repo_rate:.2f}%",
                    source="rbi_macro",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.90,
                    is_rbi=True,
                    estimated_nifty_move_pct=-1.0,
                    affected_sectors=["Financial Services", "Realty", "Consumer Durables"],
                )
            )
        elif repo_rate < repo_prev - 0.001:
            rbi_stance = "dovish"
            signals.append(
                MacroSignal(
                    signal_type="rbi_rate_cut",
                    shock_type=ShockType.RATE_CUT_RBI,
                    direction=ShockDirection.BULLISH,
                    severity=ShockSeverity.MODERATE,
                    headline=f"RBI repo rate decreased to {repo_rate:.2f}%",
                    source="rbi_macro",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.90,
                    is_rbi=True,
                    estimated_nifty_move_pct=+1.0,
                    affected_sectors=["Financial Services", "Realty", "Automobile and Auto Components"],
                )
            )

        if crude_change_pct >= self.crude_disruption_threshold_pct:
            signals.append(
                MacroSignal(
                    signal_type="crude_disruption",
                    shock_type=ShockType.OIL_SUPPLY_DISRUPTION,
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.SEVERE,
                    headline=f"Crude proxy move {crude_change_pct:+.1f}%",
                    source="macro_proxy",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.70,
                    crude_price_change_pct=crude_change_pct,
                    estimated_nifty_move_pct=-3.0,
                    affected_sectors=["Services", "Chemicals", "Oil Gas & Consumable Fuels"],
                )
            )
        elif crude_change_pct >= self.crude_spike_threshold_pct:
            signals.append(
                MacroSignal(
                    signal_type="crude_spike",
                    shock_type=ShockType.OIL_PRICE_SPIKE,
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.HIGH,
                    headline=f"Crude proxy move {crude_change_pct:+.1f}%",
                    source="macro_proxy",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.62,
                    crude_price_change_pct=crude_change_pct,
                    estimated_nifty_move_pct=-1.5,
                    affected_sectors=["Services", "Automobile and Auto Components", "Chemicals"],
                )
            )

        if inr_change_pct >= self.inr_depreciation_threshold_pct:
            signals.append(
                MacroSignal(
                    signal_type="inr_depreciation",
                    shock_type=ShockType.INR_DEPRECIATION,
                    direction=ShockDirection.MIXED,
                    severity=ShockSeverity.HIGH,
                    headline=f"INR/USD reference rate move {inr_change_pct:+.1f}%",
                    source="rbi_fx",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.78,
                    inr_usd_change_pct=-inr_change_pct,
                    estimated_nifty_move_pct=-1.0,
                    affected_sectors=["Information Technology", "Oil Gas & Consumable Fuels", "Services"],
                )
            )
        elif inr_change_pct <= -self.inr_depreciation_threshold_pct:
            signals.append(
                MacroSignal(
                    signal_type="inr_appreciation",
                    shock_type=ShockType.INR_APPRECIATION,
                    direction=ShockDirection.MIXED,
                    severity=ShockSeverity.MODERATE,
                    headline=f"INR/USD reference rate move {inr_change_pct:+.1f}%",
                    source="rbi_fx",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.70,
                    inr_usd_change_pct=-inr_change_pct,
                    estimated_nifty_move_pct=+0.6,
                    affected_sectors=["Information Technology", "Consumer Durables", "Oil Gas & Consumable Fuels"],
                )
            )

        if gsec_change_bps >= 20.0:
            signals.append(
                MacroSignal(
                    signal_type="global_yield_shock",
                    shock_type=ShockType.RATE_HIKE_FED,
                    direction=ShockDirection.BEARISH,
                    severity=ShockSeverity.MODERATE,
                    headline=f"10Y G-Sec yield jumped {gsec_change_bps:.0f} bps",
                    source="rates_proxy",
                    published_at=latest_dt,
                    availability_date=latest_dt,
                    confidence=0.58,
                    is_fed=True,
                    estimated_nifty_move_pct=-1.2,
                    affected_sectors=["Financial Services", "Capital Goods", "Realty"],
                )
            )

        global_risk_appetite = "neutral"
        if nifty_prev and nifty and ((nifty - nifty_prev) / nifty_prev * 100.0) <= -2.0:
            global_risk_appetite = "risk_off"

        context.update(
            {
                "macro_signals": self._dedupe_signals(signals),
                "rbi_stance": rbi_stance,
                "global_risk_appetite": global_risk_appetite,
                "crude_change_pct": crude_change_pct,
                "inr_change_pct": -inr_change_pct,
                "latest_data_at": max(
                    [latest_dt, *[signal.availability_date for signal in signals if getattr(signal, "availability_date", None)]],
                    default=latest_dt,
                ),
            }
        )
        return context

    def _load_macro_news_signals(self, as_of_datetime: datetime) -> list[MacroSignal]:
        path = PROJECT_ROOT / "data" / "canonical" / "news" / "market_news_history.parquet"
        if not path.exists():
            return []
        wanted = ["headline", "source", "date", "availability_date"]
        available = set(pq.ParquetFile(path).schema.names)
        df = pd.read_parquet(path, columns=[col for col in wanted if col in available])
        if df.empty:
            return []
        for column in wanted:
            if column not in df.columns:
                df[column] = "macro_news" if column == "source" else pd.NaT
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["availability_date"] = pd.to_datetime(df["availability_date"], errors="coerce")
        df["availability_date"] = df["availability_date"].fillna(df["date"])
        df = df.dropna(subset=["headline", "date", "availability_date"])
        if df.empty:
            return []
        as_of_ts = pd.Timestamp(as_of_datetime).tz_localize(None) if pd.Timestamp(as_of_datetime).tzinfo else pd.Timestamp(as_of_datetime)
        eligible = df[df["availability_date"] <= as_of_ts].copy()
        if eligible.empty:
            return []
        latest_availability = eligible["availability_date"].max()
        recent = eligible[eligible["availability_date"] >= latest_availability - pd.Timedelta(days=self.news_lookback_days)].copy()
        scorer = self._get_realtime()
        signals: list[MacroSignal] = []
        for _, row in recent.iterrows():
            headline = str(row.get("headline", "") or "").strip()
            if len(headline) < 10:
                continue
            nlp = scorer.score_single(
                headline=headline,
                published_at=pd.Timestamp(row["date"]).to_pydatetime(),
                source=str(row.get("source", "macro_news") or "macro_news"),
            )
            if nlp is None or nlp.event is None or not nlp.event.is_macro_event or nlp.conviction < 0.55:
                continue
            shock_type = EVENT_TYPE_TO_SHOCK.get(nlp.event.event_type, ShockType.NONE)
            if shock_type == ShockType.NONE:
                continue
            profile = get_shock_profile(shock_type.value)
            affected = [
                sector
                for sector, payload in profile.get("sector_impacts", {}).items()
                if abs(float(payload.get("score", 0.0) or 0.0)) >= 0.25
            ][:5]
            direction = self._direction_from_polarity(nlp.polarity, nlp.event.expected_direction)
            signals.append(
                MacroSignal(
                    signal_type=nlp.event.event_type,
                    shock_type=shock_type,
                    direction=direction,
                    severity=self._severity_from_result(abs(nlp.polarity), nlp.conviction, nlp.event.materiality),
                    headline=headline,
                    source=str(row.get("source", "macro_news") or "macro_news"),
                    published_at=pd.Timestamp(row["date"]).to_pydatetime(),
                    availability_date=nlp.availability_date or pd.Timestamp(row["availability_date"]).to_pydatetime(),
                    confidence=float(nlp.conviction),
                    is_rbi=shock_type in {ShockType.RATE_HIKE_RBI, ShockType.RATE_CUT_RBI},
                    is_geopolitical=shock_type == ShockType.GEOPOLITICAL_CONFLICT,
                    estimated_nifty_move_pct=round(abs(float(profile.get("market_level_impact", 0.0) or 0.0)) * 100.0, 2)
                    * (-1.0 if direction == ShockDirection.BEARISH else 1.0),
                    affected_sectors=affected,
                )
            )
        return signals

    @staticmethod
    def _series(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
        for column in candidates:
            if column in df.columns:
                series = pd.to_numeric(df[column], errors="coerce").dropna()
                if not series.empty:
                    return series
        return pd.Series(dtype=float)

    @staticmethod
    def _infer_crude_change(df: pd.DataFrame, nifty: float, nifty_prev: float) -> float:
        crude_cols = [column for column in df.columns if "crude" in column.lower() or "brent" in column.lower() or "wti" in column.lower()]
        for column in crude_cols:
            series = pd.to_numeric(df[column], errors="coerce").dropna()
            if len(series) >= 2 and float(series.iloc[-2]) != 0.0:
                return float((series.iloc[-1] - series.iloc[-2]) / series.iloc[-2] * 100.0)
        if nifty_prev:
            return max(0.0, min(18.0, abs((nifty - nifty_prev) / nifty_prev * 100.0) * 4.0))
        return 0.0

    def _get_realtime(self) -> RealtimeScorer:
        if self._realtime is None:
            self._realtime = RealtimeScorer(self._root_config)
        return self._realtime

    @staticmethod
    def _direction_from_polarity(polarity: float, event_direction: str) -> ShockDirection:
        if polarity <= -0.05 or event_direction == "negative":
            return ShockDirection.BEARISH
        if polarity >= 0.05 or event_direction == "positive":
            return ShockDirection.BULLISH
        return ShockDirection.NEUTRAL

    @staticmethod
    def _severity_from_result(magnitude: float, conviction: float, materiality: str) -> ShockSeverity:
        score = float(magnitude) * max(float(conviction), 0.25)
        if materiality == "high":
            score += 0.25
        if score >= 0.65:
            return ShockSeverity.HIGH
        if score >= 0.35:
            return ShockSeverity.MODERATE
        return ShockSeverity.LOW

    @staticmethod
    def _dedupe_signals(signals: list[MacroSignal]) -> list[MacroSignal]:
        deduped: dict[tuple[ShockType, str], MacroSignal] = {}
        for signal in signals:
            key = (signal.shock_type, signal.headline)
            current = deduped.get(key)
            if current is None or (signal.severity.value, signal.confidence) > (current.severity.value, current.confidence):
                deduped[key] = signal
        return list(deduped.values())
