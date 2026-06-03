#!/usr/bin/env python3
"""
Smoke test for Groww Python SDK historical candles.

Example:
  export GROWW_API_KEY="..."
  export GROWW_API_SECRET="..."
  python3 scripts/test_groww_sdk_historical.py \
    --symbol RELIANCE \
    --segment CASH \
    --start-time "2026-02-10 09:15:00" \
    --end-time "2026-02-10 15:30:00" \
    --interval-minutes 5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict

import requests

try:
    from growwapi import GrowwAPI
except Exception as exc:  # pragma: no cover - dependency check
    print(
        "Missing dependency 'growwapi'. Install it with:\n"
        "  python3 -m pip install growwapi\n"
        f"Import error: {exc}"
    )
    sys.exit(1)


BASE_URL = "https://api.groww.in/v1"


def _extract_token(body: Any) -> str:
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


def _exchange_api_key(api_key: str, api_secret: str = "", api_totp: str = "") -> str:
    key = str(api_key or "").strip()
    secret = str(api_secret or "").strip()
    totp = str(api_totp or "").strip()
    if not key:
        raise ValueError("Missing api key")
    if not secret and not totp:
        raise ValueError("Provide api secret or api totp")

    if secret:
        ts = str(int(time.time()))
        checksum = hashlib.sha256(f"{secret}{ts}".encode("utf-8")).hexdigest()
        req = {"key_type": "approval", "checksum": checksum, "timestamp": ts}
    else:
        req = {"key_type": "totp", "totp": totp}

    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-VERSION": "1.0",
    }
    response = requests.post(f"{BASE_URL}/token/api/access", headers=headers, json=req, timeout=30)
    response.raise_for_status()
    body = response.json()
    if isinstance(body, dict) and body.get("status") == "FAILURE":
        err = body.get("error", {})
        raise RuntimeError(f"Token exchange failed {err.get('code')}: {err.get('message')}")
    token = _extract_token(body)
    if not token:
        raise RuntimeError("Token exchange succeeded but access token missing in payload")
    return token


def _resolve_token(arg_token: str, arg_key: str, arg_secret: str, arg_totp: str) -> str:
    auth_token = str(arg_token or "").strip() or str(os.getenv("GROWW_API_AUTH_TOKEN", "")).strip()
    api_key = str(arg_key or "").strip() or str(os.getenv("GROWW_API_KEY", "")).strip()
    api_secret = str(arg_secret or "").strip() or str(os.getenv("GROWW_API_SECRET", "")).strip()
    api_totp = str(arg_totp or "").strip() or str(os.getenv("GROWW_API_TOTP", "")).strip()

    if auth_token:
        return auth_token
    if api_key and (api_secret or api_totp):
        return _exchange_api_key(api_key, api_secret=api_secret, api_totp=api_totp)
    if api_key:
        return api_key
    raise ValueError("Missing Groww credentials. Set GROWW_API_AUTH_TOKEN, or GROWW_API_KEY + secret/totp.")


def _parse_args() -> argparse.Namespace:
    now = datetime.now()
    default_end = now.replace(second=0, microsecond=0)
    default_start = default_end - timedelta(hours=1)

    parser = argparse.ArgumentParser(description="Test Groww Python SDK historical candle endpoint")
    parser.add_argument("--token", type=str, default="", help="Groww access token")
    parser.add_argument("--api-key", type=str, default="", help="Groww API key")
    parser.add_argument("--api-secret", type=str, default="", help="Groww API secret")
    parser.add_argument("--api-totp", type=str, default="", help="Groww API totp")
    parser.add_argument("--symbol", type=str, default="RELIANCE", help="Trading symbol (e.g. RELIANCE)")
    parser.add_argument("--exchange", type=str, default="NSE", help="Exchange (e.g. NSE)")
    parser.add_argument("--segment", type=str, default="CASH", help="Segment CASH/FNO/INDEX")
    parser.add_argument("--start-time", type=str, default=default_start.strftime("%Y-%m-%d %H:%M:%S"))
    parser.add_argument("--end-time", type=str, default=default_end.strftime("%Y-%m-%d %H:%M:%S"))
    parser.add_argument("--interval-minutes", type=int, default=5, help="Candle interval in minutes")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = _resolve_token(args.token, args.api_key, args.api_secret, args.api_totp)

    groww = GrowwAPI(token)
    exchange_value = getattr(groww, f"EXCHANGE_{str(args.exchange).strip().upper()}", str(args.exchange).strip().upper())
    seg_key = str(args.segment).strip().upper()
    if seg_key == "INDEX":
        seg_key = "CASH"
    segment_value = getattr(groww, f"SEGMENT_{seg_key}", seg_key)

    response = groww.get_historical_candle_data(
        trading_symbol=str(args.symbol).strip(),
        exchange=exchange_value,
        segment=segment_value,
        start_time=str(args.start_time).strip(),
        end_time=str(args.end_time).strip(),
        interval_in_minutes=int(args.interval_minutes),
    )
    print(json.dumps(response, indent=2, default=str)[:4000])

    if isinstance(response, dict):
        status = str(response.get("status", "")).upper()
        if status == "FAILURE":
            err = response.get("error", {})
            code = str(err.get("code", "")).strip()
            msg = str(err.get("message", "")).strip()
            print(f"SDK historical call failed: code={code}, message={msg}")
            return 2 if code == "403" else 1
        payload = response.get("payload", response)
        candles = payload.get("candles", []) if isinstance(payload, dict) else []
        print(f"candles_count={len(candles)}")
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Fatal error: {exc}")
        sys.exit(1)
