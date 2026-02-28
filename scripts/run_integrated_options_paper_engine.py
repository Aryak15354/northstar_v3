#!/usr/bin/env python3
"""
Integrated Options Paper Engine (V3-aligned)

Runs options signal -> validation -> paper execution in one loop and persists
dashboard-ready artifacts so V3 dashboard panels keep updating continuously.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.options.capital_scaling_engine import CapitalScalingEngine, ScalingState
from src.options.config_loader import get_config
from src.options.position_manager import Position, PositionLeg, PositionManager
from src.options.regime_detector import Regime, RegimeState, RegimeDetector
from src.options.stock_options_loader import get_stock_loader
from src.options.enhanced_strategy_generator_v3 import EnhancedStrategyGeneratorV3
from src.options.strategy_generator import Greeks, OptionStrategy
from src.options.survival_rules_engine import (
    PerformanceMetrics,
    Position as SurvivalPosition,
    SurvivalRulesEngine,
    Trade as SurvivalTrade,
)
from src.options.state_io import StateIOManager
from src.options.state_recovery import StateRecoveryManager
from src.options.accounting_integrity import AccountingIntegrityChecker
from src.options.tax_aware_pnl_tracker import TaxAwarePnLTracker
from src.options.trade_eligibility_validator import TradeEligibilityValidator
from src.options.trade_ledger import TradeLedger
from src.options.upstox_adapter import UpstoxAdapter
from src.options.v3_event_integration import create_event_publisher
from src.integration.alpha_os_adapter import AlphaOSAdapter
from src.sentiment.context_loader import load_sentiment_context as load_canonical_sentiment_context
from src.volatility.regime_detector import VolatilityRegime
from src.volatility.alpha_os_types import AlphaOSContext


IST = pytz.timezone("Asia/Kolkata")
AGGRESSIVE_DEFAULT_PORTFOLIO_RISK_CAP_PCT = 0.10
PORTFOLIO_OVERLAY_DEFAULT_MAX_STOCKS = 6
PORTFOLIO_OVERLAY_DEFAULT_MAX_DYNAMIC_UNDERLYINGS = 18
INDEX_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
UNBOUNDED_WEEKLY_TRADES = 1_000_000
DEFAULT_LOOP_INTERVAL_SECONDS = 300.0
SHORT_VOL_STRATEGY_TYPES = {
    "iron_condor",
    "iron_butterfly",
    "short_strangle",
    "calendar_spread",
}
HEDGE_OBJECTIVES = {
    "event_shock_hedge",
    "hedge_convexity",
    "protect_core",
    "defensive_convexity",
}
NET_PROFIT_OVERRIDE_OBJECTIVES = {"event_shock_hedge"}
MIN_NET_EXPECTANCY_INR = 1.0
HEDGE_PRIORITY_MIN_INTENSITY = 0.42
HEDGE_PRIORITY_HIGH_INTENSITY = 0.60
HEDGE_PRIORITY_ALERT_LEVELS = {"high", "critical"}
HEDGE_PREFERRED_STRATEGY_TYPES = {
    "long_strangle",
    "long_straddle",
    "bear_put_spread",
    "calendar_spread",
}
SENTIMENT_TOP_COMPANIES_LIMIT = 100
POSITIVE_SENTIMENT_LABELS = {"positive", "very_positive", "bullish"}
NEGATIVE_SENTIMENT_LABELS = {"negative", "very_negative", "bearish", "downside"}
STRATEGY_CONCENTRATION_LOOKBACK = 80
STRATEGY_CONCENTRATION_TARGET = 0.34
MAX_STRATEGY_CONCENTRATION_PENALTY = 0.70
EXPIRY_WEEKDAY_BY_UNDERLYING: Dict[str, int] = {
    # 0=Mon ... 6=Sun
    "MIDCPNIFTY": 0,
    "NIFTY": 1,
    "FINNIFTY": 1,
    "BANKNIFTY": 2,
}
DEFAULT_FALLBACK_EXPIRY_WEEKDAY = 3
SECTOR_INDEX_MAP: Dict[str, List[str]] = {
    "financial services": ["BANKNIFTY", "FINNIFTY"],
    "information technology": ["NIFTYIT"],
    "automobile and auto components": ["NIFTYAUTO"],
    "healthcare": ["NIFTYPHARMA"],
    "metals & mining": ["NIFTYMETAL"],
    "fast moving consumer goods": ["NIFTYFMCG"],
    "oil gas & consumable fuels": ["NIFTYENERGY"],
    "energy": ["NIFTYENERGY"],
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/options_integrated_engine.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("options.integrated_engine")


def _now_ist() -> datetime:
    return datetime.now(IST)


def _to_iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def _parse_dt(v: Optional[str]) -> Optional[datetime]:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is not None:
            return dt.astimezone(pytz.UTC).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _to_regime(value: str) -> VolatilityRegime:
    raw = str(value or "").strip().lower()
    mapping = {
        "low_vol": VolatilityRegime.LOW_VOL,
        "low_vol_sell": VolatilityRegime.LOW_VOL,
        "high_vol": VolatilityRegime.HIGH_VOL,
        "high_vol_sell": VolatilityRegime.HIGH_VOL,
        "crisis": VolatilityRegime.CRISIS,
        "crash_hedge": VolatilityRegime.CRISIS,
        "transition": VolatilityRegime.TRANSITION,
        "rising_vol_buy": VolatilityRegime.TRANSITION,
        "neutral": VolatilityRegime.TRANSITION,
    }
    return mapping.get(raw, VolatilityRegime.TRANSITION)


def _sentiment_sign(sentiment_label: str, sentiment_score: float) -> int:
    label = str(sentiment_label or "").strip().lower()
    if label in POSITIVE_SENTIMENT_LABELS:
        return 1
    if label in NEGATIVE_SENTIMENT_LABELS:
        return -1
    if sentiment_score >= 0.08:
        return 1
    if sentiment_score <= -0.08:
        return -1
    return 0


class IntegratedOptionsPaperEngine:
    def __init__(
        self,
        underlyings: List[str],
        aggressive: bool = True,
        market_hours_only: bool = False,
        max_trades_per_week: Optional[int] = None,
        portfolio_risk_cap_pct: Optional[float] = None,
        no_max_trades_limit: bool = False,
        portfolio_overlay: bool = True,
        portfolio_overlay_max_stocks: int = PORTFOLIO_OVERLAY_DEFAULT_MAX_STOCKS,
        reset_state: bool = False,
        start_fresh_today: bool = False,
        recovery_mode: bool = False,
    ):
        load_dotenv(".env.options", override=True)

        self.config = get_config()
        self.stock_loader = get_stock_loader()
        self.stock_key_reverse_map = {
            str(info.instrument_key).strip().upper(): str(symbol).strip().upper()
            for symbol, info in getattr(self.stock_loader, "stocks", {}).items()
        }
        generic_tokens = {"NSE", "NSE_EQ", "NSE_FO", "NFO", "BSE", "BSE_EQ", "BSE_FO", "NSE_INDEX"}

        def _sanitize_cli_underlying(raw: str) -> str:
            sym = str(raw or "").strip().upper()
            if sym in self.stock_key_reverse_map:
                sym = self.stock_key_reverse_map[sym]
            if "|" in sym:
                if sym in self.stock_key_reverse_map:
                    sym = self.stock_key_reverse_map[sym]
                else:
                    sym = sym.split("|", 1)[1].strip().upper()
            if ":" in sym:
                if sym in self.stock_key_reverse_map:
                    sym = self.stock_key_reverse_map[sym]
                else:
                    sym = sym.split(":", 1)[1].strip().upper()
            if sym.endswith(".NS"):
                sym = sym[:-3]
            alias_map = {
                "NIFTY 50": "NIFTY",
                "NIFTY BANK": "BANKNIFTY",
                "NIFTY FIN SERVICE": "FINNIFTY",
            }
            sym = alias_map.get(sym, sym)
            if not sym or sym in generic_tokens or sym.isdigit():
                return ""
            return sym.replace(" ", "")

        # Handle "ALL" keyword to load all available stocks + indices
        raw_underlyings = [_sanitize_cli_underlying(u) for u in underlyings if str(u).strip()]
        raw_underlyings = [u for u in raw_underlyings if u]
        if "ALL" in raw_underlyings:
            # Load all indices
            all_indices = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYAUTO", 
                          "NIFTYPHARMA", "NIFTYFMCG", "NIFTYMETAL", "NIFTYENERGY", "NIFTYREALTY"]
            # Load all stocks from stock_options_mapping.yaml
            all_stocks = self.stock_loader.get_all_symbols()
            self.underlyings = all_indices + all_stocks
            logger.info(f"Using ALL: {len(all_indices)} indices + {len(all_stocks)} stocks = {len(self.underlyings)} total")
        else:
            self.underlyings = raw_underlyings
        
        self.aggressive = bool(aggressive)
        self.market_hours_only = bool(market_hours_only)
        self.portfolio_overlay_enabled = bool(portfolio_overlay)
        self.portfolio_overlay_max_stocks = max(0, int(portfolio_overlay_max_stocks))
        self.reset_state_requested = bool(reset_state)
        self.start_fresh_today = bool(start_fresh_today)
        self.recovery_mode = bool(recovery_mode)
        self.no_max_trades_limit = bool(no_max_trades_limit)
        self.limit_profile: Dict[str, Any] = {}
        self.portfolio_overlay: Dict[str, Any] = {}
        self.latest_cycle_diagnostics: Dict[str, Any] = {}
        self.cycle_decision_history: List[Dict[str, Any]] = []
        self._apply_limit_overrides(
            max_trades_per_week=max_trades_per_week,
            portfolio_risk_cap_pct=portfolio_risk_cap_pct,
            no_max_trades_limit=self.no_max_trades_limit,
        )

        self.upstox = UpstoxAdapter(self.config.upstox)
        self.instrument_key_reverse_map = {
            str(v).strip().upper(): str(k).strip().upper()
            for k, v in getattr(self.upstox, "instrument_key_map", {}).items()
        }
        self.regime_detector = RegimeDetector(self.config.regime_detection)
        self.strategy_generator = EnhancedStrategyGeneratorV3(self.config.strategies)
        self.eligibility_validator = TradeEligibilityValidator(self.config)
        self.capital_scaling = CapitalScalingEngine(self.config)
        self.survival_rules = SurvivalRulesEngine(
            self.config.survival_rules,
            self.config.capital.base_capital
        )
        self.position_manager = PositionManager(
            self.config.exit_rules,
            self.config.greek_safety_bands
        )
        self.pnl_tracker = TaxAwarePnLTracker(self.config.costs, self.config.tax)
        self.trade_ledger = TradeLedger(self.config.data_paths.trade_ledger)
        self.event_publisher = create_event_publisher()

        self.snapshot_dir = PROJECT_ROOT / "snapshots"
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        self.options_live_dir = PROJECT_ROOT / "data/options/live"
        self.options_live_dir.mkdir(parents=True, exist_ok=True)
        self.chains_cache_keep_per_underlying = max(
            2,
            int(os.getenv("OPTIONS_CHAIN_CACHE_KEEP_PER_UNDERLYING", "4") or 4),
        )

        self.runtime_state_path = self.options_live_dir / "options_runtime_state.json"
        self.dashboard_state_path = self.options_live_dir / "options_dashboard_state.json"
        self.heartbeat_path = self.options_live_dir / "live_engine_heartbeat.json"
        self.eod_snapshots_dir = self.options_live_dir / "eod_snapshots"
        self.recovery_mode_report_path = self.options_live_dir / "recovery_mode_report.json"
        self.state_io = StateIOManager(self.options_live_dir)
        self.state_recovery = StateRecoveryManager(self.options_live_dir)
        self.accounting_integrity = AccountingIntegrityChecker()
        self.interrupted_operations: List[Dict[str, Any]] = self.state_io.check_interrupted_operations()
        self.recovery_required = bool(self.interrupted_operations)
        integrity_report = self.state_recovery.check_state_integrity()
        if integrity_report.get("overall_status") == "corrupted":
            logger.warning("Detected corrupted state at startup; forcing reconciliation")
            self.recovery_required = True
        self.week_start_equity: Optional[float] = None
        self.week_anchor_date: Optional[date] = None
        self.last_reconciled_at: Optional[str] = None

        self.iv_history: Dict[str, List[Dict[str, Any]]] = {}
        self.regime_history: List[Dict[str, Any]] = []
        self.greeks_history: List[Dict[str, Any]] = []
        self.last_trade_eligibility: Dict[str, Any] = {
            "signal_generated": False,
            "rejected": False,
            "violations": [],
            "timestamp": _to_iso(_now_ist()),
        }
        self.last_eligibility_checks: List[Dict[str, Any]] = []
        self.last_kill_switch: Dict[str, Any] = {"active": False}
        self.cumulative_net_pnl = 0.0
        self.scaling_state: Optional[ScalingState] = None
        self.alpha_os_enabled = bool(getattr(self.config.alpha_os, "enabled", False))
        self.alpha_os_shadow_mode = bool(getattr(self.config.alpha_os, "shadow_mode", False))
        self.alpha_os_enforce_mode = bool(getattr(self.config.alpha_os, "enforce_mode", False))
        self.alpha_os_last_intent: Dict[str, Any] = {}
        self.alpha_os_adapter: Optional[AlphaOSAdapter] = None
        if self.alpha_os_enabled:
            try:
                self.alpha_os_adapter = AlphaOSAdapter(
                    project_root=PROJECT_ROOT,
                    config=self.config.alpha_os,
                )
                logger.info(
                    "AlphaOS adapter initialized (shadow=%s enforce=%s)",
                    self.alpha_os_shadow_mode,
                    self.alpha_os_enforce_mode,
                )
            except Exception as e:
                logger.error(f"AlphaOS adapter initialization failed: {e}")
                self.alpha_os_enabled = False

        if self.interrupted_operations:
            logger.warning(
                "Detected %d interrupted WAL operations; forcing reconciliation",
                len(self.interrupted_operations),
            )
            recovery_actions = self.state_recovery.handle_interrupted_operations(self.interrupted_operations)
            logger.warning("WAL interrupted recovery actions: %s", recovery_actions)

        if self.recovery_mode or self.recovery_required:
            report = self.state_recovery.rebuild_from_ledger(
                recovery_mode=self.recovery_mode,
                base_capital=float(self.config.capital.base_capital),
                portfolio_risk_cap_pct=float(self.config.survival_rules.portfolio_risk_cap_pct),
            )
            self._write_json_atomic(self.recovery_mode_report_path, report)
            if report.get("status") != "completed":
                logger.error("Ledger recovery failed: %s", report)
            if self.interrupted_operations:
                self.state_io.resolve_interrupted_operations(
                    self.interrupted_operations,
                    reason="reconciled_on_engine_startup",
                )

        self._load_runtime_state()
        if self.reset_state_requested:
            self._reset_trade_and_runtime_state()
        elif self.start_fresh_today:
            self._enforce_today_start()

        if self.scaling_state is None:
            self.scaling_state = self.capital_scaling.initialize_state(
                starting_capital=self.config.capital.base_capital,
                trading_start_date=datetime.utcnow(),
            )

    @staticmethod
    def _resolve_project_path(path: Path) -> Path:
        return path if path.is_absolute() else (PROJECT_ROOT / path)

    @staticmethod
    def _to_ist_date(value: Any) -> Optional[date]:
        ts = pd.to_datetime(value, errors="coerce")
        if ts is None or pd.isna(ts):
            return None
        if isinstance(ts, pd.Timestamp):
            if ts.tzinfo is None:
                ts = ts.tz_localize(pytz.UTC)
            return ts.tz_convert(IST).date()
        return None

    def _enforce_today_start(self) -> None:
        """
        Enforce clean trading state from today's IST session.

        If persisted runtime/ledger artifacts contain pre-today entries, archive
        and reset so live trading metrics start from the current day only.
        """
        today_ist = _now_ist().date()
        reasons: List[str] = []

        runtime_state = self._read_json_file(self.runtime_state_path)
        runtime_day = self._to_ist_date(runtime_state.get("timestamp"))
        if runtime_day and runtime_day < today_ist:
            reasons.append(f"runtime_state_day={runtime_day.isoformat()}")

        for p in self.position_manager.get_open_positions():
            entry_day = self._to_ist_date(p.entry_time)
            if entry_day and entry_day < today_ist:
                reasons.append(f"open_position_before_today={p.position_id}")
                break
        for p in self.position_manager.get_closed_positions():
            entry_day = self._to_ist_date(p.entry_time)
            if entry_day and entry_day < today_ist:
                reasons.append(f"closed_position_before_today={p.position_id}")
                break

        try:
            ledger_df = self.trade_ledger.read_all()
            if isinstance(ledger_df, pd.DataFrame) and not ledger_df.empty and "timestamp" in ledger_df.columns:
                ts = pd.to_datetime(ledger_df["timestamp"], errors="coerce", utc=True)
                ledger_days = ts.dt.tz_convert(IST).dt.date
                if (ledger_days < today_ist).any():
                    reasons.append("ledger_contains_pre_today_entries")
        except Exception as e:
            logger.warning(f"Could not inspect trade ledger for today-start check: {e}")

        if reasons:
            logger.info(
                "start_fresh_today enabled; resetting pre-today state (%s)",
                ", ".join(reasons),
            )
            self._reset_trade_and_runtime_state()
            return

        if self.scaling_state is not None:
            scaling_day = self._to_ist_date(self.scaling_state.trading_start_date)
            if scaling_day is None or scaling_day < today_ist:
                self.scaling_state = self.capital_scaling.initialize_state(
                    starting_capital=self.config.capital.base_capital,
                    trading_start_date=datetime.utcnow(),
                )
                logger.info("Aligned scaling_state.trading_start_date to today's session")
                self._save_runtime_state()

    def _archive_for_reset(self, path: Path, archive_dir: Path) -> None:
        src = self._resolve_project_path(path)
        if not src.exists():
            return
        archive_dir.mkdir(parents=True, exist_ok=True)
        target = archive_dir / src.name
        suffix = 1
        while target.exists():
            target = archive_dir / f"{src.stem}_{suffix}{src.suffix}"
            suffix += 1
        try:
            src.replace(target)
            logger.info(f"Archived pre-reset artifact: {src} -> {target}")
        except Exception as e:
            logger.warning(f"Failed to archive {src}: {e}")

    def _reset_trade_and_runtime_state(self) -> None:
        """Reset prior paper-trade state and bootstrap clean runtime files."""
        now = _now_ist()
        stamp = now.strftime("%Y%m%d_%H%M%S")
        archive_dir = PROJECT_ROOT / "data/options/live/reset_archive" / stamp

        ledger_path = self._resolve_project_path(self.trade_ledger.ledger_path)
        position_snapshots_path = self._resolve_project_path(Path(self.config.data_paths.position_snapshots))
        regime_history_path = self._resolve_project_path(Path(self.config.data_paths.regime_history))
        iv_history_path = self._resolve_project_path(Path(self.config.data_paths.iv_history))

        for path in (
            self.runtime_state_path,
            self.dashboard_state_path,
            ledger_path,
            position_snapshots_path,
            regime_history_path,
            iv_history_path,
        ):
            self._archive_for_reset(path, archive_dir=archive_dir)

        # Clear in-memory trade/runtime state.
        self.position_manager.open_positions.clear()
        self.position_manager.closed_positions.clear()
        self.iv_history = {}
        self.regime_history = []
        self.greeks_history = []
        self.portfolio_overlay = {}
        self.latest_cycle_diagnostics = {}
        self.cycle_decision_history = []
        self.alpha_os_last_intent = {}
        self.cumulative_net_pnl = 0.0
        self.week_start_equity = float(self.config.capital.base_capital)
        self.week_anchor_date = now.date()
        self.last_reconciled_at = _to_iso(now)
        self.last_trade_eligibility = {
            "signal_generated": False,
            "rejected": False,
            "violations": [],
            "timestamp": _to_iso(now),
        }
        self.last_eligibility_checks = []
        self.last_kill_switch = {"active": False}
        self.pnl_tracker.reset_ytd()
        self.scaling_state = self.capital_scaling.initialize_state(
            starting_capital=self.config.capital.base_capital,
            trading_start_date=datetime.utcnow(),
        )

        # Recreate empty immutable trade ledger.
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.trade_ledger.ledger_path = ledger_path
        if hasattr(self.trade_ledger, "_initialize_empty_ledger"):
            self.trade_ledger._initialize_empty_ledger()
        else:
            self.trade_ledger = TradeLedger(str(ledger_path))

        self._save_runtime_state()
        dashboard_state = self._build_dashboard_state(now, chain_cache={})
        self._write_json_atomic(self.dashboard_state_path, dashboard_state)
        logger.info(
            f"Options paper state reset complete. Archived artifacts under: {archive_dir}"
        )

    def _apply_limit_overrides(
        self,
        max_trades_per_week: Optional[int],
        portfolio_risk_cap_pct: Optional[float],
        no_max_trades_limit: bool = False,
    ) -> None:
        """Apply optional limit overrides; aggressive mode gets higher defaults."""
        source = {
            "max_trades_per_week": "config",
            "portfolio_risk_cap_pct": "config",
        }
        had_weekly_override = max_trades_per_week is not None
        force_aggressive_weekly_cap = str(
            os.getenv("OPTIONS_ALLOW_AGGRESSIVE_WEEKLY_CAP", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}

        if no_max_trades_limit:
            max_trades_per_week = UNBOUNDED_WEEKLY_TRADES
            source["max_trades_per_week"] = "cli_unbounded"
        elif self.aggressive and not force_aggressive_weekly_cap:
            # Protect aggressive mode from accidental low weekly caps in launch scripts.
            max_trades_per_week = UNBOUNDED_WEEKLY_TRADES
            source["max_trades_per_week"] = (
                "aggressive_unbounded_forced"
                if had_weekly_override
                else "aggressive_unbounded_default"
            )
        elif max_trades_per_week is not None:
            source["max_trades_per_week"] = "cli_override"

        if self.aggressive and portfolio_risk_cap_pct is None:
            portfolio_risk_cap_pct = AGGRESSIVE_DEFAULT_PORTFOLIO_RISK_CAP_PCT
            source["portfolio_risk_cap_pct"] = "aggressive_default"
        elif portfolio_risk_cap_pct is not None:
            source["portfolio_risk_cap_pct"] = "cli_override"

        if max_trades_per_week is not None:
            try:
                parsed_limit = int(max_trades_per_week)
                if parsed_limit <= 0:
                    parsed_limit = UNBOUNDED_WEEKLY_TRADES
                    source["max_trades_per_week"] = "cli_unbounded"
                self.config.survival_rules.max_trades_per_week = max(1, parsed_limit)
            except Exception:
                logger.warning(f"Ignoring invalid max_trades_per_week override: {max_trades_per_week}")

        if portfolio_risk_cap_pct is not None:
            try:
                risk_cap = float(portfolio_risk_cap_pct)
                if risk_cap <= 0:
                    raise ValueError("must be > 0")
                self.config.survival_rules.portfolio_risk_cap_pct = min(1.0, risk_cap)
            except Exception:
                logger.warning(f"Ignoring invalid portfolio_risk_cap_pct override: {portfolio_risk_cap_pct}")

        self.limit_profile = {
            "aggressive_mode": self.aggressive,
            "no_max_trades_limit": bool(self.config.survival_rules.max_trades_per_week >= UNBOUNDED_WEEKLY_TRADES),
            "max_trades_per_week": int(self.config.survival_rules.max_trades_per_week),
            "portfolio_risk_cap_pct": float(self.config.survival_rules.portfolio_risk_cap_pct),
            "source": source,
        }

    @staticmethod
    def _read_json_file(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write_json_atomic(self, path: Path, payload: Dict[str, Any]) -> None:
        if not self.state_io.writer.write_json(path, payload):
            # Fallback write path if WAL-backed writer fails.
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(f"{path.suffix}.tmp")
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, default=str)
            tmp_path.replace(path)

    def _current_unrealized_pnl(self) -> float:
        return float(
            sum(
                float(getattr(p, "unrealized_pnl", 0.0) or 0.0)
                for p in self.position_manager.get_open_positions()
            )
        )

    def _current_net_equity(self) -> float:
        return float(
            float(self.config.capital.base_capital)
            + float(self.cumulative_net_pnl)
            + float(self._current_unrealized_pnl())
        )

    def _update_week_anchor(self, net_equity: float, now: datetime) -> None:
        today = now.date()
        if self.week_start_equity is None or self.week_anchor_date is None:
            self.week_start_equity = float(net_equity)
            self.week_anchor_date = today
            return
        if today.weekday() == 0 and self.week_anchor_date < today:
            self.week_start_equity = float(net_equity)
            self.week_anchor_date = today

    def _accounting_integrity_report(self, now: datetime) -> Dict[str, Any]:
        net_equity = self._current_net_equity()
        runtime_equity_payload = {
            "base_capital": float(self.config.capital.base_capital),
            "realized_net_pnl": float(self.cumulative_net_pnl),
            "unrealized_pnl": float(self._current_unrealized_pnl()),
            "net_equity": float(net_equity),
        }
        report = self.accounting_integrity.validate_equity_integrity(runtime_equity_payload)
        report["computed_net_equity"] = float(net_equity)
        report["timestamp"] = _to_iso(now)
        return report

    def _load_governance_controls(self) -> Dict[str, Any]:
        """Read governance flags written by the daemon."""
        payload = self._read_json_file(self.runtime_state_path)
        if not isinstance(payload, dict):
            return {"block_new_risk": False, "current_mode": "normal_operation", "mode_constraints": {}}
        return {
            "block_new_risk": bool(payload.get("block_new_risk", False)),
            "current_mode": str(payload.get("current_mode", "normal_operation") or "normal_operation"),
            "mode_constraints": payload.get("mode_constraints", {}) if isinstance(payload.get("mode_constraints"), dict) else {},
            "integrity_status": str(payload.get("integrity_status", "")),
            "last_governance_check": payload.get("last_governance_check"),
        }

    def _write_live_engine_heartbeat(self, now: datetime) -> None:
        heartbeat = {
            "timestamp": _to_iso(now),
            "pid": os.getpid(),
            "status": "alive",
            "recovery_mode": bool(self.recovery_mode),
        }
        self._write_json_atomic(self.heartbeat_path, heartbeat)

    def _write_daily_continuity_snapshot(
        self,
        now: datetime,
        dashboard_state: Dict[str, Any],
    ) -> None:
        self.eod_snapshots_dir.mkdir(parents=True, exist_ok=True)
        path = self.eod_snapshots_dir / f"{now.date().isoformat()}.json"
        snapshot = {
            "timestamp": _to_iso(now),
            "runtime_summary": {
                "net_equity": float(self._current_net_equity()),
                "realized_net_pnl": float(self.cumulative_net_pnl),
                "unrealized_pnl": float(self._current_unrealized_pnl()),
                "open_positions": int(len(self.position_manager.get_open_positions())),
                "closed_positions": int(len(self.position_manager.get_closed_positions())),
                "week_start_equity": float(self.week_start_equity or self._current_net_equity()),
            },
            "dashboard_state": dashboard_state,
        }
        self._write_json_atomic(path, snapshot)

    def _alpha_os_prev_cycle_multiplier(self) -> float:
        if not (self.alpha_os_enabled and self.alpha_os_enforce_mode):
            return 1.0
        intent = self.alpha_os_last_intent if isinstance(self.alpha_os_last_intent, dict) else {}
        gross_target = float(intent.get("gross_target", 0.0) or 0.0)
        risk_budget = intent.get("risk_budget", {}) if isinstance(intent.get("risk_budget"), dict) else {}
        gross_cap = float(risk_budget.get("gross_cap", 0.0) or 0.0)
        if gross_cap <= 1e-8:
            return 1.0
        scale = gross_target / gross_cap
        return float(max(0.0, min(1.25, scale)))

    def _alpha_os_prev_cycle_veto(self) -> bool:
        if not (self.alpha_os_enabled and self.alpha_os_enforce_mode):
            return False
        intent = self.alpha_os_last_intent if isinstance(self.alpha_os_last_intent, dict) else {}
        risk_budget = intent.get("risk_budget", {}) if isinstance(intent.get("risk_budget"), dict) else {}
        survival = (
            ((intent.get("diagnostics", {}) or {}).get("survival_core", {}) or {})
            if isinstance(intent.get("diagnostics"), dict)
            else {}
        )
        survival_lock = bool(
            ((survival.get("state", {}) or {}).get("directives", {}) or {}).get("lock_new_risk", False)
        )
        return bool(risk_budget.get("veto_active", False) or survival_lock)

    @staticmethod
    def _weights_from_active_positions(positions: List[Position]) -> Dict[str, float]:
        gross = float(sum(abs(float(p.max_loss or 0.0)) for p in positions))
        if gross <= 1e-12:
            return {}
        agg: Dict[str, float] = {}
        for p in positions:
            strategy = str(getattr(p, "strategy_type", "") or "unknown")
            agg[strategy] = agg.get(strategy, 0.0) + abs(float(p.max_loss or 0.0))
        return {k: float(v / gross) for k, v in agg.items()}

    def _evaluate_alpha_os_cycle(
        self,
        now: datetime,
        dashboard_state: Dict[str, Any],
        chain_cache: Dict[str, pd.DataFrame],
        current_equity: float,
    ) -> Dict[str, Any]:
        if not (self.alpha_os_enabled and self.alpha_os_adapter is not None):
            return {}
        try:
            current_positions = self.position_manager.get_open_positions()
            current_weights = self._weights_from_active_positions(current_positions)
            risk_used = float((dashboard_state.get("portfolio_risk_usage", {}) or {}).get("risk_pct", 0.0) or 0.0)
            current_drawdown = 0.0
            if self.scaling_state and self.scaling_state.equity_high_water_mark > 0:
                current_drawdown = max(
                    0.0,
                    (self.scaling_state.equity_high_water_mark - self.scaling_state.current_equity)
                    / max(self.scaling_state.equity_high_water_mark, 1e-8),
                )
            canonical_sources = {
                "dashboard_state": {"timestamp": str(dashboard_state.get("timestamp"))},
                "capital_allocations": {
                    "path": str(PROJECT_ROOT / "data/processed/capital_allocations.json"),
                    "age_seconds": self._file_age_seconds(PROJECT_ROOT / "data/processed/capital_allocations.json"),
                },
                "regime_intelligence_feed": {
                    "path": str(PROJECT_ROOT / "data/processed/regime_intelligence_feed.json"),
                    "age_seconds": self._file_age_seconds(PROJECT_ROOT / "data/processed/regime_intelligence_feed.json"),
                },
            }
            context = AlphaOSContext(
                timestamp=_to_iso(now),
                cycle_id=str(int(time.time())),
                canonical_state=dashboard_state,
                canonical_sources=canonical_sources,
                current_positions=[
                    {
                        "position_id": p.position_id,
                        "strategy_type": p.strategy_type,
                        "max_loss": float(p.max_loss or 0.0),
                        "unrealized_pnl": float(p.unrealized_pnl or 0.0),
                    }
                    for p in current_positions
                ],
                current_weights=current_weights,
                current_gross_exposure=float(sum(abs(v) for v in current_weights.values())),
                current_net_exposure=float(sum(current_weights.values())),
                current_drawdown=float(current_drawdown),
                max_gross_cap=float(max(0.0, 1.0 - risk_used)),
                max_net_cap=float(max(0.0, min(0.6, 1.0 - risk_used))),
                risk_veto_active=bool((dashboard_state.get("kill_switch_status", {}) or {}).get("active", False)),
                risk_veto_reasons=[
                    str((dashboard_state.get("kill_switch_status", {}) or {}).get("reason", ""))
                ],
                market_snapshot=dict(dashboard_state.get("market_snapshot", {}) or {}),
                portfolio_overlay=dict(dashboard_state.get("portfolio_overlay", {}) or {}),
                additional_inputs={
                    "chain_cache": chain_cache,
                    "iv_series": [
                        float(row.get("iv", 0.0) or 0.0)
                        for rows in self.iv_history.values()
                        for row in rows[-40:]
                    ],
                    "realized_vol": float(
                        abs((dashboard_state.get("regime_metrics", {}) or {}).get("iv_rank", 0.2) or 0.2)
                    ),
                    "current_equity": float(current_equity),
                    "liquidity_spread_pct": float(
                        (
                            ((dashboard_state.get("trade_eligibility", {}) or {}).get("liquidity_spread_pct", 0.0))
                            if isinstance(dashboard_state.get("trade_eligibility"), dict)
                            else 0.0
                        )
                        or 0.0
                    ),
                    "seasonality_score": 0.0,
                },
            )
            intent = self.alpha_os_adapter.evaluate_cycle(context)
            intent_dict = intent.to_dict()
            self.alpha_os_last_intent = intent_dict
            return intent_dict
        except Exception as e:
            logger.exception("AlphaOS cycle evaluation failed")
            self.alpha_os_last_intent = {
                "timestamp": _to_iso(now),
                "mode": "error",
                "reason_codes": [f"alpha_os_evaluation_error:{e}"],
            }
            return self.alpha_os_last_intent

    @staticmethod
    def _file_age_seconds(path: Path) -> Optional[float]:
        if not path.exists():
            return None
        try:
            return max(0.0, time.time() - path.stat().st_mtime)
        except Exception:
            return None

    def _append_alpha_os_artifacts(self, intent: Dict[str, Any]) -> None:
        if not (
            self.alpha_os_enabled
            and bool(getattr(self.config.alpha_os, "write_legacy_artifacts", True))
            and isinstance(intent, dict)
            and intent
        ):
            return

        alpha_block = {
            "timestamp": intent.get("timestamp"),
            "mode": intent.get("mode"),
            "used_fallback": bool(intent.get("used_fallback", False)),
            "fallback_level": intent.get("fallback_level"),
            "reason_codes": list(intent.get("reason_codes", []) or []),
            "effective_strategy_weights": dict(intent.get("strategy_weights", {}) or {}),
            "alpha_strategy_weights": dict(((intent.get("diagnostics", {}) or {}).get("alpha_os_weights", {}) or {})),
            "drift": dict(((intent.get("diagnostics", {}) or {}).get("drift", {}) or {})),
            "survival_core": dict(((intent.get("diagnostics", {}) or {}).get("survival_core", {}) or {})),
            "shadow_divergence_index": dict(
                ((intent.get("diagnostics", {}) or {}).get("shadow_divergence_index", {}) or {})
            ),
        }

        capital_path = PROJECT_ROOT / "data/processed/capital_allocations.json"
        regime_path = PROJECT_ROOT / "data/processed/regime_intelligence_feed.json"

        capital_payload = self._read_json_file(capital_path)
        capital_payload["alpha_os"] = alpha_block
        capital_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(capital_path, capital_payload)

        regime_payload = self._read_json_file(regime_path)
        regime_snap = intent.get("regime_snapshot", {}) if isinstance(intent.get("regime_snapshot"), dict) else {}
        survival_core_active = bool(
            (
                (
                    ((intent.get("diagnostics", {}) or {}).get("survival_core", {}) or {}).get("state", {})
                    or {}
                ).get("active", False)
            )
        )
        regime_payload["alpha_os"] = {
            "timestamp": intent.get("timestamp"),
            "mode": intent.get("mode"),
            "probabilities": dict(regime_snap.get("probabilities", {}) or {}),
            "confidence": float(regime_snap.get("confidence", 0.0) or 0.0),
            "model_version": regime_snap.get("model_version"),
            "stale": bool(regime_snap.get("stale", False)),
            "reason_codes": list(regime_snap.get("reason_codes", []) or []),
            "drift": dict(((intent.get("diagnostics", {}) or {}).get("drift", {}) or {})),
            "survival_core_active": survival_core_active,
        }
        regime_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(regime_path, regime_payload)

        self._append_alpha_os_timeseries(intent)
        self._append_alpha_os_strategy_posteriors(intent)

    @staticmethod
    def _alpha_os_fallback_tier(fallback_level: Optional[str], used_fallback: bool) -> int:
        level = str(fallback_level or "").strip().lower()
        if level in {"", "none"} and not used_fallback:
            return 0
        if "tier1" in level:
            return 1
        if "tier2" in level:
            return 2
        if "tier3" in level:
            return 3
        if "tier4" in level or "heuristic" in level or used_fallback:
            return 4
        return 0

    @staticmethod
    def _alpha_os_entropy(probabilities: Dict[str, Any]) -> float:
        if not isinstance(probabilities, dict) or not probabilities:
            return 0.0
        vals = np.asarray([float(v) for v in probabilities.values()], dtype=float)
        vals = np.clip(vals, 1e-12, None)
        vals = vals / max(vals.sum(), 1e-12)
        return float(-np.sum(vals * np.log(vals)))

    @staticmethod
    def _alpha_os_dominant_regime(probabilities: Dict[str, Any]) -> str:
        if not isinstance(probabilities, dict) or not probabilities:
            return "UNKNOWN"
        try:
            return str(max(probabilities.items(), key=lambda kv: float(kv[1]))[0])
        except Exception:
            return "UNKNOWN"

    def _append_alpha_os_timeseries(self, intent: Dict[str, Any]) -> None:
        diagnostics = intent.get("diagnostics", {}) if isinstance(intent.get("diagnostics"), dict) else {}
        regime_snapshot = intent.get("regime_snapshot", {}) if isinstance(intent.get("regime_snapshot"), dict) else {}
        risk_budget = intent.get("risk_budget", {}) if isinstance(intent.get("risk_budget"), dict) else {}
        meta_feedback = intent.get("meta_feedback", {}) if isinstance(intent.get("meta_feedback"), dict) else {}
        probs = regime_snapshot.get("probabilities", {}) if isinstance(regime_snapshot.get("probabilities"), dict) else {}
        drift = diagnostics.get("drift", {}) if isinstance(diagnostics.get("drift"), dict) else {}
        drift_metrics = drift.get("metrics", {}) if isinstance(drift.get("metrics"), dict) else {}
        survival_core = diagnostics.get("survival_core", {}) if isinstance(diagnostics.get("survival_core"), dict) else {}
        survival_state = (
            survival_core.get("state", {})
            if isinstance(survival_core.get("state"), dict)
            else {}
        )
        survival_directives = (
            survival_state.get("directives", {})
            if isinstance(survival_state.get("directives"), dict)
            else {}
        )
        allocator_metrics = (
            diagnostics.get("allocator_metrics", {})
            if isinstance(diagnostics.get("allocator_metrics"), dict)
            else {}
        )
        sdi = (
            diagnostics.get("shadow_divergence_index", {})
            if isinstance(diagnostics.get("shadow_divergence_index"), dict)
            else {}
        )
        sdi_components = sdi.get("components", {}) if isinstance(sdi.get("components"), dict) else {}

        row = {
            "timestamp": pd.to_datetime(intent.get("timestamp"), errors="coerce"),
            "mode": str(intent.get("mode", "unknown") or "unknown"),
            "used_fallback": bool(intent.get("used_fallback", False)),
            "fallback_level": str(intent.get("fallback_level") or ""),
            "fallback_tier": int(
                self._alpha_os_fallback_tier(
                    intent.get("fallback_level"),
                    bool(intent.get("used_fallback", False)),
                )
            ),
            "reason_codes_count": int(len(intent.get("reason_codes", []) or [])),
            "gross_target": float(intent.get("gross_target", 0.0) or 0.0),
            "net_target": float(intent.get("net_target", 0.0) or 0.0),
            "gross_cap": float(risk_budget.get("gross_cap", 0.0) or 0.0),
            "net_cap": float(risk_budget.get("net_cap", 0.0) or 0.0),
            "gross_used": float(risk_budget.get("gross_used", 0.0) or 0.0),
            "net_used": float(risk_budget.get("net_used", 0.0) or 0.0),
            "convexity_score": float(risk_budget.get("convexity_score", 0.0) or 0.0),
            "gap_risk_score": float(risk_budget.get("gap_risk_score", 0.0) or 0.0),
            "crowding_score": float(risk_budget.get("crowding_score", 0.0) or 0.0),
            "liquidity_adjusted_vega": float(risk_budget.get("liquidity_adjusted_vega", 0.0) or 0.0),
            "regime_low_vol": float(probs.get("LOW_VOL", 0.0) or 0.0),
            "regime_high_vol": float(probs.get("HIGH_VOL", 0.0) or 0.0),
            "regime_crisis": float(probs.get("CRISIS", 0.0) or 0.0),
            "regime_transition": float(probs.get("TRANSITION", 0.0) or 0.0),
            "regime_confidence": float(regime_snapshot.get("confidence", 0.0) or 0.0),
            "regime_entropy": float(self._alpha_os_entropy(probs)),
            "dominant_regime": self._alpha_os_dominant_regime(probs),
            "drift_detected": bool(drift.get("drift_detected", False)),
            "drift_severity": str(drift.get("severity", "normal") or "normal"),
            "drift_log_likelihood_roll": float(
                drift_metrics.get("log_likelihood_roll", 0.0) or 0.0
            ),
            "drift_entropy_roll": float(drift_metrics.get("entropy_roll", 0.0) or 0.0),
            "drift_transition_kl": float(drift_metrics.get("transition_kl", 0.0) or 0.0),
            "drift_emission_distance_roll": float(
                drift_metrics.get("emission_distance_roll", 0.0) or 0.0
            ),
            "survival_core_active": bool(survival_state.get("active", False)),
            "survival_active_cycles": int(survival_state.get("active_cycles", 0) or 0),
            "survival_trigger_count": int(survival_state.get("trigger_count", 0) or 0),
            "survival_lock_new_risk": bool(survival_directives.get("lock_new_risk", False)),
            "allocator_vol_proxy": float(allocator_metrics.get("vol_proxy", 0.0) or 0.0),
            "allocator_cvar_proxy": float(allocator_metrics.get("cvar_proxy", 0.0) or 0.0),
            "allocator_drawdown_probability_proxy": float(
                allocator_metrics.get("drawdown_probability_proxy", 0.0) or 0.0
            ),
            "allocator_liquidity_penalty": float(
                allocator_metrics.get("liquidity_penalty", 0.0) or 0.0
            ),
            "allocator_convexity_proxy": float(
                allocator_metrics.get("convexity_proxy", 0.0) or 0.0
            ),
            "allocator_expected_return_proxy": float(
                allocator_metrics.get("expected_return_proxy", 0.0) or 0.0
            ),
            "meta_regret_ewma": float(meta_feedback.get("regret_ewma", 0.0) or 0.0),
            "meta_confidence_ewma": float(meta_feedback.get("confidence_ewma", 0.0) or 0.0),
            "meta_credibility_relative_change": float(
                meta_feedback.get("credibility_relative_change", 0.0) or 0.0
            ),
            "meta_adjustment_multiplier": float(
                meta_feedback.get("adjustment_multiplier", 1.0) or 1.0
            ),
            "meta_hysteresis_active": bool(meta_feedback.get("hysteresis_active", False)),
            "meta_max_delta_applied": bool(meta_feedback.get("max_delta_applied", False)),
            "meta_exposure_floor_applied": bool(
                meta_feedback.get("exposure_floor_applied", False)
            ),
            "sdi": float(sdi.get("sdi", 0.0) or 0.0),
            "sdi_band": str(sdi.get("band", "aligned") or "aligned"),
            "sdi_weight_divergence_l1": float(
                sdi_components.get("weight_divergence_l1", 0.0) or 0.0
            ),
            "sdi_convexity_divergence_abs": float(
                sdi_components.get("convexity_divergence_abs", 0.0) or 0.0
            ),
            "sdi_strategy_inclusion_divergence": float(
                sdi_components.get("strategy_inclusion_divergence", 0.0) or 0.0
            ),
            "sdi_expected_return_divergence_abs": float(
                sdi_components.get("expected_return_divergence_abs", 0.0) or 0.0
            ),
            "weights_count_final": int(len(intent.get("strategy_weights", {}) or {})),
            "weights_count_alpha": int(
                len(
                    (
                        diagnostics.get("alpha_os_weights", {})
                        if isinstance(diagnostics.get("alpha_os_weights"), dict)
                        else {}
                    )
                )
            ),
            "weights_count_legacy": int(
                len(
                    (
                        diagnostics.get("legacy_weights", {})
                        if isinstance(diagnostics.get("legacy_weights"), dict)
                        else {}
                    )
                )
            ),
        }

        ts_path = PROJECT_ROOT / "data/processed/alpha_os_timeseries.parquet"
        ts_path.parent.mkdir(parents=True, exist_ok=True)
        new_df = pd.DataFrame([row]).dropna(subset=["timestamp"])
        if ts_path.exists():
            try:
                old = pd.read_parquet(ts_path)
                if isinstance(old, pd.DataFrame) and not old.empty:
                    new_df = pd.concat([old, new_df], ignore_index=True)
            except Exception:
                pass
        new_df = (
            new_df.sort_values("timestamp")
            .drop_duplicates(subset=["timestamp"], keep="last")
            .tail(20_000)
        )
        new_df.to_parquet(ts_path, index=False)

    def _append_alpha_os_strategy_posteriors(self, intent: Dict[str, Any]) -> None:
        posterior_rows = intent.get("strategy_posteriors", [])
        if not isinstance(posterior_rows, list) or not posterior_rows:
            return

        diagnostics = intent.get("diagnostics", {}) if isinstance(intent.get("diagnostics"), dict) else {}
        alpha_weights = (
            diagnostics.get("alpha_os_weights", {})
            if isinstance(diagnostics.get("alpha_os_weights"), dict)
            else {}
        )
        legacy_weights = (
            diagnostics.get("legacy_weights", {})
            if isinstance(diagnostics.get("legacy_weights"), dict)
            else {}
        )
        final_weights = intent.get("strategy_weights", {}) if isinstance(intent.get("strategy_weights"), dict) else {}

        ts = pd.to_datetime(intent.get("timestamp"), errors="coerce")
        if pd.isna(ts):
            return

        rows = []
        for row in posterior_rows:
            if not isinstance(row, dict):
                continue
            strategy = str(row.get("strategy_name", "") or "")
            if not strategy:
                continue
            rows.append(
                {
                    "timestamp": ts,
                    "mode": str(intent.get("mode", "unknown") or "unknown"),
                    "strategy_name": strategy,
                    "posterior_mean": float(row.get("posterior_mean", 0.0) or 0.0),
                    "posterior_variance": float(row.get("posterior_variance", 0.0) or 0.0),
                    "volatility": float(row.get("volatility", 0.0) or 0.0),
                    "adjusted_sharpe": float(row.get("adjusted_sharpe", 0.0) or 0.0),
                    "credibility": float(row.get("credibility", 0.0) or 0.0),
                    "information_ratio": float(row.get("information_ratio", 0.0) or 0.0),
                    "crowding_penalty": float(row.get("crowding_penalty", 1.0) or 1.0),
                    "convexity_penalty": float(row.get("convexity_penalty", 1.0) or 1.0),
                    "legacy_weight": float(legacy_weights.get(strategy, 0.0) or 0.0),
                    "alpha_weight": float(alpha_weights.get(strategy, 0.0) or 0.0),
                    "final_weight": float(final_weights.get(strategy, 0.0) or 0.0),
                }
            )

        if not rows:
            return

        out = PROJECT_ROOT / "data/processed/alpha_os_strategy_posteriors.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(rows)
        if out.exists():
            try:
                old = pd.read_parquet(out)
                if isinstance(old, pd.DataFrame) and not old.empty:
                    df = pd.concat([old, df], ignore_index=True)
            except Exception:
                pass
        df = (
            df.sort_values("timestamp")
            .drop_duplicates(subset=["timestamp", "strategy_name"], keep="last")
            .tail(100_000)
        )
        df.to_parquet(out, index=False)

    def _prime_alpha_os_precycle_intent(self, now: datetime) -> Dict[str, Any]:
        """
        Evaluate AlphaOS before trade decisions so enforce mode can act this cycle.
        """
        if not (self.alpha_os_enabled and self.alpha_os_enforce_mode and self.alpha_os_adapter is not None):
            return {}
        pre_state = self._read_json_file(self.dashboard_state_path)
        if not pre_state:
            pre_state = self._build_dashboard_state(now, chain_cache={})
        current_equity = (
            float(self.scaling_state.current_equity)
            if self.scaling_state is not None
            else float(self.config.capital.base_capital + self.cumulative_net_pnl)
        )
        return self._evaluate_alpha_os_cycle(
            now=now,
            dashboard_state=pre_state,
            chain_cache={},
            current_equity=current_equity,
        )

    def _load_sentiment_context(self, now: datetime) -> Dict[str, Any]:
        """Load latest NS-USO sentiment snapshot for overlay-aware routing."""
        out: Dict[str, Any] = {
            "available": False,
            "status": "missing",
            "summary_timestamp": None,
            "summary_age_minutes": None,
            "market_timestamp": None,
            "market_age_minutes": None,
            "fresh": False,
            "polarity": 0.0,
            "uncertainty": 0.0,
            "conviction": 1.0,
            "narrative_conflict": 0.0,
            "dominant_theme": "neutral",
            "micro_shift_score": 0.0,
            "change_velocity": 0.0,
            "delta_polarity": 0.0,
            "delta_uncertainty": 0.0,
            "delta_conviction": 0.0,
            "sentiment_bias": 0.0,      # [-1, +1], bearish -> negative
            "event_shock_score": 0.0,   # [0, +inf), larger => stronger hedge tilt
            "alert_level": "normal",    # normal | elevated | high | critical
            "news_signal_score": 0.0,
            "top_trending_companies": [],
            "negative_trending_companies": [],
            "event_company_impacts": [],
        }

        try:
            canonical = load_canonical_sentiment_context(
                now=now,
                project_root=PROJECT_ROOT,
                top_companies_limit=SENTIMENT_TOP_COMPANIES_LIMIT,
            )
            if not isinstance(canonical, dict):
                return out

            out.update(canonical)
            if not isinstance(out.get("top_trending_companies"), list):
                out["top_trending_companies"] = []
            if not isinstance(out.get("negative_trending_companies"), list):
                out["negative_trending_companies"] = []
            if not isinstance(out.get("event_company_impacts"), list):
                out["event_company_impacts"] = []

            out["status"] = str(out.get("status", "missing") or "missing").strip().lower()
            out["alert_level"] = str(out.get("alert_level", "normal") or "normal").strip().lower()
            out["dominant_theme"] = str(out.get("dominant_theme", "neutral") or "neutral")
            out["available"] = bool(out.get("available", False))
            out["fresh"] = bool(out.get("fresh", False))

            numeric_defaults = {
                "summary_age_minutes": None,
                "market_age_minutes": None,
                "polarity": 0.0,
                "uncertainty": 0.0,
                "conviction": 1.0,
                "narrative_conflict": 0.0,
                "micro_shift_score": 0.0,
                "change_velocity": 0.0,
                "delta_polarity": 0.0,
                "delta_uncertainty": 0.0,
                "delta_conviction": 0.0,
                "sentiment_bias": 0.0,
                "event_shock_score": 0.0,
                "news_signal_score": 0.0,
            }
            for key, default in numeric_defaults.items():
                raw = out.get(key, default)
                try:
                    value = float(raw)
                    if not math.isfinite(value):
                        raise ValueError("non-finite")
                    out[key] = value
                except Exception:
                    out[key] = default

            if out["available"] and out["status"] in {"", "unknown", "missing"}:
                out["status"] = "success"
            return out
        except Exception as e:
            logger.warning("Sentiment context load failed; using safe defaults: %s", e)
            return out

    def _load_portfolio_overlay_context(self, now: datetime) -> Dict[str, Any]:
        """Build portfolio-aware options context from V3 weekly portfolio artifacts + opportunity surface."""
        sentiment_context = self._load_sentiment_context(now)
        overlay: Dict[str, Any] = {
            "timestamp": _to_iso(now),
            "enabled": bool(self.portfolio_overlay_enabled),
            "status": "disabled" if not self.portfolio_overlay_enabled else "ok",
            "warnings": [],
            "weekly_rationale": "",
            "portfolio_objective": "balanced_overlay",
            "hedge_intensity": 0.0,
            "risk_on_probability": 0.5,
            "cash_level": 0.0,
            "total_exposure": 0.0,
            "dominant_sector": {"name": None, "weight": 0.0},
            "capital_allocation_top": [],
            "selected_stock_underlyings": [],
            "selected_stock_rows": [],
            "stock_objectives": {},
            "index_objectives": {},
            "dynamic_underlyings": list(self.underlyings),
            "weights_summary": {
                "total_holdings": 0,
                "option_eligible_holdings": 0,
                "selected_holdings": 0,
                "opportunity_surface_stocks": 0,
            },
            "sentiment_context": sentiment_context,
        }

        if not self.portfolio_overlay_enabled:
            return overlay

        weights_path = PROJECT_ROOT / "data/processed/portfolio_weights.parquet"
        analytics_path = PROJECT_ROOT / "data/processed/portfolio_analytics.json"
        capital_path = PROJECT_ROOT / "data/processed/capital_allocations.json"
        narrative_path = PROJECT_ROOT / "data/reports/narrative_suite_latest.json"
        regime_path = PROJECT_ROOT / "data/processed/regime_intelligence_feed.json"
        opportunity_path = PROJECT_ROOT / "data/processed/opportunity_surface.parquet"
        research_opportunity_path = PROJECT_ROOT / "data/processed/research_opportunity_surface.parquet"

        weights_rows: List[Dict[str, Any]] = []
        if not weights_path.exists():
            overlay["status"] = "partial"
            overlay["warnings"].append(f"missing_weights_file:{weights_path}")
        else:
            try:
                wdf = pd.read_parquet(weights_path)
                if isinstance(wdf, pd.DataFrame) and not wdf.empty:
                    symbol_col = "symbol" if "symbol" in wdf.columns else ("ticker" if "ticker" in wdf.columns else None)
                    weight_col = next((c for c in ["weight", "final_weight", "allocation", "w"] if c in wdf.columns), None)
                    if not symbol_col or not weight_col:
                        overlay["status"] = "partial"
                        overlay["warnings"].append("weights_missing_symbol_or_weight_column")
                    else:
                        for _, row in wdf.iterrows():
                            raw_ticker = str(row.get(symbol_col, "") or "").strip().upper()
                            symbol = raw_ticker.replace(".NS", "")
                            if not symbol:
                                continue
                            try:
                                weight = float(row.get(weight_col, 0.0) or 0.0)
                            except Exception:
                                weight = 0.0
                            if weight <= 0.0:
                                continue
                            stock = self.stock_loader.get_stock(symbol)
                            weights_rows.append({
                                "ticker": raw_ticker,
                                "symbol": symbol,
                                "weight": weight,
                                "position_role": str(row.get("position_role", "") or "").strip() or None,
                                "industry": str(row.get("Industry", "") or "").strip() or None,
                                "option_eligible": bool(stock is not None),
                                "instrument_key": stock.instrument_key if stock else None,
                                "sector": stock.sector if stock and stock.sector else (str(row.get("Industry", "") or "").strip() or None),
                            })
            except Exception as e:
                overlay["status"] = "partial"
                overlay["warnings"].append(f"weights_load_error:{e}")

        weights_rows.sort(key=lambda x: float(x.get("weight", 0.0) or 0.0), reverse=True)
        option_rows = [r for r in weights_rows if bool(r.get("option_eligible"))]
        max_sel = max(0, int(self.portfolio_overlay_max_stocks))
        selected_rows = option_rows[:max_sel] if max_sel > 0 else []

        # Load opportunity surface for alpha generation beyond portfolio
        opportunity_stocks: List[Dict[str, Any]] = []
        sentiment_driven_stocks: List[Dict[str, Any]] = []
        opp_frames: List[pd.DataFrame] = []
        if opportunity_path.exists():
            try:
                base_df = pd.read_parquet(opportunity_path)
                if isinstance(base_df, pd.DataFrame) and not base_df.empty:
                    opp_frames.append(base_df.copy())
            except Exception as e:
                overlay["warnings"].append(f"opportunity_surface_load_error:{e}")
                logger.warning(f"Could not load opportunity surface: {e}")
        if research_opportunity_path.exists():
            try:
                r_opp_df = pd.read_parquet(research_opportunity_path)
                if isinstance(r_opp_df, pd.DataFrame) and not r_opp_df.empty:
                    opp_frames.append(r_opp_df.copy())
            except Exception as e:
                overlay["warnings"].append(f"research_opportunity_surface_load_error:{e}")
                logger.warning(f"Could not load research opportunity surface: {e}")

        if opp_frames:
            try:
                opp_df = pd.concat(opp_frames, ignore_index=True, sort=False)
                if isinstance(opp_df, pd.DataFrame) and not opp_df.empty:
                    # Filter for high-conviction opportunities (Alpha Core + Momentum Breakouts)
                    if "opportunity_type" in opp_df.columns:
                        high_conviction = opp_df[
                            opp_df["opportunity_type"].astype(str).isin(["Alpha Core", "Momentum Breakouts"])
                        ].copy()
                    else:
                        # Fallback: use top mispricing + confirmation scores
                        high_conviction = opp_df[
                            (pd.to_numeric(opp_df.get("mispricing"), errors="coerce").fillna(0.0) >= 0.6)
                            & (pd.to_numeric(opp_df.get("confirmation"), errors="coerce").fillna(0.0) >= 0.5)
                        ].copy() if "mispricing" in opp_df.columns else opp_df.copy()

                    # Sort by combined score (mispricing * confirmation)
                    if "mispricing" in high_conviction.columns and "confirmation" in high_conviction.columns:
                        high_conviction["combined_score"] = (
                            pd.to_numeric(high_conviction["mispricing"], errors="coerce").fillna(0.0)
                            * pd.to_numeric(high_conviction["confirmation"], errors="coerce").fillna(0.0)
                        )
                        high_conviction = high_conviction.sort_values("combined_score", ascending=False)
                    if "ticker" in high_conviction.columns:
                        high_conviction = high_conviction.drop_duplicates(subset=["ticker"], keep="first")

                    # Get top opportunities that aren't already in portfolio
                    portfolio_tickers = {r["symbol"] for r in selected_rows}
                    for _, row in high_conviction.head(40).iterrows():  # Check top 40 merged opportunities
                        ticker_raw = str(row.get("ticker", "")).strip().upper()
                        ticker = ticker_raw.replace(".NS", "")  # Remove .NS suffix
                        if not ticker or ticker in portfolio_tickers:
                            continue

                        stock = self.stock_loader.get_stock(ticker)
                        if stock:  # Only add if options are available
                            opportunity_stocks.append({
                                "ticker": ticker,
                                "symbol": ticker,
                                "weight": 0.0,  # Not in portfolio, pure alpha play
                                "position_role": "opportunity_alpha",
                                "industry": stock.sector if stock.sector else None,
                                "option_eligible": True,
                                "instrument_key": stock.instrument_key,
                                "sector": stock.sector,
                                "mispricing": float(row.get("mispricing", 0)),
                                "confirmation": float(row.get("confirmation", 0)),
                                "opportunity_type": str(row.get("opportunity_type", "Alpha Core")),
                                "source": str(row.get("source", "opportunity_surface")),
                                "driver_variable": str(row.get("driver_variable", "") or "").strip() or None,
                                "signal_direction": str(row.get("signal_direction", "") or "").strip() or None,
                            })

                        # Limit opportunity stocks to avoid overwhelming the system
                        if len(opportunity_stocks) >= 20:
                            break

                    logger.info(
                        "Loaded %d merged opportunity surface stocks for options trading (frames=%d)",
                        len(opportunity_stocks),
                        len(opp_frames),
                    )
            except Exception as e:
                overlay["warnings"].append(f"merged_opportunity_surface_load_error:{e}")
                logger.warning(f"Could not merge opportunity surfaces: {e}")

        # Add sentiment/event-shock names from NS-USO company intelligence for cross-system coherence.
        sentiment_top = sentiment_context.get("top_trending_companies", []) if isinstance(sentiment_context, dict) else []
        event_impacts = sentiment_context.get("event_company_impacts", []) if isinstance(sentiment_context, dict) else []
        sentiment_rows_for_selection: List[Dict[str, Any]] = []
        if isinstance(sentiment_top, list) and sentiment_top:
            positive_rows: List[Dict[str, Any]] = []
            negative_rows: List[Dict[str, Any]] = []
            neutral_rows: List[Dict[str, Any]] = []

            for raw_item in sentiment_top[:SENTIMENT_TOP_COMPANIES_LIMIT]:
                if not isinstance(raw_item, dict):
                    continue
                sentiment_label = str(raw_item.get("sentiment_label", "") or "").strip().lower()
                try:
                    sentiment_score = float(raw_item.get("sentiment_score", 0.0) or 0.0)
                except Exception:
                    sentiment_score = 0.0
                try:
                    sentiment_sign = int(raw_item.get("sentiment_sign", _sentiment_sign(sentiment_label, sentiment_score)) or 0)
                except Exception:
                    sentiment_sign = _sentiment_sign(sentiment_label, sentiment_score)
                if sentiment_sign > 0:
                    positive_rows.append(raw_item)
                elif sentiment_sign < 0:
                    negative_rows.append(raw_item)
                else:
                    neutral_rows.append(raw_item)

            # For downside books, prioritize strongest negatives first.
            negative_rows = sorted(
                negative_rows,
                key=lambda row: float(row.get("signed_sentiment_intensity", 0.0) or 0.0),
            )

            seed_positive = positive_rows[:16]
            seed_negative = negative_rows[:16]
            seed_neutral = neutral_rows[:16]

            for idx in range(max(len(seed_positive), len(seed_negative), len(seed_neutral))):
                if idx < len(seed_positive):
                    sentiment_rows_for_selection.append(seed_positive[idx])
                if idx < len(seed_negative):
                    sentiment_rows_for_selection.append(seed_negative[idx])
                if idx < len(seed_neutral):
                    sentiment_rows_for_selection.append(seed_neutral[idx])

            sentiment_rows_for_selection.extend(positive_rows[16:])
            sentiment_rows_for_selection.extend(negative_rows[16:])
            sentiment_rows_for_selection.extend(neutral_rows[16:])

        seen_sentiment: set[str] = set()
        existing_syms = {str(r.get("symbol", "")).upper() for r in (selected_rows + opportunity_stocks)}
        for item in sentiment_rows_for_selection:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "") or "").replace(".NS", "").strip().upper()
            if not ticker or ticker in seen_sentiment or ticker in existing_syms:
                continue
            stock = self.stock_loader.get_stock(ticker)
            if not stock:
                continue
            sentiment_driven_stocks.append({
                "ticker": ticker,
                "symbol": ticker,
                "weight": 0.0,
                "position_role": "sentiment_event",
                "industry": stock.sector if stock.sector else None,
                "option_eligible": True,
                "instrument_key": stock.instrument_key,
                "sector": stock.sector,
                "trend_score": float(item.get("trend_score", 0.0) or 0.0),
                "sentiment_label": str(item.get("sentiment_label", "") or "").lower(),
                "headline_count": int(item.get("headline_count", 0) or 0),
            })
            seen_sentiment.add(ticker)
            if len(sentiment_driven_stocks) >= 18:
                break
        for item in (event_impacts[:30] if isinstance(event_impacts, list) else []):
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "") or "").replace(".NS", "").strip().upper()
            if not ticker or ticker in seen_sentiment or ticker in existing_syms:
                continue
            stock = self.stock_loader.get_stock(ticker)
            if not stock:
                continue
            sentiment_driven_stocks.append({
                "ticker": ticker,
                "symbol": ticker,
                "weight": 0.0,
                "position_role": "sentiment_event",
                "industry": stock.sector if stock.sector else None,
                "option_eligible": True,
                "instrument_key": stock.instrument_key,
                "sector": stock.sector,
                "trend_score": float(item.get("impact_score", 0.0) or 0.0),
                "sentiment_label": str(item.get("impact_direction", "unknown") or "unknown").lower(),
                "headline_count": 0,
                "event_type": str(item.get("event_type", "macro") or "macro"),
            })
            seen_sentiment.add(ticker)
            if len(sentiment_driven_stocks) >= 24:
                break
        if sentiment_driven_stocks:
            pos_count = 0
            neg_count = 0
            for row in sentiment_driven_stocks:
                label = str(row.get("sentiment_label", "") or "").strip().lower()
                if label in POSITIVE_SENTIMENT_LABELS:
                    pos_count += 1
                elif label in NEGATIVE_SENTIMENT_LABELS:
                    neg_count += 1
            logger.info(
                "Added %d sentiment/event-driven stocks from NS-USO overlays (positive=%d negative=%d neutral/other=%d)",
                len(sentiment_driven_stocks),
                pos_count,
                neg_count,
                max(0, len(sentiment_driven_stocks) - pos_count - neg_count),
            )

        # Combine portfolio stocks + opportunity stocks
        all_selected_rows = selected_rows + opportunity_stocks + sentiment_driven_stocks

        overlay["weights_summary"] = {
            "total_holdings": int(len(weights_rows)),
            "option_eligible_holdings": int(len(option_rows)),
            "selected_holdings": int(len(selected_rows)),
            "opportunity_surface_stocks": int(len(opportunity_stocks)),
            "sentiment_driven_stocks": int(len(sentiment_driven_stocks)),
            "total_selected": int(len(all_selected_rows)),
        }
        overlay["selected_stock_underlyings"] = [str(r.get("symbol")) for r in all_selected_rows]
        overlay["selected_stock_rows"] = all_selected_rows

        analytics = self._read_json_file(analytics_path)
        capital = self._read_json_file(capital_path)
        narrative = self._read_json_file(narrative_path)
        regime_feed = self._read_json_file(regime_path)

        portfolio_summary = analytics.get("portfolio_summary", {}) if isinstance(analytics.get("portfolio_summary"), dict) else {}
        sector_allocation = analytics.get("sector_allocation", {}) if isinstance(analytics.get("sector_allocation"), dict) else {}
        intelligence = analytics.get("intelligence_integration", {}) if isinstance(analytics.get("intelligence_integration"), dict) else {}
        dual_engine = analytics.get("dual_engine_coordination", {}) if isinstance(analytics.get("dual_engine_coordination"), dict) else {}
        current_regime = str((regime_feed.get("current_regime", {}) or {}).get("name") or dual_engine.get("market_regime") or "").strip()

        try:
            cash_level = float(portfolio_summary.get("cash_level", 0.0) or 0.0)
        except Exception:
            cash_level = 0.0
        try:
            total_exposure = float(portfolio_summary.get("total_exposure", 0.0) or 0.0)
        except Exception:
            total_exposure = 0.0
        try:
            concentration = float(portfolio_summary.get("largest_position", 0.0) or 0.0)
        except Exception:
            concentration = 0.0
        try:
            risk_on_probability = float(intelligence.get("risk_on_probability", 0.5) or 0.5)
        except Exception:
            risk_on_probability = 0.5

        dominant_sector_name = None
        dominant_sector_weight = 0.0
        if sector_allocation:
            try:
                dominant_sector_name, dominant_sector_weight = max(
                    ((str(k), float(v or 0.0)) for k, v in sector_allocation.items()),
                    key=lambda kv: kv[1],
                )
            except Exception:
                dominant_sector_name, dominant_sector_weight = None, 0.0

        sector_index_underlyings: List[str] = []
        if sector_allocation:
            try:
                ranked_sectors = sorted(
                    ((str(k), float(v or 0.0)) for k, v in sector_allocation.items()),
                    key=lambda kv: kv[1],
                    reverse=True,
                )
                for sector_name, sector_weight in ranked_sectors:
                    if sector_weight < 0.03:
                        continue
                    normalized_sector = sector_name.strip().lower()
                    for map_key, mapped_indices in SECTOR_INDEX_MAP.items():
                        if map_key in normalized_sector:
                            for idx in mapped_indices:
                                if idx not in sector_index_underlyings:
                                    sector_index_underlyings.append(idx)
                            break
                    if len(sector_index_underlyings) >= 5:
                        break
            except Exception:
                sector_index_underlyings = []

        regime_lower = current_regime.lower()
        bearish_flag = 1.0 if any(k in regime_lower for k in ("bear", "panic", "fragile", "crisis")) else 0.0
        sentiment_shock = float(sentiment_context.get("event_shock_score", 0.0) or 0.0)
        alert_level = str(sentiment_context.get("alert_level", "normal") or "normal").strip().lower()
        negative_news_count = (
            len(sentiment_context.get("negative_trending_companies", []) or [])
            if isinstance(sentiment_context, dict)
            else 0
        )
        event_impact_count = (
            len(sentiment_context.get("event_company_impacts", []) or [])
            if isinstance(sentiment_context, dict)
            else 0
        )
        news_pressure = min(0.25, (negative_news_count / 25.0) + (event_impact_count / 80.0))
        hedge_intensity = (
            max(0.0, 0.50 - cash_level) * 1.25
            + max(0.0, dominant_sector_weight - 0.12) * 1.65
            + max(0.0, total_exposure - 0.45) * 0.80
            + bearish_flag * 0.40
            + max(0.0, concentration - 0.025) * 3.0
            + min(0.55, sentiment_shock * 0.70)
            + news_pressure
        )
        hedge_intensity = min(1.0, max(0.0, hedge_intensity))
        hedge_priority_mode = (
            hedge_intensity >= HEDGE_PRIORITY_MIN_INTENSITY
            or alert_level in HEDGE_PRIORITY_ALERT_LEVELS
            or sentiment_shock >= 0.45
            or negative_news_count >= 5
            or event_impact_count >= 10
        )

        if alert_level in HEDGE_PRIORITY_ALERT_LEVELS:
            portfolio_objective = "defensive_convexity"
        elif hedge_intensity >= HEDGE_PRIORITY_HIGH_INTENSITY:
            portfolio_objective = "defensive_convexity"
        elif risk_on_probability >= 0.58 and total_exposure >= 0.35:
            portfolio_objective = "income_plus_alpha"
        else:
            portfolio_objective = "balanced_overlay"

        stock_objectives: Dict[str, Dict[str, Any]] = {}
        stock_rows: List[Dict[str, Any]] = []
        for row in all_selected_rows:
            symbol = str(row.get("symbol", "") or "")
            weight = float(row.get("weight", 0.0) or 0.0)
            role = str(row.get("position_role", "") or "").lower()
            confirmation = float(row.get("confirmation", 0.0) or 0.0)
            mispricing = float(row.get("mispricing", 0.0) or 0.0)
            sentiment_label = str(row.get("sentiment_label", "") or "").lower()
            trend_score = float(row.get("trend_score", 0.0) or 0.0)

            if role == "sentiment_event":
                if sentiment_label in {"negative", "very_negative", "bearish", "downside"}:
                    objective = "event_shock_hedge"
                    reason = "ns_uso_negative_event_company_impact"
                elif alert_level in HEDGE_PRIORITY_ALERT_LEVELS:
                    objective = "protect_core"
                    reason = "ns_uso_event_signal_during_high_alert"
                elif hedge_priority_mode:
                    objective = "protect_core"
                    reason = "ns_uso_hedge_priority_bias"
                elif trend_score >= 0.55:
                    objective = "alpha_momentum"
                    reason = "ns_uso_positive_sentiment_trend"
                else:
                    objective = "alpha_income"
                    reason = "ns_uso_sentiment_income_overlay"
            elif role == "opportunity_alpha":
                if hedge_priority_mode and sentiment_label in {"negative", "very_negative", "bearish", "downside"}:
                    objective = "event_shock_hedge"
                    reason = "opportunity_overlay_negative_sentiment_hedge"
                elif hedge_priority_mode:
                    objective = "protect_core"
                    reason = "opportunity_rebalanced_for_hedge_priority"
                elif risk_on_probability >= 0.55 and (confirmation >= 0.55 or mispricing >= 0.65):
                    objective = "alpha_momentum"
                    reason = "opportunity_surface_high_conviction"
                else:
                    objective = "alpha_income"
                    reason = "opportunity_surface_income_tilt"
            elif hedge_priority_mode and weight >= 0.010:
                objective = "protect_core"
                reason = "hedge_priority_for_weighted_core_holding"
            elif hedge_intensity >= HEDGE_PRIORITY_HIGH_INTENSITY and weight >= 0.015:
                objective = "protect_core"
                reason = "high_hedge_intensity_and_core_weight"
            elif weight >= 0.020 and risk_on_probability >= 0.55:
                objective = "alpha_income"
                reason = "high_weight_and_risk_on"
            elif role == "satellite":
                objective = "satellite_probe"
                reason = "satellite_position_option_overlay"
            else:
                objective = "alpha_momentum"
                reason = "balanced_alpha_overlay"

            stock_objectives[symbol] = {
                "objective": objective,
                "reason": reason,
                "weight": weight,
                "ticker": str(row.get("ticker", symbol)),
                "sector": row.get("sector"),
                "position_role": role or None,
                "opportunity_type": row.get("opportunity_type"),
            }
            stock_rows.append({
                "symbol": symbol,
                "ticker": str(row.get("ticker", symbol)),
                "weight": weight,
                "objective": objective,
                "reason": reason,
                "sector": row.get("sector"),
                "position_role": role or None,
                "confirmation": confirmation if role == "opportunity_alpha" else None,
                "mispricing": mispricing if role == "opportunity_alpha" else None,
                "trend_score": trend_score if role == "sentiment_event" else None,
                "sentiment_label": sentiment_label if role == "sentiment_event" else None,
            })

        base_indices = [u for u in self.underlyings if u in INDEX_UNDERLYINGS or u in sector_index_underlyings]
        if not base_indices:
            base_indices = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
        for idx in sector_index_underlyings:
            if idx not in base_indices:
                base_indices.append(idx)

        weekly_hedge_targets: List[str] = []
        if (
            alert_level in {"elevated", "high", "critical"}
            or hedge_intensity >= HEDGE_PRIORITY_MIN_INTENSITY
            or total_exposure >= 0.50
            or negative_news_count >= 4
            or event_impact_count >= 8
        ):
            weekly_hedge_targets.extend(["NIFTY", "BANKNIFTY"])
        if dominant_sector_name and "financial" in str(dominant_sector_name).lower():
            weekly_hedge_targets.append("FINNIFTY")
        for idx in weekly_hedge_targets:
            if idx not in base_indices:
                base_indices.append(idx)

        index_objectives: Dict[str, str] = {}
        for idx in base_indices:
            if alert_level in HEDGE_PRIORITY_ALERT_LEVELS:
                index_objectives[idx] = "event_shock_hedge"
            elif hedge_priority_mode and idx in INDEX_UNDERLYINGS:
                index_objectives[idx] = "hedge_convexity"
            elif hedge_intensity >= HEDGE_PRIORITY_HIGH_INTENSITY:
                index_objectives[idx] = "hedge_convexity"
            elif portfolio_objective == "income_plus_alpha":
                index_objectives[idx] = "sector_rotation_overlay" if idx in sector_index_underlyings else "income_harvest"
            else:
                index_objectives[idx] = "sector_rotation_overlay" if idx in sector_index_underlyings else "vol_breakout"
        for idx in weekly_hedge_targets:
            if alert_level in {"high", "critical"}:
                index_objectives[idx] = "event_shock_hedge"
            else:
                index_objectives[idx] = index_objectives.get(idx, "hedge_convexity")

        allocations = capital.get("allocations", {}) if isinstance(capital.get("allocations"), dict) else {}
        top_alloc = sorted(
            ((str(k), float(v or 0.0)) for k, v in allocations.items()),
            key=lambda kv: kv[1],
            reverse=True,
        )[:5]

        weekly_rationale = (
            str(narrative.get("layer_2_portfolio_rationale", "") or "").strip()
            or str((narrative.get("five_layer_narrative", {}) or {}).get("what_doing", "") or "").strip()
            or str((narrative.get("five_layer_narrative", {}) or {}).get("why_happening", "") or "").strip()
        )

        try:
            max_dynamic_underlyings = int(
                os.getenv(
                    "OPTIONS_MAX_DYNAMIC_UNDERLYINGS",
                    str(PORTFOLIO_OVERLAY_DEFAULT_MAX_DYNAMIC_UNDERLYINGS),
                )
            )
        except Exception:
            max_dynamic_underlyings = PORTFOLIO_OVERLAY_DEFAULT_MAX_DYNAMIC_UNDERLYINGS
        max_dynamic_underlyings = max(max(6, len(self.underlyings)), max_dynamic_underlyings)

        dynamic_underlyings: List[str] = []
        for sym in [*weekly_hedge_targets, *base_indices, *self.underlyings]:
            if sym and sym not in dynamic_underlyings:
                dynamic_underlyings.append(sym)
        if len(dynamic_underlyings) < max_dynamic_underlyings:
            ranked_stock_rows = sorted(
                stock_rows,
                key=lambda r: (
                    float(r.get("weight", 0.0) or 0.0),
                    1.0 if str(r.get("objective", "")).strip().lower() in HEDGE_OBJECTIVES else 0.0,
                ),
                reverse=True,
            )
            for row in ranked_stock_rows:
                sym = str(row.get("symbol", "") or "").strip().upper()
                if not sym or sym in dynamic_underlyings:
                    continue
                dynamic_underlyings.append(sym)
                if len(dynamic_underlyings) >= max_dynamic_underlyings:
                    break
        if dynamic_underlyings:
            resolved = [u for u in dynamic_underlyings if self._resolve_key(u)]
            dynamic_underlyings = resolved if resolved else dynamic_underlyings
            dynamic_underlyings = dynamic_underlyings[:max_dynamic_underlyings]

        overlay.update({
            "weekly_rationale": weekly_rationale,
            "portfolio_objective": portfolio_objective,
            "hedge_intensity": hedge_intensity,
            "risk_on_probability": risk_on_probability,
            "cash_level": cash_level,
            "total_exposure": total_exposure,
            "concentration": concentration,
            "regime": current_regime or "UNKNOWN",
            "dominant_sector": {
                "name": dominant_sector_name,
                "weight": dominant_sector_weight,
            },
            "capital_allocation_top": [
                {"strategy": k, "allocation": v} for k, v in top_alloc
            ],
            "sector_index_underlyings": sector_index_underlyings,
            "weekly_hedge_targets": list(dict.fromkeys(weekly_hedge_targets)),
            "stock_objectives": stock_objectives,
            "selected_stock_rows": stock_rows,
            "index_objectives": index_objectives,
            "dynamic_underlyings": dynamic_underlyings or list(self.underlyings),
        })
        return overlay

    def _resolve_cycle_underlyings(self, overlay: Dict[str, Any]) -> List[str]:
        if not self.portfolio_overlay_enabled:
            return list(self.underlyings)
        dynamic = overlay.get("dynamic_underlyings", [])
        if not isinstance(dynamic, list):
            return list(self.underlyings)
        generic_tokens = {"NSE", "NSE_EQ", "NSE_FO", "NFO", "BSE", "BSE_EQ", "BSE_FO", "NSE_INDEX"}
        resolved = []
        for u in dynamic:
            sym = self._normalize_underlying_symbol(u)
            if not sym or sym in resolved or sym in generic_tokens:
                continue
            if self._resolve_key(sym):
                resolved.append(sym)
        return resolved or list(self.underlyings)

    def _objective_for_underlying(self, underlying: str, overlay: Dict[str, Any]) -> Dict[str, Any]:
        default = {"objective": "balanced_overlay", "reason": "default_objective", "weight": None}
        if not isinstance(overlay, dict):
            return default

        index_objectives = overlay.get("index_objectives", {})
        if isinstance(index_objectives, dict) and underlying in index_objectives:
            return {
                "objective": str(index_objectives.get(underlying) or "balanced_overlay"),
                "reason": "index_overlay_objective",
                "weight": None,
            }

        stock_objectives = overlay.get("stock_objectives", {})
        if isinstance(stock_objectives, dict):
            stock_meta = stock_objectives.get(underlying)
            if isinstance(stock_meta, dict):
                return {
                    "objective": str(stock_meta.get("objective") or "balanced_overlay"),
                    "reason": str(stock_meta.get("reason") or "stock_overlay_objective"),
                    "weight": float(stock_meta.get("weight", 0.0) or 0.0),
                }
        return default

    @staticmethod
    def _overlay_sentiment(overlay: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(overlay, dict):
            return {}
        sentiment = overlay.get("sentiment_context")
        return sentiment if isinstance(sentiment, dict) else {}

    @classmethod
    def _is_hedge_priority_mode(cls, overlay: Dict[str, Any]) -> bool:
        hedge_intensity = float(overlay.get("hedge_intensity", 0.0) or 0.0) if isinstance(overlay, dict) else 0.0
        sentiment = cls._overlay_sentiment(overlay)
        alert = str(sentiment.get("alert_level", "normal") or "normal").strip().lower()
        event_shock = float(sentiment.get("event_shock_score", 0.0) or 0.0)
        negative_news = (
            len(sentiment.get("negative_trending_companies", []) or [])
            if isinstance(sentiment.get("negative_trending_companies"), list)
            else 0
        )
        event_impacts = (
            len(sentiment.get("event_company_impacts", []) or [])
            if isinstance(sentiment.get("event_company_impacts"), list)
            else 0
        )
        return bool(
            hedge_intensity >= HEDGE_PRIORITY_MIN_INTENSITY
            or alert in HEDGE_PRIORITY_ALERT_LEVELS
            or event_shock >= 0.45
            or negative_news >= 5
            or event_impacts >= 10
        )

    @staticmethod
    def _candidate_generation_order(objective: str) -> List[str]:
        objective = str(objective or "").strip().lower()
        if objective in {"event_shock_hedge"}:
            return [
                "bear_put_spread",
                "long_strangle",
                "calendar_spread",
                "long_straddle",
                "iron_condor",
                "iron_butterfly",
            ]
        if objective in {"hedge_convexity", "protect_core", "defensive_convexity"}:
            return [
                "bear_put_spread",
                "long_strangle",
                "calendar_spread",
                "long_straddle",
                "iron_condor",
                "iron_butterfly",
            ]
        if objective in {"sector_rotation_overlay"}:
            return [
                "calendar_spread",
                "bull_call_spread",
                "bear_put_spread",
                "iron_condor",
                "iron_butterfly",
                "long_strangle",
            ]
        if objective in {"income_harvest", "alpha_income", "income_plus_alpha"}:
            return [
                "iron_condor",
                "iron_butterfly",
                "short_strangle",
                "calendar_spread",
                "bull_call_spread",
                "bear_put_spread",
            ]
        if objective in {"vol_breakout", "alpha_momentum", "satellite_probe"}:
            return [
                "bull_call_spread",
                "bear_put_spread",
                "long_strangle",
                "calendar_spread",
                "long_straddle",
                "iron_condor",
            ]
        return [
            "calendar_spread",
            "bull_call_spread",
            "bear_put_spread",
            "iron_condor",
            "iron_butterfly",
            "long_strangle",
            "long_straddle",
        ]

    @staticmethod
    def _objective_size_multiplier(objective: str, overlay: Dict[str, Any]) -> float:
        objective = str(objective or "").strip().lower()
        hedge_intensity = float(overlay.get("hedge_intensity", 0.0) or 0.0) if isinstance(overlay, dict) else 0.0
        risk_on = float(overlay.get("risk_on_probability", 0.5) or 0.5) if isinstance(overlay, dict) else 0.5
        sentiment = (
            overlay.get("sentiment_context", {})
            if isinstance(overlay, dict) and isinstance(overlay.get("sentiment_context"), dict)
            else {}
        )
        alert = str(sentiment.get("alert_level", "normal") or "normal").strip().lower()
        event_shock = float(sentiment.get("event_shock_score", 0.0) or 0.0)
        hedge_priority_mode = IntegratedOptionsPaperEngine._is_hedge_priority_mode(overlay if isinstance(overlay, dict) else {})

        if objective in {"event_shock_hedge"}:
            return 1.25 + min(1.15, event_shock * 0.85 + hedge_intensity * 0.65)
        if objective in {"hedge_convexity", "protect_core", "defensive_convexity"}:
            return 1.18 + min(
                1.05,
                hedge_intensity * 1.0 + (0.18 if alert in HEDGE_PRIORITY_ALERT_LEVELS else 0.0),
            )
        if objective in {"sector_rotation_overlay"}:
            base = 1.0 + min(0.5, max(0.0, risk_on - 0.45))
            if hedge_priority_mode:
                base -= min(0.20, hedge_intensity * 0.25 + event_shock * 0.10)
            return max(0.70, base)
        if objective in {"income_harvest", "alpha_income", "income_plus_alpha"}:
            base = 0.98 + min(0.30, max(0.0, risk_on - 0.5))
            if hedge_priority_mode:
                base -= min(0.45, hedge_intensity * 0.55 + event_shock * 0.25)
            return max(0.55, base)
        if objective in {"vol_breakout", "alpha_momentum", "satellite_probe"}:
            base = 1.0 + min(0.3, max(0.0, risk_on - 0.45))
            if hedge_priority_mode:
                base -= min(0.25, hedge_intensity * 0.30 + event_shock * 0.15)
            return max(0.70, base)
        return 1.0

    def _generate_strategy_candidate(
        self,
        strategy_name: str,
        regime: VolatilityRegime,
        option_chain: pd.DataFrame,
        underlying: str,
    ) -> Optional[OptionStrategy]:
        # Enhanced strategy generator handles all strategy types through generate_strategy
        try:
            strategies = self.strategy_generator.generate_strategy(
                regime=regime,
                underlying=underlying,
                option_chain=option_chain,
                spot_price=float(option_chain['underlying_price'].iloc[0]) if not option_chain.empty else 100.0,
                preferred_strategy=str(strategy_name),
            )
            
            # Filter for requested strategy type if possible
            for strategy in strategies:
                if hasattr(strategy.strategy_type, 'value'):
                    strategy_type_str = str(strategy.strategy_type.value or "")
                else:
                    strategy_type_str = str(strategy.strategy_type)
                strategy_type_norm = strategy_type_str.strip().lower()
                requested_norm = str(strategy_name or "").strip().lower()
                
                if strategy_type_norm == requested_norm:
                    return strategy
                if requested_norm in strategy_type_norm or strategy_type_norm in requested_norm:
                    return strategy
            
            # Return first strategy if no specific match
            return strategies[0] if strategies else None
            
        except Exception as e:
            logger.warning(f"Enhanced strategy generation failed for {underlying} {strategy_name}: {e}")
            return None

    def _score_strategy_candidate(
        self,
        strategy: OptionStrategy,
        objective: str,
        overlay: Dict[str, Any],
        portfolio_greeks: Optional[Greeks] = None,
    ) -> Tuple[float, Dict[str, float]]:
        risk = max(1.0, abs(float(strategy.max_loss or 0.0)))
        reward = max(0.0, float(strategy.max_profit or 0.0))
        net_flow = float(strategy.net_credit_debit or 0.0)
        # Engine convention: negative net_credit_debit is net premium received (credit).
        credit = max(0.0, -net_flow)
        debit = max(0.0, net_flow)

        g = strategy.portfolio_greeks
        rr_signal = math.tanh(reward / risk)
        theta_signal = math.tanh(float(g.theta) / 250.0)
        vega_signal = math.tanh(float(g.vega) / 120.0)
        gamma_signal = math.tanh(float(g.gamma) / 50.0)
        delta_penalty = min(1.0, abs(float(g.delta)) / 80.0)
        credit_signal = credit / risk
        debit_signal = debit / risk

        objective_key = str(objective or "").strip().lower()
        hedge_intensity = float(overlay.get("hedge_intensity", 0.0) or 0.0) if isinstance(overlay, dict) else 0.0
        risk_on = float(overlay.get("risk_on_probability", 0.5) or 0.5) if isinstance(overlay, dict) else 0.5
        sentiment = self._overlay_sentiment(overlay if isinstance(overlay, dict) else {})
        alert = str(sentiment.get("alert_level", "normal") or "normal").strip().lower()
        event_shock = float(sentiment.get("event_shock_score", 0.0) or 0.0)
        strategy_type = self._strategy_type_value(strategy)
        is_short_vol = self._is_short_vol_type(strategy_type)
        is_hedge_preferred = strategy_type in HEDGE_PREFERRED_STRATEGY_TYPES
        hedge_priority_mode = self._is_hedge_priority_mode(overlay if isinstance(overlay, dict) else {})
        recent_share = self._recent_strategy_share(strategy_type)

        if objective_key in {"hedge_convexity", "protect_core", "defensive_convexity"}:
            score = (
                0.65 * vega_signal
                + 0.25 * gamma_signal
                + 0.20 * rr_signal
                - 0.35 * debit_signal
                - 0.20 * delta_penalty
                + 0.20 * hedge_intensity
            )
        elif objective_key in {"income_harvest", "alpha_income", "income_plus_alpha"}:
            score = (
                0.60 * theta_signal
                + 0.55 * credit_signal
                + 0.25 * rr_signal
                - 0.25 * delta_penalty
                - 0.15 * debit_signal
                + 0.15 * max(0.0, risk_on - 0.5)
            )
        elif objective_key in {"sector_rotation_overlay"}:
            score = (
                0.50 * rr_signal
                + 0.35 * theta_signal
                + 0.25 * vega_signal
                + 0.20 * max(0.0, risk_on - 0.45)
                - 0.20 * delta_penalty
                - 0.15 * debit_signal
            )
        elif objective_key in {"vol_breakout", "alpha_momentum", "satellite_probe"}:
            score = (
                0.45 * rr_signal
                + 0.35 * vega_signal
                + 0.20 * gamma_signal
                - 0.20 * delta_penalty
                - 0.20 * debit_signal
            )
        else:
            score = (
                0.40 * rr_signal
                + 0.30 * theta_signal
                + 0.20 * vega_signal
                - 0.20 * delta_penalty
                - 0.10 * debit_signal
            )

        hedge_bias_bonus = 0.0
        short_vol_penalty = 0.0

        if objective_key in HEDGE_OBJECTIVES:
            if is_hedge_preferred:
                hedge_bias_bonus += 0.22 + 0.18 * min(1.0, hedge_intensity + 0.5 * event_shock)
            if is_short_vol:
                short_vol_penalty += 0.55 + 0.35 * hedge_intensity
                if alert in HEDGE_PRIORITY_ALERT_LEVELS:
                    short_vol_penalty += 0.20

        if hedge_priority_mode:
            if is_hedge_preferred:
                hedge_bias_bonus += 0.20 + 0.15 * min(1.0, hedge_intensity + 0.5 * event_shock)
            if is_short_vol:
                short_vol_penalty += 0.30 + 0.45 * min(1.0, hedge_intensity) + 0.18 * min(1.0, event_shock)
                if alert in HEDGE_PRIORITY_ALERT_LEVELS:
                    short_vol_penalty += 0.22

        concentration_penalty = 0.0
        if recent_share > STRATEGY_CONCENTRATION_TARGET:
            concentration_penalty += min(
                MAX_STRATEGY_CONCENTRATION_PENALTY,
                (recent_share - STRATEGY_CONCENTRATION_TARGET) * 1.55,
            )
        if strategy_type == "long_straddle" and recent_share > 0.25:
            concentration_penalty += min(0.35, (recent_share - 0.25) * 0.90)
            if hedge_priority_mode and event_shock < 0.70:
                concentration_penalty += 0.12

        rebalance_bonus = 0.0
        if objective_key in HEDGE_OBJECTIVES or hedge_priority_mode:
            rebalance_gain = self._rebalance_gain(portfolio_greeks, g)
            rebalance_bonus = 0.18 * math.tanh(rebalance_gain / 30.0)

        score = score + hedge_bias_bonus + rebalance_bonus - short_vol_penalty - concentration_penalty

        return score, {
            "score": float(score),
            "rr_signal": float(rr_signal),
            "theta_signal": float(theta_signal),
            "vega_signal": float(vega_signal),
            "gamma_signal": float(gamma_signal),
            "delta_penalty": float(delta_penalty),
            "credit_signal": float(credit_signal),
            "debit_signal": float(debit_signal),
            "hedge_bias_bonus": float(hedge_bias_bonus),
            "short_vol_penalty": float(short_vol_penalty),
            "strategy_share_recent": float(recent_share),
            "strategy_concentration_penalty": float(concentration_penalty),
            "rebalance_bonus": float(rebalance_bonus),
        }

    @staticmethod
    def _strategy_type_value(strategy: OptionStrategy) -> str:
        if hasattr(strategy.strategy_type, "value"):
            return str(strategy.strategy_type.value or "").strip().lower()
        return str(strategy.strategy_type or "").strip().lower()

    @staticmethod
    def _is_short_vol_type(strategy_type: str) -> bool:
        return str(strategy_type or "").strip().lower() in SHORT_VOL_STRATEGY_TYPES

    def _is_short_vol_strategy(self, strategy: OptionStrategy) -> bool:
        return self._is_short_vol_type(self._strategy_type_value(strategy))

    def _alpha_os_weight_for_strategy_type(self, strategy_type: str) -> Optional[float]:
        if not (self.alpha_os_enabled and self.alpha_os_enforce_mode):
            return None
        intent = self.alpha_os_last_intent if isinstance(self.alpha_os_last_intent, dict) else {}
        if str(intent.get("mode", "")).strip().lower() != "enforce":
            return None
        weights = intent.get("strategy_weights", {}) if isinstance(intent.get("strategy_weights"), dict) else {}
        if not weights:
            return None

        st = str(strategy_type or "").strip().lower()
        lookup_keys = [st, st.replace("-", "_"), st.replace(" ", "_")]
        if st in HEDGE_PREFERRED_STRATEGY_TYPES:
            lookup_keys.extend(["long_vol", "convexity", "hedge"])
        elif self._is_short_vol_type(st):
            lookup_keys.extend(["short_vol", "income", "carry"])
        if "dispersion" in st:
            lookup_keys.append("dispersion")

        for key in lookup_keys:
            if key in weights:
                try:
                    return float(weights[key])
                except Exception:
                    continue
        return None

    def _alpha_os_strategy_size_multiplier(self, strategy_type: str) -> float:
        raw = self._alpha_os_weight_for_strategy_type(strategy_type)
        if raw is None:
            return 1.0
        intent = self.alpha_os_last_intent if isinstance(self.alpha_os_last_intent, dict) else {}
        weights = intent.get("strategy_weights", {}) if isinstance(intent.get("strategy_weights"), dict) else {}
        positive = [float(v) for v in weights.values() if isinstance(v, (int, float)) and float(v) > 0.0]
        if not positive:
            return 1.0
        baseline = sum(positive) / len(positive)
        if baseline <= 1e-12:
            return 1.0
        ratio = float(raw) / baseline
        return float(max(0.0, min(1.75, ratio)))

    def _alpha_os_strategy_blocked(self, strategy_type: str) -> Tuple[bool, Optional[str]]:
        raw = self._alpha_os_weight_for_strategy_type(strategy_type)
        if raw is None:
            return False, None
        if raw <= 0.01:
            return True, f"alpha_os_strategy_weight_gate:{strategy_type}:{raw:.4f}"
        return False, None

    def _recent_strategy_share(self, strategy_type: str, lookback: int = STRATEGY_CONCENTRATION_LOOKBACK) -> float:
        token = str(strategy_type or "").strip().lower()
        if not token:
            return 0.0
        opens = [
            row for row in (self.cycle_decision_history[-max(1, int(lookback)):] or [])
            if isinstance(row, dict) and str(row.get("status", "")).strip().lower() == "opened_position"
        ]
        if not opens:
            return 0.0
        same = [
            row for row in opens
            if str(row.get("strategy_type", "") or "").strip().lower() == token
        ]
        return float(len(same)) / float(len(opens))

    @staticmethod
    def _rebalance_gain(
        current: Optional[Greeks],
        candidate: Greeks,
    ) -> float:
        if current is None:
            return 0.0
        before = (
            0.45 * abs(float(current.delta))
            + 0.35 * abs(float(current.vega))
            + 0.20 * abs(float(current.gamma))
        )
        after = (
            0.45 * abs(float(current.delta) + float(candidate.delta))
            + 0.35 * abs(float(current.vega) + float(candidate.vega))
            + 0.20 * abs(float(current.gamma) + float(candidate.gamma))
        )
        return before - after

    def _estimate_expected_gross_pnl(
        self,
        strategy: OptionStrategy,
        objective: str,
        overlay: Dict[str, Any],
    ) -> float:
        risk = max(1.0, abs(float(strategy.max_loss or 0.0)))
        reward = max(0.0, float(strategy.max_profit or 0.0))
        objective_key = str(objective or "").strip().lower()
        sentiment = (
            overlay.get("sentiment_context", {})
            if isinstance(overlay, dict) and isinstance(overlay.get("sentiment_context"), dict)
            else {}
        )
        shock = float(sentiment.get("event_shock_score", 0.0) or 0.0)
        alert = str(sentiment.get("alert_level", "normal") or "normal").lower()
        hedge_intensity = float(overlay.get("hedge_intensity", 0.0) or 0.0) if isinstance(overlay, dict) else 0.0

        if objective_key in {"income_harvest", "alpha_income", "income_plus_alpha"}:
            win_prob = 0.58
            loss_prob = 0.42
        elif objective_key in {"event_shock_hedge", "hedge_convexity", "protect_core", "defensive_convexity"}:
            win_prob = 0.35 + min(0.20, shock * 0.18 + hedge_intensity * 0.12)
            loss_prob = 1.0 - win_prob
        elif objective_key in {"vol_breakout", "alpha_momentum", "satellite_probe"}:
            win_prob = 0.52
            loss_prob = 0.48
        else:
            win_prob = 0.50
            loss_prob = 0.50

        expected = (win_prob * reward) - (loss_prob * risk)

        if self._is_short_vol_strategy(strategy):
            expected -= min(0.35, shock * 0.25) * risk
            if alert in {"high", "critical"}:
                expected -= 0.15 * risk
        elif objective_key in HEDGE_OBJECTIVES:
            expected += min(0.30, shock * 0.20 + hedge_intensity * 0.15) * reward

        return float(expected)

    def _estimate_expected_net_pnl(
        self,
        strategy: OptionStrategy,
        objective: str,
        overlay: Dict[str, Any],
    ) -> Dict[str, float]:
        expected_gross = self._estimate_expected_gross_pnl(strategy, objective=objective, overlay=overlay)

        turnover = 0.0
        buy_turnover = 0.0
        for leg in strategy.legs:
            premium = max(0.0, float(getattr(leg, "premium", 0.0) or 0.0))
            qty = max(1.0, float(getattr(leg, "quantity", 1) or 1))
            notional = premium * qty
            turnover += notional
            if str(getattr(leg, "action", "")).strip().upper() == "BUY":
                buy_turnover += notional

        costs_cfg = self.config.costs
        tax_cfg = self.config.tax
        brokerage = float(costs_cfg.brokerage_per_leg) * len(strategy.legs) * 2.0
        exchange = turnover * float(costs_cfg.exchange_charges_pct) * 2.0
        sebi = (turnover * 2.0 / 10_000_000.0) * float(costs_cfg.sebi_charges_per_crore)
        stamp = buy_turnover * float(costs_cfg.stamp_duty_pct)
        gst = (brokerage + exchange) * float(costs_cfg.gst_pct)
        total_costs = brokerage + exchange + sebi + stamp + gst
        tax = expected_gross * float(tax_cfg.rate) if expected_gross > 0 else 0.0
        expected_net = expected_gross - total_costs - tax
        objective_key = str(objective or "").strip().lower()
        threshold_multiplier = float(tax_cfg.min_profitability_multiplier)
        if not self._is_short_vol_strategy(strategy):
            # Long-vol/debit strategies incur larger explicit costs for similar notional.
            # Keeping the same strict cost-multiple gate can reject the whole universe.
            threshold_multiplier = min(threshold_multiplier, 0.55)
            if objective_key in HEDGE_OBJECTIVES:
                threshold_multiplier = min(threshold_multiplier, 0.30)
        min_threshold = max(
            MIN_NET_EXPECTANCY_INR,
            total_costs * threshold_multiplier,
        )

        return {
            "expected_gross_pnl": float(expected_gross),
            "expected_total_costs": float(total_costs),
            "expected_tax": float(tax),
            "expected_net_pnl": float(expected_net),
            "min_threshold": float(min_threshold),
            "threshold_multiplier": float(threshold_multiplier),
        }

    def _passes_net_profit_gate(
        self,
        strategy: OptionStrategy,
        objective: str,
        overlay: Dict[str, Any],
    ) -> Dict[str, Any]:
        estimate = self._estimate_expected_net_pnl(strategy, objective=objective, overlay=overlay)
        expected_net = float(estimate.get("expected_net_pnl", 0.0) or 0.0)
        min_threshold = float(estimate.get("min_threshold", 0.0) or 0.0)
        objective_key = str(objective or "").strip().lower()
        sentiment = (
            overlay.get("sentiment_context", {})
            if isinstance(overlay, dict) and isinstance(overlay.get("sentiment_context"), dict)
            else {}
        )
        alert = str(sentiment.get("alert_level", "normal") or "normal").strip().lower()
        hedge_intensity = float(overlay.get("hedge_intensity", 0.0) or 0.0) if isinstance(overlay, dict) else 0.0
        event_shock = float(sentiment.get("event_shock_score", 0.0) or 0.0)
        hedge_priority_mode = self._is_hedge_priority_mode(overlay if isinstance(overlay, dict) else {})

        short_vol_min_threshold = float(min_threshold)
        if self._is_short_vol_strategy(strategy) and hedge_priority_mode:
            short_vol_min_threshold *= 1.15 + min(0.35, hedge_intensity * 0.30 + event_shock * 0.20)
            min_threshold = short_vol_min_threshold

        override = (
            objective_key in NET_PROFIT_OVERRIDE_OBJECTIVES
            and not self._is_short_vol_strategy(strategy)
            and alert in HEDGE_PRIORITY_ALERT_LEVELS
        )
        passed = bool(expected_net >= min_threshold or override)

        return {
            **estimate,
            "passed": passed,
            "override_applied": bool(override and expected_net < min_threshold),
            "objective": objective_key,
        }

    def _generate_portfolio_aware_strategy(
        self,
        underlying: str,
        routed_regime: Any,
        option_chain: pd.DataFrame,
        objective: str,
        overlay: Dict[str, Any],
    ) -> Tuple[Optional[OptionStrategy], Dict[str, Any]]:
        selector: Dict[str, Any] = {
            "objective": objective,
            "selected_source": None,
            "selected_strategy_type": None,
            "selected_score": None,
            "reason": "",
            "candidates": [],
        }

        normalized_regime = _to_regime(getattr(routed_regime, "value", routed_regime))
        candidates: List[Tuple[str, OptionStrategy]] = []

        try:
            default_strategies = self.strategy_generator.generate_strategy(
                regime=routed_regime,
                underlying=underlying,
                option_chain=option_chain,
                spot_price=float(option_chain['underlying_price'].iloc[0]) if not option_chain.empty else 100.0
            )
            default_strategy = default_strategies[0] if default_strategies else None
        except Exception as e:
            logger.warning(f"Default strategy generation failed for {underlying}: {e}")
            default_strategy = None

        if default_strategy is not None and default_strategy.is_valid:
            candidates.append(("regime_default", default_strategy))

        candidate_order = self._candidate_generation_order(objective)
        if self._is_hedge_priority_mode(overlay):
            hedge_first = [
                "bear_put_spread",
                "long_strangle",
                "calendar_spread",
                "long_straddle",
                "iron_condor",
                "iron_butterfly",
            ]
            ordered: List[str] = []
            for name in [*hedge_first, *candidate_order]:
                if name not in ordered:
                    ordered.append(name)
            candidate_order = ordered

        for strategy_name in candidate_order:
            candidate = self._generate_strategy_candidate(
                strategy_name=strategy_name,
                regime=normalized_regime,
                option_chain=option_chain,
                underlying=underlying,
            )
            if candidate is None:
                continue
            candidates.append((f"objective:{strategy_name}", candidate))

        if not candidates:
            selector["reason"] = "no_candidate_strategy_generated"
            return None, selector

        scored: List[Tuple[str, OptionStrategy, float, Dict[str, float]]] = []
        soft_fallback: List[Tuple[str, OptionStrategy, float, Dict[str, float], Dict[str, Any]]] = []
        current_portfolio_greeks = self.position_manager.calculate_portfolio_greeks()
        for source, strategy in candidates:
            gate_lots = self._indicative_candidate_lots(strategy, objective=objective, overlay=overlay)
            strategy_for_gate = self._scale_strategy(strategy, gate_lots) if gate_lots > 1 else strategy
            net_gate = self._passes_net_profit_gate(strategy_for_gate, objective=objective, overlay=overlay)
            score, details = self._score_strategy_candidate(
                strategy,
                objective=objective,
                overlay=overlay,
                portfolio_greeks=current_portfolio_greeks,
            )
            selector["candidates"].append({
                "source": source,
                "strategy_type": self._strategy_type_value(strategy),
                "score": float(score),
                "score_components": details,
                "max_loss": float(strategy.max_loss),
                "max_profit": float(strategy.max_profit),
                "net_credit_debit": float(strategy.net_credit_debit),
                "expected_net_pnl": float(net_gate.get("expected_net_pnl", 0.0) or 0.0),
                "min_net_threshold": float(net_gate.get("min_threshold", 0.0) or 0.0),
                "net_profit_gate_passed": bool(net_gate.get("passed", False)),
                "net_profit_override": bool(net_gate.get("override_applied", False)),
                "gate_lots": int(gate_lots),
            })
            if not bool(net_gate.get("passed", False)):
                expected_net = float(net_gate.get("expected_net_pnl", 0.0) or 0.0)
                if expected_net > 0.0:
                    soft_fallback.append((source, strategy, score, details, net_gate))
                continue
            scored.append((source, strategy, score, details))

        if not scored:
            if soft_fallback:
                soft_fallback.sort(
                    key=lambda x: (
                        float((x[4] or {}).get("expected_net_pnl", 0.0) or 0.0),
                        x[2],
                    ),
                    reverse=True,
                )
                selected_source, selected_strategy, selected_score, _selected_details, selected_gate = soft_fallback[0]
                selector["selected_source"] = selected_source
                selector["selected_strategy_type"] = self._strategy_type_value(selected_strategy)
                selector["selected_score"] = float(selected_score)
                selector["soft_net_gate_fallback"] = True
                selector["reason"] = (
                    f"fallback selected {self._strategy_type_value(selected_strategy)} with "
                    f"positive expected net ₹{float((selected_gate or {}).get('expected_net_pnl', 0.0) or 0.0):,.0f}"
                )
                return selected_strategy, selector
            selector["reason"] = "all_candidates_failed_net_profit_gate"
            return None, selector

        scored.sort(key=lambda x: x[2], reverse=True)
        selected_source, selected_strategy, selected_score, _ = scored[0]
        top_type = self._strategy_type_value(selected_strategy)
        top_share = self._recent_strategy_share(top_type)
        if top_type == "long_straddle" and top_share >= 0.45 and len(scored) > 1:
            alt = next(
                (
                    row for row in scored[1:]
                    if self._strategy_type_value(row[1]) != "long_straddle" and float(row[2]) >= float(selected_score) - 0.16
                ),
                None,
            )
            if alt is not None:
                selected_source, selected_strategy, selected_score, _ = alt
                selector["diversification_override"] = True
                selector["diversification_note"] = (
                    f"replaced long_straddle due recent share {top_share:.2f}"
                )
        selector["selected_source"] = selected_source
        selector["selected_strategy_type"] = self._strategy_type_value(selected_strategy)
        selector["selected_score"] = float(selected_score)
        selector["reason"] = (
            f"selected {self._strategy_type_value(selected_strategy)} for objective={objective} "
            f"(score={selected_score:.3f})"
        )
        return selected_strategy, selector

    def _load_runtime_state(self) -> None:
        if not self.runtime_state_path.exists():
            return

        signature_status = self.state_io.verify_runtime_state_signature()
        signature_state = str(signature_status.get("status", "unknown")).lower()
        if signature_state in {"mismatch", "signature_error"}:
            logger.error(
                "Runtime state signature invalid (%s); forcing reconciliation before load",
                signature_state,
            )
            self.recovery_required = True
            self.recovery_mode = True
            return
        if signature_state == "signature_missing":
            logger.warning("Runtime signature missing; continuing with caution")

        try:
            state = json.loads(self.runtime_state_path.read_text())
        except Exception as e:
            logger.warning(f"Could not parse runtime state: {e}")
            return

        self.iv_history = state.get("iv_history", {}) or {}
        self.regime_history = state.get("regime_history", []) or []
        self.greeks_history = state.get("greeks_history", []) or []
        self.last_trade_eligibility = state.get("last_trade_eligibility", self.last_trade_eligibility)
        self.last_eligibility_checks = state.get("last_eligibility_checks", []) or []
        self.last_kill_switch = state.get("last_kill_switch", {"active": False}) or {"active": False}
        self.portfolio_overlay = state.get("portfolio_overlay", {}) or {}
        self.latest_cycle_diagnostics = state.get("latest_cycle_diagnostics", {}) or {}
        self.cycle_decision_history = state.get("cycle_decision_history", []) or []
        self.alpha_os_last_intent = state.get("alpha_os_last_intent", {}) or {}
        self.cumulative_net_pnl = float(state.get("cumulative_net_pnl", 0.0) or 0.0)
        self.week_start_equity = (
            float(state.get("week_start_equity", 0.0))
            if state.get("week_start_equity") is not None
            else None
        )
        week_anchor_raw = state.get("week_anchor_date")
        try:
            self.week_anchor_date = (
                datetime.fromisoformat(str(week_anchor_raw)).date() if week_anchor_raw else None
            )
        except Exception:
            self.week_anchor_date = None
        self.last_reconciled_at = state.get("last_reconciled_at")

        self.position_manager.open_positions.clear()
        self.position_manager.closed_positions.clear()
        for p in state.get("open_positions", []) or []:
            pos = self._position_from_dict(p)
            if pos:
                self.position_manager.open_positions[pos.position_id] = pos
        for p in state.get("closed_positions", []) or []:
            pos = self._position_from_dict(p)
            if pos:
                self.position_manager.closed_positions.append(pos)

        scaling = state.get("scaling_state")
        if isinstance(scaling, dict):
            try:
                scaling["trading_start_date"] = _parse_dt(scaling.get("trading_start_date"))
                scaling["last_updated"] = _parse_dt(scaling.get("last_updated")) or datetime.utcnow()
                scaling["scaling_history"] = [
                    (_parse_dt(ts) or datetime.utcnow(), float(risk), str(reason))
                    for ts, risk, reason in scaling.get("scaling_history", [])
                ]
                self.scaling_state = ScalingState(**scaling)
            except Exception as e:
                logger.warning(f"Failed restoring scaling state: {e}")

        ytd = state.get("ytd", {}) or {}
        self.pnl_tracker.ytd_tax_liability = float(ytd.get("tax_liability", 0.0) or 0.0)
        self.pnl_tracker.ytd_gross_profits = float(ytd.get("gross_profits", 0.0) or 0.0)
        self.pnl_tracker.ytd_gross_losses = float(ytd.get("gross_losses", 0.0) or 0.0)
        self.pnl_tracker.ytd_total_costs = float(ytd.get("total_costs", 0.0) or 0.0)

    def _save_runtime_state(self) -> None:
        scaling = None
        if self.scaling_state is not None:
            scaling = {
                **self.scaling_state.__dict__,
                "trading_start_date": _to_iso(self.scaling_state.trading_start_date),
                "last_updated": _to_iso(self.scaling_state.last_updated),
                "scaling_history": [
                    (_to_iso(ts), risk, reason) for ts, risk, reason in self.scaling_state.scaling_history
                ],
            }

        now = _now_ist()
        unrealized_pnl = self._current_unrealized_pnl()
        net_equity = self._current_net_equity()
        self._update_week_anchor(net_equity, now)
        risk_cap_value = self._portfolio_risk_cap_value()
        risk_remaining = max(0.0, float(risk_cap_value - self._current_open_risk()))
        self.last_reconciled_at = _to_iso(now)

        state = {
            "schema_version": "2.1.0",
            "timestamp": _to_iso(now),
            "trading_day_ist": now.date().isoformat(),
            "continuity_mode": True,
            "recovery_mode": bool(self.recovery_mode),
            "start_fresh_today": bool(self.start_fresh_today),
            "base_capital": float(self.config.capital.base_capital),
            "portfolio_risk_cap_pct": float(self.config.survival_rules.portfolio_risk_cap_pct),
            "realized_net_pnl": float(self.cumulative_net_pnl),
            "unrealized_pnl": float(unrealized_pnl),
            "net_equity": float(net_equity),
            "week_start_equity": float(self.week_start_equity if self.week_start_equity is not None else net_equity),
            "week_anchor_date": self.week_anchor_date.isoformat() if self.week_anchor_date else None,
            "risk_cap_value": float(risk_cap_value),
            "risk_remaining": float(risk_remaining),
            "last_reconciled_at": self.last_reconciled_at,
            "current_mode": "normal_operation",
            "mode_constraints": {},
            "block_new_risk": False,
            "open_positions": [self._position_to_dict(p) for p in self.position_manager.get_open_positions()],
            "closed_positions": [self._position_to_dict(p) for p in self.position_manager.get_closed_positions()[-500:]],
            "scaling_state": scaling,
            "iv_history": self.iv_history,
            "regime_history": self.regime_history[-5000:],
            "greeks_history": self.greeks_history[-2000:],
            "last_trade_eligibility": self.last_trade_eligibility,
            "last_eligibility_checks": self.last_eligibility_checks,
            "last_kill_switch": self.last_kill_switch,
            "portfolio_overlay": self.portfolio_overlay,
            "latest_cycle_diagnostics": self.latest_cycle_diagnostics,
            "cycle_decision_history": self.cycle_decision_history[-5000:],
            "alpha_os_last_intent": self.alpha_os_last_intent,
            "limit_profile": self.limit_profile,
            "cumulative_net_pnl": self.cumulative_net_pnl,
            "ytd": {
                "tax_liability": self.pnl_tracker.ytd_tax_liability,
                "gross_profits": self.pnl_tracker.ytd_gross_profits,
                "gross_losses": self.pnl_tracker.ytd_gross_losses,
                "total_costs": self.pnl_tracker.ytd_total_costs,
            },
        }
        # Preserve governance fields written by daemon so the live engine doesn't
        # erase active mode constraints between governance cycles.
        existing_runtime = self._read_json_file(self.runtime_state_path)
        if isinstance(existing_runtime, dict):
            for key in (
                "recovery_mode",
                "current_mode",
                "mode_constraints",
                "block_new_risk",
                "integrity_status",
                "file_integrity_status",
                "file_integrity_issues",
                "last_governance_check",
                "research_throttled",
                "capital_tier",
            ):
                if key in existing_runtime:
                    state[key] = existing_runtime[key]
        if not self.state_io.write_runtime_state(state):
            logger.error("Failed writing runtime state; preserving previous runtime snapshot")

    def _position_to_dict(self, p: Position) -> Dict[str, Any]:
        return {
            "position_id": p.position_id,
            "strategy_type": p.strategy_type,
            "underlying": str(getattr(p, "underlying", "") or ""),
            "regime_at_entry": p.regime_at_entry.value if hasattr(p.regime_at_entry, "value") else str(p.regime_at_entry),
            "legs": [leg.__dict__ for leg in p.legs],
            "entry_time": _to_iso(p.entry_time),
            "expiry": str(p.expiry),
            "max_loss": p.max_loss,
            "max_profit": p.max_profit,
            "entry_credit_debit": p.entry_credit_debit,
            "current_value": p.current_value,
            "unrealized_pnl": p.unrealized_pnl,
            "realized_pnl": p.realized_pnl,
            "days_held": p.days_held,
            "greeks": p.greeks.__dict__ if p.greeks else None,
            "entry_greeks": p.entry_greeks.__dict__ if p.entry_greeks else None,
            "exit_time": _to_iso(p.exit_time),
            "exit_reason": p.exit_reason,
        }

    def _position_from_dict(self, d: Dict[str, Any]) -> Optional[Position]:
        try:
            legs = [PositionLeg(**leg) for leg in d.get("legs", [])]
            greeks = Greeks(**d["greeks"]) if d.get("greeks") else None
            entry_greeks = Greeks(**d["entry_greeks"]) if d.get("entry_greeks") else None
            fallback_underlying = ""
            if legs:
                symbol = str(getattr(legs[0], "symbol", "") or "").strip().upper()
                if "|" in symbol:
                    right = symbol.split("|", 1)[1].strip().upper()
                    if right and right.isalpha():
                        fallback_underlying = right
                if not fallback_underlying and "_" in symbol:
                    token = symbol.split("_", 1)[0].strip().upper()
                    if token not in {"NSE", "NSE_EQ", "NSE_FO", "NSE_INDEX", "NFO", "BSE", "BSE_EQ", "BSE_FO"}:
                        fallback_underlying = token
            underlying = self._normalize_underlying_symbol(
                d.get("underlying", ""),
                fallback=fallback_underlying or None,
            )
            return Position(
                position_id=d["position_id"],
                strategy_type=d["strategy_type"],
                underlying=underlying,
                regime_at_entry=_to_regime(d.get("regime_at_entry")),
                legs=legs,
                entry_time=_parse_dt(d.get("entry_time")) or datetime.utcnow(),
                expiry=date.fromisoformat(d.get("expiry")),
                max_loss=float(d.get("max_loss", 0.0) or 0.0),
                max_profit=float(d.get("max_profit", 0.0) or 0.0),
                entry_credit_debit=float(d.get("entry_credit_debit", 0.0) or 0.0),
                current_value=float(d.get("current_value", 0.0) or 0.0),
                unrealized_pnl=float(d.get("unrealized_pnl", 0.0) or 0.0),
                realized_pnl=d.get("realized_pnl"),
                days_held=int(d.get("days_held", 0) or 0),
                greeks=greeks,
                entry_greeks=entry_greeks,
                exit_time=_parse_dt(d.get("exit_time")),
                exit_reason=d.get("exit_reason"),
            )
        except Exception as e:
            logger.warning(f"Skipping invalid position state: {e}")
            return None

    def _is_market_hours(self) -> bool:
        """Check if current time is within Indian market hours (9:15 AM - 3:30 PM IST, Mon-Fri)"""
        now = _now_ist()
        
        # Weekend check
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Convert to minutes since midnight for easier comparison
        current_minutes = now.hour * 60 + now.minute
        market_open = 9 * 60 + 15   # 9:15 AM = 555 minutes
        market_close = 15 * 60 + 30  # 3:30 PM = 930 minutes
        
        return market_open <= current_minutes <= market_close

    def _resolve_key(self, underlying: str) -> Optional[str]:
        if underlying in self.upstox.instrument_key_map:
            return self.upstox.instrument_key_map[underlying]
        stock = self.stock_loader.get_stock(underlying)
        return stock.instrument_key if stock else None

    def _normalize_underlying_symbol(self, raw: Any, fallback: Optional[str] = None) -> str:
        """Normalize noisy underlying identifiers to canonical symbols."""
        text = str(raw or "").strip().upper()
        fallback_text = str(fallback or "").strip().upper()

        if not text and fallback_text:
            return fallback_text
        if text in self.stock_key_reverse_map:
            return self.stock_key_reverse_map[text]
        if text in self.instrument_key_reverse_map:
            return self.instrument_key_reverse_map[text]

        candidate_keys = []
        if "|" in text:
            left, right = text.split("|", 1)
            candidate_keys.append(f"{left.strip()}|{right.strip()}")
            # Direct symbol may appear in right side for index keys.
            right_token = right.strip().upper()
            if right_token in self.instrument_key_reverse_map:
                return self.instrument_key_reverse_map[right_token]
            if right_token.endswith(".NS"):
                right_token = right_token[:-3]
            if right_token.isalpha():
                text = right_token
        elif ":" in text:
            left, right = text.split(":", 1)
            candidate_keys.append(f"{left.strip()}|{right.strip()}")
            right_token = right.strip().upper()
            if right_token.endswith(".NS"):
                right_token = right_token[:-3]
            if right_token.isalpha():
                text = right_token

        for key in candidate_keys:
            mapped_stock = self.stock_key_reverse_map.get(str(key).upper())
            if mapped_stock:
                return mapped_stock
            mapped = self.instrument_key_reverse_map.get(str(key).upper())
            if mapped:
                return mapped

        if text.endswith(".NS"):
            text = text[:-3]

        generic_tokens = {"NSE", "NSE_EQ", "NSE_FO", "NFO", "BSE", "BSE_FO", "NSE_INDEX"}
        if (not text or text in generic_tokens or text.isdigit()) and fallback_text:
            return fallback_text
        return text

    def _fallback_expiries(self, underlying: str, count: int = 4) -> List[date]:
        weekday = EXPIRY_WEEKDAY_BY_UNDERLYING.get(str(underlying or "").upper(), DEFAULT_FALLBACK_EXPIRY_WEEKDAY)
        out: List[date] = []
        today = _now_ist().date()
        d = today
        for _ in range(60):
            if d.weekday() == weekday and (d - today).days >= 1:
                out.append(d)
                if len(out) >= count:
                    break
            d += timedelta(days=1)
        return out

    def _fetch_chain(self, underlying: str) -> pd.DataFrame:
        key = self._resolve_key(underlying)
        if not key:
            return pd.DataFrame()

        if hasattr(self.upstox, "is_network_available") and not self.upstox.is_network_available():
            return self._fallback_chain_from_disk(underlying)

        try:
            expiries = self.upstox.get_available_expiries(
                underlying=underlying,
                instrument_key=key,
                min_days=0,
                limit=6,
            )
        except Exception:
            expiries = []
        today = _now_ist().date()
        expiries = [exp for exp in expiries if isinstance(exp, date) and exp >= today]
        if not expiries:
            if underlying in INDEX_UNDERLYINGS:
                expiries = self._fallback_expiries(underlying, count=4)
            else:
                logger.warning(f"No expiries available for {underlying}; skipping this underlying for now")
                return pd.DataFrame()

        parts = []
        for exp in expiries[:4]:
            try:
                df = self.upstox.fetch_option_chain(underlying, exp, instrument_key=key)
            except Exception as e:
                logger.warning(f"{underlying} chain fetch failed for {exp}: {e}")
                if hasattr(self.upstox, "is_network_available") and not self.upstox.is_network_available():
                    break
                continue
            if df.empty:
                continue
            df = df.copy()
            df["underlying"] = underlying
            df["premium"] = df["ltp"].where(df["ltp"] > 0, (df["bid"] + df["ask"]) / 2.0)
            parts.append(df)
        if not parts:
            return self._fallback_chain_from_disk(underlying)
        chain = pd.concat(parts, ignore_index=True)
        chain["expiry"] = pd.to_datetime(chain["expiry"], errors="coerce")
        chain = chain.dropna(subset=["expiry"])
        
        # Save to cache for offline fallback
        self._save_chain_to_cache(underlying, chain)
        
        return chain

    def _save_chain_to_cache(self, underlying: str, chain: pd.DataFrame) -> None:
        """Save option chain to disk cache for offline fallback"""
        if chain.empty:
            return
        
        try:
            cache_dir = Path("data/options/chains_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = _now_ist().strftime("%Y%m%d_%H%M%S")
            filename = f"{underlying}_{timestamp}.parquet"
            filepath = cache_dir / filename
            
            chain.to_parquet(filepath, index=False)
            logger.debug(f"Saved chain cache: {filename}")
            
            # Clean up old cache files (keep latest N per underlying)
            pattern = f"{underlying}_*.parquet"
            files = sorted(cache_dir.glob(pattern), reverse=True)
            for old_file in files[self.chains_cache_keep_per_underlying:]:
                old_file.unlink()
                logger.debug(f"Removed old cache: {old_file.name}")
                
        except Exception as e:
            logger.warning(f"Failed to save chain cache for {underlying}: {e}")

    def _fallback_chain_from_disk(self, underlying: str) -> pd.DataFrame:
        """Load latest locally cached chain when API/network is unavailable."""
        candidates: List[Path] = []

        cache_dir = PROJECT_ROOT / "data/options/chains_cache"
        if cache_dir.exists():
            candidates.extend(sorted(cache_dir.glob(f"{underlying}_*.parquet"), reverse=True)[:5])

        candidates.extend([
            PROJECT_ROOT / f"data/options/historical/{underlying.lower()}_option_chains.parquet",
            PROJECT_ROOT / f"data/options/historical/groww/{underlying.lower()}_option_chains.parquet",
            PROJECT_ROOT / f"data/options/live/{underlying.lower()}_options_latest.parquet",
            PROJECT_ROOT / f"data/options/complete/{underlying.lower()}_all_options_latest.parquet",
            PROJECT_ROOT / "data/options/live/nifty_options_latest.parquet",
            PROJECT_ROOT / "data/options/complete/nifty_all_options_latest.parquet",
            PROJECT_ROOT / "data/options/sample_option_chain.parquet",
        ])
        for path in candidates:
            if not path.exists():
                continue
            try:
                df = pd.read_parquet(path)
            except Exception:
                continue
            if df.empty:
                continue
            c = df.copy()
            if "date" in c.columns:
                snapshot_dates = pd.to_datetime(c["date"], errors="coerce")
                if snapshot_dates.notna().any():
                    latest_date = snapshot_dates.max()
                    mask = snapshot_dates == latest_date
                    c = c.loc[mask].copy()
                    c["date"] = snapshot_dates.loc[mask].dt.date.values
            if c.empty:
                continue
            if "underlying" not in c.columns:
                c["underlying"] = underlying
            if "option_type" in c.columns:
                c["option_type"] = c["option_type"].astype(str).str.upper().replace({"C": "CE", "P": "PE"})
            if "premium" not in c.columns:
                if {"bid", "ask"}.issubset(c.columns):
                    c["premium"] = (pd.to_numeric(c["bid"], errors="coerce") + pd.to_numeric(c["ask"], errors="coerce")) / 2.0
                elif "ltp" in c.columns:
                    c["premium"] = pd.to_numeric(c["ltp"], errors="coerce")
            if "expiry" in c.columns:
                c["expiry"] = pd.to_datetime(c["expiry"], errors="coerce")
                c = c.dropna(subset=["expiry"])
                today = _now_ist().date()
                c = c[c["expiry"].dt.date >= today].copy()
                if c.empty:
                    continue
                valid_expiries = sorted(c["expiry"].dt.date.unique().tolist())[:4]
                c = c[c["expiry"].dt.date.isin(valid_expiries)].copy()
                if c.empty:
                    continue
            logger.warning(f"Using cached option chain fallback: {path}")
            return c
        return pd.DataFrame()

    def _estimate_atm_iv(self, chain: pd.DataFrame) -> float:
        if chain.empty or "iv" not in chain.columns:
            return 0.15
        c = chain.copy()
        c["iv"] = pd.to_numeric(c["iv"], errors="coerce")
        c["strike"] = pd.to_numeric(c["strike"], errors="coerce")
        c["underlying_price"] = pd.to_numeric(c["underlying_price"], errors="coerce")
        c = c.dropna(subset=["iv", "strike"])
        if c.empty:
            return 0.15
        spot = float(c["underlying_price"].dropna().iloc[0]) if c["underlying_price"].dropna().size else float(c["strike"].median())
        c["dist"] = (c["strike"] - spot).abs()
        return float(c.sort_values("dist").head(6)["iv"].median())

    def _series_for_underlying(self, underlying: str, now: datetime, iv: float) -> pd.Series:
        rows = self.iv_history.setdefault(underlying, [])
        rows.append({"timestamp": _to_iso(now), "iv": float(iv)})
        self.iv_history[underlying] = rows[-5000:]
        idx = []
        vals = []
        for r in self.iv_history[underlying]:
            dt = _parse_dt(r.get("timestamp"))
            if dt is None:
                continue
            idx.append(dt)
            vals.append(float(r.get("iv", 0.0) or 0.0))
        return pd.Series(vals, index=idx)

    def _aggressive_regime(self, state: RegimeState) -> Any:
        if not self.aggressive:
            return state.regime
        if state.regime != Regime.NEUTRAL:
            return state.regime
        return Regime.LOW_VOL_SELL if state.metrics.iv_rank >= 0.5 else Regime.RISING_VOL_BUY

    def _scale_strategy(self, strategy: OptionStrategy, multiplier: int) -> OptionStrategy:
        s = copy.deepcopy(strategy)
        m = max(1, int(multiplier))
        for leg in s.legs:
            leg.quantity = int(leg.quantity * m)
        s.max_loss *= m
        s.max_profit *= m
        s.net_credit_debit *= m
        s.portfolio_greeks = Greeks(
            delta=s.portfolio_greeks.delta * m,
            gamma=s.portfolio_greeks.gamma * m,
            theta=s.portfolio_greeks.theta * m,
            vega=s.portfolio_greeks.vega * m,
        )
        return s

    def _indicative_candidate_lots(
        self,
        strategy: OptionStrategy,
        objective: str,
        overlay: Dict[str, Any],
    ) -> int:
        """
        Estimate candidate lots for selection-time net-profit gating.
        Uses the same sizing stack as execution (capital scaling + aggressive + objective overlay).
        """
        lots = self.capital_scaling.get_position_size(self.scaling_state, strategy.max_loss)
        lots = int(max(1, round(lots)))
        if self.aggressive:
            lots = max(1, int(round(lots * 1.5)))
        size_overlay = self._objective_size_multiplier(objective, overlay)
        lots = max(1, int(round(lots * size_overlay)))
        return lots

    def _current_open_risk(self) -> float:
        return float(
            sum(
                abs(float(p.max_loss or 0.0))
                for p in self.position_manager.get_open_positions()
            )
        )

    def _portfolio_risk_cap_value(self) -> float:
        return float(
            max(0.0, self._current_net_equity() * self.config.survival_rules.portfolio_risk_cap_pct)
        )

    def _weekly_open_count(self) -> int:
        try:
            df = self.trade_ledger.read_all()
        except Exception as e:
            logger.warning("Could not read trade ledger for weekly count: %s", e)
            return 0
        if df.empty or "timestamp" not in df.columns:
            return 0
        now_ist = _now_ist()
        week_start_ist = (now_ist - timedelta(days=now_ist.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Normalize ledger timestamps to UTC-aware before comparing with week boundary.
        t = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        week_start_utc = pd.Timestamp(week_start_ist.astimezone(pytz.UTC))
        return int(((df["action"] == "open") & (t >= week_start_utc)).sum())

    def _strategy_snapshot(self, strategy: OptionStrategy) -> Dict[str, Any]:
        """Compact strategy object for dashboard diagnostics."""
        legs = []
        for leg in strategy.legs:
            legs.append({
                "strike": float(leg.strike),
                "option_type": str(leg.option_type),
                "action": str(leg.action),
                "quantity": int(leg.quantity),
                "premium": float(leg.premium),
                "expiry": str(getattr(leg.expiry, "date", lambda: leg.expiry)()),
            })
        return {
            "strategy_type": self._strategy_type_value(strategy),
            "underlying": strategy.underlying,
            "underlying_price": float(strategy.underlying_price),
            "days_to_expiry": int(strategy.days_to_expiry),
            "max_loss": float(strategy.max_loss),
            "max_profit": float(strategy.max_profit),
            "net_credit_debit": float(strategy.net_credit_debit),
            "risk_reward_ratio": float(strategy.risk_reward_ratio) if math.isfinite(strategy.risk_reward_ratio) else None,
            "greeks": {
                "delta": float(strategy.portfolio_greeks.delta),
                "gamma": float(strategy.portfolio_greeks.gamma),
                "theta": float(strategy.portfolio_greeks.theta),
                "vega": float(strategy.portfolio_greeks.vega),
            },
            "legs": legs,
        }

    def run_cycle(self) -> Dict[str, Any]:
        now = _now_ist()
        logger.info(f"Running integrated options cycle at {now.isoformat(timespec='seconds')}")
        self._write_live_engine_heartbeat(now)

        if self.market_hours_only and not self._is_market_hours():
            logger.info("Skipping cycle (outside market hours)")
            self._save_runtime_state()
            dashboard_state = self._build_dashboard_state(now, chain_cache={})
            self._write_json_atomic(self.dashboard_state_path, dashboard_state)
            self._write_daily_continuity_snapshot(now, dashboard_state)
            return {"status": "skipped", "reason": "outside_market_hours", "timestamp": _to_iso(now)}

        chain_cache: Dict[str, pd.DataFrame] = {}
        current_regimes: Dict[str, VolatilityRegime] = {}
        opened = 0
        closed = 0
        opened_position_ids: set[str] = set()
        self.portfolio_overlay = self._load_portfolio_overlay_context(now)
        cycle_underlyings = self._resolve_cycle_underlyings(self.portfolio_overlay)
        # Clear stale eligibility state from prior cycles; this cycle will set fresh outcome.
        self.last_trade_eligibility = {
            "signal_generated": False,
            "rejected": False,
            "violations": [],
            "timestamp": _to_iso(now),
        }
        self.last_eligibility_checks = []
        cycle_diag: Dict[str, Any] = {
            "timestamp": _to_iso(now),
            "underlyings_configured": list(cycle_underlyings),
            "portfolio_overlay": {
                "portfolio_objective": self.portfolio_overlay.get("portfolio_objective"),
                "hedge_intensity": self.portfolio_overlay.get("hedge_intensity"),
                "risk_on_probability": self.portfolio_overlay.get("risk_on_probability"),
                "cash_level": self.portfolio_overlay.get("cash_level"),
                "total_exposure": self.portfolio_overlay.get("total_exposure"),
                "regime": self.portfolio_overlay.get("regime"),
                "selected_stock_underlyings": self.portfolio_overlay.get("selected_stock_underlyings", []),
                "sector_index_underlyings": self.portfolio_overlay.get("sector_index_underlyings", []),
            },
            "underlyings": [],
        }
        accounting_integrity = self._accounting_integrity_report(now)
        cycle_diag["accounting_integrity"] = accounting_integrity
        governance_controls = self._load_governance_controls()
        cycle_diag["governance_controls"] = governance_controls
        block_new_risk_reasons: List[str] = []
        if self.recovery_mode:
            block_new_risk_reasons.append("recovery_mode_active")
        if accounting_integrity.get("block_new_risk"):
            block_new_risk_reasons.append("accounting_integrity_mismatch")
        if governance_controls.get("block_new_risk"):
            mode = str(governance_controls.get("current_mode", "unknown"))
            block_new_risk_reasons.append(f"governance_mode_block:{mode}")
        if block_new_risk_reasons:
            self.last_kill_switch = {
                "active": True,
                "reason": ",".join(block_new_risk_reasons),
            }
        else:
            self.last_kill_switch = {"active": False}

        precycle_alpha_os_intent = self._prime_alpha_os_precycle_intent(now)
        precycle_survival_lock = False
        if isinstance(precycle_alpha_os_intent, dict):
            diagnostics = precycle_alpha_os_intent.get("diagnostics", {}) or {}
            survival_core = diagnostics.get("survival_core", {}) if isinstance(diagnostics, dict) else {}
            survival_state = (survival_core.get("state", {}) or {}) if isinstance(survival_core, dict) else {}
            directives = survival_state.get("directives", {}) if isinstance(survival_state, dict) else {}
            precycle_survival_lock = bool((directives or {}).get("lock_new_risk", False))
        alpha_os_trade_multiplier = self._alpha_os_prev_cycle_multiplier()
        alpha_os_veto_active = self._alpha_os_prev_cycle_veto()
        cycle_diag["alpha_os_runtime"] = {
            "enabled": bool(self.alpha_os_enabled),
            "shadow_mode": bool(self.alpha_os_shadow_mode),
            "enforce_mode": bool(self.alpha_os_enforce_mode),
            "previous_cycle_trade_multiplier": float(alpha_os_trade_multiplier),
            "previous_cycle_veto": bool(alpha_os_veto_active),
            "precycle_intent_mode": str(precycle_alpha_os_intent.get("mode", "")) if isinstance(precycle_alpha_os_intent, dict) else "",
            "precycle_reason_codes": (
                list((precycle_alpha_os_intent.get("reason_codes", []) or []))[:12]
                if isinstance(precycle_alpha_os_intent, dict)
                else []
            ),
            "precycle_survival_lock": bool(precycle_survival_lock),
        }

        for underlying in cycle_underlyings:
            objective_ctx = self._objective_for_underlying(underlying, self.portfolio_overlay)
            decision: Dict[str, Any] = {
                "timestamp": _to_iso(now),
                "underlying": underlying,
                "instrument_key": self._resolve_key(underlying),
                "portfolio_objective": objective_ctx.get("objective"),
                "portfolio_reason": objective_ctx.get("reason"),
                "portfolio_weight": objective_ctx.get("weight"),
            }
            if block_new_risk_reasons:
                reason = ",".join(block_new_risk_reasons)
                self.last_kill_switch = {
                    "active": True,
                    "reason": reason,
                }
                decision.update(
                    {
                        "status": "blocked_risk_controls",
                        "reason": reason,
                    }
                )
                cycle_diag["underlyings"].append(decision)
                continue
            chain = self._fetch_chain(underlying)
            if chain.empty:
                decision.update({
                    "status": "no_chain_data",
                    "reason": "option_chain_unavailable",
                    "contracts": 0,
                })
                cycle_diag["underlyings"].append(decision)
                continue
            chain_cache[underlying] = chain
            expiries = (
                pd.to_datetime(chain.get("expiry"), errors="coerce")
                if "expiry" in chain.columns
                else pd.Series(dtype="datetime64[ns]")
            )
            expiry_values = (
                sorted(expiries.dropna().dt.date.astype(str).unique().tolist())
                if isinstance(expiries, pd.Series)
                else []
            )

            iv = self._estimate_atm_iv(chain)
            iv_series = self._series_for_underlying(underlying, now, iv)
            regime_state = self.regime_detector.detect_regime(chain, iv_series, underlying_regime="NORMAL")
            routed_regime = self._aggressive_regime(regime_state)
            current_regimes[underlying] = _to_regime(getattr(routed_regime, "value", routed_regime))
            spot = None
            if "underlying_price" in chain.columns:
                s = pd.to_numeric(chain["underlying_price"], errors="coerce").dropna()
                if not s.empty:
                    spot = float(s.median())

            decision.update({
                "status": "chain_loaded",
                "contracts": int(len(chain)),
                "expiries": expiry_values[:8],
                "spot": spot,
                "atm_iv": float(iv),
                "regime": str(getattr(regime_state.regime, "value", regime_state.regime)),
                "routed_regime": str(getattr(routed_regime, "value", routed_regime)),
                "iv_rank": float(regime_state.metrics.iv_rank),
                "confidence": float(regime_state.confidence),
            })

            self.regime_history.append({
                "timestamp": _to_iso(now),
                "underlying": underlying,
                "regime": str(getattr(regime_state.regime, "value", regime_state.regime)),
                "routed_regime": str(getattr(routed_regime, "value", routed_regime)),
                "iv_rank": float(regime_state.metrics.iv_rank),
                "confidence": float(regime_state.confidence),
            })

            strategy, selector = self._generate_portfolio_aware_strategy(
                underlying=underlying,
                routed_regime=routed_regime,
                option_chain=chain,
                objective=str(objective_ctx.get("objective") or "balanced_overlay"),
                overlay=self.portfolio_overlay,
            )
            decision["strategy_selector"] = selector
            if strategy is None:
                decision.update({
                    "status": "no_strategy",
                    "reason": selector.get("reason") or "strategy_generator_returned_none",
                })
                cycle_diag["underlyings"].append(decision)
                continue
            if not strategy.is_valid:
                decision.update({
                    "status": "strategy_invalid",
                    "reason": "strategy_validation_failed",
                    "strategy": self._strategy_snapshot(strategy),
                    "validation_errors": list(strategy.validation_errors or []),
                })
                cycle_diag["underlyings"].append(decision)
                continue
            decision["strategy"] = self._strategy_snapshot(strategy)
            strategy_type_token = self._strategy_type_value(strategy)
            blocked_by_alpha, alpha_block_reason = self._alpha_os_strategy_blocked(strategy_type_token)
            alpha_strategy_multiplier = self._alpha_os_strategy_size_multiplier(strategy_type_token)
            decision["alpha_os_strategy_gate"] = {
                "strategy_type": strategy_type_token,
                "blocked": bool(blocked_by_alpha),
                "reason": alpha_block_reason,
                "size_multiplier": float(alpha_strategy_multiplier),
            }
            if blocked_by_alpha:
                decision.update({
                    "status": "blocked_alpha_os_strategy_gate",
                    "reason": alpha_block_reason or "alpha_os_strategy_weight_block",
                })
                cycle_diag["underlyings"].append(decision)
                continue

            eligibility = self.eligibility_validator.validate_trade(strategy, regime_state, chain)
            eligibility_checks = [{
                "check": r.value,
                "passed": bool(v),
                "detail": "ok" if v else "failed",
            } for r, v in eligibility.rule_results.items()]
            self.last_trade_eligibility = {
                "signal_generated": bool(eligibility.is_eligible),
                "rejected": not bool(eligibility.is_eligible),
                "strategy_type": self._strategy_type_value(strategy),
                "violations": eligibility.violations,
                "regime": str(getattr(routed_regime, "value", routed_regime)),
                "timestamp": _to_iso(now),
            }
            self.last_eligibility_checks = eligibility_checks
            decision["eligibility"] = {
                "is_eligible": bool(eligibility.is_eligible),
                "size_adjustment": float(eligibility.size_adjustment),
                "violations": list(eligibility.violations or []),
                "checks": eligibility_checks,
            }

            if not eligibility.is_eligible:
                self.event_publisher.publish_eligibility_rejected(
                    strategy_type=self._strategy_type_value(strategy),
                    violations=eligibility.violations,
                    regime=str(getattr(routed_regime, "value", routed_regime)),
                )
                decision.update({
                    "status": "rejected_eligibility",
                    "reason": "; ".join(eligibility.violations) if eligibility.violations else "eligibility_rejected",
                })
                cycle_diag["underlyings"].append(decision)
                continue

            if alpha_os_veto_active:
                decision.update({
                    "status": "blocked_alpha_os_veto",
                    "reason": "alpha_os_previous_cycle_risk_veto",
                })
                cycle_diag["underlyings"].append(decision)
                continue
            if self.alpha_os_enabled and self.alpha_os_enforce_mode and precycle_survival_lock:
                decision.update({
                    "status": "blocked_survival_core_lock",
                    "reason": "alpha_os_survival_core_lock_new_risk",
                })
                cycle_diag["underlyings"].append(decision)
                continue

            weekly_count = self._weekly_open_count()
            weekly_limit = int(self.config.survival_rules.max_trades_per_week)
            if weekly_count >= weekly_limit:
                self.last_kill_switch = {
                    "active": True,
                    "reason": f"weekly trade limit reached ({weekly_limit})",
                }
                decision.update({
                    "status": "blocked_weekly_limit",
                    "reason": self.last_kill_switch["reason"],
                    "weekly_usage": {
                        "trades_used": weekly_count,
                        "trades_limit": weekly_limit,
                    },
                })
                cycle_diag["underlyings"].append(decision)
                continue

            lots = self.capital_scaling.get_position_size(self.scaling_state, strategy.max_loss)
            lots = int(max(1, round(lots * float(eligibility.size_adjustment))))
            if self.aggressive:
                lots = max(1, int(round(lots * 1.5)))
            size_overlay = self._objective_size_multiplier(
                str(objective_ctx.get("objective") or "balanced_overlay"),
                self.portfolio_overlay,
            )
            lots = max(1, int(round(lots * size_overlay)))
            lots = max(1, int(round(lots * alpha_strategy_multiplier)))
            if self.alpha_os_enabled and self.alpha_os_enforce_mode:
                lots = max(1, int(round(lots * alpha_os_trade_multiplier)))
            # Enforce risk-budget sizing before kill-switch evaluation so oversized
            # proposals do not trip a global portfolio risk kill switch.
            unit_risk = max(1.0, abs(float(strategy.max_loss or 0.0)))
            risk_cap = self._portfolio_risk_cap_value()
            open_risk = self._current_open_risk()
            remaining_risk = max(0.0, risk_cap - open_risk)
            affordable_lots = int(remaining_risk // unit_risk)
            decision["risk_budget"] = {
                "risk_cap": float(risk_cap),
                "open_risk": float(open_risk),
                "remaining_risk": float(remaining_risk),
                "unit_risk": float(unit_risk),
            }
            if affordable_lots <= 0:
                decision.update({
                    "status": "deferred_risk_budget",
                    "reason": (
                        f"remaining risk budget ₹{remaining_risk:,.0f} below minimum "
                        f"tradable risk ₹{unit_risk:,.0f}"
                    ),
                    "risk_budget": {
                        **decision["risk_budget"],
                        "requested_lots": int(lots),
                        "affordable_lots": int(affordable_lots),
                    },
                })
                cycle_diag["underlyings"].append(decision)
                continue
            if lots > affordable_lots:
                decision["risk_budget"]["requested_lots"] = int(lots)
                decision["risk_budget"]["affordable_lots"] = int(affordable_lots)
                lots = max(1, int(affordable_lots))
            strategy = self._scale_strategy(strategy, lots)
            decision["position_size_multiplier"] = lots
            decision["portfolio_size_multiplier"] = float(size_overlay)
            post_scale_gate = self._passes_net_profit_gate(
                strategy,
                objective=str(objective_ctx.get("objective") or "balanced_overlay"),
                overlay=self.portfolio_overlay,
            )
            decision["net_profit_gate"] = {
                "passed": bool(post_scale_gate.get("passed", False)),
                "expected_net_pnl": float(post_scale_gate.get("expected_net_pnl", 0.0) or 0.0),
                "min_threshold": float(post_scale_gate.get("min_threshold", 0.0) or 0.0),
                "override_applied": bool(post_scale_gate.get("override_applied", False)),
            }
            if not bool(post_scale_gate.get("passed", False)):
                exp_net = float(post_scale_gate.get("expected_net_pnl", 0.0) or 0.0)
                min_thr = float(post_scale_gate.get("min_threshold", 0.0) or 0.0)
                risk_budget = decision.get("risk_budget", {}) if isinstance(decision.get("risk_budget"), dict) else {}
                requested_lots = int(risk_budget.get("requested_lots", lots) or lots)
                affordable_lots = int(risk_budget.get("affordable_lots", lots) or lots)
                if affordable_lots < requested_lots:
                    decision.update({
                        "status": "deferred_risk_budget",
                        "reason": (
                            f"risk budget capped size to {affordable_lots} lots; "
                            f"expected net ₹{exp_net:,.0f} below threshold ₹{min_thr:,.0f}"
                        ),
                    })
                else:
                    decision.update({
                        "status": "rejected_net_profitability",
                        "reason": f"expected net ₹{exp_net:,.0f} below threshold ₹{min_thr:,.0f}",
                    })
                cycle_diag["underlyings"].append(decision)
                continue

            open_survival = [
                SurvivalPosition(
                    position_id=p.position_id,
                    strategy_type=p.strategy_type,
                    max_loss=p.max_loss,
                    entry_time=p.entry_time,
                    is_short_vol=p.is_short_vol(),
                )
                for p in self.position_manager.get_open_positions()
            ]
            closed_survival = [
                SurvivalTrade(
                    trade_id=p.position_id,
                    strategy_type=p.strategy_type,
                    entry_time=p.entry_time,
                    exit_time=p.exit_time,
                    max_loss=p.max_loss,
                    realized_pnl=p.realized_pnl,
                    is_short_vol=p.is_short_vol(),
                )
                for p in self.position_manager.get_closed_positions()
            ]
            ytd = self.pnl_tracker.get_ytd_summary()
            perf = PerformanceMetrics(
                current_equity=self.scaling_state.current_equity,
                ytd_gross_profits=ytd["ytd_gross_profits"],
                ytd_tax_liability=ytd["ytd_tax_liability"],
                cash_buffer=ytd["cash_buffer"],
            )
            proposed = SurvivalPosition(
                position_id=f"PROPOSED_{int(time.time())}",
                strategy_type=self._strategy_type_value(strategy),
                max_loss=strategy.max_loss,
                entry_time=now,
                is_short_vol=self._is_short_vol_strategy(strategy),
            )
            ks = self.survival_rules.check_all_kill_switches(
                open_positions=open_survival,
                closed_trades=closed_survival,
                performance=perf,
                current_time=now,
                proposed_trade=proposed,
                portfolio_risk_cap_value=self._portfolio_risk_cap_value(),
            )
            self.last_kill_switch = {
                "active": bool(ks.active),
                "reason": ks.reason,
                "triggered_rules": ks.triggered_rules,
                "cooldown_until": _to_iso(ks.cooldown_until),
            }
            if ks.active:
                decision.update({
                    "status": "blocked_kill_switch",
                    "reason": ks.reason,
                    "kill_switch": self.last_kill_switch,
                })
                cycle_diag["underlyings"].append(decision)
                continue

            open_time = _now_ist()
            position = self.position_manager.open_position(strategy, open_time)
            position.underlying = self._normalize_underlying_symbol(
                getattr(position, "underlying", ""),
                fallback=underlying,
            )
            self.trade_ledger.write_position_open(position)
            self.event_publisher.publish_position_opened(
                position_id=position.position_id,
                strategy_type=position.strategy_type,
                max_loss=position.max_loss,
                entry_time=position.entry_time,
                legs=[{"strike": leg.strike, "option_type": leg.option_type, "action": leg.action, "quantity": leg.quantity} for leg in position.legs],
            )
            opened += 1
            opened_position_ids.add(position.position_id)
            decision.update({
                "status": "opened_position",
                "position_id": position.position_id,
                "position_underlying": position.underlying,
                "opened_max_loss": float(position.max_loss),
                "opened_credit_debit": float(position.entry_credit_debit),
            })
            cycle_diag["underlyings"].append(decision)

        merged_chain = pd.concat(chain_cache.values(), ignore_index=True) if chain_cache else pd.DataFrame()
        profitable_closes = 0
        for pos in list(self.position_manager.get_open_positions()):
            if pos.position_id in opened_position_ids:
                # Avoid instant open->close churn in the same evaluation cycle.
                continue
            if not merged_chain.empty:
                self.position_manager.update_position_mtm(pos, merged_chain, now)
            default_regime_key = cycle_underlyings[0] if cycle_underlyings else (self.underlyings[0] if self.underlyings else "NIFTY")
            pos.underlying = self._normalize_underlying_symbol(
                getattr(pos, "underlying", ""),
                fallback=default_regime_key,
            )
            regime_key = str(getattr(pos, "underlying", "") or default_regime_key).strip().upper()
            regime = current_regimes.get(regime_key, current_regimes.get(default_regime_key, VolatilityRegime.TRANSITION))
            exit_signal = self.position_manager.check_exit_conditions(pos, regime, now.date())
            if not exit_signal:
                continue
            closed_pos = self.position_manager.close_position(
                pos,
                exit_time=now,
                exit_reason=exit_signal.reason.value,
            )
            trade_pnl = self.pnl_tracker.calculate_trade_pnl(closed_pos)
            self.pnl_tracker.update_ytd_tracking(trade_pnl)
            self.cumulative_net_pnl += trade_pnl.net_pnl
            if trade_pnl.net_pnl > 0:
                profitable_closes += 1
            self.trade_ledger.write_position_close(closed_pos, trade_pnl)
            self.event_publisher.publish_position_closed(
                position_id=closed_pos.position_id,
                strategy_type=closed_pos.strategy_type,
                realized_pnl=float(closed_pos.realized_pnl or 0.0),
                net_pnl=float(trade_pnl.net_pnl),
                exit_reason=str(closed_pos.exit_reason or "unknown"),
                hold_duration_days=float(closed_pos.days_held),
            )
            closed += 1

        summary = self.position_manager.get_summary()
        current_equity = float(self._current_net_equity())
        prior_risk_pct = float(self.scaling_state.current_risk_pct) if self.scaling_state is not None else None
        self.scaling_state = self.capital_scaling.update_state(
            self.scaling_state,
            current_equity=current_equity,
            recent_trades_profitable=profitable_closes,
        )
        disable_scaling_up = bool(
            self.recovery_mode
            or (governance_controls.get("mode_constraints", {}) or {}).get("disable_scaling_up", False)
        )
        if disable_scaling_up and self.scaling_state is not None and prior_risk_pct is not None:
            self.scaling_state.current_risk_pct = min(
                float(self.scaling_state.current_risk_pct),
                float(prior_risk_pct),
            )

        g = summary["portfolio_greeks"]
        self.greeks_history.append({
            "timestamp": _to_iso(now),
            "delta": g.delta,
            "gamma": g.gamma,
            "theta": g.theta,
            "vega": g.vega,
        })
        self.greeks_history = self.greeks_history[-5000:]
        cycle_diag["opened"] = int(opened)
        cycle_diag["closed"] = int(closed)
        cycle_diag["open_positions"] = int(summary.get("open_positions_count", 0) or 0)
        cycle_diag["summary"] = {
            "processed_underlyings": len(cycle_diag.get("underlyings", [])),
            "generated_strategies": int(sum(1 for d in cycle_diag.get("underlyings", []) if d.get("strategy"))),
            "rejections": int(sum(1 for d in cycle_diag.get("underlyings", []) if str(d.get("status", "")).startswith("rejected"))),
            "blocked": int(sum(1 for d in cycle_diag.get("underlyings", []) if str(d.get("status", "")).startswith("blocked"))),
        }
        self.latest_cycle_diagnostics = cycle_diag
        self.cycle_decision_history.extend([
            {
                "timestamp": _to_iso(now),
                "underlying": d.get("underlying"),
                "status": d.get("status"),
                "reason": d.get("reason"),
                "strategy_type": ((d.get("strategy") or {}).get("strategy_type")),
                "objective": d.get("portfolio_objective"),
                "selected_source": ((d.get("strategy_selector") or {}).get("selected_source")),
                "contracts": int(d.get("contracts", 0) or 0),
                "regime": d.get("routed_regime") or d.get("regime"),
                "violations": ((d.get("eligibility") or {}).get("violations") or []),
            }
            for d in cycle_diag.get("underlyings", [])
        ])
        self.cycle_decision_history = self.cycle_decision_history[-5000:]

        dashboard_state = self._build_dashboard_state(now, chain_cache)
        alpha_os_intent = self._evaluate_alpha_os_cycle(
            now=now,
            dashboard_state=dashboard_state,
            chain_cache=chain_cache,
            current_equity=current_equity,
        )
        if alpha_os_intent:
            dashboard_state["alpha_os"] = alpha_os_intent
            self._append_alpha_os_artifacts(alpha_os_intent)
        central_pnl = self._write_centralized_pnl_artifacts(now, dashboard_state)
        dashboard_state["centralized_pnl"] = central_pnl
        self._write_json_atomic(self.dashboard_state_path, dashboard_state)
        self._write_volatility_snapshot(now, dashboard_state, chain_cache)
        self._write_historical_artifacts(now, chain_cache)
        self._write_live_engine_heartbeat(now)
        self._write_daily_continuity_snapshot(now, dashboard_state)
        self._save_runtime_state()

        return {
            "status": "ok",
            "timestamp": _to_iso(now),
            "opened": opened,
            "closed": closed,
            "open_positions": summary.get("open_positions_count", 0),
            "alpha_os_mode": (
                "disabled"
                if not self.alpha_os_enabled
                else ("enforce" if self.alpha_os_enforce_mode else "shadow")
            ),
        }

    def _build_dashboard_state(self, now: datetime, chain_cache: Optional[Dict[str, pd.DataFrame]] = None) -> Dict[str, Any]:
        positions = self.position_manager.get_open_positions()
        closed = self.position_manager.get_closed_positions()
        greeks = self.position_manager.calculate_portfolio_greeks()
        trade_metrics = self._trade_metrics(closed)
        ytd = self.pnl_tracker.get_ytd_summary()
        market_snapshot = self._extract_market_snapshot(chain_cache or {})
        centralized_pnl = self._read_json_file(PROJECT_ROOT / "data/processed/v3_centralized_pnl.json")
        eligibility = dict(self.last_trade_eligibility or {})
        ts = _parse_dt(eligibility.get("timestamp")) if isinstance(eligibility, dict) else None
        if ts and (datetime.utcnow() - ts).total_seconds() > 45 * 60:
            eligibility = {
                "signal_generated": False,
                "rejected": False,
                "violations": [],
                "timestamp": _to_iso(now),
                "stale": True,
            }

        return {
            "timestamp": _to_iso(now),
            "schema_version": "2.1.0",
            "continuity_mode": True,
            "recovery_mode": bool(self.recovery_mode),
            "current_regime": self.regime_history[-1]["routed_regime"] if self.regime_history else "neutral",
            "regime_metrics": self.regime_history[-1] if self.regime_history else {},
            "active_positions": [
                {
                    "position_id": p.position_id,
                    "underlying": str(getattr(p, "underlying", "") or ""),
                    "strategy_type": p.strategy_type,
                    "max_loss": p.max_loss,
                    "entry_time": _to_iso(p.entry_time),
                    "unrealized_pnl": p.unrealized_pnl,
                    "current_value": p.current_value,
                    "greeks": p.greeks.__dict__ if p.greeks else {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0},
                }
                for p in positions
            ],
            "closed_positions": [
                {
                    "position_id": p.position_id,
                    "underlying": str(getattr(p, "underlying", "") or ""),
                    "strategy_type": p.strategy_type,
                    "entry_time": _to_iso(p.entry_time),
                    "exit_time": _to_iso(p.exit_time),
                    "realized_pnl": float(p.realized_pnl or 0.0),
                    "exit_reason": p.exit_reason,
                    "hold_duration_days": p.days_held,
                }
                for p in closed[-200:]
            ],
            "portfolio_greeks": greeks.__dict__,
            "greeks_history": self.greeks_history[-500:],
            "kill_switch_status": self.last_kill_switch,
            "active_limits": self.limit_profile,
            "weekly_risk_usage": {
                "trades_used": self._weekly_open_count(),
                "trades_limit": int(self.config.survival_rules.max_trades_per_week),
                "risk_used": float(sum(p.max_loss for p in positions)),
                "risk_limit": float(self._portfolio_risk_cap_value()),
            },
            "capital_scaling": {
                "current_risk_pct": self.scaling_state.risk_per_trade_pct if self.scaling_state else 0.01,
                "equity_high_water_mark": self.scaling_state.equity_high_water_mark if self.scaling_state else self.config.capital.base_capital,
                "current_equity": self.scaling_state.current_equity if self.scaling_state else self.config.capital.base_capital,
            },
            "portfolio_risk_usage": {
                "total_risk": float(sum(p.max_loss for p in positions)),
                "risk_cap": float(self._portfolio_risk_cap_value()),
                "risk_pct": (
                    float(sum(p.max_loss for p in positions) / self._current_net_equity())
                    if self._current_net_equity()
                    else 0.0
                ),
                "risk_cap_pct": float(self.config.survival_rules.portfolio_risk_cap_pct),
            },
            "base_capital": float(self.config.capital.base_capital),
            "realized_net_pnl": float(self.cumulative_net_pnl),
            "unrealized_pnl": float(self._current_unrealized_pnl()),
            "net_equity": float(self._current_net_equity()),
            "week_start_equity": float(self.week_start_equity if self.week_start_equity is not None else self._current_net_equity()),
            "risk_cap_value": float(self._portfolio_risk_cap_value()),
            "risk_remaining": float(max(0.0, self._portfolio_risk_cap_value() - self._current_open_risk())),
            "last_reconciled_at": self.last_reconciled_at,
            "trade_eligibility": eligibility,
            "eligibility_checks": self.last_eligibility_checks,
            "trade_metrics": trade_metrics,
            "ytd": ytd,
            "centralized_pnl": centralized_pnl,
            "market_snapshot": market_snapshot,
            "portfolio_overlay": self.portfolio_overlay,
            "options_cycle": self.latest_cycle_diagnostics,
            "options_decision_history": self.cycle_decision_history[-120:],
            "alpha_os": self.alpha_os_last_intent,
        }

    def _trade_metrics(self, closed_positions: List[Position]) -> Dict[str, Any]:
        if not closed_positions:
            return {"total_trades": 0, "win_rate": 0.0, "avg_profit": 0.0, "avg_loss": 0.0, "profit_factor": 0.0}
        pnl = [float(p.realized_pnl or 0.0) for p in closed_positions]
        wins = [x for x in pnl if x > 0]
        losses = [x for x in pnl if x < 0]
        return {
            "total_trades": len(pnl),
            "win_rate": (len(wins) / len(pnl)) if pnl else 0.0,
            "avg_profit": (sum(wins) / len(wins)) if wins else 0.0,
            "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
            "profit_factor": (sum(wins) / abs(sum(losses))) if losses else 0.0,
        }

    @staticmethod
    def _latest_frame_row(df: pd.DataFrame, date_col: str) -> Optional[pd.Series]:
        if not isinstance(df, pd.DataFrame) or df.empty or date_col not in df.columns:
            return None
        d = df.copy()
        d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
        d = d.dropna(subset=[date_col]).sort_values(date_col)
        if d.empty:
            return None
        return d.iloc[-1]

    def _build_centralized_pnl_snapshot(self, now: datetime, state: Dict[str, Any]) -> Dict[str, Any]:
        options_ytd = state.get("ytd", {}) if isinstance(state.get("ytd"), dict) else {}
        options_active = state.get("active_positions", []) if isinstance(state.get("active_positions"), list) else []
        options_closed = state.get("closed_positions", []) if isinstance(state.get("closed_positions"), list) else []
        options_unrealized = float(sum(float(p.get("unrealized_pnl", 0.0) or 0.0) for p in options_active))
        options_realized = float(sum(float(p.get("realized_pnl", 0.0) or 0.0) for p in options_closed))
        options_ytd_net = float(options_ytd.get("ytd_net_pnl", 0.0) or 0.0)

        portfolio_path = PROJECT_ROOT / "data/portfolio/pnl_on_paper.parquet"
        portfolio_equity = 0.0
        portfolio_daily_return = 0.0
        portfolio_total_pnl = 0.0
        portfolio_as_of = None
        if portfolio_path.exists():
            try:
                pdf = pd.read_parquet(portfolio_path)
                latest = self._latest_frame_row(pdf, "Date")
                if latest is not None:
                    portfolio_equity = float(pd.to_numeric(latest.get("Equity", 0.0), errors="coerce") or 0.0)
                    portfolio_daily_return = float(pd.to_numeric(latest.get("Return", 0.0), errors="coerce") or 0.0)
                    portfolio_as_of = str(pd.to_datetime(latest.get("Date"), errors="coerce"))
                if isinstance(pdf, pd.DataFrame) and not pdf.empty and "Equity" in pdf.columns:
                    start_eq = float(pd.to_numeric(pdf["Equity"], errors="coerce").dropna().iloc[0])
                    portfolio_total_pnl = portfolio_equity - start_eq
            except Exception:
                pass

        shadow_path = PROJECT_ROOT / "data/processed/shadow_pnl_series.parquet"
        shadow_value = 0.0
        shadow_daily_pnl = 0.0
        shadow_daily_return = 0.0
        shadow_total_pnl = 0.0
        shadow_as_of = None
        if shadow_path.exists():
            try:
                sdf = pd.read_parquet(shadow_path)
                key_col = "timestamp" if "timestamp" in sdf.columns else ("date" if "date" in sdf.columns else None)
                if key_col:
                    latest = self._latest_frame_row(sdf, key_col)
                else:
                    latest = None
                if latest is not None:
                    shadow_value = float(pd.to_numeric(latest.get("portfolio_value", 0.0), errors="coerce") or 0.0)
                    shadow_daily_pnl = float(pd.to_numeric(latest.get("daily_pnl", 0.0), errors="coerce") or 0.0)
                    shadow_daily_return = float(pd.to_numeric(latest.get("daily_return", 0.0), errors="coerce") or 0.0)
                    shadow_as_of = str(pd.to_datetime(latest.get(key_col), errors="coerce"))
                if isinstance(sdf, pd.DataFrame) and not sdf.empty and "portfolio_value" in sdf.columns:
                    start_val = float(pd.to_numeric(sdf["portfolio_value"], errors="coerce").dropna().iloc[0])
                    shadow_total_pnl = shadow_value - start_val
            except Exception:
                pass

        aggregate_net = float(options_ytd_net + portfolio_total_pnl + shadow_total_pnl)

        snapshot = {
            "timestamp": _to_iso(now),
            "components": {
                "options_live": {
                    "unrealized_pnl": options_unrealized,
                    "realized_pnl_closed_positions": options_realized,
                    "ytd_net_pnl_after_costs_and_tax": options_ytd_net,
                    "ytd_tax_liability": float(options_ytd.get("ytd_tax_liability", 0.0) or 0.0),
                    "ytd_total_costs": float(options_ytd.get("ytd_total_costs", 0.0) or 0.0),
                    "active_positions": int(len(options_active)),
                    "closed_positions": int(len(options_closed)),
                },
                "v3_weekly_portfolio": {
                    "equity": portfolio_equity,
                    "daily_return": portfolio_daily_return,
                    "total_pnl_from_series_start": portfolio_total_pnl,
                    "as_of": portfolio_as_of,
                },
                "shadow_portfolio": {
                    "portfolio_value": shadow_value,
                    "daily_pnl": shadow_daily_pnl,
                    "daily_return": shadow_daily_return,
                    "total_pnl_from_series_start": shadow_total_pnl,
                    "as_of": shadow_as_of,
                },
            },
            "aggregates": {
                "combined_net_pnl_estimate": aggregate_net,
                "options_share_pct": (options_ytd_net / aggregate_net) if abs(aggregate_net) > 1e-9 else 0.0,
                "weekly_portfolio_share_pct": (portfolio_total_pnl / aggregate_net) if abs(aggregate_net) > 1e-9 else 0.0,
                "shadow_share_pct": (shadow_total_pnl / aggregate_net) if abs(aggregate_net) > 1e-9 else 0.0,
                "tax_aware_net_gate": aggregate_net >= 0.0,
            },
        }
        return snapshot

    def _write_centralized_pnl_artifacts(self, now: datetime, state: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self._build_centralized_pnl_snapshot(now, state)
        out_json = PROJECT_ROOT / "data/processed/v3_centralized_pnl.json"
        out_parquet = PROJECT_ROOT / "data/processed/v3_centralized_pnl_timeseries.parquet"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(out_json, snapshot)

        row = {
            "timestamp": pd.to_datetime(snapshot.get("timestamp"), errors="coerce"),
            "options_ytd_net_pnl": float(((snapshot.get("components", {}) or {}).get("options_live", {}) or {}).get("ytd_net_pnl_after_costs_and_tax", 0.0) or 0.0),
            "options_unrealized_pnl": float(((snapshot.get("components", {}) or {}).get("options_live", {}) or {}).get("unrealized_pnl", 0.0) or 0.0),
            "weekly_portfolio_total_pnl": float(((snapshot.get("components", {}) or {}).get("v3_weekly_portfolio", {}) or {}).get("total_pnl_from_series_start", 0.0) or 0.0),
            "weekly_portfolio_equity": float(((snapshot.get("components", {}) or {}).get("v3_weekly_portfolio", {}) or {}).get("equity", 0.0) or 0.0),
            "shadow_total_pnl": float(((snapshot.get("components", {}) or {}).get("shadow_portfolio", {}) or {}).get("total_pnl_from_series_start", 0.0) or 0.0),
            "shadow_portfolio_value": float(((snapshot.get("components", {}) or {}).get("shadow_portfolio", {}) or {}).get("portfolio_value", 0.0) or 0.0),
            "combined_net_pnl_estimate": float((snapshot.get("aggregates", {}) or {}).get("combined_net_pnl_estimate", 0.0) or 0.0),
        }
        ts_df = pd.DataFrame([row]).dropna(subset=["timestamp"])
        if out_parquet.exists():
            try:
                old = pd.read_parquet(out_parquet)
                if isinstance(old, pd.DataFrame) and not old.empty:
                    ts_df = pd.concat([old, ts_df], ignore_index=True)
            except Exception:
                pass
        ts_df = ts_df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last").tail(10_000)
        ts_df.to_parquet(out_parquet, index=False)
        return snapshot

    def _extract_market_snapshot(self, chain_cache: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Extract non-zero market diagnostics even when no trade is opened."""
        contracts = 0
        nifty_price = None
        banknifty_price = None

        for underlying, chain in (chain_cache or {}).items():
            if chain is None or chain.empty:
                continue
            contracts += int(len(chain))
            spot = pd.to_numeric(chain.get("underlying_price"), errors="coerce") if "underlying_price" in chain.columns else pd.Series(dtype=float)
            if not spot.empty:
                px = float(spot.dropna().median()) if spot.dropna().size else None
                if px is not None and str(underlying).upper() == "NIFTY":
                    nifty_price = px
                if px is not None and str(underlying).upper() == "BANKNIFTY":
                    banknifty_price = px

        # Fall back to latest market data artifact.
        market_data_path = self.options_live_dir / "market_data_latest.json"
        if market_data_path.exists():
            try:
                md = json.loads(market_data_path.read_text())
                indices = md.get("indices", {}) if isinstance(md, dict) else {}
                if nifty_price is None:
                    nifty_price = float((indices.get("NIFTY", {}) or {}).get("current_price"))
                if banknifty_price is None:
                    banknifty_price = float((indices.get("BANKNIFTY", {}) or {}).get("current_price"))
            except Exception:
                pass

        # Fallback to cached latest option-chain parquet files.
        if contracts <= 0:
            cached_candidates = sorted(self.options_live_dir.glob("*_options_latest.parquet"))
            for path in cached_candidates:
                try:
                    df = pd.read_parquet(path)
                except Exception:
                    continue
                if df is None or df.empty:
                    continue
                contracts += int(len(df))
                if nifty_price is None and "nifty" in path.name.lower():
                    spot = pd.to_numeric(df.get("underlying_price"), errors="coerce") if "underlying_price" in df.columns else pd.Series(dtype=float)
                    if not spot.empty and spot.dropna().size:
                        nifty_price = float(spot.dropna().median())
                if banknifty_price is None and "banknifty" in path.name.lower():
                    spot = pd.to_numeric(df.get("underlying_price"), errors="coerce") if "underlying_price" in df.columns else pd.Series(dtype=float)
                    if not spot.empty and spot.dropna().size:
                        banknifty_price = float(spot.dropna().median())

        # If current cycle had no chains, preserve last non-zero market coverage.
        prev_path = self.snapshot_dir / "current_state.json"
        if prev_path.exists():
            try:
                prev = json.loads(prev_path.read_text())
                prev_md = prev.get("market_data", {}) if isinstance(prev, dict) else {}
                if contracts <= 0:
                    contracts = int(prev_md.get("option_contracts", 0) or 0)
                if nifty_price is None:
                    nifty_price = prev_md.get("NIFTY_price")
                if banknifty_price is None:
                    banknifty_price = prev_md.get("BANKNIFTY_price")
            except Exception:
                pass

        return {
            "option_contracts": int(max(0, contracts)),
            "NIFTY_price": float(nifty_price) if nifty_price is not None else None,
            "BANKNIFTY_price": float(banknifty_price) if banknifty_price is not None else None,
        }

    def _write_volatility_snapshot(self, now: datetime, state: Dict[str, Any], chain_cache: Optional[Dict[str, pd.DataFrame]] = None) -> None:
        positions = state["active_positions"]
        greeks = state["portfolio_greeks"]
        trade_metrics = state["trade_metrics"]
        unrealized = sum(float(p.get("unrealized_pnl", 0.0) or 0.0) for p in positions)
        realized = sum(float(p.get("realized_pnl", 0.0) or 0.0) for p in state["closed_positions"])
        market_snapshot = self._extract_market_snapshot(chain_cache or {})
        snap = {
            "timestamp": _to_iso(now),
            "cycle": int(time.time()),
            "regime": state.get("current_regime", "transition"),
            "market_data": market_snapshot,
            "portfolio_greeks": greeks,
            "total_pnl": realized + unrealized,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "today_pnl": unrealized,
            "positions": [
                {
                    "symbol": p["position_id"],
                    "option_type": p.get("strategy_type"),
                    "quantity": 1,
                    "pnl": p.get("unrealized_pnl", 0.0),
                    "delta": p.get("greeks", {}).get("delta", 0.0),
                    "gamma": p.get("greeks", {}).get("gamma", 0.0),
                    "vega": p.get("greeks", {}).get("vega", 0.0),
                    "theta": p.get("greeks", {}).get("theta", 0.0),
                    "notional": abs(float(p.get("max_loss", 0.0) or 0.0)),
                }
                for p in positions
            ],
            "performance_metrics": {
                "total_trades": trade_metrics["total_trades"],
                "win_rate": trade_metrics["win_rate"],
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
            },
            "risk_metrics": {
                "var_95": state.get("portfolio_risk_usage", {}).get("total_risk", 0.0),
                "cvar_95": state.get("portfolio_risk_usage", {}).get("total_risk", 0.0) * 1.25,
                "max_drawdown": 0.0,
                "current_drawdown": 0.0,
            },
            "strategy_allocations": self._strategy_allocations(state["active_positions"]),
            "centralized_pnl": state.get("centralized_pnl", {}),
            "execution_metrics": {
                "fill_rate": 1.0,
                "avg_slippage": 0.0,
                "total_orders": state["trade_metrics"]["total_trades"] + state["weekly_risk_usage"]["trades_used"],
                "rejected_orders": 0,
            },
            "alpha_os": state.get("alpha_os", {}),
        }
        self._write_json_atomic(self.snapshot_dir / "current_state.json", snap)
        self._write_json_atomic(self.snapshot_dir / f"state_{now.strftime('%Y%m%d_%H%M%S')}.json", snap)

    def _strategy_allocations(self, positions: List[Dict[str, Any]]) -> Dict[str, float]:
        if not positions:
            return {"Short Vol": 0.0, "Long Vol": 0.0}
        total = sum(abs(float(p.get("max_loss", 0.0) or 0.0)) for p in positions)
        if total <= 0:
            return {"Short Vol": 0.0, "Long Vol": 0.0}
        short_risk = sum(
            abs(float(p.get("max_loss", 0.0) or 0.0))
            for p in positions
            if self._is_short_vol_type(str(p.get("strategy_type", "") or ""))
        )
        long_risk = total - short_risk
        return {"Short Vol": short_risk / total, "Long Vol": long_risk / total}

    def _write_historical_artifacts(self, now: datetime, chain_cache: Dict[str, pd.DataFrame]) -> None:
        iv_rows = []
        for u, rows in self.iv_history.items():
            for r in rows[-2000:]:
                iv_rows.append({"timestamp": r.get("timestamp"), "underlying": u, "iv": r.get("iv")})
        if iv_rows:
            iv_df = pd.DataFrame(iv_rows)
            iv_df["timestamp"] = pd.to_datetime(iv_df["timestamp"], errors="coerce")
            iv_df = iv_df.dropna(subset=["timestamp"]).sort_values("timestamp")
            iv_df.to_parquet(PROJECT_ROOT / self.config.data_paths.iv_history, index=False)

        if self.regime_history:
            r_df = pd.DataFrame(self.regime_history[-10000:])
            r_df["timestamp"] = pd.to_datetime(r_df["timestamp"], errors="coerce")
            r_df = r_df.dropna(subset=["timestamp"]).sort_values("timestamp")
            r_df.to_parquet(PROJECT_ROOT / self.config.data_paths.regime_history, index=False)

        pos_rows = []
        for p in self.position_manager.get_open_positions():
            pos_rows.append({
                "timestamp": now,
                "position_id": p.position_id,
                "strategy_type": p.strategy_type,
                "entry_time": p.entry_time,
                "expiry": p.expiry,
                "max_loss": p.max_loss,
                "current_value": p.current_value,
                "unrealized_pnl": p.unrealized_pnl,
            })
        if pos_rows:
            ps = pd.DataFrame(pos_rows)
            out = PROJECT_ROOT / self.config.data_paths.position_snapshots
            if out.exists():
                old = pd.read_parquet(out)
                ps = pd.concat([old, ps], ignore_index=True).tail(10000)
            ps.to_parquet(out, index=False)

        hist_dir = PROJECT_ROOT / "data/options/historical"
        hist_dir.mkdir(parents=True, exist_ok=True)
        for u, chain in chain_cache.items():
            if chain.empty:
                continue
            h = chain.copy()
            h["date"] = now.date()
            if "symbol" not in h.columns and "underlying" in h.columns:
                h["symbol"] = h["underlying"]
            if "instrument_key" not in h.columns:
                h["instrument_key"] = ""
            out = hist_dir / f"{u.lower()}_option_chains.parquet"
            if out.exists():
                old = pd.read_parquet(out)
                h = pd.concat([old, h], ignore_index=True)
                dedupe_subset = [
                    col
                    for col in ["date", "symbol", "expiry", "strike", "option_type", "instrument_key"]
                    if col in h.columns
                ]
                h = h.drop_duplicates(subset=dedupe_subset or None, keep="last")
            h.to_parquet(out, index=False)


def _default_underlyings() -> List[str]:
    """
    Default underlyings: Use 'ALL' to dynamically load from:
    - NIFTY 50 companies (from stock_options_mapping.yaml)
    - Portfolio holdings (from portfolio_weights.parquet)
    - Opportunity surface (from opportunity_surface.parquet)
    """
    # Return ALL to trigger dynamic loading
    # This will automatically include:
    # 1. Major indices (NIFTY, BANKNIFTY, FINNIFTY, etc.)
    # 2. NIFTY 50 stocks with options
    # 3. Portfolio holdings for hedging
    # 4. Top opportunity surface stocks for alpha
    return ["ALL"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run integrated V3 options paper engine")
    parser.add_argument("--mode", choices=["single", "continuous"], default="single")
    parser.add_argument("--interval-seconds", type=float, default=None, help="Interval in seconds between cycles")
    parser.add_argument("--interval-minutes", type=float, default=None, help="Interval in minutes between cycles")
    parser.add_argument("--underlyings", type=str, default=",".join(_default_underlyings()))
    parser.add_argument(
        "--aggressive",
        dest="aggressive",
        action="store_true",
        help="Enable aggressive mode (default: enabled)",
    )
    parser.add_argument(
        "--no-aggressive",
        dest="aggressive",
        action="store_false",
        help="Disable aggressive mode",
    )
    parser.add_argument("--market-hours-only", action="store_true")
    parser.add_argument(
        "--max-trades-per-week",
        type=int,
        default=None,
        help="Override survival weekly trade cap (aggressive mode is unbounded unless this is set)",
    )
    parser.add_argument(
        "--portfolio-risk-cap-pct",
        type=float,
        default=None,
        help="Override survival portfolio risk cap as decimal (e.g. 0.10 for 10%%)",
    )
    parser.add_argument(
        "--no-max-trades-limit",
        action="store_true",
        help="Disable weekly trade-frequency cap (sets a practically unbounded limit)",
    )
    parser.add_argument(
        "--disable-portfolio-overlay",
        action="store_true",
        help="Disable V3 portfolio-aware options overlay and use static underlyings only",
    )
    parser.add_argument(
        "--portfolio-overlay-max-stocks",
        type=int,
        default=PORTFOLIO_OVERLAY_DEFAULT_MAX_STOCKS,
        help="Max option-eligible portfolio stocks to include dynamically each cycle",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Archive old paper-trade/runtime artifacts and start from a clean options paper state",
    )
    parser.add_argument(
        "--start-fresh-today",
        dest="start_fresh_today",
        action="store_true",
        help="Automatically reset runtime/trade state if persisted artifacts are from before today's IST session",
    )
    parser.add_argument(
        "--recovery-mode",
        action="store_true",
        help="Run in recovery mode - rebuild state from ledger only, disable research, minimal risk handling",
    )
    parser.add_argument(
        "--no-start-fresh-today",
        dest="start_fresh_today",
        action="store_false",
        help="Disable automatic today-start reset checks",
    )
    parser.set_defaults(start_fresh_today=False, aggressive=True)  # Changed default to False for persistence
    args = parser.parse_args()

    # Calculate interval in seconds
    if args.interval_minutes is not None:
        interval_seconds = float(args.interval_minutes) * 60.0
    elif args.interval_seconds is not None:
        interval_seconds = float(args.interval_seconds)
    else:
        interval_seconds = DEFAULT_LOOP_INTERVAL_SECONDS
    interval_seconds = max(10.0, interval_seconds)

    underlyings = [u.strip() for u in args.underlyings.split(",") if u.strip()]
    status_path = PROJECT_ROOT / "data/options/live/options_loop_status.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    last_success_at: Optional[str] = None
    state_io = StateIOManager(PROJECT_ROOT / "data/options/live")

    if not state_io.acquire_lock(timeout=5.0):
        logger.error("Could not acquire options engine lock. Another instance may be running.")
        return 2

    def _write_loop_status(status: Dict[str, Any]) -> None:
        if not state_io.writer.write_json(status_path, status):
            tmp_path = status_path.with_suffix(f"{status_path.suffix}.tmp")
            tmp_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
            tmp_path.replace(status_path)

    try:
        engine = IntegratedOptionsPaperEngine(
            underlyings=underlyings,
            aggressive=args.aggressive,
            market_hours_only=args.market_hours_only,
            max_trades_per_week=args.max_trades_per_week,
            portfolio_risk_cap_pct=args.portfolio_risk_cap_pct,
            no_max_trades_limit=bool(args.no_max_trades_limit),
            portfolio_overlay=not bool(args.disable_portfolio_overlay),
            portfolio_overlay_max_stocks=args.portfolio_overlay_max_stocks,
            reset_state=bool(args.reset_state),
            start_fresh_today=bool(args.start_fresh_today),
            recovery_mode=bool(args.recovery_mode),
        )

        if args.mode == "single":
            cycle_start = _now_ist()
            result: Dict[str, Any] = {}
            error_message: Optional[str] = None
            try:
                result = engine.run_cycle()
            except Exception as exc:
                error_message = str(exc)
                logger.exception("Single cycle failed with unhandled exception")
            cycle_end = _now_ist()

            result_status = str(result.get("status", "unknown") if isinstance(result, dict) else "unknown")
            loop_status = "failed"
            if error_message is None:
                if result_status in {"ok", "success"}:
                    loop_status = "success"
                elif result_status == "skipped":
                    loop_status = "skipped"
                elif result:
                    loop_status = "success"

            if loop_status in {"success", "skipped"}:
                last_success_at = cycle_end.isoformat()
            logger.info(f"Cycle result: {result if result else {'status': loop_status, 'error': error_message}}")

            status = {
                "timestamp": cycle_end.isoformat(),
                "status": loop_status,
                "result_status": result_status,
                "mode": "single",
                "last_cycle_started_at": cycle_start.isoformat(),
                "last_cycle_finished_at": cycle_end.isoformat(),
                "last_success_at": last_success_at,
                "duration_seconds": (cycle_end - cycle_start).total_seconds(),
                "interval_minutes": interval_seconds / 60.0,
                "next_cycle_eta": None,
                "start_fresh_today": bool(args.start_fresh_today),
                "recovery_mode": bool(args.recovery_mode),
            }
            if error_message:
                status["error"] = error_message
            if isinstance(result, dict):
                status["cycle_result"] = result
            _write_loop_status(status)
            return 1 if error_message else 0

        logger.info(f"Starting continuous mode with {interval_seconds:.1f}s ({interval_seconds/60:.1f}min) interval")

        while True:
            loop_started = time.time()
            cycle_start = _now_ist()
            result: Dict[str, Any] = {}
            error_message: Optional[str] = None
            try:
                result = engine.run_cycle()
            except Exception as exc:
                error_message = str(exc)
                logger.exception("Cycle failed with unhandled exception")
            cycle_end = _now_ist()

            result_status = str(result.get("status", "unknown") if isinstance(result, dict) else "unknown")
            loop_status = "failed"
            if error_message is None:
                if result_status in {"ok", "success"}:
                    loop_status = "success"
                elif result_status == "skipped":
                    loop_status = "skipped"
                elif result:
                    loop_status = "success"

            if loop_status in {"success", "skipped"}:
                last_success_at = cycle_end.isoformat()

            logger.info(f"Cycle result: {result if result else {'status': loop_status, 'error': error_message}}")

            # Write loop status for dashboard
            status = {
                "timestamp": cycle_end.isoformat(),
                "status": loop_status,
                "result_status": result_status,
                "last_cycle_started_at": cycle_start.isoformat(),
                "last_cycle_finished_at": cycle_end.isoformat(),
                "last_success_at": last_success_at,
                "duration_seconds": (cycle_end - cycle_start).total_seconds(),
                "interval_minutes": interval_seconds / 60.0,
                "next_cycle_eta": (cycle_end + timedelta(seconds=interval_seconds)).isoformat(),
                "start_fresh_today": bool(args.start_fresh_today),
                "recovery_mode": bool(args.recovery_mode),
            }
            if error_message:
                status["error"] = error_message
            if isinstance(result, dict):
                status["cycle_result"] = result
            _write_loop_status(status)

            elapsed = time.time() - loop_started
            sleep_for = max(1.0, interval_seconds - elapsed)
            logger.info("Sleeping %.1fs before next cycle", sleep_for)
            time.sleep(sleep_for)
    finally:
        state_io.release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
