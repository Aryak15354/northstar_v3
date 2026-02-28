"""
Upstox API Adapter for Options Trading System

Fetches live options data from Upstox API and normalizes to pipeline format.
Implements OAuth token management, rate limiting, and error handling.
"""

import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from pathlib import Path

from src.options.config_loader import UpstoxConfig

logger = logging.getLogger("options.upstox")


@dataclass
class RateLimiter:
    """Simple rate limiter for API calls"""
    max_calls_per_second: int
    last_call_time: float = 0.0
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit"""
        min_interval = 1.0 / self.max_calls_per_second
        elapsed = time.time() - self.last_call_time
        
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.3f}s")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()


class UpstoxAdapter:
    """
    Adapter for Upstox API to fetch options data
    
    Implements:
    - OAuth token management with automatic refresh
    - Rate limiting (1 request/second)
    - Option chain fetching with Greeks
    - Data normalization to parquet format
    - Error handling with exponential backoff
    """
    
    def __init__(self, config: UpstoxConfig):
        """
        Initialize Upstox adapter
        
        Args:
            config: Upstox configuration object
        """
        self.config = config
        self.rate_limiter = RateLimiter(max_calls_per_second=config.rate_limit_per_second)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Authorization': f'Bearer {config.access_token}'
        })
        self.fail_fast_on_dns_error = str(os.getenv("UPSTOX_FAIL_FAST_ON_DNS_ERROR", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        try:
            self.network_error_backoff_seconds = max(
                10.0,
                float(os.getenv("UPSTOX_NETWORK_FAIL_FAST_BACKOFF_SECONDS", "180")),
            )
        except Exception:
            self.network_error_backoff_seconds = 180.0
        self.network_down_until: float = 0.0
        
        # Instrument key mapping for all supported indices
        self.instrument_key_map = {
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
        
        # Indices not supported by Upstox API (will be skipped silently)
        self.unsupported_indices = {
            "NIFTYIT",  # Returns 400 Bad Request
        }
        
        logger.info("UpstoxAdapter initialized")

    @staticmethod
    def _is_dns_resolution_error(exc: Exception) -> bool:
        msg = str(exc or "")
        return any(
            token in msg
            for token in (
                "NameResolutionError",
                "Failed to resolve",
                "nodename nor servname provided",
                "Temporary failure in name resolution",
            )
        )

    def _mark_network_unavailable(self) -> None:
        self.network_down_until = max(
            self.network_down_until,
            time.time() + float(self.network_error_backoff_seconds),
        )

    def is_network_available(self) -> bool:
        return time.time() >= float(self.network_down_until)

    @staticmethod
    def _to_pipe_key(instrument_key: str) -> str:
        """Normalize API instrument keys to internal pipe format."""
        return str(instrument_key or "").replace(":", "|")

    @staticmethod
    def _to_colon_key(instrument_key: str) -> str:
        """Normalize internal instrument keys to API colon format."""
        return str(instrument_key or "").replace("|", ":")

    def _candidate_keys(self, instrument_key: str) -> List[str]:
        """
        Return de-duplicated key variants to maximize API compatibility.
        """
        pipe = self._to_pipe_key(instrument_key)
        colon = self._to_colon_key(instrument_key)
        if pipe == colon:
            return [pipe]
        return [pipe, colon]
    
    def _make_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make HTTP request with rate limiting and retry logic
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Query parameters
            data: Request body
            max_retries: Maximum number of retries
        
        Returns:
            Response JSON as dictionary
        
        Raises:
            requests.HTTPError: If request fails after retries
        """
        if not self.is_network_available():
            remaining = max(0.0, float(self.network_down_until) - time.time())
            raise requests.ConnectionError(
                f"Upstox network backoff active ({remaining:.0f}s remaining)"
            )

        self.rate_limiter.wait_if_needed()
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    timeout=30
                )
                response.raise_for_status()
                return response.json()
            
            except requests.HTTPError as e:
                if e.response.status_code == 401:
                    # Token expired, try to refresh
                    logger.warning("Access token expired, attempting refresh")
                    self.refresh_token()
                    continue
                
                elif e.response.status_code == 429:
                    # Rate limit exceeded
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limit exceeded, waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                elif attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise
            
            except requests.RequestException as e:
                if self.fail_fast_on_dns_error and self._is_dns_resolution_error(e):
                    self._mark_network_unavailable()
                    logger.warning(
                        "Upstox DNS/network resolution failure; entering fail-fast backoff for %.0fs",
                        self.network_error_backoff_seconds,
                    )
                    raise
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Request error (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise
        
        raise RuntimeError("Request failed after all retries")
    
    def refresh_token(self) -> str:
        """
        Refresh access token from local token sources.

        Returns:
            New access token

        Note:
            Upstox access tokens expire daily. This method supports
            manual daily token rotation by reloading from:
            1) UPSTOX_ACCESS_TOKEN env var
            2) UPSTOX_ACCESS_TOKEN_FILE (raw token or KEY=VALUE format)
            3) .env.options (or UPSTOX_ENV_FILE)
        """
        logger.info("Refreshing Upstox access token")

        new_token = self._load_access_token_from_sources(
            prefer_files=True,
            current_token=self.config.access_token,
        )
        if not new_token:
            raise NotImplementedError(
                "No refreshed access token found. "
                "Update UPSTOX_ACCESS_TOKEN (or .env.options) and retry."
            )

        if new_token == self.config.access_token:
            # We still return the token for caller compatibility, but surface
            # clear guidance that a fresh token is required after a 401.
            logger.warning("Access token refresh requested but token did not change")
            return new_token

        self.config.access_token = new_token
        self.session.headers.update({'Authorization': f'Bearer {new_token}'})
        logger.info("Upstox access token refreshed from local credentials source")
        return new_token

    def _load_access_token_from_files(self) -> Optional[str]:
        """Load token from token file and .env.options-style file."""
        token_file = str(os.getenv("UPSTOX_ACCESS_TOKEN_FILE", "")).strip()
        if token_file:
            p = Path(token_file)
            if p.exists():
                try:
                    raw = p.read_text().strip()
                    if "=" in raw:
                        key, val = raw.split("=", 1)
                        if key.strip() == "UPSTOX_ACCESS_TOKEN":
                            raw = val.strip()
                    if raw:
                        return raw
                except Exception as e:
                    logger.warning(f"Failed reading token file {p}: {e}")

        env_file = Path(str(os.getenv("UPSTOX_ENV_FILE", ".env.options")).strip())
        if env_file.exists():
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    if key.strip() == "UPSTOX_ACCESS_TOKEN":
                        token = val.strip()
                        if token:
                            return token
            except Exception as e:
                    logger.warning(f"Failed parsing env file {env_file}: {e}")

        return None

    def _load_access_token_from_sources(
        self,
        prefer_files: bool = False,
        current_token: Optional[str] = None,
    ) -> Optional[str]:
        """Load token from env, token file, or .env.options."""
        current = str(current_token or self.config.access_token or "").strip()
        env_token = str(os.getenv("UPSTOX_ACCESS_TOKEN", "")).strip()
        file_token = self._load_access_token_from_files()

        if prefer_files:
            if file_token and file_token != current and file_token != "ROTATE_REQUIRED":
                return file_token
            if env_token and env_token != current and env_token != "ROTATE_REQUIRED":
                return env_token
            if file_token and file_token != "ROTATE_REQUIRED":
                return file_token
            if env_token and env_token != "ROTATE_REQUIRED":
                return env_token
            return None

        if env_token and env_token != "ROTATE_REQUIRED":
            return env_token
        if file_token and file_token != "ROTATE_REQUIRED":
            return file_token
        return None

    def get_available_expiries(
        self,
        underlying: str,
        instrument_key: Optional[str] = None,
        min_days: int = 0,
        limit: int = 8
    ) -> List[date]:
        """
        Fetch available expiries for an index/stock from option contracts endpoint.
        """
        # Skip unsupported indices silently
        if underlying in self.unsupported_indices:
            logger.debug(f"Skipping unsupported index: {underlying}")
            return []
        
        if instrument_key is None:
            instrument_key = self.instrument_key_map.get(underlying)
            if not instrument_key:
                raise ValueError(
                    f"Unknown underlying: {underlying}. "
                    f"Supported indices: {list(self.instrument_key_map.keys())}. "
                    f"For stocks, provide instrument_key parameter."
                )

        url = self.config.endpoints.get("option_contracts")
        if not url:
            raise ValueError("Missing option_contracts endpoint in configuration")

        today = datetime.utcnow().date()
        expiries: set[date] = set()
        last_error: Optional[Exception] = None

        for key_try in self._candidate_keys(instrument_key):
            try:
                response = self._make_request("GET", url, params={"instrument_key": key_try})
            except Exception as e:
                last_error = e
                logger.debug(f"Expiry fetch failed for {key_try}: {e}")
                continue

            data = response.get("data", []) or []
            for item in data:
                exp_raw = item.get("expiry") or item.get("expiry_date")
                if not exp_raw:
                    continue
                try:
                    exp = datetime.strptime(str(exp_raw), "%Y-%m-%d").date()
                except ValueError:
                    continue
                if (exp - today).days >= int(min_days):
                    expiries.add(exp)

            if expiries:
                break

        if not expiries and last_error:
            logger.warning(f"Could not fetch expiries for {underlying}: {last_error}")

        sorted_exp = sorted(expiries)
        return sorted_exp[:max(1, int(limit))]
    
    def get_underlying_price(self, symbol: str) -> float:
        """
        Get current price of underlying index
        
        Args:
            symbol: Symbol name (e.g., "NIFTY", "BANKNIFTY")
        
        Returns:
            Current price
        """
        # Map symbol to Upstox instrument key
        instrument_key = self.instrument_key_map.get(symbol)
        if not instrument_key:
            raise ValueError(f"Unknown symbol: {symbol}. Supported: {list(self.instrument_key_map.keys())}")
        
        url = self.config.endpoints['market_quote']

        last_error: Optional[Exception] = None
        for key_try in self._candidate_keys(instrument_key):
            try:
                response = self._make_request('GET', url, params={'instrument_key': key_try})
            except Exception as e:
                last_error = e
                logger.debug(f"Underlying price fetch failed for key {key_try}: {e}")
                continue

            # Extract LTP from response.
            # API may return either NSE_INDEX|... or NSE_INDEX:... in data keys.
            data = response.get('data', {}) or {}
            for out_key in self._candidate_keys(key_try):
                if out_key in data:
                    ltp = data[out_key].get('last_price')
                    if ltp is not None:
                        logger.info(f"{symbol} price: {ltp}")
                        return float(ltp)

        if last_error:
            raise ValueError(f"Could not fetch price for {symbol}: {last_error}")
        raise ValueError(f"Could not fetch price for {symbol}")
    
    def fetch_option_chain(
        self,
        underlying: str,
        expiry: date,
        instrument_key: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch complete option chain from Upstox API
        
        Uses /v2/option/chain endpoint which returns:
        - Complete option chain with market data
        - Greeks (delta, gamma, theta, vega, IV)
        - Bid/ask prices and quantities
        - OI and OI change
        
        Args:
            underlying: Underlying symbol (index like "NIFTY" or stock like "RELIANCE")
            expiry: Expiry date
            instrument_key: Optional instrument key (for stocks). If not provided, will look up from instrument_key_map
        
        Returns:
            DataFrame with normalized option chain data
        """
        logger.info(f"Fetching option chain for {underlying} expiry {expiry}")
        
        # Skip unsupported indices silently
        if underlying in self.unsupported_indices:
            logger.warning(f"No expiries available for {underlying}; skipping this underlying for now")
            return pd.DataFrame()
        
        # Use provided instrument_key or look up from map
        if instrument_key is None:
            instrument_key = self.instrument_key_map.get(underlying)
            
            if not instrument_key:
                raise ValueError(
                    f"Unknown underlying: {underlying}. "
                    f"Supported indices: {list(self.instrument_key_map.keys())}. "
                    f"For stocks, provide instrument_key parameter."
                )
        
        # Format expiry date (YYYY-MM-DD)
        expiry_str = expiry.strftime("%Y-%m-%d")
        
        # Make API request
        url = self.config.endpoints['option_chain']
        last_error: Optional[Exception] = None
        for key_try in self._candidate_keys(instrument_key):
            params = {
                'instrument_key': key_try,
                'expiry_date': expiry_str
            }
            logger.debug(f"API request: {url} with params: {params}")

            try:
                response = self._make_request('GET', url, params=params)
            except Exception as e:
                last_error = e
                logger.debug(f"Option chain fetch failed for key {key_try}: {e}")
                continue
            
            # Log raw response for debugging
            logger.debug(f"API response ({key_try}): {response}")
            
            # Check response status
            if response.get('status') != 'success':
                logger.warning(f"API returned non-success status for {key_try}: {response}")
                continue
            
            # Check if data exists
            data = response.get('data', [])
            if not data:
                logger.warning(f"API returned empty data for {key_try}")
                continue
            
            # Parse and normalize response
            df = self._normalize_option_chain(response, underlying, expiry)
            
            logger.info(f"Fetched {len(df)} option contracts")
            return df

        if last_error:
            logger.error(f"Option chain fetch failed for {underlying}: {last_error}")
        return pd.DataFrame()
    
    def _normalize_option_chain(
        self,
        response: Dict[str, Any],
        underlying: str,
        expiry: date
    ) -> pd.DataFrame:
        """
        Normalize Upstox API response to pipeline format
        
        Response structure:
        {
          "status": "success",
          "data": [
            {
              "expiry": "2025-02-13",
              "strike_price": 21100,
              "underlying_spot_price": 22976.2,
              "call_options": { "instrument_key": "...", "market_data": {...}, "option_greeks": {...} },
              "put_options": { "instrument_key": "...", "market_data": {...}, "option_greeks": {...} }
            }
          ]
        }
        
        Args:
            response: Raw API response
            underlying: Underlying symbol
            expiry: Expiry date
        
        Returns:
            Normalized DataFrame
        """
        data = response.get('data', [])
        if not data:
            logger.warning("Empty option chain response")
            return pd.DataFrame()
        
        rows = []
        timestamp = datetime.utcnow()
        
        for item in data:
            strike = item.get('strike_price')
            spot = item.get('underlying_spot_price')
            
            if not strike or not spot:
                continue
            
            # Process call options
            call_data = item.get('call_options')
            if call_data:
                row = self._extract_option_data_v2(
                    call_data, underlying, expiry, strike, spot, 'CE', timestamp
                )
                if row:
                    rows.append(row)
            
            # Process put options
            put_data = item.get('put_options')
            if put_data:
                row = self._extract_option_data_v2(
                    put_data, underlying, expiry, strike, spot, 'PE', timestamp
                )
                if row:
                    rows.append(row)
        
        if not rows:
            logger.warning("No valid option data extracted")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # Calculate days to expiry
        df['days_to_expiry'] = (expiry - timestamp.date()).days
        
        # Validate data
        df = self._validate_option_data(df)
        
        return df
    
    def _extract_option_data_v2(
        self,
        option_data: Dict[str, Any],
        underlying: str,
        expiry: date,
        strike: float,
        spot: float,
        option_type: str,
        timestamp: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Extract and validate single option data from v2 API response
        
        Structure:
        {
          "instrument_key": "NSE_FO|51059",
          "market_data": {
            "ltp": 2449.9,
            "volume": 0,
            "oi": 750,
            "bid_price": 1856.65,
            "bid_qty": 1125,
            "ask_price": 1941.65,
            "ask_qty": 1125,
            "prev_oi": 1500
          },
          "option_greeks": {
            "vega": 4.1731,
            "theta": -472.8941,
            "gamma": 0.0001,
            "delta": 0.743,
            "iv": 262.31
          }
        }
        """
        try:
            market_data = option_data.get('market_data', {})
            greeks = (
                option_data.get('option_greeks')
                or option_data.get('optionGreeks')
                or option_data.get('greeks')
                or option_data.get('market_greeks')
                or {}
            )
            
            # Extract values with defaults
            bid = float(market_data.get('bid_price', 0))
            ask = float(market_data.get('ask_price', 0))
            ltp = float(market_data.get('ltp', 0))
            
            # Use mid price if ltp is 0
            if ltp == 0 and bid > 0 and ask > 0:
                ltp = (bid + ask) / 2
            
            return {
                'timestamp': timestamp,
                'symbol': underlying,
                'expiry': expiry,
                'strike': float(strike),
                'option_type': option_type,
                'bid': bid,
                'ask': ask,
                'ltp': ltp,
                'bid_qty': int(market_data.get('bid_qty', 0)),
                'ask_qty': int(market_data.get('ask_qty', 0)),
                'volume': int(market_data.get('volume', 0)),
                'oi': int(market_data.get('oi', 0)),
                'prev_oi': int(market_data.get('prev_oi', 0)),
                'change_oi': int(market_data.get('oi', 0)) - int(market_data.get('prev_oi', 0)),
                'iv': float(greeks.get('iv', 0)) / 100.0,  # Convert from percentage to decimal
                'delta': float(greeks.get('delta', 0)),
                'gamma': float(greeks.get('gamma', 0)),
                'theta': float(greeks.get('theta', 0)),
                'vega': float(greeks.get('vega', 0)),
                'underlying_price': float(spot),
                'instrument_key': self._to_pipe_key(option_data.get('instrument_key', ''))
            }
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to extract option data for strike {strike} {option_type}: {e}")
            return None
    
    def _validate_option_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validate option chain data
        
        Checks:
        - No missing required fields
        - No negative Greeks
        - Valid strikes
        - Bid <= Ask
        """
        if df.empty:
            return df
        
        # Check for missing fields
        required_fields = [
            'symbol', 'expiry', 'strike', 'option_type', 'bid', 'ask', 'ltp',
            'iv', 'delta', 'gamma', 'theta', 'vega', 'oi', 'volume', 'underlying_price'
        ]
        
        missing_fields = set(required_fields) - set(df.columns)
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")
        
        # Remove rows with invalid data
        initial_count = len(df)
        
        # Remove negative strikes
        df = df[df['strike'] > 0]
        
        # Remove negative Greeks (except delta which can be negative for puts)
        df = df[df['gamma'] >= 0]
        df = df[df['vega'] >= 0]
        df = df[df['iv'] >= 0]
        
        # Remove invalid bid/ask
        df = df[df['bid'] >= 0]
        df = df[df['ask'] >= 0]
        df = df[df['bid'] <= df['ask']]
        
        # Remove zero OI (illiquid)
        df = df[df['oi'] > 0]
        
        removed_count = initial_count - len(df)
        if removed_count > 0:
            logger.warning(f"Removed {removed_count} invalid option contracts")
        
        return df
    
    def fetch_option_greeks(
        self,
        instrument_keys: List[str]
    ) -> pd.DataFrame:
        """
        Fetch real-time Greeks for specific options
        
        Uses /v3/market-quote/option-greek endpoint.
        Supports up to 50 instrument keys per request.
        
        Args:
            instrument_keys: List of Upstox instrument keys
        
        Returns:
            DataFrame with Greek data
        """
        if len(instrument_keys) > self.config.max_instruments_per_request:
            raise ValueError(
                f"Too many instruments ({len(instrument_keys)}). "
                f"Max {self.config.max_instruments_per_request} per request."
            )
        
        logger.info(f"Fetching Greeks for {len(instrument_keys)} instruments")
        
        url = self.config.endpoints['option_greeks']
        pipe_keys = [self._to_pipe_key(k) for k in instrument_keys]
        colon_keys = [self._to_colon_key(k) for k in instrument_keys]

        data: Dict[str, Any] = {}
        last_error: Optional[Exception] = None
        for keys_try in [pipe_keys, colon_keys]:
            try:
                response = self._make_request(
                    'GET',
                    url,
                    params={'instrument_key': ','.join(keys_try)}
                )
            except Exception as e:
                last_error = e
                logger.debug(f"Greeks fetch failed for key format sample {keys_try[:1]}: {e}")
                continue

            data = response.get('data', {}) or {}
            if data:
                break

        if not data and last_error:
            logger.error(f"Greeks fetch failed: {last_error}")
            return pd.DataFrame()

        # Parse response
        rows = []
        
        for instrument_key, greeks_data in data.items():
            try:
                rows.append({
                    'instrument_key': self._to_pipe_key(instrument_key),
                    'last_price': float(greeks_data.get('last_price', 0)),
                    'volume': int(greeks_data.get('volume', 0)),
                    'oi': int(greeks_data.get('oi', 0)),
                    'iv': float(greeks_data.get('iv', 0)) / 100.0,
                    'delta': float(greeks_data.get('delta', 0)),
                    'gamma': float(greeks_data.get('gamma', 0)),
                    'theta': float(greeks_data.get('theta', 0)),
                    'vega': float(greeks_data.get('vega', 0))
                })
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Failed to parse Greeks for {instrument_key}: {e}")
                continue
        
        df = pd.DataFrame(rows)
        logger.info(f"Fetched Greeks for {len(df)} instruments")
        
        return df
    
    def save_to_parquet(
        self,
        df: pd.DataFrame,
        filepath: str
    ) -> None:
        """
        Save option chain data to parquet file
        
        Args:
            df: Option chain DataFrame
            filepath: Output file path
        """
        if df.empty:
            logger.warning("Empty DataFrame, not saving")
            return
        
        df.to_parquet(filepath, index=False, engine='pyarrow')
        logger.info(f"Saved {len(df)} rows to {filepath}")


if __name__ == "__main__":
    # Test Upstox adapter
    import logging
    from src.options.config_loader import get_config
    
    logging.basicConfig(level=logging.INFO)
    
    config = get_config()
    adapter = UpstoxAdapter(config.upstox)
    
    # Test underlying price fetch
    try:
        nifty_price = adapter.get_underlying_price("NIFTY")
        print(f"NIFTY price: {nifty_price}")
    except Exception as e:
        print(f"Error fetching NIFTY price: {e}")
    
    # Test option chain fetch
    try:
        expiry = date.today() + timedelta(days=7)  # Next week expiry
        df = adapter.fetch_option_chain("NIFTY", expiry)
        print(f"\nFetched {len(df)} option contracts")
        print(df.head())
    except Exception as e:
        print(f"Error fetching option chain: {e}")
