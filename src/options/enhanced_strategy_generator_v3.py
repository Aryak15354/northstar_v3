"""
Enhanced Strategy Generator V3 for Options Paper Engine.

This generator is used by the live integrated options engine and must be
resilient across imperfect option-chain snapshots. It returns multiple valid
strategy candidates so the engine can optimize by objective (hedge/income/alpha).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from src.options.strategy_generator import Greeks, OptionLeg, OptionStrategy, StrategyType
from src.volatility.regime_detector import VolatilityRegime

logger = logging.getLogger(__name__)


class EnhancedStrategyGeneratorV3:
    """Robust strategy generator with multi-strategy candidate support."""

    def __init__(self, config: Any):
        self.config = config
        logger.info("Enhanced strategy generator V3 initialized")

    def _min_eligible_days_to_expiry(self) -> int:
        eligibility = getattr(self.config, "eligibility", None)
        try:
            return max(1, int(getattr(eligibility, "min_days_to_expiry", 5) or 5))
        except Exception:
            return 5

    def generate_strategy(
        self,
        regime: Any,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        implied_vol: float = 0.20,
        risk_free_rate: float = 0.05,
        preferred_strategy: Optional[str] = None,
    ) -> List[OptionStrategy]:
        """
        Generate one or more valid strategy candidates.

        Args:
            regime: Regime enum/string.
            underlying: Underlying symbol.
            option_chain: Option-chain snapshot.
            spot_price: Current spot.
            implied_vol: Unused, kept for compatibility.
            risk_free_rate: Unused, kept for compatibility.
            preferred_strategy: Optional strategy token to prioritize.
        """
        del implied_vol, risk_free_rate

        chain = self._prepare_chain(option_chain)
        if chain.empty:
            return []

        spot = self._resolve_spot(chain, spot_price)
        regime_key = self._normalize_regime(regime)
        min_eligible_days = self._min_eligible_days_to_expiry()
        near_expiry = self._select_expiry(
            chain,
            min_days=min_eligible_days,
            max_days=max(28, min_eligible_days + 23),
            target_days=max(14, min_eligible_days + 9),
            allow_any_future_fallback=False,
        )
        far_expiry = self._select_expiry(
            chain,
            min_days=max(18, min_eligible_days + 13),
            max_days=70,
            target_days=max(35, min_eligible_days + 20),
            allow_any_future_fallback=False,
        )

        if near_expiry is None:
            near_expiry = self._select_expiry(
                chain,
                min_days=min_eligible_days,
                max_days=120,
                target_days=max(21, min_eligible_days + 10),
                allow_any_future_fallback=False,
            )
        if far_expiry is None:
            far_expiry = self._select_expiry(
                chain,
                min_days=max(10, min_eligible_days + 7),
                max_days=120,
                target_days=max(40, min_eligible_days + 25),
                allow_any_future_fallback=False,
            )

        if near_expiry is None:
            near_expiry = self._select_expiry(
                chain,
                min_days=1,
                max_days=120,
                target_days=max(10, min_eligible_days),
            )
        if near_expiry is None:
            return []

        order = self._strategy_order_for_regime(regime_key)
        if preferred_strategy:
            pref = self._normalize_strategy_name(preferred_strategy)
            order = [pref] + [name for name in order if name != pref]

        builders = {
            "iron_condor": lambda: self._build_iron_condor(chain, underlying, spot, near_expiry, regime_key),
            "iron_butterfly": lambda: self._build_iron_butterfly(chain, underlying, spot, near_expiry, regime_key),
            "calendar_spread": lambda: self._build_calendar_spread(chain, underlying, spot, near_expiry, far_expiry, regime_key),
            "long_straddle": lambda: self._build_long_straddle(chain, underlying, spot, near_expiry, regime_key),
            "long_strangle": lambda: self._build_long_strangle(chain, underlying, spot, near_expiry, regime_key),
            "short_strangle": lambda: self._build_short_strangle(chain, underlying, spot, near_expiry, regime_key),
            "bull_call_spread": lambda: self._build_bull_call_spread(chain, underlying, spot, near_expiry, regime_key),
            "bear_put_spread": lambda: self._build_bear_put_spread(chain, underlying, spot, near_expiry, regime_key),
        }

        out: List[OptionStrategy] = []
        seen: set[str] = set()
        for name in order:
            builder = builders.get(name)
            if builder is None:
                continue
            try:
                strategy = builder()
            except Exception as exc:
                logger.warning("Strategy build failed for %s %s: %s", underlying, name, exc)
                continue
            if strategy is None or not strategy.is_valid:
                continue
            token = strategy.strategy_type.value
            if token in seen:
                continue
            seen.add(token)
            out.append(strategy)

        return out

    @staticmethod
    def _normalize_option_type(value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in {"C", "CALL", "CE"}:
            return "CE"
        if text in {"P", "PUT", "PE"}:
            return "PE"
        return text

    @staticmethod
    def _normalize_regime(regime: Any) -> str:
        raw = str(getattr(regime, "value", regime) or "").strip().lower()
        if raw in {"crisis", "crash_hedge"}:
            return "crisis"
        if raw in {"high_vol", "high_vol_sell"}:
            return "high_vol_sell"
        if raw in {"low_vol", "low_vol_sell"}:
            return "low_vol_sell"
        if raw in {"rising_vol_buy", "transition", "neutral", "falling_vol_buy"}:
            return "rising_vol_buy"
        return raw or "rising_vol_buy"

    @staticmethod
    def _normalize_strategy_name(value: str) -> str:
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    def _strategy_order_for_regime(self, regime_key: str) -> List[str]:
        if regime_key in {"low_vol_sell", "high_vol_sell"}:
            return [
                "iron_condor",
                "iron_butterfly",
                "short_strangle",
                "calendar_spread",
                "bull_call_spread",
                "bear_put_spread",
                "long_strangle",
                "long_straddle",
            ]
        if regime_key == "crisis":
            return [
                "long_strangle",
                "bear_put_spread",
                "long_straddle",
                "calendar_spread",
                "iron_condor",
                "iron_butterfly",
                "short_strangle",
                "bull_call_spread",
            ]
        return [
            "calendar_spread",
            "long_strangle",
            "long_straddle",
            "bull_call_spread",
            "bear_put_spread",
            "iron_condor",
            "iron_butterfly",
            "short_strangle",
        ]

    def _prepare_chain(self, option_chain: pd.DataFrame) -> pd.DataFrame:
        if option_chain is None or option_chain.empty:
            return pd.DataFrame()

        chain = option_chain.copy()
        required = {"strike", "option_type", "expiry"}
        if not required.issubset(set(chain.columns)):
            return pd.DataFrame()

        chain["strike"] = pd.to_numeric(chain["strike"], errors="coerce")
        chain["expiry"] = pd.to_datetime(chain["expiry"], errors="coerce")
        chain["option_type"] = chain["option_type"].map(self._normalize_option_type)

        # Premium fallback hierarchy: premium -> ltp -> mid(bid,ask).
        if "premium" not in chain.columns:
            chain["premium"] = pd.NA
        chain["premium"] = pd.to_numeric(chain["premium"], errors="coerce")
        if "ltp" in chain.columns:
            ltp = pd.to_numeric(chain["ltp"], errors="coerce")
            chain["premium"] = chain["premium"].where(chain["premium"] > 0, ltp)
        if {"bid", "ask"}.issubset(chain.columns):
            bid = pd.to_numeric(chain["bid"], errors="coerce")
            ask = pd.to_numeric(chain["ask"], errors="coerce")
            mid = (bid + ask) / 2.0
            chain["premium"] = chain["premium"].where(chain["premium"] > 0, mid)

        for col in ("delta", "gamma", "theta", "vega"):
            if col not in chain.columns:
                chain[col] = 0.0
            chain[col] = pd.to_numeric(chain[col], errors="coerce").fillna(0.0)

        if "instrument_key" not in chain.columns:
            chain["instrument_key"] = ""

        chain = chain.dropna(subset=["strike", "expiry"]).copy()
        today = datetime.now().date()
        chain = chain[chain["expiry"].dt.date >= today].copy()
        chain = chain[chain["option_type"].isin(["CE", "PE"])].copy()
        chain = chain[chain["premium"].notna() & (chain["premium"] > 0)].copy()
        return chain.sort_values(["expiry", "strike"])

    def _resolve_spot(self, chain: pd.DataFrame, fallback_spot: float) -> float:
        try:
            if "underlying_price" in chain.columns:
                vals = pd.to_numeric(chain["underlying_price"], errors="coerce").dropna()
                if not vals.empty:
                    return float(vals.median())
        except Exception:
            pass
        if fallback_spot and fallback_spot > 0:
            return float(fallback_spot)
        return float(chain["strike"].median())

    def _select_expiry(
        self,
        chain: pd.DataFrame,
        min_days: int,
        max_days: int,
        target_days: int,
        allow_any_future_fallback: bool = True,
    ) -> Optional[date]:
        today = datetime.now().date()
        expiries = sorted(pd.to_datetime(chain["expiry"], errors="coerce").dropna().dt.date.unique().tolist())
        if not expiries:
            return None

        candidates: List[tuple[date, int]] = []
        for exp in expiries:
            dte = (exp - today).days
            if min_days <= dte <= max_days:
                candidates.append((exp, dte))

        if not candidates:
            if not allow_any_future_fallback:
                return None
            # fallback to nearest future expiry if window is empty
            futures = [exp for exp in expiries if (exp - today).days >= 1]
            if not futures:
                return None
            return min(futures, key=lambda exp: abs((exp - today).days - target_days))

        return min(candidates, key=lambda item: abs(item[1] - target_days))[0]

    def _slice(self, chain: pd.DataFrame, expiry: date, option_type: str) -> pd.DataFrame:
        target = self._normalize_option_type(option_type)
        exp_mask = pd.to_datetime(chain["expiry"], errors="coerce").dt.date == expiry
        out = chain[exp_mask & (chain["option_type"] == target)].copy()
        return out.sort_values("strike")

    def _pick(
        self,
        chain: pd.DataFrame,
        expiry: date,
        option_type: str,
        target_strike: float,
        direction: str = "any",
    ) -> Optional[pd.Series]:
        sliced = self._slice(chain, expiry, option_type)
        if sliced.empty:
            return None

        if direction == "above":
            sliced = sliced[sliced["strike"] >= float(target_strike)]
        elif direction == "below":
            sliced = sliced[sliced["strike"] <= float(target_strike)]
        if sliced.empty:
            sliced = self._slice(chain, expiry, option_type)
            if sliced.empty:
                return None

        sliced = sliced.copy()
        sliced["distance"] = (sliced["strike"] - float(target_strike)).abs()
        # prefer tighter spreads/liquid rows when available
        sort_cols = ["distance"]
        ascending = [True]
        if "oi" in sliced.columns:
            sliced["oi"] = pd.to_numeric(sliced["oi"], errors="coerce").fillna(0.0)
            sort_cols.append("oi")
            ascending.append(False)
        if "volume" in sliced.columns:
            sliced["volume"] = pd.to_numeric(sliced["volume"], errors="coerce").fillna(0.0)
            sort_cols.append("volume")
            ascending.append(False)
        sliced = sliced.sort_values(sort_cols, ascending=ascending)
        return sliced.iloc[0]

    @staticmethod
    def _estimate_greeks_from_context(row: pd.Series) -> Greeks:
        """Deterministic fallback Greeks when feed Greeks are missing/zero."""
        def _num(value: Any, default: float = 0.0) -> float:
            try:
                parsed = float(value)
                return default if pd.isna(parsed) else parsed
            except Exception:
                return default

        strike = max(_num(row.get("strike"), 0.0), 1e-6)
        spot = _num(row.get("underlying_price"), strike)
        if spot <= 0:
            spot = strike
        option_type = str(row.get("option_type", "") or "").strip().upper()

        expiry = pd.to_datetime(row.get("expiry"), errors="coerce")
        if pd.isna(expiry):
            dte = 14
        else:
            dte = max(1, int((expiry.date() - datetime.now().date()).days))

        distance = (strike - spot) / max(spot, 1e-6)
        dist_unit = max(0.01, min(0.20, 0.03 + 0.0015 * dte))
        scaled_dist = distance / dist_unit

        call_delta = 0.5 - max(-0.48, min(0.48, scaled_dist))
        call_delta = max(0.02, min(0.98, call_delta))
        if option_type in {"PE", "PUT", "P"}:
            delta = max(-0.98, min(-0.02, call_delta - 1.0))
        else:
            delta = call_delta

        gamma = max(0.0005, 0.010 / (1.0 + abs(distance) * 20.0 + dte / 18.0))
        theta = -max(0.05, 0.90 / (dte + 3.0)) * (1.0 + 0.35 / (1.0 + abs(distance) * 15.0))
        vega = max(0.05, 1.40 / (1.0 + abs(distance) * 12.0 + dte / 45.0))
        return Greeks(delta=float(delta), gamma=float(gamma), theta=float(theta), vega=float(vega))

    @classmethod
    def _greeks_from_row(cls, row: pd.Series) -> Greeks:
        def _num(value: Any) -> float:
            try:
                parsed = float(value)
                return 0.0 if pd.isna(parsed) else parsed
            except Exception:
                return 0.0

        delta = _num(row.get("delta", 0.0))
        gamma = _num(row.get("gamma", 0.0))
        theta = _num(row.get("theta", 0.0))
        vega = _num(row.get("vega", 0.0))

        estimated = cls._estimate_greeks_from_context(row)
        if abs(delta) + abs(gamma) + abs(theta) + abs(vega) < 1e-9:
            return estimated

        if abs(delta) < 1e-12:
            delta = estimated.delta
        if abs(gamma) < 1e-12:
            gamma = estimated.gamma
        if abs(theta) < 1e-12:
            theta = estimated.theta
        if abs(vega) < 1e-12:
            vega = estimated.vega

        return Greeks(delta=float(delta), gamma=float(gamma), theta=float(theta), vega=float(vega))

    def _leg(self, row: pd.Series, expiry: date, action: str, quantity: int = 1) -> OptionLeg:
        premium = float(row.get("premium", row.get("ltp", 0.0)) or 0.0)
        if premium <= 0:
            bid = float(row.get("bid", 0.0) or 0.0)
            ask = float(row.get("ask", 0.0) or 0.0)
            premium = (bid + ask) / 2.0 if bid > 0 and ask > 0 else max(bid, ask, 0.0)

        return OptionLeg(
            strike=float(row["strike"]),
            option_type=self._normalize_option_type(row.get("option_type")),
            expiry=datetime.combine(expiry, datetime.min.time()),
            action=str(action).upper(),
            quantity=int(max(1, quantity)),
            premium=float(max(0.0, premium)),
            greeks=self._greeks_from_row(row),
            instrument_key=str(row.get("instrument_key", "") or ""),
        )

    @staticmethod
    def _regime_enum(regime_key: str) -> VolatilityRegime:
        if regime_key == "low_vol_sell":
            return VolatilityRegime.LOW_VOL
        if regime_key == "high_vol_sell":
            return VolatilityRegime.HIGH_VOL
        if regime_key == "crisis":
            return VolatilityRegime.CRISIS
        return VolatilityRegime.TRANSITION

    def _strategy(
        self,
        strategy_type: StrategyType,
        underlying: str,
        spot: float,
        legs: List[OptionLeg],
        regime_key: str,
        expiry: date,
        max_loss: float,
        max_profit: float,
    ) -> OptionStrategy:
        greeks = Greeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0)
        for leg in legs:
            greeks = greeks + leg.total_greeks

        net = float(sum(leg.total_premium for leg in legs))
        dte = max(1, (expiry - datetime.now().date()).days)

        return OptionStrategy(
            strategy_type=strategy_type,
            legs=legs,
            underlying=underlying,
            underlying_price=float(spot),
            regime=self._regime_enum(regime_key),
            max_loss=float(max(0.0, max_loss)),
            max_profit=float(max(0.0, max_profit)),
            net_credit_debit=float(net),
            portfolio_greeks=greeks,
            created_at=datetime.now(),
            expiry_date=datetime.combine(expiry, datetime.min.time()),
            days_to_expiry=int(dte),
            is_valid=True,
            validation_errors=[],
        )

    def _pick_atm_pair(self, chain: pd.DataFrame, expiry: date, spot: float) -> Optional[tuple[pd.Series, pd.Series, float]]:
        calls = self._slice(chain, expiry, "CE")
        puts = self._slice(chain, expiry, "PE")
        if calls.empty or puts.empty:
            return None
        common = sorted(set(calls["strike"]).intersection(set(puts["strike"])))
        if not common:
            return None
        atm = min(common, key=lambda k: abs(float(k) - float(spot)))
        call = calls[calls["strike"] == atm].iloc[0]
        put = puts[puts["strike"] == atm].iloc[0]
        return call, put, float(atm)

    def _build_long_straddle(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        pair = self._pick_atm_pair(chain, expiry, spot)
        if pair is None:
            return None
        call, put, _ = pair
        legs = [self._leg(call, expiry, "BUY"), self._leg(put, expiry, "BUY")]
        debit = abs(sum(leg.total_premium for leg in legs))
        return self._strategy(
            StrategyType.LONG_STRADDLE,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=debit,
            max_profit=debit * 2.5,
        )

    def _build_long_strangle(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        call = self._pick(chain, expiry, "CE", spot * 1.025, direction="above")
        put = self._pick(chain, expiry, "PE", spot * 0.975, direction="below")
        if call is None or put is None:
            return None
        legs = [self._leg(call, expiry, "BUY"), self._leg(put, expiry, "BUY")]
        debit = abs(sum(leg.total_premium for leg in legs))
        return self._strategy(
            StrategyType.LONG_STRANGLE,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=debit,
            max_profit=debit * 2.2,
        )

    def _build_short_strangle(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        call = self._pick(chain, expiry, "CE", spot * 1.03, direction="above")
        put = self._pick(chain, expiry, "PE", spot * 0.97, direction="below")
        if call is None or put is None:
            return None
        legs = [self._leg(call, expiry, "SELL"), self._leg(put, expiry, "SELL")]
        credit = abs(sum(leg.total_premium for leg in legs))
        width = max(abs(float(call["strike"]) - spot), abs(spot - float(put["strike"])), 1.0)
        margin_proxy = max(credit * 6.0, width * 0.35)
        return self._strategy(
            StrategyType.SHORT_STRANGLE,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=margin_proxy,
            max_profit=credit,
        )

    def _build_iron_condor(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        put_short = self._pick(chain, expiry, "PE", spot * 0.98, direction="below")
        put_long = self._pick(chain, expiry, "PE", spot * 0.95, direction="below")
        call_short = self._pick(chain, expiry, "CE", spot * 1.02, direction="above")
        call_long = self._pick(chain, expiry, "CE", spot * 1.05, direction="above")
        if any(x is None for x in (put_short, put_long, call_short, call_long)):
            return None

        put_short, put_long, call_short, call_long = put_short, put_long, call_short, call_long
        if not (float(put_long["strike"]) < float(put_short["strike"]) < spot < float(call_short["strike"]) < float(call_long["strike"])):
            return None

        legs = [
            self._leg(put_long, expiry, "BUY"),
            self._leg(put_short, expiry, "SELL"),
            self._leg(call_short, expiry, "SELL"),
            self._leg(call_long, expiry, "BUY"),
        ]
        credit = abs(sum(leg.total_premium for leg in legs))
        call_width = max(1.0, float(call_long["strike"]) - float(call_short["strike"]))
        put_width = max(1.0, float(put_short["strike"]) - float(put_long["strike"]))
        max_loss = max(call_width, put_width) - credit
        max_loss = max(max_loss, max(call_width, put_width) * 0.15)
        return self._strategy(
            StrategyType.IRON_CONDOR,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=max_loss,
            max_profit=credit,
        )

    def _build_iron_butterfly(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        pair = self._pick_atm_pair(chain, expiry, spot)
        if pair is None:
            return None
        atm_call, atm_put, atm = pair

        wing = max(1.0, spot * 0.03)
        put_wing = self._pick(chain, expiry, "PE", atm - wing, direction="below")
        call_wing = self._pick(chain, expiry, "CE", atm + wing, direction="above")
        if put_wing is None or call_wing is None:
            return None

        legs = [
            self._leg(put_wing, expiry, "BUY"),
            self._leg(atm_put, expiry, "SELL"),
            self._leg(atm_call, expiry, "SELL"),
            self._leg(call_wing, expiry, "BUY"),
        ]
        credit = abs(sum(leg.total_premium for leg in legs))
        wing_width = max(float(atm) - float(put_wing["strike"]), float(call_wing["strike"]) - float(atm), 1.0)
        max_loss = max(wing_width - credit, wing_width * 0.12)
        return self._strategy(
            StrategyType.IRON_BUTTERFLY,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=max_loss,
            max_profit=credit,
        )

    def _build_bull_call_spread(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        long_call = self._pick(chain, expiry, "CE", spot, direction="above")
        short_call = self._pick(chain, expiry, "CE", spot * 1.03, direction="above")
        if long_call is None or short_call is None:
            return None
        if float(short_call["strike"]) <= float(long_call["strike"]):
            return None

        legs = [self._leg(long_call, expiry, "BUY"), self._leg(short_call, expiry, "SELL")]
        net = sum(leg.total_premium for leg in legs)
        width = float(short_call["strike"]) - float(long_call["strike"])
        max_loss = abs(net)
        max_profit = max(0.0, width - max_loss)
        return self._strategy(
            StrategyType.BULL_CALL_SPREAD,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=max_loss,
            max_profit=max_profit,
        )

    def _build_bear_put_spread(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        expiry: date,
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        long_put = self._pick(chain, expiry, "PE", spot, direction="below")
        short_put = self._pick(chain, expiry, "PE", spot * 0.97, direction="below")
        if long_put is None or short_put is None:
            return None
        if float(short_put["strike"]) >= float(long_put["strike"]):
            return None

        legs = [self._leg(long_put, expiry, "BUY"), self._leg(short_put, expiry, "SELL")]
        net = sum(leg.total_premium for leg in legs)
        width = float(long_put["strike"]) - float(short_put["strike"])
        max_loss = abs(net)
        max_profit = max(0.0, width - max_loss)
        return self._strategy(
            StrategyType.BEAR_PUT_SPREAD,
            underlying,
            spot,
            legs,
            regime_key,
            expiry,
            max_loss=max_loss,
            max_profit=max_profit,
        )

    def _build_calendar_spread(
        self,
        chain: pd.DataFrame,
        underlying: str,
        spot: float,
        near_expiry: date,
        far_expiry: Optional[date],
        regime_key: str,
    ) -> Optional[OptionStrategy]:
        if far_expiry is None or far_expiry <= near_expiry:
            return None

        near_pair = self._pick_atm_pair(chain, near_expiry, spot)
        far_pair = self._pick_atm_pair(chain, far_expiry, spot)
        if near_pair is None or far_pair is None:
            return None

        _, _, near_atm = near_pair
        far_call = self._pick(chain, far_expiry, "CE", near_atm, direction="any")
        near_call = self._pick(chain, near_expiry, "CE", near_atm, direction="any")
        if near_call is None or far_call is None:
            return None

        legs = [
            self._leg(near_call, near_expiry, "SELL"),
            self._leg(far_call, far_expiry, "BUY"),
        ]
        net = sum(leg.total_premium for leg in legs)
        max_loss = abs(net)
        max_profit = max_loss * 2.0
        return self._strategy(
            StrategyType.CALENDAR_SPREAD,
            underlying,
            spot,
            legs,
            regime_key,
            near_expiry,
            max_loss=max_loss,
            max_profit=max_profit,
        )
