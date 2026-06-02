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
from dataclasses import asdict
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
from src.options.options_regime_detector import Regime, RegimeState, RegimeDetector
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
from src.intelligence.news_brain.news_signal_state import deserialize_market_intelligence_state
from src.integration.alpha_os_adapter import AlphaOSAdapter
from src.sentiment.context_loader import (
    load_company_sentiment_scores,
    load_sentiment_context as load_canonical_sentiment_context,
)
from src.runtime import (
    DecisionMode as PRSDecisionMode,
    PortfolioRuntimeService,
    ProposalOrigin,
    TradeProposal,
    build_certification_snapshot,
)
from src.runtime.hash_utils import canonical_hash, file_sha256
from src.runtime.live_book_sync import sync_options_runtime_book
from src.pnl.runtime_accounting_sync import refresh_runtime_accounting
from src.volatility.regime_detector import VolatilityRegime
from src.volatility.alpha_os_types import AlphaOSContext


IST = pytz.timezone("Asia/Kolkata")
AGGRESSIVE_DEFAULT_PORTFOLIO_RISK_CAP_PCT = 0.14
PORTFOLIO_OVERLAY_DEFAULT_MAX_STOCKS = 6
PORTFOLIO_OVERLAY_DEFAULT_MAX_DYNAMIC_UNDERLYINGS = 180
PORTFOLIO_OVERLAY_MIN_DYNAMIC_UNDERLYINGS = 150
PORTFOLIO_OVERLAY_MAX_DYNAMIC_UNDERLYINGS = 250
INDEX_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
BROADER_INDEX_UNDERLYINGS = {"NIFTY", "MIDCPNIFTY"}
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
SENTIMENT_TOP_COMPANIES_LIMIT = 300
DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE = 0.15
DEFAULT_SENTIMENT_EXECUTION_FRACTION = 0.20
DEFAULT_SENTIMENT_EXECUTION_MIN_CANDIDATES = 24
DEFAULT_SENTIMENT_EXECUTION_MAX_CANDIDATES = 42
DEFAULT_SENTIMENT_SCAN_INDEX_UNDERLYINGS = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYAUTO",
    "NIFTYPHARMA",
    "NIFTYFMCG",
    "NIFTYMETAL",
    "NIFTYENERGY",
    "NIFTYREALTY",
]
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
UNDERLYING_TO_SECTOR: Dict[str, str] = {
    str(index).strip().upper(): str(sector).strip().lower()
    for sector, indices in SECTOR_INDEX_MAP.items()
    for index in indices
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
        if dt.tzinfo is None:
            return IST.localize(dt)
        return dt.astimezone(IST)
    except Exception:
        return None


def _position_hold_duration_minutes(position: Position, *, fallback_now: Optional[datetime] = None) -> float:
    end_time = getattr(position, "exit_time", None) or fallback_now or _now_ist()
    start_time = getattr(position, "entry_time", None) or end_time
    if getattr(start_time, "tzinfo", None) is None:
        start_time = IST.localize(start_time)
    else:
        start_time = start_time.astimezone(IST)
    if getattr(end_time, "tzinfo", None) is None:
        end_time = IST.localize(end_time)
    else:
        end_time = end_time.astimezone(IST)
    return float(max((end_time - start_time).total_seconds() / 60.0, 0.0))


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


def _directional_label_sign(value: Any) -> int:
    label = str(value or "").strip().lower()
    if label in POSITIVE_SENTIMENT_LABELS or label in {"up", "upside", "buy", "upgrade"}:
        return 1
    if label in NEGATIVE_SENTIMENT_LABELS or label in {"down", "sell", "downgrade"}:
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
        load_dotenv(".env.options", override=False)

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
        self.last_runtime_accounting_refresh_at: Optional[datetime] = None
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
        self.prs_enabled = str(os.getenv("NORTHSTAR_PRS_ENABLED", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.prs: Optional[PortfolioRuntimeService] = None
        self.prs_cert_snapshot_hash: str = ""
        self.prs_context: Dict[str, Any] = {}
        if self.prs_enabled:
            self._init_prs_runtime()

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
        self.loop_status_path = self.options_live_dir / "options_loop_status.json"
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
        self.regime_flip_tracker: Dict[str, Dict[str, Any]] = {}
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
    def _prs_db_path() -> Path:
        rel = str(os.getenv("NORTHSTAR_RUNTIME_DB", "data/runtime/portfolio_runtime.db") or "data/runtime/portfolio_runtime.db")
        p = Path(rel)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    @staticmethod
    def _prs_materialized_dir() -> Path:
        rel = str(
            os.getenv("NORTHSTAR_RUNTIME_MATERIALIZED_DIR", "data/processed/runtime")
            or "data/processed/runtime"
        )
        p = Path(rel)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    def _build_prs_context(self) -> Dict[str, str]:
        config_path = PROJECT_ROOT / "config/options_trading.yaml"
        prices_path = PROJECT_ROOT / "data/processed/prices.parquet"
        market_state_path = PROJECT_ROOT / "data/processed/market_state.parquet"

        config_hash = ""
        if config_path.exists():
            try:
                config_hash = file_sha256(str(config_path))
            except Exception:
                config_hash = ""

        data_revision_hash = canonical_hash(
            {
                "prices_mtime_ns": prices_path.stat().st_mtime_ns if prices_path.exists() else 0,
                "market_state_mtime_ns": market_state_path.stat().st_mtime_ns if market_state_path.exists() else 0,
            }
        )

        model_hash = canonical_hash(
            {
                "strategy_generator": "EnhancedStrategyGeneratorV3",
                "allowed_strategies": list(getattr(self.config.strategies, "allowed", []) or []),
            }
        )
        param_hash = canonical_hash(
            {
                "exit_rules": asdict(self.config.exit_rules),
                "greek_bands": asdict(self.config.greek_safety_bands),
                "survival_rules": asdict(self.config.survival_rules),
                "costs": asdict(self.config.costs),
                "tax": asdict(self.config.tax),
            }
        )
        feature_hash = canonical_hash(
            {
                "features": [
                    "regime_state",
                    "iv_rank",
                    "skew",
                    "term_structure_slope",
                    "realized_vol",
                    "sentiment_score",
                    "portfolio_exposure",
                ]
            }
        )
        return {
            "model_hash": model_hash,
            "param_hash": param_hash,
            "feature_hash": feature_hash,
            "data_revision_hash": data_revision_hash,
            "config_hash": config_hash,
            "drift_guard_version": str(os.getenv("NORTHSTAR_PRS_DRIFT_GUARD_VERSION", "v1") or "v1"),
        }

    def _refresh_prs_certification_snapshot(self) -> str:
        if self.prs is None:
            return ""
        self.prs_context = self._build_prs_context()
        snapshot = build_certification_snapshot(
            model_hash=self.prs_context["model_hash"],
            param_hash=self.prs_context["param_hash"],
            feature_hash=self.prs_context["feature_hash"],
            data_revision_hash=self.prs_context["data_revision_hash"],
            config_hash=self.prs_context["config_hash"],
            ttl_days=int(os.getenv("NORTHSTAR_PRS_CERT_TTL_DAYS", "30") or 30),
            drift_guard_version=self.prs_context["drift_guard_version"],
        )
        return str(self.prs.register_certification_snapshot(snapshot))

    def _init_prs_runtime(self) -> None:
        try:
            if self.prs is not None:
                try:
                    self.prs.close()
                except Exception:
                    pass
            self.prs = PortfolioRuntimeService(
                db_path=str(self._prs_db_path()),
                materialized_output_dir=str(self._prs_materialized_dir()),
                starting_cash=float(self.config.capital.base_capital),
                cert_ttl_days=int(os.getenv("NORTHSTAR_PRS_CERT_TTL_DAYS", "30") or 30),
            )
            self.prs_cert_snapshot_hash = self._refresh_prs_certification_snapshot()
            logger.info(
                "PRS runtime enabled db=%s cert_snapshot_hash=%s",
                self._prs_db_path(),
                self.prs_cert_snapshot_hash[:12] if self.prs_cert_snapshot_hash else "",
            )
        except Exception as e:
            logger.error("Failed to initialize PRS runtime; falling back to legacy path: %s", e)
            self.prs_enabled = False
            self.prs = None
            self.prs_cert_snapshot_hash = ""
            self.prs_context = {}

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
        if self.prs_enabled and self.prs is not None:
            try:
                events = self.prs.latest_events()
                if events:
                    ts = pd.to_datetime(
                        [str(e.get("timestamp_utc", "")) for e in events], errors="coerce", utc=True
                    )
                    ts = pd.Series(ts).dropna()
                    if not ts.empty and (ts.dt.tz_convert(IST).dt.date < today_ist).any():
                        reasons.append("prs_event_log_contains_pre_today_entries")
            except Exception as e:
                logger.warning("Could not inspect PRS event log for today-start check: %s", e)

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
        prs_db_path = self._prs_db_path()
        prs_materialized_dir = self._prs_materialized_dir()

        for path in (
            self.runtime_state_path,
            self.dashboard_state_path,
            ledger_path,
            position_snapshots_path,
            regime_history_path,
            iv_history_path,
            prs_db_path,
        ):
            self._archive_for_reset(path, archive_dir=archive_dir)
        if prs_materialized_dir.exists():
            for child in prs_materialized_dir.glob("*"):
                self._archive_for_reset(child, archive_dir=archive_dir)

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
        if self.prs_enabled:
            self._init_prs_runtime()

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

    def _write_cycle_progress_heartbeat(
        self,
        now: datetime,
        processed_underlyings: int,
        total_underlyings: int,
        current_underlying: Optional[str] = None,
        phase: str = "scanning_underlyings",
    ) -> None:
        total = max(0, int(total_underlyings or 0))
        processed = max(0, min(int(processed_underlyings or 0), total if total else int(processed_underlyings or 0)))
        progress_pct = float(processed / total) if total else 0.0
        heartbeat = {
            "timestamp": _to_iso(now),
            "pid": os.getpid(),
            "status": "alive",
            "recovery_mode": bool(self.recovery_mode),
            "phase": phase,
            "processed_underlyings": processed,
            "total_underlyings": total,
            "progress_pct": progress_pct,
            "current_underlying": str(current_underlying or ""),
        }
        self._write_json_atomic(self.heartbeat_path, heartbeat)

        loop_status = self._read_json_file(self.loop_status_path)
        loop_status.update(
            {
                "timestamp": _to_iso(now),
                "status": "running",
                "result_status": "running",
                "last_progress_at": _to_iso(now),
                "progress": {
                    "phase": phase,
                    "processed_underlyings": processed,
                    "total_underlyings": total,
                    "progress_pct": progress_pct,
                    "current_underlying": str(current_underlying or ""),
                },
            }
        )
        self._write_json_atomic(self.loop_status_path, loop_status)

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

    @staticmethod
    def _normalize_underlying_regime_label(value: Any) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"CRISIS", "HIGH_STRESS"}:
            return raw
        if raw in {"PANIC", "HOSTILE"}:
            return "HIGH_STRESS"
        if any(token in raw for token in ("CRISIS", "CRASH", "PANIC", "HIGH_STRESS", "HOSTILE")):
            return "HIGH_STRESS"
        return "NORMAL"

    def _current_underlying_regime_context(self) -> str:
        intent = self.alpha_os_last_intent if isinstance(self.alpha_os_last_intent, dict) else {}
        regime_snapshot = intent.get("regime_snapshot", {}) if isinstance(intent.get("regime_snapshot"), dict) else {}
        probabilities = regime_snapshot.get("probabilities", {}) if isinstance(regime_snapshot.get("probabilities"), dict) else {}
        alpha_os_regime = self._alpha_os_dominant_regime(probabilities)
        normalized = self._normalize_underlying_regime_label(alpha_os_regime)
        if normalized != "NORMAL":
            return normalized

        overlay_regime = ""
        if isinstance(self.portfolio_overlay, dict):
            overlay_regime = str(self.portfolio_overlay.get("regime", "") or "")
        normalized = self._normalize_underlying_regime_label(overlay_regime)
        if normalized != "NORMAL":
            return normalized

        return "NORMAL"

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

    def _portfolio_overlay_dynamic_target(self) -> int:
        raw_env = os.getenv("OPTIONS_MAX_DYNAMIC_UNDERLYINGS")
        if raw_env is None or str(raw_env).strip() == "":
            target = min(
                PORTFOLIO_OVERLAY_MAX_DYNAMIC_UNDERLYINGS,
                max(
                    PORTFOLIO_OVERLAY_MIN_DYNAMIC_UNDERLYINGS,
                    PORTFOLIO_OVERLAY_DEFAULT_MAX_DYNAMIC_UNDERLYINGS,
                ),
            )
        else:
            try:
                target = max(6, int(float(raw_env)))
            except Exception:
                target = PORTFOLIO_OVERLAY_DEFAULT_MAX_DYNAMIC_UNDERLYINGS

        target = max(target, max(6, len(self.underlyings)))
        available_universe = len(self._broad_option_scan_universe())
        if available_universe > 0:
            target = min(target, available_universe)
        return max(6, target)

    @staticmethod
    def _explicit_hedge_mode_enabled() -> bool:
        raw = str(os.getenv("OPTIONS_EXPLICIT_HEDGE_MODE", "0") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _sentiment_execution_candidate_count(self, universe_size: int) -> int:
        size = max(0, int(universe_size))
        if size <= 0:
            return 0
        raw_env = os.getenv("OPTIONS_SENTIMENT_EXECUTION_CANDIDATES")
        if raw_env is not None and str(raw_env).strip() != "":
            try:
                return max(1, min(size, int(float(raw_env))))
            except Exception:
                pass
        target = int(round(size * DEFAULT_SENTIMENT_EXECUTION_FRACTION))
        target = max(DEFAULT_SENTIMENT_EXECUTION_MIN_CANDIDATES, target)
        target = min(DEFAULT_SENTIMENT_EXECUTION_MAX_CANDIDATES, target)
        return max(1, min(size, target))

    def _broad_option_scan_universe(self) -> List[str]:
        all_symbols: List[str] = []
        try:
            all_symbols = [
                self._normalize_underlying_symbol(symbol)
                for symbol in self.stock_loader.get_all_symbols()
            ]
        except Exception as exc:
            logger.warning("Could not enumerate broad option scan universe: %s", exc)

        return self._ordered_unique_underlyings(
            [
                *DEFAULT_SENTIMENT_SCAN_INDEX_UNDERLYINGS,
                *self.underlyings,
                *all_symbols,
            ]
        )

    def _broaden_dynamic_underlyings(
        self,
        dynamic_underlyings: List[str],
        ranked_stock_rows: List[Dict[str, Any]],
        target_count: int,
    ) -> List[str]:
        generic_tokens = {"NSE", "NSE_EQ", "NSE_FO", "NFO", "BSE", "BSE_EQ", "BSE_FO", "NSE_INDEX"}
        ranked_symbols = [
            self._normalize_underlying_symbol(row.get("symbol"))
            for row in ranked_stock_rows
            if isinstance(row, dict)
        ]
        expanded = self._ordered_unique_underlyings(
            [
                *dynamic_underlyings,
                *ranked_symbols,
                *self._broad_option_scan_universe(),
            ]
        )
        out: List[str] = []
        for sym in expanded:
            if not sym or sym in generic_tokens or sym in out:
                continue
            out.append(sym)
            if len(out) >= max(1, int(target_count)):
                break
        return out

    def _load_exact_sentiment_snapshot(
        self,
        universe: List[str],
        as_of_date: datetime,
    ) -> pd.DataFrame:
        normalized_universe = self._ordered_unique_underlyings(universe)
        columns = [
            "underlying",
            "exact_sentiment_signal",
            "abs_exact_sentiment",
            "execution_priority",
            "daily_sentiment_signal",
            "intraday_sentiment_signal",
            "daily_sentiment_polarity",
            "daily_sentiment_conviction",
            "trend_score",
            "event_shock_factor",
            "headline_count",
            "market_moving_count",
            "sentiment_label",
            "sentiment_sign",
            "dominant_event_direction",
        ]
        if not normalized_universe:
            return pd.DataFrame(columns=columns)

        base = pd.DataFrame({"underlying": normalized_universe})
        as_of_ts = pd.Timestamp(as_of_date)
        if as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)

        daily = pd.DataFrame()
        sentiment_path = PROJECT_ROOT / "data" / "canonical" / "sentiment" / "company_sentiment_daily.parquet"
        if sentiment_path.exists():
            try:
                daily = pd.read_parquet(sentiment_path)
                if isinstance(daily, pd.DataFrame) and not daily.empty:
                    daily = daily.copy()
                    daily["date"] = pd.to_datetime(daily.get("date"), errors="coerce")
                    if "availability_date" in daily.columns:
                        daily["availability_date"] = pd.to_datetime(
                            daily.get("availability_date"),
                            errors="coerce",
                        )
                        daily = daily[daily["availability_date"] <= as_of_ts]
                    else:
                        daily = daily[daily["date"] <= as_of_ts]
                    daily["underlying"] = (
                        daily["ticker"]
                        .astype(str)
                        .str.replace(r"\.(NS|BO)$", "", regex=True)
                        .str.upper()
                    )
                    daily = daily[daily["underlying"].isin(normalized_universe)]
                    if not daily.empty:
                        sort_cols = [col for col in ["availability_date", "date"] if col in daily.columns]
                        daily = daily.sort_values(sort_cols or ["date"], kind="mergesort")
                        daily = daily.groupby("underlying", as_index=False).tail(1)
                        polarity_source = (
                            daily["sentiment_polarity"]
                            if "sentiment_polarity" in daily.columns
                            else pd.Series([0.0] * len(daily), index=daily.index)
                        )
                        daily["daily_sentiment_polarity"] = pd.to_numeric(
                            polarity_source,
                            errors="coerce",
                        ).fillna(0.0)
                        conviction_source = (
                            daily["sentiment_conviction"]
                            if "sentiment_conviction" in daily.columns
                            else pd.Series([0.0] * len(daily), index=daily.index)
                        )
                        daily["daily_sentiment_conviction"] = pd.to_numeric(
                            conviction_source,
                            errors="coerce",
                        ).fillna(0.0)
                        daily["daily_sentiment_signal"] = (
                            daily["daily_sentiment_polarity"] * daily["daily_sentiment_conviction"]
                        ).clip(lower=-1.0, upper=1.0)
                        headline_source = (
                            daily["headline_count"]
                            if "headline_count" in daily.columns
                            else (
                                daily["news_volume"]
                                if "news_volume" in daily.columns
                                else pd.Series([0.0] * len(daily), index=daily.index)
                            )
                        )
                        daily["daily_headline_count"] = pd.to_numeric(
                            headline_source,
                            errors="coerce",
                        ).fillna(0.0)
                        market_moving_source = (
                            daily["market_moving_count"]
                            if "market_moving_count" in daily.columns
                            else pd.Series([0.0] * len(daily), index=daily.index)
                        )
                        daily["market_moving_count"] = pd.to_numeric(
                            market_moving_source,
                            errors="coerce",
                        ).fillna(0.0)
                        if "dominant_event_direction" in daily.columns:
                            dominant_event_direction = daily["dominant_event_direction"]
                        else:
                            dominant_event_direction = pd.Series(
                                ["neutral"] * len(daily),
                                index=daily.index,
                            )
                        daily["dominant_event_direction"] = dominant_event_direction.astype(str).str.lower()
                        daily["dominant_direction_sign"] = daily["dominant_event_direction"].map(
                            _directional_label_sign
                        ).fillna(0).astype(int)
                        daily = daily[
                            [
                                "underlying",
                                "daily_sentiment_signal",
                                "daily_sentiment_polarity",
                                "daily_sentiment_conviction",
                                "daily_headline_count",
                                "market_moving_count",
                                "dominant_event_direction",
                                "dominant_direction_sign",
                            ]
                        ]
            except Exception as exc:
                logger.warning("Could not load canonical company sentiment for ranking: %s", exc)

        intraday = pd.DataFrame()
        try:
            intraday = load_company_sentiment_scores(
                project_root=PROJECT_ROOT,
                top_companies_limit=max(
                    SENTIMENT_TOP_COMPANIES_LIMIT,
                    len(normalized_universe) * 2,
                ),
            )
            if isinstance(intraday, pd.DataFrame) and not intraday.empty:
                intraday = intraday.copy()
                intraday["underlying"] = (
                    intraday["ticker"]
                    .astype(str)
                    .str.replace(r"\.(NS|BO)$", "", regex=True)
                    .str.upper()
                )
                intraday = intraday[intraday["underlying"].isin(normalized_universe)]
                if not intraday.empty:
                    intraday_signal_source = (
                        intraday["sentiment_signal"]
                        if "sentiment_signal" in intraday.columns
                        else pd.Series([0.0] * len(intraday), index=intraday.index)
                    )
                    intraday["intraday_sentiment_signal"] = pd.to_numeric(
                        intraday_signal_source,
                        errors="coerce",
                    ).fillna(0.0)
                    trend_source = (
                        intraday["trend_score"]
                        if "trend_score" in intraday.columns
                        else pd.Series([0.0] * len(intraday), index=intraday.index)
                    )
                    intraday["trend_score"] = pd.to_numeric(
                        trend_source,
                        errors="coerce",
                    ).fillna(0.0)
                    shock_source = (
                        intraday["event_shock_factor"]
                        if "event_shock_factor" in intraday.columns
                        else pd.Series([0.0] * len(intraday), index=intraday.index)
                    )
                    intraday["event_shock_factor"] = pd.to_numeric(
                        shock_source,
                        errors="coerce",
                    ).fillna(0.0)
                    intraday_headline_source = (
                        intraday["headline_count"]
                        if "headline_count" in intraday.columns
                        else pd.Series([0.0] * len(intraday), index=intraday.index)
                    )
                    intraday["intraday_headline_count"] = pd.to_numeric(
                        intraday_headline_source,
                        errors="coerce",
                    ).fillna(0.0)
                    if "sentiment_label" in intraday.columns:
                        sentiment_label = intraday["sentiment_label"]
                    else:
                        sentiment_label = pd.Series(["neutral"] * len(intraday), index=intraday.index)
                    intraday["sentiment_label"] = sentiment_label.astype(str).str.lower()
                    intraday = intraday[
                        [
                            "underlying",
                            "intraday_sentiment_signal",
                            "trend_score",
                            "event_shock_factor",
                            "intraday_headline_count",
                            "sentiment_label",
                        ]
                    ]
        except Exception as exc:
            logger.warning("Could not load intraday company sentiment ranking overlay: %s", exc)

        if daily.empty:
            daily = pd.DataFrame(
                columns=[
                    "underlying",
                    "daily_sentiment_signal",
                    "daily_sentiment_polarity",
                    "daily_sentiment_conviction",
                    "daily_headline_count",
                    "market_moving_count",
                    "dominant_event_direction",
                    "dominant_direction_sign",
                ]
            )
        if intraday.empty:
            intraday = pd.DataFrame(
                columns=[
                    "underlying",
                    "intraday_sentiment_signal",
                    "trend_score",
                    "event_shock_factor",
                    "intraday_headline_count",
                    "sentiment_label",
                ]
            )

        merged = base.merge(daily, how="left", on="underlying")
        merged = merged.merge(intraday, how="left", on="underlying")

        numeric_cols = [
            "daily_sentiment_signal",
            "daily_sentiment_polarity",
            "daily_sentiment_conviction",
            "daily_headline_count",
            "market_moving_count",
            "dominant_direction_sign",
            "intraday_sentiment_signal",
            "trend_score",
            "event_shock_factor",
            "intraday_headline_count",
        ]
        for col in numeric_cols:
            if col not in merged.columns:
                merged[col] = 0.0
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)

        if "dominant_event_direction" not in merged.columns:
            merged["dominant_event_direction"] = "neutral"
        merged["dominant_event_direction"] = merged["dominant_event_direction"].astype(str).str.lower()
        if "sentiment_label" not in merged.columns:
            merged["sentiment_label"] = "neutral"
        merged["sentiment_label"] = merged["sentiment_label"].astype(str).str.lower()

        merged["headline_count"] = merged[["daily_headline_count", "intraday_headline_count"]].max(axis=1)

        intraday_sign = np.sign(merged["intraday_sentiment_signal"].to_numpy(dtype=float))
        daily_sign = np.sign(merged["daily_sentiment_signal"].to_numpy(dtype=float))
        direction_sign = np.sign(merged["dominant_direction_sign"].to_numpy(dtype=float))
        sentiment_sign = intraday_sign.copy()
        sentiment_sign[np.isclose(sentiment_sign, 0.0)] = daily_sign[np.isclose(sentiment_sign, 0.0)]
        sentiment_sign[np.isclose(sentiment_sign, 0.0)] = direction_sign[np.isclose(sentiment_sign, 0.0)]
        sentiment_sign = np.sign(sentiment_sign)
        merged["sentiment_sign"] = sentiment_sign.astype(int)

        trend_component = merged["trend_score"] * merged["sentiment_sign"]
        shock_component = merged["event_shock_factor"] * merged["sentiment_sign"]
        dominant_direction_component = (
            merged["dominant_direction_sign"]
            * np.maximum(
                merged["daily_sentiment_signal"].abs(),
                merged["intraday_sentiment_signal"].abs(),
            )
        )
        headline_signal = np.tanh(merged["headline_count"] / 6.0)
        market_moving_signal = np.tanh(merged["market_moving_count"] / 2.0)

        exact_signal = (
            0.44 * merged["daily_sentiment_signal"]
            + 0.34 * merged["intraday_sentiment_signal"]
            + 0.10 * trend_component
            + 0.06 * shock_component
            + 0.04 * dominant_direction_component
            + 0.02 * market_moving_signal * merged["sentiment_sign"]
        )
        merged["exact_sentiment_signal"] = exact_signal.clip(lower=-1.0, upper=1.0)
        merged["abs_exact_sentiment"] = merged["exact_sentiment_signal"].abs()
        merged["execution_priority"] = (
            merged["abs_exact_sentiment"]
            * (
                1.0
                + 0.15 * headline_signal
                + 0.12 * market_moving_signal
                + 0.08 * merged["trend_score"].abs()
            )
        )

        neutral_mask = merged["sentiment_label"].isin({"", "neutral", "none", "nan"})
        merged.loc[neutral_mask & (merged["exact_sentiment_signal"] >= DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE), "sentiment_label"] = "positive"
        merged.loc[neutral_mask & (merged["exact_sentiment_signal"] <= -DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE), "sentiment_label"] = "negative"
        merged["sentiment_label"] = (
            merged["sentiment_label"]
            .replace({"nan": "neutral", "none": "neutral"})
            .fillna("neutral")
        )

        merged = merged.sort_values(
            ["execution_priority", "abs_exact_sentiment", "headline_count"],
            ascending=[False, False, False],
            kind="mergesort",
        )
        return merged[columns].reset_index(drop=True)

    @staticmethod
    def _overlay_sentiment_signal_map(overlay: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        targeting = overlay.get("sentiment_targeting", {}) if isinstance(overlay, dict) else {}
        signal_scores = targeting.get("signal_scores", {}) if isinstance(targeting, dict) else {}
        return signal_scores if isinstance(signal_scores, dict) else {}

    def _augment_overlay_with_sentiment_plan(
        self,
        overlay: Dict[str, Any],
        candidate_map: Dict[str, Any],
        universe_size: int,
    ) -> None:
        if not isinstance(overlay, dict):
            return

        signal_scores = candidate_map.get("signal_scores", {})
        if not isinstance(signal_scores, dict):
            signal_scores = {}
        execution_candidates = candidate_map.get("execution_candidates", [])
        if not isinstance(execution_candidates, list):
            execution_candidates = []

        stock_objectives = dict(overlay.get("stock_objectives", {}) or {})
        for sym in execution_candidates:
            normalized = self._normalize_underlying_symbol(sym, fallback=str(sym or ""))
            if not normalized:
                continue
            meta = signal_scores.get(normalized, {})
            if not isinstance(meta, dict):
                meta = {}
            exact_signal = float(meta.get("exact_sentiment_signal", 0.0) or 0.0)
            execution_priority = float(meta.get("execution_priority", 0.0) or 0.0)
            existing = dict(stock_objectives.get(normalized, {}) or {})
            if "objective" not in existing:
                if exact_signal <= -0.28:
                    objective = "event_shock_hedge"
                    reason = "exact_sentiment_negative_extreme"
                elif exact_signal <= -DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE:
                    objective = "protect_core"
                    reason = "exact_sentiment_negative_signal"
                elif exact_signal >= 0.24:
                    objective = "alpha_momentum"
                    reason = "exact_sentiment_positive_signal"
                elif exact_signal >= DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE:
                    objective = "alpha_income"
                    reason = "exact_sentiment_positive_income_signal"
                else:
                    objective = "vol_breakout"
                    reason = "exact_sentiment_high_attention_signal"

                stock_loader = getattr(self, "stock_loader", None)
                stock = None
                if stock_loader is not None:
                    try:
                        stock = stock_loader.get_stock(normalized)
                    except Exception:
                        stock = None
                existing.update(
                    {
                        "objective": objective,
                        "reason": reason,
                        "weight": float(existing.get("weight", 0.0) or 0.0),
                        "ticker": str(existing.get("ticker") or normalized),
                        "sector": existing.get("sector") or (stock.sector if stock else None),
                        "position_role": existing.get("position_role") or "broad_sentiment_scan",
                    }
                )

            existing.update(
                {
                    "exact_sentiment_signal": exact_signal,
                    "execution_priority": execution_priority,
                    "daily_sentiment_signal": float(meta.get("daily_sentiment_signal", 0.0) or 0.0),
                    "intraday_sentiment_signal": float(meta.get("intraday_sentiment_signal", 0.0) or 0.0),
                    "trend_score": float(meta.get("trend_score", 0.0) or 0.0),
                    "headline_count": int(float(meta.get("headline_count", 0.0) or 0.0)),
                    "market_moving_count": float(meta.get("market_moving_count", 0.0) or 0.0),
                    "sentiment_label": str(meta.get("sentiment_label", "neutral") or "neutral").lower(),
                }
            )
            stock_objectives[normalized] = existing

        overlay["stock_objectives"] = stock_objectives
        overlay["sentiment_execution"] = {
            "scan_universe_size": int(universe_size),
            "execution_candidate_count": int(len(execution_candidates)),
            "execution_candidates": list(execution_candidates),
            "top_positive": list(candidate_map.get("call_candidates", []) or [])[:12],
            "top_negative": list(candidate_map.get("put_candidates", []) or [])[:12],
            "top_ranked": list(candidate_map.get("ranked_universe", []) or [])[:12],
        }

    def _execution_allowed_for_underlying(
        self,
        underlying: str,
        objective_ctx: Dict[str, Any],
        overlay: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        normalized = self._normalize_underlying_symbol(underlying, fallback=underlying)
        signal_map = self._overlay_sentiment_signal_map(overlay if isinstance(overlay, dict) else {})
        signal_meta = dict(signal_map.get(normalized, {}) or {})
        targeting = overlay.get("sentiment_targeting", {}) if isinstance(overlay, dict) else {}
        execution_candidates = targeting.get("execution_candidates", []) if isinstance(targeting, dict) else []
        execution_set = {
            self._normalize_underlying_symbol(symbol, fallback=str(symbol or ""))
            for symbol in execution_candidates
            if str(symbol or "").strip()
        }
        objective = str(objective_ctx.get("objective") or "balanced_overlay").strip().lower()
        index_objectives = overlay.get("index_objectives", {}) if isinstance(overlay, dict) else {}
        is_index_underlying = normalized in INDEX_UNDERLYINGS or (
            isinstance(index_objectives, dict) and normalized in index_objectives
        )
        explicit_hedge_mode = bool(overlay.get("explicit_hedge_mode", False)) if isinstance(overlay, dict) else False

        if is_index_underlying:
            allowed = bool(explicit_hedge_mode)
            reason = (
                "explicit_hedge_mode_active"
                if allowed
                else "index_scan_only_until_explicit_hedge_mode"
            )
        elif objective != "balanced_overlay":
            allowed = True
            reason = "overlay_objective_execution_allowed"
        elif execution_set:
            allowed = normalized in execution_set
            reason = (
                "top_exact_sentiment_execution_candidate"
                if allowed
                else "scan_only_below_execution_cutoff"
            )
        else:
            exact_signal = float(signal_meta.get("exact_sentiment_signal", 0.0) or 0.0)
            allowed = abs(exact_signal) >= DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE
            reason = (
                "exact_sentiment_threshold_met"
                if allowed
                else "sentiment_data_unavailable_fallback"
            )

        signal_meta.update(
            {
                "eligible_for_execution": bool(allowed),
                "eligibility_reason": reason,
                "execution_shortlist_size": int(len(execution_set)),
                "explicit_hedge_mode": bool(explicit_hedge_mode),
            }
        )
        return bool(allowed), signal_meta

    def _load_intelligence_state(self):
        unified_state_path = PROJECT_ROOT / "data" / "state" / "unified_state.json"
        if not unified_state_path.exists():
            return None
        try:
            payload = json.loads(unified_state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read unified state intelligence payload: %s", exc)
            return None
        raw = payload.get("intelligence_state") if isinstance(payload, dict) else None
        return deserialize_market_intelligence_state(raw if isinstance(raw, dict) else None)

    def _load_urgent_shock_flag(self) -> Optional[Dict[str, Any]]:
        flag_path = PROJECT_ROOT / "data" / "intelligence" / "urgent_shock_flag.json"
        if not flag_path.exists():
            return None
        try:
            payload = json.loads(flag_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read urgent shock flag: %s", exc)
            return None

        written_at = _parse_dt(payload.get("written_at"))
        if written_at is None:
            return None
        age_minutes = max((_now_ist() - written_at).total_seconds() / 60.0, 0.0)
        if age_minutes > 30.0:
            return None
        payload["age_minutes"] = float(age_minutes)
        return payload

    def _apply_market_intelligence_overlay(
        self,
        overlay: Dict[str, Any],
        intelligence_state,
    ) -> Dict[str, Any]:
        if intelligence_state is None or not getattr(intelligence_state, "available", False):
            return overlay

        overlay = dict(overlay or {})
        urgent_flag = self._load_urgent_shock_flag()
        sentiment = dict(overlay.get("sentiment_context", {}) or {})
        severity_value = float(getattr(intelligence_state, "shock_severity").value)
        shock_confidence = float(getattr(intelligence_state, "shock_confidence", 0.0) or 0.0)
        severity_signal = min(1.0, (severity_value / 5.0) * 0.80 + shock_confidence * 0.35)
        sentiment["event_shock_score"] = max(float(sentiment.get("event_shock_score", 0.0) or 0.0), severity_signal)
        if severity_value >= 4:
            sentiment["alert_level"] = "critical"
        elif severity_value >= 3:
            sentiment["alert_level"] = "high"
        elif severity_value >= 2:
            sentiment["alert_level"] = "elevated"
        else:
            sentiment["alert_level"] = str(sentiment.get("alert_level", "normal") or "normal").lower()
        sentiment["market_intelligence_shock_type"] = intelligence_state.primary_shock_type.value
        sentiment["market_intelligence_shock_confidence"] = shock_confidence
        sentiment["negative_trending_companies"] = list(
            dict.fromkeys(
                [*(sentiment.get("negative_trending_companies", []) or []), *list(getattr(intelligence_state, "tickers_negative", []) or [])]
            )
        )

        event_impacts = []
        sector_items = sorted(
            getattr(intelligence_state, "sector_impacts", {}).items(),
            key=lambda item: abs(float(item[1].impact_score)),
            reverse=True,
        )
        for sector, impact in sector_items[:8]:
            ticker = None
            impact_direction = "mixed"
            if impact.key_tickers_at_risk:
                ticker = impact.key_tickers_at_risk[0]
                impact_direction = "negative"
            elif impact.key_tickers_to_benefit:
                ticker = impact.key_tickers_to_benefit[0]
                impact_direction = "positive"
            if not ticker:
                continue
            event_impacts.append(
                {
                    "ticker": str(ticker).replace(".NS", ""),
                    "event_type": intelligence_state.primary_shock_type.value,
                    "impact_score": float(impact.impact_score),
                    "impact_direction": impact_direction,
                    "sector": sector,
                }
            )
        sentiment["event_company_impacts"] = event_impacts
        overlay["sentiment_context"] = sentiment
        overlay["market_intelligence"] = {
            "shock_type": intelligence_state.primary_shock_type.value,
            "secondary_shock_type": intelligence_state.secondary_shock_type.value if intelligence_state.secondary_shock_type else None,
            "shock_severity": intelligence_state.shock_severity.name,
            "shock_direction": intelligence_state.shock_direction.value,
            "shock_confidence": shock_confidence,
            "requires_immediate_hedge": bool(intelligence_state.requires_immediate_hedge),
            "requires_portfolio_rebalance": bool(intelligence_state.requires_portfolio_rebalance),
            "urgent_flag_active": bool(urgent_flag),
        }
        overlay["hedge_intensity"] = max(float(overlay.get("hedge_intensity", 0.0) or 0.0), severity_signal)
        if urgent_flag:
            overlay["hedge_intensity"] = max(float(overlay.get("hedge_intensity", 0.0) or 0.0), 0.85)
            logger.warning(
                "URGENT SHOCK FLAG active: %s %s (age=%.1fmin)",
                urgent_flag.get("shock_type"),
                urgent_flag.get("severity"),
                float(urgent_flag.get("age_minutes", 0.0) or 0.0),
            )

        dynamic_underlyings = list(dict.fromkeys(overlay.get("dynamic_underlyings", []) or []))
        selected_stock_underlyings = list(dict.fromkeys(overlay.get("selected_stock_underlyings", []) or []))
        stock_objectives = dict(overlay.get("stock_objectives", {}) or {})
        index_objectives = dict(overlay.get("index_objectives", {}) or {})

        selected_strategies = list(getattr(intelligence_state, "selected_option_strategies", []) or [])
        if selected_strategies:
            logger.info(
                "Strategy library selected %s strategies: %s",
                len(selected_strategies),
                [str(item.get("strategy")) for item in selected_strategies],
            )

        for selected in selected_strategies:
            underlying = str((selected or {}).get("underlying", "") or "").strip().upper()
            if underlying and underlying not in dynamic_underlyings:
                dynamic_underlyings.insert(0, underlying)

        if severity_value >= 3:
            overlay["portfolio_objective"] = "defensive_convexity"
            index_objectives["NIFTY"] = "event_shock_hedge"
            if intelligence_state.primary_shock_type.value in {"rate_hike_rbi", "banking_stress", "fii_outflow"}:
                index_objectives["BANKNIFTY"] = "event_shock_hedge"

        for sector_name, impact in sector_items:
            if impact.impact_score <= -0.45:
                for ticker in impact.key_tickers_at_risk[:3]:
                    symbol = str(ticker).replace(".NS", "").strip().upper()
                    if symbol and symbol not in dynamic_underlyings:
                        dynamic_underlyings.append(symbol)
                    if symbol:
                        stock_objectives[symbol] = {
                            "objective": "event_shock_hedge" if severity_value >= 3 else "protect_core",
                            "reason": f"market_intelligence_negative_sector:{sector_name}",
                            "weight": float(stock_objectives.get(symbol, {}).get("weight", 0.0) or 0.0),
                            "sector": sector_name,
                        }
                        if symbol not in selected_stock_underlyings:
                            selected_stock_underlyings.append(symbol)
            elif impact.impact_score >= 0.45:
                for ticker in impact.key_tickers_to_benefit[:3]:
                    symbol = str(ticker).replace(".NS", "").strip().upper()
                    if symbol and symbol not in dynamic_underlyings:
                        dynamic_underlyings.append(symbol)
                    if symbol:
                        stock_objectives[symbol] = {
                            "objective": "alpha_momentum",
                            "reason": f"market_intelligence_beneficiary:{sector_name}",
                            "weight": float(stock_objectives.get(symbol, {}).get("weight", 0.0) or 0.0),
                            "sector": sector_name,
                        }
                        if symbol not in selected_stock_underlyings:
                            selected_stock_underlyings.append(symbol)

        overlay["dynamic_underlyings"] = dynamic_underlyings or list(self.underlyings)
        overlay["selected_stock_underlyings"] = selected_stock_underlyings
        overlay["stock_objectives"] = stock_objectives
        overlay["index_objectives"] = index_objectives
        return overlay

    def _read_alternative_frame(self, *relative_candidates: str) -> pd.DataFrame:
        for candidate in relative_candidates:
            path = PROJECT_ROOT / candidate
            if not path.exists():
                continue
            try:
                if path.suffix.lower() == ".parquet":
                    return pd.read_parquet(path)
                return pd.read_csv(path, low_memory=False)
            except Exception as exc:
                logger.warning("Could not load alternative frame %s: %s", path, exc)
        return pd.DataFrame()

    def _load_alternative_signal_stocks(self, now: datetime, existing_symbols: set[str]) -> List[Dict[str, Any]]:
        as_of = pd.Timestamp(now)
        if as_of.tzinfo is not None:
            as_of = as_of.tz_convert(None)

        results: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def _append_signal(
            *,
            ticker: str,
            score: float,
            source: str,
            event_date: Any,
            headline: str | None = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> None:
            symbol = str(ticker or "").replace(".NS", "").strip().upper()
            if not symbol or symbol in existing_symbols or symbol in seen:
                return
            stock = self.stock_loader.get_stock(symbol)
            if not stock:
                return
            signed_score = float(score or 0.0)
            if not math.isfinite(signed_score) or abs(signed_score) < 0.20:
                return
            signal_direction = "bullish" if signed_score > 0 else "bearish"
            payload = {
                "ticker": symbol,
                "symbol": symbol,
                "weight": 0.0,
                "position_role": "alternative_event",
                "industry": stock.sector if stock.sector else None,
                "option_eligible": True,
                "instrument_key": stock.instrument_key,
                "sector": stock.sector,
                "alternative_source": source,
                "alternative_signal_score": float(np.clip(signed_score, -1.0, 1.0)),
                "signal_direction": signal_direction,
                "event_date": str(pd.to_datetime(event_date, errors="coerce").date()) if pd.notna(pd.to_datetime(event_date, errors="coerce")) else None,
                "headline": str(headline or "").strip() or None,
            }
            if isinstance(metadata, dict):
                payload.update(metadata)
            results.append(payload)
            seen.add(symbol)

        bulk = self._read_alternative_frame(
            "data/canonical/alternative/bulk_deals_nse_all.parquet",
            "data/canonical/alternative/bulk_deals_nse_all.csv",
            "data/processed/alternative/bulk_deals_nse_all.parquet",
            "data/processed/alternative/bulk_deals_nse_all.csv",
            "data/processed/alternative/bulk_deals_all.csv",
        )
        if not bulk.empty:
            work = bulk.copy()
            work["date"] = pd.to_datetime(work.get("date"), errors="coerce")
            work["nse_ticker"] = work.get("nse_ticker", "").astype(str).str.replace(".NS", "", regex=False).str.upper()
            work["deal_type"] = work.get("deal_type", "").astype(str).str.upper()
            work["client_name"] = work.get("client_name", "").astype(str)
            work["company_name"] = work.get("company_name", "").astype(str)
            work["notional"] = pd.to_numeric(work.get("quantity"), errors="coerce").fillna(0.0) * pd.to_numeric(work.get("price"), errors="coerce").fillna(0.0)
            work = work[work["date"] >= (as_of - pd.Timedelta(days=10))].copy()
            if not work.empty:
                inst_mask = work["client_name"].str.contains(
                    r"FUND|MUTUAL|ASSET|CAPITAL|INSURANCE|BANK|FII|DII|TRUST|INVEST",
                    case=False,
                    regex=True,
                    na=False,
                )
                work["signed_notional"] = np.where(work["deal_type"].eq("BUY"), 1.0, -1.0) * work["notional"]
                work["inst_signed_notional"] = np.where(inst_mask, work["signed_notional"], 0.0)
                grouped = (
                    work.groupby("nse_ticker", as_index=False)
                    .agg(
                        signed_notional=("signed_notional", "sum"),
                        inst_signed_notional=("inst_signed_notional", "sum"),
                        latest_date=("date", "max"),
                        company_name=("company_name", "last"),
                    )
                )
                grouped["score"] = np.tanh(grouped["inst_signed_notional"].abs() / 5.0e8) * np.sign(grouped["inst_signed_notional"])
                grouped.loc[grouped["score"].abs() < 0.20, "score"] = np.tanh(grouped["signed_notional"].abs() / 8.0e8) * np.sign(grouped["signed_notional"])
                grouped = grouped.sort_values("score", key=lambda s: s.abs(), ascending=False).head(8)
                for _, row in grouped.iterrows():
                    _append_signal(
                        ticker=row.get("nse_ticker"),
                        score=float(row.get("score", 0.0) or 0.0),
                        source="bulk_deals",
                        event_date=row.get("latest_date"),
                        headline=f"Institutional bulk flow: {row.get('company_name', row.get('nse_ticker', ''))}",
                        metadata={"opportunity_type": "Alternative Flow"},
                    )

        ratings = self._read_alternative_frame(
            "data/canonical/alternative/credit_ratings_nse_all.parquet",
            "data/canonical/alternative/credit_ratings_nse_all.csv",
            "data/processed/alternative/credit_ratings_nse_all.parquet",
            "data/processed/alternative/credit_ratings_nse_all.csv",
            "data/processed/alternative/credit_ratings_all.csv",
        )
        if not ratings.empty:
            work = ratings.copy()
            work["date"] = pd.to_datetime(work.get("date", work.get("DATE OF CREDIT RATING")), errors="coerce", dayfirst=True)
            work["nse_ticker"] = work.get("nse_ticker", "").astype(str).str.replace(".NS", "", regex=False).str.upper()
            work["action_type"] = work.get("action_type", work.get("rating_action", "")).astype(str).str.upper()
            work["outlook"] = work.get("outlook", "").astype(str).str.upper()
            work["company_name"] = work.get("company_name", "").astype(str)
            work["new_rating"] = work.get("new_rating", work.get("rating", "")).astype(str)
            work = work[(work["date"] >= (as_of - pd.Timedelta(days=45))) & work["nse_ticker"].ne("")].copy()
            if not work.empty:
                work["score"] = 0.0
                work.loc[work["action_type"].str.contains("DOWNGRADE|WATCH_NEGATIVE|SUSPEND", na=False), "score"] -= 0.80
                work.loc[work["action_type"].str.contains("UPGRADE|REVISEUP|POSITIVE", na=False), "score"] += 0.65
                work.loc[work["outlook"].str.contains("NEGATIVE", na=False), "score"] -= 0.35
                work.loc[work["outlook"].str.contains("POSITIVE", na=False), "score"] += 0.25
                work = work[work["score"].abs() >= 0.20].copy()
                work = work.sort_values(["date", "score"], ascending=[False, False]).groupby("nse_ticker", as_index=False).head(1)
                for _, row in work.iterrows():
                    _append_signal(
                        ticker=row.get("nse_ticker"),
                        score=float(row.get("score", 0.0) or 0.0),
                        source="credit_ratings",
                        event_date=row.get("date"),
                        headline=f"Credit rating {row.get('action_type', '').strip() or 'update'}: {row.get('company_name', row.get('nse_ticker', ''))}",
                        metadata={
                            "opportunity_type": "Alternative Credit",
                            "rating_action": row.get("action_type"),
                            "new_rating": row.get("new_rating"),
                        },
                    )

        pledge = self._read_alternative_frame(
            "data/canonical/alternative/promoter_pledge_all.parquet",
            "data/canonical/alternative/promoter_pledge_all.csv",
            "data/processed/alternative/promoter_pledge_all.parquet",
            "data/processed/alternative/promoter_pledge_all.csv",
        )
        if not pledge.empty:
            work = pledge.copy()
            work["date"] = pd.to_datetime(work.get("date"), errors="coerce")
            work["nse_ticker"] = work.get("nse_ticker", "").astype(str).str.replace(".NS", "", regex=False).str.upper()
            work["company_name"] = work.get("company_name", "").astype(str)
            work["pledge_pct"] = pd.to_numeric(work.get("pledge_pct"), errors="coerce")
            work = work[(work["date"] >= (as_of - pd.Timedelta(days=450))) & work["nse_ticker"].ne("")].copy()
            if not work.empty:
                work = work.sort_values(["nse_ticker", "date"], kind="mergesort")
                work["pledge_change_1q"] = work.groupby("nse_ticker", sort=False)["pledge_pct"].diff(1)
                latest = work.groupby("nse_ticker", as_index=False).tail(1).copy()
                latest["score"] = 0.0
                latest.loc[latest["pledge_pct"] >= 50.0, "score"] -= 0.95
                latest.loc[(latest["pledge_pct"] >= 30.0) & (latest["score"] == 0.0), "score"] -= 0.75
                latest.loc[(latest["pledge_pct"] >= 15.0) & (latest["score"] == 0.0), "score"] -= 0.45
                latest.loc[latest["pledge_change_1q"] >= 5.0, "score"] -= 0.20
                latest = latest[latest["score"].abs() >= 0.25].sort_values("score").head(6)
                for _, row in latest.iterrows():
                    _append_signal(
                        ticker=row.get("nse_ticker"),
                        score=float(row.get("score", 0.0) or 0.0),
                        source="promoter_pledge",
                        event_date=row.get("date"),
                        headline=f"Promoter pledge stress: {row.get('company_name', row.get('nse_ticker', ''))}",
                        metadata={
                            "opportunity_type": "Alternative Risk",
                            "pledge_pct": float(row.get("pledge_pct", 0.0) or 0.0),
                        },
                    )

        announcements = self._read_alternative_frame(
            "data/canonical/alternative/announcements_all.parquet",
            "data/canonical/alternative/announcements_all.csv",
            "data/processed/alternative/announcements_all.parquet",
            "data/processed/alternative/announcements_all.csv",
        )
        if not announcements.empty:
            work = announcements.copy()
            work["date"] = pd.to_datetime(work.get("date"), errors="coerce")
            work["nse_ticker"] = work.get("nse_ticker", "").astype(str).str.replace(".NS", "", regex=False).str.upper()
            work["category"] = work.get("category", "").astype(str).str.upper()
            work["headline"] = work.get("headline", "").astype(str)
            work["announcement_text"] = work.get("announcement_text", "").astype(str)
            work = work[(work["date"] >= (as_of - pd.Timedelta(days=21))) & work["nse_ticker"].ne("")].copy()
            if not work.empty:
                work["score"] = 0.0
                work.loc[work["category"].str.contains("ORDER WIN", na=False), "score"] += 0.60
                work.loc[work["category"].str.contains("CAPACITY EXPANSION", na=False), "score"] += 0.35
                work.loc[work["category"].str.contains("ACQUISITION|MERGER", na=False), "score"] += 0.25
                buy_mask = work["headline"].str.contains(r"\bbuy|purchase|acquire\b", case=False, regex=True, na=False)
                sell_mask = work["headline"].str.contains(r"\bsell|sale|disposed\b", case=False, regex=True, na=False)
                work.loc[work["category"].str.contains("INSIDER TRADING", na=False) & buy_mask, "score"] += 0.35
                work.loc[work["category"].str.contains("INSIDER TRADING", na=False) & sell_mask, "score"] -= 0.35
                grouped = (
                    work.groupby("nse_ticker", as_index=False)
                    .agg(
                        score=("score", "sum"),
                        latest_date=("date", "max"),
                        headline=("headline", "last"),
                    )
                )
                grouped["score"] = grouped["score"].clip(-0.9, 0.9)
                grouped = grouped[grouped["score"].abs() >= 0.25].sort_values("score", key=lambda s: s.abs(), ascending=False).head(8)
                for _, row in grouped.iterrows():
                    _append_signal(
                        ticker=row.get("nse_ticker"),
                        score=float(row.get("score", 0.0) or 0.0),
                        source="announcements",
                        event_date=row.get("latest_date"),
                        headline=row.get("headline"),
                        metadata={"opportunity_type": "Alternative Event"},
                    )

        if results:
            logger.info("Added %d alternative-data driven stocks to the options overlay", len(results))
        return results

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
                "held_pressure_stocks": 0,
                "alternative_signal_stocks": 0,
            },
            "sentiment_context": sentiment_context,
        }

        if not self.portfolio_overlay_enabled:
            return overlay

        weights_path = PROJECT_ROOT / "data/processed/portfolio_weights.parquet"
        current_holdings_path = PROJECT_ROOT / "data/processed/current_holdings.parquet"
        current_positions_path = PROJECT_ROOT / "data/portfolio/current_positions.json"
        watchlist_path = PROJECT_ROOT / "data/processed/portfolio_sentiment_watchlist.json"
        analytics_path = PROJECT_ROOT / "data/processed/portfolio_analytics.json"
        capital_path = PROJECT_ROOT / "data/processed/capital_allocations.json"
        narrative_path = PROJECT_ROOT / "data/reports/narrative_suite_latest.json"
        regime_path = PROJECT_ROOT / "data/processed/regime_intelligence_feed.json"
        opportunity_path = PROJECT_ROOT / "data/processed/opportunity_surface.parquet"
        research_opportunity_path = PROJECT_ROOT / "data/processed/research_opportunity_surface.parquet"

        weights_rows: List[Dict[str, Any]] = []
        holdings_source = current_holdings_path if current_holdings_path.exists() else weights_path
        if not holdings_source.exists():
            overlay["status"] = "partial"
            overlay["warnings"].append(f"missing_holdings_file:{holdings_source}")
        else:
            try:
                wdf = pd.read_parquet(holdings_source)
                if isinstance(wdf, pd.DataFrame) and not wdf.empty:
                    symbol_col = "symbol" if "symbol" in wdf.columns else ("ticker" if "ticker" in wdf.columns else None)
                    weight_col = next((c for c in ["weight", "final_weight", "allocation", "w", "exposure"] if c in wdf.columns), None)
                    if not symbol_col or not weight_col:
                        overlay["status"] = "partial"
                        overlay["warnings"].append("holdings_missing_symbol_or_weight_column")
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
                overlay["warnings"].append(f"holdings_load_error:{e}")

        weights_rows.sort(key=lambda x: float(x.get("weight", 0.0) or 0.0), reverse=True)
        option_rows = [r for r in weights_rows if bool(r.get("option_eligible"))]
        max_sel = max(0, int(self.portfolio_overlay_max_stocks))
        selected_rows = option_rows[:max_sel] if max_sel > 0 else []

        # Load opportunity surface for alpha generation beyond portfolio
        opportunity_stocks: List[Dict[str, Any]] = []
        sentiment_driven_stocks: List[Dict[str, Any]] = []
        held_pressure_stocks: List[Dict[str, Any]] = []
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

        watchlist_payload = self._read_json_file(watchlist_path)
        watch_rows = (
            watchlist_payload.get("held_positions_under_pressure", [])
            if isinstance(watchlist_payload, dict)
            else []
        )
        existing_holdings = {str(r.get("symbol", "")).upper() for r in selected_rows}
        for row in watch_rows[:24] if isinstance(watch_rows, list) else []:
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker", "") or row.get("symbol", "")).replace(".NS", "").strip().upper()
            if not ticker or ticker in existing_holdings:
                continue
            stock = self.stock_loader.get_stock(ticker)
            if not stock:
                continue
            held_pressure_stocks.append({
                "ticker": ticker,
                "symbol": ticker,
                "weight": float(row.get("weight", 0.0) or 0.0),
                "position_role": "held_sentiment_pressure",
                "industry": stock.sector if stock.sector else row.get("sector"),
                "option_eligible": True,
                "instrument_key": stock.instrument_key,
                "sector": stock.sector or row.get("sector"),
                "trend_score": float(row.get("impact_score", 0.0) or 0.0),
                "sentiment_label": str(row.get("sentiment_label", "") or "").lower(),
                "headline_count": 0,
            })
            existing_holdings.add(ticker)

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

        alt_existing_symbols = {
            str(r.get("symbol", "")).upper()
            for r in (selected_rows + held_pressure_stocks + opportunity_stocks + sentiment_driven_stocks)
        }
        alternative_signal_stocks = self._load_alternative_signal_stocks(now, alt_existing_symbols)

        # Combine portfolio stocks + held-pressure names + opportunity stocks + sentiment + alternative events
        all_selected_rows = selected_rows + held_pressure_stocks + opportunity_stocks + sentiment_driven_stocks + alternative_signal_stocks

        overlay["weights_summary"] = {
            "total_holdings": int(len(weights_rows)),
            "option_eligible_holdings": int(len(option_rows)),
            "selected_holdings": int(len(selected_rows)),
            "opportunity_surface_stocks": int(len(opportunity_stocks)),
            "sentiment_driven_stocks": int(len(sentiment_driven_stocks)),
            "held_pressure_stocks": int(len(held_pressure_stocks)),
            "alternative_signal_stocks": int(len(alternative_signal_stocks)),
            "total_selected": int(len(all_selected_rows)),
        }
        overlay["selected_stock_underlyings"] = [str(r.get("symbol")) for r in all_selected_rows]
        overlay["selected_stock_rows"] = all_selected_rows

        analytics = self._read_json_file(analytics_path)
        capital = self._read_json_file(capital_path)
        narrative = self._read_json_file(narrative_path)
        regime_feed = self._read_json_file(regime_path)
        current_positions_payload = self._read_json_file(current_positions_path)

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
        if (cash_level <= 0.0 and total_exposure <= 0.0) and isinstance(current_positions_payload, dict):
            try:
                total_value = float(current_positions_payload.get("total_value", 0.0) or 0.0)
                invested_value = float(current_positions_payload.get("invested_value", 0.0) or 0.0)
                cash_value = float(current_positions_payload.get("cash", 0.0) or 0.0)
                if total_value > 0.0:
                    total_exposure = invested_value / total_value
                    cash_level = cash_value / total_value
            except Exception:
                pass
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
            raw_alt_source = row.get("alternative_source", "")
            alt_source = "" if pd.isna(raw_alt_source) else str(raw_alt_source or "").lower()
            alt_score = float(row.get("alternative_signal_score", 0.0) or 0.0)
            raw_signal_direction = row.get("signal_direction", "")
            signal_direction = "" if pd.isna(raw_signal_direction) else str(raw_signal_direction or "").lower()

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
            elif role == "alternative_event":
                if signal_direction == "bearish":
                    if alt_source in {"credit_ratings", "promoter_pledge"} or abs(alt_score) >= 0.65:
                        objective = "event_shock_hedge"
                    else:
                        objective = "protect_core"
                    reason = f"alternative_{alt_source or 'event'}_bearish_signal"
                elif alt_source in {"bulk_deals", "announcements"} and alt_score >= 0.35:
                    objective = "alpha_momentum"
                    reason = f"alternative_{alt_source}_bullish_signal"
                else:
                    objective = "alpha_income"
                    reason = f"alternative_{alt_source or 'event'}_carry_overlay"
            elif role == "held_sentiment_pressure":
                if sentiment_label in {"negative", "very_negative", "bearish", "downside"} or trend_score <= -0.20:
                    objective = "event_shock_hedge"
                    reason = "held_name_negative_sentiment_pressure"
                elif sentiment_label in {"positive", "very_positive", "bullish", "upside"} or trend_score >= 0.25:
                    objective = "alpha_momentum"
                    reason = "held_name_positive_sentiment_pressure"
                else:
                    objective = "protect_core"
                    reason = "held_name_under_live_sentiment_watch"
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
                "trend_score": trend_score if role in {"sentiment_event", "held_sentiment_pressure"} else None,
                "sentiment_label": sentiment_label if role in {"sentiment_event", "held_sentiment_pressure"} else None,
                "alternative_source": alt_source if role == "alternative_event" else None,
                "alternative_signal_score": alt_score if role == "alternative_event" else None,
                "priority_score": (
                    2.0 if objective in HEDGE_OBJECTIVES else
                    1.5 if role == "held_sentiment_pressure" else
                    1.25 if role == "sentiment_event" else
                    1.10 if role == "alternative_event" else
                    1.0 if role == "opportunity_alpha" else
                    0.5
                ),
                "signal_direction": signal_direction if role in {"alternative_event", "opportunity_alpha"} else None,
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

        max_dynamic_underlyings = self._portfolio_overlay_dynamic_target()

        dynamic_underlyings: List[str] = []
        for sym in [*weekly_hedge_targets, *base_indices, *self.underlyings]:
            if sym and sym not in dynamic_underlyings:
                dynamic_underlyings.append(sym)
        ranked_stock_rows = sorted(
            stock_rows,
            key=lambda r: (
                float(r.get("priority_score", 0.0) or 0.0),
                float(abs(r.get("weight", 0.0) or 0.0)),
                float(abs(r.get("trend_score", 0.0) or 0.0)),
                float(abs(r.get("alternative_signal_score", 0.0) or 0.0)),
            ),
            reverse=True,
        )
        if len(dynamic_underlyings) < max_dynamic_underlyings:
            dynamic_underlyings = self._broaden_dynamic_underlyings(
                dynamic_underlyings,
                ranked_stock_rows,
                max_dynamic_underlyings,
            )
        if dynamic_underlyings:
            resolved = [u for u in dynamic_underlyings if self._resolve_key(u)]
            dynamic_underlyings = resolved if resolved else dynamic_underlyings
            dynamic_underlyings = dynamic_underlyings[:max_dynamic_underlyings]

        overlay.update({
            "weekly_rationale": weekly_rationale,
            "portfolio_objective": portfolio_objective,
            "hedge_intensity": hedge_intensity,
            "explicit_hedge_mode": bool(self._explicit_hedge_mode_enabled()),
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
        intelligence_state = self._load_intelligence_state()
        return self._apply_market_intelligence_overlay(overlay, intelligence_state)

    def _resolve_cycle_underlyings(self, overlay: Dict[str, Any]) -> List[str]:
        def _sentiment_target_order(
            candidate_map: Dict[str, List[str]],
            universe: List[str],
            overlay_payload: Optional[Dict[str, Any]],
        ) -> List[str]:
            market_signal = self._load_market_sentiment_signal(_now_ist(), overlay_payload)
            effective_signal = float(
                market_signal.get(
                    "effective_global_risk_sentiment",
                    market_signal.get("global_risk_sentiment", 0.0),
                )
                or 0.0
            )

            if bool(market_signal.get("sentiment_crisis_detected")) or effective_signal <= -0.5:
                selection_mode = "put_priority"
                ordered = list(candidate_map.get("put_candidates", []) or [])
            elif effective_signal >= 0.5:
                selection_mode = "call_priority"
                ordered = list(candidate_map.get("call_candidates", []) or [])
            else:
                selection_mode = "straddle_priority"
                ordered = list(candidate_map.get("straddle_candidates", []) or [])
            ranked_universe = list(candidate_map.get("ranked_universe", []) or [])
            execution_candidates = list(candidate_map.get("execution_candidates", []) or [])
            signal_scores = dict(candidate_map.get("signal_scores", {}) or {})
            fallback_order = ranked_universe or list(universe)

            if isinstance(overlay_payload, dict):
                overlay_payload["sentiment_targeting"] = {
                    "selection_mode": selection_mode,
                    "market_signal": dict(market_signal),
                    "call_candidates": list(candidate_map.get("call_candidates", []) or []),
                    "put_candidates": list(candidate_map.get("put_candidates", []) or []),
                    "straddle_candidates": list(candidate_map.get("straddle_candidates", []) or []),
                    "ranked_universe": ranked_universe,
                    "execution_candidates": execution_candidates,
                    "signal_scores": signal_scores,
                }
                self._augment_overlay_with_sentiment_plan(
                    overlay_payload,
                    candidate_map,
                    len(universe),
                )

            logger.info(
                "Sentiment-targeted cycle universe mode=%s effective_signal=%.3f crisis=%s top=%s execution=%s",
                selection_mode,
                effective_signal,
                bool(market_signal.get("sentiment_crisis_detected")),
                ordered[: min(6, len(ordered))],
                execution_candidates[: min(6, len(execution_candidates))],
            )
            return (ordered or fallback_order)[: len(universe)] if universe else fallback_order

        if not self.portfolio_overlay_enabled:
            universe = list(self.underlyings)
            candidate_map = self.get_sentiment_ranked_underlyings(
                universe,
                _now_ist(),
                top_n=len(universe),
            )
            return _sentiment_target_order(candidate_map, universe, overlay if isinstance(overlay, dict) else {})
        dynamic = overlay.get("dynamic_underlyings", [])
        if not isinstance(dynamic, list):
            universe = list(self.underlyings)
            candidate_map = self.get_sentiment_ranked_underlyings(
                universe,
                _now_ist(),
                top_n=len(universe),
            )
            return _sentiment_target_order(candidate_map, universe, overlay if isinstance(overlay, dict) else {})
        generic_tokens = {"NSE", "NSE_EQ", "NSE_FO", "NFO", "BSE", "BSE_EQ", "BSE_FO", "NSE_INDEX"}
        resolved = []
        for u in dynamic:
            sym = self._normalize_underlying_symbol(u)
            if not sym or sym in resolved or sym in generic_tokens:
                continue
            if self._resolve_key(sym):
                resolved.append(sym)
        universe = resolved or list(self.underlyings)
        candidate_map = self.get_sentiment_ranked_underlyings(
            universe,
            _now_ist(),
            top_n=len(universe),
        )
        return _sentiment_target_order(candidate_map, universe, overlay)

    @staticmethod
    def _ordered_unique_underlyings(symbols: List[str]) -> List[str]:
        ordered: List[str] = []
        for raw in symbols or []:
            sym = str(raw or "").strip().upper()
            if sym and sym not in ordered:
                ordered.append(sym)
        return ordered

    def _load_market_sentiment_signal(
        self,
        as_of_date: datetime,
        overlay: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        as_of_ts = pd.Timestamp(as_of_date)
        if as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)

        signal: Dict[str, Any] = {
            "source": "",
            "source_timestamp": None,
            "india_market_polarity": 0.0,
            "global_risk_sentiment": 0.0,
            "effective_global_risk_sentiment": 0.0,
            "overlay_sentiment_bias": 0.0,
            "overlay_alert_level": "normal",
            "overlay_event_shock_score": 0.0,
            "sentiment_crisis_detected": False,
        }

        unified_state_path = PROJECT_ROOT / "data" / "state" / "unified_state.json"
        if unified_state_path.exists():
            try:
                payload = json.loads(unified_state_path.read_text(encoding="utf-8"))
                sentiment_state = (
                    (payload.get("sentiment_state") or payload.get("sentiment") or {})
                    if isinstance(payload, dict)
                    else {}
                )
                if isinstance(sentiment_state, dict) and sentiment_state:
                    raw_global = sentiment_state.get("global_risk_sentiment")
                    if raw_global is None:
                        zscore = pd.to_numeric(sentiment_state.get("market_sentiment_zscore"), errors="coerce")
                        if pd.notna(zscore):
                            raw_global = float(np.clip(float(zscore) / 2.0, -1.0, 1.0))
                    raw_india = sentiment_state.get("india_market_polarity", raw_global)
                    if raw_global is not None:
                        parsed_global = pd.to_numeric(raw_global, errors="coerce")
                        if pd.notna(parsed_global):
                            signal["global_risk_sentiment"] = float(parsed_global)
                            signal["effective_global_risk_sentiment"] = signal["global_risk_sentiment"]
                            signal["source"] = "unified_state"
                    if raw_india is not None:
                        parsed_india = pd.to_numeric(raw_india, errors="coerce")
                        if pd.notna(parsed_india):
                            signal["india_market_polarity"] = float(parsed_india)
                    signal["source_timestamp"] = (
                        sentiment_state.get("last_updated")
                        or payload.get("checkpoint_time")
                        or payload.get("last_updated")
                    )
                    signal["sentiment_crisis_detected"] = bool(
                        sentiment_state.get("sentiment_crisis_signal", False)
                    )
            except Exception as exc:
                logger.warning("Could not read unified sentiment state for options targeting: %s", exc)

        market_path = PROJECT_ROOT / "data" / "canonical" / "sentiment" / "market_sentiment_daily.parquet"
        if market_path.exists():
            try:
                market_df = pd.read_parquet(market_path)
                if isinstance(market_df, pd.DataFrame) and not market_df.empty:
                    market_df = market_df.copy()
                    market_df["date"] = pd.to_datetime(market_df.get("date"), errors="coerce")
                    if "availability_date" in market_df.columns:
                        market_df["availability_date"] = pd.to_datetime(
                            market_df.get("availability_date"),
                            errors="coerce",
                        )
                        market_df = market_df[market_df["availability_date"] <= as_of_ts]
                    market_df = market_df[market_df["date"] <= as_of_ts]
                    if not market_df.empty:
                        market_df = market_df.sort_values("date")
                        last_row = market_df.iloc[-1]
                        canonical_global_raw = pd.to_numeric(
                            last_row.get(
                                "global_risk_sentiment",
                                last_row.get("india_market_polarity", 0.0),
                            ),
                            errors="coerce",
                        )
                        canonical_global = float(canonical_global_raw) if pd.notna(canonical_global_raw) else 0.0
                        canonical_india_raw = pd.to_numeric(
                            last_row.get("india_market_polarity", canonical_global),
                            errors="coerce",
                        )
                        canonical_india = (
                            float(canonical_india_raw)
                            if pd.notna(canonical_india_raw)
                            else canonical_global
                        )
                        signal.update(
                            {
                                "source": "canonical_market_sentiment",
                                "source_timestamp": pd.Timestamp(last_row.get("date")).isoformat()
                                if pd.notna(last_row.get("date"))
                                else signal.get("source_timestamp"),
                                "india_market_polarity": canonical_india,
                                "global_risk_sentiment": canonical_global,
                                "effective_global_risk_sentiment": canonical_global,
                                "sentiment_crisis_detected": bool(
                                    signal.get("sentiment_crisis_detected", False)
                                    or canonical_india <= -0.6
                                    or canonical_global <= -0.8
                                ),
                            }
                        )
            except Exception as exc:
                logger.warning("Could not read canonical market sentiment for options targeting: %s", exc)

        overlay_sentiment = self._overlay_sentiment(overlay if isinstance(overlay, dict) else {})
        overlay_bias_raw = pd.to_numeric(
            overlay_sentiment.get("sentiment_bias", overlay_sentiment.get("polarity", 0.0)),
            errors="coerce",
        )
        overlay_bias = float(overlay_bias_raw) if pd.notna(overlay_bias_raw) else 0.0
        overlay_alert = str(overlay_sentiment.get("alert_level", "normal") or "normal").strip().lower()
        overlay_event_shock_raw = pd.to_numeric(
            overlay_sentiment.get("event_shock_score", 0.0),
            errors="coerce",
        )
        overlay_event_shock = (
            float(overlay_event_shock_raw) if pd.notna(overlay_event_shock_raw) else 0.0
        )
        signal["overlay_sentiment_bias"] = overlay_bias
        signal["overlay_alert_level"] = overlay_alert
        signal["overlay_event_shock_score"] = overlay_event_shock
        if abs(overlay_bias) > abs(float(signal.get("effective_global_risk_sentiment", 0.0) or 0.0)):
            signal["effective_global_risk_sentiment"] = overlay_bias
        if abs(float(signal.get("india_market_polarity", 0.0) or 0.0)) < abs(overlay_bias):
            signal["india_market_polarity"] = overlay_bias

        signal["sentiment_crisis_detected"] = bool(
            signal.get("sentiment_crisis_detected", False)
            or float(signal.get("india_market_polarity", 0.0) or 0.0) <= -0.6
            or float(signal.get("effective_global_risk_sentiment", 0.0) or 0.0) <= -0.8
            or overlay_alert in {"high", "critical"}
            or overlay_event_shock >= 0.90
        )
        return signal

    def get_sentiment_ranked_underlyings(
        self,
        universe: List[str],
        as_of_date: datetime,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Bucket underlyings into bullish, bearish, and volatility targets using exact ticker sentiment."""
        if not universe:
            return {
                "call_candidates": [],
                "put_candidates": [],
                "straddle_candidates": [],
                "ranked_universe": [],
                "execution_candidates": [],
                "signal_scores": {},
            }

        normalized_universe = self._ordered_unique_underlyings(universe)
        fallback = normalized_universe[:top_n]
        out: Dict[str, Any] = {
            "call_candidates": list(fallback),
            "put_candidates": list(fallback),
            "straddle_candidates": list(fallback),
            "ranked_universe": list(fallback),
            "execution_candidates": [],
            "signal_scores": {},
        }

        try:
            exact_snapshot = self._load_exact_sentiment_snapshot(normalized_universe, as_of_date)
            if exact_snapshot.empty:
                return out

            has_signal_data = bool(
                (
                    pd.to_numeric(exact_snapshot.get("execution_priority"), errors="coerce").fillna(0.0) > 0.0
                ).any()
                or (
                    pd.to_numeric(exact_snapshot.get("abs_exact_sentiment"), errors="coerce").fillna(0.0) > 0.0
                ).any()
            )
            if not has_signal_data:
                logger.warning("Exact sentiment data unavailable; using unranked underlying universe")
                return out

            ranked_rows = exact_snapshot.sort_values(
                ["execution_priority", "abs_exact_sentiment", "headline_count"],
                ascending=[False, False, False],
                kind="mergesort",
            )
            positive = ranked_rows[
                pd.to_numeric(ranked_rows["exact_sentiment_signal"], errors="coerce").fillna(0.0)
                >= DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE
            ].sort_values(
                ["exact_sentiment_signal", "execution_priority", "headline_count"],
                ascending=[False, False, False],
                kind="mergesort",
            )["underlying"].tolist()
            negative = ranked_rows[
                pd.to_numeric(ranked_rows["exact_sentiment_signal"], errors="coerce").fillna(0.0)
                <= -DEFAULT_SENTIMENT_EXECUTION_MIN_SCORE
            ].sort_values(
                ["exact_sentiment_signal", "execution_priority", "headline_count"],
                ascending=[True, False, False],
                kind="mergesort",
            )["underlying"].tolist()
            volatile = ranked_rows["underlying"].tolist()

            index_priority = [
                sym for sym in normalized_universe
                if sym in {"NIFTY", "BANKNIFTY"}
            ]
            residual = [
                sym for sym in normalized_universe
                if sym not in set([*volatile, *index_priority])
            ]
            execution_candidate_count = self._sentiment_execution_candidate_count(len(normalized_universe))
            execution_candidates = volatile[:execution_candidate_count]

            signal_scores: Dict[str, Dict[str, Any]] = {}
            for rank, row in enumerate(ranked_rows.to_dict("records"), start=1):
                underlying = str(row.get("underlying", "") or "").strip().upper()
                if not underlying:
                    continue
                signal_scores[underlying] = {
                    "exact_sentiment_signal": float(row.get("exact_sentiment_signal", 0.0) or 0.0),
                    "execution_priority": float(row.get("execution_priority", 0.0) or 0.0),
                    "daily_sentiment_signal": float(row.get("daily_sentiment_signal", 0.0) or 0.0),
                    "intraday_sentiment_signal": float(row.get("intraday_sentiment_signal", 0.0) or 0.0),
                    "daily_sentiment_polarity": float(row.get("daily_sentiment_polarity", 0.0) or 0.0),
                    "daily_sentiment_conviction": float(row.get("daily_sentiment_conviction", 0.0) or 0.0),
                    "trend_score": float(row.get("trend_score", 0.0) or 0.0),
                    "event_shock_factor": float(row.get("event_shock_factor", 0.0) or 0.0),
                    "headline_count": int(float(row.get("headline_count", 0.0) or 0.0)),
                    "market_moving_count": float(row.get("market_moving_count", 0.0) or 0.0),
                    "sentiment_label": str(row.get("sentiment_label", "neutral") or "neutral").lower(),
                    "sentiment_sign": int(float(row.get("sentiment_sign", 0.0) or 0.0)),
                    "dominant_event_direction": str(row.get("dominant_event_direction", "neutral") or "neutral").lower(),
                    "execution_candidate_rank": int(rank),
                }

            out = {
                "call_candidates": self._ordered_unique_underlyings(
                    [*positive, *volatile, *index_priority, *residual, *normalized_universe]
                )[:top_n],
                "put_candidates": self._ordered_unique_underlyings(
                    [*index_priority, *negative, *volatile, *residual, *normalized_universe]
                )[:top_n],
                "straddle_candidates": self._ordered_unique_underlyings(
                    [*index_priority, *volatile, *negative, *positive, *residual, *normalized_universe]
                )[:top_n],
                "ranked_universe": self._ordered_unique_underlyings(
                    [*volatile, *negative, *positive, *index_priority, *residual, *normalized_universe]
                )[:top_n],
                "execution_candidates": list(execution_candidates),
                "signal_scores": signal_scores,
            }
            logger.info(
                "Exact-sentiment candidate buckets prepared: calls=%s puts=%s straddles=%s execution=%s",
                out["call_candidates"][: min(5, len(out["call_candidates"]))],
                out["put_candidates"][: min(5, len(out["put_candidates"]))],
                out["straddle_candidates"][: min(5, len(out["straddle_candidates"]))],
                out["execution_candidates"][: min(5, len(out["execution_candidates"]))],
            )
            return out
        except Exception as exc:
            logger.warning("Sentiment ranking failed: %s", exc)
            return out

    def _sentiment_crisis_override_active(
        self,
        underlying: str,
        overlay: Optional[Dict[str, Any]] = None,
    ) -> bool:
        normalized = self._normalize_underlying_symbol(underlying)
        if normalized not in {"NIFTY", "BANKNIFTY"}:
            return False
        targeting = overlay.get("sentiment_targeting", {}) if isinstance(overlay, dict) else {}
        market_signal = targeting.get("market_signal", {}) if isinstance(targeting, dict) else {}
        if not isinstance(market_signal, dict) or not market_signal:
            market_signal = self._load_market_sentiment_signal(_now_ist(), overlay)
        return bool(market_signal.get("sentiment_crisis_detected", False))

    def _should_bypass_alpha_os_strategy_gate(
        self,
        underlying: str,
        strategy_type: str,
        overlay: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return bool(
            str(strategy_type or "").strip().lower() == "bear_put_spread"
            and self._sentiment_crisis_override_active(
                underlying,
                overlay if isinstance(overlay, dict) else self.portfolio_overlay,
            )
        )

    def _hot_load_strategy(self, strategy_name: str) -> None:
        """Compatibility hook for operator-driven strategy hot loading."""
        logger.info("Hot-load requested for strategy '%s' but dynamic loading is not implemented", strategy_name)

    def _hot_unload_strategy(self, strategy_name: str) -> None:
        """Compatibility hook for operator-driven strategy hot unloading."""
        logger.info("Hot-unload requested for strategy '%s' but dynamic unloading is not implemented", strategy_name)

    def _check_hot_reload_signals(self) -> Dict[str, Any]:
        """
        Check for optional hot-reload instructions on the canonical engine surface.
        """
        signal_path = self.options_live_dir / "strategy_hot_reload.json"
        if not signal_path.exists():
            return {"available": False, "actions": []}

        try:
            payload = json.loads(signal_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Ignoring unreadable hot-reload payload: %s", exc)
            return {"available": False, "error": str(exc), "actions": []}

        actions = payload.get("actions") or []
        for action in actions:
            if not isinstance(action, dict):
                continue
            strategy_name = str(action.get("strategy") or "").strip()
            if not strategy_name:
                continue
            op = str(action.get("op") or "").strip().lower()
            if op == "load":
                self._hot_load_strategy(strategy_name)
            elif op == "unload":
                self._hot_unload_strategy(strategy_name)
        return {"available": True, "actions": actions}

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
    def _prs_option_symbol(underlying: str, proposal_id: str) -> str:
        return f"OPT::{str(underlying or '').strip().upper()}::{str(proposal_id or '').strip().upper()}"

    def _prs_sector_for_underlying(self, underlying: str, objective_ctx: Optional[Dict[str, Any]] = None) -> str:
        normalized = self._normalize_underlying_symbol(underlying)
        if not normalized:
            return ""
        if normalized in BROADER_INDEX_UNDERLYINGS:
            return ""
        mapped_sector = UNDERLYING_TO_SECTOR.get(normalized)
        if mapped_sector:
            return mapped_sector
        try:
            stock = self.stock_loader.get_stock(normalized)
        except Exception:
            stock = None
        if stock and getattr(stock, "sector", None):
            return str(stock.sector).strip().lower()
        if isinstance(objective_ctx, dict):
            return str(objective_ctx.get("sector", "") or "").strip().lower()
        return ""

    def _dominant_sector_hint(self) -> str:
        if not isinstance(self.portfolio_overlay, dict):
            return ""
        dominant = self.portfolio_overlay.get("dominant_sector", {})
        if isinstance(dominant, dict):
            return str(dominant.get("name", "") or "").strip().lower()
        return str(dominant or "").strip().lower()

    def _get_current_equity_positions(self) -> Dict[str, Dict[str, Any]]:
        """Load current equity positions for hedge sizing from live books."""
        current_positions_path = PROJECT_ROOT / "data/portfolio/current_positions.json"
        portfolio_path = PROJECT_ROOT / "data/processed/portfolio_weights.parquet"

        if current_positions_path.exists():
            try:
                payload = json.loads(current_positions_path.read_text(encoding="utf-8"))
                positions = payload.get("positions", {}) if isinstance(payload, dict) else {}
                if isinstance(positions, dict):
                    normalized: Dict[str, Dict[str, Any]] = {}
                    for symbol, raw in positions.items():
                        row = dict(raw or {})
                        normalized_symbol = str(symbol or "").strip().upper()
                        if not normalized_symbol:
                            continue
                        row["symbol"] = normalized_symbol
                        row["weight"] = float(pd.to_numeric(row.get("weight"), errors="coerce") or 0.0)
                        row["market_value"] = float(pd.to_numeric(row.get("market_value"), errors="coerce") or 0.0)
                        normalized[normalized_symbol] = row
                    if normalized:
                        return normalized
            except Exception as exc:
                logger.warning("Could not read runtime equity positions: %s", exc)

        if portfolio_path.exists():
            try:
                df = pd.read_parquet(portfolio_path)
                if isinstance(df, pd.DataFrame) and not df.empty:
                    symbol_col = "ticker" if "ticker" in df.columns else ("symbol" if "symbol" in df.columns else None)
                    weight_col = next(
                        (c for c in ["weight", "final_weight", "allocation", "w", "exposure"] if c in df.columns),
                        None,
                    )
                    if symbol_col and weight_col:
                        normalized = {}
                        for _, row in df.iterrows():
                            symbol = str(row.get(symbol_col, "") or "").replace(".NS", "").strip().upper()
                            if not symbol:
                                continue
                            normalized[symbol] = {
                                "symbol": symbol,
                                "weight": float(pd.to_numeric(row.get(weight_col), errors="coerce") or 0.0),
                                "market_value": float(pd.to_numeric(row.get("market_value"), errors="coerce") or 0.0),
                                "sector": str(row.get("Industry", "") or "").strip() or None,
                            }
                        if normalized:
                            return normalized
            except Exception as exc:
                logger.warning("Could not read portfolio weights for hedge sizing: %s", exc)

        logger.warning("No equity position source found; hedge sizing will be approximate")
        return {}

    def _hedging_state_for_underlying(self, underlying: str, objective: str) -> Dict[str, Any]:
        objective_key = str(objective or "").strip().lower()
        ranked: List[Dict[str, Any]] = []
        for symbol, raw in self._get_current_equity_positions().items():
            row = dict(raw or {})
            row["symbol"] = str(symbol or "").strip().upper()
            row["weight"] = float(row.get("weight", 0.0) or 0.0)
            row["market_value"] = float(row.get("market_value", 0.0) or 0.0)
            ranked.append(row)
        ranked.sort(key=lambda row: (float(row.get("weight", 0.0) or 0.0), float(row.get("market_value", 0.0) or 0.0)), reverse=True)

        protected_rows: List[Dict[str, Any]] = []
        normalized_underlying = str(underlying or "").strip().upper()
        if normalized_underlying and any(str(row.get("symbol", "") or "").upper() == normalized_underlying for row in ranked):
            protected_rows = [
                row for row in ranked
                if str(row.get("symbol", "") or "").upper() == normalized_underlying
            ][:1]
        elif normalized_underlying in {"BANKNIFTY", "FINNIFTY"}:
            protected_rows = [
                row for row in ranked
                if "financial" in str(row.get("sector", "") or "").strip().lower()
                or "bank" in str(row.get("symbol", "") or "").strip().lower()
            ][:12]
        elif objective_key in HEDGE_OBJECTIVES or normalized_underlying in INDEX_UNDERLYINGS:
            protected_rows = ranked[:12]

        protected_symbols = [str(row.get("symbol", "") or "").strip().upper() for row in protected_rows if str(row.get("symbol", "") or "").strip()]
        protected_weight = sum(float(row.get("weight", 0.0) or 0.0) for row in protected_rows)
        protected_market_value = sum(float(row.get("market_value", 0.0) or 0.0) for row in protected_rows)
        return {
            "objective": objective_key,
            "underlying_symbol": normalized_underlying,
            "portfolio_objective": str((self.portfolio_overlay or {}).get("portfolio_objective", "") or ""),
            "hedge_intensity": float((self.portfolio_overlay or {}).get("hedge_intensity", 0.0) or 0.0),
            "protected_symbols": protected_symbols,
            "protected_symbols_count": int(len(protected_symbols)),
            "protected_weight": float(protected_weight),
            "protected_market_value": float(protected_market_value),
            "weekly_hedge_targets": list((self.portfolio_overlay or {}).get("weekly_hedge_targets", []) or []),
        }

    def _repair_position_metadata(self, position: Position) -> None:
        metadata = dict(getattr(position, "metadata", {}) or {})
        underlying = self._normalize_underlying_symbol(
            getattr(position, "underlying", ""),
            fallback=str(metadata.get("underlying_symbol", "") or ""),
        )
        objective_ctx = self._objective_for_underlying(underlying, self.portfolio_overlay)
        inferred_objective = str(
            metadata.get("objective")
            or objective_ctx.get("objective")
            or ("hedge_convexity" if underlying in INDEX_UNDERLYINGS else "alpha_momentum")
        ).strip()
        prs_position_key = str(metadata.get("prs_position_key") or position.position_id or "").strip()
        prs_symbol = str(metadata.get("prs_symbol") or "").strip()
        if not prs_symbol and prs_position_key:
            if prs_position_key == str(position.position_id or "").strip():
                prs_symbol = f"OPT::{prs_position_key}"
            else:
                prs_symbol = self._prs_option_symbol(underlying, prs_position_key)
        prs_symbol = prs_symbol.upper()
        hedging_state = metadata.get("hedging_state")
        if not isinstance(hedging_state, dict) or not hedging_state:
            hedging_state = self._hedging_state_for_underlying(underlying, inferred_objective)
        metadata.update(
            {
                "prs_symbol": prs_symbol,
                "prs_position_key": prs_position_key,
                "underlying_symbol": underlying,
                "objective": inferred_objective,
                "reason": str(metadata.get("reason") or objective_ctx.get("reason") or ""),
                "hedging_state": dict(hedging_state or {}),
                "sector": self._prs_sector_for_underlying(underlying, objective_ctx),
            }
        )
        position.underlying = underlying
        position.metadata = metadata

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
        liquidity_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        expected_gross = self._estimate_expected_gross_pnl(strategy, objective=objective, overlay=overlay)
        slippage_bps = 0.0
        if isinstance(liquidity_snapshot, dict):
            slippage_bps = float(
                liquidity_snapshot.get("estimated_slippage_bps", liquidity_snapshot.get("spread_bps", 0.0)) or 0.0
            )

        economics = self.pnl_tracker.estimate_trade_economics(
            legs=strategy.legs,
            expected_gross_pnl=expected_gross,
            max_loss=float(abs(strategy.max_loss or 0.0)),
            slippage_bps=slippage_bps,
        )
        direct_costs = economics.get("costs")
        total_costs = float(getattr(direct_costs, "total", 0.0) or 0.0)
        slippage_cost = float(economics.get("slippage_cost", 0.0) or 0.0)
        expected_net = float(economics.get("expected_net_pnl", 0.0) or 0.0)
        tax = float(economics.get("expected_tax", 0.0) or 0.0)
        objective_key = str(objective or "").strip().lower()
        threshold_multiplier = float(self.config.tax.min_profitability_multiplier)
        if not self._is_short_vol_strategy(strategy):
            # Long-vol/debit strategies incur larger explicit costs for similar notional.
            # Keeping the same strict cost-multiple gate can reject the whole universe.
            threshold_multiplier = min(threshold_multiplier, 0.55)
            if objective_key in HEDGE_OBJECTIVES:
                threshold_multiplier = min(threshold_multiplier, 0.30)
        min_threshold = max(
            MIN_NET_EXPECTANCY_INR,
            (total_costs + slippage_cost) * threshold_multiplier,
        )

        return {
            "expected_gross_pnl": float(expected_gross),
            "expected_total_costs": float(total_costs),
            "expected_slippage_cost": float(slippage_cost),
            "expected_slippage_bps": float(max(0.0, slippage_bps)),
            "expected_tax": float(tax),
            "expected_net_pnl": float(expected_net),
            "min_threshold": float(min_threshold),
            "threshold_multiplier": float(threshold_multiplier),
            "net_max_loss": float(economics.get("net_max_loss", abs(float(strategy.max_loss or 0.0)))),
            "cost_to_max_loss_ratio": float(economics.get("cost_to_max_loss_ratio", 0.0) or 0.0),
            "friction_total": float(economics.get("friction_total", 0.0) or 0.0),
        }

    def _passes_net_profit_gate(
        self,
        strategy: OptionStrategy,
        objective: str,
        overlay: Dict[str, Any],
        liquidity_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        estimate = self._estimate_expected_net_pnl(
            strategy,
            objective=objective,
            overlay=overlay,
            liquidity_snapshot=liquidity_snapshot,
        )
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
        eligibility_cfg = getattr(self.config, "eligibility", self.config)
        max_slippage_bps = float(getattr(eligibility_cfg, "max_expected_slippage_bps", 120.0) or 120.0)
        max_cost_ratio = float(getattr(eligibility_cfg, "max_transaction_cost_pct_of_max_loss", 0.20) or 0.20)
        expected_slippage_bps = float(estimate.get("expected_slippage_bps", 0.0) or 0.0)
        cost_to_max_loss_ratio = float(estimate.get("cost_to_max_loss_ratio", 0.0) or 0.0)

        short_vol_min_threshold = float(min_threshold)
        if self._is_short_vol_strategy(strategy) and hedge_priority_mode:
            short_vol_min_threshold *= 1.15 + min(0.35, hedge_intensity * 0.30 + event_shock * 0.20)
            min_threshold = short_vol_min_threshold

        override = (
            objective_key in NET_PROFIT_OVERRIDE_OBJECTIVES
            and not self._is_short_vol_strategy(strategy)
            and alert in HEDGE_PRIORITY_ALERT_LEVELS
        )
        slippage_ok = expected_slippage_bps <= max_slippage_bps
        cost_ratio_ok = cost_to_max_loss_ratio <= max_cost_ratio
        passed = bool((expected_net >= min_threshold or override) and slippage_ok and cost_ratio_ok)

        return {
            **estimate,
            "passed": passed,
            "override_applied": bool(override and expected_net < min_threshold),
            "objective": objective_key,
            "slippage_ok": bool(slippage_ok),
            "cost_ratio_ok": bool(cost_ratio_ok),
            "max_expected_slippage_bps": float(max_slippage_bps),
            "max_cost_to_max_loss_ratio": float(max_cost_ratio),
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
        crisis_override_active = self._sentiment_crisis_override_active(underlying, overlay)
        if crisis_override_active:
            selector["sentiment_crisis_override"] = True

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
        if crisis_override_active:
            ordered: List[str] = []
            for name in ["bear_put_spread", *candidate_order]:
                if name not in ordered:
                    ordered.append(name)
            candidate_order = ordered
        elif self._is_hedge_priority_mode(overlay):
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
            liquidity_snapshot = self._prs_liquidity_snapshot(option_chain, strategy_for_gate)
            net_gate = self._passes_net_profit_gate(
                strategy_for_gate,
                objective=objective,
                overlay=overlay,
                liquidity_snapshot=liquidity_snapshot,
            )
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
                "expected_slippage_bps": float(net_gate.get("expected_slippage_bps", 0.0) or 0.0),
                "cost_to_max_loss_ratio": float(net_gate.get("cost_to_max_loss_ratio", 0.0) or 0.0),
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
            if crisis_override_active:
                crisis_soft = [
                    row for row in soft_fallback
                    if self._strategy_type_value(row[1]) == "bear_put_spread"
                ]
                if crisis_soft:
                    crisis_soft.sort(
                        key=lambda x: (
                            float((x[4] or {}).get("expected_net_pnl", 0.0) or 0.0),
                            x[2],
                        ),
                        reverse=True,
                    )
                    selected_source, selected_strategy, selected_score, _selected_details, selected_gate = crisis_soft[0]
                    selector["selected_source"] = selected_source
                    selector["selected_strategy_type"] = self._strategy_type_value(selected_strategy)
                    selector["selected_score"] = float(selected_score)
                    selector["soft_net_gate_fallback"] = True
                    selector["crisis_override_applied"] = True
                    selector["reason"] = (
                        "sentiment crisis override selected protective bear_put_spread "
                        f"with expected net ₹{float((selected_gate or {}).get('expected_net_pnl', 0.0) or 0.0):,.0f}"
                    )
                    return selected_strategy, selector
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
        if crisis_override_active:
            crisis_candidates = [
                row for row in scored
                if self._strategy_type_value(row[1]) == "bear_put_spread"
            ]
            if crisis_candidates:
                selected_source, selected_strategy, selected_score, _ = crisis_candidates[0]
                selector["selected_source"] = selected_source
                selector["selected_strategy_type"] = self._strategy_type_value(selected_strategy)
                selector["selected_score"] = float(selected_score)
                selector["crisis_override_applied"] = True
                selector["reason"] = (
                    "sentiment crisis override selected NIFTY/BANKNIFTY protective bear_put_spread"
                )
                return selected_strategy, selector
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
        self.regime_flip_tracker = state.get("regime_flip_tracker", {}) or {}
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
                self._repair_position_metadata(pos)
                self.position_manager.open_positions[pos.position_id] = pos
        for p in state.get("closed_positions", []) or []:
            pos = self._position_from_dict(p)
            if pos:
                self._repair_position_metadata(pos)
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
        open_positions = list(self.position_manager.get_open_positions())
        closed_positions = list(self.position_manager.get_closed_positions())
        for pos in [*open_positions, *closed_positions]:
            self._repair_position_metadata(pos)

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
            "open_positions": [self._position_to_dict(p) for p in open_positions],
            "closed_positions": [self._position_to_dict(p) for p in closed_positions[-500:]],
            "scaling_state": scaling,
            "iv_history": self.iv_history,
            "regime_history": self.regime_history[-5000:],
            "greeks_history": self.greeks_history[-2000:],
            "regime_flip_tracker": self.regime_flip_tracker,
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
            return
        try:
            sync_report = self.trade_ledger.sync_runtime_state(state)
            if any(int(v) > 0 for v in sync_report.values()):
                logger.info(
                    "Recovered missing immutable trade-ledger entries from runtime state: %s",
                    sync_report,
                )
        except Exception as exc:
            logger.warning("Failed syncing runtime state into immutable trade ledger: %s", exc)
        if self.prs_enabled and self.prs is not None:
            try:
                core_payload = self._read_json_file(PROJECT_ROOT / "data/portfolio/current_positions.json")
                prs_sync = sync_options_runtime_book(
                    self.prs,
                    runtime_payload=state,
                    current_positions_payload=core_payload,
                    runtime_scope="live",
                )
                if int(prs_sync.get("trade_events", 0) or 0) > 0:
                    logger.info("Synchronized options runtime into PRS: %s", prs_sync)
            except Exception as exc:
                logger.warning("Failed syncing options runtime into PRS: %s", exc)

    def _refresh_runtime_accounting_artifacts(self, now: datetime, *, force: bool = False) -> None:
        if not force and self.last_runtime_accounting_refresh_at is not None:
            elapsed = (now - self.last_runtime_accounting_refresh_at).total_seconds()
            if elapsed < 15 * 60:
                return
        try:
            report = refresh_runtime_accounting()
            self.last_runtime_accounting_refresh_at = now
            logger.info(
                "Refreshed runtime accounting: ledger_rows=%s recon=%s",
                report.ledger_rows,
                report.reconciliation_status,
            )
        except Exception as exc:
            logger.warning("Failed refreshing runtime accounting after options cycle: %s", exc)

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
            "hold_duration_minutes": _position_hold_duration_minutes(p),
            "greeks": p.greeks.__dict__ if p.greeks else None,
            "entry_greeks": p.entry_greeks.__dict__ if p.entry_greeks else None,
            "exit_time": _to_iso(p.exit_time),
            "exit_reason": p.exit_reason,
            "metadata": dict(getattr(p, "metadata", {}) or {}),
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
                entry_time=_parse_dt(d.get("entry_time")) or _now_ist(),
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
                metadata=dict(d.get("metadata", {}) or {}),
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
            cached_chain = self._fallback_chain_from_disk(underlying)
            if not cached_chain.empty:
                logger.warning("Using cached option chain because expiry discovery failed for %s", underlying)
                return cached_chain
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
        if self.prs_enabled and self.prs is not None:
            now_ist = _now_ist()
            week_start_ist = (now_ist - timedelta(days=now_ist.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return int(self.prs.weekly_open_fill_count(week_start_ist.astimezone(pytz.UTC).isoformat()))
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

    def _prs_origin_from_objective(self, objective: str) -> ProposalOrigin:
        obj = str(objective or "").strip().lower()
        if obj in HEDGE_OBJECTIVES:
            return ProposalOrigin.OPTIONS_HEDGE
        return ProposalOrigin.OPTIONS_ALPHA

    def _prs_alpha_type_from_objective(self, objective: str) -> str:
        obj = str(objective or "").strip().lower()
        if obj in {"event_shock_hedge", "hedge_convexity", "defensive_convexity"}:
            return "convexity"
        if obj in {"volatility_relative_value", "vol_surface_distortion"}:
            return "relative_value"
        if obj in {"vol_carry", "vol_mean_reversion"}:
            return "vol"
        return "directional"

    def _prs_budget_snapshot(self) -> Dict[str, Any]:
        equity = max(1.0, float(self._current_net_equity()))
        reserve_usage = {
            "equity_alpha": 0.0,
            "options_alpha": 0.0,
            "hedge": 0.0,
            "discretionary": 0.0,
        }
        strategy_usage: Dict[str, float] = {}

        for position in self.position_manager.get_open_positions():
            self._repair_position_metadata(position)
            metadata = position.metadata if isinstance(getattr(position, "metadata", {}), dict) else {}
            objective = str(metadata.get("objective", "") or "")
            origin = self._prs_origin_from_objective(objective)
            if origin == ProposalOrigin.OPTIONS_HEDGE:
                reserve_pool = "hedge"
            elif origin == ProposalOrigin.OPTIONS_ALPHA:
                reserve_pool = "options_alpha"
            elif origin == ProposalOrigin.MANUAL:
                reserve_pool = "discretionary"
            else:
                reserve_pool = "equity_alpha"

            notional = abs(float(position.max_loss or position.current_value or position.entry_credit_debit or 0.0))
            reserve_usage[reserve_pool] = float(reserve_usage.get(reserve_pool, 0.0) + notional)
            strategy_key = str(position.strategy_type or "unknown")
            strategy_usage[strategy_key] = float(strategy_usage.get(strategy_key, 0.0) + (notional / equity))

        return {
            "reserve_usage": reserve_usage,
            "strategy_usage": strategy_usage,
        }

    def _prs_risk_snapshot(self) -> Dict[str, Any]:
        equity = max(1.0, float(self._current_net_equity()))
        strategy_exposure: Dict[str, float] = {}
        origin_exposure: Dict[str, float] = {}

        for position in self.position_manager.get_open_positions():
            self._repair_position_metadata(position)
            metadata = position.metadata if isinstance(getattr(position, "metadata", {}), dict) else {}
            objective = str(metadata.get("objective", "") or "")
            origin = self._prs_origin_from_objective(objective)
            notional = abs(float(position.max_loss or position.current_value or position.entry_credit_debit or 0.0))
            strategy_key = str(position.strategy_type or "unknown")
            strategy_exposure[strategy_key] = float(strategy_exposure.get(strategy_key, 0.0) + (notional / equity))
            origin_exposure[origin.value] = float(origin_exposure.get(origin.value, 0.0) + (notional / equity))

        return {
            "risk_budget_ratio": float(
                self._current_open_risk() / max(1e-9, self._portfolio_risk_cap_value())
            ),
            "strategy_exposure": strategy_exposure,
            "origin_exposure": origin_exposure,
            "signal_entropy": float(
                self._alpha_os_entropy((self.alpha_os_last_intent or {}).get("probabilities", {}) or {})
            ) if self.alpha_os_last_intent else 1.0,
        }

    def _build_prs_open_proposal(
        self,
        *,
        strategy: OptionStrategy,
        objective: str,
        underlying: str,
        decision: Dict[str, Any],
        now: datetime,
    ) -> TradeProposal:
        strategy_type = self._strategy_type_value(strategy)
        total_qty = float(sum(abs(int(getattr(leg, "quantity", 0) or 0)) for leg in strategy.legs) or 1.0)
        avg_price = abs(float(strategy.net_credit_debit or 0.0)) / max(1.0, total_qty)
        side = "buy" if float(strategy.net_credit_debit or 0.0) > 0.0 else "sell"
        notional = float(abs(strategy.max_loss or 0.0))
        portfolio_greeks = strategy.portfolio_greeks
        delta_per_unit = float(getattr(portfolio_greeks, "delta", 0.0) or 0.0) / max(1.0, total_qty)
        gamma_per_unit = float(getattr(portfolio_greeks, "gamma", 0.0) or 0.0) / max(1.0, total_qty)
        vega_per_unit = float(getattr(portfolio_greeks, "vega", 0.0) or 0.0) / max(1.0, total_qty)
        theta_per_unit = float(getattr(portfolio_greeks, "theta", 0.0) or 0.0) / max(1.0, total_qty)
        rho_per_unit = float(getattr(portfolio_greeks, "rho", 0.0) or 0.0) / max(1.0, total_qty)
        objective_ctx = self._objective_for_underlying(str(underlying).upper(), self.portfolio_overlay)
        sector_hint = self._prs_sector_for_underlying(str(underlying).upper(), objective_ctx)
        signal_ts = now.strftime("%Y%m%d%H%M%S")
        signal_id = f"sig_{str(underlying).upper()}_{signal_ts}"
        proposal_id = f"prop_{signal_id}_{strategy_type}"
        prs_symbol = self._prs_option_symbol(underlying, proposal_id)
        hedging_state = self._hedging_state_for_underlying(underlying, objective)
        return TradeProposal(
            proposal_id=proposal_id,
            origin=self._prs_origin_from_objective(objective),
            strategy_id=str(strategy_type),
            signal_id=signal_id,
            alpha_type=self._prs_alpha_type_from_objective(objective),
            expected_edge=float((decision.get("score_breakdown") or {}).get("base_score", 0.0) or 0.0),
            risk_score=float(notional / max(1.0, self._current_net_equity())),
            regime_context={
                "routed_regime": str(decision.get("routed_regime", "") or ""),
                "objective": str(objective or ""),
            },
            instrument_plan={
                "symbol": prs_symbol,
                "underlying_symbol": str(underlying).upper(),
                "side": side,
                "price": float(max(0.0, avg_price)),
                "quantity": float(total_qty),
                "direction": float(strategy.portfolio_greeks.delta),
                "instrument_type": "option",
                "greek_delta_per_unit": delta_per_unit,
                "greek_gamma_per_unit": gamma_per_unit,
                "greek_vega_per_unit": vega_per_unit,
                "greek_theta_per_unit": theta_per_unit,
                "greek_rho_per_unit": rho_per_unit,
                "sector": sector_hint,
                "lifecycle_action": "open",
                "position_key": proposal_id,
                "objective": str(objective or ""),
                "hedging_state": hedging_state,
            },
            requested_notional=float(max(0.0, notional)),
            certification_snapshot_hash=str(self.prs_cert_snapshot_hash or ""),
            decision_mode=PRSDecisionMode.AUTO,
            trigger_reason_code=str(decision.get("reason", "") or "proposal.runtime.default"),
            risk_override_flag=False,
        )

    def _build_prs_close_proposal(self, position: Position, now: datetime) -> TradeProposal:
        self._repair_position_metadata(position)
        metadata = position.metadata if isinstance(getattr(position, "metadata", {}), dict) else {}
        signal_id = f"close_{str(position.position_id)}_{now.strftime('%Y%m%d%H%M%S')}"
        notional = float(abs(position.current_value or position.entry_credit_debit or 0.0))
        side = "sell" if float(position.entry_credit_debit or 0.0) > 0.0 else "buy"
        total_qty = float(sum(abs(leg.quantity) for leg in position.legs) or 1.0)
        pos_greeks = position.greeks or position.entry_greeks
        delta_per_unit = float(getattr(pos_greeks, "delta", 0.0) or 0.0) / max(1.0, total_qty)
        gamma_per_unit = float(getattr(pos_greeks, "gamma", 0.0) or 0.0) / max(1.0, total_qty)
        vega_per_unit = float(getattr(pos_greeks, "vega", 0.0) or 0.0) / max(1.0, total_qty)
        theta_per_unit = float(getattr(pos_greeks, "theta", 0.0) or 0.0) / max(1.0, total_qty)
        rho_per_unit = float(getattr(pos_greeks, "rho", 0.0) or 0.0) / max(1.0, total_qty)
        objective = str(metadata.get("objective", "") or "")
        prs_symbol = str(metadata.get("prs_symbol", "") or "").strip() or f"OPT::{str(position.position_id or '').strip()}".upper()
        return TradeProposal(
            proposal_id=f"prop_{signal_id}",
            origin=self._prs_origin_from_objective(objective),
            strategy_id=str(position.strategy_type or "unknown"),
            signal_id=signal_id,
            alpha_type="closeout",
            expected_edge=0.0,
            risk_score=0.0,
            regime_context={"entry_regime": str(position.regime_at_entry)},
            instrument_plan={
                "symbol": prs_symbol,
                "underlying_symbol": str(getattr(position, "underlying", "") or ""),
                "side": side,
                "price": float(max(0.0, abs(position.current_value or 0.0)) / max(1.0, total_qty)),
                "quantity": float(total_qty),
                "instrument_type": "option",
                "greek_delta_per_unit": delta_per_unit,
                "greek_gamma_per_unit": gamma_per_unit,
                "greek_vega_per_unit": vega_per_unit,
                "greek_theta_per_unit": theta_per_unit,
                "greek_rho_per_unit": rho_per_unit,
                "close_only": True,
                "lifecycle_action": "close",
                "position_key": str(metadata.get("prs_position_key", "") or position.position_id),
                "realized_pnl": float(position.realized_pnl or 0.0),
                "objective": objective,
                "hedging_state": dict(metadata.get("hedging_state", {}) or {}),
            },
            requested_notional=notional,
            certification_snapshot_hash=str(self.prs_cert_snapshot_hash or ""),
            decision_mode=PRSDecisionMode.AUTO,
            trigger_reason_code=f"close.{str(position.exit_reason or 'rule')}",
            risk_override_flag=False,
        )

    def _prs_liquidity_snapshot(self, chain: pd.DataFrame, strategy: OptionStrategy) -> Dict[str, Any]:
        if chain.empty:
            return {"adv_notional": 0.0, "spread_bps": 0.0, "depth_qty": 0.0, "estimated_slippage_bps": 0.0}
        c = chain.copy()
        c["bid"] = pd.to_numeric(c.get("bid", 0.0), errors="coerce")
        c["ask"] = pd.to_numeric(c.get("ask", 0.0), errors="coerce")
        c["ltp"] = pd.to_numeric(c.get("ltp", c.get("premium", 0.0)), errors="coerce")
        c["volume"] = pd.to_numeric(c.get("volume", 0.0), errors="coerce")
        c["oi"] = pd.to_numeric(c.get("oi", 0.0), errors="coerce")
        leg_keys = {
            str(getattr(leg, "instrument_key", "") or "").strip()
            for leg in list(getattr(strategy, "legs", []) or [])
            if str(getattr(leg, "instrument_key", "") or "").strip()
        }
        if leg_keys and "instrument_key" in c.columns:
            filtered = c[c["instrument_key"].astype(str).isin(leg_keys)].copy()
            if not filtered.empty:
                c = filtered
        spread_bps = 0.0
        try:
            mid = (c["bid"] + c["ask"]) / 2.0
            spread = (c["ask"] - c["bid"]).clip(lower=0.0)
            ratios = (spread / mid.replace(0.0, np.nan)).dropna()
            spread_bps = float(ratios.median() * 10000.0) if not ratios.empty else 0.0
        except Exception:
            spread_bps = 0.0
        total_qty = float(sum(abs(int(getattr(leg, "quantity", 0) or 0)) for leg in strategy.legs) or 1.0)
        median_ltp = float(c["ltp"].dropna().median()) if not c["ltp"].dropna().empty else 0.0
        adv_notional = float((c["volume"].fillna(0.0) * c["ltp"].fillna(0.0)).sum())
        depth_qty = float(c["oi"].fillna(0.0).min()) if not c["oi"].dropna().empty else 0.0
        return {
            "adv_notional": float(max(adv_notional, median_ltp * total_qty * 10.0)),
            "spread_bps": float(max(0.0, spread_bps)),
            "depth_qty": float(max(depth_qty, total_qty)),
            "estimated_slippage_bps": float(min(250.0, max(0.0, spread_bps * 0.45))),
        }

    def run_cycle(self) -> Dict[str, Any]:
        now = _now_ist()
        logger.info(f"Running integrated options cycle at {now.isoformat(timespec='seconds')}")
        self._write_live_engine_heartbeat(now)
        self._check_hot_reload_signals()
        if self.prs_enabled and self.prs is not None:
            latest_ctx = self._build_prs_context()
            if latest_ctx != self.prs_context:
                self.prs_context = latest_ctx
                self.prs_cert_snapshot_hash = self._refresh_prs_certification_snapshot()

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

        total_cycle_underlyings = len(cycle_underlyings)
        self._write_cycle_progress_heartbeat(
            now,
            processed_underlyings=0,
            total_underlyings=total_cycle_underlyings,
            current_underlying=cycle_underlyings[0] if cycle_underlyings else None,
            phase="cycle_started",
        )

        for idx, underlying in enumerate(cycle_underlyings, start=1):
            if idx == 1 or idx % 5 == 0:
                self._write_cycle_progress_heartbeat(
                    _now_ist(),
                    processed_underlyings=idx - 1,
                    total_underlyings=total_cycle_underlyings,
                    current_underlying=underlying,
                    phase="scanning_underlyings",
                )
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
            underlying_regime = self._current_underlying_regime_context()
            regime_state = self.regime_detector.detect_regime(
                chain,
                iv_series,
                underlying_regime=underlying_regime,
            )
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
                "underlying_regime": underlying_regime,
                "iv_rank": float(regime_state.metrics.iv_rank),
                "confidence": float(regime_state.confidence),
            })
            execution_allowed, sentiment_gate = self._execution_allowed_for_underlying(
                underlying,
                objective_ctx,
                self.portfolio_overlay,
            )
            if sentiment_gate:
                decision["exact_sentiment"] = sentiment_gate
            if not execution_allowed:
                decision.update(
                    {
                        "status": "scan_only_sentiment_watch",
                        "reason": str(
                            sentiment_gate.get("eligibility_reason")
                            or "scan_only_below_execution_cutoff"
                        ),
                    }
                )
                cycle_diag["underlyings"].append(decision)
                continue

            self.regime_history.append({
                "timestamp": _to_iso(now),
                "underlying": underlying,
                "regime": str(getattr(regime_state.regime, "value", regime_state.regime)),
                "routed_regime": str(getattr(routed_regime, "value", routed_regime)),
                "underlying_regime": underlying_regime,
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
            crisis_strategy_override = self._should_bypass_alpha_os_strategy_gate(
                underlying,
                strategy_type_token,
                self.portfolio_overlay,
            )
            decision["alpha_os_strategy_gate"] = {
                "strategy_type": strategy_type_token,
                "blocked": bool(blocked_by_alpha),
                "reason": alpha_block_reason,
                "size_multiplier": float(alpha_strategy_multiplier),
                "override_active": bool(crisis_strategy_override),
                "override_reason": (
                    "sentiment_crisis_bear_put_override"
                    if crisis_strategy_override
                    else None
                ),
            }
            if blocked_by_alpha and not crisis_strategy_override:
                decision.update({
                    "status": "blocked_alpha_os_strategy_gate",
                    "reason": alpha_block_reason or "alpha_os_strategy_weight_block",
                })
                cycle_diag["underlyings"].append(decision)
                continue
            if crisis_strategy_override:
                logger.warning(
                    "Sentiment crisis detected; bypassing Alpha OS posterior gate for %s %s",
                    underlying,
                    strategy_type_token,
                )

            liq_snapshot = self._prs_liquidity_snapshot(chain, strategy)
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

            pre_scale_gate = self._passes_net_profit_gate(
                strategy,
                objective=str(objective_ctx.get("objective") or "balanced_overlay"),
                overlay=self.portfolio_overlay,
                liquidity_snapshot=liq_snapshot,
            )
            per_lot_risk = max(1.0, float(pre_scale_gate.get("net_max_loss", abs(float(strategy.max_loss or 0.0))) or 1.0))
            decision["trade_economics"] = {
                "per_lot_expected_net_pnl": float(pre_scale_gate.get("expected_net_pnl", 0.0) or 0.0),
                "per_lot_expected_gross_pnl": float(pre_scale_gate.get("expected_gross_pnl", 0.0) or 0.0),
                "per_lot_total_costs": float(pre_scale_gate.get("expected_total_costs", 0.0) or 0.0),
                "per_lot_slippage_cost": float(pre_scale_gate.get("expected_slippage_cost", 0.0) or 0.0),
                "per_lot_tax": float(pre_scale_gate.get("expected_tax", 0.0) or 0.0),
                "per_lot_net_max_loss": float(pre_scale_gate.get("net_max_loss", 0.0) or 0.0),
                "expected_slippage_bps": float(pre_scale_gate.get("expected_slippage_bps", 0.0) or 0.0),
                "cost_to_max_loss_ratio": float(pre_scale_gate.get("cost_to_max_loss_ratio", 0.0) or 0.0),
            }

            lots = self.capital_scaling.get_position_size(self.scaling_state, per_lot_risk)
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
            unit_risk = float(per_lot_risk)
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
                liquidity_snapshot=liq_snapshot,
            )
            strategy.max_loss = max(float(strategy.max_loss or 0.0), float(post_scale_gate.get("net_max_loss", 0.0) or 0.0))
            decision["net_profit_gate"] = {
                "passed": bool(post_scale_gate.get("passed", False)),
                "expected_net_pnl": float(post_scale_gate.get("expected_net_pnl", 0.0) or 0.0),
                "expected_gross_pnl": float(post_scale_gate.get("expected_gross_pnl", 0.0) or 0.0),
                "expected_total_costs": float(post_scale_gate.get("expected_total_costs", 0.0) or 0.0),
                "expected_slippage_cost": float(post_scale_gate.get("expected_slippage_cost", 0.0) or 0.0),
                "expected_tax": float(post_scale_gate.get("expected_tax", 0.0) or 0.0),
                "expected_slippage_bps": float(post_scale_gate.get("expected_slippage_bps", 0.0) or 0.0),
                "min_threshold": float(post_scale_gate.get("min_threshold", 0.0) or 0.0),
                "override_applied": bool(post_scale_gate.get("override_applied", False)),
                "slippage_ok": bool(post_scale_gate.get("slippage_ok", False)),
                "cost_ratio_ok": bool(post_scale_gate.get("cost_ratio_ok", False)),
                "cost_to_max_loss_ratio": float(post_scale_gate.get("cost_to_max_loss_ratio", 0.0) or 0.0),
                "net_max_loss": float(post_scale_gate.get("net_max_loss", 0.0) or 0.0),
            }
            if not bool(post_scale_gate.get("passed", False)):
                exp_net = float(post_scale_gate.get("expected_net_pnl", 0.0) or 0.0)
                min_thr = float(post_scale_gate.get("min_threshold", 0.0) or 0.0)
                slip_bps = float(post_scale_gate.get("expected_slippage_bps", 0.0) or 0.0)
                max_slip = float(post_scale_gate.get("max_expected_slippage_bps", 0.0) or 0.0)
                cost_ratio = float(post_scale_gate.get("cost_to_max_loss_ratio", 0.0) or 0.0)
                max_cost_ratio = float(post_scale_gate.get("max_cost_to_max_loss_ratio", 0.0) or 0.0)
                risk_budget = decision.get("risk_budget", {}) if isinstance(decision.get("risk_budget"), dict) else {}
                requested_lots = int(risk_budget.get("requested_lots", lots) or lots)
                affordable_lots = int(risk_budget.get("affordable_lots", lots) or lots)
                if not bool(post_scale_gate.get("slippage_ok", True)):
                    decision.update({
                        "status": "rejected_execution_friction",
                        "reason": f"expected slippage {slip_bps:.1f}bps exceeds cap {max_slip:.1f}bps",
                    })
                elif not bool(post_scale_gate.get("cost_ratio_ok", True)):
                    decision.update({
                        "status": "rejected_execution_friction",
                        "reason": f"cost-to-max-loss ratio {cost_ratio:.2f} exceeds cap {max_cost_ratio:.2f}",
                    })
                elif affordable_lots < requested_lots:
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
            prs_result = None
            if self.prs_enabled and self.prs is not None:
                open_proposal = self._build_prs_open_proposal(
                    strategy=strategy,
                    objective=str(objective_ctx.get("objective") or "balanced_overlay"),
                    underlying=underlying,
                    decision=decision,
                    now=open_time,
                )
                budget_snapshot = self._prs_budget_snapshot()
                risk_snapshot = self._prs_risk_snapshot()
                prs_result = self.prs.process_proposal(
                    open_proposal,
                    budget_snapshot=budget_snapshot,
                    risk_snapshot=risk_snapshot,
                    market_snapshot={
                        "regime_transition_probability": float((self.alpha_os_last_intent or {}).get("transition_probability", 0.0) or 0.0),
                        "vol_percentile_jump": float((decision.get("market_context") or {}).get("vol_jump", 0.0) or 0.0),
                        "correlation_spike": float((decision.get("market_context") or {}).get("corr_spike", 0.0) or 0.0),
                    },
                    market_liquidity_snapshot=liq_snapshot,
                    certification_context=dict(self.prs_context),
                    auto_fill=True,
                )
                if not bool(prs_result.approved):
                    decision.update(
                        {
                            "status": "rejected_prs",
                            "reason": str(prs_result.denial_reason or "prs_rejection"),
                            "prs": prs_result.to_dict(),
                        }
                    )
                    cycle_diag["underlyings"].append(decision)
                    continue
            position = self.position_manager.open_position(strategy, open_time)
            position.underlying = self._normalize_underlying_symbol(
                getattr(position, "underlying", ""),
                fallback=underlying,
            )
            if prs_result is not None and self.prs_enabled and self.prs is not None:
                instrument_plan = dict(open_proposal.instrument_plan or {})
                position.metadata = {
                    "prs_symbol": str(instrument_plan.get("symbol", "") or "").strip(),
                    "prs_position_key": str(instrument_plan.get("position_key", "") or "").strip(),
                    "underlying_symbol": str(instrument_plan.get("underlying_symbol", "") or position.underlying),
                    "objective": str(objective_ctx.get("objective") or "balanced_overlay"),
                    "reason": str(objective_ctx.get("reason") or decision.get("reason") or ""),
                    "hedging_state": dict(instrument_plan.get("hedging_state", {}) or {}),
                    "sector": str(instrument_plan.get("sector", "") or ""),
                }
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
                "prs_symbol": str((position.metadata or {}).get("prs_symbol", "") or ""),
                "prs": prs_result.to_dict() if prs_result is not None else {},
            })
            cycle_diag["underlyings"].append(decision)

        self._write_cycle_progress_heartbeat(
            _now_ist(),
            processed_underlyings=total_cycle_underlyings,
            total_underlyings=total_cycle_underlyings,
            current_underlying=None,
            phase="updating_positions",
        )

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
            entry_regime = str(getattr(pos.regime_at_entry, "value", pos.regime_at_entry) or "")
            current_regime_name = str(getattr(regime, "value", regime) or "")
            tracker = self.regime_flip_tracker.get(pos.position_id, {}) if isinstance(self.regime_flip_tracker, dict) else {}
            mismatch = bool(current_regime_name and current_regime_name != entry_regime)
            if mismatch:
                prior_regime = str(tracker.get("last_regime", "") or "")
                streak = int(tracker.get("streak", 0) or 0)
                streak = streak + 1 if prior_regime == current_regime_name else 1
                self.regime_flip_tracker[pos.position_id] = {
                    "last_regime": current_regime_name,
                    "streak": int(streak),
                    "last_observed_at": _to_iso(now),
                }
            else:
                self.regime_flip_tracker.pop(pos.position_id, None)
                streak = 0

            entry_time = pos.entry_time
            if getattr(entry_time, "tzinfo", None) is None:
                entry_time = entry_time.replace(tzinfo=now.tzinfo)
            else:
                entry_time = entry_time.astimezone(now.tzinfo)

            held_minutes = max((now - entry_time).total_seconds() / 60.0, 0.0)
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            since_open_minutes = max((now - market_open).total_seconds() / 60.0, 0.0)
            min_hold_minutes = max(0, int(getattr(self.config.exit_rules, "regime_flip_min_hold_minutes", 30) or 0))
            confirmation_cycles = max(1, int(getattr(self.config.exit_rules, "regime_flip_confirmation_cycles", 2) or 1))
            open_grace_minutes = max(0, int(getattr(self.config.exit_rules, "regime_flip_market_open_grace_minutes", 30) or 0))
            regime_flip_exit_allowed = (
                mismatch
                and streak >= confirmation_cycles
                and held_minutes >= float(min_hold_minutes)
                and since_open_minutes >= float(open_grace_minutes)
            )
            exit_signal = self.position_manager.check_exit_conditions(
                pos,
                regime,
                now.date(),
                current_time=now,
                regime_flip_exit_allowed=regime_flip_exit_allowed,
                minimum_hold_minutes=float(min_hold_minutes),
            )
            if not exit_signal:
                continue
            closed_pos = self.position_manager.close_position(
                pos,
                exit_time=now,
                exit_reason=exit_signal.reason.value,
            )
            self.regime_flip_tracker.pop(pos.position_id, None)
            prs_close = None
            if self.prs_enabled and self.prs is not None:
                close_proposal = self._build_prs_close_proposal(closed_pos, now)
                prs_close = self.prs.process_proposal(
                    close_proposal,
                    budget_snapshot={"reserve_usage": {}},
                    risk_snapshot={"risk_budget_ratio": 0.0},
                    market_snapshot={},
                    market_liquidity_snapshot={"adv_notional": 0.0, "spread_bps": 0.0, "depth_qty": 0.0, "estimated_slippage_bps": 0.0},
                    certification_context=dict(self.prs_context),
                    auto_fill=True,
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
                hold_duration_minutes=_position_hold_duration_minutes(closed_pos, fallback_now=now),
            )
            if prs_close is not None and (not prs_close.approved):
                logger.warning(
                    "PRS close proposal rejected for %s: %s",
                    closed_pos.position_id,
                    prs_close.denial_reason,
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
        self._refresh_runtime_accounting_artifacts(now, force=bool(opened or closed))

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
        if ts:
            compare_now = now if getattr(now, "tzinfo", None) is not None else _now_ist()
            compare_ts = ts.astimezone(compare_now.tzinfo) if getattr(ts, "tzinfo", None) is not None else ts.replace(tzinfo=compare_now.tzinfo)
            if (compare_now - compare_ts).total_seconds() > 45 * 60:
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
                    "hold_duration_minutes": _position_hold_duration_minutes(p),
                    "max_loss": float(p.max_loss or 0.0),
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
            _write_loop_status(
                {
                    "timestamp": cycle_start.isoformat(),
                    "status": "running",
                    "result_status": "running",
                    "mode": "single",
                    "last_cycle_started_at": cycle_start.isoformat(),
                    "last_cycle_finished_at": None,
                    "last_success_at": last_success_at,
                    "duration_seconds": 0.0,
                    "interval_minutes": interval_seconds / 60.0,
                    "next_cycle_eta": None,
                    "start_fresh_today": bool(args.start_fresh_today),
                    "recovery_mode": bool(args.recovery_mode),
                }
            )
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
            _write_loop_status(
                {
                    "timestamp": cycle_start.isoformat(),
                    "status": "running",
                    "result_status": "running",
                    "mode": "continuous",
                    "last_cycle_started_at": cycle_start.isoformat(),
                    "last_cycle_finished_at": None,
                    "last_success_at": last_success_at,
                    "duration_seconds": 0.0,
                    "interval_minutes": interval_seconds / 60.0,
                    "next_cycle_eta": None,
                    "start_fresh_today": bool(args.start_fresh_today),
                    "recovery_mode": bool(args.recovery_mode),
                }
            )
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
