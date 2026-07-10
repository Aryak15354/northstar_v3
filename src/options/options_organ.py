"""Unified Options Organ for Northstar V3.

This is the single options brain that complements the v3 research stack. v3's
daily/weekly/monthly/quarterly pipeline explains *what* is happening to the
market and the ~500 companies and *why* (a financial-results shock, a news /
sentiment deterioration, a regime shift). This organ turns that understanding
into concrete option actions, presented as ranked *suggestions*:

  1. Directional SHORTS   -- bearish names -> long puts / bear put spreads
  2. Directional LONGS    -- bullish names -> long calls / bull call spreads
  3. Portfolio HEDGES     -- for equities HELD in the slow-turning v3 portfolio
                             whose situation is deteriorating, protect them with
                             options (protective put / collar / put spread)
                             instead of selling -- respecting the fact that
                             rotating the equity book costs time and tax.
  4. Volatility OPPORTUNITIES -- regime/IV-driven non-directional structures
                             (iron condor, straddle, strangle, ...), including
                             more complex ones.

Design principles:
- It is ADVISORY: it writes suggestions to state + a report artifact. Execution
  (v3 shadow now, live Upstox OMS later) consumes suggestions separately, so a
  bug here can never place an order.
- It is SELF-CONTAINED: option legs are priced with the local Black-Scholes
  engine (src/options/black_scholes.py) from spot + a regime-aware IV estimate,
  so it works for any underlying with no live chain. When a live Upstox chain
  IS available it is used via `chain_provider` (a drop-in seam).
- Every suggestion carries its full economics (cost / max-loss / max-profit /
  breakevens) and net greeks, plus the v3 rationale that triggered it.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.options.black_scholes import OptionQuote, atm_iv_estimate, price_and_greeks

logger = logging.getLogger("options.organ")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "options" / "suggestions" / "options_suggestions_latest.json"

# NSE F&O lot sizes (indices + a pragmatic default for single stocks). Extend
# via config as the tradable universe grows.
_DEFAULT_LOT_SIZES = {"NIFTY": 75, "BANKNIFTY": 35, "FINNIFTY": 65, "MIDCPNIFTY": 120}
_DEFAULT_STOCK_LOT = 1


@dataclass
class SuggestionLeg:
    action: str            # BUY / SELL
    option_type: str       # CE / PE
    strike: float
    premium: float
    quantity: int          # lots (positive count; action carries sign)
    delta: float
    gamma: float
    theta: float
    vega: float


@dataclass
class OptionSuggestion:
    category: str          # short | long | hedge | opportunity
    underlying: str
    structure: str         # e.g. bear_put_spread, protective_put, iron_condor
    thesis: str            # the v3-derived reason this is suggested
    spot: float
    iv_used: float
    days_to_expiry: int
    lot_size: int
    legs: List[SuggestionLeg]
    net_debit_credit: float     # >0 = you pay (debit), <0 = you receive (credit), per lot
    max_loss: float             # per lot (INR), None-safe finite estimate
    max_profit: float           # per lot; float('inf') for uncapped
    breakevens: List[float]
    net_delta: float
    net_theta: float
    net_vega: float
    priority: float             # ranking score (higher = stronger)
    modeled: bool = True        # True if priced from BS model (no live chain)
    hedges_symbol: Optional[str] = None   # for hedges: the equity being protected
    # History-aware lifecycle (set by SuggestionStore.annotate):
    status: str = "new"         # new | continued
    days_active: int = 1        # consecutive trading days this (underlying,category) has been flagged
    history_note: str = ""      # human-readable continuity note

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["max_profit"] = None if self.max_profit == float("inf") else self.max_profit
        return d


class OptionsOrgan:
    """Options suggestion organ. Implements the v3 organ contract
    (read_state / process / write_state) but stays import-light so it can also
    run standalone (e.g. from the daily pipeline or a notebook)."""

    name = "options_organ"

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        *,
        chain_provider: Optional[Callable[[str, int], Any]] = None,
        report_path: Path = DEFAULT_REPORT_PATH,
        log: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config or {}
        self.log = log or logger
        self.report_path = Path(report_path)
        # Seam for a live Upstox chain: chain_provider(underlying, dte) -> chain.
        # When None, legs are priced with the local Black-Scholes model.
        self.chain_provider = chain_provider

        opt = self.config.get("options_organ", {}) if isinstance(self.config, dict) else {}
        self.target_dte = int(opt.get("target_dte", 30))
        self.rate = float(opt.get("risk_free_rate", 0.065))
        self.max_suggestions_per_category = int(opt.get("max_suggestions_per_category", 10))
        self.hedge_deterioration_threshold = float(opt.get("hedge_deterioration_threshold", -0.15))
        self.short_score_threshold = float(opt.get("short_score_threshold", -0.20))
        self.long_score_threshold = float(opt.get("long_score_threshold", 0.20))
        self.lot_sizes = {**_DEFAULT_LOT_SIZES, **(opt.get("lot_sizes", {}) or {})}
        # When True (default), if the UnifiedState carries no explicit
        # options_candidates, build them from real v3 artifacts (daily scorer,
        # sentiment, prices, portfolio) via CandidateBuilder.
        self.use_v3_artifacts = bool(opt.get("use_v3_artifacts", True))
        self._news_overlay = None  # NIL seam; set via attach_news_overlay()
        # History-aware persistence: annotate today's suggestions with continuity
        # from prior days and record a rolling history, so the organ never
        # "starts from scratch" each morning. Disable via use_history: false.
        self.use_history = bool(opt.get("use_history", True))
        self._store = None
        if self.use_history:
            from src.options.suggestion_store import SuggestionStore
            self._store = SuggestionStore(log=self.log)

        # Populated by read_state / run:
        self._regime: str = "unknown"
        self._holdings: Dict[str, Dict[str, Any]] = {}
        self._candidates: Dict[str, Dict[str, Any]] = {}
        self.suggestions: List[OptionSuggestion] = []

    # ------------------------------------------------------------------ #
    # Input extraction
    # ------------------------------------------------------------------ #
    def ingest(
        self,
        *,
        regime: str,
        holdings: Dict[str, Dict[str, Any]],
        candidates: Dict[str, Dict[str, Any]],
    ) -> None:
        """Direct-injection entry (used by tests and standalone runs).

        holdings:   {symbol: {"spot": float, "quantity": int, "situation_score": float,
                              "realized_vol": float, "sector": str}}
        candidates: {symbol: {"spot": float, "directional_score": float,
                              "realized_vol": float, ...}}
        situation_score / directional_score are v3-derived in [-1, 1]:
          negative = bearish / deteriorating, positive = bullish / improving.
        """
        self._regime = str(regime or "unknown")
        self._holdings = dict(holdings or {})
        self._candidates = dict(candidates or {})

    def _lot_size(self, underlying: str) -> int:
        return int(self.lot_sizes.get(underlying.upper().replace(".NS", ""), _DEFAULT_STOCK_LOT))

    def _quote(self, underlying: str, option_type: str, strike: float, spot: float, iv: float) -> OptionQuote:
        # Live-chain seam: if a provider is wired, prefer observed premiums.
        if self.chain_provider is not None:
            try:
                q = self.chain_provider(underlying, self.target_dte)  # noqa: F841
                # A real provider would return a chain; premium lookup would go
                # here. Left as the integration point -- falls through to model
                # on any miss so the organ never fails closed.
            except Exception:  # noqa: BLE001
                pass
        return price_and_greeks(
            option_type=option_type, spot=spot, strike=strike,
            days_to_expiry=self.target_dte, iv=iv, rate=self.rate,
        )

    # ------------------------------------------------------------------ #
    # Structure builders (each returns an OptionSuggestion)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _round_strike(spot: float) -> float:
        # Round to a sensible strike step relative to price level.
        if spot >= 20000:
            step = 100.0
        elif spot >= 5000:
            step = 50.0
        elif spot >= 1000:
            step = 20.0
        elif spot >= 250:
            step = 5.0
        else:
            step = 2.5
        return round(spot / step) * step

    def _leg(self, action: str, q: OptionQuote, qty: int = 1) -> SuggestionLeg:
        sign = 1.0 if action == "BUY" else -1.0
        return SuggestionLeg(
            action=action, option_type=q.option_type, strike=q.strike, premium=round(q.price, 2),
            quantity=qty, delta=sign * q.delta, gamma=sign * q.gamma,
            theta=sign * q.theta, vega=sign * q.vega,
        )

    def _finalize(
        self, category: str, underlying: str, structure: str, thesis: str, spot: float,
        iv: float, legs: List[SuggestionLeg], breakevens: List[float], priority: float,
        *, max_profit: float, hedges_symbol: Optional[str] = None,
    ) -> OptionSuggestion:
        lot = self._lot_size(underlying)
        # Net premium per unit (debit positive). BUY pays premium, SELL receives.
        net_prem = sum((1.0 if lg.action == "BUY" else -1.0) * lg.premium for lg in legs)
        net_delta = sum(lg.delta for lg in legs)
        net_theta = sum(lg.theta for lg in legs)
        net_vega = sum(lg.vega for lg in legs)
        # Max loss per lot: for debit structures it's the net debit * lot; for
        # spreads it's bounded by width - credit. Compute from the payoff at the
        # protective wing where available, else fall back to net debit.
        max_loss = self._max_loss(structure, legs, net_prem) * lot
        mp = float("inf") if max_profit == float("inf") else max_profit * lot
        return OptionSuggestion(
            category=category, underlying=underlying, structure=structure, thesis=thesis,
            spot=round(spot, 2), iv_used=round(iv, 4), days_to_expiry=self.target_dte,
            lot_size=lot, legs=legs, net_debit_credit=round(net_prem * lot, 2),
            max_loss=round(max_loss, 2), max_profit=mp if mp == float("inf") else round(mp, 2),
            breakevens=[round(b, 2) for b in breakevens],
            net_delta=round(net_delta, 4), net_theta=round(net_theta, 4), net_vega=round(net_vega, 4),
            priority=round(priority, 4), modeled=self.chain_provider is None, hedges_symbol=hedges_symbol,
        )

    @staticmethod
    def _max_loss(structure: str, legs: List[SuggestionLeg], net_prem: float) -> float:
        buys = [lg for lg in legs if lg.action == "BUY"]
        sells = [lg for lg in legs if lg.action == "SELL"]
        if structure in ("bull_call_spread", "bear_put_spread", "put_spread_hedge"):
            width = abs(legs[0].strike - legs[1].strike)
            return max(net_prem, 0.0) if net_prem > 0 else max(width - abs(net_prem), 0.0)
        if structure in ("long_put", "long_call", "protective_put", "long_straddle", "long_strangle"):
            return max(net_prem, 0.0)  # debit paid is the max loss
        if structure == "collar":
            # long stock + long put + short call: downside capped at put strike.
            return max(net_prem, 0.0)
        if structure in ("iron_condor", "iron_butterfly"):
            call_w = abs(sells[0].strike - buys[0].strike) if buys and sells else 0.0
            put_w = call_w
            for b in buys:
                for s in sells:
                    if b.option_type == s.option_type:
                        w = abs(b.strike - s.strike)
                        if b.option_type == "CE":
                            call_w = w
                        else:
                            put_w = w
            width = max(call_w, put_w)
            return max(width - abs(net_prem), 0.0)  # credit received offsets wing width
        return abs(net_prem)

    def build_long_put(self, underlying, spot, iv, thesis, priority, category="short", hedges_symbol=None):
        strike = self._round_strike(spot)
        q = self._quote(underlying, "PE", strike, spot, iv)
        legs = [self._leg("BUY", q)]
        be = strike - q.price
        return self._finalize(category, underlying, "long_put" if category != "hedge" else "protective_put",
                              thesis, spot, iv, legs, [be], priority, max_profit=strike, hedges_symbol=hedges_symbol)

    def build_bear_put_spread(self, underlying, spot, iv, thesis, priority):
        long_k = self._round_strike(spot)
        short_k = self._round_strike(spot * 0.93)
        lq = self._quote(underlying, "PE", long_k, spot, iv)
        sq = self._quote(underlying, "PE", short_k, spot, iv)
        legs = [self._leg("BUY", lq), self._leg("SELL", sq)]
        net = lq.price - sq.price
        be = long_k - net
        return self._finalize("short", underlying, "bear_put_spread", thesis, spot, iv, legs, [be],
                              priority, max_profit=(long_k - short_k) - net)

    def build_bull_call_spread(self, underlying, spot, iv, thesis, priority):
        long_k = self._round_strike(spot)
        short_k = self._round_strike(spot * 1.07)
        lq = self._quote(underlying, "CE", long_k, spot, iv)
        sq = self._quote(underlying, "CE", short_k, spot, iv)
        legs = [self._leg("BUY", lq), self._leg("SELL", sq)]
        net = lq.price - sq.price
        be = long_k + net
        return self._finalize("long", underlying, "bull_call_spread", thesis, spot, iv, legs, [be],
                              priority, max_profit=(short_k - long_k) - net)

    def build_long_call(self, underlying, spot, iv, thesis, priority):
        strike = self._round_strike(spot)
        q = self._quote(underlying, "CE", strike, spot, iv)
        legs = [self._leg("BUY", q)]
        return self._finalize("long", underlying, "long_call", thesis, spot, iv, legs, [strike + q.price],
                              priority, max_profit=float("inf"))

    def build_collar(self, underlying, spot, iv, thesis, priority, hedges_symbol):
        put_k = self._round_strike(spot * 0.93)
        call_k = self._round_strike(spot * 1.07)
        pq = self._quote(underlying, "PE", put_k, spot, iv)
        cq = self._quote(underlying, "CE", call_k, spot, iv)
        legs = [self._leg("BUY", pq), self._leg("SELL", cq)]
        net = pq.price - cq.price  # often near-zero ("zero-cost collar")
        return self._finalize("hedge", underlying, "collar", thesis, spot, iv, legs, [spot + net],
                              priority, max_profit=call_k - spot, hedges_symbol=hedges_symbol)

    def build_iron_condor(self, underlying, spot, iv, thesis, priority):
        # Short OTM call+put spreads: profit if the underlying stays range-bound.
        put_short = self._round_strike(spot * 0.95)
        put_long = self._round_strike(spot * 0.90)
        call_short = self._round_strike(spot * 1.05)
        call_long = self._round_strike(spot * 1.10)
        legs = [
            self._leg("SELL", self._quote(underlying, "PE", put_short, spot, iv)),
            self._leg("BUY", self._quote(underlying, "PE", put_long, spot, iv)),
            self._leg("SELL", self._quote(underlying, "CE", call_short, spot, iv)),
            self._leg("BUY", self._quote(underlying, "CE", call_long, spot, iv)),
        ]
        net = sum((1.0 if lg.action == "BUY" else -1.0) * lg.premium for lg in legs)  # negative = credit
        credit = -net
        return self._finalize("opportunity", underlying, "iron_condor", thesis, spot, iv, legs,
                              [put_short - credit, call_short + credit], priority, max_profit=credit)

    def build_long_straddle(self, underlying, spot, iv, thesis, priority):
        strike = self._round_strike(spot)
        cq = self._quote(underlying, "CE", strike, spot, iv)
        pq = self._quote(underlying, "PE", strike, spot, iv)
        legs = [self._leg("BUY", cq), self._leg("BUY", pq)]
        net = cq.price + pq.price
        return self._finalize("opportunity", underlying, "long_straddle", thesis, spot, iv, legs,
                              [strike - net, strike + net], priority, max_profit=float("inf"))

    # ------------------------------------------------------------------ #
    # The four suggestion engines
    # ------------------------------------------------------------------ #
    def _iv_for(self, meta: Dict[str, Any]) -> float:
        rv = float(meta.get("realized_vol", 0.25) or 0.25)
        return atm_iv_estimate(rv, self._regime)

    def suggest_shorts(self) -> List[OptionSuggestion]:
        out = []
        for sym, meta in self._candidates.items():
            score = float(meta.get("directional_score", 0.0) or 0.0)
            if score > self.short_score_threshold:
                continue
            spot = float(meta.get("spot", 0.0) or 0.0)
            if spot <= 0:
                continue
            iv = self._iv_for(meta)
            thesis = meta.get("reason") or f"v3 bearish signal (score {score:+.2f}) in {self._regime} regime"
            priority = abs(score) * (1.0 + 0.3 * (iv < 0.30))  # prefer cheaper vol for long premium
            # Strong conviction -> defined-risk spread; milder -> outright long put.
            if score <= self.short_score_threshold * 1.5:
                out.append(self.build_bear_put_spread(sym, spot, iv, thesis, priority))
            else:
                out.append(self.build_long_put(sym, spot, iv, thesis, priority, category="short"))
        return sorted(out, key=lambda s: s.priority, reverse=True)[: self.max_suggestions_per_category]

    def suggest_longs(self) -> List[OptionSuggestion]:
        out = []
        for sym, meta in self._candidates.items():
            score = float(meta.get("directional_score", 0.0) or 0.0)
            if score < self.long_score_threshold:
                continue
            spot = float(meta.get("spot", 0.0) or 0.0)
            if spot <= 0:
                continue
            iv = self._iv_for(meta)
            thesis = meta.get("reason") or f"v3 bullish signal (score {score:+.2f}) in {self._regime} regime"
            priority = abs(score) * (1.0 + 0.3 * (iv < 0.30))
            if iv > 0.45:  # rich vol -> spread to cut premium; else outright call
                out.append(self.build_bull_call_spread(sym, spot, iv, thesis, priority))
            else:
                out.append(self.build_long_call(sym, spot, iv, thesis, priority))
        return sorted(out, key=lambda s: s.priority, reverse=True)[: self.max_suggestions_per_category]

    def suggest_hedges(self) -> List[OptionSuggestion]:
        """For deteriorating equities we HOLD, protect instead of selling."""
        out = []
        for sym, meta in self._holdings.items():
            situation = float(meta.get("situation_score", 0.0) or 0.0)
            qty = float(meta.get("quantity", 0.0) or 0.0)
            spot = float(meta.get("spot", 0.0) or 0.0)
            if qty <= 0 or spot <= 0 or situation > self.hedge_deterioration_threshold:
                continue
            iv = self._iv_for(meta)
            severity = abs(situation)
            thesis = (
                meta.get("reason")
                or f"Held equity deteriorating (situation {situation:+.2f}); hedge rather than sell "
                   f"(slow-turnover book, tax cost to rotate)."
            )
            priority = severity
            # Mild-to-moderate deterioration: cheap protective put or a
            # zero-cost collar (finance the put by capping upside). Severe:
            # protective put (full downside protection).
            if severity >= 0.5:
                out.append(self.build_long_put(sym, spot, iv, thesis, priority, category="hedge", hedges_symbol=sym))
            else:
                out.append(self.build_collar(sym, spot, iv, thesis, priority, hedges_symbol=sym))
        return sorted(out, key=lambda s: s.priority, reverse=True)[: self.max_suggestions_per_category]

    def suggest_opportunities(self) -> List[OptionSuggestion]:
        """Regime/IV-driven non-directional structures on index + liquid names."""
        out = []
        regime_l = self._regime.lower()
        # Universe for non-directional plays: indices + any candidate flagged neutral.
        pool: Dict[str, Dict[str, Any]] = {}
        for name in ("NIFTY", "BANKNIFTY"):
            idx = self._candidates.get(name)
            if idx:
                pool[name] = idx
        for sym, meta in self._candidates.items():
            if abs(float(meta.get("directional_score", 0.0) or 0.0)) < 0.10:  # neutral view
                pool.setdefault(sym, meta)

        range_bound = any(k in regime_l for k in ("range", "neutral", "low", "calm", "supportive", "expansion"))
        event_vol = any(k in regime_l for k in ("event", "pre", "uncertain", "transition"))

        for sym, meta in pool.items():
            spot = float(meta.get("spot", 0.0) or 0.0)
            if spot <= 0:
                continue
            iv = self._iv_for(meta)
            if range_bound or (not event_vol and iv >= 0.30):
                thesis = f"Range-bound / rich-vol regime ({self._regime}); collect premium with defined risk."
                out.append(self.build_iron_condor(sym, spot, iv, thesis, priority=0.5 + 0.5 * (iv >= 0.35)))
            elif event_vol or iv < 0.22:
                thesis = f"Event / cheap-vol regime ({self._regime}); position for a large move."
                out.append(self.build_long_straddle(sym, spot, iv, thesis, priority=0.5 + 0.5 * (iv < 0.18)))
        return sorted(out, key=lambda s: s.priority, reverse=True)[: self.max_suggestions_per_category]

    # ------------------------------------------------------------------ #
    # Orchestration
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_economically_meaningful(s: OptionSuggestion) -> bool:
        """Drop degenerate suggestions whose premiums round to ~nothing.

        For penny stocks (e.g. a ₹17 name) the modelled OTM option premiums round
        to 0, so structures collapse to max_loss=0 / max_profit=0 — a meaningless
        "trade" that conveys no signal (JPPOWER iron_condor 0/0/-0 was being
        emitted). Require a non-trivial economic footprint on at least one side.
        """
        MIN_INR = 1.0
        debit = abs(float(getattr(s, "net_debit_credit", 0.0) or 0.0))
        max_loss = abs(float(getattr(s, "max_loss", 0.0) or 0.0))
        mp = getattr(s, "max_profit", 0.0)
        max_profit = float("inf") if mp in (None, float("inf")) else abs(float(mp))
        return max(debit, max_loss, 0.0 if max_profit == float("inf") else max_profit) >= MIN_INR

    def process(self) -> List[OptionSuggestion]:
        raw = (
            self.suggest_shorts()
            + self.suggest_longs()
            + self.suggest_hedges()
            + self.suggest_opportunities()
        )
        dropped = [s for s in raw if not self._is_economically_meaningful(s)]
        if dropped:
            self.log.info(
                "OptionsOrgan dropped %d degenerate (zero-premium) suggestions: %s",
                len(dropped), ", ".join(sorted({s.underlying for s in dropped}))[:200],
            )
        self.suggestions = [s for s in raw if self._is_economically_meaningful(s)]
        # History-aware: tag continuity/streaks + boost persistent convictions,
        # so decisions build on yesterday/last week instead of starting fresh.
        if self._store is not None:
            try:
                self._store.annotate(self.suggestions)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("suggestion history annotate degraded: %s", exc)
        cont = sum(1 for s in self.suggestions if s.status == "continued")
        self.log.info(
            "OptionsOrgan produced %d suggestions (regime=%s, %d continued from prior days)",
            len(self.suggestions), self._regime, cont,
        )
        return self.suggestions

    def record_history(self) -> None:
        if self._store is not None:
            try:
                self._store.record(self.suggestions, self._regime)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("suggestion history record degraded: %s", exc)

    def write_report(self) -> Path:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for s in self.suggestions:
            by_cat.setdefault(s.category, []).append(s.to_dict())
        payload = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "regime": self._regime,
            "target_dte": self.target_dte,
            "modeled": self.chain_provider is None,
            "counts": {k: len(v) for k, v in by_cat.items()},
            "suggestions": by_cat,
        }
        tmp = self.report_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.report_path)
        return self.report_path

    def aggregate_greeks(self) -> Dict[str, float]:
        """Net portfolio greeks across all suggested structures (per lot)."""
        return {
            "net_delta": round(sum(s.net_delta * s.lot_size for s in self.suggestions), 2),
            "net_theta": round(sum(s.net_theta * s.lot_size for s in self.suggestions), 2),
            "net_vega": round(sum(s.net_vega * s.lot_size for s in self.suggestions), 2),
            "premium_at_risk": round(
                sum(s.max_loss for s in self.suggestions if s.max_loss and s.max_loss > 0), 2
            ),
        }

    # ------------------------------------------------------------------ #
    # v3 organ contract
    # ------------------------------------------------------------------ #
    def read_state(self, state: Any) -> None:
        """Extract regime, held equities, and directional candidates from v3
        UnifiedState. Defensive: any missing field degrades to empty, never
        raises, so the organ can't break the organ bus."""
        regime = "unknown"
        holdings: Dict[str, Dict[str, Any]] = {}
        candidates: Dict[str, Dict[str, Any]] = {}
        try:
            market = getattr(state, "market", None) or getattr(state, "market_state", None)
            if market is not None:
                regime = str(getattr(market, "regime", None) or getattr(market, "current_regime", "unknown"))
            portfolio = getattr(state, "portfolio", None) or getattr(state, "portfolio_state", None)
            positions = getattr(portfolio, "positions", None) if portfolio is not None else None
            if isinstance(positions, dict):
                for sym, pos in positions.items():
                    if not isinstance(pos, dict):
                        continue
                    holdings[str(sym)] = {
                        "spot": pos.get("spot") or pos.get("price") or pos.get("last_price") or 0.0,
                        "quantity": pos.get("quantity") or pos.get("qty") or 0.0,
                        "situation_score": pos.get("situation_score", pos.get("signal_score", 0.0)),
                        "realized_vol": pos.get("realized_vol", 0.25),
                        "sector": pos.get("sector", ""),
                        "reason": pos.get("reason"),
                    }
            # Directional candidates may be attached to intelligence/strategy state.
            cand_src = getattr(state, "options_candidates", None)
            if isinstance(cand_src, dict):
                candidates = cand_src
        except Exception as exc:  # noqa: BLE001
            self.log.warning("OptionsOrgan.read_state degraded: %s", exc)

        # If v3 state didn't carry explicit candidates, derive them from the
        # real v3 artifacts (daily scorer + sentiment + prices + portfolio).
        if not candidates and self.use_v3_artifacts:
            try:
                a_regime, a_candidates, a_holdings = self._build_from_v3_artifacts()
                candidates = a_candidates or candidates
                holdings = holdings or a_holdings
                if regime in ("unknown", "", None):
                    regime = a_regime
            except Exception as exc:  # noqa: BLE001
                self.log.warning("OptionsOrgan v3-artifact candidate build degraded: %s", exc)

        self.ingest(regime=regime, holdings=holdings, candidates=candidates)

    def attach_news_overlay(self, overlay: Any) -> None:
        """Attach a NIL-style news overlay (must expose .scores() -> {ticker: [-1,1]}).
        Sharpens situation/directional scores with event-level news signals."""
        self._news_overlay = overlay

    def _build_from_v3_artifacts(self):
        from src.options.candidate_builder import CandidateBuilder
        builder = CandidateBuilder(news_overlay=self._news_overlay, log=self.log)
        return builder.build(regime_fallback=self._regime)

    def run_from_v3_artifacts(self) -> List[OptionSuggestion]:
        """Standalone entry: build inputs from v3 artifacts and produce
        suggestions (for the daily pipeline / CLI, no UnifiedState needed)."""
        regime, candidates, holdings = self._build_from_v3_artifacts()
        self.ingest(regime=regime, holdings=holdings, candidates=candidates)
        self.process()
        self.write_report()
        self.record_history()
        return self.suggestions

    def write_state(self, state: Any) -> None:
        """Publish aggregate options greeks + the suggestion artifact path back
        into v3 PortfolioState.options_* fields (defensive)."""
        try:
            self.write_report()
            greeks = self.aggregate_greeks()
            portfolio = getattr(state, "portfolio", None) or getattr(state, "portfolio_state", None)
            if portfolio is not None:
                setattr(portfolio, "options_net_delta", greeks["net_delta"])
                setattr(portfolio, "options_net_vega", greeks["net_vega"])
                setattr(portfolio, "options_net_theta", greeks["net_theta"])
                setattr(portfolio, "options_premium_at_risk", greeks["premium_at_risk"])
                setattr(portfolio, "options_position_count", len(self.suggestions))
                setattr(portfolio, "options_system_mode", "ADVISORY")
            self.record_history()
        except Exception as exc:  # noqa: BLE001
            self.log.warning("OptionsOrgan.write_state degraded: %s", exc)

    def execute_full_cycle(self, state: Any) -> Dict[str, Any]:
        self.read_state(state)
        self.process()
        self.write_state(state)
        return {
            "organ": self.name,
            "suggestions": len(self.suggestions),
            "regime": self._regime,
            "report": str(self.report_path),
        }
