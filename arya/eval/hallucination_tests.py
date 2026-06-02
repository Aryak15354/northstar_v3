"""Hallucination checks for ticker-like outputs."""

from __future__ import annotations

import re


SYMBOL_PATTERN = re.compile(r"\b[A-Z]{2,15}(?:\.NS|\.BO)?\b")
COMMON_NON_TICKERS = {
    "RBI",
    "SEBI",
    "NSE",
    "BSE",
    "NIFTY",
    "BANKNIFTY",
    "GDP",
    "CPI",
    "FII",
    "DII",
    "INR",
    "USD",
    "PAT",
    "EBITDA",
    "JSON",
}


def extract_uppercase_symbols(text: str) -> set[str]:
    symbols = set(SYMBOL_PATTERN.findall(text))
    return {symbol.removesuffix(".NS").removesuffix(".BO") for symbol in symbols} - COMMON_NON_TICKERS


def ticker_validity_rate(outputs: list[str], valid_symbols: set[str]) -> float:
    total = 0
    valid = 0
    normalised_valid = {s.removesuffix(".NS").removesuffix(".BO") for s in valid_symbols}
    for output in outputs:
        for symbol in extract_uppercase_symbols(output):
            total += 1
            if symbol in normalised_valid:
                valid += 1
    return 1.0 if total == 0 else valid / total

