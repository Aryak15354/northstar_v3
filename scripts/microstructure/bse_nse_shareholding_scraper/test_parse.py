#!/usr/bin/env python3
"""Unit tests for parse.py's category-matching logic, against SYNTHETIC fixtures.

These test the matching/aggregation LOGIC (does the parser correctly bucket labeled percentage
records into promoter/fii/dii/public/govt, sum multi-row categories, and skip shareholder-count
rows). They do NOT validate that `_CATEGORY_KEYWORDS` matches BSE/NSE's real field names -- that
requires a live response this session's sandboxed browsing policy could not fetch (bseindia.com and
nseindia.com are both blocked). Run these before the full scrape to confirm the logic is sound, then
run `run_scrape.py --verify` and compare against known values from
`data/canonical/fundamentals/shareholding_quarterly.parquet`'s 2023+ rows for the SAME ticker/quarter
to confirm the keyword guesses actually hold on a real payload.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse  # noqa: E402


def test_match_category_promoter():
    assert parse._match_category("Promoter & Promoter Group") == "promoter_pct"
    assert parse._match_category("Total Promoter") == "promoter_pct"


def test_match_category_fii_variants():
    assert parse._match_category("Foreign Portfolio Investors") == "fii_pct"
    assert parse._match_category("FII") == "fii_pct"
    assert parse._match_category("Foreign Institutional Investors") == "fii_pct"


def test_match_category_dii_variants():
    assert parse._match_category("Mutual Funds") == "dii_pct"
    assert parse._match_category("Domestic Institutional Investors") == "dii_pct"
    assert parse._match_category("Insurance Companies") == "dii_pct"


def test_match_category_govt():
    assert parse._match_category("Central Government") == "govt_pct"
    assert parse._match_category("President of India") == "govt_pct"


def test_match_category_public():
    assert parse._match_category("Public") == "public_pct"
    assert parse._match_category("Public Shareholding") == "public_pct"


def test_match_category_non_promoter_goes_to_public_not_promoter():
    """'Non-Promoter Non-Public' contains the substring 'promoter' but must NOT be bucketed into
    promoter_pct -- this is exactly why category order matters in _CATEGORY_KEYWORDS."""
    assert parse._match_category("Non-Promoter Non-Public") == "public_pct"
    assert parse._match_category("Non Promoter-Non Public Shareholding") == "public_pct"


def test_match_category_unrecognized_returns_none():
    assert parse._match_category("Some Unrelated Field") is None
    assert parse._match_category("") is None


def test_shareholder_count_detection():
    assert parse._is_shareholder_count_label("No. of Shareholders")
    assert parse._is_shareholder_count_label("Total No of Shareholders")
    assert not parse._is_shareholder_count_label("Promoter")


def test_extract_records_list_passthrough():
    payload = [{"a": 1}, {"a": 2}]
    assert parse._extract_records(payload) == payload


def test_extract_records_dict_wrapped():
    payload = {"Table": [{"a": 1}]}
    assert parse._extract_records(payload) == [{"a": 1}]
    payload2 = {"Data": [{"b": 2}]}
    assert parse._extract_records(payload2) == [{"b": 2}]
    assert parse._extract_records({"nothing": "useful"}) == []


def test_category_pct_from_records_sums_multirow_promoter():
    """A category split across multiple sub-rows (e.g. Indian promoters + foreign promoters, both
    labeled with 'Promoter' substrings) must sum, not overwrite."""
    records = [
        {"Category": "Promoter (Indian)", "Percentage": "30.5"},
        {"Category": "Promoter (Foreign)", "Percentage": "5.5"},
        {"Category": "Public", "Percentage": "64.0"},
    ]
    out = parse._category_pct_from_records(records, parse._LABEL_KEYS, parse._VALUE_KEYS)
    assert abs(out["promoter_pct"] - 36.0) < 1e-9
    assert abs(out["public_pct"] - 64.0) < 1e-9


def test_category_pct_extracts_shareholder_count_separately():
    records = [
        {"Category": "Promoter", "Percentage": "45.0"},
        {"Category": "No. of Shareholders", "Percentage": "12345"},
    ]
    out = parse._category_pct_from_records(records, parse._LABEL_KEYS, parse._VALUE_KEYS)
    assert out["n_shareholders"] == 12345.0
    assert "n_shareholders" not in {"promoter_pct"}  # sanity: not conflated with a pct category
    assert out["promoter_pct"] == 45.0


def test_category_pct_handles_percent_signs_and_commas():
    records = [{"Category": "FII", "Percentage": "12,345.6%"}]
    out = parse._category_pct_from_records(records, parse._LABEL_KEYS, parse._VALUE_KEYS)
    assert abs(out["fii_pct"] - 12345.6) < 1e-6


def test_category_pct_skips_unparseable_values():
    records = [{"Category": "Promoter", "Percentage": "N/A"}, {"Category": "Public", "Percentage": "70"}]
    out = parse._category_pct_from_records(records, parse._LABEL_KEYS, parse._VALUE_KEYS)
    assert "promoter_pct" not in out
    assert out["public_pct"] == 70.0


def test_parse_bse_json_end_to_end(tmp_path):
    payload = [
        {"Category": "Promoter & Promoter Group", "Percentage": "55.2"},
        {"Category": "Foreign Portfolio Investors", "Percentage": "20.1"},
        {"Category": "Mutual Funds", "Percentage": "10.0"},
        {"Category": "Public", "Percentage": "14.7"},
        {"Category": "No. of Shareholders", "Percentage": "50000"},
    ]
    raw = json.dumps(payload).encode()
    out = parse.parse_bse_json(raw)
    assert abs(out["promoter_pct"] - 55.2) < 1e-6
    assert abs(out["fii_pct"] - 20.1) < 1e-6
    assert abs(out["dii_pct"] - 10.0) < 1e-6
    assert abs(out["public_pct"] - 14.7) < 1e-6
    assert out["n_shareholders"] == 50000.0


def test_parse_bse_csv_end_to_end():
    csv_text = "Category,Value\nPromoter,60.0\nPublic,40.0\n"
    out = parse.parse_bse_csv(csv_text.encode())
    assert abs(out["promoter_pct"] - 60.0) < 1e-6
    assert abs(out["public_pct"] - 40.0) < 1e-6


def test_dict_wrapped_table_key_variant():
    payload = {"Table": [{"Category": "Promoter", "Percentage": "50"},
                         {"Category": "Public", "Percentage": "50"}]}
    out = parse.parse_bse_json(json.dumps(payload).encode())
    assert out["promoter_pct"] == 50.0
    assert out["public_pct"] == 50.0


if __name__ == "__main__":
    import inspect
    mod = sys.modules[__name__]
    tests = [(name, fn) for name, fn in vars(mod).items()
            if name.startswith("test_") and callable(fn)]
    passed, failed = 0, 0
    for name, fn in tests:
        try:
            if "tmp_path" in inspect.signature(fn).parameters:
                import tempfile
                with tempfile.TemporaryDirectory() as td:
                    fn(Path(td))
            else:
                fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
    raise SystemExit(0 if failed == 0 else 1)
