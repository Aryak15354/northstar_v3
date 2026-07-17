"""Self-contained Black-Scholes European option pricer + greeks.

Used by the OptionsOrgan to price and risk-assess option structures for ANY
underlying (indices and the ~F&O stock universe) when a live Upstox option
chain is not available. NSE index and stock options are European-style, so the
closed-form Black-Scholes model is appropriate. When a live chain IS available
the organ uses observed premiums instead and only borrows the greeks here.

All greeks are returned in practical trading units:
  delta  : per 1.00 move in spot        (call in [0,1], put in [-1,0])
  gamma  : d(delta)/d(spot)
  vega   : per 1 percentage-point (1%) change in IV   (i.e. raw vega / 100)
  theta  : per calendar day                            (i.e. raw annual / 365)
  rho    : per 1 percentage-point change in rates      (raw / 100)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

OptionType = Literal["CE", "PE"]

_SQRT_2PI = math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


@dataclass(frozen=True)
class OptionQuote:
    """A single modeled option leg: fair price + greeks."""
    option_type: OptionType
    strike: float
    price: float
    delta: float
    gamma: float
    theta: float   # per calendar day
    vega: float    # per 1% IV
    rho: float     # per 1% rate


def _d1_d2(spot: float, strike: float, t: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    # Guard degenerate inputs so the pricer never raises on bad data.
    sigma = max(float(sigma), 1e-6)
    t = max(float(t), 1e-6)
    spot = max(float(spot), 1e-9)
    strike = max(float(strike), 1e-9)
    vol_sqrt_t = sigma * math.sqrt(t)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * sigma * sigma) * t) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def price_and_greeks(
    *,
    option_type: OptionType,
    spot: float,
    strike: float,
    days_to_expiry: float,
    iv: float,
    rate: float = 0.065,
    dividend_yield: float = 0.0,
) -> OptionQuote:
    """Black-Scholes fair value + greeks for one European option.

    days_to_expiry is calendar days; iv and rate are decimals (0.20 = 20%).
    """
    t = max(float(days_to_expiry), 0.0) / 365.0
    if t <= 0.0:
        # At/after expiry: intrinsic value, delta is a step, other greeks ~0.
        intrinsic = max(spot - strike, 0.0) if option_type == "CE" else max(strike - spot, 0.0)
        delta = (1.0 if spot > strike else 0.0) if option_type == "CE" else (-1.0 if spot < strike else 0.0)
        return OptionQuote(option_type, strike, intrinsic, delta, 0.0, 0.0, 0.0, 0.0)

    sigma = max(float(iv), 1e-6)
    r = float(rate)
    q = float(dividend_yield)
    d1, d2 = _d1_d2(spot, strike, t, r, sigma, q)
    disc_r = math.exp(-r * t)
    disc_q = math.exp(-q * t)
    pdf_d1 = _norm_pdf(d1)

    if option_type == "CE":
        price = spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
        delta = disc_q * _norm_cdf(d1)
        theta_annual = (
            -(spot * disc_q * pdf_d1 * sigma) / (2.0 * math.sqrt(t))
            - r * strike * disc_r * _norm_cdf(d2)
            + q * spot * disc_q * _norm_cdf(d1)
        )
        rho_raw = strike * t * disc_r * _norm_cdf(d2)
    else:  # PE
        price = strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)
        delta = -disc_q * _norm_cdf(-d1)
        theta_annual = (
            -(spot * disc_q * pdf_d1 * sigma) / (2.0 * math.sqrt(t))
            + r * strike * disc_r * _norm_cdf(-d2)
            - q * spot * disc_q * _norm_cdf(-d1)
        )
        rho_raw = -strike * t * disc_r * _norm_cdf(-d2)

    gamma = (disc_q * pdf_d1) / (spot * sigma * math.sqrt(t))
    vega_raw = spot * disc_q * pdf_d1 * math.sqrt(t)  # per 1.00 (100%) change in IV

    return OptionQuote(
        option_type=option_type,
        strike=float(strike),
        price=max(float(price), 0.0),
        delta=float(delta),
        gamma=float(gamma),
        theta=float(theta_annual) / 365.0,   # per calendar day
        vega=float(vega_raw) / 100.0,         # per 1% IV
        rho=float(rho_raw) / 100.0,           # per 1% rate
    )


def atm_iv_estimate(realized_vol_annual: float, regime: str = "") -> float:
    """A pragmatic ATM implied-vol estimate when no option chain is available:
    scale realized vol up by a regime-aware volatility risk premium (options
    typically trade at a premium to realized, more so in stressed regimes)."""
    rv = max(float(realized_vol_annual), 0.05)
    regime_l = (regime or "").lower()
    if any(k in regime_l for k in ("crisis", "panic", "hostile", "stress", "bear")):
        premium = 1.35
    elif any(k in regime_l for k in ("expansion", "bull", "supportive", "calm", "low")):
        premium = 1.10
    else:
        premium = 1.20
    return min(max(rv * premium, 0.08), 1.50)
