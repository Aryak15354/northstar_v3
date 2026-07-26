#!/usr/bin/env python3
"""Parse cached raw responses into rows matching `shareholding_quarterly.parquet`'s own schema:
ticker, quarter, availability_date, promoter_pct, fii_pct, dii_pct, public_pct, govt_pct,
n_shareholders, is_delisted, record_origin, quarter_end.

This step is entirely network-free and safe to re-run any number of times against whatever is
already in the cache -- the whole point of caching raw responses first (see cache.py's docstring).

FIELD-NAME DISCLOSURE: category keyword lists below (`_CATEGORY_KEYWORDS`) are a best-effort mapping
from common SEBI Regulation-31 disclosure terminology to promoter/fii/dii/public/govt buckets. They
have NOT been checked against a real live BSE/NSE payload in this session (both domains are blocked
by this environment's browsing policy). **Before trusting parsed output across the full backfill,
run `run_scrape.py --verify`, inspect one real cached response, and refine `_CATEGORY_KEYWORDS` if
the actual field/category labels differ.** The matching logic itself (`_match_category`,
`_extract_records`) is unit-tested against synthetic fixtures in `test_parse.py` -- that tests the
LOGIC, not the keyword guesses.
"""
from __future__ import annotations

import json
import re
import sys
from io import StringIO
from pathlib import Path

import pandas as pd

try:
    from scripts.microstructure.bse_nse_shareholding_scraper import cache
except ModuleNotFoundError:  # direct script execution: python3 parse.py
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cache  # type: ignore[no-redef]

# Order matters: `_match_category` checks categories in this order and returns the first hit, so
# narrower/exclusionary patterns (e.g. "Non-Promoter..." must land in public_pct, not promoter_pct)
# are listed before the broad `\bpromoter\b` catch-all, which would otherwise wrongly match the
# substring "promoter" inside "Non-Promoter Non-Public".
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "fii_pct": [r"foreign\s*portfolio", r"\bfii\b", r"\bfpi\b", r"foreign\s*institutional"],
    "dii_pct": [r"mutual\s*fund", r"\bdii\b", r"domestic\s*institutional",
               r"financial\s*institution", r"insurance\s*compan"],
    "govt_pct": [r"central\s*government", r"state\s*government", r"president\s*of\s*india",
                r"\bgovernment\b"],
    "public_pct": [r"^public$", r"public\s*shareholding", r"non[\s-]*promoter"],
    "promoter_pct": [r"\bpromoter\b"],
}
_SHAREHOLDER_COUNT_KEYWORDS = [r"no\.?\s*of\s*shareholders", r"number\s*of\s*shareholders",
                              r"total\s*no\.?\s*of\s*shareholders"]


def _match_category(label: str) -> str | None:
    low = str(label or "").strip().lower()
    for category, patterns in _CATEGORY_KEYWORDS.items():
        for pat in patterns:
            if re.search(pat, low):
                return category
    return None


def _is_shareholder_count_label(label: str) -> bool:
    low = str(label or "").strip().lower()
    return any(re.search(p, low) for p in _SHAREHOLDER_COUNT_KEYWORDS)


def _extract_records(payload) -> list[dict]:
    """Normalize a JSON payload (list, or dict wrapping a list under a common key) into a flat list
    of {label: ..., value: ...}-shaped or free-form dict records."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("Table", "Data", "data", "Table1", "results"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


def _category_pct_from_records(records: list[dict], label_keys: list[str],
                               value_keys: list[str]) -> dict[str, float]:
    """Given free-form records, find (label, value) pairs and bucket them by category."""
    out: dict[str, float] = {}
    shareholders = None
    for rec in records:
        if not isinstance(rec, dict):
            continue
        label = next((rec[k] for k in label_keys if k in rec and rec[k]), None)
        value = next((rec[k] for k in value_keys if k in rec and rec[k] is not None), None)
        if label is None or value is None:
            continue
        try:
            v = float(str(value).replace(",", "").replace("%", "").strip())
        except (ValueError, TypeError):
            continue
        if _is_shareholder_count_label(label):
            shareholders = v
            continue
        cat = _match_category(label)
        if cat:
            out[cat] = out.get(cat, 0.0) + v
    if shareholders is not None:
        out["n_shareholders"] = shareholders
    return out


# common label/value key-name guesses across BSE/NSE JSON shapes -- extend once real payloads are seen
_LABEL_KEYS = ["Category", "category", "Particulars", "particulars", "CategoryName", "Desc", "desc"]
_VALUE_KEYS = ["Percentage", "percentage", "Perc", "PercentageOfTotal", "Value", "value",
              "Pct_of_Total_Shares", "No_Of_Shareholders"]


def parse_bse_json(raw: bytes) -> dict[str, float]:
    payload = json.loads(raw)
    records = _extract_records(payload)
    return _category_pct_from_records(records, _LABEL_KEYS, _VALUE_KEYS)


def parse_nse_json(raw: bytes) -> dict[str, float]:
    payload = json.loads(raw)
    records = _extract_records(payload)
    return _category_pct_from_records(records, _LABEL_KEYS, _VALUE_KEYS)


def parse_bse_csv(raw: bytes) -> dict[str, float]:
    text = raw.decode("utf-8", errors="replace")
    df = pd.read_csv(StringIO(text))
    if df.empty or df.shape[1] < 2:
        return {}
    label_col, value_col = df.columns[0], df.columns[-1]
    records = [{"__label": r[label_col], "__value": r[value_col]} for _, r in df.iterrows()]
    return _category_pct_from_records(records, ["__label"], ["__value"])


def parse_cached_entry(source: str, path) -> dict[str, float]:
    raw = path.read_bytes()
    if path.suffix == ".csv":
        return parse_bse_csv(raw)
    if source == "bse":
        return parse_bse_json(raw)
    return parse_nse_json(raw)


def build_normalized_table(source: str) -> pd.DataFrame:
    """Walk every cached entry for `source` and emit rows matching the canonical schema. Network-free
    -- operates purely on what's already in data/raw/exchanges/shareholding_pattern_scrape/."""
    rows = []
    for identifier, quarter_label, path in cache.iter_cached(source):
        try:
            cats = parse_cached_entry(source, path)
        except Exception as exc:
            rows.append(dict(identifier=identifier, quarter=quarter_label, parse_error=str(exc)[:200]))
            continue
        if not cats:
            continue
        row = dict(identifier=identifier, quarter=quarter_label, record_origin=f"{source}_scrape")
        for cat in ("promoter_pct", "fii_pct", "dii_pct", "public_pct", "govt_pct", "n_shareholders"):
            row[cat] = cats.get(cat)
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "nse"
    df = build_normalized_table(src)
    print(f"parsed {len(df)} rows from cached {src} responses")
    if len(df):
        print(df.head(10))
