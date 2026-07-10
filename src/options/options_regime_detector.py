"""
Options Regime Detector (legacy-compatible API)

This module provides the `src.options.options_regime_detector` interface expected by
the options stack and tests, while keeping behavior aligned with the unified
volatility engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

import numpy as np
import pandas as pd


class Regime(Enum):
    LOW_VOL_SELL = "low_vol_sell"
    HIGH_VOL_SELL = "high_vol_sell"
    RISING_VOL_BUY = "rising_vol_buy"
    CRASH_HEDGE = "crash_hedge"
    NEUTRAL = "neutral"


@dataclass
class RegimeMetrics:
    current_iv: float
    iv_rank: float
    iv_position: float
    iv_trend: str
    iv_5d_ma: float
    iv_20d_ma: float
    skew: float
    vol_of_vol_elevated: bool
    underlying_regime: str
    days_in_regime: int


@dataclass
class RegimeState:
    regime: Regime
    metrics: RegimeMetrics
    timestamp: datetime
    confidence: float
    reason: str

    @property
    def days_in_regime(self) -> int:
        return int(self.metrics.days_in_regime)


class RegimeDetector:
    """
    Regime detector for options strategy routing.

    Rules:
    - Equity crisis/high-stress always maps to CRASH_HEDGE.
    - Elevated vol-of-vol blocks short-vol (LOW_VOL_SELL/HIGH_VOL_SELL).
    - IV rank thresholds determine sell/buy/neutral states.
    """

    def __init__(self, config: Any):
        self.config = config
        self.iv_rank_lookback_days = int(self._cfg("iv_rank_lookback_days", 252))
        self.vol_of_vol_threshold = float(self._cfg("vol_of_vol_threshold", 1.5))
        self.regime_persistence_days = int(self._cfg("regime_persistence_days", 2))

        thresholds = self._cfg("thresholds", {}) or {}
        self.low_vol_sell_iv_rank = float(
            self._cfg("low_vol_sell_iv_rank", thresholds.get("low_vol_sell_iv_rank", 0.70))
        )
        self.high_vol_sell_iv_rank = float(
            self._cfg("high_vol_sell_iv_rank", thresholds.get("high_vol_sell_iv_rank", 0.80))
        )
        self.rising_vol_buy_iv_rank = float(
            self._cfg("rising_vol_buy_iv_rank", thresholds.get("rising_vol_buy_iv_rank", 0.30))
        )

        self._history: List[Regime] = []

    def _cfg(self, key: str, default: Any) -> Any:
        if hasattr(self.config, key):
            return getattr(self.config, key)
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return default

    def calculate_iv_rank(self, current_iv: float, iv_history: pd.Series) -> float:
        # NOTE: this returns the IV PERCENTILE (fraction of lookback days with IV
        # below current), in [0,1] — NOT the min-max "IV rank"
        # (current−min)/(max−min) that src/options/historical_data_loader.iv_rank
        # computes. The regime thresholds (low_vol_sell_iv_rank, etc.) are tuned
        # against THIS percentile definition; they are two different statistics
        # that share the name "iv_rank" — do not swap one for the other.
        s = pd.to_numeric(iv_history, errors="coerce").dropna()
        if s.empty:
            return 0.5
        lb = s.tail(max(2, self.iv_rank_lookback_days))
        return float((lb < float(current_iv)).sum()) / float(len(lb))

    def check_vol_of_vol(self, iv_history: pd.Series) -> bool:
        s = pd.to_numeric(iv_history, errors="coerce").dropna()
        if len(s) < 20:
            return False
        std_5 = float(s.tail(5).std(ddof=0))
        std_20 = float(s.tail(20).std(ddof=0))
        if std_20 <= 1e-9:
            return False
        return (std_5 / std_20) > self.vol_of_vol_threshold

    def _classify_iv_trend(self, iv_history: pd.Series) -> str:
        s = pd.to_numeric(iv_history, errors="coerce").dropna()
        if len(s) < 6:
            return "stable"
        short = float(s.tail(5).mean())
        long = float(s.tail(20).mean()) if len(s) >= 20 else float(s.mean())
        if short > long * 1.03:
            return "rising"
        if short < long * 0.97:
            return "falling"
        return "stable"

    def _calculate_skew(self, option_chain: pd.DataFrame) -> float:
        if option_chain is None or option_chain.empty:
            return 0.0

        df = option_chain.copy()
        if "iv" not in df.columns or "strike" not in df.columns:
            return 0.0

        df["iv"] = pd.to_numeric(df["iv"], errors="coerce")
        df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
        df = df.dropna(subset=["iv", "strike"])
        if df.empty:
            return 0.0

        if "underlying_price" in df.columns:
            spot = pd.to_numeric(df["underlying_price"], errors="coerce").dropna()
            if spot.empty:
                return 0.0
            spot = float(spot.iloc[0])
        else:
            # Fallback spot estimate from strike median.
            spot = float(df["strike"].median())

        if spot <= 0:
            return 0.0

        option_col = "option_type" if "option_type" in df.columns else None
        if option_col is None:
            return 0.0
        df[option_col] = df[option_col].astype(str).str.upper()

        # Use near-ATM OTM put and OTM call to proxy skew.
        call = df[(df[option_col].isin(["C", "CE"])) & (df["strike"] >= spot)].copy()
        put = df[(df[option_col].isin(["P", "PE"])) & (df["strike"] <= spot)].copy()
        if call.empty or put.empty:
            return 0.0

        call["dist"] = (call["strike"] - spot).abs()
        put["dist"] = (put["strike"] - spot).abs()
        call_iv = float(call.sort_values("dist").iloc[0]["iv"])
        put_iv = float(put.sort_values("dist").iloc[0]["iv"])
        return put_iv - call_iv

    def _estimate_current_iv(
        self,
        option_chain: pd.DataFrame,
        iv_history: pd.Series,
    ) -> float:
        """
        Estimate current IV from today's chain first, then IV history fallback.

        Using chain IV prevents stale-history bias where the latest history point
        can dominate classification even when the current snapshot has shifted.
        """
        df = option_chain.copy() if option_chain is not None else pd.DataFrame()
        if not df.empty and {"iv", "strike"}.issubset(df.columns):
            local = df.copy()
            local["iv"] = pd.to_numeric(local["iv"], errors="coerce")
            local["strike"] = pd.to_numeric(local["strike"], errors="coerce")
            local = local.dropna(subset=["iv", "strike"])

            if not local.empty:
                if "underlying_price" in local.columns:
                    spot_s = pd.to_numeric(local["underlying_price"], errors="coerce").dropna()
                    spot = float(spot_s.iloc[0]) if not spot_s.empty else float(local["strike"].median())
                else:
                    spot = float(local["strike"].median())

                local["dist"] = (local["strike"] - spot).abs()
                atm_slice = local.sort_values("dist").head(6)
                if not atm_slice.empty:
                    return float(atm_slice["iv"].median())

        history = pd.to_numeric(iv_history, errors="coerce").dropna()
        if not history.empty:
            return float(history.iloc[-1])

        return 0.15

    def _update_regime_history(self, regime: Regime) -> None:
        self._history.append(regime)
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

    def check_regime_persistence(self, regime: Regime) -> bool:
        if not self._history:
            return False
        cnt = 0
        for r in reversed(self._history):
            if r == regime:
                cnt += 1
            else:
                break
        return cnt >= self.regime_persistence_days

    def _days_in_regime(self, regime: Regime) -> int:
        cnt = 0
        for r in reversed(self._history):
            if r == regime:
                cnt += 1
            else:
                break
        return cnt

    def detect_regime(
        self,
        option_chain: pd.DataFrame,
        iv_history: pd.Series,
        underlying_regime: str = "NORMAL",
    ) -> RegimeState:
        now = datetime.now(timezone.utc)
        df = option_chain.copy() if option_chain is not None else pd.DataFrame()

        iv_series = pd.to_numeric(iv_history, errors="coerce").dropna()
        current_iv = self._estimate_current_iv(df, iv_series)

        iv_rank = self.calculate_iv_rank(current_iv, iv_series if not iv_series.empty else pd.Series([current_iv]))
        iv_5d_ma = float(iv_series.tail(5).mean()) if not iv_series.empty else current_iv
        iv_20d_ma = float(iv_series.tail(20).mean()) if not iv_series.empty else current_iv
        iv_trend = self._classify_iv_trend(iv_series if not iv_series.empty else pd.Series([current_iv]))
        vol_of_vol_elevated = self.check_vol_of_vol(iv_series if not iv_series.empty else pd.Series([current_iv]))
        skew = self._calculate_skew(df)
        underlying = str(underlying_regime or "NORMAL").upper()

        reason = "IV/risk conditions neutral"
        confidence = 0.65
        regime = Regime.NEUTRAL

        if underlying in {"CRISIS", "HIGH_STRESS"}:
            regime = Regime.CRASH_HEDGE
            reason = f"Underlying regime {underlying} enforces crash hedge"
            confidence = 0.95
        else:
            if vol_of_vol_elevated:
                # Elevated vol-of-vol blocks short-vol strategies.
                if iv_rank <= self.rising_vol_buy_iv_rank or iv_trend == "rising":
                    regime = Regime.RISING_VOL_BUY
                    reason = "Vol-of-vol elevated with low/rising IV rank"
                    confidence = 0.75
                else:
                    regime = Regime.NEUTRAL
                    reason = "Vol-of-vol elevated; short-vol blocked"
                    confidence = 0.70
            else:
                if iv_rank >= self.high_vol_sell_iv_rank:
                    regime = Regime.HIGH_VOL_SELL
                    reason = "IV rank above high-vol sell threshold"
                    confidence = 0.85
                elif iv_rank >= self.low_vol_sell_iv_rank:
                    regime = Regime.LOW_VOL_SELL
                    reason = "IV rank above low-vol sell threshold"
                    confidence = 0.80
                elif iv_rank <= self.rising_vol_buy_iv_rank or iv_trend == "rising":
                    regime = Regime.RISING_VOL_BUY
                    reason = "IV rank low or trend rising"
                    confidence = 0.75
                else:
                    regime = Regime.NEUTRAL
                    reason = "No high-confidence regime edge"
                    confidence = 0.60

        self._update_regime_history(regime)
        days = self._days_in_regime(regime)

        metrics = RegimeMetrics(
            current_iv=float(current_iv),
            iv_rank=float(iv_rank),
            iv_position=float(iv_rank),
            iv_trend=str(iv_trend),
            iv_5d_ma=float(iv_5d_ma),
            iv_20d_ma=float(iv_20d_ma),
            skew=float(skew),
            vol_of_vol_elevated=bool(vol_of_vol_elevated),
            underlying_regime=underlying,
            days_in_regime=int(days),
        )

        return RegimeState(
            regime=regime,
            metrics=metrics,
            timestamp=now,
            confidence=float(np.clip(confidence, 0.0, 1.0)),
            reason=reason,
        )
