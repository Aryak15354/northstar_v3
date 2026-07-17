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
from typing import Dict, List, Any, Tuple, Optional

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from src.data.price_access import canonical_price_path, read_prices_legacy
from src.runtime import (
    DecisionMode,
    ExecutionEventType,
    PortfolioRuntimeService,
    ProposalOrigin,
    TradeProposal,
    build_certification_snapshot,
)
from src.runtime.contracts import ExecutionEvent
from src.runtime.hash_utils import canonical_hash, file_sha256
from src.live.shadow_reality_publisher import refresh_shadow_reality_from_live_artifacts


class DailyShadowTrader:
    """Daily shadow trading execution engine (real-data-only)."""

    def __init__(
        self,
        initial_capital: float = 10000000,
        data_directory: str = "data/live/shadow_trading",
        *,
        execution_mode: Optional[str] = None,
        prs_db_path: Optional[str] = None,
        prs_materialized_dir: Optional[str] = None,
    ):
        self.initial_capital = float(initial_capital)
        self.current_capital = float(initial_capital)
        self.data_dir = Path(data_directory)
        self.logger = logging.getLogger(__name__)

        self.project_root = project_root
        self.weights_path = self.project_root / "data/processed/portfolio_weights.parquet"
        self.prices_path = canonical_price_path(project_root=self.project_root)

        # Create data directories
        self.positions_dir = self.data_dir / "positions"
        self.pnl_dir = self.data_dir / "pnl"
        self.decisions_dir = self.data_dir / "decisions"
        self.targets_dir = self.data_dir / "targets"
        for directory in [self.positions_dir, self.pnl_dir, self.decisions_dir, self.targets_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.execution_mode = str(
            execution_mode or os.getenv("NORTHSTAR_DAILY_SHADOW_EXECUTION_MODE", "exact_target")
        ).strip().lower()
        if self.execution_mode not in {"exact_target", "budgeted"}:
            self.logger.warning(
                "Unknown shadow execution mode '%s'; defaulting to exact_target",
                self.execution_mode,
            )
            self.execution_mode = "exact_target"
        self.position_quantity_tolerance = self._env_float(
            "NORTHSTAR_SHADOW_POSITION_TOLERANCE",
            1e-6,
        )
        self.min_target_overlap = self._env_float(
            "NORTHSTAR_SHADOW_MIN_TARGET_OVERLAP",
            0.99,
        )
        self.max_total_weight_drift = self._env_float(
            "NORTHSTAR_SHADOW_MAX_TOTAL_WEIGHT_DRIFT",
            0.01,
        )
        self.max_symbol_weight_drift = self._env_float(
            "NORTHSTAR_SHADOW_MAX_SYMBOL_WEIGHT_DRIFT",
            0.0025,
        )
        self.max_extra_positions = self._env_int(
            "NORTHSTAR_SHADOW_MAX_EXTRA_POSITIONS",
            0,
        )
        self.max_missing_target_positions = self._env_int(
            "NORTHSTAR_SHADOW_MAX_MISSING_TARGET_POSITIONS",
            0,
        )
        self.fail_on_tracking_breach = self._env_bool(
            "NORTHSTAR_SHADOW_FAIL_ON_TRACKING_BREACH",
            True,
        )
        self.prs_db_path = Path(
            str(
                prs_db_path
                or os.getenv(
                    "NORTHSTAR_PRS_DAILY_SHADOW_DB",
                    "data/runtime/daily_shadow_runtime.db",
                )
                or "data/runtime/daily_shadow_runtime.db"
            )
        )
        self.prs_materialized_dir = Path(
            str(
                prs_materialized_dir
                or os.getenv(
                    "NORTHSTAR_PRS_DAILY_SHADOW_MATERIALIZED",
                    "data/processed/runtime/daily_shadow",
                )
                or "data/processed/runtime/daily_shadow"
            )
        )

        self.current_positions: Dict[str, Dict[str, float]] = {}
        self.performance_history: List[Dict[str, Any]] = []
        self.prs = None
        self.prs_context: Dict[str, str] = {}
        self.prs_cert_snapshot_hash = ""
        self._init_prs_runtime()

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return float(default)
        try:
            return float(raw)
        except Exception:
            return float(default)

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return int(default)
        try:
            return int(float(raw))
        except Exception:
            return int(default)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return bool(default)
        return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _init_prs_runtime(self) -> None:
        self.prs = PortfolioRuntimeService(
            db_path=str(self.prs_db_path),
            materialized_output_dir=str(self.prs_materialized_dir),
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
            "model_hash": canonical_hash(
                {"engine": "daily_shadow_trader", "version": "v2_exact_target"}
            ),
            "param_hash": canonical_hash(
                {
                    "initial_capital": float(self.initial_capital),
                    "execution_mode": str(self.execution_mode),
                    "min_target_overlap": float(self.min_target_overlap),
                    "max_total_weight_drift": float(self.max_total_weight_drift),
                    "max_symbol_weight_drift": float(self.max_symbol_weight_drift),
                    "max_extra_positions": int(self.max_extra_positions),
                    "max_missing_target_positions": int(self.max_missing_target_positions),
                }
            ),
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
            created_at=datetime.now(timezone.utc),
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

    def _snapshot_current_holdings(self) -> Dict[str, Dict[str, Any]]:
        if self.prs is None:
            return {}
        snap = self.prs.get_portfolio_state().to_dict()
        return {
            str(symbol): dict(payload or {})
            for symbol, payload in dict(snap.get("holdings", {}) or {}).items()
        }

    def _resolve_reference_price(
        self,
        ticker: str,
        target_positions: Dict[str, Dict[str, float]],
        prices_current: pd.Series,
        current_holdings: Dict[str, Dict[str, Any]],
    ) -> float:
        candidates = [
            prices_current.get(ticker),
            (target_positions.get(ticker, {}) or {}).get("price"),
            (current_holdings.get(ticker, {}) or {}).get("last_price"),
            (current_holdings.get(ticker, {}) or {}).get("avg_price"),
        ]
        for candidate in candidates:
            try:
                price = float(candidate or 0.0)
            except Exception:
                price = 0.0
            if price > 0.0:
                return price
        return 0.0

    def _route_positions_via_prs_budgeted(
        self,
        target_positions: Dict[str, Dict[str, float]],
        prices_current: pd.Series,
    ) -> int:
        if self.prs is None:
            return 0
        current_holdings = self._snapshot_current_holdings()
        current_qty = {str(k): float(v.get("quantity", 0.0) or 0.0) for k, v in current_holdings.items()}
        symbols = set(current_qty.keys()) | set(target_positions.keys())
        proposal_count = 0
        for ticker in sorted(symbols):
            target_qty = float((target_positions.get(ticker, {}) or {}).get("quantity", 0.0) or 0.0)
            cur_qty = float(current_qty.get(ticker, 0.0) or 0.0)
            delta_qty = target_qty - cur_qty
            if abs(delta_qty) < self.position_quantity_tolerance:
                continue
            price = self._resolve_reference_price(
                ticker,
                target_positions,
                prices_current,
                current_holdings,
            )
            if price <= 0.0:
                continue
            side = "buy" if delta_qty > 0.0 else "sell"
            qty = float(abs(delta_qty))
            notional = float(qty * price)
            lifecycle_action = "close" if target_qty == 0.0 else "open"
            now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
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

    def _reconcile_positions_exact(
        self,
        target_positions: Dict[str, Dict[str, float]],
        prices_current: pd.Series,
    ) -> Tuple[int, List[str]]:
        if self.prs is None:
            return 0, []

        current_holdings = self._snapshot_current_holdings()
        current_qty = {
            str(symbol): float((payload or {}).get("quantity", 0.0) or 0.0)
            for symbol, payload in current_holdings.items()
        }
        symbols = set(current_qty.keys()) | set(target_positions.keys())
        adjustments = 0
        unresolved_symbols: List[str] = []

        for ticker in sorted(symbols):
            target_payload = dict(target_positions.get(ticker, {}) or {})
            current_payload = dict(current_holdings.get(ticker, {}) or {})
            target_qty = float(target_payload.get("quantity", 0.0) or 0.0)
            cur_qty = float(current_qty.get(ticker, 0.0) or 0.0)
            delta_qty = target_qty - cur_qty
            if abs(delta_qty) <= self.position_quantity_tolerance:
                continue

            price = self._resolve_reference_price(
                ticker,
                target_positions,
                prices_current,
                current_holdings,
            )
            if price <= 0.0:
                unresolved_symbols.append(str(ticker))
                continue

            side = "buy" if delta_qty > 0.0 else "sell"
            now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            notional = float(abs(delta_qty) * price)
            payload = {
                "symbol": str(ticker).upper(),
                "side": side,
                "filled_qty": float(abs(delta_qty)),
                "fill_price": float(price),
                "price": float(price),
                "quantity": float(abs(delta_qty)),
                "fill_notional": notional,
                "approved_budget_notional": notional,
                "instrument_type": str(
                    current_payload.get("instrument_type")
                    or target_payload.get("instrument_type")
                    or "equity"
                ).lower(),
                "lifecycle_action": "close" if abs(target_qty) <= self.position_quantity_tolerance else "rebalance",
                "position_key": f"daily_shadow:{str(ticker).upper()}",
                "strategy_id": "daily_shadow_trader",
                "origin": ProposalOrigin.SHADOW.value,
            }
            event = ExecutionEvent(
                event_type=ExecutionEventType.POSITION_ADJUSTED,
                proposal_id=f"shadow_exact::{ticker}::{now_str}",
                sequence_no=0,
                timestamp_utc=datetime.now(timezone.utc),
                trigger_reason_code="rebalance.shadow.daily.exact_target",
                strategy_id="daily_shadow_trader",
                signal_id=f"shadow_exact::{ticker}::{now_str}",
                certification_snapshot_hash=str(self.prs_cert_snapshot_hash or "na"),
                risk_override_flag=False,
                decision_mode=DecisionMode.AUTO,
                origin=ProposalOrigin.SHADOW,
                allocator_decision_id="shadow_exact",
                budget_decision_id="shadow_exact",
                liquidity_decision_id="shadow_exact",
                operator_id="daily_shadow_trader",
                runtime_scope="shadow",
                payload=payload,
            )
            # Exact-target shadow reconciliation is a canonical state adjustment, not a
            # live order lifecycle. Seed the FSM into a post-reconciliation state so
            # the adjustment is recorded in PRS without running through live gates.
            self.prs.fsm.force_set(event.proposal_id, ExecutionEventType.RECONCILIATION_APPLIED.value)
            self.prs.ingest_execution_event(event, risk_snapshot=None)
            adjustments += 1

        if not prices_current.empty:
            self.prs.mark_to_market(
                {str(symbol): float(price) for symbol, price in prices_current.items()},
                timestamp_utc=datetime.now(timezone.utc),
                source="daily_shadow_exact_target",
                runtime_scope="shadow",
            )

        return adjustments, unresolved_symbols

    @staticmethod
    def _position_notional(payload: Dict[str, Any]) -> float:
        quantity = float((payload or {}).get("quantity", 0.0) or 0.0)
        market_value = float((payload or {}).get("market_value", 0.0) or 0.0)
        if market_value > 0.0:
            return market_value
        price = float((payload or {}).get("price", 0.0) or 0.0)
        return abs(quantity * price)

    def _compute_tracking_summary(
        self,
        target_positions: Dict[str, Dict[str, float]],
        actual_positions: Dict[str, Dict[str, float]],
        *,
        unresolved_symbols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        unresolved = sorted({str(symbol) for symbol in (unresolved_symbols or []) if str(symbol).strip()})
        target_symbols = {
            str(symbol)
            for symbol, payload in dict(target_positions or {}).items()
            if self._position_notional(dict(payload or {})) > self.position_quantity_tolerance
        }
        actual_symbols = {
            str(symbol)
            for symbol, payload in dict(actual_positions or {}).items()
            if self._position_notional(dict(payload or {})) > self.position_quantity_tolerance
        }
        union = target_symbols | actual_symbols
        intersection = target_symbols & actual_symbols
        target_overlap = float(len(intersection) / len(union)) if union else 1.0

        def _weight_map(positions: Dict[str, Dict[str, float]]) -> Dict[str, float]:
            notionals = {
                str(symbol): self._position_notional(dict(payload or {}))
                for symbol, payload in dict(positions or {}).items()
            }
            total = float(sum(value for value in notionals.values() if value > self.position_quantity_tolerance))
            if total <= self.position_quantity_tolerance:
                return {}
            return {
                symbol: float(value / total)
                for symbol, value in notionals.items()
                if value > self.position_quantity_tolerance
            }

        target_weights = _weight_map(target_positions)
        actual_weights = _weight_map(actual_positions)
        weight_diffs = {
            symbol: abs(float(actual_weights.get(symbol, 0.0)) - float(target_weights.get(symbol, 0.0)))
            for symbol in union
        }
        total_weight_drift = float(sum(weight_diffs.values()) / 2.0)
        max_symbol_weight_drift = float(max(weight_diffs.values()) if weight_diffs else 0.0)

        quantity_mismatch_count = 0
        for symbol in union:
            target_qty = float((target_positions.get(symbol, {}) or {}).get("quantity", 0.0) or 0.0)
            actual_qty = float((actual_positions.get(symbol, {}) or {}).get("quantity", 0.0) or 0.0)
            if abs(target_qty - actual_qty) > self.position_quantity_tolerance:
                quantity_mismatch_count += 1

        extra_positions_count = len(actual_symbols - target_symbols)
        missing_target_positions_count = len(target_symbols - actual_symbols)

        breach_reasons: List[str] = []
        if target_overlap < self.min_target_overlap:
            breach_reasons.append(
                f"target_overlap={target_overlap:.4f} below floor {self.min_target_overlap:.4f}"
            )
        if total_weight_drift > self.max_total_weight_drift:
            breach_reasons.append(
                f"total_weight_drift={total_weight_drift:.6f} above limit {self.max_total_weight_drift:.6f}"
            )
        if max_symbol_weight_drift > self.max_symbol_weight_drift:
            breach_reasons.append(
                f"max_symbol_weight_drift={max_symbol_weight_drift:.6f} above limit {self.max_symbol_weight_drift:.6f}"
            )
        if extra_positions_count > self.max_extra_positions:
            breach_reasons.append(
                f"extra_positions={extra_positions_count} above limit {self.max_extra_positions}"
            )
        if missing_target_positions_count > self.max_missing_target_positions:
            breach_reasons.append(
                f"missing_target_positions={missing_target_positions_count} above limit {self.max_missing_target_positions}"
            )
        if quantity_mismatch_count > 0:
            breach_reasons.append(f"quantity_mismatch_count={quantity_mismatch_count}")
        if unresolved:
            breach_reasons.append(f"unresolved_prices={','.join(unresolved)}")

        exact_target_match = bool(
            not unresolved
            and quantity_mismatch_count == 0
            and extra_positions_count == 0
            and missing_target_positions_count == 0
        )
        breach = bool(breach_reasons)
        return {
            "execution_mode": str(self.execution_mode),
            "status": "breach" if breach else "pass",
            "breach": breach,
            "reasons": breach_reasons,
            "target_position_overlap": float(target_overlap),
            "total_weight_drift": float(total_weight_drift),
            "max_symbol_weight_drift": float(max_symbol_weight_drift),
            "extra_positions_count": int(extra_positions_count),
            "missing_target_positions_count": int(missing_target_positions_count),
            "quantity_mismatch_count": int(quantity_mismatch_count),
            "exact_target_match": bool(exact_target_match),
            "unresolved_symbols": unresolved,
            "limits": {
                "min_target_overlap": float(self.min_target_overlap),
                "max_total_weight_drift": float(self.max_total_weight_drift),
                "max_symbol_weight_drift": float(self.max_symbol_weight_drift),
                "max_extra_positions": int(self.max_extra_positions),
                "max_missing_target_positions": int(self.max_missing_target_positions),
                "position_quantity_tolerance": float(self.position_quantity_tolerance),
            },
        }

    def _route_positions_via_prs(
        self,
        target_positions: Dict[str, Dict[str, float]],
        prices_current: pd.Series,
    ) -> Tuple[int, List[str]]:
        if self.execution_mode == "exact_target":
            return self._reconcile_positions_exact(target_positions, prices_current)
        return self._route_positions_via_prs_budgeted(target_positions, prices_current), []

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
            proposals_executed, unresolved_symbols = self._route_positions_via_prs(positions_target, prices_current)
            positions = self._sync_positions_from_prs(prices_current)
            snap = self.prs.get_portfolio_state().to_dict()
            cash_value = float(snap.get("cash", 0.0) or 0.0)
            total_position_value = float(sum(p["quantity"] * p["price"] for p in positions.values()))
            portfolio_value = float(cash_value + total_position_value)
            daily_pnl = float(portfolio_value - prior_capital)
            daily_return = float(daily_pnl / prior_capital) if prior_capital > 0 else 0.0
            self.current_capital = portfolio_value
            tracking_summary = self._compute_tracking_summary(
                positions_target,
                positions,
                unresolved_symbols=unresolved_symbols,
            )

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
                "shadow_execution_mode": str(self.execution_mode),
                "tracking_summary": tracking_summary,
                "target_position_overlap": float(tracking_summary["target_position_overlap"]),
                "target_total_weight_drift": float(tracking_summary["total_weight_drift"]),
                "target_max_weight_drift": float(tracking_summary["max_symbol_weight_drift"]),
                "target_extra_positions_count": int(tracking_summary["extra_positions_count"]),
                "target_missing_positions_count": int(tracking_summary["missing_target_positions_count"]),
                "target_quantity_mismatch_count": int(tracking_summary["quantity_mismatch_count"]),
                "tracking_limit_breach": bool(tracking_summary["breach"]),
                "exact_target_match": bool(tracking_summary["exact_target_match"]),
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
                    "execution_mode": str(self.execution_mode),
                },
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "shadow_tracking_summary",
                    **tracking_summary,
                }
            ]

            self._save_daily_positions(trading_date, positions)
            self._save_daily_pnl(trading_date, pnl_data)
            self._save_daily_decisions(trading_date, decisions)
            self._save_daily_targets(trading_date, aligned_weights, positions_target, weights_date)
            self._publish_canonical_shadow_reality(trading_date)

            result = {
                "status": "success",
                "date": date_str,
                "daily_return": daily_return,
                "positions": positions,
                "pnl_data": pnl_data,
                "decisions": decisions,
            }
            self.performance_history.append(result)
            if bool(tracking_summary["breach"]) and self.fail_on_tracking_breach:
                raise RuntimeError(
                    "Shadow target convergence breach: " + "; ".join(tracking_summary["reasons"])
                )
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

        px = read_prices_legacy(
            project_root=self.project_root,
            columns=["Date", "ticker", "Close"],
        )
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

    def _save_daily_targets(
        self,
        trading_date: datetime,
        aligned_weights: pd.Series,
        positions_target: Dict[str, Dict[str, float]],
        weights_date: pd.Timestamp,
    ) -> None:
        date_str = trading_date.strftime("%Y-%m-%d")
        targets_file = self.targets_dir / f"targets_{date_str}.json"
        target_positions = {}
        for ticker, payload in sorted(dict(positions_target or {}).items()):
            payload = dict(payload or {})
            quantity = float(payload.get("quantity", 0.0) or 0.0)
            price = float(payload.get("price", 0.0) or 0.0)
            if quantity <= self.position_quantity_tolerance or price <= 0.0:
                continue
            weight = float(payload.get("weight", aligned_weights.get(ticker, 0.0)) or 0.0)
            target_positions[str(ticker)] = {
                "weight": float(weight),
                "quantity": quantity,
                "price": price,
                "notional": float(quantity * price),
            }
        payload = {
            "date": date_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "weights_date": weights_date.strftime("%Y-%m-%d"),
            "raw_weight_count": int(len(aligned_weights)),
            "eligible_target_count": int(len(target_positions)),
            "excluded_due_to_price_or_size_count": int(max(len(aligned_weights) - len(target_positions), 0)),
            "target_positions": target_positions,
        }
        targets_file.write_text(json.dumps(payload, indent=2))

    def _publish_canonical_shadow_reality(self, trading_date: datetime) -> None:
        date_str = trading_date.strftime("%Y-%m-%d")
        try:
            result = refresh_shadow_reality_from_live_artifacts(
                live_data_directory=str(self.data_dir),
                target_date=date_str,
            )
            if not result.success:
                self.logger.warning(
                    "Shadow reality publish skipped for %s: %s",
                    date_str,
                    result.reason,
                )
                return
            self.logger.info(
                "Published canonical shadow reality for %s (refreshed_dates=%s)",
                date_str,
                result.refreshed_dates,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed to publish canonical shadow reality for %s: %s",
                date_str,
                exc,
            )
