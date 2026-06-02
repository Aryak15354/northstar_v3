#!/usr/bin/env python3
"""
Diagnose Groww API token permissions for historical/backtesting endpoints.

Usage:
  export GROWW_API_AUTH_TOKEN="..."
  python scripts/diagnose_groww_permissions.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests


BASE_URL = "https://api.groww.in/v1"
INSTRUMENT_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"


def _decode_claims(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        data = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8", errors="ignore")
        claims = json.loads(data)
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}


def _extract_role(claims: Dict[str, Any]) -> str:
    sub = claims.get("sub")
    if isinstance(sub, str):
        try:
            inner = json.loads(sub)
            role = inner.get("role")
            if isinstance(role, str):
                return role
        except Exception:
            pass
    role = claims.get("role")
    return str(role) if role is not None else ""


def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-VERSION": "1.0",
    }


def _probe(token: str, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(url, headers=_headers(token), params=params, timeout=20)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text[:400]}
        return {"status": r.status_code, "body": body}
    except Exception as exc:
        return {"status": None, "error": str(exc)}


def _extract_token_from_body(body: Any) -> str:
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


def _exchange_token(api_key: str, api_secret: str = "", api_totp: str = "") -> Dict[str, Any]:
    key = str(api_key or "").strip()
    secret = str(api_secret or "").strip()
    totp = str(api_totp or "").strip()
    if not key:
        return {"ok": False, "error": "missing_api_key"}
    if not secret and not totp:
        return {"ok": False, "error": "missing_api_secret_or_totp"}

    if secret:
        ts = str(int(time.time()))
        checksum = hashlib.sha256(f"{secret}{ts}".encode("utf-8")).hexdigest()
        body = {"key_type": "approval", "checksum": checksum, "timestamp": ts}
    else:
        body = {"key_type": "totp", "totp": totp}

    url = f"{BASE_URL}/token/api/access"
    try:
        r = requests.post(url, headers=_headers(key), json=body, timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:400]}
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "body": data}
        token = _extract_token_from_body(data)
        if not token:
            return {"ok": False, "status": r.status_code, "body": data, "error": "missing_token"}
        return {"ok": True, "status": r.status_code, "token": token}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def main() -> int:
    auth_token_env = os.getenv("GROWW_API_AUTH_TOKEN", "").strip()
    api_key_env = os.getenv("GROWW_API_KEY", "").strip()
    token_or_key = (
        auth_token_env
        or api_key_env
    )
    api_secret = os.getenv("GROWW_API_SECRET", "").strip()
    api_totp = os.getenv("GROWW_API_TOTP", "").strip()

    if not token_or_key:
        print("Missing token. Set GROWW_API_AUTH_TOKEN or GROWW_API_KEY.")
        return 1

    claims = _decode_claims(token_or_key)
    role = _extract_role(claims)
    exp = claims.get("exp")
    exp_dt = None
    if isinstance(exp, (int, float)):
        exp_dt = datetime.fromtimestamp(int(exp), tz=timezone.utc)

    print("Groww Token Diagnostics")
    print("=" * 60)
    print(f"role: {role or 'N/A'}")
    if exp_dt:
        print(f"expires_utc: {exp_dt.isoformat()}")
    print(f"has_api_secret: {'yes' if bool(api_secret) else 'no'}")
    print(f"has_api_totp: {'yes' if bool(api_totp) else 'no'}")
    print()

    token = token_or_key
    # If explicit auth token is not provided and key+secret/totp are present, always
    # attempt exchange before probing. This is the canonical API-key flow.
    should_exchange = bool(not auth_token_env and api_key_env and (api_secret or api_totp))
    if should_exchange:
        print("0) Exchange API key -> access token (/token/api/access)")
        exchanged = _exchange_token(api_key_env, api_secret=api_secret, api_totp=api_totp)
        print(json.dumps({k: v for k, v in exchanged.items() if k != "token"}, indent=2)[:1200])
        if not exchanged.get("ok"):
            print("\nDiagnosis: API key exchange failed. Historical probes cannot proceed.")
            return 2
        token = str(exchanged.get("token", "")).strip()
        print("access_token_exchange: success\n")

    print("1) Probe /historical/expiries")
    p1 = _probe(token, "/historical/expiries", {"exchange": "NSE", "underlying_symbol": "NIFTY", "year": str(datetime.utcnow().year)})
    print(json.dumps(p1, indent=2)[:1200])
    print()

    print("2) Probe /historical/candles (known NIFTY contract example)")
    p2 = _probe(
        token,
        "/historical/candles",
        {
            "exchange": "NSE",
            "segment": "FNO",
            "groww_symbol": "NSE-NIFTY-17Feb26-19600-CE",
            "start_time": "2026-02-06 00:00:00",
            "end_time": "2026-02-13 23:59:59",
            "candle_interval": "1day",
        },
    )
    print(json.dumps(p2, indent=2)[:1200])
    print()

    print("3) Probe /option-chain (live)")
    p3 = _probe(token, "/option-chain/exchange/NSE/underlying/NIFTY", {"expiry_date": "2026-02-17"})
    print(json.dumps(p3, indent=2)[:1200])
    print()

    print("4) Probe instrument master host")
    try:
        r = requests.get(INSTRUMENT_URL, timeout=20)
        print(f"instrument_master_status: {r.status_code}, bytes={len(r.text)}")
    except Exception as exc:
        print(f"instrument_master_error: {exc}")
    print()

    hist_ok = p1.get("status") == 200 and p2.get("status") == 200
    live_ok = p3.get("status") == 200
    if (not hist_ok) and live_ok:
        print("Diagnosis: token has live-data access but no historical/backtesting permission.")
        print("Action: enable backtesting/historical scope on Groww app and regenerate token.")
        return 2
    if not hist_ok:
        print("Diagnosis: historical/backtesting access unavailable.")
        print("Action: verify credentials/token validity and ensure backtesting/historical scope is enabled.")
        return 2
    print("Historical endpoints look accessible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
