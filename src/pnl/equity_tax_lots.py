"""
EquityTaxLotTracker — FIFO tax-lot accounting for the paper equity book.

Indian capital-gains reality (post-2024 cash equity):
  - Short-term (< 1 year holding): STCG at 20%.
  - Long-term (>= 1 year holding): LTCG at 12.5%, with a ₹1.25 lakh annual
    exemption applied across the financial year before tax is charged.

On every BUY we push a lot (qty, cost/share, date). On every SELL we consume
lots FIFO, classify each consumed slice as short- or long-term by holding
period, and accrue the tax liability. The tracker is deterministic and
config-driven so the paper fund's realized P&L is net of the tax a real fund
would actually owe.

Design mirrors src/options/tax_aware_pnl_tracker.py but for delivery equity
with holding-period-dependent rates and the LTCG annual exemption.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = PROJECT_ROOT / "config" / "pnl_config.yaml"


@dataclass
class _Lot:
    quantity: float
    cost_per_share: float          # includes buy-side costs amortised per share
    acquired: datetime


@dataclass
class RealizedGain:
    """Result of consuming lots against one SELL."""
    ticker: str
    quantity: float
    proceeds: float                # net of sell-side costs
    cost_basis: float
    gross_gain: float              # proceeds - cost_basis (pre-tax)
    short_term_gain: float
    long_term_gain: float
    tax: float                     # tax accrued on this sell
    net_gain: float                # gross_gain - tax


class EquityTaxLotTracker:
    """FIFO lots per ticker with holding-period-aware LTCG/STCG accrual."""

    def __init__(self, config: Optional[dict] = None):
        cfg = config if config is not None else self._load_config()
        tax = (cfg or {}).get("tax", {})
        self.stcg_pct = float(tax.get("stcg_pct", 0.20))
        self.ltcg_pct = float(tax.get("ltcg_pct", 0.125))
        self.ltcg_exemption = float(tax.get("ltcg_annual_exemption_inr", 125000))
        self.long_term_days = int(tax.get("long_term_holding_days", 365))

        self._lots: dict[str, deque[_Lot]] = defaultdict(deque)
        # LTCG exemption is annual — track consumed exemption per financial year.
        self._ltcg_exemption_used: dict[int, float] = defaultdict(float)

    @staticmethod
    def _load_config() -> dict:
        if yaml is None or not _CONFIG_PATH.exists():
            return {}
        try:
            with open(_CONFIG_PATH) as fh:
                return yaml.safe_load(fh) or {}
        except Exception:  # pragma: no cover
            return {}

    @staticmethod
    def _fy(dt: datetime) -> int:
        """Indian financial year starting label (Apr–Mar). Apr 2025 → FY2025."""
        return dt.year if dt.month >= 4 else dt.year - 1

    def buy(self, ticker: str, quantity: float, cost_per_share: float, date: datetime) -> None:
        if quantity <= 0:
            return
        self._lots[ticker].append(_Lot(quantity, cost_per_share, date))

    def sell(
        self,
        ticker: str,
        quantity: float,
        proceeds_per_share: float,
        date: datetime,
    ) -> RealizedGain:
        """Consume FIFO lots for `quantity`; return realized + tax breakdown.

        `proceeds_per_share` should already be net of sell-side costs (the
        engine passes net proceeds / qty), so gross_gain is a true economic gain.
        """
        remaining = quantity
        cost_basis = 0.0
        st_gain = 0.0
        lt_gain = 0.0
        lots = self._lots[ticker]

        while remaining > 1e-9 and lots:
            lot = lots[0]
            take = min(remaining, lot.quantity)
            slice_cost = take * lot.cost_per_share
            slice_proceeds = take * proceeds_per_share
            slice_gain = slice_proceeds - slice_cost
            holding_days = (date - lot.acquired).days
            if holding_days >= self.long_term_days:
                lt_gain += slice_gain
            else:
                st_gain += slice_gain
            cost_basis += slice_cost
            remaining -= take
            lot.quantity -= take
            if lot.quantity <= 1e-9:
                lots.popleft()

        # If we somehow sell more than we hold (shouldn't happen in the engine),
        # treat the uncovered slice as zero-cost short-term (conservative).
        if remaining > 1e-9:
            st_gain += remaining * proceeds_per_share
            remaining = 0.0

        proceeds = quantity * proceeds_per_share
        gross_gain = proceeds - cost_basis

        # Tax: STCG on positive short-term gains; LTCG on positive long-term
        # gains after applying the remaining annual exemption.
        tax = 0.0
        if st_gain > 0:
            tax += st_gain * self.stcg_pct
        if lt_gain > 0:
            fy = self._fy(date)
            remaining_exemption = max(0.0, self.ltcg_exemption - self._ltcg_exemption_used[fy])
            taxable_lt = max(0.0, lt_gain - remaining_exemption)
            self._ltcg_exemption_used[fy] += min(lt_gain, remaining_exemption)
            tax += taxable_lt * self.ltcg_pct

        return RealizedGain(
            ticker=ticker, quantity=quantity, proceeds=proceeds, cost_basis=cost_basis,
            gross_gain=gross_gain, short_term_gain=st_gain, long_term_gain=lt_gain,
            tax=tax, net_gain=gross_gain - tax,
        )

    def holdings(self) -> dict[str, float]:
        """Current open quantity per ticker (FIFO lots summed)."""
        return {t: sum(l.quantity for l in lots) for t, lots in self._lots.items() if lots}

    def average_cost(self, ticker: str) -> Optional[float]:
        lots = self._lots.get(ticker)
        if not lots:
            return None
        qty = sum(l.quantity for l in lots)
        if qty <= 0:
            return None
        return sum(l.quantity * l.cost_per_share for l in lots) / qty
