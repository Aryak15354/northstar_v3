"""
Daily Shadow Trader

Executes daily shadow trading from real portfolio weights and real market prices.
No synthetic positions or random returns are generated.
"""

import sys
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Tuple

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from runtime import DecisionMode, PortfolioRuntimeService, ProposalOrigin, TradeProposal, build_certification_snapshot
from runtime.hash_utils import canonical_hash, file_sha256


class DailyShadowTrader:
    """Daily shadow trading execution engine (real-data-only)."""

    def __init__(self, initial_capital: float = 10000000, data_directory: str = "data/live/shadow_trading"):
        self.initial_capital = float(initial_capital)
        self.current_capital = float(initial_capital)
        self.data_dir = Path(data_directory)
        self.logger = logging.getLogger(__name__)

        self.project_root = project_root
        self.weights_path = self.project_root / "data/processed/portfolio_weights.parquet"
        self.prices_path = self.project_root / "data/processed/prices.parquet"

        # Create data directories
        self.positions_dir = self.data_dir / "positions"
        self.pnl_dir = self.data_dir / "pnl"
        self.decisions_dir = self.data_dir / "decisions"
        for directory in [self.positions_dir, self.pnl_dir, self.decisions_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.current_positions: Dict[str, Dict[str, float]] = {}
        self.performance_history: List[Dict[str, Any]] = []
        self.prs = None
        self.prs_context: Dict[str, str] = {}
        self.prs_cert_snapshot_hash = ""
        self._init_prs_runtime()

    def _init_prs_runtime(self) -> None:
        db_path = Path(
            str(
                os.getenv(
                    "NORTHSTAR_PRS_DAILY_SHADOW_DB",
                    "data/runtime/daily_shadow_runtime.db",
                )
                or "data/runtime/daily_shadow_runtime.db"
            )
        )
        mat_path = Path(
            str(
                os.getenv(
                    "NORTHSTAR_PRS_DAILY_SHADOW_MATERIALIZED",
                    "data/processed/runtime/daily_shadow",
                )
                or "data/processed/runtime/daily_shadow"
            )
        )
        self.prs = PortfolioRuntimeService(
            db_path=str(db_path),
            materialized_output_dir=str(mat_path),
            starting_cash=float(self.initial_capital),
        )
        self.prs_context = self._build_prs_context()
        self.prs_cert_snapshot_hash = self._refresh_prs_certification_snapshot()

    def _build_prs_context(self) -> Dict[str, str]:
        try:
            config_hash = file_sha256(__file__)
        except Exception:
            config_hash = ""
        return {
            "model_hash": canonical_hash({"engine": "daily_shadow_trader", "version": "v1"}),
            "param_hash": canonical_hash({"initial_capital": float(self.initial_capital)}),
            "feature_hash": canonical_hash(["portfolio_weights", "prices"]),
            "data_revision_hash": canonical_hash(
                {
                    "weights_mtime_ns": self.weights_path.stat().st_mtime_ns if self.weights_path.exists() else 0,
                    "prices_mtime_ns": self.prices_path.stat().st_mtime_ns if self.prices_path.exists() else 0,
                }
            ),
            "config_hash": config_hash,
            "drift_guard_version": "v1",
        }

    def _refresh_prs_certification_snapshot(self) -> str:
        if self.prs is None:
            return ""
        ctx = dict(self.prs_context)
        snap = build_certification_snapshot(
            model_hash=str(ctx.get("model_hash", "")),
            param_hash=str(ctx.get("param_hash", "")),
            feature_hash=str(ctx.get("feature_hash", "")),
            data_revision_hash=str(ctx.get("data_revision_hash", "")),
            config_hash=str(ctx.get("config_hash", "")),
            created_at=datetime.utcnow(),
            ttl_days=30,
            drift_guard_version=str(ctx.get("drift_guard_version", "v1")),
        )
        self.prs.register_certification_snapshot(snap)
        return str(snap.snapshot_hash)

    def _sync_positions_from_prs(self, prices_current: pd.Series) -> Dict[str, Dict[str, float]]:
        if self.prs is None:
            return {}
        snap = self.prs.get_portfolio_state().to_dict()
        holdings = dict(snap.get("holdings", {}) or {})
        positions: Dict[str, Dict[str, float]] = {}
        gross = 0.0
        for ticker, payload in holdings.items():
            qty = float(payload.get("quantity", 0.0) or 0.0)
            if abs(qty) < 1e-12:
                continue
            price = float(prices_current.get(ticker, payload.get("last_price", 0.0)) or 0.0)
            market_value = qty * price
            gross += abs(market_value)
            positions[str(ticker)] = {
                "quantity": qty,
                "price": price,
                "weight": 0.0,
            }
        if gross > 0.0:
            for ticker, payload in positions.items():
                payload["weight"] = float(abs(payload["quantity"] * payload["price"]) / gross)
        self.current_positions = positions
        return positions

    def _route_positions_via_prs(self, target_positions: Dict[str, Dict[str, float]], prices_current: pd.Series) -> int:
        if self.prs is None:
            return 0
        snap = self.prs.get_portfolio_state().to_dict()
        holdings = dict(snap.get("holdings", {}) or {})
        current_qty = {str(k): float(v.get("quantity", 0.0) or 0.0) for k, v in holdings.items()}
        symbols = set(current_qty.keys()) | set(target_positions.keys())
        proposal_count = 0
        for ticker in sorted(symbols):
            target_qty = float((target_positions.get(ticker, {}) or {}).get("quantity", 0.0) or 0.0)
            cur_qty = float(current_qty.get(ticker, 0.0) or 0.0)
            delta_qty = target_qty - cur_qty
            if abs(delta_qty) < 1e-9:
                continue
            price = float(prices_current.get(ticker, 0.0) or 0.0)
            if price <= 0.0:
                continue
            side = "buy" if delta_qty > 0.0 else "sell"
            qty = float(abs(delta_qty))
            notional = float(qty * price)
            lifecycle_action = "close" if target_qty == 0.0 else "open"
            now_str = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
            proposal = TradeProposal(
                proposal_id=f"prop_daily_shadow_{ticker}_{now_str}",
                origin=ProposalOrigin.SHADOW,
                strategy_id="daily_shadow_trader",
                signal_id=f"sig_daily_shadow_{ticker}_{now_str}",
                alpha_type="directional",
                expected_edge=0.0,
                risk_score=float(notional / max(1.0, float(self.current_capital))),
                regime_context={"engine": "daily_shadow_trader"},
                instrument_plan={
                    "symbol": str(ticker).upper(),
                    "side": side,
                    "price": price,
                    "quantity": qty,
                    "direction": 1.0 if side == "buy" else -1.0,
                    "instrument_type": "equity",
                    "lifecycle_action": lifecycle_action,
                    "position_key": f"daily_shadow:{str(ticker).upper()}",
                },
                requested_notional=notional,
                certification_snapshot_hash=str(self.prs_cert_snapshot_hash or ""),
                decision_mode=DecisionMode.AUTO,
                trigger_reason_code="rebalance.shadow.daily",
                risk_override_flag=False,
            )
            result = self.prs.process_proposal(
                proposal,
                budget_snapshot={"reserve_usage": {}},
                risk_snapshot={"risk_budget_ratio": 0.0, "signal_entropy": 1.0},
                market_snapshot={},
                market_liquidity_snapshot={
                    "adv_notional": float(notional * 20.0),
                    "spread_bps": 5.0,
                    "depth_qty": float(qty * 5.0),
                    "estimated_slippage_bps": 2.0,
                },
                certification_context=dict(self.prs_context),
                auto_fill=True,
            )
            if result.approved:
                proposal_count += 1
        return proposal_count

    @staticmethod
    def _to_naive_utc_ts(value: Any) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        return ts

    def execute_daily_trading(self, trading_date: datetime) -> Dict[str, Any]:
        """Execute daily shadow trading using real artifacts only."""
        date_str = trading_date.strftime("%Y-%m-%d")

        try:
            weights, weights_date = self._load_latest_weights(trading_date)
            prices_current, returns_1d, price_date, prev_price_date = self._load_returns_for_date(trading_date)

            aligned_weights = weights.reindex(returns_1d.index).fillna(0.0)
            if aligned_weights.sum() <= 0:
                raise ValueError("No overlap between portfolio weights and price returns for trading day")
            aligned_weights = aligned_weights / aligned_weights.sum()

            daily_return = float((aligned_weights * returns_1d).sum())
            prior_capital = float(self.current_capital)
            self.prs_context = self._build_prs_context()
            self.prs_cert_snapshot_hash = self._refresh_prs_certification_snapshot()
            prior_snap = self.prs.get_portfolio_state().to_dict()
            prior_capital = float(prior_snap.get("net_liquidation_value", self.current_capital) or self.current_capital)
            positions_target = self._build_positions(aligned_weights, prices_current, capital=prior_capital)
            proposals_executed = self._route_positions_via_prs(positions_target, prices_current)
            positions = self._sync_positions_from_prs(prices_current)
            snap = self.prs.get_portfolio_state().to_dict()
            cash_value = float(snap.get("cash", 0.0) or 0.0)
            total_position_value = float(sum(p["quantity"] * p["price"] for p in positions.values()))
            portfolio_value = float(cash_value + total_position_value)
            daily_pnl = float(portfolio_value - prior_capital)
            daily_return = float(daily_pnl / prior_capital) if prior_capital > 0 else 0.0
            self.current_capital = portfolio_value

            pnl_data = {
                "daily_return": daily_return,
                "daily_pnl": daily_pnl,
                "cumulative_pnl": float(self.current_capital - self.initial_capital),
                "total_position_value": total_position_value,
                "cash": cash_value,
                "portfolio_value": float(self.current_capital),
                "weights_date": weights_date.strftime("%Y-%m-%d"),
                "price_date": price_date.strftime("%Y-%m-%d"),
                "prev_price_date": prev_price_date.strftime("%Y-%m-%d"),
                "prs_mode": True,
            }

            decisions = [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "real_data_rebalance",
                    "description": (
                        f"Applied live portfolio weights from {weights_date.strftime('%Y-%m-%d')} "
                        f"to market returns on {price_date.strftime('%Y-%m-%d')}"
                    ),
                    "symbols_rebalanced": int(len(aligned_weights[aligned_weights > 0])),
                    "prs_proposals_executed": int(proposals_executed),
                }
            ]

            self._save_daily_positions(trading_date, positions)
            self._save_daily_pnl(trading_date, pnl_data)
            self._save_daily_decisions(trading_date, decisions)

            result = {
                "status": "success",
                "date": date_str,
                "daily_return": daily_return,
                "positions": positions,
                "pnl_data": pnl_data,
                "decisions": decisions,
            }
            self.performance_history.append(result)
            return result

        except Exception as e:
            self.logger.error(f"Daily trading failed for {date_str}: {e}")
            return {
                "status": "error",
                "date": date_str,
                "error": str(e),
            }

    def _load_latest_weights(self, trading_date: datetime) -> Tuple[pd.Series, pd.Timestamp]:
        if not self.weights_path.exists():
            raise FileNotFoundError(f"Portfolio weights file not found: {self.weights_path}")

        wdf = pd.read_parquet(self.weights_path)
        if wdf.empty:
            raise ValueError("Portfolio weights file is empty")

        ticker_col = "ticker" if "ticker" in wdf.columns else ("symbol" if "symbol" in wdf.columns else None)
        if ticker_col is None:
            raise ValueError("portfolio_weights missing ticker/symbol column")

        weight_col = None
        for c in ["weight", "final_weight", "allocation", "w"]:
            if c in wdf.columns:
                weight_col = c
                break
        if weight_col is None:
            raise ValueError("portfolio_weights missing weight/final_weight/allocation column")

        dcol = "date" if "date" in wdf.columns else ("Date" if "Date" in wdf.columns else None)
        if dcol is not None:
            wdf[dcol] = pd.to_datetime(wdf[dcol], errors="coerce", utc=True).dt.tz_localize(None)
            wdf = wdf.dropna(subset=[dcol])
            as_of = self._to_naive_utc_ts(trading_date).normalize()
            eligible = wdf[wdf[dcol] <= as_of]
            if eligible.empty:
                future = wdf[wdf[dcol] > as_of].sort_values(dcol)
                if future.empty:
                    raise ValueError(f"No portfolio weights available on or before {as_of.date()}")
                weights_date = pd.Timestamp(future[dcol].iloc[0]).normalize()
                day_gap = int((weights_date - as_of).days)
                if day_gap > 5:
                    raise ValueError(
                        f"No portfolio weights near {as_of.date()} (earliest available is {weights_date.date()}, gap={day_gap}d)"
                    )
                self.logger.warning(
                    "No weights on/before %s; using earliest subsequent snapshot %s (%dd gap)",
                    as_of.date(),
                    weights_date.date(),
                    day_gap,
                )
                snap = future[future[dcol] == weights_date].copy()
            else:
                weights_date = pd.Timestamp(eligible[dcol].max()).normalize()
                snap = eligible[eligible[dcol] == weights_date].copy()
        else:
            weights_date = self._to_naive_utc_ts(trading_date).normalize()
            snap = wdf.copy()

        snap[ticker_col] = snap[ticker_col].astype(str).str.strip()
        snap[weight_col] = pd.to_numeric(snap[weight_col], errors="coerce")
        snap = snap.dropna(subset=[ticker_col, weight_col])
        snap = snap[snap[weight_col] > 0.0]
        if snap.empty:
            raise ValueError("No positive portfolio weights found for shadow execution")

        weights = snap.groupby(ticker_col)[weight_col].sum().astype(float)
        if weights.sum() <= 0:
            raise ValueError("Non-positive total portfolio weight in shadow execution")
        weights = weights / weights.sum()
        return weights, weights_date

    def _load_returns_for_date(
        self, trading_date: datetime
    ) -> Tuple[pd.Series, pd.Series, pd.Timestamp, pd.Timestamp]:
        if not self.prices_path.exists():
            raise FileNotFoundError(f"Processed prices not found: {self.prices_path}")

        px = pd.read_parquet(self.prices_path, columns=["Date", "ticker", "Close"])
        px["Date"] = pd.to_datetime(px["Date"], errors="coerce", utc=True).dt.tz_localize(None)
        px["Close"] = pd.to_numeric(px["Close"], errors="coerce")
        px["ticker"] = px["ticker"].astype(str)
        px = px.dropna(subset=["Date", "ticker", "Close"])
        if px.empty:
            raise ValueError("Processed prices are empty")

        px = px.sort_values(["Date", "ticker"])
        as_of = self._to_naive_utc_ts(trading_date).normalize()
        available_dates = px.loc[px["Date"] <= as_of, "Date"].drop_duplicates().sort_values()
        if available_dates.empty:
            raise ValueError(f"No market prices available on or before {as_of.date()}")
        price_date = pd.Timestamp(available_dates.iloc[-1]).normalize()

        prior_dates = available_dates[available_dates < price_date]
        if prior_dates.empty:
            raise ValueError(f"No previous market date available before {price_date.date()}")
        prev_price_date = pd.Timestamp(prior_dates.iloc[-1]).normalize()

        cur = px[px["Date"] == price_date].set_index("ticker")["Close"].astype(float)
        prev = px[px["Date"] == prev_price_date].set_index("ticker")["Close"].astype(float)

        common = cur.index.intersection(prev.index)
        if len(common) == 0:
            raise ValueError(f"No overlapping tickers between {prev_price_date.date()} and {price_date.date()}")

        cur = cur.reindex(common)
        prev = prev.reindex(common)
        ret_1d = (cur / prev) - 1.0
        ret_1d = ret_1d.replace([pd.NA, float("inf"), float("-inf")], 0.0).fillna(0.0)
        return cur, ret_1d, price_date, prev_price_date

    def _build_positions(
        self,
        weights: pd.Series,
        prices: pd.Series,
        *,
        capital: float,
    ) -> Dict[str, Dict[str, float]]:
        positions: Dict[str, Dict[str, float]] = {}
        common = weights.index.intersection(prices.index)
        for ticker in common:
            w = float(weights.loc[ticker])
            p = float(prices.loc[ticker])
            if p <= 0 or w <= 0:
                continue
            position_value = float(capital * w)
            quantity = float(position_value / p)
            positions[str(ticker)] = {"quantity": quantity, "price": p, "weight": w}
        return positions

    def _save_daily_positions(self, trading_date: datetime, positions: Dict[str, Any]) -> None:
        date_str = trading_date.strftime("%Y-%m-%d")
        positions_file = self.positions_dir / f"positions_{date_str}.json"
        payload = {
            "date": date_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "positions": positions,
        }
        positions_file.write_text(json.dumps(payload, indent=2))

    def _save_daily_pnl(self, trading_date: datetime, pnl_data: Dict[str, Any]) -> None:
        date_str = trading_date.strftime("%Y-%m-%d")
        pnl_file = self.pnl_dir / f"pnl_{date_str}.json"
        payload = {"date": date_str, "timestamp": datetime.now(timezone.utc).isoformat(), **pnl_data}
        pnl_file.write_text(json.dumps(payload, indent=2))

    def _save_daily_decisions(self, trading_date: datetime, decisions: List[Dict[str, Any]]) -> None:
        date_str = trading_date.strftime("%Y-%m-%d")
        decisions_file = self.decisions_dir / f"decisions_{date_str}.json"
        payload = {"date": date_str, "timestamp": datetime.now(timezone.utc).isoformat(), "decisions": decisions}
        decisions_file.write_text(json.dumps(payload, indent=2))
