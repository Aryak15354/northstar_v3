from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from src.options.strategy_library.strategy_definitions import OPTION_STRATEGIES


class StrategyExecutor:
    def build(
        self,
        strategy_name: str,
        underlying: str,
        spot_price: float,
        sizing_lots: int = 1,
        strike_interval: float | None = None,
        as_of_datetime: datetime | None = None,
    ) -> dict[str, Any]:
        strategy = OPTION_STRATEGIES[strategy_name]
        as_of_datetime = as_of_datetime or datetime.utcnow()
        strike_interval = float(strike_interval or self._default_interval(underlying, spot_price))
        expiry = self._expiry_date(as_of_datetime, strategy["legs"][0]["expiry_preference"])

        legs: list[dict[str, Any]] = []
        for leg in strategy.get("legs", []):
            ratio = leg.get("quantity_ratio", 1.0)
            quantity = sizing_lots if not isinstance(ratio, (int, float)) else max(1, int(round(sizing_lots * float(ratio))))
            if leg["type"] == "futures":
                strike = round(float(spot_price), 2)
            else:
                raw_strike = float(spot_price) * (1.0 + float(leg.get("strike_offset_pct", 0.0)) / 100.0)
                strike = round(raw_strike / strike_interval) * strike_interval
            legs.append(
                {
                    "action": str(leg["action"]).upper(),
                    "instrument_type": str(leg["type"]).upper(),
                    "strike": float(strike),
                    "expiry": expiry.date().isoformat(),
                    "quantity": int(quantity),
                    "underlying": underlying,
                }
            )

        return {
            "strategy": strategy_name,
            "underlying": underlying,
            "spot_price": float(spot_price),
            "sizing_lots": int(sizing_lots),
            "expiry": expiry.date().isoformat(),
            "legs": legs,
            "notes": strategy.get("notes", ""),
        }

    @staticmethod
    def _default_interval(underlying: str, spot_price: float) -> float:
        symbol = str(underlying or "").upper()
        if symbol == "BANKNIFTY":
            return 100.0
        if symbol in {"NIFTY", "NIFTYIT", "NIFTYMETAL", "NIFTYFMCG", "NIFTYPHARMA", "NIFTYAUTO", "NIFTYREALTY", "NIFTYENERGY"}:
            return 50.0
        if float(spot_price) >= 1000:
            return 20.0
        if float(spot_price) >= 250:
            return 10.0
        return 5.0

    @staticmethod
    def _expiry_date(as_of_datetime: datetime, preference: str) -> datetime:
        pref = str(preference or "nearest_monthly").lower()
        if pref == "nearest_weekly":
            return as_of_datetime + timedelta(days=7)
        if pref == "three_month":
            return as_of_datetime + timedelta(days=90)
        if pref == "next_monthly":
            return as_of_datetime + timedelta(days=45)
        if pref == "near_month":
            return as_of_datetime + timedelta(days=30)
        return as_of_datetime + timedelta(days=30)
