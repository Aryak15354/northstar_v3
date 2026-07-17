"""
IndianEquityCostModel — full transaction-cost model for the cash/delivery
(CNC) equity segment on NSE, driven by config/pnl_config.yaml.

Every rupee that leaves the fund on a trade is itemised here so the paper
fund's P&L is honest about frictions:

    brokerage + STT + exchange txn + SEBI turnover + stamp duty + GST + slippage

Rules of the Indian cash segment encoded below:
  - STT: 0.1% on BOTH buy and sell (delivery).
  - Stamp duty: 0.015%, BUY side only.
  - GST: 18% on (brokerage + exchange txn + SEBI) only — never on STT/stamp.
  - Slippage: a fixed bps floor plus square-root market impact scaled by the
    order's size relative to the name's ADV (bigger orders cost more).

Slippage is an execution price effect (not a statutory charge); it is reported
separately from `statutory_total` so attribution stays clean, and folded into
`total` for the cash impact the ledger needs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = PROJECT_ROOT / "config" / "pnl_config.yaml"


@dataclass(frozen=True)
class TradeCostBreakdown:
    """Itemised cost for a single equity fill."""
    side: str                 # "BUY" or "SELL"
    notional: float           # abs(quantity * price)
    brokerage: float
    stt: float
    exchange_txn: float
    sebi: float
    stamp_duty: float
    gst: float
    slippage: float           # execution impact (bps floor + sqrt impact)
    statutory_total: float    # everything except slippage
    total: float              # statutory_total + slippage

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class IndianEquityCostModel:
    """Config-driven cost calculator. One instance is cheap; reuse across fills."""

    def __init__(self, config: Optional[dict] = None):
        cfg = config if config is not None else self._load_config()
        costs = (cfg or {}).get("costs", {})
        self.brokerage_pct = float(costs.get("brokerage_pct", 0.0003))
        self.brokerage_max_inr = float(costs.get("brokerage_max_inr", 20.0))
        self.stt_pct = float(costs.get("stt_pct", 0.001))
        self.exchange_txn_pct = float(costs.get("exchange_txn_pct", 0.0000297))
        self.sebi_turnover_pct = float(costs.get("sebi_turnover_pct", 0.000001))
        self.stamp_duty_pct = float(costs.get("stamp_duty_pct", 0.00015))
        self.gst_pct = float(costs.get("gst_pct", 0.18))
        self.slippage_bps = float(costs.get("slippage_bps", 5.0))
        self.impact_coefficient_bps = float(costs.get("impact_coefficient_bps", 40.0))

    @staticmethod
    def _load_config() -> dict:
        if yaml is None or not _CONFIG_PATH.exists():
            return {}
        try:
            with open(_CONFIG_PATH) as fh:
                return yaml.safe_load(fh) or {}
        except Exception:  # pragma: no cover
            return {}

    def slippage_bps_for(self, notional: float, adv_inr: Optional[float]) -> float:
        """Effective slippage in bps: fixed floor + sqrt market impact.

        impact_bps = impact_coefficient * sqrt(order_value / adv_value).
        With no/zero ADV we fall back to the floor only (impact undefined)."""
        floor = self.slippage_bps
        if adv_inr and adv_inr > 0 and notional > 0:
            impact = self.impact_coefficient_bps * math.sqrt(notional / adv_inr)
            return floor + impact
        return floor

    def cost_breakdown(
        self,
        side: str,
        notional: float,
        *,
        adv_inr: Optional[float] = None,
    ) -> TradeCostBreakdown:
        """Return the full itemised cost for one fill.

        `notional` is abs(quantity * fill_price). `side` is BUY or SELL.
        """
        side_u = str(side).upper()
        notional = abs(float(notional))
        if notional <= 0:
            return TradeCostBreakdown(side_u, 0.0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0)

        brokerage = min(notional * self.brokerage_pct, self.brokerage_max_inr)
        stt = notional * self.stt_pct                      # both sides (delivery)
        exchange_txn = notional * self.exchange_txn_pct
        sebi = notional * self.sebi_turnover_pct
        stamp_duty = notional * self.stamp_duty_pct if side_u == "BUY" else 0.0
        gst = self.gst_pct * (brokerage + exchange_txn + sebi)

        slippage_bps = self.slippage_bps_for(notional, adv_inr)
        slippage = notional * slippage_bps / 10_000.0

        statutory_total = brokerage + stt + exchange_txn + sebi + stamp_duty + gst
        total = statutory_total + slippage
        return TradeCostBreakdown(
            side=side_u, notional=notional, brokerage=brokerage, stt=stt,
            exchange_txn=exchange_txn, sebi=sebi, stamp_duty=stamp_duty, gst=gst,
            slippage=slippage, statutory_total=statutory_total, total=total,
        )

    def round_trip_cost_bps(self, notional: float, adv_inr: Optional[float] = None) -> float:
        """Convenience: total buy+sell frictions expressed in bps of notional."""
        buy = self.cost_breakdown("BUY", notional, adv_inr=adv_inr).total
        sell = self.cost_breakdown("SELL", notional, adv_inr=adv_inr).total
        return (buy + sell) / notional * 10_000.0 if notional > 0 else 0.0
