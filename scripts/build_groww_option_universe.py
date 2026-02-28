#!/usr/bin/env python3
"""
Build offline historical option-chain universe using broker historical APIs.

This script pulls option-contract candles (FNO) and writes normalized parquet
files consumable by the existing options system:
  data/options/historical/<underlying>_option_chains.parquet

Primary use case:
  - Build a local historical universe quickly while API access is available.
  - Reuse the files later in offline mode and runtime API-fallback mode.

Auth modes supported:
  - Groww:
      * Direct token via GROWW_API_AUTH_TOKEN / --api-token
      * API-key exchange via /token/api/access using key + secret/totp
  - Upstox:
      * Direct access token via UPSTOX_ACCESS_TOKEN / --upstox-access-token / --api-token
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import time
import uuid
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

try:
    from growwapi import GrowwAPI
except Exception:  # pragma: no cover - optional dependency
    GrowwAPI = None


IST = timezone(timedelta(hours=5, minutes=30))
GROWW_BASE_URL = "https://api.groww.in/v1"
INSTRUMENT_MASTER_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"
DEFAULT_LOCAL_INSTRUMENT_PATH = Path("universe/instrument.csv")
GROWW_BACKTESTING_START_DATE = date(2020, 1, 1)
UPSTOX_BASE_URL = "https://api.upstox.com"
UPSTOX_INSTRUMENT_MASTER_URL = "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
UPSTOX_INTRADAY_HISTORY_START_DATE = date(2022, 1, 1)
UPSTOX_EOD_HISTORY_START_DATE = date(2000, 1, 1)
DEFAULT_INDEX_SYMBOLS = [
    "NIFTY",
    "BANKNIFTY",
    "FINNIFTY",
    "MIDCPNIFTY",
    "NIFTYIT",
    "NIFTYAUTO",
    "NIFTYPHARMA",
    "NIFTYFMCG",
    "NIFTYMETAL",
    "NIFTYENERGY",
    "NIFTYREALTY",
]
INDEX_SPOT_ALIASES: Dict[str, List[str]] = {
    "NIFTY": ["NIFTY", "NIFTY 50", "NIFTY50"],
    "BANKNIFTY": ["BANKNIFTY", "NIFTY BANK"],
    "FINNIFTY": ["FINNIFTY", "NIFTY FIN SERVICE", "NIFTY FINANCIAL SERVICES"],
    "MIDCPNIFTY": ["MIDCPNIFTY", "NIFTY MID SELECT", "NIFTY MIDCAP SELECT"],
}
UPSTOX_INDEX_KEY_MAP: Dict[str, str] = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
    "NIFTYIT": "NSE_INDEX|Nifty IT",
    "NIFTYAUTO": "NSE_INDEX|Nifty Auto",
    "NIFTYPHARMA": "NSE_INDEX|Nifty Pharma",
    "NIFTYFMCG": "NSE_INDEX|Nifty FMCG",
    "NIFTYMETAL": "NSE_INDEX|Nifty Metal",
    "NIFTYENERGY": "NSE_INDEX|Nifty Energy",
    "NIFTYREALTY": "NSE_INDEX|Nifty Realty",
}


logger = logging.getLogger("options.groww_universe")


class GrowwForbiddenError(RuntimeError):
    """Raised when Groww denies access to requested API resources."""


class GrowwRateLimitError(RuntimeError):
    """Raised when Groww SDK rate limits historical requests."""


def _today_ist() -> date:
    return datetime.now(IST).date()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _to_groww_ts(d: date, end_of_day: bool = False) -> str:
    suffix = "23:59:59" if end_of_day else "00:00:00"
    return f"{d.isoformat()} {suffix}"


def _normalize_candle_interval(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in ("", "1day", "1d", "day", "daily"):
        return "1day"
    if raw in ("1week", "1w", "week", "weekly"):
        return "1week"
    if raw.endswith("minute"):
        prefix = raw[:-6]
        if prefix.isdigit():
            return f"{int(prefix)}minute"
    if raw.endswith("min"):
        prefix = raw[:-3]
        if prefix.isdigit():
            return f"{int(prefix)}minute"
    if raw.endswith("m"):
        prefix = raw[:-1]
        if prefix.isdigit():
            return f"{int(prefix)}minute"
    if raw.isdigit():
        return f"{int(raw)}minute"
    return raw or "1day"


def _interval_tag(interval: str) -> str:
    text = _normalize_candle_interval(interval)
    return (
        text.replace("minute", "m")
        .replace("day", "d")
        .replace("week", "w")
        .replace("/", "_")
        .replace(" ", "_")
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _normal_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    sigma: float,
    option_type: str,
) -> float:
    if spot <= 0 or strike <= 0:
        return 0.0

    if time_to_expiry <= 0 or sigma <= 0:
        intrinsic = max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)
        return intrinsic

    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * sigma * sigma) * time_to_expiry
    ) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    if option_type == "CE":
        return spot * _normal_cdf(d1) - strike * math.exp(-risk_free_rate * time_to_expiry) * _normal_cdf(d2)
    return strike * math.exp(-risk_free_rate * time_to_expiry) * _normal_cdf(-d2) - spot * _normal_cdf(-d1)


def _implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: str,
) -> float:
    if spot <= 0 or strike <= 0:
        return 0.20

    market_price = max(0.01, float(market_price))
    intrinsic = max(0.0, spot - strike) if option_type == "CE" else max(0.0, strike - spot)
    if market_price <= intrinsic + 1e-6:
        return 0.05

    low = 0.01
    high = 3.0

    # Expand upper bound if needed.
    for _ in range(6):
        high_price = _black_scholes_price(spot, strike, time_to_expiry, risk_free_rate, high, option_type)
        if high_price >= market_price:
            break
        high = min(8.0, high * 1.6)

    for _ in range(40):
        mid = 0.5 * (low + high)
        model = _black_scholes_price(spot, strike, time_to_expiry, risk_free_rate, mid, option_type)
        if model > market_price:
            high = mid
        else:
            low = mid

    return max(0.01, min(5.0, 0.5 * (low + high)))


def _option_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    sigma: float,
    option_type: str,
) -> Tuple[float, float, float, float]:
    if (
        spot <= 0
        or strike <= 0
        or sigma <= 0
        or time_to_expiry <= 0
    ):
        delta = 0.5 if option_type == "CE" else -0.5
        return delta, 0.0, 0.0, 0.0

    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (
        math.log(spot / strike)
        + (risk_free_rate + 0.5 * sigma * sigma) * time_to_expiry
    ) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    pdf_d1 = _normal_pdf(d1)
    if option_type == "CE":
        delta = _normal_cdf(d1)
        theta = (
            -(spot * pdf_d1 * sigma) / (2 * sqrt_t)
            - risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * _normal_cdf(d2)
        )
    else:
        delta = _normal_cdf(d1) - 1.0
        theta = (
            -(spot * pdf_d1 * sigma) / (2 * sqrt_t)
            + risk_free_rate * strike * math.exp(-risk_free_rate * time_to_expiry) * _normal_cdf(-d2)
        )

    gamma = pdf_d1 / (spot * sigma * sqrt_t)
    vega = spot * pdf_d1 * sqrt_t / 100.0  # Per 1% IV move
    theta_per_day = theta / 365.0
    return delta, gamma, theta_per_day, vega


def _estimate_bid_ask(ltp: float) -> Tuple[float, float]:
    mid = max(0.01, float(ltp))
    if mid < 5:
        spread = max(0.05, mid * 0.05)
    elif mid < 25:
        spread = max(0.05, mid * 0.02)
    else:
        spread = max(0.10, mid * 0.01)
    bid = max(0.01, mid - spread / 2.0)
    ask = max(bid + 0.01, mid + spread / 2.0)
    return bid, ask


def _parse_candle_timestamp(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        ts = float(raw)
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST)
        except Exception:
            return None

    text = str(raw).strip()
    if not text:
        return None

    if text.isdigit():
        return _parse_candle_timestamp(int(text))

    # Supports ISO timestamps with timezone offsets returned by Upstox
    # (example: 2025-01-01T00:00:00+05:30).
    try:
        iso_text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=IST)
        except Exception:
            continue

    return None


def _parse_candles(payload: Any) -> pd.DataFrame:
    if isinstance(payload, dict):
        candles = payload.get("candles", []) or payload.get("data", [])
    elif isinstance(payload, list):
        candles = payload
    else:
        candles = []

    rows: List[Dict[str, Any]] = []
    for candle in candles:
        if isinstance(candle, dict):
            ts = candle.get("timestamp") or candle.get("time") or candle.get("t")
            open_px = candle.get("open")
            high_px = candle.get("high")
            low_px = candle.get("low")
            close_px = candle.get("close")
            volume = candle.get("volume", 0)
            oi = candle.get("oi", candle.get("open_interest", 0))
        elif isinstance(candle, (list, tuple)):
            if len(candle) < 5:
                continue
            ts = candle[0]
            open_px = candle[1]
            high_px = candle[2]
            low_px = candle[3]
            close_px = candle[4]
            volume = candle[5] if len(candle) >= 6 else 0
            oi = candle[6] if len(candle) >= 7 else 0
        else:
            continue

        dt = _parse_candle_timestamp(ts)
        if dt is None:
            continue

        rows.append(
            {
                "timestamp": dt,
                "date": dt.date(),
                "open": _safe_float(open_px),
                "high": _safe_float(high_px),
                "low": _safe_float(low_px),
                "close": _safe_float(close_px),
                "volume": int(round(_safe_float(volume, 0.0))),
                "oi": int(round(_safe_float(oi, 0.0))),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["timestamp", "date", "open", "high", "low", "close", "volume", "oi"])

    out = pd.DataFrame(rows)
    out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    return out.reset_index(drop=True)


def _extract_groww_token_from_response(body: Any) -> str:
    if not isinstance(body, dict):
        return ""

    payload = body.get("payload")
    if isinstance(payload, dict):
        for key in ("access_token", "token", "auth_token"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    elif isinstance(payload, str) and payload.strip():
        return payload.strip()

    for key in ("access_token", "token", "auth_token"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _generate_groww_access_token(
    api_key: str,
    api_secret: str = "",
    api_totp: str = "",
    timeout_seconds: int = 30,
    max_retries: int = 3,
) -> str:
    key = str(api_key or "").strip()
    secret = str(api_secret or "").strip()
    totp = str(api_totp or "").strip()
    if not key:
        raise ValueError("Missing Groww API key")
    if not secret and not totp:
        raise ValueError("Provide api_secret (approval flow) or api_totp (totp flow)")

    url = f"{GROWW_BASE_URL}/token/api/access"
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-VERSION": "1.0",
        "x-request-id": str(uuid.uuid4()),
    }

    if secret:
        timestamp = str(int(time.time()))
        checksum = hashlib.sha256(f"{secret}{timestamp}".encode("utf-8")).hexdigest()
        req_body = {
            "key_type": "approval",
            "checksum": checksum,
            "timestamp": timestamp,
        }
        mode = "approval"
    else:
        req_body = {
            "key_type": "totp",
            "totp": totp,
        }
        mode = "totp"

    retries = max(1, int(max_retries))
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=req_body,
                timeout=max(5, int(timeout_seconds)),
            )
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                backoff = 1.5 ** attempt
                logger.warning(
                    f"Groww access-token request transient status {response.status_code}, retrying in {backoff:.1f}s"
                )
                time.sleep(backoff)
                continue
            response.raise_for_status()
            body = response.json()
            if isinstance(body, dict) and body.get("status") == "FAILURE":
                err = body.get("error", {})
                code = err.get("code", "UNKNOWN")
                msg = err.get("message", "Groww auth failure")
                raise RuntimeError(f"Groww auth error {code}: {msg}")
            token = _extract_groww_token_from_response(body)
            if not token:
                raise RuntimeError(f"Groww auth response missing token fields for mode={mode}")
            return token
        except Exception as exc:
            last_err = exc
            if attempt < retries - 1:
                backoff = 1.5 ** attempt
                logger.warning(f"Groww access-token request failed, retrying in {backoff:.1f}s: {exc}")
                time.sleep(backoff)
                continue
            break
    raise RuntimeError(f"Unable to generate Groww access token via /token/api/access: {last_err}") from last_err


class GrowwBacktestingClient:
    """Groww backtesting client with optional Python SDK candle transport."""

    def __init__(
        self,
        auth_token: str,
        base_url: str = GROWW_BASE_URL,
        timeout_seconds: int = 30,
        request_interval_seconds: float = 0.20,
        max_retries: int = 4,
        use_python_sdk: bool = False,
        sdk_fallback_to_rest: bool = True,
    ) -> None:
        token = str(auth_token or "").strip()
        if not token:
            raise ValueError("Missing Groww auth token")
        self.auth_token = token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = int(timeout_seconds)
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self.max_retries = max(1, int(max_retries))
        self.use_python_sdk = bool(use_python_sdk)
        self.sdk_fallback_to_rest = bool(sdk_fallback_to_rest)
        self._last_request_at = 0.0
        self._sdk = None

        if self.use_python_sdk:
            if GrowwAPI is None:
                raise RuntimeError(
                    "Python SDK mode requested but 'growwapi' is not installed. "
                    "Install it with: python3 -m pip install growwapi"
                )
            warnings.filterwarnings(
                "once",
                message=r"`get_historical_candle_data` is deprecated.*",
                category=DeprecationWarning,
            )
            self._sdk = GrowwAPI(self.auth_token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
            "X-API-VERSION": "1.0",
            "x-request-id": str(uuid.uuid4()),
        }

    def _wait_for_rate_limit(self) -> None:
        if self.request_interval_seconds <= 0:
            return
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)

    @staticmethod
    def _extract_payload(body: Any) -> Any:
        if isinstance(body, dict):
            if body.get("status") == "FAILURE":
                err = body.get("error", {})
                code = err.get("code", "UNKNOWN")
                msg = err.get("message", "Groww API failure")
                code_text = str(code).strip()
                if code_text in ("401", "403"):
                    raise GrowwForbiddenError(f"Groww API error {code_text}: {msg}")
                raise RuntimeError(f"Groww API error {code}: {msg}")
            if "payload" in body:
                return body.get("payload")
        return body

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            self._wait_for_rate_limit()
            self._last_request_at = time.time()
            try:
                response = requests.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout_seconds,
                )

                # Authorization failures are not transient; do not retry.
                if response.status_code in (401, 403):
                    try:
                        body = response.json()
                    except Exception:
                        body = {"raw": response.text[:500]}
                    raise GrowwForbiddenError(
                        f"HTTP {response.status_code} for {path} params={params} body={body}"
                    )

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries - 1:
                        backoff = 1.5 ** attempt
                        logger.warning(
                            f"Groww transient status {response.status_code} at {path}, retrying in {backoff:.1f}s"
                        )
                        time.sleep(backoff)
                        continue

                response.raise_for_status()
                body = response.json()
                return self._extract_payload(body)

            except Exception as exc:
                if isinstance(exc, GrowwForbiddenError):
                    raise
                last_err = exc
                if attempt < self.max_retries - 1:
                    backoff = 1.5 ** attempt
                    logger.warning(f"Groww request failed ({path}), retrying in {backoff:.1f}s: {exc}")
                    time.sleep(backoff)
                    continue
                break

        raise RuntimeError(f"Groww request failed for {path}: {last_err}") from last_err

    def download_instrument_master(self) -> pd.DataFrame:
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                response = requests.get(INSTRUMENT_MASTER_URL, timeout=self.timeout_seconds)
                response.raise_for_status()
                return pd.read_csv(StringIO(response.text), dtype=str)
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries - 1:
                    backoff = 1.5 ** attempt
                    logger.warning(
                        f"Instrument master download failed via requests (attempt {attempt + 1}/{self.max_retries}), retrying in {backoff:.1f}s: {exc}"
                    )
                    time.sleep(backoff)

        # requests failed; try curl as a transport fallback
        try:
            result = subprocess.run(
                ["curl", "-sS", INSTRUMENT_MASTER_URL],
                check=True,
                capture_output=True,
                text=True,
                timeout=max(30, self.timeout_seconds),
            )
            if not result.stdout.strip():
                raise RuntimeError("curl returned empty instrument master payload")
            return pd.read_csv(StringIO(result.stdout), dtype=str)
        except Exception as curl_exc:
            raise RuntimeError(
                f"Unable to download instrument master via requests/curl. "
                f"Last requests error: {last_err}. Curl error: {curl_exc}"
            ) from curl_exc

    @staticmethod
    def _strip_exchange_prefix(symbol: str) -> str:
        text = str(symbol or "").strip()
        if "-" not in text:
            return text
        prefix, rest = text.split("-", 1)
        if prefix.isalpha() and 2 <= len(prefix) <= 5:
            return rest
        return text

    @staticmethod
    def _parse_interval_minutes(candle_interval: str) -> Optional[int]:
        raw = _normalize_candle_interval(candle_interval)
        if raw == "1day":
            return 1440
        if raw == "1week":
            return 10080
        if raw.endswith("minute"):
            value = raw[:-6]
            if value.isdigit():
                v = int(value)
                return v if v > 0 else None
        return None

    @classmethod
    def _max_window_days_for_interval(cls, candle_interval: str) -> int:
        """
        Conservative window sizes based on Groww Python SDK historical-data limits.
        """
        minutes = cls._parse_interval_minutes(candle_interval)
        if minutes is None:
            return 7
        # Explicit SDK-documented limits
        if minutes == 1:
            return 7
        if minutes == 5:
            return 15
        if minutes == 10:
            return 30
        if minutes == 60:
            return 150
        if minutes == 240:
            return 365
        if minutes == 1440:
            return 1080  # ~3 years
        if minutes == 10080:
            return 3650

        # Safe fallbacks for other intervals.
        if minutes < 60:
            return 30
        if minutes < 240:
            return 100
        if minutes < 1440:
            return 365
        if minutes < 10080:
            return 1080
        return 3650

    @staticmethod
    def _looks_forbidden(exc: Exception) -> bool:
        text = str(exc or "").lower()
        return "403" in text or "forbidden" in text or "access forbidden" in text

    @staticmethod
    def _looks_rate_limit(exc: Exception) -> bool:
        text = str(exc or "").lower()
        return "rate limit" in text or "rate-limit" in text or "breached" in text or "429" in text

    @staticmethod
    def _looks_invalid_interval(exc: Exception) -> bool:
        text = str(exc or "").lower()
        return "invalid interval value" in text or "choose a larger interval" in text

    def _sdk_exchange_value(self, exchange: str) -> Any:
        if self._sdk is None:
            return exchange
        attr = f"EXCHANGE_{str(exchange or '').strip().upper()}"
        return getattr(self._sdk, attr, str(exchange or "NSE").strip().upper() or "NSE")

    def _sdk_segment_value(self, segment: str) -> Any:
        if self._sdk is None:
            return segment
        seg = str(segment or "").strip().upper()
        if seg == "INDEX":
            seg = "CASH"
        attr = f"SEGMENT_{seg}"
        return getattr(self._sdk, attr, seg or "CASH")

    @staticmethod
    def _derive_sdk_trading_symbol_from_groww(groww_symbol: str) -> Optional[str]:
        # Example:
        #   NSE-NIFTY-17Feb26-26000-CE -> NIFTY2621726000CE
        parts = str(groww_symbol or "").strip().upper().split("-")
        if len(parts) < 5:
            return None
        option_type = parts[-1]
        strike = parts[-2]
        expiry_text = parts[-3]
        underlying = "-".join(parts[1:-3]).replace("-", "")
        if option_type not in ("CE", "PE") or not underlying:
            return None
        try:
            expiry = datetime.strptime(expiry_text.title(), "%d%b%y")
        except Exception:
            return None
        strike_num = _safe_float(strike, -1)
        if strike_num <= 0:
            return None
        strike_text = str(int(round(strike_num)))
        expiry_code = f"{expiry.year % 100:02d}{expiry.month}{expiry.day:02d}"
        return f"{underlying}{expiry_code}{strike_text}{option_type}"

    def _sdk_symbol_candidates(self, groww_symbol: str, trading_symbol: Optional[str]) -> List[str]:
        candidates: List[str] = []
        derived = self._derive_sdk_trading_symbol_from_groww(groww_symbol)
        for raw in (trading_symbol, derived, groww_symbol, self._strip_exchange_prefix(groww_symbol)):
            text = str(raw or "").strip()
            if text and text not in candidates:
                candidates.append(text)
        return candidates

    def _get_historical_candles_via_sdk(
        self,
        exchange: str,
        segment: str,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        candle_interval: str,
        trading_symbol: Optional[str] = None,
    ) -> Any:
        if self._sdk is None:
            raise RuntimeError("Groww SDK is not initialized")

        interval_in_minutes = self._parse_interval_minutes(candle_interval)
        exchange_value = self._sdk_exchange_value(exchange)
        segment_value = self._sdk_segment_value(segment)
        timeout_sec = max(5, int(self.timeout_seconds))
        last_err: Optional[Exception] = None
        modern_forbidden_exc: Optional[Exception] = None

        # Primary path: use non-deprecated SDK method with groww_symbol + explicit timeout.
        if hasattr(self._sdk, "get_historical_candles"):
            for attempt in range(self.max_retries):
                try:
                    self._wait_for_rate_limit()
                    kwargs_gc: Dict[str, Any] = {
                        "exchange": exchange_value,
                        "segment": segment_value,
                        "groww_symbol": groww_symbol,
                        "start_time": start_time,
                        "end_time": end_time,
                        "candle_interval": candle_interval,
                        "timeout": timeout_sec,
                    }
                    self._last_request_at = time.time()
                    payload = self._sdk.get_historical_candles(**kwargs_gc)
                    return self._extract_payload(payload)
                except Exception as exc:
                    if self._looks_forbidden(exc):
                        # Some accounts are currently allowed on legacy get_historical_candle_data
                        # but forbidden on get_historical_candles. Fall back before hard failing.
                        modern_forbidden_exc = exc
                        break
                    if self._looks_rate_limit(exc):
                        last_err = exc
                        if attempt < self.max_retries - 1:
                            backoff = max(1.0, (2.0 ** attempt) * max(0.5, self.request_interval_seconds))
                            logger.warning(
                                f"Groww SDK rate limited for {groww_symbol}, retrying in {backoff:.1f}s "
                                f"({attempt + 1}/{self.max_retries})"
                            )
                            time.sleep(backoff)
                            continue
                        raise GrowwRateLimitError(
                            f"Groww SDK rate limit persisted for {groww_symbol}: {last_err}"
                        ) from last_err
                    last_err = exc
                    break

        candidates = self._sdk_symbol_candidates(groww_symbol, trading_symbol)
        for attempt in range(self.max_retries):
            saw_rate_limit = False
            for symbol_candidate in candidates:
                try:
                    self._wait_for_rate_limit()
                    kwargs: Dict[str, Any] = {
                        "trading_symbol": symbol_candidate,
                        "exchange": exchange_value,
                        "segment": segment_value,
                        "start_time": start_time,
                        "end_time": end_time,
                        "timeout": timeout_sec,
                    }
                    if interval_in_minutes is not None:
                        kwargs["interval_in_minutes"] = interval_in_minutes
                    with warnings.catch_warnings():
                        warnings.filterwarnings(
                            "ignore",
                            message=r"`get_historical_candle_data` is deprecated.*",
                            category=DeprecationWarning,
                        )
                        self._last_request_at = time.time()
                        payload = self._sdk.get_historical_candle_data(**kwargs)
                    return self._extract_payload(payload)
                except Exception as exc:
                    if self._looks_forbidden(exc):
                        raise GrowwForbiddenError(
                            f"Groww SDK forbidden for symbol={symbol_candidate} exchange={exchange} segment={segment}: {exc}"
                        ) from exc
                    if self._looks_rate_limit(exc):
                        saw_rate_limit = True
                        last_err = exc
                        break
                    last_err = exc
                    continue

            if saw_rate_limit:
                if attempt < self.max_retries - 1:
                    backoff = max(1.0, (2.0 ** attempt) * max(0.5, self.request_interval_seconds))
                    logger.warning(
                        f"Groww SDK rate limited for {groww_symbol}, retrying in {backoff:.1f}s "
                        f"({attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(backoff)
                    continue
                raise GrowwRateLimitError(
                    f"Groww SDK rate limit persisted for {groww_symbol}: {last_err}"
                ) from last_err
            break

        if modern_forbidden_exc is not None:
            logger.debug(
                f"SDK get_historical_candles forbidden for {groww_symbol}; trying legacy get_historical_candle_data fallback"
            )

        if last_err is not None and "correct value of trading symbol" in str(last_err).lower():
            # Invalid/unsupported trading_symbol format for this instrument. Treat as no-data
            # in SDK mode instead of forcing a REST fallback that may be forbidden.
            return {"candles": []}

        raise RuntimeError(
            f"Groww SDK historical candles failed for groww_symbol={groww_symbol}, trading_symbol={trading_symbol}: {last_err}"
        ) from last_err

    def get_historical_candles(
        self,
        exchange: str,
        segment: str,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        candle_interval: str = "1day",
        trading_symbol: Optional[str] = None,
    ) -> Any:
        if self.use_python_sdk:
            try:
                return self._get_historical_candles_via_sdk(
                    exchange=exchange,
                    segment=segment,
                    groww_symbol=groww_symbol,
                    start_time=start_time,
                    end_time=end_time,
                    candle_interval=candle_interval,
                    trading_symbol=trading_symbol,
                )
            except GrowwForbiddenError:
                raise
            except Exception as exc:
                if str(segment or "").strip().upper() == "FNO":
                    # On many accounts REST /historical/candles FNO is forbidden while SDK range works.
                    # Never fallback FNO SDK failures to REST to avoid hard-stop 403.
                    raise
                if self._looks_rate_limit(exc) or self._looks_invalid_interval(exc):
                    raise
                if not self.sdk_fallback_to_rest:
                    raise
                logger.warning(f"Groww SDK candles failed, falling back to REST for {groww_symbol}: {exc}")

        params = {
            "exchange": exchange,
            "segment": segment,
            "groww_symbol": groww_symbol,
            "start_time": start_time,
            "end_time": end_time,
            "candle_interval": candle_interval,
        }
        return self._get("/historical/candles", params=params)

    def get_expiries(
        self,
        exchange: str,
        underlying_symbol: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Any:
        params: Dict[str, Any] = {
            "exchange": exchange,
            "underlying_symbol": underlying_symbol,
        }
        if year is not None:
            params["year"] = str(year)
        if month is not None:
            params["month"] = str(month)
        return self._get("/historical/expiries", params=params)

    def get_contracts(
        self,
        exchange: str,
        underlying_symbol: str,
        expiry_date: str,
    ) -> Any:
        params = {
            "exchange": exchange,
            "underlying_symbol": underlying_symbol,
            "expiry_date": expiry_date,
        }
        return self._get("/historical/contracts", params=params)


class UpstoxHistoricalClient:
    """Upstox historical-data client compatible with the existing builder interface."""

    def __init__(
        self,
        access_token: str,
        base_url: str = UPSTOX_BASE_URL,
        timeout_seconds: int = 30,
        request_interval_seconds: float = 0.40,
        max_retries: int = 4,
    ) -> None:
        token = str(access_token or "").strip()
        if not token:
            raise ValueError("Missing Upstox access token")
        self.auth_token = token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = int(timeout_seconds)
        self.request_interval_seconds = max(0.0, float(request_interval_seconds))
        self.max_retries = max(1, int(max_retries))

        # Exposed to preserve compatibility with Groww builder behavior.
        self.use_python_sdk = False
        self.sdk_fallback_to_rest = False

        self._last_request_at = 0.0
        self._instrument_master_loaded = False
        self._normalized_instruments = pd.DataFrame()
        self._option_master = pd.DataFrame()
        self._underlying_key_by_symbol: Dict[str, str] = {
            str(sym).strip().upper(): str(key).strip()
            for sym, key in UPSTOX_INDEX_KEY_MAP.items()
        }
        # Upstox expired-instruments expiries API does not support year/month filtering.
        self.supports_year_filtered_expiries = False
        self._expired_plus_available: Optional[bool] = None
        self._expired_plus_warned = False
        self._expired_expiries_cache: Dict[str, List[str]] = {}
        self._expired_contracts_cache: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.auth_token}",
            "Accept": "application/json",
        }

    def _wait_for_rate_limit(self) -> None:
        if self.request_interval_seconds <= 0:
            return
        elapsed = time.time() - self._last_request_at
        if elapsed < self.request_interval_seconds:
            time.sleep(self.request_interval_seconds - elapsed)

    @staticmethod
    def _extract_error_fields(body: Any) -> Tuple[str, str]:
        if not isinstance(body, dict):
            return ("UNKNOWN", str(body)[:200])
        err = body.get("error")
        if isinstance(err, dict):
            return (str(err.get("code", "UNKNOWN")), str(err.get("message", "Unknown error")))
        errs = body.get("errors")
        if isinstance(errs, list) and errs:
            first = errs[0]
            if isinstance(first, dict):
                return (str(first.get("errorCode", first.get("code", "UNKNOWN"))), str(first.get("message", "Unknown error")))
            return ("UNKNOWN", str(first))
        return ("UNKNOWN", str(body))

    @classmethod
    def _extract_payload(cls, body: Any) -> Any:
        if isinstance(body, dict):
            status = str(body.get("status", "")).strip().lower()
            if status and status != "success":
                code, msg = cls._extract_error_fields(body)
                if code in ("401", "403"):
                    raise GrowwForbiddenError(f"Upstox API error {code}: {msg}")
                raise RuntimeError(f"Upstox API error {code}: {msg}")
            if "data" in body:
                return body.get("data")
        return body

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.base_url}{path}"
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries):
            self._wait_for_rate_limit()
            self._last_request_at = time.time()
            try:
                response = requests.get(
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout_seconds,
                )

                if response.status_code in (401, 403):
                    try:
                        body = response.json()
                    except Exception:
                        body = {"raw": response.text[:500]}
                    code, msg = self._extract_error_fields(body)
                    raise GrowwForbiddenError(
                        f"HTTP {response.status_code} for {path} params={params} code={code} message={msg}"
                    )

                if response.status_code == 429:
                    if attempt < self.max_retries - 1:
                        backoff = 1.6 ** attempt
                        logger.warning(f"Upstox rate-limited at {path}, retrying in {backoff:.1f}s")
                        time.sleep(backoff)
                        continue
                    raise GrowwRateLimitError(f"Upstox HTTP 429 at {path} params={params}")

                if response.status_code in (500, 502, 503, 504):
                    if attempt < self.max_retries - 1:
                        backoff = 1.5 ** attempt
                        logger.warning(f"Upstox transient status {response.status_code} at {path}, retrying in {backoff:.1f}s")
                        time.sleep(backoff)
                        continue

                response.raise_for_status()
                body = response.json()
                return self._extract_payload(body)

            except Exception as exc:
                if isinstance(exc, (GrowwForbiddenError, GrowwRateLimitError)):
                    raise
                last_err = exc
                if attempt < self.max_retries - 1:
                    backoff = 1.5 ** attempt
                    logger.warning(f"Upstox request failed ({path}), retrying in {backoff:.1f}s: {exc}")
                    time.sleep(backoff)
                    continue
                break

        raise RuntimeError(f"Upstox request failed for {path}: {last_err}") from last_err

    @staticmethod
    def _parse_expiry_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1e12:
                ts = ts / 1000.0
            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST).date()
            except Exception:
                return None
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            return UpstoxHistoricalClient._parse_expiry_date(int(text))
        text = text.replace("T", " ").replace("Z", "").strip()
        if " " in text:
            text = text.split(" ", 1)[0]
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt.date()
        except Exception:
            return None

    @staticmethod
    def _safe_upper(value: Any) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _to_iso_date_str(value: Any) -> str:
        parsed = UpstoxHistoricalClient._parse_expiry_date(value)
        return parsed.isoformat() if parsed is not None else ""

    @staticmethod
    def _to_numeric(value: Any) -> float:
        try:
            if value is None:
                return float("nan")
            return float(value)
        except Exception:
            return float("nan")

    @staticmethod
    def _interval_to_v3_parts(candle_interval: str) -> Tuple[str, int]:
        raw = _normalize_candle_interval(candle_interval)
        if raw == "1day":
            return ("days", 1)
        if raw == "1week":
            return ("weeks", 1)
        if raw.endswith("minute"):
            value = raw[:-6]
            if value.isdigit():
                return ("minutes", max(1, int(value)))
        raise ValueError(f"Unsupported candle interval for Upstox v3 historical endpoint: {candle_interval}")

    @staticmethod
    def _parse_interval_minutes(candle_interval: str) -> Optional[int]:
        raw = _normalize_candle_interval(candle_interval)
        if raw == "1day":
            return 1440
        if raw == "1week":
            return 10080
        if raw.endswith("minute"):
            value = raw[:-6]
            if value.isdigit():
                iv = int(value)
                return iv if iv > 0 else None
        return None

    @classmethod
    def _max_window_days_for_interval(cls, candle_interval: str) -> int:
        minutes = cls._parse_interval_minutes(candle_interval)
        if minutes is None:
            return 30
        if minutes == 1:
            return 7
        if minutes <= 5:
            return 21
        if minutes <= 15:
            return 45
        if minutes <= 30:
            return 75
        if minutes <= 60:
            return 120
        if minutes < 1440:
            return 180
        if minutes == 1440:
            return 3650
        return 3650

    @staticmethod
    def _looks_like_expired_instrument_key(instrument_key: str) -> bool:
        text = str(instrument_key or "").strip().replace(":", "|")
        parts = text.split("|")
        if len(parts) < 3:
            return False
        expiry_token = str(parts[-1]).strip()
        try:
            datetime.strptime(expiry_token, "%d-%m-%Y")
            return True
        except Exception:
            return False

    @staticmethod
    def _interval_to_expired_v2(candle_interval: str) -> Optional[str]:
        raw = _normalize_candle_interval(candle_interval)
        if raw == "1day" or raw == "1week":
            return "day"
        if raw.endswith("minute"):
            value = raw[:-6]
            if value in {"1", "3", "5", "15", "30"}:
                return f"{value}minute"
        return None

    def max_window_days_for_contract(self, candle_interval: str, groww_symbol: str) -> int:
        # Expired v2 endpoint is more reliable with smaller windows.
        if self._looks_like_expired_instrument_key(groww_symbol):
            raw = _normalize_candle_interval(candle_interval)
            if raw == "1week":
                return 365
            if raw == "1day":
                return 730
        return self._max_window_days_for_interval(candle_interval)

    def _expired_api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        if self._expired_plus_available is False:
            return None
        try:
            payload = self._get(path, params=params)
            self._expired_plus_available = True
            return payload
        except GrowwForbiddenError as exc:
            text = str(exc or "")
            lower = text.lower()
            if "udapi1149" in lower or "plus plan" in lower or "plus subscription" in lower:
                self._expired_plus_available = False
                if not self._expired_plus_warned:
                    logger.warning(
                        "Upstox expired-instruments APIs unavailable (Plus plan required). "
                        "Falling back to active instrument-master discovery."
                    )
                    self._expired_plus_warned = True
                return None
            raise

    @staticmethod
    def _aggregate_daily_payload_to_weekly(payload: Any) -> Any:
        if isinstance(payload, dict) and "candles" in payload:
            raw_candles = payload.get("candles")
        elif isinstance(payload, list):
            raw_candles = payload
        else:
            return {"candles": []}

        frame = _parse_candles({"candles": raw_candles})
        if frame.empty:
            return {"candles": []}

        frame = frame.sort_values("timestamp").copy()
        ts = pd.to_datetime(frame["timestamp"], errors="coerce")
        if getattr(ts.dt, "tz", None) is None:
            ts = ts.dt.tz_localize(IST)
        else:
            ts = ts.dt.tz_convert(IST)
        frame["week"] = ts.dt.tz_localize(None).dt.to_period("W-FRI")

        agg = (
            frame.groupby("week", as_index=False)
            .agg(
                timestamp=("timestamp", "max"),
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
                oi=("oi", "last"),
            )
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        candles: List[List[Any]] = []
        for row in agg.itertuples(index=False):
            ts_val = pd.to_datetime(getattr(row, "timestamp", None), errors="coerce")
            if pd.isna(ts_val):
                continue
            if getattr(ts_val, "tzinfo", None) is None:
                ts_val = ts_val.tz_localize(IST)
            candles.append(
                [
                    ts_val.isoformat(),
                    float(_safe_float(getattr(row, "open", 0.0), 0.0)),
                    float(_safe_float(getattr(row, "high", 0.0), 0.0)),
                    float(_safe_float(getattr(row, "low", 0.0), 0.0)),
                    float(_safe_float(getattr(row, "close", 0.0), 0.0)),
                    int(_safe_float(getattr(row, "volume", 0), 0)),
                    int(_safe_float(getattr(row, "oi", 0), 0)),
                ]
            )

        return {"candles": candles}

    def _ensure_master_loaded(self) -> None:
        if self._instrument_master_loaded:
            return
        self.download_instrument_master()

    def download_instrument_master(self) -> pd.DataFrame:
        last_err: Optional[Exception] = None
        raw_text: Optional[str] = None

        for attempt in range(self.max_retries):
            try:
                response = requests.get(UPSTOX_INSTRUMENT_MASTER_URL, timeout=max(self.timeout_seconds, 30))
                response.raise_for_status()
                blob = response.content
                try:
                    raw_text = gzip.decompress(blob).decode("utf-8")
                except Exception:
                    raw_text = blob.decode("utf-8", errors="ignore")
                break
            except Exception as exc:
                last_err = exc
                if attempt < self.max_retries - 1:
                    backoff = 1.5 ** attempt
                    logger.warning(
                        f"Upstox instrument master download failed (attempt {attempt + 1}/{self.max_retries}), retrying in {backoff:.1f}s: {exc}"
                    )
                    time.sleep(backoff)

        if raw_text is None:
            raise RuntimeError(f"Unable to download Upstox instrument master: {last_err}") from last_err

        try:
            records = json.loads(raw_text)
        except Exception as exc:
            raise RuntimeError(f"Unable to parse Upstox instrument master JSON: {exc}") from exc

        if not isinstance(records, list):
            raise RuntimeError("Unexpected Upstox instrument master payload shape (expected list)")

        raw_df = pd.DataFrame(records)
        if raw_df.empty:
            raise RuntimeError("Upstox instrument master is empty")

        for col in (
            "segment",
            "exchange",
            "instrument_type",
            "underlying_symbol",
            "trading_symbol",
            "instrument_key",
            "underlying_key",
            "expiry",
            "strike_price",
            "lot_size",
            "minimum_lot",
            "tick_size",
            "freeze_quantity",
            "exchange_token",
            "name",
        ):
            if col not in raw_df.columns:
                raw_df[col] = pd.NA

        nse_fo = raw_df[
            raw_df["exchange"].astype(str).str.upper().eq("NSE")
            & raw_df["segment"].astype(str).str.upper().eq("NSE_FO")
            & raw_df["instrument_type"].astype(str).str.upper().isin(["CE", "PE"])
            & raw_df["instrument_key"].notna()
        ].copy()

        if nse_fo.empty:
            raise RuntimeError("No NSE_FO CE/PE contracts found in Upstox instrument master")

        nse_fo["underlying_symbol"] = (
            nse_fo["underlying_symbol"]
            .fillna(nse_fo["asset_symbol"] if "asset_symbol" in nse_fo.columns else "")
            .astype(str)
            .str.strip()
            .str.upper()
        )
        nse_fo["trading_symbol"] = nse_fo["trading_symbol"].astype(str).str.strip()
        nse_fo["instrument_key"] = nse_fo["instrument_key"].astype(str).str.strip()
        nse_fo["instrument_type"] = nse_fo["instrument_type"].astype(str).str.strip().str.upper()
        nse_fo["expiry_date"] = nse_fo["expiry"].map(self._parse_expiry_date)
        nse_fo["strike_price"] = pd.to_numeric(nse_fo["strike_price"], errors="coerce")
        nse_fo["lot_size"] = pd.to_numeric(
            nse_fo["lot_size"].fillna(nse_fo["minimum_lot"]),
            errors="coerce",
        ).fillna(1).astype(int)

        option_rows = pd.DataFrame(
            {
                "exchange": "NSE",
                "exchange_token": nse_fo["exchange_token"].astype(str),
                "trading_symbol": nse_fo["trading_symbol"].astype(str),
                "groww_symbol": nse_fo["instrument_key"].astype(str),
                "name": nse_fo["name"].fillna(nse_fo["underlying_symbol"]).astype(str),
                "instrument_type": nse_fo["instrument_type"].astype(str),
                "segment": "FNO",
                "series": pd.NA,
                "isin": pd.NA,
                "underlying_symbol": nse_fo["underlying_symbol"].astype(str),
                "underlying_exchange_token": pd.NA,
                "expiry_date": nse_fo["expiry_date"],
                "strike_price": nse_fo["strike_price"],
                "lot_size": nse_fo["lot_size"],
                "tick_size": pd.to_numeric(nse_fo["tick_size"], errors="coerce"),
                "freeze_quantity": pd.to_numeric(nse_fo["freeze_quantity"], errors="coerce"),
                "is_reserved": 0,
                "buy_allowed": 1,
                "sell_allowed": 1,
                "underlying_key": nse_fo["underlying_key"].astype(str),
            }
        )

        symbol_to_underlying_key: Dict[str, str] = {}
        for row in nse_fo.itertuples(index=False):
            sym = self._safe_upper(getattr(row, "underlying_symbol", ""))
            key = str(getattr(row, "underlying_key", "") or "").strip()
            if sym and key and key.lower() != "nan":
                symbol_to_underlying_key[sym] = key.replace(":", "|")

        for sym, key in UPSTOX_INDEX_KEY_MAP.items():
            symbol_to_underlying_key[str(sym).strip().upper()] = str(key).replace(":", "|")

        spot_rows: List[Dict[str, Any]] = []
        for sym, key in sorted(symbol_to_underlying_key.items()):
            spot_rows.append(
                {
                    "exchange": "NSE",
                    "exchange_token": "",
                    "trading_symbol": sym,
                    "groww_symbol": key,
                    "name": sym,
                    "instrument_type": "INDEX" if key.startswith("NSE_INDEX|") else "EQ",
                    "segment": "INDEX" if key.startswith("NSE_INDEX|") else "CASH",
                    "series": pd.NA,
                    "isin": pd.NA,
                    "underlying_symbol": sym,
                    "underlying_exchange_token": pd.NA,
                    "expiry_date": pd.NaT,
                    "strike_price": pd.NA,
                    "lot_size": 1,
                    "tick_size": pd.NA,
                    "freeze_quantity": pd.NA,
                    "is_reserved": 0,
                    "buy_allowed": 1,
                    "sell_allowed": 1,
                    "underlying_key": key,
                }
            )

        normalized = pd.concat([option_rows, pd.DataFrame(spot_rows)], ignore_index=True, sort=False)
        normalized["groww_symbol"] = normalized["groww_symbol"].astype(str).str.strip()
        normalized = normalized[normalized["groww_symbol"].ne("")]
        normalized = normalized.drop_duplicates(subset=["groww_symbol"], keep="last").reset_index(drop=True)

        self._normalized_instruments = normalized
        self._option_master = normalized[
            normalized["segment"].astype(str).str.upper().eq("FNO")
            & normalized["instrument_type"].astype(str).str.upper().isin(["CE", "PE"])
        ].copy()
        self._underlying_key_by_symbol.update(symbol_to_underlying_key)
        self._instrument_master_loaded = True
        return normalized

    def _resolve_underlying_key(self, symbol: str) -> Optional[str]:
        key = self._underlying_key_by_symbol.get(str(symbol or "").strip().upper())
        return key.replace(":", "|") if isinstance(key, str) and key.strip() else None

    def _resolve_instrument_key(
        self,
        groww_symbol: str,
        trading_symbol: Optional[str] = None,
    ) -> Optional[str]:
        raw = str(groww_symbol or "").strip()
        if not raw and trading_symbol:
            raw = str(trading_symbol).strip()
        if not raw:
            return None

        raw = raw.replace(":", "|")
        if "|" in raw:
            return raw

        if raw.upper().startswith("NSE-"):
            symbol = raw.split("-", 1)[1].strip().upper()
            resolved = self._resolve_underlying_key(symbol)
            if resolved:
                return resolved

        if trading_symbol:
            resolved = self._resolve_underlying_key(str(trading_symbol).strip().upper())
            if resolved:
                return resolved

        return None

    def get_historical_candles(
        self,
        exchange: str,
        segment: str,
        groww_symbol: str,
        start_time: str,
        end_time: str,
        candle_interval: str = "1day",
        trading_symbol: Optional[str] = None,
    ) -> Any:
        instrument_key = self._resolve_instrument_key(groww_symbol, trading_symbol=trading_symbol)
        if not instrument_key:
            return {"candles": []}

        unit, interval_value = self._interval_to_v3_parts(candle_interval)
        from_date = str(start_time or "").strip()[:10]
        to_date = str(end_time or "").strip()[:10]
        if not from_date or not to_date:
            return {"candles": []}

        if self._looks_like_expired_instrument_key(instrument_key):
            expired_interval = self._interval_to_expired_v2(candle_interval)
            if not expired_interval:
                return {"candles": []}
            encoded_key = quote(instrument_key, safe="")
            path = f"/v2/expired-instruments/historical-candle/{encoded_key}/{expired_interval}/{to_date}/{from_date}"
            payload = self._expired_api_get(path)
            if payload is None:
                return {"candles": []}
            if _normalize_candle_interval(candle_interval) == "1week":
                return self._aggregate_daily_payload_to_weekly(payload)
            if isinstance(payload, dict) and "candles" in payload:
                return payload
            if isinstance(payload, list):
                return {"candles": payload}
            return {"candles": []}

        encoded_key = quote(instrument_key, safe="")
        path = f"/v3/historical-candle/{encoded_key}/{unit}/{interval_value}/{to_date}/{from_date}"
        try:
            payload = self._get(path)
            if isinstance(payload, dict) and "candles" in payload:
                return payload
            if isinstance(payload, list):
                return {"candles": payload}
            return payload
        except GrowwForbiddenError as exc:
            text = str(exc).lower()
            # Some historical paths are Plus-only (e.g. expired contracts).
            if "udapi1149" in text or "plus" in text:
                return {"candles": []}
            raise

    def get_expiries(
        self,
        exchange: str,
        underlying_symbol: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Any:
        self._ensure_master_loaded()
        symbol = str(underlying_symbol or "").strip().upper()
        if not symbol:
            return {"expiries": []}

        expiries: set[str] = set()

        if not self._option_master.empty:
            frame = self._option_master[
                self._option_master["underlying_symbol"].astype(str).str.upper().eq(symbol)
            ].copy()
            if not frame.empty:
                frame["expiry_date"] = pd.to_datetime(frame["expiry_date"], errors="coerce").dt.date
                frame = frame.dropna(subset=["expiry_date"])
                if year is not None:
                    frame = frame[
                        frame["expiry_date"].map(lambda x: x.year if isinstance(x, date) else -1).eq(int(year))
                    ]
                if month is not None:
                    frame = frame[
                        frame["expiry_date"].map(lambda x: x.month if isinstance(x, date) else -1).eq(int(month))
                    ]
                expiries.update(
                    {d.isoformat() for d in frame["expiry_date"].tolist() if isinstance(d, date)}
                )

        underlying_key = self._resolve_underlying_key(symbol)
        if underlying_key:
            cached = self._expired_expiries_cache.get(underlying_key)
            if cached is None:
                payload = self._expired_api_get(
                    "/v2/expired-instruments/expiries",
                    params={"instrument_key": underlying_key},
                )
                records = payload if isinstance(payload, list) else []
                parsed: List[str] = []
                for item in records:
                    d = self._parse_expiry_date(item)
                    if d is not None:
                        parsed.append(d.isoformat())
                cached = sorted(set(parsed))
                self._expired_expiries_cache[underlying_key] = cached
            for item in cached:
                d = self._parse_expiry_date(item)
                if d is None:
                    continue
                if year is not None and d.year != int(year):
                    continue
                if month is not None and d.month != int(month):
                    continue
                expiries.add(d.isoformat())

        expiries = sorted(expiries)
        return {"expiries": expiries}

    def get_contracts(
        self,
        exchange: str,
        underlying_symbol: str,
        expiry_date: str,
    ) -> Any:
        self._ensure_master_loaded()
        symbol = str(underlying_symbol or "").strip().upper()
        expiry = self._parse_expiry_date(expiry_date)
        if not symbol or expiry is None:
            return {"contracts": []}

        rows: List[Dict[str, Any]] = []

        if not self._option_master.empty:
            frame = self._option_master[
                self._option_master["underlying_symbol"].astype(str).str.upper().eq(symbol)
            ].copy()
            if not frame.empty:
                frame["expiry_date"] = pd.to_datetime(frame["expiry_date"], errors="coerce").dt.date
                frame = frame[frame["expiry_date"].eq(expiry)]
                for row in frame.itertuples(index=False):
                    rows.append(
                        {
                            "exchange": "NSE",
                            "underlying_symbol": symbol,
                            "groww_symbol": str(getattr(row, "groww_symbol", "") or "").strip(),
                            "trading_symbol": str(getattr(row, "trading_symbol", "") or "").strip(),
                            "expiry_date": self._to_iso_date_str(getattr(row, "expiry_date", None)),
                            "strike_price": self._to_numeric(getattr(row, "strike_price", None)),
                            "instrument_type": str(getattr(row, "instrument_type", "") or "").strip().upper(),
                            "lot_size": int(_safe_float(getattr(row, "lot_size", 1), 1.0)) or 1,
                        }
                    )

        underlying_key = self._resolve_underlying_key(symbol)
        if underlying_key:
            cache_key = (underlying_key, expiry.isoformat())
            expired_rows = self._expired_contracts_cache.get(cache_key)
            if expired_rows is None:
                payload = self._expired_api_get(
                    "/v2/expired-instruments/option/contract",
                    params={
                        "instrument_key": underlying_key,
                        "expiry_date": expiry.isoformat(),
                    },
                )
                records = payload if isinstance(payload, list) else []
                parsed_rows: List[Dict[str, Any]] = []
                for item in records:
                    if not isinstance(item, dict):
                        continue
                    key = str(
                        item.get("instrument_key")
                        or item.get("expired_instrument_key")
                        or item.get("groww_symbol")
                        or ""
                    ).strip()
                    if not key:
                        continue
                    parsed_rows.append(
                        {
                            "exchange": str(item.get("exchange") or "NSE").strip().upper() or "NSE",
                            "underlying_symbol": symbol,
                            "groww_symbol": key.replace(":", "|"),
                            "trading_symbol": str(item.get("trading_symbol") or "").strip(),
                            "expiry_date": self._to_iso_date_str(item.get("expiry") or item.get("expiry_date")),
                            "strike_price": self._to_numeric(item.get("strike_price")),
                            "instrument_type": str(item.get("instrument_type") or "").strip().upper(),
                            "lot_size": int(
                                _safe_float(
                                    item.get("lot_size", item.get("minimum_lot", 1)),
                                    1.0,
                                )
                            )
                            or 1,
                        }
                    )
                expired_rows = parsed_rows
                self._expired_contracts_cache[cache_key] = expired_rows
            rows.extend(expired_rows)

        if not rows:
            return {"contracts": []}

        deduped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = str(row.get("groww_symbol", "")).strip()
            if not key:
                continue
            deduped[key] = row
        rows = sorted(
            deduped.values(),
            key=lambda x: (
                str(x.get("expiry_date", "")),
                float(_safe_float(x.get("strike_price"), 0.0)),
                str(x.get("instrument_type", "")),
            ),
        )
        return {"contracts": rows}


@dataclass
class UnderlyingResult:
    symbol: str
    status: str
    rows: int = 0
    contracts_selected: int = 0
    contracts_with_data: int = 0
    contracts_failed: int = 0
    file_path: str = ""
    message: str = ""
    coverage_start: str = ""
    coverage_end: str = ""
    coverage_days: int = 0


class GrowwOptionUniverseBuilder:
    def __init__(
        self,
        client: Any,
        start_date: date,
        end_date: date,
        output_dir: Path,
        universe_file: Path,
        index_symbols: Sequence[str],
        risk_free_rate: float,
        overwrite: bool = False,
        max_contracts_per_underlying: int = 0,
        max_underlyings: int = 0,
        refresh_instruments: bool = False,
        instrument_master_file: Optional[Path] = None,
        use_contracts_api: bool = True,
        extra_contracts_files: Optional[Sequence[Path]] = None,
        candle_interval: str = "1day",
        progress_every_contracts: int = 50,
        future_expiry_days: int = 45,
        contract_listing_lookback_days: int = 365,
        resume_enabled: bool = True,
        resume_dir: Optional[Path] = None,
        provider: str = "groww",
    ) -> None:
        self.client = client
        self.provider = str(provider or "groww").strip().lower() or "groww"
        self.start_date = start_date
        self.end_date = end_date
        self.output_dir = output_dir
        self.universe_file = universe_file
        self.index_symbols = [s.strip().upper() for s in index_symbols if s.strip()]
        self.risk_free_rate = float(risk_free_rate)
        self.overwrite = bool(overwrite)
        self.max_contracts_per_underlying = max(0, int(max_contracts_per_underlying))
        self.max_underlyings = max(0, int(max_underlyings))
        self.refresh_instruments = bool(refresh_instruments)
        self.instrument_master_file = instrument_master_file
        self.use_contracts_api = bool(use_contracts_api)
        self.extra_contracts_files = [Path(p) for p in (extra_contracts_files or [])]
        self.candle_interval = _normalize_candle_interval(candle_interval)
        self.interval_minutes = GrowwBacktestingClient._parse_interval_minutes(self.candle_interval)
        self.progress_every_contracts = max(1, int(progress_every_contracts))
        self.future_expiry_days = max(0, int(future_expiry_days))
        # 0 disables pre-listing clamp and allows full requested start-date for each contract.
        self.contract_listing_lookback_days = max(0, int(contract_listing_lookback_days))
        self.resume_enabled = bool(resume_enabled)
        self.instrument_cache = output_dir / f"{self.provider}_instrument_master.parquet"
        self.resume_root = Path(resume_dir) if resume_dir is not None else (output_dir / "_resume")
        self.run_signature = hashlib.sha1(
            f"{self.provider}|{self.start_date.isoformat()}|{self.end_date.isoformat()}|{self.candle_interval}".encode("utf-8")
        ).hexdigest()[:16]

        self.output_dir.mkdir(parents=True, exist_ok=True)
        if self.resume_enabled:
            self.resume_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_contract_filename(groww_symbol: str) -> str:
        text = str(groww_symbol or "").strip().upper()
        if not text:
            text = "UNKNOWN"
        safe = "".join(ch if ch.isalnum() else "_" for ch in text)
        if len(safe) > 110:
            safe = safe[:110]
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        return f"{safe}_{digest}"

    def _resume_underlying_dir(self, symbol: str) -> Path:
        return self.resume_root / self.run_signature / symbol.lower()

    def _resume_state_path(self, symbol: str) -> Path:
        return self._resume_underlying_dir(symbol) / "state.json"

    def _resume_contracts_dir(self, symbol: str) -> Path:
        return self._resume_underlying_dir(symbol) / "contracts"

    def _load_resume_state(self, symbol: str) -> Dict[str, Any]:
        state_path = self._resume_state_path(symbol)
        if not self.resume_enabled or self.overwrite or not state_path.exists():
            return {
                "version": 1,
                "symbol": symbol,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "candle_interval": self.candle_interval,
                "contracts": {},
            }
        try:
            raw = json.loads(state_path.read_text())
        except Exception:
            return {
                "version": 1,
                "symbol": symbol,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "candle_interval": self.candle_interval,
                "contracts": {},
            }

        if (
            str(raw.get("symbol", "")).upper() != symbol.upper()
            or str(raw.get("start_date", "")) != self.start_date.isoformat()
            or str(raw.get("end_date", "")) != self.end_date.isoformat()
            or str(raw.get("candle_interval", "")).lower() != self.candle_interval
        ):
            return {
                "version": 1,
                "symbol": symbol,
                "start_date": self.start_date.isoformat(),
                "end_date": self.end_date.isoformat(),
                "candle_interval": self.candle_interval,
                "contracts": {},
            }

        contracts_state = raw.get("contracts")
        if not isinstance(contracts_state, dict):
            raw["contracts"] = {}
        return raw

    def _save_resume_state(self, symbol: str, state: Dict[str, Any]) -> None:
        if not self.resume_enabled or self.overwrite:
            return
        state_path = self._resume_state_path(symbol)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2))
        tmp.replace(state_path)

    def _resume_contract_paths(self, symbol: str, groww_symbol: str) -> Tuple[Path, str]:
        contracts_dir = self._resume_contracts_dir(symbol)
        contracts_dir.mkdir(parents=True, exist_ok=True)
        base_name = self._safe_contract_filename(groww_symbol)
        data_path = contracts_dir / f"{base_name}.parquet"
        relative_data = str(data_path.relative_to(self._resume_underlying_dir(symbol)))
        return data_path, relative_data

    @staticmethod
    def _load_contracts_file(path: Path) -> pd.DataFrame:
        src = Path(path).expanduser()
        if not src.exists():
            raise FileNotFoundError(f"Extra contracts file not found: {src}")
        if src.suffix.lower() == ".parquet":
            df = pd.read_parquet(src)
        else:
            df = pd.read_csv(src, dtype=str)
        if df.empty:
            return df

        rename_map = {str(c).strip().lower(): c for c in df.columns}

        def _col(name: str) -> Optional[str]:
            return rename_map.get(name.lower())

        # Normalize required columns expected by the builder.
        if _col("exchange") is None:
            df["exchange"] = "NSE"
        if _col("segment") is None:
            df["segment"] = "FNO"
        if _col("groww_symbol") is None:
            raise ValueError(f"Missing groww_symbol column in {src}")
        if _col("trading_symbol") is None:
            df["trading_symbol"] = ""
        if _col("instrument_type") is None:
            df["instrument_type"] = (
                df[_col("groww_symbol")]
                .astype(str)
                .str.upper()
                .str.extract(r"-(CE|PE)$", expand=False)
                .fillna("")
            )
        if _col("underlying_symbol") is None:
            df["underlying_symbol"] = (
                df[_col("groww_symbol")]
                .astype(str)
                .str.split("-")
                .str[1]
                .fillna("")
                .str.upper()
            )
        if _col("lot_size") is None:
            df["lot_size"] = "1"
        if _col("strike_price") is None:
            df["strike_price"] = pd.NA
        if _col("expiry_date") is None:
            df["expiry_date"] = pd.NA

        keep_cols = [
            "exchange",
            "exchange_token",
            "trading_symbol",
            "groww_symbol",
            "name",
            "instrument_type",
            "segment",
            "series",
            "isin",
            "underlying_symbol",
            "underlying_exchange_token",
            "expiry_date",
            "strike_price",
            "lot_size",
            "tick_size",
            "freeze_quantity",
            "is_reserved",
            "buy_allowed",
            "sell_allowed",
        ]

        for col in keep_cols:
            if col not in df.columns:
                df[col] = pd.NA

        out = df[keep_cols].copy()
        out["exchange"] = out["exchange"].astype(str).str.upper().replace({"NAN": "NSE", "": "NSE"})
        out["segment"] = out["segment"].astype(str).str.upper().replace({"NAN": "FNO", "": "FNO"})
        out["instrument_type"] = out["instrument_type"].astype(str).str.upper()
        out["underlying_symbol"] = out["underlying_symbol"].astype(str).str.upper()
        out["trading_symbol"] = out["trading_symbol"].astype(str).str.upper()
        out["groww_symbol"] = out["groww_symbol"].astype(str).str.strip()
        if self.provider != "upstox":
            out["groww_symbol"] = out["groww_symbol"].str.upper()
        return out

    def _merge_extra_contracts(self, instruments: pd.DataFrame) -> pd.DataFrame:
        if not self.extra_contracts_files:
            return instruments

        extra_frames: List[pd.DataFrame] = []
        for path in self.extra_contracts_files:
            loaded = self._load_contracts_file(path)
            if loaded.empty:
                logger.warning(f"Extra contracts file is empty: {path}")
                continue
            logger.info(f"Loaded extra contracts file: {path} ({len(loaded):,} rows)")
            extra_frames.append(loaded)

        if not extra_frames:
            return instruments

        extra = pd.concat(extra_frames, ignore_index=True, sort=False)
        merged = pd.concat([instruments, extra], ignore_index=True, sort=False)
        if "groww_symbol" in merged.columns:
            if self.provider == "upstox":
                merged["groww_symbol"] = merged["groww_symbol"].astype(str).str.strip()
            else:
                merged["groww_symbol"] = merged["groww_symbol"].astype(str).str.strip().str.upper()
            merged = merged[merged["groww_symbol"].ne("")]
            merged = merged.drop_duplicates(subset=["groww_symbol"], keep="last")
        logger.info(
            f"Merged instrument universe with extra contracts: base={len(instruments):,}, "
            f"extra={len(extra):,}, merged={len(merged):,}"
        )
        return merged.reset_index(drop=True)

    def load_instruments(self) -> pd.DataFrame:
        if self.instrument_master_file is not None:
            src = self.instrument_master_file
            if not src.exists():
                raise FileNotFoundError(f"Instrument master file not found: {src}")
            logger.info(f"Loading instrument master from file: {src}")
            if src.suffix.lower() == ".parquet":
                df = pd.read_parquet(src)
            else:
                df = pd.read_csv(src, dtype=str)
            df = self._merge_extra_contracts(df)
            if not df.empty:
                df.to_parquet(self.instrument_cache, index=False)
            return df

        if (
            self.provider == "groww"
            and DEFAULT_LOCAL_INSTRUMENT_PATH.exists()
            and not self.refresh_instruments
        ):
            src = DEFAULT_LOCAL_INSTRUMENT_PATH
            logger.info(f"Loading instrument master from local file: {src}")
            df = pd.read_csv(src, dtype=str)
            df = self._merge_extra_contracts(df)
            if not df.empty:
                df.to_parquet(self.instrument_cache, index=False)
            return df

        if self.instrument_cache.exists() and not self.refresh_instruments:
            logger.info(f"Loading instrument master from cache: {self.instrument_cache}")
            df = pd.read_parquet(self.instrument_cache)
            return self._merge_extra_contracts(df)

        logger.info(f"Downloading {self.provider.upper()} instrument master...")
        df = self.client.download_instrument_master()
        df = self._merge_extra_contracts(df)
        df.to_parquet(self.instrument_cache, index=False)
        logger.info(f"Saved instrument master cache: {self.instrument_cache} ({len(df):,} rows)")
        return df

    def load_requested_symbols(self, underlyings_arg: str) -> List[str]:
        raw = str(underlyings_arg or "").strip().upper()
        symbols: List[str]

        if raw in ("", "NIFTY500_PLUS_INDICES", "ALL"):
            symbols = self._read_nifty500_symbols()
            symbols.extend(self.index_symbols)
        elif raw == "ALL_INDICES":
            symbols = list(self.index_symbols)
        elif raw == "NIFTY500":
            symbols = self._read_nifty500_symbols()
        else:
            symbols = [x.strip().upper() for x in raw.split(",") if x.strip()]

        deduped = sorted(set(symbols))
        # Put index symbols first for fast health checks.
        index_set = set(self.index_symbols)
        deduped = [s for s in deduped if s in index_set] + [s for s in deduped if s not in index_set]
        if self.max_underlyings > 0:
            deduped = deduped[: self.max_underlyings]
        return deduped

    @staticmethod
    def _decode_jwt_payload(token: str) -> Dict[str, Any]:
        parts = str(token or "").split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        # Base64url padding
        payload += "=" * ((4 - len(payload) % 4) % 4)
        try:
            import base64

            raw = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8", errors="ignore")
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @classmethod
    def _extract_role_claim(cls, token: str) -> str:
        claims = cls._decode_jwt_payload(token)
        sub = claims.get("sub")
        if isinstance(sub, str):
            try:
                inner = json.loads(sub)
                role = inner.get("role")
                if isinstance(role, str) and role.strip():
                    return role.strip()
            except Exception:
                pass
            if sub.strip():
                return sub.strip()
        role = claims.get("role")
        return str(role).strip() if role is not None else ""

    def _preflight_backtesting_access(self) -> None:
        """
        Validate that token has historical/backtesting permission before long run.
        """
        if self.provider == "upstox":
            test_end = self.end_date
            test_start = max(self.start_date, test_end - timedelta(days=2))
            try:
                payload = self.client.get_historical_candles(
                    exchange="NSE",
                    segment="INDEX",
                    groww_symbol=UPSTOX_INDEX_KEY_MAP["NIFTY"],
                    trading_symbol="NIFTY",
                    start_time=_to_groww_ts(test_start, end_of_day=False),
                    end_time=_to_groww_ts(test_end, end_of_day=True),
                    candle_interval="1day",
                )
                candles = _parse_candles(payload)
                if candles.empty:
                    logger.warning(
                        "Upstox preflight returned empty NIFTY candles. "
                        "Proceeding, but verify token/date-range if outputs are empty."
                    )
                else:
                    logger.info("Upstox preflight passed (historical candles accessible)")
                return
            except GrowwForbiddenError as exc:
                raise RuntimeError(
                    "Upstox token is authenticated but forbidden for historical candles. "
                    "Generate a fresh access token and verify market-data permissions. "
                    f"Original error: {exc}"
                ) from exc
            except Exception as exc:
                raise RuntimeError(f"Upstox preflight failed: {exc}") from exc

        if self.client.use_python_sdk:
            test_end = self.end_date
            test_start = max(self.start_date, test_end - timedelta(days=2))
            try:
                payload = self.client.get_historical_candles(
                    exchange="NSE",
                    segment="CASH",
                    groww_symbol="NSE-RELIANCE",
                    trading_symbol="RELIANCE",
                    start_time=_to_groww_ts(test_start, end_of_day=False),
                    end_time=_to_groww_ts(test_end, end_of_day=True),
                    candle_interval="1day",
                )
                candles = _parse_candles(payload)
                if candles.empty:
                    logger.warning(
                        "SDK preflight returned empty candles for RELIANCE CASH. "
                        "Proceeding, but verify symbol/date range if output is empty."
                    )
                else:
                    logger.info("SDK preflight passed (historical candles accessible via GrowwAPI)")
                return
            except GrowwForbiddenError as exc:
                role_claim = self._extract_role_claim(self.client.auth_token)
                raise RuntimeError(
                    "Groww token is authenticated but forbidden for SDK historical candles. "
                    f"Token role/sub claim: {role_claim}. Original error: {exc}"
                ) from exc
            except Exception as exc:
                raise RuntimeError(f"SDK preflight failed: {exc}") from exc

        now = datetime.now(IST)
        try:
            self.client.get_expiries(
                exchange="NSE",
                underlying_symbol="NIFTY",
                year=now.year,
            )
            logger.info("Backtesting preflight passed (historical expiries accessible)")
            return
        except GrowwForbiddenError as exc:
            role_claim = self._extract_role_claim(self.client.auth_token)
            raise RuntimeError(
                "Groww token is authenticated but forbidden for historical/backtesting APIs (HTTP 403). "
                "Enable historical/backtesting scope on the Groww API app and generate a fresh access token. "
                f"Token role/sub claim: {role_claim}. Original error: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Backtesting preflight failed: {exc}") from exc

    def _read_nifty500_symbols(self) -> List[str]:
        if not self.universe_file.exists():
            raise FileNotFoundError(f"Universe file not found: {self.universe_file}")
        df = pd.read_csv(self.universe_file)
        symbol_col = None
        for candidate in ("Symbol", "symbol", "SYMBOL"):
            if candidate in df.columns:
                symbol_col = candidate
                break
        if symbol_col is None:
            raise ValueError(f"Could not find Symbol column in {self.universe_file}")

        symbols = (
            df[symbol_col]
            .astype(str)
            .str.strip()
            .str.upper()
            .tolist()
        )
        return [s for s in symbols if s]

    @staticmethod
    def _parse_expiry_value(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("T", " ").replace("Z", "").strip()
        if " " in text:
            text = text.split(" ", 1)[0]
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d%b%y", "%d%b%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except Exception:
                continue
        return None

    @classmethod
    def _normalize_expiries_payload(cls, payload: Any) -> List[date]:
        raw_items: Any = payload
        if isinstance(payload, dict):
            raw_items = (
                payload.get("expiries")
                or payload.get("expiry_dates")
                or payload.get("data")
                or []
            )

        if not isinstance(raw_items, list):
            return []

        expiries: List[date] = []
        for item in raw_items:
            if isinstance(item, dict):
                expiry_raw = item.get("expiry_date") or item.get("expiry") or item.get("date")
            else:
                expiry_raw = item
            parsed = cls._parse_expiry_value(expiry_raw)
            if parsed is not None:
                expiries.append(parsed)
        return sorted(set(expiries))

    @staticmethod
    def _normalize_contracts_payload(payload: Any) -> List[str]:
        raw_items: Any = payload
        if isinstance(payload, dict):
            raw_items = (
                payload.get("contracts")
                or payload.get("symbols")
                or payload.get("data")
                or []
            )

        if not isinstance(raw_items, list):
            return []

        symbols: List[str] = []
        for item in raw_items:
            if isinstance(item, str):
                value = item.strip()
            elif isinstance(item, dict):
                value = str(
                    item.get("instrument_key")
                    or item.get("expired_instrument_key")
                    or item.get("groww_symbol")
                    or item.get("symbol")
                    or item.get("trading_symbol")
                    or ""
                ).strip()
            else:
                value = ""
            if value:
                symbols.append(value)
        return sorted(set(symbols))

    @classmethod
    def _parse_contract_symbol(cls, groww_symbol: str, fallback_underlying: str) -> Optional[Dict[str, Any]]:
        text = str(groww_symbol or "").strip().upper()
        if not text:
            return None
        parts = text.split("-")
        if len(parts) < 5:
            return None

        option_type = parts[-1].upper()
        if option_type not in ("CE", "PE"):
            return None

        strike_raw = parts[-2]
        expiry_raw = parts[-3]
        underlying_symbol = "-".join(parts[1:-3]).strip().upper() or fallback_underlying
        if not underlying_symbol:
            underlying_symbol = fallback_underlying

        expiry = cls._parse_expiry_value(expiry_raw.title())
        if expiry is None:
            return None
        try:
            strike = float(strike_raw)
        except Exception:
            return None

        exchange = parts[0].upper() if parts else "NSE"
        return {
            "exchange": exchange or "NSE",
            "underlying_symbol": underlying_symbol,
            "groww_symbol": text,
            "trading_symbol": "",
            "expiry_date": expiry,
            "strike_price": strike,
            "instrument_type": option_type,
            "lot_size": 1,
        }

    def _discover_contracts_via_api(
        self,
        symbol: str,
        expiry_lower: date,
        expiry_upper: date,
        master_contracts: pd.DataFrame,
    ) -> pd.DataFrame:
        if not self.use_contracts_api:
            return pd.DataFrame()

        master_lookup: Dict[str, Dict[str, Any]] = {}
        if not master_contracts.empty:
            for row in master_contracts.itertuples(index=False):
                key = str(getattr(row, "groww_symbol", "")).strip()
                if not key:
                    continue
                master_lookup[key] = {
                    "exchange": str(getattr(row, "exchange", "NSE") or "NSE").strip().upper(),
                    "underlying_symbol": str(getattr(row, "underlying_symbol", symbol) or symbol).strip().upper(),
                    "groww_symbol": key,
                    "trading_symbol": str(getattr(row, "trading_symbol", "") or "").strip(),
                    "expiry_date": getattr(row, "expiry_date", None),
                    "strike_price": getattr(row, "strike_price", None),
                    "instrument_type": str(getattr(row, "instrument_type", "")).strip().upper(),
                    "lot_size": int(_safe_float(getattr(row, "lot_size", 1), 1.0)) or 1,
                }

        all_expiries: set[date] = set()
        supports_year_filtered = bool(getattr(self.client, "supports_year_filtered_expiries", True))
        if supports_year_filtered:
            years = range(expiry_lower.year, expiry_upper.year + 1)
            for year in years:
                payload = self.client.get_expiries(
                    exchange="NSE",
                    underlying_symbol=symbol,
                    year=year,
                )
                for expiry in self._normalize_expiries_payload(payload):
                    if expiry_lower <= expiry <= expiry_upper:
                        all_expiries.add(expiry)
        else:
            payload = self.client.get_expiries(
                exchange="NSE",
                underlying_symbol=symbol,
            )
            for expiry in self._normalize_expiries_payload(payload):
                if expiry_lower <= expiry <= expiry_upper:
                    all_expiries.add(expiry)

        rows: List[Dict[str, Any]] = []
        for expiry in sorted(all_expiries):
            payload = self.client.get_contracts(
                exchange="NSE",
                underlying_symbol=symbol,
                expiry_date=expiry.isoformat(),
            )
            contract_symbols = self._normalize_contracts_payload(payload)
            for groww_symbol in contract_symbols:
                from_master = master_lookup.get(groww_symbol)
                if from_master is not None:
                    rows.append(from_master.copy())
                    continue
                parsed = self._parse_contract_symbol(groww_symbol, fallback_underlying=symbol)
                if parsed is not None:
                    rows.append(parsed)

        if not rows:
            return pd.DataFrame()

        out = pd.DataFrame(rows)
        out["expiry_date"] = pd.to_datetime(out["expiry_date"], errors="coerce").dt.date
        out["strike_price"] = pd.to_numeric(out["strike_price"], errors="coerce")
        out["instrument_type"] = out["instrument_type"].astype(str).str.upper()
        out = out.dropna(subset=["expiry_date", "strike_price", "groww_symbol"])
        out = out[out["instrument_type"].isin(["CE", "PE"])].copy()
        out = out.drop_duplicates(subset=["groww_symbol"], keep="last")
        out = out.sort_values(["expiry_date", "strike_price", "instrument_type"])
        return out.reset_index(drop=True)

    def build(self, underlyings_arg: str) -> Dict[str, Any]:
        self._preflight_backtesting_access()
        instruments = self.load_instruments()
        symbols = self.load_requested_symbols(underlyings_arg)
        logger.info(f"Requested symbols: {len(symbols)}")

        fno_options = instruments[
            instruments["segment"].astype(str).str.upper().eq("FNO")
            & instruments["instrument_type"].astype(str).str.upper().isin(["CE", "PE"])
            & instruments["underlying_symbol"].notna()
            & instruments["groww_symbol"].notna()
        ].copy()

        if fno_options.empty:
            raise RuntimeError("No FNO options found in instrument master")

        fno_options["underlying_symbol"] = (
            fno_options["underlying_symbol"].astype(str).str.strip().str.upper()
        )
        fno_options["instrument_type"] = (
            fno_options["instrument_type"].astype(str).str.strip().str.upper()
        )
        fno_options["strike_price"] = pd.to_numeric(fno_options["strike_price"], errors="coerce")
        fno_options["expiry_date"] = pd.to_datetime(
            fno_options["expiry_date"], errors="coerce"
        ).dt.date
        fno_options = fno_options.dropna(subset=["expiry_date", "strike_price"])

        option_enabled_symbols = set(fno_options["underlying_symbol"].unique())
        logger.info(f"Option-enabled symbols in instrument master: {len(option_enabled_symbols)}")

        results: List[UnderlyingResult] = []
        started_at = datetime.now(IST)

        for idx, symbol in enumerate(symbols, start=1):
            if not self.use_contracts_api and symbol not in option_enabled_symbols:
                logger.info(f"[{idx}/{len(symbols)}] {symbol}: no listed options, skipping")
                results.append(
                    UnderlyingResult(
                        symbol=symbol,
                        status="SKIPPED_NO_OPTIONS",
                        message="No CE/PE contracts in instrument master",
                    )
                )
                continue

            logger.info(f"[{idx}/{len(symbols)}] Building {symbol}...")
            try:
                result = self._build_underlying(symbol, fno_options, instruments)
            except GrowwForbiddenError as exc:
                raise RuntimeError(
                    f"{self.provider.upper()} access forbidden while fetching historical data for {symbol}: {exc}"
                ) from exc
            except Exception as exc:
                logger.exception(f"{symbol}: build failed")
                result = UnderlyingResult(
                    symbol=symbol,
                    status="FAILED",
                    message=str(exc),
                )
            results.append(result)

        finished_at = datetime.now(IST)
        coverage_rows = []
        for r in results:
            if str(r.coverage_start).strip() and str(r.coverage_end).strip():
                coverage_rows.append(
                    {
                        "symbol": r.symbol,
                        "status": r.status,
                        "coverage_start": r.coverage_start,
                        "coverage_end": r.coverage_end,
                        "coverage_days": int(r.coverage_days or 0),
                    }
                )

        global_coverage_start = ""
        global_coverage_end = ""
        if coverage_rows:
            starts = pd.to_datetime([x["coverage_start"] for x in coverage_rows], errors="coerce")
            ends = pd.to_datetime([x["coverage_end"] for x in coverage_rows], errors="coerce")
            if len(starts.dropna()) > 0:
                global_coverage_start = str(starts.min().date())
            if len(ends.dropna()) > 0:
                global_coverage_end = str(ends.max().date())

        summary = {
            "generated_at": finished_at.isoformat(),
            "started_at": started_at.isoformat(),
            "provider": self.provider,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "requested_symbols": len(symbols),
            "coverage_summary": {
                "symbols_with_coverage": len(coverage_rows),
                "global_coverage_start": global_coverage_start,
                "global_coverage_end": global_coverage_end,
            },
            "status_breakdown": {
                "SUCCESS": sum(1 for r in results if r.status == "SUCCESS"),
                "SKIPPED_EXISTING": sum(1 for r in results if r.status == "SKIPPED_EXISTING"),
                "SKIPPED_NO_OPTIONS": sum(1 for r in results if r.status == "SKIPPED_NO_OPTIONS"),
                "EMPTY": sum(1 for r in results if r.status == "EMPTY"),
                "FAILED": sum(1 for r in results if r.status == "FAILED"),
            },
            "results": [r.__dict__ for r in results],
        }

        if self.provider == "upstox":
            plus_state = getattr(self.client, "_expired_plus_available", None)
            if plus_state is True:
                expired_state = "available"
            elif plus_state is False:
                expired_state = "unavailable"
            else:
                expired_state = "unknown"
            summary["provider_diagnostics"] = {
                "expired_instruments_api": expired_state,
                "supports_year_filtered_expiries": bool(
                    getattr(self.client, "supports_year_filtered_expiries", False)
                ),
            }

        latest_manifest = self.output_dir / f"{self.provider}_universe_manifest_latest.json"
        stamped_manifest = self.output_dir / f"{self.provider}_universe_manifest_{finished_at.strftime('%Y%m%d_%H%M%S')}.json"
        latest_manifest.write_text(json.dumps(summary, indent=2))
        stamped_manifest.write_text(json.dumps(summary, indent=2))
        logger.info(f"Manifest saved: {latest_manifest}")
        logger.info(f"Manifest saved: {stamped_manifest}")
        return summary

    def _build_underlying(
        self,
        symbol: str,
        fno_options: pd.DataFrame,
        instruments: pd.DataFrame,
    ) -> UnderlyingResult:
        output_file = self.output_dir / f"{symbol.lower()}_option_chains.parquet"

        if output_file.exists() and not self.overwrite:
            try:
                existing_dates = pd.read_parquet(output_file, columns=["date"])
                existing_dates["date"] = pd.to_datetime(existing_dates["date"], errors="coerce").dt.date
                min_existing = existing_dates["date"].min()
                max_existing = existing_dates["date"].max()
                if pd.notna(min_existing) and pd.notna(max_existing):
                    if min_existing <= self.start_date and max_existing >= self.end_date:
                        cov_days = int((max_existing - min_existing).days) if hasattr(max_existing, "__sub__") else 0
                        return UnderlyingResult(
                            symbol=symbol,
                            status="SKIPPED_EXISTING",
                            file_path=str(output_file),
                            message=f"Existing coverage {min_existing}..{max_existing}",
                            coverage_start=str(min_existing),
                            coverage_end=str(max_existing),
                            coverage_days=max(0, cov_days),
                        )
            except Exception:
                # Continue and rebuild/merge if existing file cannot be inspected.
                pass

        expiry_lower = self.start_date - timedelta(days=7)
        expiry_upper = self.end_date + timedelta(days=self.future_expiry_days)

        base_contracts = fno_options[
            fno_options["underlying_symbol"].eq(symbol)
            & (fno_options["expiry_date"] >= expiry_lower)
            & (fno_options["expiry_date"] <= expiry_upper)
        ].copy()

        contracts = base_contracts.copy()
        if self.use_contracts_api:
            try:
                api_contracts = self._discover_contracts_via_api(
                    symbol=symbol,
                    expiry_lower=expiry_lower,
                    expiry_upper=expiry_upper,
                    master_contracts=base_contracts,
                )
                if not api_contracts.empty:
                    contracts = api_contracts
                    logger.debug(f"{symbol}: discovered {len(contracts)} contracts via /historical/contracts")
            except GrowwForbiddenError as exc:
                if self.client.use_python_sdk:
                    logger.warning(
                        f"{symbol}: /historical/contracts forbidden; falling back to instrument-master contracts in SDK mode ({exc})"
                    )
                else:
                    raise
            except Exception as exc:
                logger.warning(f"{symbol}: contracts API discovery failed, using instrument-master fallback ({exc})")

        if contracts.empty:
            return UnderlyingResult(
                symbol=symbol,
                status="EMPTY",
                file_path=str(output_file),
                message="No contracts found in requested expiry window",
            )

        start_ts = _to_groww_ts(self.start_date, end_of_day=False)
        end_ts = _to_groww_ts(self.end_date, end_of_day=True)

        spot_history = self._fetch_underlying_spot_history(symbol, instruments, start_ts, end_ts)

        contracts = contracts.sort_values(["expiry_date", "strike_price", "instrument_type"])
        if self.max_contracts_per_underlying > 0:
            ref_spot = float("nan")
            if not spot_history.empty and "underlying_price" in spot_history.columns:
                spot_vals = pd.to_numeric(spot_history["underlying_price"], errors="coerce").dropna()
                if not spot_vals.empty:
                    ref_spot = float(spot_vals.iloc[-1])
            if not math.isfinite(ref_spot):
                ref_spot = float(pd.to_numeric(contracts["strike_price"], errors="coerce").median())

            tmp = contracts.copy()
            tmp["strike_price"] = pd.to_numeric(tmp["strike_price"], errors="coerce")
            tmp["expiry_date"] = pd.to_datetime(tmp["expiry_date"], errors="coerce")
            tmp = tmp.dropna(subset=["strike_price", "expiry_date"])
            if not tmp.empty:
                tmp["days_to_expiry"] = (tmp["expiry_date"] - pd.Timestamp(self.end_date)).dt.days.abs()
                tmp["strike_dist"] = (tmp["strike_price"] - ref_spot).abs()
                tmp = tmp.sort_values(["days_to_expiry", "strike_dist", "instrument_type"])
                contracts = tmp.head(self.max_contracts_per_underlying).copy()
            else:
                contracts = contracts.head(self.max_contracts_per_underlying)

        contracts = contracts.reset_index(drop=True)
        logger.info(
            f"{symbol}: selected {len(contracts)} contracts "
            f"(future-expiry-days={self.future_expiry_days}, "
            f"listing-lookback-days={self.contract_listing_lookback_days})"
        )
        contracts_failed = 0
        total_contracts = len(contracts)
        started = time.time()

        state = self._load_resume_state(symbol)
        state_contracts = state.setdefault("contracts", {})
        state_dirty = 0

        def _state_entry(groww_symbol: str) -> Dict[str, Any]:
            entry = state_contracts.get(groww_symbol)
            return entry if isinstance(entry, dict) else {}

        def _is_contract_done(groww_symbol: str) -> bool:
            entry = _state_entry(groww_symbol)
            status = str(entry.get("status", "")).strip().lower()
            if status == "empty":
                return True
            if status != "with_data":
                return False
            data_rel = str(entry.get("data_file", "")).strip()
            if not data_rel:
                return False
            data_path = self._resume_underlying_dir(symbol) / data_rel
            return data_path.exists()

        def _flush_state(force: bool = False) -> None:
            nonlocal state_dirty
            if state_dirty <= 0:
                return
            if force or state_dirty >= max(5, self.progress_every_contracts // 2):
                self._save_resume_state(symbol, state)
                state_dirty = 0

        def _mark_contract_state(
            groww_symbol: str,
            status: str,
            rows: int = 0,
            data_file: str = "",
            message: str = "",
        ) -> None:
            nonlocal state_dirty
            payload: Dict[str, Any] = {
                "status": status,
                "rows": int(rows),
                "updated_at": datetime.now(IST).isoformat(),
            }
            if data_file:
                payload["data_file"] = data_file
            if message:
                payload["message"] = str(message)
            state_contracts[groww_symbol] = payload
            state_dirty += 1
            _flush_state(force=False)

        already_processed = 0
        already_with_data = 0
        for contract in contracts.itertuples(index=False):
            gs = str(getattr(contract, "groww_symbol", "")).strip()
            if not gs or not _is_contract_done(gs):
                continue
            already_processed += 1
            if str(_state_entry(gs).get("status", "")).strip().lower() == "with_data":
                already_with_data += 1

        if already_processed > 0:
            logger.info(
                f"{symbol}: resume detected, processed={already_processed}/{total_contracts}, "
                f"with_data={already_with_data}"
            )

        contracts_with_data = already_with_data

        for contract_idx, (_, contract) in enumerate(contracts.iterrows(), start=1):
            groww_symbol = str(contract["groww_symbol"]).strip()
            if not groww_symbol:
                continue
            trading_symbol = str(contract.get("trading_symbol", "") or "").strip() or None
            exchange = str(contract.get("exchange", "NSE") or "NSE").strip().upper()
            expiry = contract["expiry_date"]
            strike = float(contract["strike_price"])
            option_type = str(contract["instrument_type"]).strip().upper()
            lot_size = int(_safe_float(contract.get("lot_size", 1), 1.0)) or 1

            if _is_contract_done(groww_symbol):
                if (
                    contract_idx % self.progress_every_contracts == 0
                    or contract_idx == total_contracts
                ):
                    elapsed = time.time() - started
                    logger.info(
                        f"{symbol}: contracts {contract_idx}/{total_contracts}, "
                        f"with_data={contracts_with_data}, failed={contracts_failed}, "
                        f"elapsed={elapsed:.0f}s"
                    )
                continue

            expiry_date = pd.to_datetime(expiry, errors="coerce")
            fetch_start = self.start_date
            fetch_end = self.end_date
            if pd.notna(expiry_date):
                expiry_d = expiry_date.date()
                fetch_end = min(fetch_end, expiry_d)
                if self.contract_listing_lookback_days > 0:
                    listing_start = expiry_d - timedelta(days=self.contract_listing_lookback_days)
                    fetch_start = max(fetch_start, listing_start)
            if fetch_start > fetch_end:
                _, _ = self._resume_contract_paths(symbol, groww_symbol)
                _mark_contract_state(
                    groww_symbol=groww_symbol,
                    status="empty",
                    rows=0,
                    message="No overlap with active contract window",
                )
                continue

            try:
                candles = self._fetch_contract_candles_windowed(
                    exchange=exchange,
                    groww_symbol=groww_symbol,
                    start_date=fetch_start,
                    end_date=fetch_end,
                    trading_symbol=trading_symbol,
                )
            except GrowwRateLimitError as exc:
                contracts_failed += 1
                _mark_contract_state(
                    groww_symbol=groww_symbol,
                    status="failed",
                    rows=0,
                    message=f"rate_limited:{exc}",
                )
                logger.warning(f"{symbol} {groww_symbol}: rate limited after retries, skipping ({exc})")
                continue
            except GrowwForbiddenError:
                raise
            except Exception as exc:
                contracts_failed += 1
                _mark_contract_state(
                    groww_symbol=groww_symbol,
                    status="failed",
                    rows=0,
                    message=str(exc),
                )
                logger.debug(f"{symbol} {groww_symbol}: fetch failed: {exc}")
                continue

            data_path, relative_data_file = self._resume_contract_paths(symbol, groww_symbol)
            if candles.empty:
                if data_path.exists():
                    data_path.unlink()
                _mark_contract_state(
                    groww_symbol=groww_symbol,
                    status="empty",
                    rows=0,
                )
            else:
                contracts_with_data += 1
                part = candles.copy()
                part["symbol"] = symbol
                part["underlying"] = symbol
                part["expiry"] = expiry
                part["strike"] = strike
                part["option_type"] = option_type
                part["instrument_key"] = groww_symbol
                part["lot_size"] = lot_size
                part.to_parquet(data_path, index=False)
                _mark_contract_state(
                    groww_symbol=groww_symbol,
                    status="with_data",
                    rows=len(part),
                    data_file=relative_data_file,
                )

            if (
                contract_idx % self.progress_every_contracts == 0
                or contract_idx == total_contracts
            ):
                elapsed = time.time() - started
                logger.info(
                    f"{symbol}: contracts {contract_idx}/{total_contracts}, "
                    f"with_data={contracts_with_data}, failed={contracts_failed}, "
                    f"elapsed={elapsed:.0f}s"
                )

        _flush_state(force=True)

        contract_files: List[Path] = []
        seen_files: set[str] = set()
        resume_base = self._resume_underlying_dir(symbol)
        for contract in contracts.itertuples(index=False):
            groww_symbol = str(getattr(contract, "groww_symbol", "")).strip()
            if not groww_symbol:
                continue
            entry = _state_entry(groww_symbol)
            if str(entry.get("status", "")).strip().lower() != "with_data":
                continue
            data_rel = str(entry.get("data_file", "")).strip()
            if not data_rel:
                continue
            data_path = resume_base / data_rel
            if not data_path.exists():
                continue
            key = str(data_path.resolve())
            if key in seen_files:
                continue
            seen_files.add(key)
            contract_files.append(data_path)

        if not contract_files:
            return UnderlyingResult(
                symbol=symbol,
                status="EMPTY",
                contracts_selected=len(contracts),
                contracts_with_data=0,
                contracts_failed=contracts_failed,
                file_path=str(output_file),
                message="No contract candles available",
            )

        contract_frames: List[pd.DataFrame] = []
        for part_file in contract_files:
            try:
                part = pd.read_parquet(part_file)
                if not part.empty:
                    contract_frames.append(part)
            except Exception as exc:
                logger.debug(f"{symbol}: failed to read checkpoint file {part_file}: {exc}")

        if not contract_frames:
            return UnderlyingResult(
                symbol=symbol,
                status="EMPTY",
                contracts_selected=len(contracts),
                contracts_with_data=0,
                contracts_failed=contracts_failed,
                file_path=str(output_file),
                message="Checkpointed contract data unreadable/empty",
            )

        chain = pd.concat(contract_frames, ignore_index=True)
        chain["date"] = pd.to_datetime(chain["date"], errors="coerce").dt.date
        chain["timestamp"] = pd.to_datetime(chain["timestamp"], errors="coerce")
        chain = chain.dropna(subset=["date", "expiry", "strike", "option_type"])

        if not spot_history.empty:
            chain = chain.merge(spot_history, on="date", how="left")
        else:
            chain["underlying_price"] = pd.NA

        inferred_spot = chain.groupby("date")["strike"].transform("median")
        chain["underlying_price"] = pd.to_numeric(chain["underlying_price"], errors="coerce")
        chain["underlying_price"] = chain["underlying_price"].fillna(inferred_spot)
        chain["underlying_price"] = chain["underlying_price"].replace(0, pd.NA).fillna(inferred_spot)
        chain["underlying_price"] = chain["underlying_price"].astype(float)

        chain["ltp"] = pd.to_numeric(chain["close"], errors="coerce").fillna(0.0)
        chain["volume"] = pd.to_numeric(chain["volume"], errors="coerce").fillna(0).astype(int)
        chain["oi"] = pd.to_numeric(chain["oi"], errors="coerce").fillna(0).astype(int)

        bids: List[float] = []
        asks: List[float] = []
        ivs: List[float] = []
        deltas: List[float] = []
        gammas: List[float] = []
        thetas: List[float] = []
        vegas: List[float] = []

        chain["days_to_expiry"] = (
            pd.to_datetime(chain["expiry"]) - pd.to_datetime(chain["date"])
        ).dt.days.clip(lower=0)
        chain["time_to_expiry"] = chain["days_to_expiry"].clip(lower=1).astype(float) / 365.0

        for row in chain.itertuples(index=False):
            ltp = _safe_float(row.ltp, 0.0)
            bid, ask = _estimate_bid_ask(ltp)
            bids.append(bid)
            asks.append(ask)

            spot = _safe_float(row.underlying_price, 0.0)
            strike = _safe_float(row.strike, 0.0)
            t = max(1.0 / 365.0, _safe_float(row.time_to_expiry, 1.0 / 365.0))
            option_type = str(row.option_type).upper()
            option_type = "CE" if option_type.startswith("C") else "PE"

            iv = _implied_volatility(
                market_price=max(0.01, ltp),
                spot=max(0.01, spot),
                strike=max(0.01, strike),
                time_to_expiry=t,
                risk_free_rate=self.risk_free_rate,
                option_type=option_type,
            )
            delta, gamma, theta, vega = _option_greeks(
                spot=max(0.01, spot),
                strike=max(0.01, strike),
                time_to_expiry=t,
                risk_free_rate=self.risk_free_rate,
                sigma=iv,
                option_type=option_type,
            )
            ivs.append(iv)
            deltas.append(delta)
            gammas.append(gamma)
            thetas.append(theta)
            vegas.append(vega)

        chain["bid"] = bids
        chain["ask"] = asks
        chain["iv"] = ivs
        chain["delta"] = deltas
        chain["gamma"] = gammas
        chain["theta"] = thetas
        chain["vega"] = vegas

        chain = chain.sort_values(["instrument_key", "date"]).reset_index(drop=True)
        chain["prev_oi"] = (
            chain.groupby("instrument_key")["oi"].shift(1).fillna(0).astype(int)
        )
        chain["change_oi"] = chain["oi"] - chain["prev_oi"]
        chain["moneyness"] = (
            chain["strike"] / chain["underlying_price"].replace(0, pd.NA)
        ).astype(float)

        # Conservative depth estimate from volume/lot size.
        depth = (chain["volume"].clip(lower=0) * 0.10).round().astype(int).clip(lower=1)
        lots = pd.to_numeric(chain["lot_size"], errors="coerce").fillna(1).astype(int).clip(lower=1)
        chain["bid_qty"] = depth.where(depth >= lots, lots)
        chain["ask_qty"] = depth.where(depth >= lots, lots)

        chain["premium"] = chain["ltp"].where(
            chain["ltp"] > 0,
            (chain["bid"] + chain["ask"]) / 2.0,
        )

        chain["option_type"] = chain["option_type"].astype(str).str.upper().replace({"C": "CE", "P": "PE"})

        final_cols = [
            "timestamp",
            "date",
            "symbol",
            "expiry",
            "strike",
            "option_type",
            "bid",
            "ask",
            "ltp",
            "bid_qty",
            "ask_qty",
            "volume",
            "oi",
            "prev_oi",
            "change_oi",
            "iv",
            "delta",
            "gamma",
            "theta",
            "vega",
            "underlying_price",
            "instrument_key",
            "days_to_expiry",
            "time_to_expiry",
            "moneyness",
            "underlying",
            "premium",
        ]
        chain = chain[final_cols].copy()
        chain = chain.dropna(subset=["date", "expiry", "strike", "option_type"])
        key_time_col = "timestamp" if (self.interval_minutes is not None and self.interval_minutes < 1440) else "date"
        # De-duplicate semantically equivalent contracts even if provider-specific
        # instrument identifiers differ (e.g. Groww symbol vs Upstox instrument_key).
        dedupe_subset = [key_time_col, "symbol", "expiry", "strike", "option_type"]
        sort_cols = [key_time_col, "expiry", "strike", "option_type"]
        chain = chain.drop_duplicates(
            subset=dedupe_subset,
            keep="last",
        )
        chain = chain.sort_values(sort_cols).reset_index(drop=True)

        if output_file.exists() and not self.overwrite:
            try:
                existing = pd.read_parquet(output_file)
                merged = pd.concat([existing, chain], ignore_index=True)
                merged = merged.drop_duplicates(
                    subset=dedupe_subset,
                    keep="last",
                )
                chain = merged.sort_values(sort_cols).reset_index(drop=True)
            except Exception as exc:
                logger.warning(f"{symbol}: could not merge existing parquet, rewriting file ({exc})")

        chain.to_parquet(output_file, index=False)
        cov_start = chain["date"].min()
        cov_end = chain["date"].max()
        cov_days = 0
        try:
            cov_days = int((pd.to_datetime(cov_end) - pd.to_datetime(cov_start)).days)
        except Exception:
            cov_days = 0

        return UnderlyingResult(
            symbol=symbol,
            status="SUCCESS",
            rows=len(chain),
            contracts_selected=len(contracts),
            contracts_with_data=int(chain["instrument_key"].nunique()),
            contracts_failed=contracts_failed,
            file_path=str(output_file),
            message=f"Saved {len(chain):,} rows",
            coverage_start=str(cov_start),
            coverage_end=str(cov_end),
            coverage_days=max(0, cov_days),
        )

    def _fetch_contract_candles_windowed(
        self,
        exchange: str,
        groww_symbol: str,
        start_date: date,
        end_date: date,
        trading_symbol: Optional[str] = None,
        max_window_days: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch candles in interval-appropriate chunks and merge.
        """
        if max_window_days is not None:
            window_days = int(max_window_days)
        elif hasattr(self.client, "max_window_days_for_contract"):
            window_days = int(self.client.max_window_days_for_contract(self.candle_interval, groww_symbol))
        else:
            window_days = int(self.client._max_window_days_for_interval(self.candle_interval))
        window_days = max(1, window_days)
        frames: List[pd.DataFrame] = []
        current_start = start_date

        while current_start <= end_date:
            current_end = min(end_date, current_start + timedelta(days=window_days - 1))
            payload = self.client.get_historical_candles(
                exchange=exchange,
                segment="FNO",
                groww_symbol=groww_symbol,
                start_time=_to_groww_ts(current_start, end_of_day=False),
                end_time=_to_groww_ts(current_end, end_of_day=True),
                candle_interval=self.candle_interval,
                trading_symbol=trading_symbol,
            )
            candles = _parse_candles(payload)
            if not candles.empty:
                frames.append(candles)
            current_start = current_end + timedelta(days=1)

        if not frames:
            return pd.DataFrame(columns=["timestamp", "date", "open", "high", "low", "close", "volume", "oi"])

        out = pd.concat(frames, ignore_index=True)
        out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        return out.reset_index(drop=True)

    def _fetch_underlying_spot_history(
        self,
        symbol: str,
        instruments: pd.DataFrame,
        start_ts: str,
        end_ts: str,
    ) -> pd.DataFrame:
        candidates: List[Tuple[str, str, str, Optional[str]]] = []
        aliases = [symbol] + INDEX_SPOT_ALIASES.get(symbol, [])
        alias_set = {a.strip().upper() for a in aliases if a.strip()}

        inst = instruments.copy()
        inst["exchange"] = inst["exchange"].astype(str).str.upper()
        inst["segment"] = inst["segment"].astype(str).str.upper()
        inst["trading_symbol"] = inst["trading_symbol"].astype(str).str.upper()

        inst_rows = inst[
            inst["exchange"].eq("NSE")
            & inst["trading_symbol"].isin(alias_set)
            & inst["groww_symbol"].notna()
            & ~inst["segment"].eq("FNO")
        ][["exchange", "segment", "groww_symbol", "trading_symbol"]].drop_duplicates()

        for row in inst_rows.itertuples(index=False):
            exchange = str(row.exchange).strip().upper() or "NSE"
            segment = str(row.segment).strip().upper()
            # Backtesting candles support CASH/FNO; map non-FNO spot segments (e.g. INDEX) to CASH.
            segment = "CASH" if segment != "FNO" else "FNO"
            trading_symbol = str(getattr(row, "trading_symbol", "") or "").strip() or None
            candidates.append((exchange, segment, str(row.groww_symbol), trading_symbol))

        # Explicit fallbacks when non-FNO row is absent in instrument master.
        candidates.extend(
            [
                ("NSE", "CASH", f"NSE-{symbol}", symbol),
            ]
        )

        seen: set[Tuple[str, str, str, Optional[str]]] = set()
        ordered_candidates: List[Tuple[str, str, str, Optional[str]]] = []
        for item in candidates:
            if item in seen:
                continue
            seen.add(item)
            ordered_candidates.append(item)

        try:
            spot_start = _parse_date(str(start_ts)[:10])
            spot_end = _parse_date(str(end_ts)[:10])
        except Exception:
            spot_start = self.start_date
            spot_end = self.end_date
        spot_window_days = max(1, self.client._max_window_days_for_interval("1day"))

        for exchange, segment, groww_symbol, trading_symbol in ordered_candidates:
            try:
                frames: List[pd.DataFrame] = []
                current_start = spot_start
                while current_start <= spot_end:
                    current_end = min(spot_end, current_start + timedelta(days=spot_window_days - 1))
                    payload = self.client.get_historical_candles(
                        exchange=exchange,
                        segment=segment,
                        groww_symbol=groww_symbol,
                        start_time=_to_groww_ts(current_start, end_of_day=False),
                        end_time=_to_groww_ts(current_end, end_of_day=True),
                        candle_interval="1day",
                        trading_symbol=trading_symbol,
                    )
                    part = _parse_candles(payload)
                    if not part.empty:
                        frames.append(part)
                    current_start = current_end + timedelta(days=1)

                if not frames:
                    continue
                candles = pd.concat(frames, ignore_index=True)
                candles = candles.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
                if candles.empty:
                    continue
                out = candles[["date", "close"]].copy()
                out = out.rename(columns={"close": "underlying_price"})
                out["underlying_price"] = pd.to_numeric(out["underlying_price"], errors="coerce")
                out = out.dropna(subset=["underlying_price"])
                if not out.empty:
                    logger.debug(f"{symbol}: spot source {segment} {groww_symbol}")
                    return out
            except GrowwForbiddenError as exc:
                logger.debug(f"{symbol}: spot source forbidden for {segment} {groww_symbol}: {exc}")
                continue
            except GrowwRateLimitError as exc:
                logger.debug(f"{symbol}: spot source rate-limited for {segment} {groww_symbol}: {exc}")
                continue
            except Exception:
                continue

        logger.warning(f"{symbol}: could not fetch spot history, using strike-median fallback")
        return pd.DataFrame(columns=["date", "underlying_price"])


def _configure_logging(verbose: bool = False) -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "option_universe.log"),
            logging.StreamHandler(),
        ],
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build offline option-chain universe (NIFTY500 + indices) from broker historical APIs"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["groww", "upstox"],
        default="groww",
        help="Historical data provider (default: groww)",
    )
    date_group = parser.add_mutually_exclusive_group(required=False)
    date_group.add_argument(
        "--days",
        type=int,
        default=45,
        help="Collect this many calendar days backward from end date (default: 45)",
    )
    date_group.add_argument(
        "--years",
        type=int,
        help="Collect this many years backward from end date (e.g. 5 for last 5 years)",
    )
    date_group.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=_today_ist().isoformat(),
        help="End date in YYYY-MM-DD (default: today IST)",
    )
    parser.add_argument(
        "--underlyings",
        type=str,
        default="NIFTY500_PLUS_INDICES",
        help="NIFTY500_PLUS_INDICES | NIFTY500 | ALL_INDICES | comma-separated symbols",
    )
    parser.add_argument(
        "--universe-file",
        type=str,
        default="universe/nifty500.csv",
        help="Path to NIFTY500 universe CSV",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/options/historical",
        help="Output directory for normalized parquet files",
    )
    parser.add_argument(
        "--instrument-master-file",
        type=str,
        default="",
        help="Optional local CSV/parquet path for Groww instrument master (offline fallback)",
    )
    parser.add_argument(
        "--extra-contracts-file",
        action="append",
        default=[],
        help=(
            "Extra CSV/parquet file containing historical option contracts "
            "(expects columns like trading_symbol/groww_symbol/expiry_date/strike_price). "
            "Can be passed multiple times."
        ),
    )
    parser.add_argument(
        "--api-token",
        type=str,
        default="",
        help=(
            "Provider auth token override. "
            "For groww: bearer token. For upstox: UPSTOX access token."
        ),
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default="",
        help="Groww API key (used to generate access token if --api-secret/--api-totp is provided)",
    )
    parser.add_argument(
        "--api-secret",
        type=str,
        default="",
        help="Groww API secret for approval-flow token generation (/token/api/access)",
    )
    parser.add_argument(
        "--api-totp",
        type=str,
        default="",
        help="Groww TOTP for totp-flow token generation (/token/api/access)",
    )
    parser.add_argument(
        "--upstox-access-token",
        type=str,
        default="",
        help="Upstox access token (defaults to UPSTOX_ACCESS_TOKEN, falls back to --api-token)",
    )
    parser.add_argument(
        "--upstox-api-key",
        type=str,
        default="",
        help="Upstox API key (informational; OAuth auth-code flow is still required for token generation)",
    )
    parser.add_argument(
        "--upstox-api-secret",
        type=str,
        default="",
        help="Upstox API secret (informational; OAuth auth-code flow is still required for token generation)",
    )
    parser.add_argument(
        "--use-python-sdk",
        action="store_true",
        help="Use Groww Python SDK for historical candle pulls (same path as GrowwAPI.get_historical_candle_data)",
    )
    parser.add_argument(
        "--sdk-only",
        action="store_true",
        help="With --use-python-sdk, do not fallback to REST candles on SDK failures",
    )
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.065,
        help="Risk-free annual rate used for IV/Greeks backfill (default: 0.065)",
    )
    parser.add_argument(
        "--candle-interval",
        type=str,
        default="1day",
        help="Candle interval for historical pull (examples: 1day, 1week, 5minute, 15minute)",
    )
    parser.add_argument(
        "--request-interval-seconds",
        type=float,
        default=0.80,
        help="Delay between API calls to avoid rate-limit (default: 0.80)",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Retry attempts per request on transient errors",
    )
    parser.add_argument(
        "--max-underlyings",
        type=int,
        default=0,
        help="Limit number of symbols (0 means all)",
    )
    parser.add_argument(
        "--max-contracts-per-underlying",
        type=int,
        default=0,
        help="Limit contracts per symbol (0 means all)",
    )
    parser.add_argument(
        "--progress-every-contracts",
        type=int,
        default=50,
        help="Log progress every N contracts within each underlying (default: 50)",
    )
    parser.add_argument(
        "--future-expiry-days",
        type=int,
        default=45,
        help="Include contracts up to N days beyond end-date for near-expiry coverage (default: 45)",
    )
    parser.add_argument(
        "--contract-listing-lookback-days",
        type=int,
        default=365,
        help=(
            "Assumed max listing window before expiry; used to skip impossible contract windows "
            "(default: 365, set 0 to disable clamp)"
        ),
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable contract-level resume checkpoints",
    )
    parser.add_argument(
        "--resume-dir",
        type=str,
        default="",
        help="Custom directory for resume checkpoints (default: <output-dir>/_resume)",
    )
    parser.add_argument(
        "--refresh-instruments",
        action="store_true",
        help="Refresh cached instrument master from selected provider",
    )
    parser.add_argument(
        "--no-contracts-api",
        action="store_true",
        help="Do not use contracts/expiries discovery APIs (fallback to instrument-master selection only)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rebuild files even if date coverage already exists",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def _resolve_groww_bearer_token(args: argparse.Namespace) -> str:
    api_token = (
        str(args.api_token or "").strip()
        or str(os.getenv("GROWW_API_AUTH_TOKEN", "")).strip()
    )
    api_key = (
        str(args.api_key or "").strip()
        or str(os.getenv("GROWW_API_KEY", "")).strip()
    )
    api_secret = (
        str(args.api_secret or "").strip()
        or str(os.getenv("GROWW_API_SECRET", "")).strip()
    )
    api_totp = (
        str(args.api_totp or "").strip()
        or str(os.getenv("GROWW_API_TOTP", "")).strip()
    )

    # If key + secret/totp is present, always prefer generating a fresh access token.
    if api_key and (api_secret or api_totp):
        logger.info("Generating Groww access token via /token/api/access")
        return _generate_groww_access_token(
            api_key=api_key,
            api_secret=api_secret,
            api_totp=api_totp,
            timeout_seconds=int(args.timeout_seconds),
            max_retries=int(args.max_retries),
        )

    # If token looks like an API key (auth-* role) and secret/totp is present, exchange it.
    if api_token and (api_secret or api_totp):
        role_claim = GrowwOptionUniverseBuilder._extract_role_claim(api_token)
        if role_claim.lower().startswith("auth-"):
            logger.info("Provided token appears to be Groww API key; generating access token via /token/api/access")
            return _generate_groww_access_token(
                api_key=api_token,
                api_secret=api_secret,
                api_totp=api_totp,
                timeout_seconds=int(args.timeout_seconds),
                max_retries=int(args.max_retries),
            )

    # Backward compatibility: many setups export access token into GROWW_API_KEY.
    if api_token:
        return api_token
    if api_key:
        logger.warning(
            "Using GROWW_API_KEY directly as bearer token. "
            "Prefer setting GROWW_API_AUTH_TOKEN, or provide GROWW_API_SECRET/GROWW_API_TOTP to auto-generate token."
        )
        return api_key

    raise ValueError(
        "Missing Groww credentials. Set GROWW_API_AUTH_TOKEN, or GROWW_API_KEY + GROWW_API_SECRET/GROWW_API_TOTP, "
        "or pass --api-token / --api-key with secret/totp."
    )


def _resolve_upstox_access_token(args: argparse.Namespace) -> str:
    access_token = (
        str(args.upstox_access_token or "").strip()
        or str(os.getenv("UPSTOX_ACCESS_TOKEN", "")).strip()
        or str(args.api_token or "").strip()
    )
    if access_token.lower().startswith("bearer "):
        access_token = access_token.split(" ", 1)[1].strip()
    if access_token:
        return access_token

    api_key = (
        str(args.upstox_api_key or "").strip()
        or str(os.getenv("UPSTOX_API_KEY", "")).strip()
        or str(args.api_key or "").strip()
    )
    api_secret = (
        str(args.upstox_api_secret or "").strip()
        or str(os.getenv("UPSTOX_API_SECRET", "")).strip()
        or str(args.api_secret or "").strip()
    )
    if api_key and api_secret:
        raise ValueError(
            "Upstox key/secret detected but access token is missing. "
            "Upstox historical APIs require an OAuth access token (set UPSTOX_ACCESS_TOKEN or --upstox-access-token)."
        )

    raise ValueError(
        "Missing Upstox access token. Set UPSTOX_ACCESS_TOKEN or pass --upstox-access-token/--api-token."
    )


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(".env.options", override=False)

    args = _parse_args()
    _configure_logging(args.verbose)
    provider = str(args.provider or "groww").strip().lower() or "groww"

    end_date = _parse_date(args.end_date)
    if args.start_date:
        start_date = _parse_date(args.start_date)
    elif args.years is not None:
        start_date = end_date - timedelta(days=max(1, int(args.years)) * 365)
    else:
        start_date = end_date - timedelta(days=max(1, int(args.days)))

    if start_date > end_date:
        raise ValueError("start-date must be <= end-date")

    if end_date > _today_ist():
        raise ValueError("end-date cannot be in the future")

    candle_interval = _normalize_candle_interval(args.candle_interval)
    interval_minutes = GrowwBacktestingClient._parse_interval_minutes(candle_interval)

    if provider == "groww":
        if start_date < GROWW_BACKTESTING_START_DATE:
            logger.warning(
                f"Requested start-date {start_date} is before configured backtesting floor "
                f"({GROWW_BACKTESTING_START_DATE}). Proceeding with requested date; "
                "provider may return empty candles for unavailable history."
            )
    else:
        if interval_minutes is not None and interval_minutes < 1440 and start_date < UPSTOX_INTRADAY_HISTORY_START_DATE:
            logger.warning(
                f"Requested start-date {start_date} is before Upstox intraday history floor "
                f"({UPSTOX_INTRADAY_HISTORY_START_DATE}). Older intraday candles may be unavailable."
            )
        elif start_date < UPSTOX_EOD_HISTORY_START_DATE:
            logger.warning(
                f"Requested start-date {start_date} is before Upstox EOD history floor "
                f"({UPSTOX_EOD_HISTORY_START_DATE}). Provider may return empty candles."
            )
        if start_date <= date(2005, 1, 1):
            logger.warning(
                "Deep-history request detected for Upstox options. "
                "Final option-chain coverage depends on contract discovery availability "
                "(active instrument master + provider expired-contract windows), "
                "so returned option history may start much later than requested."
            )

    output_dir = Path(args.output_dir)
    if candle_interval != "1day":
        output_dir = output_dir / _interval_tag(candle_interval)

    request_interval_seconds = float(args.request_interval_seconds)
    if provider == "groww" and args.use_python_sdk and request_interval_seconds < 0.50:
        logger.warning(
            f"request-interval-seconds={request_interval_seconds:.2f}s is aggressive for Groww SDK. "
            "Clamping to 0.50s to reduce rate-limit failures."
        )
        request_interval_seconds = 0.50

    if provider == "groww":
        api_token = _resolve_groww_bearer_token(args)
    else:
        api_token = _resolve_upstox_access_token(args)

    # Do not log token values.
    logger.info(f"Starting {provider.upper()} offline option universe build")
    logger.info(f"Date range: {start_date} -> {end_date}")
    logger.info(f"Underlyings mode: {args.underlyings}")
    logger.info(f"Candle interval: {candle_interval}")
    if provider == "groww":
        logger.info(f"Contracts discovery: {'API (/historical/contracts)' if not args.no_contracts_api else 'instrument master only'}")
    else:
        logger.info(
            "Contracts discovery: "
            + ("instrument-master only" if args.no_contracts_api else "instrument-master filtered expiries/contracts")
        )
    logger.info(
        f"Contract filters: future-expiry-days={int(args.future_expiry_days)}, "
        f"listing-lookback-days={int(args.contract_listing_lookback_days)}"
    )
    logger.info(
        f"Resume checkpoints: {'disabled' if args.no_resume else 'enabled'}"
        + (f" ({Path(args.resume_dir).expanduser()})" if str(args.resume_dir).strip() else "")
    )
    if provider == "groww" and args.use_python_sdk:
        logger.info(
            f"Candle transport: Python SDK ({'no REST fallback' if args.sdk_only else 'REST fallback enabled'})"
        )
    elif provider == "upstox":
        logger.info("Candle transport: Upstox REST v3 (/historical-candle)")
    else:
        logger.info("Candle transport: REST")
    if args.extra_contracts_file:
        logger.info(f"Extra contracts files: {args.extra_contracts_file}")
    logger.info(f"Output dir: {output_dir}")

    if provider == "groww":
        client: Any = GrowwBacktestingClient(
            auth_token=api_token,
            timeout_seconds=args.timeout_seconds,
            request_interval_seconds=request_interval_seconds,
            max_retries=args.max_retries,
            use_python_sdk=bool(args.use_python_sdk),
            sdk_fallback_to_rest=not bool(args.sdk_only),
        )
    else:
        if args.use_python_sdk:
            logger.warning("--use-python-sdk is Groww-only and will be ignored for Upstox provider")
        client = UpstoxHistoricalClient(
            access_token=api_token,
            timeout_seconds=args.timeout_seconds,
            request_interval_seconds=request_interval_seconds,
            max_retries=args.max_retries,
        )

    extra_contract_paths: List[Path] = []
    for raw in (args.extra_contracts_file or []):
        text = str(raw or "").strip()
        if not text:
            continue
        for piece in text.split(","):
            item = piece.strip()
            if item:
                extra_contract_paths.append(Path(item).expanduser())

    builder = GrowwOptionUniverseBuilder(
        client=client,
        start_date=start_date,
        end_date=end_date,
        output_dir=output_dir,
        universe_file=Path(args.universe_file),
        index_symbols=DEFAULT_INDEX_SYMBOLS,
        risk_free_rate=args.risk_free_rate,
        overwrite=args.overwrite,
        max_contracts_per_underlying=args.max_contracts_per_underlying,
        max_underlyings=args.max_underlyings,
        refresh_instruments=args.refresh_instruments,
        instrument_master_file=Path(args.instrument_master_file).expanduser()
        if str(args.instrument_master_file).strip()
        else None,
        use_contracts_api=not bool(args.no_contracts_api),
        extra_contracts_files=extra_contract_paths,
        candle_interval=candle_interval,
        progress_every_contracts=args.progress_every_contracts,
        future_expiry_days=args.future_expiry_days,
        contract_listing_lookback_days=args.contract_listing_lookback_days,
        resume_enabled=not bool(args.no_resume),
        resume_dir=Path(args.resume_dir).expanduser() if str(args.resume_dir).strip() else None,
        provider=provider,
    )

    summary = builder.build(args.underlyings)

    success = summary["status_breakdown"]["SUCCESS"]
    failed = summary["status_breakdown"]["FAILED"]
    empty = summary["status_breakdown"]["EMPTY"]
    logger.info(
        f"Build complete. SUCCESS={success}, FAILED={failed}, "
        f"SKIPPED_NO_OPTIONS={summary['status_breakdown']['SKIPPED_NO_OPTIONS']}, "
        f"SKIPPED_EXISTING={summary['status_breakdown']['SKIPPED_EXISTING']}, "
        f"EMPTY={empty}"
    )

    if failed > 0:
        return 1
    if success == 0 and summary.get("requested_symbols", 0) > 0:
        logger.error("No successful underlyings built. Check API permissions or date range.")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.error("Interrupted by user")
        sys.exit(130)
    except Exception as exc:
        logger.exception(f"Fatal error: {exc}")
        sys.exit(1)
