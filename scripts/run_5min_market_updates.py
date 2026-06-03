#!/usr/bin/env python3
"""Canonical intraday market refresh loop for Northstar V3."""

from __future__ import annotations

import argparse
import contextlib
import base64
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_complete_v3_system import load_core_state_payload
from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
from src.ingestion.integrated_data_pipeline import IntegratedDataPipeline
from src.options.config_loader import get_config
from src.options.upstox_adapter import UpstoxAdapter


IST = ZoneInfo("Asia/Kolkata")
LOG_PATH = PROJECT_ROOT / "logs" / "market_loop.log"
STATUS_PATH = PROJECT_ROOT / "data" / "processed" / "market_refresh_status.json"
STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"
MARKET_DATA_PATH = PROJECT_ROOT / "data" / "options" / "live" / "market_data_latest.json"

INDEX_TICKERS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "IT": "^CNXIT",
    "FMCG": "^CNXFMCG",
    "AUTO": "^CNXAUTO",
    "PHARMA": "^CNXPHARMA",
    "METAL": "^CNXMETAL",
    "REALTY": "^CNXREALTY",
    "ENERGY": "^CNXENERGY",
    "PSU": "^CNXPSE",
}


def configure_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("northstar.market_loop")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(LOG_PATH)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    if sys.stdout.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger


def _market_hours(now: datetime) -> bool:
    if now.weekday() >= 5:
        return False
    return dt_time(9, 15) <= now.time() <= dt_time(15, 30)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _load_state() -> UnifiedState:
    state = UnifiedState()
    if STATE_PATH.exists():
        try:
            state.load_snapshot(json.loads(STATE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return state


def _daily_prev_close(ticker: str) -> float | None:
    def _coerce_close(frame: pd.DataFrame) -> pd.Series:
        close = frame.get("Close")
        if close is None:
            return pd.Series(dtype=float)
        if isinstance(close, pd.DataFrame):
            if close.shape[1] == 0:
                return pd.Series(dtype=float)
            close = close.iloc[:, -1]
        return pd.to_numeric(close, errors="coerce").dropna()

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            history = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=False)
        if history is None or history.empty:
            return None
        close = _coerce_close(history)
        if len(close) >= 2:
            return float(close.iloc[-2])
        if len(close) == 1:
            return float(close.iloc[-1])
    except Exception:
        return None
    return None


def _latest_intraday_close(ticker: str) -> float | None:
    def _coerce_close(frame: pd.DataFrame) -> pd.Series:
        close = frame.get("Close")
        if close is None:
            return pd.Series(dtype=float)
        if isinstance(close, pd.DataFrame):
            if close.shape[1] == 0:
                return pd.Series(dtype=float)
            close = close.iloc[:, -1]
        return pd.to_numeric(close, errors="coerce").dropna()

    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            history = yf.download(ticker, period="1d", interval="5m", progress=False, auto_adjust=False)
        if history is None or history.empty:
            return None
        close = _coerce_close(history)
        if not close.empty:
            return float(close.iloc[-1])
    except Exception:
        return None
    return None


def _build_quote(current_price: float | None, previous_close: float | None, provider: str) -> dict[str, Any]:
    current = float(current_price) if current_price is not None else 0.0
    previous = float(previous_close) if previous_close not in [None, 0] else current
    net_change = current - previous
    pct_change = (net_change / previous * 100.0) if previous else 0.0
    return {
        "current_price": current,
        "previous_close": previous,
        "net_change": net_change,
        "pct_change": pct_change,
        "provider": provider,
    }


def _get_access_token() -> str:
    env_token = str(os.getenv("UPSTOX_ACCESS_TOKEN", "") or "").strip()
    if env_token:
        return env_token
    try:
        config = get_config()
        return str(getattr(config.upstox, "access_token", "") or "").strip()
    except Exception:
        return ""


def _token_is_usable(token: str) -> bool:
    candidate = str(token or "").strip()
    if not candidate:
        return False
    try:
        parts = candidate.split(".")
        if len(parts) != 3:
            return True
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload + padding).decode("utf-8"))
        exp = float(decoded.get("exp", 0) or 0)
        return exp > time.time() + 60.0
    except Exception:
        return True


def _upstox_adapter() -> UpstoxAdapter | None:
    token = _get_access_token()
    if not _token_is_usable(token):
        return None
    try:
        config = get_config()
        config.upstox.access_token = token
        return UpstoxAdapter(config.upstox)
    except Exception:
        return None


def _fetch_market_snapshot(logger: logging.Logger) -> tuple[dict[str, Any], str]:
    adapter = _upstox_adapter()
    snapshot = {"timestamp": datetime.now(IST).isoformat(), "indices": {}}
    provider_hits: set[str] = set()

    for symbol, ticker in INDEX_TICKERS.items():
        current_price: float | None = None
        provider = "yfinance"

        if adapter is not None and symbol in {"NIFTY", "BANKNIFTY", "FINNIFTY"}:
            try:
                current_price = float(adapter.get_underlying_price(symbol))
                provider = "upstox"
            except Exception as exc:
                logger.warning("Upstox quote unavailable for %s: %s", symbol, exc)

        if current_price is None:
            current_price = _latest_intraday_close(ticker)
            provider = "yfinance"

        if current_price is None:
            logger.warning("No intraday quote available for %s", symbol)
            continue

        previous_close = _daily_prev_close(ticker)
        snapshot["indices"][symbol] = _build_quote(current_price, previous_close, provider)
        provider_hits.add(provider)

    provider_name = "+".join(sorted(provider_hits)) if provider_hits else "none"
    return snapshot, provider_name


def _sync_canonical_state(reason: str) -> UnifiedState:
    state = _load_state()
    core_payload = load_core_state_payload()
    authority = StateAuthority(
        state,
        config={
            "dev_mode": True,
            "checkpoint_path": str(STATE_PATH),
            "state_change_log_path": str(PROJECT_ROOT / "data" / "state" / "state_change_log.jsonl"),
        },
    )
    authority.register_writer(
        writer_id="market_loop",
        allowed_sections=["market", "macro", "regime"],
        priority=WritePriority.RESEARCH,
    )

    for section_name in ("market", "macro", "regime"):
        updates = [
            StateUpdate(
                writer_id="market_loop",
                section=section_name,
                field_path=field_path,
                new_value=value,
                priority=WritePriority.RESEARCH,
                source="SYSTEM",
                reason=reason,
            )
            for field_path, value in core_payload.get(section_name, {}).items()
        ]
        if updates:
            applied = authority.batch_update(updates)
            if applied != len(updates):
                raise RuntimeError(f"{section_name}_sync_incomplete:{applied}/{len(updates)}")
    authority.checkpoint(force=True)
    return state


def run_market_update(logger: logging.Logger) -> dict[str, Any]:
    started = datetime.now(IST)
    payload: dict[str, Any] = {"started_at": started.isoformat()}
    logger.info("Starting intraday market refresh at %s", started.isoformat())

    snapshot, provider_name = _fetch_market_snapshot(logger)
    if not snapshot.get("indices"):
        payload.update(
            {
                "pipeline_status": "FAILED",
                "provider": provider_name,
                "reason": "no_live_index_quotes",
                "finished_at": datetime.now(IST).isoformat(),
            }
        )
        _write_json(STATUS_PATH, payload)
        raise RuntimeError("market_refresh_failed:no_live_index_quotes")

    _write_json(MARKET_DATA_PATH, snapshot)

    pipeline = IntegratedDataPipeline()
    market_state = pipeline.integrate_with_market_state_spine()
    state = _sync_canonical_state("Intraday market refresh")

    payload.update(
        {
            "pipeline_status": "SUCCESS",
            "provider": provider_name,
            "quote_count": len(snapshot.get("indices", {})),
            "market_state": {
                "regime": state.market.regime,
                "allowed_exposure": state.market.allowed_exposure,
                "volatility_regime": state.market.volatility_regime,
                "last_updated": state.market.last_updated,
            },
            "snapshot_timestamp": snapshot.get("timestamp"),
            "integrated_market_state_available": bool(market_state),
            "finished_at": datetime.now(IST).isoformat(),
        }
    )
    _write_json(STATUS_PATH, payload)
    logger.info(
        "Intraday market refresh complete: provider=%s quotes=%s regime=%s",
        provider_name,
        payload["quote_count"],
        payload["market_state"]["regime"],
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the canonical intraday market refresh loop.")
    parser.add_argument("--interval-minutes", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--allow-outside-market-hours", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger = configure_logger()
    interval_seconds = max(60.0, float(args.interval_minutes) * 60.0)

    try:
        while True:
            now = datetime.now(IST)
            if not args.allow_outside_market_hours and not _market_hours(now):
                payload = {
                    "timestamp": now.isoformat(),
                    "pipeline_status": "SKIPPED",
                    "reason": "outside_market_hours",
                }
                _write_json(STATUS_PATH, payload)
                logger.info("Skipping market refresh outside market hours")
            else:
                run_market_update(logger)
            if args.once:
                return 0
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Market loop interrupted by user")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
