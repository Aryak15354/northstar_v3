"""
PaperPortfolioEngine — the ONE source of truth for Northstar V3's imaginary money.

A fixed ₹100 crore paper fund that behaves like an institutional book:

  * A real position ledger with FIFO cost basis (no phantom positions).
  * Day-by-day mark-to-market: NAV = cash + Σ(qty × close). Every rupee of
    cash movement is a modelled trade, cost, tax, or expense — nothing else.
  * Systematic rules it cannot violate: single-name cap, sector cap, cash floor.
  * Hedge-fund liquidation realism: it CANNOT dump the book in a day. Each
    name's daily traded value is capped at a fraction of its ADV, and total
    daily turnover is capped at a fraction of NAV, so entries and exits scan
    over multiple days.
  * Full Indian frictions: brokerage, STT, stamp, exchange/SEBI, GST, slippage
    (IndianEquityCostModel) and realized LTCG/STCG (EquityTaxLotTracker), plus a
    daily expense-ratio drag.
  * Honest horizon: it marks to the last available price date and stops there;
    re-running after new prices land auto-extends the NAV.

The engine is target-agnostic: give it any `[ticker, weight]` target and it
produces a rule-abiding NAV path. V3 uses its live target; the famous
benchmark strategies (Buffett, Magic Formula, …) run through the exact same
machinery so future Kaggle alpha can be tested on a level field.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from src.pnl.indian_cost_model import IndianEquityCostModel
from src.pnl.equity_tax_lots import EquityTaxLotTracker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PNL_CONFIG = PROJECT_ROOT / "config" / "pnl_config.yaml"
_GOV_CONFIG = PROJECT_ROOT / "config" / "portfolio_governor_config.yaml"
_PRICES = PROJECT_ROOT / "data" / "processed" / "prices.parquet"


def _load_yaml(path: Path) -> dict:
    if yaml is None or not path.exists():
        return {}
    try:
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    except Exception:  # pragma: no cover
        return {}


# --------------------------------------------------------------------------- #
# Market data (loaded once, shared across engine runs)
# --------------------------------------------------------------------------- #
class MarketData:
    """Close-price and ADV panels, pivoted for fast daily lookups."""

    _cache: Optional["MarketData"] = None

    def __init__(self, adv_lookback: int = 20):
        px = pd.read_parquet(_PRICES, columns=["Date", "ticker", "Close", "Volume"])
        px["Date"] = pd.to_datetime(px["Date"], errors="coerce")
        px = px.dropna(subset=["Date", "ticker", "Close"]).sort_values("Date")
        px = px[~px.duplicated(subset=["Date", "ticker"], keep="last")]
        # Forward-fill so a held position always marks to its last known price
        # even on days the name didn't print a trade (NSE illiquid sessions).
        self.close = px.pivot(index="Date", columns="ticker", values="Close").sort_index()
        self.close = self._sanitize(self.close).ffill()
        turnover = (px.assign(t=px["Close"] * px["Volume"].fillna(0.0))
                    .pivot(index="Date", columns="ticker", values="t").sort_index())
        # ADV in ₹: rolling mean of daily traded value.
        self.adv = turnover.rolling(adv_lookback, min_periods=5).mean()
        self.dates = self.close.index
        self.last_date = self.dates.max()

    @staticmethod
    def _sanitize(close: pd.DataFrame) -> pd.DataFrame:
        """Safety net: back-adjust any residual price-scale discontinuities.
        The primary repair now happens at the raw→processed merge
        (src/processing/price_processor.py via src/data/price_sanitizer), so
        this is normally a no-op — kept so the fund can never be poisoned by
        an upstream regression."""
        from src.data.price_sanitizer import sanitize_close_panel
        return sanitize_close_panel(close)

    @classmethod
    def get(cls, adv_lookback: int = 20) -> "MarketData":
        if cls._cache is None:
            cls._cache = MarketData(adv_lookback=adv_lookback)
        return cls._cache


# --------------------------------------------------------------------------- #
# Result container
# --------------------------------------------------------------------------- #
@dataclass
class SimulationResult:
    strategy_id: str
    nav_history: pd.DataFrame
    positions: pd.DataFrame
    ledger: pd.DataFrame
    cost_summary: dict
    liquidation_schedule: pd.DataFrame
    metrics: dict


@dataclass
class _Position:
    qty: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.qty > 1e-6


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class PaperPortfolioEngine:
    def __init__(
        self,
        target_weights: Optional[pd.DataFrame] = None,
        *,
        strategy_id: str = "v3",
        config: Optional[dict] = None,
        market: Optional[MarketData] = None,
        target_schedule: Optional[dict] = None,
    ):
        """target_weights: a single static target (benchmark strategies).
        target_schedule: {as_of_date -> weights_df} — the POINT-IN-TIME record of
        what the target actually was over time. When a schedule is given the
        engine rebalances at each date to the target that was known AS-OF that
        date, so the NAV curve is an honest walk-forward record. The old path
        (single target replayed from inception) baked today's book into all past
        dates — a look-ahead that made nav_history.parquet a restated backfill
        that mutated on every run. See scripts/run_paper_fund.py."""
        cfg = config if config is not None else _load_yaml(_PNL_CONFIG)
        nav_cfg = cfg.get("pnl", {}).get("nav", {})
        rules = cfg.get("rules", {})
        exp = cfg.get("expenses", {})

        self.strategy_id = strategy_id
        self.starting_capital = float(nav_cfg.get("starting_capital_inr", 1_000_000_000))
        self.inception = pd.to_datetime(nav_cfg.get("inception_date", "2024-09-01"))
        self.unit_size = float(nav_cfg.get("nav_unit_size", 1000))
        self.initial_units = self.starting_capital / self.unit_size

        gov = _load_yaml(_GOV_CONFIG)
        self.equity_fraction = float(
            gov.get("default_capital_structure", {}).get("equity_fraction", 0.75)
        )

        self.max_position = float(rules.get("max_position_pct", 8.0)) / 100.0
        self.max_sector = float(rules.get("max_sector_pct", 25.0)) / 100.0
        self.cash_floor = float(rules.get("cash_floor_pct", 2.0)) / 100.0
        self.adv_participation = float(rules.get("max_adv_participation_pct", 15.0)) / 100.0
        self.max_turnover = float(rules.get("max_daily_turnover_pct", 20.0)) / 100.0
        self.rebalance_band = float(rules.get("rebalance_band_pct", 25.0)) / 100.0
        self.default_adv = float(rules.get("default_adv_inr", 50_000_000))
        self.expense_daily = float(exp.get("expense_ratio_annual_pct", 1.0)) / 100.0 / 252.0

        self.cost_model = IndianEquityCostModel(cfg)
        self.tax = EquityTaxLotTracker(cfg)
        self.market = market or MarketData.get(int(rules.get("adv_lookback_days", 20)))

        if target_schedule:
            prepared: list[tuple[pd.Timestamp, pd.DataFrame]] = []
            for raw_dt, frame in target_schedule.items():
                ts = pd.to_datetime(raw_dt, errors="coerce")
                if pd.isna(ts) or frame is None:
                    continue
                try:
                    prepared.append((pd.Timestamp(ts).normalize(), self._prepare_target(frame)))
                except ValueError:
                    continue
            if not prepared:
                raise ValueError("target_schedule produced no valid, priceable targets")
            prepared.sort(key=lambda item: item[0])
            self._schedule = prepared
            self.target = prepared[-1][1]  # latest target: used for sector lookups / reporting
            # Honest inception: the track record starts when the first REAL target
            # existed, never earlier (no flat-cash or back-projected prehistory).
            self.inception = max(self.inception, prepared[0][0])
        else:
            if target_weights is None:
                raise ValueError("provide either target_weights or target_schedule")
            self._schedule = None
            self.target = self._prepare_target(target_weights)

    # ---- target construction (rules-constrained) ------------------------- #
    def _prepare_target(self, tw: pd.DataFrame) -> pd.DataFrame:
        df = tw.copy()
        wcol = "weight" if "weight" in df.columns else ("final_weight" if "final_weight" in df.columns else None)
        if wcol is None or "ticker" not in df.columns:
            raise ValueError("target_weights needs 'ticker' and 'weight'/'final_weight'")
        df = df.rename(columns={wcol: "weight"})
        df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0.0).clip(lower=0.0)
        df = df[df["weight"] > 0]
        # only names we can actually price
        df = df[df["ticker"].isin(self.market.close.columns)]
        if df.empty:
            raise ValueError("no priceable names in target")
        df["sector"] = df.get("Industry", pd.Series(["Unknown"] * len(df), index=df.index)).fillna("Unknown")
        # The SUM of the incoming weights encodes the intended gross equity
        # exposure (e.g. the governor emits a 0.30-gross defensive book). Capture
        # it BEFORE normalising to 1, so the engine can respect that intent rather
        # than always deploying the full equity_fraction sleeve. Clipped to [0,1].
        raw_sum = float(df["weight"].sum())
        intended_gross = min(max(raw_sum, 0.0), 1.0)
        df["weight"] = df["weight"] / raw_sum
        df = self._apply_caps(df)
        out = df.reset_index(drop=True)
        out.attrs["intended_gross"] = intended_gross
        return out

    def _apply_caps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Iteratively enforce single-name and sector caps, renormalising to 1."""
        w = df.set_index("ticker")["weight"].copy()
        sector = df.set_index("ticker")["sector"]
        for _ in range(50):
            changed = False
            # single-name cap
            over = w[w > self.max_position]
            if len(over):
                excess = (over - self.max_position).sum()
                w[over.index] = self.max_position
                free = w[w < self.max_position]
                if free.sum() > 0 and excess > 1e-12:
                    w[free.index] += excess * (free / free.sum())
                    changed = True
            # sector cap
            sec_tot = w.groupby(sector).sum()
            hot = sec_tot[sec_tot > self.max_sector]
            for sec, tot in hot.items():
                names = sector[sector == sec].index
                scale = self.max_sector / tot
                spill = w[names].sum() * (1 - scale)
                w[names] *= scale
                cool = w[w.index.isin(sector[sector != sec].index)]
                if cool.sum() > 0 and spill > 1e-12:
                    w[cool.index] += spill * (cool / cool.sum())
                    changed = True
            if not changed:
                break
        w = w / w.sum()
        out = df.copy()
        out["weight"] = out["ticker"].map(w).values
        return out

    # ---- helpers --------------------------------------------------------- #
    def _rebalance_dates(self) -> list[pd.Timestamp]:
        """Inception fill + first trading day of each subsequent month."""
        dates = self.market.dates[(self.market.dates >= self.inception)]
        if len(dates) == 0:
            return []
        s = pd.Series(dates, index=dates)
        firsts = s.groupby([dates.year, dates.month]).first().tolist()
        out = sorted(set([dates[0]] + firsts))
        return [pd.Timestamp(d) for d in out]

    def _adv_at(self, date, ticker) -> float:
        try:
            v = self.market.adv.at[date, ticker]
            if pd.notna(v) and v > 0:
                return float(v)
        except Exception:
            pass
        return self.default_adv

    def _target_frame_as_of(self, d: pd.Timestamp) -> Optional[pd.DataFrame]:
        """The prepared target frame KNOWN as-of date d (most recent scheduled
        target with date <= d). With no schedule, the single static target
        applies. Before the first scheduled target existed, returns None (the
        fund holds cash)."""
        if self._schedule is None:
            return self.target
        chosen = None
        for ts, tgt in self._schedule:
            if ts <= d:
                chosen = tgt
            else:
                break
        return chosen

    def _effective_equity(self, target_frame: Optional[pd.DataFrame]) -> float:
        """Equity sleeve to deploy: the target's intended gross, HARD-CAPPED by
        the configured equity_fraction. Reconciles the two exposure controls that
        previously fought each other (governor gross vs fixed equity_fraction):
        a 0.30-gross book now deploys 30%, not the full 75%."""
        if target_frame is None or target_frame.empty:
            return 0.0
        gross = float(target_frame.attrs.get("intended_gross", 1.0))
        return min(max(gross, 0.0), float(self.equity_fraction))

    # ---- main simulation ------------------------------------------------- #
    def simulate(self) -> SimulationResult:
        close = self.market.close
        dates = [d for d in close.index if d >= self.inception]
        rebal = set(self._rebalance_dates())
        # Rebalance promptly whenever a new point-in-time target arrives, too.
        if self._schedule is not None:
            rebal |= {ts for ts, _ in self._schedule}

        cash = self.starting_capital
        positions: dict[str, _Position] = {}
        target_notional: dict[str, float] = {}   # ₹ target per name, set at rebalance
        ledger: list[dict] = []
        nav_rows: list[dict] = []
        hwm = self.starting_capital
        max_dd = 0.0
        cum_costs = 0.0
        cum_tax = 0.0
        prev_nav = self.starting_capital

        def price(d, t):
            try:
                p = close.at[d, t]
                return float(p) if pd.notna(p) else None
            except Exception:
                return None

        def mtm(d):
            v = 0.0
            for t, pos in positions.items():
                if pos.is_open:
                    p = price(d, t)
                    if p is not None:
                        v += pos.qty * p
            return v

        for d in dates:
            # 1) set targets on rebalance days (target ₹ = weight × equity sleeve of current NAV)
            #    using the weights KNOWN AS-OF this date (point-in-time, no look-ahead).
            #    The equity sleeve honours the target's intended gross (governor
            #    exposure decision), hard-capped by equity_fraction.
            if d in rebal:
                nav_now = cash + mtm(d)
                tgt_frame = self._target_frame_as_of(d)
                equity_budget = nav_now * self._effective_equity(tgt_frame)
                if tgt_frame is None or tgt_frame.empty:
                    target_notional = {}
                else:
                    target_notional = {
                        t: w * equity_budget
                        for t, w in zip(tgt_frame["ticker"], tgt_frame["weight"])
                    }

            # 2) build desired orders vs current book. A name is only traded once
            # it drifts beyond the rebalance band (or isn't yet established) — this
            # is what stops a constant target from churning (and taxing) itself.
            orders = []  # (ticker, side, value)
            for t, tgt_val in target_notional.items():
                p = price(d, t)
                if p is None or tgt_val <= 0:
                    continue
                cur_val = positions.get(t, _Position()).qty * p
                diff = tgt_val - cur_val
                drift = abs(diff) / tgt_val
                establishing = cur_val < 1000.0  # not yet built → always trade toward target
                if establishing or drift > self.rebalance_band:
                    orders.append([t, "BUY" if diff > 0 else "SELL", abs(diff)])
            # also fully exit names no longer in target
            for t, pos in positions.items():
                if pos.is_open and t not in target_notional:
                    p = price(d, t)
                    if p is not None:
                        orders.append([t, "SELL", pos.qty * p])

            # 3) apply ADV participation cap per name, then NAV turnover cap
            nav_pre = cash + mtm(d)
            turnover_budget = nav_pre * self.max_turnover
            # prioritise sells (raise cash) then buys; scale within budget
            capped = []
            for t, side, val in orders:
                adv_cap = self.adv_participation * self._adv_at(d, t)
                capped.append([t, side, min(val, adv_cap)])
            sells = [o for o in capped if o[1] == "SELL"]
            buys = [o for o in capped if o[1] == "BUY"]
            # Cash-floor enforcement: BUYS may not spend cash below the floor.
            # Previously buys were bounded only by the turnover budget, so a
            # drawdown + a full target could drive cash negative even though the
            # docstring promised "a cash floor it cannot violate". Conservatively
            # cap cumulative buy spend at (current cash − floor); same-day sell
            # proceeds are intentionally NOT counted so the floor can never break.
            buy_cash_budget = max(0.0, cash - self.cash_floor * nav_pre)
            spent = 0.0
            buy_spent = 0.0
            day_orders = []
            for t, side, val in sells + buys:
                room = turnover_budget - spent
                if room <= 0:
                    break
                v = min(val, room)
                if side == "BUY":
                    v = min(v, buy_cash_budget - buy_spent)
                if v < 1000.0:
                    continue
                day_orders.append([t, side, v])
                spent += v
                if side == "BUY":
                    buy_spent += v

            # 4) execute fills at close ± slippage; book costs, taxes, ledger
            for t, side, val in day_orders:
                p = price(d, t)
                if p is None or p <= 0:
                    continue
                adv = self._adv_at(d, t)
                slip_bps = self.cost_model.slippage_bps_for(val, adv)
                fill = p * (1 + slip_bps / 10_000.0) if side == "BUY" else p * (1 - slip_bps / 10_000.0)
                qty = val / fill
                cb = self.cost_model.cost_breakdown(side, val, adv_inr=adv)
                statutory = cb.total - cb.slippage  # slippage already in the fill price
                pos = positions.setdefault(t, _Position())
                realized_tax = 0.0
                if side == "BUY":
                    # amortise buy-side statutory costs into cost basis per share
                    cost_per_share = fill + statutory / qty
                    self.tax.buy(t, qty, cost_per_share, d.to_pydatetime())
                    pos.qty += qty
                    cash -= (val + statutory)
                else:
                    qty = min(qty, pos.qty)
                    if qty <= 0:
                        continue
                    net_proceeds = qty * fill - statutory
                    gain = self.tax.sell(t, qty, net_proceeds / qty, d.to_pydatetime())
                    realized_tax = gain.tax
                    pos.qty -= qty
                    cash += (qty * fill - statutory - realized_tax)
                cum_costs += cb.total
                cum_tax += realized_tax
                # Attribution note: slippage is an EXECUTION price effect and is
                # already embedded in `fill` (hence in `notional` and in the
                # tax-lot realized_pnl/gross_gain). So the ledger's transaction_cost
                # / net_pnl record STATUTORY charges only — otherwise summing
                # realized_pnl + net_pnl would subtract slippage twice. Slippage is
                # surfaced separately via slippage_cost / slippage_bps. (cum_costs
                # remains the full friction total for the standalone cost summary.)
                ledger.append(dict(
                    entry_id=str(uuid.uuid4()),
                    entry_type=("EQUITY_BUY" if side == "BUY" else "EQUITY_SELL"),
                    book="EQUITY", trade_date=d, settlement_date=d, recorded_at=datetime.now(),
                    ticker=t, quantity=(qty if side == "BUY" else -qty), price=fill,
                    notional=qty * fill, realized_pnl=(0.0 if side == "BUY" else gain.gross_gain),
                    unrealized_pnl_change=0.0, transaction_cost=-statutory,
                    slippage_cost=-cb.slippage, net_pnl=-(statutory + realized_tax),
                    strategy_id=self.strategy_id, source="PAPER", slippage_bps=slip_bps,
                ))

            # 5) expense-ratio drag (daily, on NAV)
            nav_after_trades = cash + mtm(d)
            expense = nav_after_trades * self.expense_daily
            cash -= expense
            cum_costs += expense

            # 6) mark NAV and record
            equity_val = mtm(d)
            nav = cash + equity_val
            if nav > hwm:
                hwm = nav
            dd = (nav / hwm - 1) if hwm > 0 else 0.0
            max_dd = min(max_dd, dd)
            daily_ret = (nav / prev_nav - 1) if prev_nav > 0 else 0.0
            prev_nav = nav
            nav_rows.append(dict(
                date=d, nav_combined=nav, nav_equity_only=nav, nav_options_pnl=0.0,
                nav_per_unit=nav / self.initial_units, daily_return=daily_ret,
                daily_return_equity=daily_ret, high_water_mark=hwm, drawdown=dd,
                max_drawdown_to_date=max_dd, net_cash_position=cash,
                transaction_costs_cumulative=cum_costs,
            ))

        nav_df = pd.DataFrame(nav_rows)
        positions_df = self._positions_frame(positions, dates[-1] if dates else self.inception)
        ledger_df = pd.DataFrame(ledger)
        liq = self._liquidation_schedule(positions, dates[-1] if dates else self.inception)
        metrics = self._metrics(nav_df, cum_costs, cum_tax)
        cost_summary = dict(
            cumulative_costs=cum_costs, cumulative_tax=cum_tax,
            cost_drag_pct=(cum_costs / self.starting_capital * 100.0),
            tax_drag_pct=(cum_tax / self.starting_capital * 100.0),
        )
        return SimulationResult(self.strategy_id, nav_df, positions_df, ledger_df,
                                cost_summary, liq, metrics)

    # ---- output frames --------------------------------------------------- #
    def _positions_frame(self, positions: dict, last_date) -> pd.DataFrame:
        rows = []
        nav = None
        for t, pos in positions.items():
            if not pos.is_open:
                continue
            p = None
            try:
                p = float(self.market.close.at[last_date, t])
            except Exception:
                p = self.tax.average_cost(t)
            avg = self.tax.average_cost(t) or p
            mv = pos.qty * (p or 0.0)
            rows.append(dict(
                ticker=t, quantity=pos.qty, avg_cost=avg, last_price=p,
                market_value=mv, unrealized_pnl=(p - avg) * pos.qty if (p and avg) else 0.0,
                sector=self.target.set_index("ticker")["sector"].get(t, "Unknown"),
                strategy_id=self.strategy_id, as_of=last_date,
            ))
        df = pd.DataFrame(rows)
        if not df.empty:
            tot = df["market_value"].sum()
            df["weight_pct"] = 100.0 * df["market_value"] / tot if tot > 0 else 0.0
            df = df.sort_values("market_value", ascending=False)
        return df

    def _liquidation_schedule(self, positions: dict, last_date) -> pd.DataFrame:
        """Days-to-exit each name at the ADV participation cap — proves the book
        cannot be liquidated in a day."""
        rows = []
        for t, pos in positions.items():
            if not pos.is_open:
                continue
            try:
                p = float(self.market.close.at[last_date, t])
            except Exception:
                continue
            mv = pos.qty * p
            adv = self._adv_at(last_date, t)
            daily_cap = self.adv_participation * adv
            days = math.ceil(mv / daily_cap) if (daily_cap > 0 and np.isfinite(mv)) else 999
            rows.append(dict(ticker=t, market_value=mv, adv_inr=adv,
                             daily_exit_cap=daily_cap, days_to_exit=days))
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("days_to_exit", ascending=False)
        return df

    def _metrics(self, nav_df: pd.DataFrame, cum_costs: float, cum_tax: float) -> dict:
        if nav_df.empty:
            return {}
        r = nav_df["daily_return"].dropna()
        total_return = nav_df["nav_combined"].iloc[-1] / self.starting_capital - 1
        years = max(len(nav_df) / 252.0, 1e-9)
        ann = (1 + total_return) ** (1 / years) - 1
        vol = r.std() * np.sqrt(252) if len(r) else 0.0
        sharpe = (ann - 0.065) / vol if vol > 0 else 0.0
        return dict(
            total_return_pct=total_return * 100, annualized_return_pct=ann * 100,
            annualized_vol_pct=vol * 100, sharpe=sharpe,
            max_drawdown_pct=nav_df["max_drawdown_to_date"].min() * 100,
            final_nav=nav_df["nav_combined"].iloc[-1],
            as_of=str(nav_df["date"].iloc[-1].date()), trading_days=len(nav_df),
        )
